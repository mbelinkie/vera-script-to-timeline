/** Transactional, occurrence-owned English subtitle copy (no Research network access). */
import { randomUUID } from "node:crypto";

import type { PrincipalRef } from "@vera/contracts";
import {
  approveSubtitleCopyV1, assertValidSubtitleCopyV1, deriveSubtitleCopyV1,
  reviseSubtitleCopyV1, type SubtitleCopyTrackV1,
} from "@vera/contracts/subtitle-copy";
import type { ResearchClipSnapshotV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  ProjectAuthError, ProjectAuthorizationService, ProjectSerializationConflictError,
  type SqlClient, type SqlPool,
} from "@vera/project-authorization";

import {
  checkedDocument, fingerprint, ProjectDocumentError, ProjectDocumentInputError,
  requireHistoryLimit, requireRevision, requireUuid, sha256,
} from "./model.js";
import { enumerateResearchOccurrences } from "./research-choices.js";
import type { ProjectDocumentService } from "./service.js";

export interface SubtitleCopyDeriveInput {
  occurrenceId: string;
  expectedSourceDigest: string;
  expectedDocumentRevision: number;
  expectedDocumentDigest: string;
  clientMutationId: string;
  writeSessionId?: string;
}

export interface SubtitleCopyRevisionInput {
  occurrenceId: string;
  expectedSourceDigest: string;
  expectedVersion: number;
  clientMutationId: string;
  writeSessionId?: string;
}

export interface SubtitleCopyEditInput extends SubtitleCopyRevisionInput {
  englishText: string;
}

export interface SubtitleCopyReceipt {
  projectId: string;
  occurrenceId: string;
  version: number;
  digest: string;
  clientMutationId: string;
  duplicateDelivery: boolean;
}

export interface SubtitleCopyView {
  projectId: string;
  occurrenceId: string;
  documentRevision: number;
  documentDigest: string;
  /** Only describes the Timeline's saved pin, never live Research currency. */
  binding: "not_derived" | "current" | "stale" | "orphan";
  currentSourceDigest: string | null;
  track: SubtitleCopyTrackV1 | null;
  digest: string | null;
}

export interface SubtitleCopyHistoryItem {
  version: number;
  operation: "derive" | "edit" | "approve" | "rederive";
  actorId: string;
  clientMutationId: string;
  createdAt: string;
  digest: string;
  sourceDigest: string;
  track: SubtitleCopyTrackV1;
}

export interface SubtitleCopyHistoryPage {
  projectId: string;
  occurrenceId: string;
  revisions: SubtitleCopyHistoryItem[];
  nextBeforeVersion: number | null;
}

interface DocumentHead {
  document_id: string;
  revision: string;
  document_json: string;
  content_digest: string;
}

interface CopyHead {
  occurrence_id: string;
  track_id: string;
  revision: string;
  source_digest: string;
  content_digest: string;
}

interface CopyRevision {
  occurrence_id: string;
  track_id: string;
  revision: string;
  expected_revision: string;
  operation: SubtitleCopyHistoryItem["operation"];
  actor_id: string;
  client_mutation_id: string;
  request_digest: string;
  source_json: string;
  source_digest: string;
  baseline_english: string;
  track_json: string;
  content_digest: string;
  created_at: Date | string;
}

const digestPattern = /^sha256:[a-f0-9]{64}$/u;
const conflict = (): ProjectDocumentError => new ProjectDocumentError("version_conflict", 409);
const reused = (): ProjectDocumentError => new ProjectDocumentError("idempotency_conflict", 409);
const missing = (): ProjectDocumentError => new ProjectDocumentError("not_found", 404);
const unavailable = (): ProjectDocumentError => new ProjectDocumentError("service_unavailable", 503);
const number = (value: string): number => {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw unavailable();
  return parsed;
};
const digest = (value: string): string => {
  if (typeof value !== "string" || !digestPattern.test(value)) {
    throw new ProjectDocumentInputError("Expected a SHA-256 digest.");
  }
  return value;
};

