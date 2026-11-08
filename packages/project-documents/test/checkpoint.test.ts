import { randomUUID } from "node:crypto";

import { ProjectAuthorizationService, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDocumentService } from "../src/service.js";
import { harness, initialProject } from "./helpers.js";

vi.setConfig({ testTimeout: 60_000 });
const cleanups: Array<() => Promise<void>> = [];
async function setup() {
  const h = await harness();
  cleanups.push(async () => { await h.db.close(); });
  return h;
}
afterEach(async () => {
  for (const cleanup of cleanups.splice(0)) await cleanup();
});

const checkpointInput = (sourceRevision = 0) => ({
  checkpointId: randomUUID(), clientMutationId: randomUUID(),
  name: "Draft checkpoint", sourceRevision,
});

describe("immutable, authorized project checkpoints", () => {
  it("freezes exact historic revision bytes, retains origin across edits/restarts and lists viewer-visible approval", async () => {
    const { db, pool, auth, service, owner, editor, viewer } = await setup();
    const project = initialProject();
    const genesis = await service.createProject(owner, project);
    await auth.changeMembership(project.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(project.projectId, owner, viewer.principalId, "viewer");
    await service.putDocument(project.projectId, editor, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Second draft" },
    });
    const request = checkpointInput();
    const created = await service.createCheckpoint(project.projectId, editor, request);
    expect(created).toMatchObject({ checkpointId: request.checkpointId,
      clientMutationId: request.clientMutationId, sourceRevision: 0,
      sourceDigest: genesis.documentDigest, documentId: project.document.id,
      createdBy: editor.principalId, duplicateDelivery: false, approval: null,
      document: project.document });
    expect(created.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}T.*Z$/u);
    const raw = await db.query<{ document_json: string; source_digest: string }>(
      "SELECT document_json,source_digest FROM stt_document_checkpoints WHERE project_id=$1 AND checkpoint_id=$2",
      [project.projectId, request.checkpointId],
    );
    const original = await db.query<{ document_json: string }>(
      "SELECT document_json FROM stt_document_revisions WHERE project_id=$1 AND revision=0", [project.projectId],
    );
    expect(raw.rows[0]?.document_json).toBe(original.rows[0]?.document_json);
    expect(raw.rows[0]?.source_digest).toBe(genesis.documentDigest);
    await service.putDocument(project.projectId, owner, {
      expectedRevision: 1, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Third draft" },
    });
    const reopened = new ProjectDocumentService(pool, new ProjectAuthorizationService(pool));
    expect((await reopened.getCheckpoint(project.projectId, viewer, request.checkpointId)).document)
      .toEqual(project.document);
    expect((await reopened.getDocument(project.projectId, viewer)).revision).toBe(2);
    expect((await reopened.listCheckpoints(project.projectId, viewer)).checkpoints).toEqual([
      { checkpointId: created.checkpointId, name: created.name,
        sourceRevision: 0, sourceDigest: created.sourceDigest, documentId: created.documentId,
        createdBy: editor.principalId, createdAt: created.createdAt, approval: null },
    ]);
    const approvalId = randomUUID();
    await expect(service.approveCheckpoint(project.projectId, editor, request.checkpointId,
      { clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 403 });
    await expect(service.createCheckpoint(project.projectId, viewer, checkpointInput()))
      .rejects.toMatchObject({ status: 403 });
    const approved = await reopened.approveCheckpoint(project.projectId, owner, request.checkpointId,
      { clientMutationId: approvalId });
    expect(approved).toMatchObject({ projectId: project.projectId, checkpointId: request.checkpointId,
      clientMutationId: approvalId, approvedBy: owner.principalId, duplicateDelivery: false });
    expect(approved.approvedAt).toMatch(/^\d{4}-\d{2}-\d{2}T.*Z$/u);
    const inspected = await service.getCheckpoint(project.projectId, viewer, request.checkpointId);
    expect(inspected.approval).toEqual({ approvedBy: owner.principalId, approvedAt: approved.approvedAt });
    expect(inspected.document).toEqual(project.document);
    expect((await service.listCheckpoints(project.projectId, viewer)).checkpoints[0]?.approval)
      .toEqual(inspected.approval);
    for (const table of ["stt_document_checkpoints", "stt_checkpoint_approvals"]) {
      await expect(db.query(`UPDATE ${table} SET project_id=project_id WHERE project_id=$1`,
        [project.projectId])).rejects.toThrow();
      await expect(db.query(`DELETE FROM ${table} WHERE project_id=$1`, [project.projectId]))
        .rejects.toThrow();
    }
    expect((await reopened.getCheckpoint(project.projectId, viewer, request.checkpointId)).approval)
      .toEqual(inspected.approval);
  });

  it("provides exact replay receipts, rejects reused keys, names, IDs and invalid input", async () => {
    const { db, service, owner } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    const input = checkpointInput();
    const saved = await service.createCheckpoint(project.projectId, owner, input);
    await service.putDocument(project.projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Changed after checkpoint" },
    });
    const replay = await service.createCheckpoint(project.projectId, owner, input);
    expect(replay).toEqual({ ...saved, duplicateDelivery: true });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...input, name: "Changed" })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...input, checkpointId: randomUUID() })).rejects.toMatchObject({ status: 409 });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...checkpointInput(), name: "draft CHECKPOINT" })).rejects.toMatchObject({ status: 409 });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...checkpointInput(), checkpointId: input.checkpointId, name: "Other" }))
      .rejects.toMatchObject({ status: 409 });
    for (const name of ["", " ", " Leading", "Trailing ", "a\nb", "tab\t", "x".repeat(121),
      "a\u007fb", "a\u009fb", 5]) {
      await expect(service.createCheckpoint(project.projectId, owner,
        { ...checkpointInput(), name: name as string })).rejects.toMatchObject({ status: 400 });
    }
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...checkpointInput(77), name: "Missing revision" })).rejects.toMatchObject({ status: 404 });
    const counts = await db.query<{ count: string }>(
      "SELECT count(*)::text AS count FROM stt_document_checkpoints WHERE project_id=$1", [project.projectId],
    );
    expect(counts.rows[0]?.count).toBe("1");
    const approving = { clientMutationId: randomUUID() };
    const approved = await service.approveCheckpoint(project.projectId, owner, input.checkpointId, approving);
    expect(await service.approveCheckpoint(project.projectId, owner, input.checkpointId, approving))
      .toEqual({ ...approved, duplicateDelivery: true });
    expect(await service.createCheckpoint(project.projectId, owner, input))
      .toEqual({ ...saved, duplicateDelivery: true });
    await expect(service.approveCheckpoint(project.projectId, owner, input.checkpointId,
      { clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 409, code: "version_conflict" });
    await expect(service.approveCheckpoint(project.projectId, owner, randomUUID(), approving))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    expect((await db.query<{ count: string }>(
      "SELECT count(*)::text AS count FROM stt_checkpoint_approvals WHERE project_id=$1", [project.projectId],
    )).rows[0]?.count).toBe("1");
  });

  it("does not allow mutation keys to be reused across document writes, checkpoint and approval commands", async () => {
    const { service, owner } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    const writeId = randomUUID();
    await service.putDocument(project.projectId, owner, { expectedRevision: 0,
      clientMutationId: writeId, document: project.document });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...checkpointInput(), clientMutationId: writeId }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const savedInput = checkpointInput();
    await service.createCheckpoint(project.projectId, owner, savedInput);
    await expect(service.putDocument(project.projectId, owner, {
      expectedRevision: 1, clientMutationId: savedInput.clientMutationId,
      document: project.document,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.approveCheckpoint(project.projectId, owner, savedInput.checkpointId,
      { clientMutationId: savedInput.clientMutationId }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const approvalId = randomUUID();
    await service.approveCheckpoint(project.projectId, owner, savedInput.checkpointId,
      { clientMutationId: approvalId });
    await expect(service.putDocument(project.projectId, owner, {
      expectedRevision: 1, clientMutationId: approvalId, document: project.document,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.createCheckpoint(project.projectId, owner,
      { ...checkpointInput(), clientMutationId: approvalId }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
  });

  it("denies foreign-project checkpoint IDs, revoked users and Producer approval replay after disability", async () => {
    const { auth, db, service, owner, editor, viewer } = await setup();
    const first = initialProject();
    const second = initialProject();
    await service.createProject(owner, first);
    await service.createProject(editor, second);
    await auth.changeMembership(first.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(first.projectId, owner, viewer.principalId, "viewer");
    const savedInput = checkpointInput();
    await service.createCheckpoint(first.projectId, owner, savedInput);
    await expect(service.getCheckpoint(second.projectId, editor, savedInput.checkpointId))
      .rejects.toMatchObject({ status: 404 });
    await expect(service.approveCheckpoint(second.projectId, editor, savedInput.checkpointId,
      { clientMutationId: randomUUID() })).rejects.toMatchObject({ status: 404 });
    await expect(service.getCheckpoint(second.projectId, viewer, savedInput.checkpointId))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.listCheckpoints(second.projectId, viewer)).rejects.toMatchObject({ status: 403 });
    await expect(service.createCheckpoint(second.projectId, owner, checkpointInput()))
      .rejects.toMatchObject({ status: 403 });
    await auth.changeMembership(first.projectId, owner, viewer.principalId, null);
    await expect(service.listCheckpoints(first.projectId, viewer)).rejects.toMatchObject({ status: 403 });
    await expect(service.getCheckpoint(first.projectId, viewer, savedInput.checkpointId))
      .rejects.toMatchObject({ status: 403 });
    await auth.changeMembership(first.projectId, owner, editor.principalId, null);
    await expect(service.createCheckpoint(first.projectId, editor, checkpointInput()))
      .rejects.toMatchObject({ status: 403 });
    const approvalInput = { clientMutationId: randomUUID() };
    await service.approveCheckpoint(first.projectId, owner, savedInput.checkpointId, approvalInput);
    await db.query("UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1", [owner.principalId]);
    await expect(service.approveCheckpoint(first.projectId, owner, savedInput.checkpointId, approvalInput))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.getCheckpoint(first.projectId, owner, savedInput.checkpointId))
      .rejects.toMatchObject({ status: 403 });
  });

  it("detects forged checkpoint digest, frozen bytes, source identity, approval and malformed reads", async () => {
    const { auth, pool, service, owner } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    const input = checkpointInput();
    await service.createCheckpoint(project.projectId, owner, input);
    const fakePool = (change: Record<string, unknown>): SqlPool => ({
      connect: async () => {
        const db = await pool.connect();
        return {
          query: async <T>(sql: string, params?: readonly unknown[]) => {
            const result = await db.query<T>(sql, params);
            if (!sql.includes("FROM stt_document_checkpoints c")) return result;
            return { rows: result.rows.map((row) => ({ ...(row as object), ...change }) as T) };
          },
          release: () => { db.release?.(); },
        } satisfies SqlClient;
      },
    });
    for (const change of [
      { source_digest: `sha256:${"0".repeat(64)}` },
      { source_digest: `sha256:${"0".repeat(64)}`,
        revision_digest: `sha256:${"0".repeat(64)}` },
      { document_json: "{}" },
      { revision_document_json: "{}" },
      { document_id: randomUUID() },
      { source_revision: "99" },
      { request_digest: `sha256:${"0".repeat(64)}` },
      { approved_by: owner.principalId, approved_at: new Date(),
        approval_mutation_id: randomUUID(), approval_request_digest: "invalid" },
    ]) {
      const tamperedPool = fakePool(change);
      const corrupt = new ProjectDocumentService(tamperedPool,
        new ProjectAuthorizationService(tamperedPool));
      await expect(corrupt.getCheckpoint(project.projectId, owner, input.checkpointId))
        .rejects.toMatchObject({ status: 503 });
      await expect(corrupt.listCheckpoints(project.projectId, owner))
        .rejects.toMatchObject({ status: 503 });
      await expect(corrupt.createCheckpoint(project.projectId, owner, input))
        .rejects.toMatchObject({ status: 503 });
    }
    await expect(service.getCheckpoint(project.projectId, owner, randomUUID()))
      .rejects.toMatchObject({ status: 404 });
    await expect(service.getCheckpoint(project.projectId, owner, "not-a-uuid"))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.listCheckpoints(project.projectId, owner, { limit: 101 }))
      .rejects.toMatchObject({ status: 400 });
    await expect(service.listCheckpoints(project.projectId, owner,
      { beforeCheckpointId: "invalid" })).rejects.toMatchObject({ status: 400 });
    expect((await new ProjectDocumentService(pool, auth)
      .getCheckpoint(project.projectId, owner, input.checkpointId)).document).toEqual(project.document);
  });

  it("paginates by stable checkpoint IDs without exposing records outside the project", async () => {
    const { service, owner, viewer, auth } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    await auth.changeMembership(project.projectId, owner, viewer.principalId, "viewer");
    const ids = [];
    for (let i = 0; i < 3; i++) {
      const input = { ...checkpointInput(), name: `Version ${i}` };
      await service.createCheckpoint(project.projectId, owner, input);
      ids.push(input.checkpointId);
    }
    const pages = [];
    let beforeCheckpointId: string | undefined;
    for (let i = 0; i < 3; i++) {
      const page = await service.listCheckpoints(project.projectId, viewer, {
        limit: 1, ...(beforeCheckpointId === undefined ? {} : { beforeCheckpointId }),
      });
      pages.push(page);
      beforeCheckpointId = page.nextBeforeCheckpointId ?? undefined;
    }
    expect(pages.flatMap((page) => page.checkpoints.map((row) => row.checkpointId)))
      .toEqual(ids.sort().reverse());
    expect(pages[2]?.nextBeforeCheckpointId).toBeNull();
    expect((await service.listCheckpoints(project.projectId, viewer,
      { beforeCheckpointId: ids.sort()[0]! })).checkpoints).toEqual([]);
  });
});
