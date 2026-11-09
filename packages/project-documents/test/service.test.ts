import { randomUUID } from "node:crypto";

import {
  ProjectAuthorizationService,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDocumentService } from "../src/service.js";
import { ProjectCommentService } from "../src/comments.js";
import { checkedDocument } from "../src/model.js";
import { documentFor, extrasDocumentFor, harness, initialProject, settingsFor } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Test pool implements the asynchronous SQL port. */
vi.setConfig({ testTimeout: 45_000 });
const close: Array<() => Promise<void>> = [];
async function setup() {
  const h = await harness();
  close.push(async () => { await h.db.close(); });
  return h;
}
afterEach(async () => {
  for (const cleanup of close.splice(0)) await cleanup();
});

describe("durable Extras operations", () => {
  it("parks, restores and duplicates typed saved content with immutable digests and CAS", async () => {
    const { service, auth, db, pool, owner, editor, viewer } = await setup();
    const projectId = randomUUID();
    const { document, rowId, sectionId, citationId } = extrasDocumentFor(projectId);
    const created = await service.createProject(owner, { projectId, title: "Extras", clientRequestId: randomUUID(), document });
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
    const writeSessionId = await auth.openWriteSession(projectId, editor);
    const park = { expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId,
      operation: { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() } };
    const before = await service.getDocument(projectId, viewer);
    expect(before.digest).toBe(created.documentDigest);
    await expect(service.applyExtrasOperation(projectId, viewer, park)).rejects.toMatchObject({ status: 403 });
    await expect(service.applyExtrasOperation(randomUUID(), editor, park)).rejects.toMatchObject({ status: 403 });
    expect(await service.getDocument(projectId, viewer)).toEqual(before);

    const first = await service.applyExtrasOperation(projectId, editor, park);
    expect(first).toMatchObject({ revision: 1, duplicateDelivery: false });
    const saved = await service.getDocument(projectId, viewer);
    expect(saved.digest).toBe(checkedDocument(saved.document, projectId).digest);
    expect(saved.document.activeDraft.blocks).toHaveLength(1);
    expect(saved.document.activeDraft.supportingItems).toEqual([]);
    expect(saved.document.stash?.[0]?.rows[0]).toEqual(document.activeDraft.blocks[1]);
    expect(saved.document.stash?.[0]?.supportingItems[0]?.id).toBe(citationId);
    expect(saved.document.rowEditRevision).toBe(1);
    expect(saved.document.extras).toEqual([]);
    expect(await service.applyExtrasOperation(projectId, editor, park))
      .toEqual({ ...first, duplicateDelivery: true });
    await expect(service.applyExtrasOperation(projectId, editor, { ...park,
      operation: { ...park.operation, bundleId: randomUUID() } }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.putDocument(projectId, editor, { expectedRevision: 0,
      clientMutationId: park.clientMutationId, document, writeSessionId }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.applyExtrasOperation(projectId, editor, { ...park, clientMutationId: randomUUID() }))
      .rejects.toMatchObject({ status: 409, code: "version_conflict" });
    await expect(service.applyExtrasOperation(projectId, editor, { expectedRevision: 1,
      clientMutationId: randomUUID(), writeSessionId,
      operation: { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() } }))
      .rejects.toMatchObject({ status: 400, metadata: { operationCode: "ROW_SELECTION_INVALID" } });
    expect(await service.getDocument(projectId, viewer)).toEqual(saved);

    const destination = { sectionId, afterRowId: null, beforeRowId: null };
    const duplicate = await service.applyExtrasOperation(projectId, editor, { expectedRevision: 1,
      clientMutationId: randomUUID(), writeSessionId,
      operation: { kind: "duplicate_stash_rows", rowIds: [rowId], destination } });
    const cloned = await service.getDocument(projectId, viewer);
    expect(cloned.document.activeDraft.blocks).toHaveLength(2);
    expect(cloned.document.activeDraft.blocks[1]?.id).not.toBe(rowId);
    expect(cloned.document.stash?.[0]?.rows[0]?.id).toBe(rowId);
    expect(cloned.document.stash?.[0]?.supportingItems[0]?.id).toBe(citationId);
    expect(cloned.digest).toBe(duplicate.digest);
    const restored = await service.applyExtrasOperation(projectId, editor, { expectedRevision: 2,
      clientMutationId: randomUUID(), writeSessionId,
      operation: { kind: "restore_stash", bundleId: park.operation.bundleId,
        destination: { sectionId, afterRowId: cloned.document.activeDraft.blocks[1]!.id, beforeRowId: null } } });
    const final = await new ProjectDocumentService(pool, auth).getDocument(projectId, viewer);
    expect(final.revision).toBe(3);
    expect(final.document.activeDraft.blocks[2]?.id).toBe(rowId);
    expect(final.document.stash).toEqual([]);
    expect(restored.digest).toBe(final.digest);
    expect((await service.getDocumentRevision(projectId, viewer, 1)).document).toEqual(saved.document);
    expect((await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [projectId],
    )).rows[0]?.n).toBe(4);
  });

  it("refuses invalid, stale, cross-operation and revoked replays without changing head or comments", async () => {
    const { auth, service, owner, editor, viewer, db } = await setup();
    const projectId = randomUUID();
    const { document, rowId } = extrasDocumentFor(projectId);
    await service.createProject(owner, { projectId, title: "Extras", clientRequestId: randomUUID(), document });
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
    const session = await auth.openWriteSession(projectId, editor);
    const original = await service.getDocument(projectId, owner);
    const invalid: unknown[] = [
      { kind: "delete_rows", rowIds: [rowId] },
      { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID(), actorId: owner.principalId },
      { kind: "stash_rows", rowIds: [rowId, rowId], bundleId: randomUUID() },
      { kind: "duplicate_stash_rows", rowIds: [rowId], destination: {
        sectionId: randomUUID(), afterRowId: null, beforeRowId: null } },
    ];
    for (const operation of invalid) {
      await expect(service.applyExtrasOperation(projectId, editor, {
        expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId: session, operation,
      })).rejects.toMatchObject({ status: 400 });
    }
    const hostile = new Proxy({ kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() }, {
      get(target, key, receiver) {
        if (key === "kind") throw new Error("hostile command getter");
        return Reflect.get(target, key, receiver) as unknown;
      },
    });
    await expect(service.applyExtrasOperation(projectId, editor, {
      expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId: session,
      operation: hostile,
    })).rejects.toMatchObject({ status: 400, metadata: { operationCode: "EXTRAS_COMMAND_INVALID" } });
    const park = { expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId: session,
      operation: { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() } };
    await service.applyExtrasOperation(projectId, editor, park);
    const committed = await service.getDocument(projectId, owner);
    await auth.changeMembership(projectId, owner, editor.principalId, null);
    await expect(service.applyExtrasOperation(projectId, editor, park)).rejects.toMatchObject({ status: 403 });
    await expect(service.applyExtrasOperation(projectId, editor, { ...park,
      clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 403 });
    expect(await service.getDocument(projectId, viewer)).toEqual(committed);
    expect((await service.getDocumentRevision(projectId, owner, 0)).document).toEqual(original.document);
    expect((await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [projectId],
    )).rows[0]?.n).toBe(2);
  });

  it("rebases anchored comments in the same transaction and rolls back on comment storage failure", async () => {
    const { db, pool, auth, service, owner, editor } = await setup();
    const projectId = randomUUID();
    const { document, rowId } = extrasDocumentFor(projectId);
    await service.createProject(owner, { projectId, title: "Extras", clientRequestId: randomUUID(), document });
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    const comments = new ProjectCommentService(pool, auth);
    await comments.applyOperation(projectId, editor, { expectedCommentRevision: 0,
      clientMutationId: randomUUID(), operation: { kind: "create", threadId: randomUUID(),
        messageId: randomUUID(), body: "Preserved comment", mentionActorIds: [],
        anchor: { kind: "block", blockId: rowId } } });
    const initialComments = await comments.getComments(projectId, owner);
    const original = await service.getDocument(projectId, owner);
    const writeSessionId = await auth.openWriteSession(projectId, editor);
    const operation = { expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId,
      operation: { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() } };
    const brokenPool: SqlPool = { connect: async () => {
      const raw = await pool.connect();
      return { query: async <R>(sql: string, args?: readonly unknown[]) => {
        if (sql.startsWith("UPDATE stt_comment_heads")) throw new Error("synthetic comment failure");
        return await raw.query<R>(sql, args);
      }, release: () => { raw.release?.(); } } satisfies SqlClient;
    } };
    const broken = new ProjectDocumentService(brokenPool, new ProjectAuthorizationService(brokenPool));
    await expect(broken.applyExtrasOperation(projectId, editor, operation))
      .rejects.toMatchObject({ status: 503 });
    expect(await service.getDocument(projectId, owner)).toEqual(original);
    expect(await comments.getComments(projectId, owner)).toEqual(initialComments);
    const receipt = await service.applyExtrasOperation(projectId, editor, operation);
    expect(receipt.revision).toBe(1);
    const after = await comments.getComments(projectId, owner);
    expect(after.documentRevision).toBe(1);
    expect(after.commentRevision).toBe(2);
    expect(after.threads).toHaveLength(1);
    expect(after.threads[0]?.messages[0]?.body).toBe("Preserved comment");
    expect((await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [projectId],
    )).rows[0]?.n).toBe(2);
  });
});

