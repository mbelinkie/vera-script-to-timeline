import { createHash } from "node:crypto";
import type {
  ContentSlot,
  NarrationBlockV2,
  ReturnSlot,
  UnattachedVisualV2,
  WordInpointAnchor,
} from "./generated/contracts-v2.js";
import { wordCoverageOffsetV2 } from "./authoring-v2-validation.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

/**
 * On Camera coverage (S03 D193). On Camera is not something the writer places:
 * it fills every spoken word that no visual covers, and its only authored
 * choice is Wide or Tight framing per passage.
 *
 * Storage stays the existing slot list so old documents load and the compiler
 * is unchanged. This module reads a row's slots as a layout of placed visuals
 * with word ranges, applies a range change to that layout, and writes the
 * whole sequence back in one canonical shape:
 *
 * - every spoken word is covered by exactly one visible slot;
 * - adjacent On Camera coverage is one slot with one framing;
 * - a return exists only where its parent really resumes with words.
 *
 * Slots that an edit does not affect keep their ID, boundary anchor, relation
 * and version, so rebuilding an already canonical row is byte-stable.
 */

export type OnCameraFramingV2 = "wide" | "tight";

type Slot = ContentSlot | ReturnSlot;
type OnCameraPayload = Extract<ContentSlot["payload"], { kind: "on_camera" }>;

export interface CoverageRefusalV2 {
  code: string;
  message: string;
  entityId?: string;
}

export interface CoverageEditOutcomeV2 {
  slots: Slot[];
  /** Deliberately placed visuals that lost every word; kept for Attach to words. */
  unattached: UnattachedVisualV2[];
  changedSlotIds: string[];
  payloadIds: string[];
}

interface PlacedVisual {
  slot: ContentSlot;
  /** Whole word range in spoken-token offsets, including nested cutaways. */
  start: number;
  end: number;
  /** A non-camera visual this one cuts away from and returns to. */
  parentId: string | null;
  /** Stored as a cutaway over On Camera; kept when the new sequence still allows it. */
  cameraCutaway: boolean;
}

interface Passage {
  /** The writer chose this shot (explicit framing or a recorded take); it wins over a passage that only filled a gap. */
  authored: boolean;
  slot: ContentSlot;
  start: number;
  end: number;
  framing: OnCameraFramingV2;
  presenterChoiceId: string | null;
}

interface RowLayout {
  wordCount: number;
  visuals: PlacedVisual[];
  passages: Passage[];
}

type Segment =
  | { kind: "camera"; start: number; end: number; framing: OnCameraFramingV2; presenterChoiceId: string | null; identity: Passage | null }
  | { kind: "visual"; visual: PlacedVisual; start: number; end: number };

export function onCameraFramingV2(payload: ContentSlot["payload"]): OnCameraFramingV2 | null {
  return payload.kind === "on_camera" ? payload.framing ?? "wide" : null;
}

export function isCoverageRefusalV2(value: unknown): value is CoverageRefusalV2 {
  return typeof value === "object" && value !== null && !Array.isArray(value) && "code" in value && "message" in value;
}

/**
 * Give one placed visual the whole selection (D113, D145, D192). The visual
 * before it ends where the selection begins, one that starts inside it starts
 * on the next word, and one left with no words becomes unattached. On Camera
 * fills every word nothing covers. Refusals name the reason and change nothing.
 */
export function setVisualRangeV2(
  row: NarrationBlockV2,
  slotId: string,
  startTokenId: string,
  endTokenId: string,
): CoverageEditOutcomeV2 | CoverageRefusalV2 {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return refusal("PRIMARY_SEQUENCE_MISSING", "The row has no primary visual sequence.");
  const target = sequence.slots.find((slot) => slot.id === slotId);
  if (!target || target.kind !== "content") {
    return refusal("RANGE_SLOT_MISSING", "Choose a visual that is placed on words in this row.", slotId);
  }
  if (target.payload.kind === "on_camera") {
    return refusal("ON_CAMERA_RANGE_DERIVED", "On Camera fills the words no visual covers, so it has no range to set. Change a visual's range instead.", slotId);
  }
  const tokens = spokenTokensV2(row);
  const first = tokens.findIndex((token) => token.id === startTokenId);
  const last = tokens.findIndex((token) => token.id === endTokenId);
  if (first < 0 || last < 0) {
    return refusal("RANGE_OUTSIDE_ROW", "The selection falls outside this row's spoken words.", slotId);
  }
  if (last < first) return refusal("RANGE_REVERSED", "The selection's last word comes before its first word.", slotId);
  const layout = readLayout(row);
  if (isCoverageRefusalV2(layout)) return layout;
  const moved = moveRange(layout, slotId, first, last + 1);
  if (isCoverageRefusalV2(moved)) return moved;
  const slots = buildSlots(row, layout, moved.visuals);
  if (isCoverageRefusalV2(slots)) return slots;
  const unattached = moved.unattached.flatMap((visual): UnattachedVisualV2[] =>
    visual.slot.payload.kind === "visual"
      ? [{ slotId: visual.slot.id, payload: visual.slot.payload, version: 1 }]
      : []);
  if (unattached.length === 0 && sameAuthoringJsonV2(slots, sequence.slots)) {
    return refusal("RANGE_UNCHANGED", "The selection is already this visual's range.", slotId);
  }
  return outcome(sequence.slots, slots, moved.unattached, unattached);
}

