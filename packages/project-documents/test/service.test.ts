import { randomUUID } from "node:crypto";

import {
  ProjectAuthorizationService,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDocumentService } from "../src/service.js";
import { documentFor, harness, initialProject, settingsFor } from "./helpers.js";

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
