import { createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";

import {
  ProjectAuthError,
  type ProjectAuthorizationService,
  type SqlPool,
} from "@vera/project-authorization";

type UserPrincipal = Parameters<ProjectAuthorizationService["authorizeRequest"]>[1];

export const AGENT_PROTOCOL_VERSION = "stt-build-agent/v1";
export const PAIRING_TTL_MS = 5 * 60 * 1000;
export const HEARTBEAT_FRESH_MS = 90 * 1000;
export const AGENT_CAPABILITIES = ["free_package_v1", "studio_readback_v1"] as const;
export type AgentCapability = typeof AGENT_CAPABILITIES[number];
export type BuildClock = () => Date;

const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/iu;
const TOKEN = /^(?:stto_|sttag_)[A-Za-z0-9_-]{43}$/u;

export class PairingError extends Error {
  override readonly name = "PairingError";
  constructor(
    readonly code: "invalid_pairing_request" | "pairing_not_available" | "agent_not_available",
    readonly status: 400 | 401 | 404,
  ) { super(code); }
}

export function validProjectUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

export function isAgentToken(value: unknown, prefix: "stto_" | "sttag_"): value is string {
  return typeof value === "string" && value.length === prefix.length + 43 &&
    value.startsWith(prefix) && TOKEN.test(value);
}

/** Hash a high-entropy opaque token; never persist or log its raw value. */
export function tokenDigest(token: string): string {
  return `sha256:${createHash("sha256").update(token, "utf8").digest("hex")}`;
}

/** Compare digests in constant time, including if a stored digest is corrupt. */
export function sameDigest(a: string, b: string): boolean {
  const digestShape = /^sha256:[0-9a-f]{64}$/u;
  if (!digestShape.test(a) || !digestShape.test(b)) return false;
  return timingSafeEqual(Buffer.from(a.slice(7), "hex"), Buffer.from(b.slice(7), "hex"));
}

function issueToken(prefix: "stto_" | "sttag_"): string {
  return prefix + randomBytes(32).toString("base64url");
}

function validLabel(label: unknown): label is string {
  return typeof label === "string" && label.length >= 1 && label.length <= 128 &&
    label.trim() === label && Array.from(label).every((c) => {
      const code = c.charCodeAt(0);
      return code >= 32 && code !== 127;
    });
}

function parseCapabilities(value: unknown): AgentCapability[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > AGENT_CAPABILITIES.length ||
      value.some((cap) => !AGENT_CAPABILITIES.some((allowed) => allowed === cap)) ||
      new Set(value as unknown[]).size !== value.length) {
    throw new PairingError("invalid_pairing_request", 400);
  }
  return value as AgentCapability[];
}

function validClock(now: Date): string {
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) {
    throw new Error("invalid_service_clock");
  }
  return now.toISOString();
}

interface OfferRow {
  id: string;
  created_by: string;
  offer_digest: string;
  protocol_version: string;
  expires_at: string | Date;
  consumed_at: string | Date | null;
  revoked_at: string | Date | null;
}

/** Credentials are delivered only in the immediate successful response. */
export class ProjectAgentPairingService {
  constructor(
    private readonly pool: SqlPool,
    private readonly authorization: ProjectAuthorizationService,
    private readonly clock: BuildClock = () => new Date(),
  ) {}

