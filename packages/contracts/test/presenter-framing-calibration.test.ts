import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canonicalJson } from "../src/compiler-core.js";
import { presenterFramingProfileContentJson, snapshotPresenterFramingCalibration, validatePresenterFramingProfile } from "../src/presenter-framing.js";

const id = "f646c9c0-5f84-4e78-b6cc-1ec11d47a946";
function fixture() {
  return validatePresenterFramingProfile(JSON.parse(readFileSync(new URL("./fixtures/presenter-framing/profile.json", import.meta.url), "utf8")));
}
function calibration() {
  const profile = fixture();
  return { status: "sample_readback_complete", message: "Synthetic test readback only.",
    context: structuredClone(profile.context), observed_transforms: { wide: { ...profile.wide }, tight: { ...profile.tight } }, color_limitations: [] };
}

describe("captured presenter profile revisions", () => {
  it("creates initial immutable version one from the captured pair with the exact shared hash", () => {
    const input = calibration();
    const before = canonicalJson(input);
    const snapshot = snapshotPresenterFramingCalibration(input, null, id);
    expect(snapshot.id).toBe(id);
    expect(snapshot.version).toBe(1);
    expect(snapshot.profileHash).toBe(fixture().profileHash);
    expect(presenterFramingProfileContentJson(snapshot)).toBe(presenterFramingProfileContentJson(fixture()));
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.tight)).toBe(true);
    expect(canonicalJson(input)).toBe(before);
  });

  it("increments the same identity and pins edited captures without changing old profile bytes", () => {
    const prior = fixture();
    const bytes = canonicalJson(prior);
    const input = calibration();
    input.observed_transforms.tight.Pan += 0.25;
    const next = snapshotPresenterFramingCalibration(input, prior, id);
    expect(next.id).toBe(prior.id);
    expect(next.version).toBe(prior.version + 1);
    expect(next.profileHash).not.toBe(prior.profileHash);
    expect(next.tight.Pan).toBe(input.observed_transforms.tight.Pan);
    input.observed_transforms.tight.Pan += 100;
    expect(next.tight.Pan).not.toBe(input.observed_transforms.tight.Pan);
    expect(canonicalJson(prior)).toBe(bytes);
  });

  it.each(["pending", "blocked", "manual_reported", "applied_verified", ""])("rejects incomplete or unrelated status %s", (status) => {
    expect(() => snapshotPresenterFramingCalibration({ ...calibration(), status }, null, id)).toThrow();
  });

  it.each([null, {}, { status: "sample_readback_complete" }])("refuses absent sample context/pair %#", (input) => {
    expect(() => snapshotPresenterFramingCalibration(input, null, id)).toThrow();
  });

  it.each(["wide", "tight"] as const)("requires both %s sample axes to preserve aspect ratio", (key) => {
    const input = calibration();
    input.observed_transforms[key].ZoomY += 0.5;
    expect(() => snapshotPresenterFramingCalibration(input, null, id)).toThrow();
  });

  it.each([{}, { wide: fixture().wide }, { wide: fixture().wide, tight: fixture().tight, medium: fixture().wide }])("requires exactly the paired captured members %#", (observed_transforms) => {
    expect(() => snapshotPresenterFramingCalibration({ ...calibration(), observed_transforms }, null, id)).toThrow();
  });

  it("refuses malformed context rather than filling missing raster facts", () => {
    const input = calibration();
    input.context = { ...input.context, sourceRaster: { ...input.context.sourceRaster, width: 0 } };
    expect(() => snapshotPresenterFramingCalibration(input, null, id)).toThrow();
  });

  it("requires the existing snapshot hash and exact same logical identity on revision", () => {
    const prior = fixture();
    expect(() => snapshotPresenterFramingCalibration(calibration(), { ...prior, profileHash: `sha256:${"0".repeat(64)}` }, id)).toThrow();
    expect(() => snapshotPresenterFramingCalibration(calibration(), prior, "f646c9c0-5f84-4e78-b6cc-1ec11d47a947")).toThrow();
    expect(() => snapshotPresenterFramingCalibration(calibration(), null, "invalid")).toThrow();
  });

  it("does not hash informational messages or auxiliary color limitations", () => {
    const input = calibration();
    const withNotes = { ...input, message: "Different readback note", color_limitations: ["Color unavailable"] };
    expect(snapshotPresenterFramingCalibration(input, null, id)).toEqual(snapshotPresenterFramingCalibration(withNotes, null, id));
  });

  it("refuses overflow of an existing profile version", () => {
    const prior = { ...fixture(), version: Number.MAX_SAFE_INTEGER };
    expect(() => snapshotPresenterFramingCalibration(calibration(), prior, id)).toThrow();
  });
});
