import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  applyCommentOperationV2, createCommentStateV2, serializeCommentStateV2, deserializeCommentStateV2,
  applyRowEditV2, createRowEditSessionV2, validateScriptDocumentV2,
  type CommentAnchorV2, type CommentOperationV2, type CommentStateV2,
} from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const actorId = "synthetic-actor-matthew";
function fixture() {
  const { document } = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
  const first = document.activeDraft.blocks[0] as NarrationBlockV2;
  first.text = "hello blue world";
  first.tokens = [
    { id: id(101), value: "hello", startOffset: 0, endOffset: 5 },
    { id: id(102), value: "blue", startOffset: 6, endOffset: 10 },
    { id: id(103), value: "world", startOffset: 11, endOffset: 16 },
  ];
  const second: NarrationBlockV2 = { ...structuredClone(first), id: id(200), orderKey: "b0", primaryVisualSequence: { id: id(203), version: 1, slots: [{
    id: id(204), kind: "content", version: 1, relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
    payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval",
  }] },
    text: "other row", tokens: [
      { id: id(201), value: "other", startOffset: 0, endOffset: 5 },
      { id: id(202), value: "row", startOffset: 6, endOffset: 9 },
    ] };
  document.activeDraft.blocks.push(second);
  expect(validateScriptDocumentV2(document).valid).toBe(true);
  const anchors: CommentAnchorV2[] = [
    { kind: "text", blockId: first.id, startTokenId: id(102), endTokenId: id(103) },
    { kind: "card", blockId: first.id, cardId: first.primaryVisualSequence!.slots[0]!.id },
    { kind: "block", blockId: second.id },
    { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id },
  ];
  return { document, first, second, anchors };
}
function apply(state: CommentStateV2, op: CommentOperationV2) {
  const result = applyCommentOperationV2(state, state.revision, op);
  if (!result.ok) throw new Error(result.error);
  return result.state;
}
const create = (anchor: CommentAnchorV2, n: number): Extract<CommentOperationV2, { kind: "create" }> => ({
  id: `create-${n}`, actorId, kind: "create", threadId: `thread-${n}`, messageId: `message-${n}`,
  body: "Review this synthetic wording", mentionActorIds: [actorId], anchor,
});