  async createOffer(projectId: string, producer: UserPrincipal, input: {
    agentLabel: unknown;
    protocolVersion: unknown;
  }): Promise<{ offerId: string; offerToken: string; projectId: string; expiresAt: string }> {
    if (!validProjectUuid(projectId) || !validLabel(input.agentLabel) ||
        input.protocolVersion !== AGENT_PROTOCOL_VERSION) {
      throw new PairingError("invalid_pairing_request", 400);
    }
    const created = this.clock();
    const createdAt = validClock(created);
    const expiresAt = validClock(new Date(created.getTime() + PAIRING_TTL_MS));
    const offerToken = issueToken("stto_");
    const offerId = randomUUID();
    await this.authorization.withAuthorizedMutation(projectId, producer, "manage_settings", async (db, actorId) => {
      await db.query(
        "INSERT INTO stt_build_pairing_offers" +
          "(id,project_id,created_by,offer_digest,agent_label,protocol_version,created_at,expires_at) " +
          "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
        [offerId, projectId, actorId, tokenDigest(offerToken), input.agentLabel,
          AGENT_PROTOCOL_VERSION, createdAt, expiresAt],
      );
    });
    return { offerId, offerToken, projectId, expiresAt };
  }

  /** Atomic one-time consume. No user identity is inferred from the offer. */
  async consumeOffer(input: {
    projectId: unknown;
    offerToken: unknown;
    protocolVersion: unknown;
    capabilities: unknown;
  }): Promise<{ agentId: string; agentToken: string; credentialVersion: number; projectId: string }> {
    if (!validProjectUuid(input.projectId) || !isAgentToken(input.offerToken, "stto_") ||
        input.protocolVersion !== AGENT_PROTOCOL_VERSION) {
      throw new PairingError("invalid_pairing_request", 400);
    }
    const capabilities = parseCapabilities(input.capabilities);
    const now = validClock(this.clock());
    const digest = tokenDigest(input.offerToken);
    const db = await this.pool.connect();
    try {
      await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      try {
        const found = await db.query<OfferRow>(
          "SELECT id,created_by,offer_digest,protocol_version,expires_at,consumed_at,revoked_at " +
            "FROM stt_build_pairing_offers WHERE project_id=$1 AND offer_digest=$2 FOR UPDATE",
          [input.projectId, digest],
        );
        const offer = found.rows[0];
        if (!offer || !sameDigest(digest, offer.offer_digest) ||
            offer.protocol_version !== AGENT_PROTOCOL_VERSION ||
            offer.consumed_at !== null || offer.revoked_at !== null ||
            new Date(offer.expires_at).getTime() <= new Date(now).getTime()) {
          throw new PairingError("pairing_not_available", 401);
        }
        // An issued offer must NOT outlive the producer's current membership.
        // Reuse the canonical #379 row locks under this consume transaction.
        try {
          await this.authorization.authorizeInTransaction(db, input.projectId,
            { principalKind: "user", principalId: offer.created_by }, "manage_settings");
        } catch (error) {
          if (error instanceof ProjectAuthError && error.status === 403) {
            throw new PairingError("pairing_not_available", 401);
          }
          throw error;
        }
        const claimed = await db.query<{ id: string }>(
          "UPDATE stt_build_pairing_offers SET consumed_at=$2 " +
            "WHERE id=$1 AND consumed_at IS NULL AND revoked_at IS NULL " +
            "AND expires_at > $2 RETURNING id",
          [offer.id, now],
        );
        if (claimed.rows.length !== 1) throw new PairingError("pairing_not_available", 401);
        const agentId = randomUUID();
        const agentToken = issueToken("sttag_");
        await db.query(
          "INSERT INTO stt_project_build_agents" +
            "(id,project_id,pairing_offer_id,credential_digest,credential_version," +
            "protocol_version,capabilities,paired_at) VALUES($1,$2,$3,$4,1,$5,$6,$7)",
          [agentId, input.projectId, offer.id, tokenDigest(agentToken),
            AGENT_PROTOCOL_VERSION, JSON.stringify({ supported: capabilities }), now],
        );
        await db.query("COMMIT");
        return { agentId, agentToken, credentialVersion: 1, projectId: input.projectId };
      } catch (error) {
        await db.query("ROLLBACK").catch(() => undefined);
        throw error;
      }
    } finally {
      db.release?.();
    }
  }

