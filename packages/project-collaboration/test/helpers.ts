import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import { PGlite } from "@electric-sql/pglite";
import type { PrincipalRef } from "@vera/contracts";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type SqlPool,
} from "@vera/project-authorization";
import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectIdeasMigration,
  ProjectDocumentService,
} from "@vera/project-documents";

import { CollaborationClient } from "../src/client.js";
import { CollaborationHub, type CollaborationConnection } from "../src/hub.js";
import { applyProjectCollaborationMigration } from "../src/migration.js";
import { ProjectCollaborationService, type CollaborationOptions } from "../src/service.js";

/* eslint-disable @typescript-eslint/require-await -- Test pool implements the asynchronous SQL port. */

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/giu;
const template = (JSON.parse(readFileSync(new URL(
  "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
), "utf8")) as { document: ScriptDocumentV2 }).document.activeDraft.blocks[0] as NarrationBlockV2;

/** A real, valid narration row with fresh IDs and one token per word. */
export function narrationRow(text: string): NarrationBlockV2 {
  const ids = new Map<string, string>();
  const row = JSON.parse(JSON.stringify(template).replace(UUID, (id) => {
    if (!ids.has(id)) ids.set(id, randomUUID());
    return ids.get(id)!;
  })) as NarrationBlockV2;
  row.text = text;
  row.tokens = [...text.matchAll(/[^\s[\]]+/gu)].map((match) => ({
    id: randomUUID(), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  }));
  return row;
}

export function scriptFor(projectId: string, texts: string[]): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: randomUUID(), projectId, title: "First draft",
    activeDraft: {
      blocks: [
        { type: "section", id: randomUUID(), title: "Opening", orderKey: "a", version: 1 },
        ...texts.map(narrationRow),
      ],
      supportingItems: [],
    },
    ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
}

let sharedDatabase: Promise<PGlite> | undefined;
/** One migrated in-memory database per test file; every test makes its own project. */
export function database(): Promise<PGlite> {
  return sharedDatabase ??= freshDatabase();
}

export async function freshDatabase(): Promise<PGlite> {
  const db = new PGlite();
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  await applyProjectCommentsMigration(db);
  await applyProjectHistoryMigration(db);
  await applyProjectIdeasMigration(db);
  await applyProjectCollaborationMigration(db);
  return db;
}

/** One "running server" on a database. Call again with the same database to simulate a restart. */
export function server(db: PGlite, options: CollaborationOptions = {}) {
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const documents = new ProjectDocumentService(pool, auth);
  const collaboration = new ProjectCollaborationService(pool, auth, documents, options);
  const hub = new CollaborationHub(collaboration, { revalidateIntervalMs: 0 });
  return { pool, auth, documents, collaboration, hub };
}

export async function harness(texts = ["hello world"], options: CollaborationOptions = {}) {
  const db = await database();
  const running = server(db, options);
  const actor = (subject: string) => running.auth.resolveActor({ issuer: "https://trusted.suite.test", subject });
  const owner = await actor("owner");
  const editor = await actor("editor");
  const viewer = await actor("viewer");
  const projectId = randomUUID();
  const document = scriptFor(projectId, texts);
  await running.documents.createProject(owner, { projectId, title: "Demo project", clientRequestId: randomUUID(), document });
  await running.auth.changeMembership(projectId, owner, editor.principalId, "editor");
  await running.auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
  const rowIds = document.activeDraft.blocks.filter((block) => block.type === "narration").map((block) => block.id);
  return { db, ...running, owner, editor, viewer, projectId, document, rowIds };
}

export interface Link { connection: CollaborationConnection; drop(): void; closedWith: number | undefined }

/** An in-memory connection between a client and the hub, delivered asynchronously like a socket. */
export async function link(
  hub: CollaborationHub, projectId: string, principal: PrincipalRef, client: CollaborationClient,
): Promise<Link> {
  let live = true;
  let connection: CollaborationConnection | undefined;
  const early: Uint8Array[] = [];
  const result: Link = {
    connection: undefined as unknown as CollaborationConnection,
    closedWith: undefined,
    drop: () => {
      if (!live) return;
      live = false;
      connection?.disconnected();
      client.detached();
    },
  };
  client.attach({
    send: (bytes) => { if (!live) return; if (connection) connection.receive(bytes); else early.push(bytes); },
    close: () => { result.drop(); },
  });
  try {
    connection = await hub.connect(projectId, principal, {
      send: (bytes) => { queueMicrotask(() => { if (live) client.receive(bytes); }); },
      close: (code) => {
        queueMicrotask(() => { if (live) { live = false; result.closedWith = code; client.detached(); } });
      },
    });
  } catch (error) {
    live = false;
    client.detached();
    throw error;
  }
  result.connection = connection;
  for (const bytes of early) connection.receive(bytes);
  return result;
}

/** Let every queued message and database step finish. */
export async function settle(...links: Link[]): Promise<void> {
  for (let round = 0; round < 6; round += 1) {
    await Promise.all(links.map((item) => item.connection.settled()));
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

export function rowText(client: CollaborationClient, rowId: string): string {
  const root = client.read() as unknown as { document: ScriptDocumentV2 };
  const row = root.document.activeDraft.blocks.find((block) => block.id === rowId);
  return row && "text" in row && typeof row.text === "string" ? row.text : "";
}

/** Edit one Draft row's text on a client. */
export function editRow(client: CollaborationClient, rowId: string, edit: (text: string) => string): void {
  client.change((root) => {
    const document = (root as unknown as { document: ScriptDocumentV2 }).document;
    const row = document.activeDraft.blocks.find((block) => block.id === rowId) as NarrationBlockV2;
    row.text = edit(row.text);
  });
}
