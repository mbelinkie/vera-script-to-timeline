import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import { createRowEditSessionV2, deserializeAuthoringDocumentV2, serializeAuthoringDocumentV2 } from "../src/authoring-v2-rows.js";
import { indexResearchClipUsageV2 } from "../src/research-clip-usage-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, RowAudioSpanIntentV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
import { researchOccurrence } from "./issue-367-fixture.js";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
type Frozen = { document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 };
const fixture = (): Frozen => JSON.parse(readFileSync(
  `${root}tests/data/authoring_v2/issue_173/compiler/visual-only-image-still-25fps-default.input.golden.json`, "utf8",
)) as Frozen;

function sequence(): Frozen {
  const { document, dependencies } = fixture();
  const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
  row.visualOnlyTiming = { kind: "visual_only", durationOverrideMs: 4000 };
  const clipId = id(3101);
  const secondStillId = id(3102);
  row.additionalVisuals = [
    { payload: { kind: "visual", payloadId: clipId, pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(60) },
      audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 10, durationFrames: 50 } } },
    { payload: { ...row.payload, payloadId: secondStillId },
      visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 2500 } },
  ];
  const original = dependencies.occurrenceResolutions[0]!;
  const originalBinding = dependencies.preparedMedia[0]!;
  const clip = structuredClone(original);
  clip.payloadId = clipId;
  clip.preparedMediaRequirementKey = "prep:clip-in-sequence";
  clip.logicalSourceBounds.endFrame = 100;
  clip.sourceFrameMap.decodedPackageFrameCount = 100;
  clip.occurrenceSourceInFrame = 10;
  clip.selectedSourceRange = { startFrame: 10, endFrame: 60 };
  const clipBinding = structuredClone(originalBinding);
  clipBinding.requirementKey = clip.preparedMediaRequirementKey;
  clipBinding.requestedRange.sourceInFrame = 10;
  clipBinding.requestedRange.duration = { numerator: 2, denominator: 1 };
  clipBinding.timeMapping.sourceOrigin = { numerator: 2, denominator: 5 };
  clipBinding.timeMapping.sourceFrameMap = structuredClone(clip.sourceFrameMap);
  clipBinding.verification.decodedFrameCount = 50;
  const third = structuredClone(original);
  third.payloadId = secondStillId;
  third.preparedMediaRequirementKey = "prep:second-still";
  const thirdBinding = structuredClone(originalBinding);
  thirdBinding.requirementKey = third.preparedMediaRequirementKey;
  dependencies.occurrenceResolutions.push(clip, third);
  dependencies.preparedMedia.push(clipBinding, thirdBinding);
  return { document, dependencies };
}

function musicCue(cueId: number, rowId: string): RowAudioSpanIntentV2 {
  return {
    id: id(cueId), startRowId: rowId, endRowId: rowId,
    source: {
      mediaReferenceId: id(cueId + 1), artifactId: id(cueId + 2), artifactVersion: 1,
      contentHash: `sha256:${"b".repeat(64)}`,
    },
    settings: { gainDb: -12 },
    timing: { sourceInFrame: 24, sourceOutFrame: 96, timelineIn: { kind: "row_edge", blockId: rowId, edge: "start" } },
  };
}

