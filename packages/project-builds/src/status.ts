import { randomUUID } from "node:crypto";

import {
  type ProjectAuthorizationService, type SqlClient, type SqlPool,
} from "@vera/project-authorization";

import { type AgentCredentialInput, ProjectAgentAuthenticationService } from "./agent-auth.js";
import { type BuildClock, validProjectUuid } from "./pairing.js";
import {
  appendEvent, BuildServiceError, checkedNow, loadFrozen, retrySerializable, safeNumber,
  stillCurrent, type AcceptedSourceAuthority, type BuildStatus, verifiedPins,
} from "./submission.js";

type UserPrincipal = Parameters<ProjectAuthorizationService["authorizeRequest"]>[1];
const DIGEST = /^sha256:[0-9a-f]{64}$/u;
const STAGE = /^[a-z][a-z0-9_-]{0,63}$/u;
const LEASE_MS = 60_000;

interface DispatchRow {
  status: BuildStatus;
  reason_code: string | null;
  lease_epoch: number | string;
  assigned_agent_id: string | null;
  lease_expires_at: string | Date | null;
}
export interface StageProgress {
  readonly leaseEpoch: number;
  readonly status: "running" | "needs_action" | "waiting_reconcile" | "failed";
  readonly stageKey: string;
  readonly receiptDigest: string | null;
  readonly reasonCode: string | null;
}
export interface VerifiedInspection {
  readonly kind: "synthetic" | "verified_package" | "native_readback";
  readonly stageKey: string;
  readonly receiptDigest: string;
  readonly outputDigest: string;
  readonly verificationDigest: string;
}
/** Trust boundary: a real inspector must *independently* validate stored effects
 * and readback, not simply echo an agent's claims. No inspector = no proof. */
export interface IndependentEvidenceInspector {
  /** Installed by trusted backend infrastructure, never supplied by HTTP.
   * Independently inspect the frozen job, exact target and stored effects;
   * machine reports and native start responses alone are not verification. */
  inspect(db: SqlClient, projectId: string, jobId: string, stageKey: string,
    receiptDigest: string): Promise<VerifiedInspection | null>;
}

function validId(value: unknown): value is string {
  return validProjectUuid(value);
}
function validEpoch(epoch: unknown): epoch is number {
  return typeof epoch === "number" && Number.isSafeInteger(epoch) && epoch > 0;
}
function validReason(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && /^[a-z][a-z0-9_]{0,79}$/u.test(value));
}
function validStage(value: unknown): value is string {
  return typeof value === "string" && STAGE.test(value);
}
function validDigest(value: unknown): value is string {
  return typeof value === "string" && DIGEST.test(value);
}
function invalid(): never { throw new BuildServiceError("invalid_build_request", 400); }

async function dispatchForUpdate(db: SqlClient, projectId: string, jobId: string): Promise<DispatchRow> {
  const row = (await db.query<DispatchRow>(
    "SELECT status,reason_code,lease_epoch,assigned_agent_id,lease_expires_at " +
      "FROM stt_build_dispatches WHERE project_id=$1 AND job_id=$2 FOR UPDATE",
    [projectId, jobId],
  )).rows[0];
  if (!row) throw new BuildServiceError("not_found", 404);
  return row;
}
async function checkSubmitter(db: SqlClient, auth: ProjectAuthorizationService,
  projectId: string, actorId: string, buildClass: "preview" | "release"): Promise<void> {
  await auth.authorizeInTransaction(db, projectId,
    { principalKind: "user", principalId: actorId },
    buildClass === "preview" ? "preview_build" : "release_build");
}
async function checkLease(db: SqlClient, projectId: string, jobId: string,
  agentId: string, epoch: number, now: string): Promise<DispatchRow> {
  const row = await dispatchForUpdate(db, projectId, jobId);
  if (row.assigned_agent_id !== agentId || safeNumber(row.lease_epoch) !== epoch ||
      !["leased", "running"].includes(row.status) || row.lease_expires_at === null ||
      new Date(row.lease_expires_at).getTime() <= new Date(now).getTime()) {
    throw new BuildServiceError("lease_conflict", 409);
  }
  return row;
}

