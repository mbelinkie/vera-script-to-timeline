import { randomUUID } from "node:crypto";

import { snapshotResearchCandidateV2 } from "@vera/contracts/authoring-v2";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler } from "../src/api.js";
import { fingerprint } from "../src/model.js";
import { ResearchChoiceReadService } from "../src/research-choices.js";
import { SubtitleCopyService } from "../src/subtitle-copy.js";
import { documentFor, harness } from "./helpers.js";
import { researchCandidate, researchId, researchOccurrence } from "../../contracts/test/issue-367-fixture.js";

/* eslint-disable @typescript-eslint/require-await -- fake identity/Research adapters are intentionally offline */
vi.setConfig({ testTimeout: 120_000 });
const cleaners: Array<() => Promise<void>> = [];
afterEach(async () => { for (const close of cleaners.splice(0)) await close(); });
const base = "https://offline-suite.test/v1/projects";
const identity: SuiteIdentityPort = {
  authenticate: async (request) => {
    const subject = request.headers.get("X-Test-Suite-Identity");
    if (!subject) throw new Error("No trusted suite identity");
    return { issuer: "https://trusted.suite.test", subject };
  },
};

const send = (projectId: string, route: string, subject = "viewer", method = "GET",
  data?: unknown, contentType = "application/json") => new Request(`${base}/${projectId}${route}`, {
    method, headers: { "X-Test-Suite-Identity": subject,
      ...(data === undefined ? {} : { "Content-Type": contentType }) },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
const body = async <T = Record<string, unknown>>(reply: Response): Promise<T> =>
  await reply.json() as T;

async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const projectId = randomUUID();
  const first = researchOccurrence(830100, false);
  const second = researchOccurrence(830200, false);
  first.researchClip!.video.sourceLanguage = "es";
  second.researchClip!.video.sourceLanguage = "es";
  const doc = documentFor(projectId);
  doc.activeDraft.blocks = [first, second];
  await h.service.createProject(h.owner, { projectId, document: doc,
    title: "Offline subtitle QA", clientRequestId: randomUUID() });
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  const session = await h.auth.openWriteSession(projectId, h.editor);
  const current = await h.service.getDocument(projectId, h.owner);
  const candidate = researchCandidate();
  const latest = { ...candidate, version: 4, englishText: "New authorized English baseline",
    video: { ...candidate.video, sourceLanguage: "es" } };
  const reads: string[] = [];
  const researchChoices = new ResearchChoiceReadService(h.service, {
    readCurrentClip: async (_principal, _researchProjectId, clipId) => {
      reads.push(clipId);
      return latest;
    },
  });
  const api = createProjectApiHandler({ identity, authorization: h.auth, documents: h.service,
    researchChoices, subtitleCopies: new SubtitleCopyService(h.pool, h.auth, h.service) });
  const path = (id: string) => `/subtitle-copies/${id}`;
  const derive = (id: string, digest: string) => ({
    expectedDocumentRevision: 0, expectedDocumentDigest: current.digest,
    expectedSourceDigest: digest, clientMutationId: randomUUID(), writeSessionId: session,
  });
  const revise = (digest: string, expectedVersion: number) => ({
    expectedSourceDigest: digest, expectedVersion, clientMutationId: randomUUID(),
    writeSessionId: session,
  });
  return { ...h, projectId, first, second, doc, current, latest, reads, api, path, derive, revise, session };
}

describe("subtitle-copy routes with trusted synthetic identity and PGlite", () => {
  it("derives independent uses, preserves reviewed copy across reorder/Stash and safely rederives after Research choice", async () => {
    const h = await setup();
    const firstPin = fingerprint(h.first.researchClip!);
    const secondPin = fingerprint(h.second.researchClip!);
    const firstPath = h.path(h.first.id), secondPath = h.path(h.second.id);
    const preflight = await h.api(send(h.projectId, firstPath));
    expect(preflight.status).toBe(200);
    expect(await body(preflight)).toMatchObject({ binding: "not_derived", currentSourceDigest: firstPin,
      track: null });
    const create = h.derive(h.first.id, firstPin);
    const first = await h.api(send(h.projectId, firstPath + "/derive", "editor", "POST", create));
    expect(first.status).toBe(201);
    expect(await body(first)).toMatchObject({ version: 1, duplicateDelivery: false });
    expect((await h.api(send(h.projectId, firstPath + "/derive", "editor", "POST", create))).status).toBe(200);
    expect((await h.api(send(h.projectId, secondPath + "/derive", "editor", "POST",
      h.derive(h.second.id, secondPin)))).status).toBe(201);
    const edit = { operation: "edit", ...h.revise(firstPin, 1),
      englishText: "Reviewed English, independent of script order" };
    const revised = await h.api(send(h.projectId, firstPath, "editor", "PATCH", edit));
    expect(revised.status).toBe(200);
    expect(await body(revised)).toMatchObject({ version: 2 });
    const readAfterEdit = await body(await h.api(send(h.projectId, firstPath)));
    expect(readAfterEdit).toMatchObject({ binding: "current", track: { version: 2,
      source: { englishText: "Frozen English text" },
      segments: [{ englishText: edit.englishText }] } });

    // Ordinary script changes do not write the sidecar. First reorder, then move
    // the same saved occurrence into Stash without changing the frozen Research pin.
    const reordered = structuredClone(h.current.document);
    reordered.activeDraft.blocks.reverse();
    const saved = await h.api(send(h.projectId, "/document", "editor", "PUT", {
      expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId: h.session,
      document: reordered,
    }));
    expect(saved.status).toBe(200);
    const parked = structuredClone(reordered);
    parked.activeDraft.blocks = [h.second];
    parked.stash = [{ id: randomUUID(), rows: [h.first], supportingItems: [] }];
    parked.stashOutline = [{ rowId: h.first.id, kind: "clip", parentRowId: null, sectionId: null }];
    expect((await h.api(send(h.projectId, "/document", "editor", "PUT", {
      expectedRevision: 1, clientMutationId: randomUUID(), writeSessionId: h.session,
      document: parked,
    }))).status).toBe(200);
    expect(await body(await h.api(send(h.projectId, firstPath)))).toMatchObject({
      binding: "current", documentRevision: 2, digest: readAfterEdit.digest,
      track: { version: 2, segments: [{ englishText: edit.englishText }] },
    });
    expect(await body(await h.api(send(h.projectId, secondPath)))).toMatchObject({
      binding: "current", track: { version: 1, segments: [{ englishText: "Frozen English text" }] },
    });
    const history = await body<{revisions: unknown[]; nextBeforeVersion: number | null}>(
      await h.api(send(h.projectId, firstPath + "/revisions?limit=1")));
    expect(history.revisions).toMatchObject([{ version: 2, operation: "edit" }]);
    expect(history.nextBeforeVersion).toBe(2);
    const prior = await body(await h.api(send(h.projectId, firstPath + "/revisions?beforeVersion=2")));
    expect(prior.revisions).toMatchObject([{ version: 1, operation: "derive",
      track: { source: { englishText: "Frozen English text" } } }]);

    // Only the separately trusted #390 adapter may advance the saved source pin.
    const choice = await h.api(send(h.projectId, "/research-choices/choice", "editor", "POST", {
      choice: "update", occurrenceId: h.first.id, researchProjectId: researchId(710002),
      clipId: researchId(710001), expectedRevision: 2, expectedClipVersion: 3,
      expectedLatestVersion: 4, clientMutationId: randomUUID(), writeSessionId: h.session,
    }));
    expect(choice.status, await choice.text()).toBe(200);
    expect(h.reads).toEqual([researchId(710001)]);
    const stale = await body(await h.api(send(h.projectId, firstPath)));
    expect(stale).toMatchObject({ binding: "stale", track: { version: 2,
      segments: [{ englishText: edit.englishText }] } });
    expect(stale.currentSourceDigest).toBe(fingerprint(snapshotResearchCandidateV2(h.latest)));
    const blocked = await h.api(send(h.projectId, firstPath, "editor", "PATCH", {
      operation: "edit", ...h.revise(stale.currentSourceDigest as string, 2),
      englishText: "Must not silently replace accepted copy",
    }));
    expect(blocked.status).toBe(409);
    expect((await h.api(send(h.projectId, firstPath + "/rederive", "editor", "POST",
      h.revise(stale.currentSourceDigest as string, 2)))).status).toBe(200);
    const current = await body(await h.api(send(h.projectId, firstPath)));
    expect(current).toMatchObject({ binding: "current", track: { version: 3,
      reviewState: "needs_review", source: { englishText: h.latest.englishText },
      segments: [{ englishText: h.latest.englishText }] } });
    const revisions = await body<{revisions: Array<{operation: string}>}>(
      await h.api(send(h.projectId, firstPath + "/revisions")));
    expect(revisions.revisions.map((r) => r.operation))
      .toEqual(["rederive", "edit", "derive"]);
    expect(revisions.revisions[1]).toMatchObject({ track: {
      source: { englishText: "Frozen English text" }, segments: [{ englishText: edit.englishText }] } });
    expect((await h.api(send(h.projectId, secondPath))).status).toBe(200);
    expect((await h.service.listDocumentRevisions(h.projectId, h.owner)).revisions).toHaveLength(4);
  });

  it("strictly validates route, query, JSON, action, CAS, and denies forged/revoked editor replay", async () => {
    const h = await setup();
    const path = h.path(h.first.id), pin = fingerprint(h.first.researchClip!);
    const create = h.derive(h.first.id, pin);
    const unauthorized = await h.api(new Request(`${base}/${h.projectId}${path}/derive`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(create),
    }));
    expect(unauthorized.status).toBe(401);
    expect((await h.api(send(h.projectId, path + "/derive", "viewer", "POST", create))).status).toBe(403);
    for (const bad of [
      send(h.projectId, path + "/derive?ignored=1", "editor", "POST", create),
      send(h.projectId, path + "/revisions?limit=1&limit=2"),
      send(h.projectId, path + "/revisions?beforeVersion=0"),
      send(h.projectId, path + "/revisions?cursor=1"),
      send(h.projectId, path + "?extra=1"),
      send(h.projectId, path + "/derive", "editor", "POST", { ...create, source: h.first.researchClip }),
      send(h.projectId, path + "/derive", "editor", "POST", { ...create, unexpected: 1 }),
      send(h.projectId, path + "/derive", "editor", "POST", create, "text/plain"),
      send(h.projectId, path, "editor", "PATCH", { operation: "edit", ...h.revise(pin, 1) }),
      send(h.projectId, path, "editor", "PATCH", { operation: "approve", ...h.revise(pin, 1),
        englishText: "forbidden" }),
      send(h.projectId, path, "editor", "PATCH", { operation: "delete", ...h.revise(pin, 1) }),
      send(h.projectId, path + "/rederive", "editor", "POST", { ...h.revise(pin, 1),
        englishText: "not allowed" }),
    ]) expect((await h.api(bad)).status).toBe(400);
    expect((await h.api(send(h.projectId, path + "/derive", "editor", "PATCH", create))).status).toBe(404);
    expect((await h.api(send(h.projectId, path + "/revisions", "editor", "POST", create))).status).toBe(404);
    const derived = await h.api(send(h.projectId, path + "/derive", "editor", "POST", create));
    expect(derived.status).toBe(201);
    expect((await h.api(send(h.projectId, path, "editor", "PATCH", {
      operation: "approve", ...h.revise(pin, 1),
    }))).status).toBe(200);
    expect(await body(await h.api(send(h.projectId, path)))).toMatchObject({
      track: { version: 2, reviewState: "reviewed", reviewerId: h.editor.principalId },
    });
    const refused = await h.api(send(h.projectId, path, "editor", "PATCH", {
      operation: "edit", ...h.revise(pin, 1), englishText: "stale version",
    }));
    expect(refused.status).toBe(409);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, null);
    expect((await h.api(send(h.projectId, path + "/derive", "editor", "POST", create))).status).toBe(403);
    expect((await h.api(send(h.projectId, path, "editor", "PATCH", {
      operation: "approve", ...h.revise(pin, 2),
    }))).status).toBe(403);
    expect((await h.api(send(h.projectId, path + "/revisions", "editor"))).status).toBe(403);
    expect((await h.api(send(randomUUID(), path))).status).toBe(403);
    expect((await h.api(send(h.projectId, path + "/revisions"))).status).toBe(200);
  });

  it("refuses unmounted subtitle capability rather than using a network/provider fallback", async () => {
    const h = await setup();
    const disabled = createProjectApiHandler({ identity, authorization: h.auth, documents: h.service });
    expect((await disabled(send(h.projectId, h.path(h.first.id)))).status).toBe(503);
    expect((await disabled(send(h.projectId, h.path(h.first.id) + "/derive", "editor", "POST",
      h.derive(h.first.id, fingerprint(h.first.researchClip!))))).status).toBe(503);
    expect((await h.api(send(h.projectId, h.path(randomUUID())))).status).toBe(404);
    expect((await h.api(send(h.projectId, h.path(h.first.id) + "/revisions"))).status).toBe(404);
  });
});
