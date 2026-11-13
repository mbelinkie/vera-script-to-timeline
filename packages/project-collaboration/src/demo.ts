import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { fileURLToPath } from "node:url";

import { PGlite } from "@electric-sql/pglite";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type SqlPool,
  type SuiteIdentityPort,
} from "@vera/project-authorization";
import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectIdeasMigration,
  ProjectDocumentService,
} from "@vera/project-documents";

import { CollaborationClient } from "./client.js";
import { CollaborationHub } from "./hub.js";
import { applyProjectCollaborationMigration } from "./migration.js";
import { ProjectCollaborationService } from "./service.js";
import { sameJson } from "./tree.js";
import { attachCollaborationSocket, connectCollaborationSocket } from "./websocket.js";

/* eslint-disable @typescript-eslint/require-await -- The demo pool and identity implement asynchronous ports. */

const PARAGRAPH = "The harbour is quiet at dawn.";

function script(projectId: string, rowId: string): ScriptDocumentV2 {
  const words = [...PARAGRAPH.matchAll(/\S+/gu)];
  const row: NarrationBlockV2 = {
    type: "narration", id: rowId, orderKey: "b", text: PARAGRAPH, version: 1,
    tokens: words.map((word) => ({ id: randomUUID(), value: word[0], startOffset: word.index,
      endOffset: word.index + word[0].length })),
    overlayEvents: [], timingPolicy: "narration_spine", state: "excluded", notes: [],
  };
  return {
    schemaVersion: "script-document/v2", id: randomUUID(), projectId, title: "Demo script",
    activeDraft: {
      blocks: [{ type: "section", id: randomUUID(), title: "Opening", orderKey: "a", version: 1 }, row],
      supportingItems: [],
    },
    ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: "sha256:" + "0".repeat(64),
  };
}

function textOf(client: CollaborationClient, rowId: string): string {
  const document = (client.read() as unknown as { document: ScriptDocumentV2 }).document;
  return (document.activeDraft.blocks.find((block) => block.id === rowId) as NarrationBlockV2).text;
}

function type(client: CollaborationClient, rowId: string, edit: (text: string) => string): void {
  client.change((root) => {
    const document = (root as unknown as { document: ScriptDocumentV2 }).document;
    const row = document.activeDraft.blocks.find((block) => block.id === rowId) as NarrationBlockV2;
    row.text = edit(row.text);
  });
}

export interface DemoResult {
  matthew: string;
  writer: string;
  saved: string;
  identical: boolean;
  savedRevision: number;
  authors: { actor: string; text: string }[];
}

/**
 * A real collaboration service on a throwaway in-memory database, reached
 * over real WebSockets by two scripted people who type over each other, go
 * offline, and come back.
 */
