import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type SqlPool,
} from "@vera/project-authorization";

import { applyProjectCommentsMigration, applyProjectDocumentsMigration } from "../src/migration.js";
import { ProjectDocumentService } from "../src/service.js";

/* eslint-disable @typescript-eslint/require-await -- Test pool implements the asynchronous SQL port. */

export function documentFor(projectId: string, documentId = randomUUID()): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: documentId, projectId, title: "First draft",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 4, liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
}

export function settingsFor(projectId: string, id = randomUUID()) {
  return {
    schemaVersion: "authoring-project-settings/v1" as const,
    id, projectId, version: 1, settingsHash: "sha256:" + "b".repeat(64),
  };
}

export async function harness() {
  const db = new PGlite();
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  await applyProjectCommentsMigration(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const service = new ProjectDocumentService(pool, auth);
  const owner = await auth.resolveActor({ issuer: "https://trusted.suite.test", subject: "owner" });
  const editor = await auth.resolveActor({ issuer: "https://trusted.suite.test", subject: "editor" });
  const viewer = await auth.resolveActor({ issuer: "https://trusted.suite.test", subject: "viewer" });
  return { db, pool, auth, service, owner, editor, viewer };
}

export function initialProject(projectId = randomUUID()) {
  return { projectId, title: "Demo project", clientRequestId: randomUUID(), document: documentFor(projectId) };
}