describe("durable project creation", () => {
  it("atomically bootstraps only the first Producer and reopens the exact head", async () => {
    const { db, pool, auth, service, owner, viewer } = await setup();
    const initial = initialProject();
    const created = await service.createProject(owner, initial);
    expect(created.project.projectId).toBe(initial.projectId);
    expect(created.project.linkedResearchProjectIds).toEqual([]);
    expect(created.documentRevision).toBe(0);
    expect(created.duplicateDelivery).toBe(false);
    const reopened = new ProjectDocumentService(pool, auth);
    expect(await reopened.getDocument(initial.projectId, owner)).toEqual({
      projectId: initial.projectId, document: initial.document,
      revision: 0, digest: created.documentDigest,
    });
    expect((await service.createProject(owner, initial)).duplicateDelivery).toBe(true);
    const members = await db.query<{ role: string }>(
      "SELECT role FROM vera_project_members WHERE project_id=$1",
      [initial.projectId],
    );
    expect(members.rows.map((row) => row.role)).toEqual(["producer"]);
    const history = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [initial.projectId]);
    expect(history.rows[0]?.n).toBe(1);
    await expect(service.getDocument(initial.projectId, viewer)).rejects.toMatchObject({ status: 403 });
    await expect(service.getDocument(randomUUID(), owner)).rejects.toMatchObject({ status: 403 });
    await expect(service.createProject(owner, { ...initial, title: "Changed" }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.createProject(viewer, { ...initial, clientRequestId: randomUUID() }))
      .rejects.toMatchObject({ status: 409, code: "already_exists" });
  });

  it("rechecks membership before returning the original project on replay", async () => {
    const { auth, service, owner, editor } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "producer");
    await auth.changeMembership(initial.projectId, editor, owner.principalId, null);
    await expect(service.createProject(owner, initial)).rejects.toMatchObject({ status: 403 });
    await expect(service.getDocument(initial.projectId, owner)).rejects.toMatchObject({ status: 403 });
  });

  it("refuses to bootstrap a Producer disabled after an earlier trusted authentication", async () => {
    const { db, service, owner } = await setup();
    const initial = initialProject();
    await db.query("UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1", [owner.principalId]);
    await expect(service.createProject(owner, initial))
      .rejects.toMatchObject({ status: 403, code: "action_not_allowed" });
    const projects = await db.query<{ n: number }>("SELECT count(*)::integer AS n FROM stt_projects");
    expect(projects.rows[0]?.n).toBe(0);
  });
});

