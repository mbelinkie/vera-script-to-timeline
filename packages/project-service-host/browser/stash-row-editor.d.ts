import type { RowEditCommandV2, PrimarySequenceProjectionV2 } from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";

export type StashRowEditorMember = NonNullable<ScriptDocumentV2["stash"]>[number]["rows"][number];

export interface StashRowEditorSaveMetadata {
  groupId: string | null;
  expectedRevision: number;
  expectedRowIds: string[];
}

export interface StashRowEditorOpenOptions {
  row?: StashRowEditorMember;
  members?: StashRowEditorMember[];
  groupId?: string | null;
  expectedRevision?: number;
  expectedRowIds?: string[];
  onSave?: (members: StashRowEditorMember[], metadata: StashRowEditorSaveMetadata) => boolean | Promise<boolean>;
  onStatus?: (message: string) => void;
}

export interface StashRowEditorApplyResult {
  ok: boolean;
  document: ScriptDocumentV2;
  splitProof?: string;
}

export interface StashRowEditorOptions {
  host: HTMLElement;
  getDocument: () => ScriptDocumentV2;
  applyCommand: (document: ScriptDocumentV2, command: RowEditCommandV2,
    splitProof?: string, expectedSequenceVersion?: number) => Promise<StashRowEditorApplyResult>;
  fetchProjection?: (document: ScriptDocumentV2) => Promise<PrimarySequenceProjectionV2>;
  onSave?: (members: StashRowEditorMember[], metadata: StashRowEditorSaveMetadata) => boolean | Promise<boolean>;
}

export interface StashRowEditor {
  open(options: StashRowEditorOpenOptions): boolean | void;
  close(): void;
  isOpen(): boolean;
  destroy(): void;
}

export function createStashRowEditorDocument(document: ScriptDocumentV2,
  members: StashRowEditorMember[], groupId?: string | null): ScriptDocumentV2;

export function mountStashRowEditor(options: StashRowEditorOptions): StashRowEditor;
