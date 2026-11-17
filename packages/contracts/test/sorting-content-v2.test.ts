import { describe, expect, it } from "vitest";
import {
  applyCommentOperationV2, applyRowEditV2, createCommentStateV2, createSortingTrialV2,
  deserializeAuthoringDocumentV2, deserializeCommentStateV2, resumeSortingTrialV2,
  serializeAuthoringDocumentV2, serializeCommentStateV2, validateScriptDocumentV2,
  type RowEditCommandV2, type SortingAcceptanceV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
import { researchStashFixture } from "./issue-367-fixture.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
function row(n: number): NarrationBlockV2 {
  const text = `Words${n}`;
  return {
    id: id(n), type: "narration", orderKey: `${n}`, text,
    tokens: [{ id: id(n + 1000), value: text, startOffset: 0, endOffset: text.length }],
    primaryVisualSequence: { id: id(n + 2000), version: 1, slots: [{
      id: id(n + 3000), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1,
    }] }, overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}
function clip(n: number): VisualOnlyBlockV2 {
  return { id: id(n), type: "visual_only", orderKey: `${n}`, version: 1,
    payload: { kind: "visual", payloadId: id(n + 1000), pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: id(n + 2000) }, audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 48 } },
  };
}
function document(): ScriptDocumentV2 {
  return { schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Content Sorting",
    activeDraft: { blocks: [row(100), row(200), row(300)], supportingItems: [] },
    ideaOutline: [], extras: [], liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}` };
}
const gap = (afterRowId: string | null, beforeRowId: string | null, sectionId: string | null = null) => ({ sectionId, afterRowId, beforeRowId });
function seed() {
  let baseline = document();
  for (const command of [
    { kind: "create_stash_note", row: row(400), bundleId: id(8000), sectionId: null, parentRowId: null, afterRowId: null },
    { kind: "create_stash_note", row: row(500), bundleId: id(8001), sectionId: null, parentRowId: null, afterRowId: id(400) },
    { kind: "create_stash_clip", row: clip(600), bundleId: id(8002), sectionId: null, parentRowId: id(500), afterRowId: null },
  ] satisfies RowEditCommandV2[]) {
    const result = applyRowEditV2(baseline, baseline.rowEditRevision ?? 0, command);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    baseline = result.document;
  }
  return baseline;
}
function apply(trial: ReturnType<typeof createSortingTrialV2>, command: RowEditCommandV2) {
  const result = trial.apply(command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  return result.document;
}
function authored(textRow: NarrationBlockV2): NarrationBlockV2 {
  const tokens = textRow.tokens.map((token) => ({ ...token, startOffset: token.startOffset + 5, endOffset: token.endOffset + 5 }));
  return { ...textRow, text: `EDIT ${textRow.text}`, tokens: [tokens[0]!, ...tokens.slice(1)], version: textRow.version + 1 };
}
function literalNote(n: number, text: string): NarrationBlockV2 {
  const original = row(n);
  return { ...original, text, tokens: text ? [{ ...original.tokens[0]!, value: text, endOffset: text.length }] : [] };
}
function literalBaseline(text: string): ScriptDocumentV2 {
  const initial = document();
  const created = applyRowEditV2(initial, 0, {
    kind: "create_stash_note", bundleId: id(8800), row: literalNote(800, text),
    sectionId: null, parentRowId: null, afterRowId: null,
  });
  expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
  return created.document;
}
function narration(doc: ScriptDocumentV2, rowId: string): NarrationBlockV2 {
  const found = [...doc.activeDraft.blocks, ...(doc.stash ?? []).flatMap((bundle) => bundle.rows)].find((item) => item.id === rowId);
  if (found?.type !== "narration") throw new Error("Missing narration fixture");
  return found;
}
function copiedNote(doc: ScriptDocumentV2, sourceId: string): NarrationBlockV2 {
  const row = doc.activeDraft.blocks.find((item) => item.type === "narration" && item.stashOrigin?.sourceNoteRowId === sourceId);
  if (row?.type !== "narration") throw new Error("Missing independent Stash note copy");
  return row;
}
const activeIds = (doc: ScriptDocumentV2) => doc.activeDraft.blocks.map((item) => item.id);

describe("content-editable Sorting", () => {
  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes mixed edited-parent return as %s with exact replay, original history and no orphan", (outcome) => {
    const baseline = seed();
    const original = structuredClone(baseline);
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_stash_rows", rowIds: [id(500)], destination: gap(id(300), null) });
    const placedSnapshot = trial.document;
    const parent = copiedNote(trial.document, id(500));
    apply(trial, { kind: "edit_row", rowId: parent.id, row: authored(parent) });
    const editedSnapshot = trial.document;
    apply(trial, { kind: "stash_rows", rowIds: [parent.id, id(600)], bundleId: id(8900) });
    expect(trial.document.stashOutline?.find((entry) => entry.rowId === id(500))?.kind).toBe("note");
    expect(trial.document.stashOutline?.find((entry) => entry.rowId === parent.id)?.kind).toBe("row");
    expect(narration(trial.document, parent.id).text).toMatch(/^EDIT/);
    expect(narration(trial.document, id(500)).stashChecklist?.completed).toBe(true);
    const pending = trial.preview();
    const snapshot = trial.serialize();
    if (outcome === "all") {
      const undone = resumeSortingTrialV2(snapshot);
      expect(undone.returnToSorting()).toBe(true);
      for (const previous of [editedSnapshot, placedSnapshot, baseline]) {
        expect(undone.undo().ok).toBe(true);
        expect({ ...undone.document, rowEditRevision: 0 }).toEqual({ ...previous, rowEditRevision: 0 });
      }
    }
    const resumed = resumeSortingTrialV2(snapshot);
    expect(resumed.document).toEqual(pending);
    expect(resumed.returnToSorting()).toBe(true);
    const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(reloaded.ok).toBe(true);
    if (reloaded.ok) expect(reloaded.document).toEqual(result.document);
    const entries = result.document.stashOutline!;
    expect(entries.find((entry) => entry.rowId === id(500))?.kind).toBe("note");
    expect(entries.find((entry) => entry.rowId === parent.id)?.kind === "row").toBe(outcome === "all" || outcome === "edits_only");
    expect(entries.some((entry) => entry.rowId === id(600))).toBe(outcome !== "edits_only");
    expect(result.document.activeDraft.blocks.some((row) => row.id === id(600))).toBe(outcome === "edits_only");
    expect(narration(result.document, id(500)).text).toBe(row(500).text);
    expect(narration(result.document, id(500)).stashChecklist?.completed ?? false).toBe(outcome === "all" || outcome === "edits_only");
    if (outcome === "all" || outcome === "edits_only") expect(narration(result.document, parent.id).text).toMatch(/^EDIT/);
    expect(baseline).toEqual(original);
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("honors exact drop for a returned mixed branch in %s, not guessed historical neighbors", (outcome) => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_stash_rows", rowIds: [id(500)], destination: gap(id(300), null) });
    const parent = copiedNote(trial.document, id(500));
    apply(trial, { kind: "edit_row", rowId: parent.id, row: authored(parent) });
    apply(trial, { kind: "stash_rows", rowIds: [parent.id, id(600)], bundleId: id(8910),
      destination: { sectionId: null, parentRowId: null, afterRowId: null, beforeRowId: id(400) } });
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.document).toEqual(trial.document);
    const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(result.document.stashOutline?.find((entry) => entry.rowId === id(500))?.kind).toBe("note");
    expect(result.document.stashOutline?.some((entry) => entry.rowId === parent.id)).toBe(outcome === "all" || outcome === "edits_only");
    if (outcome === "all") expect(result.document.stashOutline?.[0]?.rowId).toBe(parent.id);
  });

  it("keeps attached-footage trims authored while parent-only placement remains layout", () => {
    const { doc, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(doc);
    apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "clear_out" });
    apply(trial, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null), includeDescendants: false });
    const copyId = copiedNote(trial.document, note.id).id;
    const saved = trial.serialize();
    const edits = resumeSortingTrialV2(saved).accept(doc, "edits_only");
    const sorting = resumeSortingTrialV2(saved).accept(doc, "sorting_only");
    expect(edits.ok, JSON.stringify(edits.diagnostics)).toBe(true);
    expect(sorting.ok, JSON.stringify(sorting.diagnostics)).toBe(true);
    expect(edits.document.stash?.flatMap((bundle) => bundle.rows).some((row) => row.id === note.id)).toBe(true);
    expect(edits.document.activeDraft.blocks.some((row) => row.id === copyId)).toBe(true);
    expect(sorting.document.activeDraft.blocks.some((row) => row.id === copyId)).toBe(false);
    expect(narration(edits.document, note.id).attachedFootage?.clip.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 24, durationFrames: 84 });
    expect(narration(sorting.document, note.id).attachedFootage?.clip.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 24, durationFrames: 36 });
    expect(validateScriptDocumentV2(edits.document).valid).toBe(true);
    expect(validateScriptDocumentV2(sorting.document).valid).toBe(true);
  });
  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("resolves literal note text and semantic speech separately under %s", (outcome) => {
    const raw = '  [outer [inner]] stray ] "quote" 😀\nline [ ';
    const rewritten = `${raw}\nwritten [again`;
    const baseline = literalBaseline(raw);
    const baselineCopy = structuredClone(baseline);
    const original = narration(baseline, id(800));
    expect(original.plainDirection).toBe(true);
    expect(original.text).toBe(raw);
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_stash_rows", rowIds: [id(800)], destination: gap(id(300), null) });
    const placed = copiedNote(trial.document, id(800));
    expect(placed.stashOrigin).toMatchObject({ kind: "note", sourceNoteRowId: id(800), returnEligible: true });
    // D84: copying is itself spoken; literal brackets need no Make spoken step.
    const spoken = placed;
    expect(spoken.text).toBe(raw);
    expect(spoken.plainDirection).toBeUndefined();
    expect(spoken.tokens.every((token) => token.spoken === undefined)).toBe(true);
    apply(trial, { kind: "edit_row", rowId: spoken.id, row: {
      ...spoken, text: rewritten, tokens: [{ ...spoken.tokens[0]!, value: rewritten, startOffset: 0, endOffset: rewritten.length }], version: spoken.version + 1,
    } });
    apply(trial, { kind: "move_rows", rowIds: [id(100)], destination: gap(id(300), placed.id) });
    const expectedPending = trial.preview();
    const saved = trial.serialize();
    const resumed = resumeSortingTrialV2(saved);
    expect(resumed.phase).toBe("preview");
    expect(resumed.document).toEqual(expectedPending);
    expect(resumed.apply({ kind: "delete_rows", rowIds: [id(200)] }).diagnostics[0]?.code).toBe("SORTING_READ_ONLY");
    expect(resumed.returnToSorting()).toBe(true);
    const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    const afterLoad = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(afterLoad.ok).toBe(true);
    if (!afterLoad.ok) return;
    expect(afterLoad.document).toEqual(result.document);
    const source = narration(afterLoad.document, id(800));
    expect(source.text).toBe(raw);
    expect(source.plainDirection).toBe(true);
    if (outcome === "all") {
      expect(activeIds(result.document)).toEqual([id(200), id(300), id(100), placed.id]);
      expect(narration(result.document, placed.id)).toMatchObject({ text: rewritten, stashOrigin: { kind: "note", returnEligible: false } });
      expect(narration(result.document, placed.id).plainDirection).toBeUndefined();
    } else if (outcome === "edits_only") {
      expect(activeIds(result.document)).toEqual([...activeIds(baseline), placed.id]);
      expect(narration(result.document, placed.id).text).toBe(rewritten);
      expect(narration(result.document, placed.id).plainDirection).toBeUndefined();
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(800))?.kind).toBe("note");
      expect(source.stashChecklist?.completed).toBe(true);
    } else if (outcome === "sorting_only") {
      expect(activeIds(result.document)).toEqual([id(200), id(300), id(100)]);
      expect(source).toEqual(original);
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(800))?.kind).toBe("note");
    } else {
      expect(result.document).toEqual(baseline);
      expect(source).toEqual(original);
    }
    expect(baseline).toEqual(baselineCopy);
  });

  it("restores semantic conversion and exact edited literal text through replayed Undo", () => {
    const raw = "literal] [nested] 🌼";
    const baseline = literalBaseline(raw);
    const trial = createSortingTrialV2(baseline);
    const snapshots = [trial.document];
    apply(trial, { kind: "place_stash_rows", rowIds: [id(800)], destination: gap(id(300), null) });
    snapshots.push(trial.document);
    apply(trial, { kind: "make_spoken", blockId: id(800), startOffset: 0, endOffset: raw.length });
    snapshots.push(trial.document);
    const spoken = narration(trial.document, id(800));
    const rewritten = "edited [not structural] ] 😁";
    apply(trial, { kind: "edit_row", rowId: id(800), row: { ...spoken, text: rewritten,
      tokens: [{ ...spoken.tokens[0]!, value: rewritten, endOffset: rewritten.length }], version: spoken.version + 1 } });
    snapshots.push(trial.document);
    apply(trial, { kind: "make_stage_direction", blockId: id(800), startOffset: 0, endOffset: rewritten.length });
    snapshots.push(trial.document);
    expect(narration(trial.document, id(800))).toMatchObject({ text: rewritten, plainDirection: true });
    const resumed = resumeSortingTrialV2(trial.serialize());
    for (let index = snapshots.length - 2; index >= 0; index -= 1) {
      const undone = resumed.undo();
      expect(undone.ok, JSON.stringify(undone.diagnostics)).toBe(true);
      expect({ ...resumed.document, rowEditRevision: 0 }).toEqual({ ...snapshots[index], rowEditRevision: 0 });
    }
    expect(resumed.accept(baseline)).toMatchObject({ ok: true, changed: false });
  });
  it("refuses reusing deleted identities without losing pending work, while Undo permits retry", () => {
    const baseline = document();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "create_row", row: row(700), destination: gap(id(300), null) });
    apply(trial, { kind: "delete_rows", rowIds: [id(700)] });
    const pending = trial.document;
    expect(trial.apply({ kind: "create_row", row: row(700), destination: gap(id(300), null) }).diagnostics[0]?.code).toBe("SORTING_ROW_ID_REUSED");
    expect(trial.document).toEqual(pending);
    expect(trial.undo().ok).toBe(true);
    expect(trial.undo().ok).toBe(true);
    apply(trial, { kind: "create_row", row: row(700), destination: gap(id(300), null) });
    apply(trial, { kind: "delete_rows", rowIds: [id(100)] });
    expect(trial.apply({ kind: "create_row", row: row(100), destination: gap(null, id(200)) }).diagnostics[0]?.code).toBe("SORTING_ROW_ID_REUSED");
    expect(trial.accept(baseline, "edits_only").ok).toBe(true);
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("classifies parked Stash authoring and moved-row deletion under %s", (outcome) => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "edit_row", rowId: id(400), row: authored(narration(baseline, id(400))) });
    apply(trial, { kind: "create_stash_note", row: row(700), bundleId: id(8200), sectionId: null, parentRowId: null, afterRowId: id(500) });
    apply(trial, { kind: "move_rows", rowIds: [id(200)], destination: gap(id(300), null) });
    apply(trial, { kind: "delete_rows", rowIds: [id(200)] });
    const resumed = resumeSortingTrialV2(trial.serialize());
    const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (outcome === "all" || outcome === "edits_only") {
      expect(activeIds(result.document)).toEqual([id(100), id(300)]);
      expect(narration(result.document, id(400)).text).toMatch(/^EDIT/);
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(400))?.kind).toBe("note");
      expect(result.document.stash?.flatMap((bundle) => bundle.rows).some((saved) => saved.id === id(700))).toBe(true);
    } else {
      expect(narration(result.document, id(400)).text).toBe(narration(baseline, id(400)).text);
      expect(result.document.stash?.flatMap((bundle) => bundle.rows).some((saved) => saved.id === id(700))).toBe(false);
      expect(activeIds(result.document)).toEqual(outcome === "sorting_only" ? [id(100), id(300), id(200)] : [id(100), id(200), id(300)]);
    }
  });

  it("preserves original note/clip conversion after sorting-only, including return and full Undo", () => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_stash_rows", rowIds: [id(500)], destination: gap(id(300), null) });
    const original = trial.document;
    const copyId = copiedNote(original, id(500)).id;
    const footage = original.activeDraft.blocks.find((item) => item.id === id(600));
    if (footage?.type !== "visual_only") throw new Error("Missing clip");
    apply(trial, { kind: "edit_row", rowId: footage.id, row: { ...footage, version: 2, payload: { ...footage.payload, framingPolicy: "cover" } } });
    expect(trial.undo().ok).toBe(true);
    expect({ ...trial.document, rowEditRevision: 0 }).toEqual({ ...original, rowEditRevision: 0 });
    apply(trial, { kind: "stash_rows", rowIds: [copyId, id(600)], bundleId: id(8300) });
    const accepted = trial.accept(baseline, "sorting_only");
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    expect(accepted.document.stashOutline).toEqual(baseline.stashOutline);
    expect(narration(accepted.document, id(500))).toEqual(narration(baseline, id(500)));
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s independently after mixed public operations, preview and reload", (outcome) => {
    const baseline = seed();
    const original = structuredClone(baseline);
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "create_row", row: row(700), destination: gap(id(300), null) });
    apply(trial, { kind: "move_rows", rowIds: [id(100)], destination: gap(id(700), null) });
    apply(trial, { kind: "place_stash_rows", rowIds: [id(400), id(500)], destination: gap(id(200), id(300)) });
    const copied400 = copiedNote(trial.document, id(400));
    const copied500 = copiedNote(trial.document, id(500));
    apply(trial, { kind: "edit_row", rowId: id(100), row: authored(narration(trial.document, id(100))) });
    // Each copy is already spoken (D84); source notes remain saved and unchanged.
    const footage = trial.document.activeDraft.blocks.find((item) => item.id === id(600));
    if (footage?.type !== "visual_only") throw new Error("Missing converted footage");
    apply(trial, { kind: "edit_row", rowId: footage.id, row: { ...footage, visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 10, durationFrames: 24 } }, version: 2 } });
    apply(trial, { kind: "delete_rows", rowIds: [id(200)] });
    const depth = trial.undoDepth;
    const pending = trial.preview();
    expect(trial.apply({ kind: "delete_rows", rowIds: [id(300)] }).diagnostics[0]?.code).toBe("SORTING_READ_ONLY");
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.phase).toBe("preview");
    expect(resumed.document).toEqual(pending);
    expect(resumed.undoDepth).toBe(depth);
    resumed.returnToSorting();
    expect(resumed.document).toEqual(pending);
    const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(saved.ok).toBe(true);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(baseline).toEqual(original);
    if (outcome === "discard") { expect(result.document).toEqual(baseline); return; }
    expect(result.document.rowEditRevision).toBe((baseline.rowEditRevision ?? 0) + (outcome === "sorting_only" ? 0 : 1));
    if (outcome === "all") {
      expect(activeIds(result.document)).toEqual([copied400.id, copied500.id, id(600), id(300), id(700), id(100)]);
      expect(narration(result.document, id(100)).text).toMatch(/^EDIT/);
      expect(narration(result.document, copied400.id).stashOrigin?.sourceNoteRowId).toBe(id(400));
      expect(narration(result.document, id(400)).stashChecklist?.completed).toBe(true);
    } else if (outcome === "edits_only") {
      expect(activeIds(result.document)).toContain(copied400.id);
      expect(activeIds(result.document)).toContain(copied500.id);
      expect(activeIds(result.document)).toContain(id(600));
      expect(activeIds(result.document)).not.toContain(id(200));
      expect(narration(result.document, id(100)).text).toMatch(/^EDIT/);
      expect(narration(result.document, id(400)).text).toBe(row(400).text);
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(400))?.kind).toBe("note");
      expect(narration(result.document, id(400)).stashChecklist?.completed).toBe(true);
      expect(result.document.stashOutline?.some((entry) => entry.rowId === id(600))).toBe(false);
    } else {
      // Sorting-only cannot retain an authored note-copy gesture or its clip.
      expect(activeIds(result.document).sort()).toEqual([id(100), id(200), id(300)].sort());
      expect(activeIds(result.document)).not.toContain(copied400.id);
      expect(activeIds(result.document)).not.toContain(copied500.id);
      expect(narration(result.document, id(100)).text).toBe(row(100).text);
      expect(narration(result.document, id(400)).text).toBe(row(400).text);
      expect(narration(result.document, id(400)).plainDirection).toBe(true);
      expect(narration(result.document, id(400)).stashChecklist?.completed ?? false).toBe(false);
      expect(result.document.stashOutline?.some((entry) => entry.rowId === id(600))).toBe(true);
    }
  });

  it("Undo restores every snapshot and converted eligibility while discussions survive row deletion outcomes", () => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    const snapshots: ScriptDocumentV2[] = [trial.document];
    apply(trial, { kind: "place_stash_rows", rowIds: [id(400)], destination: gap(id(300), null), includeDescendants: false });
    snapshots.push(trial.document);
    const copy = copiedNote(trial.document, id(400));
    for (const command of [
      { kind: "edit_row", rowId: copy.id, row: authored(copy) },
      { kind: "stash_rows", rowIds: [copy.id], bundleId: id(8100) },
      { kind: "create_row", row: row(700), destination: gap(id(300), null) },
      { kind: "delete_rows", rowIds: [id(200)] },
    ] satisfies RowEditCommandV2[]) { apply(trial, command); snapshots.push(trial.document); }
    const resumed = resumeSortingTrialV2(trial.serialize());
    for (let i = snapshots.length - 2; i >= 0; i--) {
      expect(resumed.undo().ok).toBe(true);
      expect({ ...resumed.document, rowEditRevision: 0 }).toEqual({ ...snapshots[i], rowEditRevision: 0 });
    }
    expect(resumed.accept(baseline)).toMatchObject({ ok: true, changed: false });

    for (const outcome of ["all", "edits_only", "sorting_only", "discard"] as const) {
      let comments = createCommentStateV2(baseline);
      const created = applyCommentOperationV2(comments, comments.revision, { kind: "create", id: "create", actorId: "producer", threadId: "thread", messageId: "message", body: "Keep this discussion", mentionActorIds: [], anchor: { kind: "block", blockId: id(200) } });
      if (!created.ok) throw new Error(created.error);
      comments = created.state;
      const deleted = createSortingTrialV2(baseline);
      apply(deleted, { kind: "delete_rows", rowIds: [id(200)] });
      const reply = applyCommentOperationV2(comments, comments.revision, { kind: "reply", id: "reply", actorId: "producer", threadId: "thread", messageId: "reply-message", body: "Reply while pending", mentionActorIds: [] });
      if (!reply.ok) throw new Error(reply.error);
      const context = { state: deserializeCommentStateV2(serializeCommentStateV2(reply.state)), id: "resolve-sorting", actorId: "producer" };
      const result = outcome === "discard" ? deleted.discard(baseline, context) : deleted.accept(baseline, outcome, context);
      expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
      expect(result.comments?.threads[0]?.messages).toHaveLength(2);
      expect(result.comments?.threads[0]?.attachment.status).toBe(outcome === "all" || outcome === "edits_only" ? "stale" : "attached");
      expect(result.comments && deserializeCommentStateV2(serializeCommentStateV2(result.comments))).toEqual(result.comments);
    }
  });

  it("refuses stale canonical, malformed commands and comment dependencies without closing or losing pending work", () => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "edit_row", rowId: id(100), row: authored(narration(baseline, id(100))) });
    const pending = trial.document;
    const stale = { ...baseline, title: "Outside change" };
    for (const mode of ["all", "edits_only", "sorting_only"] satisfies SortingAcceptanceV2[]) {
      expect(trial.accept(stale, mode)).toMatchObject({ ok: false, changed: false, document: stale, diagnostics: [{ code: "SORTING_BASELINE_CHANGED" }] });
      expect(trial.document).toEqual(pending);
    }
    expect(trial.apply({ kind: "create_row", row: row(700), destination: gap(null, null, id(9999)) }).ok).toBe(false);
    expect(trial.apply({ kind: "edit_row", rowId: id(9999), row: row(700) }).ok).toBe(false);
    expect(trial.apply({ kind: "delete_rows", rowIds: [id(100)] }, -1).ok).toBe(false);
    const invalidClip = { ...clip(710), invalid: () => "not saved JSON" };
    expect(trial.apply({ kind: "create_stash_clip", row: invalidClip, bundleId: id(8500), sectionId: null, parentRowId: null, afterRowId: null }).diagnostics[0]?.code).toBe("SORTING_COMMAND_INVALID");
    expect(trial.document).toEqual(pending);
    expect(trial.accept(baseline, "all", { state: createCommentStateV2(stale), id: "bad", actorId: "producer" }).ok).toBe(false);
    expect(trial.phase).toBe("sorting");
    expect(trial.document).toEqual(pending);
    const malformed = JSON.parse(trial.serialize()) as { actions: unknown[] };
    malformed.actions.push({ kind: "edit_row", rowId: id(100), row: null });
    expect(() => resumeSortingTrialV2(JSON.stringify(malformed))).toThrow(/SORTING_COMMAND_INVALID/);
    expect(trial.accept(baseline).ok).toBe(true);
  });
});
