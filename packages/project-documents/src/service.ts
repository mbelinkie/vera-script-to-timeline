import type { PrincipalRef } from "@vera/contracts";
import type { AuthoringProjectSettingsV1, ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  ProjectAuthError,
  ProjectAuthorizationService,
  ProjectSerializationConflictError,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";

import {
  checkedDocument,
  checkedSettings,
  fingerprint,
  ProjectDocumentError,
  ProjectDocumentInputError,
  requireCheckpointName,
  requireHistoryLimit,
  requireRevision,
  requireTitle,
  requireUuid,
  sha256,
} from "./model.js";
import { reconcileCommentsForDocumentRevision } from "./comments.js";
import { compareDocuments, type SemanticChange } from "./semantic-diff.js";

type Digest = string;
interface HeadRow {
  document_id: string;
  revision: string;
  document_json: string;
  content_digest: Digest;
}
interface SettingsRow {
  settings_id: string;
  settings_revision: string;
  settings_json: string;
  content_digest: Digest;
}
interface ProjectRow {
  id: string;
  title: string;
  project_version: string;
  linked_research_project_ids: string[];
}
interface MutationRow {
  request_digest: string;
  revision: string;
  content_digest: string;
}
interface TitleMutationRow {
  request_digest: string;
  project_version: string;
  title: string;
}
interface RevisionRow {
  document_id: string;
  revision: string;
  expected_revision: string | null;
  actor_id: string;
  client_mutation_id: string;
  content_digest: Digest;
  document_json: string;
  created_at: Date | string;
  restore_checkpoint_id: string | null;
  restore_source_revision: string | null;
  restore_source_digest: string | null;
  restored_by: string | null;
  restore_mutation_id: string | null;
}

interface CheckpointRow {
  project_id: string;
  checkpoint_id: string;
  name: string;
  source_revision: string;
  document_id: string;
  document_json: string;
  source_digest: string;
  created_by: string;
  client_mutation_id: string;
  request_digest: string;
  created_at: Date | string;
  revision_document_id: string;
  revision_document_json: string;
  revision_digest: string;
  approved_by: string | null;
  approval_mutation_id: string | null;
  approval_request_digest: string | null;
  approved_at: Date | string | null;
}

const CHECKPOINT_COLUMNS =
  "c.project_id,c.checkpoint_id,c.name,c.source_revision::text,c.document_id," +
  "c.document_json,c.source_digest,c.created_by,c.client_mutation_id,c.request_digest,c.created_at," +
  "r.document_id AS revision_document_id,r.document_json AS revision_document_json," +
  "r.content_digest AS revision_digest,a.approved_by," +
  "a.client_mutation_id AS approval_mutation_id,a.request_digest AS approval_request_digest,a.approved_at";
const CHECKPOINT_FROM =
  " FROM stt_document_checkpoints c JOIN stt_document_revisions r" +
  " ON r.project_id=c.project_id AND r.revision=c.source_revision" +
  " LEFT JOIN stt_checkpoint_approvals a" +
  " ON a.project_id=c.project_id AND a.checkpoint_id=c.checkpoint_id";

// Restoration attribution lives in the separate append-only provenance table.
const REVISION_COLUMNS =
  "r.document_id,r.revision::text,r.expected_revision::text,r.actor_id," +
  "r.client_mutation_id,r.content_digest,r.document_json,r.created_at," +
  "x.checkpoint_id AS restore_checkpoint_id,x.source_revision::text AS restore_source_revision," +
  "x.source_digest AS restore_source_digest,x.restored_by," +
  "x.client_mutation_id AS restore_mutation_id";
const REVISION_FROM =
  " FROM stt_document_revisions r LEFT JOIN stt_document_restores x " +
  "ON x.project_id=r.project_id AND x.new_revision=r.revision";

export interface DocumentRevisionSummary {
  revision: number;
  expectedRevision: number | null;
  actorId: string;
  clientMutationId: string;
  digest: string;
  createdAt: string;
  restoreOrigin: { checkpointId: string; sourceRevision: number; sourceDigest: string } | null;
}
export interface DocumentHistoryPage {
  projectId: string;
  revisions: readonly DocumentRevisionSummary[];
  /** Exclusive cursor for the next page, or null when fully consumed. */
  nextBeforeRevision: number | null;
}
export interface DocumentRevisionView extends DocumentView {
  attribution: DocumentRevisionSummary;
}
export interface DocumentComparisonView {
  projectId: string;
  from: DocumentRevisionSummary;
  to: DocumentRevisionSummary;
  changes: readonly SemanticChange[];
  totalChanges: number;
  truncated: boolean;
}

export interface CheckpointApproval {
  approvedBy: string;
  approvedAt: string;
}
export interface CheckpointSummary {
  checkpointId: string;
  name: string;
  sourceRevision: number;
  sourceDigest: string;
  documentId: string;
  createdBy: string;
  createdAt: string;
  approval: CheckpointApproval | null;
}
export interface CheckpointView extends CheckpointSummary {
  projectId: string;
  document: ScriptDocumentV2;
}
export interface CheckpointPage {
  projectId: string;
  checkpoints: readonly CheckpointSummary[];
  nextBeforeCheckpointId: string | null;
}
export interface CheckpointCreateReceipt extends Omit<CheckpointView, "approval"> {
  /** Approval is a later independent event, never part of the creation receipt. */
  approval: null;
  clientMutationId: string;
  duplicateDelivery: boolean;
}
export interface CheckpointApprovalReceipt extends CheckpointApproval {
  projectId: string;
  checkpointId: string;
  clientMutationId: string;
  duplicateDelivery: boolean;
}

export interface CreateCheckpointInput {
  checkpointId: string;
  clientMutationId: string;
  name: string;
  sourceRevision: number;
}
export interface ApproveCheckpointInput {
  clientMutationId: string;
}

const MAX_COMPARISON_CHANGES = 200;

export interface CreateProjectInput {
  clientRequestId: string;
  projectId: string;
  title: string;
  document: ScriptDocumentV2;
  settings?: AuthoringProjectSettingsV1;
}
export interface PutDocumentInput {
  expectedRevision: number;
  clientMutationId: string;
  document: ScriptDocumentV2;
  writeSessionId?: string;
}
export interface PutSettingsInput {
  expectedSettingsRevision: number;
  clientMutationId: string;
  settings: AuthoringProjectSettingsV1;
}
export interface PatchProjectInput {
  expectedProjectVersion: number;
  clientMutationId: string;
  title: string;
}
export interface ProjectView {
  projectId: string;
  title: string;
  projectVersion: number;
  linkedResearchProjectIds: readonly string[];
}
export interface DocumentView {
  projectId: string;
  revision: number;
  digest: string;
  document: ScriptDocumentV2;
}
export interface SettingsView {
  projectId: string;
  settingsRevision: number;
  digest: string;
  settings: AuthoringProjectSettingsV1;
}
export interface MutationReceipt {
  projectId: string;
  clientMutationId: string;
  revision: number;
  digest: string;
  duplicateDelivery: boolean;
}

const unavailable = (): ProjectDocumentError =>
  new ProjectDocumentError("service_unavailable", 503);
const missing = (): ProjectDocumentError =>
  new ProjectDocumentError("not_found", 404);
const conflict = (metadata?: Readonly<Record<string, string | number>>): ProjectDocumentError =>
  new ProjectDocumentError("version_conflict", 409, metadata);
const reused = (): ProjectDocumentError =>
  new ProjectDocumentError("idempotency_conflict", 409);

function pgCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    return typeof code === "string" ? code : undefined;
  }
  return undefined;
}

