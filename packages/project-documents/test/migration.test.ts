import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectSubtitleCopiesMigration,
  PROJECT_COMMENTS_MIGRATION,
  PROJECT_COMMENTS_MIGRATION_DIGEST,
  PROJECT_DOCUMENTS_MIGRATION,
  PROJECT_HISTORY_MIGRATION,
  PROJECT_HISTORY_MIGRATION_DIGEST,
  PROJECT_SUBTITLE_COPIES_MIGRATION,
  PROJECT_SUBTITLE_COPIES_MIGRATION_DIGEST,
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

describe("forward-only STT subtitle copies schema 005", () => {
  it("requires project documents, pins its receipt, is repeatable and preserves old schema/data", async () => {
    const db = await database();
    await expect(applyProjectSubtitleCopiesMigration(db)).rejects.toThrow();
    const uncommitted = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM vera_schema_migrations WHERE migration_name=$1",
      [PROJECT_SUBTITLE_COPIES_MIGRATION],
    );
    expect(uncommitted.rows[0]?.n).toBe(0);
    await applyProjectDocumentsMigration(db);
    const actor = randomUUID(), project = randomUUID(), document = randomUUID();
    const digest = `sha256:${"a".repeat(64)}`;
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','subtitle-owner')", [actor]);
    await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'Existing project',$2,$3,$4)", [project, actor, randomUUID(), digest]);
    await db.query("INSERT INTO stt_document_revisions(project_id,revision,document_id,expected_revision," +
      "actor_id,client_mutation_id,request_digest,content_digest,document_json) " +
      "VALUES($1,0,$2,NULL,$3,$4,$5,$5,$6)",
    [project, document, actor, randomUUID(), digest, '{"frozen":"prior document"}']);
    const before = await db.query<{ document_json: string }>(
      "SELECT document_json FROM stt_document_revisions WHERE project_id=$1 AND revision=0", [project],
    );
    await applyProjectSubtitleCopiesMigration(db);
    await applyProjectSubtitleCopiesMigration(db);
    const receipt = await db.query<{ schema_version: number; checksum: string }>(
      "SELECT schema_version,encode(checksum,'hex') AS checksum FROM vera_schema_migrations " +
      "WHERE migration_name=$1", [PROJECT_SUBTITLE_COPIES_MIGRATION],
    );
    expect(receipt.rows).toEqual([{
      schema_version: 5, checksum: PROJECT_SUBTITLE_COPIES_MIGRATION_DIGEST,
    }]);
    const tables = await db.query<{ tablename: string }>(
      "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'stt_subtitle_copy_%'",
    );
    expect(tables.rows.map(({ tablename }) => tablename).sort()).toEqual([
      "stt_subtitle_copy_heads", "stt_subtitle_copy_revisions",
    ]);
    const after = await db.query<{ document_json: string }>(
      "SELECT document_json FROM stt_document_revisions WHERE project_id=$1 AND revision=0", [project],
    );
    expect(after.rows).toEqual(before.rows);
    const receipt001 = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM vera_schema_migrations WHERE migration_name=$1",
      [PROJECT_DOCUMENTS_MIGRATION],
    );
    expect(receipt001.rows[0]?.n).toBe(1);
  });

  it("refuses checksum or version tampering without rewriting history", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectSubtitleCopiesMigration(db);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["0".repeat(64), PROJECT_SUBTITLE_COPIES_MIGRATION]);
    await expect(applyProjectSubtitleCopiesMigration(db)).rejects.toThrow("checksum mismatch");
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=99 " +
      "WHERE migration_name=$2", [PROJECT_SUBTITLE_COPIES_MIGRATION_DIGEST, PROJECT_SUBTITLE_COPIES_MIGRATION]);
    await expect(applyProjectSubtitleCopiesMigration(db)).rejects.toThrow("checksum mismatch");
    const rows = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_subtitle_copy_revisions",
    );
    expect(rows.rows[0]?.count).toBe(0);
  });

  it("keeps immutable provenance, contiguous CAS revisions and preserved old copies after rederive", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectSubtitleCopiesMigration(db);
    const actor = randomUUID(), project = randomUUID(), occurrence = randomUUID(), track = randomUUID();
    const digestA = `sha256:${"a".repeat(64)}`, digestB = `sha256:${"b".repeat(64)}`;
    const digestC = `sha256:${"c".repeat(64)}`;
    const frozenSource = '{"source":"exact original transcript","englishText":"Hello"}';
    const sourceChanged = '{"source":"changed transcript","englishText":"Greetings"}';
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','subtitle-writer')", [actor]);
    await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'Subtitle copy',$2,$3,$4)", [project, actor, randomUUID(), digestA]);
    const insert = "INSERT INTO stt_subtitle_copy_revisions(project_id,occurrence_id,track_id," +
      "revision,expected_revision,operation,actor_id,client_mutation_id,request_digest," +
      "source_json,source_digest,baseline_english,track_json,content_digest) " +
      "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)";
    const revision = (version: number, expected: number, operation: string, mutation: string = randomUUID(),
      source = frozenSource, sourceDigest = digestA, baseline = "Hello", textDigest = digestB,
    ) => [project, occurrence, track, version, expected, operation, actor, mutation, digestA,
      source, sourceDigest, baseline, JSON.stringify({ version, operation, source, baseline }), textDigest];
    const first = revision(1, 0, "derive");
    await expect(db.query(insert, [randomUUID(), ...first.slice(1)])).rejects.toThrow();
    await db.query(insert, first);
    const head = "INSERT INTO stt_subtitle_copy_heads(project_id,occurrence_id,track_id,revision," +
      "source_digest,content_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6,$7)";
    await expect(db.query(head, [project, randomUUID(), randomUUID(), 2, digestA, digestB, actor]))
      .rejects.toThrow();
    await db.query(head, [project, occurrence, track, 1, digestA, digestB, actor]);
    await expect(db.query(head, [project, randomUUID(), track, 1, digestA, digestB, actor]))
      .rejects.toThrow();
    await expect(db.query(insert, revision(1, 0, "derive"))).rejects.toThrow();
    await expect(db.query(insert, revision(2, 0, "edit"))).rejects.toThrow();
    await expect(db.query(insert, revision(3, 2, "edit"))).rejects.toThrow(/not contiguous/u);
    await expect(db.query(insert, revision(2, 1, "edit", randomUUID(), sourceChanged)))
      .rejects.toThrow(/provenance is immutable/u);
    await expect(db.query(insert, revision(2, 1, "approve", randomUUID(), frozenSource, digestA,
      "Rewritten baseline"))).rejects.toThrow(/provenance is immutable/u);
    await expect(db.query(insert, revision(2, 1, "rederive"))).rejects.toThrow(/changed source/u);
    const second = revision(2, 1, "edit", randomUUID(), frozenSource, digestA, "Hello", digestC);
    await db.query(insert, second);
    await expect(db.query("UPDATE stt_subtitle_copy_heads SET revision=3 WHERE project_id=$1 AND occurrence_id=$2",
      [project, occurrence])).rejects.toThrow(/next-revision CAS/u);
    await expect(db.query("UPDATE stt_subtitle_copy_heads SET revision=2,content_digest=$3," +
      "source_digest=$4 WHERE project_id=$1 AND occurrence_id=$2",
    [project, occurrence, digestB, digestA])).rejects.toThrow();
    await db.query("UPDATE stt_subtitle_copy_heads SET revision=2,content_digest=$3," +
      "updated_by=$4 WHERE project_id=$1 AND occurrence_id=$2 AND revision=1 AND source_digest=$5",
    [project, occurrence, digestC, actor, digestA]);
    await expect(db.query("DELETE FROM stt_subtitle_copy_heads WHERE project_id=$1", [project]))
      .rejects.toThrow(/cannot be deleted/u);
    await expect(db.query("UPDATE stt_subtitle_copy_revisions SET source_json=$2 WHERE project_id=$1",
      [project, sourceChanged])).rejects.toThrow(/append-only/u);
    await expect(db.query("DELETE FROM stt_subtitle_copy_revisions WHERE project_id=$1", [project]))
      .rejects.toThrow(/append-only/u);
    const third = revision(3, 2, "rederive", randomUUID(), sourceChanged, digestB, "Greetings", digestA);
    await db.query(insert, third);
    await db.query("UPDATE stt_subtitle_copy_heads SET revision=3,source_digest=$3,content_digest=$4," +
      "updated_by=$5 WHERE project_id=$1 AND occurrence_id=$2 AND revision=2 AND source_digest=$6",
    [project, occurrence, digestB, digestA, actor, digestA]);
    const history = await db.query<{ revision: string; source_json: string; baseline_english: string }>(
      "SELECT revision::text,source_json,baseline_english FROM stt_subtitle_copy_revisions " +
      "WHERE project_id=$1 AND occurrence_id=$2 ORDER BY revision", [project, occurrence],
    );
    expect(history.rows).toEqual([
      { revision: "1", source_json: frozenSource, baseline_english: "Hello" },
      { revision: "2", source_json: frozenSource, baseline_english: "Hello" },
      { revision: "3", source_json: sourceChanged, baseline_english: "Greetings" },
    ]);
    const current = await db.query<{ revision: string; source_digest: string }>(
      "SELECT revision::text,source_digest FROM stt_subtitle_copy_heads WHERE project_id=$1", [project],
    );
    expect(current.rows).toEqual([{ revision: "3", source_digest: digestB }]);
    await expect(db.query(insert, revision(4, 3, "edit", first[7] as string,
      sourceChanged, digestB, "Greetings"))).rejects.toThrow();
  });
});

