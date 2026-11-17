import type { NarrationBlockV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { derivedCoverageIdV2, isCoverageRefusalV2, redistributeCoverageV2 } from "./authoring-v2-coverage.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { markStashOriginEditedV2 } from "./authoring-v2-stash-origin.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { wordCoverageOffsetV2 } from "./authoring-v2-validation.js";
import { cutNarrationWordRangeV2, moveWordAnchoredEntitiesToStashV2, type RowWordSelectionV2 } from "./authoring-v2-row-split-join.js";

/** Partial-word Stash is intentionally distinct from whole-row Stash. */
export type StashSelectedWordsCommandV2 = {
  kind: "stash_selected_words";
  rowId: string;
  words: RowWordSelectionV2;
  bundleId: string;
  stashRowId: string;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

export function isStashSelectedWordsCommandV2(value: unknown): value is StashSelectedWordsCommandV2 {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) return false;
  const command = value as Record<string, unknown>;
  if (Object.keys(command).length !== 5 ||
    !["kind", "rowId", "words", "bundleId", "stashRowId"].every((key) => Object.hasOwn(command, key)) ||
    command.kind !== "stash_selected_words" || typeof command.rowId !== "string" || !UUID.test(command.rowId) ||
    typeof command.bundleId !== "string" || !UUID.test(command.bundleId) ||
    typeof command.stashRowId !== "string" || !UUID.test(command.stashRowId)) return false;
  const words = command.words;
  if (!words || typeof words !== "object" || Array.isArray(words) || Object.getPrototypeOf(words) !== Object.prototype) return false;
  const selection = words as Record<string, unknown>;
  return Object.keys(selection).length === 2 && Object.hasOwn(selection, "startTokenId") &&
    Object.hasOwn(selection, "endTokenId") &&
    typeof selection.startTokenId === "string" && UUID.test(selection.startTokenId) &&
    typeof selection.endTokenId === "string" && UUID.test(selection.endTokenId);
}

const issue = (code: string, message: string, blockId?: string): AuthoringDiagnosticV2 => ({
  code, message, jsonPath: "/activeDraft/blocks", ...(blockId ? { blockId } : {}),
});

/** Plan both row changes on clones; the caller either commits both or neither. */
export function prepareStashWordCutV2(
  document: ScriptDocumentV2,
  command: StashSelectedWordsCommandV2,
  reservedIds: ReadonlySet<string>,
): { updated: NarrationBlockV2; saved: NarrationBlockV2; kind: "note" | "row" } | AuthoringDiagnosticV2 {
  const row = document.activeDraft.blocks.find((block) => block.id === command.rowId);
  if (!row || row.type !== "narration" || row.state !== "active" || row.plainDirection === true) {
    return issue("ROW_SELECTION_INVALID", "Select words in an active spoken narration row.", command.rowId);
  }
  if (!Number.isSafeInteger(row.version) || row.version === Number.MAX_SAFE_INTEGER) {
    return issue("ROW_CONTENT_INVALID", "The source row version cannot advance.", row.id);
  }
  const sequenceId = derivedCoverageIdV2(`${command.stashRowId}:note-sequence`);
  const baseSlotId = derivedCoverageIdV2(`${command.stashRowId}:note-base-slot`);
  const newlyOwned = [command.bundleId, command.stashRowId, sequenceId, baseSlotId].map((id) => id.toLowerCase());
  if (new Set(newlyOwned).size !== newlyOwned.length || newlyOwned.some((id) => reservedIds.has(id))) {
    return issue("STASH_WORD_ID_DUPLICATE", "Provide new Stash and row identities without any existing owner.", row.id);
  }
  const cut = cutNarrationWordRangeV2(row, command.words);
  if ("code" in cut) return cut;
  const movedIds = cut.extracted.tokens.map((token) => token.id);

  if (!row.primaryVisualSequence || row.unattachedVisuals?.length || row.attachedFootage) {
    return issue("STASH_WORD_OWNERSHIP_REVIEW_REQUIRED", "Unattached or note-owned footage cannot be divided with a word selection.", row.id);
  }
  // A row-granular music or reference anchor cannot be silently retargeted to
  // a subset of its words. Later phases may move safely provable references.
  const referencesMovedWord = (value: unknown): boolean => {
    const encoded = JSON.stringify(value);
    return encoded.includes(row.id) || movedIds.some((id) => encoded.includes(id));
  };
  if ((document.rowReferences ?? []).some((item) => item.rowId === row.id || referencesMovedWord(item.anchor)) ||
    (document.rowTransitions ?? []).some((item) => item.fromRowId === row.id || item.toRowId === row.id) ||
    (document.rowAudioSpans ?? []).some((span) => {
      const ids = document.activeDraft.blocks.filter((block) => block.type !== "section").map((block) => block.id);
      const start = ids.indexOf(span.startRowId);
      const end = ids.indexOf(span.endRowId);
      const at = ids.indexOf(row.id);
      return start >= 0 && end >= 0 && at >= Math.min(start, end) && at <= Math.max(start, end);
    }) ||
    [document.activeDraft.supportingItems, ...(document.stash ?? []).map((bundle) => bundle.supportingItems)]
      .some((items) => items.some(referencesMovedWord))) {
    return issue("ROW_REFERENCE_REVIEW_REQUIRED", "Review row-level music, comments or supporting references before stashing part of this row.", row.id);
  }
  const updated: NarrationBlockV2 = structuredClone(row);
  updated.text = cut.remaining.text;
  updated.tokens = cut.remaining.tokens;
  const saved: NarrationBlockV2 = {
    type: "narration", id: command.stashRowId, orderKey: `stash-words-${command.stashRowId}`,
    text: cut.extracted.text,
    tokens: cut.extracted.tokens,
    primaryVisualSequence: { id: sequenceId, version: 1, slots: [{
      id: baseSlotId, kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
  const plainNoteCoverage = structuredClone(saved.primaryVisualSequence!);
  const moved = moveWordAnchoredEntitiesToStashV2(row, updated, saved);
  if (moved) return moved;

  // Redistribute across BOTH rows before making a plain note: visual starts
  // decide ownership, while starts before the selection stay and are clipped.
  // A surviving prior-start visual must never be copied into the saved row.
  const reflow = redistributeCoverageV2([row], [updated, saved]);
  if (isCoverageRefusalV2(reflow)) return issue(reflow.code, reflow.message, row.id);
  for (const [index, target] of [updated, saved].entries()) {
    const slots = reflow[index];
    if (!slots || !target.primaryVisualSequence) {
      return issue("STASH_WORD_OWNERSHIP_REVIEW_REQUIRED", "The picture coverage could not be rebuilt safely.", row.id);
    }
    const previous = target.primaryVisualSequence.slots;
    target.primaryVisualSequence.slots = slots;
    if (!sameAuthoringJsonV2(slots, previous)) target.primaryVisualSequence.version += 1;
  }
  const movedVisual = saved.primaryVisualSequence!.slots.some((slot) =>
    slot.kind === "content" && slot.payload.kind !== "on_camera");
  // A chosen camera take/framing is still authored visual information; do not
  // erase it by converting selected words to a direction note.
  const originalSpoken = spokenTokensV2(row);
  const movedAuthoredCamera = row.primaryVisualSequence.slots.some((slot) => {
    if (slot.kind !== "content" || slot.payload.kind !== "on_camera" ||
      (slot.payload.framing === undefined && slot.payload.presenterChoiceId === null)) return false;
    const boundary = slot.boundaryBefore;
    const start = boundary.kind === "row_start" ? 0 :
      boundary.kind === "spoken_word" || boundary.kind === "audible_word_end"
        ? wordCoverageOffsetV2(boundary.anchor, row) : null;
    return start !== null && movedIds.includes(originalSpoken[start]?.id ?? "");
  });
  // Word-bound annotations, beats and overlays also require spoken words and
  // stay a saved row, rather than becoming invalid anchors in a plain note.
  const movedWordObjects = saved.overlayEvents.length > 0 ||
    (saved.annotations?.length ?? 0) > 0 || (saved.performanceBeats?.length ?? 0) > 0;
  const kind = movedVisual || movedAuthoredCamera || movedWordObjects ? "row" : "note";
  if (kind === "note") {
    // An earlier-start On Camera framing remains with the source. A compact
    // note has no spoken coverage or inherited camera cards of its own.
    saved.primaryVisualSequence = plainNoteCoverage;
    saved.plainDirection = true;
    saved.tokens.forEach((token) => { token.spoken = false; });
    saved.stashChecklist = { completed: false, manualRevision: 0 };
  }
  updated.version += 1;
  markStashOriginEditedV2(updated);
  return { updated, saved, kind };
}
