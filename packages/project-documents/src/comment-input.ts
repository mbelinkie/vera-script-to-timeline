import type { CommentAnchorV2, CommentOperationV2 } from "@vera/contracts/authoring-v2";

import { ProjectDocumentInputError, requireObject, requireUuid } from "./model.js";

/** Internal replace_document is never a client-writable operation. */
export type PublicCommentOperation = Exclude<CommentOperationV2, { kind: "replace_document" }>;

export const MAX_COMMENT_BODY_BYTES = 20_000;
export const MAX_COMMENT_MENTIONS = 25;

const SHAPES = {
  create: ["kind", "threadId", "messageId", "body", "mentionActorIds", "anchor"],
  reply: ["kind", "threadId", "messageId", "body", "mentionActorIds"],
  resolve: ["kind", "threadId"],
  reopen: ["kind", "threadId"],
  reattach: ["kind", "threadId", "anchor"],
} as const;

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): void {
  if (Object.keys(value).length !== keys.length ||
      keys.some((key) => !Object.hasOwn(value, key))) {
    throw new ProjectDocumentInputError("Unsupported comment operation fields.");
  }
}

function trustedAnchor(raw: unknown): CommentAnchorV2 {
  const anchor = requireObject(raw);
  switch (anchor.kind) {
    case "text":
      exactKeys(anchor, ["kind", "blockId", "startTokenId", "endTokenId"]);
      return { kind: "text", blockId: requireUuid(anchor.blockId),
        startTokenId: requireUuid(anchor.startTokenId), endTokenId: requireUuid(anchor.endTokenId) };
    case "card":
      exactKeys(anchor, ["kind", "blockId", "cardId"]);
      return { kind: "card", blockId: requireUuid(anchor.blockId), cardId: requireUuid(anchor.cardId) };
    case "block":
      exactKeys(anchor, ["kind", "blockId"]);
      return { kind: "block", blockId: requireUuid(anchor.blockId) };
    case "between_blocks":
      exactKeys(anchor, ["kind", "afterBlockId", "beforeBlockId"]);
      return { kind: "between_blocks", afterBlockId: requireUuid(anchor.afterBlockId),
        beforeBlockId: requireUuid(anchor.beforeBlockId) };
    default:
      throw new ProjectDocumentInputError("Unsupported comment anchor kind.");
  }
}

/**
 * Build the internal operation from trusted identity and a server-selected
 * mutation ID. Client-supplied IDs are allowed only for thread/message/anchor.
 * Target existence and same-project active mentions are verified in the
 * authorized SQL transaction, not at this parsing boundary.
 */
export function trustedCommentOperation(
  trustedActorId: string, clientMutationId: string, raw: unknown,
): PublicCommentOperation {
  const actorId = requireUuid(trustedActorId);
  const id = requireUuid(clientMutationId);
  const input = requireObject(raw);
  const kind = input.kind;
  if (typeof kind !== "string" || !Object.hasOwn(SHAPES, kind)) {
    throw new ProjectDocumentInputError("Unsupported comment operation kind.");
  }
  const shape = SHAPES[kind as keyof typeof SHAPES];
  exactKeys(input, shape);
  const threadId = requireUuid(input.threadId);

  if (kind === "resolve") return { kind, id, actorId, threadId };
  if (kind === "reopen") return { kind, id, actorId, threadId };
  if (kind === "reattach") {
    return { kind, id, actorId, threadId, anchor: trustedAnchor(input.anchor) };
  }

  const messageId = requireUuid(input.messageId);
  if (typeof input.body !== "string" || !input.body.trim() ||
      Buffer.byteLength(input.body, "utf8") > MAX_COMMENT_BODY_BYTES) {
    throw new ProjectDocumentInputError("Invalid comment message body.");
  }
  if (!Array.isArray(input.mentionActorIds) || input.mentionActorIds.length > MAX_COMMENT_MENTIONS) {
    throw new ProjectDocumentInputError("Invalid comment mentions.");
  }
  const mentionActorIds: string[] = [];
  for (const mention of input.mentionActorIds) mentionActorIds.push(requireUuid(mention));
  if (new Set(mentionActorIds).size !== mentionActorIds.length) {
    throw new ProjectDocumentInputError("Duplicate comment mentions.");
  }
  const message = { id, actorId, threadId, messageId, body: input.body, mentionActorIds };
  if (kind === "reply") return { ...message, kind };
  if (kind === "create") return { ...message, kind, anchor: trustedAnchor(input.anchor) };
  throw new ProjectDocumentInputError("Unsupported comment operation kind.");
}
