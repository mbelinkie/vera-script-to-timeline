import { randomUUID } from "node:crypto";

import { snapshotResearchCandidateV2 } from "@vera/contracts/authoring-v2";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fingerprint } from "../src/model.js";
import { SubtitleCopyService } from "../src/subtitle-copy.js";
import { documentFor, harness } from "./helpers.js";
import { researchCandidate, researchOccurrence } from "../../contracts/test/issue-367-fixture.js";

vi.setConfig({ testTimeout: 120_000 });
const cleaners: Array<() => Promise<void>> = [];
afterEach(async () => { for (const close of cleaners.splice(0)) await close(); });

async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const projectId = randomUUID();
  const first = researchOccurrence(820100, false);
  const second = researchOccurrence(820200, false);
  first.researchClip!.video.sourceLanguage = "es";
  second.researchClip!.video.sourceLanguage = "es";
  const doc = documentFor(projectId);
  doc.activeDraft.blocks = [first, second];
  await h.service.createProject(h.owner, {
    projectId, title: "Subtitle copies", document: doc, clientRequestId: randomUUID(),
  });
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  const session = await h.auth.openWriteSession(projectId, h.editor);
  const subtitles = new SubtitleCopyService(h.pool, h.auth, h.service);
  const firstDigest = fingerprint(first.researchClip!);
  const secondDigest = fingerprint(second.researchClip!);
  const derive = (occurrenceId: string, expectedSourceDigest: string, mutationId = randomUUID()) => ({
    occurrenceId, expectedSourceDigest, expectedDocumentRevision: 0,
    expectedDocumentDigest: fingerprint(doc), clientMutationId: mutationId, writeSessionId: session,
  });
  // checkedDocument uses serialized bytes, not canonical-key-order fingerprints.
  const initial = await h.service.getDocument(projectId, h.owner);
  return { ...h, projectId, doc, first, second, session, subtitles, initial,
    firstDigest, secondDigest,
    derive: (occurrenceId: string, sourceDigest: string, id = randomUUID()) => ({
      ...derive(occurrenceId, sourceDigest, id), expectedDocumentDigest: initial.digest,
    }),
  };
}

