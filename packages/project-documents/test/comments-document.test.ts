import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { ProjectAuthorizationService, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectCommentService } from "../src/comments.js";
import { ProjectDocumentService } from "../src/service.js";
import { sha256 } from "../src/model.js";
import { documentFor, harness } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Test-only SQL proxy mimics asynchronous pool. */
vi.setConfig({ testTimeout: 90_000 });
const id = () => randomUUID();
const closers: Array<() => Promise<void>> = [];

function synthetic(projectId: string) {
  const original = JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
  ), "utf8")) as { document: ScriptDocumentV2 };
  const document = documentFor(projectId);
  const block = structuredClone(original.document.activeDraft.blocks[0]) as NarrationBlockV2;
  block.text = "hello blue world";
  block.tokens = [
    { id: id(), value: "hello", startOffset: 0, endOffset: 5 },
    { id: id(), value: "blue", startOffset: 6, endOffset: 10 },
    { id: id(), value: "world", startOffset: 11, endOffset: 16 },
  ];
  document.activeDraft.blocks.push(block);
  return { document, block, anchor: { kind: "text" as const,
    blockId: block.id, startTokenId: block.tokens[1]!.id, endTokenId: block.tokens[2]!.id } };
}

async function setup() {
  const h = await harness();
  closers.push(async () => { await h.db.close(); });
  const projectId = id();
  const { document, block, anchor } = synthetic(projectId);
  await h.service.createProject(h.owner, { projectId, title: "Atomic comment test", clientRequestId: id(), document });
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  const comments = new ProjectCommentService(h.pool, h.auth);
  const threadId = id();
  const create = { kind: "create", threadId, messageId: id(), body: "Comment sentinel 385",
    mentionActorIds: [] as string[], anchor };
  return { ...h, comments, projectId, document, block, anchor, create, threadId };
}

type H = Awaited<ReturnType<typeof setup>>;
async function comment(h: H) {
  return await h.comments.applyOperation(h.projectId, h.editor, {
    expectedCommentRevision: 0, clientMutationId: id(), operation: h.create,
  });
}
function edited(h: H): ScriptDocumentV2 {
  const changed = structuredClone(h.document);
  const block = changed.activeDraft.blocks[0] as NarrationBlockV2;
  block.text = "hello green world";
  block.tokens[1]!.value = "green";
  block.tokens[1]!.endOffset = 11;
  block.tokens[2]!.startOffset = 12;
  block.tokens[2]!.endOffset = 17;
  block.version++;
  return changed;
}
async function put(h: H, doc: ScriptDocumentV2, expectedRevision = 0, mutationId = id()) {
  return await h.service.putDocument(h.projectId, h.owner, {
    expectedRevision, clientMutationId: mutationId, document: doc,
  });
}

afterEach(async () => { for (const close of closers.splice(0)) await close(); });

