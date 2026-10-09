import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import documentSchema from "../../../contracts/script-document-v2.schema.json" with { type: "json" };
import dependenciesSchema from "../../../contracts/compiler-dependencies-v2.schema.json" with { type: "json" };
import manifestSchema from "../../../contracts/timeline-manifest-v2.schema.json" with { type: "json" };
import genericTorso from "../src/assets/generic-torso-v1.json" with { type: "json" };
import type { NarrationAudioBindingV2, StillPictureTreatmentV2, SlatePictureTreatmentV2 } from "@vera/contracts/v2";

const ajv = new Ajv2020({ strict: true, allErrors: true });
formatsModule.default.default(ajv);
for (const schema of [documentSchema, dependenciesSchema, manifestSchema]) {
  ajv.addSchema(schema);
}
const validateAudio = ajv.getSchema(
  `${dependenciesSchema.$id}#/$defs/NarrationAudioBindingV2`,
)!;
const validateSource = ajv.getSchema(`${manifestSchema.$id}#/$defs/ManifestSourceV2`)!;
const validateTreatment = ajv.getSchema(`${manifestSchema.$id}#/$defs/PictureTreatmentV2`)!;
const validateBuild = ajv.getSchema(`${dependenciesSchema.$id}#/$defs/BuildIdentityV2`)!;
const validateMarker = ajv.getSchema(`${manifestSchema.$id}#/$defs/ScriptMarkerTreatmentV2`)!;

const audio: NarrationAudioBindingV2 = {
  narrationAssetId: "00000000-0000-4000-8000-000000000001",
  audioHash: `sha256:${"a".repeat(64)}`,
  timingHash: `sha256:${"c".repeat(64)}`,
  cacheAssetId: "b".repeat(64),
  locator: "immutable/narration.wav",
  durationSamples: 96000,
  sampleRate: 48000,
  channels: 1,
};

describe("P4 additive narration and picture evidence", () => {
  it("identifies static frame holds without authorizing a clip hold", () => {
    for (const pictureKind of ["image", "capture", "graphic"]) {
      expect(validateTreatment({ kind: "still_frame", pictureKind, framingPolicy: "contain" })).toBe(true);
      expect(validateTreatment({ kind: "still_frame", pictureKind, framingPolicy: "cover" })).toBe(true);
      expect(validateTreatment({ kind: "still_frame", pictureKind, framingPolicy: "native" })).toBe(true);
    }
    expect(validateTreatment({ kind: "still_frame", pictureKind: "clip", framingPolicy: "contain" })).toBe(false);
    expect(validateTreatment({ kind: "still_frame", pictureKind: "image", framingPolicy: "stretch" })).toBe(false);
    expect(validateTreatment({ kind: "still_frame", pictureKind: "image", framingPolicy: "contain", inventedDuration: 100 })).toBe(false);
  });

  it("retains exact marker text with its supporting-item identity", () => {
    const marker = { supportingItemId: audio.narrationAssetId, text: "  Editor note — café.  " };
    expect(validateMarker(marker)).toBe(true);
    expect(JSON.parse(JSON.stringify(marker))).toEqual(marker);
    expect(validateMarker({ ...marker, text: "" })).toBe(false);
    expect(validateMarker({ ...marker, supportingItemId: "unknown" })).toBe(false);
    expect(validateMarker({ ...marker, guessedName: "note" })).toBe(false);
  });

  it("freezes an explicit forced Preview choice and forbids it for Release", () => {
    const build = {
      buildId: audio.narrationAssetId,
      manifestId: audio.narrationAssetId,
      reportId: audio.narrationAssetId,
      buildClass: "preview",
    };
    expect(validateBuild(build)).toBe(true);
    expect(validateBuild({ ...build, forcePreviewVisuals: true })).toBe(true);
    expect(validateBuild({ ...build, buildClass: "release", forcePreviewVisuals: false })).toBe(true);
    expect(validateBuild({ ...build, buildClass: "release", forcePreviewVisuals: true })).toBe(false);
  });

  it("validates exact audio evidence and rejects unsafe samples and locators", () => {
    expect(validateAudio(audio)).toBe(true);
    for (const patch of [
      { durationSamples: 0 },
      { durationSamples: Number.MAX_SAFE_INTEGER + 1 },
      { sampleRate: 0 },
      { channels: -1 },
      { cacheAssetId: "abc" },
      { locator: "../audio.wav" },
      { locator: "audio//file.wav" },
      { locator: "audio/" },
      { locator: "audio\nfile.wav" },
      { locator: "https://example.com/audio.wav" },
      { unexpected: true },
    ]) {
      expect(validateAudio({ ...audio, ...patch })).toBe(false);
    }
  });

  it("serializes narration as sample evidence without a fictional picture frame map", () => {
    const source = { id: audio.narrationAssetId, narrationAudio: audio };
    expect(validateSource(source)).toBe(true);
    expect(validateSource({ ...source, sourceFrameMap: {} })).toBe(false);
    expect(validateSource({ ...source, narrationAudio: { ...audio, audioHash: "wrong" } })).toBe(false);
  });

  it("pins the actual torso bytes and freezes fixed still composition and exact slate text", () => {
    const bytes = readFileSync(new URL("../src/assets/generic-torso-v1.svg", import.meta.url));
    expect(`sha256:${createHash("sha256").update(bytes).digest("hex")}`).toBe(genericTorso.contentHash);
    expect(genericTorso.width * 9).toBe(genericTorso.height * 16);
    const treatment: StillPictureTreatmentV2 = {
      kind: "still",
      reference: { ...genericTorso, provenance: { origin: "local_import", originalFilename: "generic-torso-v1.svg" } },
      composition: {
        framingPolicy: "contain",
        horizontalAlignment: "center",
        verticalAlignment: "center",
        backgroundColor: "#000000",
        motionPreset: "none",
      },
    };
    expect(validateTreatment(treatment)).toBe(true);
    expect(validateTreatment({ ...treatment, composition: { ...treatment.composition, framingPolicy: "cover" } })).toBe(false);
    const slate: SlatePictureTreatmentV2 = { kind: "slate", purpose: "intentional", text: "  Keep exact author text — café.  " };
    expect(validateTreatment(slate)).toBe(true);
    expect(JSON.parse(JSON.stringify(slate))).toEqual(slate);
    expect(validateTreatment({ ...slate, reference: genericTorso })).toBe(false);
  });
});
