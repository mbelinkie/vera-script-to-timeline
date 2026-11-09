import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2, VisualOnlyBlockV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";

import { applyExtrasStorageOperation, parseExtrasOperationCommand } from "../src/extras-operations.js";
import { documentFor } from "./helpers.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const fixturePath = fileURLToPath(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url));
const gap = { sectionId: id(500), afterRowId: null, beforeRowId: null };
const command = (rowIds: string[]) => ({ kind: "duplicate_stash_rows", rowIds, destination: gap });
const allocator = (initial = 100000) => {
  let next = initial;
  return () => id(next++);
};

function fixture() {
  const row = (JSON.parse(readFileSync(fixturePath, "utf8")) as { document: ScriptDocumentV2 })
    .document.activeDraft.blocks[0] as NarrationBlockV2;
  const document = documentFor(id(2));
  document.id = id(1);
  document.activeDraft.blocks = [{ type: "section", id: gap.sectionId, orderKey: "1", title: "Draft", version: 1 }, row];
  const token = row.tokens[0]!;
  const range = { blockId: row.id, startTokenId: token.id, endTokenId: token.id,
    startAffinity: "before" as const, endAffinity: "after" as const, quotedText: token.value, anchorVersion: 1 };
  row.annotations = [{ id: id(600), kind: "performance_note", range: structuredClone(range), value: "context", includeInPrompter: false, version: 1 }];
  row.performanceBeats = [{ id: id(601), range: structuredClone(range), version: 1 }];
  const anchor = { kind: "word" as const, anchor: { blockId: row.id, tokenId: token.id,
    affinity: "before" as const, quotedWord: token.value, anchorVersion: 1 } };
  const citation: SupportingItemV2 = { id: id(602), role: "citation", version: 1, orderKey: "c",
    content: "Archive citation", placement: { kind: "point", anchor }, displayAttachment: anchor };
  document.activeDraft.supportingItems = [citation];
  const parked = applyExtrasStorageOperation(document, { kind: "stash_rows", rowIds: [row.id], bundleId: id(603) });
  expect(parked.ok, JSON.stringify(parked.diagnostics)).toBe(true);
  return { document: parked.document, row, citation, range };
}

function copied(document: ScriptDocumentV2) {
  const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration");
  expect(row).toBeDefined();
  return row!;
}

function refuseWithoutMutation(document: ScriptDocumentV2, raw: unknown, code: string, next = allocator()) {
  const before = JSON.stringify(document);
  const result = applyExtrasStorageOperation(document, raw, next);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(false);
  expect(result.diagnostics[0]?.code).toBe(code);
  expect(result.document).toBe(document);
  expect(JSON.stringify(document)).toBe(before);
}

