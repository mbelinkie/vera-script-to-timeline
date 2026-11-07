import { beforeEach, describe, expect, it, vi } from "vitest";

const migrations = vi.hoisted(() => ({ auth: vi.fn(), docs: vi.fn() }));
vi.mock("@vera/project-authorization", async (importOriginal) => ({
  ...await importOriginal<object>(),
  applyProjectAuthorizationMigration: migrations.auth,
}));
vi.mock("@vera/project-documents", async (importOriginal) => ({
  ...await importOriginal<object>(),
  applyProjectDocumentsMigration: migrations.docs,
}));

import { MIGRATION_DIGEST, MIGRATION_NAME, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { PROJECT_DOCUMENTS_MIGRATION, PROJECT_DOCUMENTS_MIGRATION_DIGEST } from "@vera/project-documents";

import { applyQaMigrations, assertQaDatabaseTarget, QaDatabaseRefusal } from "../src/migrate.js";
import type { QaConfig } from "../src/qa-config.js";

const config = {
  databaseName: "vera_stt_qa_sandbox",
  databaseUser: "qa_actor",
} as QaConfig;
const user = {
  database_name: "vera_stt_qa_sandbox", user_name: "qa_actor", superuser: false,
  createdb: false, createrole: false, replication: false, bypassrls: false,
};
const receipts = [
  { name: MIGRATION_NAME, version: 1, checksum: MIGRATION_DIGEST },
  { name: PROJECT_DOCUMENTS_MIGRATION, version: 1, checksum: PROJECT_DOCUMENTS_MIGRATION_DIGEST },
];

function harness(args: { user?: typeof user; tables?: { schema_name: string; table_name: string }[];
  receipts?: typeof receipts } = {}) {
  const release = vi.fn();
  const query = vi.fn((sql: string) => {
    if (sql.includes("current_database()")) return Promise.resolve({ rows: [args.user ?? user] });
    if (sql.includes("FROM pg_class")) return Promise.resolve({ rows: args.tables ?? [] });
    if (sql.includes("FROM vera_schema_migrations")) return Promise.resolve({ rows: args.receipts ?? receipts });
    throw new Error(`unrecognized fake SQL: ${sql}`);
  });
  const client = { query, release } as unknown as SqlClient;
  const pool: SqlPool = { connect: vi.fn().mockResolvedValue(client) };
  return { client, pool, query, release };
}

describe("QA target preflight and ordered migrations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    migrations.auth.mockResolvedValue(undefined);
    migrations.docs.mockResolvedValue(undefined);
  });

  it("checks identity and all preexisting tables before any DDL", async () => {
    const h = harness({ tables: [
      { schema_name: "public", table_name: "vera_project_members" },
      { schema_name: "public", table_name: "stt_document_heads" },
    ] });
    await expect(assertQaDatabaseTarget(h.client, config)).resolves.toBeUndefined();
    expect(h.query).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["wrong database", { database_name: "postgres" }],
    ["wrong role", { user_name: "postgres" }],
    ["superuser", { superuser: true }],
    ["createdb", { createdb: true }],
    ["createrole", { createrole: true }],
    ["replication", { replication: true }],
    ["bypassrls", { bypassrls: true }],
  ])("refuses %s before migrations", async (_name, replacement) => {
    const h = harness({ user: { ...user, ...replacement } });
    await expect(applyQaMigrations(h.pool, config)).rejects.toThrow(QaDatabaseRefusal);
    expect(migrations.auth).not.toHaveBeenCalled();
    expect(migrations.docs).not.toHaveBeenCalled();
    expect(h.release).toHaveBeenCalledOnce();
  });

  it("refuses non-service and Research tables or schemas", async () => {
    for (const table of [
      { schema_name: "public", table_name: "research_clips" },
      { schema_name: "research", table_name: "stt_projects" },
    ]) {
      const h = harness({ tables: [table] });
      await expect(applyQaMigrations(h.pool, config)).rejects.toThrow(QaDatabaseRefusal);
    }
    expect(migrations.auth).not.toHaveBeenCalled();
  });

  it("runs auth before documents on a single held client, then verifies exact checksums", async () => {
    const calls: string[] = [];
    migrations.auth.mockImplementation((db: SqlClient) => {
      calls.push("auth"); expect(db).toBe(h.client);
      return Promise.resolve();
    });
    migrations.docs.mockImplementation((db: SqlClient) => {
      calls.push("docs"); expect(db).toBe(h.client);
      return Promise.resolve();
    });
    const h = harness();
    expect(await applyQaMigrations(h.pool, config)).toEqual(receipts);
    expect(calls).toEqual(["auth", "docs"]);
    expect(h.query.mock.calls.map(([sql]) => sql.includes("FROM vera_schema_migrations")))
      .toEqual([false, false, true]);
    expect(h.release).toHaveBeenCalledOnce();
  });

  it("fails shut on bad or extra migration receipts", async () => {
    for (const changed of [
      [receipts[0]!, { ...receipts[1]!, checksum: "0".repeat(64) }],
      [receipts[0]!],
      [...receipts, { name: "unexpected", version: 1, checksum: "c".repeat(64) }],
    ]) {
      const h = harness({ receipts: changed });
      await expect(applyQaMigrations(h.pool, config)).rejects.toThrow(QaDatabaseRefusal);
      expect(h.release).toHaveBeenCalledOnce();
    }
  });

  it("does not start docs on an auth failure and always releases the client", async () => {
    migrations.auth.mockRejectedValueOnce(new Error("checksum refused"));
    const h = harness();
    await expect(applyQaMigrations(h.pool, config)).rejects.toThrow("checksum refused");
    expect(migrations.docs).not.toHaveBeenCalled();
    expect(h.release).toHaveBeenCalledOnce();
  });
});
