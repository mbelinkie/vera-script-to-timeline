import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  createRowEditSessionV2,
  createSortingTrialV2,
  resumeSortingTrialV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  selectRowRangeV2,
  validateScriptDocumentV2,
  type RowEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type {
  ContentSlot,
  DirectionBlock,
  NarrationBlockV2,
  NoteDraftBlock,
  OverlayEventV2,
  RowAudioSpanIntentV2,
  ScriptDocumentV2,
  SupportingItemV2,
  VisualOnlyBlockV2,
} from "@vera/contracts/v2";

const id = (value: number): string =>
  `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const contentHash = `sha256:${"a".repeat(64)}`;

function row(value: number): NarrationBlockV2 {
  const rowId = id(value);
  const tokenId = id(value + 1000);
  const text = `row${value} words`;
  const firstWord = `row${value}`;
  return {
    type: "narration",
    id: rowId,
    orderKey: `row-${value}`,
    text,
    tokens: [
      { id: tokenId, value: firstWord, startOffset: 0, endOffset: firstWord.length },
      { id: id(value + 2000), value: "words", startOffset: firstWord.length + 1, endOffset: text.length },
    ],
    primaryVisualSequence: {
      id: id(value + 3000),
      slots: [{
        id: id(value + 4000),
        kind: "content",
        relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval",
        version: 1,
      }],
      version: 1,
    },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "active",
    notes: [],
    version: 1,
  };
}

function section(value: number, title: string) {
  return { type: "section" as const, id: id(value), orderKey: `section-${value}`, title, version: 1 };
}

function wordAnchor(block: NarrationBlockV2, tokenIndex = 0) {
  const token = block.tokens[tokenIndex];
  if (!token) throw new Error(`Missing token ${tokenIndex} in row ${block.id}.`);
  return {
    blockId: block.id,
    tokenId: token.id,
    affinity: "before" as const,
    quotedWord: token.value,
    anchorVersion: 1,
  };
}

function richNarration(value: number): NarrationBlockV2 {
  const block = row(value);
  const first = block.tokens[0];
  const second = block.tokens[1];
  if (!first || !second) throw new Error(`Expected two tokens in row ${block.id}.`);
  const annotationRange = {
    blockId: block.id,
    startTokenId: first.id,
    endTokenId: second.id,
    startAffinity: "before" as const,
    endAffinity: "after" as const,
    quotedText: block.text,
    anchorVersion: 1,
  };
  const visualPayload = (payloadId: string, mediaReferenceId: string, pictureKind: "clip" | "image") => ({
    kind: "visual" as const,
    payloadId,
    pictureKind,
    source: { kind: "media_reference" as const, mediaReferenceId },
    sourceUsage: pictureKind === "clip" ? { sourceInFrame: 12 } : null,
    audioPolicy: "mute" as const,
    framingPolicy: "contain" as const,
  });
  const clip: ContentSlot = {
    id: id(value + 4000), kind: "content", relation: { kind: "base" },
    boundaryBefore: { kind: "row_start" },
    payload: visualPayload(id(value + 5000), id(value + 6000), "clip"),
    playoutPolicy: "match_structural_interval", version: 1,
  };
  const image: ContentSlot = {
    id: id(value + 4001), kind: "content", relation: { kind: "sequential" },
    boundaryBefore: { kind: "spoken_word", anchor: wordAnchor(block, 1) },
    payload: visualPayload(id(value + 5001), id(value + 6001), "image"),
    playoutPolicy: "match_structural_interval", version: 1,
  };
  const overlay: OverlayEventV2 = {
    id: id(value + 7000),
    payload: visualPayload(id(value + 7001), id(value + 7002), "image"),
    timing: {
      kind: "timed",
      start: { kind: "word", anchor: wordAnchor(block) },
      end: { kind: "word", anchor: wordAnchor(block, 1) },
    },
    version: 1,
  };
  block.primaryVisualSequence = { id: block.primaryVisualSequence!.id, slots: [clip, image], version: 1 };
  block.annotations = [{
    id: id(value + 8000), kind: "pronunciation_alias", range: annotationRange,
    value: "row pronunciation", includeInPrompter: true, version: 1,
  }];
  block.overlayEvents = [overlay];
  block.notes = ["Keep the visual sequence attached to this exact narration row."];
  return block;
}

function direction(value: number): DirectionBlock {
  return { type: "direction", id: id(value), orderKey: `direction-${value}`, text: "Hold on the wide shot.", buildBehavior: "timeline_marker", version: 1 };
}

function visualOnly(value: number): VisualOnlyBlockV2 {
  return {
    type: "visual_only", id: id(value), orderKey: `visual-${value}`, version: 1,
    payload: {
      kind: "visual", payloadId: id(value + 1000), pictureKind: "image",
      source: { kind: "media_reference", mediaReferenceId: id(value + 2000) },
      audioPolicy: "mute", framingPolicy: "contain",
    },
    visualOnlyTiming: { kind: "visual_only" },
  };
}

function noteDraft(value: number): NoteDraftBlock {
  return { type: "note_draft", id: id(value), orderKey: `note-${value}`, text: "Keep this note with the row run.", state: "excluded", version: 1 };
}

function citation(block: NarrationBlockV2): SupportingItemV2 {
  const anchor = wordAnchor(block);
  return {
    id: id(9000),
    version: 1,
    orderKey: "citation-1",
    role: "citation",
    content: "Source attached to this row",
    placement: { kind: "point", anchor: { kind: "word", anchor } },
    displayAttachment: { kind: "word", anchor },
  };
}

function audioSpan(
  value: number,
  startRowId: string,
  endRowId: string,
  settings: RowAudioSpanIntentV2["settings"] = { gainDb: -12, loop: true },
): RowAudioSpanIntentV2 {
  return {
    id: id(value),
    startRowId,
    endRowId,
    source: {
      mediaReferenceId: id(value + 1000),
      artifactId: id(value + 2000),
      artifactVersion: 3,
      contentHash,
    },
    settings,
  };
}

function documentWith(
  blocks: ScriptDocumentV2["activeDraft"]["blocks"],
  options: {
    supportingItems?: SupportingItemV2[];
    rowTransitions?: NonNullable<ScriptDocumentV2["rowTransitions"]>;
    rowReferences?: NonNullable<ScriptDocumentV2["rowReferences"]>;
    rowAudioSpans?: NonNullable<ScriptDocumentV2["rowAudioSpans"]>;
  } = {},
): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Row edit synthetic sample",
    activeDraft: { blocks, supportingItems: options.supportingItems ?? [] },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: contentHash,
    ...(options.rowTransitions ? { rowTransitions: options.rowTransitions } : {}),
    ...(options.rowReferences ? { rowReferences: options.rowReferences } : {}),
    ...(options.rowAudioSpans ? { rowAudioSpans: options.rowAudioSpans } : {}),
  };
}

function rows(document: ScriptDocumentV2): string[] {
  return document.activeDraft.blocks
    .filter((block) => block.type !== "section")
    .map((block) => block.id);
}

function gap(sectionId: string | null, afterRowId: string | null, beforeRowId: string | null) {
  return { sectionId, afterRowId, beforeRowId };
}

describe("provisional Sorting trials", () => {
  it("keeps script and saved Stash canonical until one complete acceptance", () => {
    const [a, b, c] = [richNarration(610), row(611), row(612)];
    const initial = documentWith([a, b, c], { supportingItems: [citation(a)] });
    const saved = applyRowEditV2(initial, 0, { kind: "stash_rows", rowIds: [c.id], bundleId: id(620) }).document;
    const before = structuredClone(saved);
    const trial = createSortingTrialV2(saved);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, b.id, null) }).ok).toBe(true);
    expect(trial.apply({ kind: "stash_rows", rowIds: [a.id], bundleId: id(621) }).ok).toBe(true);
    expect(trial.apply({ kind: "restore_stash", bundleId: id(620), destination: gap(null, b.id, null) }).ok).toBe(true);
    const intended = trial.document;
    const preview = trial.preview();
    expect(preview).toEqual(intended);
    preview.title = "Mutating a read-only snapshot cannot edit the trial";
    expect(trial.document).toEqual(intended);
    expect(trial.apply({ kind: "stash_rows", rowIds: [b.id], bundleId: id(622) }).diagnostics[0]?.code).toBe("SORTING_READ_ONLY");
    expect(trial.returnToSorting()).toBe(true);
    expect(trial.document).toEqual(intended);
    expect(saved).toEqual(before);
    const accepted = trial.accept(saved);
    expect(accepted).toMatchObject({ ok: true, changed: true });
    expect(accepted.document).toEqual({ ...intended, rowEditRevision: 2 });
    expect(accepted.document.stash?.[0]?.rows).toEqual([a]);
    expect(accepted.document.stash?.[0]?.supportingItems).toEqual([citation(a)]);
    expect(rows(accepted.document)).toEqual([b.id, c.id]);
    expect(trial.accept(accepted.document)).toMatchObject({ ok: false, changed: false, diagnostics: [{ code: "SORTING_TRIAL_CLOSED" }] });
    expect(saved).toEqual(before);
  });

  it("discards both trial surfaces and leaves even a changed canonical document untouched", () => {
    const [a, b] = [row(630), row(631)];
    const baseline = documentWith([a, b]);
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "stash_rows", rowIds: [a.id], bundleId: id(632) }).ok).toBe(true);
    trial.preview();
    const discard = trial.discard(baseline);
    expect(discard).toMatchObject({ ok: true, document: baseline });
    expect(discard.document).toBe(baseline);
    expect(trial.document).toEqual(baseline);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.undoDepth).toBe(0);
    expect(trial.returnToSorting()).toBe(false);
    expect(trial.accept(baseline).ok).toBe(false);
    const other = createSortingTrialV2(baseline);
    const changed = { ...baseline, title: "An intervening author edit" };
    expect(other.discard(changed).document).toBe(changed);
  });

  it("round-trips a pending preview and Undo history by replaying real row operations", () => {
    const [a, b, c] = [row(640), row(641), row(642)];
    const baseline = documentWith([a, b, c]);
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, c.id, null) }).ok).toBe(true);
    expect(trial.apply({ kind: "stash_rows", rowIds: [b.id], bundleId: id(643) }).ok).toBe(true);
    expect(trial.undo().ok).toBe(true);
    trial.preview();
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.phase).toBe("preview");
    expect(resumed.document).toEqual(trial.document);
    expect(resumed.movedRowIds).toEqual([a.id]);
    expect(resumed.undoDepth).toBe(1);
    const saved = trial.serialize();
    expect(resumed.accept(baseline).document).toEqual(trial.accept(baseline).document);
    const undone = resumeSortingTrialV2(saved);
    undone.returnToSorting();
    expect(undone.undo().ok).toBe(true);
    expect(undone.accept(baseline)).toMatchObject({ ok: true, changed: false, document: baseline });
  });

  it.each(["script", "stash", "revision", "live head"])("refuses acceptance after a changed %s baseline, including after resume", (surface) => {
    const [a, b, c] = [row(650), row(651), row(652)];
    const baseline = applyRowEditV2(documentWith([a, b, c]), 0, { kind: "stash_rows", rowIds: [c.id], bundleId: id(653) }).document;
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, b.id, null) }).ok).toBe(true);
    const resumed = resumeSortingTrialV2(trial.serialize());
    const changed = structuredClone(baseline);
    if (surface === "script") changed.title = "changed";
    if (surface === "stash") changed.stash![0]!.rows[0].orderKey = "changed";
    if (surface === "revision") changed.rowEditRevision = 17;
    if (surface === "live head") changed.liveHeadSequence = 1;
    const before = structuredClone(changed);
    const intended = resumed.document;
    const result = resumed.accept(changed);
    expect(result).toMatchObject({ ok: false, changed: false, diagnostics: [{ code: "SORTING_BASELINE_CHANGED" }] });
    expect(result.document).toBe(changed);
    expect(changed).toEqual(before);
    expect(resumed.document).toEqual(intended);
    expect(resumed.phase).toBe("sorting");
  });

  it("clears net deliberate moved marks at the original position, after Undo and Stash/restore", () => {
    const [a, b, c] = [row(660), row(661), row(662)];
    const baseline = documentWith([a, b, c]);
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, c.id, null) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([a.id]);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, null, b.id) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.apply({ kind: "move_rows", rowIds: [b.id], destination: gap(null, null, a.id) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([b.id]);
    expect(trial.undo().ok).toBe(true);
    expect(trial.apply({ kind: "stash_rows", rowIds: [b.id], bundleId: id(663) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([b.id]);
    expect(trial.apply({ kind: "restore_stash", bundleId: id(663), destination: gap(null, a.id, c.id) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.undo().ok).toBe(true);
    expect(trial.movedRowIds).toEqual([b.id]);
    expect(trial.undo().ok).toBe(true);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.accept(baseline)).toMatchObject({ ok: true, changed: false });
  });

  it("keeps trial content read-only and refuses corrupt or oversized saved trials", () => {
    const [a, b] = [row(670), row(671)];
    const baseline = documentWith([a, b]);
    const trial = createSortingTrialV2(baseline);
    const contentEdit = { kind: "edit_stash_row", row: a } as unknown as RowEditCommandV2;
    expect(trial.apply(contentEdit).diagnostics[0]?.code).toBe("SORTING_CONTENT_READ_ONLY");
    expect(trial.undoDepth).toBe(0);
    expect(trial.document).toEqual(baseline);
    const saved = JSON.parse(trial.serialize()) as { actions: unknown[] };
    saved.actions = [contentEdit];
    expect(() => resumeSortingTrialV2(JSON.stringify(saved))).toThrow(/SORTING_CONTENT_READ_ONLY/);
    saved.actions = [{ kind: "undo" }];
    expect(() => resumeSortingTrialV2(JSON.stringify(saved))).toThrow(/ROW_UNDO_EMPTY/);
    expect(() => resumeSortingTrialV2("x".repeat(5_000_001))).toThrow(/size limit/);
    expect(() => resumeSortingTrialV2("null")).toThrow(/Invalid saved/);
    saved.actions = Array.from({ length: 2001 }, () => ({ kind: "undo" }));
    expect(() => resumeSortingTrialV2(JSON.stringify(saved))).toThrow(/Invalid saved/);
  });

  it("does not mark an undone move when a later row displaces it, and accepts a Stash/restore no-op honestly", () => {
    const [a, b, c] = [row(690), row(691), row(692)];
    const baseline = documentWith([a, b, c]);
    const trial = createSortingTrialV2(baseline);
    trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, c.id, null) });
    trial.undo();
    trial.apply({ kind: "move_rows", rowIds: [b.id], destination: gap(null, null, a.id) });
    expect(trial.movedRowIds).toEqual([b.id]);
    trial.undo();
    trial.apply({ kind: "stash_rows", rowIds: [b.id], bundleId: id(693) });
    trial.apply({ kind: "restore_stash", bundleId: id(693), destination: gap(null, a.id, c.id) });
    expect(trial.movedRowIds).toEqual([]);
    const accepted = trial.accept(baseline);
    expect(accepted).toMatchObject({ ok: true, changed: false });
    expect(accepted.document).toBe(baseline);
    expect(trial.document).toEqual(baseline);
  });

  it("reuses transition/audio rules and refuses unsupported trial moves without adding history", () => {
    const [a, b, c] = [row(680), row(681), row(682)];
    const baseline = documentWith([a, b, c], {
      rowAudioSpans: [audioSpan(683, a.id, b.id)],
      rowTransitions: [{ id: id(684), fromRowId: a.id, toRowId: b.id, effect: "crossfade", settings: { frames: 5 }, state: "active" }],
    });
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "stash_rows", rowIds: [a.id], bundleId: id(685) }).diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(trial.undoDepth).toBe(0);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, c.id, null) }).ok).toBe(true);
    expect(trial.document.rowAudioSpans?.[0]?.review?.alert).toBe("Music now ends with this row. Review");
    expect(trial.document.rowTransitions?.[0]).toMatchObject({ state: "needs_review", settings: { frames: 5 } });
    expect(baseline.rowAudioSpans?.[0]?.review).toBeUndefined();
    expect(trial.undo().ok).toBe(true);
    expect(trial.document.rowAudioSpans).toEqual(baseline.rowAudioSpans);
    expect(trial.document.rowTransitions).toEqual(baseline.rowTransitions);
    expect(trial.accept(baseline)).toMatchObject({ ok: true, changed: false });
  });

  it("clears a returned row's mark while retaining relationship review rather than silently reapplying effects", () => {
    const [a, b, c] = [row(700), row(701), row(702)];
    const baseline = documentWith([a, b, c], {
      rowTransitions: [{ id: id(703), fromRowId: a.id, toRowId: b.id, effect: "crossfade", settings: { frames: 6 }, state: "active" }],
    });
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, c.id, null) }).ok).toBe(true);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, null, b.id) }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.document.rowTransitions?.[0]?.state).toBe("needs_review");
    expect(trial.accept(baseline)).toMatchObject({ ok: true, changed: true });
  });

  it("marks only the moved section's rows and clears them when that section returns", () => {
    const [a, b, c] = [row(710), row(711), row(712)];
    const baseline = documentWith([section(713, "First"), a, section(714, "Second"), b, section(715, "Third"), c]);
    const trial = createSortingTrialV2(baseline);
    expect(trial.apply({ kind: "move_section", sectionId: id(713), destination: { afterSectionId: id(715), beforeSectionId: null } }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([a.id]);
    expect(trial.apply({ kind: "move_section", sectionId: id(713), destination: { afterSectionId: null, beforeSectionId: id(714) } }).ok).toBe(true);
    expect(trial.movedRowIds).toEqual([]);
    expect(trial.accept(baseline)).toMatchObject({ ok: true, changed: false });
  });

  it("keeps a deliberate move marked when other moves restore only its numeric row index", () => {
    const [a, b, c] = [row(720), row(721), row(722)];
    const trial = createSortingTrialV2(documentWith([a, b, c]));
    expect(trial.apply({ kind: "move_rows", rowIds: [b.id], destination: gap(null, c.id, null) }).ok).toBe(true);
    expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(null, b.id, null) }).ok).toBe(true);
    expect(rows(trial.document)).toEqual([c.id, b.id, a.id]);
    expect(trial.movedRowIds).toEqual([b.id, a.id]);
  });

  it("keeps Undo and resume available when the bounded edit limit is reached", () => {
    const [a, b] = [row(730), row(731)];
    const baseline = documentWith([a, b]);
    const trial = createSortingTrialV2(baseline);
    for (let index = 0; index < 1000; index++) {
      const destination = index % 2 === 0 ? gap(null, b.id, null) : gap(null, null, b.id);
      expect(trial.apply({ kind: "move_rows", rowIds: [a.id], destination }).ok).toBe(true);
    }
    expect(trial.apply({ kind: "stash_rows", rowIds: [a.id], bundleId: id(732) }).diagnostics[0]?.code).toBe("SORTING_TRIAL_LIMIT");
    expect(trial.undoDepth).toBe(1000);
    expect(trial.undo().ok).toBe(true);
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.document).toEqual(trial.document);
    expect(resumed.undoDepth).toBe(999);
    expect(resumed.undo().ok).toBe(true);
  });
});

describe("authoring v2 whole-row edits", () => {
  it("moves one row within its section and marks separated pair intents for review", () => {
    const [a, b, c] = [row(10), row(11), row(12)];
    const sectionId = id(20);
    const document = documentWith([
      section(20, "First"), a, b, c,
    ], {
      rowTransitions: [
        { id: id(30), fromRowId: a.id, toRowId: b.id, effect: "crossfade", settings: { frames: 6 }, state: "active" },
        { id: id(31), fromRowId: b.id, toRowId: c.id, effect: "crossfade", settings: { frames: 8 }, state: "active" },
      ],
      rowReferences: [{ id: id(40), rowId: b.id, kind: "reference", anchor: { label: "kept with stable row id" } }],
    });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [b.id],
      destination: gap(sectionId, c.id, null),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([a.id, c.id, b.id]);
    expect(result.document.rowEditRevision).toBe(1);
    expect(result.document.rowTransitions?.map(({ state }) => state)).toEqual(["needs_review", "needs_review"]);
    expect(result.document.rowReferences).toEqual(document.rowReferences);

    const returned = applyRowEditV2(result.document, 1, {
      kind: "move_rows",
      rowIds: [b.id],
      destination: gap(sectionId, a.id, c.id),
    });
    expect(returned.ok).toBe(true);
    expect(rows(returned.document)).toEqual([a.id, b.id, c.id]);
    expect(returned.document.rowTransitions?.map(({ state }) => state)).toEqual(["needs_review", "needs_review"]);
  });

  it("moves a contiguous run across sections while preserving its internal transition and row content", () => {
    const [a, b, c, d, e] = [row(50), row(51), row(52), row(53), row(54)];
    const secondSectionId = id(61);
    const internalTransition = { id: id(70), fromRowId: b.id, toRowId: c.id, effect: "dip", settings: { frames: 5 }, state: "active" as const };
    const separatedTransition = { id: id(71), fromRowId: d.id, toRowId: e.id, effect: "cut", settings: {}, state: "active" as const };
    const document = documentWith([
      section(60, "First"), a, b, c,
      section(61, "Second"), d, e,
    ], {
      rowTransitions: [internalTransition, separatedTransition],
      rowReferences: [{ id: id(72), rowId: c.id, kind: "comment", anchor: { tokenId: c.tokens[0].id } }],
    });
    const movedRows = structuredClone([b, c]);

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [b.id, c.id],
      destination: gap(secondSectionId, d.id, e.id),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([a.id, d.id, b.id, c.id, e.id]);
    expect(result.document.activeDraft.blocks.filter((block) => block.id === b.id || block.id === c.id)).toEqual(movedRows);
    expect(result.document.rowTransitions).toEqual([
      internalTransition,
      { ...separatedTransition, state: "needs_review" },
    ]);
    expect(result.document.rowReferences).toEqual(document.rowReferences);
  });

  it("moves a section as a unit and keeps its row order", () => {
    const [a, b, c, d] = [row(80), row(81), row(82), row(83)];
    const firstSectionId = id(90);
    const secondSectionId = id(91);
    const span = audioSpan(92, c.id, d.id);
    const document = documentWith([
      section(90, "First"), a, b,
      section(91, "Second"), c, d,
    ], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_section",
      sectionId: secondSectionId,
      destination: { afterSectionId: null, beforeSectionId: firstSectionId },
    });

    expect(result.ok).toBe(true);
    expect(result.document.activeDraft.blocks.map((block) => block.id)).toEqual([
      secondSectionId, c.id, d.id, firstSectionId, a.id, b.id,
    ]);
    expect(result.document.rowAudioSpans).toEqual([span]);
  });

  it("selects a row range and stops at the next section boundary", () => {
    const [a, b, c, d] = [row(100), row(101), row(102), row(103)];
    const document = documentWith([
      section(110, "First"), a, b, c,
      section(111, "Second"), d,
    ]);

    expect(selectRowRangeV2(document, b.id, c.id)).toEqual({
      rowIds: [b.id, c.id], boundaryReached: false, diagnostics: [],
    });
    expect(selectRowRangeV2(document, c.id, d.id)).toEqual({
      rowIds: [c.id], boundaryReached: true, diagnostics: [],
    });
  });

  it("refuses stale, noncontiguous, and self-intersecting edits without changing the document", () => {
    const [a, b, c, d] = [row(120), row(121), row(122), row(123)];
    const sectionId = id(124);
    const document = documentWith([section(124, "First"), a, b, c, d]);

    const stale = applyRowEditV2(document, 1, {
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, d.id, null),
    });
    const noncontiguous = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [a.id, c.id], destination: gap(sectionId, d.id, null),
    });
    const selfIntersecting = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [b.id, c.id], destination: gap(sectionId, b.id, c.id),
    });
    const noOp = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, a.id, c.id),
    });

    for (const result of [stale, noncontiguous, selfIntersecting, noOp]) {
      expect(result.ok).toBe(false);
      expect(result.diagnostics.length).toBeGreaterThan(0);
      expect(result.document).toEqual(document);
    }
  });

  it("refuses to split a supporting item anchored between rows across active and stash bundles", () => {
    const [a, b] = [row(140), row(141)];
    const betweenRows = { kind: "between_blocks" as const, beforeBlockId: a.id, afterBlockId: b.id };
    const supportingItem: SupportingItemV2 = {
      id: id(142),
      version: 1,
      orderKey: "reference-1",
      role: "reference",
      content: "This reference belongs to the gap between these rows",
      placement: { kind: "point", anchor: betweenRows },
      displayAttachment: betweenRows,
    };
    const document = documentWith([section(143, "First"), a, b], { supportingItems: [supportingItem] });

    const result = applyRowEditV2(document, 0, {
      kind: "stash_rows", rowIds: [b.id], bundleId: id(144),
    });

    expect(result.ok).toBe(false);
    expect(result.diagnostics.length).toBeGreaterThan(0);
    expect(result.document).toEqual(document);
  });

  it("stashes and restores rows with anchored citations through a saved JSON roundtrip", () => {
    const [a, b] = [row(150), row(151)];
    const sectionId = id(152);
    const supportingItem = citation(b);
    const document = documentWith([section(152, "First"), a, b], {
      supportingItems: [supportingItem],
      rowReferences: [{ id: id(153), rowId: b.id, kind: "reference", anchor: { source: "notes" } }],
    });

    const stashed = applyRowEditV2(document, 0, {
      kind: "stash_rows", rowIds: [b.id], bundleId: id(154),
    });

    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    expect(rows(stashed.document)).toEqual([a.id]);
    expect(stashed.document.activeDraft.supportingItems).toEqual([]);
    expect(stashed.document.stash?.[0]).toMatchObject({
      id: id(154), rows: [b], supportingItems: [supportingItem],
      originalGap: gap(sectionId, a.id, null),
    });
    expect(stashed.document.rowReferences).toEqual(document.rowReferences);

    const savedJson = serializeAuthoringDocumentV2(stashed.document);
    const saved = deserializeAuthoringDocumentV2(savedJson);
    expect(saved.ok).toBe(true);
    if (!saved.ok) throw new Error("Expected saved row draft to deserialize.");
    expect(validateScriptDocumentV2(saved.document).valid).toBe(true);
    const restored = applyRowEditV2(saved.document, saved.document.rowEditRevision ?? 0, {
      kind: "restore_stash",
      bundleId: id(154),
      destination: gap(sectionId, a.id, null),
    });

    expect(restored.ok).toBe(true);
    expect(rows(restored.document)).toEqual([a.id, b.id]);
    expect(restored.document.activeDraft.blocks.find((block) => block.id === b.id)).toEqual(b);
    expect(restored.document.activeDraft.supportingItems).toEqual([supportingItem]);
    expect(restored.document.rowReferences).toEqual(document.rowReferences);
    expect(validateScriptDocumentV2(restored.document).valid).toBe(true);
  });

  it("preserves mixed rich row content, citations, and opaque comments through move, stash, and restore", () => {
    const rich = richNarration(320);
    const directionRow = direction(321);
    const visualRow = visualOnly(322);
    const noteRow = noteDraft(323);
    const movingRows = [rich, directionRow, visualRow, noteRow];
    const secondSectionId = id(331);
    const destination = row(324);
    const trailing = row(325);
    const supportingItem = citation(rich);
    const rowReferences: NonNullable<ScriptDocumentV2["rowReferences"]> = [{
      id: id(332), rowId: rich.id, kind: "comment",
      anchor: { commentId: "comment-27", tokenId: wordAnchor(rich, 1).tokenId, quotedText: "words" },
    }];
    const document = documentWith([
      section(330, "Source"), ...movingRows,
      section(331, "Destination"), destination, trailing,
    ], { supportingItems: [supportingItem], rowReferences });

    const moved = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: movingRows.map((block) => block.id),
      destination: gap(secondSectionId, destination.id, trailing.id),
    });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(rows(moved.document)).toEqual([destination.id, ...movingRows.map((block) => block.id), trailing.id]);
    expect(moved.document.activeDraft.blocks.filter((block) => movingRows.some((row) => row.id === block.id))).toEqual(movingRows);
    expect(moved.document.activeDraft.supportingItems).toEqual([supportingItem]);
    expect(moved.document.rowReferences).toEqual(rowReferences);

    const stashed = applyRowEditV2(moved.document, 1, {
      kind: "stash_rows",
      rowIds: movingRows.map((block) => block.id),
      bundleId: id(333),
    });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    expect(stashed.document.stash?.[0]?.rows).toEqual(movingRows);
    expect(stashed.document.stash?.[0]?.supportingItems).toEqual([supportingItem]);
    expect(stashed.document.rowReferences).toEqual(rowReferences);

    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(stashed.document));
    expect(saved.ok).toBe(true);
    if (!saved.ok) throw new Error("Expected mixed row stash to survive saved JSON roundtrip.");
    expect(saved.document.stash).toEqual(stashed.document.stash);
    expect(saved.document.rowReferences).toEqual(rowReferences);
    const restored = applyRowEditV2(saved.document, saved.document.rowEditRevision ?? 0, {
      kind: "restore_stash",
      bundleId: id(333),
      destination: gap(secondSectionId, destination.id, trailing.id),
    });
    expect(restored.ok).toBe(true);
    expect(restored.document.activeDraft.blocks.filter((block) => movingRows.some((row) => row.id === block.id))).toEqual(movingRows);
    expect(restored.document.activeDraft.supportingItems).toEqual([supportingItem]);
    expect(restored.document.rowReferences).toEqual(rowReferences);
    expect(validateScriptDocumentV2(restored.document).valid).toBe(true);
  });

  it("rejects duplicate stash IDs and nested payload identity collisions across saved surfaces", () => {
    const active = row(340);
    const parked = row(341);
    const destination = row(342);
    const sharedPayloadId = id(345);
    const makeImage = (payloadId: string, mediaReferenceId: string) => ({
      kind: "visual" as const, payloadId, pictureKind: "image" as const,
      source: { kind: "media_reference" as const, mediaReferenceId },
      sourceUsage: null, audioPolicy: "mute" as const, framingPolicy: "contain" as const,
    });
    for (const [block, mediaReferenceId] of [[active, id(346)], [parked, id(347)]] as const) {
      const sequence = block.primaryVisualSequence;
      const slot = sequence?.slots[0];
      if (!slot || slot.kind !== "content") throw new Error("Expected a base content slot.");
      slot.payload = makeImage(sharedPayloadId, mediaReferenceId);
    }
    const identityCollision = documentWith([section(343, "First"), active, section(344, "Second"), destination]);
    identityCollision.stash = [{ id: id(348), rows: [parked], supportingItems: [] }];
    const identityValidation = validateScriptDocumentV2(identityCollision);
    expect(identityValidation.valid).toBe(false);
    expect(identityValidation.diagnostics.map(({ code }) => code)).toContain("ENTITY_ID_DUPLICATE");

    const duplicateBundle = documentWith([section(349, "First"), row(350)]);
    const existingBundleId = id(351);
    duplicateBundle.stash = [
      { id: existingBundleId, rows: [row(352)], supportingItems: [] },
      { id: existingBundleId, rows: [row(353)], supportingItems: [] },
    ];
    const duplicateValidation = validateScriptDocumentV2(duplicateBundle);
    expect(duplicateValidation.valid).toBe(false);
    expect(duplicateValidation.diagnostics.map(({ code }) => code)).toContain("ENTITY_ID_DUPLICATE");
    const refused = applyRowEditV2(duplicateBundle, 0, {
      kind: "stash_rows", rowIds: [id(350)], bundleId: existingBundleId,
    });
    expect(refused.ok).toBe(false);
    expect(refused.document).toEqual(duplicateBundle);
  });

  it("distinguishes a standalone row identity from its payload without rejecting shared media references", () => {
    const standalone: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(600), orderKey: "a0", version: 1,
      payload: { kind: "visual", payloadId: id(600), pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: id(600) }, audioPolicy: "mute", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only" },
    };
    const document = documentWith([standalone]);
    expect(validateScriptDocumentV2(document).diagnostics).toContainEqual(expect.objectContaining({ code: "ENTITY_ID_DUPLICATE", jsonPath: "/activeDraft/blocks/0/payload/payloadId" }));
    standalone.id = id(601);
    expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
    const stashed = applyRowEditV2(document, 0, { kind: "stash_rows", rowIds: [standalone.id], bundleId: id(602) });
    expect(stashed.ok).toBe(true);
    expect(validateScriptDocumentV2(stashed.document)).toEqual({ valid: true, diagnostics: [] });
  });

  it("keeps stale parked timing as a serialized warning", () => {
    const active = row(100000);
    const parked = richNarration(360);
    const overlay = parked.overlayEvents[0]!;
    if (overlay.timing.kind !== "timed") throw new Error("Expected timed overlay fixture.");
    overlay.timing.start = { kind: "word", anchor: { ...wordAnchor(parked), tokenId: id(9999) } };
    const document = documentWith([section(362, "First"), active]);
    document.stash = [{ id: id(363), rows: [parked], supportingItems: [] }];

    const validationBeforeSave = validateScriptDocumentV2(document);
    expect(validationBeforeSave.valid, JSON.stringify(validationBeforeSave.diagnostics)).toBe(true);
    expect(validationBeforeSave.diagnostics).toContainEqual(expect.objectContaining({
      code: "STALE_PLACEMENT_ANCHOR", severity: "warning", jsonPath: "/stash/0/rows/0/overlayEvents/0/timing/start",
    }));

    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(document));
    expect(saved.ok).toBe(true);
    if (!saved.ok) throw new Error("Expected stale parked authoring to remain serializable.");
    const validation = validateScriptDocumentV2(saved.document);
    expect(validation.valid).toBe(true);
    expect(validation.diagnostics).toContainEqual(expect.objectContaining({
      code: "STALE_PLACEMENT_ANCHOR", severity: "warning", jsonPath: "/stash/0/rows/0/overlayEvents/0/timing/start",
    }));
  });

  it("rejects malformed saved authoring JSON at the serialization boundary", () => {
    const malformedJson = deserializeAuthoringDocumentV2("{");
    const invalidDocument = deserializeAuthoringDocumentV2("{}");
    const nonJsonOpaque = documentWith([section(364, "First"), row(365)], {
      rowReferences: [{ id: id(366), rowId: id(365), kind: "reference", anchor: { score: Number.NaN } }],
    });

    expect(malformedJson).toMatchObject({ ok: false, diagnostics: [{ code: "DOCUMENT_JSON_INVALID" }] });
    expect(invalidDocument.ok).toBe(false);
    if (invalidDocument.ok) throw new Error("Expected an invalid saved document to be refused.");
    expect(invalidDocument.diagnostics.map(({ code }) => code)).toContain("SCHEMA_INVALID");
    expect(() => serializeAuthoringDocumentV2(nonJsonOpaque)).toThrow();
  });

  it("keeps a full audio span intact when its contiguous run moves", () => {
    const [a, b, c, d, e] = [row(160), row(161), row(162), row(163), row(164)];
    const secondSectionId = id(166);
    const span = audioSpan(167, b.id, d.id, { volume: 0.7, loop: false });
    const document = documentWith([
      section(165, "First"), a, b, c, d,
      section(166, "Second"), e,
    ], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [b.id, c.id, d.id],
      destination: gap(secondSectionId, e.id, null),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([a.id, e.id, b.id, c.id, d.id]);
    expect(result.document.rowAudioSpans).toEqual([span]);
  });

  it("preserves the old audio endpoint and settings when one endpoint move needs review", () => {
    const [a, b, c, d, e] = [row(170), row(171), row(172), row(173), row(174)];
    const sectionId = id(175);
    const span = audioSpan(176, b.id, d.id, { volume: 0.55, ducking: "voice" });
    const document = documentWith([section(175, "First"), a, b, c, d, e], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [d.id],
      destination: gap(sectionId, e.id, null),
    });

    expect(result.ok).toBe(true);
    expect(result.document.rowAudioSpans).toEqual([{
      ...span,
      endRowId: b.id,
      review: {
        previousEndRowId: d.id,
        previousSettings: span.settings,
        alert: "Music now ends with this row. Review",
      },
    }]);
  });

  it("keeps a moved audio starting row as a one-row span with the original endpoint review details", () => {
    const [a, b, c, d, e] = [row(177), row(178), row(179), row(180), row(181)];
    const sectionId = id(182);
    const span = audioSpan(183, b.id, d.id, { volume: 0.6, fade: "short" });
    const document = documentWith([section(182, "First"), a, b, c, d, e], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [b.id],
      destination: gap(sectionId, e.id, null),
    });

    expect(result.ok).toBe(true);
    expect(result.document.rowAudioSpans).toEqual([{
      ...span,
      endRowId: b.id,
      review: {
        previousEndRowId: d.id,
        previousSettings: span.settings,
        alert: "Music now ends with this row. Review",
      },
    }]);
  });

  it("refuses partial, cross-section, overlapping, and stashed audio-span edits", () => {
    const [a, b, c, d, e, f] = [row(190), row(191), row(192), row(193), row(194), row(195)];
    const firstSectionId = id(196);
    const secondSectionId = id(197);
    const makeDocument = (rowAudioSpans: RowAudioSpanIntentV2[]) => documentWith([
      section(196, "First"), a, b, c, d, e,
      section(197, "Second"), f,
    ], { rowAudioSpans });
    const partial = applyRowEditV2(makeDocument([audioSpan(198, b.id, d.id)]), 0, {
      kind: "move_rows", rowIds: [c.id], destination: gap(firstSectionId, e.id, null),
    });
    const insertion = applyRowEditV2(makeDocument([audioSpan(199, b.id, d.id)]), 0, {
      kind: "move_rows", rowIds: [e.id], destination: gap(firstSectionId, b.id, c.id),
    });
    const crossSection = applyRowEditV2(makeDocument([audioSpan(200, b.id, d.id)]), 0, {
      kind: "move_rows", rowIds: [d.id], destination: gap(secondSectionId, f.id, null),
    });
    const overlap = applyRowEditV2(makeDocument([
      audioSpan(201, b.id, d.id), audioSpan(202, c.id, e.id),
    ]), 0, {
      kind: "move_rows", rowIds: [d.id], destination: gap(firstSectionId, e.id, null),
    });
    const stashed = applyRowEditV2(makeDocument([audioSpan(203, b.id, d.id)]), 0, {
      kind: "stash_rows", rowIds: [c.id], bundleId: id(204),
    });

    for (const result of [partial, insertion, crossSection, overlap, stashed]) {
      expect(result.ok).toBe(false);
      expect(result.diagnostics.map(({ code }) => code)).toContain("AUDIO_REVIEW_REQUIRED");
      expect(result.document).toEqual(makeDocument(result.document.rowAudioSpans ?? []));
    }
  });

  it("undoes every command atomically, including saved relationships, alerts and references", () => {
    const [a, b, c, d] = [row(400), row(401), row(402), row(403)];
    const first = id(410);
    const second = id(411);
    const base = documentWith([section(410, "First"), a, b, c, section(411, "Second"), d], {
      supportingItems: [citation(b)],
      rowReferences: [{ id: id(412), rowId: b.id, kind: "comment", anchor: { quote: b.text } }],
      rowTransitions: [{ id: id(413), fromRowId: a.id, toRowId: b.id, effect: "dissolve", settings: { frames: 8 }, state: "active" }],
    });
    const withAudio = structuredClone(base);
    withAudio.rowAudioSpans = [audioSpan(414, b.id, c.id)];
    const stashed = applyRowEditV2(base, 0, { kind: "stash_rows", rowIds: [b.id], bundleId: id(415) });
    expect(stashed.ok).toBe(true);
    const cases: { document: ScriptDocumentV2; command: RowEditCommandV2 }[] = [
      { document: withAudio, command: { kind: "move_rows", rowIds: [c.id], destination: gap(first, null, a.id) } },
      { document: withAudio, command: { kind: "move_section", sectionId: second, destination: { afterSectionId: null, beforeSectionId: first } } },
      { document: base, command: { kind: "stash_rows", rowIds: [b.id], bundleId: id(415) } },
      { document: stashed.document, command: { kind: "restore_stash", bundleId: id(415), destination: gap(first, a.id, c.id) } },
    ];
    for (const { document, command } of cases) {
      const session = createRowEditSessionV2(document);
      const result = session.apply(command);
      expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
      expect(session.undoDepth).toBe(1);
      if (command.kind === "move_rows") expect(session.document.rowAudioSpans?.[0]?.review?.alert).toBe("Music now ends with this row. Review");
      session.view("outline");
      session.view("stash");
      session.view("script");
      const undone = { ...document, rowEditRevision: (document.rowEditRevision ?? 0) + 2 };
      expect(session.undo().document).toEqual(undone);
      expect(session.undoDepth).toBe(0);
      const refused = session.apply({ kind: "move_rows", rowIds: [a.id], destination: gap(first, null, a.id) });
      expect(refused.ok).toBe(false);
      expect(session.document).toEqual(undone);
      expect(session.undoDepth).toBe(0);
    }
  });

  it("keeps isolated undo history when switching views and rejects stale session revisions", () => {
    const [a, b, c] = [row(180), row(181), row(182)];
    const sectionId = id(183);
    const document = documentWith([section(183, "First"), a, b, c]);
    const session = createRowEditSessionV2(document);

    const applied = session.apply({
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, c.id, null),
    });
    expect(applied.ok).toBe(true);
    expect(rows(session.document)).toEqual([a.id, c.id, b.id]);
    expect(session.undoDepth).toBe(1);

    applied.document.activeDraft.blocks.splice(0);
    const documentSnapshot = session.document;
    documentSnapshot.activeDraft.blocks.splice(0);
    const scriptSnapshot = session.view("script");
    scriptSnapshot.splice(0);
    expect(rows(session.document)).toEqual([a.id, c.id, b.id]);

    session.view("outline");
    session.view("script");
    session.view("stash");

    expect(session.revision).toBe(1);
    expect(session.undoDepth).toBe(1);
    expect(session.undo().ok).toBe(true);
    expect(session.revision).toBe(2);
    expect(session.document).toEqual({ ...document, rowEditRevision: 2 });
    expect(session.undoDepth).toBe(0);

    const stale = session.apply({
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, c.id, null),
    }, 1);
    expect(stale.ok).toBe(false);
    expect(stale.document).toEqual({ ...document, rowEditRevision: 2 });
    expect(session.revision).toBe(2);
    expect(session.apply({
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, c.id, null),
    }).ok).toBe(true);
    expect(session.document.rowEditRevision).toBe(3);
    expect(applyRowEditV2(session.document, 1, {
      kind: "move_rows", rowIds: [b.id], destination: gap(sectionId, a.id, c.id),
    }).ok).toBe(false);
  });

  it("does not let an old stale item hide a newly broken supporting anchor", () => {
    const [a, b, c] = [row(500), row(501), row(502)];
    const staleItem = citation(a);
    staleItem.placement = { kind: "point", anchor: { kind: "word", anchor: { ...wordAnchor(a), tokenId: id(9998) } } };
    const currentItem = { ...citation(b), id: id(520), placement: { kind: "point" as const, anchor: { kind: "between_blocks" as const, beforeBlockId: a.id, afterBlockId: b.id } } };
    const document = documentWith([a, b, c], { supportingItems: [staleItem, currentItem] });
    expect(validateScriptDocumentV2(document).diagnostics.filter((item) => item.code === "STALE_PLACEMENT_ANCHOR")).toHaveLength(1);
    const result = applyRowEditV2(document, 0, { kind: "move_rows", rowIds: [b.id], destination: gap(null, c.id, null) });
    expect(result.ok).toBe(false);
    expect(result.diagnostics.some((item) => item.code === "STALE_PLACEMENT_ANCHOR")).toBe(true);
    expect(result.document).toBe(document);
  });

  it("refuses changes within unresolved cross-section and reversed audio coverage", () => {
    const [a, b, x] = [row(530), row(531), row(532)];
    const first = id(540), second = id(541), third = id(542);
    const document = documentWith([section(540, "First"), a, section(541, "Second"), b, section(542, "Third"), x], {
      rowAudioSpans: [audioSpan(550, a.id, b.id)],
    });
    const commands: RowEditCommandV2[] = [
      { kind: "move_section", sectionId: third, destination: { afterSectionId: first, beforeSectionId: second } },
      { kind: "move_rows", rowIds: [x.id], destination: gap(second, null, b.id) },
    ];
    for (const command of commands) {
      const result = applyRowEditV2(document, 0, command);
      expect(result.ok).toBe(false);
      expect(result.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
      expect(result.document).toBe(document);
    }
    document.rowAudioSpans = [audioSpan(550, b.id, a.id)];
    expect(applyRowEditV2(document, 0, { kind: "move_rows", rowIds: [a.id], destination: gap(second, null, b.id) }).diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(applyRowEditV2(document, 0, { kind: "move_rows", rowIds: [x.id], destination: gap(null, null, null) }).ok).toBe(true);
    const acrossBoundary = documentWith([section(540, "First"), a, x, section(541, "Second"), b], { rowAudioSpans: [audioSpan(550, a.id, b.id)] });
    const result = applyRowEditV2(acrossBoundary, 0, { kind: "move_rows", rowIds: [x.id], destination: gap(second, null, b.id) });
    expect(result.ok).toBe(false);
    expect(result.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(result.document).toBe(acrossBoundary);
  });
});
