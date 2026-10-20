import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import type {
  ContentSlot,
  NarrationBlockV2,
  NarrationToken,
  PerformanceBeat,
  ScriptDocumentV2,
  SupportingItemV2,
  TextAnchorRange,
  TimedPlacement,
  WordAudibleEndAnchor,
  WordInpointAnchor,
} from "../src/generated/contracts-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import {
  applyAcceptedOmissionV2,
  type AcceptedOmissionV2,
} from "../src/issue-189-v2-omission.js";

const id = (value: number): string =>
  `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const hash = (value: string): string =>
  `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const fixedHash = `sha256:${"f".repeat(64)}`;

type PointAnchor = NonNullable<TimedPlacement["start"]>;
type WordAnchor = WordInpointAnchor | WordAudibleEndAnchor;

function makeTokens(values: string[], separators = values.slice(1).map(() => " "), firstId = 100): { text: string; tokens: [NarrationToken, ...NarrationToken[]] } {
  let text = "";
  const tokens = values.map((value, index) => {
    if (index > 0) text += separators[index - 1]!;
    const startOffset = text.length;
    text += value;
    return { id: id(firstId + index), value, startOffset, endOffset: text.length };
  });
  return { text, tokens: [tokens[0]!, ...tokens.slice(1)] };
}

function wordAnchor(row: NarrationBlockV2, tokenIndex: number, affinity: "before" | "after" = "before"): WordAnchor {
  const token = row.tokens[tokenIndex]!;
  return {
    blockId: row.id,
    tokenId: token.id,
    affinity,
    quotedWord: token.value,
    anchorVersion: 1,
  };
}

function pointAnchor(row: NarrationBlockV2, tokenIndex: number, affinity: "before" | "after" = "before"): PointAnchor {
  return affinity === "before"
    ? { kind: "word", anchor: wordAnchor(row, tokenIndex, affinity) as WordInpointAnchor }
    : { kind: "audible_word_end", anchor: wordAnchor(row, tokenIndex, affinity) as WordAudibleEndAnchor };
}

function textRange(
  row: NarrationBlockV2,
  startTokenIndex: number,
  endTokenIndex: number,
  startAffinity: "before" | "after" = "before",
  endAffinity: "before" | "after" = "after",
): TextAnchorRange {
  const startToken = row.tokens[startTokenIndex]!;
  const endToken = row.tokens[endTokenIndex]!;
  const start = startAffinity === "before" ? startToken.startOffset : startToken.endOffset;
  const end = endAffinity === "before" ? endToken.startOffset : endToken.endOffset;
  return {
    blockId: row.id,
    startTokenId: startToken.id,
    endTokenId: endToken.id,
    startAffinity,
    endAffinity,
    quotedText: row.text.slice(start, end),
    anchorVersion: 1,
  };
}

function visualPayload(payloadId: number): ContentSlot["payload"] {
  return {
    kind: "visual",
    payloadId: id(payloadId),
    pictureKind: "image",
    source: { kind: "media_reference", mediaReferenceId: id(payloadId + 1000) },
    sourceUsage: null,
    audioPolicy: "mute",
    framingPolicy: "contain",
  };
}

function rowWith(
  values = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"],
  separators?: string[],
  blockId = 10,
): NarrationBlockV2 {
  const tokenized = makeTokens(values, separators, blockId === 10 ? 100 : blockId * 10 + 100);
  const row: NarrationBlockV2 = {
    type: "narration",
    id: id(blockId),
    orderKey: `row-${blockId}`,
    text: tokenized.text,
    tokens: tokenized.tokens,
    primaryVisualSequence: {
      id: id(blockId + 1),
      slots: [{
        id: id(blockId + 2),
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
  return row;
}

function documentWith(
  row = rowWith(),
  supportingItems: SupportingItemV2[] = [],
): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Issue 191 sanitized omission sample",
    activeDraft: {
      blocks: [row, rowWith(["Other", "row", "is", "untouched"], undefined, 20)],
      supportingItems,
    },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 3,
    liveStateVector: "AQID",
    liveContentHash: fixedHash,
  };
}

function editFor(document: ScriptDocumentV2, tokenIndexes = [2]): AcceptedOmissionV2 {
  const row = document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10),
  )!;
  return {
    schemaVersion: "issue-189-v2-accepted-omission/v1",
    expectedDocumentHash: sha256CanonicalJson(document),
    blockId: row.id,
    blockRevision: row.version,
    tokenIds: tokenIndexes.map((index) => row.tokens[index]!.id),
    evidenceHash: hash("evidence"),
    decisionHash: hash("decision"),
  };
}

