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
  | { ok: true; row: NarrationBlockV2; survivingTokenIds: string[]; deletedTokenIds: string[]; createdTokenIds: string[] }
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
  if (directions.issues.length > 0 || directions.runs.some((run) =>
    edit.startOffset < run.closeOffset + 1 && edit.endOffset > run.openOffset ||
    edit.startOffset === edit.endOffset && edit.startOffset > run.openOffset && edit.startOffset < run.closeOffset + 1)) {
    return refusal("NARRATION_TEXT_DIRECTION_UNSUPPORTED", "Edit stage-direction words using the dedicated direction commands.");
  }
  // Inserting brackets could silently reinterpret an old spoken word as a direction.
  if (edit.insertedText.includes("[") || edit.insertedText.includes("]")) {
    return refusal("NARRATION_TEXT_DIRECTION_UNSUPPORTED", "Edit direction delimiters with the dedicated direction commands.");
  }

  const text = row.text.slice(0, edit.startOffset) + edit.insertedText + row.text.slice(edit.endOffset);
  if (text === row.text) return refusal("NARRATION_TEXT_NO_CHANGE", "The replacement leaves the narration text unchanged.");
  const nextLexemes = lexemes(text);
  const delta = edit.insertedText.length - (edit.endOffset - edit.startOffset);
  const next: (NarrationToken | null)[] = nextLexemes.map(() => null);
  const oldUsed = new Set<string>();
  const newUsed = new Set<number>();

  // Positions before/after the splice are the only globally allowed matches.
  for (const token of row.tokens) {
    const translated = token.endOffset <= edit.startOffset
      ? token.startOffset
      : token.startOffset >= edit.endOffset ? token.startOffset + delta : null;
    if (translated === null) continue;
    const index = nextLexemes.findIndex((lexeme, i) => !newUsed.has(i) &&
      lexeme.startOffset === translated && lexeme.endOffset === translated + token.value.length && lexeme.value === token.value);
    if (index < 0) continue;
    next[index] = { ...token, startOffset: translated, endOffset: translated + token.value.length };
    newUsed.add(index);
    oldUsed.add(token.id);
  }

  const candidates = row.tokens.filter((token) => !oldUsed.has(token.id));
  const remaining = nextLexemes.map((_lexeme, i) => i).filter((i) => !newUsed.has(i));

  // Exact words at the edges of the changed local window win before rewrites.
  // This is why H1 keeps the second `harbor`'s ID on `harbor`, not on `old`.
  let left = 0;
  while (left < candidates.length && left < remaining.length &&
    candidates[left]!.value === nextLexemes[remaining[left]!]!.value) {
    const old = candidates[left]!;
    const index = remaining[left]!;
    next[index] = { ...old, ...nextLexemes[index]! };
    oldUsed.add(old.id);
    newUsed.add(index);
    left += 1;
  }
  let oldRight = candidates.length - 1;
  let newRight = remaining.length - 1;
  while (oldRight >= left && newRight >= left &&
    candidates[oldRight]!.value === nextLexemes[remaining[newRight]!]!.value) {
    const old = candidates[oldRight]!;
    const index = remaining[newRight]!;
    next[index] = { ...old, ...nextLexemes[index]! };
    oldUsed.add(old.id);
    newUsed.add(index);
    oldRight -= 1;
    newRight -= 1;
  }
  const rewritten = candidates.filter((token) => !oldUsed.has(token.id));
  const unmatched = remaining.filter((index) => !newUsed.has(index));
  if (rewritten.length && unmatched.length && rewritten.length !== unmatched.length) {
    return refusal("NARRATION_TEXT_IDENTITY_AMBIGUOUS", "The edit would ambiguously split or merge word identities; use a smaller splice.");
  }
  rewritten.slice(0, unmatched.length).forEach((token, index) => {
    const at = unmatched[index]!;
    next[at] = { ...token, ...nextLexemes[at]! };
    oldUsed.add(token.id);
    newUsed.add(at);
  });

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
    next[index] = { id, ...nextLexemes[index]! };
  }

  const tokens = next as NarrationToken[];
  // A nonspoken token may survive unchanged, but may not move outside its
  // original bracket pair through an accidental lexical restructure.
  const resultRow = { ...structuredClone(row), text, tokens };
  if (inspectStageDirectionsV2(resultRow).issues.length > 0 ||
      tokens.some((token) => token.spoken === false && !row.tokens.some((old) => old.id === token.id && old.spoken === false))) {
    return refusal("NARRATION_TEXT_DIRECTION_UNSUPPORTED", "The edit would break a stage-direction pair.");
  }
  return {
    ok: true,
    row: resultRow,
    survivingTokenIds: row.tokens.filter((token) => oldUsed.has(token.id)).map((token) => token.id),
    deletedTokenIds: row.tokens.filter((token) => !oldUsed.has(token.id)).map((token) => token.id),
    createdTokenIds,
  };
}
