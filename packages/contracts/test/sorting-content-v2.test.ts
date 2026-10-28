import { describe, expect, it } from "vitest";
import {
  applyCommentOperationV2, applyRowEditV2, createCommentStateV2, createSortingTrialV2,
  deserializeAuthoringDocumentV2, deserializeCommentStateV2, resumeSortingTrialV2,
  serializeAuthoringDocumentV2, serializeCommentStateV2, validateScriptDocumentV2,
  type RowEditCommandV2, type SortingAcceptanceV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";

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
function narration(doc: ScriptDocumentV2, rowId: string): NarrationBlockV2 {
  const found = [...doc.activeDraft.blocks, ...(doc.stash ?? []).flatMap((bundle) => bundle.rows)].find((item) => item.id === rowId);
  if (found?.type !== "narration") throw new Error("Missing narration fixture");
  return found;
}
const activeIds = (doc: ScriptDocumentV2) => doc.activeDraft.blocks.map((item) => item.id);

describe("content-editable Sorting", () => {
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
    const footage = original.activeDraft.blocks.find((item) => item.id === id(600));
    if (footage?.type !== "visual_only") throw new Error("Missing clip");
    apply(trial, { kind: "edit_row", rowId: footage.id, row: { ...footage, version: 2, payload: { ...footage.payload, framingPolicy: "cover" } } });
    expect(trial.undo().ok).toBe(true);
    expect({ ...trial.document, rowEditRevision: 0 }).toEqual({ ...original, rowEditRevision: 0 });
    apply(trial, { kind: "stash_rows", rowIds: [id(500), id(600)], bundleId: id(8300) });
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
    apply(trial, { kind: "edit_row", rowId: id(100), row: authored(narration(trial.document, id(100))) });
    const note = narration(trial.document, id(400));
    apply(trial, { kind: "make_spoken", blockId: note.id, startOffset: note.tokens[0].startOffset, endOffset: note.tokens.at(-1)!.endOffset });
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
    expect(result.document.rowEditRevision).toBe((baseline.rowEditRevision ?? 0) + 1);
    if (outcome === "all") {
      expect(activeIds(result.document)).toEqual([id(400), id(500), id(600), id(300), id(700), id(100)]);
      expect(narration(result.document, id(100)).text).toMatch(/^EDIT/);
      expect(narration(result.document, id(400)).stashOrigin?.returnEligible).toBe(false);
    } else if (outcome === "edits_only") {
      expect(activeIds(result.document)).toEqual([id(100), id(300), id(700)]);
      expect(narration(result.document, id(100)).text).toMatch(/^EDIT/);
      expect(narration(result.document, id(400)).text).toBe(row(400).text);
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(400))?.kind).toBe("row");
      expect(result.document.stashOutline?.find((entry) => entry.rowId === id(600))).toMatchObject({ kind: "row", parentRowId: id(500) });
    } else {
      // The move's only destination was the discarded new row: it is removed too.
      expect(activeIds(result.document)).toEqual([id(100), id(200), id(400), id(500), id(600), id(300)]);
      expect(narration(result.document, id(100)).text).toBe(row(100).text);
      expect(narration(result.document, id(400)).text).toBe(`[${row(400).text}]`);
      expect(narration(result.document, id(400)).stashOrigin?.returnEligible).toBe(true);
    }
  });

  it("Undo restores every snapshot and converted eligibility while discussions survive row deletion outcomes", () => {
    const baseline = seed();
    const trial = createSortingTrialV2(baseline);
    const snapshots: ScriptDocumentV2[] = [trial.document];
    for (const command of [
      { kind: "place_stash_rows", rowIds: [id(400)], destination: gap(id(300), null) },
      { kind: "edit_row", rowId: id(400), row: authored(narration(baseline, id(400))) },
      { kind: "stash_rows", rowIds: [id(400)], bundleId: id(8100) },
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
    expect(trial.accept(baseline, "all", { state: createCommentStateV2(stale), id: "bad", actorId: "producer" }).ok).toBe(false);
    expect(trial.phase).toBe("sorting");
    expect(trial.document).toEqual(pending);
    const malformed = JSON.parse(trial.serialize()) as { actions: unknown[] };
    malformed.actions.push({ kind: "edit_row", rowId: id(100), row: null });
    expect(() => resumeSortingTrialV2(JSON.stringify(malformed))).toThrow(/SORTING_COMMAND_INVALID/);
    expect(trial.accept(baseline).ok).toBe(true);
  });
});