export class ProjectBuildStatusService {
  constructor(
    private readonly pool: SqlPool,
    private readonly auth: ProjectAuthorizationService,
    private readonly agents: ProjectAgentAuthenticationService,
    private readonly sources?: AcceptedSourceAuthority,
    private readonly clock: BuildClock = () => new Date(),
    private readonly evidenceInspector?: IndependentEvidenceInspector,
  ) {}

  /** Scoped discovery only; discovering a job never assigns or authorizes an effect. */
  async pollQueued(input: AgentCredentialInput): Promise<readonly string[]> {
    return await this.agents.withAuthenticatedAgent(input, async (db) => {
      const rows = await db.query<{ job_id: string }>(
        "SELECT job_id FROM stt_build_dispatches WHERE project_id=$1 " +
          "AND status='queued' AND assigned_agent_id IS NULL AND lease_expires_at IS NULL " +
          "ORDER BY updated_at,job_id LIMIT 50",
        [input.projectId],
      );
      return rows.rows.map(({ job_id }) => job_id);
    });
  }

  /** Redacted durable event/evidence readback, authorized on every request. */
  async get(projectId: string, viewer: UserPrincipal, jobId: string) {
    if (!validId(projectId) || !validId(jobId)) return invalid();
    return await this.auth.withAuthorizedMutation(projectId, viewer, "view_build_results", async (db) => {
      const frozen = await loadFrozen(db, projectId, jobId);
      const dispatch = await dispatchForUpdate(db, projectId, jobId);
      // A crashed/offline worker must not appear indefinitely "running" after
      // its transport lease expires. Reconcile once on authorized readback;
      // never re-queue an uncertain stage or discard its earlier receipts.
      const now = checkedNow(this.clock);
      if ((dispatch.status === "leased" || dispatch.status === "running") &&
          dispatch.lease_expires_at !== null &&
          new Date(dispatch.lease_expires_at).getTime() <= new Date(now).getTime()) {
        await db.query(
          "UPDATE stt_build_dispatches SET status='waiting_reconcile'," +
            "reason_code='lease_expired',lease_expires_at=NULL,updated_at=$3 " +
            "WHERE project_id=$1 AND job_id=$2",
          [projectId, jobId, now],
        );
        await appendEvent(db, projectId, jobId, "waiting_reconcile",
          safeNumber(dispatch.lease_epoch), now, "lease_expired", dispatch.assigned_agent_id);
        dispatch.status = "waiting_reconcile";
        dispatch.reason_code = "lease_expired";
      }
      const events = (await db.query<{
        id: string; lease_epoch: string | number; status: BuildStatus;
        stage_key: string | null; evidence_kind: string; receipt_digest: string | null;
        reason_code: string | null;
      }>(
        "SELECT id::text,lease_epoch,status,stage_key,evidence_kind,receipt_digest,reason_code " +
          "FROM stt_build_events WHERE project_id=$1 AND job_id=$2 ORDER BY id",
        [projectId, jobId],
      )).rows.map((event) => ({
        eventId: event.id, leaseEpoch: safeNumber(event.lease_epoch),
        status: event.status, stageKey: event.stage_key,
        evidenceKind: event.evidence_kind, receiptDigest: event.receipt_digest,
        reasonCode: event.reason_code,
      }));
      const evidence = (await db.query<{
        stage_key: string; receipt_digest: string; output_digest: string;
        verification_digest: string; evidence_kind: string;
      }>(
        "SELECT stage_key,receipt_digest,output_digest,verification_digest,evidence_kind " +
          "FROM stt_build_evidence WHERE project_id=$1 AND job_id=$2 ORDER BY created_at,id",
        [projectId, jobId],
      )).rows;
      return {
        jobId, targetId: frozen.row.target_id, buildClass: frozen.row.build_class,
        mode: frozen.row.mode, revision: safeNumber(frozen.row.expected_revision),
        documentDigest: frozen.row.document_digest,
        settingsRevision: safeNumber(frozen.row.settings_revision),
        settingsDigest: frozen.row.settings_digest,
        snapshotDigest: frozen.row.snapshot_digest,
        selectedSources: frozen.pins,
        status: dispatch.status, reasonCode: dispatch.reason_code,
        leaseEpoch: safeNumber(dispatch.lease_epoch), events, evidence,
        // Never return raw stored authoring JSON, local paths, credentials or agent tokens.
      };
    });
  }

