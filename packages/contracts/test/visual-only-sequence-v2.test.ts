import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import { createRowEditSessionV2, deserializeAuthoringDocumentV2, serializeAuthoringDocumentV2 } from "../src/authoring-v2-rows.js";
import { indexResearchClipUsageV2 } from "../src/research-clip-usage-v2.js";
import type { CompilerDependenciesV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
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

describe("#585 visuals-only ordered cards", () => {
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
    for (const payloadIds of [
      [id(31), id(3101)],
      [id(31), id(3101), id(999999)],
      [id(31), id(31), id(3102)],
      [id(31), id(3101), id(3102)],
    ]) {
      const result = session.apply({ kind: "reorder_visual_only", rowId, payloadIds });
      expect(result.ok).toBe(false);
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
    expect(validateScriptDocumentV2(document).diagnostics.map((item) => item.code)).toContain("ENTITY_ID_DUPLICATE");
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
