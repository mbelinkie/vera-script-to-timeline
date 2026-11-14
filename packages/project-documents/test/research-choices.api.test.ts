import { randomUUID } from "node:crypto";

import { createResearchClipOccurrenceV2 } from "@vera/contracts/authoring-v2";
import type { PrincipalRef } from "@vera/contracts";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler } from "../src/api.js";
import {
  enumerateResearchOccurrences, ResearchChoiceReadService, ResearchReadDeniedError,
  type ResearchAuthorizedReadPort,
} from "../src/research-choices.js";
import { documentFor, harness } from "./helpers.js";
import { researchCandidate, researchId, researchNote, researchOccurrence } from "../../contracts/test/issue-367-fixture.js";

/* eslint-disable @typescript-eslint/require-await -- trusted test-only authorization adapters */
vi.setConfig({ testTimeout: 90_000 });
const cleaners: Array<() => Promise<void>> = [];
afterEach(async () => { for (const close of cleaners.splice(0)) await close(); });
const base = "https://local.stt.test/v1/projects";
const identity: SuiteIdentityPort = {
  authenticate: async (request) => {
    const subject = request.headers.get("X-Test-Suite-Identity");
    if (!subject) throw new Error("No suite identity");
    return { issuer: "https://trusted.suite.test", subject };
  },
};

const request = (path: string, subject = "viewer", method = "GET") =>
  new Request(base + path, { method, headers: { "X-Test-Suite-Identity": subject } });

async function json(response: Response): Promise<Record<string, unknown>> {
  const result: unknown = await response.json();
  if (result === null || typeof result !== "object" || Array.isArray(result)) throw new Error("Invalid object");
  return result as Record<string, unknown>;
}

async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const projectId = randomUUID();
  const document = documentFor(projectId);
  const first = researchOccurrence(730100, false);
  const second = researchOccurrence(730200, false);
  const different = createResearchClipOccurrenceV2({
    rowId: researchId(730300), payloadId: researchId(730301), orderKey: "different",
    candidate: { ...researchCandidate(), id: researchId(710009) },
  });
  document.activeDraft.blocks = [first, second];
  const bundleId = randomUUID();
  document.stash = [{ id: bundleId, rows: [different], supportingItems: [] }];
  document.stashOutline = [{ rowId: different.id, kind: "clip", parentRowId: null, sectionId: null }];
  await h.service.createProject(h.owner, {
    projectId, document, title: "Read compare", clientRequestId: randomUUID(),
  });
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  const allowed = new Set([h.owner.principalId, h.viewer.principalId]);
  const calls: Array<{ principal: PrincipalRef; projectId: string; clipId: string }> = [];
  let candidate: unknown = { ...researchCandidate(), version: 4,
    englishText: "Changed text in Research" };
  let other: unknown = { ...researchCandidate(), id: researchId(710009), version: 4 };
  let override: ((id: string, principal: PrincipalRef) => Promise<unknown>) | undefined;
  const port: ResearchAuthorizedReadPort = {
    readCurrentClip: async (principal, researchProjectId, clipId) => {
      calls.push({ principal, projectId: researchProjectId, clipId });
      if (!allowed.has(principal.principalId)) throw new ResearchReadDeniedError();
      if (override) return await override(clipId, principal);
      return clipId === researchId(710009) ? other : candidate;
    },
  };
  const choices = new ResearchChoiceReadService(h.service, port);
  const api = createProjectApiHandler({ identity, authorization: h.auth,
    documents: h.service, researchChoices: choices });
  return {
    ...h, projectId, first, second, different, document, bundleId,
    allowed, calls, api, port, choices,
    setCandidate: (value: unknown) => { candidate = value; },
    setOther: (value: unknown) => { other = value; },
    override: (callback: typeof override) => { override = callback; },
  };
}

