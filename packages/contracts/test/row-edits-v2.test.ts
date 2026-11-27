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
  const first = block.tokens[0]!;
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

function citation(block: NarrationBlockV2, value = 9000): SupportingItemV2 {
  const anchor = wordAnchor(block);
  return {
    id: id(value),
    version: 1,
    orderKey: value === 9000 ? "citation-1" : `citation-${value}`,
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

describe("#677 ordinary row transitions", () => {
  type TransitionCommand = Extract<RowEditCommandV2, { kind: "add_row_transition" | "remove_row_transition" }>;
  const clipRow = (value: number): NarrationBlockV2 => {
    const block = row(value);
    const root = block.primaryVisualSequence!.slots[0] as ContentSlot;
    root.payload = {
      kind: "visual", payloadId: id(value + 5000), pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: id(value + 6000) },
      sourceUsage: { sourceInFrame: 12 }, audioPolicy: "mute", framingPolicy: "contain",
    };
    return block;
  };
  const commandFor = (from: NarrationBlockV2 | VisualOnlyBlockV2, to: NarrationBlockV2 | VisualOnlyBlockV2, value = 99001): TransitionCommand => ({
    kind: "add_row_transition", transitionId: id(value), fromRowId: from.id, toRowId: to.id,
    expectedFromVersion: from.version, expectedToVersion: to.version,
  });
  const intentFor = (command: TransitionCommand) => ({
    id: command.transitionId, ...(command.fromRowId === undefined ? {} : { fromRowId: command.fromRowId }), toRowId: command.toRowId,
    effect: "Cross Dissolve", settings: { durationFrames: 24, alignment: "center" }, state: "active" as const,
  });
  const refuse = (document: ScriptDocumentV2, command: unknown, code: string, revision = document.rowEditRevision ?? 0) => {
    const original = structuredClone(document);
    const result = applyRowEditV2(document, revision, command as RowEditCommandV2);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(false);
    expect(result.diagnostics[0]?.code).toBe(code);
    expect(result.document).toBe(document);
    expect(document).toEqual(original);
  };

  it("adds one exact preset, persists it, removes it and records one Undo per action", () => {
    const [a, b, c, d] = [10000, 20000, 30000, 40000].map(clipRow) as [NarrationBlockV2, NarrationBlockV2, NarrationBlockV2, NarrationBlockV2];
    const add = commandFor(a, b);
    const other = intentFor(commandFor(c, d, 99002));
    const initial = documentWith([a, b, c, d], {
      rowTransitions: [other], rowReferences: [{ id: id(99003), rowId: b.id, kind: "comment", anchor: { label: "Keep" } }],
      rowAudioSpans: [audioSpan(99004, a.id, d.id)], supportingItems: [citation(a, 99005)],
    });
    const snapshot = structuredClone(initial);
    const session = createRowEditSessionV2(initial);
    const added = session.apply(add);
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    expect(added.document).toEqual({ ...initial, rowTransitions: [other, intentFor(add)], rowEditRevision: 1 });
    expect(session.undoDepth).toBe(1);
    expect(initial).toEqual(snapshot);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(added.document))).toEqual({ ok: true, document: added.document });
    expect(session.undo().document.rowTransitions).toEqual([other]);
    expect(session.redo().document.rowTransitions).toEqual([other, intentFor(add)]);
    const removed = session.apply({ ...add, kind: "remove_row_transition" });
    expect(removed.ok, JSON.stringify(removed.diagnostics)).toBe(true);
    expect(removed.document).toEqual({ ...initial, rowEditRevision: 4 });
    expect(session.undoDepth).toBe(2);
    expect(session.undo().document.rowTransitions).toEqual([other, intentFor(add)]);
    expect(session.redo().document.rowTransitions).toEqual([other]);
  });

  it("omits an empty transition collection and permits a single muted visual-only clip", () => {
    const a = clipRow(10000);
    const b = visualOnly(20000);
    b.payload = { ...b.payload, pictureKind: "clip" };
    b.visualOnlyTiming = { kind: "visual_only", selectedSourceRange: { startFrame: 12, durationFrames: 108 } };
    const initial = documentWith([a, b]);
    const add = commandFor(a, b);
    const added = applyRowEditV2(initial, 0, add);
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    expect(added.document.rowTransitions).toEqual([intentFor(add)]);
    const removed = applyRowEditV2(added.document, 1, { ...add, kind: "remove_row_transition" });
    expect(removed.ok, JSON.stringify(removed.diagnostics)).toBe(true);
    expect(removed.document).toEqual({ ...initial, rowEditRevision: 2 });
    expect(Object.hasOwn(removed.document, "rowTransitions")).toBe(false);
  });

  it("refuses invalid shape, stale document and row versions, and missing or reordered neighbors", () => {
    const a = clipRow(10000), b = clipRow(20000), c = clipRow(30000);
    const initial = documentWith([a, b, c]);
    const add = commandFor(a, b);
    for (const malformed of [
      { ...add, transitionId: "not-a-uuid" }, { ...add, fromRowId: "" }, { ...add, toRowId: null },
      { ...add, expectedFromVersion: 0 }, { ...add, expectedToVersion: 1.5 },
      { ...add, expectedToVersion: Number.MAX_SAFE_INTEGER + 1 }, { ...add, expectedToVersion: "1" },
      { ...add, expectedToVersion: undefined }, { ...add, effect: "cut" },
    ]) {
      refuse(initial, malformed, "ROW_COMMAND_INVALID");
      refuse(initial, { ...malformed, kind: "remove_row_transition" }, "ROW_COMMAND_INVALID");
    }
    refuse(initial, add, "ROW_REVISION_STALE", 1);
    refuse(initial, { ...add, expectedFromVersion: 2 }, "ROW_TRANSITION_STALE");
    refuse(initial, { ...add, expectedToVersion: 2 }, "ROW_TRANSITION_STALE");
    for (const blocks of [[b, a, c], [a, c], [b, c], [a, c, b]]) {
      refuse(documentWith(blocks), add, "ROW_TRANSITION_PAIR_INVALID");
    }
    refuse(initial, { ...add, toRowId: a.id }, "ROW_TRANSITION_PAIR_INVALID");
    const session = createRowEditSessionV2(initial);
    expect(session.apply({ ...add, expectedToVersion: 2 }).ok).toBe(false);
    expect(session.revision).toBe(0);
    expect(session.undoDepth).toBe(0);
  });

  it("authors a section-crossing transition and preserves it across an unrelated edit", () => {
    const a = clipRow(10000), b = clipRow(20000);
    const heading = section(99010, "Next");
    const session = createRowEditSessionV2(documentWith([a, heading, b]));
    const add = commandFor(a, b);
    const added = session.apply(add);
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    expect(added.document.rowTransitions).toEqual([intentFor(add)]);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(added.document))).toEqual({ ok: true, document: added.document });
    const renamed = session.apply({ kind: "rename_section", sectionId: heading.id, title: "New title" });
    expect(renamed.ok, JSON.stringify(renamed.diagnostics)).toBe(true);
    expect(renamed.document.rowTransitions).toEqual([intentFor(add)]);
    expect(session.apply({ ...add, kind: "remove_row_transition" }).document.rowTransitions).toBeUndefined();
  });

  it("saves a one-sided opening fade, protects its target, and removes it after review", () => {
    const a = clipRow(10000), b = clipRow(20000);
    const heading = section(99010, "Opening");
    const initial = documentWith([heading, direction(30000), a, b]);
    const add = { kind: "add_row_transition" as const, transitionId: id(99001), toRowId: a.id, expectedToVersion: a.version };
    refuse(initial, { ...add, expectedFromVersion: 1 }, "ROW_COMMAND_INVALID");
    refuse(initial, { ...add, fromRowId: b.id }, "ROW_COMMAND_INVALID");
    refuse(initial, { ...add, toRowId: b.id }, "ROW_TRANSITION_PAIR_INVALID");

    const session = createRowEditSessionV2(initial);
    const added = session.apply(add);
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    const intent = { ...intentFor(add), settings: { durationFrames: 24, alignment: "right" } };
    expect(added.document.rowTransitions).toEqual([intent]);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(added.document))).toEqual({ ok: true, document: added.document });
    expect(session.undo().document.rowTransitions).toBeUndefined();
    expect(session.redo().document.rowTransitions).toEqual([intent]);
    refuse(added.document, { ...add, transitionId: id(99002) }, "ROW_TRANSITION_PAIR_OCCUPIED");
    refuse(added.document, { kind: "delete_rows", rowIds: [a.id] }, "ROW_REFERENCE_REVIEW_REQUIRED");

    const inserted = session.apply({ kind: "create_row", row: clipRow(40000), destination: gap(heading.id, id(30000), a.id) });
    expect(inserted.ok, JSON.stringify(inserted.diagnostics)).toBe(true);
    expect(inserted.document.rowTransitions).toEqual([{ ...intent, state: "needs_review" }]);
    expect(session.apply({ ...add, kind: "remove_row_transition" }).document.rowTransitions).toBeUndefined();
  });

  it("refuses unsupported clip-root shapes on either side", () => {
    const a = clipRow(10000), b = clipRow(20000);
    const still = clipRow(20000);
    const stillRoot = still.primaryVisualSequence!.slots[0] as ContentSlot;
    if (stillRoot.payload.kind !== "visual") throw new Error("Expected visual fixture");
    stillRoot.payload = { ...stillRoot.payload, pictureKind: "image", sourceUsage: null };
    const audible = clipRow(20000);
    const audibleRoot = audible.primaryVisualSequence!.slots[0] as ContentSlot;
    if (audibleRoot.payload.kind !== "visual") throw new Error("Expected visual fixture");
    audibleRoot.payload = { ...audibleRoot.payload, audioPolicy: "quiet" };
    const rich = richNarration(20000);
    for (const incompatible of [row(20000), still, audible, rich, direction(20000), visualOnly(20000)]) {
      refuse(documentWith([a, incompatible]), commandFor(a, b), "ROW_TRANSITION_INELIGIBLE");
    }
    refuse(documentWith([row(10000), b]), commandFor(a, b), "ROW_TRANSITION_INELIGIBLE");
  });

  it("preserves exact and dormant pairs, prevents shared active rows, and removes only the named active intent", () => {
    const a = clipRow(10000), b = clipRow(20000), c = clipRow(30000), d = clipRow(40000);
    const add = commandFor(b, c);
    const previous = intentFor(commandFor(a, b, 99002));
    const next = intentFor(commandFor(c, d, 99003));
    for (const occupied of [previous, next, intentFor({ ...add, transitionId: id(99004) }), { ...intentFor({ ...add, transitionId: id(99004) }), state: "needs_review" as const }]) {
      refuse(documentWith([a, b, c, d], { rowTransitions: [occupied] }), add, "ROW_TRANSITION_PAIR_OCCUPIED");
    }
    const initial = documentWith([a, b, c, d]);
    refuse(initial, { ...add, transitionId: a.id.toUpperCase() }, "ROW_TRANSITION_ID_OCCUPIED");
    const saved = documentWith([a, b, c, d], { rowTransitions: [intentFor(add)] });
    const remove = { ...add, kind: "remove_row_transition" as const };
    refuse(saved, { ...remove, transitionId: id(99005) }, "ROW_TRANSITION_NOT_FOUND");
    refuse(saved, { ...remove, fromRowId: a.id, toRowId: b.id }, "ROW_TRANSITION_NOT_FOUND");
    refuse(saved, { ...remove, expectedToVersion: 2 }, "ROW_TRANSITION_STALE");
    refuse(saved, { ...remove, expectedFromVersion: 2 }, "ROW_TRANSITION_STALE");
    refuse(initial, remove, "ROW_TRANSITION_NOT_FOUND");
  });
  it("removes the exact reviewed transition after a move across sections and supports Undo and deletion", () => {
    const a = clipRow(10000), b = clipRow(20000), c = clipRow(30000), d = clipRow(40000);
    const heading = section(99010, "Next");
    const add = commandFor(a, b);
    const other = intentFor(commandFor(c, d, 99002));
    const session = createRowEditSessionV2(documentWith([a, b, heading, c, d], { rowTransitions: [other] }));
    expect(session.apply(add).ok).toBe(true);
    const moved = session.apply({ kind: "move_rows", rowIds: [b.id], destination: gap(heading.id, d.id, null) });
    expect(moved.ok).toBe(true);
    const reviewed = { ...intentFor(add), state: "needs_review" };
    expect(moved.document.rowTransitions).toEqual([other, reviewed]);
    const remove = { ...add, kind: "remove_row_transition" as const,
      expectedFromVersion: moved.document.activeDraft.blocks.find((block) => block.id === a.id)!.version,
      expectedToVersion: moved.document.activeDraft.blocks.find((block) => block.id === b.id)!.version };
    expect(session.apply({ kind: "delete_rows", rowIds: [a.id] }).diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    expect(session.apply({ ...remove, transitionId: other.id }).ok).toBe(false);
    expect(session.apply({ ...remove, toRowId: c.id }).ok).toBe(false);
    expect(session.apply({ ...remove, toRowId: id(99999) }).ok).toBe(false);
    expect(session.apply({ ...remove, expectedToVersion: remove.expectedToVersion + 1 }).ok).toBe(false);
    const removed = session.apply(remove);
    expect(removed.ok, JSON.stringify(removed.diagnostics)).toBe(true);
    expect(removed.document.rowTransitions).toEqual([other]);
    expect(removed.document.activeDraft).toEqual(moved.document.activeDraft);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(removed.document))).toEqual({ ok: true, document: removed.document });
    expect(session.undo().document.rowTransitions).toEqual([other, reviewed]);
    expect(session.redo().document.rowTransitions).toEqual([other]);
    expect(session.apply({ kind: "delete_rows", rowIds: [a.id] }).ok).toBe(true);
  });

  it("refuses removing a reviewed transition through a different current neighbor", () => {
    const a = clipRow(10000), b = clipRow(20000), c = clipRow(30000);
    const add = commandFor(a, b);
    const session = createRowEditSessionV2(documentWith([a, b, c]));
    expect(session.apply(add).ok).toBe(true);
    const moved = session.apply({ kind: "move_rows", rowIds: [b.id], destination: gap(null, c.id, null) });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    const blocks = moved.document.activeDraft.blocks;
    expect(blocks.map((block) => block.id)).toEqual([a.id, c.id, b.id]);
    expect(moved.document.rowTransitions).toEqual([{ ...intentFor(add), state: "needs_review" }]);
    const version = (target: { id: string }) => blocks.find((block) => block.id === target.id)!.version;
    const refused = session.apply({ kind: "remove_row_transition", transitionId: add.transitionId,
      fromRowId: a.id, toRowId: c.id, expectedFromVersion: version(a), expectedToVersion: version(c) });
    expect(refused).toMatchObject({ ok: false, document: moved.document, diagnostics: [{ code: "ROW_TRANSITION_NOT_FOUND" }] });
    expect(session.undoDepth).toBe(2);
  });

});

