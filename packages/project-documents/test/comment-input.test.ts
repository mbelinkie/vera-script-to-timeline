import { randomUUID } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  MAX_COMMENT_BODY_BYTES, MAX_COMMENT_MENTIONS, trustedCommentOperation,
} from "../src/comment-input.js";

const ids = () => ({ actor: randomUUID(), mutation: randomUUID(), thread: randomUUID(), message: randomUUID() });
const anchors = () => [
  { kind: "text", blockId: randomUUID(), startTokenId: randomUUID(), endTokenId: randomUUID() },
  { kind: "card", blockId: randomUUID(), cardId: randomUUID() },
  { kind: "block", blockId: randomUUID() },
  { kind: "between_blocks", afterBlockId: randomUUID(), beforeBlockId: randomUUID() },
] as const;

describe("trusted client comment operations", () => {
  it("stamps trusted identity and only accepts five exact public operation shapes", () => {
    const { actor, mutation, thread, message } = ids();
    for (const anchor of anchors()) {
      const op = trustedCommentOperation(actor, mutation, {
        kind: "create", threadId: thread, messageId: message, body: "unchanged \n body",
        mentionActorIds: [actor], anchor,
      });
      expect(op).toEqual({ kind: "create", id: mutation, actorId: actor,
        threadId: thread, messageId: message, body: "unchanged \n body", mentionActorIds: [actor], anchor });
      const reattach = trustedCommentOperation(actor, mutation, { kind: "reattach", threadId: thread, anchor });
      expect(reattach).toEqual({ kind: "reattach", id: mutation, actorId: actor, threadId: thread, anchor });
    }
    expect(trustedCommentOperation(actor, mutation, {
      kind: "reply", threadId: thread, messageId: message, body: "answer", mentionActorIds: [],
    })).toEqual({ kind: "reply", id: mutation, actorId: actor,
      threadId: thread, messageId: message, body: "answer", mentionActorIds: [] });
    for (const kind of ["resolve", "reopen"]) {
      expect(trustedCommentOperation(actor, mutation, { kind, threadId: thread })).toEqual({
        kind, id: mutation, actorId: actor, threadId: thread,
      });
    }
  });

  it("rejects forged attribution, internal replacements, missing and extra fields", () => {
    const { actor, mutation, thread, message } = ids();
    const reply = { kind: "reply", threadId: thread, messageId: message, body: "x", mentionActorIds: [] };
    for (const raw of [
      { ...reply, actorId: randomUUID() }, { ...reply, id: mutation },
      { ...reply, clientMutationId: mutation }, { ...reply, role: "producer" },
      { ...reply, document: {} }, { ...reply, messageId: undefined },
      { kind: "replace_document", document: {} },
      { kind: "resolve", threadId: thread, body: "not allowed" },
      { kind: "reattach", threadId: thread },
      { kind: "delete", threadId: thread }, null, [], "reply",
    ]) {
      expect(() => trustedCommentOperation(actor, mutation, raw)).toThrow();
    }
    expect(() => trustedCommentOperation("actor-from-header", mutation, reply)).toThrow();
    expect(() => trustedCommentOperation(actor, "mutation-not-uuid", reply)).toThrow();
    expect(() => trustedCommentOperation(actor, mutation, { ...reply, threadId: "not-a-uuid" })).toThrow();
  });

  it("validates exact anchor fields and UUID identities without guessing targets", () => {
    const { actor, mutation, thread, message } = ids();
    const base = { kind: "create", threadId: thread, messageId: message, body: "x", mentionActorIds: [] };
    const [text, card, block, between] = anchors();
    const invalid = [
      { ...text, unexpected: "field" }, { ...card, cardId: "invalid" },
      { ...block, blockId: "" }, { ...between, afterBlockId: null },
      { kind: "text", blockId: randomUUID(), startTokenId: randomUUID() },
      { kind: "unknown", blockId: randomUUID() }, [], null,
    ];
    for (const anchor of invalid) {
      expect(() => trustedCommentOperation(actor, mutation, { ...base, anchor })).toThrow();
      expect(() => trustedCommentOperation(actor, mutation, { kind: "reattach", threadId: thread, anchor })).toThrow();
    }
  });

  it("bounds UTF-8 body size, nonblank text, and normalized distinct mention IDs", () => {
    const { actor, mutation, thread, message } = ids();
    const base = { kind: "reply", threadId: thread, messageId: message, body: "hello", mentionActorIds: [] };
    expect(trustedCommentOperation(actor, mutation, { ...base, body: "x".repeat(MAX_COMMENT_BODY_BYTES) }).kind).toBe("reply");
    const validMention = randomUUID();
    const normalized = trustedCommentOperation(actor.toUpperCase(), mutation.toUpperCase(), {
      ...base, mentionActorIds: [validMention.toUpperCase()],
    });
    expect(normalized.actorId).toBe(actor);
    expect(normalized.id).toBe(mutation);
    expect(normalized).toMatchObject({ mentionActorIds: [validMention] });
    for (const raw of [
      { ...base, body: "  \t" }, { ...base, body: "" },
      { ...base, body: "🌿".repeat(5_001) },
      { ...base, mentionActorIds: [validMention, validMention.toUpperCase()] },
      { ...base, mentionActorIds: ["not-a-uuid"] },
      { ...base, mentionActorIds: Array.from({ length: MAX_COMMENT_MENTIONS + 1 }, randomUUID) },
      { ...base, mentionActorIds: [null] }, { ...base, mentionActorIds: "actor" },
      { ...base, mentionActorIds: Array<string>(1) },
    ]) {
      expect(() => trustedCommentOperation(actor, mutation, raw)).toThrow();
    }
  });
});
