import { randomUUID } from "node:crypto";

import type { RowGapV2 } from "@vera/contracts/v2";
import {
  applyProjectAuthorizationMigration, ProjectAuthorizationService, type SqlClient, type SqlPool,
} from "@vera/project-authorization";
import pg from "pg";
import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyIdeasV1, type IdeaItemV1, type IdeaOutlineV1 } from "../src/ideas-model.js";
import { sha256 } from "../src/model.js";
import {
  applyProjectCommentsMigration, applyProjectDocumentsMigration,
  applyProjectHistoryMigration, applyProjectIdeasMigration,
} from "../src/migration.js";
import { ProjectDocumentService, type PromoteIdeaInput } from "../src/service.js";
import { harness, initialProject } from "./helpers.js";

vi.setConfig({ testTimeout: 90_000 });

const cleanup: Array<() => Promise<void>> = [];
const gap: RowGapV2 = { sectionId: null, afterRowId: null, beforeRowId: null };
const item = (orderKey = "a", parentId: string | null = null, text = "  Idea  text\nunchanged  "): IdeaItemV1 => ({
  id: randomUUID(), parentId, orderKey, text, state: "open",
  linkedDraftBlockIds: [], collapsed: false, version: 1,
});
const outline = (documentId: string, items: IdeaItemV1[]): IdeaOutlineV1 =>
  ({ ...emptyIdeasV1(documentId), items });
const promotion = (source: IdeaItemV1, expectedIdeasRevision = 1, expectedRevision = 0,
  destination: RowGapV2 = gap, blockId = randomUUID(), mutationId = randomUUID()): PromoteIdeaInput => ({
  expectedIdeasRevision, expectedRevision, clientMutationId: mutationId,
  ideaId: source.id, draftBlockId: blockId, orderKey: "a", destination,
});

async function setup() {
  const h = await harness();
  cleanup.push(async () => { await h.db.close(); });
  const initial = initialProject();
  await h.service.createProject(h.owner, initial);
  const parent = { ...item("a", null, "Parent Idea"), collapsed: true };
  const source = item("a", parent.id);
  const sibling = item("b", parent.id, "Sibling");
  const ideas = outline(initial.document.id, [parent, source, sibling]);
  await h.service.putIdeas(initial.projectId, h.owner, {
    expectedIdeasRevision: 0, clientMutationId: randomUUID(), ideas,
  });
  return { ...h, initial, projectId: initial.projectId, parent, source, sibling, ideas };
}

async function snapshot(db: Awaited<ReturnType<typeof harness>>["db"], projectId: string) {
  const rows = await db.query<{
    documents: number; ideas: number; receipts: number;
    document_revision: string; ideas_revision: string;
    document_json: string; ideas_json: string;
  }>(
    "SELECT (SELECT count(*)::int FROM stt_document_revisions WHERE project_id=$1) AS documents," +
      "(SELECT count(*)::int FROM stt_idea_revisions WHERE project_id=$1) AS ideas," +
      "(SELECT count(*)::int FROM stt_ideas_mutation_receipts WHERE project_id=$1) AS receipts," +
      "d.revision::text AS document_revision,i.revision::text AS ideas_revision," +
      "d.document_json,i.ideas_json FROM stt_document_heads d JOIN stt_idea_heads i" +
      " ON i.project_id=d.project_id WHERE d.project_id=$1",
    [projectId],
  );
  return rows.rows[0]!;
}

afterEach(async () => { for (const close of cleanup.splice(0)) await close(); });