function enrichedDocument(): ScriptDocumentV2 {
  const row = rowWith();
  row.primaryVisualSequence!.slots.push({
    id: id(13),
    kind: "content",
    relation: { kind: "sequential" },
    boundaryBefore: { kind: "spoken_word", anchor: wordAnchor(row, 4, "before") as WordInpointAnchor },
    payload: visualPayload(14),
    playoutPolicy: "match_structural_interval",
    version: 1,
  });
  row.overlayEvents.push({
    id: id(15),
    payload: visualPayload(16) as Extract<ContentSlot["payload"], { kind: "visual" }>,
    timing: { kind: "timed", start: pointAnchor(row, 1), end: pointAnchor(row, 3, "after") },
    version: 1,
  });
  row.annotations = [{
    id: id(17),
    kind: "performance_note",
    range: textRange(row, 0, 4),
    value: "keep the surviving phrase connected",
    includeInPrompter: true,
    version: 1,
  }];
  row.performanceBeats = [{ id: id(18), range: textRange(row, 0, 1), version: 1 } satisfies PerformanceBeat];
  const enclosing = textRange(row, 0, 4);
  const supportRange: SupportingItemV2 = {
    id: id(30),
    version: 1,
    orderKey: "support-0",
    role: "citation",
    content: "sanitized support",
    placement: { kind: "range", range: enclosing },
    displayAttachment: textRange(row, 1, 4),
  };
  const supportPoint: SupportingItemV2 = {
    id: id(31),
    version: 1,
    orderKey: "support-1",
    role: "reference",
    content: "surviving point",
    placement: { kind: "point", anchor: pointAnchor(row, 3) },
  };
  const supportTimed: SupportingItemV2 = {
    id: id(32),
    version: 1,
    orderKey: "support-2",
    role: "audio_cue",
    content: "surviving timed anchors",
    placement: { kind: "timed", start: pointAnchor(row, 3, "after"), end: pointAnchor(row, 4) },
  };
  return documentWith(row, [supportRange, supportPoint, supportTimed]);
}

