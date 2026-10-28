import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import {
  applyCommentOperationV2,
  createCommentStateV2,
  deserializeCommentStateV2,
  serializeCommentStateV2,
  type CommentResultV2,
  type CommentStateV2,
} from "./authoring-v2-comments.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

export interface SortingCommentContextV2 {
  state: CommentStateV2;
  id: string;
  actorId: string;
}

/**
 * Reconcile canonical discussion state with the final chosen sorting document.
 * Pending sorting edits stay outside this state; this helper is for one final
 * accept or discard decision. Comments created on rows introduced only during
 * a pending trial are unsupported; callers must refuse finalization if any
 * exist because this context cannot preserve them.
 */
export function resolveSortingCommentsV2(
  canonical: ScriptDocumentV2,
  intended: ScriptDocumentV2,
  context: SortingCommentContextV2,
): CommentResultV2 {
  const suppliedContext = context as SortingCommentContextV2 | null | undefined;
  const originalState = suppliedContext && typeof suppliedContext === "object" ? suppliedContext.state : undefined;
  try {
    if (!suppliedContext || typeof suppliedContext !== "object" || !originalState) throw new Error("Comment reconciliation context is missing its state.");
    if (typeof suppliedContext.id !== "string" || !suppliedContext.id.trim() || typeof suppliedContext.actorId !== "string" || !suppliedContext.actorId.trim()) {
      throw new Error("Comment reconciliation attribution must be nonempty.");
    }

    const savedState = serializeCommentStateV2(originalState);
    const validatedState = deserializeCommentStateV2(savedState);
    const validatedCanonical = createCommentStateV2(canonical).document;
    if (!sameAuthoringJsonV2(validatedState.document, validatedCanonical)) {
      throw new Error("Comment state does not match the sorting canonical document.");
    }
    const validatedIntended = createCommentStateV2(intended).document;
    if (sameAuthoringJsonV2(validatedCanonical, validatedIntended)) return { ok: true, state: originalState };

    const result = applyCommentOperationV2(validatedState, validatedState.revision, {
      id: suppliedContext.id,
      actorId: suppliedContext.actorId,
      kind: "replace_document",
      document: structuredClone(validatedIntended),
    });
    return result.ok ? result : { ok: false, state: originalState, error: result.error };
  } catch (error) {
    return {
      ok: false,
      state: originalState ?? createCommentStateV2(canonical),
      error: error instanceof Error ? error.message : "Invalid comment reconciliation.",
    };
  }
}
