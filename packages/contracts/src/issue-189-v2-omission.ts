/** Pure v2 transformation of an independently accepted omission decision. */
import { createHash } from "node:crypto";

import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import type {
  NarrationBlockV2,
  ScriptDocumentV2,
  SupportingItemV2,
  TextAnchorRange,
  TimedPlacement,
  WordAudibleEndAnchor,
  WordInpointAnchor,
} from "./generated/contracts-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";

const HASH_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const JOINING_GAP = /^[ \t\r\n]+$/u;
const SENTENCE_PUNCTUATION = /[.!?]/u;
const SENTENCE_END = /[.!?]$/u;

export interface AcceptedOmissionV2 {
  schemaVersion: "issue-189-v2-accepted-omission/v1";
  expectedDocumentHash: string;
  blockId: string;
  blockRevision: number;
  tokenIds: string[];
  evidenceHash: string;
  decisionHash: string;
}

export interface RegenerationRequestV2 {
  schemaVersion: "issue-189-v2-row-request/v1";
  policy: "replace_whole_row";
  blockId: string;
  blockRevision: number;
  text: string;
  textHash: string;
  revisedDocumentHash: string;
  evidenceHash: string;
  decisionHash: string;
}

export interface OmissionRevisionV2 {
  document: ScriptDocumentV2;
  documentJson: string;
  regeneration: RegenerationRequestV2;
}

type WordAnchor = WordInpointAnchor | WordAudibleEndAnchor;
type PointAnchor = NonNullable<TimedPlacement["start"]>;
type AnchorValue = WordAnchor | TextAnchorRange | PointAnchor;

function requireFact(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function next(value: number, label: string): number {
  requireFact(
    Number.isSafeInteger(value) && value >= 0 && Number.isSafeInteger(value + 1),
    `${label} must remain an exact safe integer`,
  );
  return value + 1;
}

function narrationRow(document: ScriptDocumentV2, blockId: string): NarrationBlockV2 | undefined {
  return document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.id === blockId,
  );
}

function tokenIndex(row: NarrationBlockV2, tokenId: string): number {
  return row.tokens.findIndex((token) => token.id === tokenId);
}

function isTextRange(value: unknown): value is TextAnchorRange {
  return typeof value === "object" && value !== null && "startTokenId" in value && "endTokenId" in value;
}

function isWordAnchor(value: unknown): value is WordAnchor {
  return typeof value === "object" && value !== null && "blockId" in value && "tokenId" in value && "quotedWord" in value;
}

function checkWordAnchor(
  anchor: WordAnchor,
  ownerBlockId: string | undefined,
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (ownerBlockId !== undefined && anchor.blockId !== ownerBlockId) {
    throw new Error("cross-row anchor owner is unsupported");
  }
  const row = narrationRow(document, anchor.blockId);
  const token = row?.tokens.find((candidate) => candidate.id === anchor.tokenId);
  requireFact(
    row !== undefined &&
      token !== undefined &&
      token.value === anchor.quotedWord &&
      row.text.slice(token.startOffset, token.endOffset) === token.value,
    "stale word anchor is unsupported",
  );
  if (anchor.blockId === targetBlockId && removedTokenIds.has(anchor.tokenId)) {
    throw new Error("removed anchor word is unsupported");
  }
}

function checkTextRange(
  range: TextAnchorRange,
  ownerBlockId: string | undefined,
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (ownerBlockId !== undefined && range.blockId !== ownerBlockId) {
    throw new Error("cross-row anchor owner is unsupported");
  }
  const row = narrationRow(document, range.blockId);
  const startToken = row?.tokens.find((token) => token.id === range.startTokenId);
  const endToken = row?.tokens.find((token) => token.id === range.endTokenId);
  const start = startToken === undefined ? -1 : range.startAffinity === "before" ? startToken.startOffset : startToken.endOffset;
  const end = endToken === undefined ? -1 : range.endAffinity === "before" ? endToken.startOffset : endToken.endOffset;
  requireFact(
    row !== undefined &&
      startToken !== undefined &&
      endToken !== undefined &&
      row.tokens.indexOf(startToken) <= row.tokens.indexOf(endToken) &&
      start < end &&
      row.text.slice(start, end) === range.quotedText,
    "stale text range is unsupported",
  );
  if (range.blockId === targetBlockId && (removedTokenIds.has(range.startTokenId) || removedTokenIds.has(range.endTokenId))) {
    throw new Error("removed anchor endpoint is unsupported");
  }
}

