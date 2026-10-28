import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  applyCommentOperationV2,
  createCommentStateV2,
  deserializeCommentStateV2,
  serializeCommentStateV2,
  type CommentAnchorV2,
  type CommentOperationV2,
  type CommentStateV2,
} from "../src/authoring-v2-comments.js";
import { applyRowEditV2 } from "../src/authoring-v2-rows.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { resolveSortingCommentsV2 } from "../src/authoring-v2-sorting-comments.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const actorId = "sorting-comment-author";
function fixture() {
  const { document } = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
  const first = document.activeDraft.blocks[0] as NarrationBlockV2;
  first.text = "hello blue world";
  first.tokens = [
    { id: id(101), value: "hello", startOffset: 0, endOffset: 5 },
    { id: id(102), value: "blue", startOffset: 6, endOffset: 10 },
    { id: id(103), value: "world", startOffset: 11, endOffset: 16 },
  ];
  const second: NarrationBlockV2 = {
    ...structuredClone(first),
    id: id(200),
    orderKey: "b0",
    primaryVisualSequence: { id: id(203), version: 1, slots: [{
      id: id(204), kind: "content", version: 1, relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval",
    }] },
    text: "other row",
    tokens: [
      { id: id(201), value: "other", startOffset: 0, endOffset: 5 },
      { id: id(202), value: "row", startOffset: 6, endOffset: 9 },
    ],
  };
  document.activeDraft.blocks.push(second);
  const anchors: CommentAnchorV2[] = [
    { kind: "text", blockId: first.id, startTokenId: id(102), endTokenId: id(103) },
    { kind: "card", blockId: first.id, cardId: first.primaryVisualSequence!.slots[0]!.id },
    { kind: "block", blockId: second.id },
    { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id },
  ];
  return { document, first, second, anchors };
}

function apply(state: CommentStateV2, operation: CommentOperationV2): CommentStateV2 {
  const result = applyCommentOperationV2(state, state.revision, operation);
  if (!result.ok) throw new Error(result.error);
  return result.state;
}

function comments() {
  const data = fixture();
  let state = createCommentStateV2(data.document);
  data.anchors.forEach((anchor, index) => {
    state = apply(state, {
      id: `create-${index}`, actorId, kind: "create", threadId: `thread-${index}`, messageId: `message-${index}`,
      body: `Comment ${index}`, mentionActorIds: [], anchor,
    });
  });
  state = apply(state, { id: "reply", actorId: "reply-author", kind: "reply", threadId: "thread-0", messageId: "reply-0", body: "Keep this reply", mentionActorIds: [] });
  return { ...data, state };
}

function resolve(document: ScriptDocumentV2, intended: ScriptDocumentV2, state: CommentStateV2, id = "sorting-finalize") {
  return resolveSortingCommentsV2(document, intended, { state, id, actorId: "sorting-reviewer" });
}

describe("sorting comment reconciliation", () => {
  it("reconciles once against the accepted document and preserves replies and serialized history", () => {
    const { document, second, state } = comments();
    const accepted = structuredClone(document);
    accepted.activeDraft.blocks = accepted.activeDraft.blocks.filter((block) => block.id !== second.id);

    const result = resolve(document, accepted, state);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.state.document).toEqual(accepted);
    expect(result.state.threads.map((thread) => [thread.id, thread.attachment.anchor.kind, thread.attachment.status])).toEqual([
      ["thread-0", "text", "attached"],
      ["thread-1", "card", "attached"],
      ["thread-2", "block", "stale"],
      ["thread-3", "between_blocks", "stale"],
    ]);
    expect(result.state.threads[0]!.messages.map((message) => [message.id, message.actorId, message.body])).toEqual([
      ["message-0", actorId, "Comment 0"], ["reply-0", "reply-author", "Keep this reply"],
    ]);
    expect(result.state.history.filter((operation) => operation.kind === "replace_document")).toEqual([{
      id: "sorting-finalize", actorId: "sorting-reviewer", kind: "replace_document", document: accepted,
    }]);
    expect(deserializeCommentStateV2(serializeCommentStateV2(result.state))).toEqual(result.state);
    expect(state.document).toEqual(document);
  });

  it("keeps exact anchors through a row move and stales only a rewritten text range", () => {
    const moved = comments();
    const move = applyRowEditV2(moved.document, 0, {
      kind: "move_rows", rowIds: [moved.first.id], destination: { sectionId: null, afterRowId: moved.second.id, beforeRowId: null },
    });
    expect(move.ok).toBe(true);
    if (!move.ok) return;
    const movedResult = resolve(moved.document, move.document, moved.state, "sorting-move");
    expect(movedResult.ok).toBe(true);
    if (!movedResult.ok) return;
    expect(movedResult.state.threads.map((thread) => thread.attachment.status)).toEqual(["attached", "attached", "attached", "stale"]);
    expect(movedResult.state.threads.map((thread) => thread.attachment.anchor)).toEqual(moved.anchors);

    const rewritten = comments();
    const intended = structuredClone(rewritten.document);
    const row = intended.activeDraft.blocks[0] as NarrationBlockV2;
    row.text = "hello pink world";
    row.tokens[1]!.value = "pink";
    row.version++;
    const rewrittenResult = resolve(rewritten.document, intended, rewritten.state, "sorting-rewrite");
    expect(rewrittenResult.ok).toBe(true);
    if (!rewrittenResult.ok) return;
    expect(rewrittenResult.state.threads.map((thread) => thread.attachment.status)).toEqual(["stale", "attached", "attached", "attached"]);
    expect(rewrittenResult.state.threads.map((thread) => thread.attachment.anchor)).toEqual(rewritten.anchors);
  });

  it("leaves comments untouched for discard and rejects mismatched or invalid reconciliation atomically", () => {
    const { document, state } = comments();
    const discarded = resolve(document, structuredClone(document), state);
    expect(discarded).toEqual({ ok: true, state });
    expect(state.revision).toBe(5);
    expect(state.history).toHaveLength(5);

    const differentCanonical = structuredClone(document);
    (differentCanonical.activeDraft.blocks[0] as NarrationBlockV2).version++;
    const mismatch = resolve(differentCanonical, document, state);
    expect(mismatch.ok).toBe(false);
    expect(mismatch.state).toBe(state);
    expect(state.revision).toBe(5);

    const changed = structuredClone(document);
    (changed.activeDraft.blocks[0] as NarrationBlockV2).version++;
    const duplicateOperation = resolve(document, changed, state, "create-0");
    expect(duplicateOperation.ok).toBe(false);
    expect(duplicateOperation.state).toBe(state);
    expect(state.history).toHaveLength(5);

    const corrupted = structuredClone(state);
    corrupted.threads[0]!.resolved = true;
    const invalid = resolve(document, changed, corrupted);
    expect(invalid.ok).toBe(false);
    expect(invalid.state).toBe(corrupted);
    expect(corrupted.threads[0]!.resolved).toBe(true);

    const missingContext = resolveSortingCommentsV2(document, document, null as never);
    expect(missingContext.ok).toBe(false);
    expect(missingContext.state.document).toEqual(document);
  });
});
