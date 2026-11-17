import type { ContentSlot, NarratedVisualPayloadV2, NarrationBlockV2 } from "./generated/contracts-v2.js";
import {
  attachVisualV2,
  derivedCoverageIdV2,
  isCoverageRefusalV2,
  removeVisualV2,
  type CoverageRefusalV2,
} from "./authoring-v2-coverage.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { retypeVisualPayloadV2 } from "./authoring-v2-visual-type.js";
import type { DroppedVisualDetailV2, VisualTypeChangeV2 } from "./authoring-v2.js";

/**
 * The life of one visual card after it exists (S03 §4, #578): move it to
 * another row, attach it to words, change its type, delete it, or lift it out
 * for Stash. Every function here edits the rows it is given in place and
 * either completes or returns a refusal having changed nothing; the callers
 * work on a private copy of the document and make the edit one Undo entry.
 *
 * A visual is found either on words (a content slot in the row's sequence) or
 * waiting for Attach to words (`unattachedVisuals`). On Camera is neither: it
 * is what fills the words no visual covers (D193), so it cannot be moved,
 * stashed, deleted or retyped.
 */

export interface VisualLifecycleOutcomeV2 {
  slotIds: string[];
  payloadIds: string[];
  dropped?: DroppedVisualDetailV2[];
}

export type VisualLifecycleResultV2 = VisualLifecycleOutcomeV2 | CoverageRefusalV2;

function refusal(code: string, message: string, entityId?: string): CoverageRefusalV2 {
  return { code, message, ...(entityId ? { entityId } : {}) };
}

function placedSlot(row: NarrationBlockV2, slotId: string): ContentSlot | undefined {
  return row.primaryVisualSequence?.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.id === slotId);
}

function dropWaiting(row: NarrationBlockV2, slotId: string): void {
  const rest = (row.unattachedVisuals ?? []).filter((item) => item.slotId !== slotId);
  if (rest.length > 0) row.unattachedVisuals = rest;
  else delete row.unattachedVisuals;
}

function bump(row: NarrationBlockV2): void {
  if (row.primaryVisualSequence) row.primaryVisualSequence.version += 1;
}

/** Take a placed visual off its words and store the recalculated row. */
function unplace(row: NarrationBlockV2, slotId: string): { slotIds: string[]; payloadIds: string[] } | CoverageRefusalV2 {
  const removed = removeVisualV2(row, slotId);
  if (isCoverageRefusalV2(removed)) return removed;
  row.primaryVisualSequence!.slots = removed.slots;
  bump(row);
  return { slotIds: removed.changedSlotIds, payloadIds: removed.payloadIds };
}

/**
 * Lift one visual out of its row, keeping its source and trim, for a move to
 * another row or to Stash. On Camera fills the words it leaves.
 */
export function liftVisualV2(
  row: NarrationBlockV2,
  slotId: string,
  purpose: "moved" | "stashed",
): { payload: NarratedVisualPayloadV2; slotIds: string[]; payloadIds: string[] } | CoverageRefusalV2 {
  const waiting = (row.unattachedVisuals ?? []).find((item) => item.slotId === slotId);
  if (waiting) {
    dropWaiting(row, slotId);
    bump(row);
    return { payload: waiting.payload, slotIds: [slotId], payloadIds: [waiting.payload.payloadId] };
  }
  const slot = placedSlot(row, slotId);
  if (!slot) return refusal("VISUAL_SLOT_MISSING", "Choose a visual that is in this row.", slotId);
  if (slot.payload.kind === "on_camera") {
    return refusal("ON_CAMERA_NOT_A_VISUAL", `On Camera fills the words no visual covers, so it cannot be ${purpose}. Move or stash a visual instead.`, slotId);
  }
  if (slot.payload.kind === "undefined") {
    return refusal("VISUAL_UNDEFINED_EMPTY", `Visual Undefined has no picture yet, so there is nothing to be ${purpose}. Choose a type for it first.`, slotId);
  }
  const payload = slot.payload;
  const unplaced = unplace(row, slotId);
  if (isCoverageRefusalV2(unplaced)) return unplaced;
  return { payload, ...unplaced };
}

/** Drag a card to another row (D87, D88, D146). */
export function moveVisualToRowV2(
  source: NarrationBlockV2,
  destination: NarrationBlockV2,
  slotId: string,
): VisualLifecycleResultV2 {
  if (source.id === destination.id) {
    return refusal("CROSS_ROW_REQUIRED", "This visual is already in that row. Use Attach to words or Set range to place it on different words.", slotId);
  }
  const wordless = spokenTokensV2(destination).length === 0;
  const destinationSequence = destination.primaryVisualSequence;
  const only = destinationSequence?.slots.length === 1 ? destinationSequence.slots[0] : undefined;
  if (wordless) {
    // A row with no narration has no words to wait for: the visual is simply that row's picture (D146).
    if (!destinationSequence) {
      return refusal("PRIMARY_SEQUENCE_MISSING", "The row you are moving to has no picture sequence to hold a visual.", destination.id);
    }
    const free = only?.kind === "content" &&
      (only.payload.kind === "undefined" || only.payload.kind === "on_camera" && only.payload.presenterChoiceId === null);
    if (!free) {
      return refusal("WORDLESS_ROW_VISUAL_TAKEN", "That row has no narration and already holds a picture. A row without words holds one picture for now; move or delete it first.", destination.id);
    }
  }
  const lifted = liftVisualV2(source, slotId, "moved");
  if (isCoverageRefusalV2(lifted)) return lifted;
  const slotIds = [...lifted.slotIds];
  if (wordless) {
    slotIds.push(only!.id, slotId);
    destinationSequence!.slots = [{
      id: slotId, kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: lifted.payload, playoutPolicy: "match_structural_interval", version: 1,
    }];
  } else {
    destination.unattachedVisuals = [...(destination.unattachedVisuals ?? []), { slotId, payload: lifted.payload, version: 1 }];
  }
  bump(destination);
  return { slotIds: [...new Set(slotIds)], payloadIds: lifted.payloadIds };
}

