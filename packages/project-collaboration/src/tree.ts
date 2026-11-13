import * as Y from "yjs";

/**
 * Mapping between the saved script JSON and the shared Yjs document.
 *
 * - Anything with an ID (a row, a supporting item, an Idea) is one entry in a
 *   Yjs map keyed by that ID. Moving it changes one position value; it can
 *   never be duplicated or dropped by a merge of two moves.
 * - Fields of such an entity merge one by one (last writer wins per field).
 * - Prose (`text`, a section `title`) is shared text and merges per character.
 * - Narration word tokens are never stored: they are computed from the shared
 *   text, so they always agree with it. A word keeps its ID for as long as its
 *   first character survives.
 *
 * Materializing is a pure function of the Yjs state, so every client and the
 * server compute exactly the same JSON from the same state.
 *
 * This module has no Node dependency; the browser editor (#73) can use it.
 */

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type JsonObject = { [key: string]: Json };

export type Shape =
  | { readonly kind: "map"; readonly fields: ShapeFields }
  | { readonly kind: "list"; readonly element: ShapeFields }
  | { readonly kind: "text" }
  | { readonly kind: "tokens" };
export type ShapeFields = Readonly<Record<string, Shape>>;

const ENTITY: ShapeFields = {};
const ROW: ShapeFields = {
  text: { kind: "text" },
  title: { kind: "text" },
  tokens: { kind: "tokens" },
  overlayEvents: { kind: "list", element: ENTITY },
};
const list = (element: ShapeFields): Shape => ({ kind: "list", element });

/** One project = one shared document holding the script (Draft and Extras) and Ideas. */
export const ROOT_SHAPE: ShapeFields = {
  document: {
    kind: "map",
    fields: {
      activeDraft: { kind: "map", fields: { blocks: list(ROW), supportingItems: list(ENTITY) } },
      // Extras currently live in the Stash fields of the script document.
      stash: list(ENTITY),
      stashSections: list(ENTITY),
      stashGroups: list(ENTITY),
      rowTransitions: list(ENTITY),
      rowAudioSpans: list(ENTITY),
      rowReferences: list(ENTITY),
    },
  },
  ideas: { kind: "map", fields: { items: list({ text: { kind: "text" } }) } },
};

export const ROOT_KEY = "vera";
const POSITION = "\u0000pos";
const TOKEN_SEEDS = "\u0000seed";
const TOKEN_PIN = "\u0000pin";
const hidden = (key: string): boolean => key.startsWith("\u0000");

type YMap = Y.Map<unknown>;

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function clone<T extends Json>(value: T): T {
  return structuredClone(value);
}

