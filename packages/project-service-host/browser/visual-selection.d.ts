export type VisualSelectionType = "onscreen_placeholder" | "need_to_find" | "visual_undefined";

export const ADD_VISUAL_TYPES: readonly {
  readonly type: VisualSelectionType;
  readonly label: string;
}[];

export function selectedSpokenWords(
  row: { text?: string; plainDirection?: boolean; tokens?: readonly {
    id?: string; spoken?: boolean; startOffset: number; endOffset: number;
  }[] } | null,
  selection: { start: number; end: number } | null,
  requireIds?: boolean,
): { startTokenId: string | null; endTokenId: string | null;
  startOffset: number; endOffset: number } | null;
