import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration } from "@vera/project-authorization";
import { applyProjectDocumentsMigration } from "@vera/project-documents";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyProjectBuildsMigration,
  BUILD_REFUSALS_MIGRATION,
  BUILD_REFUSALS_MIGRATION_DIGEST,
  PROJECT_BUILDS_MIGRATION,
  PROJECT_BUILDS_MIGRATION_DIGEST,
} from "../src/migration.js";

// PGlite cold initialization on the mounted test filesystem is slower than RAM.
vi.setConfig({ testTimeout: 120_000 });
const databases: PGlite[] = [];
async function fresh() {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  return db;
}
async function migrated() {
  const db = await fresh();
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  await applyProjectBuildsMigration(db);
  return db;
}
async function actorAndProject(db: PGlite): Promise<{ actor: string; project: string }> {
  const actor = randomUUID();
  const project = randomUUID();
  await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test',$2)",
    [actor, actor]);
  await db.query(
    "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'Synthetic test',$2,$3,$4)",
    [project, actor, randomUUID(), "sha256:" + "a".repeat(64)],
  );
  return { actor, project };
}
const digest = "sha256:" + "b".repeat(64);
async function submission(
  db: PGlite, project: string, actor: string, requestKey = randomUUID(),
): Promise<string> {
  const id = randomUUID();
  await db.query(
    "INSERT INTO stt_build_submissions(id,project_id,target_id,submitted_by,idempotency_key," +
      "request_digest,build_class,mode,expected_revision,document_id,document_json," +
      "document_digest,settings_revision,settings_json,settings_digest,snapshot_digest) " +
      "VALUES ($1,$2,$3,$4,$5,$6,'preview','free',0,$7,'{}',$8,1,'{}',$9,$10)",
    [id, project, randomUUID(), actor, requestKey, digest, randomUUID(), digest, digest, digest],
  );
  return id;
}
afterEach(async () => {
  for (const db of databases.splice(0)) await db.close();
});

