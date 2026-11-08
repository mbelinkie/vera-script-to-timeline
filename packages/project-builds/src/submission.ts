import { randomUUID } from "node:crypto";

import {
  ProjectAuthorizationService, ProjectSerializationConflictError,
  type SqlClient, type SqlPool,
} from "@vera/project-authorization";
import { fingerprint, sha256 } from "@vera/project-documents";

import { buildIntentFingerprint, parseBuildIntent, type BuildIntent, type SourcePin } from "./model.js";
import { type BuildClock, validProjectUuid } from "./pairing.js";

type UserPrincipal = Parameters<ProjectAuthorizationService["authorizeRequest"]>[1];
export type BuildStatus = "blocked" | "queued" | "leased" | "running" | "needs_action" |
  "stale_snapshot" | "waiting_reconcile" | "ready_to_import" | "import_confirmed" |
  "verified_package" | "verified_native" | "refused" | "failed" | "cancelled";

export class BuildServiceError extends Error {
  override readonly name = "BuildServiceError";
  constructor(
    readonly code: "invalid_build_request" | "not_found" | "idempotency_conflict" |
      "stale_snapshot" | "tampered_snapshot" | "settings_unavailable" |
      "source_unverified" | "invalid_transition" | "lease_conflict" | "service_unavailable",
    readonly status: 400 | 404 | 409 | 503,
  ) { super(code); }
}

export interface AcceptedSourceAuthority {
  /** Trusted backend adapter. Must read *accepted*, versioned records using this exact SQL transaction.
   * A user-supplied list, #158 observation or general Research access is NOT an implementation. */
  verifySelected(db: SqlClient, projectId: string, selected: readonly SourcePin[]):
    Promise<readonly SourcePin[] | null>;
}

export interface BuildReceipt {
  readonly jobId: string;
  readonly targetId: string;
  readonly status: BuildStatus;
  readonly reasonCode: "source_unverified" | null;
  readonly duplicateDelivery: boolean;
  readonly snapshotDigest: string;
}

export interface FrozenRow {
  id: string;
  project_id: string;
  target_id: string;
  submitted_by: string;
  request_digest: string;
  build_class: BuildIntent["buildClass"];
  mode: BuildIntent["mode"];
  expected_revision: number | string;
  document_id: string;
  document_json: string;
  document_digest: string;
  settings_revision: number | string;
  settings_json: string;
  settings_digest: string;
  snapshot_digest: string;
}

interface HeadRow {
  document_id: string;
  revision: number | string;
  document_json: string;
  content_digest: string;
}
interface SettingsRow {
  settings_revision: number | string;
  settings_json: string;
  content_digest: string;
}

export function safeNumber(value: number | string): number {
  const n = Number(value);
  if (!Number.isSafeInteger(n) || n < 0) throw new BuildServiceError("tampered_snapshot", 409);
  return n;
}

export function checkedNow(clock: BuildClock): string {
  const now = clock();
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) throw Error("invalid_service_clock");
  return now.toISOString();
}

function validStoredJson(json: string, projectId: string, documentId?: string): boolean {
  try {
    const parsed: unknown = JSON.parse(json);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return false;
    const record = parsed as Record<string, unknown>;
    return validProjectUuid(record.projectId) &&
      record.projectId.toLowerCase() === projectId.toLowerCase() &&
      (documentId === undefined || (validProjectUuid(record.id) &&
        record.id.toLowerCase() === documentId.toLowerCase()));
  } catch { return false; }
}

function verifyStoredBytes(json: string, digest: string, projectId: string, id?: string): void {
  if (sha256(json) !== digest || !validStoredJson(json, projectId, id)) {
    throw new BuildServiceError("tampered_snapshot", 409);
  }
}

/** Never let a mutable or untrusted source selection become a verified source pin. */
export async function verifiedPins(
  db: SqlClient, projectId: string, selected: readonly SourcePin[],
  authority?: AcceptedSourceAuthority,
): Promise<boolean> {
  if (selected.length === 0) return true;
  if (!authority) return false;
  const records = await authority.verifySelected(db, projectId, selected);
  if (!records || records.length !== selected.length) return false;
  const expected = new Map(selected.map((pin) => [pin.sourceId, pin]));
  const seen = new Set<string>();
  for (const record of records) {
    const original = expected.get(record.sourceId);
    if (!original || seen.has(record.sourceId) ||
        original.revision !== record.revision || original.sha256 !== record.sha256) return false;
    seen.add(record.sourceId);
  }
  return seen.size === selected.length;
}