describe("Issue 191 v2 accepted omission", () => {
  it("deterministically removes one phrase, updates only enclosing ranges, and requests a whole-row replacement", () => {
    const input = enrichedDocument();
    const originalInput = canonicalJson(input);
    const originalSequence = canonicalJson(input.activeDraft.blocks[0]!.type === "narration" ? input.activeDraft.blocks[0]!.primaryVisualSequence : null);
    const originalOtherRow = canonicalJson(input.activeDraft.blocks[1]);
    const result = applyAcceptedOmissionV2(input, editFor(input));
    const row = result.document.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("missing revised row");

    expect(row.text).toBe("Alpha Bravo Delta Echo Foxtrot");
    expect(row.tokens.map((token) => token.value)).toEqual(["Alpha", "Bravo", "Delta", "Echo", "Foxtrot"]);
    expect(row.tokens.map((token) => [token.startOffset, token.endOffset])).toEqual([
      [0, 5], [6, 11], [12, 17], [18, 22], [23, 30],
    ]);
    expect(row.version).toBe(2);
    expect(canonicalJson(row.primaryVisualSequence)).toBe(originalSequence);
    expect(row.annotations?.[0]?.range.quotedText).toBe("Alpha Bravo Delta Echo");
    expect(row.annotations?.[0]?.range.anchorVersion).toBe(2);
    expect(row.annotations?.[0]?.version).toBe(2);
    expect(row.performanceBeats?.[0]?.range.quotedText).toBe("Alpha Bravo");
    expect(row.performanceBeats?.[0]?.version).toBe(1);

    const rangeSupport = result.document.activeDraft.supportingItems[0]!;
    expect(rangeSupport.version).toBe(2);
    if (rangeSupport.placement.kind !== "range") throw new Error("missing support range");
    expect(rangeSupport.placement.range.quotedText).toBe("Alpha Bravo Delta Echo");
    if (!rangeSupport.displayAttachment || "kind" in rangeSupport.displayAttachment) throw new Error("missing display range");
    expect(rangeSupport.displayAttachment.quotedText).toBe("Bravo Delta Echo");
    expect(canonicalJson(result.document.activeDraft.blocks[1])).toBe(originalOtherRow);
    expect(result.document.liveHeadSequence).toBe(input.liveHeadSequence + 1);
    expect(result.document.liveStateVector).toBe("");
    expect(result.document.liveContentHash).toBe(
      sha256CanonicalJson(Object.fromEntries(Object.entries(result.document).filter(([key]) => key !== "liveContentHash"))),
    );
    expect(result.documentJson).toBe(canonicalJson(result.document));
    expect(result.regeneration).toEqual({
      schemaVersion: "issue-189-v2-row-request/v1",
      policy: "replace_whole_row",
      blockId: row.id,
      blockRevision: row.version,
      text: row.text,
      textHash: hash(row.text),
      revisedDocumentHash: sha256CanonicalJson(result.document),
      evidenceHash: hash("evidence"),
      decisionHash: hash("decision"),
    });
    expect(Object.keys(result.regeneration).sort()).toEqual([
      "blockId", "blockRevision", "decisionHash", "evidenceHash", "policy", "revisedDocumentHash", "schemaVersion", "text", "textHash",
    ]);
    expect(canonicalJson(input)).toBe(originalInput);

    const repeatInput = enrichedDocument();
    const repeat = applyAcceptedOmissionV2(repeatInput, editFor(repeatInput));
    expect(repeat.documentJson).toBe(result.documentJson);
    expect(canonicalJson(repeat.regeneration)).toBe(canonicalJson(result.regeneration));
  });

  it("keeps UTF-16 offsets exact when the removed token contains an astral symbol", () => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "😀Charlie", "Delta", "Echo"]));
    const result = applyAcceptedOmissionV2(input, editFor(input));
    const row = result.document.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("missing revised row");
    expect(row.text).toBe("Alpha Bravo Delta Echo");
    expect(row.tokens.map((token) => [token.id, token.startOffset, token.endOffset])).toEqual([
      [id(100), 0, 5], [id(101), 6, 11], [id(103), 12, 17], [id(104), 18, 22],
    ]);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("preserves surviving astral text, token IDs and exact range affinities for two omitted tokens", () => {
    const row = rowWith(["😀Alpha", "Bravo", "Remove", "These", "Delta", "Echo"]);
    row.annotations = [{ id: id(80), kind: "performance_note", range: textRange(row, 1, 4, "after", "before"), value: "gap", includeInPrompter: true, version: 1 }];
    const input = documentWith(row);
    const result = applyAcceptedOmissionV2(input, editFor(input, [2, 3]));
    const revised = result.document.activeDraft.blocks[0]!;
    if (revised.type !== "narration") throw new Error("missing row");
    expect(revised.text).toBe("😀Alpha Bravo Delta Echo");
    expect(revised.tokens.map((token) => [token.id, token.startOffset, token.endOffset])).toEqual([
      [id(100), 0, 7], [id(101), 8, 13], [id(104), 14, 19], [id(105), 20, 24],
    ]);
    expect(revised.annotations![0]!.range).toEqual({ ...row.annotations[0]!.range, quotedText: " ", anchorVersion: 2 });
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it.each(["\ud800Alpha", "\udfffAlpha"])("refuses unpaired surrogate text: %s", (word) => {
    const input = documentWith(rowWith([word, "Bravo", "Remove", "These", "Delta"]));
    expect(validateScriptDocumentV2(input).valid).toBe(true);
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/Unicode scalar/);
  });

  it.each(["display", "prior"])("refuses a removed supporting endpoint: %s", (kind) => {
    const row = rowWith();
    const support: SupportingItemV2 = { id: id(81), version: 1, orderKey: "support", role: "reference", content: "retained support", placement: { kind: "unplaced", reason: "deliberate" } };
    if (kind === "display") support.displayAttachment = textRange(row, 2, 4);
    else support.placement = { kind: "unplaced", reason: "deliberate", priorAnchor: pointAnchor(row, 2) };
    const input = documentWith(row, [support]);
    const before = canonicalJson(input);
    expect(validateScriptDocumentV2(input).valid).toBe(true);
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/removed/);
    expect(canonicalJson(input)).toBe(before);
  });

  it.each([
    ["content before", (row: NarrationBlockV2) => {
      row.primaryVisualSequence!.slots[1] = {
        id: id(40), kind: "content", relation: { kind: "sequential" },
        boundaryBefore: { kind: "spoken_word", anchor: wordAnchor(row, 2, "before") as WordInpointAnchor },
        payload: visualPayload(41), playoutPolicy: "match_structural_interval", version: 1,
      };
    }],
    ["content after", (row: NarrationBlockV2) => {
      row.primaryVisualSequence!.slots[1] = {
        id: id(42), kind: "content", relation: { kind: "sequential" },
        boundaryBefore: { kind: "audible_word_end", anchor: wordAnchor(row, 2, "after") as WordAudibleEndAnchor },
        payload: visualPayload(43), playoutPolicy: "match_structural_interval", version: 1,
      };
    }],
    ["return", (row: NarrationBlockV2) => {
      const base = row.primaryVisualSequence!.slots[0]!;
      row.primaryVisualSequence!.slots = [
        base,
        {
          id: id(44), kind: "content", relation: { kind: "cutaway", parentSlotId: base.id },
          boundaryBefore: { kind: "spoken_word", anchor: wordAnchor(row, 1, "before") as WordInpointAnchor },
          payload: visualPayload(45), playoutPolicy: "match_structural_interval", version: 1,
        },
        { id: id(46), kind: "return", parentSlotId: base.id, inpoint: wordAnchor(row, 2, "before"), version: 1 },
        {
          id: id(47), kind: "content", relation: { kind: "sequential" },
          boundaryBefore: { kind: "spoken_word", anchor: wordAnchor(row, 4, "before") as WordInpointAnchor },
          payload: visualPayload(48), playoutPolicy: "match_structural_interval", version: 1,
        },
      ];
    }],
    ["overlay start", (row: NarrationBlockV2) => {
      row.overlayEvents.push({ id: id(49), payload: visualPayload(50) as Extract<ContentSlot["payload"], { kind: "visual" }>, timing: { kind: "timed", start: pointAnchor(row, 2), end: pointAnchor(row, 3) }, version: 1 });
    }],
    ["overlay end", (row: NarrationBlockV2) => {
      row.overlayEvents.push({ id: id(51), payload: visualPayload(52) as Extract<ContentSlot["payload"], { kind: "visual" }>, timing: { kind: "timed", start: pointAnchor(row, 1), end: pointAnchor(row, 2, "after") }, version: 1 });
    }],
    ["annotation", (row: NarrationBlockV2) => {
      row.annotations = [{ id: id(53), kind: "performance_note", range: textRange(row, 2, 3), value: "note", includeInPrompter: true, version: 1 }];
    }],
    ["performance", (row: NarrationBlockV2) => {
      row.performanceBeats = [{ id: id(54), range: textRange(row, 2, 3), version: 1 }];
    }],
  ])("refuses removed token IDs for every owned anchor surface: %s", (_name, mutate) => {
    const input = enrichedDocument();
    const row = input.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("missing row");
    mutate(row);
    const original = canonicalJson(input);
    expect(validateScriptDocumentV2(input).valid).toBe(true);
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/removed/);
    expect(canonicalJson(input)).toBe(original);
  });

  it("refuses a removed supporting point and timed anchor", () => {
    for (const placement of [
      { kind: "range", range: textRange(rowWith(), 2, 3) } as const,
      { kind: "point", anchor: pointAnchor(rowWith(), 2) } as const,
      { kind: "timed", start: pointAnchor(rowWith(), 2), end: pointAnchor(rowWith(), 3) } as const,
    ]) {
      const row = rowWith();
      const input = documentWith(row, [{ id: id(60), version: 1, orderKey: "support", role: "audio_cue", content: "anchor", placement }]);
      const original = canonicalJson(input);
      expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/removed/);
      expect(canonicalJson(input)).toBe(original);
    }
  });

  it("refuses cross-row owner ranges without repairing them", () => {
    const input = enrichedDocument();
    const target = input.activeDraft.blocks[0]!;
    const other = input.activeDraft.blocks[1]!;
    if (target.type !== "narration" || other.type !== "narration") throw new Error("missing rows");
    other.annotations = [{ id: id(70), kind: "performance_note", range: textRange(target, 0, 4), value: "cross-row", includeInPrompter: true, version: 1 }];
    const original = canonicalJson(input);
    expect(validateScriptDocumentV2(input).valid).toBe(true);
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/cross-row/);
    expect(canonicalJson(input)).toBe(original);
  });

  it.each([
    ["stale document hash", (edit: AcceptedOmissionV2) => { edit.expectedDocumentHash = fixedHash; }],
    ["stale row revision", (edit: AcceptedOmissionV2) => { edit.blockRevision += 1; }],
    ["noncontiguous phrase", (edit: AcceptedOmissionV2) => { edit.tokenIds = [id(102), id(104)]; }],
    ["phrase at row edge", (edit: AcceptedOmissionV2) => { edit.tokenIds = [id(100)]; }],
    ["unexpected key", (edit: AcceptedOmissionV2) => { (edit as AcceptedOmissionV2 & { extra?: string }).extra = "no"; }],
    ["invalid evidence hash", (edit: AcceptedOmissionV2) => { edit.evidenceHash = fixedHash.slice(0, -1); }],
  ])("refuses %s before changing the input", (_name, mutate) => {
    const input = enrichedDocument();
    const edit = editFor(input);
    mutate(edit);
    const original = canonicalJson(input);
    expect(() => applyAcceptedOmissionV2(input, edit)).toThrow();
    expect(canonicalJson(input)).toBe(original);
  });

  it.each([
    [["Alpha", "Bravo.", "Charlie", "Delta", "Echo"]],
    [["Alpha", "Bravo", "Charlie.", "Delta", "Echo"]],
  ])("refuses conservative sentence punctuation: %j", (values) => {
    const input = documentWith(rowWith(values));
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/punctuation/);
  });

  it("refuses punctuation in every joining gap", () => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "Charlie", "Delta", "Echo"], [" ", ", ", " ", " "]));
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/joining-gap/);
  });

  it("joins a comma-delimited single-word parenthetical with one space", () => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "Charlie", "Delta", "Echo"], [" ", ", ", ", ", " "]));
    const revised = applyAcceptedOmissionV2(input, editFor(input)).document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(revised.text).toBe("Alpha Bravo Delta Echo");
    for (const token of revised.tokens) expect(revised.text.slice(token.startOffset, token.endOffset)).toBe(token.value);
  });

  it.each([
    [[" ", ", ", ",", " "]],
    [[" ", ",", ", ", " "]],
    [[" ", ",  ", ", ", " "]],
    [[" ", ", ", " , ", " "]],
    [[" ", "; ", "; ", " "]],
  ])("keeps refusing other single-token punctuation gaps: %j", (separators) => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "Charlie", "Delta", "Echo"], separators));
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/joining-gap/);
  });

  it("keeps refusing a multi-token phrase set off by commas", () => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"], [" ", ", ", " ", ", ", " "]));
    expect(() => applyAcceptedOmissionV2(input, editFor(input, [2, 3]))).toThrow(/joining-gap/);
  });

  it.each([
    [" ", "", " ", " "],
    [" ", " ", "", " "],
  ])("refuses a sub-word omission at either outer join: %j", (...separators) => {
    const input = documentWith(rowWith(["Alpha", "Bravo", "Charlie", "Delta", "Echo"], separators));
    expect(validateScriptDocumentV2(input).valid).toBe(true);
    expect(() => applyAcceptedOmissionV2(input, editFor(input))).toThrow(/joining-gap/);
  });
});