export async function runDemo(log: (line: string) => void = () => undefined): Promise<DemoResult> {
  const db = new PGlite();
  await db.waitReady;
  for (const migrate of [applyProjectAuthorizationMigration, applyProjectDocumentsMigration,
    applyProjectCommentsMigration, applyProjectHistoryMigration, applyProjectIdeasMigration,
    applyProjectCollaborationMigration]) await migrate(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const documents = new ProjectDocumentService(pool, auth);
  const collaboration = new ProjectCollaborationService(pool, auth, documents, { materializeDelayMs: 200 });
  const hub = new CollaborationHub(collaboration);

  // Demo sign-in: each person holds a private random token.
  const tokens = new Map<string, string>([[randomUUID(), "matthew"], [randomUUID(), "writer"]]);
  const identity: SuiteIdentityPort = {
    authenticate: async (request) => {
      const subject = tokens.get(request.headers.get("authorization")?.replace(/^Bearer /u, "") ?? "");
      if (!subject) throw new Error("unknown token");
      return { issuer: "urn:vera:stt:collaboration-demo", subject };
    },
  };
  const [matthewToken, writerToken] = [...tokens.keys()] as [string, string];
  const matthewActor = await auth.resolveActor({ issuer: "urn:vera:stt:collaboration-demo", subject: "matthew" });
  const writerActor = await auth.resolveActor({ issuer: "urn:vera:stt:collaboration-demo", subject: "writer" });
  const names = new Map([[matthewActor.principalId, "Matthew"], [writerActor.principalId, "Writer"]]);
  const projectId = randomUUID();
  const rowId = randomUUID();
  await documents.createProject(matthewActor, { projectId, title: "Demo project",
    clientRequestId: randomUUID(), document: script(projectId, rowId) });
  await auth.changeMembership(projectId, matthewActor, writerActor.principalId, "editor");

  const server = createServer((_request, response) => { response.writeHead(404).end(); });
  await new Promise<void>((resolve) => { server.listen(0, "127.0.0.1", resolve); });
  const port = (server.address() as AddressInfo).port;
  attachCollaborationSocket(server, { identity, authorization: auth, hub, expectedHost: `127.0.0.1:${port}` });
  const url = `ws://127.0.0.1:${port}/v1/projects/${projectId}/collaboration`;

  // The script runs faster than a person types, so every change is its own undo step.
  const matthew = new CollaborationClient({ undoCaptureMs: 0 });
  const writer = new CollaborationClient({ undoCaptureMs: 0 });
  const show = (step: string): void => {
    log(`\n${step}`);
    log(`  Matthew [${matthew.state}]: ${textOf(matthew, rowId)}`);
    log(`  Writer  [${writer.state}]: ${textOf(writer, rowId)}`);
  };
  const synced = async (): Promise<void> => {
    await Promise.all([matthew.whenSynced(), writer.whenSynced()]);
    // Give the other person's copy a moment to receive what was just stored.
    for (let waited = 0; waited < 2_000 && !sameJson(matthew.read(), writer.read()); waited += 20) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };

  try {
    let matthewSocket = await connectCollaborationSocket(matthew, url, { Authorization: `Bearer ${matthewToken}` });
    const writerSocket = await connectCollaborationSocket(writer, url, { Authorization: `Bearer ${writerToken}` });
    await synced();
    show("1. Both open the same script.");

    type(matthew, rowId, (text) => text.replace("quiet", "quiet and grey"));
    type(writer, rowId, (text) => text.replace("at dawn", "at dawn, before the boats leave"));
    await synced();
    show("2. Both type in the same paragraph at the same moment.");

    matthewSocket.close();
    await matthewSocket.closed;
    type(matthew, rowId, (text) => text.replace("The harbour", "The old harbour"));
    type(matthew, rowId, (text) => text.replace(" and grey", ""));
    type(writer, rowId, (text) => text + " Nobody is awake yet.");
    await writer.whenSynced();
    show("3. Matthew goes offline and keeps editing; the writer keeps typing.");

    matthewSocket = await connectCollaborationSocket(matthew, url, { Authorization: `Bearer ${matthewToken}` });
    await synced();
    show("4. Matthew reconnects. Both sets of changes are merged.");

    writer.undo();
    await synced();
    show("5. The writer presses undo: only the writer's last change goes away.");

    await collaboration.flush(projectId);
    const saved = await documents.getDocument(projectId, matthewActor);
    const savedText = (saved.document.activeDraft.blocks.find((block) => block.id === rowId) as NarrationBlockV2).text;
    const authors = (await collaboration.authorship(projectId, matthewActor, rowId))
      .map((run) => ({ actor: names.get(run.actorId ?? "") ?? "unknown", text: run.text }));
    const result: DemoResult = {
      matthew: textOf(matthew, rowId), writer: textOf(writer, rowId), saved: savedText,
      identical: sameJson(matthew.read(), writer.read()), savedRevision: saved.revision, authors,
    };
    log(`\nSaved script (revision ${saved.revision}): ${savedText}`);
    log("Who wrote what:");
    for (const run of authors) log(`  ${run.actor.padEnd(8)} ${JSON.stringify(run.text)}`);
    log(result.identical && result.saved === result.matthew
      ? "\nRESULT: both people and the saved script hold exactly the same text."
      : "\nRESULT: MISMATCH. The copies differ.");
    matthewSocket.close();
    writerSocket.close();
    return result;
  } finally {
    matthew.destroy();
    writer.destroy();
    await hub.close();
    server.closeAllConnections();
    await new Promise<void>((resolve) => { server.close(() => { resolve(); }); });
    await db.close();
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  runDemo((line) => { process.stdout.write(line + "\n"); }).then((result) => {
    process.exitCode = result.identical && result.saved === result.matthew ? 0 : 1;
  }, (error: unknown) => {
    process.stderr.write(`Collaboration demo failed: ${error instanceof Error ? error.message : "unknown error"}\n`);
    process.exitCode = 1;
  });
}
