import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { applyStashRowEditV2 } from "../src/authoring-v2-stash.js";
import {
  applyRowEditV2,
  createRowEditSessionV2,
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
  const token = row.tokens[0]!;
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
  const token = edited.tokens[0]!;
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
  it("preserves the typed visual, token and anchored citation identities over two explicit cross-section returns", () => {
    const state = stashFixtureNarration();
    const original = structuredClone(state.document.stash![0]!.rows[0]);
    const firstSection = id(98500);
    const laterSection = id(98501);
    const document = structuredClone(state.document);
    document.activeDraft.blocks.push(
      { type: "section", id: firstSection, title: "First", orderKey: "1", version: 1 },
      { type: "section", id: laterSection, title: "Later", orderKey: "2", version: 1 },
    );
    const placed = applyRowEditV2(document, 1, {
      kind: "restore_stash", bundleId: state.bundleId,
      destination: { sectionId: laterSection, afterRowId: null, beforeRowId: null },
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.activeDraft.blocks.at(-1)).toEqual(original);
    expect(placed.document.activeDraft.supportingItems).toEqual([state.supportingItem]);
    const returned = applyRowEditV2(placed.document, 2, {
      kind: "stash_rows", rowIds: [original.id], bundleId: id(98502),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(returned.document.stash?.flatMap((bundle) => bundle.supportingItems)).toContainEqual(state.supportingItem);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(returned.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const restored = applyRowEditV2(loaded.document, 3, {
      kind: "restore_stash", bundleId: id(98502),
      destination: { sectionId: firstSection, afterRowId: null, beforeRowId: null },
    });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(restored.document.activeDraft.blocks[1]).toEqual(original);
    expect(restored.document.activeDraft.supportingItems).toEqual([state.supportingItem]);
    expect(restored.document.extras).toEqual([]);
    expect(state.document.stash![0]!.rows[0]).toEqual(original);
  });

  it("preserves frozen return history through active edits and an atomic saved-row return", () => {
    const state = stashFixtureNarration();
    const placed = applyRowEditV2(state.document, 1, {
      kind: "place_stash_rows", rowIds: [state.originalRow.id], destination: state.originalGap,
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const active = placed.document.activeDraft.blocks.find((row) => row.id === state.originalRow.id) as NarrationBlockV2;
    const historical = structuredClone(active.stashOrigin);
    expect(historical).toMatchObject({ kind: "row", precedingSiblingRowIds: [], followingSiblingRowIds: [] });
    const replacement = structuredClone(active);
    replacement.notes.push("Saved edited version");
    replacement.version += 1;
    const session = createRowEditSessionV2(placed.document);
    const edited = session.apply({ kind: "edit_row", rowId: active.id, row: replacement });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    const editedRow = edited.document.activeDraft.blocks.find((row) => row.id === active.id) as NarrationBlockV2;
    expect(editedRow.stashOrigin).toEqual({ ...historical, returnEligible: false });
    const returned = session.apply({ kind: "stash_rows", rowIds: [active.id], bundleId: id(98000) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(returned.document.stashOutline?.find((entry) => entry.rowId === active.id)?.kind).toBe("row");
    expect(returned.document.stash?.flatMap((bundle) => bundle.rows).find((row) => row.id === active.id)).toMatchObject({ notes: ["Saved edited version"] });
    expect(returned.document.stash?.flatMap((bundle) => bundle.supportingItems)).toContainEqual(state.supportingItem);
    const undo = session.undo();
    expect(undo.ok).toBe(true);
    expect(undo.document.activeDraft.blocks.find((row) => row.id === active.id)).toEqual(editedRow);
  });
  it("prevents ordinary whole-row edits from replacing or secretly trimming an exclusive footage attachment", () => {
    const { document, bundleId } = stashFixtureNarration();
    const original = document.stash!.find((bundle) => bundle.id === bundleId)!.rows[0] as NarrationBlockV2;
    const clip: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(92000), orderKey: "owned-clip", version: 1,
      payload: {
        kind: "visual", payloadId: id(92001), pictureKind: "clip",
        source: { kind: "media_reference", mediaReferenceId: id(92002) },
        audioPolicy: "mute", framingPolicy: "contain",
      },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 4, durationFrames: 40 } },
    };
    original.attachedFootage = { clip };
    document.stashOutline = [{ rowId: original.id, kind: "note", sectionId: null, parentRowId: null }];
    const revision = document.rowEditRevision ?? 0;
    const before = JSON.stringify(document);
    const noClip = structuredClone(original);
    delete noClip.attachedFootage;
    const trimmed = structuredClone(original);
    trimmed.attachedFootage!.clip.visualOnlyTiming.selectedSourceRange = { startFrame: 10, durationFrames: 20 };
    for (const forged of [noClip, trimmed]) {
      const result = applyStashRowEditV2(document, revision, { bundleId, rowId: original.id, row: forged });
      expect(result.ok).toBe(false);
      expect(result.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_REVIEW_REQUIRED");
      expect(result.document).toBe(document);
      const routed = applyRowEditV2(document, revision, { kind: "edit_row", rowId: original.id, row: forged });
      expect(routed.ok).toBe(false);
      expect(routed.document).toBe(document);
      expect(JSON.stringify(document)).toBe(before);
    }
    const safe = structuredClone(original);
    safe.notes.push("ordinary saved annotation");
    safe.version++;
    const accepted = applyStashRowEditV2(document, revision, { bundleId, rowId: original.id, row: safe });
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    if (accepted.ok) {
      const note = accepted.document.stash!.find((bundle) => bundle.id === bundleId)!.rows[0] as NarrationBlockV2;
      expect(note.attachedFootage?.clip).toEqual(clip);
    }
  });
  it("edits a literal compact note as raw text, preserves intent, and refuses implicit speech and corrupt tokens", () => {
    const document: ScriptDocumentV2 = {
      schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Literal note edits",
      activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
      liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
    };
    const row = structuredClone(input().activeDraft.blocks.find((item): item is NarrationBlockV2 => item.type === "narration")!);
    row.id = id(97000);
    row.text = "[outer [inner]] unmatched] 😀";
    row.tokens = [...row.text.matchAll(/\S+/gu)].map((word, index) => ({
      id: id(97100 + index), value: word[0], startOffset: word.index,
      endOffset: word.index + word[0].length,
    }));
    const created = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(97500), row,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    if (!created.ok) return;
    const original = created.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(original.plainDirection).toBe(true);
    expect(original.text).toBe(row.text);

    const session = createRowEditSessionV2(created.document);
    const newText = "  literal] [nested [more]] '😀'\nend [ ";
    const replacement = structuredClone(original);
    replacement.text = newText;
    replacement.tokens = [...newText.matchAll(/\S+/gu)].map((word, index) => ({
      id: id(97700 + index), value: word[0], startOffset: word.index,
      endOffset: word.index + word[0].length, spoken: false as const,
    }));
    replacement.version += 1;
    const edited = session.apply({ kind: "edit_row", rowId: row.id, row: replacement });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    expect((session.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe(newText);
    expect((session.document.stash![0]!.rows[0] as NarrationBlockV2).plainDirection).toBe(true);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document)).ok).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect((session.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe(row.text);
    expect((session.document.stash![0]!.rows[0] as NarrationBlockV2).tokens).toEqual(original.tokens);

    const implicitSpeech = structuredClone(original);
    delete implicitSpeech.plainDirection;
    implicitSpeech.tokens.forEach((token) => { delete token.spoken; });
    const refused = applyStashRowEditV2(created.document, 1, { bundleId: id(97500), rowId: row.id, row: implicitSpeech });
    expect(refused.diagnostics[0]?.code).toBe("STASH_ROW_INTENT_INVALID");
    expect(refused.document).toBe(created.document);

    const corrupt = structuredClone(replacement);
    corrupt.tokens[0]!.spoken = true;
    const invalid = applyStashRowEditV2(created.document, 1, { bundleId: id(97500), rowId: row.id, row: corrupt });
    expect(invalid.ok).toBe(false);
    expect(invalid.diagnostics.some((item) => item.code === "PLAIN_DIRECTION_INTENT_INVALID")).toBe(true);
    expect(invalid.document).toBe(created.document);
    expect(created.document.stash![0]!.rows[0]).toEqual(original);
  });

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