/**
 * Attach a visual that has no words yet to the whole selection (D87, D113).
 * It is the same make-room rule as a range change: `moveRange` decides what
 * the neighbouring visuals keep. A selection that sits wholly inside one
 * visual, or inside one On Camera passage, becomes a cutaway that returns to
 * it after the selection (D94).
 */
export function attachVisualV2(
  row: NarrationBlockV2,
  slotId: string,
  startTokenId: string,
  endTokenId: string,
): CoverageEditOutcomeV2 | CoverageRefusalV2 {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return refusal("PRIMARY_SEQUENCE_MISSING", "The row has no primary visual sequence.");
  const waiting = (row.unattachedVisuals ?? []).find((item) => item.slotId === slotId);
  if (!waiting) {
    return refusal("ATTACH_VISUAL_MISSING", "Choose a visual in this row that is waiting for Attach to words.", slotId);
  }
  const tokens = spokenTokensV2(row);
  const first = tokens.findIndex((token) => token.id === startTokenId);
  const last = tokens.findIndex((token) => token.id === endTokenId);
  if (first < 0 || last < 0) {
    return refusal("RANGE_OUTSIDE_ROW", "The selection falls outside this row's spoken words.", slotId);
  }
  if (last < first) return refusal("RANGE_REVERSED", "The selection's last word comes before its first word.", slotId);
  const layout = readLayout(row);
  if (isCoverageRefusalV2(layout)) return layout;
  const start = first;
  const end = last + 1;
  const slot: ContentSlot = {
    id: waiting.slotId, kind: "content", relation: { kind: "sequential" }, boundaryBefore: { kind: "row_start" },
    payload: waiting.payload, playoutPolicy: "match_structural_interval", version: waiting.version,
  };
  const container = layout.visuals.find((visual) => !visual.parentId && visual.start < start && end < visual.end);
  const insidePassage = layout.passages.some((passage) => passage.start < start && end < passage.end);
  let displaced: PlacedVisual[] = [];
  const place = (parentId: string | null): Slot[] | CoverageRefusalV2 => {
    const arriving: PlacedVisual = { slot, start: -1, end: -1, parentId, cameraCutaway: insidePassage };
    const moved = moveRange({ ...layout, visuals: [...layout.visuals, arriving] }, slotId, start, end);
    if (isCoverageRefusalV2(moved)) return moved;
    displaced = moved.unattached;
    return buildSlots(row, layout, moved.visuals);
  };
  let slots = container ? place(container.slot.id) : place(null);
  // Where a cutaway cannot be stored (the parent's other cutaways are elsewhere), the visual before simply ends at the selection.
  if (container && isCoverageRefusalV2(slots)) slots = place(null);
  if (isCoverageRefusalV2(slots)) return slots;
  const unattached = displaced.flatMap((visual): UnattachedVisualV2[] =>
    visual.slot.payload.kind === "visual"
      ? [{ slotId: visual.slot.id, payload: visual.slot.payload, version: 1 }]
      : []);
  return outcome(sequence.slots, slots, displaced, unattached);
}

/**
 * Take one placed visual off its words (move to another row, Stash, Delete).
 * On Camera fills the words it leaves (D193); a cutaway inside it stands on
 * its own. A row with no spoken words goes back to its single On Camera card.
 */
export function removeVisualV2(row: NarrationBlockV2, slotId: string): CoverageEditOutcomeV2 | CoverageRefusalV2 {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return refusal("PRIMARY_SEQUENCE_MISSING", "The row has no primary visual sequence.");
  const target = sequence.slots.find((slot) => slot.id === slotId);
  if (!target || target.kind !== "content" || target.payload.kind === "on_camera") {
    return refusal("VISUAL_SLOT_MISSING", "Choose a visual that is placed in this row.", slotId);
  }
  const gone: PlacedVisual = { slot: target, start: 0, end: 0, parentId: null, cameraCutaway: false };
  if (spokenTokensV2(row).length === 0) {
    if (sequence.slots.length !== 1) {
      return unresolved("This row has no spoken words but holds more than one picture, which this edit cannot recalculate.", slotId);
    }
    return outcome(sequence.slots, emptyRowCoverageV2(sequence.id), [gone], []);
  }
  const layout = readLayout(row);
  if (isCoverageRefusalV2(layout)) return layout;
  const visuals = layout.visuals
    .filter((visual) => visual.slot.id !== slotId)
    .map((visual) => ({ ...visual, parentId: visual.parentId === slotId ? null : visual.parentId }));
  const slots = buildSlots(row, layout, visuals);
  if (isCoverageRefusalV2(slots)) return slots;
  return outcome(sequence.slots, slots, [gone], []);
}

/** Set Wide or Tight for one On Camera passage; the choice covers the passage's return too. */
export function setOnCameraFramingV2(
  row: NarrationBlockV2,
  slotId: string,
  framing: OnCameraFramingV2,
): CoverageEditOutcomeV2 | CoverageRefusalV2 {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return refusal("PRIMARY_SEQUENCE_MISSING", "The row has no primary visual sequence.");
  const target = sequence.slots.find((slot) => slot.id === slotId);
  if (!target || target.kind !== "content" || target.payload.kind !== "on_camera") {
    return refusal("FRAMING_SLOT_MISSING", "Wide or Tight applies to an On Camera passage in this row.", slotId);
  }
  if (onCameraFramingV2(target.payload) === framing) {
    return refusal("FRAMING_UNCHANGED", `This On Camera passage is already ${framing === "wide" ? "Wide" : "Tight"}.`, slotId);
  }
  const reframed = sequence.slots.map((slot): Slot => slot.id !== slotId || slot.kind !== "content" || slot.payload.kind !== "on_camera"
    ? slot
    : { ...slot, payload: { kind: "on_camera", presenterChoiceId: slot.payload.presenterChoiceId, framing }, version: slot.version + 1 });
  const slots = normalizeSlots({ ...row, primaryVisualSequence: { ...sequence, slots: reframed } }) ?? reframed;
  return outcome(sequence.slots, slots, [], []);
}

