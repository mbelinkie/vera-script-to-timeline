// Pure bracket intent. Only projected spoken-token IDs may enter a visual
// command; character offsets and pointer coordinates never become anchors.
export function proposeVisualRange(row, slotId, startIndex, endIndexExclusive) {
  const current = row?.brackets?.find((item) => item.slotId === slotId);
  const tokens = row?.tokens;
  if (!current || !Array.isArray(tokens) || !Number.isInteger(startIndex) ||
      !Number.isInteger(endIndexExclusive) || startIndex < 0 ||
      startIndex >= endIndexExclusive || endIndexExclusive > tokens.length) {
    return { ok: false, reason: "Choose at least one spoken word within this row." };
  }
  if (current.startTokenIndex === startIndex && current.endTokenIndexExclusive === endIndexExclusive) {
    return { ok: false, reason: "This is already the visual's range." };
  }
  const startTokenId = tokens[startIndex]?.tokenId;
  const endTokenId = tokens[endIndexExclusive - 1]?.tokenId;
  if (!startTokenId || !endTokenId) return { ok: false, reason: "The selected words cannot be located." };
  const exact = row.brackets.find((item) => item.slotId !== slotId &&
    item.startTokenIndex === startIndex && item.endTokenIndexExclusive === endIndexExclusive);
  return {
    ok: true,
    wordCount: endIndexExclusive - startIndex,
    setCommand: { kind: "set_visual_range", blockId: row.blockId, slotId, startTokenId, endTokenId },
    swapCommand: exact ? {
      kind: "swap_ranges", blockId: row.blockId, firstSlotId: slotId, secondSlotId: exact.slotId,
    } : null,
  };
}

export function stepVisualBracket(range, edge, delta, wordCount, context) {
  const index = edge === "start" ? range.startTokenIndex : range.endTokenIndexExclusive;
  return moveVisualBracket(range, edge, index + delta, wordCount, context);
}

export function moveVisualBracket(range, edge, wordIndex, wordCount, context) {
  if (!Number.isInteger(wordIndex) || wordCount < 1) return {
    startIndex: range.startTokenIndex, endIndexExclusive: range.endTokenIndexExclusive,
  };
  // D192: the projection has brackets for placed non-camera visuals only.
  // Use the original range, not the moving preview, to identify neighbours:
  // repeated pointer/keyboard moves must not cross a neighbour once overlapped.
  // The opening bracket stops at the previous visual's end (#715); the
  // closing bracket may shorten the next visual but leaves its last word.
  let minStart = 0;
  let maxEnd = wordCount;
  for (const neighbour of context.brackets) {
    if (neighbour.endTokenIndexExclusive <= context.originalRange.startTokenIndex) {
      minStart = Math.max(minStart, neighbour.endTokenIndexExclusive);
    }
    if (neighbour.startTokenIndex >= context.originalRange.endTokenIndexExclusive) {
      maxEnd = Math.min(maxEnd, neighbour.endTokenIndexExclusive - 1);
    }
  }
  return edge === "start" ? {
    startIndex: Math.max(minStart, Math.min(wordIndex, range.endTokenIndexExclusive - 1)),
    endIndexExclusive: range.endTokenIndexExclusive,
  } : {
    startIndex: range.startTokenIndex,
    endIndexExclusive: Math.max(range.startTokenIndex + 1, Math.min(maxEnd, wordIndex)),
  };
}