function checkPointAnchor(
  anchor: PointAnchor,
  ownerBlockId: string | undefined,
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (anchor.kind === "word" || anchor.kind === "audible_word_end") {
    checkWordAnchor(anchor.anchor, ownerBlockId, document, targetBlockId, removedTokenIds);
  } else if (anchor.kind === "between_blocks") {
    const blocks = document.activeDraft.blocks;
    const before = blocks.findIndex((block) => block.id === anchor.beforeBlockId);
    const after = blocks.findIndex((block) => block.id === anchor.afterBlockId);
    requireFact(before >= 0 && after === before + 1, "stale between-blocks anchor is unsupported");
  } else {
    requireFact(
      document.activeDraft.blocks.some((block) => block.type === "narration" && block.overlayEvents.some((event) => event.id === anchor.eventId)),
      "stale overlay event anchor is unsupported",
    );
  }
}

function checkTimedPlacement(
  placement: TimedPlacement,
  ownerBlockId: string | undefined,
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (placement.start) checkPointAnchor(placement.start, ownerBlockId, document, targetBlockId, removedTokenIds);
  if (placement.end) checkPointAnchor(placement.end, ownerBlockId, document, targetBlockId, removedTokenIds);
}

function checkPlacement(
  placement: SupportingItemV2["placement"],
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (placement.kind === "range") {
    checkTextRange(placement.range, undefined, document, targetBlockId, removedTokenIds);
  } else if (placement.kind === "point") {
    checkPointAnchor(placement.anchor, undefined, document, targetBlockId, removedTokenIds);
  } else if (placement.kind === "timed") {
    checkTimedPlacement(placement, undefined, document, targetBlockId, removedTokenIds);
  } else if (placement.priorAnchor) {
    checkAnchorValue(placement.priorAnchor, undefined, document, targetBlockId, removedTokenIds);
  }
}

function checkAnchorValue(
  value: AnchorValue,
  ownerBlockId: string | undefined,
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  if (isTextRange(value)) checkTextRange(value, ownerBlockId, document, targetBlockId, removedTokenIds);
  else if (isWordAnchor(value)) checkWordAnchor(value, ownerBlockId, document, targetBlockId, removedTokenIds);
  else checkPointAnchor(value, ownerBlockId, document, targetBlockId, removedTokenIds);
}

function checkAllAnchors(
  document: ScriptDocumentV2,
  targetBlockId: string,
  removedTokenIds: ReadonlySet<string>,
): void {
  for (const block of document.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    const ownerBlockId = block.id;
    for (const slot of block.primaryVisualSequence?.slots ?? []) {
      if (slot.kind === "return") {
        if (slot.inpoint) checkWordAnchor(slot.inpoint, ownerBlockId, document, targetBlockId, removedTokenIds);
      } else if (slot.boundaryBefore.kind === "spoken_word" || slot.boundaryBefore.kind === "audible_word_end") {
        checkWordAnchor(slot.boundaryBefore.anchor, ownerBlockId, document, targetBlockId, removedTokenIds);
      }
    }
    for (const event of block.overlayEvents) {
      checkTimedPlacement(event.timing, ownerBlockId, document, targetBlockId, removedTokenIds);
    }
    for (const annotation of block.annotations ?? []) {
      checkTextRange(annotation.range, ownerBlockId, document, targetBlockId, removedTokenIds);
    }
    for (const beat of block.performanceBeats ?? []) {
      checkTextRange(beat.range, ownerBlockId, document, targetBlockId, removedTokenIds);
    }
  }
  for (const item of document.activeDraft.supportingItems) {
    checkPlacement(item.placement, document, targetBlockId, removedTokenIds);
    if (item.displayAttachment) {
      checkAnchorValue(item.displayAttachment, undefined, document, targetBlockId, removedTokenIds);
    }
  }
}

function rangeQuote(row: NarrationBlockV2, range: TextAnchorRange): string {
  const startToken = row.tokens.find((token) => token.id === range.startTokenId);
  const endToken = row.tokens.find((token) => token.id === range.endTokenId);
  requireFact(startToken !== undefined && endToken !== undefined, "omission leaves a stale text range");
  const start = range.startAffinity === "before" ? startToken.startOffset : startToken.endOffset;
  const end = range.endAffinity === "before" ? endToken.startOffset : endToken.endOffset;
  requireFact(start < end, "omission leaves an empty text range");
  return row.text.slice(start, end);
}