/** Retry *whole* SERIALIZABLE operations only; never retry a genuine stale CAS. */
async function retryTransaction<T>(operation: () => Promise<T>): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof ProjectDocumentError || error instanceof ProjectAuthError) throw error;
      if (error instanceof ProjectSerializationConflictError ||
          pgCode(error) === "40001" || pgCode(error) === "40P01") {
        if (attempt < 2) continue;
        throw unavailable();
      }
      if (pgCode(error) === "23505") {
        throw new ProjectDocumentError("already_exists", 409);
      }
      throw unavailable();
    }
  }
  throw unavailable();
}

function actorId(principal: PrincipalRef): string {
  if (principal.principalKind !== "user") throw new ProjectDocumentInputError("Expected suite user actor.");
  return requireUuid(principal.principalId);
}
function int(value: string): number {
  const number = Number(value);
  if (!Number.isSafeInteger(number)) throw unavailable();
  return number;
}
function viewProject(row: ProjectRow): ProjectView {
  // Research links are deliberately disabled; the schema also rejects nonempty arrays.
  return {
    projectId: row.id,
    title: row.title,
    projectVersion: int(row.project_version),
    linkedResearchProjectIds: row.linked_research_project_ids,
  };
}
function viewDocument(projectId: string, row: HeadRow): DocumentView {
  return { projectId, revision: int(row.revision), digest: row.content_digest,
    document: JSON.parse(row.document_json) as ScriptDocumentV2 };
}
function viewSettings(projectId: string, row: SettingsRow): SettingsView {
  return { projectId, settingsRevision: int(row.settings_revision), digest: row.content_digest,
    settings: JSON.parse(row.settings_json) as AuthoringProjectSettingsV1 };
}

