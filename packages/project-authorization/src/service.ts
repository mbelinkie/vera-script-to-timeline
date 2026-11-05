import { randomUUID } from "node:crypto";

import type { AuthorizationDecisionRef, PrincipalRef } from "@vera/contracts";

import { canPerformProjectAction, type ProjectRole } from "./policy.js";

export interface SqlResult<R> { readonly rows: readonly R[] }
export interface SqlClient {
  query<R = Record<string, unknown>>(
    sql: string, parameters?: readonly unknown[],
  ): Promise<SqlResult<R>>;
  exec?(sql: string): Promise<unknown>;
  release?(): void;
}
export interface SqlPool { connect(): Promise<SqlClient> }

// Implemented by the existing suite identity, NOT by this package.
// Never implement authenticate() by trusting a user-submitted issuer/subject.
export interface SuiteIdentityPort {
  authenticate(request: Request): Promise<{
    readonly issuer: string;
    readonly subject: string;
  }>;
}
export class ProjectAuthError extends Error {
  override readonly name = "ProjectAuthError";
  constructor(
    readonly code: "authentication_required" | "action_not_allowed" |
      "authorization_unavailable" | "version_conflict",
    readonly status: 401 | 403 | 409 | 503,
  ) {
    super(code);
  }
}
// Raised when a SERIALIZABLE transaction is aborted (40001) or a deadlock
// victim is chosen (40P01). Consumers must retry the whole operation with
// bounded attempts and idempotent side effects.
export class ProjectSerializationConflictError extends Error {
  override readonly name = "ProjectSerializationConflictError";
  readonly retryable = true;
  constructor() {
    super("serialization_conflict");
  }
}
const denied = (): ProjectAuthError =>
  new ProjectAuthError("action_not_allowed", 403);
const unavailable = (error: unknown): ProjectAuthError =>
  error instanceof ProjectAuthError ? error :
    new ProjectAuthError("authorization_unavailable", 503);
function isSerializationConflict(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const code = (error as { code?: unknown }).code;
  return code === "40001" || code === "40P01";
}
const UUID = /^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$/u;
function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function validIdentityPart(value: unknown): value is string {
  return typeof value === "string" &&
    value.length > 0 && value.length <= 1024 && value.trim() === value;
}
function userId(principal: PrincipalRef): string {
  if (principal.principalKind !== "user" || !validUuid(principal.principalId)) {
    throw denied();
  }
  return principal.principalId;
}
interface MembershipRow {
  role: ProjectRole;
  active: boolean;
  version: number;
  disabled_at: Date | string | null;
}
interface SessionRow {
  membership_version: number;
  revoked_at: Date | string | null;
}

export class ProjectAuthorizationService {
  constructor(private readonly pool: SqlPool) {}

  // Only pool acquisition failures are wrapped here; work() errors propagate
  // unchanged so consumer operations keep their own error contracts.
  private async withClient<T>(
    work: (db: SqlClient) => Promise<T>,
  ): Promise<T> {
    let db: SqlClient | undefined;
    try {
      db = await this.pool.connect();
    } catch (error) {
      throw unavailable(error);
    }
    try {
      return await work(db);
    } finally {
      db?.release?.();
    }
  }

  // Wraps failures of THIS service's own database work as 503 while letting
  // ProjectAuthError refusals pass through unchanged.
  private async guard<T>(work: () => Promise<T>): Promise<T> {
    try {
      return await work();
    } catch (error) {
      if (error instanceof ProjectSerializationConflictError) throw error;
      if (isSerializationConflict(error)) {
        throw new ProjectSerializationConflictError();
      }
      throw unavailable(error);
    }
  }

  private async transaction<T>(
    work: (db: SqlClient) => Promise<T>,
  ): Promise<T> {
    return await this.withClient(async (db) => {
      try {
        await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      } catch (error) {
        throw unavailable(error);
      }
      try {
        const result = await work(db);
        try {
          await db.query("COMMIT");
        } catch (error) {
          if (isSerializationConflict(error)) {
            throw new ProjectSerializationConflictError();
          }
          throw unavailable(error);
        }
        return result;
      } catch (error) {
        await db.query("ROLLBACK").catch(() => undefined);
        if (isSerializationConflict(error)) {
          throw new ProjectSerializationConflictError();
        }
        throw error;
      }
    });
  }

  // Call ONLY with the trusted SuiteIdentityPort result; never with raw JSON.
  async resolveActor(verified: {
    readonly issuer: string;
    readonly subject: string;
  }): Promise<PrincipalRef> {
    if (!validIdentityPart(verified.issuer) ||
        !validIdentityPart(verified.subject)) {
      throw new ProjectAuthError("authentication_required", 401);
    }
    return await this.withClient(async (db) =>
      await this.guard(async () => {
        const result = await db.query<{ id: string; disabled_at: string | null }>(
          "INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,$2,$3) " +
          "ON CONFLICT(issuer,subject) DO UPDATE SET issuer=EXCLUDED.issuer " +
          "RETURNING id,disabled_at",
          [randomUUID(), verified.issuer, verified.subject],
        );
        const actor = result.rows[0];
        if (!actor || actor.disabled_at !== null) throw denied();
        return { principalKind: "user", principalId: actor.id };
      }));
  }

