import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
} from "@vera/contracts/authoring-v2";
import { applyStashRowEditV2 } from "../src/authoring-v2-stash.js";
import type {
  CompilerDependenciesV2,
  NarrationBlockV2,
  RowAudioSpanIntentV2,
  RowTransitionIntentV2,
  ScriptDocumentV2,
  SupportingItemV2,
} from "@vera/contracts/v2";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import { exportPrompter } from "../src/prompter-export.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const fixturePath = `${repositoryRoot}tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json`;
const id = (value: number): string =>
  `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const exportSettings = {
  includeSectionNavigation: true,
  includeBeatNumbers: true,
} as const;

interface CompilerInput {
  document: ScriptDocumentV2;
  dependencies: CompilerDependenciesV2;
}

function input(): CompilerInput {
  return JSON.parse(readFileSync(fixturePath, "utf8")) as CompilerInput;
}

function stashedRow(): NarrationBlockV2 {
  const rowId = id(9001);
  const tokenId = id(9002);
  const payloadId = id(9003);
  const text = "STASHED";
  return {
    type: "narration",
    id: rowId,
    orderKey: "z-stashed",
    text,
    tokens: [{ id: tokenId, value: text, startOffset: 0, endOffset: text.length }],
    primaryVisualSequence: {
      id: id(9004),
      version: 1,
      slots: [{
        id: id(9005),
        kind: "content",
        relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: {
          kind: "visual",
          payloadId,
          pictureKind: "clip",
          source: { kind: "media_reference", mediaReferenceId: id(9006) },
          sourceUsage: { sourceInFrame: 0 },
          audioPolicy: "mute",
          framingPolicy: "contain",
        },
        playoutPolicy: "match_structural_interval",
        version: 1,
      }],
    },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "active",
    notes: [],
    version: 1,
  };
}

function citation(row: NarrationBlockV2): SupportingItemV2 {
  const token = row.tokens[0];
  const anchor = {
    blockId: row.id,
    tokenId: token.id,
    affinity: "before" as const,
    quotedWord: token.value,
    anchorVersion: 1,
  };
  const attachment = { kind: "word" as const, anchor };
  return {
    id: id(9007),
    version: 1,
    orderKey: "stashed-citation",
    role: "citation",
    content: "Citation stored with the stashed row",
    placement: { kind: "point", anchor: attachment },
    displayAttachment: attachment,
  };
}

function payloadIds(row: NarrationBlockV2): string[] {
  return row.primaryVisualSequence?.slots.flatMap((slot) =>
    slot.kind === "content" && slot.payload.kind !== "on_camera"
      ? [slot.payload.payloadId]
      : [],
  ) ?? [];
}

function activeNarration(document: ScriptDocumentV2): NarrationBlockV2 {
  const row = document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.state === "active",
  );
  if (!row) throw new Error("Expected an active fixture narration row");
  return row;
}

function mediaNeeds(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2) {
  return resolveMediaRequirementsV2(document, {
    timing: dependencies.narrationTimingMaps,
    ...(dependencies.narrationBoundaryEvidence
      ? { boundaryEvidence: dependencies.narrationBoundaryEvidence }
      : {}),
    defaults: dependencies.authoringDefaults,
    sourceDescriptors: dependencies.occurrenceResolutions,
    frameRate: dependencies.timeline.frameRate,
  });
}

describe("row-edit consumers", () => {
  it("keeps stashed rows and their support out of prompter, timeline, and media needs", () => {
    const { document, dependencies } = input();
    const activeRow = activeNarration(document);
    const row = stashedRow();
    const supportingItem = citation(row);
    document.activeDraft.blocks.push(row);
    document.activeDraft.supportingItems.push(supportingItem);

    const edit = applyRowEditV2(document, 0, {
      kind: "stash_rows",
      rowIds: [row.id],
      bundleId: id(9008),
    });

    expect(edit.ok).toBe(true);
    expect(edit.document.activeDraft.blocks.map((block) => block.id)).toEqual(
      document.activeDraft.blocks.filter((block) => block.id !== row.id).map((block) => block.id),
    );
    expect(edit.document.stash?.[0]?.rows).toEqual([row]);
    expect(edit.document.stash?.[0]?.supportingItems).toEqual([supportingItem]);
    expect(edit.document.activeDraft.supportingItems).toEqual([]);

    const editedRow = structuredClone(row);
    editedRow.text = "EDITED STASHED";
    editedRow.tokens = [{
      ...editedRow.tokens[0],
      value: editedRow.text,
      startOffset: 0,
      endOffset: editedRow.text.length,
    }];
    const slot = editedRow.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Expected a visual content slot");
    slot.payload.sourceUsage = { sourceInFrame: 24 };
    slot.payload.framingPolicy = "cover";
    const stashEdit = applyStashRowEditV2(edit.document, edit.document.rowEditRevision ?? 0, {
      bundleId: id(9008),
      rowId: row.id,
      row: editedRow,
    });
    expect(stashEdit.ok).toBe(true);
    if (!stashEdit.ok) return;
    expect(stashEdit.document.stash?.[0]?.rows).toEqual([editedRow]);
    expect(stashEdit.document.stash?.[0]?.supportingItems).toEqual([supportingItem]);

    const exported = exportPrompter(stashEdit.document, exportSettings);
    expect(exported.ok).toBe(true);
    if (!exported.ok) return;
    expect(exported.sidecar.beats.map((beat) => beat.expectedText)).toEqual([activeRow.text]);
    expect(exported.text).not.toContain(row.text);
    expect(exported.text).not.toContain(editedRow.text);
    expect(exported.text).not.toContain(supportingItem.content);

    const compiled = compileTimelineV2(stashEdit.document, dependencies);
    expect(compiled.ok).toBe(true);
    if (!compiled.ok) return;
    expect(compiled.manifest.timeline.durationFrames).toBe(96);
    expect(compiled.manifest.events.some((event) =>
      event.provenance.blockId === row.id ||
      (event.provenance.payloadId !== null && payloadIds(row).includes(event.provenance.payloadId)),
    )).toBe(false);

    const needs = mediaNeeds(stashEdit.document, dependencies);
    expect(needs.ok).toBe(true);
    if (!needs.ok) return;
    expect(needs.durationFrames).toBe(96);
    expect(needs.requirements.map((requirement) => requirement.payloadId)).toEqual(payloadIds(activeRow));
    expect(needs.requirements.some((requirement) => payloadIds(row).includes(requirement.payloadId))).toBe(false);
  });

  it("restores the fixture row through serialization and returns its original consumer outputs", () => {
    const { document, dependencies } = input();
    const originalExport = exportPrompter(document, exportSettings);
    const originalCompile = compileTimelineV2(document, dependencies);
    const originalNeeds = mediaNeeds(document, dependencies);
    expect(originalExport.ok).toBe(true);
    expect(originalCompile.ok).toBe(true);
    expect(originalNeeds.ok).toBe(true);
    if (!originalExport.ok || !originalCompile.ok || !originalNeeds.ok) return;

    const row = activeNarration(document);
    const bundleId = id(9010);
    const stashed = applyRowEditV2(document, 0, {
      kind: "stash_rows",
      rowIds: [row.id],
      bundleId,
    });
    expect(stashed.ok).toBe(true);
    if (!stashed.ok) return;
    expect(stashed.document.activeDraft.blocks).toEqual([]);

    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(stashed.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const restored = applyRowEditV2(loaded.document, loaded.document.rowEditRevision ?? 0, {
      kind: "restore_stash",
      bundleId,
      destination: { sectionId: null, afterRowId: null, beforeRowId: null },
    });
    expect(restored.ok).toBe(true);
    if (!restored.ok) return;
    expect(restored.document.activeDraft.blocks).toEqual([row]);

    const restoredExport = exportPrompter(restored.document, exportSettings);
    const restoredCompile = compileTimelineV2(restored.document, dependencies);
    const restoredNeeds = mediaNeeds(restored.document, dependencies);
    expect(restoredExport.ok).toBe(true);
    expect(restoredCompile.ok).toBe(true);
    expect(restoredNeeds.ok).toBe(true);
    if (!restoredExport.ok || !restoredCompile.ok || !restoredNeeds.ok) return;

    expect(restoredExport.text).toBe(originalExport.text);
    expect(restoredExport.sidecarJson).toBe(originalExport.sidecarJson);
    expect(restoredCompile.manifest.events).toEqual(originalCompile.manifest.events);
    expect(restoredCompile.manifest.timeline.durationFrames).toBe(originalCompile.manifest.timeline.durationFrames);
    expect(restoredNeeds.requirements).toEqual(originalNeeds.requirements);
    expect(restoredNeeds.durationFrames).toBe(originalNeeds.durationFrames);
  });

  it("makes restored edited text eligible again, requiring fresh narration timing rather than reusing stale audio", () => {
    const { document, dependencies } = input();
    const row = activeNarration(document);
    const bundleId = id(9011);
    const stashed = applyRowEditV2(document, 0, { kind: "stash_rows", rowIds: [row.id], bundleId });
    expect(stashed.ok).toBe(true);
    const editedRow = structuredClone(row);
    editedRow.text = "goodbye";
    editedRow.tokens[0] = { ...editedRow.tokens[0], value: "goodbye", endOffset: 7 };
    editedRow.version++;
    const edited = applyStashRowEditV2(stashed.document, 1, { bundleId, rowId: row.id, row: editedRow });
    expect(edited.ok).toBe(true);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(edited.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const restored = applyRowEditV2(loaded.document, 2, { kind: "restore_stash", bundleId, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(restored.ok).toBe(true);
    expect(restored.document.activeDraft.blocks).toEqual([editedRow]);
    const exported = exportPrompter(restored.document, exportSettings);
    expect(exported.ok).toBe(true);
    if (exported.ok) expect(exported.text).toContain("goodbye");
    const compiled = compileTimelineV2(restored.document, dependencies);
    const needs = mediaNeeds(restored.document, dependencies);
    expect(compiled.ok).toBe(false);
    expect(needs.ok).toBe(false);
    if (!compiled.ok) expect(compiled.diagnostics.some((item) => item.code === "STALE_TIMING_MAP")).toBe(true);
    if (!needs.ok) expect(needs.diagnostics.some((item) => item.code === "STALE_TIMING_MAP")).toBe(true);
  });

  it.each([
    ["row audio spans", "ROW_AUDIO_RUNTIME_UNAVAILABLE"],
    ["active cross-row transitions", "ROW_TRANSITION_RUNTIME_UNAVAILABLE"],
  ] as const)("refuses unsupported %s in both timeline and media-needs consumers", (_label, expectedCode) => {
    const { document, dependencies } = input();
    const row = activeNarration(document);
    if (expectedCode === "ROW_AUDIO_RUNTIME_UNAVAILABLE") {
      const span: RowAudioSpanIntentV2 = {
        id: id(9020),
        startRowId: row.id,
        endRowId: row.id,
        source: {
          mediaReferenceId: id(9021),
          artifactId: id(9022),
          artifactVersion: 1,
          contentHash: `sha256:${"b".repeat(64)}`,
        },
        settings: {},
      };
      document.rowAudioSpans = [span];
    } else {
      const next = stashedRow();
      document.activeDraft.blocks.push(next);
      const transition: RowTransitionIntentV2 = {
        id: id(9023),
        fromRowId: row.id,
        toRowId: next.id,
        effect: "crossfade",
        settings: { frames: 6 },
        state: "active",
      };
      document.rowTransitions = [transition];
    }

    const compiled = compileTimelineV2(document, dependencies);
    expect(compiled.ok).toBe(false);
    if (compiled.ok) return;
    expect(compiled.diagnostics.map((diagnostic) => diagnostic.code)).toContain(expectedCode);

    const needs = mediaNeeds(document, dependencies);
    expect(needs.ok).toBe(false);
    if (needs.ok) return;
    expect(needs.diagnostics.map((diagnostic) => diagnostic.code)).toContain(expectedCode);
  });
});
