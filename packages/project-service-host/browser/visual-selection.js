/** The source-free types available in the first browser-authoring release. */
export const ADD_VISUAL_TYPES = Object.freeze([
  { type: "onscreen_placeholder", label: "Onscreen Placeholder" },
  { type: "need_to_find", label: "Need to Find" },
  { type: "visual_undefined", label: "Visual Undefined" },
]);

/**
 * Select by UTF-16 text offsets, but return the model's *spoken* token IDs.
 * Direction tokens are not picture cues. Optimistic local tokens may have no
 * IDs yet; the caller must resolve this again against the committed document
 * after any queued typing, with requireIds=true, before issuing a command.
 */
export function selectedSpokenWords(row, selection, requireIds = false) {
  if (row?.plainDirection === true || !Array.isArray(row?.tokens) || !selection ||
      !Number.isSafeInteger(selection.start) || !Number.isSafeInteger(selection.end) ||
      selection.start < 0 || selection.end <= selection.start ||
      selection.end > row.text?.length) return null;
  const selected = row.tokens.filter((token) => token?.spoken !== false &&
    Number.isSafeInteger(token.startOffset) && Number.isSafeInteger(token.endOffset) &&
    token.startOffset < token.endOffset && token.endOffset > selection.start &&
    token.startOffset < selection.end);
  if (!selected.length) return null;
  const first = selected[0];
  const last = selected[selected.length - 1];
  if (requireIds && (typeof first.id !== "string" || !first.id ||
      typeof last.id !== "string" || !last.id)) return null;
  return { startTokenId: first.id ?? null, endTokenId: last.id ?? null,
    startOffset: first.startOffset, endOffset: last.endOffset };
}

/**
 * Freeze the committed identity of the selected spoken range before a sidebar
 * takes focus. No DOM geometry or mutable row/token objects belong here.
 */
export function captureSelectedDrop(model, target) {
  if (!model?.projectId || !model.id || !target?.selected) return null;
  const row = model.activeDraft?.blocks.find((item) => item.id === target.rowId);
  if (row?.type !== "narration" || row.state !== "active" || typeof row.text !== "string" ||
      row.text !== target.text || row.version !== target.rowVersion ||
      row.primaryVisualSequence?.version !== target.sequenceVersion ||
      !Number.isSafeInteger(row.version) || !Number.isSafeInteger(row.primaryVisualSequence?.version) ||
      row.version < 1 || row.primaryVisualSequence.version < 1 ||
      row.version >= Number.MAX_SAFE_INTEGER || row.primaryVisualSequence.version >= Number.MAX_SAFE_INTEGER) return null;
  const words = selectedSpokenWords(row, target.selection, true);
  if (!words || words.startOffset < 0 || words.endOffset > row.text.length) return null;
  return Object.freeze({
    projectId: model.projectId, documentId: model.id, rowId: row.id, text: row.text,
    rowVersion: row.version, sequenceVersion: row.primaryVisualSequence.version,
    selection: Object.freeze({ start: target.selection.start, end: target.selection.end }),
    ...words,
  });
}

/** Resolve only the original exact selection, never a nearby or repeated word. */
export function selectedDropPlacement(model, snapshot) {
  if (!snapshot || model?.projectId !== snapshot.projectId || model?.id !== snapshot.documentId) return null;
  const current = captureSelectedDrop(model, { ...snapshot, selected: true });
  if (!current || current.startTokenId !== snapshot.startTokenId || current.endTokenId !== snapshot.endTokenId ||
      current.startOffset !== snapshot.startOffset || current.endOffset !== snapshot.endOffset) return null;
  return { kind: "selected_words", rowId: current.rowId,
    expectedRowVersion: current.rowVersion, expectedSequenceVersion: current.sequenceVersion,
    startTokenId: current.startTokenId, endTokenId: current.endTokenId };
}
