import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";
import profileFixtureJson from "./fixtures/presenter-framing/profile.json" with { type: "json" };
import {
  presenterFramingProfileContent,
  presenterFramingProfileContentJson,
  presenterFramingProfileHash,
  presenterFramingProfilePin,
  validatePresenterFramingProfile,
  type PresenterFramingProfileSnapshot,
} from "../src/presenter-framing.js";

type Mutable<T> = T extends object ? { -readonly [K in keyof T]: Mutable<T[K]> } : T;
type MutableProfile = Mutable<PresenterFramingProfileSnapshot>;

const fixture = deepFreeze(structuredClone(profileFixtureJson)) as PresenterFramingProfileSnapshot;
const profileContentBytes = readFileSync(new URL("./fixtures/presenter-framing/profile-content.json", import.meta.url), "utf8");
const expectedProfileHash = "sha256:7ed635c2ece1fa21b755d8e6e42c828721886e1880e891531bab0b0b30c559cb";

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const nested of Object.values(value)) deepFreeze(nested);
    Object.freeze(value);
  }
  return value;
}

function mutableFixture(): MutableProfile {
  return structuredClone(fixture) as MutableProfile;
}

function objectAtPath(value: object, path: string[]): Record<string, unknown> {
  let current: unknown = value;
  for (const segment of path) current = (current as Record<string, unknown>)[segment];
  if (current === null || typeof current !== "object") throw new Error(`Path is not an object: ${path.join(".")}`);
  return current as Record<string, unknown>;
}

function setAtPath(value: object, path: string[], replacement: unknown): void {
  const last = path.at(-1);
  if (last === undefined) throw new Error("A path must have at least one segment.");
  objectAtPath(value, path.slice(0, -1))[last] = replacement;
}

function deleteAtPath(value: object, path: string[]): void {
  const last = path.at(-1);
  if (last === undefined) throw new Error("A path must have at least one segment.");
  delete objectAtPath(value, path.slice(0, -1))[last];
}

function rehashedCandidate(change: (candidate: MutableProfile) => void): MutableProfile {
  const candidate = mutableFixture();
  change(candidate);
  candidate.profileHash = presenterFramingProfileHash(candidate);
  return candidate;
}

const exactKeyObjects = [
  { name: "snapshot", path: [] },
  { name: "context", path: ["context"] },
  { name: "source raster", path: ["context", "sourceRaster"] },
  { name: "source pixel aspect", path: ["context", "sourceRaster", "pixelAspect"] },
  { name: "source frame rate", path: ["context", "sourceRaster", "frameRate"] },
  { name: "timeline raster", path: ["context", "timelineRaster"] },
  { name: "timeline pixel aspect", path: ["context", "timelineRaster", "pixelAspect"] },
  { name: "timeline frame rate", path: ["context", "timelineRaster", "frameRate"] },
  { name: "Resolve context", path: ["context", "resolve"] },
  { name: "adapter context", path: ["context", "adapter"] },
  { name: "invariants", path: ["invariants"] },
  { name: "wide transform", path: ["wide"] },
  { name: "tight transform", path: ["tight"] },
];

const requiredKeysByObject: Array<{ name: string; path: string[]; keys: string[] }> = [
  { name: "snapshot", path: [], keys: ["schemaVersion", "id", "version", "profileHash", "context", "invariants", "wide", "tight"] },
  { name: "context", path: ["context"], keys: ["sourceRaster", "timelineRaster", "resolve", "adapter"] },
  { name: "source raster", path: ["context", "sourceRaster"], keys: ["width", "height", "pixelAspect", "orientation", "scalingContext", "frameRate"] },
  { name: "source pixel aspect", path: ["context", "sourceRaster", "pixelAspect"], keys: ["numerator", "denominator"] },
  { name: "source frame rate", path: ["context", "sourceRaster", "frameRate"], keys: ["numerator", "denominator"] },
  { name: "timeline raster", path: ["context", "timelineRaster"], keys: ["width", "height", "pixelAspect", "frameRate"] },
  { name: "timeline pixel aspect", path: ["context", "timelineRaster", "pixelAspect"], keys: ["numerator", "denominator"] },
  { name: "timeline frame rate", path: ["context", "timelineRaster", "frameRate"], keys: ["numerator", "denominator"] },
  { name: "Resolve context", path: ["context", "resolve"], keys: ["product", "version", "build", "apiContext"] },
  { name: "adapter context", path: ["context", "adapter"], keys: ["release", "sourceIdentity"] },
  { name: "invariants", path: ["invariants"], keys: ["TransformEnabled", "DynamicZoomEnabled", "RotationAngle", "AnchorPointX", "AnchorPointY", "FlipX", "FlipY"] },
  { name: "wide transform", path: ["wide"], keys: ["ZoomX", "ZoomY", "Pan", "Tilt"] },
  { name: "tight transform", path: ["tight"], keys: ["ZoomX", "ZoomY", "Pan", "Tilt"] },
];