function rewriteRange(
  range: TextAnchorRange,
  originalRow: NarrationBlockV2,
  revisedRow: NarrationBlockV2,
  firstRemovedIndex: number,
  lastRemovedIndex: number,
): boolean {
  if (range.blockId !== originalRow.id) return false;
  const startIndex = tokenIndex(originalRow, range.startTokenId);
  const endIndex = tokenIndex(originalRow, range.endTokenId);
  requireFact(startIndex >= 0 && endIndex >= 0, "omission leaves a stale text range");
  if (startIndex >= firstRemovedIndex || endIndex <= lastRemovedIndex) return false;
  range.quotedText = rangeQuote(revisedRow, range);
  range.anchorVersion = next(range.anchorVersion, "text anchor version");
  return true;
}

function rewriteSupportingAnchor(
  value: AnchorValue,
  originalRow: NarrationBlockV2,
  revisedRow: NarrationBlockV2,
  firstRemovedIndex: number,
  lastRemovedIndex: number,
): boolean {
  return isTextRange(value)
    ? rewriteRange(value, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex)
    : false;
}

function rewriteAnchors(
  document: ScriptDocumentV2,
  originalRow: NarrationBlockV2,
  revisedRow: NarrationBlockV2,
  firstRemovedIndex: number,
  lastRemovedIndex: number,
): void {
  for (const block of document.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    if (block.id === originalRow.id) {
      for (const annotation of block.annotations ?? []) {
        if (rewriteRange(annotation.range, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex)) {
          annotation.version = next(annotation.version, "annotation version");
        }
      }
      for (const beat of block.performanceBeats ?? []) {
        if (rewriteRange(beat.range, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex)) {
          beat.version = next(beat.version, "performance beat version");
        }
      }
    }
  }
  for (const item of document.activeDraft.supportingItems) {
    let changed = false;
    if (item.placement.kind === "range") {
      changed = rewriteRange(item.placement.range, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex);
    } else if (item.placement.kind === "unplaced" && item.placement.priorAnchor) {
      changed = rewriteSupportingAnchor(item.placement.priorAnchor, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex);
    } else if (item.placement.kind === "point") {
      changed = rewriteSupportingAnchor(item.placement.anchor, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex);
    } else if (item.placement.kind === "timed") {
      if (item.placement.start) changed = rewriteSupportingAnchor(item.placement.start, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex) || changed;
      if (item.placement.end) changed = rewriteSupportingAnchor(item.placement.end, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex) || changed;
    }
    if (item.displayAttachment) {
      changed = rewriteSupportingAnchor(item.displayAttachment, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex) || changed;
    }
    if (changed) item.version = next(item.version, "supporting item version");
  }
}

