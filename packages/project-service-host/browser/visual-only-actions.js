/** Read one complete, unique visual-only placement order without mutating its row. */
export function visualOnlyIds(row) {
  if (row?.type !== "visual_only" || typeof row.id !== "string" || !row.id ||
      !Array.isArray(row.additionalVisuals) && row.additionalVisuals !== undefined ||
      typeof row.payload?.payloadId !== "string" || !row.payload.payloadId) return null;
  const ids = [row.payload.payloadId, ...(row.additionalVisuals ?? []).map((item) => item?.payload?.payloadId)];
  return ids.every((id) => typeof id === "string" && id.length > 0) &&
    new Set(ids).size === ids.length ? ids : null;
}

/** Drop before an existing placement, or append to the end with null. */
export function planVisualOnlyReorder(row, draggedPayloadId, beforePayloadId = null) {
  const original = visualOnlyIds(row);
  if (!original || original.length < 2 || !original.includes(draggedPayloadId) ||
      beforePayloadId !== null && !original.includes(beforePayloadId) ||
      draggedPayloadId === beforePayloadId) return null;
  const without = original.filter((item) => item !== draggedPayloadId);
  const index = beforePayloadId === null ? without.length : without.indexOf(beforePayloadId);
  if (index < 0) return null;
  const payloadIds = [...without.slice(0, index), draggedPayloadId, ...without.slice(index)];
  if (payloadIds.every((item, i) => original[i] === item)) return null;
  return { kind: "reorder_visual_only", rowId: row.id, payloadIds };
}

/** UI-only field validation; set_visual_only_hold still validates the model edit. */
export function parseHoldSeconds(raw) {
  if (typeof raw !== "string") return null;
  const matched = /^(?:(\d+)(?:\.(\d{1,3}))?|\.(\d{1,3}))$/u.exec(raw.trim());
  if (!matched) return null;
  // Work in integral milliseconds first to avoid rejecting valid 1.001 s due
  // to binary floating point (1.001 * 1000 can be 1000.9999999999999).
  const wholeMs = Number(matched[1] ?? "0") * 1000;
  const fractionalMs = Number((matched[2] ?? matched[3] ?? "").padEnd(3, "0"));
  const milliseconds = wholeMs + fractionalMs;
  return Number.isSafeInteger(milliseconds) && milliseconds > 0 ? milliseconds / 1000 : null;
}
