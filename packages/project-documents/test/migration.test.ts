import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  PROJECT_COMMENTS_MIGRATION,
  PROJECT_COMMENTS_MIGRATION_DIGEST,
  PROJECT_DOCUMENTS_MIGRATION,
} from "../src/migration.js";

// Cold PGlite startup on mounted Linux filesystems can be unusually slow.
vi.setConfig({ testTimeout: 120_000 });
const databases: PGlite[] = [];
async function database() {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  return db;
}
afterEach(async () => {
  for (const db of databases.splice(0)) await db.close();
});

describe("additive STT project schema", () => {
  it("applies after identity migration, is repeatable and rejects tampered checksums", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectDocumentsMigration(db);
    const row = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM vera_schema_migrations WHERE migration_name=$1",
      [PROJECT_DOCUMENTS_MIGRATION],
    );
    expect(row.rows[0]?.n).toBe(1);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["00".repeat(32), PROJECT_DOCUMENTS_MIGRATION]);
    await expect(applyProjectDocumentsMigration(db)).rejects.toThrow("checksum mismatch");
    const stillOne = await db.query<{ n: number }>("SELECT count(*)::integer AS n FROM stt_projects");
    expect(stillOne.rows[0]?.n).toBe(0);
  });

  it("rejects a project with nonempty Research links at the database boundary", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'suite','actor')",
      ["11111111-1111-4111-8111-111111111111"]);
    await expect(db.query(
      "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest," +
        "linked_research_project_ids) VALUES($1,'Test',$2,$3,$4,$5)",
      ["22222222-2222-4222-8222-222222222222", "11111111-1111-4111-8111-111111111111",
        "33333333-3333-4333-8333-333333333333", "sha256:" + "a".repeat(64),
        ["44444444-4444-4444-8444-444444444444"]],
    )).rejects.toThrow();
  });
});

describe("forward-only STT comment schema 002", () => {
  it("runs after 001, records exact SHA/version, and is repeatable without touching 001", async () => {
    const db = await database();
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectDocumentsMigration(db);
    const rows = await db.query<{ migration_name: string; schema_version: number; checksum: string }>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(rows.rows).toHaveLength(2);
    expect(rows.rows.find((row) => row.migration_name === PROJECT_COMMENTS_MIGRATION)).toMatchObject({
      schema_version: 2, checksum: PROJECT_COMMENTS_MIGRATION_DIGEST,
    });
    expect(rows.rows.some((row) => row.migration_name === PROJECT_DOCUMENTS_MIGRATION)).toBe(true);
    const tables = await db.query<{ name: string }>(
      "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'stt_comment_%'",
    );
    expect(tables.rows.map((row) => row.name).sort()).toEqual(["stt_comment_events", "stt_comment_heads"]);
  });

  it("refuses mismatched digest or version without applying another migration", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["00".repeat(32), PROJECT_COMMENTS_MIGRATION]);
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow("checksum mismatch");
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=99 " +
      "WHERE migration_name=$2", [PROJECT_COMMENTS_MIGRATION_DIGEST, PROJECT_COMMENTS_MIGRATION]);
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow("checksum mismatch");
    const result = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_comment_events",
    );
    expect(result.rows[0]?.count).toBe(0);
  });

  it("enforces event uniqueness, revision monotonicity, checksums and append-only triggers", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    const actor = randomUUID();
    const project = randomUUID();
    const request = randomUUID();
    const digest = `sha256:${"a".repeat(64)}`;
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','synthetic')", [actor]);
    await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'Test',$2,$3,$4)", [project, actor, randomUUID(), digest]);
    const headSql = "INSERT INTO stt_comment_heads(project_id,document_id,document_revision,comment_revision," +
      "state_json,state_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6,$7)";
    await db.query(headSql, [project, randomUUID(), 0, 1, "{}", digest, actor]);
    await expect(db.query(headSql, [randomUUID(), randomUUID(), 0, 0, "{}", digest, actor])).rejects.toThrow();
    await expect(db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [project, "invalid"])).rejects.toThrow();
    const eventSql = "INSERT INTO stt_comment_events(project_id,comment_revision,expected_comment_revision," +
      "document_revision,actor_id,client_mutation_id,request_digest,operation_json) " +
      "VALUES($1,$2,$3,0,$4,$5,$6,$7)";
    await db.query(eventSql, [project, 1, 0, actor, request, digest, "{}"]);
    await expect(db.query(eventSql, [project, 3, 0, actor, randomUUID(), digest, "{}"])).rejects.toThrow();
    await expect(db.query(eventSql, [project, 2, 1, actor, request, digest, "{}"])).rejects.toThrow();
    await expect(db.query(eventSql, [project, 2, 1, actor, randomUUID(), "invalid", "{}"])).rejects.toThrow();
    await expect(db.query("UPDATE stt_comment_events SET operation_json='{}' WHERE project_id=$1",
      [project])).rejects.toThrow(/append-only/u);
    await expect(db.query("DELETE FROM stt_comment_events WHERE project_id=$1", [project]))
      .rejects.toThrow(/append-only/u);
    const history = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_comment_events WHERE project_id=$1", [project],
    );
    expect(history.rows[0]?.count).toBe(1);
  });
});