const missingKeyCases = requiredKeysByObject.flatMap(({ name, path, keys }) => keys.map((key) => ({
  name: `${name} rejects a missing ${key}`,
  path: [...path, key],
})));

const contextTextPaths = [
  ["context", "sourceRaster", "orientation"],
  ["context", "sourceRaster", "scalingContext"],
  ["context", "resolve", "product"],
  ["context", "resolve", "version"],
  ["context", "resolve", "build"],
  ["context", "resolve", "apiContext"],
  ["context", "adapter", "release"],
  ["context", "adapter", "sourceIdentity"],
];

const contextPlaceholders = ["", "   ", "unknown", "unspecified", "guessed", "n/a"];
const contextPlaceholderCases = contextTextPaths.flatMap((path) => contextPlaceholders.map((value) => ({
  name: `${path.join(".")} rejects ${JSON.stringify(value)}`,
  path,
  value,
})));

const dimensionPaths = [
  ["context", "sourceRaster", "width"],
  ["context", "sourceRaster", "height"],
  ["context", "timelineRaster", "width"],
  ["context", "timelineRaster", "height"],
];
const rationalPaths = [
  ["context", "sourceRaster", "pixelAspect", "numerator"],
  ["context", "sourceRaster", "pixelAspect", "denominator"],
  ["context", "sourceRaster", "frameRate", "numerator"],
  ["context", "sourceRaster", "frameRate", "denominator"],
  ["context", "timelineRaster", "pixelAspect", "numerator"],
  ["context", "timelineRaster", "pixelAspect", "denominator"],
  ["context", "timelineRaster", "frameRate", "numerator"],
  ["context", "timelineRaster", "frameRate", "denominator"],
];
const invalidPositiveIntegers = [0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY];

const nonFiniteTransformCases = ["wide", "tight"].flatMap((member) => ["ZoomX", "ZoomY", "Pan", "Tilt"].flatMap((property) => [
  Number.NaN,
  Number.POSITIVE_INFINITY,
  Number.NEGATIVE_INFINITY,
].map((value) => ({ member, property, value }))));

const invalidInvariantCases: Array<{ property: string; value: unknown }> = [
  { property: "TransformEnabled", value: false },
  { property: "DynamicZoomEnabled", value: true },
  { property: "RotationAngle", value: 1 },
  { property: "AnchorPointX", value: 0.01 },
  { property: "AnchorPointY", value: -0.01 },
  { property: "FlipX", value: true },
  { property: "FlipY", value: true },
];

