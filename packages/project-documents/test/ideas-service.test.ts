import { randomUUID } from "node:crypto";

import { ProjectAuthorizationService, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyIdeasV1, type IdeaItemV1, type IdeaOutlineV1 } from "../src/ideas-model.js";
import { sha256 } from "../src/model.js";
import { ProjectDocumentService } from "../src/service.js";
import { harness, initialProject } from "./helpers.js";

vi.setConfig({ testTimeout: 90_000 });

const cleanup: Array<() => Promise<void>> = [];
async function setup() {
  const h = await harness();
  cleanup.push(async () => { await h.db.close(); });
  const initial = initialProject();
  await h.service.createProject(h.owner, initial);
  return { ...h, initial, projectId: initial.projectId, documentId: initial.document.id };
}
afterEach(async () => { for (const close of cleanup.splice(0)) await close(); });

const item = (orderKey = "a", parentId: string | null = null, text = "  original \ntext "): IdeaItemV1 => ({
  id: randomUUID(), parentId, orderKey, text, state: "open", linkedDraftBlockIds: [],
  collapsed: false, version: 1,
});
const outline = (documentId: string, items: IdeaItemV1[]): IdeaOutlineV1 =>
  ({ ...emptyIdeasV1(documentId), items });
const put = (ideas: IdeaOutlineV1, expectedIdeasRevision = 0, clientMutationId = randomUUID()) =>
  ({ ideas, expectedIdeasRevision, clientMutationId });

async function counts(db: Awaited<ReturnType<typeof harness>>["db"], projectId: string) {
  const rows = await db.query<{ ideas: number; receipts: number; documents: number }>(
    "SELECT (SELECT count(*)::int FROM stt_idea_revisions WHERE project_id=$1) AS ideas," +
      " (SELECT count(*)::int FROM stt_ideas_mutation_receipts WHERE project_id=$1) AS receipts," +
      " (SELECT count(*)::int FROM stt_document_revisions WHERE project_id=$1) AS documents",
    [projectId],
  );
  return rows.rows[0];
}

