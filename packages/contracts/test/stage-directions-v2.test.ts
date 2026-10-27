import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  applyCommentOperationV2,
  applyStageDirectionEditV2,
  createCommentStateV2,
  deserializeAuthoringDocumentV2,
  inspectStageDirectionsV2,
  projectPrimarySequenceV2,
  serializeAuthoringDocumentV2,
  spokenNarrationViewV2,
  undoStageDirectionEditV2,
  validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import { exportPrompter } from "../src/prompter-export.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

function documentWithText(text: string, words: string[]): { document: ScriptDocumentV2; row: NarrationBlockV2 } {
  const parsed = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
  const document = parsed.document;
  const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration")!;
  row.text = text;
  let cursor = 0;
  const tokens = words.map((value, index) => {
    const startOffset = text.indexOf(value, cursor);
    if (startOffset < 0) throw new Error(`Missing token ${value} in fixture text.`);
    const endOffset = startOffset + value.length;
    cursor = endOffset;
    return { id: id(101 + index), value, startOffset, endOffset };
  });
  row.tokens = [tokens[0]!, ...tokens.slice(1)];
  row.version = 1;
  row.state = "active";
  row.primaryVisualSequence = {
    id: id(900), version: 1, slots: [{
      id: id(901), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }],
  };
  row.overlayEvents = [];
  row.annotations = [];
  row.performanceBeats = [];
  row.notes = [];
  document.activeDraft.blocks = [row];
  document.activeDraft.supportingItems = [];
  document.stash = [];
  document.rowReferences = [];
  document.rowTransitions = [];
  const validation = validateScriptDocumentV2(document);
  if (!validation.valid) throw new Error(JSON.stringify(validation.diagnostics));
  return { document, row };
}

function requireSuccess<T extends { ok: boolean; diagnostics: unknown[] }>(result: T): asserts result is T & { ok: true } {
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
}

