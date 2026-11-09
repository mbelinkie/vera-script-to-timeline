import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyIdeasV1 } from "../src/ideas-model.js";
import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectIdeasMigration,
  PROJECT_IDEAS_MIGRATION,
  PROJECT_IDEAS_MIGRATION_DIGEST,
} from "../src/migration.js";
import { sha256 } from "../src/model.js";

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

async function existingDocuments(db: PGlite) {
  await applyProjectDocumentsMigration(db);
  await applyProjectCommentsMigration(db);
  await applyProjectHistoryMigration(db);
}

async function existingProject(db: PGlite) {
  const actor = randomUUID(), project = randomUUID(), document = randomUUID(), digest = sha256("{}");
  await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','idea-actor')", [actor]);
  await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
    "VALUES($1,'Ideas',$2,$3,$4)", [project, actor, randomUUID(), digest]);
  await db.query("INSERT INTO stt_document_heads(project_id,document_id,revision,document_json,content_digest,updated_by) " +
    "VALUES($1,$2,0,'{}',$3,$4)", [project, document, digest, actor]);
  return { actor, project, document };
}

describe("forward-only Ideas sidecar migration", () => {
  it("needs project storage, then installs once with independent checksum/version/receipt", async () => {
    const db = await database();
    await expect(applyProjectIdeasMigration(db)).rejects.toThrow();
    const missing = await db.query<{ count: number }>(
      "SELECT count(*)::int AS count FROM vera_schema_migrations WHERE migration_name=$1", [PROJECT_IDEAS_MIGRATION]);
    expect(missing.rows[0]?.count).toBe(0);
    await existingDocuments(db);
    await applyProjectIdeasMigration(db);
    const before = await db.query<{ migration_name: string; schema_version: number; checksum: string }>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(before.rows).toHaveLength(4);
    expect(before.rows.find((row) => row.migration_name === PROJECT_IDEAS_MIGRATION)).toEqual({
      migration_name: PROJECT_IDEAS_MIGRATION, schema_version: 4, checksum: PROJECT_IDEAS_MIGRATION_DIGEST,
    });
    await applyProjectIdeasMigration(db);
    const after = await db.query<typeof before.rows[number]>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(after.rows).toEqual(before.rows);
    const tables = await db.query<{ name: string }>(
      "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' " +
      "AND tablename IN ('stt_idea_heads','stt_idea_revisions','stt_ideas_mutation_receipts')",
    );
    expect(tables.rows.map(({ name }) => name).sort()).toEqual([
      "stt_idea_heads", "stt_idea_revisions", "stt_ideas_mutation_receipts",
    ]);
  });

  it("rejects checksum/version tampering and leaves retained rows intact", async () => {
    const db = await database();
    await existingDocuments(db);
    await applyProjectIdeasMigration(db);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["0".repeat(64), PROJECT_IDEAS_MIGRATION]);
    await expect(applyProjectIdeasMigration(db)).rejects.toThrow("checksum mismatch");
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=77 WHERE migration_name=$2",
      [PROJECT_IDEAS_MIGRATION_DIGEST, PROJECT_IDEAS_MIGRATION]);
    await expect(applyProjectIdeasMigration(db)).rejects.toThrow("checksum mismatch");
    expect((await db.query("SELECT * FROM stt_idea_revisions")).rows).toHaveLength(0);
  });

  it("keeps preexisting projects without destructive backfill and immutably protects revisions/receipts", async () => {
    const db = await database();
    await existingDocuments(db);
    const { actor, project, document } = await existingProject(db);
    await applyProjectIdeasMigration(db);
    // The service interprets absence as emptyIdeasV1(document) at revision 0.
    expect((await db.query("SELECT * FROM stt_idea_heads WHERE project_id=$1", [project])).rows).toHaveLength(0);
    const json = JSON.stringify(emptyIdeasV1(document)), digest = sha256(json), mutation = randomUUID();
    const revisionValues = [project, 1, 0, document, actor, mutation, "put_ideas", digest, digest, json];
    const insertRevision = "INSERT INTO stt_idea_revisions(project_id,revision,expected_revision,document_id," +
      "actor_id,client_mutation_id,operation,request_digest,content_digest,ideas_json) " +
      "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)";
    await db.query(insertRevision, revisionValues);
    await db.query("INSERT INTO stt_idea_heads(project_id,document_id,revision,ideas_json,content_digest,updated_by) " +
      "VALUES($1,$2,1,$3,$4,$5)", [project, document, json, digest, actor]);
    await db.query("INSERT INTO stt_ideas_mutation_receipts(project_id,actor_id,client_mutation_id," +
      "operation,request_digest,ideas_revision,ideas_digest) VALUES($1,$2,$3,'put_ideas',$4,1,$5)",
    [project, actor, mutation, digest, digest]);

    await expect(db.query("UPDATE stt_idea_revisions SET ideas_json='{}' WHERE project_id=$1", [project])).rejects.toThrow();
    await expect(db.query("DELETE FROM stt_idea_revisions WHERE project_id=$1", [project])).rejects.toThrow();
    await expect(db.query("UPDATE stt_ideas_mutation_receipts SET request_digest=$1 WHERE project_id=$2",
      [sha256("changed"), project])).rejects.toThrow();
    await expect(db.query("DELETE FROM stt_ideas_mutation_receipts WHERE project_id=$1", [project])).rejects.toThrow();
    await expect(db.query(insertRevision, [project, 2, 1, document, actor, mutation,
      "put_ideas", digest, digest, json])).rejects.toThrow();
    await expect(db.query(insertRevision, [project, 3, 1, document, actor, randomUUID(),
      "put_ideas", digest, digest, json])).rejects.toThrow();
    await expect(db.query(insertRevision, [randomUUID(), 1, 0, document, actor, randomUUID(),
      "put_ideas", digest, digest, json])).rejects.toThrow();
    await expect(db.query(insertRevision, [project, 2, 1, randomUUID(), actor, randomUUID(),
      "put_ideas", digest, digest, json])).rejects.toThrow();
    expect((await db.query("SELECT * FROM stt_idea_revisions WHERE project_id=$1", [project])).rows).toHaveLength(1);
    expect((await db.query("SELECT * FROM stt_ideas_mutation_receipts WHERE project_id=$1", [project])).rows).toHaveLength(1);
  });
});