describe("forward-only STT history schema 003", () => {
  it("requires document schema, records its exact receipt and repeats without changing prior migrations", async () => {
    const db = await database();
    await expect(applyProjectHistoryMigration(db)).rejects.toThrow();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectHistoryMigration(db);
    const before = await db.query<{ migration_name: string; schema_version: number; checksum: string }>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(before.rows).toHaveLength(3);
    expect(before.rows.find((row) => row.migration_name === PROJECT_HISTORY_MIGRATION)).toMatchObject({
      schema_version: 3, checksum: PROJECT_HISTORY_MIGRATION_DIGEST,
    });
    await applyProjectHistoryMigration(db);
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    const after = await db.query<typeof before.rows[number]>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(after.rows).toEqual(before.rows);
    const tables = await db.query<{ name: string }>(
      "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' " +
      "AND tablename IN ('stt_document_checkpoints','stt_checkpoint_approvals','stt_document_restores')",
    );
    expect(tables.rows.map(({ name }) => name).sort()).toEqual([
      "stt_checkpoint_approvals", "stt_document_checkpoints", "stt_document_restores",
    ]);
  });

  it("fails closed on checksum or version tampering without altering schema/data", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectHistoryMigration(db);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["0".repeat(64), PROJECT_HISTORY_MIGRATION]);
    await expect(applyProjectHistoryMigration(db)).rejects.toThrow("checksum mismatch");
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=44 " +
      "WHERE migration_name=$2", [PROJECT_HISTORY_MIGRATION_DIGEST, PROJECT_HISTORY_MIGRATION]);
    await expect(applyProjectHistoryMigration(db)).rejects.toThrow("checksum mismatch");
    const rows = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_document_checkpoints",
    );
    expect(rows.rows[0]?.count).toBe(0);
  });

  it("enforces project FKs, unique checkpoint name/receipts, immutable history and provenance", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectHistoryMigration(db);
    const actor = randomUUID(), project = randomUUID(), document = randomUUID();
    const checkpoint = randomUUID(), approval = randomUUID(), mutation = randomUUID();
    const digest = `sha256:${"a".repeat(64)}`;
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','history-actor')", [actor]);
    await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'History',$2,$3,$4)", [project, actor, randomUUID(), digest]);
    const revisionSql = "INSERT INTO stt_document_revisions(project_id,revision,document_id," +
      "expected_revision,actor_id,client_mutation_id,request_digest,content_digest,document_json) " +
      "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)";
    await db.query(revisionSql, [project, 0, document, null, actor, randomUUID(), digest, digest, "{}"]);
    await db.query(revisionSql, [project, 1, document, 0, actor, randomUUID(), digest, digest, "{}"]);
    await db.query(revisionSql, [project, 2, document, 1, actor, randomUUID(), digest, digest, "{}"]);
    const checkpointSql = "INSERT INTO stt_document_checkpoints(project_id,checkpoint_id,name," +
      "source_revision,document_id,document_json,source_digest,created_by,client_mutation_id," +
      "request_digest) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)";
    const values = [project, checkpoint, "Draft A", 0, document, "{}", digest, actor, mutation, digest];
    await db.query(checkpointSql, values);
    await expect(db.query(checkpointSql, [...values.slice(0, 1), randomUUID(), "draft a",
      ...values.slice(3, 8), randomUUID(), digest])).rejects.toThrow();
    await expect(db.query(checkpointSql, [project, randomUUID(), "B", 0, document, "{}",
      digest, actor, mutation, digest])).rejects.toThrow();
    await expect(db.query(checkpointSql, [project, randomUUID(), "Missing", 999, document,
      "{}", digest, actor, randomUUID(), digest])).rejects.toThrow();
    await expect(db.query(checkpointSql, [randomUUID(), randomUUID(), "Foreign", 0, document,
      "{}", digest, actor, randomUUID(), digest])).rejects.toThrow();
    await db.query("INSERT INTO stt_checkpoint_approvals(project_id,checkpoint_id,approved_by," +
      "client_mutation_id,request_digest) VALUES($1,$2,$3,$4,$5)",
    [project, checkpoint, actor, approval, digest]);
    await expect(db.query("INSERT INTO stt_checkpoint_approvals(project_id,checkpoint_id,approved_by," +
      "client_mutation_id,request_digest) VALUES($1,$2,$3,$4,$5)",
    [project, checkpoint, actor, randomUUID(), digest])).rejects.toThrow();
    await db.query("INSERT INTO stt_document_restores(project_id,new_revision,checkpoint_id," +
      "source_revision,source_digest,restored_by,client_mutation_id) VALUES($1,$2,$3,$4,$5,$6,$7)",
    [project, 1, checkpoint, 0, digest, actor, randomUUID()]);
    // The new revision exists, so this specifically exercises the composite
    // source-checkpoint tuple FK rather than the new-revision FK.
    await expect(db.query("INSERT INTO stt_document_restores(project_id,new_revision,checkpoint_id," +
      "source_revision,source_digest,restored_by,client_mutation_id) VALUES($1,$2,$3,$4,$5,$6,$7)",
    [project, 2, checkpoint, 0, `sha256:${"b".repeat(64)}`, actor, randomUUID()])).rejects.toThrow();
    await expect(db.query("INSERT INTO stt_document_restores(project_id,new_revision,checkpoint_id," +
      "source_revision,source_digest,restored_by,client_mutation_id) " +
      "VALUES($1,2,$2,1,$3,$4,$5)",
    [project, checkpoint, digest, actor, randomUUID()])).rejects.toThrow();
    for (const table of ["stt_document_checkpoints", "stt_checkpoint_approvals", "stt_document_restores"]) {
      await expect(db.query(`UPDATE ${table} SET project_id=project_id WHERE project_id=$1`,
        [project])).rejects.toThrow(/append-only/u);
      await expect(db.query(`DELETE FROM ${table} WHERE project_id=$1`, [project]))
        .rejects.toThrow(/append-only/u);
      const rows = await db.query<{ count: number }>(
        `SELECT count(*)::integer AS count FROM ${table} WHERE project_id=$1`, [project]);
      expect(rows.rows[0]?.count).toBe(1);
    }
  });
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