export function snapshotFingerprint(
  row: Pick<FrozenRow, "project_id" | "target_id" | "submitted_by" |
    "build_class" | "mode" | "expected_revision" | "document_id" |
    "document_json" | "document_digest" | "settings_revision" |
    "settings_json" | "settings_digest">,
  pins: readonly SourcePin[],
): string {
  return fingerprint({
    projectId: row.project_id, targetId: row.target_id, submittedBy: row.submitted_by,
    buildClass: row.build_class, mode: row.mode, revision: safeNumber(row.expected_revision),
    documentId: row.document_id, documentJson: row.document_json,
    documentDigest: row.document_digest, settingsRevision: safeNumber(row.settings_revision),
    settingsJson: row.settings_json, settingsDigest: row.settings_digest,
    selectedSources: pins,
  });
}

export async function loadFrozen(db: SqlClient, projectId: string, jobId: string): Promise<{
  row: FrozenRow; pins: SourcePin[];
}> {
  const result = await db.query<FrozenRow>(
    "SELECT id,project_id,target_id,submitted_by,request_digest,build_class,mode," +
      "expected_revision,document_id,document_json,document_digest,settings_revision," +
      "settings_json,settings_digest,snapshot_digest FROM stt_build_submissions " +
      "WHERE project_id=$1 AND id=$2", [projectId, jobId],
  );
  const row = result.rows[0];
  if (!row) throw new BuildServiceError("not_found", 404);
  const pins = (await db.query<{ source_id: string; source_revision: string; source_digest: string }>(
    "SELECT source_id,source_revision,source_digest FROM stt_build_source_pins " +
      "WHERE project_id=$1 AND job_id=$2 ORDER BY source_id",
    [projectId, jobId],
  )).rows.map((pin) => ({
    sourceId: pin.source_id, revision: pin.source_revision, sha256: pin.source_digest,
  }));
  verifyStoredBytes(row.document_json, row.document_digest, projectId, row.document_id);
  verifyStoredBytes(row.settings_json, row.settings_digest, projectId);
  if (snapshotFingerprint(row, pins) !== row.snapshot_digest) {
    throw new BuildServiceError("tampered_snapshot", 409);
  }
  return { row, pins };
}

/** A head edit or changed settings must NOT silently rebase an older frozen job. */
export async function stillCurrent(db: SqlClient, row: FrozenRow): Promise<boolean> {
  const head = (await db.query<HeadRow>(
    "SELECT document_id,revision,document_json,content_digest FROM stt_document_heads " +
      "WHERE project_id=$1", [row.project_id],
  )).rows[0];
  const settings = (await db.query<SettingsRow>(
    "SELECT settings_revision,settings_json,content_digest FROM stt_project_settings " +
      "WHERE project_id=$1", [row.project_id],
  )).rows[0];
  if (!head || !settings) return false;
  verifyStoredBytes(head.document_json, head.content_digest, row.project_id, head.document_id);
  verifyStoredBytes(settings.settings_json, settings.content_digest, row.project_id);
  return head.document_id === row.document_id &&
    safeNumber(head.revision) === safeNumber(row.expected_revision) &&
    head.content_digest === row.document_digest &&
    safeNumber(settings.settings_revision) === safeNumber(row.settings_revision) &&
    settings.content_digest === row.settings_digest;
}

function pgCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && "code" in error) {
    const code: unknown = error.code;
    return typeof code === "string" ? code : undefined;
  }
  return undefined;
}

export async function retrySerializable<T>(callback: () => Promise<T>): Promise<T> {
  for (let n = 0; n < 3; n++) {
    try { return await callback(); } catch (error) {
      if (error instanceof ProjectSerializationConflictError ||
          pgCode(error) === "40001" || pgCode(error) === "40P01") {
        if (n < 2) continue;
        throw new BuildServiceError("service_unavailable", 503);
      }
      throw error;
    }
  }
  throw new BuildServiceError("service_unavailable", 503);
}

export async function appendEvent(
  db: SqlClient, projectId: string, jobId: string, status: BuildStatus,
  epoch: number, now: string, reason: string | null = null, agentId: string | null = null,
  stageKey: string | null = null, receiptDigest: string | null = null,
  evidenceKind: "untrusted_report" | "synthetic" | "verified_package" | "native_readback" = "untrusted_report",
): Promise<string> {
  const event = await db.query<{ id: string }>(
    "INSERT INTO stt_build_events(project_id,job_id,agent_id,lease_epoch,status," +
      "reason_code,stage_key,receipt_digest,created_at,evidence_kind) " +
      "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id::text",
    [projectId, jobId, agentId, epoch, status, reason, stageKey, receiptDigest, now, evidenceKind],
  );
  return event.rows[0]!.id;
}