describe("#585 visuals-only ordered cards", () => {
  function narratedDestination(legacy: VisualOnlyBlockV2, twoStills = false): NarrationBlockV2 {
    const row: NarrationBlockV2 = {
      type: "narration", id: id(74603), orderKey: "z0", version: 1,
      state: "active", timingPolicy: "narration_spine", text: "one two",
      tokens: [
        { id: id(74604), value: "one", startOffset: 0, endOffset: 3 },
        { id: id(74605), value: "two", startOffset: 4, endOffset: 7 },
      ],
      notes: [], overlayEvents: [],
      primaryVisualSequence: { id: id(74606), version: 1, slots: [{
        id: id(74607), version: 1, kind: "content", relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" }, playoutPolicy: "match_structural_interval",
        payload: { ...legacy.payload, payloadId: id(74608), audioPolicy: "mute", sourceUsage: null },
      }] },
    };
    if (twoStills) row.primaryVisualSequence!.slots.push({
      id: id(74610), version: 1, kind: "content", relation: { kind: "sequential" },
      boundaryBefore: { kind: "spoken_word", anchor: {
        blockId: row.id, tokenId: id(74605), affinity: "before", quotedWord: "two", anchorVersion: 1,
      } }, playoutPolicy: "match_structural_interval",
      payload: { ...legacy.payload, payloadId: id(74611), audioPolicy: "mute", sourceUsage: null },
    });
    return row;
  }

  it("#746 preserves the inherited hold yet lets the still move back onto narration", () => {
    const { document, dependencies } = fixture();
    const legacy = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const session = createRowEditSessionV2(document, dependencies.authoringDefaults.visualOnlyStillDurationMs);
    const appended = session.apply({ kind: "add_visual_to_wordless_row", rowId: legacy.id,
      payloadId: id(74601), slotId: id(74602), visualType: "onscreen_placeholder" });
    expect(appended.ok, JSON.stringify(appended.diagnostics)).toBe(true);
    const compiled = compileTimelineV2(appended.document, dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (!compiled.ok) throw new Error("Legacy fixture did not compile");
    expect(compiled.manifest.events.filter(e => e.kind === "primary_visual" || e.kind === "placeholder")
      .map(e => e.recordRange)).toEqual([
      { startFrame: 0, endFrame: 75 }, { startFrame: 75, endFrame: 175 },
    ]);
    const before = structuredClone(appended.document);
    expect((before.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming).toEqual({
      kind: "visual_only", durationOverrideMs: 3000, systemPreservedDefaultHold: true,
    });
    const target = narratedDestination(legacy);
    before.activeDraft.blocks.push(target);
    expect(validateScriptDocumentV2(before).valid).toBe(true);
    const custom = structuredClone(before);
    delete (custom.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming.systemPreservedDefaultHold;
    const customSession = createRowEditSessionV2(custom, 3000);
    const refused = customSession.apply({ kind: "move_wordless_visual", sourceRowId: legacy.id,
      destinationRowId: target.id, payloadId: legacy.payload.payloadId,
      destinationSlotId: id(74609), expectedDestinationSequenceVersion: 1 });
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics.map(d => d.code)).toContain("WORDLESS_TIMING_UNSUPPORTED");
    expect(refused.document).toEqual(custom);
    expect(customSession.undoDepth).toBe(0);
    const moveSession = createRowEditSessionV2(before, 3000);
    const moved = moveSession.apply({ kind: "move_wordless_visual", sourceRowId: legacy.id,
      destinationRowId: target.id, payloadId: legacy.payload.payloadId,
      destinationSlotId: id(74609), expectedDestinationSequenceVersion: 1 });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(moved.document.activeDraft.blocks.find(b => b.id === target.id)).toMatchObject({
      type: "narration", unattachedVisuals: [{
        slotId: id(74609), payload: { ...legacy.payload, sourceUsage: null },
      }],
    });
    expect(moved.document.activeDraft.blocks[0]).toMatchObject({
      payload: { payloadId: id(74601) }, visualOnlyTiming: { durationOverrideMs: 4000 },
    });
    expect(moveSession.undoDepth).toBe(1);
    expect(moveSession.undo().document.activeDraft.blocks).toEqual(before.activeDraft.blocks);
  });

  it("#746 restores cleared narration after moving in an inherited still", () => {
    const { document } = fixture();
    const legacy = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const target = narratedDestination(legacy, true);
    document.activeDraft.blocks.push(target);
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const session = createRowEditSessionV2(document, 3000);
    const cleared = session.apply({ kind: "edit_narration_text", rowId: target.id,
      startOffset: 0, endOffset: target.text.length, insertedText: "", editId: id(74612) });
    expect(cleared.ok, JSON.stringify(cleared.diagnostics)).toBe(true);
    const moved = session.apply({ kind: "move_wordless_visual", sourceRowId: legacy.id,
      destinationRowId: target.id, payloadId: legacy.payload.payloadId,
      destinationSlotId: id(74613), replacementPayloadId: id(74614) });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    const beforeRestore = moved.document.activeDraft.blocks.find(b => b.id === target.id);
    expect(beforeRestore).toMatchObject({
      type: "visual_only", additionalVisuals: [
        { visualOnlyTiming: { durationOverrideMs: 4000 } },
        { payload: { payloadId: legacy.payload.payloadId }, visualOnlyTiming: {
          durationOverrideMs: 3000, systemPreservedDefaultHold: true,
        } },
      ],
    });
    const restored = session.apply({ kind: "edit_narration_text", rowId: target.id,
      startOffset: 0, endOffset: 0, insertedText: "new words", editId: id(74615) });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(restored.document.activeDraft.blocks.find(b => b.id === target.id)).toMatchObject({
      type: "narration", text: "new words", primaryVisualSequence: { id: id(74606) },
      unattachedVisuals: [
        { slotId: id(74607), payload: { payloadId: id(74608) } },
        { slotId: id(74610), payload: { payloadId: id(74611) } },
        { slotId: id(74613), payload: { payloadId: legacy.payload.payloadId, sourceUsage: null } },
      ],
    });
    expect(session.undo().document.activeDraft.blocks).toEqual(moved.document.activeDraft.blocks);
  });

  it("#725 keeps a legacy three-second still when appending a new four-second card", () => {
    const { document, dependencies } = fixture();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const session = createRowEditSessionV2(document, dependencies.authoringDefaults.visualOnlyStillDurationMs);
    const result = session.apply({ kind: "add_visual_to_wordless_row", rowId: row.id,
      payloadId: id(7251), slotId: id(7252), visualType: "onscreen_placeholder" });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const compiled = compileTimelineV2(result.document, dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (!compiled.ok) return;
    expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual" || event.kind === "placeholder")
      .map((event) => event.recordRange)).toEqual([
      { startFrame: 0, endFrame: 75 }, { startFrame: 75, endFrame: 175 },
    ]);
    expect(result.document.activeDraft.blocks[0]).toMatchObject({
      visualOnlyTiming: { durationOverrideMs: 3000 },
      additionalVisuals: [{ visualOnlyTiming: { durationOverrideMs: 4000 } }],
    });
    expect(session.undo().document.activeDraft.blocks[0]).toEqual(row);
  });

  it("#725 keeps the effective holds on both sides of a wordless move", () => {
    const { document } = fixture();
    const source = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const destination = structuredClone(source);
    destination.id = id(7253);
    destination.orderKey = "b0";
    destination.payload.payloadId = id(7254);
    source.additionalVisuals = [{ payload: { ...source.payload, payloadId: id(7255) },
      visualOnlyTiming: { kind: "visual_only" } }];
    document.activeDraft.blocks.push(destination);
    const session = createRowEditSessionV2(document, 3200);
    const result = session.apply({ kind: "move_wordless_visual", sourceRowId: source.id,
      destinationRowId: destination.id, payloadId: source.payload.payloadId });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks).toMatchObject([
      { payload: { payloadId: id(7255) }, visualOnlyTiming: { durationOverrideMs: 4000 } },
      { visualOnlyTiming: { durationOverrideMs: 3200 }, additionalVisuals: [
        { payload: { payloadId: source.payload.payloadId }, visualOnlyTiming: { durationOverrideMs: 4000 } },
      ] },
    ]);
    expect(session.undo().document.activeDraft.blocks).toEqual(document.activeDraft.blocks);
  });

  it("#725 gives two stills explicit four-second holds when narration is cleared", () => {
    const { document, dependencies } = sequence();
    const visualRow = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const stills = [visualRow.payload, visualRow.additionalVisuals![1]!.payload] as const;
    const row: NarrationBlockV2 = {
      type: "narration", id: visualRow.id, orderKey: visualRow.orderKey, version: 1,
      state: "active", timingPolicy: "narration_spine", text: "one two",
      tokens: [{ id: id(7256), value: "one", startOffset: 0, endOffset: 3 },
        { id: id(7257), value: "two", startOffset: 4, endOffset: 7 }],
      notes: [], overlayEvents: [],
      primaryVisualSequence: { id: id(7258), version: 1, slots: [{
        id: id(7259), version: 1, kind: "content", relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" }, playoutPolicy: "match_structural_interval",
        payload: { ...stills[0], audioPolicy: "mute", sourceUsage: null },
      }, {
        id: id(7260), version: 1, kind: "content", relation: { kind: "sequential" },
        boundaryBefore: { kind: "spoken_word", anchor: {
          blockId: visualRow.id, tokenId: id(7257), affinity: "before", quotedWord: "two", anchorVersion: 1,
        } }, playoutPolicy: "match_structural_interval",
        payload: { ...stills[1], audioPolicy: "mute", sourceUsage: null },
      }] },
    };
    dependencies.occurrenceResolutions.splice(1, 1);
    dependencies.preparedMedia.splice(1, 1);
    document.activeDraft.blocks[0] = row;
    const session = createRowEditSessionV2(document);
    const result = session.apply({ kind: "edit_narration_text", rowId: row.id,
      startOffset: 0, endOffset: row.text.length, insertedText: "", editId: id(7261) });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks[0]).toMatchObject({
      type: "visual_only", visualOnlyTiming: { durationOverrideMs: 4000 },
      additionalVisuals: [{ visualOnlyTiming: { durationOverrideMs: 4000 } }],
    });
    const compiled = compileTimelineV2(result.document, dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (compiled.ok) expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual")
      .map((event) => event.recordRange)).toEqual([
      { startFrame: 0, endFrame: 100 }, { startFrame: 100, endFrame: 200 },
    ]);
  });

  it("#621 appends independent four-second placeholders, keeps order across save/reload and one-step Undo", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const session = createRowEditSessionV2(document);
    const beforeCount = row.additionalVisuals!.length;
    const result = session.apply({ kind: "add_visual_to_wordless_row", rowId: row.id,
      payloadId: id(94111), slotId: id(94112), visualType: "onscreen_placeholder" });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(session.undoDepth).toBe(1);
    const actual = result.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(actual.additionalVisuals).toHaveLength(beforeCount + 1);
    expect(actual.additionalVisuals!.at(-1)!.visualOnlyTiming.durationOverrideMs).toBe(4000);
    const copy = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(copy).toEqual({ ok: true, document: result.document });
    expect(session.undo().document.activeDraft.blocks[0]).toEqual(row);
    const bad = createRowEditSessionV2(document).apply({ kind: "add_visual_to_wordless_row", rowId: row.id,
      payloadId: row.payload.payloadId, slotId: id(94113), visualType: "onscreen_placeholder" });
    expect(bad.ok).toBe(false);
    expect(bad.diagnostics.map((item) => item.code)).toContain("VISUAL_ID_DUPLICATE");
  });
  it("stores an explicit selected music cue, keeps the fixed hold, and makes it read-only", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const first = musicCue(9101, row.id);
    const second = musicCue(9201, row.id);
    row.visualOnlyTiming.durationOverrideMs = 2500;
    document.rowAudioSpans = [first, second];
    const session = createRowEditSessionV2(document);

    const matched = session.apply({
      kind: "set_visual_only_audio_match", rowId: row.id, payloadId: row.payload.payloadId, cueId: second.id,
    });
    expect(matched.ok, JSON.stringify(matched.diagnostics)).toBe(true);
    const changed = matched.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(changed.visualOnlyTiming).toMatchObject({ durationOverrideMs: 2500, matchAudioDuration: { cueId: second.id } });
    expect(changed.visualOnlyTiming.matchAudioDuration?.cueId).not.toBe(first.id);

    const hold = session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: row.payload.payloadId, holdSeconds: 5 });
    expect(hold.ok).toBe(false);
    expect(hold.diagnostics.map((item) => item.code)).toContain("VISUAL_HOLD_MATCHED");
    const duplicate = session.apply({
      kind: "set_visual_only_audio_match", rowId: row.id, payloadId: row.additionalVisuals![1]!.payload.payloadId, cueId: second.id,
    });
    expect(duplicate.ok).toBe(false);
    expect(duplicate.diagnostics).toContainEqual(expect.objectContaining({ code: "MUSIC_MATCH_INVALID", entityId: row.additionalVisuals![1]!.payload.payloadId }));
    expect(session.undoDepth).toBe(1);
  });

  it("does not opt into matching when a cue is merely added, and refuses an absent cue", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const cue = musicCue(9301, row.id);
    document.rowAudioSpans = [cue];
    expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
    expect(row.visualOnlyTiming.matchAudioDuration).toBeUndefined();

    const result = createRowEditSessionV2(document).apply({
      kind: "set_visual_only_audio_match", rowId: row.id, payloadId: row.payload.payloadId, cueId: id(9399),
    });
    expect(result.ok).toBe(false);
    expect(result.diagnostics.map((item) => item.code)).toContain("VISUAL_AUDIO_MATCH_INVALID");
  });

  it("deleting a matched cue clears the link, restores the fixed hold, and reports it", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const cue = musicCue(9401, row.id);
    delete row.visualOnlyTiming.durationOverrideMs;
    document.rowAudioSpans = [cue];
    const session = createRowEditSessionV2(document);
    expect(session.apply({
      kind: "set_visual_only_audio_match", rowId: row.id, payloadId: row.payload.payloadId, cueId: cue.id,
    }).ok).toBe(true);

    const deleted = session.apply({ kind: "delete_row_audio_span", cueId: cue.id });
    expect(deleted.ok, JSON.stringify(deleted.diagnostics)).toBe(true);
    expect(deleted.diagnostics.some((item) => item.code === "VISUAL_AUDIO_MATCH_CLEARED" &&
      item.severity === "warning" && item.message.includes("4 s"))).toBe(true);
    const restored = deleted.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(restored.visualOnlyTiming).toEqual({ kind: "visual_only", durationOverrideMs: 4000 });
    expect(deleted.document.rowAudioSpans).toBeUndefined();
    expect(session.undo().document.activeDraft.blocks[0]).toMatchObject({
      visualOnlyTiming: { durationOverrideMs: 4000, matchAudioDuration: { cueId: cue.id } },
    });
  });

  it("keeps a concurrent missing-cue match recoverable for materialization and explicit clearing", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const still = row.additionalVisuals![1]!;
    const payloadId = still.payload.payloadId;
    still.visualOnlyTiming = { kind: "visual_only", matchAudioDuration: { cueId: id(9501) } };
    const validation = validateScriptDocumentV2(document);
    expect(validation.valid).toBe(false);
    expect(validation.diagnostics).toContainEqual(expect.objectContaining({ code: "MUSIC_MATCH_INVALID" }));
    const saved = serializeAuthoringDocumentV2(document);
    const reloaded = deserializeAuthoringDocumentV2(saved);
    expect(reloaded.ok).toBe(true);
    if (!reloaded.ok) return;
    expect((reloaded.document.activeDraft.blocks[0] as VisualOnlyBlockV2).additionalVisuals?.[1]?.visualOnlyTiming.matchAudioDuration)
      .toEqual({ cueId: id(9501) });
    const session = createRowEditSessionV2(reloaded.document);
    const reordered = session.apply({
      kind: "reorder_visual_only", rowId: row.id, payloadIds: [payloadId, row.payload.payloadId, row.additionalVisuals![0].payload.payloadId],
    });
    expect(reordered.ok, JSON.stringify(reordered.diagnostics)).toBe(true);
    const cleared = session.apply({
      kind: "set_visual_only_audio_match", rowId: row.id, payloadId, cueId: null,
    });
    expect(cleared.ok, JSON.stringify(cleared.diagnostics)).toBe(true);
    expect(cleared.diagnostics).toContainEqual(expect.objectContaining({ code: "VISUAL_AUDIO_MATCH_CLEARED", severity: "warning" }));
    expect((cleared.document.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming)
      .toEqual({ kind: "visual_only", durationOverrideMs: 4000 });
  });

  it("clears a matched still when deleting its cue while the row is in Stash", () => {
    const { document } = sequence();
    const still = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const anchor: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(9601), orderKey: "z0", version: 1,
      payload: { ...still.payload, payloadId: id(9602) },
      visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 4000 },
    };
    document.activeDraft.blocks.push(anchor);
    const cue = musicCue(9610, anchor.id);
    document.rowAudioSpans = [cue];
    const session = createRowEditSessionV2(document);
    const matched = session.apply({
      kind: "set_visual_only_audio_match", rowId: still.id, payloadId: still.payload.payloadId, cueId: cue.id,
    });
    expect(matched.ok, JSON.stringify(matched.diagnostics)).toBe(true);
    const stashed = session.apply({ kind: "stash_rows", rowIds: [still.id], bundleId: id(9620) });
    expect(stashed.ok, JSON.stringify(stashed.diagnostics)).toBe(true);
    const deleted = session.apply({ kind: "delete_row_audio_span", cueId: cue.id });
    expect(deleted.ok, JSON.stringify(deleted.diagnostics)).toBe(true);
    expect(deleted.document.stash?.[0]?.rows[0]).toMatchObject({
      visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 4000 },
    });
    expect(deleted.document.stash?.[0]?.rows[0]).not.toHaveProperty("visualOnlyTiming.matchAudioDuration");
  });

  it("keeps distinct placement names with each held visual and never changes compiled events or report", () => {
    const { document, dependencies } = sequence();
    const baseline = compileTimelineV2(document, dependencies);
    expect(baseline.ok, JSON.stringify(baseline)).toBe(true);
    if (!baseline.ok) return;
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    // First and third stills are two placements of the same source.
    expect(row.payload.source).toEqual(row.additionalVisuals![1]!.payload.source);
    const session = createRowEditSessionV2(document);
    for (const [payloadId, name] of [
      [id(3102), "Different angle"], [id(31), "Hero"], [id(3101), "Trimmed insert"],
    ] as Array<[string, string]>) {
      const renamed = session.apply({ kind: "rename_visual_placement", rowId: row.id, payloadId, name });
      expect(renamed.ok, JSON.stringify(renamed.diagnostics)).toBe(true);
    }
    expect(session.undoDepth).toBe(3);
    const named = session.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect([named.payload.displayName, ...named.additionalVisuals!.map((item) => item.payload.displayName)])
      .toEqual(["Hero", "Trimmed insert", "Different angle"]);
    expect(named.payload.source).toEqual(named.additionalVisuals![1]!.payload.source);
    const compiled = compileTimelineV2(session.document, dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (!compiled.ok) return;
    expect(compiled.manifest).toEqual(baseline.manifest);
    expect(compiled.report).toEqual(baseline.report);
    expect(compiled.manifestJson).toBe(baseline.manifestJson);
    expect(compiled.reportJson).toBe(baseline.reportJson);
    expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual")
      .map((event) => event.provenance.payloadId)).toEqual([id(31), id(3101), id(3102)]);

    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document));
    expect(reloaded.ok).toBe(true);
    if (reloaded.ok) expect(reloaded.document).toEqual(session.document);
    const ordered = session.apply({
      kind: "reorder_visual_only", rowId: row.id, payloadIds: [id(3102), id(3101), id(31)],
    });
    expect(ordered.ok, JSON.stringify(ordered.diagnostics)).toBe(true);
    const after = ordered.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect([after.payload.displayName, ...after.additionalVisuals!.map((item) => item.payload.displayName)])
      .toEqual(["Different angle", "Trimmed insert", "Hero"]);
    expect(after.visualOnlyTiming.durationOverrideMs).toBe(2500);
    expect(after.additionalVisuals![1]!.visualOnlyTiming.durationOverrideMs).toBe(4000);
    const noNames = structuredClone(ordered.document);
    const stripped = noNames.activeDraft.blocks[0] as VisualOnlyBlockV2;
    delete stripped.payload.displayName;
    for (const item of stripped.additionalVisuals ?? []) delete item.payload.displayName;
    const withNames = compileTimelineV2(ordered.document, dependencies);
    const withoutNames = compileTimelineV2(noNames, dependencies);
    expect(withNames.ok, JSON.stringify(withNames)).toBe(true);
    expect(withoutNames.ok, JSON.stringify(withoutNames)).toBe(true);
    if (withNames.ok && withoutNames.ok) {
      expect(withNames.manifest).toEqual(withoutNames.manifest);
      expect(withNames.report).toEqual(withoutNames.report);
    }
    expect(session.undo().ok).toBe(true);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.displayName).toBe("Hero");
  });

  it("validates, saves and reloads still/trimmed-clip/still with distinct held durations", () => {
    const { document } = sequence();
    expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
    const result = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(document));
    expect(result.ok, JSON.stringify(result)).toBe(true);
    if (!result.ok) return;
    expect(result.document).toEqual(document);
    const row = result.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect([row.payload.payloadId, ...row.additionalVisuals!.map((visual) => visual.payload.payloadId)])
      .toEqual([id(31), id(3101), id(3102)]);
    expect(row.additionalVisuals![0].visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 10, durationFrames: 50 });
  });

  it("reorders a whole card (payload + timing) as one Undo, changing no other row data", () => {
    const { document, dependencies } = sequence();
    const session = createRowEditSessionV2(document);
    const before = session.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const changed = session.apply({ kind: "reorder_visual_only", rowId: before.id, payloadIds: [id(3102), id(3101), id(31)] });
    expect(changed.ok, JSON.stringify(changed.diagnostics)).toBe(true);
    expect(session.undoDepth).toBe(1);
    const now = changed.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(now.payload.payloadId).toBe(id(3102));
    expect(now.visualOnlyTiming.durationOverrideMs).toBe(2500);
    expect(now.additionalVisuals!.map((visual) => visual.payload.payloadId)).toEqual([id(3101), id(31)]);
    expect(now.additionalVisuals![1]!.visualOnlyTiming.durationOverrideMs).toBe(4000);
    expect({ ...now, version: before.version }).toEqual({ ...before, payload: now.payload,
      visualOnlyTiming: now.visualOnlyTiming, additionalVisuals: now.additionalVisuals });
    const compiled = compileTimelineV2(changed.document, dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (compiled.ok) expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual")
      .map((event) => event.provenance.payloadId)).toEqual([id(3102), id(3101), id(31)]);
    const undone = session.undo();
    expect(undone.ok).toBe(true);
    expect(undone.document.activeDraft.blocks[0]).toEqual(before);
    expect(session.undoDepth).toBe(0);
  });

  it("#621 compiles reordered six-second holds as contiguous manifest records and preserves one Undo per edit", () => {
    const { document, dependencies } = sequence();
    const session = createRowEditSessionV2(document);
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const changedHold = session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(31), holdSeconds: 6 });
    expect(changedHold.ok, JSON.stringify(changedHold.diagnostics)).toBe(true);
    const refused = session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(31), holdSeconds: -2 });
    expect(refused.ok).toBe(false);
    expect(session.undoDepth).toBe(1);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming.durationOverrideMs).toBe(6000);
    const order = [id(3102), id(31), id(3101)];
    const reordered = session.apply({ kind: "reorder_visual_only", rowId: row.id, payloadIds: order });
    expect(reordered.ok, JSON.stringify(reordered.diagnostics)).toBe(true);
    expect(session.undoDepth).toBe(2);
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(session.document));
    expect(saved).toEqual({ ok: true, document: session.document });
    const built = compileTimelineV2(session.document, dependencies);
    expect(built.ok, JSON.stringify(built)).toBe(true);
    if (built.ok) {
      expect(built.manifest.events.filter((event) => event.kind === "primary_visual")
        .map((event) => ({ id: event.provenance.payloadId, range: event.recordRange }))).toEqual([
          { id: id(3102), range: { startFrame: 0, endFrame: 63 } },
          { id: id(31), range: { startFrame: 63, endFrame: 213 } },
          { id: id(3101), range: { startFrame: 213, endFrame: 263 } },
        ]);
      expect(built.manifest.timeline.durationFrames).toBe(263);
    }
    expect(session.undo().ok).toBe(true);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).payload.payloadId).toBe(id(31));
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming.durationOverrideMs).toBe(6000);
    expect(session.undo().ok).toBe(true);
    expect(session.document.activeDraft.blocks[0]).toEqual(row);
    expect(session.undoDepth).toBe(0);
  });

  it("edits each still hold in seconds and refuses zero, negative or clip holds with an actionable message", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    const session = createRowEditSessionV2(document);
    for (const holdSeconds of [0, -2]) {
      const refused = session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(3102), holdSeconds });
      expect(refused.ok).toBe(false);
      expect(refused.diagnostics.some((item) => item.code === "VISUAL_HOLD_INVALID" && item.message.includes("positive"))).toBe(true);
      expect(session.undoDepth).toBe(0);
    }
    expect(session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(3101), holdSeconds: 4 }).ok).toBe(false);
    expect(session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(3102), holdSeconds: 4.0 }).ok).toBe(true);
    expect(session.document.activeDraft.blocks[0]).toMatchObject({ additionalVisuals: [{}, { visualOnlyTiming: { durationOverrideMs: 4000 } }] });
    expect(session.apply({ kind: "set_visual_only_hold", rowId: row.id, payloadId: id(3102), holdSeconds: 2.5 }).ok).toBe(true);
    expect(session.document.activeDraft.blocks[0]).toMatchObject({ additionalVisuals: [{}, { visualOnlyTiming: { durationOverrideMs: 2500 } }] });
    expect(session.undo().ok).toBe(true);
    expect((session.document.activeDraft.blocks[0] as VisualOnlyBlockV2).additionalVisuals![1]!.visualOnlyTiming.durationOverrideMs).toBe(4000);
  });

  it("refuses missing, substituted, repeated and unchanged visual orders without altering Undo history", () => {
    const { document } = sequence();
    const session = createRowEditSessionV2(document);
    const rowId = document.activeDraft.blocks[0]!.id;
    for (const { payloadIds, refusal } of [
      { payloadIds: [id(31), id(3101)], refusal: "VISUAL_ORDER_INVALID" },
      { payloadIds: [id(31), id(3101), id(999999)], refusal: "VISUAL_ORDER_INVALID" },
      { payloadIds: [id(31), id(31), id(3102)], refusal: "ROW_COMMAND_INVALID" },
      { payloadIds: [id(31), id(3101), id(3102)], refusal: "ROW_EDIT_NO_CHANGE" },
    ]) {
      const result = session.apply({ kind: "reorder_visual_only", rowId, payloadIds });
      expect(result.ok).toBe(false);
      expect(result.diagnostics.map((item) => item.code)).toContain(refusal);
      expect(result.document).toEqual(document);
      expect(session.undoDepth).toBe(0);
    }
  });

  it("compiles contiguous events: four-second still, two-second trimmed clip, 2.5-second still", () => {
    const { document, dependencies } = sequence();
    const built = compileTimelineV2(document, dependencies);
    expect(built.ok, JSON.stringify(built)).toBe(true);
    if (!built.ok) return;
    expect(built.manifest.events.filter((event) => event.kind === "primary_visual")
      .map((event) => ({ payloadId: event.provenance.payloadId, range: event.recordRange }))).toEqual([
        { payloadId: id(31), range: { startFrame: 0, endFrame: 100 } },
        { payloadId: id(3101), range: { startFrame: 100, endFrame: 150 } },
        { payloadId: id(3102), range: { startFrame: 150, endFrame: 213 } },
      ]);
    expect(built.manifest.timeline.durationFrames).toBe(213);
  });

  it("refuses duplicate payloads or a still with a selected clip range", () => {
    const { document } = sequence();
    const row = document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    row.additionalVisuals![1]!.payload.payloadId = row.payload.payloadId;
    expect(validateScriptDocumentV2(document).diagnostics).toContainEqual(expect.objectContaining({
      code: "ENTITY_ID_DUPLICATE",
      message: "Each visual in this row needs a distinct payload ID.",
      jsonPath: "/activeDraft/blocks/0/additionalVisuals/1/payload/payloadId",
      entityId: row.payload.payloadId,
    }));
    row.additionalVisuals![1]!.payload.payloadId = id(3102);
    row.additionalVisuals![1]!.visualOnlyTiming.selectedSourceRange = { startFrame: 0, durationFrames: 1 };
    expect(validateScriptDocumentV2(document).diagnostics.map((item) => item.code)).toContain("SCHEMA_INVALID");
  });

  it("defaults newly created single and additional stills to 4.0 s without retroactively changing saved rows", () => {
    const { document } = fixture();
    const row = structuredClone(document.activeDraft.blocks[0]) as VisualOnlyBlockV2;
    document.activeDraft.blocks = [];
    const session = createRowEditSessionV2(document);
    const created = session.apply({ kind: "create_row", row, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    expect((created.document.activeDraft.blocks[0] as VisualOnlyBlockV2).visualOnlyTiming.durationOverrideMs).toBe(4000);
    expect(row.visualOnlyTiming.durationOverrideMs).toBeUndefined();
    expect(session.undo().document.activeDraft.blocks).toEqual([]);

    row.additionalVisuals = [{ payload: { ...row.payload, payloadId: id(3103) }, visualOnlyTiming: { kind: "visual_only" } }];
    const multiple = session.apply({ kind: "create_row", row, destination: { sectionId: null, afterRowId: null, beforeRowId: null } });
    expect(multiple.ok).toBe(true);
    const made = multiple.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    expect(made.visualOnlyTiming.durationOverrideMs).toBe(4000);
    expect(made.additionalVisuals![0].visualOnlyTiming.durationOverrideMs).toBe(4000);
  });

  it("indexes every Research clip in a visuals-only row as its own use", () => {
    const { document } = fixture();
    const clip = researchOccurrence(811000, false);
    clip.additionalVisuals = [{ payload: { ...clip.payload, payloadId: id(811011) },
      visualOnlyTiming: structuredClone(clip.visualOnlyTiming), researchClip: structuredClone(clip.researchClip!),
      ...(clip.frameBinding ? { frameBinding: structuredClone(clip.frameBinding) } : {}) }];
    document.activeDraft.blocks = [clip];
    expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
    const usage = indexResearchClipUsageV2(document);
    expect(usage).toHaveLength(1);
    expect(usage[0]!.scriptUses.map((item) => item.placementId)).toEqual([clip.id, id(811011)]);
  });

  it("does not change the exact legacy single-visual golden manifest or report", () => {
    const { document, dependencies } = fixture();
    const result = compileTimelineV2(document, dependencies);
    expect(result.ok, JSON.stringify(result)).toBe(true);
    if (!result.ok) return;
    const stem = `${root}tests/data/authoring_v2/issue_173/compiler/visual-only-image-still-25fps-default`;
    expect(result.manifestJson).toBe(readFileSync(`${stem}.manifest.golden.json`, "utf8"));
    expect(result.reportJson).toBe(readFileSync(`${stem}.report.golden.json`, "utf8"));
  });
});