describe("#588 visual placement names", () => {
  const rename = (rowId: string, payloadId: string, name: string): RowEditCommandV2 =>
    ({ kind: "rename_visual_placement", rowId, payloadId, name });

  it("renames only one of several uses of the same media, with one document revision and Undo", () => {
    const first = richNarration(22000);
    const second = richNarration(32000);
    const wordless = visualOnly(42000);
    const firstSlot = first.primaryVisualSequence!.slots[0] as ContentSlot;
    const secondSlot = second.primaryVisualSequence!.slots[0] as ContentSlot;
    if (firstSlot.payload.kind !== "visual" || secondSlot.payload.kind !== "visual") throw new Error("Expected clips");
    secondSlot.payload.source = structuredClone(firstSlot.payload.source);
    wordless.payload.source = structuredClone(firstSlot.payload.source);
    const initial = documentWith([first, second, wordless]);
    expect(validateScriptDocumentV2(initial).valid).toBe(true);
    const baseline = structuredClone(initial);
    const session = createRowEditSessionV2(initial);

    const changed = session.apply(rename(first.id, firstSlot.payload.payloadId, "  Window   take ✨  "));
    expect(changed.ok, JSON.stringify(changed.diagnostics)).toBe(true);
    expect(session.revision).toBe(1);
    expect(session.undoDepth).toBe(1);
    const renamed = changed.document.activeDraft.blocks[0] as NarrationBlockV2;
    const newSlot = renamed.primaryVisualSequence!.slots[0] as ContentSlot;
    if (newSlot.payload.kind !== "visual") throw new Error("Expected clip");
    expect(newSlot.payload.displayName).toBe("Window   take ✨");
    expect(changed.document.activeDraft.blocks[1]).toEqual(second);
    expect(changed.document.activeDraft.blocks[2]).toEqual(wordless);
    const expected = structuredClone(initial);
    const expectedSlot = (expected.activeDraft.blocks[0] as NarrationBlockV2).primaryVisualSequence!.slots[0] as ContentSlot;
    if (expectedSlot.payload.kind !== "visual") throw new Error("Expected clip");
    expectedSlot.payload.displayName = "Window   take ✨";
    expected.rowEditRevision = 1;
    expect(changed.document).toEqual(expected);
    expect(initial).toEqual(baseline);

    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document));
    expect(reloaded.ok).toBe(true);
    if (reloaded.ok) expect(reloaded.document).toEqual(changed.document);
    expect(session.undo().ok).toBe(true);
    expect(session.undoDepth).toBe(0);
    expect(session.document).toEqual({ ...baseline, rowEditRevision: 2 });
  });

  it("targets waiting narration visuals, the first and extra wordless visuals, and saved Stash rows", () => {
    const spoken = richNarration(51000);
    const pending = structuredClone((spoken.primaryVisualSequence!.slots[1] as ContentSlot).payload);
    if (pending.kind !== "visual") throw new Error("Expected still");
    pending.payloadId = id(110000);
    spoken.unattachedVisuals = [{ slotId: id(110001), payload: pending, version: 1 }];
    const wordless = visualOnly(61000);
    const additional = structuredClone(wordless.payload);
    additional.payloadId = id(64000);
    wordless.additionalVisuals = [{ payload: additional, visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 2000 } }];
    const initial = documentWith([spoken, wordless]);
    const initialValidation = validateScriptDocumentV2(initial);
    expect(initialValidation.valid, JSON.stringify(initialValidation.diagnostics)).toBe(true);
    const session = createRowEditSessionV2(initial);
    expect(session.apply(rename(spoken.id, pending.payloadId, "Waiting still")).ok).toBe(true);
    expect(session.apply(rename(wordless.id, wordless.payload.payloadId, "First still")).ok).toBe(true);
    expect(session.apply(rename(wordless.id, additional.payloadId, "Second still")).ok).toBe(true);
    const saved = session.apply({ kind: "stash_rows", rowIds: [spoken.id], bundleId: id(69000) });
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    const renamedInStash = session.apply(rename(spoken.id, pending.payloadId, "Stashed still"));
    expect(renamedInStash.ok, JSON.stringify(renamedInStash.diagnostics)).toBe(true);
    const stashRow = renamedInStash.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(stashRow.unattachedVisuals![0]!.payload.displayName).toBe("Stashed still");
    expect((renamedInStash.document.activeDraft.blocks[0] as VisualOnlyBlockV2).additionalVisuals![0].payload.displayName).toBe("Second still");
    expect((renamedInStash.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.displayName).toBe("First still");
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document));
    expect(loaded.ok).toBe(true);
    if (loaded.ok) expect(loaded.document).toEqual(session.document);
    expect(session.undo().ok).toBe(true);
    expect((session.document.stash![0]!.rows[0] as NarrationBlockV2).unattachedVisuals![0]!.payload.displayName).toBe("Waiting still");
  });

  it("clears a custom name on whitespace and refuses no-ops without history or source mutation", () => {
    const clip = visualOnly(72000);
    const session = createRowEditSessionV2(documentWith([clip]));
    expect(session.apply(rename(clip.id, clip.payload.payloadId, "  Closeup  ")).ok).toBe(true);
    const named = session.document;
    const unchanged = session.apply(rename(clip.id, clip.payload.payloadId, "Closeup"));
    expect(unchanged.ok).toBe(false);
    expect(unchanged.diagnostics[0]?.code).toBe("ROW_EDIT_NO_CHANGE");
    expect(unchanged.document).toEqual(named);
    expect(session.undoDepth).toBe(1);
    expect(session.revision).toBe(1);
    const cleared = session.apply(rename(clip.id, clip.payload.payloadId, " \t\u2003 "));
    expect(cleared.ok, JSON.stringify(cleared.diagnostics)).toBe(true);
    expect((cleared.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload).not.toHaveProperty("displayName");
    expect(session.undoDepth).toBe(2);
    const secondClear = session.apply(rename(clip.id, clip.payload.payloadId, "  "));
    expect(secondClear.ok).toBe(false);
    expect(session.undoDepth).toBe(2);
    expect(session.undo().ok).toBe(true);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.displayName).toBe("Closeup");
    expect(session.undo().ok).toBe(true);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.displayName).toBeUndefined();
    expect(session.undoDepth).toBe(0);
  });

  it("refuses wrong row, missing or unsupported placement, malformed command and stale revision", () => {
    const clip = visualOnly(80000);
    const neighbor = visualOnly(83000);
    const onCamera = row(86000);
    const document = documentWith([clip, neighbor, onCamera]);
    const input = rename(clip.id, clip.payload.payloadId, "New name");
    const invalid: Array<[RowEditCommandV2, string]> = [
      [rename(neighbor.id, clip.payload.payloadId, "Wrong row"), "VISUAL_NOT_FOUND"],
      [rename(clip.id, id(89999), "Missing"), "VISUAL_NOT_FOUND"],
      [rename(onCamera.id, clip.payload.payloadId, "Not a visual"), "VISUAL_NOT_FOUND"],
      [rename(id(89998), clip.payload.payloadId, "Missing row"), "ROW_NOT_FOUND"],
      [rename("", clip.payload.payloadId, "Invalid"), "ROW_COMMAND_INVALID"],
      [rename(clip.id, "", "Invalid"), "ROW_COMMAND_INVALID"],
      [{ ...input, unexpected: "unsafe" } as unknown as RowEditCommandV2, "ROW_COMMAND_INVALID"],
      [{ ...input, name: null } as unknown as RowEditCommandV2, "ROW_COMMAND_INVALID"],
      [{ ...input, name: 12 } as unknown as RowEditCommandV2, "ROW_COMMAND_INVALID"],
      [Object.assign(Object.create({ inherited: true }), input) as RowEditCommandV2, "ROW_COMMAND_INVALID"],
    ];
    const unsupported = structuredClone(document);
    const visual = unsupported.activeDraft.blocks[0] as VisualOnlyBlockV2;
    visual.payload.pictureKind = "unresolved_visual";
    visual.payload.source = { kind: "unresolved_visual", description: "Choose footage" };
    expect(validateScriptDocumentV2(unsupported).valid).toBe(true);
    const unsupportedResult = applyRowEditV2(unsupported, 0, input);
    expect(unsupportedResult.ok).toBe(false);
    expect(unsupportedResult.diagnostics[0]?.code).toBe("VISUAL_RENAME_UNSUPPORTED");
    expect(unsupportedResult.document).toBe(unsupported);

    const session = createRowEditSessionV2(document);
    for (const [command, code] of invalid) {
      const current = session.document;
      const result = session.apply(command);
      expect(result.ok).toBe(false);
      expect(result.diagnostics[0]?.code).toBe(code);
      expect(result.document).toEqual(current);
      expect(session.revision).toBe(0);
      expect(session.undoDepth).toBe(0);
    }
    const stale = applyRowEditV2(document, 1, input);
    expect(stale.ok).toBe(false);
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(document);
    const exhausted = { ...document, rowEditRevision: Number.MAX_SAFE_INTEGER };
    const overflow = applyRowEditV2(exhausted, Number.MAX_SAFE_INTEGER, input);
    expect(overflow.ok).toBe(false);
    expect(overflow.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(overflow.document).toBe(exhausted);
    expect(document.activeDraft.blocks).toEqual([clip, neighbor, onCamera]);
  });

  it("keeps grouped Stash members atomic and refuses preexisting invalid alias data", () => {
    const [a, b] = [visualOnly(91000), visualOnly(94000)];
    const initial = documentWith([a, b]);
    const stashed = applyRowEditV2(initial, 0, { kind: "stash_rows", rowIds: [a.id, b.id], bundleId: id(98000) });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    const group = applyRowEditV2(stashed.document, 1, { kind: "group_stash_rows", groupId: id(99000), rowIds: [a.id, b.id] });
    expect(group.ok, JSON.stringify(group.diagnostics)).toBe(true);
    const session = createRowEditSessionV2(group.document);
    const attempt = session.apply(rename(a.id, a.payload.payloadId, "Not independently"));
    expect(attempt.ok).toBe(false);
    expect(attempt.diagnostics[0]?.code).toBe("STASH_GROUP_ATOMIC_REQUIRED");
    expect(session.document).toEqual(group.document);
    expect(session.undoDepth).toBe(0);

    const bad = structuredClone(initial);
    (bad.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.displayName = " \t ";
    const malformed = applyRowEditV2(bad, 0, rename(b.id, b.payload.payloadId, "Valid name"));
    expect(malformed.ok).toBe(false);
    expect(malformed.diagnostics.some((diagnostic) => diagnostic.code === "SCHEMA_INVALID")).toBe(true);
    expect(malformed.document).toBe(bad);
  });
});