/**
 * Rebuild a row's stored sequence in canonical shape without changing any
 * visual's range. Returns null when the row is already canonical, or when its
 * structure is unresolved (media-timed cuts, a return with no word, stale
 * anchors) and so cannot be recalculated.
 */
export function normalizeCoverageV2(row: NarrationBlockV2): Slot[] | null {
  return normalizeSlots(row);
}

/** A stable identity derived from existing ones, so replaying an edit writes the same document. */
export function derivedCoverageIdV2(seed: string): string {
  const hex = createHash("sha256").update(seed, "utf8").digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-${"89ab"[Number.parseInt(hex[16]!, 16) % 4]!}${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/** A row with no spoken words shows one On Camera card. */
export function emptyRowCoverageV2(sequenceId: string): ContentSlot[] {
  return [{
    id: derivedCoverageIdV2(`${sequenceId}:on_camera:empty`), kind: "content", relation: { kind: "base" },
    boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
    playoutPolicy: "match_structural_interval", version: 1,
  }];
}

/** The deliberately placed visuals of a row, in the shape kept for Attach to words. */
export function placedVisualsAsUnattachedV2(row: NarrationBlockV2): UnattachedVisualV2[] {
  return (row.primaryVisualSequence?.slots ?? []).flatMap((slot): UnattachedVisualV2[] =>
    slot.kind === "content" && slot.payload.kind === "visual" ? [{ slotId: slot.id, payload: slot.payload, version: 1 }] : []);
}

export interface NarrationCoverageReconciliationV2 {
  slots: Slot[];
  unattachedVisuals: UnattachedVisualV2[];
}

/**
 * Rebuild the picture sequence after an *already identity-mapped* text splice.
 * A visual follows its original first token, never the next word or an equal
 * phrase elsewhere. A lost start becomes a waiting visual with its original
 * media payload. readLayout/buildSlots remain the single range/On Camera engine.
 */
export function reconcileNarrationTextCoverageV2(
  before: NarrationBlockV2,
  after: NarrationBlockV2,
  reshapedTokenIds: ReadonlyMap<string, readonly string[]>,
): NarrationCoverageReconciliationV2 | CoverageRefusalV2 {
  const sequence = before.primaryVisualSequence;
  if (!sequence || !after.primaryVisualSequence || after.primaryVisualSequence.id !== sequence.id) {
    return refusal("PRIMARY_SEQUENCE_MISSING", "Text edits require the row's existing picture sequence.");
  }
  const oldWords = spokenTokensV2(before);
  const newWords = spokenTokensV2(after);
  const position = new Map(newWords.map((token, index) => [token.id, index]));
  const firstPosition = (id: string) => position.get(reshapedTokenIds.get(id)?.[0] ?? id);
  const lastPosition = (id: string) => position.get(reshapedTokenIds.get(id)?.at(-1) ?? id);
  const waiting = [...(before.unattachedVisuals ?? [])];

  // Changes entirely inside stage directions leave all spoken cues intact.
  if (after.text !== "" && oldWords.length === newWords.length &&
      oldWords.every((word, index) => word.id === newWords[index]!.id && word.value === newWords[index]!.value)) {
    return { slots: sequence.slots, unattachedVisuals: waiting };
  }

  if (newWords.length === 0) {
    // D135/D146: a single picture stays in the sequence. The row edit handles
    // clearing multiple pictures with the ordered visuals-only representation.
    const pictures = sequence.slots.filter((slot): slot is ContentSlot =>
      slot.kind === "content" && slot.payload.kind === "visual");
    if (pictures.length > 1 || waiting.length > 0) {
      return unresolved("Review the pictures before clearing all spoken words in this row.");
    }
    const picture = pictures[0] ?? sequence.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.payload.kind === "on_camera");
    if (!picture) return unresolved("The empty row has no picture to keep.");
    const single: ContentSlot = {
      ...picture, relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      playoutPolicy: "match_structural_interval",
    };
    if (picture.playoutPolicy !== "match_structural_interval") {
      return unresolved("A media-timed picture cannot be changed to wordless playout without losing its timing.", picture.id);
    }
    if (!sameAuthoringJsonV2(single, picture)) single.version += 1;
    return { slots: [single], unattachedVisuals: [] };
  }

  if (oldWords.length === 0) {
    if (sequence.slots.length !== 1 || waiting.length > 0 || sequence.slots[0]?.kind !== "content") {
      return unresolved("This wordless picture sequence cannot be given new narration without reviewing the pictures.");
    }
    const only = sequence.slots[0];
    return { slots: [only], unattachedVisuals: [] };
  }

  const source = readLayout(before);
  if (isCoverageRefusalV2(source)) return source;

  const lost = new Set<string>();
  const visuals: PlacedVisual[] = [];
  const claimedStarts = new Set<number>();
  // A surviving visual's last word and the start of the next passage both
  // constrain its range; the existing layout supplies the actual boundaries.
  const boundaries = [...source.visuals.map((visual) => visual.start),
    ...source.passages.map((passage) => passage.start)].sort((a, b) => a - b);
  for (const visual of source.visuals) {
    const start = firstPosition(oldWords[visual.start]!.id);
    // A join can collapse two starts onto one word. Keep the earlier card
    // placed and retain the other card, with its own identity, for reattachment.
    if (start === undefined || claimedStarts.has(start)) {
      if (visual.slot.payload.kind !== "visual") return unresolved("A non-media visual lost its start word.", visual.slot.id);
      lost.add(visual.slot.id);
      waiting.push({ slotId: visual.slot.id, payload: visual.slot.payload, version: visual.slot.version });
      continue;
    }
    claimedStarts.add(start);
    // Include new words introduced inside the old interval. If a following
    // boundary's original token survives, stop exactly at that token.
    const following = boundaries.find((boundary) => boundary >= visual.end);
    const nextBoundary = following === undefined ? undefined : firstPosition(oldWords[following]?.id ?? "");
    const last = oldWords.slice(visual.start, visual.end).reduce<number | undefined>((latest, token) => {
      const at = lastPosition(token.id);
      return at === undefined ? latest : Math.max(latest ?? at, at);
    }, undefined);
    const end = nextBoundary !== undefined
      ? Math.max(start + 1, nextBoundary) : following === undefined ? newWords.length : last === undefined ? start + 1 : last + 1;
    if (end <= start) return unresolved("A surviving picture would have no words left.", visual.slot.id);
    visuals.push({ ...visual, start, end });
  }

  if (visuals.some((visual) => visual.parentId && lost.has(visual.parentId))) {
    return unresolved("A cutaway's parent lost its cue word; preserve the cutaway by revising the edit.");
  }
  // A return cannot be silently rebound to a different spoken word.
  for (const slot of sequence.slots) {
    if (slot.kind === "return" && slot.inpoint && firstPosition(slot.inpoint.tokenId) === undefined) {
      return unresolved("The word where a cutaway returns was deleted.", slot.id);
    }
  }

  const passages: Passage[] = source.passages.flatMap((passage) => {
    const starts = oldWords.slice(passage.start, passage.end)
      .flatMap((token) => [firstPosition(token.id), lastPosition(token.id)]).filter((index): index is number => index !== undefined);
    return starts.length ? [{ ...passage, start: Math.min(...starts), end: Math.max(...starts) + 1 }] : [];
  });
  const slots = buildSlots(after, { wordCount: newWords.length, visuals, passages }, visuals);
  if (isCoverageRefusalV2(slots)) return slots;
  // A reflow that silently changes a cutaway's return cue is not a safe
  // splice, even when the original cue token still happens to exist.
  for (const prior of sequence.slots) {
    if (prior.kind !== "return") continue;
    const rebuilt = slots.find((slot) => slot.id === prior.id);
    const expected = prior.inpoint ? newWords[firstPosition(prior.inpoint.tokenId) ?? -1]?.id : undefined;
    if (rebuilt?.kind !== "return" || rebuilt.inpoint?.tokenId !== expected) {
      return unresolved("The cutaway's return cue cannot be preserved exactly through this edit.", prior.id);
    }
  }
  return { slots, unattachedVisuals: waiting };
}

/**
 * Recalculate coverage after words move between rows (split and join, S03 D97).
 *
 * `sources` are the rows as stored before the edit. `targets` are the rows the
 * edit leaves, with their final ID, text and tokens and a primary sequence
 * whose ID is the one to write. Every spoken token keeps its ID, so each word
 * is found in exactly one target.
 *
 * A visual travels with its first word and keeps the words that stay next to
 * it; where its words part company it is clipped, so no visual ends up in two
 * rows. On Camera then fills every word nothing covers, by the same rule as a
 * range change (D193): a passage keeps its Wide or Tight choice in both rows,
 * and keeps its stored identity in the row its first word goes to.
 *
 * Returns the slots to store for each target, or null where a target's stored
 * slots must stay exactly as they are.
 */
export function redistributeCoverageV2(
  sources: NarrationBlockV2[],
  targets: NarrationBlockV2[],
): (Slot[] | null)[] | CoverageRefusalV2 {
  if (!sources.some((source) => source.primaryVisualSequence)) return targets.map(() => null);
  const where = new Map<string, { target: number; offset: number }>();
  targets.forEach((target, index) => spokenTokensV2(target).forEach((token, offset) => where.set(token.id, { target: index, offset })));
  const layouts = targets.map((): { visuals: PlacedVisual[]; passages: Passage[] } => ({ visuals: [], passages: [] }));
  const prior: Slot[] = [];
  const identityHolder = new Map<string, number>();

  for (const source of sources) {
    if (!source.primaryVisualSequence) continue;
    prior.push(...source.primaryVisualSequence.slots);
    const tokens = spokenTokensV2(source);
    if (tokens.length === 0) continue;
    const layout = readLayout(source);
    if (isCoverageRefusalV2(layout)) return layout;
    /** The leading words of [start, end) that stay together, as a range in their new row. */
    const place = (start: number, end: number): { target: number; start: number; count: number } | null => {
      const head = where.get(tokens[start]!.id);
      if (!head) return null;
      let count = 1;
      while (start + count < end) {
        const next = where.get(tokens[start + count]!.id);
        if (!next || next.target !== head.target || next.offset !== head.offset + count) break;
        count += 1;
      }
      return { target: head.target, start: head.offset, count };
    };
    const lost = (): CoverageRefusalV2 => refusal("RANGE_OUTSIDE_ROW", "A word that carries a visual would no longer be in any row.");
    const rowOf = new Map<string, number>();
    const moved: { visual: PlacedVisual; target: number }[] = [];
    for (const visual of layout.visuals) {
      const placed = place(visual.start, visual.end);
      if (!placed) return lost();
      rowOf.set(visual.slot.id, placed.target);
      moved.push({ target: placed.target, visual: { ...visual, start: placed.start, end: placed.start + placed.count } });
    }
    for (const { visual, target } of moved) {
      // A cutaway whose parent went to the other row stands on its own.
      if (visual.parentId && rowOf.get(visual.parentId) !== target) visual.parentId = null;
      layouts[target]!.visuals.push(visual);
    }
    for (const passage of layout.passages) {
      for (let cursor = passage.start; cursor < passage.end;) {
        const placed = place(cursor, passage.end);
        if (!placed) return lost();
        const holder = identityHolder.get(passage.slot.id);
        if (holder === undefined) identityHolder.set(passage.slot.id, placed.target);
        const sequenceId = targets[placed.target]!.primaryVisualSequence?.id ?? targets[placed.target]!.id;
        const slot = holder === undefined || holder === placed.target
          ? passage.slot
          : { ...passage.slot, id: derivedCoverageIdV2(`${sequenceId}:carried:${passage.slot.id}`) };
        layouts[placed.target]!.passages.push({ ...passage, slot, start: placed.start, end: placed.start + placed.count });
        cursor += placed.count;
      }
    }
  }

  const result: (Slot[] | null)[] = [];
  for (const [index, target] of targets.entries()) {
    const sequence = target.primaryVisualSequence;
    if (!sequence) return refusal("PRIMARY_SEQUENCE_MISSING", "The row has no primary visual sequence.", target.id);
    const wordCount = spokenTokensV2(target).length;
    if (wordCount === 0) {
      const stored = sources.find((source) => source.id === target.id);
      // A row that had no spoken words before the edit keeps its stored pictures untouched.
      if (stored?.primaryVisualSequence && spokenTokensV2(stored).length === 0) {
        result.push(null);
        continue;
      }
      result.push(emptyRowCoverageV2(sequence.id));
      continue;
    }
    const layout = layouts[index]!;
    const slots = buildSlots(
      { ...target, primaryVisualSequence: { ...sequence, slots: prior } },
      { wordCount, visuals: layout.visuals, passages: layout.passages },
      layout.visuals,
    );
    if (isCoverageRefusalV2(slots)) return slots;
    result.push(slots);
  }
  return result;
}

function normalizeSlots(row: NarrationBlockV2): Slot[] | null {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return null;
  const layout = readLayout(row);
  if (isCoverageRefusalV2(layout)) return null;
  const slots = buildSlots(row, layout, layout.visuals.map((visual) => ({ ...visual })));
  if (isCoverageRefusalV2(slots) || sameAuthoringJsonV2(slots, sequence.slots)) return null;
  return slots;
}

function outcome(
  before: Slot[],
  after: Slot[],
  removed: PlacedVisual[],
  unattached: UnattachedVisualV2[],
): CoverageEditOutcomeV2 {
  const priorById = new Map(before.map((slot) => [slot.id, slot]));
  const nextIds = new Set(after.map((slot) => slot.id));
  const changedSlotIds = [
    ...after.filter((slot) => !sameAuthoringJsonV2(priorById.get(slot.id), slot)).map((slot) => slot.id),
    ...before.filter((slot) => !nextIds.has(slot.id)).map((slot) => slot.id),
  ];
  const payloadIds = new Set<string>();
  for (const id of changedSlotIds) {
    const slot = after.find((candidate) => candidate.id === id) ?? priorById.get(id);
    if (slot?.kind === "content" && slot.payload.kind !== "on_camera") payloadIds.add(slot.payload.payloadId);
  }
  for (const visual of removed) {
    if (visual.slot.payload.kind !== "on_camera") payloadIds.add(visual.slot.payload.payloadId);
  }
  return { slots: after, unattached, changedSlotIds: [...new Set(changedSlotIds)], payloadIds: [...payloadIds] };
}

function refusal(code: string, message: string, entityId?: string): CoverageRefusalV2 {
  return { code, message, ...(entityId ? { entityId } : {}) };
}

function unresolved(message: string, entityId?: string): CoverageRefusalV2 {
  return refusal("RANGE_SEQUENCE_UNRESOLVED", message, entityId);
}

function slotStart(slot: ContentSlot, row: NarrationBlockV2): number | null {
  if (slot.boundaryBefore.kind === "row_start") return 0;
  return slot.boundaryBefore.kind === "spoken_word" || slot.boundaryBefore.kind === "audible_word_end"
    ? wordCoverageOffsetV2(slot.boundaryBefore.anchor, row)
    : null;
}

/** Read stored slots as placed visuals with word ranges plus the On Camera passages between them. */
function readLayout(row: NarrationBlockV2): RowLayout | CoverageRefusalV2 {
  const slots = row.primaryVisualSequence?.slots ?? [];
  const wordCount = spokenTokensV2(row).length;
  if (slots.length === 0 || wordCount === 0) return unresolved("The row has no spoken words or no picture sequence to recalculate.");
  const groups: { root: ContentSlot; start: number; children: { slot: ContentSlot; start: number }[]; returnAt: number | null }[] = [];
  let cursor = 0;
  while (cursor < slots.length) {
    const root = slots[cursor]!;
    if (root.kind !== "content" || root.relation.kind === "cutaway") {
      return unresolved("A cutaway or return has no visual before it to return to.", root.id);
    }
    if (root.playoutPolicy !== "match_structural_interval") {
      return unresolved("A clip that plays to its own end has no exact word range. Give its next cut an exact word first.", root.id);
    }
    const start = cursor === 0 ? (root.boundaryBefore.kind === "row_start" ? 0 : null) : slotStart(root, row);
    if (start === null) return unresolved("A visual's first word is missing or out of date.", root.id);
    cursor += 1;
    const children: { slot: ContentSlot; start: number }[] = [];
    while (cursor < slots.length) {
      const child = slots[cursor]!;
      if (child.kind !== "content" || child.relation.kind !== "cutaway") break;
      if (child.relation.parentSlotId !== root.id) return unresolved("A cutaway names a visual it does not sit inside.", child.id);
      if (child.payload.kind === "on_camera") {
        return unresolved("On Camera is stored here as a cutaway inside another visual, which this edit cannot recalculate.", child.id);
      }
      const childStart = slotStart(child, row);
      if (childStart === null) return unresolved("A cutaway's first word is missing or out of date.", child.id);
      children.push({ slot: child, start: childStart });
      cursor += 1;
    }
    let returnAt: number | null = null;
    const possibleReturn = slots[cursor];
    if (children.length > 0) {
      if (!possibleReturn || possibleReturn.kind !== "return" || possibleReturn.parentSlotId !== root.id || !possibleReturn.inpoint) {
        return unresolved("A cutaway has no word chosen for its return yet.", root.id);
      }
      returnAt = wordCoverageOffsetV2(possibleReturn.inpoint, row);
      if (returnAt === null) return unresolved("A return's word is missing or out of date.", possibleReturn.id);
      cursor += 1;
    } else if (possibleReturn?.kind === "return") {
      return unresolved("A return has no cutaway before it.", possibleReturn.id);
    }
    groups.push({ root, start, children, returnAt });
  }

  const visuals: PlacedVisual[] = [];
  const passages: Passage[] = [];
  for (const [index, group] of groups.entries()) {
    const end = groups[index + 1]?.start ?? wordCount;
    const marks = [group.start, ...group.children.map((child) => child.start), ...(group.returnAt === null ? [] : [group.returnAt])];
    const ordered = marks.every((mark, markIndex) => markIndex === 0 || mark > marks[markIndex - 1]!);
    if (!ordered || marks.at(-1)! > end || group.start >= end || (group.returnAt === null && marks.at(-1)! >= end)) {
      return unresolved("Two cuts in this row land on the same word or are out of order.", group.root.id);
    }
    const resumes = group.returnAt !== null && group.returnAt < end;
    const childEnd = (childIndex: number): number => group.children[childIndex + 1]?.start ?? group.returnAt ?? end;
    const payload = group.root.payload;
    if (payload.kind === "on_camera") {
      const shot = {
        slot: group.root,
        framing: onCameraFramingV2(payload)!,
        presenterChoiceId: payload.presenterChoiceId,
        authored: payload.framing !== undefined || payload.presenterChoiceId !== null,
      };
      passages.push({ ...shot, start: group.start, end: group.children[0]?.start ?? end });
      group.children.forEach((child, childIndex) => visuals.push({
        slot: child.slot, start: child.start, end: childEnd(childIndex), parentId: null, cameraCutaway: true,
      }));
      if (resumes) passages.push({ ...shot, start: group.returnAt!, end });
      continue;
    }
    visuals.push({
      slot: group.root,
      start: group.start,
      end: group.children.length > 0 && !resumes ? group.children[0]!.start : end,
      parentId: null,
      cameraCutaway: false,
    });
    group.children.forEach((child, childIndex) => visuals.push({
      slot: child.slot, start: child.start, end: childEnd(childIndex), parentId: resumes ? group.root.id : null, cameraCutaway: false,
    }));
  }
  return { wordCount, visuals, passages };
}

/** Apply the make-room rule for one visual's new range [start, end). */
function moveRange(
  layout: RowLayout,
  slotId: string,
  start: number,
  end: number,
): { visuals: PlacedVisual[]; unattached: PlacedVisual[] } | CoverageRefusalV2 {
  const visuals = layout.visuals.map((visual) => ({ ...visual }));
  const target = visuals.find((visual) => visual.slot.id === slotId);
  if (!target) return refusal("RANGE_SLOT_MISSING", "Choose a visual that is placed on words in this row.", slotId);
  if (target.start === start && target.end === end) {
    return refusal("RANGE_UNCHANGED", "The selection is already this visual's range.", slotId);
  }
  const parent = target.parentId ? visuals.find((visual) => visual.slot.id === target.parentId) : undefined;
  // A cutaway stays a cutaway only while its parent still shows on both sides of it.
  const keepsParent = parent !== undefined && parent.start < start && end < parent.end;
  target.start = start;
  target.end = end;
  if (!keepsParent) target.parentId = null;

  const unattached: PlacedVisual[] = [];
  const kept: PlacedVisual[] = [];
  for (const visual of visuals) {
    if (visual === target || (keepsParent && visual === parent)) {
      kept.push(visual);
      continue;
    }
    if (visual.parentId === target.slot.id) {
      // The edited visual's own cutaways stay while they still sit inside it.
      if (start < visual.start && visual.end < end) {
        kept.push(visual);
        continue;
      }
      visual.parentId = null;
    }
    if (visual.end <= start || visual.start >= end) {
      kept.push(visual);
    } else if (visual.start < start) {
      visual.end = start;
      kept.push(visual);
    } else if (visual.end > end) {
      visual.start = end;
      kept.push(visual);
    } else {
      unattached.push(visual);
    }
  }
  return { visuals: kept, unattached };
}

/**
 * A cutaway needs its parent on both sides. Where a parent no longer shows
 * before or after a cutaway, the parent simply ends or starts there and the
 * cutaway stands on its own.
 */
function settleNesting(visuals: PlacedVisual[]): CoverageRefusalV2 | null {
  const byId = new Map(visuals.map((visual) => [visual.slot.id, visual]));
  for (let changed = true; changed;) {
    changed = false;
    for (const visual of [...visuals].sort((left, right) => left.start - right.start)) {
      if (!visual.parentId) continue;
      const parent = byId.get(visual.parentId);
      if (parent && parent.start < visual.start && visual.end < parent.end) continue;
      if (parent && visual.end > parent.start && visual.start < parent.end) {
        if (visual.start <= parent.start) parent.start = Math.max(parent.start, visual.end);
        else parent.end = Math.min(parent.end, visual.start);
        if (parent.start >= parent.end) {
          return refusal("RANGE_PARENT_EMPTY", "This range would leave the visual it cuts away from with no words.", parent.slot.id);
        }
      }
      visual.parentId = null;
      changed = true;
    }
  }
  return null;
}

/** Write the whole sequence for a layout: roots tile the row, On Camera fills the gaps. */
function buildSlots(row: NarrationBlockV2, layout: RowLayout, visuals: PlacedVisual[]): Slot[] | CoverageRefusalV2 {
  const sequence = row.primaryVisualSequence!;
  const tokens = spokenTokensV2(row);
  const settled = settleNesting(visuals);
  if (settled) return settled;

  const top = visuals.filter((visual) => !visual.parentId).sort((left, right) => left.start - right.start);
  const childrenOf = new Map<string, PlacedVisual[]>();
  for (const visual of visuals) {
    if (visual.start < 0 || visual.start >= visual.end || visual.end > layout.wordCount) {
      return refusal("RANGE_OUTSIDE_ROW", "The selection falls outside this row's spoken words.", visual.slot.id);
    }
    if (!visual.parentId) continue;
    if (!top.some((candidate) => candidate.slot.id === visual.parentId)) {
      return refusal("RANGE_NESTING_UNSUPPORTED", "A cutaway cannot sit inside another cutaway.", visual.slot.id);
    }
    childrenOf.set(visual.parentId, [...(childrenOf.get(visual.parentId) ?? []), visual]);
  }
  for (const [index, visual] of top.entries()) {
    const next = top[index + 1];
    if (next && visual.end > next.start) {
      return refusal("RANGE_OVERLAP_UNRESOLVED", "Two visuals would cover the same words.", next.slot.id);
    }
  }
  for (const [parentId, children] of childrenOf) {
    children.sort((left, right) => left.start - right.start);
    if (children.some((child, index) => index > 0 && child.start !== children[index - 1]!.end)) {
      return refusal(
        "RANGE_RETURN_ORPHANED",
        "This range would make a visual resume more than once in the row, leaving a return with nothing before it. Move the cutaways so they stay next to each other, or shorten the visual they sit inside.",
        parentId,
      );
    }
  }

  const segments: Segment[] = [];
  const addCamera = (start: number, end: number): void => {
    if (start >= end) return;
    const identity = layout.passages
      .filter((passage) => passage.start < end && passage.end > start)
      .sort((left, right) => Number(right.authored) - Number(left.authored) || left.start - right.start)[0] ?? null;
    segments.push({
      kind: "camera", start, end, identity,
      framing: identity?.framing ?? "wide",
      presenterChoiceId: identity?.presenterChoiceId ?? null,
    });
  };
  let covered = 0;
  for (const visual of top) {
    addCamera(covered, visual.start);
    segments.push({ kind: "visual", visual, start: visual.start, end: visual.end });
    covered = visual.end;
  }
  addCamera(covered, layout.wordCount);
  // Freed words return to the shot already used in this row: the nearest earlier passage, else the next one.
  const cameras = segments.filter((segment): segment is Extract<Segment, { kind: "camera" }> => segment.kind === "camera");
  for (const [index, camera] of cameras.entries()) {
    if (camera.identity) continue;
    const source = cameras.slice(0, index).reverse().find((candidate) => candidate.identity) ??
      cameras.slice(index + 1).find((candidate) => candidate.identity);
    if (source) camera.framing = source.framing;
  }

  const priorById = new Map(sequence.slots.map((slot) => [slot.id, slot]));
  const priorReturnByParent = new Map(
    sequence.slots.flatMap((slot): [string, ReturnSlot][] => slot.kind === "return" ? [[slot.parentSlotId, slot]] : []),
  );
  const taken = new Set<string>([
    sequence.id,
    ...row.tokens.map((token) => token.id),
    ...sequence.slots.flatMap((slot) => slot.kind === "content" && slot.payload.kind !== "on_camera" ? [slot.id, slot.payload.payloadId] : [slot.id]),
    ...(row.unattachedVisuals ?? []).flatMap((item) => [item.slotId, item.payload.payloadId]),
  ]);
  const used = new Set<string>();
  const derive = (seed: string): string => {
    for (let attempt = 0; ; attempt += 1) {
      const hex = createHash("sha256").update(`${sequence.id}:${seed}:${attempt}`, "utf8").digest("hex");
      const id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-${"89ab"[Number.parseInt(hex[16]!, 16) % 4]!}${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
      if (!taken.has(id)) {
        taken.add(id);
        return id;
      }
    }
  };
  const wordAnchor = (offset: number, priorVersion: number): WordInpointAnchor => {
    const token = tokens[offset]!;
    return { blockId: row.id, tokenId: token.id, affinity: "before", quotedWord: token.value, anchorVersion: priorVersion + 1 };
  };
  const out: Slot[] = [];
  const emitContent = (
    id: string,
    start: number,
    relation: ContentSlot["relation"],
    payload: ContentSlot["payload"],
  ): void => {
    const prior = priorById.get(id);
    const priorContent = prior?.kind === "content" ? prior : undefined;
    const priorBoundary = priorContent?.boundaryBefore;
    const priorAnchorVersion = priorBoundary && "anchor" in priorBoundary ? priorBoundary.anchor.anchorVersion : 0;
    const boundaryBefore: ContentSlot["boundaryBefore"] = relation.kind === "base"
      ? { kind: "row_start" }
      : priorContent && priorBoundary && priorBoundary.kind !== "row_start" && slotStart(priorContent, row) === start
        ? priorBoundary
        : { kind: "spoken_word", anchor: wordAnchor(start, priorAnchorVersion) };
    const slot: ContentSlot = {
      id,
      kind: "content",
      relation,
      boundaryBefore,
      payload,
      playoutPolicy: "match_structural_interval",
      version: priorContent?.version ?? 1,
    };
    if (priorContent && !sameAuthoringJsonV2(priorContent, slot)) slot.version = priorContent.version + 1;
    out.push(priorContent && slot.version === priorContent.version ? priorContent : slot);
  };
  const emitReturn = (parentSlotId: string, at: number): void => {
    const prior = priorReturnByParent.get(parentSlotId);
    const reusable = prior && !used.has(prior.id) ? prior : undefined;
    const id = reusable?.id ?? derive(`return:${parentSlotId}`);
    used.add(id);
    const inpoint = reusable?.inpoint && wordCoverageOffsetV2(reusable.inpoint, row) === at
      ? reusable.inpoint
      : wordAnchor(at, reusable?.inpoint?.anchorVersion ?? 0);
    const slot: ReturnSlot = { id, kind: "return", parentSlotId, inpoint, version: reusable?.version ?? 1 };
    if (reusable && !sameAuthoringJsonV2(reusable, slot)) slot.version = reusable.version + 1;
    out.push(reusable && slot.version === reusable.version ? reusable : slot);
  };
  const rootRelation = (): ContentSlot["relation"] => out.length === 0 ? { kind: "base" } : { kind: "sequential" };

  for (let index = 0; index < segments.length;) {
    const segment = segments[index]!;
    if (segment.kind === "visual") {
      const visual = segment.visual;
      emitContent(visual.slot.id, visual.start, rootRelation(), visual.slot.payload);
      const children = childrenOf.get(visual.slot.id) ?? [];
      for (const child of children) {
        emitContent(child.slot.id, child.start, { kind: "cutaway", parentSlotId: visual.slot.id }, child.slot.payload);
      }
      if (children.length > 0) emitReturn(visual.slot.id, children.at(-1)!.end);
      index += 1;
      continue;
    }
    // A run of cutaways stays over On Camera only when the same shot really resumes after it.
    let closing = index + 1;
    while (closing < segments.length) {
      const candidate = segments[closing]!;
      if (candidate.kind !== "visual" || !candidate.visual.cameraCutaway || childrenOf.has(candidate.visual.slot.id)) break;
      closing += 1;
    }
    const resumed = segments[closing];
    const returns = closing > index + 1 && resumed?.kind === "camera" &&
      resumed.framing === segment.framing && resumed.presenterChoiceId === segment.presenterChoiceId;
    const identityId = segment.identity?.slot.id;
    const id = identityId && !used.has(identityId)
      ? identityId
      : derive(`on_camera:${tokens[segment.start]!.id}`);
    used.add(id);
    const priorPayload = segment.identity?.slot.payload as OnCameraPayload | undefined;
    const payload: OnCameraPayload = {
      kind: "on_camera",
      presenterChoiceId: segment.presenterChoiceId,
      ...(segment.framing !== "wide" || priorPayload?.framing !== undefined ? { framing: segment.framing } : {}),
    };
    emitContent(id, segment.start, rootRelation(), payload);
    if (!returns) {
      index += 1;
      continue;
    }
    for (const cutaway of segments.slice(index + 1, closing)) {
      if (cutaway.kind !== "visual") continue;
      emitContent(cutaway.visual.slot.id, cutaway.start, { kind: "cutaway", parentSlotId: id }, cutaway.visual.slot.payload);
    }
    emitReturn(id, resumed.start);
    index = closing + 1;
  }
  return out;
}