describe("single-writer typed document head", () => {
  it("retries the entire SERIALIZABLE mutation and fails closed after three aborts", async () => {
    const { db, pool, service, owner } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    let aborts = 1;
    const retryPool: SqlPool = {
      connect: async () => {
        const client = await pool.connect();
        return {
          query: async <R>(sql: string, params?: readonly unknown[]) => {
            if (sql === "COMMIT" && aborts-- > 0) {
              throw Object.assign(new Error("serialization abort"), { code: "40001" });
            }
            return await client.query<R>(sql, params);
          },
          release: () => { client.release?.(); },
        } satisfies SqlClient;
      },
    };
    const retrying = new ProjectDocumentService(retryPool, new ProjectAuthorizationService(retryPool));
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Retried after abort" } };
    expect((await retrying.putDocument(initial.projectId, owner, mutation)).revision).toBe(1);
    expect(aborts).toBe(-1);
    const committed = await service.getDocument(initial.projectId, owner);
    const count = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1",
      [initial.projectId],
    );
    expect(count.rows[0]?.n).toBe(2);

    aborts = 3;
    await expect(retrying.putDocument(initial.projectId, owner, {
      expectedRevision: 1, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Never committed" },
    })).rejects.toMatchObject({ status: 503, code: "service_unavailable" });
    expect(await service.getDocument(initial.projectId, owner)).toEqual(committed);
  });

  it("appends exactly one authorized revision and returns immutable replay receipts", async () => {
    const { db, service, owner } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Revised", liveHeadSequence: 4 } };
    const saved = await service.putDocument(initial.projectId, owner, mutation);
    expect(saved.revision).toBe(1);
    expect(saved.duplicateDelivery).toBe(false);
    expect(await service.putDocument(initial.projectId, owner, mutation)).toEqual({
      ...saved, duplicateDelivery: true,
    });
    expect((await service.getDocument(initial.projectId, owner)).document.liveContentHash)
      .toBe(initial.document.liveContentHash);
    await expect(service.putDocument(initial.projectId, owner,
      { ...mutation, document: { ...mutation.document, title: "Changed replay" } }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.putDocument(initial.projectId, owner,
      { ...mutation, clientMutationId: randomUUID() }))
      .rejects.toMatchObject({ status: 409, metadata: {
        currentRevision: 1, currentDigest: saved.digest,
      } });
    await expect(service.putDocument(initial.projectId, owner, {
      ...mutation, clientMutationId: randomUUID(), expectedRevision: 1,
      document: documentFor(initial.projectId),
    })).rejects.toMatchObject({ status: 400 });
    const count = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1",
      [initial.projectId]);
    expect(count.rows[0]?.n).toBe(2);
    await expect(db.query("DELETE FROM stt_document_revisions WHERE project_id=$1", [initial.projectId]))
      .rejects.toThrow();
    expect((await service.getDocument(initial.projectId, owner)).revision).toBe(1);
  });

  it("enforces Viewer/Editor permissions and revocation before idempotency", async () => {
    const { db, service, auth, owner, editor, viewer } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    expect((await service.getDocument(initial.projectId, viewer)).revision).toBe(0);
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Editor change" } };
    await expect(service.putDocument(initial.projectId, viewer, mutation))
      .rejects.toMatchObject({ status: 403 });
    const session = await auth.openWriteSession(initial.projectId, editor);
    const accepted = await service.putDocument(initial.projectId, editor,
      { ...mutation, writeSessionId: session });
    expect(accepted.revision).toBe(1);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, null);
    await expect(service.putDocument(initial.projectId, editor,
      { ...mutation, writeSessionId: session })).rejects.toMatchObject({ status: 403 });
    await expect(service.putDocument(initial.projectId, editor,
      { ...mutation, clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 403 });
    const count = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1",
      [initial.projectId]);
    expect(count.rows[0]?.n).toBe(2);
  });

  it("rolls back an inserted revision if the head write fails", async () => {
    const { db, service, auth, owner, pool } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    const original = await service.getDocument(initial.projectId, owner);
    const raw = await pool.connect();
    const brokenPool: SqlPool = { connect: async () => ({
      query: async <T>(sql: string, params?: readonly unknown[]) => {
        if (sql.startsWith("UPDATE stt_document_heads")) throw new Error("database refused head update");
        return await raw.query<T>(sql, params);
      },
    } satisfies SqlClient) };
    const broken = new ProjectDocumentService(brokenPool, new ProjectAuthorizationService(brokenPool));
    await expect(broken.putDocument(initial.projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Should roll back" },
    })).rejects.toMatchObject({ status: 503 });
    expect(await service.getDocument(initial.projectId, owner)).toEqual(original);
    const count = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1",
      [initial.projectId]);
    expect(count.rows[0]?.n).toBe(1);
    await expect(new ProjectDocumentService({ connect: async () => { throw new Error("offline"); } }, auth)
      .createProject(owner, initialProject())).rejects.toMatchObject({ status: 503 });
  });
});