describe("#580 narration splice across saved authoring extras", () => {
  it("keeps section order, annotation and overlay, citations, comment references and unrelated rows byte-for-byte", () => {
    const rich = richNarration(7500);
    const neighbor = row(81000);
    const marker = direction(7900);
    const reference: NonNullable<ScriptDocumentV2["rowReferences"]>[number] = {
      id: id(9001), rowId: rich.id, kind: "comment",
      anchor: { commentId: "review-7500", tokenId: wordAnchor(rich, 1).tokenId, quotedText: "words" },
    };
    const initial = documentWith([section(7800, "Part"), rich, marker, neighbor], {
      supportingItems: [citation(rich, 9000)], rowReferences: [reference],
    });
    expect(validateScriptDocumentV2(initial).diagnostics).toEqual([]);
    const baseline = structuredClone(initial);
    const session = createRowEditSessionV2(initial);
    const edited = session.apply({
      kind: "edit_narration_text", rowId: rich.id,
      startOffset: 0, endOffset: 0, insertedText: "Important ", editId: id(95000),
    });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    expect(edited.document.rowEditRevision).toBe(1);
    expect(session.undoDepth).toBe(1);
    expect(edited.document.activeDraft.blocks.map((block) => block.id)).toEqual(initial.activeDraft.blocks.map((block) => block.id));
    expect(edited.document.activeDraft.blocks.filter((block) => block.id !== rich.id))
      .toEqual(initial.activeDraft.blocks.filter((block) => block.id !== rich.id));
    const changed = edited.document.activeDraft.blocks[1];
    expect(changed?.type).toBe("narration");
    if (changed?.type !== "narration") return;
    expect(changed.tokens.slice(1).map((token) => token.id)).toEqual(rich.tokens.map((token) => token.id));
    expect(changed.tokens.slice(1).map((token) => token.startOffset)).toEqual(
      rich.tokens.map((token) => token.startOffset + "Important ".length),
    );
    expect(changed.notes).toEqual(rich.notes);
    expect(changed.annotations).toEqual(rich.annotations);
    expect(changed.overlayEvents).toEqual(rich.overlayEvents);
    // A newly spoken prefix needs an On Camera passage before the original
    // clip; that derived gap is not a replacement for either authored picture.
    const authoredPictures = (slots: ContentSlot[]) => slots
      .filter((slot) => slot.payload.kind === "visual")
      .map((slot) => ({ id: slot.id, payload: slot.payload }));
    expect(changed.primaryVisualSequence!.slots[0]).toMatchObject({
      kind: "content", payload: { kind: "on_camera" }, boundaryBefore: { kind: "row_start" },
    });
    expect(authoredPictures(changed.primaryVisualSequence!.slots.filter((slot): slot is ContentSlot => slot.kind === "content")))
      .toEqual(authoredPictures(rich.primaryVisualSequence!.slots.filter((slot): slot is ContentSlot => slot.kind === "content")));
    expect(edited.document.activeDraft.supportingItems).toEqual(initial.activeDraft.supportingItems);
    expect(edited.document.rowReferences).toEqual(initial.rowReferences);
    expect(edited.document.extras).toEqual([]);
    expect(validateScriptDocumentV2(edited.document).diagnostics).toEqual([]);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(edited.document));
    expect(loaded).toEqual({ ok: true, document: edited.document });

    expect(session.undo().ok).toBe(true);
    expect(session.undoDepth).toBe(0);
    expect(session.revision).toBe(2);
    const undoneWithoutRevision = structuredClone(session.document);
    delete undoneWithoutRevision.rowEditRevision;
    expect(undoneWithoutRevision).toEqual(baseline);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document)).ok).toBe(true);
    expect(session.undo().ok).toBe(false);
    expect(initial).toEqual(baseline);
  });

  it("P3 refuses a multi-picture row with anchored annotation, overlay and citation without losing any saved data", () => {
    const rich = richNarration(7600);
    const initial = documentWith([rich, row(81001)], { supportingItems: [citation(rich, 9100)] });
    const baseline = structuredClone(initial);
    expect(validateScriptDocumentV2(initial).diagnostics).toEqual([]);
    const session = createRowEditSessionV2(initial);
    const result = session.apply({
      kind: "edit_narration_text", rowId: rich.id,
      startOffset: 0, endOffset: rich.text.length, insertedText: "", editId: id(96000),
    });
    expect(result.ok).toBe(false);
    expect(result.diagnostics[0]?.code).toBe("RANGE_SEQUENCE_UNRESOLVED");
    expect(result.document).toEqual(initial);
    expect(session.document).toEqual(initial);
    expect(session.undoDepth).toBe(0);
    expect(session.revision).toBe(0);
    expect(session.undo().ok).toBe(false);
    expect(initial).toEqual(baseline);
  });

  it("refuses rewriting an externally quoted annotation/citation instead of saving silently stale anchors", () => {
    const rich = richNarration(7700);
    const document = documentWith([rich], { supportingItems: [citation(rich, 9200)] });
    expect(validateScriptDocumentV2(document).diagnostics).toEqual([]);
    const session = createRowEditSessionV2(document);
    const first = rich.tokens[0]!;
    const result = session.apply({
      kind: "edit_narration_text", rowId: rich.id,
      startOffset: first.startOffset, endOffset: first.endOffset,
      insertedText: "changed", editId: id(97000),
    });
    expect(result.ok).toBe(false);
    expect(result.diagnostics.map((item) => item.code)).toContain("STALE_TEXT_RANGE");
    expect(result.document).toEqual(document);
    expect(session.document).toEqual(document);
    expect(session.undoDepth).toBe(0);
    expect(session.revision).toBe(0);
  });
});

