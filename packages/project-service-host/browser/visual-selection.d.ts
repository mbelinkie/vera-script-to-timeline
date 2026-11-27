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

type SelectionOffsets = { start: number; end: number };
type SelectionDropModel = {
  projectId: string;
  id: string;
  activeDraft?: { blocks: readonly {
    id: string; type: string; state?: string; text?: string; version?: number;
    plainDirection?: boolean;
    primaryVisualSequence?: { version: number };
    tokens?: readonly { id?: string | undefined; spoken?: boolean; startOffset: number; endOffset: number }[];
  }[] };
};
type SelectedDropTarget = {
  rowId: string; text: string; rowVersion: number; sequenceVersion?: number | undefined;
  selected: boolean; selection: SelectionOffsets;
};
export type SelectedDropSnapshot = Readonly<{
  projectId: string; documentId: string; rowId: string; text: string;
  rowVersion: number; sequenceVersion: number;
  selection: Readonly<SelectionOffsets>;
  startTokenId: string; endTokenId: string; startOffset: number; endOffset: number;
}>;
export function captureSelectedDrop(model: SelectionDropModel | null,
  target: SelectedDropTarget | null): SelectedDropSnapshot | null;
export function selectedDropPlacement(model: SelectionDropModel | null,
  snapshot: SelectedDropSnapshot | null): {
    kind: "selected_words"; rowId: string; expectedRowVersion: number;
    expectedSequenceVersion: number; startTokenId: string; endTokenId: string;
  } | null;
