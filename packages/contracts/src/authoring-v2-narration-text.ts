import { createHash } from "node:crypto";

import type { NarrationBlockV2, NarrationToken } from "./generated/contracts-v2.js";
import { inspectStageDirectionsV2 } from "./authoring-v2-stage-directions.js";

/** An exact replacement in the *old* row's UTF-16 coordinates. */
export interface NarrationTextReplacementV2 {
  startOffset: number;
  endOffset: number;
  insertedText: string;
  editId: string;
}

export interface NarrationTextIdentityV2 {
  documentId: string;
  revision: number;
  /** IDs anywhere in the document, including other rows and visual payloads. */
  reservedIds: ReadonlySet<string>;
}

export type NarrationTextSpliceResultV2 =
  | {
    ok: true;
    row: NarrationBlockV2;
    survivingTokenIds: string[];
    deletedTokenIds: string[];
    createdTokenIds: string[];
    /** New words containing characters from an old word that split or joined. */
    reshapedTokenIds: ReadonlyMap<string, readonly string[]>;
  }
  | { ok: false; code: string; message: string };

interface Lexeme { value: string; startOffset: number; endOffset: number }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const refusal = (code: string, message: string): NarrationTextSpliceResultV2 => ({ ok: false, code, message });

/** JavaScript offsets are UTF-16 code units, including the two units of an emoji. */
function completeSurrogates(text: string): boolean {
  for (let offset = 0; offset < text.length; offset += 1) {
    const unit = text.charCodeAt(offset);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = text.charCodeAt(offset + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
      offset += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) return false;
  }
  return true;
}

function scalarBoundary(text: string, offset: number): boolean {
  if (!Number.isSafeInteger(offset) || offset < 0 || offset > text.length) return false;
  if (offset === 0 || offset === text.length) return true;
  const preceding = text.charCodeAt(offset - 1);
  const following = text.charCodeAt(offset);
  return !(preceding >= 0xd800 && preceding <= 0xdbff && following >= 0xdc00 && following <= 0xdfff);
}

/** Literal lexemes; bracket delimiters are not tokens in the saved narration grammar. */
function lexemes(text: string): Lexeme[] {
  return Array.from(text.matchAll(/[^\s[\]]+/gu), (match) => ({
    value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  }));
}

