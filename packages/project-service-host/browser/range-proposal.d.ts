export interface BracketRange {
  startTokenIndex: number;
  endTokenIndexExclusive: number;
}

export interface RangeProjection {
  blockId: string;
  tokens: Array<{ tokenId: string }>;
  brackets: Array<BracketRange & { slotId: string }>;
}

export type PendingRange = { startIndex: number; endIndexExclusive: number };
/** Fixed projected non-camera ranges for the lifetime of a bracket gesture. */
export interface BracketContext {
  originalRange: BracketRange;
  brackets: readonly BracketRange[];
}

export declare function proposeVisualRange(row: RangeProjection, slotId: string,
  startIndex: number, endIndexExclusive: number):
  | { ok: false; reason: string }
  | { ok: true; wordCount: number;
      setCommand: { kind: "set_visual_range"; blockId: string; slotId: string; startTokenId: string; endTokenId: string };
      swapCommand: { kind: "swap_ranges"; blockId: string; firstSlotId: string; secondSlotId: string } | null };

export declare function stepVisualBracket(range: BracketRange, edge: "start" | "end",
  delta: number, wordCount: number, context: BracketContext): PendingRange;
export declare function moveVisualBracket(range: BracketRange, edge: "start" | "end",
  wordIndex: number, wordCount: number, context: BracketContext): PendingRange;