describe("Extras atomic duplicate-as-new", () => {
  it("rejects extra keys, forged actor/IDs, missing roots and invalid destinations", () => {
    const { document, row } = fixture();
    for (const raw of [
      { ...command([row.id]), actorId: id(999) },
      { ...command([row.id]), bundleId: id(700) },
      { ...command([row.id]), rowIds: [row.id, row.id] },
      { ...command([row.id]), includeDescendants: false },
      { ...command([row.id]), destination: { ...gap, parentRowId: null } },
      { ...command([row.id]), destination: { ...gap, afterRowId: id(999) } },
    ]) {
      const parsed = parseExtrasOperationCommand(raw);
      if ("destination" in raw && "afterRowId" in raw.destination && raw.destination.afterRowId === id(999)) {
        expect(parsed).toEqual(raw);
        refuseWithoutMutation(document, raw, "ROW_DESTINATION_INVALID");
      } else {
        expect(parsed).toBeNull();
        refuseWithoutMutation(document, raw, "EXTRAS_COMMAND_INVALID");
      }
    }
    refuseWithoutMutation(document, command([id(999)]), "ROW_SELECTION_INVALID");
  });

  it("duplicates tokens, annotations, beats, visual slots, payload and citation into one new Draft row", () => {
    const { document, row, citation, range } = fixture();
    const originalBytes = JSON.stringify(document.stash);
    const original = JSON.stringify(document);
    const result = applyExtrasStorageOperation(document, command([row.id]), allocator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(JSON.stringify(document)).toBe(original);
    expect(JSON.stringify(result.document.stash)).toBe(originalBytes);
    expect(result.document.extras).toEqual([]);
    expect(result.document.rowEditRevision).toBe(2);
    const clone = copied(result.document);
    const old = document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(clone.id).not.toBe(old.id);
    expect(clone.tokens[0]!.id).not.toBe(old.tokens[0]!.id);
    expect(clone.primaryVisualSequence!.id).not.toBe(old.primaryVisualSequence!.id);
    expect(clone.primaryVisualSequence!.slots[0]!.id).not.toBe(old.primaryVisualSequence!.slots[0]!.id);
    const slot = clone.primaryVisualSequence!.slots[0]!;
    const oldSlot = old.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual" ||
        oldSlot.kind !== "content" || oldSlot.payload.kind !== "visual") throw new Error("Expected visual payload");
    expect(slot.payload.payloadId).not.toBe(oldSlot.payload.payloadId);
    expect(slot.payload.source).toEqual(oldSlot.payload.source); // external media evidence stays immutable
    expect(clone.annotations![0]!.id).not.toBe(old.annotations![0]!.id);
    expect(clone.performanceBeats![0]!.id).not.toBe(old.performanceBeats![0]!.id);
    for (const current of [clone.annotations![0]!.range, clone.performanceBeats![0]!.range]) {
      expect(current).toMatchObject({ ...range, blockId: clone.id, startTokenId: clone.tokens[0]!.id, endTokenId: clone.tokens[0]!.id });
    }
    const newItem = result.document.activeDraft.supportingItems[0]!;
    expect(newItem.id).not.toBe(citation.id);
    expect(newItem.content).toBe(citation.content);
    expect(newItem.placement).toMatchObject({ kind: "point", anchor: { anchor: {
      blockId: clone.id, tokenId: clone.tokens[0]!.id, quotedWord: row.tokens[0]!.value,
    } } });
    expect(newItem.displayAttachment).toEqual((newItem.placement as { anchor: unknown }).anchor);
    expect(clone.stashOrigin).toBeUndefined();
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("preserves attached footage and Research/media external IDs while remapping both owned occurrences", () => {
    const { document, row } = fixture();
    const saved = document.stash![0]!.rows[0] as NarrationBlockV2;
    const slot = saved.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Expected clip");
    const clip: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(605), orderKey: "clip", version: 1,
      payload: { kind: "visual", payloadId: id(606), pictureKind: "clip", source: structuredClone(slot.payload.source), audioPolicy: "mute", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 20 } },
    };
    saved.attachedFootage = { clip };
    slot.payload.selectedSourceRange = { startFrame: 0, durationFrames: 20 };
    document.stashOutline![0]!.kind = "note";
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const before = JSON.stringify(document.stash);
    const result = applyExtrasStorageOperation(document, command([row.id]), allocator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const fresh = copied(result.document);
    expect(fresh.attachedFootage?.clip.id).not.toBe(clip.id);
    expect(fresh.attachedFootage?.clip.payload.payloadId).not.toBe(clip.payload.payloadId);
    expect(fresh.attachedFootage?.clip.payload.source).toEqual(clip.payload.source);
    expect(fresh.attachedFootage?.clip.visualOnlyTiming).toEqual(clip.visualOnlyTiming);
    expect(JSON.stringify(result.document.stash)).toBe(before);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("refuses an attached clip without an exact one-slot visual mirror", () => {
    const { document, row } = fixture();
    const saved = document.stash![0]!.rows[0] as NarrationBlockV2;
    saved.attachedFootage = { clip: {
      type: "visual_only", id: id(651), orderKey: "clip", version: 1,
      payload: { kind: "visual", payloadId: id(652), pictureKind: "clip",
        source: { kind: "media_reference", mediaReferenceId: id(653) }, audioPolicy: "mute", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 20 } },
    } };
    // Canonical saved notes may have an on-camera placeholder; it cannot become a second, implicit clip owner.
    document.stashOutline![0]!.kind = "note";
    expect(validateScriptDocumentV2(document).diagnostics.filter((d) => d.severity !== "warning")).toEqual([]);
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
  });

  it("remaps previous-media slot edges and event timing anchors while retaining their literal timing", () => {
    const { document, row } = fixture();
    const saved = document.stash![0]!.rows[0] as NarrationBlockV2;
    const root = saved.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("Expected clip root");
    root.playoutPolicy = "complete_logged_clip";
    saved.primaryVisualSequence!.slots.push({
      id: id(608), kind: "content", relation: { kind: "sequential" },
      boundaryBefore: { kind: "previous_media_end", controllingSlotId: root.id },
      payload: { ...structuredClone(root.payload), payloadId: id(609) },
      playoutPolicy: "match_structural_interval", version: 1,
    });
    saved.overlayEvents.push({
      id: id(610), version: 1,
      payload: { kind: "visual", payloadId: id(611), pictureKind: "unresolved_visual",
        source: { kind: "unresolved_visual", description: "Reference shot" },
        sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain" },
      timing: { kind: "timed", start: { kind: "word", anchor: {
        blockId: row.id, tokenId: row.tokens[0]!.id, affinity: "before",
        quotedWord: row.tokens[0]!.value, anchorVersion: 1,
      } }, durationMs: 700 },
    });
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const result = applyExtrasStorageOperation(document, command([row.id]), allocator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const fresh = copied(result.document);
    const second = fresh.primaryVisualSequence!.slots[1]!;
    if (second.kind !== "content" || second.boundaryBefore.kind !== "previous_media_end" || second.payload.kind !== "visual") throw new Error("Expected sequential slot");
    expect(second.boundaryBefore.controllingSlotId).toBe(fresh.primaryVisualSequence!.slots[0]!.id);
    expect(second.payload.payloadId).not.toBe(id(609));
    expect(fresh.overlayEvents[0]!.id).not.toBe(id(610));
    expect(fresh.overlayEvents[0]!.payload.payloadId).not.toBe(id(611));
    const start = fresh.overlayEvents[0]!.timing.start;
    expect(start).toMatchObject({ kind: "word", anchor: { blockId: fresh.id, tokenId: fresh.tokens[0]!.id } });
    expect(fresh.overlayEvents[0]!.timing.durationMs).toBe(700);
  });

  it("duplicates a closed saved parent/child branch in outline preorder, preserving the originals", () => {
    const { document, row } = fixture();
    const child = { type: "direction" as const, id: id(700), orderKey: "child", text: "B roll idea", buildBehavior: "none" as const, version: 1 };
    document.stash!.push({ id: id(701), rows: [child], supportingItems: [] });
    document.stashOutline = [
      { rowId: row.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "row", parentRowId: row.id, sectionId: null },
    ];
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const oldStash = JSON.stringify(document.stash);
    const result = applyExtrasStorageOperation(document, command([row.id]), allocator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks.slice(1).map((r) => r.type)).toEqual(["narration", "direction"]);
    expect(result.document.activeDraft.blocks[2]!.id).not.toBe(child.id);
    expect(JSON.stringify(result.document.stash)).toBe(oldStash);
    expect(result.document.stashOutline).toEqual(document.stashOutline);
    expect(result.document.rowEditRevision).toBe(2);
  });

  it("refuses cross-boundary citation anchors and unknown/orphan token edges rather than copying a guessed reference", () => {
    const { document, row } = fixture();
    const outside = { type: "direction" as const, id: id(700), orderKey: "outside", text: "Outside", buildBehavior: "none" as const, version: 1 };
    document.stash![0]!.rows.push(outside);
    document.stashOutline!.push({ rowId: outside.id, kind: "row", parentRowId: null, sectionId: null });
    document.stash![0]!.supportingItems.push({
      id: id(701), role: "reference", content: "Both rows", version: 1, orderKey: "cross",
      placement: { kind: "point", anchor: { kind: "between_blocks", beforeBlockId: row.id, afterBlockId: outside.id } },
    });
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    document.stash![0]!.supportingItems.pop();
    const first = document.stash![0]!.supportingItems[0]!;
    if (first.placement.kind !== "point" || first.placement.anchor.kind !== "word") throw new Error("Expected word anchor");
    first.placement.anchor.anchor.tokenId = id(999999);
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
  });

  it("refuses orphaned saved supporting references and a citation wrongly attached to a different bundle", () => {
    const { document, row } = fixture();
    const item = document.stash![0]!.supportingItems[0]!;
    if (item.placement.kind !== "point" || item.placement.anchor.kind !== "word") throw new Error("Expected word");
    item.placement.anchor.anchor.blockId = id(999);
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    item.placement.anchor.anchor.blockId = row.id;
    document.stash!.push({ id: id(750), rows: [{ type: "direction", id: id(751), orderKey: "unrelated", text: "Other", buildBehavior: "none", version: 1 }], supportingItems: [item] });
    document.stash![0]!.supportingItems = [];
    document.stashOutline!.push({ rowId: id(751), kind: "row", parentRowId: null, sectionId: null });
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
  });

  it("refuses half of an atomic saved group, opaque refs, audio, transitions, and unknown owned nested identities", () => {
    const { document, row } = fixture();
    const second = { type: "direction" as const, id: id(702), orderKey: "next", text: "Other", buildBehavior: "none" as const, version: 1 };
    document.stash!.push({ id: id(703), rows: [second], supportingItems: [] });
    document.stashOutline!.push({ rowId: second.id, kind: "row", parentRowId: null, sectionId: null });
    document.stashGroups = [{ id: id(704), rowIds: [row.id, second.id] }];
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    delete document.stashGroups;
    document.rowReferences = [{ id: id(705), rowId: row.id, kind: "comment", anchor: { untrusted: true } }];
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    delete document.rowReferences;
    document.rowAudioSpans = [{ id: id(706), startRowId: row.id, endRowId: second.id,
      source: { mediaReferenceId: id(707), artifactId: id(708), artifactVersion: 1, contentHash: `sha256:${"a".repeat(64)}` }, settings: {} }];
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    delete document.rowAudioSpans;
    document.rowTransitions = [{ id: id(709), fromRowId: row.id, toRowId: second.id, effect: "dissolve", settings: {}, state: "needs_review" }];
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED");
    delete document.rowTransitions;
    const saved = document.stash![0]!.rows[0] as NarrationBlockV2;
    Object.assign(saved, { undocumented: { id: id(710) } });
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_INVALID");
  });

  it("refuses allocator collisions, reused IDs, bogus UUIDs and exceptions atomically", () => {
    const { document, row } = fixture();
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_ID_COLLISION", () => row.id);
    const slot = row.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual" || slot.payload.source.kind !== "media_reference") throw new Error("Expected media source");
    const sourceId = slot.payload.source.mediaReferenceId;
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_ID_COLLISION", () => sourceId);
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_ID_COLLISION", () => "not-uuid");
    let call = 0;
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_ID_COLLISION", () => id(100000 + Math.min(call++, 1)));
    refuseWithoutMutation(document, command([row.id]), "EXTRAS_DUPLICATE_REVIEW_REQUIRED", () => { throw new Error("allocator unavailable"); });
  });
});
