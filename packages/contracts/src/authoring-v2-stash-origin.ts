import type { StashOriginV2 } from "./generated/contracts-v2.js";

export interface RowWithStashOriginV2 {
  stashOrigin?: StashOriginV2;
}

/** Authored edits make a converted source ineligible for compact reconstruction. */
export function markStashOriginEditedV2(row: RowWithStashOriginV2): void {
  if (row.stashOrigin) row.stashOrigin.returnEligible = false;
}

/** Whole-row callers cannot replace or forge the origin carried by the current row. */
export function preserveStashOriginAfterEditV2<T extends RowWithStashOriginV2>(current: RowWithStashOriginV2, replacement: T): T {
  if (current.stashOrigin) replacement.stashOrigin = { ...current.stashOrigin, returnEligible: false };
  else delete replacement.stashOrigin;
  return replacement;
}
