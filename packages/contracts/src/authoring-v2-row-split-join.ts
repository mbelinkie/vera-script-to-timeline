import type { NarrationBlockV2, NarrationToken, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import {
  derivedCoverageIdV2,
  emptyRowCoverageV2,
  isCoverageRefusalV2,
  placedVisualsAsUnattachedV2,
  redistributeCoverageV2,
} from "./authoring-v2-coverage.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { inspectStageDirectionsV2 } from "./authoring-v2-stage-directions.js";
import { preserveStashOriginAfterEditV2 } from "./authoring-v2-stash-origin.js";

/**
 * Split and join script rows (S03 D97, D114, D115, D137, D138).
 *
 * Words move between rows with their token IDs, so everything anchored to a
 * word follows it: visuals (by the On Camera coverage rule), overlays,
 * pronunciation and performance notes, supporting items and word comments.
 *
 * What moves
 * - Split at the cursor: the words from the cursor on go to a new row below.
 *   With no words on one side there is nothing to split; that is Add row
 *   (`create_row`), because a script row with no words cannot be stored yet.
 * - Split from a selection: a selection that includes the row's first word
 *   becomes a new row above; one that includes its last word becomes a new row
 *   below. The original row keeps its ID and the other words.
 * - Join: the selected words (or the whole row) go to the end of the row above
 *   or the start of the row below. A row left with no content is removed.
 * - A stage direction is never divided: it stays with its first word.
 * - A paragraph break is a line break in the row's text. One after a row's
 *   final word travels with that word. Joining a whole row to the row above
 *   (Backspace, D115) starts it as a new paragraph; joining selected words
 *   uses a space.
 *
 * What still points at a row afterwards
 * - A reference to "the end of the row" (an outgoing transition, the last row
 *   of a music cue, a Stash return gap after it) follows the row's last words.
 *   A reference to "the start of the row" follows its first words.
 * - A join is refused, with nothing changed, when a reference cannot keep its
 *   meaning: a transition between the two rows, a music cue that covers only
 *   one of them, or a note or overlay whose words would end up in two rows.
 */

export type RowWordSelectionV2 = { startTokenId: string; endTokenId: string };

export type SplitRowCommandV2 = {
  kind: "split_row";
  rowId: string;
  /** ID for the row the split creates. */
  newRowId: string;
  /** The cursor (the token it sits before; null at the end of the row) or a selection of whole tokens. */
  at: { beforeTokenId: string | null } | RowWordSelectionV2;
};

export type JoinRowsCommandV2 = {
  kind: "join_rows";
  rowId: string;
  direction: "previous" | "next";
  /** The selected words, or null for the whole row as a new paragraph (D115). */
  words: RowWordSelectionV2 | null;
};

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Problem = AuthoringDiagnosticV2;
interface Piece { text: string; tokens: NarrationToken[] }

const isProblem = (value: unknown): value is Problem =>
  typeof value === "object" && value !== null && "code" in value && "message" in value && "jsonPath" in value;

function problem(code: string, message: string, blockId?: string, entityId?: string): Problem {
  return { code, message, jsonPath: "/activeDraft", ...(blockId ? { blockId } : {}), ...(entityId ? { entityId } : {}) };
}

function isSelection(value: unknown): value is RowWordSelectionV2 {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  const item = value as Record<string, unknown>;
  return keys.length === 2 && typeof item.startTokenId === "string" && item.startTokenId.length > 0 &&
    typeof item.endTokenId === "string" && item.endTokenId.length > 0;
}

/** Exact command shape; anything else is refused before the document is read. */
export function isSplitOrJoinCommandV2(value: unknown): value is SplitRowCommandV2 | JoinRowsCommandV2 {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const command = value as Record<string, unknown>;
  const keys = Object.keys(command);
  if (typeof command.rowId !== "string" || command.rowId.length === 0) return false;
  if (command.kind === "split_row") {
    if (keys.length !== 4 || typeof command.newRowId !== "string" || command.newRowId.length === 0 || command.newRowId === command.rowId) return false;
    const at = command.at;
    if (isSelection(at)) return true;
    if (!at || typeof at !== "object" || Array.isArray(at) || Object.keys(at).length !== 1 || !Object.hasOwn(at, "beforeTokenId")) return false;
    const before = (at as Record<string, unknown>).beforeTokenId;
    return before === null || typeof before === "string" && before.length > 0;
  }
  if (command.kind === "join_rows") {
    return keys.length === 4 && (command.direction === "previous" || command.direction === "next") &&
      Object.hasOwn(command, "words") && (command.words === null || isSelection(command.words));
  }
  return false;
}

/** True when a join puts back together exactly the two rows a split made (D124). */
export function joinReversesSplitV2(document: ScriptDocumentV2, command: JoinRowsCommandV2, splitRowIds: readonly [string, string]): boolean {
  const blocks = document.activeDraft.blocks;
  const index = blocks.findIndex((block) => block.id === command.rowId);
  const row = blocks[index];
  const neighbour = blocks[index + (command.direction === "previous" ? -1 : 1)];
  if (!row || row.type !== "narration" || !neighbour) return false;
  if (!splitRowIds.includes(row.id) || !splitRowIds.includes(neighbour.id) || row.id === neighbour.id) return false;
  return command.words === null ||
    row.tokens.length > 0 && command.words.startTokenId === row.tokens[0]!.id && command.words.endTokenId === row.tokens.at(-1)!.id;
}

function eligible(row: Block | undefined, verb: "split" | "joined"): NarrationBlockV2 | Problem {
  if (!row || row.type === "section") return problem("ROW_NOT_FOUND", "Choose an existing row in the script.");
  if (row.type !== "narration") {
    return problem("ROW_SPLIT_JOIN_UNSUPPORTED", `Only a narration row can be ${verb}.`, row.id);
  }
  if (row.plainDirection === true) {
    return problem("ROW_SPLIT_JOIN_UNSUPPORTED", `A row that is one whole stage direction cannot be ${verb}. Make it spoken first.`, row.id);
  }
  if (row.attachedFootage) {
    return problem("ROW_SPLIT_JOIN_UNSUPPORTED", `A note that owns attached footage cannot be ${verb}. Detach the footage first.`, row.id);
  }
  if (inspectStageDirectionsV2(row).issues.length > 0) {
    return problem("ROW_SPLIT_JOIN_UNSUPPORTED", `Fix this row's stage direction brackets before it is ${verb}.`, row.id);
  }
  return row;
}

/** A boundary that falls inside a stage direction moves to its end: the direction stays with its first word. */
function snap(row: NarrationBlockV2, boundary: number): number {
  const run = inspectStageDirectionsV2(row).runs.find((item) => item.startTokenIndex < boundary && boundary < item.endTokenIndexExclusive);
  return run ? run.endTokenIndexExclusive : boundary;
}

/** The selection as whole tokens [from, to), after the stage-direction rule. */
function selected(row: NarrationBlockV2, words: RowWordSelectionV2): { from: number; to: number } | Problem {
  const first = row.tokens.findIndex((token) => token.id === words.startTokenId);
  const last = row.tokens.findIndex((token) => token.id === words.endTokenId);
  if (first < 0 || last < 0) return problem("ROW_SELECTION_INVALID", "The selection falls outside this row's words.", row.id);
  if (last < first) return problem("ROW_SELECTION_INVALID", "The selection's last word comes before its first word.", row.id);
  const from = snap(row, first);
  const to = snap(row, last + 1);
  if (from >= to) return problem("ROW_SELECTION_INVALID", "The selection is inside one stage direction, which moves only as a whole from its first word.", row.id);
  return { from, to };
}

/** Where the text divides between token `boundary - 1` and token `boundary`. */
function seam(row: NarrationBlockV2, boundary: number): { headEnd: number; tailStart: number } {
  const previousEnd = row.tokens[boundary - 1]!.endOffset;
  const gap = row.text.slice(previousEnd, row.tokens[boundary]!.startOffset);
  const space = gap.search(/\s/u);
  if (space < 0) {
    // No space to divide at: an opening bracket starts the second part, anything else ends the first.
    const bracket = gap.indexOf("[");
    const at = previousEnd + (bracket < 0 ? gap.length : bracket);
    return { headEnd: at, tailStart: at };
  }
  const run = /^\s+/u.exec(gap.slice(space))![0].length;
  return { headEnd: previousEnd + space, tailStart: previousEnd + space + run };
}

/** The first `boundary` tokens with their text. The whole row keeps its text exactly. */
function head(row: NarrationBlockV2, boundary: number): Piece {
  if (boundary <= 0) return { text: "", tokens: [] };
  if (boundary >= row.tokens.length) return { text: row.text, tokens: row.tokens.map((token) => ({ ...token })) };
  return { text: row.text.slice(0, seam(row, boundary).headEnd), tokens: row.tokens.slice(0, boundary).map((token) => ({ ...token })) };
}

/** The tokens from `boundary` on, with the text after them (so a final paragraph break travels, D138). */
function tail(row: NarrationBlockV2, boundary: number): Piece {
  if (boundary >= row.tokens.length) return { text: "", tokens: [] };
  if (boundary <= 0) return { text: row.text, tokens: row.tokens.map((token) => ({ ...token })) };
  const start = seam(row, boundary).tailStart;
  return {
    text: row.text.slice(start),
    tokens: row.tokens.slice(boundary).map((token) => ({ ...token, startOffset: token.startOffset - start, endOffset: token.endOffset - start })),
  };
}

function concat(first: Piece, second: Piece, paragraph: boolean): Piece {
  let separator = "";
  if (first.text.length > 0 && second.text.length > 0) {
    if (paragraph) separator = /\n\s*$/u.test(first.text) || /^\s*\n/u.test(second.text) ? "" : "\n";
    else separator = /\s$/u.test(first.text) || /^\s/u.test(second.text) ? "" : " ";
  }
  const shift = first.text.length + separator.length;
  return {
    text: `${first.text}${separator}${second.text}`,
    tokens: [...first.tokens, ...second.tokens.map((token) => ({ ...token, startOffset: token.startOffset + shift, endOffset: token.endOffset + shift }))],
  };
}

const TOKEN_KEYS = ["tokenId", "startTokenId", "endTokenId"];

function tokenReferences(value: unknown, found = new Set<string>()): Set<string> {
  if (!value || typeof value !== "object") return found;
  for (const [key, child] of Object.entries(value)) {
    if (TOKEN_KEYS.includes(key) && typeof child === "string") found.add(child);
    else tokenReferences(child, found);
  }
  return found;
}

interface Move {
  /** The row the words leave, as stored before the edit. */
  source: NarrationBlockV2;
  /** The row the moved words arrive in. */
  destinationId: string;
  movedTokenIds: Set<string>;
  /** The source row is removed, so everything it owned goes with its words. */
  removed: boolean;
}

/**
 * Point every word anchor at the row its word is now in. Returns the reason
 * when one anchor names words that ended up in two rows.
 */
function retargetAnchors(value: unknown, move: Move): string | null {
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) {
    for (const child of value) {
      const reason = retargetAnchors(child, move);
      if (reason) return reason;
    }
    return null;
  }
  const item = value as Record<string, unknown>;
  if (item.blockId === move.source.id) {
    const named = TOKEN_KEYS.flatMap((key) => typeof item[key] === "string" ? [item[key]] : []);
    const moving = named.filter((tokenId) => move.movedTokenIds.has(tokenId)).length;
    if (moving > 0 && moving < named.length) return "It is anchored to words that would end up in two rows.";
    if (named.length > 0 ? moving > 0 : move.removed) item.blockId = move.destinationId;
  }
  for (const child of Object.values(item)) {
    const reason = retargetAnchors(child, move);
    if (reason) return reason;
  }
  return null;
}

