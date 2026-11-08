import { randomUUID } from "node:crypto";

import {
  ProjectAuthorizationService, type SqlClient, type SqlPool,
} from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDocumentService } from "../src/service.js";
import { harness, initialProject, settingsFor } from "./helpers.js";

vi.setConfig({ testTimeout: 90_000 });
const cleanups: Array<() => Promise<void>> = [];
async function setup() {
  const h = await harness();
  cleanups.push(async () => { await h.db.close(); });
  return h;
}
afterEach(async () => { for (const cleanup of cleanups.splice(0)) await cleanup(); });

describe("checkpoint restore is a new, attributed and atomic document head", () => {
  it("retains exact frozen bytes and provenance without mutating checkpoint, approval, history, settings or title", async () => {
    const { db, pool, auth, service, owner, editor, viewer } = await setup();
    const project = initialProject();
    const genesis = await service.createProject(owner, project);
    await auth.changeMembership(project.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(project.projectId, owner, viewer.principalId, "viewer");
    const checkpointId = randomUUID();
    await service.createCheckpoint(project.projectId, editor, {
      checkpointId, clientMutationId: randomUUID(), sourceRevision: 0, name: "Frozen baseline",
    });
    const approval = await service.approveCheckpoint(project.projectId, owner, checkpointId,
      { clientMutationId: randomUUID() });
    await service.putDocument(project.projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Changed draft" },
    });
    await service.putDocument(project.projectId, owner, {
      expectedRevision: 1, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Latest draft" },
    });
    const settings = settingsFor(project.projectId);
    await service.putSettings(project.projectId, owner, {
      expectedSettingsRevision: 0, clientMutationId: randomUUID(), settings,
    });
    await service.patchProject(project.projectId, owner, {
      expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "Renamed project",
    });
    const before = await db.query<{ document_json: string; source_digest: string }>(
      "SELECT document_json,source_digest FROM stt_document_checkpoints WHERE project_id=$1",
      [project.projectId],
    );
    const request = { expectedRevision: 2, clientMutationId: randomUUID() };
    const restored = await service.restoreCheckpoint(project.projectId, editor, checkpointId, request);
    expect(restored).toEqual({ projectId: project.projectId, revision: 3,
      clientMutationId: request.clientMutationId, digest: genesis.documentDigest, duplicateDelivery: false });
    expect(await service.getDocument(project.projectId, viewer)).toEqual({
      projectId: project.projectId, revision: 3, digest: genesis.documentDigest, document: project.document,
    });
    const revision = await service.getDocumentRevision(project.projectId, viewer, 3);
    expect(revision).toMatchObject({ revision: 3, document: project.document,
      attribution: { actorId: editor.principalId, clientMutationId: request.clientMutationId,
        expectedRevision: 2, restoreOrigin: {
          checkpointId, sourceRevision: 0, sourceDigest: genesis.documentDigest,
        } } });
    expect((await service.getDocumentRevision(project.projectId, owner, 1)).document.title).toBe("Changed draft");
    expect((await service.getDocumentRevision(project.projectId, owner, 2)).document.title).toBe("Latest draft");
    expect((await service.getCheckpoint(project.projectId, viewer, checkpointId)).approval)
      .toEqual({ approvedAt: approval.approvedAt, approvedBy: owner.principalId });
    expect(await service.getSettings(project.projectId, owner)).toMatchObject({ settings, settingsRevision: 1 });
    expect(await service.getProject(project.projectId, owner)).toMatchObject({
      title: "Renamed project", projectVersion: 2,
    });
    expect((await db.query("SELECT document_json,source_digest FROM stt_document_checkpoints WHERE project_id=$1",
      [project.projectId])).rows).toEqual(before.rows);
    const raw = await db.query<{ restored_by: string; client_mutation_id: string; document_json: string }>(
      "SELECT x.restored_by,x.client_mutation_id,r.document_json FROM stt_document_restores x" +
        " JOIN stt_document_revisions r ON r.project_id=x.project_id AND r.revision=x.new_revision" +
        " WHERE x.project_id=$1 AND x.new_revision=3", [project.projectId],
    );
    expect(raw.rows[0]).toMatchObject({ restored_by: editor.principalId,
      client_mutation_id: request.clientMutationId, document_json: before.rows[0]?.document_json });
    const newHead = await service.putDocument(project.projectId, owner, {
      expectedRevision: 3, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Work after restore" },
    });
    expect(newHead.revision).toBe(4);
    const reopened = new ProjectDocumentService(pool, auth);
    expect(await reopened.restoreCheckpoint(project.projectId, editor, checkpointId, request))
      .toEqual({ ...restored, duplicateDelivery: true });
    expect((await service.getDocument(project.projectId, owner)).revision).toBe(4);
    await expect(service.restoreCheckpoint(project.projectId, editor, checkpointId,
      { ...request, expectedRevision: 3 }))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const counts = await db.query<{ revisions: number; restores: number }>(
      "SELECT (SELECT count(*)::integer FROM stt_document_revisions WHERE project_id=$1) AS revisions," +
        "(SELECT count(*)::integer FROM stt_document_restores WHERE project_id=$1) AS restores",
      [project.projectId],
    );
    expect(counts.rows[0]).toEqual({ revisions: 5, restores: 1 });
  });

  it("requires editor role and valid write session, and checks both before replay", async () => {
    const { auth, service, owner, editor, viewer } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    await auth.changeMembership(project.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(project.projectId, owner, viewer.principalId, "viewer");
    const checkpointId = randomUUID();
    await service.createCheckpoint(project.projectId, owner, {
      checkpointId, clientMutationId: randomUUID(), name: "Unapproved", sourceRevision: 0,
    });
    const request = { expectedRevision: 0, clientMutationId: randomUUID() };
    await expect(service.restoreCheckpoint(project.projectId, viewer, checkpointId, request))
      .rejects.toMatchObject({ status: 403 });
    await expect(service.restoreCheckpoint(project.projectId, editor, randomUUID(), request))
      .rejects.toMatchObject({ status: 404 });
    await expect(service.restoreCheckpoint(project.projectId, editor, checkpointId,
      { ...request, writeSessionId: randomUUID() })).rejects.toMatchObject({ status: 403 });
    const sessionId = await auth.openWriteSession(project.projectId, editor);
    const restored = await service.restoreCheckpoint(project.projectId, editor, checkpointId,
      { ...request, writeSessionId: sessionId });
    expect(restored.revision).toBe(1);
    await auth.changeMembership(project.projectId, owner, editor.principalId, null);
    await expect(service.restoreCheckpoint(project.projectId, editor, checkpointId,
      { ...request, writeSessionId: sessionId })).rejects.toMatchObject({ status: 403 });
    await auth.changeMembership(project.projectId, owner, editor.principalId, "editor");
    await expect(service.restoreCheckpoint(project.projectId, editor, checkpointId,
      { ...request, writeSessionId: sessionId })).rejects.toMatchObject({ status: 403 });
    expect((await service.getDocument(project.projectId, owner)).revision).toBe(1);
  });

  it("rejects stale revisions, key reuse across commands, foreign checkpoints, malformed inputs and disabled actors", async () => {
    const { db, service, owner, editor } = await setup();
    const project = initialProject();
    const other = initialProject();
    await service.createProject(owner, project);
    await service.createProject(editor, other);
    const checkpointId = randomUUID();
    await service.createCheckpoint(project.projectId, owner, {
      checkpointId, clientMutationId: randomUUID(), name: "Start", sourceRevision: 0,
    });
    await expect(service.restoreCheckpoint(other.projectId, editor, checkpointId, {
      expectedRevision: 0, clientMutationId: randomUUID(),
    })).rejects.toMatchObject({ status: 404 });
    await service.putDocument(project.projectId, owner, {
      expectedRevision: 0, clientMutationId: randomUUID(), document: project.document,
    });
    const old = { expectedRevision: 0, clientMutationId: randomUUID() };
    await expect(service.restoreCheckpoint(project.projectId, owner, checkpointId, old))
      .rejects.toMatchObject({ status: 409, metadata: { currentRevision: 1 } });
    const request = { expectedRevision: 1, clientMutationId: randomUUID() };
    await service.restoreCheckpoint(project.projectId, owner, checkpointId, request);
    await expect(service.restoreCheckpoint(project.projectId, owner, checkpointId, {
      expectedRevision: 2, clientMutationId: request.clientMutationId,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.putDocument(project.projectId, owner, {
      expectedRevision: 2, clientMutationId: request.clientMutationId, document: project.document,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.createCheckpoint(project.projectId, owner, {
      checkpointId: randomUUID(), name: "Bad key", sourceRevision: 0,
      clientMutationId: request.clientMutationId,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    const foreignKey = randomUUID();
    await service.createCheckpoint(project.projectId, owner, {
      checkpointId: randomUUID(), name: "Reserved key", sourceRevision: 0, clientMutationId: foreignKey,
    });
    await expect(service.restoreCheckpoint(project.projectId, owner, checkpointId, {
      expectedRevision: 2, clientMutationId: foreignKey,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(service.restoreCheckpoint(project.projectId, owner, checkpointId, {
      expectedRevision: -1, clientMutationId: randomUUID(),
    })).rejects.toMatchObject({ status: 400 });
    await expect(service.restoreCheckpoint(project.projectId, owner, "bad-id", request))
      .rejects.toMatchObject({ status: 400 });
    await db.query("UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1", [owner.principalId]);
    await expect(service.restoreCheckpoint(project.projectId, owner, checkpointId, request))
      .rejects.toMatchObject({ status: 403 });
  });

  it("rolls back revision, provenance, head and comments on failed head CAS or provenance insert", async () => {
    const { db, pool, service, owner } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    const checkpointId = randomUUID();
    await service.createCheckpoint(project.projectId, owner, {
      checkpointId, clientMutationId: randomUUID(), name: "Rollback", sourceRevision: 0,
    });
    const baseline = await service.getDocument(project.projectId, owner);
    const before = await db.query<{ revisions: number; restores: number }>(
      "SELECT (SELECT count(*)::integer FROM stt_document_revisions WHERE project_id=$1) AS revisions," +
        "(SELECT count(*)::integer FROM stt_document_restores WHERE project_id=$1) AS restores",
      [project.projectId],
    );
    for (const failAt of ["UPDATE stt_document_heads", "INSERT INTO stt_document_restores"]) {
      const failPool: SqlPool = { connect: async () => {
        const connection = await pool.connect();
        return {
          query: async <R>(sql: string, params?: readonly unknown[]) => {
            if (sql.startsWith(failAt)) {
              if (failAt.startsWith("UPDATE")) return { rows: [] as R[] };
              throw new Error("injected provenance failure");
            }
            return await connection.query<R>(sql, params);
          },
          release: () => { connection.release?.(); },
        } satisfies SqlClient;
      } };
      const faulty = new ProjectDocumentService(failPool, new ProjectAuthorizationService(failPool));
      await expect(faulty.restoreCheckpoint(project.projectId, owner, checkpointId, {
        expectedRevision: 0, clientMutationId: randomUUID(),
      })).rejects.toMatchObject({ status: failAt.startsWith("UPDATE") ? 409 : 503 });
      expect(await service.getDocument(project.projectId, owner)).toEqual(baseline);
      expect((await db.query("SELECT (SELECT count(*)::integer FROM stt_document_revisions " +
        "WHERE project_id=$1) AS revisions,(SELECT count(*)::integer FROM stt_document_restores " +
        "WHERE project_id=$1) AS restores", [project.projectId])).rows).toEqual(before.rows);
    }
  });

  it("fails closed for altered checkpoint-source digests and changed frozen bytes, including replay", async () => {
    const { pool, service, owner } = await setup();
    const project = initialProject();
    await service.createProject(owner, project);
    const checkpointId = randomUUID();
    await service.createCheckpoint(project.projectId, owner, {
      checkpointId, clientMutationId: randomUUID(), name: "Integrity", sourceRevision: 0,
    });
    const request = { expectedRevision: 0, clientMutationId: randomUUID() };
    await service.restoreCheckpoint(project.projectId, owner, checkpointId, request);
    for (const sqlTarget of ["FROM stt_document_checkpoints c", "FROM stt_document_checkpoints WHERE"]) {
      const badPool: SqlPool = { connect: async () => {
        const connection = await pool.connect();
        return {
          query: async <R>(sql: string, params?: readonly unknown[]) => {
            const result = await connection.query<R>(sql, params);
            if (!sql.includes(sqlTarget)) return result;
            return { rows: result.rows.map((row) => ({ ...(row as object),
              document_json: "{}" }) as R) };
          },
          release: () => { connection.release?.(); },
        } satisfies SqlClient;
      } };
      const tampered = new ProjectDocumentService(badPool, new ProjectAuthorizationService(badPool));
      await expect(tampered.restoreCheckpoint(project.projectId, owner, checkpointId, {
        expectedRevision: 1, clientMutationId: randomUUID(),
      })).rejects.toMatchObject({ status: 503 });
      if (sqlTarget.includes(" c")) {
        await expect(tampered.restoreCheckpoint(project.projectId, owner, checkpointId, request))
          .rejects.toMatchObject({ status: 503 });
      }
    }
    expect((await service.getDocument(project.projectId, owner)).revision).toBe(1);
    expect((await service.listDocumentRevisions(project.projectId, owner)).revisions).toHaveLength(2);
  });
});
