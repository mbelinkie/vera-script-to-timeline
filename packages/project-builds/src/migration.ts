import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import type { SqlClient } from "@vera/project-authorization";

export const PROJECT_BUILDS_MIGRATION = "stt_project_builds_001";
const SQL = readFileSync(new URL("../migrations/001_project_builds.sql", import.meta.url), "utf8");
export const PROJECT_BUILDS_MIGRATION_DIGEST = createHash("sha256").update(SQL).digest("hex");
export const BUILD_REFUSALS_MIGRATION = "stt_project_builds_002_preflight_refusals";
const REFUSALS_SQL = readFileSync(new URL("../migrations/002_preflight_refusals.sql", import.meta.url), "utf8");
export const BUILD_REFUSALS_MIGRATION_DIGEST =
  createHash("sha256").update(REFUSALS_SQL).digest("hex");

/** Apply *after* authorization and project-documents migrations on one DB. */
export async function applyProjectBuildsMigration(db: SqlClient): Promise<void> {
  await db.query("BEGIN");
  try {
    await db.query("SELECT pg_advisory_xact_lock($1)", [38_200_001]);
    for (const step of [
      { name: PROJECT_BUILDS_MIGRATION, sql: SQL, digest: PROJECT_BUILDS_MIGRATION_DIGEST },
      { name: BUILD_REFUSALS_MIGRATION, sql: REFUSALS_SQL, digest: BUILD_REFUSALS_MIGRATION_DIGEST },
    ]) {
      const previous = await db.query<{ checksum: string; schema_version: number }>(
        "SELECT encode(checksum,'hex') AS checksum,schema_version " +
          "FROM vera_schema_migrations WHERE migration_name=$1",
        [step.name],
      );
      if (previous.rows.length > 1) throw new Error("project builds duplicate migration receipt");
      if (previous.rows.length === 1) {
        if (previous.rows[0]?.checksum !== step.digest ||
            Number(previous.rows[0]?.schema_version) !== 1) {
          throw new Error("project builds migration checksum mismatch");
        }
      } else {
        if (db.exec) await db.exec(step.sql);
        else await db.query(step.sql);
        await db.query(
          "INSERT INTO vera_schema_migrations(migration_name,schema_version,checksum) " +
            "VALUES($1,1,decode($2,'hex'))",
          [step.name, step.digest],
        );
      }
    }
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => undefined);
    throw error;
  }
}