  /** Claim gives a bounded *transport* lease only, never permission for native effects. */
  async claim(input: AgentCredentialInput, jobId: string): Promise<{
    jobId: string; leaseEpoch: number; leaseExpiresAt: string; snapshotDigest: string;
  }> {
    if (!validId(input.projectId) || !validId(jobId)) return invalid();
    const outcome = await this.agents.withAuthenticatedAgent(input, async (db, agentId, now) => {
      const projectId = input.projectId as string;
      const frozen = await loadFrozen(db, projectId, jobId);
      const dispatch = await dispatchForUpdate(db, projectId, jobId);
      if (dispatch.status !== "queued" || dispatch.assigned_agent_id !== null ||
          dispatch.lease_expires_at !== null) {
        throw new BuildServiceError("invalid_transition", 409);
      }
      await checkSubmitter(db, this.auth, projectId, frozen.row.submitted_by, frozen.row.build_class);
      const available = await stillCurrent(db, frozen.row);
      const sourcesVerified = available && await verifiedPins(db, projectId, frozen.pins, this.sources);
      if (!available || !sourcesVerified) {
        const status = available ? "blocked" : "stale_snapshot";
        const reason = available ? "source_unverified" : "stale_snapshot";
        await db.query(
          "UPDATE stt_build_dispatches SET status=$3,reason_code=$4,updated_at=$5 " +
            "WHERE project_id=$1 AND job_id=$2",
          [projectId, jobId, status, reason, now],
        );
        await appendEvent(db, projectId, jobId, status, safeNumber(dispatch.lease_epoch), now, reason);
        return { refused: reason } as const;
      }
      const capability = frozen.row.mode === "free" ? "free_package_v1" : "studio_readback_v1";
      const agent = (await db.query<{ capabilities: { supported?: unknown } }>(
        "SELECT capabilities FROM stt_project_build_agents WHERE project_id=$1 AND id=$2",
        [projectId, agentId],
      )).rows[0];
      if (!agent || !Array.isArray(agent.capabilities.supported) ||
          !agent.capabilities.supported.includes(capability)) {
        throw new BuildServiceError("invalid_transition", 409);
      }
      const epoch = safeNumber(dispatch.lease_epoch) + 1;
      const expires = new Date(new Date(now).getTime() + LEASE_MS).toISOString();
      await db.query(
        "UPDATE stt_build_dispatches SET status='leased',reason_code=NULL," +
          "assigned_agent_id=$3,lease_epoch=$4,lease_expires_at=$5,updated_at=$6 " +
          "WHERE project_id=$1 AND job_id=$2 AND status='queued' AND lease_epoch=$7",
        [projectId, jobId, agentId, epoch, expires, now, dispatch.lease_epoch],
      );
      await appendEvent(db, projectId, jobId, "leased", epoch, now, null, agentId);
      return { jobId, leaseEpoch: epoch, leaseExpiresAt: expires,
        snapshotDigest: frozen.row.snapshot_digest };
    });
    if ("refused" in outcome) {
      throw new BuildServiceError(outcome.refused === "stale_snapshot" ? "stale_snapshot" : "source_unverified", 409);
    }
    return outcome;
  }