/** Divide a row's word-anchored entities between the words that stay and the words that move. */
function divide<T extends { id: string }>(items: T[] | undefined, move: Move, label: string): { stay: T[]; go: T[] } | Problem {
  const stay: T[] = [];
  const go: T[] = [];
  for (const item of items ?? []) {
    const named = [...tokenReferences(item)];
    const moving = named.filter((tokenId) => move.movedTokenIds.has(tokenId)).length;
    if (moving > 0 && moving < named.length) {
      return problem("ROW_ANCHOR_STRADDLES_BOUNDARY", `${label} covers words on both sides of this boundary. Shorten or remove it first.`, move.source.id, item.id);
    }
    if (named.length > 0 ? moving === 0 : !move.removed) {
      stay.push(item);
      continue;
    }
    const moved = structuredClone(item);
    const reason = retargetAnchors(moved, move);
    if (reason) return problem("ROW_ANCHOR_STRADDLES_BOUNDARY", `${label}: ${reason}`, move.source.id, item.id);
    go.push(moved);
  }
  return { stay, go };
}

function setList<K extends "annotations" | "performanceBeats" | "unattachedVisuals">(row: NarrationBlockV2, key: K, items: NonNullable<NarrationBlockV2[K]>, keepEmpty: boolean): void {
  if (items.length > 0 || keepEmpty) row[key] = items;
  else delete row[key];
}