describe("forward-only STT comment schema 002", () => {
  it("runs after 001, records exact SHA/version, and is repeatable without touching 001", async () => {
    const db = await database();
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectDocumentsMigration(db);
    const rows = await db.query<{ migration_name: string; schema_version: number; checksum: string }>(
      "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
      "FROM vera_schema_migrations WHERE migration_name LIKE 'stt_project_%' ORDER BY migration_name",
    );
    expect(rows.rows).toHaveLength(2);
    expect(rows.rows.find((row) => row.migration_name === PROJECT_COMMENTS_MIGRATION)).toMatchObject({
      schema_version: 2, checksum: PROJECT_COMMENTS_MIGRATION_DIGEST,
    });
    expect(rows.rows.some((row) => row.migration_name === PROJECT_DOCUMENTS_MIGRATION)).toBe(true);
    const tables = await db.query<{ name: string }>(
      "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'stt_comment_%'",
    );
    expect(tables.rows.map((row) => row.name).sort()).toEqual(["stt_comment_events", "stt_comment_heads"]);
  });

  it("refuses mismatched digest or version without applying another migration", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex') WHERE migration_name=$2",
      ["00".repeat(32), PROJECT_COMMENTS_MIGRATION]);
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow("checksum mismatch");
    await db.query("UPDATE vera_schema_migrations SET checksum=decode($1,'hex'),schema_version=99 " +
      "WHERE migration_name=$2", [PROJECT_COMMENTS_MIGRATION_DIGEST, PROJECT_COMMENTS_MIGRATION]);
    await expect(applyProjectCommentsMigration(db)).rejects.toThrow("checksum mismatch");
    const result = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_comment_events",
    );
    expect(result.rows[0]?.count).toBe(0);
  });

  it("enforces event uniqueness, revision monotonicity, checksums and append-only triggers", async () => {
    const db = await database();
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    const actor = randomUUID();
    const project = randomUUID();
    const request = randomUUID();
    const digest = `sha256:${"a".repeat(64)}`;
    await db.query("INSERT INTO vera_identity_actors(id,issuer,subject) VALUES($1,'test','synthetic')", [actor]);
    await db.query("INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
      "VALUES($1,'Test',$2,$3,$4)", [project, actor, randomUUID(), digest]);
    const headSql = "INSERT INTO stt_comment_heads(project_id,document_id,document_revision,comment_revision," +
      "state_json,state_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6,$7)";
    await db.query(headSql, [project, randomUUID(), 0, 1, "{}", digest, actor]);
    await expect(db.query(headSql, [randomUUID(), randomUUID(), 0, 0, "{}", digest, actor])).rejects.toThrow();
    await expect(db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [project, "invalid"])).rejects.toThrow();
    const eventSql = "INSERT INTO stt_comment_events(project_id,comment_revision,expected_comment_revision," +
      "document_revision,actor_id,client_mutation_id,request_digest,operation_json) " +
      "VALUES($1,$2,$3,0,$4,$5,$6,$7)";
    await db.query(eventSql, [project, 1, 0, actor, request, digest, "{}"]);
    await expect(db.query(eventSql, [project, 3, 0, actor, randomUUID(), digest, "{}"])).rejects.toThrow();
    await expect(db.query(eventSql, [project, 2, 1, actor, request, digest, "{}"])).rejects.toThrow();
    await expect(db.query(eventSql, [project, 2, 1, actor, randomUUID(), "invalid", "{}"])).rejects.toThrow();
    await expect(db.query("UPDATE stt_comment_events SET operation_json='{}' WHERE project_id=$1",
      [project])).rejects.toThrow(/append-only/u);
    await expect(db.query("DELETE FROM stt_comment_events WHERE project_id=$1", [project]))
      .rejects.toThrow(/append-only/u);
    const history = await db.query<{ count: number }>(
      "SELECT count(*)::integer AS count FROM stt_comment_events WHERE project_id=$1", [project],
    );
    expect(history.rows[0]?.count).toBe(1);
  });
});