/** Deep equality that ignores object key order. */
export function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length &&
      left.every((item, index) => sameJson(item, right[index]));
  }
  if (!isObject(left) || !isObject(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length &&
    keys.every((key) => Object.hasOwn(right, key) && sameJson(left[key], right[key]));
}

/** An array can be a keyed list only when every element is an object with its own unique ID. */
function keyable(value: unknown): value is JsonObject[] {
  if (!Array.isArray(value)) return false;
  const seen = new Set<string>();
  for (const item of value) {
    if (!isObject(item) || typeof item.id !== "string" || !item.id || seen.has(item.id)) return false;
    seen.add(item.id);
  }
  return true;
}

// ---- positions -------------------------------------------------------------

const DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
const digit = (value: string | undefined): number => value === undefined ? 0 : Math.max(0, DIGITS.indexOf(value));

/** A key strictly between `low` and `high` (null = no upper bound). Keys never end in "0". */
export function positionBetween(low: string, high: string | null): string {
  let out = "";
  let upper = high;
  for (let index = 0; ; index += 1) {
    const a = digit(low[index]);
    const b = upper !== null && index < upper.length ? digit(upper[index]) : DIGITS.length;
    if (b - a > 1) return out + DIGITS[a + ((b - a) >> 1)]!;
    out += DIGITS[a]!;
    if (b - a === 1) upper = null;
  }
}

/** Evenly spread starting keys, so later inserts between neighbours stay short. */
function initialPositions(count: number): string[] {
  let width = 1;
  while (DIGITS.length ** width <= count + 1) width += 1;
  const step = Math.floor(DIGITS.length ** width / (count + 1));
  return Array.from({ length: count }, (_, index) => {
    let value = (index + 1) * step;
    let key = "";
    for (let place = 0; place < width; place += 1) {
      key = DIGITS[value % DIGITS.length]! + key;
      value = Math.floor(value / DIGITS.length);
    }
    return key.replace(/0+$/u, "");
  });
}

function positionOf(element: unknown): string | undefined {
  const value = element instanceof Y.Map ? (element as YMap).get(POSITION) : undefined;
  return typeof value === "string" ? value : undefined;
}

function orderedEntries(listMap: YMap): [string, YMap][] {
  const entries: [string, YMap, string][] = [];
  listMap.forEach((value, key) => {
    if (value instanceof Y.Map) entries.push([key, value as YMap, positionOf(value) ?? ""]);
  });
  entries.sort((a, b) => a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
  return entries.map(([key, value]) => [key, value]);
}

// ---- narration tokens ------------------------------------------------------

/** Deterministic 128-bit mix, formatted as a UUID. Identity only; not a security boundary. */
function derivedUuid(name: string): string {
  let h1 = 1779033703, h2 = 3144134277, h3 = 1013904242, h4 = 2773480762;
  for (let index = 0; index < name.length; index += 1) {
    const code = name.charCodeAt(index);
    h1 = h2 ^ Math.imul(h1 ^ code, 597399067);
    h2 = h3 ^ Math.imul(h2 ^ code, 2869860233);
    h3 = h4 ^ Math.imul(h3 ^ code, 951274213);
    h4 = h1 ^ Math.imul(h4 ^ code, 2716044179);
  }
  h1 = Math.imul(h3 ^ (h1 >>> 18), 597399067);
  h2 = Math.imul(h4 ^ (h2 >>> 22), 2869860233);
  h3 = Math.imul(h1 ^ (h3 >>> 17), 951274213);
  h4 = Math.imul(h2 ^ (h4 >>> 19), 2716044179);
  const hex = [h1 ^ h2 ^ h3 ^ h4, h2 ^ h1, h3 ^ h1, h4 ^ h1]
    .map((part) => (part >>> 0).toString(16).padStart(8, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/** The Yjs identity of the character at `index`: stable for as long as that character exists. */
export function characterKey(text: Y.Text, index: number): string | null {
  const item = Y.createRelativePositionFromTypeIndex(text, index).item;
  return item ? `${item.client}:${item.clock}` : null;
}

interface Token { id: string; value: string; startOffset: number; endOffset: number; spoken?: false }

/**
 * Words are runs of characters that are neither whitespace nor square
 * brackets. Words inside one tight `[...]` pair are a nonspoken direction. In
 * a whole-row plain direction every bracket is literal and nothing is spoken.
 */
function deriveTokens(row: YMap, text: Y.Text): Token[] {
  const content = text.toJSON();
  const plain = row.get("plainDirection") === true;
  const seeds = row.get(TOKEN_SEEDS);
  const tokens: Token[] = [];
  for (const match of content.matchAll(plain ? /\S+/gu : /[^\s[\]]+/gu)) {
    const key = characterKey(text, match.index);
    const seeded = key !== null && seeds instanceof Y.Map ? (seeds as YMap).get(key) : undefined;
    tokens.push({
      id: typeof seeded === "string" ? seeded : derivedUuid(`vera-token:${key ?? match.index}`),
      value: match[0],
      startOffset: match.index,
      endOffset: match.index + match[0].length,
      ...(plain ? { spoken: false as const } : {}),
    });
  }
  if (plain) return tokens;
  let index = 0;
  while (index < tokens.length) {
    const first = tokens[index]!;
    if (content[first.startOffset - 1] !== "[" || content[first.startOffset - 2] === "[") { index += 1; continue; }
    let last = index;
    while (last + 1 < tokens.length &&
        !/[[\]]/u.test(content.slice(tokens[last]!.endOffset, tokens[last + 1]!.startOffset))) last += 1;
    const close = tokens[last]!.endOffset;
    if (content[close] === "]" && content[close + 1] !== "]") {
      for (let inside = index; inside <= last; inside += 1) tokens[inside]!.spoken = false;
    }
    index = last + 1;
  }
  return tokens;
}

function consistentTokens(text: string, tokens: unknown): tokens is Token[] {
  if (!Array.isArray(tokens)) return false;
  let previousEnd = 0;
  for (const token of tokens as unknown[]) {
    if (!isObject(token) || typeof token.id !== "string" ||
        typeof token.startOffset !== "number" || typeof token.endOffset !== "number" ||
        token.startOffset < previousEnd || token.endOffset <= token.startOffset ||
        text.slice(token.startOffset, token.endOffset) !== token.value) return false;
    previousEnd = token.endOffset;
  }
  return true;
}

/**
 * Keep the IDs (and, when our word rule would disagree, the exact tokens) that
 * a saved script supplied. Tokens that do not match their text are ignored and
 * recomputed, so an edit that only changed `text` needs no token bookkeeping.
 */
function adoptTokens(row: YMap, after: JsonObject): void {
  const text = row.get("text");
  if (!(text instanceof Y.Text)) {
    if (after.tokens !== undefined) row.set("tokens", clone(after.tokens));
    return;
  }
  if (row.has("tokens")) row.delete("tokens");
  let seeds = row.get(TOKEN_SEEDS) as YMap | undefined;
  if (!(seeds instanceof Y.Map)) {
    seeds = new Y.Map();
    row.set(TOKEN_SEEDS, seeds);
  }
  const content = text.toJSON();
  const supplied = after.tokens;
  if (typeof after.text !== "string" || after.text !== content || !consistentTokens(content, supplied)) {
    if (row.has(TOKEN_PIN)) row.delete(TOKEN_PIN);
    return;
  }
  if (!sameJson(deriveTokens(row, text), supplied)) {
    for (const token of supplied) {
      const key = characterKey(text, token.startOffset);
      if (key !== null && seeds.get(key) !== token.id) seeds.set(key, token.id);
    }
  }
  if (sameJson(deriveTokens(row, text), supplied)) {
    if (row.has(TOKEN_PIN)) row.delete(TOKEN_PIN);
  } else {
    row.set(TOKEN_PIN, { text: content, tokens: clone(supplied as unknown as Json) });
  }
}

// ---- JSON -> Yjs -----------------------------------------------------------

function writeValue(parent: YMap, key: string, value: Json, shape: Shape | undefined): void {
  if (shape?.kind === "text" && typeof value === "string") {
    const text = new Y.Text();
    parent.set(key, text);
    if (value) text.insert(0, value);
  } else if (shape?.kind === "list" && keyable(value)) {
    const listMap: YMap = new Y.Map();
    parent.set(key, listMap);
    const positions = initialPositions(value.length);
    value.forEach((element, index) => { writeElement(listMap, element, positions[index]!, shape.element); });
  } else if (shape?.kind === "map" && isObject(value)) {
    const map: YMap = new Y.Map();
    parent.set(key, map);
    writeFields(map, value, shape.fields);
  } else {
    parent.set(key, clone(value));
  }
}

function writeFields(map: YMap, value: JsonObject, fields: ShapeFields): void {
  for (const [key, item] of Object.entries(value)) {
    if (!hidden(key) && fields[key]?.kind !== "tokens") writeValue(map, key, item, fields[key]);
  }
  if (fields.tokens && Object.hasOwn(value, "tokens")) adoptTokens(map, value);
}

function writeElement(listMap: YMap, value: JsonObject, position: string, fields: ShapeFields): void {
  const element: YMap = new Y.Map();
  listMap.set(value.id as string, element);
  element.set(POSITION, position);
  writeFields(element, value, fields);
}

/** Fill an empty shared document from saved JSON. Call inside a transaction. */
export function seedRoot(doc: Y.Doc, value: JsonObject): void {
  writeFields(doc.getMap(ROOT_KEY), value, ROOT_SHAPE);
}

// ---- Yjs -> JSON -----------------------------------------------------------

function readValue(value: unknown, shape: Shape | undefined): Json {
  if (value instanceof Y.Text) return value.toJSON();
  if (value instanceof Y.Map) {
    const map = value as YMap;
    if (shape?.kind === "list") {
      return orderedEntries(map).map(([id, element]) => ({ ...readFields(element, shape.element), id }));
    }
    return readFields(map, shape?.kind === "map" ? shape.fields : {});
  }
  return clone(value as Json);
}

function readFields(map: YMap, fields: ShapeFields): JsonObject {
  const out: JsonObject = {};
  for (const key of [...map.keys()].sort()) {
    if (!hidden(key)) out[key] = readValue(map.get(key), fields[key]);
  }
  const text = map.get("text");
  if (fields.tokens && text instanceof Y.Text && map.get(TOKEN_SEEDS) instanceof Y.Map) {
    const pin = map.get(TOKEN_PIN);
    out.tokens = isObject(pin) && pin.text === out.text && pin.tokens !== undefined
      ? clone(pin.tokens)
      : deriveTokens(map, text) as unknown as Json;
  }
  return out;
}

/** The whole shared document as plain JSON: `{ document, ideas }`. */
export function readRoot(doc: Y.Doc): JsonObject {
  return readFields(doc.getMap(ROOT_KEY), ROOT_SHAPE);
}

// ---- applying a JSON change to Yjs ------------------------------------------

function isSurrogatePair(text: string, index: number): boolean {
  const before = text.charCodeAt(index - 1);
  const after = text.charCodeAt(index);
  return before >= 0xd800 && before <= 0xdbff && after >= 0xdc00 && after <= 0xdfff;
}

type TextEdit = { at: number; remove: number; insert: string };

/**
 * The character edits that turn `before` into `after`, last first. Typing in
 * two places gives two small edits rather than one big replacement, so other
 * people's concurrent typing in between is left alone.
 */
function textEdits(before: string, after: string): TextEdit[] {
  let prefix = 0;
  const limit = Math.min(before.length, after.length);
  while (prefix < limit && before[prefix] === after[prefix]) prefix += 1;
  if (prefix > 0 && (isSurrogatePair(before, prefix) || isSurrogatePair(after, prefix))) prefix -= 1;
  let suffix = 0;
  while (suffix < limit - prefix &&
      before[before.length - 1 - suffix] === after[after.length - 1 - suffix]) suffix += 1;
  if (suffix > 0 && (isSurrogatePair(before, before.length - suffix) ||
      isSurrogatePair(after, after.length - suffix))) suffix -= 1;
  const a = Array.from(before.slice(prefix, before.length - suffix));
  const b = Array.from(after.slice(prefix, after.length - suffix));
  if (!a.length && !b.length) return [];
  const whole: TextEdit[] = [{ at: prefix, remove: a.join("").length, insert: b.join("") }];
  if (!a.length || !b.length || a.length * b.length > 4_000_000) return whole;
  // Longest common subsequence over code points (never splits a surrogate pair).
  const width = b.length + 1;
  const table = new Uint32Array((a.length + 1) * width);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i * width + j] = a[i] === b[j]
        ? table[(i + 1) * width + j + 1]! + 1
        : Math.max(table[(i + 1) * width + j]!, table[i * width + j + 1]!);
    }
  }
  const edits: TextEdit[] = [];
  let i = 0, j = 0, at = prefix;
  let open: TextEdit | undefined;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      open = undefined;
      at += a[i]!.length;
      i += 1; j += 1;
      continue;
    }
    if (!open) edits.push(open = { at, remove: 0, insert: "" });
    if (j < b.length && (i === a.length || table[i * width + j + 1]! >= table[(i + 1) * width + j]!)) {
      open.insert += b[j]!;
      j += 1;
    } else {
      open.remove += a[i]!.length;
      at += a[i]!.length;
      i += 1;
    }
  }
  return edits.reverse();
}

