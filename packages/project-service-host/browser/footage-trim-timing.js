// Only call with the authorized, identity-matched cue DTO. Original-video ms,
// never decoded cut frames. Without complete coverage, silence is not evidence.
export function cueExcerpt(cues, startMs, endMs, fullText) {
  const fallback = { kind: "full", text: fullText,
    note: "A trimmed excerpt isn't available for this saved transcript." };
  if (!Number.isSafeInteger(startMs) || !Number.isSafeInteger(endMs) ||
      startMs < 0 || endMs <= startMs || !Array.isArray(cues) ||
      cues.some(c => !c || !Number.isSafeInteger(c.startMs) ||
        !Number.isSafeInteger(c.endMs) || c.startMs < 0 ||
        c.endMs <= c.startMs || typeof c.text !== "string" || !c.text.trim())) return fallback;
  const overlap = [...cues].sort((a, b) => a.startMs - b.startMs || a.endMs - b.endMs)
    .filter(c => c.startMs < endMs && c.endMs > startMs);
  if (!overlap.length) return fallback;
  return {
    kind: "cue", text: [
      ...(overlap.some(c => c.startMs < startMs) ? ["…"] : []),
      ...overlap.map(c => c.text),
      ...(overlap.some(c => c.endMs > endMs) ? ["…"] : []),
    ].join(" "),
    note: "Approximate excerpt from caption timing.",
  };
}
