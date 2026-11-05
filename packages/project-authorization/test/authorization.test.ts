import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type { PrincipalRef } from "@vera/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyProjectAuthorizationMigration,
  MIGRATION_DIGEST,
  MIGRATION_NAME,
} from "../src/migration.js";
import { canPerformProjectAction } from "../src/policy.js";
import {
  ProjectAuthorizationService,
  ProjectSerializationConflictError,
  type SqlClient,
  type SqlPool,
} from "../src/service.js";

/* eslint-disable @typescript-eslint/require-await -- Test doubles implement async ports. */

// Each test boots an isolated PGlite WASM database. Cold Linux CI filesystems
// may exceed Vitest's 5s default without any assertion or query failing.
vi.setConfig({ testTimeout: 20_000 });

const PROJECT = "11111111-1111-4111-8111-111111111111";
const OTHER_PROJECT = "22222222-2222-4222-8222-222222222222";
const clients: PGlite[] = [];

async function harness() {
  const db = new PGlite();
  clients.push(db);
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const admin = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "person-admin",
  });
  const editor = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "person-editor",
  });
  const viewer = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "person-viewer",
  });
  await db.query("BEGIN");
  try {
    await auth.provisionFirstProducerInProjectTransaction(db, PROJECT, admin);
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK");
    throw error;
  }
  return { db, auth, admin, editor, viewer };
}
afterEach(async () => {
  for (const db of clients.splice(0)) await db.close();
});