function gap(sectionId: string | null, afterRowId: string | null, beforeRowId: string | null) {
  return { sectionId, afterRowId, beforeRowId };
}

describe("script section-break edits", () => {
  it("creates a titled section at the exact between-row gap, preserving rows and the prior section", () => {
    const [a, b, c] = [row(800), row(801), row(802)];
    const initial = documentWith([a, b, c]);
    const sectionId = id(8100);
    const created = applyRowEditV2(initial, 0, {
      kind: "create_section", sectionId, title: "Chapter Two", destination: gap(null, a.id, b.id),
    });
    expect(created.ok).toBe(true);
    expect(created.document.activeDraft.blocks).toEqual([
      a, { type: "section", id: sectionId, orderKey: `section-${sectionId}`, title: "Chapter Two", version: 1 }, b, c,
    ]);
    expect(created.document.rowEditRevision).toBe(1);
    expect(rows(created.document)).toEqual([a.id, b.id, c.id]);
    expect(initial.activeDraft.blocks).toEqual([a, b, c]);
    expect(selectRowRangeV2(created.document, a.id, c.id)).toMatchObject({ rowIds: [a.id], boundaryReached: true });

    const named = documentWith([section(8101, "Opening"), a, b, c]);
    const inNamed = applyRowEditV2(named, 0, {
      kind: "create_section", sectionId, title: "  Kept as typed  ", destination: gap(id(8101), a.id, b.id),
    });
    expect(inNamed.ok).toBe(true);
    expect(inNamed.document.activeDraft.blocks).toEqual([
      section(8101, "Opening"), a,
      { type: "section", id: sectionId, orderKey: `section-${sectionId}`, title: "  Kept as typed  ", version: 1 }, b, c,
    ]);
    expect(inNamed.document.rowEditRevision).toBe(1);
    expect(validateScriptDocumentV2(inNamed.document).diagnostics).toEqual([]);
  });

  it("reviews a transition crossed by a new break and refuses changed music coverage", () => {
    const [a, b, c] = [row(892), row(893), row(894)];
    const command: RowEditCommandV2 = {
      kind: "create_section", sectionId: id(8920), title: "New chapter", destination: gap(null, a.id, b.id),
    };
    const musical = documentWith([a, b, c], { rowAudioSpans: [audioSpan(8921, a.id, c.id)] });
    const refused = applyRowEditV2(musical, 0, command);
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(refused.document).toBe(musical);

    const transition = {
      id: id(8922), fromRowId: a.id, toRowId: b.id, effect: "dip" as const,
      settings: { frames: 4 }, state: "active" as const,
    };
    const withTransition = documentWith([a, b, c], { rowTransitions: [transition] });
    const result = applyRowEditV2(withTransition, 0, command);
    expect(result.ok).toBe(true);
    expect(result.document.rowTransitions).toEqual([{ ...transition, state: "needs_review" }]);
    expect(rows(result.document)).toEqual([a.id, b.id, c.id]);
    expect(validateScriptDocumentV2(result.document).diagnostics).toEqual([]);
  });

  it("renames only the target heading title and version, with one document revision", () => {
    const [a, b] = [row(820), row(821)];
    const heading = section(8200, "Original");
    const initial = documentWith([heading, a, b]);
    const renamed = applyRowEditV2(initial, 0, {
      kind: "rename_section", sectionId: heading.id, title: "  Renamed exactly  ",
    });
    expect(renamed.ok).toBe(true);
    expect(renamed.document).toEqual({
      ...initial,
      rowEditRevision: 1,
      activeDraft: { ...initial.activeDraft, blocks: [{ ...heading, title: "  Renamed exactly  ", version: 2 }, a, b] },
    });
    expect(initial.activeDraft.blocks[0]).toEqual(heading);
  });

  it("atomically refuses blank titles, wrong gaps, bad IDs, duplicates, and stale CAS", () => {
    const [a, b, c] = [row(830), row(831), row(832)];
    const heading = section(8300, "Existing");
    const initial = documentWith([a, heading, b, c]);
    const snapshot = structuredClone(initial);
    const sectionId = id(8301);
    const create = { kind: "create_section" as const, sectionId, title: "New", destination: gap(heading.id, b.id, c.id) };
    const malformed: unknown[] = [
      { ...create, title: "" },
      { ...create, title: " \t " },
      { ...create, title: 4 },
      { ...create, sectionId: "not-a-uuid" },
      { ...create, sectionId: a.id },
      { ...create, sectionId: b.tokens[0]!.id },
      { ...create, destination: gap(heading.id, null, b.id) },
      { ...create, destination: gap(heading.id, c.id, null) },
      { ...create, destination: gap(heading.id, a.id, b.id) },
      { ...create, destination: gap(null, a.id, b.id) },
      { ...create, destination: { ...create.destination, beforeRowId: 5 } },
      { ...create, destination: { ...create.destination, extra: true } },
      { ...create, unexpected: true },
      { kind: "rename_section", sectionId: heading.id, title: " " },
      { kind: "rename_section", sectionId: heading.id, title: heading.title },
      { kind: "rename_section", sectionId: id(8302), title: "Missing" },
      { kind: "rename_section", sectionId: heading.id, title: "Other", extra: true },
    ];
    const accessor = { ...create };
    Object.defineProperty(accessor, "title", { get: () => "Accessor title", enumerable: true });
    malformed.push(accessor);
    for (const value of malformed) {
      const result = applyRowEditV2(initial, 0, value as RowEditCommandV2);
      expect(result.ok, JSON.stringify(value)).toBe(false);
      expect(result.document, JSON.stringify(value)).toBe(initial);
      expect(result.diagnostics.length).toBeGreaterThan(0);
    }
    expect(applyRowEditV2(initial, 0, { ...create, sectionId: a.id }).diagnostics[0]?.code)
      .toBe("SECTION_ID_DUPLICATE");
    const stale = applyRowEditV2(initial, 1, create);
    expect(stale.ok).toBe(false);
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(initial);
    const staleRename = applyRowEditV2(initial, 1, { kind: "rename_section", sectionId: heading.id, title: "Renamed" });
    expect(staleRename.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(staleRename.document).toBe(initial);
    expect(initial).toEqual(snapshot);
  });

  it("deletes a middle break without losing or rewriting its rows, references, music or reviewed transitions", () => {
    // Rich narration's second slot uses value+4001; keep it distinct from b's value+4000.
    const [a, b, c, d] = [richNarration(940), row(841), row(842), row(843)];
    const [first, middle, last] = [section(8400, "First"), section(8401, "Middle"), section(8402, "Last")];
    const span = audioSpan(8403, b.id, c.id, { gainDb: -9, loop: false });
    const oldBoundary = {
      id: id(8404), fromRowId: a.id, toRowId: b.id, effect: "crossfade" as const,
      settings: { frames: 7 }, state: "needs_review" as const,
    };
    const inSection = {
      id: id(8405), fromRowId: b.id, toRowId: c.id, effect: "dip" as const,
      settings: { frames: 6 }, state: "active" as const,
    };
    const initial = documentWith([first, a, middle, b, c, last, d], {
      rowAudioSpans: [span], rowTransitions: [oldBoundary, inSection],
      supportingItems: [citation(a, 8406)],
      rowReferences: [{ id: id(8407), rowId: c.id, kind: "comment", anchor: { label: "unchanged" } }],
    });
    const snapshot = structuredClone(initial);
    const result = applyRowEditV2(initial, 0, { kind: "delete_section_break", sectionId: middle.id });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks).toEqual([first, a, b, c, last, d]);
    expect(rows(result.document)).toEqual([a.id, b.id, c.id, d.id]);
    expect(result.document.rowAudioSpans).toEqual([span]);
    expect(result.document.rowTransitions).toEqual([oldBoundary, inSection]);
    expect(result.document.activeDraft.supportingItems).toEqual(initial.activeDraft.supportingItems);
    expect(result.document.rowReferences).toEqual(initial.rowReferences);
    expect(result.document.rowEditRevision).toBe(1);
    expect(validateScriptDocumentV2(result.document).diagnostics).toEqual([]);
    expect(selectRowRangeV2(result.document, a.id, c.id)).toMatchObject({
      rowIds: [a.id, b.id, c.id], boundaryReached: false,
    });
    expect(initial).toEqual(snapshot);
  });

  it("deletes leading and later breaks, leaving the first rows unsectioned and all other order intact", () => {
    const [a, b, c, d] = [row(850), row(851), row(852), row(853)];
    const [first, second, third] = [section(8500, "First"), section(8501, "Second"), section(8502, "Third")];
    const initial = documentWith([first, a, second, b, c, third, d]);
    const leading = applyRowEditV2(initial, 0, { kind: "delete_section_break", sectionId: first.id });
    expect(leading.ok).toBe(true);
    expect(leading.document.activeDraft.blocks).toEqual([a, second, b, c, third, d]);
    expect(selectRowRangeV2(leading.document, a.id, d.id)).toMatchObject({
      rowIds: [a.id], boundaryReached: true,
    });
    const later = applyRowEditV2(leading.document, 1, { kind: "delete_section_break", sectionId: third.id });
    expect(later.ok).toBe(true);
    expect(later.document.activeDraft.blocks).toEqual([a, second, b, c, d]);
    expect(selectRowRangeV2(later.document, b.id, d.id)).toMatchObject({
      rowIds: [b.id, c.id, d.id], boundaryReached: false,
    });
    expect(rows(later.document)).toEqual([a.id, b.id, c.id, d.id]);
    expect(initial.activeDraft.blocks).toEqual([first, a, second, b, c, third, d]);
  });

  it("refuses deleting a break that would newly span music over its former boundary", () => {
    const [a, b, c] = [row(860), row(861), row(862)];
    const [first, second] = [section(8600, "First"), section(8601, "Second")];
    // This unresolved cross-section source is retained at baseline; merging it
    // would create a new audible extent and must require explicit review.
    const span = audioSpan(8602, a.id, c.id);
    const initial = documentWith([first, a, second, b, c], { rowAudioSpans: [span] });
    const snapshot = structuredClone(initial);
    const command: RowEditCommandV2 = { kind: "delete_section_break", sectionId: second.id };
    const direct = applyRowEditV2(initial, 0, command);
    expect(direct.ok).toBe(false);
    expect(direct.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(direct.document).toBe(initial);
    const session = createRowEditSessionV2(initial);
    expect(session.apply(command).diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(session.document).toEqual(initial);
    expect(session.undoDepth).toBe(0);
    expect(session.undo().diagnostics[0]?.code).toBe("ROW_UNDO_EMPTY");
    expect(initial).toEqual(snapshot);
  });

  it("refuses missing, malformed and stale delete operations without changing the input", () => {
    const [a, b] = [row(870), row(871)];
    const first = section(8700, "First");
    const initial = documentWith([first, a, b]);
    const bad: unknown[] = [
      { kind: "delete_section_break", sectionId: id(8701) },
      { kind: "delete_section_break", sectionId: a.id },
      { kind: "delete_section_break", sectionId: "" },
      { kind: "delete_section_break", sectionId: "not-a-uuid" },
      { kind: "delete_section_break", sectionId: first.id, extra: true },
    ];
    for (const command of bad) {
      const result = applyRowEditV2(initial, 0, command as RowEditCommandV2);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(initial);
    }
    const stale = applyRowEditV2(initial, 1, { kind: "delete_section_break", sectionId: first.id });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(initial);
    const session = createRowEditSessionV2(initial);
    expect(session.apply({ kind: "delete_section_break", sectionId: id(8701) }).ok).toBe(false);
    expect(session.undoDepth).toBe(0);
  });

  it("gives create, rename and delete exactly one Undo each and persists every successful document", () => {
    const [a, b, c] = [row(880), row(881), row(882)];
    const heading = section(8800, "Original");
    const initial = documentWith([heading, a, b, c]);
    const commands: RowEditCommandV2[] = [
      { kind: "create_section", sectionId: id(8801), title: "New", destination: gap(heading.id, a.id, b.id) },
      { kind: "rename_section", sectionId: heading.id, title: "New name" },
      { kind: "delete_section_break", sectionId: heading.id },
    ];
    for (const command of commands) {
      const session = createRowEditSessionV2(initial);
      const outcome = session.apply(command);
      expect(outcome.ok, command.kind).toBe(true);
      expect(session.undoDepth).toBe(1);
      expect(session.revision).toBe(1);
      expect(outcome.document.rowEditRevision).toBe(1);
      expect(serializeAuthoringDocumentV2(outcome.document)).toBe(JSON.stringify(outcome.document));
      const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(outcome.document));
      expect(loaded.ok).toBe(true);
      if (loaded.ok) expect(loaded.document).toEqual(outcome.document);
      expect(session.undo().ok).toBe(true);
      expect(session.undoDepth).toBe(0);
      expect(session.revision).toBe(2);
      expect(session.document).toEqual({ ...initial, rowEditRevision: 2 });
      expect(session.undo().diagnostics[0]?.code).toBe("ROW_UNDO_EMPTY");
    }
  });

  it("refuses non-JSON section results instead of persisting a lossy document", () => {
    const [a, b] = [row(890), row(891)];
    const heading = section(8900, "Old");
    const initial = documentWith([heading, a, b], {
      rowReferences: [{ id: id(8901), rowId: a.id, kind: "reference", anchor: { score: Number.NaN } }],
    });
    for (const command of [
      { kind: "create_section", sectionId: id(8902), title: "New", destination: gap(heading.id, a.id, b.id) },
      { kind: "rename_section", sectionId: heading.id, title: "New" },
      { kind: "delete_section_break", sectionId: heading.id },
    ] satisfies RowEditCommandV2[]) {
      const result = applyRowEditV2(initial, 0, command);
      expect(result.ok, command.kind).toBe(false);
      expect(result.document, command.kind).toBe(initial);
      expect(result.diagnostics.length).toBeGreaterThan(0);
    }
  });
});

describe("provisional Sorting trials", () => {
  it("keeps script and saved Stash canonical until one complete acceptance", () => {
    const [a, b, c] = [richNarration(610), row(630), row(650)];
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
    expect(trial.undo().document).toEqual(baseline);
    expect(trial.apply({ kind: "stash_rows", rowIds: [a.id], bundleId: id(633) }).document).toEqual(baseline);
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

  it("refuses unsupported commands and corrupt or oversized saved trials", () => {
    const [a, b] = [row(670), row(671)];
    const baseline = documentWith([a, b]);
    const trial = createSortingTrialV2(baseline);
    const contentEdit = { kind: "edit_stash_row", row: a } as unknown as RowEditCommandV2;
    expect(trial.apply(contentEdit).diagnostics[0]?.code).toBe("SORTING_COMMAND_INVALID");
    expect(trial.undoDepth).toBe(0);
    expect(trial.document).toEqual(baseline);
    const saved = JSON.parse(trial.serialize()) as { actions: unknown[] };
    saved.actions = [contentEdit];
    expect(() => resumeSortingTrialV2(JSON.stringify(saved))).toThrow(/SORTING_COMMAND_INVALID/);
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
    expect(trial.document.rowAudioSpans?.[0]?.review?.alert).toBe("Music shortened by this move");
    expect(trial.document.rowTransitions?.[0]).toMatchObject({ state: "needs_review", settings: { frames: 5 } });
    expect(baseline.rowAudioSpans?.[0]?.review).toBeUndefined();
    expect(trial.undo().ok).toBe(true);
    expect(trial.document.rowAudioSpans).toEqual(baseline.rowAudioSpans);
    expect(trial.document.rowTransitions).toEqual(baseline.rowTransitions);
    expect(trial.accept(baseline)).toMatchObject({ ok: true, changed: false });
  });

  it("previews and cancels shortening, then exactly undoes it in Sorting", () => {
    const [a, b, c, d, e] = [row(686), row(687), row(688), row(689), row(690)];
    const baseline = documentWith([a, b, c, d, e], { rowAudioSpans: [audioSpan(691, a.id, e.id)] });
    const command: RowEditCommandV2 = {
      kind: "move_rows", rowIds: [e.id], destination: gap(null, c.id, d.id),
    };
    const cancelled = createSortingTrialV2(baseline);
    expect(cancelled.apply(command).ok).toBe(true);
    const preview = cancelled.preview();
    expect(preview.rowAudioSpans?.[0]).toMatchObject({ endRowId: c.id, review: { previousEndRowId: e.id, alert: "Music shortened by this move" } });
    expect(baseline.rowAudioSpans?.[0]).toEqual(audioSpan(691, a.id, e.id));
    expect(cancelled.discard(baseline)).toMatchObject({ ok: true, document: baseline });
    expect(cancelled.document).toEqual(baseline);

    const undoTrial = createSortingTrialV2(baseline);
    expect(undoTrial.apply(command).ok).toBe(true);
    undoTrial.preview();
    expect(undoTrial.returnToSorting()).toBe(true);
    expect(undoTrial.undo().ok).toBe(true);
    expect(undoTrial.document).toEqual({ ...baseline, rowEditRevision: 2 });
    expect(undoTrial.document.rowAudioSpans).toEqual(baseline.rowAudioSpans);
    expect(undoTrial.undoDepth).toBe(0);
    expect(undoTrial.accept(baseline)).toMatchObject({ ok: true, changed: false, document: baseline });
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
  }, 15_000);
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
      rowReferences: [{ id: id(72), rowId: c.id, kind: "comment", anchor: { tokenId: c.tokens[0]!.id } }],
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
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
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

  it("keeps the original prefix when moving the audio end row interrupts its coverage", () => {
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
      endRowId: c.id,
      review: {
        previousEndRowId: d.id,
        previousSettings: span.settings,
        alert: "Music shortened by this move",
      },
    }]);
  });

  it("refuses shortening a matched cue instead of stranding its visual", () => {
    const [a, b, c, d, e] = [row(184), row(185), row(186), visualOnly(187), row(188)];
    const sectionId = id(189);
    const span = audioSpan(190, a.id, d.id);
    d.visualOnlyTiming.matchAudioDuration = { cueId: span.id };
    const document = documentWith([section(189, "First"), a, b, c, d, e], {
      rowAudioSpans: [span],
    });

    expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
    const result = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [d.id], destination: gap(sectionId, e.id, null),
    });

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContainEqual(expect.objectContaining({
      code: "MUSIC_MATCH_STRANDED", blockId: d.id, entityId: span.id,
    }));
    expect(result.diagnostics[0]?.message).toContain("Clear Match audio duration");
    expect(result.document).toBe(document);
    expect(rows(document)).toEqual([a.id, b.id, c.id, d.id, e.id]);
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
        alert: "Music shortened by this move",
      },
    }]);
  });

  it("ends ABCDE→ABCED music at C, the first interrupted original join", () => {
    const [a, b, c, d, e] = [row(300), row(301), row(302), row(303), row(304)];
    const sectionId = id(305);
    const span = audioSpan(8_000, a.id, e.id, { gainDb: -12, fade: "in" });
    const document = documentWith([section(305, "First"), a, b, c, d, e], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [e.id], destination: gap(sectionId, c.id, d.id),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([a.id, b.id, c.id, e.id, d.id]);
    expect(result.document.rowAudioSpans).toEqual([{
      ...span,
      endRowId: c.id,
      review: {
        previousEndRowId: e.id,
        previousSettings: span.settings,
        alert: "Music shortened by this move",
      },
    }]);
  });

  it("keeps #125 music through chalk-crescent when only paper-signal-frame moves past two rows", () => {
    const [start, chalkCrescent, paperSignalFrame, unrelatedOne, unrelatedTwo] = [
      row(310), row(311), row(312), row(313), row(314),
    ];
    const sectionId = id(315);
    const span = audioSpan(8_010, start.id, paperSignalFrame.id);
    const document = documentWith([
      section(315, "First"), start, chalkCrescent, paperSignalFrame, unrelatedOne, unrelatedTwo,
    ], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows",
      rowIds: [paperSignalFrame.id],
      destination: gap(sectionId, unrelatedTwo.id, null),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([start.id, chalkCrescent.id, unrelatedOne.id, unrelatedTwo.id, paperSignalFrame.id]);
    expect(result.document.rowAudioSpans).toEqual([{
      ...span,
      endRowId: chalkCrescent.id,
      review: {
        previousEndRowId: paperSignalFrame.id,
        previousSettings: span.settings,
        alert: "Music shortened by this move",
      },
    }]);
  });

  it("shortens at the first break from a moved middle row, unrelated insertion, or group", () => {
    const [a, b, c, d, e, x, y] = [
      row(320), row(321), row(322), row(323), row(324), row(325), row(326),
    ];
    const sectionId = id(327);
    const span = audioSpan(8_020, a.id, e.id, { gainDb: -18, loop: true });
    const cases = [
      {
        document: documentWith([section(327, "First"), a, b, c, d, e, x], { rowAudioSpans: [span] }),
        command: { kind: "move_rows" as const, rowIds: [c.id], destination: gap(sectionId, e.id, x.id) },
        expectedRows: [a.id, b.id, d.id, e.id, c.id, x.id],
        expectedEnd: b.id,
      },
      {
        document: documentWith([section(327, "First"), a, b, c, d, e, x], { rowAudioSpans: [span] }),
        command: { kind: "move_rows" as const, rowIds: [x.id], destination: gap(sectionId, a.id, b.id) },
        expectedRows: [a.id, x.id, b.id, c.id, d.id, e.id],
        expectedEnd: a.id,
      },
      {
        document: documentWith([section(327, "First"), a, b, c, d, e, x, y], { rowAudioSpans: [span] }),
        command: { kind: "move_rows" as const, rowIds: [x.id, y.id], destination: gap(sectionId, a.id, b.id) },
        expectedRows: [a.id, x.id, y.id, b.id, c.id, d.id, e.id],
        expectedEnd: a.id,
      },
    ];

    for (const { document, command, expectedRows, expectedEnd } of cases) {
      const result = applyRowEditV2(document, 0, command);
      expect(result.ok).toBe(true);
      expect(rows(result.document)).toEqual(expectedRows);
      expect(result.document.rowAudioSpans).toEqual([{
        ...span,
        endRowId: expectedEnd,
        review: {
          previousEndRowId: e.id,
          previousSettings: span.settings,
          alert: "Music shortened by this move",
        },
      }]);
    }
  });

  it("leaves an unaffected span unchanged when an unrelated row moves outside it", () => {
    const [a, b, c, x] = [row(330), row(331), row(332), row(333)];
    const sectionId = id(334);
    const span = audioSpan(8_030, a.id, b.id);
    const document = documentWith([section(334, "First"), a, b, c, x], { rowAudioSpans: [span] });

    const result = applyRowEditV2(document, 0, {
      kind: "move_rows", rowIds: [x.id], destination: gap(sectionId, null, a.id),
    });

    expect(result.ok).toBe(true);
    expect(rows(result.document)).toEqual([x.id, a.id, b.id, c.id]);
    expect(result.document.rowAudioSpans).toEqual([span]);
  });

  it("shortens partial and in-span insertion moves, but still refuses cross-section, overlap, and Stash edits", () => {
    const [a, b, c, d, e, f] = [row(190), row(191), row(192), row(193), row(194), row(195)];
    const firstSectionId = id(196);
    const secondSectionId = id(197);
    const makeDocument = (rowAudioSpans: RowAudioSpanIntentV2[]) => documentWith([
      section(196, "First"), a, b, c, d, e,
      section(197, "Second"), f,
    ], { rowAudioSpans });
    const partialDocument = makeDocument([audioSpan(198, b.id, d.id)]);
    const partial = applyRowEditV2(partialDocument, 0, {
      kind: "move_rows", rowIds: [c.id], destination: gap(firstSectionId, e.id, null),
    });
    const insertionDocument = makeDocument([audioSpan(199, b.id, d.id)]);
    const insertion = applyRowEditV2(insertionDocument, 0, {
      kind: "move_rows", rowIds: [e.id], destination: gap(firstSectionId, b.id, c.id),
    });
    const crossSectionDocument = makeDocument([audioSpan(200, b.id, d.id)]);
    const crossSection = applyRowEditV2(crossSectionDocument, 0, {
      kind: "move_rows", rowIds: [d.id], destination: gap(secondSectionId, f.id, null),
    });
    const overlapDocument = makeDocument([
      audioSpan(201, b.id, d.id), audioSpan(202, c.id, e.id),
    ]);
    const overlap = applyRowEditV2(overlapDocument, 0, {
      kind: "move_rows", rowIds: [d.id], destination: gap(firstSectionId, e.id, null),
    });
    const stashDocument = makeDocument([audioSpan(203, b.id, d.id)]);
    const stashed = applyRowEditV2(stashDocument, 0, {
      kind: "stash_rows", rowIds: [c.id], bundleId: id(204),
    });

    expect(partial.ok).toBe(true);
    expect(rows(partial.document)).toEqual([a.id, b.id, d.id, e.id, c.id, f.id]);
    expect(partial.document.rowAudioSpans).toEqual([{
      ...partialDocument.rowAudioSpans![0]!,
      endRowId: b.id,
      review: { previousEndRowId: d.id, previousSettings: partialDocument.rowAudioSpans![0]!.settings, alert: "Music shortened by this move" },
    }]);

    expect(insertion.ok).toBe(true);
    expect(rows(insertion.document)).toEqual([a.id, b.id, e.id, c.id, d.id, f.id]);
    expect(insertion.document.rowAudioSpans).toEqual([{
      ...insertionDocument.rowAudioSpans![0]!,
      endRowId: b.id,
      review: { previousEndRowId: d.id, previousSettings: insertionDocument.rowAudioSpans![0]!.settings, alert: "Music shortened by this move" },
    }]);

    for (const { document, result } of [
      { document: crossSectionDocument, result: crossSection },
      { document: overlapDocument, result: overlap },
      { document: stashDocument, result: stashed },
    ]) {
      expect(result.ok).toBe(false);
      expect(result.diagnostics.map(({ code }) => code)).toContain("AUDIO_REVIEW_REQUIRED");
      expect(result.document).toEqual(document);
    }
  });

  it("refuses a middle-row crossing or unrelated insertion from another section", () => {
    const [a, b, c, d, e, outside] = [row(340), row(341), row(342), row(343), row(344), row(345)];
    const firstSectionId = id(346);
    const secondSectionId = id(347);
    const span = audioSpan(8_040, a.id, e.id);
    const crossing = documentWith([
      section(346, "First"), a, b, c, d, e,
      section(347, "Second"), outside,
    ], { rowAudioSpans: [span] });
    const crossed = applyRowEditV2(crossing, 0, {
      kind: "move_rows", rowIds: [c.id], destination: gap(secondSectionId, outside.id, null),
    });
    const insertion = documentWith([
      section(346, "First"), a, b, c, d, e,
      section(347, "Second"), outside,
    ], { rowAudioSpans: [span] });
    const inserted = applyRowEditV2(insertion, 0, {
      kind: "move_rows", rowIds: [outside.id], destination: gap(firstSectionId, b.id, c.id),
    });

    for (const [document, result] of [[crossing, crossed], [insertion, inserted]] as const) {
      expect(result.ok).toBe(false);
      expect(result.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
      expect(result.document).toBe(document);
    }
  });

  it("retains the first review source, endpoint, and settings across repeated shortening without regrowing", () => {
    const [a, b, c, d, e] = [row(350), row(351), row(352), row(353), row(354)];
    const sectionId = id(355);
    const settings = { gainDb: -12, fadeInFrames: 8, mix: "under-voice" };
    const span = audioSpan(8_050, a.id, e.id, settings);
    const baseline = documentWith([section(355, "First"), a, b, c, d, e], { rowAudioSpans: [span] });
    const first = applyRowEditV2(baseline, 0, {
      kind: "move_rows", rowIds: [e.id], destination: gap(sectionId, c.id, d.id),
    });
    expect(first.ok).toBe(true);
    const firstSpan = first.document.rowAudioSpans![0]!;
    expect(firstSpan.endRowId).toBe(c.id);
    expect(firstSpan.review).toEqual({ previousEndRowId: e.id, previousSettings: settings, alert: "Music shortened by this move" });

    const second = applyRowEditV2(first.document, first.document.rowEditRevision ?? 0, {
      kind: "move_rows", rowIds: [c.id], destination: gap(sectionId, d.id, null),
    });
    expect(second.ok).toBe(true);
    expect(second.document.rowAudioSpans?.[0]).toEqual({
      ...span,
      endRowId: b.id,
      review: { previousEndRowId: e.id, previousSettings: settings, alert: "Music shortened by this move" },
    });

    const restoredJoin = applyRowEditV2(second.document, second.document.rowEditRevision ?? 0, {
      kind: "move_rows", rowIds: [c.id], destination: gap(sectionId, b.id, e.id),
    });
    expect(restoredJoin.ok).toBe(true);
    expect(rows(restoredJoin.document)).toEqual([a.id, b.id, c.id, e.id, d.id]);
    expect(restoredJoin.document.rowAudioSpans?.[0]).toEqual({
      ...span,
      endRowId: b.id,
      review: { previousEndRowId: e.id, previousSettings: settings, alert: "Music shortened by this move" },
    });
  });

  it.each(["Music now ends with this row. Review", "Music shortened by this move"] as const)("round-trips the %s saved review alert", (alert) => {
    const [a, b, c] = [row(360), row(361), row(362)];
    const span = audioSpan(8_060, a.id, b.id, { gainDb: -6 });
    const reviewed = {
      ...span,
      review: { previousEndRowId: c.id, previousSettings: span.settings, alert },
    };
    const document = documentWith([a, b, c], { rowAudioSpans: [reviewed] });

    const restored = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(document));

    expect(restored.ok).toBe(true);
    if (restored.ok) expect(restored.document.rowAudioSpans).toEqual([reviewed]);
  });

  it("does not create row history for stale or cross-section audio-span refusals", () => {
    const [a, b, c, d, e, outside] = [row(370), row(371), row(372), row(373), row(374), row(375)];
    const secondSectionId = id(377);
    const baseline = documentWith([
      section(376, "First"), a, b, c, d, e,
      section(377, "Second"), outside,
    ], { rowAudioSpans: [audioSpan(8_070, a.id, e.id)] });
    const session = createRowEditSessionV2(baseline);
    const command: RowEditCommandV2 = {
      kind: "move_rows", rowIds: [c.id], destination: gap(secondSectionId, outside.id, null),
    };

    const stale = session.apply(command, 1);
    expect(stale.ok).toBe(false);
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(session.undoDepth).toBe(0);
    expect(session.document).toEqual(baseline);

    const refused = session.apply(command);
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(session.undoDepth).toBe(0);
    expect(session.document).toEqual(baseline);
    expect(session.undo().diagnostics[0]?.code).toBe("ROW_UNDO_EMPTY");
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
      if (command.kind === "move_rows") expect(session.document.rowAudioSpans?.[0]?.review?.alert).toBe("Music shortened by this move");
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

describe("independent Stash rows and optional sections", () => {
  it("restores one selected row from a saved section, retains its neighbors and atomically undoes", () => {
    const [before, a, b, c, after] = [row(100), richNarration(1000), richNarration(10000), richNarration(20000), row(40000)];
    const attachments = [citation(a, 9301), citation(b, 9302), citation(c, 9303)];
    const initial = documentWith([before, a, b, c, after], {
      supportingItems: attachments,
      rowTransitions: [{ id: id(9600), fromRowId: a.id, toRowId: b.id, effect: "crossfade", settings: { frames: 5 }, state: "active" }],
    });
    const stashed = applyRowEditV2(initial, 0, { kind: "stash_rows", rowIds: [a.id, b.id, c.id], bundleId: id(9500) });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    expect(stashed.document.stashSections).toBeUndefined();

    const setup = createRowEditSessionV2(stashed.document);
    expect(setup.apply({ kind: "create_stash_section", sectionId: id(9400), title: "Research" }).ok).toBe(true);
    expect(setup.apply({ kind: "move_stash_rows", rowIds: [a.id, b.id, c.id], sectionId: id(9400) }).ok).toBe(true);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(setup.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    expect(loaded.document.stashSections).toEqual([{ id: id(9400), title: "Research", rowIds: [] }]);
    expect(loaded.document.stashOutline).toEqual([a, b, c].map((savedRow) => ({ rowId: savedRow.id, kind: "row", parentRowId: null, sectionId: id(9400) })));

    const session = createRowEditSessionV2(loaded.document);
    const restored = session.apply({
      kind: "restore_stash_rows",
      rowIds: [b.id],
      destination: gap(null, before.id, after.id),
    });
    expect(restored.ok).toBe(true);
    expect(rows(restored.document)).toEqual([before.id, b.id, after.id]);
    expect(restored.document.activeDraft.supportingItems).toEqual([attachments[1]]);
    expect(restored.document.rowTransitions).toEqual([{ id: id(9600), fromRowId: a.id, toRowId: b.id, effect: "crossfade", settings: { frames: 5 }, state: "needs_review" }]);
    expect(restored.document.stash?.[0]?.rows).toEqual([a, c]);
    expect(restored.document.stash?.[0]?.supportingItems).toEqual([attachments[0], attachments[2]]);
    expect(restored.document.stashSections).toEqual([{ id: id(9400), title: "Research", rowIds: [] }]);
    expect(restored.document.stashOutline).toEqual([a, c].map((savedRow) => ({ rowId: savedRow.id, kind: "row", parentRowId: null, sectionId: id(9400) })));

    expect(session.undo().ok).toBe(true);
    expect(rows(session.document)).toEqual([before.id, after.id]);
    expect(session.document.activeDraft.supportingItems).toEqual([]);
    expect(session.document.stash?.[0]?.rows).toEqual([a, b, c]);
    expect(session.document.stash?.[0]?.supportingItems).toEqual(attachments);
    expect(session.document.stashSections).toEqual([{ id: id(9400), title: "Research", rowIds: [] }]);
    expect(session.document.stashOutline).toEqual([a, b, c].map((savedRow) => ({ rowId: savedRow.id, kind: "row", parentRowId: null, sectionId: id(9400) })));
  });

  it("restores explicit multi-selection in visible order without restoring an unselected neighbor", () => {
    const [before, a, b, c, after] = [row(720), row(721), row(722), row(723), row(724)];
    const stashed = applyRowEditV2(documentWith([before, a, b, c, after]), 0, {
      kind: "stash_rows", rowIds: [a.id, b.id, c.id], bundleId: id(9520),
    });
    const sectioned = applyRowEditV2(stashed.document, 1, { kind: "create_stash_section", sectionId: id(9420), title: "Later" });
    const assigned = applyRowEditV2(sectioned.document, 2, { kind: "move_stash_rows", rowIds: [a.id, b.id, c.id], sectionId: id(9420) });
    expect(assigned.ok).toBe(true);

    const restored = applyRowEditV2(assigned.document, 3, {
      kind: "restore_stash_rows",
      rowIds: [c.id, a.id],
      destination: gap(null, before.id, after.id),
    });
    expect(restored.ok).toBe(true);
    expect(rows(restored.document)).toEqual([before.id, a.id, c.id, after.id]);
    expect(restored.document.stash?.[0]?.rows).toEqual([b]);
    expect(restored.document.stashSections).toEqual([{ id: id(9420), title: "Later", rowIds: [] }]);
    expect(restored.document.stashOutline).toEqual([{ rowId: b.id, kind: "row", parentRowId: null, sectionId: id(9420) }]);
  });

  it("refuses stale or invalid membership changes without mutating the saved document", () => {
    const [a, b] = [row(730), row(731)];
    const stashed = applyRowEditV2(documentWith([a, b]), 0, { kind: "stash_rows", rowIds: [a.id, b.id], bundleId: id(9530) });
    const created = applyRowEditV2(stashed.document, 1, { kind: "create_stash_section", sectionId: id(9430), title: "Later" });
    const before = structuredClone(created.document);
    const stale = applyRowEditV2(created.document, 1, { kind: "move_stash_rows", rowIds: [a.id], sectionId: id(9430) });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(created.document);
    const missingSection = applyRowEditV2(created.document, 2, { kind: "move_stash_rows", rowIds: [a.id], sectionId: id(9431) });
    expect(missingSection.diagnostics[0]?.code).toBe("STASH_SECTION_NOT_FOUND");
    expect(missingSection.document).toBe(created.document);
    const duplicateSelection = applyRowEditV2(created.document, 2, {
      kind: "restore_stash_rows",
      rowIds: [a.id, a.id],
      destination: gap(null, null, null),
    });
    expect(duplicateSelection.diagnostics[0]?.code).toBe("ROW_SELECTION_INVALID");
    expect(duplicateSelection.document).toBe(created.document);
    expect(created.document).toEqual(before);

    const invalid = structuredClone(created.document);
    invalid.stashSections![0]!.rowIds = [id(9999)];
    expect(validateScriptDocumentV2(invalid).diagnostics.some((item) => item.code === "ROW_REFERENCE_INVALID")).toBe(true);
    const invalidSaved = deserializeAuthoringDocumentV2(JSON.stringify(invalid));
    expect(invalidSaved.ok).toBe(false);
    if (!invalidSaved.ok) expect(invalidSaved.diagnostics.some((item) => item.code === "ROW_REFERENCE_INVALID")).toBe(true);

    const audioProtected = documentWith([], { rowAudioSpans: [audioSpan(9550, a.id, b.id)] });
    audioProtected.stash = [{ id: id(9549), rows: [a, b], supportingItems: [] }];
    const audioRefusal = applyRowEditV2(audioProtected, 0, {
      kind: "restore_stash_rows",
      rowIds: [a.id],
      destination: gap(null, null, null),
    });
    expect(audioRefusal.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(audioRefusal.document).toBe(audioProtected);
  });

  it.each([[1], [0, 2]])("refuses splitting a timed supporting range around middle saved rows (%j)", (...selection: number[]) => {
    const savedRows = [richNarration(50000), richNarration(60000), richNarration(70000)];
    const first = savedRows[0]!;
    const last = savedRows[2]!;
    const support: SupportingItemV2 = {
      ...citation(first, 9800),
      role: "audio_cue",
      placement: {
        kind: "timed",
        start: { kind: "word", anchor: wordAnchor(first) },
        end: { kind: "word", anchor: wordAnchor(last) },
      },
    };
    const initial = documentWith(savedRows, { supportingItems: [support] });
    const stashed = applyRowEditV2(initial, 0, {
      kind: "stash_rows", rowIds: savedRows.map((row) => row.id), bundleId: id(9801),
    });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    const before = structuredClone(stashed.document);
    const restored = applyRowEditV2(stashed.document, 1, {
      kind: "restore_stash_rows", rowIds: selection.map((index) => savedRows[index]!.id),
      destination: gap(null, null, null),
    });
    expect(restored.ok).toBe(false);
    expect(restored.diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    expect(restored.document).toBe(stashed.document);
    expect(restored.document).toEqual(before);
  });

  it("allows Stash organization in Sorting while retaining local Undo and rejecting unsupported commands", () => {
    const [a, b] = [row(740), row(741)];
    const stashed = applyRowEditV2(documentWith([a, b]), 0, { kind: "stash_rows", rowIds: [a.id, b.id], bundleId: id(9540) }).document;
    const trial = createSortingTrialV2(stashed);
    expect(trial.apply({ kind: "create_stash_section", sectionId: id(9440), title: "Later" }).ok).toBe(true);
    expect(trial.apply({ kind: "move_stash_rows", rowIds: [a.id, b.id], sectionId: id(9440) }).ok).toBe(true);
    expect(trial.apply({ kind: "restore_stash_rows", rowIds: [b.id], destination: gap(null, null, null) }).ok).toBe(true);
    expect(trial.document.activeDraft.blocks.map((block) => block.id)).toEqual([b.id]);
    expect(trial.undo().ok).toBe(true);
    expect(trial.document.stash?.[0]?.rows).toEqual([a, b]);
    expect(trial.document.stashSections).toEqual([{ id: id(9440), title: "Later", rowIds: [] }]);
    expect(trial.document.stashOutline).toEqual([a, b].map((savedRow) => ({ rowId: savedRow.id, kind: "row", parentRowId: null, sectionId: id(9440) })));
    expect(trial.preview()).toEqual(trial.document);
    expect(trial.returnToSorting()).toBe(true);
    const contentEdit = { kind: "edit_stash_row", row: a } as unknown as RowEditCommandV2;
    expect(trial.apply(contentEdit).diagnostics[0]?.code).toBe("SORTING_COMMAND_INVALID");
    expect(trial.accept(stashed)).toMatchObject({ ok: true, changed: true });
  });
});
