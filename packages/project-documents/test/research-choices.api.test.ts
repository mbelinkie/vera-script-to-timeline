import { randomUUID } from "node:crypto";

import { createResearchClipOccurrenceV2, snapshotResearchCandidateV2 } from "@vera/contracts/authoring-v2";
import type { PrincipalRef } from "@vera/contracts";
import type { NarrationBlockV2 } from "@vera/contracts/v2";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler } from "../src/api.js";
import {
  enumerateResearchOccurrences, updateResearchOccurrence, ResearchChoiceReadService, ResearchReadDeniedError,
  type ResearchAuthorizedReadPort,
} from "../src/research-choices.js";
import { documentFor, harness } from "./helpers.js";
import { researchCandidate, researchId, researchNote, researchOccurrence,
  researchNestedNote, researchMirroredNote } from "../../contracts/test/issue-367-fixture.js";
import { attachVisualToWordsV2 } from "../../contracts/src/authoring-v2-visual-lifecycle.js";
import { toNarratedPlacementV2 } from "../../contracts/src/authoring-v2-wordless.js";

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
  const first = researchOccurrence(730100, true);
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

const choiceRequest = (projectId: string, data: Record<string, unknown>, subject = "owner") =>
  new Request(`${base}/${projectId}/research-choices/choice`, {
    method: "POST", headers: { "X-Test-Suite-Identity": subject, "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

const choice = (occurrenceId: string, choiceKind: "keep" | "update", expectedRevision = 0,
  clientMutationId?: string) => ({
    choice: choiceKind, occurrenceId, researchProjectId: researchId(710002), clipId: researchId(710001),
    expectedRevision, expectedClipVersion: 3, expectedLatestVersion: 4,
    ...(clientMutationId ? { clientMutationId } : {}),
  });

describe("Research choices: explicit keep/update CAS", () => {
  it("compares, keeps, and updates Research visuals waiting for words in active and Stash rows (#727)", async () => {
    const h = await setup();
    const next = structuredClone(h.document);
    const waitingRow = (n: number): NarrationBlockV2 => {
      const row = researchNote(n);
      delete row.plainDirection;
      row.tokens.forEach((token) => { token.spoken = true; });
      row.unattachedVisuals = [n + 20, n + 40].map((id) => {
        const clip = researchOccurrence(id, true);
        const converted = toNarratedPlacementV2(clip);
        if (!("value" in converted)) throw new Error(converted.message);
        return { slotId: researchId(id + 2), payload: converted.value, version: 3 };
      });
      return row;
    };
    const active = waitingRow(790100);
    const stashed = waitingRow(790200);
    next.activeDraft.blocks.push(active);
    next.stash![0]!.rows.push(stashed);
    next.stashOutline!.push({ rowId: stashed.id, kind: "row", parentRowId: null, sectionId: null });
    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: 0, clientMutationId: randomUUID(), document: next,
    });
    const before = await h.service.getDocument(h.projectId, h.owner);
    const route = `/${h.projectId}/research-choices`;
    const expectedOwners = [h.first.id, h.second.id, ...active.unattachedVisuals!.map((v) => v.payload.payloadId),
      h.different.id, ...stashed.unattachedVisuals!.map((v) => v.payload.payloadId)];
    expect(enumerateResearchOccurrences(before.document).map((v) => v.occurrenceId)).toEqual(expectedOwners);
    expect((await json(await h.api(request(route)))).occurrences)
      .toMatchObject(expectedOwners.map((occurrenceId) => ({ occurrenceId })));
    let revision = 1;
    for (const row of [active, stashed]) {
      const index = row === active ? 0 : 1;
      const waiting = row.unattachedVisuals![index]!;
      const target = waiting.payload.payloadId;
      const location = { kind: row === active ? "active_primary" : "stash_primary",
        rowId: row.id, slotId: waiting.slotId, ...(row === stashed ? { stashBundleId: h.bundleId } : {}) };
      expect(await json(await h.api(request(`${route}/compare?occurrenceId=${target}`))))
        .toMatchObject({ occurrenceId: target, location, assessment: { kind: "update_available",
          pinned: { clipVersion: 3 }, latest: { clipVersion: 4 } } });
      const preChoice = await h.service.getDocument(h.projectId, h.owner);
      expect((await h.api(choiceRequest(h.projectId, choice(target, "keep", revision)))).status).toBe(200);
      expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(preChoice);
      const update = await h.api(choiceRequest(h.projectId, choice(target, "update", revision, randomUUID())));
      expect(update.status, await update.text()).toBe(200);
      const after = await h.service.getDocument(h.projectId, h.owner);
      expect(after.revision).toBe(++revision);
      const expected = structuredClone(preChoice.document);
      const changed = (row === active ? expected.activeDraft.blocks : expected.stash![0]!.rows)
        .find((block) => block.id === row.id);
      if (changed?.type !== "narration") throw new Error("Expected narration row");
      const selected = changed.unattachedVisuals![index]!;
      selected.payload.researchClip = snapshotResearchCandidateV2({ ...researchCandidate(), version: 4,
        englishText: "Changed text in Research" });
      delete selected.payload.frameBinding;
      delete selected.payload.selectedSourceRange;
      selected.payload.pictureKind = "unresolved_visual";
      selected.payload.source = { kind: "unresolved_visual", description: "Research clip lacks verified Timeline media/frame binding" };
      selected.payload.sourceUsage = null;
      selected.version++;
      changed.primaryVisualSequence!.version++;
      changed.version++;
      expect(after.document.activeDraft).toEqual(expected.activeDraft);
      expect(after.document.stash).toEqual(expected.stash);
      expect(after.document.stashOutline).toEqual(expected.stashOutline);
      expect(enumerateResearchOccurrences(after.document).map((v) => v.occurrenceId)).toEqual(expectedOwners);
      expect(await h.service.getDocumentRevision(h.projectId, h.owner, preChoice.revision))
        .toMatchObject({ document: preChoice.document, digest: preChoice.digest });
    }
    const reattached = structuredClone((await h.service.getDocument(h.projectId, h.owner)).document);
    const row = reattached.activeDraft.blocks.find((block) => block.id === active.id);
    if (row?.type !== "narration") throw new Error("Expected narration row");
    const waiting = row.unattachedVisuals![0]!;
    const attached = attachVisualToWordsV2(row, waiting.slotId, row.tokens[0]!.id, row.tokens[1]!.id);
    if (!("payloadIds" in attached)) throw new Error(attached.message);
    expect(attached.payloadIds).toContain(waiting.payload.payloadId);
    row.version++;
    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: revision, clientMutationId: randomUUID(), document: reattached,
    });
    const saved = await h.service.getDocument(h.projectId, h.owner);
    expect(enumerateResearchOccurrences(saved.document).find((v) => v.occurrenceId === waiting.payload.payloadId))
      .toMatchObject({ pinned: { clipVersion: 4 }, location: { kind: "active_primary", rowId: row.id, slotId: waiting.slotId } });
  });

  it("compares, keeps and updates individual additional visuals in active and Stash stacks (#718)", async () => {
    const h = await setup();
    const next = structuredClone(h.document);
    const active = next.activeDraft.blocks[0];
    const stashed = next.stash![0]!.rows[0];
    if (active?.type !== "visual_only" || stashed?.type !== "visual_only") throw new Error("Expected visual rows");
    const placement = (n: number) => {
      const clip = researchOccurrence(n, true);
      return { payload: clip.payload, visualOnlyTiming: clip.visualOnlyTiming,
        researchClip: clip.researchClip!, frameBinding: clip.frameBinding! };
    };
    active.additionalVisuals = [placement(780100), placement(780200)];
    stashed.additionalVisuals = [placement(780300), placement(780400)];
    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: 0, clientMutationId: randomUUID(), document: next,
    });
    const before = await h.service.getDocument(h.projectId, h.owner);
    const route = `/${h.projectId}/research-choices`;
    const expectedOwners = [active.id, ...active.additionalVisuals.map((v) => v.payload.payloadId),
      h.second.id, stashed.id, ...stashed.additionalVisuals.map((v) => v.payload.payloadId)];
    expect(enumerateResearchOccurrences(before.document).map((v) => v.occurrenceId)).toEqual(expectedOwners);
    const listing = await json(await h.api(request(route)));
    expect(listing.occurrences).toMatchObject(expectedOwners.map((occurrenceId) => ({ occurrenceId })));
    let revision = 1;
    for (const row of [active, stashed]) {
      const index = row === active ? 0 : 1;
      const child = row.additionalVisuals![index]!;
      const target = child.payload.payloadId;
      const location = row === active ? { kind: "active_visual", rowId: row.id } :
        { kind: "stash_visual", rowId: row.id, stashBundleId: h.bundleId };
      expect(await json(await h.api(request(`${route}/compare?occurrenceId=${target}`))))
        .toMatchObject({ occurrenceId: target, location, assessment: { kind: "update_available",
          pinned: { clipVersion: 3 }, latest: { clipVersion: 4 } } });
      const preChoice = await h.service.getDocument(h.projectId, h.owner);
      expect((await h.api(choiceRequest(h.projectId, choice(target, "keep", revision)))).status).toBe(200);
      expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(preChoice);
      const update = await h.api(choiceRequest(h.projectId, choice(target, "update", revision, randomUUID())));
      expect(update.status, await update.text()).toBe(200);
      const after = await h.service.getDocument(h.projectId, h.owner);
      expect(after.revision).toBe(++revision);
      const expected = structuredClone(preChoice.document);
      const changed = row === active ? expected.activeDraft.blocks[0] : expected.stash![0]!.rows[0];
      if (changed?.type !== "visual_only") throw new Error("Expected visual row");
      const selected = changed.additionalVisuals![index]!;
      selected.researchClip = snapshotResearchCandidateV2({ ...researchCandidate(), version: 4,
        englishText: "Changed text in Research" });
      delete selected.frameBinding;
      delete selected.visualOnlyTiming.selectedSourceRange;
      selected.payload.pictureKind = "unresolved_visual";
      selected.payload.source = { kind: "unresolved_visual", description: "Research clip lacks verified Timeline media/frame binding" };
      changed.version++;
      expect(after.document.activeDraft).toEqual(expected.activeDraft);
      expect(after.document.stash).toEqual(expected.stash);
      expect(after.document.stashOutline).toEqual(expected.stashOutline);
      expect(enumerateResearchOccurrences(after.document).map((v) => v.occurrenceId)).toEqual(expectedOwners);
      expect(await h.service.getDocumentRevision(h.projectId, h.owner, preChoice.revision))
        .toMatchObject({ document: preChoice.document, digest: preChoice.digest });
      expect(await h.service.getDocumentRevision(h.projectId, h.owner, 1))
        .toMatchObject({ document: before.document, digest: before.digest });
    }
    // Removing one additional placement is a normal edit, not a change to the
    // root or the other child merely because they share the same row location.
    const afterChoices = await h.service.getDocument(h.projectId, h.owner);
    const removed = structuredClone(afterChoices.document);
    const stack = removed.activeDraft.blocks[0];
    if (stack?.type !== "visual_only") throw new Error("Expected visual row");
    const removedId = stack.additionalVisuals![0].payload.payloadId;
    stack.additionalVisuals = [stack.additionalVisuals![1]!];
    stack.version++;
    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: revision, clientMutationId: randomUUID(), document: removed,
    });
    const afterRemoval = await h.service.getDocument(h.projectId, h.owner);
    expect(afterRemoval.document).toEqual(removed);
    expect(enumerateResearchOccurrences(afterRemoval.document).map((v) => v.occurrenceId))
      .toEqual(expectedOwners.filter((id) => id !== removedId));
  });

  it("lists and independently updates nested visuals, the active mirror and grouped/attached Stash owners", async () => {
    const h = await setup();
    const original = await h.service.getDocument(h.projectId, h.owner);
    const next = structuredClone(original.document);
    const nested = researchNestedNote(760100);
    const mirrored = researchMirroredNote(760200);
    const grouped = [researchOccurrence(760300, false), researchOccurrence(760400, false)];
    const parked = researchNote(760700);
    parked.attachedFootage = { clip: researchOccurrence(760720, false) };
    const groupId = researchId(760600);
    next.activeDraft.blocks.push(nested, mirrored);
    next.stash!.push({ id: researchId(760500), rows: [grouped[0]!, grouped[1]!, parked], supportingItems: [] });
    next.stashOutline!.push(...grouped.map((row) => ({ rowId: row.id,
      kind: "row" as const, parentRowId: null, sectionId: null })),
    { rowId: parked.id, kind: "note", parentRowId: null, sectionId: null });
    next.stashGroups = [{ id: groupId, rowIds: [grouped[0]!.id, grouped[1]!.id] }];
    // Compact items are independent saved occurrences, not active clip uses.
    next.stashResearchItems = [{
      id: researchId(760800), sectionId: null, noteRowId: parked.id, kind: "quote",
      quote: {
        researchQuoteId: researchId(760801), researchProjectId: researchId(760802), researchSourceId: researchId(760803),
        researchQuoteVersion: 2, spokenText: "Original quote words", displayText: "Edited quote words",
        speakerName: "Synthetic speaker", speakerTitle: "", citationText: "Synthetic citation",
        italicSpan: null, templateRevision: "template-v1",
      },
      background: null,
    }];

    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: 0, clientMutationId: randomUUID(), document: next,
    });
    const frozen = await h.service.getDocument(h.projectId, h.owner);
    const checkpointId = randomUUID();
    await h.service.createCheckpoint(h.projectId, h.owner, {
      checkpointId, sourceRevision: 1, clientMutationId: randomUUID(), name: "All Research surfaces",
    });
    const checkpoint = await h.service.getCheckpoint(h.projectId, h.owner, checkpointId);
    const route = `/${h.projectId}/research-choices`;
    const listing = await json(await h.api(request(route)));
    const occurrences = listing.occurrences as Array<{ occurrenceId: string; location: {kind: string} }>;
    expect(occurrences).toHaveLength(9);
    expect(occurrences.filter((item) => item.location.kind === "active_attachment"))
      .toMatchObject([{ occurrenceId: mirrored.attachedFootage!.clip.id,
        location: { kind: "active_attachment", rowId: mirrored.id } }]);
    expect(occurrences.map((item) => item.location.kind)).toEqual([
      "active_visual", "active_visual", "active_primary", "active_overlay", "active_attachment",
      "stash_visual", "stash_visual", "stash_visual", "stash_attachment",
    ]);
    const targets = [
      (nested.primaryVisualSequence!.slots[0] as {payload: {payloadId: string}}).payload.payloadId,
      nested.overlayEvents[0]!.payload.payloadId,
      mirrored.attachedFootage!.clip.id, grouped[0]!.id, grouped[1]!.id,
      parked.attachedFootage.clip.id,
    ];
    const authorizedLatest = snapshotResearchCandidateV2({ ...researchCandidate(), version: 4 });
    for (const target of targets) {
      // The very same structure is legal when the authorized choice owns it,
      // but never when submitted as an ordinary whole-document PUT.
      const illegal = updateResearchOccurrence(frozen.document, target, authorizedLatest);
      const refused = await h.api(new Request(`${base}/${h.projectId}/document`, {
        method: "PUT", headers: { "X-Test-Suite-Identity": "owner", "Content-Type": "application/json" },
        body: JSON.stringify({ expectedRevision: 1, clientMutationId: randomUUID(), document: illegal }),
      }));
      expect(refused.status).toBe(409);
      expect(await json(refused)).toEqual({ error: "version_conflict" });
    }
    for (const kind of ["primary", "overlay"] as const) {
      // A caller cannot disguise a retarget as a new occurrence ID while
      // retaining the same saved slot or overlay event ownership.
      const swapped = structuredClone(frozen.document);
      const row = swapped.activeDraft.blocks.find((block) => block.id === nested.id) as NarrationBlockV2;
      const slot = row.primaryVisualSequence!.slots[0]!;
      if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Expected visual slot");
      const payload = kind === "primary" ? slot.payload : row.overlayEvents[0]!.payload;
      payload.payloadId = randomUUID();
      payload.researchClip = structuredClone(authorizedLatest);
      const refused = await h.api(new Request(`${base}/${h.projectId}/document`, {
        method: "PUT", headers: { "X-Test-Suite-Identity": "owner", "Content-Type": "application/json" },
        body: JSON.stringify({ expectedRevision: 1, clientMutationId: randomUUID(), document: swapped }),
      }));
      expect(refused.status).toBe(409);
    }
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(frozen);
    let revision = 1;
    for (const target of targets) {
      const response = await h.api(choiceRequest(h.projectId,
        choice(target, "update", revision, randomUUID())));
      expect(response.status, `Failed Research owner ${target}: ${await response.text()}`).toBe(200);
      revision++;
      const current = await h.service.getDocument(h.projectId, h.owner);
      expect(current.revision).toBe(revision);
      expect(enumerateResearchOccurrences(current.document).find((owner) => owner.occurrenceId === target)
        ?.pinned.clipVersion).toBe(4);
    }
    const after = await h.service.getDocument(h.projectId, h.owner);
    const activeMirror = after.document.activeDraft.blocks.find((block) => block.id === mirrored.id) as NarrationBlockV2;
    const slot = activeMirror.primaryVisualSequence!.slots[0]!;
    expect(activeMirror.attachedFootage!.clip.frameBinding).toBeUndefined();
    expect(activeMirror.attachedFootage!.clip.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Expected mirror");
    expect(slot.payload.researchClip).toEqual(activeMirror.attachedFootage!.clip.researchClip);
    expect(slot.payload.frameBinding).toBeUndefined();
    expect(slot.payload.sourceUsage).toBeNull();
    expect(slot.payload.selectedSourceRange).toBeUndefined();
    expect(after.document.stashGroups).toEqual(next.stashGroups);
    expect(frozen.document.stashResearchItems).toEqual(next.stashResearchItems);
    expect(after.document.stashResearchItems).toEqual(next.stashResearchItems);
    expect((await h.service.getDocumentRevision(h.projectId, h.owner, 1)).document).toEqual(frozen.document);
    expect(await h.service.getCheckpoint(h.projectId, h.owner, checkpointId)).toEqual(checkpoint);
    // Different saved uses of the same Research clip remain pinned independently.
    expect(enumerateResearchOccurrences(after.document).filter((owner) => owner.pinned.clipVersion === 3))
      .toHaveLength(3);
  });
  it("keeps byte-stable, including old verified frames, history and a later available update", async () => {
    const h = await setup();
    const before = await h.service.getDocument(h.projectId, h.owner);
    const checkpointId = randomUUID();
    await h.service.createCheckpoint(h.projectId, h.owner, {
      checkpointId, sourceRevision: 0, clientMutationId: randomUUID(), name: "Before choice",
    });
    const oldCheckpoint = await h.service.getCheckpoint(h.projectId, h.owner, checkpointId);
    const keep = await h.api(choiceRequest(h.projectId, choice(h.first.id, "keep")));
    expect(keep.status).toBe(200);
    expect(await json(keep)).toMatchObject({ revision: 0, digest: before.digest });
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(before);
    expect(await h.service.getCheckpoint(h.projectId, h.owner, checkpointId)).toEqual(oldCheckpoint);
    expect((await h.service.listDocumentRevisions(h.projectId, h.owner)).revisions).toHaveLength(1);
    const again = await h.api(choiceRequest(h.projectId, choice(h.first.id, "keep")));
    expect(again.status).toBe(200);
    expect((await json(await h.api(request(`/${h.projectId}/research-choices`)))).occurrences)
      .toMatchObject([
        { state: "update_available", pinnedVersion: 3 },
        { state: "update_available", pinnedVersion: 3 },
        { state: "update_available", pinnedVersion: 3 },
      ]);
  });

  it("updates only one chosen use; invalidates version-bound media and preserves immutable revisions", async () => {
    const h = await setup();
    const before = await h.service.getDocument(h.projectId, h.owner);
    const checkpointId = randomUUID();
    await h.service.createCheckpoint(h.projectId, h.owner, {
      checkpointId, sourceRevision: 0, clientMutationId: randomUUID(), name: "Frozen before update",
    });
    const savedCheckpoint = await h.service.getCheckpoint(h.projectId, h.owner, checkpointId);
    const mutationId = randomUUID();
    const update = await h.api(choiceRequest(h.projectId, choice(h.first.id, "update", 0, mutationId)));
    expect(update.status).toBe(200);
    expect(await json(update)).toMatchObject({ revision: 1, clientMutationId: mutationId,
      duplicateDelivery: false });
    const after = await h.service.getDocument(h.projectId, h.owner);
    expect(after.revision).toBe(1);
    const [first, second] = after.document.activeDraft.blocks;
    if (first?.type !== "visual_only" || second?.type !== "visual_only") throw new Error("Invalid fixture");
    expect(first.researchClip).toMatchObject({ clipVersion: 4,
      englishText: "Changed text in Research" });
    expect(first.frameBinding).toBeUndefined();
    expect(first.payload.pictureKind).toBe("unresolved_visual");
    expect(first.payload.source.kind).toBe("unresolved_visual");
    expect(first.payload.framingPolicy).toBeUndefined();
    expect(first.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    expect(first.version).toBe(h.first.version + 1);
    expect(second).toEqual(h.second);
    expect(after.document.stash).toEqual(before.document.stash);
    expect(await h.service.getDocumentRevision(h.projectId, h.owner, 0))
      .toMatchObject({ document: before.document, digest: before.digest });
    expect(await h.service.getCheckpoint(h.projectId, h.owner, checkpointId)).toEqual(savedCheckpoint);
    expect((await h.service.listDocumentRevisions(h.projectId, h.owner)).revisions).toHaveLength(2);
    // A same request (including a later delivery after the head advanced) returns the saved receipt.
    const duplicate = await h.api(choiceRequest(h.projectId,
      choice(h.first.id, "update", 0, mutationId)));
    expect(duplicate.status).toBe(200);
    expect(await json(duplicate)).toMatchObject({ revision: 1, digest: after.digest,
      duplicateDelivery: true });
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(after);
    // Even another occurrence of the same Research clip cannot reuse the mutation ID.
    const differing = await h.api(choiceRequest(h.projectId,
      choice(h.second.id, "update", 0, mutationId)));
    expect(differing.status).toBe(409);
    expect(await json(differing)).toEqual({ error: "idempotency_conflict" });
    await h.service.putDocument(h.projectId, h.owner, {
      expectedRevision: 1, clientMutationId: randomUUID(),
      document: { ...after.document, activeDraft: {
        ...after.document.activeDraft, blocks: [after.document.activeDraft.blocks[1]!],
      } },
    });
    // A late duplicate delivery still uses the immutable receipt after its
    // target occurrence has legitimately been removed by another edit.
    const replayAfterDeletion = await h.api(choiceRequest(h.projectId,
      choice(h.first.id, "update", 0, mutationId)));
    expect(replayAfterDeletion.status).toBe(200);
    expect(await json(replayAfterDeletion)).toMatchObject({ revision: 1, digest: after.digest,
      duplicateDelivery: true });
  });

  it("refuses stale head, Research version races, old pin, revoked Research and Timeline edit grants", async () => {
    const h = await setup();
    const input = choice(h.first.id, "update", 0, randomUUID());
    const initial = await h.service.getDocument(h.projectId, h.owner);
    expect((await h.api(choiceRequest(h.projectId, { ...input, expectedClipVersion: 2 }))).status).toBe(409);
    h.setCandidate({ ...researchCandidate(), version: 5 });
    expect((await h.api(choiceRequest(h.projectId, input))).status).toBe(409);
    h.setCandidate({ ...researchCandidate(), version: 4 });
    h.allowed.delete(h.owner.principalId);
    const refused = await h.api(choiceRequest(h.projectId, input));
    expect(refused.status).toBe(403);
    expect(await json(refused)).toEqual({ error: "action_not_allowed" });
    h.allowed.add(h.owner.principalId);
    const callsBefore = h.calls.length;
    expect((await h.api(choiceRequest(h.projectId, input, "viewer"))).status).toBe(403);
    expect(h.calls).toHaveLength(callsBefore);
    h.override(async () => {
      await h.service.putDocument(h.projectId, h.owner, {
        expectedRevision: 0, clientMutationId: randomUUID(),
        document: { ...initial.document, title: "Concurrent edit" },
      });
      return { ...researchCandidate(), version: 4 };
    });
    expect((await h.api(choiceRequest(h.projectId, input))).status).toBe(409);
    const afterRace = await h.service.getDocument(h.projectId, h.owner);
    expect(afterRace.revision).toBe(1);
    expect(afterRace.document.activeDraft.blocks).toEqual(initial.document.activeDraft.blocks);
    h.override(undefined);
    expect((await h.api(choiceRequest(h.projectId, input))).status).toBe(409);
    expect((await h.service.listDocumentRevisions(h.projectId, h.owner)).revisions).toHaveLength(2);
  });

  it("rejects revoked replay even when its receipt was committed", async () => {
    const h = await setup();
    const input = choice(h.first.id, "update", 0, randomUUID());
    expect((await h.api(choiceRequest(h.projectId, input))).status).toBe(200);
    const after = await h.service.getDocument(h.projectId, h.owner);
    h.allowed.delete(h.owner.principalId);
    expect((await h.api(choiceRequest(h.projectId, input))).status).toBe(403);
    h.allowed.add(h.owner.principalId);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "editor");
    const byEditor = choice(h.second.id, "update", 1, randomUUID());
    expect((await h.api(choiceRequest(h.projectId, byEditor, "editor"))).status).toBe(403);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, null);
    expect((await h.api(choiceRequest(h.projectId, byEditor, "editor"))).status).toBe(403);
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(after);
  });

  it("validates POST envelope types without Research access or writes", async () => {
    const h = await setup();
    const valid = choice(h.first.id, "update", 0, randomUUID());
    for (const malformed of [
      { ...valid, choice: "retarget" },
      { ...valid, researchProjectId: 123 },
      { ...valid, expectedRevision: "0" },
      { ...valid, expectedClipVersion: 0 },
      { ...valid, clientMutationId: "bad" },
      { ...valid, unexpected: true },
    ]) {
      const response = await h.api(choiceRequest(h.projectId, malformed));
      expect(response.status).toBe(400);
      expect(await json(response)).toEqual({ error: "invalid_request" });
    }
    expect(h.calls).toHaveLength(0);
    expect((await h.service.getDocument(h.projectId, h.owner)).revision).toBe(0);
  });
});