describe("closed project permissions", () => {
  it("never grants Research read through STT membership or a link", () => {
    for (const role of ["producer","editor","viewer","owner",null]) {
      expect(canPerformProjectAction(role, "read_research")).toBe(false);
      expect(canPerformProjectAction(role, "*")).toBe(false);
    }
    expect(canPerformProjectAction("viewer", "view_document")).toBe(true);
    expect(canPerformProjectAction("viewer", "edit_document")).toBe(false);
    expect(canPerformProjectAction("editor", "comment")).toBe(true);
    expect(canPerformProjectAction("editor", "preview_build")).toBe(true);
    expect(canPerformProjectAction("editor", "release_build")).toBe(false);
    expect(canPerformProjectAction("producer", "release_build")).toBe(true);
    expect(canPerformProjectAction("producer", "link_research")).toBe(true);
    expect(canPerformProjectAction("producer", "read_research")).toBe(false);
    expect(canPerformProjectAction(42, "view_document")).toBe(false);
    expect(canPerformProjectAction("viewer", 42)).toBe(false);
  });

  it("reuses stable actor IDs but never infers membership", async () => {
    const { auth, admin, editor } = await harness();
    const again = await auth.resolveActor({
      issuer: "https://suite.example.test", subject: "person-admin",
    });
    expect(again).toEqual(admin);
    await expect(auth.authorizeRequest(PROJECT, editor, "view_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(OTHER_PROJECT, admin, "view_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
  });

  it("grants explicit Editor/Viewer roles, rechecks current DB, and audits actor", async () => {
    const { db, auth, admin, editor, viewer } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await auth.changeMembership(PROJECT, admin, viewer.principalId, "viewer");
    await expect(auth.authorizeRequest(PROJECT, editor, "edit_document"))
      .resolves.toMatchObject({ role: "editor", recheckMode: "every_request" });
    await expect(auth.authorizeRequest(PROJECT, viewer, "view_document"))
      .resolves.toMatchObject({ role: "viewer" });
    await expect(auth.authorizeRequest(PROJECT, viewer, "edit_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(PROJECT, editor, "release_build"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    const audit = await db.query<{actor_id:string;target_actor_id:string}>(
      "SELECT actor_id,target_actor_id FROM vera_project_membership_audit " +
      "WHERE change_kind='grant' ORDER BY occurred_at",
    );
    expect(audit.rows).toHaveLength(2);
    expect(audit.rows.every((r) => r.actor_id === admin.principalId)).toBe(true);
  });

  it("demotion revokes open write sessions and cannot be revived by cached role", async () => {
    const { db, auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    const session = await auth.openWriteSession(PROJECT, editor);
    await auth.authorizeRequest(PROJECT, editor, "edit_document", session);
    await auth.changeMembership(PROJECT, admin, editor.principalId, "viewer");
    await expect(auth.authorizeRequest(PROJECT, editor, "edit_document", session))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(PROJECT, editor, "view_document", session))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    const revoked = await db.query<{revoked_at:string|null}>(
      "SELECT revoked_at FROM vera_project_write_sessions WHERE id=$1", [session],
    );
    expect(revoked.rows[0]?.revoked_at).not.toBeNull();
    await expect(auth.openWriteSession(PROJECT, editor))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    // Re-promotion never validates a previously revoked session.
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await expect(auth.authorizeRequest(PROJECT, editor, "edit_document", session))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    const fresh = await auth.openWriteSession(PROJECT, editor);
    await expect(auth.authorizeRequest(PROJECT, editor, "edit_document", fresh))
      .resolves.toMatchObject({ role: "editor" });
  });

  it("refuses last-Producer removal and forged/unknown principals", async () => {
    const { auth, admin, viewer } = await harness();
    await expect(auth.changeMembership(PROJECT, admin, admin.principalId, null))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.changeMembership(PROJECT, viewer, viewer.principalId, "producer"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    const forged: PrincipalRef = {
      principalKind: "service", principalId: admin.principalId,
    };
    await expect(auth.authorizeRequest(PROJECT, forged, "view_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(PROJECT, admin, "read_research"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(PROJECT, admin, "delete_everything"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
  });

  it("keeps mutation permission and write in one transaction", async () => {
    const { db, auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await auth.withAuthorizedMutation(
      PROJECT, editor, "edit_document", async (client: SqlClient, actorId) => {
        expect(actorId).toBe(editor.principalId);
        await client.query("SELECT $1::uuid", [actorId]);
      },
    );
    await auth.changeMembership(PROJECT, admin, editor.principalId, null);
    let called = false;
    await expect(auth.withAuthorizedMutation(
      PROJECT, editor, "edit_document", async () => {
        called = true;
      },
    )).rejects.toMatchObject({ code: "action_not_allowed" });
    expect(called).toBe(false);
    const count = await db.query<{count:string}>(
      "SELECT count(*)::text AS count FROM vera_project_membership_audit",
    );
    expect(Number(count.rows[0]?.count)).toBeGreaterThan(1);
  });

  it("rolls back downstream writes when the authorized operation fails", async () => {
    const { db, auth, admin, editor } = await harness();
    await db.exec("CREATE TABLE scratch (value text PRIMARY KEY)");
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await expect(auth.withAuthorizedMutation(
      PROJECT, editor, "edit_document", async (client) => {
        await client.query("INSERT INTO scratch(value) VALUES('pending')");
        throw new Error("downstream failure");
      },
    )).rejects.toBeInstanceOf(Error);
    const left = await db.query<{count:string}>(
      "SELECT count(*)::text AS count FROM scratch",
    );
    expect(Number(left.rows[0]?.count)).toBe(0);
  });

  it("fails closed when database cannot be consulted", async () => {
    const broken = new ProjectAuthorizationService({
      connect: async () => { throw new Error("offline"); },
    });
    const actor: PrincipalRef = {
      principalKind: "user", principalId: randomUUID(),
    };
    await expect(broken.authorizeRequest(PROJECT, actor, "view_document"))
      .rejects.toMatchObject({ code: "authorization_unavailable", status: 503 });
    await expect(broken.resolveActor({
      issuer: "https://suite.example.test", subject: "person",
    })).rejects.toMatchObject({ code: "authorization_unavailable", status: 503 });
    const failingQuery = new ProjectAuthorizationService({
      connect: async () => ({
        query: async () => { throw new Error("connection reset"); },
      }),
    });
    await expect(failingQuery.authorizeRequest(PROJECT, actor, "view_document"))
      .rejects.toMatchObject({ code: "authorization_unavailable", status: 503 });
  });

  it("refuses grants to unknown actor IDs instead of a foreign-key failure", async () => {
    const { auth, admin } = await harness();
    await expect(auth.changeMembership(PROJECT, admin, randomUUID(), "editor"))
      .rejects.toMatchObject({ code: "action_not_allowed", status: 403 });
  });

  it("propagates consumer operation errors unchanged from withAuthorizedMutation", async () => {
    const { auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    class DomainError extends Error {
      override readonly name = "DomainError";
    }
    await expect(auth.withAuthorizedMutation(
      PROJECT, editor, "edit_document", async () => {
        throw new DomainError("payload invalid");
      },
    )).rejects.toBeInstanceOf(DomainError);
  });

  it("reports serialization conflicts as a retryable dedicated error", async () => {
    const { db } = await harness();
    const realPool: SqlPool = { connect: async () => db };
    // A client whose COMMIT aborts with PostgreSQL's serialization code.
    const conflicting: SqlPool = {
      connect: async () => {
        const inner = await realPool.connect();
        return {
          query: async <R>(sql: string, parameters?: readonly unknown[]) => {
            if (sql === "COMMIT") {
              const error = new Error("could not serialize access");
              Object.assign(error, { code: "40001" });
              throw error;
            }
            return await inner.query<R>(sql, parameters);
          },
        };
      },
    };
    const service = new ProjectAuthorizationService(conflicting);
    const admin = await service.resolveActor({
      issuer: "https://suite.example.test", subject: "person-admin",
    });
    await expect(service.withAuthorizedMutation(
      PROJECT, admin, "manage_members", async () => undefined,
    )).rejects.toBeInstanceOf(ProjectSerializationConflictError);
  });

  it.each(["40001", "40P01"])(
    "preserves serialization conflicts raised during the locked authorization check (%s)",
    async (code) => {
      const admin: PrincipalRef = {
        principalKind: "user", principalId: randomUUID(),
      };
      const conflicting: SqlPool = {
        connect: async () => ({
          query: async <R>(sql: string) => {
            if (sql.includes("SELECT m.role,m.active,m.version,a.disabled_at")) {
              const error = new Error("could not serialize access during authorization");
              Object.assign(error, { code });
              throw error;
            }
            return { rows: [] as R[] };
          },
        }),
      };
      const service = new ProjectAuthorizationService(conflicting);
      await expect(service.withAuthorizedMutation(
        PROJECT, admin, "manage_members", async () => undefined,
      )).rejects.toBeInstanceOf(ProjectSerializationConflictError);
    },
  );

  it("exposes a same-transaction check for consumer transactions", async () => {
    const { db, auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await db.query("BEGIN");
    const decision = await auth.authorizeInTransaction(
      db, PROJECT, editor, "edit_document",
    );
    expect(decision).toMatchObject({ role: "editor" });
    await db.query("ROLLBACK");
    await expect(auth.authorizeInTransaction(
      db, PROJECT, editor, "release_build",
    )).rejects.toMatchObject({ code: "action_not_allowed" });
  });
});

describe("identity lifecycle", () => {
  it("maps a verified issuer+subject to one immutable actor UUID", async () => {
    const { db, auth, admin } = await harness();
    const again = await auth.resolveActor({
      issuer: "https://suite.example.test", subject: "person-admin",
    });
    const actors = await db.query<{id:string}>(
      "SELECT id FROM vera_identity_actors",
    );
    expect(actors.rows.map((r) => r.id)).toContain(admin.principalId);
    expect(again.principalId).toBe(admin.principalId);
  });

  it("does not merge distinct actors on issuer or subject collision", async () => {
    const { auth, admin } = await harness();
    const sameSubjectOtherIssuer = await auth.resolveActor({
      issuer: "https://other.example.test", subject: "person-admin",
    });
    const sameIssuerOtherSubject = await auth.resolveActor({
      issuer: "https://suite.example.test", subject: "person-admin-2",
    });
    expect(sameSubjectOtherIssuer.principalId)
      .not.toBe(admin.principalId);
    expect(sameIssuerOtherSubject.principalId)
      .not.toBe(admin.principalId);
  });

  it("rejects malformed or non-UUID identity input and project IDs", async () => {
    const { auth, admin } = await harness();
    await expect(auth.resolveActor({ issuer: "", subject: "s" }))
      .rejects.toMatchObject({ code: "authentication_required", status: 401 });
    await expect(auth.resolveActor({ issuer: " padded ", subject: "s" }))
      .rejects.toMatchObject({ code: "authentication_required", status: 401 });
    await expect(auth.authorizeRequest("not-a-uuid", admin, "view_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(
      PROJECT, admin, "view_document", "not-a-uuid",
    )).rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.changeMembership(
      PROJECT, admin, "not-a-uuid", "editor",
    )).rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.changeMembership(
      PROJECT, admin, randomUUID(), "owner" as never,
    )).rejects.toMatchObject({ code: "action_not_allowed" });
  });

  it("refuses disabled identities even if they re-sign in", async () => {
    const { db, auth, admin } = await harness();
    await db.query(
      "UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1",
      [admin.principalId],
    );
    await expect(auth.resolveActor({
      issuer: "https://suite.example.test", subject: "person-admin",
    })).rejects.toMatchObject({ code: "action_not_allowed" });
    await expect(auth.authorizeRequest(PROJECT, admin, "view_document"))
      .rejects.toMatchObject({ code: "action_not_allowed" });
  });

  it("reports a stale open session as a recoverable version conflict", async () => {
    const { db, auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    const session = await auth.openWriteSession(PROJECT, editor);
    // Simulate a version bump that did not revoke this session, e.g. an
    // out-of-band membership write from a future consumer.
    await db.query(
      "UPDATE vera_project_write_sessions SET membership_version=99 WHERE id=$1",
      [session],
    );
    await expect(auth.authorizeRequest(PROJECT, editor, "view_document", session))
      .rejects.toMatchObject({ code: "version_conflict", status: 409 });
  });
});

describe("migration", () => {
  it("is repeatable, digest-checked, and refuses a tampered record", async () => {
    const db = new PGlite();
    clients.push(db);
    await db.waitReady;
    await applyProjectAuthorizationMigration(db);
    await applyProjectAuthorizationMigration(db);
    const recorded = await db.query<{checksum:string;schema_version:number}>(
      "SELECT encode(checksum,'hex') AS checksum,schema_version " +
      "FROM vera_schema_migrations WHERE migration_name=$1",
      [MIGRATION_NAME],
    );
    expect(recorded.rows[0]?.checksum).toBe(MIGRATION_DIGEST);
    expect(Number(recorded.rows[0]?.schema_version)).toBe(1);
    await db.query(
      "UPDATE vera_schema_migrations SET checksum=decode($1,'hex') " +
      "WHERE migration_name=$2",
      ["00".repeat(32), MIGRATION_NAME],
    );
    await expect(applyProjectAuthorizationMigration(db))
      .rejects.toThrow(/checksum mismatch/u);
  });

  it("keeps the membership audit append-only", async () => {
    const { db } = await harness();
    await expect(db.query(
      "UPDATE vera_project_membership_audit SET new_role='editor'",
    )).rejects.toThrow(/append-only/u);
  });
});

describe("notification and session revocation", () => {
  it("emits a membership change notification after commit", async () => {
    const { db, auth, admin, editor } = await harness();
    const received: Array<{ channel: string; payload: string }> = [];
    db.onNotification((channel, payload) => {
      received.push({ channel, payload });
    });
    await db.query("LISTEN vera_membership_changed");
    const version = await auth.changeMembership(
      PROJECT, admin, editor.principalId, "editor",
    );
    // PGlite delivers notifications on a subsequent query on the same
    // connection; poll briefly rather than asserting synchronously.
    for (let attempt = 0; attempt < 20 && received.length === 0; attempt += 1) {
      await db.query("SELECT 1");
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    expect(received).toHaveLength(1);
    expect(received[0]?.channel).toBe("vera_membership_changed");
    expect(JSON.parse(received[0]?.payload ?? "{}")).toMatchObject({
      projectId: PROJECT,
      actorId: editor.principalId,
      version,
    });
  });

  it("closes open write sessions on revoke in the same transaction", async () => {
    const { db, auth, admin, editor } = await harness();
    await auth.changeMembership(PROJECT, admin, editor.principalId, "editor");
    await auth.openWriteSession(PROJECT, editor);
    await auth.changeMembership(PROJECT, admin, editor.principalId, null);
    const open = await db.query<{total:string}>(
      "SELECT count(*)::text AS total FROM vera_project_write_sessions " +
      "WHERE project_id=$1 AND revoked_at IS NULL",
      [PROJECT],
    );
    expect(Number(open.rows[0]?.total)).toBe(0);
  });
});