/**
 * Build the rows a move leaves: `remaining` (null when the source row is
 * removed) and `destination` with the moved words added before or after its own.
 */
function moveEntities(
  move: Move,
  remaining: NarrationBlockV2 | null,
  destination: NarrationBlockV2,
  side: "append" | "prepend",
): Problem | null {
  const source = move.source;
  const order = <T>(own: T[], arriving: T[]): T[] => side === "append" ? [...own, ...arriving] : [...arriving, ...own];
  const annotations = divide(source.annotations, move, "A pronunciation or performance note");
  if (isProblem(annotations)) return annotations;
  const beats = divide(source.performanceBeats, move, "A performance beat");
  if (isProblem(beats)) return beats;
  const overlays = divide(source.overlayEvents, move, "An overlay");
  if (isProblem(overlays)) return overlays;
  if (remaining) {
    setList(remaining, "annotations", annotations.stay, source.annotations !== undefined);
    setList(remaining, "performanceBeats", beats.stay, source.performanceBeats !== undefined);
    remaining.overlayEvents = overlays.stay;
  }
  setList(destination, "annotations", order(destination.annotations ?? [], annotations.go), destination.annotations !== undefined);
  setList(destination, "performanceBeats", order(destination.performanceBeats ?? [], beats.go), destination.performanceBeats !== undefined);
  destination.overlayEvents = order(destination.overlayEvents, overlays.go);
  if (move.removed) {
    destination.notes = order(destination.notes, source.notes);
    // Visuals with no word to travel on are kept for Attach to words, never dropped.
    const wordless = source.tokens.every((token) => token.spoken === false) ? placedVisualsAsUnattachedV2(source) : [];
    setList(destination, "unattachedVisuals",
      order(destination.unattachedVisuals ?? [], [...(source.unattachedVisuals ?? []), ...wordless]),
      destination.unattachedVisuals !== undefined);
  }
  return null;
}