function verifiedRevision(row: CopyRevision, occurrenceId: string): SubtitleCopyHistoryItem {
  let track: SubtitleCopyTrackV1;
  try {
    const raw: unknown = JSON.parse(row.track_json);
    assertValidSubtitleCopyV1(raw);
    track = raw;
    if (row.occurrence_id !== occurrenceId || track.occurrenceId !== occurrenceId ||
        row.track_id !== track.id || number(row.revision) !== track.version ||
        number(row.expected_revision) !== track.version - 1 ||
        sha256(row.track_json) !== row.content_digest ||
        fingerprint(track.source) !== row.source_digest ||
        JSON.stringify(track.source) !== row.source_json ||
        track.source.englishText !== row.baseline_english ||
        !["derive", "edit", "approve", "rederive"].includes(row.operation) ||
        ((track.version === 1) !== (row.operation === "derive")) ||
        (row.operation === "derive" && track.reviewState !== "needs_review") ||
        (row.operation === "approve" && track.reviewState !== "reviewed") ||
        !digestPattern.test(row.request_digest) ||
        !requireUuid(row.actor_id) || !requireUuid(row.client_mutation_id)) throw unavailable();
  } catch { throw unavailable(); }
  const createdAt = new Date(row.created_at).toISOString();
  return {
    version: track.version, operation: row.operation, actorId: row.actor_id,
    clientMutationId: row.client_mutation_id, createdAt, digest: row.content_digest,
    sourceDigest: row.source_digest, track,
  };
}

/** Rechecks the real document head in the SAME transaction as each copy write. */
async function savedDocument(db: SqlClient, projectId: string, lock: boolean) {
  const rows = await db.query<DocumentHead>(
    "SELECT document_id,revision::text,document_json,content_digest " +
      "FROM stt_document_heads WHERE project_id=$1" + (lock ? " FOR UPDATE" : ""),
    [projectId],
  );
  const row = rows.rows[0];
  if (!row) throw missing();
  if (sha256(row.document_json) !== row.content_digest) throw unavailable();
  let document: ScriptDocumentV2;
  try {
    document = checkedDocument(JSON.parse(row.document_json) as unknown,
      projectId, row.document_id).document;
  } catch { throw unavailable(); }
  return { revision: number(row.revision), digest: row.content_digest, document };
}

function savedPin(document: ScriptDocumentV2, occurrenceId: string): ResearchClipSnapshotV2 | null {
  return enumerateResearchOccurrences(document)
    .find((item) => item.occurrenceId === occurrenceId)?.pinned ?? null;
}

async function headFor(db: SqlClient, projectId: string, occurrenceId: string): Promise<CopyHead | null> {
  const found = await db.query<CopyHead>(
    "SELECT occurrence_id,track_id,revision::text,source_digest,content_digest " +
      "FROM stt_subtitle_copy_heads WHERE project_id=$1 AND occurrence_id=$2",
    [projectId, occurrenceId],
  );
  return found.rows[0] ?? null;
}

async function revisionFor(
  db: SqlClient, projectId: string, occurrenceId: string, version: number,
): Promise<SubtitleCopyHistoryItem> {
  const found = await db.query<CopyRevision>(
    "SELECT occurrence_id,track_id,revision::text,expected_revision::text,operation,actor_id," +
      "client_mutation_id,request_digest,source_json,source_digest,baseline_english," +
      "track_json,content_digest,created_at FROM stt_subtitle_copy_revisions " +
      "WHERE project_id=$1 AND occurrence_id=$2 AND revision=$3",
    [projectId, occurrenceId, version],
  );
  if (!found.rows[0]) throw unavailable();
  return verifiedRevision(found.rows[0], occurrenceId);
}

async function currentCopy(db: SqlClient, projectId: string, occurrenceId: string) {
  const head = await headFor(db, projectId, occurrenceId);
  if (!head) return null;
  const revision = await revisionFor(db, projectId, occurrenceId, number(head.revision));
  if (revision.track.id !== head.track_id || revision.sourceDigest !== head.source_digest ||
      revision.digest !== head.content_digest) throw unavailable();
  return revision;
}

function checkedBase(input: SubtitleCopyRevisionInput) {
  return {
    occurrenceId: requireUuid(input.occurrenceId),
    sourceDigest: digest(input.expectedSourceDigest),
    expected: requireRevision(input.expectedVersion),
    mutationId: requireUuid(input.clientMutationId),
    sessionId: input.writeSessionId === undefined ? undefined : requireUuid(input.writeSessionId),
  };
}

/** Project permissions are separate from Research: only a frozen saved pin is read. */
export class SubtitleCopyService {
  constructor(
    private readonly pool: SqlPool,
    private readonly authorization: ProjectAuthorizationService,
    private readonly documents: ProjectDocumentService,
  ) {}

