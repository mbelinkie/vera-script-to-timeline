import { PGlite } from "@electric-sql/pglite";
import { afterEach, describe, expect, it } from "vitest";

import {
  applyPublicCaptureMigration,
  DatabaseMigrationError,
  PUBLIC_CAPTURE_MIGRATION_CHECKSUM,
  PUBLIC_CAPTURE_MIGRATION_NAME,
  SingleClientCaptureDatabase,
  revertEmptyPublicCaptureMigration,
} from "../src/database.js";

const databases: PGlite[] = [];

async function database(): Promise<PGlite> {
  const value = new PGlite();
  databases.push(value);
  await value.waitReady;
  return value;
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map(async (value) => await value.close()));
});

describe("public_page_capture_v1_expand", () => {
  it("applies transactionally, remains disabled, verifies, and reapplies", async () => {
    const db = await database();

    const first = await applyPublicCaptureMigration(db);
    const second = await applyPublicCaptureMigration(db);

    expect(first).toEqual(second);
    expect(first.checksum).toBe(PUBLIC_CAPTURE_MIGRATION_CHECKSUM);
    expect(first.executionEnabled).toBe(false);
    expect(first.tables).toHaveLength(15);
  }, 30_000);

  it("retains the accepted named constraints, indexes, and immutability guards", async () => {
    const db = await database();
    const verified = await applyPublicCaptureMigration(db);

    expect(verified.constraints).toEqual(
      expect.arrayContaining([
        "fk_capture_current_configuration",
        "uq_capture_job_idempotency_scope",
        "uq_capture_lease_epoch",
        "uq_capture_attempt_lease",
        "uq_capture_revision_number",
        "uq_capture_revision_job",
        "uq_capture_revision_attempt",
        "uq_capture_revision_provenance",
        "uq_capture_change_current_revision",
        "uq_capture_selection_target_sequence",
        "uq_capture_selection_effect",
        "uq_capture_protection_source",
        "uq_capture_protection_effect",
        "uq_capture_protection_release",
        "uq_capture_audit_object_sequence",
      ]),
    );
    expect(verified.indexes).toEqual(
      expect.arrayContaining([
        "ix_capture_jobs_queue",
        "ix_capture_leases_expiry",
        "ix_capture_revisions_history",
        "ix_capture_selections_target",
        "ix_capture_protections_active",
        "ix_capture_audit_time",
        "uq_capture_job_build",
        "uq_capture_active_lease",
      ]),
    );
    expect(verified.triggers).toHaveLength(14);
  }, 30_000);

  it("grants each runtime role only its required read and mutation surface", async () => {
    const db = await database();
    await applyPublicCaptureMigration(db);

    const privileges = await db.query<{
      api_can_insert_artifacts: boolean;
      api_can_read_revisions: boolean;
      api_can_update_configuration: boolean;
      api_can_update_revision_counter: boolean;
      reader_can_delete: boolean;
      reader_can_read_restricted_provenance: boolean;
      worker_can_insert_jobs: boolean;
      worker_can_insert_pin_releases: boolean;
      worker_can_read_configuration: boolean;
      worker_can_read_execution_setting: boolean;
      worker_can_update_configuration: boolean;
      worker_can_update_revision_counter: boolean;
    }>(
      `SELECT
         has_table_privilege(
           'vera_capture_api', 'capture_artifacts', 'INSERT'
         ) AS api_can_insert_artifacts,
         has_table_privilege(
           'vera_capture_api', 'capture_revisions', 'SELECT'
         ) AS api_can_read_revisions,
         has_column_privilege(
           'vera_capture_api', 'captures',
           'current_configuration_version', 'UPDATE'
         ) AS api_can_update_configuration,
         has_column_privilege(
           'vera_capture_api', 'captures', 'next_revision_number', 'UPDATE'
         ) AS api_can_update_revision_counter,
         has_table_privilege(
           'vera_capture_reader', 'captures', 'DELETE'
         ) AS reader_can_delete,
         has_table_privilege(
           'vera_capture_reader', 'capture_provenance_manifests', 'SELECT'
         ) AS reader_can_read_restricted_provenance,
         has_table_privilege(
           'vera_capture_worker', 'capture_jobs', 'INSERT'
         ) AS worker_can_insert_jobs,
         has_table_privilege(
           'vera_capture_worker', 'capture_protection_releases', 'INSERT'
         ) AS worker_can_insert_pin_releases,
         has_table_privilege(
           'vera_capture_worker', 'capture_configurations', 'SELECT'
         ) AS worker_can_read_configuration,
         has_table_privilege(
           'vera_capture_worker', 'public_page_capture_settings', 'SELECT'
         ) AS worker_can_read_execution_setting,
         has_column_privilege(
           'vera_capture_worker', 'captures',
           'current_configuration_version', 'UPDATE'
         ) AS worker_can_update_configuration,
         has_column_privilege(
           'vera_capture_worker', 'captures', 'next_revision_number', 'UPDATE'
         ) AS worker_can_update_revision_counter`,
    );

    expect(privileges.rows).toEqual([
      {
        api_can_insert_artifacts: false,
        api_can_read_revisions: true,
        api_can_update_configuration: true,
        api_can_update_revision_counter: false,
        reader_can_delete: false,
        reader_can_read_restricted_provenance: false,
        worker_can_insert_jobs: false,
        worker_can_insert_pin_releases: false,
        worker_can_read_configuration: true,
        worker_can_read_execution_setting: true,
        worker_can_update_configuration: false,
        worker_can_update_revision_counter: true,
      },
    ]);
  }, 30_000);

  it("rolls back only while every capture table and object reference is empty", async () => {
    const empty = await database();
    await applyPublicCaptureMigration(empty);
    await expect(
      revertEmptyPublicCaptureMigration(empty, {
        hasObjectReferences: () => true,
      }),
    ).rejects.toMatchObject({
      code: "rollback_object_references_exist",
    });
    await revertEmptyPublicCaptureMigration(empty);
    const tables = await empty.query<{ table_name: string }>(
      `SELECT table_name
         FROM information_schema.tables
        WHERE table_name = 'captures'`,
    );
    expect(tables.rows).toHaveLength(0);

    const populated = await database();
    await applyPublicCaptureMigration(populated);
    await insertCapture(populated);
    await expect(
      revertEmptyPublicCaptureMigration(populated),
    ).rejects.toMatchObject({ code: "rollback_data_exists" });
    expect(
      await populated.query("SELECT 1 FROM captures"),
    ).toMatchObject({ rows: [{ "?column?": 1 }] });
  }, 30_000);

  it("detects checksum substitution instead of reinterpreting a version", async () => {
    const db = await database();
    await applyPublicCaptureMigration(db);
    await db.query(
      `UPDATE vera_schema_migrations
          SET checksum = decode(repeat('00', 32), 'hex')
        WHERE migration_name = $1`,
      [PUBLIC_CAPTURE_MIGRATION_NAME],
    );

    await expect(applyPublicCaptureMigration(db)).rejects.toBeInstanceOf(
      DatabaseMigrationError,
    );
  }, 30_000);

  it("rolls a failed service transaction back without partial state", async () => {
    const db = await database();
    await applyPublicCaptureMigration(db);
    const transactions = new SingleClientCaptureDatabase(db);

    await expect(
      transactions.transaction(async (client) => {
        await client.query(
          `INSERT INTO captures (
              project_id, capture_id, state, current_configuration_version,
              created_by_kind, created_by_id
            ) VALUES ($1, $2, 'active', 1, 'user', $3)`,
          [
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222223",
            "dddddddd-dddd-4ddd-8ddd-ddddddddddd2",
          ],
        );
        throw new Error("synthetic transaction failure");
      }),
    ).rejects.toThrow("synthetic transaction failure");
    expect(
      await db.query("SELECT count(*)::int AS count FROM captures"),
    ).toMatchObject({ rows: [{ count: 0 }] });
  }, 30_000);

  it("rejects cross-project references, duplicate versions, and immutable edits", async () => {
    const db = await database();
    await applyPublicCaptureMigration(db);
    await insertCapture(db);

    await expect(
      db.query(
        `INSERT INTO capture_configurations (
            project_id, capture_id, configuration_version, schema_version,
            canonical_url_digest, redacted_url_display, query_key_names,
            restricted_request_envelope, restricted_request_key_version,
            region_intent, acquisition_policy, periodic_execution_enabled,
            capture_profile_id, capture_profile_version, settings_json,
            settings_digest, previous_configuration_digest, created_by_kind,
            created_by_id, created_at
          )
          SELECT $1::uuid, capture_id, configuration_version, schema_version,
            canonical_url_digest, redacted_url_display, query_key_names,
            restricted_request_envelope, restricted_request_key_version,
            region_intent, acquisition_policy, periodic_execution_enabled,
            capture_profile_id, capture_profile_version, settings_json,
            settings_digest, previous_configuration_digest, created_by_kind,
            created_by_id, created_at
          FROM capture_configurations
          WHERE project_id = $2`,
        [
          "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          "11111111-1111-4111-8111-111111111111",
        ],
      ),
    ).rejects.toThrow();

    await expect(
      db.query(
        `INSERT INTO capture_configurations
          SELECT *
          FROM capture_configurations
          WHERE project_id = $1`,
        ["11111111-1111-4111-8111-111111111111"],
      ),
    ).rejects.toThrow();

    await expect(
      db.query(
        `UPDATE capture_configurations
            SET redacted_url_display = 'https://mutated.example.org/'
          WHERE project_id = $1`,
        ["11111111-1111-4111-8111-111111111111"],
      ),
    ).rejects.toThrow(/immutable/u);
    expect(
      await db.query<{ redacted_url_display: string }>(
        `SELECT redacted_url_display
           FROM capture_configurations
          WHERE project_id = $1`,
        ["11111111-1111-4111-8111-111111111111"],
      ),
    ).toMatchObject({
      rows: [
        {
          redacted_url_display:
            "https://capture.example.org/story?edition=%5BREDACTED%5D",
        },
      ],
    });
  }, 30_000);
});

