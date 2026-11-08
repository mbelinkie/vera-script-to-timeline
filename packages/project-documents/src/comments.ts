import type { PrincipalRef } from "@vera/contracts";
import {
  applyCommentOperationV2,
  createCommentStateV2,
  deserializeCommentStateV2,
  serializeCommentStateV2,
  type CommentStateV2,
  type CommentThreadV2,
} from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  ProjectAuthError,
  ProjectAuthorizationService,
  ProjectSerializationConflictError,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";

import { trustedCommentOperation } from "./comment-input.js";
import {
  checkedDocument,
  fingerprint,
  ProjectDocumentError,
  ProjectDocumentInputError,
  requireRevision,
  requireUuid,
  sha256,
} from "./model.js";

export const MAX_COMMENT_OPERATIONS = 5_000;
const MAX_STATE_BYTES = 8 * 1024 * 1024;

interface DocumentRow {
  document_id: string;
  revision: string;
  document_json: string;
  content_digest: string;
}
interface CommentRow {
  document_id: string;
  document_revision: string;
  comment_revision: string;
  state_json: string;
  state_digest: string;
}
interface EventRow {
  comment_revision: string;
  expected_comment_revision: string;
  document_revision: string;
  request_digest: string;
  operation_json: string;
}

export interface CommentView {
  projectId: string;
  documentRevision: number;
  commentRevision: number;
  threads: CommentThreadV2[];
}
export interface CommentMutationInput {
  expectedCommentRevision: number;
  clientMutationId: string;
  operation: unknown;
}
export interface CommentMutationReceipt {
  projectId: string;
  clientMutationId: string;
  commentRevision: number;
  digest: string;
  duplicateDelivery: boolean;
}

const unavailable = (): ProjectDocumentError => new ProjectDocumentError("service_unavailable", 503);
const missing = (): ProjectDocumentError => new ProjectDocumentError("not_found", 404);
const reused = (): ProjectDocumentError => new ProjectDocumentError("idempotency_conflict", 409);

function safeInt(value: string): number {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 0) throw unavailable();
  return number;
}
function pgCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && "code" in error && typeof error.code === "string") {
    return error.code;
  }
  return undefined;
}
async function retry<T>(work: () => Promise<T>): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await work();
    } catch (error) {
      if (error instanceof ProjectDocumentError || error instanceof ProjectAuthError) throw error;
      if (error instanceof ProjectSerializationConflictError ||
          pgCode(error) === "40001" || pgCode(error) === "40P01") {
        if (attempt < 2) continue;
      }
      throw unavailable();
    }
  }
  throw unavailable();
}

/** The caller must hold the document row lock before accessing a comment head. */
async function readCommentState(
  db: SqlClient, projectId: string, document: ScriptDocumentV2,
  documentRevision: number, lock: "FOR UPDATE" | "FOR SHARE",
): Promise<{ state: CommentStateV2; row: CommentRow | undefined }> {
  const result = await db.query<CommentRow>(
    "SELECT document_id,document_revision::text,comment_revision::text,state_json,state_digest " +
      `FROM stt_comment_heads WHERE project_id=$1 ${lock}`,
    [projectId],
  );
  const row = result.rows[0];
  if (!row) return { state: createCommentStateV2(document), row: undefined };
  if (row.document_id !== document.id || safeInt(row.document_revision) !== documentRevision ||
      Buffer.byteLength(row.state_json, "utf8") > MAX_STATE_BYTES ||
      sha256(row.state_json) !== row.state_digest) throw unavailable();
  let state: CommentStateV2;
  try {
    state = deserializeCommentStateV2(row.state_json);
  } catch {
    throw unavailable();
  }
  if (safeInt(row.comment_revision) !== state.revision || state.history.length > MAX_COMMENT_OPERATIONS ||
      state.document.projectId !== projectId || state.document.id !== document.id ||
      fingerprint(state.document) !== fingerprint(document)) throw unavailable();
  return { state, row };
}

