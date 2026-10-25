import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { applyStashRowEditV2 } from "../src/authoring-v2-stash.js";
import {
  applyRowEditV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
} from "../src/authoring-v2-rows.js";
import type {
  NarrationBlockV2,
  ScriptDocumentV2,
  SupportingItemV2,
  VisualOnlyBlockV2,
} from "../src/generated/contracts-v2.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const fixturePath = `${repositoryRoot}tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json`;
const id = (value: number): string =>
  `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;

function input(): ScriptDocumentV2 {
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
    document: ScriptDocumentV2;
  };
  return fixture.document;
}

function citation(row: NarrationBlockV2): SupportingItemV2 {
  const token = row.tokens[0];
  const attachment = {
    kind: "word" as const,
    anchor: {
      blockId: row.id,
      tokenId: token.id,
      affinity: "before" as const,
      quotedWord: token.value,
      anchorVersion: 1,
    },
  };
  return {
    id: id(9007),
    version: 1,
    orderKey: "saved-stash-citation",
    role: "citation",
    content: "Keep this attachment with the edited row",
    placement: { kind: "point", anchor: attachment },
    displayAttachment: attachment,
  };
}

function stashFixtureNarration() {
  const document = input();
  const row = document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration",
  );
  if (!row) throw new Error("Expected the fixture narration row");
  const originalRow = structuredClone(row);
  const supportingItem = citation(row);
  document.activeDraft.supportingItems.push(supportingItem);
  const bundleId = id(9008);
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, {
    kind: "stash_rows",
    rowIds: [row.id],
    bundleId,
  });
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  const bundle = result.document.stash?.find((candidate) => candidate.id === bundleId);
  if (!bundle) throw new Error("Expected the saved Stash bundle");
  return { document: result.document, originalRow, supportingItem, bundleId, originalGap: bundle.originalGap! };
}

function editNarration(row: NarrationBlockV2): NarrationBlockV2 {
  const edited = structuredClone(row);
  const prefix = "EDITED ";
  edited.text = prefix + edited.text;
  const shiftedTokens = edited.tokens.map((token) => ({
    ...token,
    startOffset: token.startOffset + prefix.length,
    endOffset: token.endOffset + prefix.length,
  }));
  const cameraToken = {
    id: id(9011),
    value: "there",
    startOffset: edited.text.length + 1,
    endOffset: edited.text.length + 1 + "there".length,
  };
  edited.text += ` ${cameraToken.value}`;
  edited.tokens = [{ id: id(9010), value: "EDITED", startOffset: 0, endOffset: 6 }, ...shiftedTokens, cameraToken];
  const token = edited.tokens[0];
  edited.annotations = [{
    id: id(9009),
    kind: "performance_note",
    range: {
      blockId: edited.id,
      startTokenId: token.id,
      endTokenId: token.id,
      startAffinity: "before",
      endAffinity: "after",
      quotedText: token.value,
      anchorVersion: 1,
    },
    value: "Hold the final word",
    includeInPrompter: false,
    version: 1,
  }];
  const slot = edited.primaryVisualSequence!.slots[0]!;
  if (slot.kind !== "content" || slot.payload.kind !== "visual") {
    throw new Error("Expected a visual content slot in the fixture row");
  }
  slot.payload.sourceUsage = { sourceInFrame: 24 };
  slot.payload.framingPolicy = "cover";
  slot.payload.audioPolicy = "quiet";
  edited.primaryVisualSequence!.slots.push({
    id: id(9012),
    kind: "content",
    relation: { kind: "sequential" },
    boundaryBefore: {
      kind: "spoken_word",
      anchor: {
        blockId: edited.id,
        tokenId: cameraToken.id,
        affinity: "before",
        quotedWord: cameraToken.value,
        anchorVersion: 1,
      },
    },
    payload: { kind: "on_camera", presenterChoiceId: null },
    playoutPolicy: "match_structural_interval",
    version: 1,
  });
  edited.primaryVisualSequence!.version += 1;
  edited.version += 1;
  return edited;
}

describe("saved Stash row edits", () => {
  it("edits an OC/VO camera range and restores it with the original attachment and identities", () => {
    const state = stashFixtureNarration();
    const originalDocument = structuredClone(state.document);
    const current = state.document.stash![0]!.rows[0] as NarrationBlockV2;
    const edited = editNarration(current);

    const result = applyStashRowEditV2(state.document, 1, {
      bundleId: state.bundleId,
      rowId: current.id,
      row: edited,
    });

    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (!result.ok) return;
    expect(result.document).not.toBe(state.document);
    expect(state.document).toEqual(originalDocument);
    expect(result.document.rowEditRevision).toBe(2);
    expect(result.document.stash?.[0]?.rows).toEqual([edited]);
    expect(result.document.stash?.[0]?.rows[0]?.id).toBe(state.originalRow.id);
    expect(result.document.stash?.[0]?.rows[0]?.type).toBe("narration");
    expect(result.document.stash?.[0]?.supportingItems).toEqual([state.supportingItem]);
    expect(result.document.stash?.[0]?.originalGap).toEqual(state.originalGap);
    const originalBase = state.originalRow.primaryVisualSequence!.slots[0]!;
    const editedBase = edited.primaryVisualSequence!.slots[0]!;
    const cameraSlot = edited.primaryVisualSequence!.slots[1]!;
    if (originalBase.kind !== "content" || originalBase.payload.kind !== "visual" || editedBase.kind !== "content" || editedBase.payload.kind !== "visual") {
      throw new Error("Expected the original visual base slot to retain its payload");
    }
    expect(editedBase.id).toBe(originalBase.id);
    expect(editedBase.payload.payloadId).toBe(originalBase.payload.payloadId);
    expect(cameraSlot).toMatchObject({
      id: id(9012),
      kind: "content",
      relation: { kind: "sequential" },
      boundaryBefore: {
        kind: "spoken_word",
        anchor: { tokenId: id(9011), affinity: "before", quotedWord: "there" },
      },
      payload: { kind: "on_camera", presenterChoiceId: null },
    });

    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const restored = applyRowEditV2(loaded.document, 2, {
      kind: "restore_stash",
      bundleId: state.bundleId,
      destination: state.originalGap,
    });
    expect(restored.ok).toBe(true);
    if (!restored.ok) return;
    expect(restored.document.activeDraft.blocks).toEqual([edited]);
    expect(restored.document.activeDraft.supportingItems).toEqual([state.supportingItem]);
    expect(restored.document.activeDraft.blocks[0]?.id).toBe(state.originalRow.id);
    expect(restored.document.rowEditRevision).toBe(3);
  });

  it("edits a visual-only source range and visual settings while parked", () => {
    const document = input();
    const row: VisualOnlyBlockV2 = {
      type: "visual_only",
      id: id(9100),
      orderKey: "z-visual-only",
      version: 1,
      payload: {
        kind: "visual",
        payloadId: id(9101),
        pictureKind: "clip",
        source: { kind: "media_reference", mediaReferenceId: id(9102) },
        audioPolicy: "mute",
        framingPolicy: "contain",
      },
      visualOnlyTiming: {
        kind: "visual_only",
        selectedSourceRange: { startFrame: 12, durationFrames: 24 },
      },
    };
    document.activeDraft.blocks.push(row);
    const bundleId = id(9103);
    const stashed = applyRowEditV2(document, 0, {
      kind: "stash_rows",
      rowIds: [row.id],
      bundleId,
    });
    expect(stashed.ok).toBe(true);
    if (!stashed.ok) return;

    const edited = structuredClone(row);
    edited.visualOnlyTiming.selectedSourceRange = { startFrame: 48, durationFrames: 72 };
    edited.payload.audioPolicy = "full";
    edited.payload.framingPolicy = "cover";
    edited.version += 1;
    const result = applyStashRowEditV2(stashed.document, 1, {
      bundleId,
      rowId: row.id,
      row: edited,
    });

    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    if (!result.ok) return;
    expect(result.document.stash?.[0]?.rows[0]).toEqual(edited);
    expect(result.document.activeDraft.blocks).toEqual(stashed.document.activeDraft.blocks);
  });

  it("reports no-op, stale, missing-target, and row-identity refusals without mutation", () => {
    const state = stashFixtureNarration();
    const row = state.document.stash![0]!.rows[0] as NarrationBlockV2;
    const unchanged = structuredClone(state.document);

    const noOp = applyStashRowEditV2(state.document, 1, {
      bundleId: state.bundleId,
      rowId: row.id,
      row: structuredClone(row),
    });
    expect(noOp.ok).toBe(false);
    expect(noOp.diagnostics[0]?.code).toBe("STASH_ROW_EDIT_NO_CHANGE");
    expect(noOp.document).toBe(state.document);
    const reorderedKeys = Object.fromEntries(Object.entries(row).reverse()) as NarrationBlockV2;
    const reordered = applyStashRowEditV2(state.document, 1, { bundleId: state.bundleId, rowId: row.id, row: reorderedKeys });
    expect(reordered.diagnostics[0]?.code).toBe("STASH_ROW_EDIT_NO_CHANGE");
    expect(reordered.document).toBe(state.document);

    const stale = applyStashRowEditV2(state.document, 0, {
      bundleId: state.bundleId,
      rowId: row.id,
      row: editNarration(row),
    });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(state.document);

    const missing = applyStashRowEditV2(state.document, 1, {
      bundleId: id(9999),
      rowId: row.id,
      row: editNarration(row),
    });
    expect(missing.diagnostics[0]?.code).toBe("STASH_BUNDLE_NOT_FOUND");
    expect(missing.document).toBe(state.document);

    const changedIdentity = editNarration(row);
    changedIdentity.id = id(9998);
    const identity = applyStashRowEditV2(state.document, 1, {
      bundleId: state.bundleId,
      rowId: row.id,
      row: changedIdentity,
    });
    expect(identity.diagnostics[0]?.code).toBe("STASH_ROW_IDENTITY_INVALID");
    expect(identity.document).toBe(state.document);
    expect(state.document).toEqual(unchanged);
  });

  it("rejects new schema and duplicate-identity errors", () => {
    const state = stashFixtureNarration();
    const row = state.document.stash![0]!.rows[0] as NarrationBlockV2;
    const invalidSchema = editNarration(row);
    invalidSchema.version = 0;
    const schemaResult = applyStashRowEditV2(state.document, 1, {
      bundleId: state.bundleId,
      rowId: row.id,
      row: invalidSchema,
    });
    expect(schemaResult.ok).toBe(false);
    expect(schemaResult.diagnostics.map((item) => item.code)).toContain("SCHEMA_INVALID");
    expect(schemaResult.document).toBe(state.document);

    const duplicateIdentity = editNarration(row);
    duplicateIdentity.primaryVisualSequence!.id = duplicateIdentity.id;
    const identityResult = applyStashRowEditV2(state.document, 1, {
      bundleId: state.bundleId,
      rowId: row.id,
      row: duplicateIdentity,
    });
    expect(identityResult.ok).toBe(false);
    expect(identityResult.diagnostics.map((item) => item.code)).toContain("ENTITY_ID_DUPLICATE");
    expect(identityResult.document).toBe(state.document);
  });
});
