import type { NarratedVisualPayloadV2, NarrationBlockV2, VisualOnlyBlockV2 } from "./generated/contracts-v2.js";

/** A whole wordless placement: trim, source snapshot and frame binding travel together. */
export type WordlessPlacementV2 = NonNullable<VisualOnlyBlockV2["additionalVisuals"]>[number];
type Problem = { code: string; message: string };
type Converted<T> = { value: T } | Problem;

const problem = (code: string, message: string): Problem => ({ code, message });

export function wordlessPlacementsV2(row: VisualOnlyBlockV2): WordlessPlacementV2[] {
  return [{
    payload: row.payload,
    visualOnlyTiming: row.visualOnlyTiming,
    ...(row.researchClip ? { researchClip: row.researchClip } : {}),
    ...(row.frameBinding ? { frameBinding: row.frameBinding } : {}),
  }, ...(row.additionalVisuals ?? [])];
}

function setPlacements(row: VisualOnlyBlockV2, placements: WordlessPlacementV2[]): void {
  const [first, ...rest] = placements;
  row.payload = first!.payload;
  row.visualOnlyTiming = first!.visualOnlyTiming;
  if (first!.researchClip) row.researchClip = first!.researchClip;
  else delete row.researchClip;
  if (first!.frameBinding) row.frameBinding = first!.frameBinding;
  else delete row.frameBinding;
  if (rest.length > 0) row.additionalVisuals = rest as NonNullable<VisualOnlyBlockV2["additionalVisuals"]>;
  else delete row.additionalVisuals;
}

/** No unrepresented clip out-point, audio policy or source metadata may be dropped. */
export function toWordlessPlacementV2(payload: NarratedVisualPayloadV2): Converted<WordlessPlacementV2> {
  const { selectedSourceRange, sourceUsage, researchClip, frameBinding, ...standalone } = payload;
  if (payload.pictureKind === "clip") {
    if (!selectedSourceRange || !sourceUsage ||
        selectedSourceRange.startFrame !== sourceUsage.sourceInFrame ||
        !Number.isSafeInteger(selectedSourceRange.startFrame) || selectedSourceRange.startFrame < 0 ||
        !Number.isSafeInteger(selectedSourceRange.durationFrames) || selectedSourceRange.durationFrames <= 0) {
      return problem("WORDLESS_CLIP_TRIM_REQUIRED", "Choose an exact source in and out for the clip before moving it to a wordless row.");
    }
  } else if (selectedSourceRange || sourceUsage) {
    return problem("WORDLESS_SOURCE_UNSUPPORTED", "This picture has source usage that a wordless row cannot represent without losing its trim.");
  }
  return { value: {
    payload: standalone,
    visualOnlyTiming: { kind: "visual_only", ...(selectedSourceRange
      ? { selectedSourceRange } : { durationOverrideMs: 4000 }) },
    ...(researchClip ? { researchClip } : {}),
    ...(frameBinding ? { frameBinding } : {}),
  } };
}

/** A narrated waiting visual has no fixed hold or music-match semantics. */
export function toNarratedPlacementV2(placement: WordlessPlacementV2): Converted<NarratedVisualPayloadV2> {
  const { payload, visualOnlyTiming, researchClip, frameBinding } = placement;
  if (payload.audioPolicy === "full" || visualOnlyTiming.matchAudioDuration ||
      (visualOnlyTiming.durationOverrideMs !== undefined && visualOnlyTiming.durationOverrideMs !== 4000)) {
    return problem("WORDLESS_TIMING_UNSUPPORTED", "Clear custom hold, matched music or full source audio before moving this picture onto narration.");
  }
  const range = visualOnlyTiming.selectedSourceRange;
  if (payload.pictureKind === "clip") {
    if (!range || !Number.isSafeInteger(range.startFrame) || range.startFrame < 0 ||
      !Number.isSafeInteger(range.durationFrames) || range.durationFrames <= 0 ||
      visualOnlyTiming.durationOverrideMs !== undefined) {
      return problem("WORDLESS_CLIP_TRIM_REQUIRED", "The clip needs a complete source trim and no fixed hold before moving onto narration.");
    }
  } else if (range) {
    return problem("WORDLESS_SOURCE_UNSUPPORTED", "This source trim cannot be represented on narrated words.");
  }
  return { value: {
    ...payload,
    audioPolicy: payload.audioPolicy,
    sourceUsage: range ? { sourceInFrame: range.startFrame } : null,
    ...(range ? { selectedSourceRange: range } : {}),
    ...(researchClip ? { researchClip } : {}),
    ...(frameBinding ? { frameBinding } : {}),
  } };
}

export function newWordlessPlaceholderV2(payloadId: string, visualType: "onscreen_placeholder" | "need_to_find"): WordlessPlacementV2 {
  return {
    payload: visualType === "onscreen_placeholder"
      ? { kind: "visual", payloadId, pictureKind: "intentional_placeholder",
        source: { kind: "intentional_placeholder", text: "Onscreen Placeholder" }, audioPolicy: "mute", framingPolicy: "contain" }
      : { kind: "visual", payloadId, pictureKind: "unresolved_visual",
        source: { kind: "unresolved_visual", description: "Need to Find" }, audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 4000 },
  };
}