  /** Private manifest read for the ACTIVE, versioned, scoped transport lease. */
  async frozenForAgent(input: AgentCredentialInput, jobId: string, epoch: number) {
    if (!validId(input.projectId) || !validId(jobId) || !validEpoch(epoch)) return invalid();
    const outcome = await this.agents.withAuthenticatedAgent(input, async (db, agentId, now) => {
      const projectId = input.projectId as string;
      const dispatch = await checkLease(db, projectId, jobId, agentId, epoch, now);
      const frozen = await loadFrozen(db, projectId, jobId);
      await checkSubmitter(db, this.auth, projectId, frozen.row.submitted_by, frozen.row.build_class);
      // Recheck mutable head + selected accepted pins immediately before worker materialization.
      if (!await stillCurrent(db, frozen.row) ||
          !await verifiedPins(db, projectId, frozen.pins, this.sources)) {
        await db.query(
          "UPDATE stt_build_dispatches SET status='stale_snapshot',reason_code='stale_snapshot'," +
            "lease_expires_at=NULL,updated_at=$3 WHERE project_id=$1 AND job_id=$2",
          [projectId, jobId, now],
        );
        await appendEvent(db, projectId, jobId, "stale_snapshot",
          safeNumber(dispatch.lease_epoch), now, "stale_snapshot", agentId);
        return { refused: "stale_snapshot" } as const;
      }
      return {
        jobId, targetId: frozen.row.target_id, projectId,
        documentJson: frozen.row.document_json, documentDigest: frozen.row.document_digest,
        documentRevision: safeNumber(frozen.row.expected_revision),
        settingsJson: frozen.row.settings_json, settingsDigest: frozen.row.settings_digest,
        settingsRevision: safeNumber(frozen.row.settings_revision),
        selectedSources: frozen.pins, snapshotDigest: frozen.row.snapshot_digest,
        buildClass: frozen.row.build_class, mode: frozen.row.mode,
      };
    });
    if ("refused" in outcome) throw new BuildServiceError("stale_snapshot", 409);
    return outcome;
  }

  /** Untrusted agent report remains labeled as untrusted, never verified-native. */
  async appendProgress(input: AgentCredentialInput, jobId: string, report: StageProgress): Promise<string> {
    if (!validId(input.projectId) || !validId(jobId) || !validEpoch(report.leaseEpoch) ||
        !["running", "needs_action", "waiting_reconcile", "failed"].includes(report.status) ||
        !validStage(report.stageKey) ||
        (report.receiptDigest !== null && !validDigest(report.receiptDigest)) ||
        !validReason(report.reasonCode)) return invalid();
    return await this.agents.withAuthenticatedAgent(input, async (db, agentId, now) => {
      const projectId = input.projectId as string;
      const dispatch = await checkLease(db, projectId, jobId, agentId, report.leaseEpoch, now);
      const frozen = await loadFrozen(db, projectId, jobId);
      await checkSubmitter(db, this.auth, projectId, frozen.row.submitted_by, frozen.row.build_class);
      const expires = report.status === "running"
        ? new Date(new Date(now).getTime() + LEASE_MS).toISOString() : null;
      await db.query(
        "UPDATE stt_build_dispatches SET status=$3,reason_code=$4," +
          "lease_expires_at=$5,updated_at=$6 WHERE project_id=$1 AND job_id=$2 AND lease_epoch=$7",
        [projectId, jobId, report.status, report.reasonCode, expires, now, dispatch.lease_epoch],
      );
      return await appendEvent(db, projectId, jobId, report.status, report.leaseEpoch,
        now, report.reasonCode, agentId, report.stageKey, report.receiptDigest);
    });
  }

