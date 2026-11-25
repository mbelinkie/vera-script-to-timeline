import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import type { RowEditCommandV2 } from "@vera/contracts/authoring-v2";

export interface StashLocation {
  sectionId?: string | null;
  parentRowId?: string | null;
  afterRowId?: string | null;
}
export interface StashWordSelection { start: number; end: number }
export interface StashWordIntent {
  rowId: string;
  rowVersion: number;
  text: string;
  rowSnapshot: string;
  words: { startTokenId: string; endTokenId: string };
}
export interface StashDropIntent {
  noteRowId: string;
  rowId: string;
  beforeTokenId: string;
  noteSnapshot: string;
  rowSnapshot: string;
}
export type DraftGap = Extract<RowEditCommandV2, { kind: "restore_stash_rows" }>["destination"];
export interface OriginalDraftLocation {
  label: string;
  gap: Readonly<DraftGap> | null;
  available: boolean;
}
export interface WholeRowStashIntent {
  readonly projectId: string;
  readonly documentId: string;
  readonly sectionId: string | null;
  readonly rowIds: readonly string[];
  readonly draftSnapshot: string;
  readonly stashSnapshot: string;
}
export type SavedPlacementKind = "restore_stash_rows" | "place_stash_rows" | "duplicate_stash_rows";
export interface SavedPlacementIntent<K extends SavedPlacementKind = SavedPlacementKind> {
  readonly projectId: string;
  readonly documentId: string;
  readonly kind: K;
  readonly rowIds: readonly string[];
  readonly destination: Readonly<DraftGap>;
  readonly includeDescendants?: boolean;
  readonly stashSnapshot: string;
  readonly draftSnapshot: string;
}
export type SavedPlacementCommand<K extends SavedPlacementKind = SavedPlacementKind> =
  K extends "duplicate_stash_rows" ? { kind: K; rowIds: string[]; destination: DraftGap } :
  Extract<RowEditCommandV2, { kind: K }>;
export interface StashSectionView {
  id: string | null;
  title: string;
  entries: Array<{ rowId: string; kind: string; sectionId: string | null;
    parentRowId: string | null; row: NonNullable<ScriptDocumentV2["stash"]>[number]["rows"][number];
    bundleId: string; originalDraft: OriginalDraftLocation; hasDescendants: boolean; groupRestricted: boolean }>;
}
export type StashEditorQueue = (command: (document: ScriptDocumentV2) => RowEditCommandV2,
  label: string, options: { structural: true }) => Promise<boolean>;

export function projectStash(document: ScriptDocumentV2): StashSectionView[];
export function originalDraftLocation(document: ScriptDocumentV2,
  bundle: NonNullable<ScriptDocumentV2["stash"]>[number]): OriginalDraftLocation;
export function draftGapChoices(document: ScriptDocumentV2): Array<{ gap: Readonly<DraftGap>; label: string }>;
export function captureWholeRowStash(document: ScriptDocumentV2,
  rowIds: readonly string[]): WholeRowStashIntent | null;
export function wholeRowStashCommand(document: ScriptDocumentV2, intent: WholeRowStashIntent,
  makeId?: () => string): Extract<RowEditCommandV2, { kind: "stash_rows" }>;
export function captureSavedPlacement<K extends SavedPlacementKind>(document: ScriptDocumentV2, kind: K,
  rowIds: readonly string[], destination: Readonly<DraftGap>,
  includeDescendants?: boolean): SavedPlacementIntent<K> | null;
export function savedPlacementCommand<K extends SavedPlacementKind>(document: ScriptDocumentV2,
  intent: SavedPlacementIntent<K>): SavedPlacementCommand<K>;
export function createStashNoteCommand(document: ScriptDocumentV2, text: string,
  location?: StashLocation, makeId?: () => string): Extract<RowEditCommandV2, { kind: "create_stash_note" }>;
export function captureStashWords(document: ScriptDocumentV2, rowId: string,
  selection: StashWordSelection): StashWordIntent | null;
export function stashWordsCommand(document: ScriptDocumentV2, intent: StashWordIntent,
  makeId?: () => string): Extract<RowEditCommandV2, { kind: "stash_selected_words" }>;
export function captureStashNoteDrop(document: ScriptDocumentV2, noteRowId: string,
  rowId: string, beforeTokenId: string): StashDropIntent | null;
export function insertStashNoteCommand(document: ScriptDocumentV2,
  intent: StashDropIntent): Extract<RowEditCommandV2, { kind: "insert_stash_note_words" }>;
export function createStashActions(queue: StashEditorQueue, getDocument: () => ScriptDocumentV2,
  makeId?: () => string, queueExtras?: (command: (document: ScriptDocumentV2) =>
    Extract<RowEditCommandV2, { kind: "stash_rows" }> | SavedPlacementCommand, label: string) => Promise<boolean>): {
    view: () => StashSectionView[];
    stashRow: (rowId: string) => Promise<boolean>;
    placeSaved: (intent: SavedPlacementIntent) => Promise<boolean>;
    addNote: (text: string, location?: StashLocation) => Promise<boolean>;
    stashWords: (rowId: string, selection: StashWordSelection) => Promise<boolean>;
    dropNote: (noteRowId: string, rowId: string, beforeTokenId: string) => Promise<boolean>;
  };
