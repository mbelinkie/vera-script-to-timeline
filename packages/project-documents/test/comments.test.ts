import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { CommentAnchorV2 } from "@vera/contracts/authoring-v2";
import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { ProjectAuthorizationService, type SqlClient, type SqlPool } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ProjectCommentService, reconcileCommentsForDocumentRevision,
  type CommentMutationInput,
} from "../src/comments.js";
import { checkedDocument, sha256 } from "../src/model.js";
import { documentFor, harness } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Test-only pool wrappers implement async SQL. */
vi.setConfig({ testTimeout: 90_000 });
const cleanup: Array<() => Promise<void>> = [];
const id = () => randomUUID();

function fixture(projectId: string): { document: ScriptDocumentV2; anchors: CommentAnchorV2[] } {
  const original = JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
  ), "utf8")) as { document: ScriptDocumentV2 };
  const document = documentFor(projectId);
  const first = structuredClone(original.document.activeDraft.blocks[0]) as NarrationBlockV2;
  first.text = "hello blue world";
  first.tokens = [
    { id: id(), value: "hello", startOffset: 0, endOffset: 5 },
    { id: id(), value: "blue", startOffset: 6, endOffset: 10 },
    { id: id(), value: "world", startOffset: 11, endOffset: 16 },
  ];
  const second: NarrationBlockV2 = {
    ...structuredClone(first), id: id(), orderKey: "b0", text: "other row",
    tokens: [{ id: id(), value: "other", startOffset: 0, endOffset: 5 },
      { id: id(), value: "row", startOffset: 6, endOffset: 9 }],
    primaryVisualSequence: { id: id(), version: 1, slots: [{
      id: id(), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
  };
  document.activeDraft.blocks.push(first, second);
  expect(validateScriptDocumentV2(document).valid).toBe(true);
  return { document, anchors: [
    { kind: "text", blockId: first.id, startTokenId: first.tokens[1]!.id, endTokenId: first.tokens[2]!.id },
    { kind: "card", blockId: first.id, cardId: first.primaryVisualSequence!.slots[0]!.id },
    { kind: "block", blockId: second.id },
    { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id },
  ] };
}

async function setup() {
  const h = await harness();
  cleanup.push(async () => { await h.db.close(); });
  const projectId = id();
  const { document, anchors } = fixture(projectId);
  await h.service.createProject(h.owner, { projectId, title: "Synthetic", clientRequestId: id(), document });
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  return { ...h, projectId, document, anchors,
    comments: new ProjectCommentService(h.pool, h.auth) };
}

const create = (anchor: CommentAnchorV2, threadId = id(), messageId = id(), mentionActorIds: string[] = []) => ({
  kind: "create", threadId, messageId, body: "Unique comment sentinel: A41", mentionActorIds, anchor,
});
const reply = (threadId: string, mentionActorIds: string[] = []) => ({
  kind: "reply", threadId, messageId: id(), body: "Second message", mentionActorIds,
});
async function operation(
  ctx: Awaited<ReturnType<typeof setup>>, principal: typeof ctx.owner,
  expectedCommentRevision: number, raw: unknown, clientMutationId: string = id(),
) {
  return await ctx.comments.applyOperation(ctx.projectId, principal,
    { expectedCommentRevision, clientMutationId, operation: raw });
}

afterEach(async () => {
  for (const close of cleanup.splice(0)) await close();
});

describe("durable anchored comments", () => {
  it("starts with read-only empty state, persists four anchors, attribution, replies and resolution", async () => {
    const h = await setup();
    expect(await h.comments.getComments(h.projectId, h.viewer)).toEqual({
      projectId: h.projectId, documentRevision: 0, commentRevision: 0, threads: [],
    });
    expect((await h.db.query<{ n: number }>("SELECT count(*)::integer AS n FROM stt_comment_heads")).rows[0]?.n)
      .toBe(0);
    const threads = h.anchors.map(() => id());
    for (const [index, anchor] of h.anchors.entries()) {
      const receipt = await operation(h, h.editor, index, create(anchor, threads[index], id(), [h.owner.principalId]));
      expect(receipt).toMatchObject({ commentRevision: index + 1, duplicateDelivery: false });
    }
    await operation(h, h.owner, 4, reply(threads[0]!, [h.editor.principalId]));
    await operation(h, h.editor, 5, { kind: "resolve", threadId: threads[0] });
    await operation(h, h.owner, 6, { kind: "reopen", threadId: threads[0] });
    const reopened = new ProjectCommentService(h.pool, h.auth);
    const current = await reopened.getComments(h.projectId, h.viewer);
    expect(current).toMatchObject({ commentRevision: 7, documentRevision: 0 });
    expect(current.threads.map((thread) => thread.attachment.status)).toEqual([
      "attached", "attached", "attached", "attached",
    ]);
    expect(current.threads[0]?.attachment.quotedText).toBe("blue world");
    expect(current.threads[0]?.resolved).toBe(false);
    expect(current.threads[0]?.messages.map((msg) => [msg.actorId, msg.mentionActorIds])).toEqual([
      [h.editor.principalId, [h.owner.principalId]], [h.owner.principalId, [h.editor.principalId]],
    ]);
    const count = await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_events WHERE project_id=$1", [h.projectId]);
    expect(count.rows[0]?.n).toBe(7);
    await expect(h.db.query("UPDATE stt_comment_events SET operation_json='{}' WHERE project_id=$1", [h.projectId]))
      .rejects.toThrow(/append-only/u);
    await expect(h.db.query("DELETE FROM stt_comment_events WHERE project_id=$1", [h.projectId]))
      .rejects.toThrow(/append-only/u);
  });

  it("replays the original receipt after later revisions and refuses different request, stale CAS and duplicate IDs", async () => {
    const h = await setup();
    const first = create(h.anchors[0]!);
    const clientMutationId = id();
    const a = await operation(h, h.editor, 0, first, clientMutationId);
    await operation(h, h.owner, 1, reply(first.threadId));
    expect(await operation(h, h.editor, 0, first, clientMutationId))
      .toEqual({ ...a, duplicateDelivery: true });
    await expect(operation(h, h.editor, 0, { ...first, body: "different" }, clientMutationId))
      .rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await expect(operation(h, h.editor, 0, create(h.anchors[1]!)))
      .rejects.toMatchObject({ status: 409, code: "version_conflict", metadata: { currentCommentRevision: 2 } });
    await expect(operation(h, h.editor, 2, create(h.anchors[1]!, first.threadId)))
      .rejects.toMatchObject({ status: 400 });
    await expect(operation(h, h.editor, 2, { ...reply(first.threadId), messageId: first.messageId }))
      .rejects.toMatchObject({ status: 400 });
    await expect(operation(h, h.editor, 2, { kind: "create", threadId: id(), messageId: id(),
      body: "bad anchor", mentionActorIds: [], anchor: { kind: "block", blockId: id() } }))
      .rejects.toMatchObject({ status: 400 });
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(2);
  });

  it("refuses Viewer writes and cross-project reads/writes, and rechecks revoked actors before replay", async () => {
    const h = await setup();
    const saved = create(h.anchors[0]!);
    const clientMutationId = id();
    await expect(operation(h, h.viewer, 0, saved)).rejects.toMatchObject({ status: 403 });
    await expect(h.comments.getComments(id(), h.owner)).rejects.toMatchObject({ status: 403 });
    const other = await setup();
    await expect(h.comments.getComments(other.projectId, h.editor)).rejects.toMatchObject({ status: 403 });
    await expect(h.comments.applyOperation(other.projectId, h.editor,
      { expectedCommentRevision: 0, clientMutationId: id(), operation: saved }))
      .rejects.toMatchObject({ status: 403 });
    await operation(h, h.editor, 0, saved, clientMutationId);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, null);
    await expect(h.comments.getComments(h.projectId, h.editor)).rejects.toMatchObject({ status: 403 });
    await expect(operation(h, h.editor, 0, saved, clientMutationId)).rejects.toMatchObject({ status: 403 });
    expect((await h.comments.getComments(h.projectId, h.viewer)).commentRevision).toBe(1);
  });

  it("refuses forged operation actor and invalid/foreign/disabled mentions without an existence oracle", async () => {
    const h = await setup();
    const other = await setup();
    const base = create(h.anchors[0]!);
    for (const operationInput of [
      { ...base, actorId: h.owner.principalId },
      { ...base, id: id() },
      { ...base, mentionActorIds: [id()] },
      { ...base, mentionActorIds: [other.owner.principalId] },
    ]) {
      await expect(operation(h, h.editor, 0, operationInput)).rejects.toMatchObject({ status: 400 });
    }
    await h.db.query("UPDATE vera_identity_actors SET disabled_at=now() WHERE id=$1", [h.viewer.principalId]);
    await expect(operation(h, h.editor, 0, { ...base, mentionActorIds: [h.viewer.principalId] }))
      .rejects.toMatchObject({ status: 400 });
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(0);
    expect((await h.db.query<{ n: number }>("SELECT count(*)::integer AS n FROM stt_comment_events")).rows[0]?.n)
      .toBe(0);
  });

  it("refuses an inactive same-project mention even when the actor identity remains enabled", async () => {
    const h = await setup();
    await h.auth.changeMembership(h.projectId, h.owner, h.viewer.principalId, null);
    await expect(operation(h, h.editor, 0,
      create(h.anchors[0]!, id(), id(), [h.viewer.principalId])))
      .rejects.toMatchObject({ status: 400 });
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(0);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_events WHERE project_id=$1", [h.projectId],
    )).rows[0]?.n).toBe(0);
  });

  it("cannot reattach an already-attached thread or invent a new event", async () => {
    const h = await setup();
    const first = create(h.anchors[0]!);
    await operation(h, h.editor, 0, first);
    await expect(operation(h, h.editor, 1, {
      kind: "reattach", threadId: first.threadId, anchor: h.anchors[1],
    })).rejects.toMatchObject({ status: 400 });
    expect((await h.comments.getComments(h.projectId, h.owner)).threads[0]?.attachment)
      .toMatchObject({ status: "attached", anchor: h.anchors[0] });
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_comment_events WHERE project_id=$1", [h.projectId],
    )).rows[0]?.n).toBe(1);
  });

  it("rejects corrupt checksums, replay corruption and mismatched document bindings instead of resetting", async () => {
    const h = await setup();
    await operation(h, h.owner, 0, create(h.anchors[0]!));
    const saved = await h.db.query<{ state_digest: string }>(
      "SELECT state_digest FROM stt_comment_heads WHERE project_id=$1", [h.projectId]);
    await h.db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [h.projectId, `sha256:${"0".repeat(64)}`]);
    await expect(h.comments.getComments(h.projectId, h.owner)).rejects.toMatchObject({ status: 503 });
    await h.db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [h.projectId, saved.rows[0]!.state_digest]);
    await h.db.query("UPDATE stt_comment_heads SET state_json='{}' WHERE project_id=$1", [h.projectId]);
    await expect(h.comments.getComments(h.projectId, h.owner)).rejects.toMatchObject({ status: 503 });
    await h.db.query("UPDATE stt_comment_heads SET state_digest=$2 WHERE project_id=$1",
      [h.projectId, sha256("{}")]);
    await expect(operation(h, h.owner, 1, create(h.anchors[1]!))).rejects.toMatchObject({ status: 503 });
    const other = await setup();
    await operation(other, other.owner, 0, create(other.anchors[0]!));
    await other.db.query("UPDATE stt_comment_heads SET document_revision=2 WHERE project_id=$1", [other.projectId]);
    await expect(other.comments.getComments(other.projectId, other.owner)).rejects.toMatchObject({ status: 503 });
  });

  it("rolls back head creation and event when a late SQL write fails", async () => {
    const h = await setup();
    const brokenPool: SqlPool = { connect: async () => ({
      query: async <T>(sql: string, params?: readonly unknown[]) => {
        if (sql.startsWith("INSERT INTO stt_comment_events")) throw new Error("synthetic storage failure");
        return await h.db.query<T>(sql, params === undefined ? undefined : [...params]);
      },
    } satisfies SqlClient) };
    const broken = new ProjectCommentService(brokenPool, new ProjectAuthorizationService(brokenPool));
    await expect(broken.applyOperation(h.projectId, h.owner, {
      expectedCommentRevision: 0, clientMutationId: id(), operation: create(h.anchors[0]!),
    } satisfies CommentMutationInput)).rejects.toMatchObject({ status: 503 });
    const rows = await h.db.query<{ heads: number; events: number }>(
      "SELECT (SELECT count(*)::integer FROM stt_comment_heads) AS heads," +
      "(SELECT count(*)::integer FROM stt_comment_events) AS events",
    );
    expect(rows.rows[0]).toEqual({ heads: 0, events: 0 });
  });

  it("stales anchors only through trusted document reconciliation, then permits explicit reattach", async () => {
    const h = await setup();
    const first = create(h.anchors[0]!);
    const initial = await operation(h, h.editor, 0, first);
    const revised = structuredClone(h.document);
    const narration = revised.activeDraft.blocks[0] as NarrationBlockV2;
    narration.text = "hello green world";
    narration.tokens[1]!.value = "green";
    narration.tokens[1]!.endOffset = 11;
    narration.tokens[2]!.startOffset = 12;
    narration.tokens[2]!.endOffset = 17;
    narration.version++;
    const changed = checkedDocument(revised, h.projectId);
    await h.db.query("BEGIN");
    try {
      await h.db.query("UPDATE stt_document_heads SET revision=1,document_json=$2,content_digest=$3 " +
        "WHERE project_id=$1", [h.projectId, changed.documentJson, changed.digest]);
      await reconcileCommentsForDocumentRevision(h.db, h.projectId, h.document, 0, revised, 1,
        h.owner.principalId);
      await h.db.query("COMMIT");
    } catch (error) {
      await h.db.query("ROLLBACK");
      throw error;
    }
    const stale = await h.comments.getComments(h.projectId, h.viewer);
    expect(stale.commentRevision).toBe(2);
    expect(stale.documentRevision).toBe(1);
    expect(stale.threads[0]?.attachment).toMatchObject({ status: "stale", quotedText: "blue world" });
    await expect(operation(h, h.editor, 2, { kind: "reattach", threadId: first.threadId,
      anchor: { kind: "block", blockId: id() } })).rejects.toMatchObject({ status: 400 });
    await operation(h, h.editor, 2, { kind: "reattach", threadId: first.threadId, anchor: h.anchors[0] });
    expect((await h.comments.getComments(h.projectId, h.viewer)).threads[0]?.attachment.status).toBe("attached");
    expect(await operation(h, h.editor, 0, first, initial.clientMutationId))
      .toEqual({ ...initial, duplicateDelivery: true });
    const events = await h.db.query<{ revision: string }>(
      "SELECT comment_revision::text AS revision FROM stt_comment_events ORDER BY comment_revision",
    );
    expect(events.rows.map(({ revision }) => revision)).toEqual(["1", "3"]);
  });

  it("keeps a failed trusted replacement and head write in one rollback boundary", async () => {
    const h = await setup();
    await operation(h, h.owner, 0, create(h.anchors[0]!));
    const revised = { ...h.document, title: "Revision without matching prior state" };
    const checked = checkedDocument(revised, h.projectId);
    await h.db.query("BEGIN");
    try {
      await h.db.query("UPDATE stt_document_heads SET revision=1,document_json=$2,content_digest=$3 " +
        "WHERE project_id=$1", [h.projectId, checked.documentJson, checked.digest]);
      await expect(reconcileCommentsForDocumentRevision(h.db, h.projectId, h.document, 99, revised, 100,
        h.owner.principalId)).rejects.toMatchObject({ status: 503 });
    } finally {
      await h.db.query("ROLLBACK");
    }
    expect((await h.service.getDocument(h.projectId, h.owner)).revision).toBe(0);
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(1);
  });

  it("advances a byte-identical document revision without inventing comment history", async () => {
    const h = await setup();
    const first = create(h.anchors[0]!);
    const receipt = await operation(h, h.editor, 0, first);
    const before = await h.db.query<{ state_digest: string }>(
      "SELECT state_digest FROM stt_comment_heads WHERE project_id=$1", [h.projectId]);
    await h.db.query("BEGIN");
    try {
      await h.db.query("UPDATE stt_document_heads SET revision=1 WHERE project_id=$1", [h.projectId]);
      await reconcileCommentsForDocumentRevision(h.db, h.projectId, h.document, 0, h.document, 1,
        h.owner.principalId);
      await h.db.query("COMMIT");
    } catch (error) {
      await h.db.query("ROLLBACK");
      throw error;
    }
    const after = await h.db.query<{ state_digest: string }>(
      "SELECT state_digest FROM stt_comment_heads WHERE project_id=$1", [h.projectId]);
    expect(after.rows[0]).toEqual(before.rows[0]);
    expect(await h.comments.getComments(h.projectId, h.editor)).toMatchObject({
      documentRevision: 1, commentRevision: 1,
    });
    expect(await operation(h, h.editor, 0, first, receipt.clientMutationId))
      .toEqual({ ...receipt, duplicateDelivery: true });
    await operation(h, h.owner, 1, reply(first.threadId));
    expect((await h.comments.getComments(h.projectId, h.owner)).commentRevision).toBe(2);
  });
});
