import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import buildReportSchema from "../../../contracts/build-report-v1.schema.json" with { type: "json" };
import scriptDocumentSchema from "../../../contracts/script-document-v1.schema.json" with { type: "json" };
import timelineManifestSchema from "../../../contracts/timeline-manifest-v1.schema.json" with { type: "json" };
import { canonicalJson, compileTimeline, sha256CanonicalJson } from "../src/compiler-core.js";
import { EV24_COUNTRY_IDS, EV24_SETTING_HASH } from "../src/ev24-lower-third.js";
import type { CompilerDependenciesV1, ScriptDocumentV1 } from "../src/generated/contracts.js";
import { validateScriptDocument } from "../src/script-validator.js";

const dataPath = (name: string): string => fileURLToPath(new URL(`../../../tests/data/issue_7/${name}`, import.meta.url));
const readJson = <T>(name: string): T => JSON.parse(readFileSync(dataPath(name), "utf8")) as T;
const document = (name: "normal" | "otis" = "normal") => readJson<ScriptDocumentV1>(`${name}.script-document.json`);
const dependencies = () => readJson<CompilerDependenciesV1>("normal.compiler-dependencies.json");

function graphicSource(doc: ScriptDocumentV1) {
  const block = doc.activeDraft.blocks[1];
  if (block?.type !== "narration") throw new Error("Expected narration block.");
  const source = block.visualEvents[1]?.source;
  if (source?.kind !== "curated_fusion_graphic") throw new Error("Expected EV24 graphic.");
  return source;
}

function compiled(name: "normal" | "otis", target: "studio" | "free") {
  const deps = dependencies();
  deps.build.graphicDeliveryTarget = target;
  return compileTimeline(document(name), deps);
}

function expectGolden(name: "normal" | "otis", target: "studio" | "free"): void {
  const result = compiled(name, target);
  expect(result.ok).toBe(true);
  if (!result.ok) return;
  for (const [kind, actual] of [["manifest", result.manifestJson], ["report", result.reportJson]] as const) {
    const path = dataPath(`${name}.${target}.${kind}.golden.json`);
    if (process.env.UPDATE_GOLDENS === "1") writeFileSync(path, actual, "utf8");
    expect(actual).toBe(readFileSync(path, "utf8"));
  }
}