/** Reject corrupted historical bytes, typed documents or provenance; never return partial history. */
function verifiedRevision(projectId: string, row: RevisionRow): DocumentRevisionView {
  if (sha256(row.document_json) !== row.content_digest) throw unavailable();
  let document: ScriptDocumentV2;
  try {
    document = checkedDocument(JSON.parse(row.document_json) as unknown,
      projectId, row.document_id).document;
  } catch {
    throw unavailable();
  }
  const revision = int(row.revision);
  const expectedRevision = row.expected_revision === null ? null : int(row.expected_revision);
  if ((revision === 0 && expectedRevision !== null) ||
      (revision > 0 && expectedRevision !== revision - 1)) throw unavailable();
  let createdAt: string;
  try {
    createdAt = new Date(row.created_at).toISOString();
  } catch {
    throw unavailable();
  }
  let restoreOrigin: DocumentRevisionSummary["restoreOrigin"] = null;
  if (row.restore_checkpoint_id !== null) {
    if (row.restore_source_revision === null || row.restore_source_digest === null ||
        row.restore_source_digest !== row.content_digest || row.restored_by !== row.actor_id ||
        row.restore_mutation_id !== row.client_mutation_id) throw unavailable();
    restoreOrigin = { checkpointId: row.restore_checkpoint_id,
      sourceRevision: int(row.restore_source_revision), sourceDigest: row.restore_source_digest };
  }
  return {
    projectId, revision, digest: row.content_digest, document,
    attribution: { revision, expectedRevision, actorId: row.actor_id,
      clientMutationId: row.client_mutation_id, digest: row.content_digest, createdAt, restoreOrigin },
  };
}

function asIso(value: Date | string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw unavailable();
  return date.toISOString();
}

/** Verify the immutable checkpoint against its immutable source, not just its own hash. */
function verifiedCheckpoint(projectId: string, row: CheckpointRow): CheckpointView {
  const sourceRevision = int(row.source_revision);
  if (row.project_id !== projectId ||
      row.document_id !== row.revision_document_id ||
      row.source_digest !== row.revision_digest ||
      row.document_json !== row.revision_document_json ||
      sha256(row.document_json) !== row.source_digest ||
      row.request_digest !== fingerprint({ kind: "create_checkpoint", projectId,
        checkpointId: row.checkpoint_id, name: row.name, sourceRevision })) throw unavailable();
  let document: ScriptDocumentV2;
  try {
    document = checkedDocument(JSON.parse(row.document_json) as unknown,
      projectId, row.document_id).document;
    requireCheckpointName(row.name);
    requireUuid(row.checkpoint_id);
    requireUuid(row.client_mutation_id);
    requireUuid(row.created_by);
  } catch {
    throw unavailable();
  }
  const approval = row.approved_by === null ? null : {
    approvedBy: row.approved_by, approvedAt: asIso(row.approved_at!),
  };
  if (row.approved_by === null ?
    (row.approval_mutation_id !== null || row.approval_request_digest !== null || row.approved_at !== null) :
    (row.approval_mutation_id === null || row.approved_at === null ||
      row.approval_request_digest !== fingerprint({ kind: "approve_checkpoint", projectId,
        checkpointId: row.checkpoint_id }))) throw unavailable();
  return { projectId, checkpointId: row.checkpoint_id, name: row.name, sourceRevision,
    sourceDigest: row.source_digest, documentId: row.document_id, document,
    createdBy: row.created_by, createdAt: asIso(row.created_at), approval };
}

function checkpointSummary(view: CheckpointView): CheckpointSummary {
  const { checkpointId, name, sourceRevision, sourceDigest, documentId,
    createdBy, createdAt, approval } = view;
  return { checkpointId, name, sourceRevision, sourceDigest, documentId,
    createdBy, createdAt, approval };
}

export class ProjectDocumentService {
  constructor(
    private readonly pool: SqlPool,
    private readonly auth: ProjectAuthorizationService,
  ) {}

  private async transaction<T>(operation: (db: SqlClient) => Promise<T>): Promise<T> {
    return await retryTransaction(async () => {
      const db = await this.pool.connect();
      try {
        await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
        try {
          const result = await operation(db);
          await db.query("COMMIT");
          return result;
        } catch (error) {
          await db.query("ROLLBACK").catch(() => undefined);
          throw error;
        }
      } finally {
        db.release?.();
      }
    });
  }

  private async authorized<T>(
    projectId: string,
    principal: PrincipalRef,
    action: "view_document" | "view_history" | "edit_document" | "manage_settings" |
      "create_checkpoint" | "approve_checkpoint",
    operation: (db: SqlClient, actor: string) => Promise<T>,
    writeSessionId?: string,
  ): Promise<T> {
    return await retryTransaction(async () =>
      await this.auth.withAuthorizedMutation(projectId, principal, action, operation, writeSessionId));
  }

