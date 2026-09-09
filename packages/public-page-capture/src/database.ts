import { readFileSync } from "node:fs";

import { sha256 } from "./crypto.js";

export const PUBLIC_CAPTURE_MIGRATION_NAME = "public_page_capture_v1_expand";
export const PUBLIC_CAPTURE_SCHEMA_VERSION = 1;

export const PUBLIC_CAPTURE_MIGRATION_SQL = readFileSync(
  new URL(
    "../migrations/public_page_capture_v1_expand.sql",
    import.meta.url,
  ),
  "utf8",
);
export const PUBLIC_CAPTURE_MIGRATION_CHECKSUM = sha256(
  PUBLIC_CAPTURE_MIGRATION_SQL,
);

export interface QueryResult<Row = Record<string, unknown>> {
  readonly rows: readonly Row[];
  readonly rowCount?: number | null;
}

export interface SqlClient {
  query<Row = Record<string, unknown>>(
    sql: string,
    parameters?: readonly unknown[],
  ): Promise<QueryResult<Row>>;
  exec?(sql: string): Promise<unknown>;
}

export interface CaptureDatabase {
  transaction<T>(operation: (client: SqlClient) => Promise<T>): Promise<T>;
}

export interface SqlConnection extends SqlClient {
  release?(): void;
}

export interface SqlPool {
  connect(): Promise<SqlConnection>;
}

async function inSerializableTransaction<T>(
  client: SqlClient,
  operation: (client: SqlClient) => Promise<T>,
): Promise<T> {
  await client.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
  try {
    const value = await operation(client);
    await client.query("COMMIT");
    return value;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }
}

export class PooledCaptureDatabase implements CaptureDatabase {
  constructor(private readonly pool: SqlPool) {}

  async transaction<T>(
    operation: (client: SqlClient) => Promise<T>,
  ): Promise<T> {
    const client = await this.pool.connect();
    try {
      return await inSerializableTransaction(client, operation);
    } finally {
      client.release?.();
    }
  }
}

export class SingleClientCaptureDatabase implements CaptureDatabase {
  private tail: Promise<void> = Promise.resolve();

  constructor(private readonly client: SqlClient) {}

  async transaction<T>(
    operation: (client: SqlClient) => Promise<T>,
  ): Promise<T> {
    let unlock = (): void => undefined;
    const previous = this.tail;
    this.tail = new Promise<void>((resolve) => {
      unlock = resolve;
    });
    await previous;
    try {
      return await inSerializableTransaction(this.client, operation);
    } finally {
      unlock();
    }
  }
}

export class DatabaseMigrationError extends Error {
  override readonly name = "DatabaseMigrationError";

  constructor(readonly code: string, message: string) {
    super(message);
  }
}

const captureTables = [
  "capture_audit_events",
  "capture_protection_releases",
  "capture_revision_protections",
  "capture_revision_selections",
  "capture_revision_use_decisions",
  "capture_change_signals",
  "capture_revisions",
  "capture_provenance_manifests",
  "capture_artifacts",
  "capture_attempts",
  "capture_leases",
  "capture_jobs",
  "capture_configurations",
  "captures",
] as const;

async function execute(client: SqlClient, sql: string): Promise<void> {
  if (client.exec) {
    await client.exec(sql);
  } else {
    await client.query(sql);
  }
}

function checksumHex(): string {
  return PUBLIC_CAPTURE_MIGRATION_CHECKSUM.slice("sha256:".length);
}

export interface MigrationVerification {
  readonly checksum: string;
  readonly constraints: readonly string[];
  readonly executionEnabled: false;
  readonly indexes: readonly string[];
  readonly tables: readonly string[];
  readonly triggers: readonly string[];
}

export async function verifyPublicCaptureMigration(
  client: SqlClient,
): Promise<MigrationVerification> {
  const migration = await client.query<{
    checksum: string;
    schema_version: number;
  }>(
    `SELECT encode(checksum, 'hex') AS checksum, schema_version
       FROM vera_schema_migrations
      WHERE migration_name = $1`,
    [PUBLIC_CAPTURE_MIGRATION_NAME],
  );
  const stored = migration.rows[0];
  if (
    !stored ||
    Number(stored.schema_version) !== PUBLIC_CAPTURE_SCHEMA_VERSION ||
    stored.checksum !== checksumHex()
  ) {
    throw new DatabaseMigrationError(
      "migration_checksum_mismatch",
      "The public capture migration record is absent or does not match its retained bytes.",
    );
  }

  const tableResult = await client.query<{ table_name: string }>(
    `SELECT table_name
       FROM information_schema.tables
      WHERE table_schema = current_schema()
        AND table_name = ANY($1::text[])
      ORDER BY table_name`,
    [[...captureTables, "public_page_capture_settings"]],
  );
  const tables = tableResult.rows.map(({ table_name }) => table_name);
  if (tables.length !== captureTables.length + 1) {
    throw new DatabaseMigrationError(
      "migration_objects_missing",
      "The public capture schema is incomplete.",
    );
  }

  const setting = await client.query<{ enabled: boolean }>(
    `SELECT enabled
       FROM public_page_capture_settings
      WHERE setting_name = 'public_page_capture_execution'`,
  );
  if (setting.rows[0]?.enabled !== false) {
    throw new DatabaseMigrationError(
      "migration_not_disabled",
      "Public capture execution must remain disabled after schema application.",
    );
  }

  const constraints = await client.query<{ conname: string }>(
    `SELECT conname
       FROM pg_constraint
      WHERE conname LIKE 'ck_capture_%'
         OR conname LIKE 'fk_capture_%'
         OR conname LIKE 'uq_capture_%'
      ORDER BY conname`,
  );
  const indexes = await client.query<{ indexname: string }>(
    `SELECT indexname
       FROM pg_indexes
      WHERE schemaname = current_schema()
        AND (
            indexname LIKE 'ix_capture_%'
            OR indexname IN (
                'uq_capture_job_build',
                'uq_capture_active_lease'
            )
        )
      ORDER BY indexname`,
  );
  const triggers = await client.query<{ trigger_name: string }>(
    `SELECT trigger_name
       FROM information_schema.triggers
      WHERE trigger_schema = current_schema()
        AND trigger_name LIKE 'tr_capture_%'
      ORDER BY trigger_name`,
  );
  return {
    checksum: PUBLIC_CAPTURE_MIGRATION_CHECKSUM,
    constraints: constraints.rows.map(({ conname }) => conname),
    executionEnabled: false,
    indexes: indexes.rows.map(({ indexname }) => indexname),
    tables,
    triggers: [...new Set(triggers.rows.map(({ trigger_name }) => trigger_name))],
  };
}

