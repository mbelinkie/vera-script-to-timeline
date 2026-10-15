import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { canonicalJson, compileTimeline, sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV1, GraphicProvenanceSnapshot, ScriptDocumentV1 } from "../src/generated/contracts.js";
import type { CompilerDependenciesV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

const repo = fileURLToPath(new URL("../../../", import.meta.url));
const read = <T>(path: string): T => JSON.parse(readFileSync(`${repo}${path}`, "utf8")) as T;
const hash = (text: string): string => sha256CanonicalJson(text);
const id = (n: number): string => `21800000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const stem = "tests/data/authoring_v2/issue_173/compiler/visual-only-graphic-still-ntsc-default";

function v1() {
  const document = read<ScriptDocumentV1>("tests/data/issue_7/normal.script-document.json");
  const dependencies = read<CompilerDependenciesV1>("tests/data/issue_7/normal.compiler-dependencies.json");
  const block = document.activeDraft.blocks[1]!;
  if (block.type !== "narration" || block.visualEvents[1]?.source.kind !== "curated_fusion_graphic") throw new Error("graphic fixture");
  const source = block.visualEvents[1].source;
  const dependency = dependencies.resolvedGraphics![0]!;
  const semanticSnapshot = { values: structuredClone(source.semanticInputs), badgeAsset: structuredClone(dependency.badgeAssets[0]!) };
  const snapshot: GraphicProvenanceSnapshot = {
    schemaVersion: "graphic-provenance/v1", projectId: document.projectId,
    template: { templateKey: source.templateKey, projectRevisionId: source.projectRevisionId, packageDigest: source.packageDigest, entryAssetHash: dependency.entryAssetHash },
    semanticSnapshot, semanticSnapshotHash: sha256CanonicalJson(semanticSnapshot),
    sources: [{ sourceKey: "tally", citation: { title: "Synthetic tally", publisher: "Fictional Lab", originalLocator: null, versionLabel: "1" }, snapshot: { artifactId: id(1), contentHash: hash("retained bytes"), mediaType: "application/json" } }],
    derivation: { mode: "manual", version: "1", note: "Source tally selects fictional output labels; no arithmetic, rounding or exclusions.", method: null, parameters: {} },
  };
  source.provenance = { kind: "derived", snapshotHash: sha256CanonicalJson(snapshot) };
  dependencies.graphicProvenanceSnapshots = [snapshot];
  return { document, dependencies, source, snapshot };
}

function v2() {
  const pair = read<{ document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 }>(`${stem}.input.golden.json`);
  const content = v1();
  const block = pair.document.activeDraft.blocks[0]!;
  if (block.type !== "visual_only" || block.payload.source.kind !== "graphic_revision") throw new Error("graphic fixture");
  const source = block.payload.source;
  content.snapshot.projectId = pair.document.projectId;
  const provenance = { kind: "derived" as const, snapshotHash: sha256CanonicalJson(content.snapshot) };
  pair.dependencies.graphicProvenanceSnapshots = [content.snapshot];
  pair.dependencies.resolvedGraphicContents = [{ graphicId: source.graphicId, revisionId: source.revisionId, projectId: pair.document.projectId, template: content.snapshot.template, semanticSnapshot: content.snapshot.semanticSnapshot, semanticSnapshotHash: content.snapshot.semanticSnapshotHash, provenance }];
  const descriptor = pair.dependencies.occurrenceResolutions[0]!;
  descriptor.graphicContentClass = "derived";
  descriptor.graphicContentBinding = { graphicId: source.graphicId, revisionId: source.revisionId, provenanceHash: provenance.snapshotHash };
  return { ...pair, descriptor, content: pair.dependencies.resolvedGraphicContents[0]!, snapshot: content.snapshot };
}

describe("#218 compiler provenance boundary", () => {
  it("refuses non-JSON provenance before recursive validation without evaluating getters", () => {
    const cycle: Record<string, unknown> = {}; cycle.self = cycle;
    let accessed = false;
    const accessor = Object.defineProperty({}, "value", { enumerable: true, get: () => { accessed = true; return 1; } });
    for (const value of [cycle, Number.NaN, Infinity, undefined, 1n, new Date(), accessor, Object.assign([1], { extra: 2 })]) {
      const input = v1(); input.snapshot.derivation.parameters = { value };
      const result = compileTimeline(input.document, input.dependencies);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.diagnostics[0]?.code).toBe("GRAPHIC_PROVENANCE_INCOMPLETE");
    }
    expect(accessed).toBe(false);
    const input = v2(); input.snapshot.derivation.parameters = { value: cycle };
    expect(compileTimelineV2(input.document, input.dependencies)).toMatchObject({ ok: false, diagnostics: [{ code: "GRAPHIC_PROVENANCE_INCOMPLETE" }] });
  });

  it("v1 retains derived pointers without changing semantic, template or event identity", () => {
    const input = v1();
    const before = canonicalJson(input);
    const compiled = compileTimeline(input.document, input.dependencies);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (!compiled.ok) return;
    const event = compiled.manifest.events.find((item) => item.kind === "fusion_graphic")!;
    expect(event).toMatchObject({ graphicProvenance: input.source.provenance, semanticSnapshotHash: input.snapshot.semanticSnapshotHash });
    expect(compiled.report.eventResults.find((item) => item.eventId === event.id)).toMatchObject({ graphicProvenance: input.source.provenance });
    const legacy = v1(); delete legacy.source.provenance; delete legacy.dependencies.graphicProvenanceSnapshots;
    const legacyResult = compileTimeline(legacy.document, legacy.dependencies);
    expect(legacyResult.ok).toBe(true);
    if (legacyResult.ok) {
      const original = legacyResult.manifest.events.find((item) => item.kind === "fusion_graphic")!;
      expect(event.id).toBe(original.id); expect(event.sourceId).toBe(original.sourceId);
      if (event.kind === "fusion_graphic" && original.kind === "fusion_graphic") expect(event.semanticSnapshotHash).toBe(original.semanticSnapshotHash);
    }
    expect(canonicalJson(input)).toBe(before);
    expect(compileTimeline(input.document, input.dependencies)).toEqual(compiled);
  });

  it("v1 preserves the accepted legacy omission trust residual and explicit manual binding", () => {
    const input = v1(); input.source.provenance = { kind: "manual" }; delete input.dependencies.graphicProvenanceSnapshots;
    const manual = compileTimeline(input.document, input.dependencies);
    expect(manual.ok).toBe(true);
    if (manual.ok) expect(manual.manifest.events.find((item) => item.kind === "fusion_graphic")).toMatchObject({ graphicProvenance: { kind: "manual" } });
    delete input.source.provenance;
    const legacy = compileTimeline(input.document, input.dependencies);
    expect(legacy.ok).toBe(true);
    if (legacy.ok) expect(legacy.manifest.events.find((item) => item.kind === "fusion_graphic")).not.toHaveProperty("graphicProvenance");
  });

  it.each([
    ["missing", "GRAPHIC_PROVENANCE_UNAVAILABLE", (x: ReturnType<typeof v1>) => { x.dependencies.graphicProvenanceSnapshots = []; }],
    ["wrong project", "GRAPHIC_PROVENANCE_UNAUTHORIZED", (x: ReturnType<typeof v1>) => { x.snapshot.projectId = id(9); x.source.provenance = { kind: "derived", snapshotHash: sha256CanonicalJson(x.snapshot) }; }],
    ["template", "GRAPHIC_PROVENANCE_MISMATCH", (x: ReturnType<typeof v1>) => { x.snapshot.template.projectRevisionId = "different"; x.source.provenance = { kind: "derived", snapshotHash: sha256CanonicalJson(x.snapshot) }; }],
    ["changed values", "GRAPHIC_PROVENANCE_MISMATCH", (x: ReturnType<typeof v1>) => { x.source.semanticInputs.topLineOverride = "changed"; }],
    ["duplicate", "GRAPHIC_PROVENANCE_UNEXPECTED", (x: ReturnType<typeof v1>) => { x.dependencies.graphicProvenanceSnapshots!.push(structuredClone(x.snapshot)); }],
    ["unused", "GRAPHIC_PROVENANCE_UNEXPECTED", (x: ReturnType<typeof v1>) => { x.source.provenance = { kind: "manual" }; }],
  ] as const)("v1 refuses %s provenance", (_name, code, mutate) => {
    const input = v1(); mutate(input);
    const result = compileTimeline(input.document, input.dependencies);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.diagnostics.map((item) => item.code)).toContain(code);
  });

  it("v2 propagates P while preserving materialized media hashes and identities", () => {
    const input = v2(); const before = canonicalJson(input);
    const result = compileTimelineV2(input.document, input.dependencies);
    expect(result.ok, JSON.stringify(result)).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.events[0]?.provenance).toMatchObject({ graphicProvenanceHash: input.descriptor.graphicContentBinding!.provenanceHash, originalSourceHash: input.descriptor.sourceSnapshot.contentHash });
    expect(result.report.dependenciesHash).toBe(sha256CanonicalJson(input.dependencies));
    expect(compileTimelineV2(input.document, input.dependencies)).toEqual(result);
    expect(canonicalJson(input)).toBe(before);
  });

  it("v2 retains P on narrated primary and overlay graphic paths", () => {
    const input = read<{ document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 }>("tests/data/authoring_v2/issue_173/compiler/root-child-overlay-return.input.golden.json");
    const graphic = v2();
    input.dependencies.graphicProvenanceSnapshots = graphic.dependencies.graphicProvenanceSnapshots!;
    input.dependencies.resolvedGraphicContents = graphic.dependencies.resolvedGraphicContents!;
    const row = input.document.activeDraft.blocks[0]!;
    if (row.type !== "narration") throw new Error("narration fixture");
    const root = row.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("visual fixture");
    const rootPayloadId = root.payload.payloadId;
    const oldGraphic = graphic.document.activeDraft.blocks[0]!;
    if (oldGraphic.type !== "visual_only") throw new Error("visual-only fixture");
    for (const payload of [root.payload, row.overlayEvents[0]!.payload]) {
      payload.pictureKind = "graphic";
      payload.source = structuredClone(oldGraphic.payload.source);
      payload.sourceUsage = null;
    }
    input.dependencies.occurrenceResolutions = input.dependencies.occurrenceResolutions.map((descriptor) => ({ ...structuredClone(graphic.descriptor), owner: descriptor.owner, payloadId: descriptor.payloadId, preparedMediaRequirementKey: descriptor.preparedMediaRequirementKey }));
    input.dependencies.preparedMedia = input.dependencies.occurrenceResolutions.map((descriptor) => {
      const binding = structuredClone(graphic.dependencies.preparedMedia[0]!);
      binding.requirementKey = descriptor.preparedMediaRequirementKey!;
      binding.targetRate = input.dependencies.timeline.frameRate;
      binding.timeMapping.deliveredRate = input.dependencies.timeline.frameRate;
      binding.verification.decodedFrameRate = input.dependencies.timeline.frameRate;
      binding.verification.videoTimeBase = { numerator: 1, denominator: 24 };
      return binding;
    });
    const result = compileTimelineV2(input.document, input.dependencies);
    expect(result.ok, JSON.stringify(result)).toBe(true);
    if (result.ok) {
      const events = result.manifest.events.filter((event) => [rootPayloadId, row.overlayEvents[0]!.payload.payloadId].includes(event.provenance.payloadId ?? ""));
      expect(new Set(events.map((event) => event.trackRole))).toEqual(new Set(["primary_root", "overlay"]));
      expect(events.every((event) => event.provenance.graphicProvenanceHash === graphic.descriptor.graphicContentBinding!.provenanceHash)).toBe(true);
    }
  });

  it("v2 manual content has no derived pointer, and non-graphics forbid classification", () => {
    const input = v2(); input.content.provenance = { kind: "manual" };
    delete input.dependencies.graphicProvenanceSnapshots; input.descriptor.graphicContentClass = "manual"; delete input.descriptor.graphicContentBinding;
    const manual = compileTimelineV2(input.document, input.dependencies);
    expect(manual.ok, JSON.stringify(manual)).toBe(true);
    if (manual.ok) expect(manual.manifest.events[0]?.provenance).not.toHaveProperty("graphicProvenanceHash");
    const block = input.document.activeDraft.blocks[0]!;
    if (block.type !== "visual_only") throw new Error("visual-only fixture");
    block.payload.source = { kind: "media_reference", mediaReferenceId: input.descriptor.mediaReferenceId };
    block.payload.pictureKind = "image";
    const invalid = compileTimelineV2(input.document, input.dependencies);
    expect(invalid.ok).toBe(false);
    if (!invalid.ok) expect(invalid.diagnostics.map((item) => item.code)).toContain("GRAPHIC_PROVENANCE_UNEXPECTED");
  });

  it.each([
    ["class omitted", "GRAPHIC_PROVENANCE_INCOMPLETE", (x: ReturnType<typeof v2>) => { delete x.descriptor.graphicContentClass; }],
    ["content dropped", "GRAPHIC_PROVENANCE_INCOMPLETE", (x: ReturnType<typeof v2>) => { delete x.dependencies.resolvedGraphicContents; }],
    ["binding dropped", "GRAPHIC_PROVENANCE_INCOMPLETE", (x: ReturnType<typeof v2>) => { delete x.descriptor.graphicContentBinding; }],
    ["wrong revision", "GRAPHIC_PROVENANCE_MISMATCH", (x: ReturnType<typeof v2>) => { x.descriptor.graphicContentBinding!.revisionId = id(8); }],
    ["wrong P", "GRAPHIC_PROVENANCE_MISMATCH", (x: ReturnType<typeof v2>) => { x.descriptor.graphicContentBinding!.provenanceHash = hash("wrong"); }],
    ["wrong content project", "GRAPHIC_PROVENANCE_UNAUTHORIZED", (x: ReturnType<typeof v2>) => { x.content.projectId = id(8); }],
    ["duplicate content", "GRAPHIC_PROVENANCE_UNEXPECTED", (x: ReturnType<typeof v2>) => { x.dependencies.resolvedGraphicContents!.push(structuredClone(x.content)); }],
    ["legacy with new content", "GRAPHIC_PROVENANCE_UNEXPECTED", (x: ReturnType<typeof v2>) => { x.descriptor.graphicContentClass = "legacy_unclassified"; delete x.descriptor.graphicContentBinding; }],
  ] as const)("v2 refuses %s", (_name, code, mutate) => {
    const input = v2(); mutate(input); const result = compileTimelineV2(input.document, input.dependencies);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.diagnostics.map((item) => item.code)).toContain(code);
  });

  it("exposes false upstream legacy classification as a trusted-resolver residual", () => {
    const input = v2(); delete input.dependencies.resolvedGraphicContents; delete input.dependencies.graphicProvenanceSnapshots;
    input.descriptor.graphicContentClass = "legacy_unclassified"; delete input.descriptor.graphicContentBinding;
    // The compiler cannot infer a false trusted classification from the rendered file hash.
    const result = compileTimelineV2(input.document, input.dependencies);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.manifest.events[0]?.provenance).not.toHaveProperty("graphicProvenanceHash");
  });

  it("retains original v2 graphic goldens and migrates only approved classification/report hashes", () => {
    for (const suffix of ["ntsc-default", "25fps-default", "ntsc-override"]) {
      const path = `tests/data/authoring_v2/issue_173/compiler/visual-only-graphic-still-${suffix}`;
      const input = read<{ document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 }>(`${path}.input.golden.json`);
      const old = compileTimelineV2(input.document, input.dependencies);
      expect(old.ok).toBe(false);
      if (!old.ok) expect(old.diagnostics.map((item) => item.code)).toContain("GRAPHIC_PROVENANCE_INCOMPLETE");
      input.dependencies.occurrenceResolutions[0]!.graphicContentClass = "legacy_unclassified";
      const result = compileTimelineV2(input.document, input.dependencies);
      expect(result.ok, JSON.stringify(result)).toBe(true);
      if (!result.ok) continue;
      const inputJson = `${JSON.stringify(input, null, 2)}\n`;
      if (process.env.UPDATE_ISSUE_218_GOLDENS === "1") {
        writeFileSync(`${repo}${path}.issue-218-migrated.input.golden.json`, inputJson);
        writeFileSync(`${repo}${path}.issue-218-migrated.report.golden.json`, result.reportJson);
      }
      expect(inputJson).toBe(readFileSync(`${repo}${path}.issue-218-migrated.input.golden.json`, "utf8"));
      expect(result.reportJson).toBe(readFileSync(`${repo}${path}.issue-218-migrated.report.golden.json`, "utf8"));
      expect(result.manifestJson).toBe(readFileSync(`${repo}${path}.manifest.golden.json`, "utf8"));
      const oldReport = read<Record<string, unknown>>(`${path}.report.golden.json`);
      expect({ ...result.report, dependenciesHash: oldReport.dependenciesHash }).toEqual(oldReport);
    }
  });
});
