import { randomUUID } from "node:crypto";

import type { NarrationBlockV2 } from "@vera/contracts/v2";
import { ProjectAuthorizationService, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDocumentService } from "../src/service.js";
import { documentFor, harness, initialProject } from "./helpers.js";

vi.setConfig({ testTimeout: 45_000 });
const cleanups: Array<() => Promise<void>> = [];
async function setup() {
  const h = await harness();
  cleanups.push(async () => { await h.db.close(); });
  return h;
}
afterEach(async () => {
  for (const cleanup of cleanups.splice(0)) await cleanup();
});

function narration(): NarrationBlockV2 {
  return {
    type: "narration", id: randomUUID(), orderKey: "a0", text: "Hello",
    tokens: [{ id: randomUUID(), value: "Hello", startOffset: 0, endOffset: 5 }],
    primaryVisualSequence: { id: randomUUID(), version: 1, slots: [{
      id: randomUUID(), kind: "content", relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

describe("project-scoped attributed revision history", () => {
  it("lists genesis through multiple attributed writers with stable descending cursor pages and restart", async () => {
    const { service, auth, pool, owner, editor, viewer } = await setup();
    const initial = initialProject();
    const genesis = await service.createProject(owner, initial);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    const firstId = randomUUID();
    const secondId = randomUUID();
    const first = await service.putDocument(initial.projectId, editor, {
      expectedRevision: 0, clientMutationId: firstId,
      document: { ...initial.document, title: "Editor update" },
    });
    const second = await service.putDocument(initial.projectId, owner, {
      expectedRevision: 1, clientMutationId: secondId,
      document: { ...initial.document, title: "Producer update" },
    });
    const reopened = new ProjectDocumentService(pool, new ProjectAuthorizationService(pool));
    const all = await reopened.listDocumentRevisions(initial.projectId, viewer);
    expect(all.nextBeforeRevision).toBeNull();
    expect(all.revisions.map((row) => row.revision)).toEqual([2, 1, 0]);
    expect(all.revisions.map((row) => row.expectedRevision)).toEqual([1, 0, null]);
    expect(all.revisions.map((row) => row.actorId)).toEqual([
      owner.principalId, editor.principalId, owner.principalId,
    ]);
    expect(all.revisions.map((row) => row.clientMutationId)).toEqual([
      secondId, firstId, initial.clientRequestId,
    ]);
    expect(all.revisions.map((row) => row.digest)).toEqual([
      second.digest, first.digest, genesis.documentDigest,
    ]);
    for (const entry of all.revisions) {
      expect(entry.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}T.*Z$/u);
      expect(entry.restoreOrigin).toBeNull();
    }
    const pages = [];
    let beforeRevision: number | undefined;
    for (let i = 0; i < 3; i++) {
      const page = await service.listDocumentRevisions(initial.projectId, viewer,
        { limit: 1, ...(beforeRevision === undefined ? {} : { beforeRevision }) });
      pages.push(page);
      beforeRevision = page.nextBeforeRevision ?? undefined;
    }
    expect(pages.map((page) => page.revisions[0]?.revision)).toEqual([2, 1, 0]);
    expect(pages.map((page) => page.nextBeforeRevision)).toEqual([2, 1, null]);
    expect((await service.listDocumentRevisions(initial.projectId, viewer,
      { beforeRevision: 0 })).revisions).toEqual([]);
    const historic = await reopened.getDocumentRevision(initial.projectId, viewer, 1);
    expect(historic.document.title).toBe("Editor update");
    expect(historic.attribution).toEqual(all.revisions[1]);
    expect((await reopened.getDocumentRevision(initial.projectId, viewer, 0)).document)
      .toEqual(initial.document);
    expect((await reopened.getDocument(initial.projectId, viewer)).revision).toBe(2);
  });

  it("compares two authorized, checked saved snapshots, not caller-supplied JSON", async () => {
    const { service, owner } = await setup();
    const projectId = randomUUID();
    const initial = { projectId, clientRequestId: randomUUID(), title: "Demo",
      document: { ...documentFor(projectId), activeDraft: { blocks: [narration()], supportingItems: [] } } };
    await service.createProject(owner, initial);
    const original = initial.document.activeDraft.blocks[0]!;
    if (original.type !== "narration") throw new Error("Expected narration fixture");
    const updated = { ...original, text: "Hi", tokens: [
      { ...original.tokens[0]!, value: "Hi", endOffset: 2 },
    ], version: 2 };
    await service.putDocument(projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Changed", activeDraft: {
        blocks: [updated], supportingItems: [],
      } },
    });
    const diff = await service.compareDocumentRevisions(projectId, owner, 0, 1);
    expect(diff.from.revision).toBe(0);
    expect(diff.to.revision).toBe(1);
    expect(diff.totalChanges).toBe(2);
    expect(diff.truncated).toBe(false);
    expect(diff.changes).toEqual([
      { surface: "document", entityId: initial.document.id, kind: "modified", fields: ["title"] },
      { surface: "draft_block", entityId: original.id, kind: "modified", fields: ["text", "tokens", "version"] },
    ]);
    expect((await service.compareDocumentRevisions(projectId, owner, 1, 1)).changes).toEqual([]);
    expect((await service.compareDocumentRevisions(projectId, owner, 1, 0)).changes)
      .toEqual(diff.changes);
    await expect(service.compareDocumentRevisions(projectId, owner, 0, 100))
      .rejects.toMatchObject({ status: 404 });
  });

  it("reports exact total and stable first 200 changes when the semantic response is bounded", async () => {
    const { service, owner } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    const items = Array.from({ length: 205 }, (_, index) => ({
      id: randomUUID(), version: 1, orderKey: String(index), role: "citation" as const,
      content: `Source ${index}`, placement: { kind: "unplaced" as const, reason: "Not anchored" },
    }));
    await service.putDocument(initial.projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, activeDraft: { blocks: [], supportingItems: items } },
    });
    const result = await service.compareDocumentRevisions(initial.projectId, owner, 0, 1);
    expect(result.totalChanges).toBe(205);
    expect(result.truncated).toBe(true);
    expect(result.changes).toHaveLength(200);
    expect(result.changes.map((change) => change.entityId))
      .toEqual(items.map((item) => item.id).sort().slice(0, 200));
  });

  it("fails closed on foreign or revoked membership and validates all revision selectors", async () => {
    const { auth, service, owner, editor, viewer, db } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    expect((await service.listDocumentRevisions(initial.projectId, viewer)).revisions).toHaveLength(1);
    const foreign = initialProject();
    await service.createProject(editor, foreign);
    await expect(service.listDocumentRevisions(foreign.projectId, owner)).rejects.toMatchObject({ status: 403 });
    await expect(service.getDocumentRevision(foreign.projectId, owner, 0))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.compareDocumentRevisions(foreign.projectId, owner, 0, 0))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.listDocumentRevisions(randomUUID(), owner)).rejects.toMatchObject({ status: 403 });
    await expect(service.getDocumentRevision(initial.projectId, owner, 50))
      .rejects.toMatchObject({ status: 404 });
    for (const limit of [0, -1, 1.5, 101, NaN, "20"] as unknown[]) {
      await expect(service.listDocumentRevisions(initial.projectId, owner, { limit: limit as number }))
        .rejects.toMatchObject({ status: 400 });
    }
    await expect(service.listDocumentRevisions(initial.projectId, owner, { beforeRevision: -1 }))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.getDocumentRevision(initial.projectId, owner, Number.MAX_SAFE_INTEGER + 1))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.compareDocumentRevisions(initial.projectId, owner, -1, 0))
      .rejects.toMatchObject({ status: 400 });
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, null);
    await expect(service.listDocumentRevisions(initial.projectId, viewer)).rejects.toMatchObject({ status: 403 });
    await expect(service.getDocumentRevision(initial.projectId, viewer, 0))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.compareDocumentRevisions(initial.projectId, viewer, 0, 0))
      .rejects.toMatchObject({ status: 403 });
    await db.query("UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1", [editor.principalId]);
    await expect(service.listDocumentRevisions(initial.projectId, editor)).rejects.toMatchObject({ status: 403 });
  });

  it("detects digest, typed-body and identity corruption without returning historical bytes", async () => {
    const { service, auth, pool, owner } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    const forged = (change: Record<string, unknown>): ProjectDocumentService => {
      const forgedPool: SqlPool = { connect: async () => {
        const real = await pool.connect();
        return {
          query: async <T>(sql: string, args?: readonly unknown[]) => {
            const result = await real.query<T>(sql, args);
            if (!sql.includes("FROM stt_document_revisions r")) return result;
            return { rows: result.rows.map((row) => ({ ...(row as object), ...change }) as T) };
          },
          release: () => { real.release?.(); },
        } satisfies SqlClient;
      } };
      return new ProjectDocumentService(forgedPool, new ProjectAuthorizationService(forgedPool));
    };
    for (const change of [
      { content_digest: `sha256:${"0".repeat(64)}` },
      { document_json: "{}" },
      { document_json: JSON.stringify({ ...initial.document, id: randomUUID() }) },
      { expected_revision: "100" },
    ]) {
      const corrupt = forged(change);
      await expect(corrupt.getDocumentRevision(initial.projectId, owner, 0))
        .rejects.toMatchObject({ status: 503 });
      await expect(corrupt.listDocumentRevisions(initial.projectId, owner))
        .rejects.toMatchObject({ status: 503 });
      await expect(corrupt.compareDocumentRevisions(initial.projectId, owner, 0, 0))
        .rejects.toMatchObject({ status: 503 });
    }
    expect((await service.listDocumentRevisions(initial.projectId, owner)).revisions).toHaveLength(1);
    expect((await new ProjectDocumentService(pool, auth)
      .getDocumentRevision(initial.projectId, owner, 0)).document).toEqual(initial.document);
  });
});