/** Attach to words (D113): the waiting visual takes the whole selection and its neighbours make room. */
export function attachVisualToWordsV2(
  row: NarrationBlockV2,
  slotId: string,
  startTokenId: string,
  endTokenId: string,
): VisualLifecycleResultV2 {
  const attached = attachVisualV2(row, slotId, startTokenId, endTokenId);
  if (isCoverageRefusalV2(attached)) return attached;
  row.primaryVisualSequence!.slots = attached.slots;
  dropWaiting(row, slotId);
  if (attached.unattached.length > 0) row.unattachedVisuals = [...(row.unattachedVisuals ?? []), ...attached.unattached];
  bump(row);
  return { slotIds: attached.changedSlotIds, payloadIds: attached.payloadIds };
}

/** Delete (D100): On Camera fills the words; the row's last visual leaves Visual Undefined on them instead. */
export function deleteVisualV2(row: NarrationBlockV2, slotId: string): VisualLifecycleResultV2 {
  const waiting = (row.unattachedVisuals ?? []).find((item) => item.slotId === slotId);
  if (waiting) {
    dropWaiting(row, slotId);
    bump(row);
    return { slotIds: [slotId], payloadIds: [waiting.payload.payloadId] };
  }
  const sequence = row.primaryVisualSequence;
  const slot = placedSlot(row, slotId);
  if (!sequence || !slot) return refusal("VISUAL_SLOT_MISSING", "Choose a visual that is in this row.", slotId);
  if (slot.payload.kind === "on_camera") {
    return refusal("ON_CAMERA_NOT_A_VISUAL", "On Camera fills the words no visual covers, so it cannot be deleted. Put a visual on those words instead.", slotId);
  }
  const others = sequence.slots.some((candidate) =>
    candidate.kind === "content" && candidate.id !== slotId && candidate.payload.kind !== "on_camera") ||
    (row.unattachedVisuals ?? []).length > 0;
  if (others) return unplace(row, slotId);
  if (slot.payload.kind === "undefined") {
    return refusal("VISUAL_UNDEFINED_LAST", "This row's only card is already Visual Undefined, so there is nothing left to delete.", slotId);
  }
  const deletedPayloadId = slot.payload.payloadId;
  const undefinedPayloadId = derivedCoverageIdV2(`${sequence.id}:deleted:${deletedPayloadId}`);
  slot.payload = { kind: "undefined", payloadId: undefinedPayloadId, description: "The row's last visual was deleted." };
  slot.version += 1;
  bump(row);
  return { slotIds: [slotId], payloadIds: [deletedPayloadId, undefinedPayloadId] };
}

/** Change type (D93, D100): the visual keeps its words and identity; what the new type cannot hold is reported. */
export function changeVisualTypeV2(row: NarrationBlockV2, slotId: string, to: VisualTypeChangeV2): VisualLifecycleResultV2 {
  const waiting = (row.unattachedVisuals ?? []).find((item) => item.slotId === slotId);
  const slot = waiting ? undefined : placedSlot(row, slotId);
  if (!waiting && !slot) return refusal("VISUAL_SLOT_MISSING", "Choose a visual that is in this row.", slotId);
  if (slot?.payload.kind === "on_camera") {
    return refusal("ON_CAMERA_NOT_A_VISUAL", "On Camera fills the words no visual covers, so it has no type to change. Add a visual on those words instead.", slotId);
  }
  const current = (waiting?.payload ?? slot!.payload);

  if (to.type === "on_camera") {
    // On Camera is not stored as a visual: choosing it means nothing covers these words any more.
    const dropped: DroppedVisualDetailV2[] = [{
      what: "visual",
      message: waiting
        ? "The visual was removed. It had no words, so nothing else in the row changes."
        : "The visual was removed, and On Camera now fills its words.",
    }];
    if (waiting) {
      dropWaiting(row, slotId);
      bump(row);
      return { slotIds: [slotId], payloadIds: [current.payloadId], dropped };
    }
    const unplaced = unplace(row, slotId);
    return isCoverageRefusalV2(unplaced) ? unplaced : { ...unplaced, dropped };
  }

  const retyped = retypeVisualPayloadV2(current, to);
  if (!retyped.ok) return refusal(retyped.code, retyped.message, slotId);
  if (waiting) {
    if (retyped.payload.kind !== "visual") {
      return refusal("CHANGE_TYPE_NEEDS_WORDS", "Visual Undefined marks words that still need a picture. Attach this visual to words first, or delete it.", slotId);
    }
    waiting.payload = retyped.payload;
    waiting.version += 1;
  } else {
    const staysFootage = retyped.payload.kind === "visual" && retyped.payload.pictureKind === "clip";
    if (slot!.playoutPolicy === "complete_logged_clip" && !staysFootage) {
      return refusal("COMPLETE_CLIP_REPAIR_REQUIRED", "This footage plays to its own end and the next cut depends on it. Give the next cut an exact word before changing its type.", slotId);
    }
    slot!.payload = retyped.payload;
    slot!.version += 1;
  }
  bump(row);
  return { slotIds: [slotId], payloadIds: [current.payloadId], dropped: retyped.dropped };
}