/**
 * Apply the edits that turn `before` into `after`. If the live text has moved
 * on from `before` (a save made against an older copy), the new characters
 * are still inserted, but text that is no longer where it was is left alone:
 * nothing typed is ever removed on a guess.
 */
function spliceText(text: Y.Text, before: string, after: string): void {
  const live = text.toJSON();
  for (const edit of textEdits(before, after)) {
    let at = edit.at;
    let remove = edit.remove;
    const removed = before.slice(edit.at, edit.at + edit.remove);
    if (live !== before && live.slice(at, at + remove) !== removed) {
      // Not where it was: add the new text, remove nothing.
      at = Math.min(at, live.length);
      remove = 0;
    }
    if (remove) text.delete(at, remove);
    if (edit.insert) text.insert(at, edit.insert);
  }
}

function applyFields(map: YMap, before: JsonObject, after: JsonObject, fields: ShapeFields): void {
  let touched = false;
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (hidden(key) || sameJson(before[key], after[key])) continue;
    touched = true;
    const shape = fields[key];
    if (shape?.kind === "tokens") continue;
    const next = after[key];
    const previous = before[key];
    const current = map.get(key);
    if (next === undefined) {
      map.delete(key);
    } else if (shape?.kind === "text" && typeof next === "string" && typeof previous === "string" &&
        current instanceof Y.Text) {
      spliceText(current, previous, next);
    } else if (shape?.kind === "list" && keyable(next) && keyable(previous) && current instanceof Y.Map) {
      applyList(current as YMap, previous, next, shape.element);
    } else if (shape?.kind === "map" && isObject(next) && isObject(previous) && current instanceof Y.Map) {
      applyFields(current as YMap, previous, next, shape.fields);
    } else {
      writeValue(map, key, next, shape);
    }
  }
  if (touched && fields.tokens && Object.hasOwn(after, "tokens")) {
    // Changing the text without touching the tokens is not token authorship:
    // the stale tokens are dropped and recomputed from the new text.
    if (sameJson(before.text, after.text) || !sameJson(before.tokens, after.tokens)) adoptTokens(map, after);
    else if (map.has(TOKEN_PIN)) map.delete(TOKEN_PIN);
  }
}

