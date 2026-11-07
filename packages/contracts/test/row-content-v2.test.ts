import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { applyRowEditV2, createRowEditSessionV2 } from "../src/authoring-v2-rows.js";
import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2, VisualOnlyBlockV2 } from "@vera/contracts/v2";

const fixtureUrl = new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url);
const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;

function documentFromFixture(): ScriptDocumentV2 {
  return (JSON.parse(readFileSync(fixtureUrl, "utf8")) as { document: ScriptDocumentV2 }).document;
}

function narration(value: number): NarrationBlockV2 {
  return {
    type: "narration",
    id: id(value),
    orderKey: `note-${value}`,
    text: "Wait",
    tokens: [{ id: id(value + 100), value: "Wait", startOffset: 0, endOffset: 4 }],
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "excluded",
    notes: [],
    version: 1,
  };
}

function clip(value: number): VisualOnlyBlockV2 {
  return {
    type: "visual_only",
    id: id(value),
    orderKey: `clip-${value}`,
    payload: {
      kind: "visual",
      payloadId: id(value + 100),
      pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: id(value + 101) },
      audioPolicy: "mute",
      framingPolicy: "contain",
    },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 48 } },
    version: 1,
  };
}

function activeNarration(document: ScriptDocumentV2): NarrationBlockV2 {
  const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration");
  if (!row) throw new Error("Expected a narration row in the fixture.");
  return row;
}

function gapBefore(document: ScriptDocumentV2, rowId: string) {
  let sectionId: string | null = null;
  let previousRowId: string | null = null;
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      sectionId = block.id;
      previousRowId = null;
    } else if (block.id === rowId) {
      return { sectionId, afterRowId: previousRowId, beforeRowId: rowId };
    } else {
      previousRowId = block.id;
    }
  }
  throw new Error(`Missing fixture row ${rowId}.`);
}

function gapAfter(document: ScriptDocumentV2, rowId: string) {
  let sectionId: string | null = null;
  let rows: string[] = [];
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      const index = rows.indexOf(rowId);
      if (index >= 0) return { sectionId, afterRowId: rowId, beforeRowId: rows[index + 1] ?? null };
      sectionId = block.id;
      rows = [];
    } else rows.push(block.id);
  }
  const index = rows.indexOf(rowId);
  if (index >= 0) return { sectionId, afterRowId: rowId, beforeRowId: rows[index + 1] ?? null };
  throw new Error(`Missing fixture row ${rowId}.`);
}

function wordAttachment(row: NarrationBlockV2, attachmentId: string): SupportingItemV2 {
  const token = row.tokens[0]!;
  const anchor = { blockId: row.id, tokenId: token.id, affinity: "before" as const, quotedWord: token.value, anchorVersion: row.version };
  return {
    id: attachmentId,
    version: 1,
    orderKey: "row-local",
    role: "reference",
    content: "Row-local reference",
    placement: { kind: "point", anchor: { kind: "word", anchor } },
    displayAttachment: { kind: "word", anchor },
  };
}

