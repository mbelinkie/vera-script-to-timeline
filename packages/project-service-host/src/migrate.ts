import {
  applyProjectAuthorizationMigration,
  MIGRATION_DIGEST,
  MIGRATION_NAME,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectIdeasMigration,
  PROJECT_COMMENTS_MIGRATION,
  PROJECT_COMMENTS_MIGRATION_DIGEST,
  PROJECT_DOCUMENTS_MIGRATION,
  PROJECT_DOCUMENTS_MIGRATION_DIGEST,
  PROJECT_HISTORY_MIGRATION,
  PROJECT_HISTORY_MIGRATION_DIGEST,
  PROJECT_IDEAS_MIGRATION,
  PROJECT_IDEAS_MIGRATION_DIGEST,
} from "@vera/project-documents";
import {
  applyProjectBuildsMigration,
  BUILD_REFUSALS_MIGRATION,
  BUILD_REFUSALS_MIGRATION_DIGEST,
  PROJECT_BUILDS_MIGRATION,
  PROJECT_BUILDS_MIGRATION_DIGEST,
} from "@vera/project-builds";

import type { QaConfig } from "./qa-config.js";

export class QaDatabaseRefusal extends Error {
  override readonly name = "QaDatabaseRefusal";
  constructor() { super("unsafe development-QA database target or migration state"); }
}

const ALLOWED_TABLES = new Set([
  "vera_schema_migrations",
  "vera_identity_actors",
  "vera_project_members",
  "vera_project_write_sessions",
  "vera_project_membership_audit",
  "stt_projects",
  "stt_document_heads",
  "stt_document_revisions",
  "stt_project_settings",
  "stt_settings_revisions",
  "stt_project_title_mutations",
  "stt_comment_heads",
  "stt_comment_events",
  "stt_document_checkpoints",
  "stt_checkpoint_approvals",
  "stt_document_restores",
  "stt_idea_heads",
  "stt_idea_revisions",
  "stt_ideas_mutation_receipts",
  "stt_build_pairing_offers",
  "stt_project_build_agents",
  "stt_build_submissions",
  "stt_build_source_pins",
  "stt_build_dispatches",
  "stt_build_events",
  "stt_build_evidence",
  "stt_build_preflight_refusals",
]);

const EXPECTED_MIGRATIONS = [
  { name: MIGRATION_NAME, version: 1, checksum: MIGRATION_DIGEST },
  { name: PROJECT_DOCUMENTS_MIGRATION, version: 1, checksum: PROJECT_DOCUMENTS_MIGRATION_DIGEST },
  { name: PROJECT_COMMENTS_MIGRATION, version: 2, checksum: PROJECT_COMMENTS_MIGRATION_DIGEST },
  { name: PROJECT_HISTORY_MIGRATION, version: 3, checksum: PROJECT_HISTORY_MIGRATION_DIGEST },
  { name: PROJECT_IDEAS_MIGRATION, version: 4, checksum: PROJECT_IDEAS_MIGRATION_DIGEST },
  { name: PROJECT_BUILDS_MIGRATION, version: 1, checksum: PROJECT_BUILDS_MIGRATION_DIGEST },
  { name: BUILD_REFUSALS_MIGRATION, version: 1, checksum: BUILD_REFUSALS_MIGRATION_DIGEST },
] as const;

export interface QaMigrationReceipt {
  readonly name: string;
  readonly version: number;
  readonly checksum: string;
}

/** Fail before performing DDL against any other database, privileged role or schema. */
export async function assertQaDatabaseTarget(db: SqlClient, config: QaConfig): Promise<void> {
  const connection = await db.query<{
    database_name: string;
    user_name: string;
    superuser: boolean;
    createdb: boolean;
    createrole: boolean;
    replication: boolean;
    bypassrls: boolean;
  }>(
    "SELECT current_database() AS database_name, current_user AS user_name, " +
    "r.rolsuper AS superuser, r.rolcreatedb AS createdb, " +
    "r.rolcreaterole AS createrole, r.rolreplication AS replication, " +
    "r.rolbypassrls AS bypassrls FROM pg_roles r WHERE r.rolname=current_user",
  );
  const actual = connection.rows[0];
  if (connection.rows.length !== 1 || !actual ||
      actual.database_name !== config.databaseName ||
      actual.user_name !== config.databaseUser ||
      actual.superuser !== false || actual.createdb !== false ||
      actual.createrole !== false || actual.replication !== false ||
      actual.bypassrls !== false) throw new QaDatabaseRefusal();

  // Include views and foreign/materialized tables as well as base tables:
  // an existing non-QA schema must not silently be accepted as a fresh QA DB.
  const tables = await db.query<{ schema_name: string; table_name: string }>(
    "SELECT n.nspname AS schema_name, c.relname AS table_name " +
    "FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid " +
    "WHERE n.nspname NOT IN ('pg_catalog', 'pg_toast', 'information_schema') " +
    "AND n.nspname NOT LIKE 'pg_temp_%' AND n.nspname NOT LIKE 'pg_toast_temp_%' " +
    "AND c.relkind IN ('r','p','v','m','f')",
  );
  if (tables.rows.some(({ schema_name, table_name }) =>
    schema_name !== "public" || !ALLOWED_TABLES.has(table_name))) {
    throw new QaDatabaseRefusal();
  }
}

/** Apply only the checksum-pinned QA migrations, in dependency order. */
export async function applyQaMigrations(
  pool: SqlPool,
  config: QaConfig,
): Promise<readonly QaMigrationReceipt[]> {
  const db = await pool.connect();
  try {
    await assertQaDatabaseTarget(db, config);
    await applyProjectAuthorizationMigration(db);
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectHistoryMigration(db);
    await applyProjectIdeasMigration(db);
    await applyProjectBuildsMigration(db);
    const receipts = await db.query<{
      name: string;
      version: number;
      checksum: string;
    }>(
      "SELECT migration_name AS name, schema_version AS version, " +
      "encode(checksum,'hex') AS checksum FROM vera_schema_migrations",
    );
    if (receipts.rows.length !== EXPECTED_MIGRATIONS.length ||
        EXPECTED_MIGRATIONS.some((expected) => !receipts.rows.some((actual) =>
          actual.name === expected.name && Number(actual.version) === expected.version &&
          actual.checksum === expected.checksum))) {
      throw new QaDatabaseRefusal();
    }
    return EXPECTED_MIGRATIONS.map(({ name, version, checksum }) => ({ name, version, checksum }));
  } finally {
    db.release?.();
  }
}