function tokenId(identity: NarrationTextIdentityV2, rowId: string, editId: string, ordinal: number): string {
  const hex = createHash("sha256")
    .update(`vera:narration-text:v2:${identity.documentId}:${rowId}:${identity.revision}:${editId}:${ordinal}`, "utf8")
    .digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-${"89ab"[Number.parseInt(hex[16]!, 16) % 4]!}${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/**
 * Pure, positional word-identity splice. Unchanged tokens are reserved by their
 * translated exact offsets *before* any local matching. Only the neighborhood
 * touched by the supplied edit can compete for a surviving token ID. In
 * particular, an identical phrase elsewhere in the row can never steal a cue.
 *
 * Visuals, quotes and other word-bound references are intentionally unchanged
 * here; their atomic reconciliation belongs to the row transaction's coverage
 * phase. A caller must validate or refuse before saving an unreconciled row.
 */
export function spliceNarrationTextV2(
  row: NarrationBlockV2,
  edit: NarrationTextReplacementV2,
  identity: NarrationTextIdentityV2,
): NarrationTextSpliceResultV2 {
  if (!row || row.type !== "narration" || row.plainDirection === true || typeof row.text !== "string" || !Array.isArray(row.tokens)) {
    return refusal("NARRATION_TEXT_TARGET_INVALID", "Edit the text of an ordinary narration row.");
  }
  if (!edit || typeof edit.insertedText !== "string" || !uuid.test(edit.editId ?? "") ||
      !scalarBoundary(row.text, edit.startOffset) || !scalarBoundary(row.text, edit.endOffset) ||
      edit.startOffset > edit.endOffset || !completeSurrogates(row.text) || !completeSurrogates(edit.insertedText)) {
    return refusal("NARRATION_TEXT_SPAN_INVALID", "Use a complete UTF-16 replacement range and text with no split or unpaired surrogates.");
  }
  if (!identity || !uuid.test(identity.documentId ?? "") || !Number.isSafeInteger(identity.revision) ||
      identity.revision < 0 || !(identity.reservedIds instanceof Set)) {
    return refusal("NARRATION_TEXT_IDENTITY_INVALID", "Provide the original document identity, revision, and reserved IDs.");
  }
  const oldLexemes = lexemes(row.text);
  if (oldLexemes.length !== row.tokens.length || oldLexemes.some((lexeme, i) =>
    lexeme.value !== row.tokens[i]?.value || lexeme.startOffset !== row.tokens[i]?.startOffset ||
    lexeme.endOffset !== row.tokens[i]?.endOffset) ||
      new Set(row.tokens.map((token) => token.id)).size !== row.tokens.length) {
    return refusal("NARRATION_TEXT_GRAMMAR_UNSUPPORTED", "The existing words cannot be retokenized without losing their identities.");
  }
  const directions = inspectStageDirectionsV2(row);
  const badDirection = () => refusal("NARRATION_TEXT_DIRECTION_UNSUPPORTED", "Keep both delimiters of each stage direction or remove the pair together.");
  // Inserting brackets could silently reinterpret an old spoken word as a direction.
  if (edit.insertedText.includes("[") || edit.insertedText.includes("]")) {
    return refusal("NARRATION_TEXT_DIRECTION_UNSUPPORTED", "Edit direction delimiters with the dedicated direction commands.");
  }
  if (directions.issues.length > 0) return badDirection();

  let { startOffset, endOffset, insertedText } = edit;
  for (const { openOffset, closeOffset } of directions.runs) {
    const removesOpen = startOffset <= openOffset && openOffset < endOffset;
    const removesClose = startOffset <= closeOffset && closeOffset < endOffset;
    if (removesOpen !== removesClose) return badDirection();
    if (openOffset < startOffset && endOffset <= closeOffset) {
      const inner = row.text.slice(openOffset + 1, startOffset) + insertedText + row.text.slice(endOffset, closeOffset);
      // A pair with no words cannot carry nonspoken intent in the saved model.
      if (!inner.trim()) {
        startOffset = openOffset;
        endOffset = closeOffset + 1;
        insertedText = "";
      }
    }
  }
  const text = row.text.slice(0, startOffset) + insertedText + row.text.slice(endOffset);
  if (text === row.text) return refusal("NARRATION_TEXT_NO_CHANGE", "The replacement leaves the narration text unchanged.");
  const nextLexemes = lexemes(text);
  const delta = insertedText.length - (endOffset - startOffset);
  const translate = (offset: number) => offset < startOffset ? offset : offset + delta;
  const pairs = directions.runs.flatMap(({ openOffset, closeOffset }) =>
    startOffset <= openOffset && openOffset < endOffset ? [] : [{
      openOffset: translate(openOffset), closeOffset: translate(closeOffset),
    }]);
  const nonspoken = nextLexemes.map((word) => pairs.some(({ openOffset, closeOffset }) =>
    openOffset < word.startOffset && word.endOffset <= closeOffset));
  const next: (NarrationToken | null)[] = nextLexemes.map(() => null);
  const oldUsed = new Set<string>();
  const assign = (token: NarrationToken, index: number) => {
    next[index] = { ...token, ...nextLexemes[index]! };
    oldUsed.add(token.id);
  };
  const sameSpeech = (token: NarrationToken, index: number) => (token.spoken === false) === nonspoken[index];

  // Positions before/after the splice are the only globally allowed matches.
  const indexAtStart = new Map(nextLexemes.map((word, index) => [word.startOffset, index]));
  for (const token of row.tokens) {
    const translated = token.endOffset <= startOffset
      ? token.startOffset
      : token.startOffset >= endOffset ? token.startOffset + delta : null;
    const index = translated === null ? undefined : indexAtStart.get(translated);
    if (index !== undefined && nextLexemes[index]!.value === token.value && sameSpeech(token, index)) assign(token, index);
  }

  // A split keeps the ID on the first surviving part. In a join, the first
  // contributing word owns the ID, but coverage can still follow the others.
  const reshaped = new Map<string, number[]>();
  for (const token of row.tokens) {
    if (oldUsed.has(token.id)) continue;
    const offsets = [];
    if (token.startOffset < startOffset) offsets.push(token.startOffset);
    if (token.endOffset > endOffset) offsets.push(Math.max(token.startOffset, endOffset) + delta);
    const indexes = [...new Set(offsets.map((offset) => nextLexemes.findIndex((word, index) =>
      word.startOffset <= offset && offset < word.endOffset && sameSpeech(token, index))))].filter((index) => index >= 0);
    const first = indexes[0];
    if (first === undefined) continue;
    reshaped.set(token.id, indexes);
    if (next[first] === null) assign(token, first);
  }

  const candidates = row.tokens.filter((token) => !oldUsed.has(token.id) && !reshaped.has(token.id));
  const remaining = nextLexemes.map((_lexeme, i) => i).filter((i) => next[i] === null);

  // Exact words at the edges of the changed local window win before rewrites.
  // This is why H1 keeps the second `harbor`'s ID on `harbor`, not on `old`.
  let left = 0;
  while (left < candidates.length && left < remaining.length &&
    sameSpeech(candidates[left]!, remaining[left]!) &&
    candidates[left]!.value === nextLexemes[remaining[left]!]!.value) {
    assign(candidates[left]!, remaining[left]!);
    left += 1;
  }
  let oldRight = candidates.length - 1;
  let newRight = remaining.length - 1;
  while (oldRight >= left && newRight >= left &&
    sameSpeech(candidates[oldRight]!, remaining[newRight]!) &&
    candidates[oldRight]!.value === nextLexemes[remaining[newRight]!]!.value) {
    assign(candidates[oldRight]!, remaining[newRight]!);
    oldRight -= 1;
    newRight -= 1;
  }
  // Fully replaced words retain identity in edit order within the same speech intent.
  const rewritten = candidates.slice(left, oldRight + 1);
  for (const index of remaining.slice(left, newRight + 1)) {
    const oldIndex = rewritten.findIndex((token) => sameSpeech(token, index));
    if (oldIndex >= 0) assign(rewritten.splice(oldIndex, 1)[0]!, index);
  }

  const createdTokenIds: string[] = [];
  const usedIds = new Set(identity.reservedIds);
  // Even direct helper calls must not allocate an ID already on the current row.
  row.tokens.forEach((token) => usedIds.add(token.id));
  let ordinal = 0;
  for (let index = 0; index < next.length; index += 1) {
    if (next[index] !== null) continue;
    const id = tokenId(identity, row.id, edit.editId, ordinal++);
    if (usedIds.has(id)) return refusal("NARRATION_TEXT_ID_COLLISION", "A newly generated word identity already belongs to another document entity.");
    usedIds.add(id);
    createdTokenIds.push(id);
    next[index] = { id, ...nextLexemes[index]!, ...(nonspoken[index] ? { spoken: false } : {}) };
  }

  const tokens = next as NarrationToken[];
  const resultRow = { ...structuredClone(row), text, tokens };
  const inspected = inspectStageDirectionsV2(resultRow);
  if (inspected.issues.length > 0 || inspected.runs.length !== pairs.length) return badDirection();
  return {
    ok: true,
    row: resultRow,
    survivingTokenIds: row.tokens.filter((token) => oldUsed.has(token.id)).map((token) => token.id),
    deletedTokenIds: row.tokens.filter((token) => !oldUsed.has(token.id)).map((token) => token.id),
    createdTokenIds,
    reshapedTokenIds: new Map([...reshaped].map(([old, indexes]) => [old, indexes.map((index) => tokens[index]!.id)])),
  };
}
