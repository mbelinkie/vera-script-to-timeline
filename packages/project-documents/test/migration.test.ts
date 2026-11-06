import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyProjectDocumentsMigration,
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
