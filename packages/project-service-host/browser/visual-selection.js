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