describe("Research choices: independent authorized GET/compare", () => {
  it("compares repeat pins and Stash independently, dedupes only within a request, and never writes", async () => {
    const h = await setup();
    const path = `/${h.projectId}/research-choices`;
    const original = await h.service.getDocument(h.projectId, h.viewer);
    const page = await h.api(request(path));
    expect(page.status).toBe(200);
    expect(page.headers.get("Cache-Control")).toBe("no-store");
    expect(await json(page)).toMatchObject({ revision: 0, digest: original.digest,
      occurrences: [
        { occurrenceId: h.first.id, pinnedVersion: 3, latestVersion: 4,
          state: "update_available", changedFields: ["englishText"] },
        { occurrenceId: h.second.id, pinnedVersion: 3, latestVersion: 4,
          state: "update_available", changedFields: ["englishText"] },
        { occurrenceId: h.different.id, location: { kind: "stash_visual", stashBundleId: h.bundleId },
          pinnedVersion: 3, latestVersion: 4, state: "update_available", changedFields: [] },
      ],
    });
    expect(h.calls).toHaveLength(2); // two Research ids; repeated uses never disappear
    expect(h.calls.every((call) => call.principal.principalId === h.viewer.principalId)).toBe(true);
    expect(h.calls[0]).toMatchObject({ projectId: researchId(710002), clipId: researchId(710001) });

    const compare = await h.api(request(path + `/compare?occurrenceId=${h.second.id}`));
    expect(compare.status).toBe(200);
    expect(await json(compare)).toMatchObject({ revision: 0, occurrenceId: h.second.id,
      assessment: { kind: "update_available", changedFields: ["englishText"],
        pinned: { clipVersion: 3, englishText: "Frozen English text" },
        latest: { clipVersion: 4, englishText: "Changed text in Research" } } });
    expect(h.calls).toHaveLength(3); // no persistent Research cache
    expect(await h.service.getDocument(h.projectId, h.viewer)).toEqual(original);
    expect((await h.service.listDocumentRevisions(h.projectId, h.viewer)).revisions).toHaveLength(1);
  });

  it("checks Timeline before Research, independently denies Research, and discloses no earlier clips", async () => {
    const h = await setup();
    const path = `/${h.projectId}/research-choices`;
    expect((await h.api(request(path, "editor"))).status).toBe(403);
    expect(h.calls).toHaveLength(0);
    h.allowed.delete(h.viewer.principalId);
    const denied = await h.api(request(path));
    expect(denied.status).toBe(403);
    expect(await json(denied)).toEqual({ error: "action_not_allowed" });
    h.allowed.add(h.viewer.principalId);
    h.override(async (clipId) => {
      if (clipId === researchId(710009)) throw new ResearchReadDeniedError();
      return { ...researchCandidate(), version: 4, englishText: "secret earlier result" };
    });
    const partial = await h.api(request(path));
    expect(partial.status).toBe(403);
    expect(JSON.stringify(await json(partial))).not.toContain("secret earlier result");
    expect((await h.api(request(path + `/compare?occurrenceId=${h.different.id}`))).status).toBe(403);
    expect((await h.service.getDocument(h.projectId, h.owner)).revision).toBe(0);
  });

  it("fails closed for unavailable, malformed and mismatched Research, and preserves safe errors", async () => {
    const h = await setup();
    const path = `/${h.projectId}/research-choices`;
    h.override(async () => { throw new Error("secret token and transcript"); });
    for (const route of [path, path + `/compare?occurrenceId=${h.first.id}`]) {
      const failed = await h.api(request(route));
      expect(failed.status).toBe(503);
      expect(await json(failed)).toEqual({ error: "service_unavailable" });
    }
    h.override(undefined);
    for (const malformed of [null, {}, { ...researchCandidate(), version: "4" },
      { ...researchCandidate(), id: randomUUID() }]) {
      h.setCandidate(malformed);
      expect((await h.api(request(path))).status).toBe(503);
    }
    h.setCandidate({ ...researchCandidate(), version: 3, englishText: "same version drift" });
    expect(await json(await h.api(request(path + `/compare?occurrenceId=${h.first.id}`))))
      .toMatchObject({ assessment: { kind: "inconsistent", reason: "same_version_changed" } });
    h.setCandidate({ ...researchCandidate(), version: 2 });
    expect(await json(await h.api(request(path + `/compare?occurrenceId=${h.first.id}`))))
      .toMatchObject({ assessment: { kind: "inconsistent", reason: "older_version" } });
    h.setCandidate(researchCandidate());
    expect(await json(await h.api(request(path + `/compare?occurrenceId=${h.first.id}`))))
      .toMatchObject({ assessment: { kind: "current" } });
    expect((await h.service.getDocument(h.projectId, h.viewer)).revision).toBe(0);
  });

  it("rechecks Timeline permission and head after Research read; enforces strict GET shapes", async () => {
    const h = await setup();
    const path = `/${h.projectId}/research-choices`;
    h.override(async (clipId) => {
      await h.auth.changeMembership(h.projectId, h.owner, h.viewer.principalId, null);
      return clipId === researchId(710009) ? { ...researchCandidate(), id: clipId } : researchCandidate();
    });
    expect((await h.api(request(path))).status).toBe(403);
    await h.auth.changeMembership(h.projectId, h.owner, h.viewer.principalId, "viewer");
    h.override(undefined);
    expect((await h.api(request(path + "?x=1"))).status).toBe(400);
    expect((await h.api(request(path + `/compare?occurrenceId=${h.first.id}&occurrenceId=${h.second.id}`))).status).toBe(400);
    expect((await h.api(request(path + "/compare"))).status).toBe(400);
    expect((await h.api(request(path + "/compare?occurrenceId=invalid"))).status).toBe(400);
    expect((await h.api(request(path + `/compare?occurrenceId=${randomUUID()}`))).status).toBe(404);
    expect((await h.api(request(path, "viewer", "POST"))).status).toBe(404);
    expect((await h.api(new Request(base + path))).status).toBe(401);
    const unmounted = createProjectApiHandler({ identity, authorization: h.auth, documents: h.service });
    expect((await unmounted(request(path))).status).toBe(503);
    expect((await unmounted(request(path, "viewer", "POST"))).status).toBe(404);
  });

  it("refuses a comparison if the Timeline head changes while Research is being read", async () => {
    const h = await setup();
    const original = await h.service.getDocument(h.projectId, h.owner);
    h.override(async () => {
      await h.service.putDocument(h.projectId, h.owner, {
        expectedRevision: 0, clientMutationId: randomUUID(),
        document: { ...original.document, title: "Concurrent title edit" },
      });
      return { ...researchCandidate(), version: 4 };
    });
    const result = await h.api(request(`/${h.projectId}/research-choices/compare?occurrenceId=${h.first.id}`));
    expect(result.status).toBe(409);
    expect(await json(result)).toEqual({ error: "version_conflict" });
    expect((await h.service.getDocument(h.projectId, h.owner)).revision).toBe(1);
  });

  it("enumerates nested primary, overlay, attached clip, and mirror without double-counting", () => {
    const note = researchNote(740200);
    const clip = researchOccurrence(740300, false);
    note.attachedFootage = { clip };
    note.stashOrigin = { kind: "note", returnEligible: true,
      parentRowId: null, sectionId: null, afterSiblingRowId: null, beforeSiblingRowId: null };
    const source = clip.payload.source;
    const slot = note.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content") throw new Error("Expected content slot");
    slot.payload = { kind: "visual", payloadId: researchId(740400), pictureKind: "unresolved_visual",
      source, sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
      researchClip: clip.researchClip! };
    note.overlayEvents = [{ id: researchId(740500), version: 1, payload: {
      kind: "visual", payloadId: researchId(740501), pictureKind: "unresolved_visual",
      source, sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
      researchClip: clip.researchClip!,
    }, timing: { kind: "timed", durationMs: 1000, start: { kind: "word", anchor: {
      blockId: note.id, tokenId: note.tokens[0]!.id, affinity: "before", quotedWord: "Look", anchorVersion: 1,
    } } } }];
    const doc = documentFor(randomUUID());
    doc.activeDraft.blocks.push(note);
    expect(enumerateResearchOccurrences(doc).map((x) => x.occurrenceId))
      .toEqual([clip.id, researchId(740501)]);
    delete note.stashOrigin;
    expect(enumerateResearchOccurrences(doc).map((x) => x.occurrenceId))
      .toEqual([clip.id, researchId(740400), researchId(740501)]);
  });
});
