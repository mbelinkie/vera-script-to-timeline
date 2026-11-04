import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import type { SqlClient } from "./service.js";

export const MIGRATION_NAME = "vera_project_identity_membership_001";
const SQL = readFileSync(
  new URL("../migrations/001_identity_membership.sql", import.meta.url),
  "utf8",
);
export const MIGRATION_DIGEST = createHash("sha256").update(SQL).digest("hex");

export async function applyProjectAuthorizationMigration(
  client: SqlClient,
): Promise<void> {
  await client.query("BEGIN");
  try {
    await client.query(
      "CREATE TABLE IF NOT EXISTS vera_schema_migrations (" +
      "migration_name text PRIMARY KEY, schema_version integer NOT NULL, " +
      "checksum bytea NOT NULL CHECK (octet_length(checksum) = 32), " +
      "applied_at timestamptz NOT NULL DEFAULT now())",
    );
    await client.query("SELECT pg_advisory_xact_lock($1)", [37_900_001]);
    const old = await client.query<{ checksum: string; schema_version: number }>(
      "SELECT encode(checksum, 'hex') AS checksum, schema_version " +
      "FROM vera_schema_migrations WHERE migration_name=$1",
      [MIGRATION_NAME],
    );
    if (old.rows.length > 0) {
      if (old.rows[0]?.checksum !== MIGRATION_DIGEST ||
          Number(old.rows[0]?.schema_version) !== 1) {
        throw new Error("project authorization migration checksum mismatch");
      }
    } else {
      if (client.exec) await client.exec(SQL);
      else await client.query(SQL);
      await client.query(
        "INSERT INTO vera_schema_migrations " +
        "(migration_name,schema_version,checksum) VALUES ($1,1,decode($2,'hex'))",
        [MIGRATION_NAME, MIGRATION_DIGEST],
      );
    }
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }
}
