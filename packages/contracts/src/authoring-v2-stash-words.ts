import type { NarrationBlockV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { derivedCoverageIdV2 } from "./authoring-v2-coverage.js";
import { markStashOriginEditedV2 } from "./authoring-v2-stash-origin.js";
import { cutNarrationWordRangeV2, type RowWordSelectionV2 } from "./authoring-v2-row-split-join.js";

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

/**
 * Plan a pure plain-note cut. All entities beyond a single On Camera passage
 * remain fenced until phase 2 implements ownership-aware visual/reference moves.
 * No mutations occur here; the command adapter commits both sides to one clone.
 */
export function preparePlainStashWordCutV2(
  document: ScriptDocumentV2,
  command: StashSelectedWordsCommandV2,
  reservedIds: ReadonlySet<string>,
): { updated: NarrationBlockV2; note: NarrationBlockV2 } | AuthoringDiagnosticV2 {
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

  const soleCamera = row.primaryVisualSequence?.slots.length === 1 &&
    row.primaryVisualSequence.slots[0]?.kind === "content" &&
    row.primaryVisualSequence.slots[0].relation.kind === "base" &&
    row.primaryVisualSequence.slots[0].boundaryBefore.kind === "row_start" &&
    row.primaryVisualSequence.slots[0].payload.kind === "on_camera" &&
    row.primaryVisualSequence.slots[0].payload.presenterChoiceId === null &&
    row.primaryVisualSequence.slots[0].payload.framing === undefined;
  if (!soleCamera || row.overlayEvents.length > 0 || row.annotations?.length || row.performanceBeats?.length ||
    row.unattachedVisuals?.length || row.attachedFootage) {
    return issue("STASH_WORD_OWNERSHIP_REVIEW_REQUIRED", "Move attached visuals and word-anchored objects only with their ownership-aware Stash operation.", row.id);
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
  updated.version += 1;
  markStashOriginEditedV2(updated);

  const note: NarrationBlockV2 = {
    type: "narration", id: command.stashRowId, orderKey: `stash-words-${command.stashRowId}`,
    text: cut.extracted.text,
    tokens: cut.extracted.tokens.map((token) => ({ ...token, spoken: false })),
    plainDirection: true,
    primaryVisualSequence: { id: sequenceId, version: 1, slots: [{
      id: baseSlotId, kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
    stashChecklist: { completed: false, manualRevision: 0 },
  };
  return { updated, note };
}
