import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import type {
  AuthoringDefaultsV2,
  CompilerDependenciesV2,
  NarrationBlockV2,
  ScriptDocumentV2,
  VisualOnlyBlockV2,
} from "../src/generated/contracts-v2.js";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const fixtureRoot = `${root}tests/data/authoring_v2/issue_173/compiler/`;
const goldens = `${root}tests/data/authoring_v2/issue_336/compiler/`;
type FrozenInput = { document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 };
type ImageMotion = NonNullable<AuthoringDefaultsV2["imageMotionDefault"]>;
type NativeMotion = Extract<ImageMotion, { mode: "native_dynamic_zoom" }>;

function fixture(name: string): FrozenInput {
  return JSON.parse(readFileSync(`${fixtureRoot}${name}.input.golden.json`, "utf8")) as FrozenInput;
}

// Test geometry only: not a product preset or a claim that this mapping is
// qualified in Resolve. Native qualification/refusal belongs to phases 2–4.
const nativeMotion = (): NativeMotion => ({
  mode: "native_dynamic_zoom",
  start: { focusX: 0.5, focusY: 0.5, scale: 1 },
  end: { focusX: 0.65, focusY: 0.35, scale: 1.125 },
  easing: "linear",
});

function golden(name: string, value: string): void {
  if (process.env.UPDATE_COMPILER_V2_GOLDENS === "1") {
    mkdirSync(goldens, { recursive: true });
    writeFileSync(`${goldens}${name}.golden.json`, value, "utf8");
  }
  expect(value).toBe(readFileSync(`${goldens}${name}.golden.json`, "utf8"));
}