describe("paired stage-direction operations", () => {
  it("keeps quotes, parentheses, and literal brackets spoken until explicitly classified", () => {
    const { row } = documentWithText('She said "go" (slowly) [literally] today.', ["She", "said", '"go"', "(slowly)", "[literally]", "today."]);
    expect(row.tokens.every((token) => token.spoken === undefined)).toBe(true);
    expect(inspectStageDirectionsV2(row)).toEqual({ runs: [], issues: [] });
    expect(spokenNarrationViewV2(row).text).toBe(row.text);
    expect(spokenNarrationViewV2(row).tokens.map((token) => token.value)).toEqual(row.tokens.map((token) => token.value));
  });

  it("wraps only selected words, keeps stable references, exports spoken text, and snapshot-undoes", () => {
    const { document } = documentWithText("hello blue world", ["hello", "blue", "world"]);
    const row = document.activeDraft.blocks[0] as NarrationBlockV2;
    const blueId = row.tokens[1]!.id;
    const worldId = row.tokens[2]!.id;
    const annotationId = id(800);
    row.annotations = [{
      id: annotationId,
      kind: "performance_note",
      range: { blockId: row.id, startTokenId: worldId, endTokenId: worldId, startAffinity: "before", endAffinity: "after", quotedText: "world", anchorVersion: 1 },
      value: "Emphasize",
      includeInPrompter: true,
      version: 1,
    }];
    const annotationValidation = validateScriptDocumentV2(document);
    expect(annotationValidation.valid, JSON.stringify(annotationValidation.diagnostics)).toBe(true);

    let comments = createCommentStateV2(document);
    const created = applyCommentOperationV2(comments, 0, {
      id: "comment-create", actorId: "actor", kind: "create", threadId: "thread", messageId: "message",
      body: "Keep this wording", mentionActorIds: [],
      anchor: { kind: "text", blockId: row.id, startTokenId: blueId, endTokenId: blueId },
    });
    if (!created.ok) throw new Error(created.error);
    comments = created.state;

    const edit = applyStageDirectionEditV2(comments.document, row.version, {
      kind: "make_stage_direction", blockId: row.id, startOffset: 6, endOffset: 10,
    });
    requireSuccess(edit);
    const editedRow = edit.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(editedRow.text).toBe("hello [blue] world");
    expect(editedRow.tokens.map((token) => token.id)).toEqual(row.tokens.map((token) => token.id));
    expect(editedRow.tokens.map((token) => token.spoken)).toEqual([undefined, false, undefined]);
    expect(spokenNarrationViewV2(editedRow)).toMatchObject({ text: "hello world", tokens: [{ value: "hello" }, { value: "world", startOffset: 6 }] });

    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(edit.document));
    expect(saved.ok).toBe(true);
    if (!saved.ok) throw new Error("Stage-direction classification did not survive save/reload.");
    expect(saved.document.activeDraft.blocks[0]).toEqual(editedRow);
    const exported = exportPrompter(saved.document, { includeSectionNavigation: true, includeBeatNumbers: false });
    if (!exported.ok) throw new Error(JSON.stringify(exported.diagnostics));
    expect(exported.text).toContain("hello");
    expect(exported.text).not.toContain("blue");
    expect(exported.sidecar.beats.flatMap((beat) => beat.annotations).some((annotation) => annotation.id === annotationId && annotation.visibleInPrompter)).toBe(true);

    const commentUpdate = applyCommentOperationV2(comments, 1, {
      id: "comment-update-stage", actorId: "actor", kind: "replace_document", document: edit.document,
    });
    if (!commentUpdate.ok) throw new Error(commentUpdate.error);
    comments = commentUpdate.state;
    expect(comments.threads[0]!.attachment).toMatchObject({ status: "attached", quotedText: "blue", tokens: [{ id: blueId, value: "blue" }] });

    const undone = undoStageDirectionEditV2(edit.document, edit.undo!);
    requireSuccess(undone);
    const restoredRow = undone.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(restoredRow.text).toBe("hello blue world");
    expect(restoredRow.tokens.map((token) => token.spoken)).toEqual([undefined, undefined, undefined]);
    expect(restoredRow.tokens.map((token) => token.id)).toEqual(row.tokens.map((token) => token.id));
    expect(restoredRow.annotations).toEqual(row.annotations);
    const restoredComments = applyCommentOperationV2(comments, 2, {
      id: "comment-update-undo", actorId: "actor", kind: "replace_document", document: undone.document,
    });
    if (!restoredComments.ok) throw new Error(restoredComments.error);
    expect(restoredComments.state.threads[0]!.attachment).toMatchObject({ status: "attached", quotedText: "blue" });
  });

  it("deletes either marker of a recognized pair together and restores the marked state on Undo", () => {
    for (const offset of [6, 11]) {
      const { document, row } = documentWithText("hello [blue] world", ["hello", "blue", "world"]);
      row.tokens[1]!.spoken = false;
      expect(validateScriptDocumentV2(document).valid).toBe(true);
      const deleted = applyStageDirectionEditV2(document, row.version, { kind: "delete_direction_delimiter", blockId: row.id, offset });
      requireSuccess(deleted);
      const deletedRow = deleted.document.activeDraft.blocks[0] as NarrationBlockV2;
      expect(deletedRow.text).toBe("hello blue world");
      expect(deletedRow.tokens[1]!.spoken).toBeUndefined();
      const undone = undoStageDirectionEditV2(deleted.document, deleted.undo!);
      requireSuccess(undone);
      const restoredRow = undone.document.activeDraft.blocks[0] as NarrationBlockV2;
      expect(restoredRow.text).toBe("hello [blue] world");
      expect(restoredRow.tokens.map((token) => token.spoken)).toEqual([undefined, false, undefined]);
    }
  });

  it("supports a direction-only row, keeps it out of narration, and makes it spoken again", () => {
    const { document, row } = documentWithText("quietly now", ["quietly", "now"]);
    const edit = applyStageDirectionEditV2(document, row.version, {
      kind: "make_stage_direction", blockId: row.id, startOffset: 0, endOffset: row.text.length,
    });
    requireSuccess(edit);
    const directionRow = edit.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(directionRow.text).toBe("[quietly now]");
    expect(directionRow.tokens.every((token) => token.spoken === false)).toBe(true);
    expect(projectPrimarySequenceV2(edit.document).rows[0]!.tokens).toEqual([]);
    const exported = exportPrompter(edit.document, { includeSectionNavigation: true, includeBeatNumbers: false });
    if (!exported.ok) throw new Error(JSON.stringify(exported.diagnostics));
    expect(exported.text).toBe("");

    const madeSpoken = applyStageDirectionEditV2(edit.document, directionRow.version, {
      kind: "make_spoken", blockId: row.id,
      startOffset: directionRow.tokens[0]!.startOffset,
      endOffset: directionRow.tokens.at(-1)!.endOffset,
    });
    requireSuccess(madeSpoken);
    const spokenRow = madeSpoken.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(spokenRow.text).toBe("quietly now");
    expect(spokenRow.tokens.map((token) => token.spoken)).toEqual([undefined, undefined]);
  });

  it("restores the exact literal pair on Undo and refuses malformed nested direction brackets", () => {
    const { document, row } = documentWithText("hello [blue] world", ["hello", "blue", "world"]);
    const classified = applyStageDirectionEditV2(document, row.version, {
      kind: "make_stage_direction", blockId: row.id, startOffset: 6, endOffset: 12,
    });
    requireSuccess(classified);
    expect((classified.document.activeDraft.blocks[0] as NarrationBlockV2).text).toBe("hello [blue] world");
    const undone = undoStageDirectionEditV2(classified.document, classified.undo!);
    requireSuccess(undone);
    const restoredRow = undone.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(restoredRow.text).toBe("hello [blue] world");
    expect(restoredRow.tokens.map((token) => token.spoken)).toEqual([undefined, undefined, undefined]);

    const malformed = documentWithText("hello [[blue]] world", ["hello", "blue", "world"]);
    malformed.row.tokens[1]!.spoken = false;
    expect(inspectStageDirectionsV2(malformed.row).issues).toHaveLength(1);
    expect(validateScriptDocumentV2(malformed.document).valid).toBe(false);
    const refused = applyStageDirectionEditV2(malformed.document, malformed.row.version, {
      kind: "make_spoken", blockId: malformed.row.id, startOffset: 8, endOffset: 12,
    });
    expect(refused.ok).toBe(false);
    expect(refused.document).toEqual(malformed.document);
  });
});
