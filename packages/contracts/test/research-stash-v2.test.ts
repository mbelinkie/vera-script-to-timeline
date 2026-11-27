import { describe, expect, it } from "vitest";
import type { ScriptDocumentV2, StashResearchQuoteV2, StashResearchStillV2 } from "../src/generated/contracts-v2.js";
import { applyRowEditV2, createRowEditSessionV2, deserializeAuthoringDocumentV2, serializeAuthoringDocumentV2, type RowEditCommandV2 } from "../src/authoring-v2-rows.js";
import { captureResearchStashItemV2, consumeResearchStashItemV2, captureResearchQuoteBoxV2, type StashResearchItemV2 } from "../src/research-stash-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { createSortingTrialV2 } from "../src/authoring-v2-sorting.js";
import { researchId, researchStashFixture } from "./issue-367-fixture.js";

const id = researchId;
const section = id(910100);
const otherSection = id(910101);
const asset = {
  versionId: "original-v1", sha256: "a".repeat(64), byteCount: 4096,
  mimeType: "image/png" as const, width: 640, height: 480,
};
function quote(n = 910010): StashResearchQuoteV2 {
  return {
    id: id(n), sectionId: null, noteRowId: null, kind: "quote",
    quote: {
      researchQuoteId: id(910001), researchProjectId: id(910002), researchSourceId: id(910003),
      researchQuoteVersion: 3, spokenText: "The original words", displayText: "The edited words",
      speakerName: "Synthetic speaker", speakerTitle: "Synthetic title", citationText: "A synthetic source",
      citationOverridden: true, italicSpan: { start: 2, end: 11 }, templateRevision: "template-v1",
    },
    background: { kind: "still_image", displayName: "Kept source picture", picture: {
      researchProjectId: id(910002), ownerKind: "source", ownerId: id(910003),
      revisionId: id(910004), original: asset,
    } },
  };
}
function still(): StashResearchStillV2 {
  return {
    id: id(910011), sectionId: null, noteRowId: null, kind: "still",
    still: {
      researchProjectId: id(910002), itemId: id(910005), itemVersion: 4, sourceId: id(910006),
      title: "Synthetic still", credit: "Synthetic credit",
      provenance: { kind: "still_crop", inputSha256: "b".repeat(64), crop: { x: 0.2, y: 0.1, width: 0.5, height: 0.7 } },
      original: asset,
    },
  };
}
function apply(doc: ScriptDocumentV2, command: RowEditCommandV2): ScriptDocumentV2 {
  const result = applyRowEditV2(doc, doc.rowEditRevision ?? 0, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expect(result.document.rowEditRevision).toBe((doc.rowEditRevision ?? 0) + 1);
  return result.document;
}
function capture(doc: ScriptDocumentV2, item: StashResearchItemV2): ScriptDocumentV2 {
  const result = captureResearchStashItemV2(doc, doc.rowEditRevision ?? 0, item);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expect(result.document.rowEditRevision).toBe((doc.rowEditRevision ?? 0) + 1);
  return result.document;
}
function fixture() {
  const { doc, note, anchor } = researchStashFixture(false);
  return { doc: apply(apply(doc, { kind: "create_stash_section", sectionId: section, title: "One" }),
    { kind: "create_stash_section", sectionId: otherSection, title: "Two" }), note, anchor };
}
function move(itemId: string, sectionId: string | null, noteRowId: string | null, afterItemId: string | null = null): RowEditCommandV2 {
  return { kind: "move_stash_research_item", itemId, sectionId, noteRowId, afterItemId };
}

describe("saved compact Research Stash", () => {
  it("round-trips old documents unchanged, and retains exact independently frozen quote/still snapshots without adding Draft rows", () => {
    const { doc } = researchStashFixture(false);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(doc))).toEqual({ ok: true, document: doc });
    const q = quote();
    const s = still();
    const next = capture(capture(doc, q), s);
    expect(next.stashResearchItems).toEqual([q, s]);
    expect(next.activeDraft).toEqual(doc.activeDraft);
    expect(next.stash).toEqual(doc.stash);
    expect(doc.stashResearchItems).toBeUndefined();
    q.quote.displayText = "Modified caller copy";
    expect(next.stashResearchItems![0]).not.toEqual(q);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(next))).toEqual({ ok: true, document: next });
    const saved = apply(next, { kind: "create_stash_section", sectionId: section, title: "Unrelated edit" });
    expect(saved.stashResearchItems).toEqual(next.stashResearchItems);
  });

  it("consumes one exact quote only after normal placement; stale gaps and wrong kinds preserve every occurrence", () => {
    const { doc, note } = researchStashFixture(false);
    const q = { ...quote(), noteRowId: note.id };
    const saved = capture(capture(doc, q), still());
    const snapshot = structuredClone(saved);
    const request = { expectedDocumentRevision: saved.rowEditRevision!,
      destination: { kind: "gap" as const, sectionId: null, afterRowId: null, beforeRowId: null } };
    for (const refused of [
      consumeResearchStashItemV2(saved, q.id, { kind: "quote", request: { ...request, expectedDocumentRevision: 0 } }),
      consumeResearchStashItemV2(saved, q.id, { kind: "quote", request: { ...request,
        destination: { ...request.destination, afterRowId: id(999999) } } }),
      consumeResearchStashItemV2(saved, still().id, { kind: "quote", request }),
    ]) {
      expect(refused.ok).toBe(false);
      expect(refused.document).toBe(saved);
    }
    const placed = consumeResearchStashItemV2(saved, q.id, { kind: "quote", request });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.rowEditRevision).toBe(saved.rowEditRevision! + 1);
    expect(placed.document.stashResearchItems).toEqual([still()]);
    expect(saved).toEqual(snapshot);
    const row = placed.document.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("Missing quote row");
    const event = row.overlayEvents[0]!;
    expect(row.text).toBe("“The original words”");
    expect(event.quoteBox).toMatchObject({ displayText: q.quote.displayText, speakerName: q.quote.speakerName,
      citationText: q.quote.citationText, citationOverridden: true });
    const recapture = { expectedDocumentRevision: placed.document.rowEditRevision!, rowId: row.id,
      expectedRowVersion: row.version, overlayId: event.id, expectedOverlayVersion: event.version };
    const refused = captureResearchQuoteBoxV2(placed.document, recapture, { sectionId: null, noteRowId: null },
      still().id, q.quote.spokenText, null);
    expect(refused.ok).toBe(false);
    expect(refused.document).toBe(placed.document);
    const captured = captureResearchQuoteBoxV2(placed.document, recapture, { sectionId: null, noteRowId: note.id },
      id(910013), q.quote.spokenText, null);
    expect(captured.ok, JSON.stringify(captured.diagnostics)).toBe(true);
    expect(captured.document.rowEditRevision).toBe(placed.document.rowEditRevision! + 1);
    expect(captured.document.stashResearchItems).toEqual([still(), { ...q, id: id(910013) }]);
    const after = captured.document.activeDraft.blocks[0]!;
    if (after.type !== "narration") throw new Error("Missing quote row");
    expect(after.tokens).toEqual(row.tokens);
    expect(after.primaryVisualSequence).toEqual(row.primaryVisualSequence);
    expect(after.overlayEvents).toEqual([]);
  });

  it("retires only the unshared generated quote placeholder and preserves the exact attributed words", () => {
    const { doc } = researchStashFixture(false);
    const q = { ...quote(), background: null };
    const saved = capture(doc, q);
    const placed = consumeResearchStashItemV2(saved, q.id, { kind: "quote", request: {
      expectedDocumentRevision: saved.rowEditRevision!,
      destination: { kind: "gap", sectionId: null, afterRowId: null, beforeRowId: null },
    } });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const row = placed.document.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("Missing quote row");
    const event = row.overlayEvents[0]!;
    const request = { expectedDocumentRevision: placed.document.rowEditRevision!, rowId: row.id,
      expectedRowVersion: row.version, overlayId: event.id, expectedOverlayVersion: event.version };
    const location = { sectionId: null, noteRowId: null };
    const snapshot = structuredClone(placed.document);
    const savedBox = captureResearchQuoteBoxV2(placed.document, request, location, id(910015), null, null);
    expect(savedBox.ok, JSON.stringify(savedBox.diagnostics)).toBe(true);
    expect(savedBox.document.rowEditRevision).toBe(placed.document.rowEditRevision! + 1);
    expect(savedBox.document.stashResearchItems).toEqual([{ ...q, id: id(910015) }]);
    const after = savedBox.document.activeDraft.blocks[0]!;
    if (after.type !== "narration") throw new Error("Missing quote row");
    expect(after.text).toBe(row.text);
    expect(after.tokens).toEqual(row.tokens);
    expect(after.overlayEvents).toEqual([]);
    expect(after.primaryVisualSequence?.slots.some((slot) => slot.kind === "content" &&
      slot.payload.kind === "visual" && slot.payload.pictureKind === "unresolved_visual")).toBe(false);
    expect(placed.document).toEqual(snapshot);

    // Another adjacent quote can still depend on the same generated slate.
    const second = capture(placed.document, { ...q, id: id(910016) });
    const appended = consumeResearchStashItemV2(second, id(910016), { kind: "quote", request: {
      expectedDocumentRevision: second.rowEditRevision!,
      rowId: row.id, destination: { kind: "insert", beforeTokenId: null },
      expectedRowVersion: row.version, expectedSequenceVersion: row.primaryVisualSequence!.version,
    } });
    expect(appended.ok, JSON.stringify(appended.diagnostics)).toBe(true);
    const sharedRow = appended.document.activeDraft.blocks[0]!;
    if (sharedRow.type !== "narration") throw new Error("Missing quote row");
    expect(sharedRow.overlayEvents[1]?.quoteBox?.backgroundPayloadId).toBe(event.quoteBox?.backgroundPayloadId);
    const shared = captureResearchQuoteBoxV2(appended.document, {
      ...request, expectedDocumentRevision: appended.document.rowEditRevision!, expectedRowVersion: sharedRow.version,
      expectedOverlayVersion: sharedRow.overlayEvents[0]!.version,
    }, location, id(910017), null, null);
    expect(shared.ok, JSON.stringify(shared.diagnostics)).toBe(true);
    const remaining = shared.document.activeDraft.blocks[0]!;
    if (remaining.type !== "narration") throw new Error("Missing quote row");
    expect(remaining.primaryVisualSequence).toEqual(sharedRow.primaryVisualSequence);
    expect(remaining.overlayEvents).toEqual([sharedRow.overlayEvents[1]]);
  });

  it("permits multiple independent occurrences of the same Library quote, but refuses repeated or occupied occurrence IDs", () => {
    const { doc, note } = researchStashFixture(false);
    const first = capture(doc, quote());
    const second = capture(first, quote(910012));
    expect(second.stashResearchItems!.map((item) => item.id)).toEqual([quote().id, id(910012)]);
    for (const item of [quote(), { ...quote(), id: note.id }, { ...quote(), id: doc.id }]) {
      const result = captureResearchStashItemV2(second, second.rowEditRevision!, item);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(second);
    }
    const duplicate = structuredClone(second);
    duplicate.stashResearchItems!.push(quote());
    expect(validateScriptDocumentV2(duplicate).diagnostics.some((diagnostic) => diagnostic.code === "ENTITY_ID_DUPLICATE")).toBe(true);
    expect(deserializeAuthoringDocumentV2(JSON.stringify(duplicate)).ok).toBe(false);
  });

  it("attaches, reorders, detaches and removes one exact occurrence with one revision and one Undo per row operation", () => {
    const { doc, note } = fixture();
    const saved = capture(capture(doc, quote()), still());
    const session = createRowEditSessionV2(saved);
    const q = quote().id, s = still().id;
    expect(session.apply(move(q, null, note.id)).ok).toBe(true);
    expect(session.apply(move(s, null, note.id, q)).ok).toBe(true);
    expect(session.document.stashResearchItems!.map((item) => [item.id, item.noteRowId])).toEqual([[q, note.id], [s, note.id]]);
    expect(session.apply(move(s, null, note.id)).ok).toBe(true);
    expect(session.document.stashResearchItems!.map((item) => item.id)).toEqual([s, q]);
    const attached = session.document;
    expect(session.apply(move(q, section, null)).ok).toBe(true);
    expect(session.undoDepth).toBe(4);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashResearchItems).toEqual(attached.stashResearchItems);
    expect(session.revision).toBe(saved.rowEditRevision! + 5);
    expect(session.apply({ kind: "delete_stash_research_item", itemId: q }).ok).toBe(true);
    expect(session.document.stashResearchItems).toEqual([attached.stashResearchItems![0]]);
    expect(session.document.stash).toEqual(saved.stash);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashResearchItems).toEqual(attached.stashResearchItems);
  });

  it("refuses missing owners, stale edits and mismatched section or ordering anchors without changing the document", () => {
    const { doc, note, anchor } = fixture();
    const saved = capture(capture(doc, quote()), still());
    const q = quote().id, s = still().id;
    const owned = apply(saved, move(s, null, note.id));
    for (const command of [
      move(q, section, note.id), move(q, null, id(999999)), move(q, null, anchor.id, s),
      move(q, null, null, q), move(q, id(999999), null),
      { kind: "delete_stash_research_item", itemId: id(999999) } as const,
    ]) {
      const result = applyRowEditV2(owned, owned.rowEditRevision!, command);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(owned);
    }
    expect(applyRowEditV2(owned, owned.rowEditRevision! - 1, move(q, null, null)).document).toBe(owned);
    expect(captureResearchStashItemV2(owned, owned.rowEditRevision!, { ...quote(910015), noteRowId: id(999999) }).document).toBe(owned);
    const invalid = structuredClone(owned);
    invalid.stashResearchItems![0]!.noteRowId = id(999999);
    expect(deserializeAuthoringDocumentV2(JSON.stringify(invalid)).ok).toBe(false);
  });

  it("carries note-owned occurrences across section moves and promotes all items when the section is deleted", () => {
    const { doc, note } = fixture();
    const saved = capture(capture(doc, { ...quote(), noteRowId: note.id }), { ...still(), sectionId: section });
    const moved = apply(saved, { kind: "move_stash_rows", rowIds: [note.id], sectionId: section });
    expect(moved.stashResearchItems!.map((item) => item.sectionId)).toEqual([section, section]);
    const removed = apply(moved, { kind: "delete_stash_section", sectionId: section });
    expect(removed.stashResearchItems!.map((item) => [item.sectionId, item.noteRowId])).toEqual([[null, note.id], [null, null]]);
    expect(validateScriptDocumentV2(removed).valid).toBe(true);
  });

  it("refuses deleting, restoring or converting an owner rather than orphaning its compact Research item", () => {
    const { doc, anchor } = fixture();
    const saved = capture(doc, { ...quote(), noteRowId: anchor.id });
    const bundle = saved.stash!.find((entry) => entry.rows.some((row) => row.id === anchor.id))!;
    for (const command of [
      { kind: "delete_rows", rowIds: [anchor.id], stashBranch: { attachedClipIds: [] } } as const,
      { kind: "restore_stash", bundleId: bundle.id, destination: { sectionId: null, afterRowId: null, beforeRowId: null } } as const,
      { kind: "set_stash_outline", entries: saved.stashOutline!.map((entry) => entry.rowId === anchor.id ? { ...entry, kind: "row" as const } : entry) } as const,
    ]) {
      const result = applyRowEditV2(saved, saved.rowEditRevision!, command as RowEditCommandV2);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(saved);
    }
    const detached = apply(saved, move(quote().id, null, null));
    expect(applyRowEditV2(detached, detached.rowEditRevision!, {
      kind: "delete_rows", rowIds: [anchor.id], stashBranch: { attachedClipIds: [] },
    }).ok).toBe(true);
  });

  it("refuses malformed saved snapshots, mismatched picture ownership, out-of-range citations and unknown kinds", () => {
    const { doc } = researchStashFixture(false);
    const q = quote();
    const bad = [
      { ...q, unexpected: true },
      { ...q, kind: "audio" },
      { ...q, quote: { ...q.quote, italicSpan: { start: 0, end: 100 } } },
      { ...q, quote: { ...q.quote, displayText: " " } },
      { ...q, background: { ...q.background!, picture: { ...q.background!.picture, ownerId: id(999999) } } },
      { ...still(), still: { ...still().still, original: { ...asset, width: 20000 } } },
      { ...still(), still: { ...still().still, provenance: { ...still().still.provenance, crop: { x: 0.9, y: 0, width: 0.5, height: 1 } } } },
    ];
    for (const item of bad) {
      const candidate = { ...doc, stashResearchItems: [item] };
      expect(validateScriptDocumentV2(candidate).valid).toBe(false);
      expect(deserializeAuthoringDocumentV2(JSON.stringify(candidate)).ok).toBe(false);
    }
  });

  it("preserves the frozen collection in Sorting accept/discard and refuses compact Research commands inside a trial", () => {
    const { doc, note } = fixture();
    const saved = capture(doc, { ...quote(), noteRowId: note.id });
    for (const outcome of ["all", "sorting_only", "edits_only"] as const) {
      const trial = createSortingTrialV2(saved);
      expect(trial.apply(move(quote().id, null, null)).ok).toBe(false);
      expect(trial.apply({ kind: "move_stash_rows", rowIds: [note.id], sectionId: section }).ok).toBe(true);
      const accepted = trial.accept(saved, outcome);
      expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
      expect(accepted.document.stashResearchItems).toEqual([{ ...quote(), noteRowId: note.id, sectionId: outcome === "edits_only" ? null : section }]);
    }
    const trial = createSortingTrialV2(saved);
    expect(trial.apply({ kind: "move_stash_rows", rowIds: [note.id], sectionId: section }).ok).toBe(true);
    expect(trial.discard(saved).document.stashResearchItems).toEqual(saved.stashResearchItems);
  });
});