/**
 * Recalculate the rows' pictures from the stored rows, then stamp versions.
 * When no spoken word changes row, stored pictures are left exactly as they are.
 */
function recover(sources: NarrationBlockV2[], targets: NarrationBlockV2[], spokenWordsMoved: boolean): Problem | null {
  if (spokenWordsMoved) {
    const anySequence = sources.some((source) => source.primaryVisualSequence);
    for (const target of targets) {
      if (anySequence && !target.primaryVisualSequence) {
        target.primaryVisualSequence = { id: derivedCoverageIdV2(`${target.id}:primary_sequence`), slots: [], version: 0 };
      }
    }
    const covered = redistributeCoverageV2(sources, targets);
    if (isCoverageRefusalV2(covered)) {
      return problem(covered.code, covered.message, undefined, covered.entityId);
    }
    targets.forEach((target, index) => {
      const slots = covered[index];
      const sequence = target.primaryVisualSequence;
      if (!slots || !sequence) return;
      if (sameAuthoringJsonV2(slots, sequence.slots)) return;
      target.primaryVisualSequence = { id: sequence.id, slots, version: sequence.version + 1 };
    });
  }
  for (const target of targets) {
    const stored = sources.find((source) => source.id === target.id);
    if (!stored) {
      // A new row with no words of its own still shows its one On Camera card.
      if (!target.primaryVisualSequence && sources.some((source) => source.primaryVisualSequence)) {
        const sequenceId = derivedCoverageIdV2(`${target.id}:primary_sequence`);
        target.primaryVisualSequence = { id: sequenceId, slots: emptyRowCoverageV2(sequenceId), version: 1 };
      }
      continue;
    }
    if (sameAuthoringJsonV2(stored, target)) continue;
    preserveStashOriginAfterEditV2(stored, target);
    target.version = stored.version + 1;
  }
  return null;
}