  async authenticateRequest(
    request: Request,
    identity: SuiteIdentityPort,
  ): Promise<PrincipalRef> {
    let verified: Awaited<ReturnType<SuiteIdentityPort["authenticate"]>>;
    try {
      verified = await identity.authenticate(request);
    } catch {
      throw new ProjectAuthError("authentication_required", 401);
    }
    return await this.resolveActor(verified);
  }

  private async check(
    db: SqlClient,
    projectId: string,
    principal: PrincipalRef,
    action: string,
    sessionId?: string,
    lock = false,
  ): Promise<AuthorizationDecisionRef> {
    if (!validUuid(projectId)) throw denied();
    const actorId = userId(principal);
    const result = await db.query<MembershipRow>(
      "SELECT m.role,m.active,m.version,a.disabled_at FROM vera_project_members m " +
      "JOIN vera_identity_actors a ON a.id=m.actor_id " +
      "WHERE m.project_id=$1 AND m.actor_id=$2" +
      (lock ? " FOR SHARE OF m, a" : ""),
      [projectId, actorId],
    );
    const member = result.rows[0];
    if (!member || member.active !== true ||
        member.disabled_at !== null ||
        !canPerformProjectAction(member.role, action)) throw denied();
    if (sessionId !== undefined) {
      if (!validUuid(sessionId)) throw denied();
      const session = await db.query<SessionRow>(
        "SELECT membership_version,revoked_at FROM vera_project_write_sessions " +
        "WHERE id=$1 AND project_id=$2 AND actor_id=$3" +
        (lock ? " FOR SHARE" : ""),
        [sessionId, projectId, actorId],
      );
      const s = session.rows[0];
      if (!s || s.revoked_at !== null) throw denied();
      if (Number(s.membership_version) !== Number(member.version)) {
        // A real session whose membership changed since it was opened is a
        // recoverable conflict: the client should close it and open a fresh
        // one. Missing or revoked sessions are plain refusals.
        throw new ProjectAuthError("version_conflict", 409);
      }
    }
    return {
      decisionId: randomUUID(),
      action,
      principal,
      projectId,
      role: member.role,
      membershipVersion: Number(member.version),
      decidedAt: new Date().toISOString(),
      recheckMode: "every_request",
    };
  }

  // Structurally implements existing public-page-capture ProjectAuthorizationPort.
  // The API boundary MUST reauthenticate each request before calling this method.
  async authorize(
    projectId: string,
    principal: PrincipalRef,
    action: string,
  ): Promise<AuthorizationDecisionRef> {
    return await this.authorizeRequest(projectId, principal, action);
  }

  async authorizeRequest(
    projectId: string,
    principal: PrincipalRef,
    action: string,
    sessionId?: string,
  ): Promise<AuthorizationDecisionRef> {
    return await this.withClient(async (db) =>
      await this.guard(async () =>
        await this.check(db, projectId, principal, action, sessionId)));
  }

  // Same-transaction variant for consumers whose publish transaction runs on
  // the same PostgreSQL database (e.g. the capture commit flow). The check
  // takes FOR SHARE locks on the membership row inside the caller's
  // transaction, so a concurrent role change serializes after the caller's
  // publish commits instead of racing it.
  async authorizeInTransaction(
    db: SqlClient,
    projectId: string,
    principal: PrincipalRef,
    action: string,
  ): Promise<AuthorizationDecisionRef> {
    return await this.guard(async () =>
      await this.check(db, projectId, principal, action, undefined, true));
  }

  // Every persistence mutation in #380 must use the SAME db transaction.
  // The actor ID is explicit so consumers can stamp immutable attribution.
  // Failures of the consumer operation propagate unchanged; only this
  // service's own database failures become authorization_unavailable (503).
  async withAuthorizedMutation<T>(
    projectId: string,
    principal: PrincipalRef,
    action: string,
    operation: (db: SqlClient, actorId: string) => Promise<T>,
    sessionId?: string,
  ): Promise<T> {
    return await this.transaction(async (db) => {
      await this.guard(async () => {
        await this.check(db, projectId, principal, action, sessionId, true);
      });
      return await operation(db, userId(principal));
    });
  }