describe("bounded sequential S03 comments", () => {
  it("attributes create/reply/resolve/reopen on all four anchor kinds and round trips exact history", () => {
    const { document, anchors } = fixture();
    let state = createCommentStateV2(document);
    anchors.forEach((anchor, n) => { state = apply(state, create(anchor, n)); });
    state = apply(state, { id: "reply", actorId, kind: "reply", threadId: "thread-0", messageId: "reply-0", body: "Reply", mentionActorIds: [actorId] });
    state = apply(state, { id: "resolve", actorId, kind: "resolve", threadId: "thread-0" });
    expect(state.threads[0]!.resolved).toBe(true);
    state = apply(state, { id: "reopen", actorId, kind: "reopen", threadId: "thread-0" });
    expect(state.threads[0]!.resolved).toBe(false);
    expect(state.threads[0]!.messages.map((message) => [message.id, message.actorId, message.mentionActorIds])).toEqual([
      ["message-0", actorId, [actorId]], ["reply-0", actorId, [actorId]],
    ]);
    expect(state.threads.map((thread) => thread.attachment.status)).toEqual(Array<string>(4).fill("attached"));
    expect(state.history.every((op) => op.actorId === actorId)).toBe(true);
    expect(state.document).toEqual(document);
    expect(deserializeCommentStateV2(serializeCommentStateV2(state))).toEqual(state);
    expect(document).toEqual(createCommentStateV2(document).document);
  });

  it("keeps stable range/card/block IDs through text edits and a real whole-row move, but stales a broken gap", () => {
    const { document, first, second, anchors } = fixture();
    let state = createCommentStateV2(document);
    anchors.forEach((anchor, n) => { state = apply(state, create(anchor, n)); });
    const edited = structuredClone(state.document);
    const row = edited.activeDraft.blocks[0] as NarrationBlockV2;
    row.text = "Greetings blue world";
    row.tokens[0]!.value = "Greetings";
    row.tokens[0]!.endOffset = 9;
    row.tokens[1]!.startOffset += 4;
    row.tokens[1]!.endOffset += 4;
    row.tokens[2]!.startOffset += 4;
    row.tokens[2]!.endOffset += 4;
    row.version++;
    state = apply(state, { id: "text-edit", actorId, kind: "replace_document", document: edited });
    expect(state.threads[0]!.attachment.quotedText).toBe("blue world");
    expect(state.threads.every((thread) => thread.attachment.status === "attached")).toBe(true);
    const moved = applyRowEditV2(state.document, 0, { kind: "move_rows", rowIds: [first.id], destination: { sectionId: null, afterRowId: second.id, beforeRowId: null } });
    expect(moved.ok).toBe(true);
    state = apply(state, { id: "row-move", actorId, kind: "replace_document", document: moved.document });
    expect(state.document.activeDraft.blocks.map((row) => row.id)).toEqual([second.id, first.id]);
    expect(state.threads.map((thread) => [thread.id, thread.attachment.status])).toEqual([
      ["thread-0", "attached"], ["thread-1", "attached"], ["thread-2", "attached"], ["thread-3", "stale"],
    ]);
    expect(state.threads.map((thread) => thread.attachment.anchor)).toEqual(anchors);
    const restored = applyRowEditV2(state.document, 1, { kind: "move_rows", rowIds: [second.id], destination: { sectionId: null, afterRowId: first.id, beforeRowId: null } });
    expect(restored.ok).toBe(true);
    state = apply(state, { id: "row-move-back", actorId, kind: "replace_document", document: restored.document });
    expect(state.threads[3]!.attachment.status).toBe("stale");
    state = apply(state, { id: "gap-reattach", actorId, kind: "reattach", threadId: "thread-3", anchor: anchors[3]! });
    expect(state.threads[3]!.attachment.status).toBe("attached");
    expect(deserializeCommentStateV2(serializeCommentStateV2(state))).toEqual(state);
  });

  it("never guesses after deletion or token replacement even when identical quoted words return", () => {
    const { document, first, anchors } = fixture();
    let state = apply(createCommentStateV2(document), create(anchors[0]!, 0));
    const deleted = structuredClone(document);
    const row = deleted.activeDraft.blocks[0] as NarrationBlockV2;
    row.text = "hello world";
    row.tokens.splice(1, 1);
    row.tokens[1]!.startOffset = 6;
    row.tokens[1]!.endOffset = 11;
    row.version++;
    state = apply(state, { id: "delete", actorId, kind: "replace_document", document: deleted });
    expect(state.threads[0]!.attachment.status).toBe("stale");
    expect(state.threads[0]!.attachment.quotedText).toBe("blue world");
    state = deserializeCommentStateV2(serializeCommentStateV2(state));
    state = apply(state, { id: "restore-identities", actorId, kind: "replace_document", document });
    expect(state.threads[0]!.attachment.status).toBe("stale");
    const restored = structuredClone(document);
    const restoredRow = restored.activeDraft.blocks[0] as NarrationBlockV2;
    restoredRow.tokens[1]!.id = id(999);
    state = apply(state, { id: "restore-words", actorId, kind: "replace_document", document: restored });
    expect(state.threads[0]!.attachment.status).toBe("stale");
    state = apply(state, { id: "explicit", actorId, kind: "reattach", threadId: "thread-0", anchor: { kind: "text", blockId: first.id, startTokenId: id(999), endTokenId: id(103) } });
    expect(state.threads[0]!.attachment.status).toBe("attached");
    expect(state.threads[0]!.id).toBe("thread-0");
    expect(state.threads[0]!.messages[0]!.id).toBe("message-0");
  });

  it("explicit Undo restores only newly orphaned comments, never an already stale lookalike", () => {
    const { document, first, anchors } = fixture();
    const session = createRowEditSessionV2(document);
    let state = apply(createCommentStateV2(document), create(anchors[0]!, 0));
    const deletion = (editId: string) => session.apply({
      kind: "edit_narration_text", rowId: first.id,
      startOffset: 6, endOffset: 11, insertedText: "", editId,
    });
    const deletedBefore = deletion(id(700));
    expect(deletedBefore.ok).toBe(true);
    state = apply(state, { id: "earlier-delete", actorId, kind: "replace_document", document: deletedBefore.document });
    expect(state.threads[0]!.attachment).toMatchObject({ status: "stale", orphanedByDocumentOperationId: "earlier-delete" });

    const restoredBefore = session.undo();
    expect(restoredBefore.ok).toBe(true);
    state = apply(state, { id: "ordinary-restore", actorId, kind: "replace_document", document: restoredBefore.document });
    expect(state.threads[0]!.attachment.status).toBe("stale");
    expect(state.threads[0]!.attachment.orphanedByDocumentOperationId).toBeUndefined();
    state = apply(state, create(anchors[0]!, 1));

    const deletedAgain = deletion(id(701));
    expect(deletedAgain.ok).toBe(true);
    state = apply(state, { id: "latest-delete", actorId, kind: "replace_document", document: deletedAgain.document });
    expect(state.threads.map((thread) => thread.attachment.status)).toEqual(["stale", "stale"]);
    expect(state.threads[1]!.attachment.orphanedByDocumentOperationId).toBe("latest-delete");
    const originalEvidence = structuredClone(state.threads[1]!.attachment);
    const savedAfterDelete = deserializeCommentStateV2(serializeCommentStateV2(state));
    expect(savedAfterDelete).toEqual(state);

    const undone = session.undo();
    expect(undone.ok).toBe(true);
    const undo = { id: "verified-undo", actorId, kind: "undo_document" as const,
      undoOfOperationId: "latest-delete", document: undone.document };
    expect(applyCommentOperationV2(state, state.revision,
      { ...undo, undoOfOperationId: "earlier-delete" }).state).toBe(state);
    state = apply(state, undo);
    expect(state.threads[0]!.attachment.status).toBe("stale");
    expect(state.threads[1]!.attachment).toMatchObject({
      status: "attached", anchor: originalEvidence.anchor,
      tokens: originalEvidence.tokens, quotedText: originalEvidence.quotedText,
    });
    expect(state.threads[1]!.attachment).not.toHaveProperty("orphanedByDocumentOperationId");
    expect(state.threads[1]!.messages).toEqual(savedAfterDelete.threads[1]!.messages);
    expect(deserializeCommentStateV2(serializeCommentStateV2(state))).toEqual(state);
  });

  it("refuses forged, stale and replayed Undo claims without changing any comment history", () => {
    const { document, first, anchors } = fixture();
    const session = createRowEditSessionV2(document);
    let state = apply(createCommentStateV2(document), create(anchors[0]!, 0));
    const edited = session.apply({ kind: "edit_narration_text", rowId: first.id,
      startOffset: 6, endOffset: 11, insertedText: "", editId: id(710) });
    expect(edited.ok).toBe(true);
    state = apply(state, { id: "edit-to-undo", actorId, kind: "replace_document", document: edited.document });
    const restored = session.undo();
    expect(restored.ok).toBe(true);
    const correct = { id: "undo", actorId, kind: "undo_document" as const,
      undoOfOperationId: "edit-to-undo", document: restored.document };
    const alteredText = structuredClone(restored.document);
    (alteredText.activeDraft.blocks[0] as NarrationBlockV2).notes.push("forged modification");
    const wrongRevision = { ...restored.document, rowEditRevision: edited.document.rowEditRevision };
    const invalid = [
      { ...correct, undoOfOperationId: "unrelated" },
      { ...correct, undoOfOperationId: "" },
      { ...correct, document: alteredText },
      { ...correct, document: wrongRevision },
      { ...correct, actorId: "" },
      { ...correct, extra: true },
    ];
    for (const forged of invalid) {
      const result = applyCommentOperationV2(state, state.revision, forged as typeof correct);
      expect(result).toMatchObject({ ok: false, state });
      expect(result.state).toBe(state);
    }
    expect(applyCommentOperationV2(state, state.revision - 1, correct).ok).toBe(false);
    const snapshot = structuredClone(state);
    expect(state).toEqual(snapshot);
    const successful = apply(state, correct);
    expect(successful.threads[0]!.attachment.status).toBe("attached");
    expect(applyCommentOperationV2(successful, successful.revision, { ...correct, id: "second-undo" }).state).toBe(successful);
    const serialized = JSON.parse(serializeCommentStateV2(successful)) as { operations: CommentOperationV2[] };
    const last = serialized.operations.at(-1)!;
    if (last.kind !== "undo_document") throw new Error("Expected Undo record");
    last.undoOfOperationId = "forged";
    expect(() => deserializeCommentStateV2(JSON.stringify(serialized))).toThrow(/Undo does not match/);
    expect(deserializeCommentStateV2(serializeCommentStateV2(successful))).toEqual(successful);
  });

  it("stales rewritten interior tokens, missing cards and missing blocks, preserving their old evidence", () => {
    const { document, first, anchors } = fixture();
    let state = createCommentStateV2(document);
    const range: CommentAnchorV2 = { kind: "text", blockId: first.id, startTokenId: id(101), endTokenId: id(103) };
    [range, anchors[1]!, anchors[2]!].forEach((anchor, n) => { state = apply(state, create(anchor, n)); });
    const changed = structuredClone(document);
    const row = changed.activeDraft.blocks[0] as NarrationBlockV2;
    row.text = "hello pink world";
    row.tokens[1]!.value = "pink";
    row.primaryVisualSequence!.slots[0]!.id = id(998);
    changed.activeDraft.blocks.pop();
    state = apply(state, { id: "rewrite", actorId, kind: "replace_document", document: changed });
    expect(state.threads.map((thread) => thread.attachment.status)).toEqual(["stale", "stale", "stale"]);
    expect(state.threads[0]!.attachment.quotedText).toBe("hello blue world");
  });

  it("refuses stale, duplicate, repeated and missing-target operations without touching content or history", () => {
    const { document, first, anchors } = fixture();
    const state = apply(createCommentStateV2(document), create(anchors[0]!, 0));
    const snapshot = structuredClone(state);
    const reply: CommentOperationV2 = { id: "reply", actorId, kind: "reply", threadId: "thread-0", messageId: "reply", body: "Reply", mentionActorIds: [] };
    const invalid: CommentOperationV2[] = [
      create(anchors[0]!, 0),
      { ...create(anchors[0]!, 0), id: "duplicate-thread", messageId: "new" },
      { ...reply, messageId: "message-0" },
      { ...reply, threadId: "absent" },
      create({ kind: "block", blockId: id(9999) }, 1),
      create({ kind: "card", blockId: first.id, cardId: id(9999) }, 1),
      create({ kind: "text", blockId: first.id, startTokenId: id(103), endTokenId: id(102) }, 1),
      create({ kind: "between_blocks", afterBlockId: first.id, beforeBlockId: first.id }, 1),
      { id: "reopen", actorId, kind: "reopen", threadId: "thread-0" },
      { id: "reattach", actorId, kind: "reattach", threadId: "thread-0", anchor: anchors[0]! },
      { id: "no-change", actorId, kind: "replace_document", document },
      { id: "wrong-document", actorId, kind: "replace_document", document: { ...document, id: id(9999) } },
      { ...reply, mentionActorIds: [actorId, actorId] },
      { ...reply, mentionActorIds: Array<string>(1) },
      { ...reply, actorId: "" },
    ];
    invalid.forEach((operation) => {
      const result = applyCommentOperationV2(state, state.revision, operation);
      expect(result.ok).toBe(false);
      expect(result.state).toBe(state);
      expect(state).toEqual(snapshot);
    });
    expect(applyCommentOperationV2(state, 0, reply)).toMatchObject({ ok: false, state });
    let next = apply(state, reply);
    expect(applyCommentOperationV2(next, next.revision, reply).ok).toBe(false);
    next = apply(next, { id: "resolved", actorId, kind: "resolve", threadId: "thread-0" });
    expect(applyCommentOperationV2(next, next.revision, { id: "resolved-again", actorId, kind: "resolve", threadId: "thread-0" }).state).toBe(next);
    const missing = structuredClone(document);
    (missing.activeDraft.blocks[0] as NarrationBlockV2).tokens[1]!.id = id(999);
    next = apply(next, { id: "stale-target", actorId, kind: "replace_document", document: missing });
    const reattach = applyCommentOperationV2(next, next.revision, { id: "missing-reattach", actorId, kind: "reattach", threadId: "thread-0", anchor: anchors[0]! });
    expect(reattach.ok).toBe(false);
    expect(reattach.state).toBe(next);
  });

  it("rejects malformed or tampered save data rather than accepting partial history", () => {
    const { document, anchors } = fixture();
    const state = apply(createCommentStateV2(document), create(anchors[0]!, 0));
    const saved = serializeCommentStateV2(state);
    expect(() => deserializeCommentStateV2(saved.replace('"kind":"create"', '"kind":"unknown"'))).toThrow();
    expect(() => deserializeCommentStateV2(saved.replace('"actorId":"synthetic-actor-matthew"', '"actorId":""'))).toThrow();
    expect(() => serializeCommentStateV2({ ...state, revision: 99 })).toThrow();
    expect(() => deserializeCommentStateV2("null")).toThrow();
  });
});