/** The reference would have to point inside a row, which it cannot. */
const REFUSE = Symbol("refuse");
type Edge = string | typeof REFUSE;

interface EdgeChanges {
  /** References to the end of a row (outgoing transition, last music row, gap after it). */
  trailing: Map<string, Edge>;
  /** References to the start of a row (incoming transition, first music row, gap before it). */
  leading: Map<string, Edge>;
}

function follow(map: Map<string, Edge>, rowId: string | null | undefined): string | null | undefined | Problem {
  if (typeof rowId !== "string") return rowId;
  const next = map.get(rowId);
  if (next === undefined) return rowId;
  return next === REFUSE ? problem("ROW_REFERENCE_REVIEW_REQUIRED", "", rowId) : next;
}

/** Move row-level references so each still means the same place in the script. */
function retargetReferences(working: ScriptDocumentV2, edges: EdgeChanges, move: Move): Problem | null {
  const refuse = (message: string, entityId?: string): Problem => problem("ROW_REFERENCE_REVIEW_REQUIRED", message, move.source.id, entityId);

  for (const pair of working.rowTransitions ?? []) {
    const from = follow(edges.trailing, pair.fromRowId);
    const to = follow(edges.leading, pair.toRowId);
    if (isProblem(from) || isProblem(to)) return refuse("A transition sits between these two rows. Remove it before joining them.", pair.id);
    pair.fromRowId = from as string;
    pair.toRowId = to as string;
  }
  for (const span of working.rowAudioSpans ?? []) {
    const start = follow(edges.leading, span.startRowId);
    const end = follow(edges.trailing, span.endRowId);
    const previousEnd = span.review ? follow(edges.trailing, span.review.previousEndRowId) : undefined;
    if (isProblem(start) || isProblem(end) || isProblem(previousEnd)) {
      return refuse("A music cue starts or ends between these two rows. Move the cue's start or end before joining them.", span.id);
    }
    span.startRowId = start as string;
    span.endRowId = end as string;
    if (span.review) span.review.previousEndRowId = previousEnd as string;
  }
  for (const bundle of working.stash ?? []) {
    if (!bundle.originalGap) continue;
    const after = follow(edges.trailing, bundle.originalGap.afterRowId);
    const before = follow(edges.leading, bundle.originalGap.beforeRowId);
    if (isProblem(after) || isProblem(before)) {
      return refuse("Saved Stash rows remember the gap between these two rows as their place. Restore or delete them before joining.", bundle.id);
    }
    bundle.originalGap.afterRowId = after as string | null;
    bundle.originalGap.beforeRowId = before as string | null;
  }

  const gaps = (value: unknown): boolean => {
    if (!value || typeof value !== "object") return true;
    const item = value as Record<string, unknown>;
    if (!Array.isArray(value) && typeof item.afterBlockId === "string" && typeof item.beforeBlockId === "string") {
      const after = follow(edges.trailing, item.afterBlockId);
      const before = follow(edges.leading, item.beforeBlockId);
      if (isProblem(after) || isProblem(before)) return false;
      item.afterBlockId = after;
      item.beforeBlockId = before;
    }
    return Object.values(item).every(gaps);
  };
  for (const item of working.activeDraft.supportingItems) {
    if (!gaps(item.placement) || !gaps(item.displayAttachment)) {
      return refuse("A supporting item is placed between these two rows. Move it before joining them.", item.id);
    }
    const reason = retargetAnchors(item.placement, move) ?? retargetAnchors(item.displayAttachment, move);
    if (reason) return refuse(`A supporting item cannot follow its words. ${reason}`, item.id);
  }

  for (const reference of working.rowReferences ?? []) {
    if (reference.rowId !== move.source.id) continue;
    const named = [...tokenReferences(reference.anchor)];
    const moving = named.filter((tokenId) => move.movedTokenIds.has(tokenId)).length;
    if (moving > 0 && moving < named.length) {
      return refuse("A comment or reference is anchored to words that would end up in two rows. Shorten or remove it first.", reference.id);
    }
    if (named.length > 0 ? moving === 0 : !move.removed) continue;
    reference.rowId = move.destinationId;
    const inside = (value: unknown): void => {
      if (!value || typeof value !== "object") return;
      const item = value as Record<string, unknown>;
      for (const key of ["blockId", "rowId"]) if (item[key] === move.source.id) item[key] = move.destinationId;
      Object.values(item).forEach(inside);
    };
    inside(reference.anchor);
  }
  return null;
}