describe("authorized, independent Ideas head", () => {
  it("lazily reads revision zero, saves ordered nested content, and survives a new service instance", async () => {
    const { db, pool, auth, service, owner, initial, projectId, documentId } = await setup();
    const empty = emptyIdeasV1(documentId);
    expect(await service.getIdeas(projectId, owner)).toEqual({
      projectId, ideasRevision: 0, ideas: empty, digest: sha256(JSON.stringify(empty)),
    });
    expect((await db.query("SELECT * FROM stt_idea_heads")).rows).toHaveLength(0);
    const root = { ...item("a", null, "  root\n"), collapsed: true };
    const child = item("a", root.id, "\n  child text \n");
    const sibling = item("b", root.id);
    const secondRoot = item("z");
    const ideas = outline(documentId, [root, child, sibling, secondRoot]);
    const mutation = put(ideas);
    const stored = await service.putIdeas(projectId, owner, mutation);
    expect(stored).toEqual({ projectId, clientMutationId: mutation.clientMutationId,
      ideasRevision: 1, ideasDigest: sha256(JSON.stringify(ideas)), duplicateDelivery: false });
    const reopened = new ProjectDocumentService(pool, auth);
    expect(await reopened.getIdeas(projectId, owner)).toEqual({
      projectId, ideasRevision: 1, digest: stored.ideasDigest, ideas,
    });
    expect((await reopened.getDocument(projectId, owner)).document).toEqual(initial.document);
    expect((await reopened.getDocument(projectId, owner)).revision).toBe(0);
    expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 1 });
  });

  it("supports Editor writes with a live write session, Viewer reads, and denial after revocation", async () => {
    const { auth, service, owner, editor, viewer, projectId, documentId } = await setup();
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
    const first = put(outline(documentId, [item()]));
    await expect(service.putIdeas(projectId, viewer, first)).rejects.toMatchObject({ status: 403 });
    expect((await service.getIdeas(projectId, viewer)).ideasRevision).toBe(0);
    const session = await auth.openWriteSession(projectId, editor);
    expect((await service.putIdeas(projectId, editor, { ...first, writeSessionId: session })).ideasRevision).toBe(1);
    await auth.changeMembership(projectId, owner, editor.principalId, null);
    await expect(service.putIdeas(projectId, editor, { ...first, writeSessionId: session }))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.getIdeas(projectId, editor)).rejects.toMatchObject({ status: 403 });
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await expect(service.putIdeas(projectId, editor, { ...first, writeSessionId: session }))
      .rejects.toMatchObject({ status: 403 });
    expect((await service.getIdeas(projectId, viewer)).ideasRevision).toBe(1);
  });

  it("replays exactly one immutable receipt even after the head advances; key reuse is a conflict", async () => {
    const { db, service, owner, projectId, documentId } = await setup();
    const a = item();
    const first = put(outline(documentId, [a]));
    const original = await service.putIdeas(projectId, owner, first);
    const second = put(outline(documentId, [{ ...a, text: "Edited", version: 2 }]), 1);
    await service.putIdeas(projectId, owner, second);
    expect(await service.putIdeas(projectId, owner, first)).toEqual({ ...original, duplicateDelivery: true });
    await expect(service.putIdeas(projectId, owner, {
      ...first, ideas: outline(documentId, [{ ...a, text: "Imposter" }]),
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.putIdeas(projectId, owner, { ...first, expectedIdeasRevision: 1 }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect(await counts(db, projectId)).toEqual({ ideas: 2, receipts: 2, documents: 1 });
  });

  it("rejects stale heads, duplicate siblings/IDs, malformed input, wrong document and foreign project", async () => {
    const { db, service, owner, viewer, projectId, documentId } = await setup();
    const a = item();
    const first = await service.putIdeas(projectId, owner, put(outline(documentId, [a])));
    await expect(service.putIdeas(projectId, owner, put(outline(documentId, [a]))))
      .rejects.toMatchObject({ status: 409, metadata: {
        currentIdeasRevision: 1, currentDigest: first.ideasDigest,
      } });
    const invalid: IdeaItemV1[][] = [
      [a, { ...item(), id: a.id, orderKey: "b" }],
      [a, item("a")],
      [item("z"), item("a")],
      [item("a", randomUUID())],
    ];
    for (const entries of invalid) {
      await expect(service.putIdeas(projectId, owner, put(outline(documentId, entries), 1)))
        .rejects.toMatchObject({ status: 400 });
    }
    await expect(service.putIdeas(projectId, owner,
      { ...put(outline(documentId, []), 1), role: "producer" } as never))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.putIdeas(projectId, owner, null as never))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.putIdeas(projectId, owner, put(outline(randomUUID(), []), 1)))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.getIdeas(randomUUID(), owner)).rejects.toMatchObject({ status: 403 });
    const other = initialProject();
    await service.createProject(viewer, other);
    await expect(service.getIdeas(other.projectId, owner)).rejects.toMatchObject({ status: 403 });
    await expect(service.putIdeas(other.projectId, owner, put(outline(other.document.id, []))))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.getIdeas(projectId, viewer)).rejects.toMatchObject({ status: 403 });
    await expect(service.putIdeas(projectId, viewer, put(outline(documentId, []), 1)))
      .rejects.toMatchObject({ status: 403 });
    expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 1 });
  });

  it("requires exact version advancement for changed items and forbids forged Draft backlinks", async () => {
    const { service, owner, projectId, documentId } = await setup();
    const a = item("a"), b = item("b");
    await service.putIdeas(projectId, owner, put(outline(documentId, [a, b])));
    const wrong = [
      [{ ...a, text: "changed" }, b],
      [{ ...a, version: 2 }, b],
      [a, { ...b, linkedDraftBlockIds: [randomUUID()], version: 2 }],
      [a, b, { ...item("c"), version: 2 }],
      [a, b, { ...item("c"), state: "incorporated" as const }],
    ];
    for (const items of wrong) {
      await expect(service.putIdeas(projectId, owner, put(outline(documentId, items), 1)))
        .rejects.toMatchObject({ status: 400 });
    }
    const edited = { ...a, text: "changed", version: 2 };
    await service.putIdeas(projectId, owner, put(outline(documentId, [edited, b]), 1));
    const next = item("c");
    await service.putIdeas(projectId, owner, put(outline(documentId, [edited, b, next]), 2));
    const reordered = { ...next, orderKey: "0", version: 2 };
    const result = await service.putIdeas(projectId, owner, put(outline(documentId, [reordered, edited, b]), 3));
    expect(result.ideasRevision).toBe(4);
    expect((await service.getIdeas(projectId, owner)).ideas.items).toEqual([reordered, edited, b]);
  });

  it("reserves mutation keys across Ideas and document writes in either direction", async () => {
    const { db, service, owner, initial, projectId, documentId } = await setup();
    const ideasMutation = put(outline(documentId, [item()]));
    await service.putIdeas(projectId, owner, ideasMutation);
    await expect(service.putDocument(projectId, owner, { expectedRevision: 0,
      clientMutationId: ideasMutation.clientMutationId, document: initial.document }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const docMutationId = randomUUID();
    await service.putDocument(projectId, owner, { expectedRevision: 0,
      clientMutationId: docMutationId, document: { ...initial.document, title: "New title" } });
    await expect(service.putIdeas(projectId, owner,
      put(outline(documentId, [item("b")]), 1, docMutationId)))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 2 });
  });

  it("rolls back revision/head/receipt when the head write or receipt insert fails", async () => {
    const { db, pool, service, owner, projectId, documentId } = await setup();
    const first = put(outline(documentId, [item()]));
    await service.putIdeas(projectId, owner, first);
    const before = await service.getIdeas(projectId, owner);
    const next = put(outline(documentId, [
      { ...first.ideas.items[0]!, text: "changed", version: 2 },
    ]), 1);
    for (const prefix of ["UPDATE stt_idea_heads", "INSERT INTO stt_ideas_mutation_receipts"]) {
      const brokenPool: SqlPool = { connect: async () => {
        const dbClient = await pool.connect();
        return { query: async <R>(sql: string, params?: readonly unknown[]) => {
          if (sql.startsWith(prefix)) throw new Error("Injected database failure");
          return await dbClient.query<R>(sql, params);
        }, release: () => dbClient.release?.() } satisfies SqlClient;
      } };
      const broken = new ProjectDocumentService(brokenPool, new ProjectAuthorizationService(brokenPool));
      await expect(broken.putIdeas(projectId, owner, next)).rejects.toMatchObject({ status: 503 });
      expect(await service.getIdeas(projectId, owner)).toEqual(before);
      expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 1 });
    }
    expect((await service.putIdeas(projectId, owner, next)).ideasRevision).toBe(2);
  });

  it("fails closed on head digest corruption rather than reading or rewriting damaged bytes", async () => {
    const { db, service, owner, projectId, documentId } = await setup();
    const mutation = put(outline(documentId, [item()]));
    await service.putIdeas(projectId, owner, mutation);
    await db.query("UPDATE stt_idea_heads SET content_digest=$2 WHERE project_id=$1",
      [projectId, sha256("tampered")]);
    await expect(service.getIdeas(projectId, owner)).rejects.toMatchObject({ status: 503 });
    await expect(service.putIdeas(projectId, owner, put(outline(documentId, []), 1)))
      .rejects.toMatchObject({ status: 503 });
    expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 1 });
  });

  it("retries the whole serializable Ideas transaction without duplicate revisions", async () => {
    const { db, pool, service, owner, projectId, documentId } = await setup();
    let aborts = 1;
    const retryPool: SqlPool = { connect: async () => {
      const client = await pool.connect();
      return { query: async <R>(sql: string, params?: readonly unknown[]) => {
        if (sql === "COMMIT" && aborts-- > 0) {
          throw Object.assign(new Error("synthetic serialization abort"), { code: "40001" });
        }
        return await client.query<R>(sql, params);
      }, release: () => client.release?.() } satisfies SqlClient;
    } };
    const retrying = new ProjectDocumentService(retryPool, new ProjectAuthorizationService(retryPool));
    const first = put(outline(documentId, [item()]));
    expect((await retrying.putIdeas(projectId, owner, first)).ideasRevision).toBe(1);
    expect(aborts).toBe(-1);
    expect(await counts(db, projectId)).toEqual({ ideas: 1, receipts: 1, documents: 1 });
    expect((await service.getIdeas(projectId, owner)).ideas).toEqual(first.ideas);
  });
});