describe("forward-only checksum-pinned build schema", () => {
  it("requires predecessor schemas; applies additively, exactly once and records its hash", async () => {
    const db = await fresh();
    await expect(applyProjectBuildsMigration(db)).rejects.toThrow();
    await applyProjectAuthorizationMigration(db);
    await expect(applyProjectBuildsMigration(db)).rejects.toThrow();
    await applyProjectDocumentsMigration(db);
    await applyProjectBuildsMigration(db);
    await applyProjectBuildsMigration(db);
    const names = (await db.query<{ table_name: string }>(
      "SELECT table_name FROM information_schema.tables WHERE table_schema='public' " +
        "AND table_type='BASE TABLE' ORDER BY table_name",
    )).rows.map((row) => row.table_name);
    for (const name of [
      "vera_project_members", "stt_document_revisions",
      "stt_build_pairing_offers", "stt_project_build_agents", "stt_build_submissions",
      "stt_build_source_pins", "stt_build_dispatches", "stt_build_events",
      "stt_build_evidence",
      "stt_build_preflight_refusals",
    ]) expect(names).toContain(name);
    expect(names).toHaveLength(19); // original 11 + 8 new, including preflight refusals
    const receipts = await db.query<{ checksum: string; version: number }>(
      "SELECT encode(checksum,'hex') AS checksum,schema_version AS version " +
        "FROM vera_schema_migrations WHERE migration_name=$1", [PROJECT_BUILDS_MIGRATION],
    );
    expect(receipts.rows).toEqual([{ checksum: PROJECT_BUILDS_MIGRATION_DIGEST, version: 1 }]);
    const refusalReceipt = await db.query<{ checksum: string }>(
      "SELECT encode(checksum,'hex') AS checksum FROM vera_schema_migrations " +
        "WHERE migration_name=$1", [BUILD_REFUSALS_MIGRATION],
    );
    expect(refusalReceipt.rows[0]?.checksum).toBe(BUILD_REFUSALS_MIGRATION_DIGEST);
    expect((await db.query("SELECT * FROM vera_schema_migrations")).rows).toHaveLength(4);
  });

  it("rejects tampered checksum/version and leaves the original tables/data untouched", async () => {
    const db = await migrated();
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') " +
      "WHERE migration_name=$2", ["ff".repeat(32), PROJECT_BUILDS_MIGRATION]);
    await expect(applyProjectBuildsMigration(db)).rejects.toThrow("checksum mismatch");
    expect((await db.query("SELECT * FROM stt_build_submissions")).rows).toHaveLength(0);
    await db.query(
      "UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=2 " +
        "WHERE migration_name=$2", [PROJECT_BUILDS_MIGRATION_DIGEST, PROJECT_BUILDS_MIGRATION],
    );
    await expect(applyProjectBuildsMigration(db)).rejects.toThrow("checksum mismatch");
  });

  it("enforces scoped foreign keys, unique request keys, hashes and frozen history", async () => {
    const db = await migrated();
    const left = await actorAndProject(db);
    const right = await actorAndProject(db);
    const offer = randomUUID();
    await db.query(
      "INSERT INTO stt_build_pairing_offers(id,project_id,created_by,offer_digest,agent_label," +
        "protocol_version,expires_at) VALUES($1,$2,$3,$4,'local','v1',now() + interval '5 minutes')",
      [offer, left.project, left.actor, digest],
    );
    const agent = randomUUID();
    await expect(db.query(
      "INSERT INTO stt_project_build_agents(id,project_id,pairing_offer_id,credential_digest," +
        "protocol_version) VALUES ($1,$2,$3,$4,'v1')",
      [agent, right.project, offer, "sha256:" + "c".repeat(64)],
    )).rejects.toThrow();
    await db.query(
      "INSERT INTO stt_project_build_agents(id,project_id,pairing_offer_id,credential_digest," +
        "protocol_version) VALUES ($1,$2,$3,$4,'v1')",
      [agent, left.project, offer, "sha256:" + "c".repeat(64)],
    );
    const requestKey = randomUUID();
    const job = await submission(db, left.project, left.actor, requestKey);
    await expect(submission(db, left.project, left.actor, requestKey)).rejects.toThrow();
    // Project membership is enforced by #379 service authorization, not by
    // the global identity FK. The idempotency key is project/actor scoped.
    await submission(db, right.project, right.actor, requestKey);
    await expect(db.query(
      "INSERT INTO stt_build_dispatches(project_id,job_id,assigned_agent_id,status) " +
        "VALUES($1,$2,$3,'queued')", [right.project, job, agent],
    )).rejects.toThrow();
    await db.query("INSERT INTO stt_build_dispatches(project_id,job_id,status) " +
      "VALUES($1,$2,'queued')", [left.project, job]);
    await expect(db.query("UPDATE stt_build_dispatches SET status='native_success' WHERE job_id=$1",
      [job])).rejects.toThrow();
    await db.query(
      "INSERT INTO stt_build_source_pins(project_id,job_id,source_id,source_revision,source_digest) " +
        "VALUES($1,$2,$3,'1',$4)",
      [left.project, job, randomUUID(), digest],
    );
    await expect(db.query("DELETE FROM stt_build_source_pins WHERE job_id=$1", [job]))
      .rejects.toThrow("append-only");
    await expect(db.query("UPDATE stt_build_submissions SET document_json='[]' WHERE id=$1",
      [job])).rejects.toThrow("append-only");
    await expect(db.query("DELETE FROM stt_build_submissions WHERE id=$1", [job]))
      .rejects.toThrow("append-only");

    const event = await db.query<{ id: string }>(
      "INSERT INTO stt_build_events(project_id,job_id,lease_epoch,status) " +
        "VALUES($1,$2,0,'queued') RETURNING id::text", [left.project, job],
    );
    const eventId = event.rows[0]?.id;
    await db.query(
      "INSERT INTO stt_build_evidence(id,project_id,job_id,event_id,stage_key," +
        "receipt_digest,output_digest,evidence_kind,verification_digest) " +
        "VALUES($1,$2,$3,$4,'compile',$5,$6,'synthetic',$7)",
      [randomUUID(), left.project, job, eventId, digest, digest, digest],
    );
    await expect(db.query("DELETE FROM stt_build_events WHERE id=$1", [eventId]))
      .rejects.toThrow("append-only");
    await expect(db.query("UPDATE stt_build_evidence SET evidence_kind='native_readback' " +
      "WHERE job_id=$1", [job])).rejects.toThrow("append-only");
  });

  it("refusal receipts are scoped, unique, hash-checked and append-only", async () => {
    const db = await migrated();
    const first = await actorAndProject(db);
    const request = randomUUID();
    await db.query(
      "INSERT INTO stt_build_preflight_refusals(project_id,submitted_by,idempotency_key," +
        "request_digest,expected_revision,reason_code) VALUES($1,$2,$3,$4,0,'settings_unavailable')",
      [first.project, first.actor, request, digest],
    );
    await expect(db.query(
      "INSERT INTO stt_build_preflight_refusals(project_id,submitted_by,idempotency_key," +
        "request_digest,expected_revision,reason_code) VALUES($1,$2,$3,$4,0,'settings_unavailable')",
      [first.project, first.actor, request, digest],
    )).rejects.toThrow();
    await expect(db.query("UPDATE stt_build_preflight_refusals SET reason_code='settings_unavailable'"))
      .rejects.toThrow("append-only");
    await expect(db.query("DELETE FROM stt_build_preflight_refusals"))
      .rejects.toThrow("append-only");
  });
});