function textHash(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function isUnicodeScalarText(value: string): boolean {
  return Buffer.from(value, "utf8").toString("utf8") === value;
}

export function applyAcceptedOmissionV2(
  input: ScriptDocumentV2,
  edit: AcceptedOmissionV2,
): OmissionRevisionV2 {
  const validation = validateScriptDocumentV2(input);
  requireFact(validation.valid, `v2 script validator refused input: ${canonicalJson(validation.diagnostics)}`);

  const expectedKeys = [
    "blockId",
    "blockRevision",
    "decisionHash",
    "evidenceHash",
    "expectedDocumentHash",
    "schemaVersion",
    "tokenIds",
  ];
  requireFact(
    canonicalJson(Object.keys(edit).sort()) === canonicalJson(expectedKeys),
    "unexpected omission edit fields",
  );
  requireFact(edit.schemaVersion === "issue-189-v2-accepted-omission/v1", "unsupported omission schema version");
  requireFact(HASH_PATTERN.test(edit.expectedDocumentHash), "invalid expected document hash");
  requireFact(HASH_PATTERN.test(edit.evidenceHash), "invalid evidence hash");
  requireFact(HASH_PATTERN.test(edit.decisionHash), "invalid decision hash");
  requireFact(sha256CanonicalJson(input) === edit.expectedDocumentHash, "stale current document hash");
  requireFact(typeof edit.blockId === "string" && edit.blockId.length > 0, "omission block ID is required");
  requireFact(Number.isSafeInteger(edit.blockRevision) && edit.blockRevision > 0, "omission block revision is invalid");
  requireFact(Array.isArray(edit.tokenIds) && edit.tokenIds.length > 0, "selected token IDs are required");
  requireFact(edit.tokenIds.every((tokenId) => typeof tokenId === "string" && tokenId.length > 0), "selected token IDs are invalid");
  requireFact(new Set(edit.tokenIds).size === edit.tokenIds.length, "selected token IDs must be unique");

  const originalRow = narrationRow(input, edit.blockId);
  requireFact(originalRow?.state === "active", "active narration row required");
  requireFact(originalRow.version === edit.blockRevision, "stale narration row revision");
  requireFact(
    isUnicodeScalarText(originalRow.text) && originalRow.tokens.every((token) => isUnicodeScalarText(token.value)),
    "narration text must contain Unicode scalar values",
  );
  const positions = edit.tokenIds.map((tokenId) => tokenIndex(originalRow, tokenId));
  const firstRemovedIndex = positions[0]!;
  const lastRemovedIndex = positions.at(-1)!;
  requireFact(
    firstRemovedIndex > 0 &&
      lastRemovedIndex < originalRow.tokens.length - 1 &&
      positions.every((position, index) => position === firstRemovedIndex + index),
    "selected token IDs must be an ordered contiguous interior phrase",
  );
  const previous = originalRow.tokens[firstRemovedIndex - 1]!;
  const following = originalRow.tokens[lastRemovedIndex + 1]!;
  for (let index = firstRemovedIndex; index <= lastRemovedIndex + 1; index += 1) {
    requireFact(
      JOINING_GAP.test(originalRow.text.slice(originalRow.tokens[index - 1]!.endOffset, originalRow.tokens[index]!.startOffset)),
      "unsupported joining-gap punctuation",
    );
  }
  const selectedText = originalRow.text.slice(
    originalRow.tokens[firstRemovedIndex]!.startOffset,
    originalRow.tokens[lastRemovedIndex]!.endOffset,
  );
  requireFact(!SENTENCE_END.test(previous.value) && !SENTENCE_PUNCTUATION.test(selectedText), "sentence punctuation boundary is unsupported");

  const removedTokenIds = new Set(edit.tokenIds);
  checkAllAnchors(input, edit.blockId, removedTokenIds);

  const document = structuredClone(input);
  const revisedRow = narrationRow(document, edit.blockId);
  requireFact(revisedRow !== undefined, "missing cloned narration row");
  const delta = 1 - (following.startOffset - previous.endOffset);
  revisedRow.text = originalRow.text.slice(0, previous.endOffset) +
    " " +
    originalRow.text.slice(following.startOffset);
  const kept = revisedRow.tokens
    .filter((token) => !removedTokenIds.has(token.id))
    .map((token) => token.startOffset >= following.startOffset
      ? { ...token, startOffset: token.startOffset + delta, endOffset: token.endOffset + delta }
      : token);
  const firstKept = kept[0];
  requireFact(firstKept !== undefined, "empty narration after omission");
  revisedRow.tokens = [firstKept, ...kept.slice(1)];
  revisedRow.version = next(originalRow.version, "narration row version");
  rewriteAnchors(document, originalRow, revisedRow, firstRemovedIndex, lastRemovedIndex);

  document.liveHeadSequence = next(input.liveHeadSequence, "live head sequence");
  document.liveStateVector = "";
  document.liveContentHash = sha256CanonicalJson(
    Object.fromEntries(Object.entries(document).filter(([key]) => key !== "liveContentHash")),
  );
  const afterValidation = validateScriptDocumentV2(document);
  requireFact(afterValidation.valid, `v2 script validator refused omission: ${canonicalJson(afterValidation.diagnostics)}`);
  const documentJson = canonicalJson(document);
  const regeneration = {
    schemaVersion: "issue-189-v2-row-request/v1" as const,
    policy: "replace_whole_row" as const,
    blockId: revisedRow.id,
    blockRevision: revisedRow.version,
    text: revisedRow.text,
    textHash: textHash(revisedRow.text),
    revisedDocumentHash: sha256CanonicalJson(document),
    evidenceHash: edit.evidenceHash,
    decisionHash: edit.decisionHash,
  };
  return { document, documentJson, regeneration };
}