async function persistCommentState(
  db: SqlClient, projectId: string, documentId: string, documentRevision: number,
  previous: CommentRow | undefined, state: CommentStateV2, actorId: string,
): Promise<string> {
  if (state.history.length > MAX_COMMENT_OPERATIONS) {
    throw new ProjectDocumentInputError("Comment history limit exceeded.");
  }
  let json: string;
  try {
    json = serializeCommentStateV2(state);
  } catch {
    throw unavailable();
  }
  if (Buffer.byteLength(json, "utf8") > MAX_STATE_BYTES) {
    throw new ProjectDocumentInputError("Comment state size limit exceeded.");
  }
  const digest = sha256(json);
  if (previous) {
    const updated = await db.query<{ project_id: string }>(
      "UPDATE stt_comment_heads SET document_revision=$3,comment_revision=$4,state_json=$5," +
      "state_digest=$6,updated_by=$7,updated_at=now() " +
      "WHERE project_id=$1 AND document_revision=$2 AND comment_revision=$8 RETURNING project_id",
      [projectId, safeInt(previous.document_revision), documentRevision, state.revision,
        json, digest, actorId, safeInt(previous.comment_revision)],
    );
    if (!updated.rows[0]) throw unavailable();
  } else {
    await db.query(
      "INSERT INTO stt_comment_heads(project_id,document_id,document_revision,comment_revision," +
      "state_json,state_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6,$7)",
      [projectId, documentId, documentRevision, state.revision, json, digest, actorId],
    );
  }
  return digest;
}

/** Called within the document PUT's authorized transaction, with its document head locked.
 * No event row is written for internal document changes.
 */
export async function reconcileCommentsForDocumentRevision(
  db: SqlClient, projectIdInput: string, previousDocument: ScriptDocumentV2,
  previousDocumentRevision: number, nextDocument: ScriptDocumentV2,
  nextDocumentRevision: number, trustedActorId: string,
): Promise<void> {
  const projectId = requireUuid(projectIdInput);
  const actorId = requireUuid(trustedActorId);
  const previousRevision = requireRevision(previousDocumentRevision);
  const nextRevision = requireRevision(nextDocumentRevision);
  if (nextRevision !== previousRevision + 1) throw new ProjectDocumentInputError("Invalid document revision transition.");
  const oldDocument = checkedDocument(previousDocument, projectId).document;
  const newDocument = checkedDocument(nextDocument, projectId, oldDocument.id).document;
  const { state, row } = await readCommentState(db, projectId, oldDocument, previousRevision, "FOR UPDATE");
  if (!row) return;
  if (fingerprint(oldDocument) !== fingerprint(newDocument)) {
    const result = applyCommentOperationV2(state, state.revision, {
      kind: "replace_document", id: `document-revision:${nextRevision}`, actorId, document: newDocument,
    });
    if (!result.ok) throw unavailable();
    await persistCommentState(db, projectId, oldDocument.id, nextRevision, row, result.state, actorId);
  } else {
    // A byte-identical document still increments its storage revision, but the
    // pure anchor engine deliberately rejects a no-op replace_document.
    const result = await db.query<{ project_id: string }>(
      "UPDATE stt_comment_heads SET document_revision=$3,updated_by=$4,updated_at=now() " +
      "WHERE project_id=$1 AND document_revision=$2 AND comment_revision=$5 RETURNING project_id",
      [projectId, previousRevision, nextRevision, actorId, state.revision],
    );
    if (!result.rows[0]) throw unavailable();
  }
}

async function checkedDocumentHead(db: SqlClient, projectId: string, lock: "FOR UPDATE" | "FOR SHARE") {
  const result = await db.query<DocumentRow>(
    "SELECT document_id,revision::text,document_json,content_digest " +
      `FROM stt_document_heads WHERE project_id=$1 ${lock}`,
    [projectId],
  );
  const row = result.rows[0];
  if (!row) throw missing();
  if (sha256(row.document_json) !== row.content_digest) throw unavailable();
  let document: ScriptDocumentV2;
  try {
    document = checkedDocument(JSON.parse(row.document_json) as unknown, projectId, row.document_id).document;
  } catch {
    throw unavailable();
  }
  return { document, revision: safeInt(row.revision) };
}

async function verifyMentions(db: SqlClient, projectId: string, ids: string[]): Promise<void> {
  if (ids.length === 0) return;
  const result = await db.query<{ actor_id: string }>(
    "SELECT m.actor_id FROM vera_project_members m " +
      "JOIN vera_identity_actors a ON a.id=m.actor_id " +
      "WHERE m.project_id=$1 AND m.actor_id=ANY($2::uuid[]) AND m.active=true " +
      "AND a.disabled_at IS NULL FOR SHARE OF m,a",
    [projectId, ids],
  );
  // One indistinguishable refusal for missing, disabled and foreign actors.
  if (result.rows.length !== ids.length) throw new ProjectDocumentInputError("Invalid comment mentions.");
}

/** Authenticated, SERIALIZABLE comment reads and mutations; no build-visible state. */
export class ProjectCommentService {
  constructor(private readonly pool: SqlPool, private readonly auth: ProjectAuthorizationService) {}