describe("Producer-only project setup", () => {
  it("persists optional settings with immutable ID, CAS and audit, and title updates", async () => {
    const { db, service, auth, owner, editor } = await setup();
    const initial = initialProject();
    await service.createProject(owner, initial);
    await expect(service.getSettings(initial.projectId, owner)).rejects.toMatchObject({ status: 404 });
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    const settings = settingsFor(initial.projectId);
    const put = { expectedSettingsRevision: 0, clientMutationId: randomUUID(), settings };
    await expect(service.putSettings(initial.projectId, editor, put)).rejects.toMatchObject({ status: 403 });
    const first = await service.putSettings(initial.projectId, owner, put);
    expect(first.revision).toBe(1);
    expect((await service.putSettings(initial.projectId, owner, put)).duplicateDelivery).toBe(true);
    await expect(service.putSettings(initial.projectId, owner,
      { ...put, settings: { ...settings, version: 2 } }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect((await service.getSettings(initial.projectId, editor)).settings).toEqual(settings);
    await expect(service.putSettings(initial.projectId, owner,
      { ...put, clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 409 });
    await expect(service.putSettings(initial.projectId, owner,
      { ...put, expectedSettingsRevision: 1, clientMutationId: randomUUID(),
        settings: settingsFor(initial.projectId) })).rejects.toMatchObject({ status: 400 });
    const second = await service.putSettings(initial.projectId, owner, {
      ...put, expectedSettingsRevision: 1, clientMutationId: randomUUID(),
      settings: { ...settings, version: 2 },
    });
    expect(second.revision).toBe(2);
    const title = { expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "Renamed" };
    await expect(service.patchProject(initial.projectId, editor, title)).rejects.toMatchObject({ status: 403 });
    const renamed = await service.patchProject(initial.projectId, owner, title);
    expect(renamed.project.projectVersion).toBe(2);
    expect((await service.patchProject(initial.projectId, owner, title)).duplicateDelivery).toBe(true);
    await expect(service.patchProject(initial.projectId, owner, { ...title, title: "Changed replay" }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.patchProject(initial.projectId, owner,
      { ...title, clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 409 });
    expect((await service.getProject(initial.projectId, editor)).title).toBe("Renamed");
    const counts = await db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_settings_revisions WHERE project_id=$1",
      [initial.projectId]);
    expect(counts.rows[0]?.n).toBe(2);
    await expect(db.query("UPDATE stt_settings_revisions SET settings_json='{}' WHERE project_id=$1",
      [initial.projectId])).rejects.toThrow();
  });
});