/** Music is row-granular: a join may not carry words into or out of a cue. */
function musicBoundary(working: ScriptDocumentV2, firstRowId: string, secondRowId: string): Problem | null {
  const rows = working.activeDraft.blocks.filter((block) => block.type !== "section").map((block) => block.id);
  for (const span of working.rowAudioSpans ?? []) {
    const start = rows.indexOf(span.startRowId);
    const end = rows.indexOf(span.endRowId);
    if (start < 0 || end < 0) continue;
    const covers = (rowId: string): boolean => {
      const at = rows.indexOf(rowId);
      return at >= Math.min(start, end) && at <= Math.max(start, end);
    };
    if (covers(firstRowId) !== covers(secondRowId)) {
      return problem("ROW_REFERENCE_REVIEW_REQUIRED", "A music cue starts or ends between these two rows, so joining them would move words into or out of the music. Move the cue's start or end first.", firstRowId, span.id);
    }
  }
  return null;
}

function newRow(source: NarrationBlockV2, id: string, piece: Piece): NarrationBlockV2 {
  return {
    type: "narration", id, orderKey: `${source.orderKey}/${id.slice(0, 8)}`,
    text: piece.text, tokens: piece.tokens, overlayEvents: [],
    timingPolicy: "narration_spine", state: source.state, notes: [], version: 1,
  };
}

function split(working: ScriptDocumentV2, command: SplitRowCommandV2): Problem | null {
  const blocks = working.activeDraft.blocks;
  const index = blocks.findIndex((block) => block.id === command.rowId);
  const stored = eligible(blocks[index], "split");
  if (isProblem(stored)) return stored;
  const everyRow = [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)];
  if (everyRow.some((block) => block.id === command.newRowId)) {
    return problem("ROW_ID_DUPLICATE", "A new row needs an unused row ID.", stored.id);
  }
  const count = stored.tokens.length;

  /** Token range [from, to) that goes to the new row, and whether that row sits above the original. */
  let from: number;
  let to: number;
  if ("beforeTokenId" in command.at) {
    const beforeTokenId = command.at.beforeTokenId;
    const cursor = beforeTokenId === null ? count : stored.tokens.findIndex((token) => token.id === beforeTokenId);
    if (cursor < 0) return problem("ROW_SELECTION_INVALID", "The cursor is not at a word in this row.", stored.id);
    from = snap(stored, cursor);
    to = count;
    if (from === 0 || from === count) {
      // A script row cannot be stored with no words yet (#580), so this is Add row, not a split.
      return problem("ROW_SPLIT_NO_WORDS", from === 0
        ? "There are no words before the cursor to leave in this row. Add a row above instead."
        : "There are no words after the cursor to move to a new row. Add a row below instead.", stored.id);
    }
  } else {
    const range = selected(stored, command.at);
    if (isProblem(range)) return range;
    if (range.from === 0 && range.to === count) {
      return problem("ROW_SPLIT_WHOLE_ROW", "The whole row is selected, so there is nothing to split off.", stored.id);
    }
    if (range.from !== 0 && range.to !== count) {
      return problem("ROW_SPLIT_MID_ROW", "Split needs a selection that includes the row's first or last word.", stored.id);
    }
    ({ from, to } = range);
  }
  const above = from === 0;

  const kept = structuredClone(stored);
  const made = newRow(stored, command.newRowId, above ? head(stored, to) : tail(stored, from));
  const remainder = above ? tail(stored, to) : head(stored, from);
  kept.text = remainder.text;
  kept.tokens = remainder.tokens;
  const move: Move = { source: stored, destinationId: made.id, movedTokenIds: new Set(made.tokens.map((token) => token.id)), removed: false };
  const entities = moveEntities(move, kept, made, "append");
  if (entities) return entities;
  const references = retargetReferences(working, above
    ? { trailing: new Map(), leading: new Map([[stored.id, made.id]]) }
    : { trailing: new Map([[stored.id, made.id]]), leading: new Map() }, move);
  if (references) return references;
  const spoken = made.tokens.some((token) => token.spoken !== false);
  const pictures = recover([stored], above ? [made, kept] : [kept, made], spoken);
  if (pictures) return pictures;
  blocks.splice(index, 1, ...(above ? [made, kept] : [kept, made]));
  return null;
}