  private async authorized<T>(
    projectId: string, principal: PrincipalRef, action: "view_document" | "view_history" | "edit_document",
    work: (db: SqlClient, actor: string) => Promise<T>, sessionId?: string,
  ): Promise<T> {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        return await this.authorization.withAuthorizedMutation(projectId, principal, action, work, sessionId);
      } catch (error) {
        if (error instanceof ProjectDocumentError || error instanceof ProjectAuthError) throw error;
        const code = typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
        if (error instanceof ProjectSerializationConflictError || code === "40001" || code === "40P01") {
          if (attempt < 2) continue;
        }
        if (code === "23505") throw conflict();
        throw unavailable();
      }
    }
    throw unavailable();
  }

  async get(projectIdInput: string, principal: PrincipalRef, occurrenceIdInput: string): Promise<SubtitleCopyView> {
    const projectId = requireUuid(projectIdInput), occurrenceId = requireUuid(occurrenceIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) => {
      const doc = await savedDocument(db, projectId, false);
      const pin = savedPin(doc.document, occurrenceId);
      const copy = await currentCopy(db, projectId, occurrenceId);
      if (!copy && !pin) throw missing();
      const currentSourceDigest = pin ? fingerprint(pin) : null;
      return { projectId, occurrenceId, documentRevision: doc.revision, documentDigest: doc.digest,
        binding: !copy ? "not_derived" : !pin ? "orphan" :
          copy.sourceDigest === currentSourceDigest ? "current" : "stale",
        currentSourceDigest, track: copy?.track ?? null, digest: copy?.digest ?? null };
    });
  }

  async history(
    projectIdInput: string, principal: PrincipalRef, occurrenceIdInput: string,
    limitInput = 20, beforeVersionInput?: number,
  ): Promise<SubtitleCopyHistoryPage> {
    const projectId = requireUuid(projectIdInput), occurrenceId = requireUuid(occurrenceIdInput);
    const limit = requireHistoryLimit(limitInput);
    const before = beforeVersionInput === undefined ? null : requireRevision(beforeVersionInput);
    if (before === 0) throw new ProjectDocumentInputError("Invalid subtitle history cursor.");
    return await this.authorized(projectId, principal, "view_history", async (db) => {
      if (!await headFor(db, projectId, occurrenceId)) throw missing();
      const found = await db.query<CopyRevision>(
        "SELECT occurrence_id,track_id,revision::text,expected_revision::text,operation,actor_id," +
          "client_mutation_id,request_digest,source_json,source_digest,baseline_english," +
          "track_json,content_digest,created_at FROM stt_subtitle_copy_revisions " +
          "WHERE project_id=$1 AND occurrence_id=$2 AND ($3::bigint IS NULL OR revision < $3) " +
          "ORDER BY revision DESC LIMIT $4",
        [projectId, occurrenceId, before, limit + 1],
      );
      const revisions = found.rows.slice(0, limit).map((row) => verifiedRevision(row, occurrenceId));
      return { projectId, occurrenceId, revisions,
        nextBeforeVersion: found.rows.length > limit ? revisions.at(-1)!.version : null };
    });
  }

  async derive(
    projectIdInput: string, principal: PrincipalRef, input: SubtitleCopyDeriveInput,
  ): Promise<SubtitleCopyReceipt> {
    const projectId = requireUuid(projectIdInput);
    const expectedDocumentRevision = requireRevision(input.expectedDocumentRevision);
    const expectedDocumentDigest = digest(input.expectedDocumentDigest);
    return await this.write(projectId, principal, "derive", {
      ...input, expectedVersion: 0,
    }, { expectedDocumentRevision, expectedDocumentDigest });
  }

  async edit(projectId: string, principal: PrincipalRef, input: SubtitleCopyEditInput) {
    return await this.write(requireUuid(projectId), principal, "edit", input, undefined, input.englishText);
  }

  async approve(projectId: string, principal: PrincipalRef, input: SubtitleCopyRevisionInput) {
    return await this.write(requireUuid(projectId), principal, "approve", input);
  }

  async rederive(projectId: string, principal: PrincipalRef, input: SubtitleCopyRevisionInput) {
    return await this.write(requireUuid(projectId), principal, "rederive", input);
  }

  private async write(
    projectId: string, principal: PrincipalRef,
    operation: SubtitleCopyHistoryItem["operation"], input: SubtitleCopyRevisionInput,
    creation?: { expectedDocumentRevision: number; expectedDocumentDigest: string }, englishText?: string,
  ): Promise<SubtitleCopyReceipt> {
    const { occurrenceId, sourceDigest, expected, mutationId, sessionId } = checkedBase(input);
    if ((operation === "derive") !== (expected === 0)) throw conflict();
    if (operation === "edit" && typeof englishText !== "string") {
      throw new ProjectDocumentInputError("Expected subtitle English text.");
    }
    const requestDigest = fingerprint({ operation, projectId, occurrenceId,
      expectedSourceDigest: sourceDigest, expectedVersion: expected,
      ...(creation ?? {}), ...(operation === "edit" ? { englishText } : {}) });
    return await this.authorized(projectId, principal, "edit_document", async (db, actor) => {
      await this.documents.assertNoForeignMutation(db, projectId, actor, mutationId, "subtitle_copy");
      // All document writes take this row first. Hold it through checking the
      // binding, prior receipt and the subtitle CAS to prevent retarget races.
      const document = await savedDocument(db, projectId, true);
      const pin = savedPin(document.document, occurrenceId);
      const pinDigest = pin ? fingerprint(pin) : null;
      if (!pin || pinDigest !== sourceDigest) throw conflict();
      const prior = await db.query<CopyRevision>(
        "SELECT occurrence_id,track_id,revision::text,expected_revision::text,operation,actor_id," +
          "client_mutation_id,request_digest,source_json,source_digest,baseline_english," +
          "track_json,content_digest,created_at FROM stt_subtitle_copy_revisions " +
          "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        const replay = verifiedRevision(prior.rows[0], prior.rows[0].occurrence_id);
        return { projectId, occurrenceId: replay.track.occurrenceId, version: replay.version,
          digest: replay.digest, clientMutationId: mutationId, duplicateDelivery: true };
      }
      if (creation && (document.revision !== creation.expectedDocumentRevision ||
          document.digest !== creation.expectedDocumentDigest)) throw conflict();
      const current = await currentCopy(db, projectId, occurrenceId);
      if ((current?.version ?? 0) !== expected) throw conflict();
      if (current && operation !== "rederive" && current.sourceDigest !== pinDigest) throw conflict();
      if (operation === "rederive" && (!current || current.sourceDigest === pinDigest)) throw conflict();
      let track: SubtitleCopyTrackV1;
      try {
        if (operation === "derive") {
          track = deriveSubtitleCopyV1(randomUUID(), occurrenceId, randomUUID(), pin);
        } else if (!current) {
          throw conflict();
        } else if (operation === "edit") {
          track = reviseSubtitleCopyV1(current.track, pin, expected, englishText!, actor);
        } else if (operation === "approve") {
          track = approveSubtitleCopyV1(current.track, pin, expected, actor);
        } else {
          if (current.track.version === Number.MAX_SAFE_INTEGER ||
              current.track.segments[0]!.version === Number.MAX_SAFE_INTEGER) throw conflict();
          const derived = deriveSubtitleCopyV1(current.track.id, occurrenceId,
            current.track.segments[0]!.id, pin);
          derived.version = current.track.version + 1;
          derived.segments[0]!.version = current.track.segments[0]!.version + 1;
          track = derived;
        }
        assertValidSubtitleCopyV1(track);
      } catch (error) {
        if (error instanceof ProjectDocumentError) throw error;
        if (error instanceof RangeError) throw conflict();
        throw unavailable();
      }
      const version = track.version;
      const sourceJson = JSON.stringify(track.source), trackJson = JSON.stringify(track);
      const contentDigest = sha256(trackJson);
      await db.query(
        "INSERT INTO stt_subtitle_copy_revisions(project_id,occurrence_id,track_id,revision," +
          "expected_revision,operation,actor_id,client_mutation_id,request_digest,source_json," +
          "source_digest,baseline_english,track_json,content_digest)" +
          " VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
        [projectId, occurrenceId, track.id, version, expected, operation, actor, mutationId,
          requestDigest, sourceJson, fingerprint(track.source), track.source.englishText, trackJson, contentDigest],
      );
      if (!current) {
        await db.query(
          "INSERT INTO stt_subtitle_copy_heads(project_id,occurrence_id,track_id,revision," +
            "source_digest,content_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6,$7)",
          [projectId, occurrenceId, track.id, version, pinDigest, contentDigest, actor],
        );
      } else {
        const changed = await db.query<{ revision: string }>(
          "UPDATE stt_subtitle_copy_heads SET revision=$4,source_digest=$5,content_digest=$6," +
            "updated_by=$7,updated_at=now() WHERE project_id=$1 AND occurrence_id=$2 " +
            "AND revision=$3 RETURNING revision::text",
          [projectId, occurrenceId, expected, version, pinDigest, contentDigest, actor],
        );
        if (!changed.rows.length) throw conflict();
      }
      return { projectId, occurrenceId, version, digest: contentDigest,
        clientMutationId: mutationId, duplicateDelivery: false };
    }, sessionId);
  }
}
