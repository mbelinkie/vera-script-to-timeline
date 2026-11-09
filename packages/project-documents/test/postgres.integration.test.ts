import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import pg from "pg";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import { describe, expect, it, vi } from "vitest";

import { ProjectCommentService } from "../src/comments.js";
import {
  applyProjectCommentsMigration, applyProjectDocumentsMigration, applyProjectHistoryMigration,
} from "../src/migration.js";
import { ProjectDocumentService } from "../src/service.js";
import { documentFor, extrasDocumentFor, initialProject } from "./helpers.js";

/** Run only with a disposable PostgreSQL DB, never a live deployment. */
const scratchUrl = process.env.VERA_PROJECT_DOCUMENTS_TEST_DATABASE_URL;
const postgres = scratchUrl ? describe : describe.skip;
vi.setConfig({ testTimeout: 90_000 });

postgres("independent PostgreSQL connections", () => {
  it("serializes concurrent Extras CAS with another Extras writer and ordinary PUT; revoked sessions cannot replay", async () => {
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
      const migrations = await pool.connect();
      try {
        await applyProjectAuthorizationMigration(migrations);
        await applyProjectDocumentsMigration(migrations);
        await applyProjectCommentsMigration(migrations);
        await applyProjectHistoryMigration(migrations);
      } finally { migrations.release?.(); }
      const auth = new ProjectAuthorizationService(pool);
      const documents = new ProjectDocumentService(pool, auth);
      const owner = await auth.resolveActor({ issuer: "https://extras-races.test", subject: randomUUID() });
      const editor = await auth.resolveActor({ issuer: "https://extras-races.test", subject: randomUUID() });
      const projectId = randomUUID();
      const { document, rowId, sectionId, citationId } = extrasDocumentFor(projectId);
      await documents.createProject(owner, {
        projectId, title: "Disposable Extras races", clientRequestId: randomUUID(), document,
      });
      await auth.changeMembership(projectId, owner, editor.principalId, "editor");
      const writeSessionId = await auth.openWriteSession(projectId, editor);
      const parks = [randomUUID(), randomUUID()].map((bundleId) => ({
        expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId,
        operation: { kind: "stash_rows", rowIds: [rowId], bundleId },
      }));
      const competing = await Promise.allSettled(parks.map(async (input) =>
        await documents.applyExtrasOperation(projectId, editor, input)));
      expect(competing.filter((result) => result.status === "fulfilled")).toHaveLength(1);
      expect(competing.filter((result) => result.status === "rejected"))
        .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
      const winnerIndex = competing.findIndex((result) => result.status === "fulfilled");
      const winner = parks[winnerIndex]!;
      const parked = await documents.getDocument(projectId, owner);
      expect(parked.revision).toBe(1);
      expect(parked.document.activeDraft.blocks.map((row) => row.id)).toEqual([sectionId]);
      expect(parked.document.stash?.[0]?.rows[0]?.id).toBe(rowId);
      expect(parked.document.stash?.[0]?.supportingItems[0]?.id).toBe(citationId);
      expect(parked.document.stash?.[0]?.id).toBe(winner.operation.bundleId);
      const ordinaryPut = { expectedRevision: 1, clientMutationId: randomUUID(),
        document: { ...parked.document, title: "Competing ordinary PUT" } };
      const restore = { expectedRevision: 1, clientMutationId: randomUUID(), writeSessionId,
        operation: { kind: "restore_stash", bundleId: winner.operation.bundleId,
          destination: { sectionId, afterRowId: null, beforeRowId: null } } };
      const mixed = await Promise.allSettled([
        documents.applyExtrasOperation(projectId, editor, restore),
        documents.putDocument(projectId, owner, ordinaryPut),
      ]);
      expect(mixed.filter((result) => result.status === "fulfilled")).toHaveLength(1);
      expect(mixed.filter((result) => result.status === "rejected"))
        .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
      const head = await new ProjectDocumentService(pool, auth).getDocument(projectId, owner);
      expect(head.revision).toBe(2);
      expect(head.document.activeDraft.blocks.some((row) => row.id === rowId))
        .toBe(mixed[0]?.status === "fulfilled");
      expect(head.document.stash?.some((bundle) => bundle.id === winner.operation.bundleId))
        .toBe(mixed[1]?.status === "fulfilled");
      expect(head.digest).toMatch(/^sha256:[a-f\d]{64}$/u);

      await auth.changeMembership(projectId, owner, editor.principalId, null);
      await Promise.all([
        expect(documents.applyExtrasOperation(projectId, editor, winner)).rejects.toMatchObject({ status: 403 }),
        expect(documents.applyExtrasOperation(projectId, editor, {
          ...restore, expectedRevision: 2, clientMutationId: randomUUID(),
        })).rejects.toMatchObject({ status: 403 }),
      ]);
      const afterRevoke = await new ProjectDocumentService(pool, auth).getDocument(projectId, owner);
      expect(afterRevoke).toEqual(head);
      const db = await pool.connect();
      try {
        const counts = await db.query<{ count: number }>(
          "SELECT count(*)::integer AS count FROM stt_document_revisions WHERE project_id=$1", [projectId],
        );
        expect(counts.rows[0]?.count).toBe(3); // creation + exactly two winning revisions
      } finally { db.release?.(); }
    } finally { await server.end(); }
  });

  it("serializes a checkpoint restore against an edit and two competing restores with independent clients", async () => {
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
      const migrationClient = await pool.connect();
      try {
        await applyProjectAuthorizationMigration(migrationClient);
        await applyProjectDocumentsMigration(migrationClient);
        await applyProjectCommentsMigration(migrationClient);
        await applyProjectHistoryMigration(migrationClient);
      } finally { migrationClient.release?.(); }
      const auth = new ProjectAuthorizationService(pool);
      const documents = new ProjectDocumentService(pool, auth);
      const owner = await auth.resolveActor({ issuer: "https://integration.test", subject: randomUUID() });
      const initial = initialProject();
      await documents.createProject(owner, initial);
      const checkpointId = randomUUID();
      await documents.createCheckpoint(initial.projectId, owner, {
        checkpointId, clientMutationId: randomUUID(), name: "Concurrent baseline", sourceRevision: 0,
      });
      const race = await Promise.allSettled([
        documents.restoreCheckpoint(initial.projectId, owner, checkpointId, {
          expectedRevision: 0, clientMutationId: randomUUID(),
        }),
        documents.putDocument(initial.projectId, owner, {
          expectedRevision: 0, clientMutationId: randomUUID(),
          document: { ...initial.document, title: "Concurrent edit" },
        }),
      ]);
      expect(race.filter((value) => value.status === "fulfilled")).toHaveLength(1);
      expect(race.filter((value) => value.status === "rejected")).toMatchObject([
        { status: "rejected", reason: { status: 409 } },
      ]);
      expect((await documents.getDocument(initial.projectId, owner)).revision).toBe(1);
      const twoRestores = await Promise.allSettled([
        documents.restoreCheckpoint(initial.projectId, owner, checkpointId, {
          expectedRevision: 1, clientMutationId: randomUUID(),
        }),
        documents.restoreCheckpoint(initial.projectId, owner, checkpointId, {
          expectedRevision: 1, clientMutationId: randomUUID(),
        }),
      ]);
      expect(twoRestores.filter((value) => value.status === "fulfilled")).toHaveLength(1);
      expect(twoRestores.filter((value) => value.status === "rejected")).toMatchObject([
        { status: "rejected", reason: { status: 409 } },
      ]);
      const reopened = new ProjectDocumentService(pool, auth);
      expect((await reopened.getDocument(initial.projectId, owner)).revision).toBe(2);
      expect((await reopened.getDocumentRevision(initial.projectId, owner, 2)).attribution.restoreOrigin)
        .toMatchObject({ checkpointId, sourceRevision: 0 });
      const db = await pool.connect();
      try {
        const count = await db.query<{ revisions: number; restores: number }>(
          "SELECT (SELECT count(*)::integer FROM stt_document_revisions WHERE project_id=$1) AS revisions," +
            "(SELECT count(*)::integer FROM stt_document_restores WHERE project_id=$1) AS restores",
          [initial.projectId],
        );
        expect(count.rows[0]).toMatchObject({
          revisions: 3, restores: race[0]?.status === "fulfilled" ? 2 : 1,
        });
      } finally { db.release?.(); }
    } finally { await server.end(); }
  });

  it("serializes competing document writers and permission revocation", async () => {
    const server = new pg.Pool({ connectionString: scratchUrl, max: 6 });
    const pool: SqlPool = {
      connect: async (): Promise<SqlClient> => {
        const client = await server.connect();
        return {
          query: async <R>(sql: string, params?: readonly unknown[]) => {
            const result = await client.query(sql, params ? [...params] : []);
            return { rows: result.rows as R[] };
          },
          release: () => { client.release(); },
        };
      },
    };
    try {
      const migrationClient = await pool.connect();
      try {
        await applyProjectAuthorizationMigration(migrationClient);
        await applyProjectDocumentsMigration(migrationClient);
        await applyProjectCommentsMigration(migrationClient);
      } finally {
        migrationClient.release?.();
      }
      const auth = new ProjectAuthorizationService(pool);
      const service = new ProjectDocumentService(pool, auth);
      const owner = await auth.resolveActor({ issuer: "https://suite.integration.test", subject: randomUUID() });
      const editor = await auth.resolveActor({ issuer: "https://suite.integration.test", subject: randomUUID() });
      const initial = initialProject();
      await service.createProject(owner, initial);
      const competing = await Promise.allSettled([
        service.putDocument(initial.projectId, owner, {
          expectedRevision: 0, clientMutationId: randomUUID(),
          document: { ...initial.document, title: "Writer one" },
        }),
        service.putDocument(initial.projectId, owner, {
          expectedRevision: 0, clientMutationId: randomUUID(),
          document: { ...initial.document, title: "Writer two" },
        }),
      ]);
      expect(competing.filter((result) => result.status === "fulfilled")).toHaveLength(1);
      expect(competing.filter((result) => result.status === "rejected")).toHaveLength(1);
      expect(competing.find((result) => result.status === "rejected"))
        .toMatchObject({ reason: { status: 409 } });
      expect((await service.getDocument(initial.projectId, owner)).revision).toBe(1);
      await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
      const session = await auth.openWriteSession(initial.projectId, editor);
      const mutation = {
        expectedRevision: 1, clientMutationId: randomUUID(), writeSessionId: session,
        document: { ...initial.document, title: "Editor revision" },
      };
      expect((await service.putDocument(initial.projectId, editor, mutation)).revision).toBe(2);
      await auth.changeMembership(initial.projectId, owner, editor.principalId, null);
      await expect(service.putDocument(initial.projectId, editor, mutation))
        .rejects.toMatchObject({ status: 403 });
      // A new service instance/pool connection sees the same durable head.
      const reopened = new ProjectDocumentService(pool, auth);
      expect((await reopened.getDocument(initial.projectId, owner)).revision).toBe(2);
      const db = await pool.connect();
      try {
        const rows = await db.query<{ n: number }>(
          "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1",
          [initial.projectId],
        );
        expect(rows.rows[0]?.n).toBe(3);
      } finally {
        db.release?.();
      }
    } finally {
      await server.end();
    }
  });

  it("serializes competing comment creates, replies and document revisions across real connections", async () => {
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
      const db = await pool.connect();
      try {
        await applyProjectAuthorizationMigration(db);
        await applyProjectDocumentsMigration(db);
        await applyProjectCommentsMigration(db);
      } finally { db.release?.(); }
      const auth = new ProjectAuthorizationService(pool);
      const documents = new ProjectDocumentService(pool, auth);
      const comments = new ProjectCommentService(pool, auth);
      const producer = await auth.resolveActor({ issuer: "https://integration.test", subject: randomUUID() });
      const editor = await auth.resolveActor({ issuer: "https://integration.test", subject: randomUUID() });
      const projectId = randomUUID();
      const document = documentFor(projectId);
      const fixture = JSON.parse(readFileSync(new URL(
        "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
      ), "utf8")) as { document: ScriptDocumentV2 };
      document.activeDraft.blocks.push(structuredClone(fixture.document.activeDraft.blocks[0]!));
      await documents.createProject(producer, {
        projectId, title: "Disposable PG comment race", clientRequestId: randomUUID(), document,
      });
      await auth.changeMembership(projectId, producer, editor.principalId, "editor");
      const anchor = { kind: "block" as const, blockId: document.activeDraft.blocks[0]!.id };
      const create = (threadId: string) => ({ expectedCommentRevision: 0,
        clientMutationId: randomUUID(), operation: {
          kind: "create", threadId, messageId: randomUUID(), body: "race synthetic",
          mentionActorIds: [producer.principalId], anchor,
        } });
      const firstId = randomUUID();
      const creates = await Promise.allSettled([
        comments.applyOperation(projectId, editor, create(firstId)),
        comments.applyOperation(projectId, editor, create(randomUUID())),
      ]);
      expect(creates.filter((result) => result.status === "fulfilled")).toHaveLength(1);
      expect(creates.filter((result) => result.status === "rejected"))
        .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
      const created = await comments.getComments(projectId, producer);
      expect(created).toMatchObject({ documentRevision: 0, commentRevision: 1 });
      expect(created.threads).toHaveLength(1);
      const threadId = created.threads[0]!.id;
      const reply = (expectedCommentRevision: number) => ({ expectedCommentRevision,
        clientMutationId: randomUUID(), operation: {
          kind: "reply", threadId, messageId: randomUUID(), body: "racing reply",
          mentionActorIds: [] as string[],
        } });
      const replies = await Promise.allSettled([
        comments.applyOperation(projectId, producer, reply(1)),
        comments.applyOperation(projectId, editor, reply(1)),
      ]);
      expect(replies.filter((result) => result.status === "fulfilled")).toHaveLength(1);
      expect(replies.filter((result) => result.status === "rejected"))
        .toMatchObject([{ status: "rejected", reason: { status: 409 } }]);
      // A title edit changes the typed document and the comment replay head in one commit.
      const race = await Promise.allSettled([
        documents.putDocument(projectId, producer, {
          expectedRevision: 0, clientMutationId: randomUUID(),
          document: { ...document, title: "a concurrent document write" },
        }),
        comments.applyOperation(projectId, editor, reply(2)),
      ]);
      expect(race[0]?.status).toBe("fulfilled");
      if (race[1]?.status === "rejected") {
        expect(race[1].reason).toMatchObject({ status: 409 });
      }
      const state = await comments.getComments(projectId, producer);
      expect(state.documentRevision).toBe(1);
      expect(state.commentRevision).toBe(race[1]?.status === "fulfilled" ? 4 : 3);
      expect(state.threads[0]?.messages).toHaveLength(race[1]?.status === "fulfilled" ? 3 : 2);
      const c = await pool.connect();
      try {
        const head = await c.query<{ revision: string; n: string; state_json: string; state_digest: string }>(
          "SELECT h.comment_revision::text AS revision," +
            "(SELECT count(*)::text FROM stt_comment_events WHERE project_id=$1) AS n," +
            "h.state_json,h.state_digest FROM stt_comment_heads h WHERE h.project_id=$1", [projectId],
        );
        expect(Number(head.rows[0]?.revision)).toBe(state.commentRevision);
        expect(Number(head.rows[0]?.n)).toBe(race[1]?.status === "fulfilled" ? 3 : 2);
        const { sha256 } = await import("../src/model.js");
        expect(sha256(head.rows[0]!.state_json)).toBe(head.rows[0]!.state_digest);
      } finally { c.release?.(); }
      const replayKey = randomUUID();
      const denied = await comments.applyOperation(projectId, editor, {
        expectedCommentRevision: state.commentRevision, clientMutationId: replayKey,
        operation: { kind: "resolve", threadId },
      });
      await auth.changeMembership(projectId, producer, editor.principalId, null);
      await expect(comments.applyOperation(projectId, editor, {
        expectedCommentRevision: state.commentRevision, clientMutationId: replayKey,
        operation: { kind: "resolve", threadId },
      })).rejects.toMatchObject({ status: 403 });
      expect(denied.commentRevision).toBe(state.commentRevision + 1);
    } finally { await server.end(); }
  });
});