  // Trusted internal #380 new-project transaction ONLY. Never expose this
  // as an unauthenticated endpoint or use it against an existing project.
  async provisionFirstProducerInProjectTransaction(
    db: SqlClient,
    projectId: string,
    principal: PrincipalRef,
  ): Promise<void> {
    if (!validUuid(projectId)) throw denied();
    const actorId = userId(principal);
    await this.guard(async () => {
      await db.query("SELECT pg_advisory_xact_lock(hashtext($1))", [projectId]);
      const anyMember = await db.query<{ actor_id: string }>(
        "SELECT actor_id FROM vera_project_members WHERE project_id=$1 LIMIT 1",
        [projectId],
      );
      if (anyMember.rows.length) throw denied();
      await db.query(
        "INSERT INTO vera_project_members(project_id,actor_id,role) " +
        "VALUES($1,$2,'producer')",
        [projectId, actorId],
      );
      await db.query(
        "INSERT INTO vera_project_membership_audit" +
        "(id,project_id,actor_id,target_actor_id,old_role,new_role,change_kind,membership_version) " +
        "VALUES($1,$2,$3,$3,NULL,'producer','bootstrap',1)",
        [randomUUID(), projectId, actorId],
      );
    });
  }

  async openWriteSession(
    projectId: string,
    principal: PrincipalRef,
  ): Promise<string> {
    return await this.transaction(async (db) =>
      await this.guard(async () => {
        const decision = await this.check(
          db, projectId, principal, "edit_document", undefined, true,
        );
        const id = randomUUID();
        await db.query(
          "INSERT INTO vera_project_write_sessions" +
          "(id,project_id,actor_id,membership_version) VALUES($1,$2,$3,$4)",
          // check() always stamps the version; the fallback can never be stored
          // because the column CHECK (membership_version > 0) rejects it.
          [id, projectId, userId(principal), decision.membershipVersion ?? 0],
        );
        return id;
      }));
  }

  async changeMembership(
    projectId: string,
    principal: PrincipalRef,
    targetActorId: string,
    newRole: ProjectRole | null,
  ): Promise<number | null> {
    if (!validUuid(projectId) || !validUuid(targetActorId) ||
        (newRole !== null && !["producer","editor","viewer"].includes(newRole))) {
      throw denied();
    }
    return await this.transaction(async (db) =>
      await this.guard(async () => {
      await db.query("SELECT pg_advisory_xact_lock(hashtext($1))", [projectId]);
      await this.check(db, projectId, principal, "manage_members", undefined, true);
      const prior = await db.query<{
        role: ProjectRole; active: boolean; version: number;
      }>(
        "SELECT role,active,version FROM vera_project_members " +
        "WHERE project_id=$1 AND actor_id=$2 FOR UPDATE",
        [projectId, targetActorId],
      );
      const old = prior.rows[0];
      if ((!old || !old.active) && newRole === null) return null;
      if (old?.active === true && newRole === old.role) {
        return Number(old.version);
      }
      if (!old && newRole !== null) {
        // Granting requires a known actor; an unknown UUID is a refusal, not
        // a foreign-key failure.
        const target = await db.query<{ id: string }>(
          "SELECT id FROM vera_identity_actors WHERE id=$1",
          [targetActorId],
        );
        if (!target.rows[0]) throw denied();
      }
      if (old?.role === "producer" && old.active &&
          newRole !== "producer") {
        const count = await db.query<{ total: string }>(
          "SELECT count(*)::text AS total FROM vera_project_members " +
          "WHERE project_id=$1 AND role='producer' AND active=true",
          [projectId],
        );
        if (Number(count.rows[0]?.total) <= 1) throw denied();
      }
      let version: number;
      if (newRole === null) {
        const result = await db.query<{ version: number }>(
          "UPDATE vera_project_members SET active=false,version=version+1," +
          "changed_at=now() WHERE project_id=$1 AND actor_id=$2 " +
          "RETURNING version",
          [projectId, targetActorId],
        );
        version = Number(result.rows[0]?.version);
      } else {
        const result = await db.query<{ version: number }>(
          "INSERT INTO vera_project_members(project_id,actor_id,role) " +
          "VALUES($1,$2,$3) ON CONFLICT(project_id,actor_id) " +
          "DO UPDATE SET role=EXCLUDED.role,active=true," +
          "version=vera_project_members.version+1,changed_at=now() " +
          "RETURNING version",
          [projectId, targetActorId, newRole],
        );
        version = Number(result.rows[0]?.version);
      }
      // Invalidate already-open editing sessions in the SAME transaction.
      await db.query(
        "UPDATE vera_project_write_sessions SET revoked_at=now() " +
        "WHERE project_id=$1 AND actor_id=$2 AND revoked_at IS NULL",
        [projectId, targetActorId],
      );
      await db.query(
        "INSERT INTO vera_project_membership_audit" +
        "(id,project_id,actor_id,target_actor_id,old_role,new_role," +
        "change_kind,membership_version) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
        [
          randomUUID(), projectId, userId(principal), targetActorId,
          old?.active ? old.role : null, newRole,
          newRole === null ? "revoke" : old?.active ? "change" : "grant",
          version,
        ],
      );
      // PostgreSQL delivers this only after commit; socket gateways LISTEN
      // and close sessions, while DB checks still independently deny them.
      await db.query(
        "SELECT pg_notify('vera_membership_changed', $1)",
        [JSON.stringify({ projectId, actorId: targetActorId, version })],
      );
      return version;
      }));
  }
}
