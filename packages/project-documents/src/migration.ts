import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import type { SqlClient } from "@vera/project-authorization";

export const PROJECT_DOCUMENTS_MIGRATION = "stt_project_documents_001";
const SQL = readFileSync(new URL("../migrations/001_stt_projects_documents.sql", import.meta.url), "utf8");
export const PROJECT_DOCUMENTS_MIGRATION_DIGEST = createHash("sha256").update(SQL).digest("hex");

/** Run after applyProjectAuthorizationMigration, using the same PostgreSQL database. */
export async function applyProjectDocumentsMigration(db: SqlClient): Promise<void> {
  await db.query("BEGIN");
  try {
    await db.query("SELECT pg_advisory_xact_lock($1)", [38_000_001]);
    const old = await db.query<{ checksum: string; schema_version: number }>(
      "SELECT encode(checksum,'hex') AS checksum,schema_version FROM vera_schema_migrations WHERE migration_name=$1",
      [PROJECT_DOCUMENTS_MIGRATION],
    );
    if (old.rows.length) {
      if (old.rows[0]?.checksum !== PROJECT_DOCUMENTS_MIGRATION_DIGEST ||
          Number(old.rows[0]?.schema_version) !== 1) {
        throw new Error("project documents migration checksum mismatch");
      }
    } else {
      if (db.exec) await db.exec(SQL);
      else await db.query(SQL);
      await db.query(
        "INSERT INTO vera_schema_migrations(migration_name,schema_version,checksum) VALUES($1,1,decode($2,'hex'))",
        [PROJECT_DOCUMENTS_MIGRATION, PROJECT_DOCUMENTS_MIGRATION_DIGEST],
      );
    }
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => undefined);
    throw error;
  }
}