describe("public authored row edits", () => {
  it("creates and edits complete active rows at exact gaps with one revision each", () => {
    const document = documentFromFixture();
    const before = structuredClone(document);
    const existing = activeNarration(document);
    const newRow = { type: "note_draft" as const, id: id(98001), orderKey: "new-note", text: "Research this", state: "excluded" as const, version: 1 };

    const created = applyRowEditV2(document, 0, { kind: "create_row", row: newRow, destination: gapBefore(document, existing.id) });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    if (!created.ok) return;
    expect(document).toEqual(before);
    expect(created.document.rowEditRevision).toBe(1);
    expect(created.document.activeDraft.blocks.findIndex((block) => block.id === newRow.id) + 1).toBe(
      created.document.activeDraft.blocks.findIndex((block) => block.id === existing.id),
    );

    const wrongType = applyRowEditV2(created.document, 1, {
      kind: "edit_row", rowId: existing.id, row: { ...existing, type: "direction" },
    } as never);
    expect(wrongType).toMatchObject({ ok: false, diagnostics: [{ code: "ROW_IDENTITY_INVALID" }] });

    const edited = structuredClone(existing);
    edited.notes = [...edited.notes, "Authored row content changed"];
    const result = applyRowEditV2(created.document, 1, { kind: "edit_row", rowId: existing.id, row: edited });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (!result.ok) return;
    expect(result.document.rowEditRevision).toBe(2);
    expect(result.document.activeDraft.blocks.find((block) => block.id === existing.id)).toMatchObject({ notes: edited.notes });
    expect(created.document.activeDraft.blocks.find((block) => block.id === existing.id)).not.toMatchObject({ notes: edited.notes });
  });

  it("lets the row-edit session undo an authored row creation to its exact prior content", () => {
    const document = documentFromFixture();
    const before = structuredClone(document);
    const row = activeNarration(document);
    const session = createRowEditSessionV2(document);
    const created = session.apply({
      kind: "create_row",
      row: { type: "note_draft", id: id(98004), orderKey: "undo-note", text: "Undo me", state: "excluded", version: 1 },
      destination: gapBefore(document, row.id),
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    expect(session.revision).toBe(1);

    const undone = session.undo();
    expect(undone.ok).toBe(true);
    expect(undone.document).toEqual({ ...before, rowEditRevision: 2 });
    expect(session.revision).toBe(2);
  });

  it("preserves row identity and marks an edited Stash source ineligible for compact return", () => {
    const document = documentFromFixture();
    const row = activeNarration(document);
    row.stashOrigin = { kind: "note", parentRowId: null, sectionId: null, afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: true };
    const replacement = structuredClone(row);
    replacement.notes = [...replacement.notes, "Changed while in Draft"];

    const result = applyRowEditV2(document, 0, { kind: "edit_row", rowId: row.id, row: replacement });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (!result.ok) return;
    const edited = result.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.id === row.id && block.type === "narration");
    expect(edited?.stashOrigin).toMatchObject({ kind: "note", returnEligible: false });
    if (!edited) return;
    const attachment = wordAttachment(edited, id(98003));
    result.document.activeDraft.supportingItems.push(attachment);

    const stashed = applyRowEditV2(result.document, 1, { kind: "stash_rows", rowIds: [row.id], bundleId: id(98002) });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    if (!stashed.ok) return;
    const saved = structuredClone(stashed.document.stash![0]!.rows[0] as NarrationBlockV2);
    saved.notes = [...saved.notes, "Edited in Stash"];
    const stashEdit = applyRowEditV2(stashed.document, 2, { kind: "edit_row", rowId: row.id, row: saved });
    expect(stashEdit.ok, JSON.stringify(stashEdit.diagnostics)).toBe(true);
    if (!stashEdit.ok) return;
    expect(stashEdit.document.rowEditRevision).toBe(3);
    expect(stashEdit.document.stash?.[0]?.supportingItems).toEqual([attachment]);
    expect(stashEdit.document.stash?.[0]?.rows[0]).toMatchObject({ id: row.id, type: "narration", notes: saved.notes });
  });

  it("routes stage-direction edits through the row command and advances the document revision once", () => {
    const document = documentFromFixture();
    const row = activeNarration(document);
    const token = row.tokens[0]!;
    const result = applyRowEditV2(document, 0, {
      kind: "make_stage_direction",
      blockId: row.id,
      startOffset: token.startOffset,
      endOffset: token.endOffset,
    });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (!result.ok) return;
    expect(result.document.rowEditRevision).toBe(1);
    const changed = result.document.activeDraft.blocks.find((block) => block.id === row.id);
    expect(changed).toMatchObject({ version: row.version + 1 });
    if (changed?.type === "narration") expect(changed.text).toContain("[");

    const saved = narration(98010);
    const stashNote = applyRowEditV2(document, 0, {
      kind: "create_stash_note",
      bundleId: id(98011),
      row: saved,
      sectionId: null,
      parentRowId: null,
      afterRowId: null,
      mode: "authored",
    });
    expect(stashNote.ok, JSON.stringify(stashNote.diagnostics)).toBe(true);
    if (!stashNote.ok) return;
    const stashedEdit = applyRowEditV2(stashNote.document, 1, {
      kind: "make_stage_direction",
      blockId: saved.id,
      startOffset: 0,
      endOffset: saved.text.length,
    });
    expect(stashedEdit.ok, JSON.stringify(stashedEdit.diagnostics)).toBe(true);
    if (!stashedEdit.ok) return;
    expect(stashedEdit.document.rowEditRevision).toBe(2);
    expect(stashedEdit.document.stash?.[0]?.rows[0]).toMatchObject({ id: saved.id, version: saved.version + 1 });
  });

  it("deletes row-local attachments and references, but refuses cross-row or audio dependencies", () => {
    const document = documentFromFixture();
    const row = activeNarration(document);
    const attachment = wordAttachment(row, id(98020));
    document.activeDraft.supportingItems.push(attachment);
    document.rowReferences = [{ id: id(98021), rowId: row.id, kind: "reference", anchor: { note: "local" } }];

    const deleted = applyRowEditV2(document, 0, { kind: "delete_rows", rowIds: [row.id] });
    expect(deleted.ok, JSON.stringify(deleted.diagnostics)).toBe(true);
    if (!deleted.ok) return;
    expect(deleted.document.activeDraft.blocks.some((block) => block.id === row.id)).toBe(false);
    expect(deleted.document.activeDraft.supportingItems).toEqual([]);
    expect(deleted.document.rowReferences).toBeUndefined();
    expect(deleted.document.rowEditRevision).toBe(1);

    const cross = documentFromFixture();
    const first = activeNarration(cross);
    const second = { type: "note_draft" as const, id: id(98026), orderKey: "cross-row-note", text: "Neighbor", state: "excluded" as const, version: 1 };
    const withNeighbor = applyRowEditV2(cross, 0, { kind: "create_row", row: second, destination: gapAfter(cross, first.id) });
    expect(withNeighbor.ok, JSON.stringify(withNeighbor.diagnostics)).toBe(true);
    if (!withNeighbor.ok) return;
    withNeighbor.document.activeDraft.supportingItems.push({
      id: id(98022), version: 1, orderKey: "cross-row", role: "reference", content: "Spans rows",
      placement: { kind: "unplaced", reason: "manual review" },
      displayAttachment: { kind: "between_blocks", beforeBlockId: first.id, afterBlockId: second.id },
    });
    const crossBefore = structuredClone(withNeighbor.document);
    const refusedCross = applyRowEditV2(withNeighbor.document, 1, { kind: "delete_rows", rowIds: [first.id] });
    expect(refusedCross).toMatchObject({ ok: false, diagnostics: [{ code: "ROW_REFERENCE_REVIEW_REQUIRED" }] });
    expect(refusedCross.document).toBe(withNeighbor.document);
    expect(withNeighbor.document).toEqual(crossBefore);

    const audio = documentFromFixture();
    const audioRow = activeNarration(audio);
    audio.rowAudioSpans = [{
      id: id(98023), startRowId: audioRow.id, endRowId: audioRow.id,
      source: { mediaReferenceId: id(98024), artifactId: id(98025), artifactVersion: 1, contentHash: `sha256:${"c".repeat(64)}` },
      settings: {},
    }];
    const audioRefusal = applyRowEditV2(audio, 0, { kind: "delete_rows", rowIds: [audioRow.id] });
    expect(audioRefusal).toMatchObject({ ok: false, diagnostics: [{ code: "AUDIO_REVIEW_REQUIRED" }] });
  });

  it("deletes a complete Stash branch and refuses a parent-only delete", () => {
    const document = documentFromFixture();
    const parent = narration(98030);
    const child = clip(98032);
    const createdParent = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(98031), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null, mode: "authored",
    });
    expect(createdParent.ok, JSON.stringify(createdParent.diagnostics)).toBe(true);
    if (!createdParent.ok) return;
    const createdChild = applyRowEditV2(createdParent.document, 1, {
      kind: "create_stash_clip", bundleId: id(98034), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    });
    expect(createdChild.ok, JSON.stringify(createdChild.diagnostics)).toBe(true);
    if (!createdChild.ok) return;

    const refusedParent = applyRowEditV2(createdChild.document, 2, { kind: "delete_rows", rowIds: [parent.id] });
    expect(refusedParent).toMatchObject({ ok: false, diagnostics: [{ code: "STASH_OUTLINE_BRANCH_REQUIRED" }] });
    expect(refusedParent.document).toBe(createdChild.document);

    const deletedBranch = applyRowEditV2(createdChild.document, 2, { kind: "delete_rows", rowIds: [parent.id, child.id] });
    expect(deletedBranch.ok, JSON.stringify(deletedBranch.diagnostics)).toBe(true);
    if (!deletedBranch.ok) return;
    expect(deletedBranch.document.rowEditRevision).toBe(3);
    expect(deletedBranch.document.stash).toEqual([]);
    expect(deletedBranch.document.stashOutline).toBeUndefined();
  });

  it("rejects malformed authored commands and rows without throwing", () => {
    const document = documentFromFixture();
    const row = activeNarration(document);
    const extraKey = applyRowEditV2(document, 0, {
      kind: "delete_rows", rowIds: [row.id], unexpected: true,
    } as never);
    expect(extraKey).toMatchObject({ ok: false, diagnostics: [{ code: "ROW_COMMAND_INVALID" }] });

    const nonJsonRow = { ...row, customValue: undefined };
    const invalidContent = applyRowEditV2(document, 0, { kind: "edit_row", rowId: row.id, row: nonJsonRow });
    expect(invalidContent).toMatchObject({ ok: false, diagnostics: [{ code: "ROW_COMMAND_INVALID" }] });
  });
});

