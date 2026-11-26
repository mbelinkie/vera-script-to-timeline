import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;

/** Match the exact ordered active Draft divider, without skipping section headings. */
export function ordinaryTransitionPairV2(
  document: ScriptDocumentV2, fromRowId: string, toRowId: string,
): { from: Row; to: Row } | null {
  const blocks = document.activeDraft.blocks;
  const index = blocks.findIndex((block) => block.id === fromRowId);
  const from = blocks[index];
  const to = blocks[index + 1];
  if (!from || !to || from.type === "section" || to.type === "section" || to.id !== toRowId) return null;
  return { from, to };
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