describe("subtitle copy authorized source-pinned service", () => {
  it("derives independent frozen copies, retains edits across unrelated document saves, and reads history", async () => {
    const h = await setup();
    const preflight = await h.subtitles.get(h.projectId, h.viewer, h.first.id);
    expect(preflight).toMatchObject({ binding: "not_derived", track: null,
      currentSourceDigest: h.firstDigest, documentRevision: 0 });
    const request = h.derive(h.first.id, h.firstDigest);
    const one = await h.subtitles.derive(h.projectId, h.editor, request);
    expect(one).toMatchObject({ version: 1, duplicateDelivery: false });
    expect(await h.subtitles.derive(h.projectId, h.editor, request))
      .toEqual({ ...one, duplicateDelivery: true });
    const other = await h.subtitles.derive(h.projectId, h.editor,
      h.derive(h.second.id, h.secondDigest));
    expect(other.version).toBe(1);
    const pinned = (await h.subtitles.get(h.projectId, h.viewer, h.first.id)).track!;
    expect(pinned).toMatchObject({ version: 1, reviewState: "needs_review",
      source: { englishText: "Frozen English text", loggedSelection: { transcriptStartMs: 1000,
        transcriptEndMs: 4000 } }, segments: [{ englishText: "Frozen English text",
          sourceStartMs: 1000, sourceEndMs: 4000 }] });
    const edit = { occurrenceId: h.first.id, expectedSourceDigest: h.firstDigest,
      expectedVersion: 1, englishText: "Carefully revised English", clientMutationId: randomUUID(),
      writeSessionId: h.session };
    const receipt = await h.subtitles.edit(h.projectId, h.editor, edit);
    expect(receipt.version).toBe(2);
    const changed = { ...h.initial.document, title: "Unrelated title save" };
    await h.service.putDocument(h.projectId, h.editor, {
      expectedRevision: 0, clientMutationId: randomUUID(), document: changed,
      writeSessionId: h.session,
    });
    const after = await h.subtitles.get(h.projectId, h.viewer, h.first.id);
    expect(after).toMatchObject({ binding: "current", documentRevision: 1, track: {
      version: 2, reviewState: "reviewed", reviewerId: h.editor.principalId,
      source: { englishText: "Frozen English text" },
      segments: [{ englishText: "Carefully revised English", sourceStartMs: 1000 }] } });
    expect((await h.subtitles.get(h.projectId, h.viewer, h.second.id)).track?.version).toBe(1);
    const page = await h.subtitles.history(h.projectId, h.viewer, h.first.id, 1);
    expect(page.revisions.map((r) => r.version)).toEqual([2]);
    expect(page.nextBeforeVersion).toBe(2);
    const older = await h.subtitles.history(h.projectId, h.viewer, h.first.id, 10, 2);
    expect(older.revisions).toMatchObject([{ version: 1, operation: "derive",
      track: { source: { englishText: "Frozen English text" }, reviewState: "needs_review" } }]);
    expect(older.nextBeforeVersion).toBeNull();
    const revisions = await h.db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_subtitle_copy_revisions WHERE project_id=$1",
      [h.projectId]);
    expect(revisions.rows[0]?.count).toBe(3);
  });

  it("refuses stale source, document CAS, version CAS, forged lease and operation ID collisions", async () => {
    const h = await setup();
    const request = h.derive(h.first.id, h.firstDigest);
    await expect(h.subtitles.derive(h.projectId, h.viewer, request)).rejects.toMatchObject({ status: 403 });
    await expect(h.subtitles.derive(h.projectId, h.editor,
      { ...request, writeSessionId: randomUUID() })).rejects.toMatchObject({ status: 403 });
    await expect(h.subtitles.derive(h.projectId, h.editor,
      { ...request, expectedSourceDigest: `sha256:${"0".repeat(64)}` })).rejects.toMatchObject({ status: 409 });
    await expect(h.subtitles.derive(h.projectId, h.editor,
      { ...request, expectedDocumentRevision: 12 })).rejects.toMatchObject({ status: 409 });
    const derived = await h.subtitles.derive(h.projectId, h.editor, request);
    await expect(h.subtitles.derive(h.projectId, h.editor,
      { ...request, clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 409 });
    const edit = { occurrenceId: h.first.id, expectedSourceDigest: h.firstDigest, expectedVersion: 1,
      englishText: "A changed subtitle", clientMutationId: randomUUID(), writeSessionId: h.session };
    await expect(h.subtitles.edit(h.projectId, h.editor, {
      ...edit, clientMutationId: request.clientMutationId })).rejects.toMatchObject({ code: "idempotency_conflict" });
    await expect(h.service.putDocument(h.projectId, h.editor, {
      expectedRevision: 0, clientMutationId: request.clientMutationId,
      document: { ...h.initial.document, title: "Should not save" },
      writeSessionId: h.session,
    })).rejects.toMatchObject({ code: "idempotency_conflict" });
    const edited = await h.subtitles.edit(h.projectId, h.editor, edit);
    expect(edited.version).toBe(2);
    await expect(h.subtitles.edit(h.projectId, h.editor, {
      ...edit, clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 409 });
    await expect(h.subtitles.rederive(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: h.firstDigest,
      expectedVersion: 2, clientMutationId: randomUUID(), writeSessionId: h.session,
    })).rejects.toMatchObject({ status: 409 });
    const before = await h.subtitles.get(h.projectId, h.owner, h.first.id);
    expect(before.digest).toBe(edited.digest);
    expect(derived.version).toBe(1);
  });

  it("retains stale and orphan history; only explicit rederive changes pinned provenance", async () => {
    const h = await setup();
    await h.subtitles.derive(h.projectId, h.editor, h.derive(h.first.id, h.firstDigest));
    const approved = await h.subtitles.approve(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: h.firstDigest,
      expectedVersion: 1, clientMutationId: randomUUID(), writeSessionId: h.session,
    });
    expect(approved.version).toBe(2);
    const candidate = researchCandidate();
    const latest = snapshotResearchCandidateV2({ ...candidate, version: 4,
      video: { ...candidate.video, sourceLanguage: "es" },
      englishText: "New pinned English baseline" });
    await h.service.applyResearchChoice(h.projectId, h.editor, {
      choice: "update", occurrenceId: h.first.id, researchProjectId: candidate.projectId,
      clipId: candidate.id, expectedRevision: 0, expectedClipVersion: 3,
      expectedLatestVersion: 4, clientMutationId: randomUUID(), writeSessionId: h.session,
    }, latest);
    const stale = await h.subtitles.get(h.projectId, h.viewer, h.first.id);
    expect(stale).toMatchObject({ binding: "stale", track: {
      version: 2, source: { englishText: "Frozen English text" } } });
    await expect(h.subtitles.edit(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: stale.currentSourceDigest!, expectedVersion: 2,
      englishText: "Unauthorized retarget", clientMutationId: randomUUID(),
      writeSessionId: h.session,
    })).rejects.toMatchObject({ status: 409 });
    const redone = await h.subtitles.rederive(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: stale.currentSourceDigest!,
      expectedVersion: 2, clientMutationId: randomUUID(), writeSessionId: h.session,
    });
    expect(redone.version).toBe(3);
    const current = await h.subtitles.get(h.projectId, h.viewer, h.first.id);
    expect(current).toMatchObject({ binding: "current", track: {
      version: 3, reviewState: "needs_review", source: { englishText: "New pinned English baseline" },
      segments: [{ englishText: "New pinned English baseline" }] } });
    const prior = await h.subtitles.history(h.projectId, h.viewer, h.first.id);
    expect(prior.revisions.map((r) => r.operation)).toEqual(["rederive", "approve", "derive"]);
    expect(prior.revisions[1]!.track.source.englishText).toBe("Frozen English text");
    const doc = await h.service.getDocument(h.projectId, h.owner);
    await h.service.putDocument(h.projectId, h.editor, {
      expectedRevision: doc.revision, clientMutationId: randomUUID(), writeSessionId: h.session,
      document: { ...doc.document, activeDraft: { ...doc.document.activeDraft,
        blocks: doc.document.activeDraft.blocks.filter((b) => b.id !== h.first.id) } },
    });
    expect((await h.subtitles.get(h.projectId, h.viewer, h.first.id)).binding).toBe("orphan");
    await expect(h.subtitles.approve(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: stale.currentSourceDigest!,
      expectedVersion: 3, clientMutationId: randomUUID(), writeSessionId: h.session,
    })).rejects.toMatchObject({ status: 409 });
    expect((await h.subtitles.history(h.projectId, h.viewer, h.first.id)).revisions).toHaveLength(3);
  });

  it("denies revoked editor and even exact replay, preserves copy on failure", async () => {
    const h = await setup();
    const request = h.derive(h.first.id, h.firstDigest);
    const receipt = await h.subtitles.derive(h.projectId, h.editor, request);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, null);
    await expect(h.subtitles.derive(h.projectId, h.editor, request)).rejects.toMatchObject({ status: 403 });
    await expect(h.subtitles.approve(h.projectId, h.editor, {
      occurrenceId: h.first.id, expectedSourceDigest: h.firstDigest, expectedVersion: 1,
      clientMutationId: randomUUID(), writeSessionId: h.session,
    })).rejects.toMatchObject({ status: 403 });
    const view = await h.subtitles.get(h.projectId, h.viewer, h.first.id);
    expect(view).toMatchObject({ binding: "current", digest: receipt.digest, track: { version: 1 } });
  });
});
