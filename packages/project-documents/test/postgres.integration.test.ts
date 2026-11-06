import { randomUUID } from "node:crypto";

import pg from "pg";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import { describe, expect, it, vi } from "vitest";

import { applyProjectDocumentsMigration } from "../src/migration.js";
import { ProjectDocumentService } from "../src/service.js";
import { initialProject } from "./helpers.js";

/** Run only with a disposable PostgreSQL DB, never a live deployment. */
const scratchUrl = process.env.VERA_PROJECT_DOCUMENTS_TEST_DATABASE_URL;
const postgres = scratchUrl ? describe : describe.skip;
vi.setConfig({ testTimeout: 90_000 });

postgres("independent PostgreSQL connections", () => {
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
});
