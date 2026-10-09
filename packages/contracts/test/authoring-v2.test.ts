import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import {
  applyVisualSequenceEditV2,
  placementAnchorKeyV2,
  projectPrimarySequenceV2,
  resolveTimedPlacementV2,
  validateScriptDocumentV2,
} from "@vera/contracts/authoring-v2";
import type {
  ContentSlot,
  NarrationBlockV2,
  NarrationToken,
  NarrationTokenTimingMapV2,
  OverlayEventV2,
  RationalTime,
  ReturnSlot,
  ScriptDocumentV2,
  SupportingItemV2,
  TimedPlacement,
  WordInpointAnchor,
} from "@vera/contracts/v2";
import type { VisualSequenceEditCommandV2 } from "../src/authoring-v2.js";

const id = (value: number): string =>
  `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const contentHash = `sha256:${"a".repeat(64)}`;
const sha256 = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;

function makeTokens(words: string[], firstId = 1000): [NarrationToken, ...NarrationToken[]] {
  let offset = 0;
  const tokens = words.map((value, index) => {
    const token = {
      id: id(firstId + index),
      value,
      startOffset: offset,
      endOffset: offset + value.length,
    };
    offset += value.length + 1;
    return token;
  });
  return [tokens[0]!, ...tokens.slice(1)];
}

function anchor(row: NarrationBlockV2, tokenIndex: number, version = 1): WordInpointAnchor {
  const token = row.tokens[tokenIndex]!;
  return {
    blockId: row.id,
    tokenId: token.id,
    affinity: "before",
    quotedWord: token.value,
    anchorVersion: version,
  };
}

function onCamera(): ContentSlot["payload"] {
  return { kind: "on_camera", presenterChoiceId: null };
}

function visual(payloadId: number, pictureKind: "clip" | "image" = "image"): ContentSlot["payload"] {
  return {
    kind: "visual",
    payloadId: id(payloadId),
    pictureKind,
    source: { kind: "media_reference", mediaReferenceId: id(payloadId + 10000) },
    sourceUsage: pictureKind === "clip" ? { sourceInFrame: 0 } : null,
    audioPolicy: "mute",
    framingPolicy: "contain",
  };
}

function contentSlot(
  slotId: number,
  payload: ContentSlot["payload"],
  boundaryBefore: ContentSlot["boundaryBefore"],
  relation: "base" | "sequential" | { cutawayParentId: string } = "base",
  playoutPolicy: ContentSlot["playoutPolicy"] = "match_structural_interval",
): ContentSlot {
  return {
    id: id(slotId),
    kind: "content",
    relation: typeof relation === "string"
      ? { kind: relation }
      : { kind: "cutaway", parentSlotId: relation.cutawayParentId },
    boundaryBefore,
    payload,
    playoutPolicy,
    version: 1,
  };
}

function narration(options: {
  blockId?: number;
  words?: string[];
  slots?: (row: NarrationBlockV2) => (ContentSlot | ReturnSlot)[];
  overlays?: (row: NarrationBlockV2) => OverlayEventV2[];
  state?: "active" | "excluded";
} = {}): NarrationBlockV2 {
  const blockId = options.blockId ?? 100;
  const tokens = makeTokens(options.words ?? "we can show what changed after review today".split(" "), blockId * 20);
  const row: NarrationBlockV2 = {
    type: "narration",
    id: id(blockId),
    orderKey: "a0",
    text: tokens.map((token) => token.value).join(" "),
    tokens,
    primaryVisualSequence: { id: id(blockId + 1), slots: [], version: 1 },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: options.state ?? "active",
    notes: [],
    version: 1,
  };
  row.primaryVisualSequence!.slots = options.slots?.(row) ?? [
    contentSlot(blockId + 2, onCamera(), { kind: "row_start" }),
  ];
  row.overlayEvents = options.overlays?.(row) ?? [];
  return row;
}

function documentWith(
  rows: NarrationBlockV2[],
  supportingItems: SupportingItemV2[] = [],
): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Authoring v2 synthetic sample",
    activeDraft: { blocks: rows, supportingItems },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: contentHash,
  };
}

function sequenceAt(document: ScriptDocumentV2, index = 0) {
  const block = document.activeDraft.blocks[index];
  if (block?.type !== "narration" || !block.primaryVisualSequence) {
    throw new Error(`Expected narration block ${index} with a primary sequence`);
  }
  return block.primaryVisualSequence;
}

function apply(document: ScriptDocumentV2, command: VisualSequenceEditCommandV2) {
  const blockId = command.kind === "move_payload" ? command.sourceBlockId : command.blockId;
  const row = document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.id === blockId,
  )!;
  return applyVisualSequenceEditV2(document, row.primaryVisualSequence!.version, command);
}

function wordPoint(row: NarrationBlockV2, tokenIndex: number) {
  return { kind: "word", anchor: anchor(row, tokenIndex) } as const;
}

function placementContext(
  row: NarrationBlockV2,
  anchorTimes: Record<string, RationalTime>,
): Parameters<typeof resolveTimedPlacementV2>[1] {
  return {
    document: documentWith([row]),
    blockId: row.id,
    rowBounds: { start: { numerator: 0, denominator: 1 }, end: { numerator: 10, denominator: 1 } },
    anchorTimes,
  };
}

function timingMap(row: NarrationBlockV2): NarrationTokenTimingMapV2 {
  return {
    blockId: row.id,
    blockRevision: row.version,
    textHash: sha256(row.text),
    tokenizationVersion: "tokenizer/v1",
    narrationAssetId: id(8800),
    audioHash: `sha256:${"b".repeat(64)}`,
    timingHash: `sha256:${"c".repeat(64)}`,
    alignmentVersion: "align/v1",
    precision: "audible_word_marks",
    tokens: row.tokens.map((token, index) => ({
      tokenId: token.id,
      startOffset: token.startOffset,
      endOffset: token.endOffset,
      quotedText: token.value,
      startTime: { numerator: index * 2, denominator: 5 },
      audibleEnd: { numerator: (index + 1) * 2, denominator: 5 },
      endBasis: "evidenced_audible_end" as const,
    })) as NarrationTokenTimingMapV2["tokens"],
  };
}

describe("authoring v2 validation and pure row projection", () => {
  it("projects continuous roots, cutaway returns, On Camera resumes, overlays and row-local ordinals", () => {
    const row = narration({
      slots: (r) => {
        const base = contentSlot(200, onCamera(), { kind: "row_start" });
        const child = contentSlot(201, visual(202), { kind: "spoken_word", anchor: anchor(r, 2) }, { cutawayParentId: base.id });
        const returned = { id: id(203), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 5), version: 1 } satisfies ReturnSlot;
        const next = contentSlot(204, visual(205), { kind: "spoken_word", anchor: anchor(r, 6) }, "sequential");
        return [base, child, returned, next];
      },
      overlays: (r) => [{
        id: id(206),
        payload: visual(207) as OverlayEventV2["payload"],
        timing: { kind: "timed", start: wordPoint(r, 4), end: wordPoint(r, 7) },
        version: 1,
      }, {
        id: id(208),
        payload: visual(209) as OverlayEventV2["payload"],
        timing: { kind: "timed", start: wordPoint(r, 6), end: wordPoint(r, 7) },
        version: 1,
      }],
    });
    const document = documentWith([row]);

    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const projection = projectPrimarySequenceV2(document).rows[0]!;
    expect(projection.renderable).toBe(true);
    expect(projection.tokens.map((token) => token.primarySlotId)).toEqual([
      id(200), id(200), id(201), id(201), id(201), id(200), id(204), id(204),
    ]);
    expect(projection.tokens[5]?.onCameraResumes).toBe(true);
    expect(projection.tokens[2]?.hostState).toBe("voiceover");
    expect(projection.slots.map((slot) => [slot.slotId, slot.structuralIndex, slot.humanOrdinal])).toEqual([
      [id(200), 0, null],
      [id(201), 1, 1],
      [id(204), 3, 3],
    ]);
    expect(projection.overlays[0]).toMatchObject({
      humanOrdinal: 2,
      startTokenIndex: 4,
      endTokenIndex: 7,
      parentSlotId: null,
    });
    expect(projection.overlays[1]?.humanOrdinal).toBe(4);
    expect(projection.returns[0]).toMatchObject({ structuralIndex: 2, parentOrdinal: null, startTokenIndex: 5 });
    expect(projectPrimarySequenceV2(document).rows[0]).toEqual(projection);
  });

  it("keeps a reversed B-roll parent continuous under On Camera and reveals the same slot at return", () => {
    const row = narration({ slots: (r) => {
      const base = contentSlot(210, visual(211, "clip"), { kind: "row_start" });
      const presenter = contentSlot(212, onCamera(), { kind: "spoken_word", anchor: anchor(r, 2) }, { cutawayParentId: base.id });
      const returned = { id: id(213), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 5), version: 1 } satisfies ReturnSlot;
      const next = contentSlot(214, visual(215), { kind: "spoken_word", anchor: anchor(r, 6) }, "sequential");
      return [base, presenter, returned, next];
    } });
    const projected = projectPrimarySequenceV2(documentWith([row])).rows[0]!;
    expect(projected.tokens.map((token) => token.primarySlotId)).toEqual([
      id(210), id(210), id(212), id(212), id(212), id(210), id(214), id(214),
    ]);
    expect(projected.tokens[0]?.hostState).toBe("voiceover");
    expect(projected.tokens[2]?.hostState).toBe("on_camera");
    expect(projected.tokens[5]?.hostState).toBe("voiceover");
    expect(projected.tokens[5]?.onCameraResumes).toBe(false);
    expect(projected.renderable).toBe(true);
  });

  it("does not call an On Camera-to-On Camera child a presenter resume", () => {
    const row = narration({ slots: (r) => {
      const base = contentSlot(220, onCamera(), { kind: "row_start" });
      const child = contentSlot(221, onCamera(), { kind: "spoken_word", anchor: anchor(r, 2) }, { cutawayParentId: base.id });
      const returned = { id: id(222), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 4), version: 1 } satisfies ReturnSlot;
      return [base, child, returned];
    } });
    const projected = projectPrimarySequenceV2(documentWith([row])).rows[0]!;
    expect(projected.tokens[4]?.onCameraResumes).toBe(false);
  });

  it("does not mark a parent return as a resume when an On Camera child is already visible", () => {
    const row = narration({ slots: (r) => {
      const base = contentSlot(223, onCamera(), { kind: "row_start" });
      const visualChild = contentSlot(224, visual(225), { kind: "spoken_word", anchor: anchor(r, 2) }, { cutawayParentId: base.id });
      const onCameraChild = contentSlot(226, onCamera(), { kind: "spoken_word", anchor: anchor(r, 4) }, { cutawayParentId: base.id });
      const returned = { id: id(227), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 6), version: 1 } satisfies ReturnSlot;
      return [base, visualChild, onCameraChild, returned];
    } });
    const projected = projectPrimarySequenceV2(documentWith([row])).rows[0]!;
    expect(projected.tokens[6]?.hostState).toBe("on_camera");
    expect(projected.tokens[6]?.onCameraResumes).toBe(false);
  });

  it("keeps a singleton visual ordinal at one and validates exact row/token/text anchors", () => {
    const row = narration({ slots: () => [contentSlot(230, visual(231), { kind: "row_start" })] });
    const projection = projectPrimarySequenceV2(documentWith([row])).rows[0]!;
    expect(projection.slots[0]?.humanOrdinal).toBe(1);

    const stale = structuredClone(row);
    stale.primaryVisualSequence!.slots.push(contentSlot(232, visual(233), {
      kind: "spoken_word",
      anchor: { ...anchor(stale, 3), blockId: id(999), quotedWord: "nearby" },
    }, "sequential"));
    const validation = validateScriptDocumentV2(documentWith([stale]));
    expect(validation.diagnostics.map((item) => item.code)).toContain("STALE_WORD_ANCHOR");
    expect(projectPrimarySequenceV2(documentWith([stale])).rows[0]?.renderable).toBe(false);
  });

  it("orders a startless end-plus-duration overlay from verified timing without inventing a word anchor", () => {
    const row = narration({
      slots: (r) => [
        contentSlot(240, visual(241), { kind: "row_start" }),
        contentSlot(242, visual(243), { kind: "spoken_word", anchor: anchor(r, 5) }, "sequential"),
      ],
      overlays: (r) => [{
        id: id(244),
        payload: visual(245) as OverlayEventV2["payload"],
        timing: { kind: "timed", end: wordPoint(r, 6), durationMs: 800 },
        version: 1,
      }],
    });
    const document = documentWith([row]);
    const withTiming = projectPrimarySequenceV2(document, { narrationTimingMaps: [timingMap(row)] }).rows[0]!;
    expect(withTiming.overlays[0]).toMatchObject({ humanOrdinal: 2, startTokenIndex: null, parentSlotId: null });
    expect(withTiming.slots.find((slot) => slot.slotId === id(242))?.humanOrdinal).toBe(3);

    const withoutTiming = projectPrimarySequenceV2(document).rows[0]!;
    expect(withoutTiming.overlays[0]?.humanOrdinal).toBeNull();
    expect(withoutTiming.diagnostics.map((item) => item.code)).toContain("OVERLAY_START_UNRESOLVED");
  });

  it("preserves Unplaced reason and anchor evidence in projection", () => {
    const item: SupportingItemV2 = {
      id: id(250),
      version: 1,
      orderKey: "b0",
      role: "picture",
      content: "An optional visual",
      pictureKind: "image",
      source: { kind: "media_reference", mediaReferenceId: id(251) },
      placement: { kind: "unplaced", reason: "No editorial interval was chosen", priorAnchor: wordPoint(narration(), 2).anchor, neighboringBlockIds: [id(100)] },
    };
    const row = narration();
    const projected = projectPrimarySequenceV2(documentWith([row], [item])).rows[0]!.supportingItems[0]!;
    expect(projected).toMatchObject({
      itemId: id(250),
      placementKind: "unplaced",
      placement: { kind: "unplaced", reason: "No editorial interval was chosen", neighboringBlockIds: [id(100)] },
      interval: null,
    });
  });
});

describe("authoring v2 structural edit transactions", () => {
  it("inserts exact sequential words, defaults to explicit undefined, and adds siblings under one return", () => {
    const row = narration();
    const document = documentWith([row]);
    const inserted = apply(document, {
      kind: "insert_sequential",
      blockId: row.id,
      boundary: anchor(row, 2),
      slotId: id(300),
      payload: visual(301),
    });
    expect(inserted.ok).toBe(true);
    expect(sequenceAt(inserted.document).slots[1]).toMatchObject({
      id: id(300),
      boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[2]?.id, quotedWord: "show" } },
    });

    const undefinedRow = narration({ blockId: 310 });
    const undefinedInsert = apply(documentWith([undefinedRow]), {
      kind: "insert_sequential",
      blockId: id(310),
      boundary: anchor(undefinedRow, 2),
      slotId: id(314),
      undefinedPayloadId: id(315),
    });
    expect(undefinedInsert.ok).toBe(true);
    expect(sequenceAt(undefinedInsert.document).slots[1]).toMatchObject({
      payload: { kind: "undefined", payloadId: id(315) },
    });

    const childDoc = documentWith([narration()]);
    const childRow = childDoc.activeDraft.blocks[0] as NarrationBlockV2;
    const base = childRow.primaryVisualSequence!.slots[0] as ContentSlot;
    const first = apply(childDoc, {
      kind: "insert_cutaway",
      blockId: childRow.id,
      boundary: anchor(childRow, 2),
      parentSlotId: base.id,
      slotId: id(320),
      returnSlotId: id(321),
      payload: visual(322),
    });
    expect(first.ok).toBe(true);
    expect(projectPrimarySequenceV2(first.document).rows[0]?.renderable).toBe(false);
    expect(projectPrimarySequenceV2(first.document).rows[0]?.diagnostics.map((item) => item.code)).toContain("RETURN_INPOINT_MISSING");
    const second = apply(first.document, {
      kind: "insert_cutaway",
      blockId: childRow.id,
      boundary: anchor(childRow, 4),
      parentSlotId: base.id,
      slotId: id(323),
      returnSlotId: id(324),
      payload: visual(325),
    });
    expect(second.ok).toBe(true);
    expect(sequenceAt(second.document).slots.map((slot) => slot.id)).toEqual([
      base.id, id(320), id(323), id(321),
    ]);
  });

  it("converts and flattens groups without guessing a return or changing payload identity", () => {
    const row = narration({ slots: (r) => [
      contentSlot(330, visual(331), { kind: "row_start" }),
      contentSlot(332, visual(333), { kind: "spoken_word", anchor: anchor(r, 3) }, "sequential"),
    ] });
    const document = documentWith([row]);
    const converted = apply(document, {
      kind: "convert_sequential_to_cutaway",
      blockId: row.id,
      slotId: id(332),
      returnSlotId: id(334),
    });
    expect(converted.ok).toBe(true);
    expect(sequenceAt(converted.document).slots[1]).toMatchObject({
      id: id(332), relation: { kind: "cutaway", parentSlotId: id(330) }, payload: { payloadId: id(333) },
    });
    const flattened = apply(converted.document, {
      kind: "flatten_cutaway_group",
      blockId: row.id,
      parentSlotId: id(330),
    });
    expect(flattened.ok).toBe(true);
    expect(sequenceAt(flattened.document).slots.map((slot) => slot.kind)).toEqual([
      "content", "content",
    ]);
    expect(sequenceAt(flattened.document).slots[1]).toMatchObject({
      id: id(332), relation: { kind: "sequential" }, boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[3]?.id } },
    });
  });

  it("moves shared word boundaries exactly and swaps payloads without moving structure", () => {
    const row = narration({ slots: (r) => [
      contentSlot(340, visual(341), { kind: "row_start" }),
      contentSlot(342, visual(343), { kind: "spoken_word", anchor: anchor(r, 4) }, "sequential"),
    ] });
    const document = documentWith([row]);
    const moved = apply(document, {
      kind: "move_word_boundary",
      blockId: row.id,
      boundaryOwnerId: id(342),
      tokenId: row.tokens[3]!.id,
    });
    expect(moved.ok).toBe(true);
    expect(sequenceAt(moved.document).slots[1]).toMatchObject({
      boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[3]?.id, quotedWord: row.tokens[3]?.value } },
    });

    const before = structuredClone(row.primaryVisualSequence!.slots);
    const swapped = apply(document, {
      kind: "swap_payloads",
      blockId: row.id,
      firstSlotId: id(340),
      secondSlotId: id(342),
    });
    expect(swapped.ok).toBe(true);
    expect(sequenceAt(swapped.document).slots.map((slot) => slot.id)).toEqual(before.map((slot) => slot.id));
    expect(sequenceAt(swapped.document).slots.map((slot) => slot.kind === "content" ? slot.payload : null)).toEqual([
      before[1]?.kind === "content" ? before[1].payload : null,
      before[0]?.kind === "content" ? before[0].payload : null,
    ]);

    const stale = apply(document, {
      kind: "insert_sequential",
      blockId: row.id,
      boundary: { ...anchor(row, 2), quotedWord: "nearby" },
      slotId: id(344),
      payload: visual(345),
    });
    expect(stale.ok).toBe(false);
    expect(stale.document).toBe(document);
  });

  it("atomically switches complete-clip boundaries and keeps mode policy with the structural slot", () => {
    const row = narration({ slots: (r) => [
      contentSlot(350, visual(351, "clip"), { kind: "row_start" }, "base", "match_structural_interval"),
      contentSlot(352, visual(353, "clip"), { kind: "spoken_word", anchor: anchor(r, 4) }, "sequential"),
      contentSlot(354, onCamera(), { kind: "spoken_word", anchor: anchor(r, 6) }, "sequential"),
    ] });
    const document = documentWith([row]);
    const enabled = apply(document, {
      kind: "set_playout_policy",
      blockId: row.id,
      slotId: id(350),
      policy: "complete_logged_clip",
    });
    expect(enabled.ok).toBe(true);
    expect(sequenceAt(enabled.document).slots[0]).toMatchObject({ playoutPolicy: "complete_logged_clip" });
    expect(sequenceAt(enabled.document).slots[1]).toMatchObject({
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(350) },
    });

    const swapped = apply(enabled.document, {
      kind: "swap_payloads",
      blockId: row.id,
      firstSlotId: id(350),
      secondSlotId: id(352),
    });
    expect(swapped.ok).toBe(true);
    expect(sequenceAt(swapped.document).slots[0]).toMatchObject({
      id: id(350), relation: { kind: "base" }, playoutPolicy: "complete_logged_clip", payload: { payloadId: id(353) },
    });
    expect(sequenceAt(swapped.document).slots[1]).toMatchObject({
      id: id(352), relation: { kind: "sequential" }, boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(350) },
    });

    const refusedSwap = apply(enabled.document, {
      kind: "swap_payloads",
      blockId: row.id,
      firstSlotId: id(350),
      secondSlotId: id(354),
    });
    expect(refusedSwap.ok).toBe(false);
    expect(refusedSwap.document).toBe(enabled.document);
    const disabled = apply(enabled.document, {
      kind: "set_playout_policy",
      blockId: row.id,
      slotId: id(350),
      policy: "match_structural_interval",
      nextBoundary: anchor(row, 3),
    });
    expect(disabled.ok).toBe(true);
    expect(sequenceAt(disabled.document).slots[1]).toMatchObject({
      boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[3]?.id } },
    });

    const invalid = narration({ slots: () => [contentSlot(360, visual(361, "clip"), { kind: "row_start" })] });
    const finalController = apply(documentWith([invalid]), {
      kind: "set_playout_policy", blockId: invalid.id, slotId: id(360), policy: "complete_logged_clip",
    });
    expect(finalController.ok).toBe(false);
    expect(sequenceAt(finalController.document).slots[0]).toMatchObject({ playoutPolicy: "match_structural_interval" });
  });

  it("creates and exits a complete-clip chain in controller order using exact caller words", () => {
    const row = narration({ blockId: 600, slots: (r) => [
      contentSlot(610, visual(611, "clip"), { kind: "row_start" }, "base"),
      contentSlot(612, visual(613, "clip"), { kind: "spoken_word", anchor: anchor(r, 2) }, "sequential"),
      contentSlot(614, visual(615, "clip"), { kind: "spoken_word", anchor: anchor(r, 5) }, "sequential"),
    ] });
    const original = documentWith([row]);
    const bComplete = apply(original, {
      kind: "set_playout_policy", blockId: row.id, slotId: id(612), policy: "complete_logged_clip",
    });
    expect(bComplete.ok).toBe(true);
    expect(sequenceAt(bComplete.document).slots[2]).toMatchObject({
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(612) },
    });

    const aComplete = apply(bComplete.document, {
      kind: "set_playout_policy", blockId: row.id, slotId: id(610), policy: "complete_logged_clip",
    });
    expect(aComplete.ok).toBe(true);
    expect(sequenceAt(aComplete.document).slots[1]).toMatchObject({
      playoutPolicy: "complete_logged_clip",
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(610) },
    });
    expect(sequenceAt(aComplete.document).slots[2]).toMatchObject({
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(612) },
    });
    expect(validateScriptDocumentV2(aComplete.document).valid).toBe(true);

    const aMatch = apply(aComplete.document, {
      kind: "set_playout_policy",
      blockId: row.id,
      slotId: id(610),
      policy: "match_structural_interval",
      nextBoundary: anchor(row, 3),
    });
    expect(aMatch.ok).toBe(true);
    expect(sequenceAt(aMatch.document).slots[0]).toMatchObject({ playoutPolicy: "match_structural_interval" });
    expect(sequenceAt(aMatch.document).slots[1]).toMatchObject({
      boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[3]?.id } },
      playoutPolicy: "complete_logged_clip",
    });
    expect(sequenceAt(aMatch.document).slots[2]).toMatchObject({
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(612) },
    });
    expect(validateScriptDocumentV2(aMatch.document).valid).toBe(true);

    const bMatch = apply(aMatch.document, {
      kind: "set_playout_policy",
      blockId: row.id,
      slotId: id(612),
      policy: "match_structural_interval",
      nextBoundary: anchor(row, 6),
    });
    expect(bMatch.ok).toBe(true);
    expect(sequenceAt(bMatch.document).slots[1]).toMatchObject({ playoutPolicy: "match_structural_interval" });
    expect(sequenceAt(bMatch.document).slots[2]).toMatchObject({
      boundaryBefore: { kind: "spoken_word", anchor: { tokenId: row.tokens[6]?.id } },
    });
    expect(validateScriptDocumentV2(bMatch.document).valid).toBe(true);
    expect(validateScriptDocumentV2(original).valid).toBe(true);
  });

  it("refuses equal and crossed shared-word moves without changing the input document", () => {
    const row = narration({ blockId: 620, slots: (r) => [
      contentSlot(630, onCamera(), { kind: "row_start" }),
      contentSlot(631, visual(632), { kind: "spoken_word", anchor: anchor(r, 4) }, "sequential"),
      contentSlot(633, visual(634), { kind: "spoken_word", anchor: anchor(r, 6) }, "sequential"),
    ] });
    const document = documentWith([row]);
    const before = JSON.stringify(document);
    const equal = apply(document, {
      kind: "move_word_boundary", blockId: row.id, boundaryOwnerId: id(631), tokenId: row.tokens[0].id,
    });
    expect(equal.ok).toBe(false);
    expect(equal.diagnostics.map((item) => item.code)).toContain("BOUNDARY_CROSSED_OR_COLLAPSED");
    expect(equal.document).toBe(document);
    expect(JSON.stringify(document)).toBe(before);

    const crossed = apply(document, {
      kind: "move_word_boundary", blockId: row.id, boundaryOwnerId: id(631), tokenId: row.tokens[7]!.id,
    });
    expect(crossed.ok).toBe(false);
    expect(crossed.diagnostics.map((item) => item.code)).toContain("BOUNDARY_CROSSED_OR_COLLAPSED");
    expect(crossed.document).toBe(document);
    expect(JSON.stringify(document)).toBe(before);
  });

  it("moves a root and its explicitly deleted child group across rows atomically", () => {
    const source = narration({ blockId: 640, slots: (r) => {
      const base = contentSlot(650, onCamera(), { kind: "row_start" });
      const moving = contentSlot(651, visual(652), { kind: "spoken_word", anchor: anchor(r, 4) }, "sequential");
      const child = contentSlot(653, visual(654), { kind: "spoken_word", anchor: anchor(r, 5) }, { cutawayParentId: moving.id });
      const returned = { id: id(655), kind: "return", parentSlotId: moving.id, inpoint: anchor(r, 6), version: 1 } satisfies ReturnSlot;
      return [base, moving, child, returned];
    } });
    const destination = narration({ blockId: 660 });
    const document = documentWith([source, destination]);
    const before = JSON.stringify(document);
    const moved = apply(document, {
      kind: "move_payload",
      sourceBlockId: source.id,
      sourceSlotId: id(651),
      sourceRepair: "delete_children",
      destinationBlockId: destination.id,
      expectedDestinationSequenceVersion: 1,
      destination: { kind: "sequential", boundary: anchor(destination, 2), slotId: id(670) },
    });
    expect(moved.ok).toBe(true);
    expect(moved.document).not.toBe(document);
    expect(JSON.stringify(document)).toBe(before);
    expect(sequenceAt(moved.document).slots).toHaveLength(1);
    expect(sequenceAt(moved.document, 1).slots[1]).toMatchObject({
      id: id(670), payload: { kind: "visual", payloadId: id(652) },
    });
    expect(moved.evidence?.beforeSequenceVersions).toEqual({ [source.id]: 1, [destination.id]: 1 });
    expect(moved.evidence?.afterSequenceVersions).toEqual({ [source.id]: 2, [destination.id]: 2 });
    expect(moved.evidence?.slotIds).toEqual([id(651), id(653), id(655), id(670)]);
    expect(moved.evidence?.payloadIds).toEqual([id(652), id(654)]);
    expect(moved.evidence?.blockIds).toEqual([source.id, destination.id]);
  });

  it("preserves a cutaway outpoint when deleting the base and refuses atomic cross-row repair", () => {
    const source = narration({ blockId: 370, slots: (r) => {
      const base = contentSlot(380, onCamera(), { kind: "row_start" });
      const child = contentSlot(381, visual(382), { kind: "spoken_word", anchor: anchor(r, 2) }, { cutawayParentId: base.id });
      const returned = { id: id(383), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 5), version: 1 } satisfies ReturnSlot;
      const next = contentSlot(384, visual(385), { kind: "spoken_word", anchor: anchor(r, 7) }, "sequential");
      return [base, child, returned, next];
    } });
    const promoted = apply(documentWith([source]), {
      kind: "delete_slot", blockId: source.id, slotId: id(380), replacementSlotId: id(386), replacementPayloadId: id(387),
    });
    expect(promoted.ok).toBe(true);
    expect(sequenceAt(promoted.document).slots).toMatchObject([
      { id: id(381), relation: { kind: "base" }, boundaryBefore: { kind: "row_start" } },
      { id: id(386), relation: { kind: "sequential" }, boundaryBefore: { kind: "spoken_word", anchor: { tokenId: source.tokens[5]?.id } }, payload: { kind: "undefined", payloadId: id(387) } },
      { id: id(384), relation: { kind: "sequential" }, boundaryBefore: { kind: "spoken_word", anchor: { tokenId: source.tokens[7]?.id } } },
    ]);

    const target = narration({ blockId: 390 });
    const sourceWithGroup = narration({ blockId: 400, slots: (r) => {
      const base = contentSlot(410, visual(411), { kind: "row_start" });
      const child = contentSlot(412, visual(413), { kind: "spoken_word", anchor: anchor(r, 4) }, { cutawayParentId: base.id });
      const returned = { id: id(414), kind: "return", parentSlotId: base.id, inpoint: anchor(r, 6), version: 1 } satisfies ReturnSlot;
      return [base, child, returned];
    } });
    const crossRow = documentWith([sourceWithGroup, target]);
    const refused = apply(crossRow, {
      kind: "move_payload",
      sourceBlockId: sourceWithGroup.id,
      sourceSlotId: id(410),
      sourceRepair: "reject",
      destinationBlockId: target.id,
      expectedDestinationSequenceVersion: 1,
      destination: { kind: "sequential", boundary: anchor(target, 2), slotId: id(415) },
    });
    expect(refused.ok).toBe(false);
    expect(refused.document).toBe(crossRow);
    expect(sequenceAt(refused.document).slots.map((slot) => slot.id)).toEqual(
      sourceWithGroup.primaryVisualSequence?.slots.map((slot) => slot.id),
    );
    expect(sequenceAt(refused.document, 1).slots).toHaveLength(1);
  });

  it("moves an Unplaced picture by identity with lineage and increments both row versions once", () => {
    const source = narration({ blockId: 420 });
    const destination = narration({ blockId: 430 });
    const support: SupportingItemV2 = {
      id: id(440), version: 1, orderKey: "b0", role: "picture", content: "An image",
      pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: id(441) },
      placement: { kind: "unplaced", reason: "Not placed yet" },
    };
    const document = documentWith([source, destination], [support]);
    const result = apply(document, {
      kind: "promote_supporting_picture",
      blockId: destination.id,
      supportingItemId: support.id,
      destination: { kind: "sequential", boundary: anchor(destination, 2), slotId: id(442) },
      audioPolicy: "mute",
      framingPolicy: "contain",
      sourceUsage: null,
    });
    expect(result.ok).toBe(true);
    expect(result.document.activeDraft.supportingItems).toHaveLength(0);
    expect(sequenceAt(result.document, 1).slots[1]).toMatchObject({ payload: { payloadId: support.id } });
    expect(result.evidence?.lineage).toEqual({ fromSupportingItemId: support.id, toPayloadId: support.id });
    expect(result.evidence?.beforeSequenceVersions).toEqual({ [destination.id]: 1 });
    expect(result.evidence?.afterSequenceVersions).toEqual({ [destination.id]: 2 });
  });
});

describe("D24 timed placement resolution", () => {
  it("resolves consistent two-of-three facts with exact rational arithmetic", () => {
    const row = narration();
    const start = wordPoint(row, 1);
    const end = wordPoint(row, 3);
    const context = placementContext(row, {
      [placementAnchorKeyV2(start)]: { numerator: 1, denominator: 1 },
      [placementAnchorKeyV2(end)]: { numerator: 3, denominator: 1 },
    });
    expect(resolveTimedPlacementV2({ kind: "timed", start, durationMs: 2000 }, context)).toMatchObject({
      status: "resolved",
      interval: { start: { numerator: 1, denominator: 1 }, end: { numerator: 3, denominator: 1 }, duration: { numerator: 2, denominator: 1 } },
    });
    expect(resolveTimedPlacementV2({ kind: "timed", start, end, durationMs: 2000 }, context).status).toBe("resolved");
    expect(resolveTimedPlacementV2({ kind: "timed", start, end, durationMs: 1000 }, context).status).toBe("refused");
  });

  it("refuses stale, equal, crossed, negative, zero, out-of-row and unreduced facts without nearest repair", () => {
    const row = narration();
    const start = wordPoint(row, 1);
    const end = wordPoint(row, 3);
    const times = {
      [placementAnchorKeyV2(start)]: { numerator: 1, denominator: 1 },
      [placementAnchorKeyV2(end)]: { numerator: 3, denominator: 1 },
    };
    const context = placementContext(row, times);
    expect(resolveTimedPlacementV2({ kind: "timed", start, end }, context).status).toBe("resolved");
    expect(resolveTimedPlacementV2({ kind: "timed", start, end, durationMs: 0 }, context).status).toBe("refused");
    expect(resolveTimedPlacementV2({ kind: "timed", start, end, durationMs: -1 }, context).status).toBe("refused");

    const crossed = placementContext(row, {
      [placementAnchorKeyV2(start)]: { numerator: 3, denominator: 1 },
      [placementAnchorKeyV2(end)]: { numerator: 1, denominator: 1 },
    });
    expect(resolveTimedPlacementV2({ kind: "timed", start, end }, crossed).status).toBe("refused");
    const outside = placementContext(row, {
      [placementAnchorKeyV2(start)]: { numerator: 9, denominator: 1 },
      [placementAnchorKeyV2(end)]: { numerator: 11, denominator: 1 },
    });
    expect(resolveTimedPlacementV2({ kind: "timed", start, end }, outside).status).toBe("refused");

    const stale = { ...start, anchor: { ...start.anchor, tokenId: id(9999), quotedWord: "word-nearby" } };
    const stalePoint = placementAnchorKeyV2(stale);
    expect(resolveTimedPlacementV2({ kind: "timed", start: stale, end }, placementContext(row, { ...times, [stalePoint]: { numerator: 1, denominator: 1 } })).status).toBe("refused");

    const unreduced = placementContext(row, {
      [placementAnchorKeyV2(start)]: { numerator: 2, denominator: 2 },
      [placementAnchorKeyV2(end)]: { numerator: 3, denominator: 1 },
    });
    expect(resolveTimedPlacementV2({ kind: "timed", start, end }, unreduced).status).toBe("refused");
    expect(resolveTimedPlacementV2({ kind: "timed", start, end }, {
      ...context,
      document: documentWith([narration({ state: "excluded" })]),
    }).status).toBe("refused");
  });

  it("returns Unplaced and duration-only intent without deriving an interval", () => {
    const excluded = narration({ state: "excluded" });
    const context = placementContext(excluded, {});
    const unplaced: SupportingItemV2["placement"] = { kind: "unplaced", reason: "Choose a location" };
    expect(resolveTimedPlacementV2(unplaced, context)).toMatchObject({ status: "unplaced", interval: null });
    const durationOnly = { kind: "timed", durationMs: 900 } as TimedPlacement;
    expect(resolveTimedPlacementV2(durationOnly, context)).toMatchObject({ status: "unplaced", interval: null });
    const invalidDuration = { kind: "timed", durationMs: 0 } as TimedPlacement;
    expect(resolveTimedPlacementV2(invalidDuration, context).status).toBe("refused");
  });
});

describe("display-only complete clip cut estimates", () => {
  it("uses an exact verified preview or the five-word fallback window without persisting an anchor", () => {
    const row = narration({ blockId: 500, words: "one two three four five six seven eight".split(" "), slots: () => [
      contentSlot(510, visual(511, "clip"), { kind: "row_start" }, "base", "complete_logged_clip"),
      contentSlot(512, visual(513, "clip"), { kind: "previous_media_end", controllingSlotId: id(510) }, "sequential"),
    ] });
    const bounds = [{
      mediaReferenceId: id(10511), contentHash, loggedStartFrame: 0, loggedEndExclusiveFrame: 3,
      frameRate: { numerator: 1, denominator: 1 },
    }];
    const fallback = projectPrimarySequenceV2(documentWith([row]), { mediaBounds: bounds }).rows[0]?.mediaCutEstimates[0];
    expect(fallback).toMatchObject({ timingSource: "400ms_per_token_fallback", tokenWindow: row.tokens.slice(3, 8).map((token) => token.id) });
    expect(row.primaryVisualSequence?.slots[1]).toMatchObject({ boundaryBefore: { kind: "previous_media_end", controllingSlotId: id(510) } });

    const verified = projectPrimarySequenceV2(documentWith([row]), {
      mediaBounds: bounds,
      narrationTimingMaps: [timingMap(row)],
    }).rows[0]?.mediaCutEstimates[0];
    expect(verified).toMatchObject({
      timingSource: "verified_preview",
      estimatedCutSeconds: { numerator: 3, denominator: 1 },
      tokenWindow: row.tokens.slice(3, 8).map((token) => token.id),
    });

    const stalePreview = projectPrimarySequenceV2(documentWith([row]), {
      mediaBounds: bounds,
      narrationTimingMaps: [{ ...timingMap(row), textHash: `sha256:${"d".repeat(64)}` }],
    }).rows[0]?.mediaCutEstimates[0];
    expect(stalePreview?.timingSource).toBe("400ms_per_token_fallback");

    const unknownEndBasis = structuredClone(timingMap(row));
    unknownEndBasis.tokens[0] = { ...unknownEndBasis.tokens[0], endBasis: "unknown" };
    const unknownPreview = projectPrimarySequenceV2(documentWith([row]), {
      mediaBounds: bounds,
      narrationTimingMaps: [unknownEndBasis],
    }).rows[0]?.mediaCutEstimates[0];
    expect(unknownPreview?.timingSource).toBe("400ms_per_token_fallback");
  });
});