function applyList(listMap: YMap, before: JsonObject[], after: JsonObject[], fields: ShapeFields): void {
  const beforeById = new Map(before.map((item) => [item.id as string, item]));
  const afterIds = new Set(after.map((item) => item.id as string));
  for (const id of beforeById.keys()) if (!afterIds.has(id)) listMap.delete(id);

  const beforeOrder = before.map((item) => item.id as string).filter((id) => afterIds.has(id));
  const afterOrder = after.map((item) => item.id as string).filter((id) => beforeById.has(id));
  const reordered = beforeOrder.some((id, index) => id !== afterOrder[index]);

  // Where each target element sits today; new or re-created elements have no position.
  const positions = after.map((item) => {
    const id = item.id as string;
    return beforeById.has(id) ? positionOf(listMap.get(id)) : undefined;
  });
  // Without a reorder, existing elements keep their place; only new ones are slotted in.
  const keep = reordered ? longestIncreasing(positions) : new Set(positions.map((_, index) => index));
  let low = "";
  after.forEach((item, index) => {
    const id = item.id as string;
    const previous = beforeById.get(id);
    const existing = listMap.get(id);
    const held = positions[index];
    let position: string;
    if (held !== undefined && keep.has(index) && held > low) {
      position = held;
    } else {
      let high: string | null = null;
      for (let later = index + 1; later < after.length && high === null; later += 1) {
        const candidate = positions[later];
        if (candidate !== undefined && keep.has(later) && candidate > low) high = candidate;
      }
      position = positionBetween(low, high);
    }
    low = position;
    if (previous && existing instanceof Y.Map) {
      if (position !== held) (existing as YMap).set(POSITION, position);
      applyFields(existing as YMap, previous, item, fields);
    } else if (!previous || !sameJson(previous, item)) {
      // Unknown here, or removed live while the writer changed it: (re)create as written.
      writeElement(listMap, item, position, fields);
    }
  });
}

/** Indexes of a longest strictly increasing run of the defined positions. */
function longestIncreasing(positions: (string | undefined)[]): Set<number> {
  const tails: number[] = [];
  const previous = new Array<number>(positions.length).fill(-1);
  positions.forEach((position, index) => {
    if (position === undefined) return;
    let lowIndex = 0;
    let highIndex = tails.length;
    while (lowIndex < highIndex) {
      const middle = (lowIndex + highIndex) >> 1;
      if (positions[tails[middle]!]! < position) lowIndex = middle + 1;
      else highIndex = middle;
    }
    if (lowIndex > 0) previous[index] = tails[lowIndex - 1]!;
    tails[lowIndex] = index;
  });
  const keep = new Set<number>();
  for (let index = tails.at(-1) ?? -1; index >= 0; index = previous[index]!) keep.add(index);
  return keep;
}

/**
 * Apply the difference between two JSON snapshots to the shared document.
 * Only what changed between `before` and `after` is touched, so anything other
 * people changed in the meantime is kept. Call inside a transaction.
 */
export function applyRootChange(doc: Y.Doc, before: JsonObject, after: JsonObject): void {
  applyFields(doc.getMap(ROOT_KEY), before, after, ROOT_SHAPE);
}
