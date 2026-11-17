import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import { deserializeAuthoringDocumentV2, serializeAuthoringDocumentV2 } from "./authoring-v2-rows.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { commentQuoteV2 } from "./authoring-v2-stage-directions.js";

export type CommentAnchorV2 =
  | { kind: "text"; blockId: string; startTokenId: string; endTokenId: string }
  | { kind: "card"; blockId: string; cardId: string }
  | { kind: "block"; blockId: string }
  | { kind: "between_blocks"; afterBlockId: string; beforeBlockId: string };
export interface CommentMessageV2 {
  id: string; actorId: string; body: string; mentionActorIds: string[];
}
export interface CommentAttachmentV2 {
  anchor: CommentAnchorV2;
  status: "attached" | "stale";
  /** Exact semantic evidence, never a search query for automatic repair. */
  tokens: { id: string; value: string }[];
  quotedText: string | null;
  /** Replay-derived provenance for a single document edit, not an auto-repair hint. */
  orphanedByDocumentOperationId?: string;
}
export interface CommentThreadV2 {
  id: string; attachment: CommentAttachmentV2; resolved: boolean; messages: CommentMessageV2[];
}
type Attribution = { id: string; actorId: string };
type MessageInput = { messageId: string; body: string; mentionActorIds: string[] };
export type CommentOperationV2 = Attribution & (
  | ({ kind: "create"; threadId: string; anchor: CommentAnchorV2 } & MessageInput)
  | ({ kind: "reply"; threadId: string } & MessageInput)
  | { kind: "resolve"; threadId: string }
  | { kind: "reopen"; threadId: string }
  | { kind: "reattach"; threadId: string; anchor: CommentAnchorV2 }
  | { kind: "replace_document"; document: ScriptDocumentV2 }
  | { kind: "undo_document"; document: ScriptDocumentV2; undoOfOperationId: string }
);
export interface CommentStateV2 {
  initialDocument: ScriptDocumentV2;
  document: ScriptDocumentV2;
  revision: number;
  threads: CommentThreadV2[];
  history: CommentOperationV2[];
}
export type CommentResultV2 = { ok: true; state: CommentStateV2 } | { ok: false; state: CommentStateV2; error: string };

const nonempty = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Expected an object.");
  return value as Record<string, unknown>;
}
function fields(value: Record<string, unknown>, names: string) {
  if (!sameAuthoringJsonV2(Object.keys(value).sort(), names.split(" ").sort())) throw new Error("Unsupported operation fields.");
}
function anchorInput(value: unknown): CommentAnchorV2 {
  const anchor = record(value);
  const names = anchor.kind === "text" ? "kind blockId startTokenId endTokenId"
    : anchor.kind === "card" ? "kind blockId cardId"
      : anchor.kind === "block" ? "kind blockId"
        : anchor.kind === "between_blocks" ? "kind afterBlockId beforeBlockId" : "";
  if (!names) throw new Error("Unsupported anchor kind.");
  fields(anchor, names);
  if (!Object.values(anchor).every(nonempty)) throw new Error("Anchor identities must be nonempty.");
  return anchor as unknown as CommentAnchorV2;
}
function operationInput(value: unknown): CommentOperationV2 {
  const op = record(value);
  const names = op.kind === "create" ? "id actorId kind threadId anchor messageId body mentionActorIds"
    : op.kind === "reply" ? "id actorId kind threadId messageId body mentionActorIds"
      : op.kind === "resolve" || op.kind === "reopen" ? "id actorId kind threadId"
        : op.kind === "reattach" ? "id actorId kind threadId anchor"
          : op.kind === "replace_document" ? "id actorId kind document"
            : op.kind === "undo_document" ? "id actorId kind document undoOfOperationId" : "";
  if (!names) throw new Error("Unsupported comment operation.");
  fields(op, names);
  for (const key of ["id", "actorId", "threadId", "messageId", "body", "undoOfOperationId"]) {
    if (key in op && !nonempty(op[key])) throw new Error(`${key} must be nonempty.`);
  }
  if ("anchor" in op) anchorInput(op.anchor);
  if ("mentionActorIds" in op && (!Array.isArray(op.mentionActorIds) || !Array.from(op.mentionActorIds).every(nonempty) || new Set(op.mentionActorIds).size !== op.mentionActorIds.length)) throw new Error("Mentions must be distinct stable actor IDs.");
  return op as unknown as CommentOperationV2;
}