  /** Independent verifier is mandatory; raw agent attestations cannot upgrade evidence tier. */
  async inspectEvidence(input: AgentCredentialInput, jobId: string, epoch: number,
    stageKey: string, receiptDigest: string): Promise<string> {
    if (!validId(input.projectId) || !validId(jobId) || !validEpoch(epoch) ||
        !validStage(stageKey) || !validDigest(receiptDigest)) return invalid();
    return await this.agents.withAuthenticatedAgent(input, async (db, agentId, now) => {
      const projectId = input.projectId as string;
      await checkLease(db, projectId, jobId, agentId, epoch, now);
      const frozen = await loadFrozen(db, projectId, jobId);
      await checkSubmitter(db, this.auth, projectId, frozen.row.submitted_by, frozen.row.build_class);
      // Revalidate the authority that the local agent was required to retain
      // before every stage. Revoked sources or an advanced head cannot elevate
      // an old untrusted receipt, even if an inspector is installed later.
      if (!await stillCurrent(db, frozen.row)) {
        throw new BuildServiceError("stale_snapshot", 409);
      }
      if (!await verifiedPins(db, projectId, frozen.pins, this.sources)) {
        throw new BuildServiceError("source_unverified", 409);
      }
      if (!this.evidenceInspector) throw new BuildServiceError("invalid_transition", 409);
      const proof = await this.evidenceInspector.inspect(db, projectId, jobId, stageKey, receiptDigest);
      if (!proof || proof.stageKey !== stageKey || proof.receiptDigest !== receiptDigest ||
          !validDigest(proof.outputDigest) || !validDigest(proof.verificationDigest) ||
          !["synthetic", "verified_package", "native_readback"].includes(proof.kind) ||
          (proof.kind === "native_readback" &&
            (frozen.row.mode !== "studio" || stageKey !== "verifying_timeline")) ||
          (proof.kind === "verified_package" && stageKey !== "verifying_import_package")) {
        throw new BuildServiceError("invalid_transition", 409);
      }
      const status: BuildStatus = proof.kind === "verified_package" ? "verified_package" :
        proof.kind === "native_readback" ? "verified_native" : "running";
      const eventId = await appendEvent(db, projectId, jobId, status, epoch, now,
        null, agentId, stageKey, receiptDigest, proof.kind);
      await db.query(
        "INSERT INTO stt_build_evidence(id,project_id,job_id,event_id,stage_key,receipt_digest," +
          "output_digest,evidence_kind,verification_digest,created_at) " +
          "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
        [randomUUID(), projectId, jobId, eventId, stageKey, receiptDigest,
          proof.outputDigest, proof.kind, proof.verificationDigest, now],
      );
      if (status !== "running") {
        await db.query(
          "UPDATE stt_build_dispatches SET status=$3,lease_expires_at=NULL,updated_at=$4 " +
            "WHERE project_id=$1 AND job_id=$2",
          [projectId, jobId, status, now],
        );
      }
      return eventId;
    });
  }

  /** Cancelling leased/running work requires reconciliation, never another native mutation. */
  async cancel(projectId: string, user: UserPrincipal, jobId: string): Promise<BuildStatus> {
    if (!validId(projectId) || !validId(jobId)) return invalid();
    return await retrySerializable(async () =>
      await this.auth.withAuthorizedMutation(projectId, user, "view_build_results", async (db) => {
        const frozen = await loadFrozen(db, projectId, jobId);
        await checkSubmitter(db, this.auth, projectId, frozen.row.submitted_by, frozen.row.build_class);
        await this.auth.authorizeInTransaction(db, projectId, user,
          frozen.row.build_class === "preview" ? "preview_build" : "release_build");
        const dispatch = await dispatchForUpdate(db, projectId, jobId);
        if (!["blocked", "queued", "leased", "running", "needs_action",
          "stale_snapshot", "failed"].includes(dispatch.status)) {
          throw new BuildServiceError("invalid_transition", 409);
        }
        const status: BuildStatus = ["leased", "running"].includes(dispatch.status)
          ? "waiting_reconcile" : "cancelled";
        const now = checkedNow(this.clock);
        await db.query(
          "UPDATE stt_build_dispatches SET status=$3,reason_code=NULL," +
            "lease_expires_at=NULL,updated_at=$4 WHERE project_id=$1 AND job_id=$2",
          [projectId, jobId, status, now],
        );
        await appendEvent(db, projectId, jobId, status, safeNumber(dispatch.lease_epoch), now);
        return status;
      }));
  }
}
