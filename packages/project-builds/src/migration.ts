import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import type { SqlClient } from "@vera/project-authorization";

export const PROJECT_BUILDS_MIGRATION = "stt_project_builds_001";
const SQL = readFileSync(new URL("../migrations/001_project_builds.sql", import.meta.url), "utf8");
export const PROJECT_BUILDS_MIGRATION_DIGEST = createHash("sha256").update(SQL).digest("hex");

/** Apply *after* authorization and project-documents migrations on one DB. */
export async function applyProjectBuildsMigration(db: SqlClient): Promise<void> {
  await db.query("BEGIN");
  try {
    await db.query("SELECT pg_advisory_xact_lock($1)", [38_200_001]);
    const previous = await db.query<{ checksum: string; schema_version: number }>(
      "SELECT encode(checksum,'hex') AS checksum,schema_version " +
        "FROM vera_schema_migrations WHERE migration_name=$1",
      [PROJECT_BUILDS_MIGRATION],
    );
    if (previous.rows.length > 1) throw new Error("project builds duplicate migration receipt");
    if (previous.rows.length === 1) {
      if (previous.rows[0]?.checksum !== PROJECT_BUILDS_MIGRATION_DIGEST ||
          Number(previous.rows[0]?.schema_version) !== 1) {
        throw new Error("project builds migration checksum mismatch");
      }
    } else {
      if (db.exec) await db.exec(SQL);
      else await db.query(SQL);
      await db.query(
        "INSERT INTO vera_schema_migrations(migration_name,schema_version,checksum) " +
          "VALUES($1,1,decode($2,'hex'))",
        [PROJECT_BUILDS_MIGRATION, PROJECT_BUILDS_MIGRATION_DIGEST],
      );
    }
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => undefined);
    throw error;
  }
}