function attachment(document: ScriptDocumentV2, anchor: CommentAnchorV2): CommentAttachmentV2 | null {
  const blocks = document.activeDraft.blocks;
  if (anchor.kind === "between_blocks") {
    const index = blocks.findIndex((block) => block.id === anchor.afterBlockId);
    if (index < 0 || blocks[index + 1]?.id !== anchor.beforeBlockId) return null;
    return { anchor: structuredClone(anchor), status: "attached", tokens: [], quotedText: null };
  }
  const block = blocks.find((block) => block.id === anchor.blockId);
  if (!block) return null;
  if (anchor.kind === "text") {
    if (block.type !== "narration") return null;
    const start = block.tokens.findIndex((token) => token.id === anchor.startTokenId);
    const end = block.tokens.findIndex((token) => token.id === anchor.endTokenId);
    if (start < 0 || end < start) return null;
    const tokens = block.tokens.slice(start, end + 1);
    if (tokens.some((token, index) => !Number.isSafeInteger(token.startOffset) || !Number.isSafeInteger(token.endOffset) || token.startOffset < 0 || token.endOffset <= token.startOffset || token.endOffset > block.text.length || block.text.slice(token.startOffset, token.endOffset) !== token.value || index > 0 && token.startOffset < tokens[index - 1]!.endOffset)) return null;
    return { anchor: structuredClone(anchor), status: "attached", tokens: tokens.map(({ id, value }) => ({ id, value })), quotedText: commentQuoteV2(block, tokens[0]!.startOffset, tokens.at(-1)!.endOffset) };
  }
  if (anchor.kind === "card") {
    const exists = block.type === "narration" ? (
      block.primaryVisualSequence?.slots.some((slot) => slot.kind === "content" && slot.id === anchor.cardId) ||
      block.unattachedVisuals?.some((visual) => visual.slotId === anchor.cardId)
    ) : block.type === "visual_only" && (block.payload.payloadId === anchor.cardId ||
      block.additionalVisuals?.some((visual) => visual.payload.payloadId === anchor.cardId));
    if (!exists) return null;
  }
  return { anchor: structuredClone(anchor), status: "attached", tokens: [], quotedText: null };
}

/** The same word or card anchor in the one other row that now holds its first word or its card. */
function followedAnchor(before: ScriptDocumentV2, document: ScriptDocumentV2, anchor: CommentAnchorV2): CommentAnchorV2 | null {
  if (anchor.kind !== "text" && anchor.kind !== "card") return null;
  if (anchor.kind === "card") {
    const previous = before.activeDraft.blocks.find((block) => block.id === anchor.blockId);
    const current = document.activeDraft.blocks.find((block) => block.id === anchor.blockId);
    // Wordless cards use payload IDs. Follow the same visual in either
    // direction so clearing narration and Undo keep its comment attached.
    const narration = previous?.type === "narration" ? previous : current?.type === "narration" ? current : undefined;
    if (narration && ((previous?.type === "narration" && current?.type === "visual_only") ||
                      (previous?.type === "visual_only" && current?.type === "narration"))) {
      const placements = [
        ...(narration.primaryVisualSequence?.slots ?? []).flatMap((slot) =>
          slot.kind === "content" && slot.payload.kind === "visual" ? [{ slotId: slot.id, payload: slot.payload }] : []),
        ...(narration.unattachedVisuals ?? []),
      ];
      const placement = placements.find((card) => previous.type === "narration"
        ? card.slotId === anchor.cardId : card.payload.payloadId === anchor.cardId);
      if (placement) return { ...anchor, cardId: previous.type === "narration" ? placement.payload.payloadId : placement.slotId };
    }
  }
  const holders = document.activeDraft.blocks.filter((block) => block.type === "narration" && block.id !== anchor.blockId && (
    anchor.kind === "text"
      ? block.tokens.some((token) => token.id === anchor.startTokenId)
      : block.primaryVisualSequence?.slots.some((slot) => slot.kind === "content" && slot.id === anchor.cardId) ||
        block.unattachedVisuals?.some((visual) => visual.slotId === anchor.cardId)));
  return holders.length === 1 ? { ...anchor, blockId: holders[0]!.id } : null;
}