describe("presenter framing profile boundary", () => {
  it("accepts the frozen complete paired fixture without guessing context", () => {
    expect(validatePresenterFramingProfile(fixture)).toEqual(fixture);
  });

  it.each(missingKeyCases)("$name", ({ path }) => {
    expect(() => validatePresenterFramingProfile(rehashedCandidate((candidate) => deleteAtPath(candidate, path)))).toThrow();
  });

  it.each(exactKeyObjects)("rejects an unknown key in the $name object", ({ path }) => {
    const candidate = rehashedCandidate((profile) => {
      objectAtPath(profile, path).unexpected = "not part of v1";
    });
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it.each(contextPlaceholderCases)("rejects guessed or empty context at $name", ({ path, value }) => {
    const candidate = rehashedCandidate((profile) => setAtPath(profile, path, value));
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it.each(dimensionPaths.flatMap((path) => invalidPositiveIntegers.map((value) => ({ path, value }))))(
    "rejects invalid raster dimensions at $path with $value",
    ({ path, value }) => {
      const candidate = mutableFixture();
      setAtPath(candidate, path, value);
      if (Number.isFinite(value)) candidate.profileHash = presenterFramingProfileHash(candidate);
      expect(() => validatePresenterFramingProfile(candidate)).toThrow();
    },
  );

  it.each(rationalPaths.flatMap((path) => invalidPositiveIntegers.map((value) => ({ path, value }))))(
    "rejects invalid context rationals at $path with $value",
    ({ path, value }) => {
      const candidate = mutableFixture();
      setAtPath(candidate, path, value);
      if (Number.isFinite(value)) candidate.profileHash = presenterFramingProfileHash(candidate);
      expect(() => validatePresenterFramingProfile(candidate)).toThrow();
    },
  );

  it.each(nonFiniteTransformCases)("rejects non-finite $member.$property", ({ member, property, value }) => {
    const candidate = mutableFixture();
    setAtPath(candidate, [member, property], value);
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it.each([
    { member: "wide", property: "ZoomX", value: 0 },
    { member: "wide", property: "ZoomY", value: -0.25 },
    { member: "tight", property: "ZoomX", value: -1 },
    { member: "tight", property: "ZoomY", value: 0 },
  ])("requires positive zoom on $member.$property", ({ member, property, value }) => {
    const candidate = rehashedCandidate((profile) => setAtPath(profile, [member, property], value));
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it.each(["wide", "tight"])("requires equal zoom axes for %s", (member) => {
    const candidate = rehashedCandidate((profile) => {
      setAtPath(profile, [member, "ZoomY"], (profile[member as "wide" | "tight"].ZoomY + 0.125));
    });
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it.each(invalidInvariantCases)("requires the neutral invariant $property=$value", ({ property, value }) => {
    const candidate = rehashedCandidate((profile) => setAtPath(profile, ["invariants", property], value));
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it("requires a UUID identity, positive integer version, and lowercase SHA-256 profile hash", () => {
    const invalidCases = [
      rehashedCandidate((profile) => { profile.id = "profile-1"; }),
      rehashedCandidate((profile) => { profile.version = 0; }),
      rehashedCandidate((profile) => { profile.version = 1.5; }),
      { ...fixture, profileHash: `sha256:${"A".repeat(64)}` },
    ];
    for (const candidate of invalidCases) expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it("rejects a well-formed but stale profile hash", () => {
    const candidate = mutableFixture();
    candidate.profileHash = `sha256:${"0".repeat(64)}`;
    expect(() => validatePresenterFramingProfile(candidate)).toThrow();
  });

  it("returns a detached, deeply immutable snapshot whose prior bytes cannot change", () => {
    const input = mutableFixture();
    const snapshot = validatePresenterFramingProfile(input);
    const priorBytes = presenterFramingProfileContentJson(snapshot);
    input.context.sourceRaster.width = 1280;
    input.wide.Pan = 999;
    expect(presenterFramingProfileContentJson(snapshot)).toBe(priorBytes);
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.context.sourceRaster)).toBe(true);
    expect(Reflect.set(snapshot.context.sourceRaster, "width", 1280)).toBe(false);
    expect(presenterFramingProfileContentJson(snapshot)).toBe(priorBytes);
  });

  it("projects an exact pin from a validated snapshot", () => {
    expect(presenterFramingProfilePin(fixture)).toEqual({
      id: fixture.id,
      version: fixture.version,
      profileHash: fixture.profileHash,
    });
    expect(Object.isFrozen(presenterFramingProfilePin(fixture))).toBe(true);
  });
});

describe("presenter framing profile hash", () => {
  it("matches the fixed SHA-256 hash of the paired content fixture", () => {
    expect(fixture.profileHash).toBe(expectedProfileHash);
    expect(presenterFramingProfileHash(fixture)).toBe(expectedProfileHash);
  });

  it("exposes the exact canonical identity-content bytes for another runtime", () => {
    expect(presenterFramingProfileContentJson(fixture)).toBe(profileContentBytes);
    expect(presenterFramingProfileContent(fixture)).toEqual(JSON.parse(profileContentBytes));
  });

  it("excludes snapshot identity, version, profile hash, and external receipt locators", () => {
    const candidate = mutableFixture();
    candidate.id = "a57e1e62-e649-4732-9b32-93412fa016a4";
    candidate.version += 1;
    candidate.profileHash = `sha256:${"0".repeat(64)}`;
    const withReceipt = { ...candidate, externalReceiptLocator: "/machine-specific/receipt.json" } as PresenterFramingProfileSnapshot;
    expect(presenterFramingProfileHash(candidate)).toBe(expectedProfileHash);
    expect(presenterFramingProfileHash(withReceipt)).toBe(expectedProfileHash);
  });

  it.each([
    { name: "schema version", path: ["schemaVersion"], value: "presenter-framing-profile-snapshot/v2" },
    { name: "context", path: ["context", "resolve", "build"], value: "changed-build" },
    { name: "neutral invariants", path: ["invariants", "FlipX"], value: true },
    { name: "wide transform", path: ["wide", "Pan"], value: 0.25 },
    { name: "tight transform", path: ["tight", "Tilt"], value: 0.875 },
  ])("includes $name in the canonical hash", ({ path, value }) => {
    const candidate = mutableFixture();
    setAtPath(candidate, path, value);
    expect(presenterFramingProfileHash(candidate)).not.toBe(expectedProfileHash);
  });
});
