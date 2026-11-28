import type { ProjectAction } from "@vera/project-authorization";
import type { DocumentHistoryPage, CheckpointPage, CheckpointView, CreateCheckpointInput, ApproveCheckpointInput,
  CheckpointCreateReceipt, CheckpointApprovalReceipt, DocumentRevisionSummary, CheckpointSummary } from "@vera/project-documents";

export interface HistoryContext {
  projectId: string | null;
  capabilities: readonly ProjectAction[];
  /** Null when no exact acknowledged saved revision is available. */
  savedHead: number | null;
}
export interface HistoryApi {
  listDocumentRevisions(projectId: string, query: {limit: number; beforeRevision?: number}): Promise<DocumentHistoryPage>;
  listCheckpoints(projectId: string, query: {limit: number; beforeCheckpointId?: string}): Promise<CheckpointPage>;
  getCheckpoint(projectId: string, checkpointId: string): Promise<CheckpointView>;
  createCheckpoint(projectId: string, input: CreateCheckpointInput): Promise<CheckpointCreateReceipt>;
  approveCheckpoint(projectId: string, checkpointId: string, input: ApproveCheckpointInput): Promise<CheckpointApprovalReceipt>;
}
interface Page<T, C> { items: T[]; cursor: C | null | undefined; loading: boolean; error: string | null }
export interface HistoryState {
  context: HistoryContext;
  history: Page<DocumentRevisionSummary, number>;
  checkpoints: Page<CheckpointSummary, string>;
  mutation: { busy: boolean; error: string | null; pending: {kind: "create" | "approve"; name?: string; checkpointId: string} | null };
  canCreate: boolean;
  canApprove: boolean;
  canRestore: boolean;
}
interface Options { api: HistoryApi; makeId?: () => string; pageSize?: number }
export function createHistoryControls(options: Options & {onChange?: (state: HistoryState) => void}): {
  snapshot(): HistoryState;
  setContext(context: HistoryContext): void;
  loadHistory(): Promise<void>;
  loadCheckpoints(): Promise<void>;
  refresh(): Promise<void>;
  create(name: string): Promise<void>;
  approve(id: string): Promise<void>;
  retry(): Promise<void>;
};
export function mountHistoryPanel(options: Options & {
  root: HTMLElement;
  onCompare?: (selection: {mount: HTMLElement; checkpoint: CheckpointView; toRevision: number}) => void;
  onRestore?: (selection: {projectId: string; checkpointId: string}) => void;
}): {
  comparisonMount: HTMLElement;
  setContext(context: HistoryContext): Promise<void>;
  refresh(): Promise<void>;
  destroy(): void;
};