describe("issue #7 curated Fusion graphics", () => {
  it("keeps the EV24 country contract aligned with the registered profile", () => {
    expect(scriptDocumentSchema.$defs.Ev24SemanticInputs.properties.country.enum).toEqual(EV24_COUNTRY_IDS);
  });

  it("matches issue-owned goldens and repeats byte-identically", () => {
    expectGolden("normal", "studio");
    expectGolden("normal", "free");
    expectGolden("otis", "studio");
    for (const name of ["normal", "otis"] as const) {
      const first = compiled(name, "studio");
      const second = compiled(name, "studio");
      expect(first).toEqual(second);
    }
  });

  it("preserves pinned EV24 identity, anchor, V4, absent overrides, and Otis without Year", () => {
    for (const name of ["normal", "otis"] as const) {
      const result = compiled(name, "studio");
      expect(result.ok).toBe(true);
      if (!result.ok) continue;
      const source = result.manifest.sources.find((item) => item.kind === "fusion_template");
      const event = result.manifest.events.find((item) => item.kind === "fusion_graphic");
      expect(source).toMatchObject({ templateKey: "ev24-lower-third", entryAssetHash: EV24_SETTING_HASH });
      expect(event).toMatchObject({ trackId: "video-4", trackKind: "video", recordRange: { startFrame: 0, durationFrames: 120 }, provenance: { authoringKind: "visual_event" } });
      if (event?.kind !== "fusion_graphic") continue;
      const block = document(name).activeDraft.blocks[1];
      if (block?.type !== "narration") throw new Error("Expected narration block.");
      expect(event.anchor).toEqual(block.visualEvents[1]?.range);
      expect(event.semanticSnapshotHash).toBe(sha256CanonicalJson(event.semanticSnapshot));
      if (name === "normal") expect(event.semanticSnapshot).toMatchObject({ values: { country: "finland", year: 2024, topLineOverride: null, bottomLineOverride: null, badgeOverrideAssetId: "asset_ev24_badge_1" }, badgeAsset: { assetId: "asset_ev24_badge_1", contentHash: `sha256:${"c".repeat(64)}` } });
      else {
        expect(event.semanticSnapshot).toMatchObject({ values: { country: "otis", topLineOverride: "The Code", bottomLineOverride: "Nemo" }, badgeAsset: null });
        expect(event.semanticSnapshot.values).not.toHaveProperty("year");
      }
    }
  });

  it("reports planned Studio live versus Free placeholder and linked manual completion without changing manifest bytes", () => {
    const studio = compiled("normal", "studio");
    const free = compiled("normal", "free");
    expect(studio.ok && free.ok).toBe(true);
    if (!studio.ok || !free.ok) return;
    expect(studio.manifestJson).toBe(free.manifestJson);
    const graphicId = "70000000-0000-4000-8000-000000000001";
    expect(studio.report.eventResults.find((item) => item.eventId === graphicId)).toMatchObject({ disposition: "placed", graphicMaterialization: "live", manualCompletionRequired: false });
    expect(free.report.eventResults.find((item) => item.eventId === graphicId)).toMatchObject({ disposition: "placeholder", graphicMaterialization: "placeholder", manualCompletionRequired: true });
    expect(free.report.manualCompletionItems).toEqual(expect.arrayContaining([expect.objectContaining({ entity: { kind: "timeline_event", id: graphicId } })]));
    expect(new Set(free.report.eventResults.map((item) => item.eventId))).toEqual(new Set(free.manifest.events.map((item) => item.id)));
    expect(free.report.manifest.contentHash).toBe(sha256CanonicalJson(free.manifest));
  });

  it("changes the resolved snapshot hash when the project badge bytes change", () => {
    const first = compiled("normal", "studio");
    const deps = dependencies();
    deps.resolvedGraphics![0]!.badgeAssets[0]!.contentHash = `sha256:${"d".repeat(64)}`;
    const second = compileTimeline(document(), deps);
    expect(first.ok && second.ok).toBe(true);
    if (!first.ok || !second.ok) return;
    const before = first.manifest.events.find((item) => item.kind === "fusion_graphic");
    const after = second.manifest.events.find((item) => item.kind === "fusion_graphic");
    expect(after?.semanticSnapshotHash).not.toBe(before?.semanticSnapshotHash);
    expect(second.report.manifest.contentHash).not.toBe(first.report.manifest.contentHash);
  });

  it("accepts the exact 64-frame EV24 minimum", () => {
    const deps = dependencies();
    deps.narration[0]!.audio.durationSamples = 128128;
    const result = compileTimeline(document(), deps);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.events.find((item) => item.kind === "fusion_graphic")?.recordRange.durationFrames).toBe(64);
  });

  it("rejects unsafe author fields, invalid country/Year, and invalid graphic presentation", () => {
    const mutations: Array<(doc: ScriptDocumentV1) => void> = [
      (doc) => { graphicSource(doc).semanticInputs.country = "unknown" as "finland"; },
      (doc) => { graphicSource(doc).semanticInputs.year = 0; },
      (doc) => { graphicSource(doc).semanticInputs.badgeOverrideAssetId = "/tmp/badge.png"; },
      (doc) => { Object.assign(graphicSource(doc), { fusionTool: "ControlHub" }); },
      (doc) => { Object.assign(graphicSource(doc), { script: "print(1)" }); },
      (doc) => { const block = doc.activeDraft.blocks[1]; if (block?.type === "narration") block.visualEvents[1]!.presentationMode = "full_frame"; },
      (doc) => { graphicSource(doc).semanticInputs.topLineOverride = ""; },
    ];
    for (const mutate of mutations) {
      const doc = document();
      mutate(doc);
      expect(validateScriptDocument(doc).valid).toBe(false);
    }
    const otis = document("otis");
    graphicSource(otis).semanticInputs.year = 2024;
    expect(validateScriptDocument(otis).valid).toBe(false);
  });

  it("fails closed for missing or stale revisions, wrong project/hash/badge, target, and short duration", () => {
    const mutations: Array<[string, (deps: CompilerDependenciesV1) => void]> = [
      ["GRAPHIC_DEPENDENCY_MISSING", (deps) => { deps.resolvedGraphics = []; }],
      ["GRAPHIC_REVISION_MISMATCH", (deps) => { deps.resolvedGraphics![0]!.packageDigest = `sha256:${"d".repeat(64)}`; }],
      ["GRAPHIC_REVISION_MISMATCH", (deps) => { deps.resolvedGraphics![0]!.projectId = "70000000-0000-4000-8000-000000000002"; }],
      ["GRAPHIC_REVISION_MISMATCH", (deps) => { deps.resolvedGraphics![0]!.entryAssetHash = `sha256:${"d".repeat(64)}`; }],
      ["GRAPHIC_BADGE_MISSING", (deps) => { deps.resolvedGraphics![0]!.badgeAssets = []; }],
      ["GRAPHIC_DELIVERY_TARGET_MISSING", (deps) => { delete deps.build.graphicDeliveryTarget; }],
      ["GRAPHIC_DURATION_TOO_SHORT", (deps) => { deps.narration[0]!.audio.durationSamples = 96000; }],
    ];
    for (const [code, mutate] of mutations) {
      const deps = dependencies();
      mutate(deps);
      const result = compileTimeline(document(), deps);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.diagnostics.map((item) => item.code)).toContain(code);
    }
  });

  it("types baked results for future verified assets without emitting one", () => {
    const result = compiled("normal", "studio");
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const report = structuredClone(result.report);
    const graphic = report.eventResults.find((item) => item.graphicMaterialization === "live")!;
    graphic.graphicMaterialization = "baked";
    const ajv = new Ajv2020({ strict: true });
    formatsModule.default.default(ajv);
    ajv.addSchema(scriptDocumentSchema);
    ajv.addSchema(timelineManifestSchema);
    const validate = ajv.compile(buildReportSchema);
    expect(validate(report)).toBe(true);
    expect(canonicalJson(result.report)).not.toContain('"graphicMaterialization": "baked"');
  });
});
