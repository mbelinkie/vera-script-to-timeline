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
export interface StashSectionView {
  id: string | null;
  title: string;
  entries: Array<{ rowId: string; kind: string; sectionId: string | null;
    parentRowId: string | null; row: NonNullable<ScriptDocumentV2["stash"]>[number]["rows"][number] }>;
}
export type StashEditorQueue = (command: (document: ScriptDocumentV2) => RowEditCommandV2,
  label: string, options: { structural: true }) => Promise<boolean>;

export function projectStash(document: ScriptDocumentV2): StashSectionView[];
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
  makeId?: () => string): {
    view: () => StashSectionView[];
    addNote: (text: string, location?: StashLocation) => Promise<boolean>;
    stashWords: (rowId: string, selection: StashWordSelection) => Promise<boolean>;
    dropNote: (noteRowId: string, rowId: string, beforeTokenId: string) => Promise<boolean>;
  };