function frozenGolden(name: string, inputs: FrozenInput, manifest: string, report: string): void {
  golden(`${name}.input`, `${JSON.stringify(inputs, null, 2)}\n`);
  golden(`${name}.manifest`, manifest);
  golden(`${name}.report`, report);
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
for (const name of [
  "script-document-v2.schema.json",
  "authoring-project-settings-v1.schema.json",
  "compiler-dependencies-v2.schema.json",
  "timeline-manifest-v2.schema.json",
]) {
  ajv.addSchema(JSON.parse(readFileSync(`${root}contracts/${name}`, "utf8")) as object);
}
const validateSettings = ajv.getSchema("https://schemas.vera.video/contracts/authoring-project-settings-v1.schema.json")!;
const validateDocument = ajv.getSchema("https://schemas.vera.video/contracts/script-document-v2.schema.json")!;
const validateManifest = ajv.getSchema("https://schemas.vera.video/contracts/timeline-manifest-v2.schema.json")!;

describe("#336 frozen v2 still-image motion", () => {
  it("accepts configured project defaults and explicit None without changing legacy settings", () => {
    const { document, dependencies } = fixture("narrated-image-still-holds");
    const settings = {
      schemaVersion: "authoring-project-settings/v1",
      id: "00000000-0000-4000-8000-000000000099",
      projectId: document.projectId,
      version: 1,
      settingsHash: dependencies.authoringDefaults.settingsHash,
      imageMotionDefault: nativeMotion(),
    };
    expect(validateSettings(settings), JSON.stringify(validateSettings.errors)).toBe(true);
    expect(validateSettings({ ...settings, imageMotionDefault: { mode: "none" } })).toBe(true);
    const legacy = { ...settings } as Partial<typeof settings>;
    delete legacy.imageMotionDefault;
    expect(validateSettings(legacy)).toBe(true);
    expect(validateSettings({ ...settings, imageMotionDefault: { mode: "native_dynamic_zoom" } })).toBe(false);
    expect(validateSettings({ ...settings, imageMotionDefault: { mode: "none", easing: "linear" } })).toBe(false);
  });

  it("validates normalized source focus and disallows motion on clips and placeholders", () => {
    const { document } = fixture("narrated-image-still-holds");
    const row = document.activeDraft.blocks[0] as NarrationBlockV2;
    const rootSlot = row.primaryVisualSequence!.slots[0]!;
    if (rootSlot.kind !== "content" || rootSlot.payload.kind !== "visual") throw new Error("Expected still root");
    rootSlot.payload.imageMotion = nativeMotion();
    expect(validateDocument(document), JSON.stringify(validateDocument.errors)).toBe(true);
    rootSlot.payload.imageMotion = { ...nativeMotion(), start: { focusX: -0.01, focusY: 0.5, scale: 1 } };
    expect(validateDocument(document)).toBe(false);
    rootSlot.payload.imageMotion = { ...nativeMotion(), end: { focusX: 0.5, focusY: 0.5, scale: 0 } };
    expect(validateDocument(document)).toBe(false);
    rootSlot.payload.imageMotion = nativeMotion();
    rootSlot.payload.pictureKind = "clip";
    expect(validateDocument(document)).toBe(false);
    rootSlot.payload.pictureKind = "image";
    rootSlot.payload.imageMotion = { mode: "none" };
    expect(validateDocument(document), JSON.stringify(validateDocument.errors)).toBe(true);

    const visual = fixture("visual-only-image-still-ntsc-default");
    const block = visual.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
    block.payload.imageMotion = { mode: "none" };
    expect(validateDocument(visual.document)).toBe(true);
    block.payload.pictureKind = "clip";
    expect(validateDocument(visual.document)).toBe(false);
  });

  it("freezes inherited native zoom and an explicit None overlay independently of live defaults", () => {
    const input = fixture("narrated-image-still-holds");
    input.dependencies.authoringDefaults.imageMotionDefault = nativeMotion();
    const row = input.document.activeDraft.blocks[0] as NarrationBlockV2;
    row.overlayEvents[0]!.payload.imageMotion = { mode: "none" };
    const before = JSON.stringify(input);
    const result = compileTimelineV2(input.document, input.dependencies);
    expect(result.ok, JSON.stringify(result)).toBe(true);
    if (!result.ok) return;
    expect(JSON.stringify(input)).toBe(before);
    const primary = result.manifest.events.find((event) => event.kind === "primary_visual")!;
    const overlay = result.manifest.events.find((event) => event.kind === "overlay_visual")!;
    expect(primary.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: "image", framingPolicy: "contain", imageMotion: nativeMotion() });
    expect(overlay.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: "image", framingPolicy: "cover", imageMotion: { mode: "none" } });
    expect(primary.recordRange).toEqual({ startFrame: 0, endFrame: 96 });
    expect(overlay.recordRange).toEqual({ startFrame: 0, endFrame: 24 });
    expect(primary.sourceRange).toEqual({ startFrame: 0, endFrame: 1 });
    expect(validateManifest(result.manifest), JSON.stringify(validateManifest.errors)).toBe(true);
    frozenGolden("narrated-native-default-overlay-none", input, result.manifestJson, result.reportJson);

    // Changing a subsequent default or profile creates a new immutable identity;
    // the previously compiled bytes and resolved treatment stay unchanged.
    const newer = structuredClone(input);
    newer.dependencies.authoringDefaults.imageMotionDefault = { ...nativeMotion(), end: { focusX: 0.7, focusY: 0.45, scale: 1.2 } };
    newer.dependencies.compiler.profileHash = `sha256:${"f".repeat(64)}`;
    const rebuilt = compileTimelineV2(newer.document, newer.dependencies);
    expect(rebuilt.ok).toBe(true);
    if (rebuilt.ok) {
      expect(rebuilt.manifestJson).not.toBe(result.manifestJson);
      expect(rebuilt.report.dependenciesHash).not.toBe(result.report.dependenciesHash);
      expect(primary.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: "image", framingPolicy: "contain", imageMotion: nativeMotion() });
    }
  });

  it("rebuilds short and long still occurrences at exact frames without changing source frames", () => {
    for (const { name, durationMs, frames, none } of [
      { name: "visual-only-native-short", durationMs: 1000, frames: 24, none: false },
      { name: "visual-only-none-long", durationMs: 6000, frames: 144, none: true },
    ]) {
      const input = fixture("visual-only-image-still-ntsc-default");
      const block = input.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
      block.visualOnlyTiming.durationOverrideMs = durationMs;
      input.dependencies.authoringDefaults.imageMotionDefault = nativeMotion();
      if (none) block.payload.imageMotion = { mode: "none" };
      const needs = resolveMediaRequirementsV2(input.document, {
        defaults: input.dependencies.authoringDefaults,
        timing: [], sourceDescriptors: input.dependencies.occurrenceResolutions,
        frameRate: input.dependencies.timeline.frameRate,
      });
      expect(needs.ok, JSON.stringify(needs)).toBe(true);
      if (needs.ok) expect(needs.durationFrames).toBe(frames);
      const compiled = compileTimelineV2(input.document, input.dependencies);
      expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
      if (!compiled.ok) continue;
      expect(compiled.manifest.timeline.durationFrames).toBe(frames);
      const still = compiled.manifest.events.find((event) => event.kind === "primary_visual")!;
      expect(still.recordRange).toEqual({ startFrame: 0, endFrame: frames });
      expect(still.sourceRange).toEqual({ startFrame: 0, endFrame: 1 });
      expect(still.pictureTreatment).toMatchObject({ kind: "still_frame", imageMotion: none ? { mode: "none" } : nativeMotion() });
      frozenGolden(name, input, compiled.manifestJson, compiled.reportJson);
    }
  });

  it("rejects invalid frozen motion and stale source provenance before a manifest is issued", () => {
    const bad = fixture("visual-only-image-still-ntsc-default");
    bad.dependencies.authoringDefaults.imageMotionDefault = { ...nativeMotion(), easing: "ease_out" };
    const changed = compileTimelineV2(bad.document, bad.dependencies);
    expect(changed.ok).toBe(true); // Valid intent; runtime must qualify or refuse this ease.
    bad.dependencies.authoringDefaults.imageMotionDefault = { ...nativeMotion(), end: { focusX: 1.1, focusY: 0, scale: 1 } };
    const invalid = compileTimelineV2(bad.document, bad.dependencies);
    expect(invalid.ok).toBe(false);
    if (!invalid.ok) expect(invalid.diagnostics.map((item) => item.code)).toContain("DEPENDENCIES_SCHEMA_INVALID");

    const stale = fixture("visual-only-image-still-ntsc-default");
    stale.dependencies.authoringDefaults.imageMotionDefault = nativeMotion();
    stale.dependencies.occurrenceResolutions[0]!.sourceSnapshot.probeHash = `sha256:${"f".repeat(64)}`;
    const refused = compileTimelineV2(stale.document, stale.dependencies);
    expect(refused.ok).toBe(false);
    if (!refused.ok) expect(refused.diagnostics.map((item) => item.code)).toContain("SOURCE_MAPPING_MISMATCH");
  });
});