  private async selectProject(db: SqlClient, projectId: string): Promise<ProjectRow> {
    const result = await db.query<ProjectRow>(
      "SELECT id,title,project_version::text,linked_research_project_ids FROM stt_projects WHERE id=$1",
      [projectId],
    );
    const row = result.rows[0];
    if (!row) throw missing();
    return row;
  }

  /** Only call inside a transaction that has already passed view_history authorization. */
  private async selectRevision(db: SqlClient, projectId: string, revision: number): Promise<DocumentRevisionView> {
    const result = await db.query<RevisionRow>(
      "SELECT " + REVISION_COLUMNS + REVISION_FROM + " WHERE r.project_id=$1 AND r.revision=$2",
      [projectId, revision],
    );
    if (!result.rows[0]) throw missing();
    return verifiedRevision(projectId, result.rows[0]);
  }

  private async selectCheckpoint(db: SqlClient, projectId: string, checkpointId: string): Promise<CheckpointView> {
    const result = await db.query<CheckpointRow>(
      "SELECT " + CHECKPOINT_COLUMNS + CHECKPOINT_FROM +
        " WHERE c.project_id=$1 AND c.checkpoint_id=$2",
      [projectId, checkpointId],
    );
    if (!result.rows[0]) throw missing();
    return verifiedCheckpoint(projectId, result.rows[0]);
  }

  /** Mutation IDs are per actor/project across document writes, checkpoints, and approvals. */
  private async assertNoForeignMutation(
    db: SqlClient, projectId: string, actor: string, mutationId: string,
    operation: "create_checkpoint" | "approve_checkpoint" | "edit_document",
  ): Promise<void> {
    if (operation === "edit_document") {
      // Existing independent build consumers can still host document schema
      // 001+comments 002 without the additive history 003 tables. A missing
      // pair means no checkpoint mutation keys can exist; a partial pair is
      // a broken migration and must not silently weaken protection.
      const installed = await db.query<{ checkpoints: boolean; approvals: boolean }>(
        "SELECT to_regclass('stt_document_checkpoints') IS NOT NULL AS checkpoints," +
          " to_regclass('stt_checkpoint_approvals') IS NOT NULL AS approvals",
      );
      const state = installed.rows[0];
      if (!state || state.checkpoints !== state.approvals) throw unavailable();
      if (!state.checkpoints) return;
    }
    const tables = operation === "edit_document" ?
      ["stt_document_checkpoints", "stt_checkpoint_approvals"] :
      ["stt_document_revisions", operation === "create_checkpoint" ?
        "stt_checkpoint_approvals" : "stt_document_checkpoints"];
    for (const table of tables) {
      const actorColumn = table === "stt_document_revisions" ? "actor_id" :
        table === "stt_checkpoint_approvals" ? "approved_by" : "created_by";
      const found = await db.query<{ exists: number }>(
        `SELECT 1 AS exists FROM ${table} WHERE project_id=$1 AND ${actorColumn}=$2 AND client_mutation_id=$3`,
        [projectId, actor, mutationId],
      );
      if (found.rows.length) throw reused();
    }
  }