/** Injected attribution only: this module neither authenticates actors nor grants permissions. */
export function createCommentStateV2(document: ScriptDocumentV2): CommentStateV2 {
  const parsed = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(document));
  if (!parsed.ok) throw new Error("Invalid comment document.");
  return { initialDocument: structuredClone(parsed.document), document: parsed.document, revision: 0, threads: [], history: [] };
}

/** A sequential local transaction; refusal returns the original state, including its history. */
export function applyCommentOperationV2(state: CommentStateV2, expectedRevision: number, input: CommentOperationV2): CommentResultV2 {
  try {
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== state.revision || expectedRevision === Number.MAX_SAFE_INTEGER) throw new Error("Stale comment revision.");
    const op = operationInput(input);
    if (state.history.some((prior) => prior.id === op.id)) throw new Error("Duplicate operation ID.");
    const next = { ...state, document: structuredClone(state.document), threads: structuredClone(state.threads), history: [...state.history] };
    if (op.kind === "replace_document" || op.kind === "undo_document") {
      const document = createCommentStateV2(op.document).document;
      if (document.id !== state.document.id || document.projectId !== state.document.projectId) throw new Error("Document identity changed.");
      if (sameAuthoringJsonV2(document, state.document)) throw new Error("Document edit has no change.");
      if (op.kind === "undo_document") {
        // A comment op cannot attest to a row session's Undo. Require the most recent
        // document edit, its exact preimage and the row session's next revision instead.
        const lastIndex = state.history.findLastIndex((item) => item.kind === "replace_document" || item.kind === "undo_document");
        const last = state.history[lastIndex];
        if (!last || last.kind !== "replace_document" || last.id !== op.undoOfOperationId ||
          !sameAuthoringJsonV2(last.document, state.document)) throw new Error("Undo does not match the latest document edit.");
        const preceding = state.history.slice(0, lastIndex).findLast((item) => item.kind === "replace_document" || item.kind === "undo_document");
        const priorDocument = preceding && (preceding.kind === "replace_document" || preceding.kind === "undo_document")
          ? preceding.document : state.initialDocument;
        const preimage = structuredClone(priorDocument);
        const restored = structuredClone(document);
        delete preimage.rowEditRevision;
        delete restored.rowEditRevision;
        const beforeRevision = state.document.rowEditRevision;
        const undoRevision = document.rowEditRevision;
        if (!sameAuthoringJsonV2(preimage, restored) ||
          typeof beforeRevision !== "number" || !Number.isSafeInteger(beforeRevision) ||
          typeof undoRevision !== "number" || !Number.isSafeInteger(undoRevision) ||
          undoRevision !== beforeRevision + 1) throw new Error("Undo document is not the verified pre-edit image.");
      }
      next.document = document;
      for (const thread of next.threads) {
        if (thread.attachment.status === "stale") {
          if (op.kind === "undo_document" && thread.attachment.orphanedByDocumentOperationId === op.undoOfOperationId) {
            const restored = attachment(document, thread.attachment.anchor);
            if (restored && sameAuthoringJsonV2(restored.tokens, thread.attachment.tokens) &&
              restored.quotedText === thread.attachment.quotedText) thread.attachment = restored;
          }
          // A later document operation cannot revive an older orphan by coincidence.
          delete thread.attachment.orphanedByDocumentOperationId;
          continue;
        }
        let current = attachment(document, thread.attachment.anchor);
        if (!current) {
          // A split or join moves words and visuals to another row with their IDs; the comment follows them.
          const followed = followedAnchor(state.document, document, thread.attachment.anchor);
          const moved = followed ? attachment(document, followed) : null;
          if (moved && sameAuthoringJsonV2(moved.tokens, thread.attachment.tokens) && moved.quotedText === thread.attachment.quotedText) {
            thread.attachment.anchor = moved.anchor;
            current = moved;
          }
        }
        const anchor = thread.attachment.anchor;
        const previousBlock = anchor.kind === "text" ? state.document.activeDraft.blocks.find((block) => block.id === anchor.blockId) : undefined;
        const nextBlock = anchor.kind === "text" ? document.activeDraft.blocks.find((block) => block.id === anchor.blockId) : undefined;
        const classificationOnly = previousBlock?.type === "narration" && nextBlock?.type === "narration" &&
          previousBlock.text === nextBlock.text && sameAuthoringJsonV2(
            previousBlock.tokens.map((token) => ({ ...token, spoken: null })),
            nextBlock.tokens.map((token) => ({ ...token, spoken: null })),
          );
        if (!current || !sameAuthoringJsonV2(current.tokens, thread.attachment.tokens) ||
          current.quotedText !== thread.attachment.quotedText && !classificationOnly) {
          thread.attachment.status = "stale";
          if (op.kind === "replace_document") thread.attachment.orphanedByDocumentOperationId = op.id;
        }
        else thread.attachment.quotedText = current.quotedText;
      }
    } else {
      let thread = next.threads.find((thread) => thread.id === op.threadId);
      if (op.kind === "create") {
        if (thread) throw new Error("Duplicate thread ID.");
        const target = attachment(next.document, op.anchor);
        if (!target) throw new Error("Missing or ambiguous anchor target.");
        thread = { id: op.threadId, attachment: target, resolved: false, messages: [] };
        next.threads.push(thread);
      }
      if (!thread) throw new Error("Missing comment thread.");
      if (op.kind === "create" || op.kind === "reply") {
        if (next.threads.some((item) => item.messages.some((message) => message.id === op.messageId))) throw new Error("Duplicate message ID.");
        thread.messages.push({ id: op.messageId, actorId: op.actorId, body: op.body, mentionActorIds: [...op.mentionActorIds] });
      } else if (op.kind === "resolve" || op.kind === "reopen") {
        const resolved = op.kind === "resolve";
        if (thread.resolved === resolved) throw new Error("Thread already has that resolution state.");
        thread.resolved = resolved;
      } else {
        if (thread.attachment.status !== "stale") throw new Error("Only stale threads can be reattached.");
        const target = attachment(next.document, op.anchor);
        if (!target) throw new Error("Missing or ambiguous reattachment target.");
        thread.attachment = target;
      }
    }
    next.revision++;
    next.history.push(structuredClone(op));
    return { ok: true, state: next };
  } catch (error) {
    return { ok: false, state, error: error instanceof Error ? error.message : "Invalid comment operation." };
  }
}

/** Local value round trip via validated replay, not durable service storage. */
export function serializeCommentStateV2(state: CommentStateV2): string {
  const json = JSON.stringify({ schemaVersion: "authoring-comments/v1", initialDocument: state.initialDocument, operations: state.history });
  const replayed = deserializeCommentStateV2(json);
  if (!sameAuthoringJsonV2(state, replayed)) throw new Error("Comment state does not match its operation history.");
  return json;
}
export function deserializeCommentStateV2(json: string): CommentStateV2 {
  const saved = record(JSON.parse(json) as unknown);
  fields(saved, "schemaVersion initialDocument operations");
  if (saved.schemaVersion !== "authoring-comments/v1" || !Array.isArray(saved.operations)) throw new Error("Unsupported comment save format.");
  const document = deserializeAuthoringDocumentV2(JSON.stringify(saved.initialDocument));
  if (!document.ok) throw new Error("Invalid saved comment document.");
  let state = createCommentStateV2(document.document);
  for (const operation of saved.operations) {
    const result = applyCommentOperationV2(state, state.revision, operationInput(operation));
    if (!result.ok) throw new Error(result.error);
    state = result.state;
  }
  return state;
}