export async function applyPublicCaptureMigration(
  client: SqlClient,
): Promise<MigrationVerification> {
  await client.query("BEGIN");
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS vera_schema_migrations (
        migration_name text PRIMARY KEY,
        schema_version integer NOT NULL,
        checksum bytea NOT NULL CHECK (octet_length(checksum) = 32),
        applied_at timestamptz NOT NULL DEFAULT now()
      )
    `);
    await client.query("SELECT pg_advisory_xact_lock($1)", [39_000_001]);
    const existing = await client.query<{
      checksum: string;
      schema_version: number;
    }>(
      `SELECT encode(checksum, 'hex') AS checksum, schema_version
         FROM vera_schema_migrations
        WHERE migration_name = $1`,
      [PUBLIC_CAPTURE_MIGRATION_NAME],
    );
    if (existing.rows[0]) {
      if (
        existing.rows[0].checksum !== checksumHex() ||
        Number(existing.rows[0].schema_version) !==
          PUBLIC_CAPTURE_SCHEMA_VERSION
      ) {
        throw new DatabaseMigrationError(
          "migration_checksum_mismatch",
          "A different public capture migration is already recorded under this name.",
        );
      }
      await client.query("COMMIT");
      return await verifyPublicCaptureMigration(client);
    }

    await execute(client, PUBLIC_CAPTURE_MIGRATION_SQL);
    await client.query(
      `INSERT INTO vera_schema_migrations (
          migration_name,
          schema_version,
          checksum
        ) VALUES ($1, $2, decode($3, 'hex'))`,
      [
        PUBLIC_CAPTURE_MIGRATION_NAME,
        PUBLIC_CAPTURE_SCHEMA_VERSION,
        checksumHex(),
      ],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }
  return await verifyPublicCaptureMigration(client);
}

export interface DownMigrationOptions {
  readonly hasObjectReferences?: () => boolean | Promise<boolean>;
}

export async function revertEmptyPublicCaptureMigration(
  client: SqlClient,
  options: DownMigrationOptions = {},
): Promise<void> {
  if (await options.hasObjectReferences?.()) {
    throw new DatabaseMigrationError(
      "rollback_object_references_exist",
      "The public capture migration cannot roll back while object references exist.",
    );
  }
  const counts = await client.query<{ total: string }>(
    `SELECT sum(row_count)::text AS total
       FROM (
        ${captureTables
          .map(
            (table) =>
              `SELECT count(*)::bigint AS row_count FROM ${table}`,
          )
          .join(" UNION ALL ")}
       ) AS capture_row_counts`,
  );
  if (BigInt(counts.rows[0]?.total ?? "0") !== 0n) {
    throw new DatabaseMigrationError(
      "rollback_data_exists",
      "The public capture migration is forward-only after any capture record exists.",
    );
  }

  await client.query("BEGIN");
  try {
    await execute(
      client,
      `
      REVOKE ALL ON public_page_capture_settings, captures,
        capture_configurations, capture_jobs, capture_leases, capture_attempts,
        capture_artifacts, capture_provenance_manifests, capture_revisions,
        capture_change_signals, capture_revision_use_decisions,
        capture_revision_selections, capture_revision_protections,
        capture_protection_releases, capture_audit_events
        FROM vera_capture_reader, vera_capture_api, vera_capture_worker;
      DROP TABLE capture_audit_events;
      DROP TABLE capture_protection_releases;
      DROP TABLE capture_revision_protections;
      DROP TABLE capture_revision_selections;
      DROP TABLE capture_revision_use_decisions;
      DROP TABLE capture_change_signals;
      ALTER TABLE capture_jobs DROP CONSTRAINT fk_capture_job_output_revision;
      DROP TABLE capture_revisions;
      DROP TABLE capture_provenance_manifests;
      DROP TABLE capture_artifacts;
      DROP TABLE capture_attempts;
      DROP TABLE capture_leases;
      DROP TABLE capture_jobs;
      ALTER TABLE captures DROP CONSTRAINT fk_capture_current_configuration;
      DROP TABLE capture_configurations;
      DROP TABLE captures;
      DROP TABLE public_page_capture_settings;
      DROP FUNCTION deny_capture_immutable_change();
      DROP FUNCTION deny_capture_delete();
      `,
    );
    await client.query(
      "DELETE FROM vera_schema_migrations WHERE migration_name = $1",
      [PUBLIC_CAPTURE_MIGRATION_NAME],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }
}