describe("atomic document PUT / anchored comment bridge", () => {
  it("does not create comment storage for projects without a comment head", async () => {
    const h = await setup();
    await put(h, edited(h));
    expect(await h.comments.getComments(h.projectId, h.owner)).toMatchObject({
      documentRevision: 1, commentRevision: 0, threads: [],
    });
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_heads")).rows[0]?.n).toBe(0);
  });

  it("stales exactly once with a document edit; replay and subsequent explicit reattach are safe", async () => {
    const h = await setup();
    await comment(h);
    const mutationId = id();
    const newDocument = edited(h);
    const changed = await put(h, newDocument, 0, mutationId);
    expect(changed).toMatchObject({ revision: 1, duplicateDelivery: false });
    const stale = await h.comments.getComments(h.projectId, h.owner);
    expect(stale).toMatchObject({ documentRevision: 1, commentRevision: 2 });
    expect(stale.threads[0]?.attachment).toMatchObject({ status: "stale", quotedText: "blue world" });
    expect(stale.threads[0]?.messages[0]?.body).toBe("Comment sentinel 385");
    expect(await put(h, newDocument, 0, mutationId)).toEqual({ ...changed, duplicateDelivery: true });
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(2);
    await expect(h.comments.applyOperation(h.projectId, h.editor, {
      expectedCommentRevision: 1, clientMutationId: id(), operation: { kind: "resolve", threadId: h.threadId },
    })).rejects.toMatchObject({ status: 409, metadata: { currentCommentRevision: 2 } });
    await h.comments.applyOperation(h.projectId, h.editor, {
      expectedCommentRevision: 2, clientMutationId: id(), operation: {
        kind: "reattach", threadId: h.threadId, anchor: h.anchor,
      },
    });
    expect((await h.comments.getComments(h.projectId, h.owner)).threads[0]?.attachment)
      .toMatchObject({ status: "attached", quotedText: "green world" });
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_events")).rows[0]?.n).toBe(2);
    expect((await h.service.getDocument(h.projectId, h.owner)).document).toEqual(newDocument);
  });

  it("advances a byte-identical document revision without rewriting comment history/digest", async () => {
    const h = await setup();
    await comment(h);
    const before = await h.db.query<{ state_digest: string; state_json: string }>(
      "SELECT state_digest,state_json FROM stt_comment_heads WHERE project_id=$1", [h.projectId]);
    await put(h, h.document);
    const after = await h.db.query<{ state_digest: string; state_json: string; document_revision: string }>(
      "SELECT state_digest,state_json,document_revision::text FROM stt_comment_heads WHERE project_id=$1", [h.projectId]);
    expect(after.rows[0]).toMatchObject({ ...before.rows[0], document_revision: "1" });
    expect(await h.comments.getComments(h.projectId, h.owner)).toMatchObject({
      documentRevision: 1, commentRevision: 1,
    });
  });

  it("rolls back document revision and digest when comment state is corrupt", async () => {
    const h = await setup();
    await comment(h);
    const previous = await h.service.getDocument(h.projectId, h.owner);
    await h.db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [h.projectId, sha256("corrupt")]);
    await expect(put(h, edited(h))).rejects.toMatchObject({ status: 503 });
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(previous);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions")).rows[0]?.n).toBe(1);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_events")).rows[0]?.n).toBe(1);
  });

  it("rolls back a document PUT if the late comment head write fails", async () => {
    const h = await setup();
    await comment(h);
    const brokenPool: SqlPool = { connect: async () => ({
      query: async <T>(sql: string, params?: readonly unknown[]) => {
        if (sql.startsWith("UPDATE stt_comment_heads")) throw new Error("synthetic write failure");
        return await h.db.query<T>(sql, params === undefined ? undefined : [...params]);
      },
    } satisfies SqlClient) };
    const broken = new ProjectDocumentService(brokenPool, new ProjectAuthorizationService(brokenPool));
    await expect(broken.putDocument(h.projectId, h.owner, {
      expectedRevision: 0, clientMutationId: id(), document: edited(h),
    })).rejects.toMatchObject({ status: 503 });
    expect((await h.service.getDocument(h.projectId, h.owner)).revision).toBe(0);
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(1);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions")).rows[0]?.n).toBe(1);
  });

  it("serial orders comment creation and edit, rejecting the losing stale CAS", async () => {
    const h = await setup();
    await comment(h); // Comment wins first and must be invalidated in the following PUT.
    await put(h, edited(h));
    await expect(h.comments.applyOperation(h.projectId, h.editor, {
      expectedCommentRevision: 1, clientMutationId: id(), operation: {
        kind: "reply", threadId: h.threadId, messageId: id(), body: "late reply", mentionActorIds: [],
      },
    })).rejects.toMatchObject({ status: 409 });
    await h.comments.applyOperation(h.projectId, h.editor, {
      expectedCommentRevision: 2, clientMutationId: id(), operation: {
        kind: "reply", threadId: h.threadId, messageId: id(), body: "fresh reply", mentionActorIds: [],
      },
    });
    expect(await h.comments.getComments(h.projectId, h.owner)).toMatchObject({
      documentRevision: 1, commentRevision: 3,
    });
  });
});