function join(working: ScriptDocumentV2, command: JoinRowsCommandV2): Problem | null {
  const blocks = working.activeDraft.blocks;
  const index = blocks.findIndex((block) => block.id === command.rowId);
  const stored = eligible(blocks[index], "joined");
  if (isProblem(stored)) return stored;
  const previous = command.direction === "previous";
  const neighbourIndex = index + (previous ? -1 : 1);
  const neighbour = blocks[neighbourIndex];
  if (!neighbour) {
    return problem("ROW_JOIN_NO_NEIGHBOUR", previous ? "This is the first row, so there is no row above to join." : "This is the last row, so there is no row below to join.", stored.id);
  }
  if (neighbour.type === "section") {
    return problem("ROW_JOIN_SECTION_BREAK", "Rows cannot be joined across a section break.", stored.id);
  }
  const target = eligible(neighbour, "joined");
  if (isProblem(target)) return target;
  if (target.state !== stored.state) {
    return problem("ROW_SPLIT_JOIN_UNSUPPORTED", "An excluded row cannot be joined to an active one.", stored.id);
  }

  const count = stored.tokens.length;
  let from = 0;
  let to = count;
  if (command.words) {
    const range = selected(stored, command.words);
    if (isProblem(range)) return range;
    ({ from, to } = range);
    if (previous ? from !== 0 : to !== count) {
      return problem("ROW_JOIN_MID_ROW", previous
        ? "Join to the row above needs a selection that includes this row's first word."
        : "Join to the row below needs a selection that includes this row's last word.", stored.id);
    }
  }
  const removed = from === 0 && to === count;
  const music = musicBoundary(working, stored.id, target.id);
  if (music) return music;

  const moving = previous ? head(stored, to) : tail(stored, from);
  const own: Piece = { text: target.text, tokens: target.tokens.map((token) => ({ ...token })) };
  const paragraph = command.words === null;
  const merged = previous ? concat(own, moving, paragraph) : concat(moving, own, paragraph);
  const grown = structuredClone(target);
  grown.text = merged.text;
  grown.tokens = merged.tokens;
  let remaining: NarrationBlockV2 | null = null;
  if (!removed) {
    const remainder = previous ? tail(stored, to) : head(stored, from);
    remaining = structuredClone(stored);
    remaining.text = remainder.text;
    remaining.tokens = remainder.tokens;
  }
  const move: Move = { source: stored, destinationId: target.id, movedTokenIds: new Set(moving.tokens.map((token) => token.id)), removed };
  const entities = moveEntities(move, remaining, grown, previous ? "append" : "prepend");
  if (entities) return entities;
  const edges: EdgeChanges = !removed
    ? { trailing: new Map(), leading: new Map() }
    : previous
      ? { trailing: new Map([[stored.id, target.id]]), leading: new Map([[stored.id, REFUSE]]) }
      : { trailing: new Map([[stored.id, REFUSE]]), leading: new Map([[stored.id, target.id]]) };
  const references = retargetReferences(working, edges, move);
  if (references) return references;

  const targets = previous ? [grown, ...(remaining ? [remaining] : [])] : [...(remaining ? [remaining] : []), grown];
  const spoken = moving.tokens.some((token) => token.spoken !== false);
  const pictures = recover(previous ? [target, stored] : [stored, target], targets, spoken);
  if (pictures) return pictures;
  const first = Math.min(index, neighbourIndex);
  blocks.splice(first, 2, ...targets);
  return null;
}

/** Apply one split or join to a working copy. A returned problem means the copy must be discarded. */
export function applySplitOrJoinV2(working: ScriptDocumentV2, command: SplitRowCommandV2 | JoinRowsCommandV2): AuthoringDiagnosticV2 | null {
  return command.kind === "split_row" ? split(working, command) : join(working, command);
}
