import {
  ProjectAuthError,
  type ProjectAuthorizationService,
  type SqlClient, type SqlPool,
} from "@vera/project-authorization";

import {
  AGENT_PROTOCOL_VERSION,
  type BuildClock,
  isAgentToken,
  sameDigest,
  tokenDigest,
  validProjectUuid,
} from "./pairing.js";

export class AgentAuthenticationError extends Error {
  override readonly name = "AgentAuthenticationError";
  readonly code = "agent_authentication_required";
  readonly status = 401;
  constructor() { super("agent_authentication_required"); }
}

interface AgentRow {
  id: string;
  created_by: string;
  credential_digest: string;
  credential_version: string | number;
  protocol_version: string;
  revoked_at: Date | string | null;
}

/** Not a SuiteIdentityPort and never an authorization to edit a project. */
export interface AgentCredentialInput {
  readonly projectId: unknown;
  readonly agentToken: unknown;
  readonly credentialVersion: unknown;
}

export interface AssignedJobNotice {
  readonly jobId: string;
  readonly status: "queued" | "leased" | "running" | "waiting_reconcile";
  readonly leaseEpoch: number;
  readonly leaseExpiresAt: string | null;
}

export class ProjectAgentAuthenticationService {
  constructor(
    private readonly pool: SqlPool,
    private readonly authorization: ProjectAuthorizationService,
    private readonly clock: BuildClock = () => new Date(),
  ) {}

  /** Reauthenticate every call, holding a lock through the scoped operation. */
  private async withAgent<T>(
    input: AgentCredentialInput,
    action: (db: SqlClient, agentId: string, now: string) => Promise<T>,
  ): Promise<T> {
    if (!validProjectUuid(input.projectId) || !isAgentToken(input.agentToken, "sttag_") ||
        typeof input.credentialVersion !== "number" ||
        !Number.isSafeInteger(input.credentialVersion) || input.credentialVersion <= 0) {
      throw new AgentAuthenticationError();
    }
    const digest = tokenDigest(input.agentToken);
    const now = this.clock();
    if (!Number.isFinite(now.getTime())) throw new Error("invalid_service_clock");
    const db = await this.pool.connect();
    try {
      await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      try {
        const rows = await db.query<AgentRow>(
          "SELECT a.id,o.created_by,a.credential_digest,a.credential_version," +
            "a.protocol_version,a.revoked_at " +
            "FROM stt_project_build_agents a " +
            "JOIN stt_build_pairing_offers o ON o.id=a.pairing_offer_id " +
            "AND o.project_id=a.project_id " +
            "WHERE a.project_id=$1 AND a.credential_digest=$2 FOR SHARE OF a",
          [input.projectId, digest],
        );
        const agent = rows.rows[0];
        if (!agent || !sameDigest(digest, agent.credential_digest) ||
            agent.revoked_at !== null || agent.protocol_version !== AGENT_PROTOCOL_VERSION ||
            Number(agent.credential_version) !== input.credentialVersion) {
          throw new AgentAuthenticationError();
        }
        // An old credential cannot preserve authority after issuer role loss.
        // This locks current issuer membership through the whole poll/heartbeat.
        try {
          await this.authorization.authorizeInTransaction(db, input.projectId,
            { principalKind: "user", principalId: agent.created_by }, "manage_settings");
        } catch (error) {
          if (error instanceof ProjectAuthError && error.status === 403) {
            throw new AgentAuthenticationError();
          }
          throw error;
        }
        const result = await action(db, agent.id, now.toISOString());
        await db.query("COMMIT");
        return result;
      } catch (error) {
        await db.query("ROLLBACK").catch(() => undefined);
        throw error;
      }
    } finally {
      db.release?.();
    }
  }

  /** Reconnecting with a current credential needs no new offer or impersonation. */
  async heartbeat(input: AgentCredentialInput): Promise<{
    agentId: string; projectId: string; credentialVersion: number; authenticated: true;
  }> {
    return await this.withAgent(input, async (db, agentId, now) => {
      await db.query(
        "UPDATE stt_project_build_agents SET last_heartbeat_at=$3 " +
          "WHERE project_id=$1 AND id=$2 AND revoked_at IS NULL",
        [input.projectId, agentId, now],
      );
      return {
        agentId, projectId: input.projectId as string,
        credentialVersion: input.credentialVersion as number, authenticated: true as const,
      };
    });
  }

  /** Poll is observational: assignment/epoch claims and stage effects belong to later phases. */
  async pollAssignedJobs(input: AgentCredentialInput): Promise<readonly AssignedJobNotice[]> {
    return await this.withAgent(input, async (db, agentId, now) => {
      const rows = await db.query<{
        job_id: string; status: AssignedJobNotice["status"];
        lease_epoch: number | string; lease_expires_at: Date | string | null;
      }>(
        "SELECT job_id,status,lease_epoch,lease_expires_at FROM stt_build_dispatches " +
          "WHERE project_id=$1 AND assigned_agent_id=$2 " +
          "AND status IN ('queued','leased','running','waiting_reconcile') " +
          "AND (lease_expires_at IS NULL OR lease_expires_at > $3) " +
          "ORDER BY updated_at,job_id LIMIT 50",
        [input.projectId, agentId, now],
      );
      return rows.rows.map((row) => ({
        jobId: row.job_id,
        status: row.status,
        leaseEpoch: Number(row.lease_epoch),
        leaseExpiresAt: row.lease_expires_at === null ? null : new Date(row.lease_expires_at).toISOString(),
      }));
    });
  }
}
