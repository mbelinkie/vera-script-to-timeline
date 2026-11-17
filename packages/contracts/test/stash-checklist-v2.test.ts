import { describe, expect, it } from "vitest";
import {
  applyRowEditV2, createRowEditSessionV2, createSortingTrialV2,
  deserializeAuthoringDocumentV2, projectStashChecklistV2,
  serializeAuthoringDocumentV2, validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const gap = (afterRowId: string | null = null) => ({ sectionId: null, afterRowId, beforeRowId: null });

function note(n: number, text = "[literal] words"): NarrationBlockV2 {
  return {
    type: "narration", id: id(n), orderKey: `note-${n}`, text, plainDirection: true,
    tokens: [...text.matchAll(/\S+/gu)].map((word, index) => ({
      id: id(n * 10 + index + 1), value: word[0],
      startOffset: word.index, endOffset: word.index + word[0].length, spoken: false,
    })),
    primaryVisualSequence: { id: id(n * 10 + 10), version: 1, slots: [{
      id: id(n * 10 + 11), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function clip(n: number): VisualOnlyBlockV2 {
  return {
    type: "visual_only", id: id(n), orderKey: `clip-${n}`,
    payload: { kind: "visual", payloadId: id(n * 10 + 1), pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: id(n * 10 + 2) }, audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 24 } }, version: 1,
  };
}

function fixture(withFootage = false): { doc: ScriptDocumentV2; source: NarrationBlockV2; child: NarrationBlockV2; other: VisualOnlyBlockV2 } {
  const source = note(100);
  if (withFootage) source.attachedFootage = { clip: clip(500) };
  const child = note(200, "child words");
  const other = clip(300);
  const doc: ScriptDocumentV2 = {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Checklist transaction",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
    stash: [source, child, other].map((row, i) => ({ id: id(700 + i), rows: [row], supportingItems: [] })),
    stashOutline: [
      { rowId: source.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "note", parentRowId: source.id, sectionId: null },
      { rowId: other.id, kind: "clip", parentRowId: null, sectionId: null },
    ],
  };
  return { doc, source, child, other };
}

function savedNote(doc: ScriptDocumentV2, sourceId: string): NarrationBlockV2 {
  const row = doc.stash?.flatMap((bundle) => bundle.rows).find((item) => item.id === sourceId);
  if (row?.type !== "narration") throw new Error("Missing saved note");
  return row;
}
function withoutRevision(doc: ScriptDocumentV2): Omit<ScriptDocumentV2, "rowEditRevision"> {
  const copy = structuredClone(doc);
  delete copy.rowEditRevision;
  return copy;
}

function place(doc: ScriptDocumentV2, rowIds: string[], afterRowId: string | null = null, includeDescendants = false) {
  return applyRowEditV2(doc, doc.rowEditRevision ?? 0, {
    kind: "place_stash_rows", rowIds, destination: gap(afterRowId), includeDescendants,
  });
}

describe("persisted Stash note and clip checklist (issue #373)", () => {
  it("starts unchecked, has no parent cascade, and saves manual toggles and Undo exactly", () => {
    const { doc, source, child, other } = fixture();
    const session = createRowEditSessionV2(doc);
    const checked = session.apply({ kind: "set_stash_completion", rowId: source.id, completed: true });
    expect(checked.ok, JSON.stringify(checked.diagnostics)).toBe(true);
    expect(savedNote(checked.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 1 });
    expect(savedNote(checked.document, child.id).stashChecklist).toBeUndefined();
    const clipChecked = session.apply({ kind: "set_stash_completion", rowId: other.id, completed: true });
    expect(clipChecked.ok, JSON.stringify(clipChecked.diagnostics)).toBe(true);
    const persisted = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(clipChecked.document));
    expect(persisted.ok).toBe(true);
    if (!persisted.ok) return;
    expect(persisted.document.stash![2]!.rows[0]).toMatchObject({ stashChecklist: { completed: true, manualRevision: 1 } });
    expect(withoutRevision(session.undo().document)).toEqual(withoutRevision(checked.document));
    expect(withoutRevision(session.undo().document)).toEqual(withoutRevision(doc));
  });

  it("copies words, attached footage and every owned identity, checks source, then reverses only its cause", () => {
    const { doc, source } = fixture(true);
    const a = place(doc, [source.id]);
    expect(a.ok, JSON.stringify(a.diagnostics)).toBe(true);
    expect(a.placementCounts).toMatchObject({ copiedNotes: 1, attachedFootageCopies: 1 });
    const copiedA = a.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(copiedA.id).not.toBe(source.id);
    expect(copiedA.text).toBe(source.text);
    expect(copiedA.plainDirection).toBeUndefined();
    expect(copiedA.tokens.every((token) => token.spoken !== false)).toBe(true);
    expect(copiedA.tokens[0]?.id).not.toBe(source.tokens[0]?.id);
    expect(copiedA.primaryVisualSequence?.slots[0]?.id).not.toBe(source.primaryVisualSequence?.slots[0]?.id);
    expect(copiedA.attachedFootage?.clip.id).not.toBe(source.attachedFootage?.clip.id);
    expect(copiedA.attachedFootage?.clip.payload.source).toEqual(source.attachedFootage?.clip.payload.source);
    expect(savedNote(a.document, source.id).attachedFootage).toEqual(source.attachedFootage);
    expect(savedNote(a.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 0, automaticCopyId: copiedA.id });

    const b = place(a.document, [source.id], copiedA.id);
    expect(b.ok, JSON.stringify(b.diagnostics)).toBe(true);
    const copiedB = b.document.activeDraft.blocks[1] as NarrationBlockV2;
    expect(copiedB.id).not.toBe(copiedA.id);
    expect(copiedB.stashOrigin?.completionCaused).toBe(false);
    const returnB = applyRowEditV2(b.document, 2, { kind: "stash_rows", rowIds: [copiedB.id], bundleId: id(900) });
    expect(returnB.ok, JSON.stringify(returnB.diagnostics)).toBe(true);
    expect(savedNote(returnB.document, source.id).stashChecklist?.completed).toBe(true);
    expect(returnB.document.stashOutline).toHaveLength(3);
    const returnA = applyRowEditV2(returnB.document, 3, { kind: "stash_rows", rowIds: [copiedA.id], bundleId: id(901) });
    expect(returnA.ok, JSON.stringify(returnA.diagnostics)).toBe(true);
    expect(returnA.document.activeDraft.blocks).toEqual([]);
    expect(savedNote(returnA.document, source.id).stashChecklist?.completed).toBe(false);
    expect(returnA.document.stashOutline).toHaveLength(3);
    expect(validateScriptDocumentV2(returnA.document).valid).toBe(true);
  });

  it("returns A before B without reference counting, but manual uncheck/recheck wins", () => {
    const { doc, source } = fixture();
    const a = place(doc, [source.id]);
    expect(a.ok).toBe(true);
    const aId = a.document.activeDraft.blocks[0]!.id;
    const b = place(a.document, [source.id], aId);
    expect(b.ok).toBe(true);
    const bId = b.document.activeDraft.blocks[1]!.id;
    const returnedA = applyRowEditV2(b.document, 2, { kind: "stash_rows", rowIds: [aId], bundleId: id(903) });
    expect(returnedA.ok, JSON.stringify(returnedA.diagnostics)).toBe(true);
    expect(savedNote(returnedA.document, source.id).stashChecklist?.completed).toBe(false);
    expect(returnedA.document.activeDraft.blocks.map((row) => row.id)).toEqual([bId]);
    const returnedB = applyRowEditV2(returnedA.document, 3, { kind: "stash_rows", rowIds: [bId], bundleId: id(904) });
    expect(returnedB.ok, JSON.stringify(returnedB.diagnostics)).toBe(true);
    expect(savedNote(returnedB.document, source.id).stashChecklist?.completed).toBe(false);

    const unchecked = applyRowEditV2(a.document, 1, { kind: "set_stash_completion", rowId: source.id, completed: false });
    expect(unchecked.ok).toBe(true);
    const rechecked = applyRowEditV2(unchecked.document, 2, { kind: "set_stash_completion", rowId: source.id, completed: true });
    expect(rechecked.ok).toBe(true);
    const manualReturn = applyRowEditV2(rechecked.document, 3, { kind: "stash_rows", rowIds: [aId], bundleId: id(905) });
    expect(manualReturn.ok, JSON.stringify(manualReturn.diagnostics)).toBe(true);
    expect(savedNote(manualReturn.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 2 });
  });

  it("keeps saved full rows when the source or copy was edited or the source was deleted", () => {
    const { doc, source } = fixture(true);
    const a = place(doc, [source.id]);
    expect(a.ok).toBe(true);
    const copy = a.document.activeDraft.blocks[0] as NarrationBlockV2;
    const sourceEdited = structuredClone(savedNote(a.document, source.id));
    sourceEdited.notes.push("changed source content");
    const edited = applyRowEditV2(a.document, 1, { kind: "edit_row", rowId: source.id, row: sourceEdited });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    const returned = applyRowEditV2(edited.document, 2, { kind: "stash_rows", rowIds: [copy.id], bundleId: id(910) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(returned.document.stashOutline?.some((entry) => entry.rowId === copy.id && entry.kind === "row")).toBe(true);
    expect((returned.document.stash?.flatMap((bundle) => bundle.rows).find((row) => row.id === copy.id) as NarrationBlockV2).attachedFootage).toEqual(copy.attachedFootage);
    expect(savedNote(returned.document, source.id).stashChecklist?.completed).toBe(true);

    const other = fixture();
    const placed = place(other.doc, [other.source.id]);
    const copied = structuredClone(placed.document.activeDraft.blocks[0] as NarrationBlockV2);
    copied.notes.push("edited copy");
    const changedCopy = applyRowEditV2(placed.document, 1, { kind: "edit_row", rowId: copied.id, row: copied });
    expect(changedCopy.ok).toBe(true);
    const missing = applyRowEditV2(changedCopy.document, 2, { kind: "delete_rows", rowIds: [other.source.id, other.child.id] });
    expect(missing.ok, JSON.stringify(missing.diagnostics)).toBe(true);
    const saved = applyRowEditV2(missing.document, 3, { kind: "stash_rows", rowIds: [copied.id], bundleId: id(911) });
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    expect(saved.document.stashOutline?.some((entry) => entry.rowId === copied.id && entry.kind === "row")).toBe(true);
  });

  it("permanently breaks a copy's return link after a source edit, even when source bytes are restored", () => {
    const { doc, source } = fixture(true);
    const placed = place(doc, [source.id]);
    expect(placed.ok).toBe(true);
    const copiedId = placed.document.activeDraft.blocks[0]!.id;
    const original = structuredClone(savedNote(placed.document, source.id));
    const edited = structuredClone(original);
    edited.notes.push("temporary change");
    const changed = applyRowEditV2(placed.document, 1, { kind: "edit_row", rowId: source.id, row: edited });
    expect(changed.ok, JSON.stringify(changed.diagnostics)).toBe(true);
    expect((changed.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(false);
    const restored = applyRowEditV2(changed.document, 2, { kind: "edit_row", rowId: source.id, row: original });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(savedNote(restored.document, source.id).notes).toEqual(original.notes);
    const saved = applyRowEditV2(restored.document, 3, {
      kind: "stash_rows", rowIds: [copiedId], bundleId: id(920),
    });
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    expect(saved.document.stashOutline?.find((item) => item.rowId === copiedId)?.kind).toBe("row");
    expect(savedNote(saved.document, source.id).stashChecklist?.completed).toBe(true);

    const clipPlaced = place(doc, [source.id]);
    const attachedClip = savedNote(clipPlaced.document, source.id).attachedFootage?.clip;
    if (!attachedClip) throw new Error("Expected saved attached footage");
    const clipId = attachedClip.id;
    const footage = applyRowEditV2(clipPlaced.document, 1, {
      kind: "trim_research_clip", clipRowId: clipId, edge: "clear_out",
    });
    // The fixture's generic media reference is not an evidenced Research clip,
    // so a rejected trim cannot invalidate the link or alter completion.
    expect(footage.ok).toBe(false);
    expect(footage.document).toBe(clipPlaced.document);
  });

  it("breaks linked returns on attached-footage edits, even after reattaching the original clip", () => {
    const { doc, source } = fixture(true);
    const placed = place(doc, [source.id]);
    expect(placed.ok).toBe(true);
    const copyId = placed.document.activeDraft.blocks[0]!.id;
    const clipId = source.attachedFootage!.clip.id;
    const detached = applyRowEditV2(placed.document, 1, {
      kind: "detach_stash_footage", noteRowId: source.id, bundleId: id(936),
    });
    expect(detached.ok, JSON.stringify(detached.diagnostics)).toBe(true);
    expect((detached.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(false);
    const reattached = applyRowEditV2(detached.document, 2, {
      kind: "attach_stash_footage", noteRowId: source.id, clipRowId: clipId,
    });
    expect(reattached.ok, JSON.stringify(reattached.diagnostics)).toBe(true);
    expect(savedNote(reattached.document, source.id).attachedFootage?.clip.id).toBe(clipId);
    const returned = applyRowEditV2(reattached.document, 3, {
      kind: "stash_rows", rowIds: [copyId], bundleId: id(937),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(returned.document.stashOutline?.find((item) => item.rowId === copyId)?.kind).toBe("row");
    expect(savedNote(returned.document, source.id).stashChecklist?.completed).toBe(true);
  });

  it("does not invalidate a linked copy after moving it, but grouped return keeps saved members", () => {
    const { doc, source, child } = fixture();
    const first = place(doc, [source.id]);
    expect(first.ok).toBe(true);
    const sourceCopyId = first.document.activeDraft.blocks[0]!.id;
    const second = place(first.document, [child.id], sourceCopyId);
    expect(second.ok).toBe(true);
    const childCopyId = second.document.activeDraft.blocks[1]!.id;
    const moved = applyRowEditV2(second.document, 2, {
      kind: "move_rows", rowIds: [sourceCopyId], destination: gap(childCopyId),
    });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect((moved.document.activeDraft.blocks[1] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(true);
    const single = applyRowEditV2(moved.document, 3, {
      kind: "stash_rows", rowIds: [sourceCopyId], bundleId: id(941),
    });
    expect(single.ok, JSON.stringify(single.diagnostics)).toBe(true);
    expect(savedNote(single.document, source.id).stashChecklist?.completed).toBe(false);

    const grouped = applyRowEditV2(second.document, 2, {
      kind: "stash_group_rows", rowIds: [sourceCopyId, childCopyId],
      bundleId: id(942), groupId: id(943), sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(grouped.ok, JSON.stringify(grouped.diagnostics)).toBe(true);
    expect(grouped.document.activeDraft.blocks).toHaveLength(0);
    expect(grouped.document.stashOutline?.find((item) => item.rowId === sourceCopyId)?.kind).toBe("row");
    expect(grouped.document.stashOutline?.find((item) => item.rowId === childCopyId)?.kind).toBe("row");
    expect(savedNote(grouped.document, source.id).stashChecklist?.completed).toBe(true);
    expect(savedNote(grouped.document, child.id).stashChecklist?.completed).toBe(true);
  });

  it("skips completed descendants and clips regardless of Hide completed, but retains needed ancestor context", () => {
    const { doc, source, child, other } = fixture();
    const checked = applyRowEditV2(doc, 0, { kind: "set_stash_completion", rowId: other.id, completed: true });
    expect(checked.ok).toBe(true);
    const parentChecked = applyRowEditV2(checked.document, 1, { kind: "set_stash_completion", rowId: source.id, completed: true });
    expect(parentChecked.ok).toBe(true);
    expect(projectStashChecklistV2(parentChecked.document, true)).toMatchObject({
      visibleRowIds: [source.id, child.id], hiddenRowIds: [other.id], hiddenClips: 1,
    });
    const selected = place(parentChecked.document, [source.id], null, true);
    expect(selected.ok, JSON.stringify(selected.diagnostics)).toBe(true);
    expect(selected.placementCounts).toMatchObject({ copiedNotes: 2, skippedCompleted: 0 });
    const refused = place(parentChecked.document, [other.id]);
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.code).toBe("STASH_NOTHING_TO_PLACE");
    expect(refused.document).toBe(parentChecked.document);
  });

  it("refuses invalid destinations without completion side effects and restores exact copy/checkbox by Undo", () => {
    const { doc, source } = fixture();
    const session = createRowEditSessionV2(doc);
    const refused = session.apply({ kind: "place_stash_rows", rowIds: [source.id], destination: gap(id(9999)) });
    expect(refused.ok).toBe(false);
    expect(session.document).toEqual(doc);
    const placed = session.apply({ kind: "place_stash_rows", rowIds: [source.id], destination: gap() });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(withoutRevision(session.undo().document)).toEqual(withoutRevision(doc));
  });

  it("keeps and discards one copied-note gesture through selective Sorting acceptance", () => {
    const { doc, source } = fixture();
    const all = createSortingTrialV2(doc);
    expect(all.apply({ kind: "place_stash_rows", rowIds: [source.id], destination: gap(), includeDescendants: false }).ok).toBe(true);
    const edits = all.accept(doc, "edits_only");
    expect(edits.ok, JSON.stringify(edits.diagnostics)).toBe(true);
    expect(edits.document.activeDraft.blocks).toHaveLength(1);
    expect(savedNote(edits.document, source.id).stashChecklist?.completed).toBe(true);
    const onlySorting = createSortingTrialV2(doc);
    expect(onlySorting.apply({ kind: "place_stash_rows", rowIds: [source.id], destination: gap(), includeDescendants: false }).ok).toBe(true);
    const sorting = onlySorting.accept(doc, "sorting_only");
    expect(sorting.ok, JSON.stringify(sorting.diagnostics)).toBe(true);
    expect(sorting.document.activeDraft.blocks).toEqual([]);
    expect(savedNote(sorting.document, source.id).stashChecklist).toBeUndefined();
    const discarded = createSortingTrialV2(doc);
    expect(discarded.apply({ kind: "place_stash_rows", rowIds: [source.id], destination: gap(), includeDescendants: false }).ok).toBe(true);
    expect(discarded.discard(doc).document).toEqual(doc);
  });

  it("keeps mixed note-copy and ordinary clip move atomic under all selective Sorting outcomes", () => {
    const { doc, source, child, other } = fixture();
    const baseline = structuredClone(doc);
    baseline.stashOutline!.find((entry) => entry.rowId === other.id)!.parentRowId = source.id;
    savedNote(baseline, child.id).stashChecklist = { completed: true, manualRevision: 0 };
    const command = {
      kind: "place_stash_rows" as const, rowIds: [source.id], destination: gap(), includeDescendants: true,
    };
    const all = createSortingTrialV2(baseline);
    const mixed = all.apply(command);
    expect(mixed.ok, JSON.stringify(mixed.diagnostics)).toBe(true);
    expect(mixed.placementCounts).toMatchObject({ copiedNotes: 1, movedClips: 1, skippedCompleted: 1 });
    const created = mixed.document.activeDraft.blocks.find((row) => row.type === "narration") as NarrationBlockV2;
    expect(mixed.document.activeDraft.blocks.map((row) => row.type)).toEqual(["narration", "visual_only"]);
    expect(savedNote(mixed.document, source.id).stashChecklist?.completed).toBe(true);

    const accepted = all.accept(baseline, "all");
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    expect(accepted.document.activeDraft.blocks.map((row) => row.id)).toEqual([created.id, other.id]);
    const edits = createSortingTrialV2(baseline);
    expect(edits.apply(command).ok).toBe(true);
    const editsAccepted = edits.accept(baseline, "edits_only");
    expect(editsAccepted.ok, JSON.stringify(editsAccepted.diagnostics)).toBe(true);
    expect(editsAccepted.document.activeDraft.blocks.map((row) => row.id)).toEqual([created.id, other.id]);
    expect(savedNote(editsAccepted.document, source.id).stashChecklist?.completed).toBe(true);
    expect(editsAccepted.document.stashOutline?.some((entry) => entry.rowId === other.id)).toBe(false);

    const sorting = createSortingTrialV2(baseline);
    expect(sorting.apply(command).ok).toBe(true);
    const sortingAccepted = sorting.accept(baseline, "sorting_only");
    expect(sortingAccepted.ok, JSON.stringify(sortingAccepted.diagnostics)).toBe(true);
    expect(withoutRevision(sortingAccepted.document)).toEqual(withoutRevision(baseline));
    const discarded = createSortingTrialV2(baseline);
    expect(discarded.apply(command).ok).toBe(true);
    expect(discarded.discard(baseline).document).toEqual(baseline);
  });
});