export class ProjectBuildSubmissionService {
  constructor(
    private readonly pool: SqlPool,
    private readonly authorization: ProjectAuthorizationService,
    private readonly sources?: AcceptedSourceAuthority,
    private readonly clock: BuildClock = () => new Date(),
  ) {}

  async submit(projectInput: string, principal: UserPrincipal, raw: unknown): Promise<BuildReceipt> {
    if (!validProjectUuid(projectInput)) throw new BuildServiceError("invalid_build_request", 400);
    const projectId = projectInput.toLowerCase();
    const intent = parseBuildIntent(raw);
    const requestDigest = buildIntentFingerprint(intent);
    const action = intent.buildClass === "preview" ? "preview_build" : "release_build";
    const outcome = await retrySerializable(async () =>
      await this.authorization.withAuthorizedMutation(projectId, principal, action, async (db, actorId) => {
        // An explicit key is exclusive across accepted jobs and preflight refusals.
        // Lock *before* checking either table; retry the whole SERIALIZABLE
        // transaction when a competing writer changed the initial snapshot.
        await db.query("SELECT pg_advisory_xact_lock(hashtext($1),hashtext($2))",
          [projectId + ":" + actorId, intent.idempotencyKey]);
        // The idempotency comparison precedes head lookup: retrying a previously
        // accepted frozen request never consumes an advanced live head.
        const existing = await db.query<{
          id: string; target_id: string; request_digest: string; snapshot_digest: string;
        }>(
          "SELECT id,target_id,request_digest,snapshot_digest FROM stt_build_submissions " +
            "WHERE project_id=$1 AND submitted_by=$2 AND idempotency_key=$3",
          [projectId, actorId, intent.idempotencyKey],
        );
        const prior = existing.rows[0];
        if (prior) {
          if (prior.request_digest !== requestDigest) {
            throw new BuildServiceError("idempotency_conflict", 409);
          }
          const frozen = await loadFrozen(db, projectId, prior.id);
          const dispatch = (await db.query<{ status: BuildStatus; reason_code: string | null }>(
            "SELECT status,reason_code FROM stt_build_dispatches WHERE job_id=$1 AND project_id=$2",
            [prior.id, projectId],
          )).rows[0];
          if (!dispatch) throw new BuildServiceError("tampered_snapshot", 409);
          return {
            jobId: prior.id, targetId: prior.target_id,
            // The replay is informational, never proof of successful work.
            status: dispatch.status,
            reasonCode: dispatch.reason_code === "source_unverified" ? "source_unverified" as const : null,
            duplicateDelivery: true,
            snapshotDigest: frozen.row.snapshot_digest,
          };
        }
        const refusal = (await db.query<{ request_digest: string; reason_code: string }>(
          "SELECT request_digest,reason_code FROM stt_build_preflight_refusals " +
            "WHERE project_id=$1 AND submitted_by=$2 AND idempotency_key=$3",
          [projectId, actorId, intent.idempotencyKey],
        )).rows[0];
        if (refusal) {
          if (refusal.request_digest !== requestDigest) {
            throw new BuildServiceError("idempotency_conflict", 409);
          }
          return { refused: "settings_unavailable" } as const;
        }
        const head = (await db.query<HeadRow>(
          "SELECT document_id,revision,document_json,content_digest " +
            "FROM stt_document_heads WHERE project_id=$1", [projectId],
        )).rows[0];
        if (!head) throw new BuildServiceError("not_found", 404);
        verifyStoredBytes(head.document_json, head.content_digest, projectId, head.document_id);
        if (safeNumber(head.revision) !== intent.expectedRevision ||
            head.content_digest !== intent.expectedDigest) {
          throw new BuildServiceError("stale_snapshot", 409);
        }
        const settings = (await db.query<SettingsRow>(
          "SELECT settings_revision,settings_json,content_digest " +
            "FROM stt_project_settings WHERE project_id=$1", [projectId],
        )).rows[0];
        // No fake settings or snapshots just to satisfy NOT NULL constraints.
        if (!settings) {
          await db.query(
            "INSERT INTO stt_build_preflight_refusals(project_id,submitted_by,idempotency_key," +
              "request_digest,expected_revision,reason_code,created_at) " +
              "VALUES($1,$2,$3,$4,$5,'settings_unavailable',$6)",
            [projectId, actorId, intent.idempotencyKey, requestDigest,
              intent.expectedRevision, checkedNow(this.clock)],
          );
          return { refused: "settings_unavailable" } as const;
        }
        verifyStoredBytes(settings.settings_json, settings.content_digest, projectId);
        const accepted = await verifiedPins(db, projectId, intent.selectedSources, this.sources);
        const jobId = randomUUID();
        const targetId = randomUUID();
        const now = checkedNow(this.clock);
        const row = {
          project_id: projectId, target_id: targetId, submitted_by: actorId,
          build_class: intent.buildClass, mode: intent.mode,
          expected_revision: intent.expectedRevision, document_id: head.document_id,
          document_json: head.document_json, document_digest: head.content_digest,
          settings_revision: safeNumber(settings.settings_revision),
          settings_json: settings.settings_json, settings_digest: settings.content_digest,
        };
        const snapshotDigest = snapshotFingerprint(row, intent.selectedSources);
        await db.query(
          "INSERT INTO stt_build_submissions(id,project_id,target_id,submitted_by,idempotency_key," +
            "request_digest,build_class,mode,expected_revision,document_id,document_json," +
            "document_digest,settings_revision,settings_json,settings_digest,snapshot_digest,submitted_at) " +
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)",
          [jobId, projectId, targetId, actorId, intent.idempotencyKey, requestDigest,
            row.build_class, row.mode, row.expected_revision, row.document_id, row.document_json,
            row.document_digest, row.settings_revision, row.settings_json,
            row.settings_digest, snapshotDigest, now],
        );
        for (const pin of intent.selectedSources) {
          await db.query(
            "INSERT INTO stt_build_source_pins(project_id,job_id,source_id,source_revision,source_digest) " +
              "VALUES($1,$2,$3,$4,$5)",
            [projectId, jobId, pin.sourceId, pin.revision, pin.sha256],
          );
        }
        const status = accepted ? "queued" as const : "blocked" as const;
        const reasonCode = accepted ? null : "source_unverified" as const;
        await db.query(
          "INSERT INTO stt_build_dispatches(project_id,job_id,status,reason_code,updated_at) " +
            "VALUES($1,$2,$3,$4,$5)",
          [projectId, jobId, status, reasonCode, now],
        );
        await appendEvent(db, projectId, jobId, status, 0, now, reasonCode);
        return { jobId, targetId, status, reasonCode, duplicateDelivery: false, snapshotDigest };
      }));
    if ("refused" in outcome) throw new BuildServiceError("settings_unavailable", 409);
    return outcome;
  }

  /** Only pre-execution source blocks can be retried: failed/uncertain stages may
   * have performed native effects and must remain for explicit reconciliation. */
  async resume(projectInput: string, principal: UserPrincipal, jobId: string): Promise<BuildStatus> {
    if (!validProjectUuid(projectInput) || !validProjectUuid(jobId)) {
      throw new BuildServiceError("invalid_build_request", 400);
    }
    const projectId = projectInput.toLowerCase();
    return await retrySerializable(async () =>
      await this.authorization.withAuthorizedMutation(projectId, principal, "view_build_results",
        async (db) => {
          const frozen = await loadFrozen(db, projectId, jobId);
          // A Viewer can inspect status, but must never dispatch or resume.
          await this.authorization.authorizeInTransaction(db, projectId, principal,
            frozen.row.build_class === "preview" ? "preview_build" : "release_build");
          await this.authorization.authorizeInTransaction(db, projectId,
            { principalKind: "user", principalId: frozen.row.submitted_by },
            frozen.row.build_class === "preview" ? "preview_build" : "release_build");
          const row = (await db.query<{ status: BuildStatus; lease_epoch: number | string }>(
            "SELECT status,lease_epoch FROM stt_build_dispatches " +
              "WHERE project_id=$1 AND job_id=$2 FOR UPDATE", [projectId, jobId],
          )).rows[0];
          if (!row || row.status !== "blocked") {
            throw new BuildServiceError("invalid_transition", 409);
          }
          const current = await stillCurrent(db, frozen.row);
          const verified = current && await verifiedPins(db, projectId, frozen.pins, this.sources);
          const status: BuildStatus = !current ? "stale_snapshot" : verified ? "queued" : "blocked";
          const reason = !current ? "stale_snapshot" : !verified ? "source_unverified" : null;
          const now = checkedNow(this.clock);
          await db.query(
            "UPDATE stt_build_dispatches SET status=$3,reason_code=$4,assigned_agent_id=NULL," +
              "lease_expires_at=NULL,updated_at=$5 WHERE project_id=$1 AND job_id=$2",
            [projectId, jobId, status, reason, now],
          );
          await appendEvent(db, projectId, jobId, status, safeNumber(row.lease_epoch), now, reason);
          return status;
        }));
  }
}
