import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import {
  applyCommentOperationV2, createCommentStateV2, deserializeCommentStateV2, serializeCommentStateV2,
  projectPrimarySequenceV2, type CommentAnchorV2, type CommentOperationV2,
} from "@vera/contracts/authoring-v2";
import type { CompilerDependenciesV2, NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import { exportPrompter } from "../src/prompter-export.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
function fixture() {
  const { document, dependencies } = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 };
  const first = document.activeDraft.blocks[0] as NarrationBlockV2;
  const second: NarrationBlockV2 = {
    ...structuredClone(first), id: id(100), orderKey: "b0", text: "world",
    tokens: [{ id: id(101), value: "world", startOffset: 0, endOffset: 5 }],
    primaryVisualSequence: { id: id(103), version: 1, slots: [{
      id: id(104), kind: "content", version: 1, relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval",
    }] },
  };
  document.activeDraft.blocks.push(second);
  const timing = structuredClone(dependencies.narrationTimingMaps[0]!);
  timing.blockId = second.id;
  timing.textHash = `sha256:${createHash("sha256").update(second.text).digest("hex")}`;
  timing.tokens[0].tokenId = second.tokens[0].id;
  timing.tokens[0].quotedText = second.text;
  timing.narrationAssetId = id(102);
  timing.audio!.narrationAssetId = id(102);
  timing.audio!.locator = "Builds/narration/world.wav";
  dependencies.narrationTimingMaps.push(timing);
  dependencies.document.textHash = `sha256:${createHash("sha256").update("hello\nworld").digest("hex")}`;
  return { document, dependencies, first, second };
}
function consumers(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2) {
  const projection = projectPrimarySequenceV2(document);
  const prompter = exportPrompter(document, { includeSectionNavigation: true, includeBeatNumbers: true });
  const compiler = compileTimelineV2(document, dependencies);
  const needs = resolveMediaRequirementsV2(document, {
    timing: dependencies.narrationTimingMaps, defaults: dependencies.authoringDefaults,
    sourceDescriptors: dependencies.occurrenceResolutions, frameRate: dependencies.timeline.frameRate,
  });
  expect(prompter.ok).toBe(true);
  expect(compiler.ok).toBe(true);
  expect(needs.ok).toBe(true);
  if (!prompter.ok || !compiler.ok || !needs.ok) throw new Error("Synthetic consumer fixture must compile and export.");
  expect(prompter.sidecar.beats.map((beat) => beat.expectedText)).toEqual(["hello", "world"]);
  expect(compiler.manifest.timeline.durationFrames).toBe(192);
  expect(needs.durationFrames).toBe(192);
  expect(needs.requirements).toHaveLength(1);
  return { projection, prompter, compiler, needs };
}

it("keeps real narration projection, prompter bytes, compiler duration/timeline and media needs identical through comment-only changes", () => {
  const { document, dependencies, first, second } = fixture();
  const before = consumers(document, dependencies);
  let state = createCommentStateV2(document);
  const actorId = "public-synthetic-actor";
  const anchors: CommentAnchorV2[] = [
    { kind: "text", blockId: first.id, startTokenId: first.tokens[0].id, endTokenId: first.tokens[0].id },
    { kind: "card", blockId: first.id, cardId: first.primaryVisualSequence!.slots[0]!.id },
    { kind: "block", blockId: second.id },
    { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id },
  ];
  const operations: CommentOperationV2[] = anchors.map((anchor, n) => ({
    id: `create-${n}`, actorId, kind: "create", threadId: `thread-${n}`, messageId: `message-${n}`,
    body: "UNSPOKEN COMMENT", mentionActorIds: [actorId], anchor,
  }));
  operations.push(
    { id: "reply", actorId, kind: "reply", threadId: "thread-0", messageId: "reply", body: "UNSPOKEN REPLY", mentionActorIds: [actorId] },
    { id: "resolve", actorId, kind: "resolve", threadId: "thread-0" },
    { id: "reopen", actorId, kind: "reopen", threadId: "thread-0" },
  );
  for (const operation of operations) {
    const result = applyCommentOperationV2(state, state.revision, operation);
    if (!result.ok) throw new Error(result.error);
    state = result.state;
    expect(consumers(state.document, dependencies)).toEqual(before);
  }
  const loaded = deserializeCommentStateV2(serializeCommentStateV2(state));
  expect(loaded).toEqual(state);
  expect(consumers(loaded.document, dependencies)).toEqual(before);
  expect(loaded.document).toEqual(document);
  expect(loaded.document.liveHeadSequence).toBe(dependencies.document.liveHeadSequence);
  expect(loaded.document.liveContentHash).toBe(dependencies.document.contentHash);
  expect(before.prompter.text).not.toContain("UNSPOKEN");
});
