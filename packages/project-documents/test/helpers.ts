import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import { PGlite } from "@electric-sql/pglite";
import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2 } from "@vera/contracts/v2";
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
} from "../src/migration.js";
import { ProjectDocumentService } from "../src/service.js";

/* eslint-disable @typescript-eslint/require-await -- Test pool implements the asynchronous SQL port. */

export function documentFor(projectId: string, documentId = randomUUID()): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: documentId, projectId, title: "First draft",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 4, liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
}

/** Real typed narration, primary footage and cited anchors for durable Extras tests. */
export function extrasDocumentFor(projectId: string) {
  const original = JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
  ), "utf8")) as { document: ScriptDocumentV2 };
  const document = documentFor(projectId);
  const sectionId = randomUUID();
  const row = structuredClone(original.document.activeDraft.blocks[0]) as NarrationBlockV2;
  const token = row.tokens[0]!;
  const anchor = { kind: "word" as const, anchor: { blockId: row.id,
    tokenId: token.id, affinity: "before" as const, quotedWord: token.value, anchorVersion: 1 } };
  const citation: SupportingItemV2 = { id: randomUUID(), role: "citation", version: 1,
    orderKey: "evidence", content: "Verified evidence", placement: { kind: "point", anchor },
    displayAttachment: anchor };
  document.activeDraft.blocks = [
    { type: "section", id: sectionId, title: "Draft", orderKey: "1", version: 1 }, row,
  ];
  document.activeDraft.supportingItems = [citation];
  return { document, sectionId, rowId: row.id, citationId: citation.id };
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
  await applyProjectHistoryMigration(db);
  await applyProjectIdeasMigration(db);
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