/** A true empty draft row or one wordless narrated visual can be promoted in one edit. */
export function promoteWordlessNarrationV2(
  row: NarrationBlockV2, incoming: WordlessPlacementV2, incomingSlotId: string, incomingSlotVersion = 1,
): Converted<VisualOnlyBlockV2> {
  const sequence = row.primaryVisualSequence;
  const only = sequence?.slots.length === 1 ? sequence.slots[0] : undefined;
  if (row.state !== "active" || row.text !== "" || row.tokens.length !== 0 || row.plainDirection ||
      row.attachedFootage || row.notes.length || row.overlayEvents.length ||
      row.annotations?.length || row.performanceBeats?.length || row.unattachedVisuals?.length ||
      !sequence || !only || only.kind !== "content" ||
      only.relation.kind !== "base" || only.boundaryBefore.kind !== "row_start" ||
      only.playoutPolicy !== "match_structural_interval") {
    return problem("WORDLESS_PROMOTION_UNSAFE", "Use an empty ordinary narration row with no attached settings or extra picture slots.");
  }
  if (row.version === Number.MAX_SAFE_INTEGER || sequence.version === Number.MAX_SAFE_INTEGER) {
    return problem("ROW_CONTENT_INVALID", "This row cannot safely advance its revision.");
  }
  const base = { type: "visual_only" as const, id: row.id, orderKey: row.orderKey, version: row.version + 1,
    ...(row.stashOrigin ? { stashOrigin: row.stashOrigin } : {}),
    ...(row.stashChecklist ? { stashChecklist: row.stashChecklist } : {}),
  };
  if (only.payload.kind === "on_camera" && only.payload.presenterChoiceId === null ||
      only.payload.kind === "undefined") {
    return { value: { ...base, ...incoming } };
  }
  if (only.payload.kind !== "visual") {
    return problem("WORDLESS_PROMOTION_UNSAFE", "A chosen presenter picture cannot become an independent visual.");
  }
  const converted = toWordlessPlacementV2(only.payload);
  if (!("value" in converted)) return converted;
  if (only.id === incomingSlotId || only.payload.payloadId === incoming.payload.payloadId) {
    return problem("VISUAL_ID_DUPLICATE", "A new visual must have distinct placement and slot identities.");
  }
  return { value: {
    ...base, ...converted.value,
    additionalVisuals: [incoming],
    clearedNarration: { id: sequence.id, version: sequence.version,
      slots: [
        { id: only.id, version: only.version, visualId: only.payload.payloadId },
        { id: incomingSlotId, version: incomingSlotVersion, visualId: incoming.payload.payloadId },
      ],
    },
  } };
}

export function appendWordlessV2(row: VisualOnlyBlockV2, placement: WordlessPlacementV2, slotId: string, slotVersion = 1): Problem | null {
  if (row.version === Number.MAX_SAFE_INTEGER) return problem("ROW_CONTENT_INVALID", "The visual row revision cannot advance safely.");
  if (wordlessPlacementsV2(row).some((item) => item.payload.payloadId === placement.payload.payloadId)) {
    return problem("VISUAL_ID_DUPLICATE", "The target row already has this visual identity.");
  }
  if (row.clearedNarration && (row.clearedNarration.version === Number.MAX_SAFE_INTEGER ||
      row.clearedNarration.slots.some((item) => item.id === slotId))) {
    return problem("VISUAL_ID_DUPLICATE", "The original narration slot identities must remain distinct and versionable.");
  }
  setPlacements(row, [...wordlessPlacementsV2(row), placement]);
  if (row.clearedNarration) {
    row.clearedNarration.slots.push({ id: slotId, version: slotVersion, visualId: placement.payload.payloadId });
    row.clearedNarration.version += 1;
  }
  row.version += 1;
  return null;
}

/** The last picture leaves a visible placeholder; a cleared narration map must remain lossless. */
export function liftWordlessV2(
  row: VisualOnlyBlockV2, payloadId: string, replacementPayloadId?: string,
): Converted<{ placement: WordlessPlacementV2; priorSlotId?: string }> {
  const placements = wordlessPlacementsV2(row);
  const index = placements.findIndex((item) => item.payload.payloadId === payloadId);
  if (index < 0) return problem("VISUAL_NOT_FOUND", "Choose a picture that belongs to the source row.");
  if (row.version === Number.MAX_SAFE_INTEGER || row.clearedNarration?.version === Number.MAX_SAFE_INTEGER) {
    return problem("ROW_CONTENT_INVALID", "The visual row cannot safely advance its revision.");
  }
  if (row.clearedNarration && placements.length <= 2) {
    return problem("CLEARED_NARRATION_REVIEW_REQUIRED", "This row keeps original narration identities for both pictures. Restore its narration before removing one.");
  }
  if (placements.length === 1 && !replacementPayloadId) {
    return problem("WORDLESS_EMPTY_SOURCE", "Provide a fresh placeholder identity so the source row remains visible.");
  }
  if (placements.length !== 1 && replacementPayloadId) {
    return problem("ROW_COMMAND_INVALID", "Only the last picture needs a replacement placeholder identity.");
  }
  const priorSlotId = row.clearedNarration?.slots.find((slot) => slot.visualId === payloadId)?.id;
  const rest = placements.filter((item) => item.payload.payloadId !== payloadId);
  if (rest.length === 0) rest.push(newWordlessPlaceholderV2(replacementPayloadId!, "onscreen_placeholder"));
  setPlacements(row, rest);
  if (row.clearedNarration) {
    const slots = row.clearedNarration.slots.filter((slot) => slot.visualId !== payloadId);
    row.clearedNarration.slots = slots as NonNullable<VisualOnlyBlockV2["clearedNarration"]>["slots"];
    row.clearedNarration.version += 1;
  }
  row.version += 1;
  return { value: { placement: placements[index]!, ...(priorSlotId ? { priorSlotId } : {}) } };
}