  async createCheckpoint(
    projectIdInput: string, principal: PrincipalRef, input: CreateCheckpointInput,
  ): Promise<CheckpointCreateReceipt> {
    const projectId = requireUuid(projectIdInput);
    const checkpointId = requireUuid(input.checkpointId);
    const mutationId = requireUuid(input.clientMutationId);
    const name = requireCheckpointName(input.name);
    const sourceRevision = requireRevision(input.sourceRevision);
    const requestDigest = fingerprint({ kind: "create_checkpoint", projectId, checkpointId,
      name, sourceRevision });
    return await this.authorized(projectId, principal, "create_checkpoint", async (db, actor) => {
      await this.assertNoForeignMutation(db, projectId, actor, mutationId, "create_checkpoint");
      const prior = await db.query<{ checkpoint_id: string; request_digest: string }>(
        "SELECT checkpoint_id,request_digest FROM stt_document_checkpoints " +
          "WHERE project_id=$1 AND created_by=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest || prior.rows[0].checkpoint_id !== checkpointId) {
          throw reused();
        }
        const checkpoint = await this.selectCheckpoint(db, projectId, checkpointId);
        return { ...checkpoint, approval: null, clientMutationId: mutationId, duplicateDelivery: true };
      }
      // Re-read immutable source bytes in the authorized transaction; no payload comes from the caller.
      const revision = await db.query<RevisionRow>(
        "SELECT " + REVISION_COLUMNS + REVISION_FROM +
          " WHERE r.project_id=$1 AND r.revision=$2",
        [projectId, sourceRevision],
      );
      if (!revision.rows[0]) throw missing();
      verifiedRevision(projectId, revision.rows[0]);
      const source = revision.rows[0];
      await db.query(
        "INSERT INTO stt_document_checkpoints(project_id,checkpoint_id,name,source_revision," +
          "document_id,document_json,source_digest,created_by,client_mutation_id,request_digest)" +
          " VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
        [projectId, checkpointId, name, sourceRevision, source.document_id,
          source.document_json, source.content_digest, actor, mutationId, requestDigest],
      );
      const checkpoint = await this.selectCheckpoint(db, projectId, checkpointId);
      return { ...checkpoint, approval: null, clientMutationId: mutationId, duplicateDelivery: false };
    });
  }

  async getCheckpoint(
    projectIdInput: string, principal: PrincipalRef, checkpointIdInput: string,
  ): Promise<CheckpointView> {
    const projectId = requireUuid(projectIdInput);
    const checkpointId = requireUuid(checkpointIdInput);
    return await this.authorized(projectId, principal, "view_history", async (db) =>
      await this.selectCheckpoint(db, projectId, checkpointId));
  }

  async listCheckpoints(
    projectIdInput: string, principal: PrincipalRef,
    options: { limit?: number; beforeCheckpointId?: string } = {},
  ): Promise<CheckpointPage> {
    const projectId = requireUuid(projectIdInput);
    const limit = requireHistoryLimit(options.limit ?? 50);
    const before = options.beforeCheckpointId === undefined ? null : requireUuid(options.beforeCheckpointId);
    return await this.authorized(projectId, principal, "view_history", async (db) => {
      const result = await db.query<CheckpointRow>(
        "SELECT " + CHECKPOINT_COLUMNS + CHECKPOINT_FROM +
          " WHERE c.project_id=$1 AND ($2::uuid IS NULL OR c.checkpoint_id < $2::uuid)" +
          " ORDER BY c.checkpoint_id DESC LIMIT $3",
        [projectId, before, limit + 1],
      );
      const checkpoints = result.rows.slice(0, limit)
        .map((row) => checkpointSummary(verifiedCheckpoint(projectId, row)));
      return { projectId, checkpoints, nextBeforeCheckpointId: result.rows.length > limit ?
        (checkpoints[checkpoints.length - 1]?.checkpointId ?? null) : null };
    });
  }

  async approveCheckpoint(
    projectIdInput: string, principal: PrincipalRef,
    checkpointIdInput: string, input: ApproveCheckpointInput,
  ): Promise<CheckpointApprovalReceipt> {
    const projectId = requireUuid(projectIdInput);
    const checkpointId = requireUuid(checkpointIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const requestDigest = fingerprint({ kind: "approve_checkpoint", projectId, checkpointId });
    return await this.authorized(projectId, principal, "approve_checkpoint", async (db, actor) => {
      await this.assertNoForeignMutation(db, projectId, actor, mutationId, "approve_checkpoint");
      const prior = await db.query<{ checkpoint_id: string; request_digest: string; approved_at: Date | string }>(
        "SELECT checkpoint_id,request_digest,approved_at FROM stt_checkpoint_approvals" +
          " WHERE project_id=$1 AND approved_by=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest || prior.rows[0].checkpoint_id !== checkpointId) {
          throw reused();
        }
        await this.selectCheckpoint(db, projectId, checkpointId);
        return { projectId, checkpointId, clientMutationId: mutationId, approvedBy: actor,
          approvedAt: asIso(prior.rows[0].approved_at), duplicateDelivery: true };
      }
      const checkpoint = await this.selectCheckpoint(db, projectId, checkpointId);
      if (checkpoint.approval !== null) throw conflict();
      await db.query(
        "INSERT INTO stt_checkpoint_approvals(project_id,checkpoint_id,approved_by,client_mutation_id,request_digest)" +
          " VALUES($1,$2,$3,$4,$5)",
        [projectId, checkpointId, actor, mutationId, requestDigest],
      );
      const approved = await this.selectCheckpoint(db, projectId, checkpointId);
      if (!approved.approval) throw unavailable();
      return { projectId, checkpointId, clientMutationId: mutationId,
        ...approved.approval, duplicateDelivery: false };
    });
  }

  async listDocumentRevisions(
    projectIdInput: string, principal: PrincipalRef,
    options: { limit?: number; beforeRevision?: number } = {},
  ): Promise<DocumentHistoryPage> {
    const projectId = requireUuid(projectIdInput);
    const limit = requireHistoryLimit(options.limit ?? 50);
    const before = options.beforeRevision === undefined ? null : requireRevision(options.beforeRevision);
    return await this.authorized(projectId, principal, "view_history", async (db) => {
      const result = await db.query<RevisionRow>(
        "SELECT " + REVISION_COLUMNS + REVISION_FROM +
          " WHERE r.project_id=$1 AND ($2::bigint IS NULL OR r.revision < $2)" +
          " ORDER BY r.revision DESC LIMIT $3",
        [projectId, before, limit + 1],
      );
      const revisions = result.rows.slice(0, limit)
        .map((row) => verifiedRevision(projectId, row).attribution);
      return { projectId, revisions, nextBeforeRevision: result.rows.length > limit ?
        (revisions[revisions.length - 1]?.revision ?? null) : null };
    });
  }

  async getDocumentRevision(
    projectIdInput: string, principal: PrincipalRef, revisionInput: number,
  ): Promise<DocumentRevisionView> {
    const projectId = requireUuid(projectIdInput);
    const revision = requireRevision(revisionInput);
    return await this.authorized(projectId, principal, "view_history", async (db) =>
      await this.selectRevision(db, projectId, revision));
  }

  async compareDocumentRevisions(
    projectIdInput: string, principal: PrincipalRef, fromInput: number, toInput: number,
  ): Promise<DocumentComparisonView> {
    const projectId = requireUuid(projectIdInput);
    const fromRevision = requireRevision(fromInput);
    const toRevision = requireRevision(toInput);
    return await this.authorized(projectId, principal, "view_history", async (db) => {
      // Both snapshots are read under the same authorization and SQL snapshot.
      const from = await this.selectRevision(db, projectId, fromRevision);
      const to = fromRevision === toRevision ? from :
        await this.selectRevision(db, projectId, toRevision);
      const allChanges = compareDocuments(from.document, to.document);
      return { projectId, from: from.attribution, to: to.attribution,
        changes: allChanges.slice(0, MAX_COMPARISON_CHANGES),
        totalChanges: allChanges.length, truncated: allChanges.length > MAX_COMPARISON_CHANGES };
    });
  }

  async createProject(principal: PrincipalRef, input: CreateProjectInput): Promise<{
    project: ProjectView; documentRevision: number; documentDigest: string;
    duplicateDelivery: boolean;
  }> {
    const projectId = requireUuid(input.projectId);
    const requestId = requireUuid(input.clientRequestId);
    const title = requireTitle(input.title);
    const document = checkedDocument(input.document, projectId);
    const settings = input.settings === undefined ? undefined : checkedSettings(input.settings, projectId);
    const createDigest = fingerprint({ projectId, title, document: document.document, settings: settings?.settings ?? null });
    const creator = actorId(principal);
    return await this.transaction(async (db) => {
      // Authentication happened before the request reached this transaction.
      // Recheck and lock the actor so a concurrent disable cannot interleave
      // between project insertion and first-Producer provisioning.
      const actor = await db.query<{ disabled_at: string | null }>(
        "SELECT disabled_at FROM vera_identity_actors WHERE id=$1 FOR SHARE", [creator],
      );
      if (!actor.rows[0] || actor.rows[0].disabled_at !== null) {
        throw new ProjectAuthError("action_not_allowed", 403);
      }
      // Unique per authenticated actor, independent of projectId. Replays must
      // be authorized again; the old bootstrap cannot act as a permission grant.
      const prior = await db.query<{ id: string; create_request_digest: string }>(
        "SELECT id,create_request_digest FROM stt_projects " +
          "WHERE created_by=$1 AND client_create_request_id=$2",
        [creator, requestId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].create_request_digest !== createDigest) throw reused();
        await this.auth.authorizeInTransaction(db, prior.rows[0].id, principal, "view_document");
        const project = await this.selectProject(db, prior.rows[0].id);
        const head = await db.query<HeadRow>(
          "SELECT document_id,revision::text,document_json,content_digest FROM stt_document_heads WHERE project_id=$1",
          [project.id],
        );
        if (!head.rows[0]) throw missing();
        return { project: viewProject(project), documentRevision: int(head.rows[0].revision),
          documentDigest: head.rows[0].content_digest, duplicateDelivery: true };
      }
      await db.query(
        "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
          "VALUES($1,$2,$3,$4,$5)",
        [projectId, title, creator, requestId, createDigest],
      );
      await db.query(
        "INSERT INTO stt_document_heads(project_id,document_id,revision,document_json,content_digest,updated_by) " +
          "VALUES($1,$2,0,$3,$4,$5)",
        [projectId, document.document.id, document.documentJson, document.digest, creator],
      );
      await db.query(
        "INSERT INTO stt_document_revisions(project_id,revision,document_id,expected_revision,actor_id," +
          "client_mutation_id,request_digest,content_digest,document_json) " +
          "VALUES($1,0,$2,NULL,$3,$4,$5,$6,$7)",
        [projectId, document.document.id, creator, requestId, createDigest, document.digest, document.documentJson],
      );
      if (settings) {
        await db.query(
          "INSERT INTO stt_project_settings(project_id,settings_id,settings_revision,settings_json,content_digest,updated_by) " +
            "VALUES($1,$2,1,$3,$4,$5)",
          [projectId, settings.settings.id, settings.settingsJson, settings.digest, creator],
        );
        await db.query(
          "INSERT INTO stt_settings_revisions(project_id,settings_revision,settings_id,expected_revision," +
            "actor_id,client_mutation_id,request_digest,content_digest,settings_json) " +
            "VALUES($1,1,$2,NULL,$3,$4,$5,$6,$7)",
          [projectId, settings.settings.id, creator, requestId, createDigest, settings.digest, settings.settingsJson],
        );
      }
      await this.auth.provisionFirstProducerInProjectTransaction(db, projectId, principal);
      const project = await this.selectProject(db, projectId);
      return { project: viewProject(project), documentRevision: 0,
        documentDigest: document.digest, duplicateDelivery: false };
    });
  }

  async getProject(projectIdInput: string, principal: PrincipalRef): Promise<ProjectView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) =>
      viewProject(await this.selectProject(db, projectId)));
  }

  async getDocument(projectIdInput: string, principal: PrincipalRef): Promise<DocumentView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) => {
      const head = await db.query<HeadRow>(
        "SELECT document_id,revision::text,document_json,content_digest " +
          "FROM stt_document_heads WHERE project_id=$1",
        [projectId],
      );
      if (!head.rows[0]) throw missing();
      return viewDocument(projectId, head.rows[0]);
    });
  }

  async getSettings(projectIdInput: string, principal: PrincipalRef): Promise<SettingsView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) => {
      await this.selectProject(db, projectId);
      const head = await db.query<SettingsRow>(
        "SELECT settings_id,settings_revision::text,settings_json,content_digest " +
          "FROM stt_project_settings WHERE project_id=$1",
        [projectId],
      );
      if (!head.rows[0]) throw missing();
      return viewSettings(projectId, head.rows[0]);
    });
  }

  async putDocument(
    projectIdInput: string, principal: PrincipalRef, input: PutDocumentInput,
  ): Promise<MutationReceipt> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedRevision);
    const sessionId = input.writeSessionId === undefined ? undefined : requireUuid(input.writeSessionId);
    const document = checkedDocument(input.document, projectId);
    const requestDigest = fingerprint({ expectedRevision: expected, document: document.document });
    return await this.authorized(projectId, principal, "edit_document", async (db, actor) => {
      await this.assertNoForeignMutation(db, projectId, actor, mutationId, "edit_document");
      const prior = await db.query<MutationRow>(
        "SELECT request_digest,revision::text,content_digest FROM stt_document_revisions " +
          "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { projectId, clientMutationId: mutationId, revision: int(prior.rows[0].revision),
          digest: prior.rows[0].content_digest, duplicateDelivery: true };
      }
      const head = await db.query<HeadRow>(
        "SELECT document_id,revision::text,document_json,content_digest " +
          "FROM stt_document_heads WHERE project_id=$1 FOR UPDATE",
        [projectId],
      );
      const current = head.rows[0];
      if (!current) throw missing();
      // Comment mutations lock this same row before the comment head. Holding
      // it through replacement prevents a comment write from racing the edit.
      if (sha256(current.document_json) !== current.content_digest) throw unavailable();
      let previousDocument: ScriptDocumentV2;
      try {
        previousDocument = checkedDocument(JSON.parse(current.document_json) as unknown,
          projectId, current.document_id).document;
      } catch {
        throw unavailable();
      }
      if (requireUuid(document.document.id) !== requireUuid(current.document_id)) {
        throw new ProjectDocumentInputError("Document ID cannot change.");
      }
      if (int(current.revision) !== expected) {
        throw conflict({ currentRevision: int(current.revision), currentDigest: current.content_digest });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Revision exhausted.");
      const revision = expected + 1;
      await db.query(
        "INSERT INTO stt_document_revisions(project_id,revision,document_id,expected_revision,actor_id," +
          "client_mutation_id,request_digest,content_digest,document_json) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [projectId, revision, current.document_id, expected, actor, mutationId,
          requestDigest, document.digest, document.documentJson],
      );
      const changed = await db.query<{ revision: string }>(
        "UPDATE stt_document_heads SET revision=$3,document_json=$4,content_digest=$5," +
          "updated_by=$6,updated_at=now() WHERE project_id=$1 AND revision=$2 RETURNING revision::text",
        [projectId, expected, revision, document.documentJson, document.digest, actor],
      );
      if (!changed.rows[0]) throw conflict({ currentRevision: expected });
      // Atomic with the head and immutable document revision. Corrupt or stale
      // comment state aborts the entire edit, never leaving skewed heads.
      await reconcileCommentsForDocumentRevision(db, projectId, previousDocument, expected,
        document.document, revision, actor);
      return { projectId, clientMutationId: mutationId, revision,
        digest: document.digest, duplicateDelivery: false };
    }, sessionId);
  }

  async patchProject(
    projectIdInput: string, principal: PrincipalRef, input: PatchProjectInput,
  ): Promise<{ project: ProjectView; clientMutationId: string; duplicateDelivery: boolean }> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedProjectVersion);
    if (!expected) throw new ProjectDocumentInputError("Project version must be positive.");
    const title = requireTitle(input.title);
    const requestDigest = fingerprint({ expectedProjectVersion: expected, title });
    return await this.authorized(projectId, principal, "manage_settings", async (db, actor) => {
      const prior = await db.query<TitleMutationRow>(
        "SELECT request_digest,project_version::text,title FROM stt_project_title_mutations " +
          "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { project: { projectId, title: prior.rows[0].title,
          projectVersion: int(prior.rows[0].project_version), linkedResearchProjectIds: [] },
        clientMutationId: mutationId, duplicateDelivery: true };
      }
      const row = await this.selectProject(db, projectId);
      if (int(row.project_version) !== expected) {
        throw conflict({ currentProjectVersion: int(row.project_version) });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Project version exhausted.");
      const changed = await db.query<{ project_version: string }>(
        "UPDATE stt_projects SET title=$3,project_version=$4,updated_at=now() " +
          "WHERE id=$1 AND project_version=$2 RETURNING project_version::text",
        [projectId, expected, title, expected + 1],
      );
      if (!changed.rows[0]) throw conflict({ currentProjectVersion: expected });
      await db.query(
        "INSERT INTO stt_project_title_mutations(project_id,project_version,expected_project_version," +
          "actor_id,client_mutation_id,request_digest,title) VALUES($1,$2,$3,$4,$5,$6,$7)",
        [projectId, expected + 1, expected, actor, mutationId, requestDigest, title],
      );
      return { project: { ...viewProject(row), title, projectVersion: expected + 1 },
        clientMutationId: mutationId, duplicateDelivery: false };
    });
  }

  async putSettings(
    projectIdInput: string, principal: PrincipalRef, input: PutSettingsInput,
  ): Promise<MutationReceipt> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedSettingsRevision);
    const settings = checkedSettings(input.settings, projectId);
    const requestDigest = fingerprint({ expectedSettingsRevision: expected, settings: settings.settings });
    return await this.authorized(projectId, principal, "manage_settings", async (db, actor) => {
      const prior = await db.query<MutationRow>(
        "SELECT request_digest,settings_revision::text AS revision,content_digest " +
          "FROM stt_settings_revisions WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { projectId, clientMutationId: mutationId, revision: int(prior.rows[0].revision),
          digest: prior.rows[0].content_digest, duplicateDelivery: true };
      }
      await this.selectProject(db, projectId);
      const head = await db.query<SettingsRow>(
        "SELECT settings_id,settings_revision::text,settings_json,content_digest " +
          "FROM stt_project_settings WHERE project_id=$1",
        [projectId],
      );
      const current = head.rows[0];
      const currentRevision = current ? int(current.settings_revision) : 0;
      if (current && requireUuid(settings.settings.id) !== requireUuid(current.settings_id)) {
        throw new ProjectDocumentInputError("Settings ID cannot change.");
      }
      if (currentRevision !== expected) {
        throw conflict({ currentSettingsRevision: currentRevision,
          ...(current ? { currentDigest: current.content_digest } : {}) });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Settings revision exhausted.");
      const revision = expected + 1;
      await db.query(
        "INSERT INTO stt_settings_revisions(project_id,settings_revision,settings_id,expected_revision," +
          "actor_id,client_mutation_id,request_digest,content_digest,settings_json) " +
          "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [projectId, revision, settings.settings.id, expected, actor, mutationId,
          requestDigest, settings.digest, settings.settingsJson],
      );
      if (!current) {
        await db.query(
          "INSERT INTO stt_project_settings(project_id,settings_id,settings_revision," +
            "settings_json,content_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6)",
          [projectId, settings.settings.id, revision, settings.settingsJson, settings.digest, actor],
        );
      } else {
        const changed = await db.query<{ settings_revision: string }>(
          "UPDATE stt_project_settings SET settings_revision=$3,settings_json=$4," +
            "content_digest=$5,updated_by=$6,updated_at=now() WHERE project_id=$1 AND settings_revision=$2 " +
            "RETURNING settings_revision::text",
          [projectId, expected, revision, settings.settingsJson, settings.digest, actor],
        );
        if (!changed.rows[0]) throw conflict({ currentSettingsRevision: expected });
      }
      return { projectId, clientMutationId: mutationId, revision,
        digest: settings.digest, duplicateDelivery: false };
    });
  }
}