  async revokeAgent(projectId: string, producer: UserPrincipal, agentId: string): Promise<void> {
    if (!validProjectUuid(projectId) || !validProjectUuid(agentId)) {
      throw new PairingError("invalid_pairing_request", 400);
    }
    await this.authorization.withAuthorizedMutation(projectId, producer, "manage_settings", async (db) => {
      const changed = await db.query<{ id: string }>(
        "UPDATE stt_project_build_agents SET revoked_at=$3,last_heartbeat_at=NULL " +
          "WHERE project_id=$1 AND id=$2 AND revoked_at IS NULL RETURNING id",
        [projectId, agentId, validClock(this.clock())],
      );
      if (changed.rows.length !== 1) throw new PairingError("agent_not_available", 404);
    });
  }

  /** Cancel a leaked/unwanted offer before it can be consumed. */
  async revokeOffer(projectId: string, producer: UserPrincipal, offerId: string): Promise<void> {
    if (!validProjectUuid(projectId) || !validProjectUuid(offerId)) {
      throw new PairingError("invalid_pairing_request", 400);
    }
    await this.authorization.withAuthorizedMutation(projectId, producer, "manage_settings", async (db) => {
      const changed = await db.query<{ id: string }>(
        "UPDATE stt_build_pairing_offers SET revoked_at=$3 " +
          "WHERE project_id=$1 AND id=$2 AND consumed_at IS NULL AND revoked_at IS NULL RETURNING id",
        [projectId, offerId, validClock(this.clock())],
      );
      if (changed.rows.length !== 1) throw new PairingError("pairing_not_available", 404);
    });
  }

  async rotateAgent(projectId: string, producer: UserPrincipal, agentId: string): Promise<{
    agentId: string; agentToken: string; credentialVersion: number;
  }> {
    if (!validProjectUuid(projectId) || !validProjectUuid(agentId)) {
      throw new PairingError("invalid_pairing_request", 400);
    }
    return await this.authorization.withAuthorizedMutation(projectId, producer, "manage_settings", async (db) => {
      const agentToken = issueToken("sttag_");
      const changed = await db.query<{ credential_version: string | number }>(
        "UPDATE stt_project_build_agents SET credential_digest=$3," +
          "credential_version=credential_version+1,last_heartbeat_at=NULL " +
          "WHERE project_id=$1 AND id=$2 AND revoked_at IS NULL RETURNING credential_version",
        [projectId, agentId, tokenDigest(agentToken)],
      );
      if (changed.rows.length !== 1) throw new PairingError("agent_not_available", 404);
      return { agentId, agentToken, credentialVersion: Number(changed.rows[0]!.credential_version) };
    });
  }

  /** Readiness is advisory, not native verification or build authorization. */
  async readiness(projectId: string, viewer: UserPrincipal): Promise<{
    agents: readonly { agentId: string; protocolVersion: string; connected: boolean; credentialVersion: number }[];
    canBuild: false; nativeVerified: false;
  }> {
    if (!validProjectUuid(projectId)) throw new PairingError("invalid_pairing_request", 400);
    return await this.authorization.withAuthorizedMutation(projectId, viewer, "view_build_results", async (db) => {
      const rows = await db.query<{
        id: string; protocol_version: string; last_heartbeat_at: Date | string | null;
        credential_version: string | number;
      }>(
        "SELECT id,protocol_version,last_heartbeat_at,credential_version " +
          "FROM stt_project_build_agents WHERE project_id=$1 AND revoked_at IS NULL ORDER BY id",
        [projectId],
      );
      const time = this.clock().getTime();
      return {
        agents: rows.rows.map((row) => ({
          agentId: row.id, protocolVersion: row.protocol_version,
          connected: row.last_heartbeat_at !== null &&
            time >= new Date(row.last_heartbeat_at).getTime() &&
            time - new Date(row.last_heartbeat_at).getTime() < HEARTBEAT_FRESH_MS,
          credentialVersion: Number(row.credential_version),
        })),
        canBuild: false as const,
        nativeVerified: false as const,
      };
    });
  }
}