// #367 phase 3: authoritative Research occurrence edits and independent return.
import { createResearchClipOccurrenceV2, serializeAuthoringDocumentV2, deserializeAuthoringDocumentV2, validateScriptDocumentV2 } from "../src/authoring-v2.js";
import { researchCandidate, researchId, researchOccurrence, researchStashFixture } from "./issue-367-fixture.js";

describe("Research footage occurrence edits and original-note return (issue 367)", () => {
  const rev = (doc: ScriptDocumentV2) => doc.rowEditRevision ?? 0;
  const apply = (doc: ScriptDocumentV2, command: Parameters<typeof applyRowEditV2>[2]) =>
    applyRowEditV2(doc, rev(doc), command);
  const returnClip = (doc: ScriptDocumentV2, clipRowId: string) =>
    apply(doc, { kind: "stash_rows", rowIds: [clipRowId], bundleId: researchId(760101) });

  it("trims in/out/clear-out only one owned occurrence, roundtrips, and refuses invalid frames atomically", () => {
    const { doc, note, clip } = researchStashFixture();
    const independent = researchOccurrence(730200);
    doc.stash!.push({ id: researchId(740300), rows: [independent], supportingItems: [] });
    doc.stashOutline!.push({ rowId: independent.id, kind: "clip", parentRowId: note.id, sectionId: null });
    const original = structuredClone(doc);
    const source = researchCandidate();
    const session = createRowEditSessionV2(doc);
    const inpoint = session.apply({ kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 36 });
    expect(inpoint.ok, JSON.stringify(inpoint.diagnostics)).toBe(true);
    const outpoint = session.apply({ kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 52 });
    expect(outpoint.ok, JSON.stringify(outpoint.diagnostics)).toBe(true);
    const clearOut = session.apply({ kind: "trim_research_clip", clipRowId: clip.id, edge: "clear_out" });
    expect(clearOut.ok, JSON.stringify(clearOut.diagnostics)).toBe(true);
    const owner = clearOut.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2;
    expect(owner.attachedFootage?.clip.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 36, durationFrames: 72 });
    expect(owner.attachedFootage?.clip.researchClip).toEqual(clip.researchClip);
    expect(researchCandidate()).toEqual(source);
    expect(clearOut.document.stash!.flatMap((b) => b.rows).find((r) => r.id === independent.id)).toEqual(independent);
    expect(doc).toEqual(original);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(clearOut.document));
    expect(loaded.ok).toBe(true);
    if (loaded.ok) expect(loaded.document).toEqual(clearOut.document);
    for (const command of [
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 109 },
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 108 },
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 36 },
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "clear_out", frame: 108 },
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 37, extra: true },
    ] as unknown as Parameters<typeof applyRowEditV2>[2][]) {
      const failed = session.apply(command);
      expect(failed.ok).toBe(false);
      expect(failed.document).toEqual(clearOut.document);
    }
    const undone = session.undo();
    expect(undone.ok).toBe(true);
    const prior = structuredClone(outpoint.document);
    prior.rowEditRevision = undone.document.rowEditRevision ?? 0;
    expect(undone.document).toEqual(prior);
    expect(session.apply({ kind: "trim_research_clip", clipRowId: clip.id, edge: "clear_out" }, 0).diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
  });

  it("places footage separately with stable identity and reattaches only to the original empty note", () => {
    const { doc, note, clip, anchor } = researchStashFixture();
    const before = structuredClone(doc);
    const session = createRowEditSessionV2(doc);
    const placed = session.apply({ kind: "place_attached_footage", noteRowId: note.id, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const active = placed.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(active.id).toBe(clip.id);
    expect(active.stashOrigin).toMatchObject({
      kind: "clip", originalAttachedNoteRowId: note.id, originalAttachedNoteParentRowId: null,
      originalAttachedNoteAfterSiblingRowId: anchor.id, returnEligible: true,
    });
    expect((placed.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2).attachedFootage).toBeUndefined();
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(placed.document));
    expect(saved.ok).toBe(true);
    const returned = session.apply({ kind: "stash_rows", rowIds: [clip.id], bundleId: researchId(760101) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    const owner = returned.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2;
    expect(owner.attachedFootage?.clip).toEqual(clip);
    expect(returned.document.stashOutline?.map((r) => r.rowId)).toEqual([anchor.id, note.id]);
    expect(returned.document.activeDraft.blocks).toHaveLength(0);
    expect(validateScriptDocumentV2(returned.document).valid).toBe(true);
    const undo = session.undo();
    expect(undo.ok).toBe(true);
    expect(undo.document.activeDraft.blocks[0]?.id).toBe(clip.id);
    expect(doc).toEqual(before);
  });

  it("occupied owners keep ordinary children; edited occurrences stay independent saved rows", () => {
    const { doc, note, clip } = researchStashFixture();
    const placed = apply(doc, { kind: "place_attached_footage", noteRowId: note.id, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(placed.ok).toBe(true);
    const extra = createResearchClipOccurrenceV2({
      rowId: researchId(730500), payloadId: researchId(730501), orderKey: "replacement",
      candidate: researchCandidate(),
      frameBinding: { clipId: researchId(710001), clipVersion: 3, mediaReferenceId: researchId(710008), loggedStartFrame: 12, loggedEndFrame: 108 },
    });
    const created = apply(placed.document, { kind: "create_stash_clip", bundleId: researchId(740500), row: extra, sectionId: null, parentRowId: note.id, afterRowId: null });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    const occupied = apply(created.document, { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: extra.id });
    expect(occupied.ok, JSON.stringify(occupied.diagnostics)).toBe(true);
    const returned = returnClip(occupied.document, clip.id);
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    const noteRow = returned.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2;
    expect(noteRow.attachedFootage?.clip.id).toBe(extra.id);
    expect(returned.document.stashOutline?.find((entry) => entry.rowId === clip.id)).toMatchObject({ kind: "clip", parentRowId: note.id });

    const changed = apply(placed.document, { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 44 });
    expect(changed.ok, JSON.stringify(changed.diagnostics)).toBe(true);
    expect((changed.document.activeDraft.blocks[0] as VisualOnlyBlockV2).stashOrigin?.returnEligible).toBe(false);
    const editedReturn = returnClip(changed.document, clip.id);
    expect(editedReturn.ok, JSON.stringify(editedReturn.diagnostics)).toBe(true);
    expect((editedReturn.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2).attachedFootage).toBeUndefined();
    expect(editedReturn.document.stashOutline?.find((entry) => entry.rowId === clip.id)?.kind).toBe("row");
    expect((editedReturn.document.stash!.flatMap((b) => b.rows).find((r) => r.id === clip.id) as VisualOnlyBlockV2).visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 24, durationFrames: 20 });
  });

  it("uses original anchors when owner is moved or missing, and refuses ambiguous fallback", () => {
    const { doc, note, clip, anchor } = researchStashFixture();
    const placed = apply(doc, { kind: "place_attached_footage", noteRowId: note.id, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(placed.ok).toBe(true);
    const moved = apply(placed.document, { kind: "set_stash_outline", entries: [
      { rowId: note.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: anchor.id, kind: "note", parentRowId: null, sectionId: null },
    ] });
    expect(moved.ok).toBe(true);
    const returnedMoved = returnClip(moved.document, clip.id);
    expect(returnedMoved.ok, JSON.stringify(returnedMoved.diagnostics)).toBe(true);
    expect(returnedMoved.document.stashOutline?.find((entry) => entry.rowId === clip.id)).toMatchObject({ kind: "clip", parentRowId: null });
    expect((returnedMoved.document.stash!.flatMap((b) => b.rows).find((r) => r.id === note.id) as NarrationBlockV2).attachedFootage).toBeUndefined();

    const missing = structuredClone(placed.document);
    missing.stash = missing.stash!.filter((b) => !b.rows.some((r) => r.id === note.id));
    missing.stashOutline = missing.stashOutline!.filter((entry) => entry.rowId !== note.id);
    expect(validateScriptDocumentV2(missing).valid).toBe(true);
    const returnedMissing = returnClip(missing, clip.id);
    expect(returnedMissing.ok, JSON.stringify(returnedMissing.diagnostics)).toBe(true);
    expect(returnedMissing.document.stashOutline?.map((entry) => entry.rowId)).toEqual([anchor.id, clip.id]);

    const ambiguous = structuredClone(missing);
    const active = ambiguous.activeDraft.blocks[0] as VisualOnlyBlockV2;
    active.stashOrigin!.originalAttachedNoteAfterSiblingRowId = null;
    const refused = returnClip(ambiguous, clip.id);
    expect(refused.ok).toBe(false);
    expect(refused.document).toBe(ambiguous);
  });
});