  async getComments(projectIdInput: string, principal: PrincipalRef): Promise<CommentView> {
    const projectId = requireUuid(projectIdInput);
    return await retry(async () => await this.auth.withAuthorizedMutation(
      projectId, principal, "view_comments", async (db) => {
        try {
          const head = await checkedDocumentHead(db, projectId, "FOR SHARE");
          const { state } = await readCommentState(db, projectId, head.document, head.revision, "FOR SHARE");
          return { projectId, documentRevision: head.revision, commentRevision: state.revision,
            threads: structuredClone(state.threads) };
        } catch (error) {
          if (error instanceof ProjectDocumentError) throw error;
          // Let the outer retry replay the entire authorized transaction after
          // a SERIALIZABLE write conflict, not disguise it as an outage.
          if (error instanceof ProjectSerializationConflictError ||
              pgCode(error) === "40001" || pgCode(error) === "40P01") throw error;
          throw unavailable();
        }
      },
    ));
  }

  async applyOperation(
    projectIdInput: string, principal: PrincipalRef, input: CommentMutationInput,
  ): Promise<CommentMutationReceipt> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedCommentRevision);
    if (principal.principalKind !== "user") throw new ProjectDocumentInputError("Expected suite user actor.");
    // Parse untrusted payload before any database work, but only stamp the actor
    // from the authorization callback within the committing transaction.
    return await retry(async () => await this.auth.withAuthorizedMutation(
      projectId, principal, "comment", async (db, actor) => {
        const operation = trustedCommentOperation(actor, mutationId, input.operation);
        const requestDigest = fingerprint({ expectedCommentRevision: expected, operation });
        try {
          // The already-existing document row is the deterministic first-writer
          // lock even when there is no comment head yet.
          const doc = await checkedDocumentHead(db, projectId, "FOR UPDATE");
          const { state, row } = await readCommentState(db, projectId, doc.document, doc.revision, "FOR UPDATE");
          const prior = await db.query<EventRow>(
            "SELECT comment_revision::text,expected_comment_revision::text,document_revision::text," +
              "request_digest,operation_json FROM stt_comment_events " +
              "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
            [projectId, actor, mutationId],
          );
          const event = prior.rows[0];
          if (event) {
            if (event.request_digest !== requestDigest) throw reused();
            const revision = safeInt(event.comment_revision);
            const original = state.history[revision - 1];
            if (revision === 0 || safeInt(event.expected_comment_revision) !== expected ||
                safeInt(event.document_revision) > doc.revision ||
                JSON.stringify(original) !== event.operation_json ||
                JSON.stringify(original) !== JSON.stringify(operation)) throw unavailable();
            // Reconstitute the exact original saved-state digest, not the
            // possibly newer comment head digest.
            const historicJson = JSON.stringify({ schemaVersion: "authoring-comments/v1",
              initialDocument: state.initialDocument, operations: state.history.slice(0, revision) });
            return { projectId, clientMutationId: mutationId, commentRevision: revision,
              digest: sha256(historicJson), duplicateDelivery: true };
          }
          if (state.revision !== expected) {
            throw new ProjectDocumentError("version_conflict", 409, { currentCommentRevision: state.revision });
          }
          if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Revision exhausted.");
          if (operation.kind === "create" || operation.kind === "reply") {
            await verifyMentions(db, projectId, operation.mentionActorIds);
          }
          const result = applyCommentOperationV2(state, expected, operation);
          if (!result.ok) throw new ProjectDocumentInputError(result.error);
          const digest = await persistCommentState(
            db, projectId, doc.document.id, doc.revision, row, result.state, actor,
          );
          await db.query(
            "INSERT INTO stt_comment_events(project_id,comment_revision,expected_comment_revision," +
              "document_revision,actor_id,client_mutation_id,request_digest,operation_json) " +
              "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
            [projectId, result.state.revision, expected, doc.revision, actor, mutationId,
              requestDigest, JSON.stringify(operation)],
          );
          return { projectId, clientMutationId: mutationId, commentRevision: result.state.revision,
            digest, duplicateDelivery: false };
        } catch (error) {
          if (error instanceof ProjectDocumentError) throw error;
          // Never swallow PostgreSQL's serialization/deadlock signal here:
          // the bounded retry must obtain a fresh authorized snapshot.
          if (error instanceof ProjectSerializationConflictError ||
              pgCode(error) === "40001" || pgCode(error) === "40P01") throw error;
          throw unavailable();
        }
      },
    ));
  }
}
