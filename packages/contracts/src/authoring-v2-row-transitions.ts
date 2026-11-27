import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;

/** Section headings mark a divider without adding picture to it. */
export function rowTransitionDividerV2(
  blocks: readonly Block[], fromRowId: string | undefined, toRowId: string,
): { from?: Row; to: Row } | null {
  if (fromRowId === undefined) {
    const first = blocks.find((block): block is Row => block.type === "visual_only" ||
      block.type === "narration" && block.state === "active");
    return first?.id === toRowId ? { to: first } : null;
  }
  const rows = blocks.filter((block) => block.type !== "section");
  const index = rows.findIndex((row) => row.id === fromRowId);
  const from = rows[index];
  const to = rows[index + 1];
  return from && to?.id === toRowId ? { from, to } : null;
}

/** Structural eligibility only. The compiler still verifies media and handles. */
export function qualifiedTransitionRowShapeV2(row: Row): boolean {
  if (row.type === "visual_only") {
    return !row.additionalVisuals?.length && row.payload.kind === "visual" &&
      row.payload.pictureKind === "clip" && row.payload.audioPolicy === "mute";
  }
  if (row.type !== "narration" || row.state !== "active" || row.plainDirection === true ||
      row.overlayEvents.length !== 0 || row.primaryVisualSequence?.slots.length !== 1) return false;
  const slot = row.primaryVisualSequence.slots[0];
  return slot?.kind === "content" && slot.relation.kind === "base" &&
    slot.boundaryBefore.kind === "row_start" && slot.playoutPolicy === "match_structural_interval" &&
    slot.payload.kind === "visual" && slot.payload.pictureKind === "clip" && slot.payload.audioPolicy === "mute";
}