describe("authorized, two-head atomic Ideas promotion", () => {
  it("copies exact nested source into one excluded Draft note, keeps metadata and commits paired immutable revisions", async () => {
    const { db, pool, auth, service, owner, initial, projectId, parent, source, sibling, ideas } = await setup();
    const input = promotion(source);
    const receipt = await service.promoteIdea(projectId, owner, input);
    const doc = await service.getDocument(projectId, owner);
    const now = await service.getIdeas(projectId, owner);
    expect(receipt).toMatchObject({ projectId, clientMutationId: input.clientMutationId,
      documentRevision: 1, ideasRevision: 2, duplicateDelivery: false });
    expect(receipt.documentDigest).toBe(doc.digest);
    expect(receipt.ideasDigest).toBe(now.digest);
    expect(doc.document.activeDraft.blocks).toEqual([{
      type: "note_draft", id: input.draftBlockId, orderKey: "a", text: source.text,
      state: "excluded", version: 1,
    }]);
    expect(doc.document.ideaOutline).toEqual([]);
    expect(doc.document.extras).toEqual([]);
    expect(doc.document.rowEditRevision).toBe(1);
    for (const field of ["id", "projectId", "liveHeadSequence", "liveStateVector", "liveContentHash"] as const) {
      expect(doc.document[field]).toEqual(initial.document[field]);
    }
    expect(now.ideas.items).toEqual([
      parent, { ...source, version: 2, state: "incorporated", linkedDraftBlockIds: [input.draftBlockId] },
      sibling,
    ]);
    expect(ideas.items[1]).toEqual(source);
    expect(await snapshot(db, projectId)).toMatchObject({
      documents: 2, ideas: 2, receipts: 2, document_revision: "1", ideas_revision: "2",
    });
    const paired = await db.query<{
      ideas_operation: string; document_revision: string; ideas_digest: string;
      document_digest: string; doc_actor: string; idea_actor: string;
    }>(
      "SELECT i.operation AS ideas_operation,i.document_revision::text,i.content_digest AS ideas_digest," +
        "d.content_digest AS document_digest,d.actor_id AS doc_actor,i.actor_id AS idea_actor" +
        " FROM stt_idea_revisions i JOIN stt_document_revisions d" +
        " ON d.project_id=i.project_id AND d.revision=i.document_revision" +
        " WHERE i.project_id=$1 AND i.operation='promote_idea'", [projectId],
    );
    expect(paired.rows).toEqual([{
      ideas_operation: "promote_idea", document_revision: "1", ideas_digest: now.digest,
      document_digest: doc.digest, doc_actor: owner.principalId, idea_actor: owner.principalId,
    }]);
    const reopened = new ProjectDocumentService(pool, auth);
    expect((await reopened.getIdeas(projectId, owner)).ideas).toEqual(now.ideas);
  });

  it("allows two distinct placements from one source but not an implicit duplicate", async () => {
    const { db, service, owner, projectId, source } = await setup();
    const first = promotion(source);
    await service.promoteIdea(projectId, owner, first);
    const second = promotion(source, 2, 1,
      { sectionId: null, afterRowId: first.draftBlockId, beforeRowId: null });
    second.orderKey = "b";
    await service.promoteIdea(projectId, owner, second);
    const doc = await service.getDocument(projectId, owner);
    expect(doc.document.activeDraft.blocks.map((row) => row.id))
      .toEqual([first.draftBlockId, second.draftBlockId]);
    expect(doc.document.activeDraft.blocks.map((row) => row.type)).toEqual(["note_draft", "note_draft"]);
    expect((await service.getIdeas(projectId, owner)).ideas.items[1]).toEqual({
      ...source, state: "incorporated", version: 3,
      linkedDraftBlockIds: [first.draftBlockId, second.draftBlockId],
    });
    expect(await snapshot(db, projectId)).toMatchObject({ documents: 3, ideas: 3, receipts: 3 });
  });

  it("replays a paired immutable receipt after later edits, never appends or swaps the row", async () => {
    const { db, service, owner, projectId, source, initial } = await setup();
    const first = promotion(source);
    const receipt = await service.promoteIdea(projectId, owner, first);
    const further = promotion(source, 2, 1,
      { sectionId: null, afterRowId: first.draftBlockId, beforeRowId: null });
    further.orderKey = "b";
    await service.promoteIdea(projectId, owner, further);
    expect(await service.promoteIdea(projectId, owner, first))
      .toEqual({ ...receipt, duplicateDelivery: true });
    for (const changed of [
      { ...first, orderKey: "x" },
      { ...first, expectedRevision: 1 },
      { ...first, draftBlockId: randomUUID() },
      { ...first, ideaId: randomUUID() },
    ]) await expect(service.promoteIdea(projectId, owner, changed))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    // A promotion key cannot masquerade as a document or Ideas PUT receipt.
    await expect(service.putDocument(projectId, owner, { expectedRevision: 2,
      clientMutationId: first.clientMutationId, document: initial.document }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.putIdeas(projectId, owner, { expectedIdeasRevision: 3,
      clientMutationId: first.clientMutationId, ideas: (await service.getIdeas(projectId, owner)).ideas }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect(await snapshot(db, projectId)).toMatchObject({ documents: 3, ideas: 3, receipts: 3 });
  });

  it("rejects a document PUT key, an Ideas PUT key or a reused promotion key across operations", async () => {
    const { db, service, owner, projectId, source, initial } = await setup();
    const key = randomUUID();
    await service.putDocument(projectId, owner, { expectedRevision: 0,
      clientMutationId: key, document: { ...initial.document, title: "Updated" } });
    await expect(service.promoteIdea(projectId, owner, promotion(source, 1, 1, gap, randomUUID(), key)))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const ideasKey = randomUUID();
    const outlineNow = (await service.getIdeas(projectId, owner)).ideas;
    await service.putIdeas(projectId, owner, { expectedIdeasRevision: 1,
      clientMutationId: ideasKey, ideas: outlineNow });
    await expect(service.promoteIdea(projectId, owner, promotion(source, 2, 1, gap, randomUUID(), ideasKey)))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect(await snapshot(db, projectId)).toMatchObject({ documents: 2, ideas: 2, receipts: 2 });
  });

  it("checks both independent expected versions and aborts entirely for either stale head", async () => {
    const { db, service, owner, projectId, source, initial } = await setup();
    const promoted = promotion(source);
    await service.promoteIdea(projectId, owner, promoted);
    const before = await snapshot(db, projectId);
    await expect(service.promoteIdea(projectId, owner, promotion(source, 1, 1, gap, randomUUID())))
      .rejects.toMatchObject({ status: 409, metadata: { currentIdeasRevision: 2 } });
    await expect(service.promoteIdea(projectId, owner, promotion(source, 2, 0, gap, randomUUID())))
      .rejects.toMatchObject({ status: 409, metadata: { currentRevision: 1 } });
    expect(await snapshot(db, projectId)).toEqual(before);
    await service.putDocument(projectId, owner, { expectedRevision: 1, clientMutationId: randomUUID(),
      document: { ...(await service.getDocument(projectId, owner)).document, title: "Draft changed" } });
    const docChanged = await snapshot(db, projectId);
    await expect(service.promoteIdea(projectId, owner, promotion(source, 2, 1, gap, randomUUID())))
      .rejects.toMatchObject({ status: 409, metadata: { currentRevision: 2 } });
    expect(await snapshot(db, projectId)).toEqual(docChanged);
    expect(initial.document.activeDraft.blocks).toEqual([]);
  });

  it("rejects malformed commands, forged positions, duplicate IDs, missing Ideas and foreign projects", async () => {
    const { db, service, owner, viewer, projectId, source, parent, initial } = await setup();
    const before = await snapshot(db, projectId);
    const bad: PromoteIdeaInput[] = [
      { ...promotion(source), draftBlockId: source.id },
      { ...promotion(source), draftBlockId: parent.id },
      { ...promotion(source), ideaId: randomUUID() },
      { ...promotion(source), orderKey: "   " },
      { ...promotion(source), destination: { ...gap, beforeRowId: randomUUID() } },
      { ...promotion(source), destination: { ...gap, sectionId: randomUUID() } },
      { ...promotion(source), destination: { ...gap, extra: true } as never },
      { ...promotion(source), role: "producer" } as never,
      { ...promotion(source), expectedRevision: -1 },
    ];
    for (const input of bad) await expect(service.promoteIdea(projectId, owner, input))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.promoteIdea(projectId, owner, null as never))
      .rejects.toMatchObject({ status: 400 });
    expect(await snapshot(db, projectId)).toEqual(before);
    const other = initialProject();
    await service.createProject(viewer, other);
    await expect(service.promoteIdea(other.projectId, owner, promotion(source)))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.promoteIdea(projectId, viewer, promotion(source)))
      .rejects.toMatchObject({ status: 403 });
    expect((await service.getDocument(projectId, owner)).document).toEqual(initial.document);
  });

  it("rechecks editor permissions and write-session validity even on exact replay", async () => {
    const { auth, service, owner, editor, viewer, projectId, source } = await setup();
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
    const session = await auth.openWriteSession(projectId, editor);
    const input = { ...promotion(source), writeSessionId: session };
    await expect(service.promoteIdea(projectId, viewer, input)).rejects.toMatchObject({ status: 403 });
    const done = await service.promoteIdea(projectId, editor, input);
    expect(done.documentRevision).toBe(1);
    expect((await service.promoteIdea(projectId, editor, input)).duplicateDelivery).toBe(true);
    await auth.changeMembership(projectId, owner, editor.principalId, null);
    await expect(service.promoteIdea(projectId, editor, input)).rejects.toMatchObject({ status: 403 });
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await expect(service.promoteIdea(projectId, editor, input)).rejects.toMatchObject({ status: 403 });
  });

  it("rolls back both revisions, both heads and receipt when late SQL writes fail", async () => {
    const { db, pool, service, owner, projectId, source } = await setup();
    const first = promotion(source);
    const before = await snapshot(db, projectId);
    for (const prefix of [
      "UPDATE stt_document_heads", "INSERT INTO stt_idea_revisions",
      "UPDATE stt_idea_heads", "INSERT INTO stt_ideas_mutation_receipts",
    ]) {
      const brokenPool: SqlPool = { connect: async () => {
        const client = await pool.connect();
        return { query: async <R>(sql: string, params?: readonly unknown[]) => {
          if (sql.startsWith(prefix)) throw new Error("synthetic late DB failure");
          return await client.query<R>(sql, params);
        }, release: () => client.release?.() } satisfies SqlClient;
      } };
      const broken = new ProjectDocumentService(brokenPool, new ProjectAuthorizationService(brokenPool));
      await expect(broken.promoteIdea(projectId, owner, first)).rejects.toMatchObject({ status: 503 });
      expect(await snapshot(db, projectId)).toEqual(before);
      expect((await service.getIdeas(projectId, owner)).ideas.items[1]).toEqual(source);
      expect((await service.getDocument(projectId, owner)).document.activeDraft.blocks).toEqual([]);
    }
    expect((await service.promoteIdea(projectId, owner, first)).documentRevision).toBe(1);
  });

  it("rejects tampered head digests and does not reconstruct damaged content", async () => {
    const { db, service, owner, projectId, source } = await setup();
    const before = await snapshot(db, projectId);
    await db.query("UPDATE stt_document_heads SET content_digest=$2 WHERE project_id=$1",
      [projectId, sha256("tampered")]);
    await expect(service.promoteIdea(projectId, owner, promotion(source)))
      .rejects.toMatchObject({ status: 503 });
    await db.query("UPDATE stt_document_heads SET content_digest=$2 WHERE project_id=$1",
      [projectId, sha256(before.document_json)]);
    await db.query("UPDATE stt_idea_heads SET content_digest=$2 WHERE project_id=$1",
      [projectId, sha256("tampered")]);
    await expect(service.promoteIdea(projectId, owner, promotion(source)))
      .rejects.toMatchObject({ status: 503 });
    expect(await snapshot(db, projectId)).toMatchObject({ documents: 1, ideas: 1, receipts: 1 });
  });
});

/** Real independent connections; never point this integration suite at a production database. */
const scratchUrl = process.env.VERA_PROJECT_DOCUMENTS_TEST_DATABASE_URL;
const postgres = scratchUrl ? it : it.skip;
postgres("serializes competing promotions on disposable PostgreSQL without orphaning either revision", async () => {
  const server = new pg.Pool({ connectionString: scratchUrl, max: 8 });
  const pool: SqlPool = { connect: async (): Promise<SqlClient> => {
    const client = await server.connect();
    return {
      query: async <R>(sql: string, params?: readonly unknown[]) => {
        const result = await client.query(sql, params ? [...params] : []);
        return { rows: result.rows as R[] };
      },
      release: () => { client.release(); },
    };
  } };
  try {
    const migration = await pool.connect();
    try {
      await applyProjectAuthorizationMigration(migration);
      await applyProjectDocumentsMigration(migration);
      await applyProjectCommentsMigration(migration);
      await applyProjectHistoryMigration(migration);
      await applyProjectIdeasMigration(migration);
    } finally { migration.release?.(); }
    const auth = new ProjectAuthorizationService(pool);
    const service = new ProjectDocumentService(pool, auth);
    const owner = await auth.resolveActor({ issuer: "https://trusted.integration.test", subject: randomUUID() });
    const initial = initialProject();
    await service.createProject(owner, initial);
    const source = item();
    await service.putIdeas(initial.projectId, owner, { expectedIdeasRevision: 0,
      clientMutationId: randomUUID(), ideas: outline(initial.document.id, [source]) });

    const competitors = await Promise.allSettled([
      service.promoteIdea(initial.projectId, owner, promotion(source)),
      service.promoteIdea(initial.projectId, owner, promotion(source)),
    ]);
    expect(competitors.filter((result) => result.status === "fulfilled")).toHaveLength(1);
    expect(competitors.filter((result) => result.status === "rejected"))
      .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
    const ideas = await service.getIdeas(initial.projectId, owner);
    const doc = await service.getDocument(initial.projectId, owner);
    expect(ideas.ideasRevision).toBe(2);
    expect(doc.revision).toBe(1);
    expect(doc.document.activeDraft.blocks).toHaveLength(1);
    expect(ideas.ideas.items[0]?.linkedDraftBlockIds)
      .toEqual([doc.document.activeDraft.blocks[0]!.id]);

    const next = promotion(source, 2, 1,
      { sectionId: null, afterRowId: doc.document.activeDraft.blocks[0]!.id, beforeRowId: null });
    next.orderKey = "b";
    const second = await Promise.allSettled([
      service.promoteIdea(initial.projectId, owner, next),
      service.putDocument(initial.projectId, owner, { expectedRevision: 1,
        clientMutationId: randomUUID(), document: { ...doc.document, title: "Competing edit" } }),
    ]);
    expect(second.filter((result) => result.status === "fulfilled")).toHaveLength(1);
    expect(second.filter((result) => result.status === "rejected"))
      .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
    const finalIdeas = await service.getIdeas(initial.projectId, owner);
    const finalDoc = await service.getDocument(initial.projectId, owner);
    expect(finalDoc.revision).toBe(2);
    expect(finalIdeas.ideasRevision).toBe(second[0]?.status === "fulfilled" ? 3 : 2);
    expect(finalDoc.document.activeDraft.blocks).toHaveLength(finalIdeas.ideas.items[0]!.linkedDraftBlockIds.length);
    const db = await pool.connect();
    try {
      const counts = await db.query<{ docs: number; ideas: number; receipts: number }>(
        "SELECT (SELECT count(*)::int FROM stt_document_revisions WHERE project_id=$1) AS docs," +
          " (SELECT count(*)::int FROM stt_idea_revisions WHERE project_id=$1) AS ideas," +
          " (SELECT count(*)::int FROM stt_ideas_mutation_receipts WHERE project_id=$1) AS receipts",
        [initial.projectId],
      );
      expect(counts.rows).toEqual([{ docs: 3,
        ideas: finalIdeas.ideasRevision, receipts: finalIdeas.ideasRevision }]);
    } finally { db.release?.(); }
  } finally { await server.end(); }
});
