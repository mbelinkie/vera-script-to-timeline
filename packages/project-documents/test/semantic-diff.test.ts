import { randomUUID } from "node:crypto";

import type { NarrationBlockV2, SupportingItemV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";

import { compareDocuments } from "../src/semantic-diff.js";
import { documentFor } from "./helpers.js";

function narration(id = randomUUID()): NarrationBlockV2 {
  return {
    type: "narration", id, orderKey: "a0", text: "Hello",
    tokens: [{ id: randomUUID(), value: "Hello", startOffset: 0, endOffset: 5 }],
    primaryVisualSequence: { id: randomUUID(), version: 1, slots: [{
      id: randomUUID(), kind: "content", relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function supporting(id = randomUUID()): SupportingItemV2 {
  return { id, version: 1, orderKey: "a0", role: "citation", content: "Source",
    placement: { kind: "unplaced", reason: "Awaiting authoring" } };
}

describe("deterministic typed semantic comparison", () => {
  it("ignores collaboration head evidence and reserved empty Ideas/Extras", () => {
    const before = documentFor(randomUUID());
    expect(compareDocuments(before, { ...before, liveHeadSequence: 99,
      liveStateVector: "YQ==", liveContentHash: `sha256:${"b".repeat(64)}` })).toEqual([]);
    expect(compareDocuments(before, { ...before, title: "New" })).toEqual([
      { surface: "document", entityId: before.id, kind: "modified", fields: ["title"] },
    ]);
  });

  it("sorts typed document, row and support edits by surface and stable ID", () => {
    const baseline = documentFor(randomUUID());
    const reordered = narration("00000000-0000-4000-8000-000000000001");
    const edited = narration("00000000-0000-4000-8000-000000000002");
    const removed = narration("00000000-0000-4000-8000-000000000004");
    const added = narration("00000000-0000-4000-8000-000000000003");
    const note = supporting();
    const before = { ...baseline, activeDraft: {
      blocks: [removed, edited, reordered], supportingItems: [note],
    } };
    const after = { ...baseline, title: "New title", activeDraft: {
      blocks: [added, { ...edited, text: "Hi", tokens: [{ ...edited.tokens[0]!, value: "Hi", endOffset: 2 }] },
        { ...reordered, orderKey: "z9" }],
      supportingItems: [{ ...note, content: "Revised", placement: { kind: "unplaced" as const, reason: "Unknown" } }],
    } };
    expect(compareDocuments(before, after)).toEqual([
      { surface: "document", entityId: baseline.id, kind: "modified", fields: ["title"] },
      { surface: "draft_block", entityId: reordered.id, kind: "reordered", fields: ["orderKey"] },
      { surface: "draft_block", entityId: edited.id, kind: "modified", fields: ["text", "tokens"] },
      { surface: "draft_block", entityId: added.id, kind: "added", fields: [] },
      { surface: "draft_block", entityId: removed.id, kind: "removed", fields: [] },
      { surface: "supporting_item", entityId: note.id, kind: "modified", fields: ["content", "placement"] },
    ]);
    expect(compareDocuments(after, after)).toEqual([]);
  });

  it("uses canonical object-key comparisons but preserves unresolved typed values", () => {
    const baseline = documentFor(randomUUID());
    const note = supporting();
    const before = { ...baseline, activeDraft: { blocks: [], supportingItems: [
      { ...note, placement: { kind: "unplaced" as const, reason: "Unresolved" } },
    ] } };
    const reorderedKeys = { ...baseline, activeDraft: { blocks: [], supportingItems: [
      { ...note, placement: { reason: "Unresolved", kind: "unplaced" as const } },
    ] } };
    expect(compareDocuments(before, reorderedKeys)).toEqual([]);
    const changed = { ...reorderedKeys, activeDraft: { blocks: [], supportingItems: [
      { ...note, placement: { kind: "unplaced" as const, reason: "Still missing" } },
    ] } };
    expect(compareDocuments(before, changed)).toEqual([
      { surface: "supporting_item", entityId: note.id, kind: "modified", fields: ["placement"] },
    ]);
  });

  it("identifies a nested typed visual edit without emitting a generic JSON patch", () => {
    const baseline = documentFor(randomUUID());
    const row = narration();
    const original = { ...baseline, activeDraft: { blocks: [row], supportingItems: [] } };
    const altered = { ...row, primaryVisualSequence: {
      ...row.primaryVisualSequence!, slots: [{
        ...row.primaryVisualSequence!.slots[0]!,
        payload: { kind: "on_camera" as const, presenterChoiceId: randomUUID() },
      }],
    } };
    expect(compareDocuments(original, { ...original, activeDraft: {
      blocks: [altered], supportingItems: [],
    } })).toEqual([
      { surface: "draft_block", entityId: row.id, kind: "modified", fields: ["primaryVisualSequence"] },
    ]);
  });

  it("refuses foreign identity and duplicate semantic row IDs", () => {
    const a = documentFor(randomUUID());
    expect(() => compareDocuments(a, documentFor(randomUUID()))).toThrow();
    expect(() => compareDocuments(a, { ...a, id: randomUUID() })).toThrow();
    const row = narration();
    expect(() => compareDocuments({ ...a, activeDraft: { blocks: [row, row], supportingItems: [] } }, a))
      .toThrow("Duplicate semantic identity");
  });
});