async function insertCapture(db: PGlite): Promise<void> {
  await db.exec(`
    BEGIN;
    INSERT INTO captures (
      project_id,
      capture_id,
      state,
      current_configuration_version,
      created_by_kind,
      created_by_id
    ) VALUES (
      '11111111-1111-4111-8111-111111111111',
      '22222222-2222-4222-8222-222222222222',
      'active',
      1,
      'user',
      'dddddddd-dddd-4ddd-8ddd-ddddddddddd2'
    );
    INSERT INTO capture_configurations (
      project_id,
      capture_id,
      configuration_version,
      schema_version,
      canonical_url_digest,
      redacted_url_display,
      query_key_names,
      restricted_request_envelope,
      restricted_request_key_version,
      region_intent,
      acquisition_policy,
      capture_profile_id,
      capture_profile_version,
      settings_json,
      settings_digest,
      created_by_kind,
      created_by_id
    ) VALUES (
      '11111111-1111-4111-8111-111111111111',
      '22222222-2222-4222-8222-222222222222',
      1,
      'public-page-capture-api/v1',
      decode(repeat('11', 32), 'hex'),
      'https://capture.example.org/story?edition=%5BREDACTED%5D',
      '["edition"]'::jsonb,
      decode('00', 'hex'),
      1,
      '{"kind":"full_viewport"}'::jsonb,
      'now',
      '33333333-3333-4333-8333-333333333333',
      1,
      '{"region":{"kind":"full_viewport"}}'::jsonb,
      decode(repeat('33', 32), 'hex'),
      'user',
      'dddddddd-dddd-4ddd-8ddd-ddddddddddd2'
    );
    COMMIT;
  `);
}
