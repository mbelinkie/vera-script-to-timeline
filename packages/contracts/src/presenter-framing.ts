import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";

export type PresenterFramingKey = "wide" | "tight";

export interface PresenterFramingRational {
  readonly numerator: number;
  readonly denominator: number;
}

export interface PresenterFramingTransform {
  readonly ZoomX: number;
  readonly ZoomY: number;
  readonly Pan: number;
  readonly Tilt: number;
}

export interface PresenterFramingContext {
  readonly sourceRaster: {
    readonly width: number;
    readonly height: number;
    readonly pixelAspect: PresenterFramingRational;
    readonly orientation: string;
    readonly scalingContext: string;
    readonly frameRate: PresenterFramingRational;
  };
  readonly timelineRaster: {
    readonly width: number;
    readonly height: number;
    readonly pixelAspect: PresenterFramingRational;
    readonly frameRate: PresenterFramingRational;
  };
  readonly resolve: {
    readonly product: string;
    readonly version: string;
    readonly build: string;
    readonly apiContext: string;
  };
  readonly adapter: {
    readonly release: string;
    readonly sourceIdentity: string;
  };
}

export interface PresenterFramingInvariants {
  readonly TransformEnabled: true;
  readonly DynamicZoomEnabled: false;
  readonly RotationAngle: 0;
  readonly AnchorPointX: 0;
  readonly AnchorPointY: 0;
  readonly FlipX: false;
  readonly FlipY: false;
}

export interface PresenterFramingProfileContent {
  readonly schemaVersion: "presenter-framing-profile-snapshot/v1";
  readonly context: PresenterFramingContext;
  readonly invariants: PresenterFramingInvariants;
  readonly wide: PresenterFramingTransform;
  readonly tight: PresenterFramingTransform;
}

export interface PresenterFramingProfileSnapshot extends PresenterFramingProfileContent {
  readonly id: string;
  readonly version: number;
  readonly profileHash: string;
}

export type PresenterFramingProfilePin = Pick<PresenterFramingProfileSnapshot, "id" | "version" | "profileHash">;

/** Return only the content covered by profileHash; evidence locators belong beside the snapshot. */
export function presenterFramingProfileContent(snapshot: PresenterFramingProfileSnapshot): PresenterFramingProfileContent {
  return Object.freeze({
    schemaVersion: snapshot.schemaVersion,
    context: snapshot.context,
    invariants: snapshot.invariants,
    wide: snapshot.wide,
    tight: snapshot.tight,
  });
}

/** The exact canonical JSON bytes hashed by the snapshot and shared with other runtimes. */
export function presenterFramingProfileContentJson(snapshot: PresenterFramingProfileSnapshot): string {
  return canonicalJson(presenterFramingProfileContent(snapshot));
}

export function presenterFramingProfileHash(snapshot: PresenterFramingProfileSnapshot): string {
  return sha256CanonicalJson(presenterFramingProfileContent(snapshot));
}

export function presenterFramingProfilePin(snapshot: PresenterFramingProfileSnapshot): PresenterFramingProfilePin {
  return Object.freeze({ id: snapshot.id, version: snapshot.version, profileHash: snapshot.profileHash });
}

export function validatePresenterFramingProfile(value: unknown): PresenterFramingProfileSnapshot {
  function object(input: unknown, keys: string[], label: string): Record<string, unknown> {
    if (input === null || typeof input !== "object" || Array.isArray(input)) throw new Error(`Invalid ${label} object.`);
    const prototype: unknown = Object.getPrototypeOf(input);
    if (prototype !== Object.prototype && prototype !== null) throw new Error(`Invalid ${label} prototype.`);
    const actual = Reflect.ownKeys(input);
    if (actual.length !== keys.length || actual.some((key) => typeof key !== "string" || !keys.includes(key))
      || Object.values(Object.getOwnPropertyDescriptors(input)).some((descriptor) => !("value" in descriptor) || !descriptor.enumerable)) throw new Error(`Unexpected or missing ${label} fields.`);
    return input as Record<string, unknown>;
  }
  function positiveInteger(input: unknown, label: string): void {
    if (typeof input !== "number" || !Number.isSafeInteger(input) || input <= 0) throw new Error(`Invalid ${label}.`);
  }
  function text(input: unknown, label: string): void {
    if (typeof input !== "string" || ["", "unknown", "unspecified", "guessed", "n/a"].includes(input.trim().toLowerCase())) throw new Error(`Missing captured ${label}.`);
  }
  function rational(input: unknown, label: string): void {
    const rate = object(input, ["numerator", "denominator"], label);
    positiveInteger(rate.numerator, `${label} numerator`);
    positiveInteger(rate.denominator, `${label} denominator`);
  }
  function transform(input: unknown, label: string): void {
    const tuple = object(input, ["ZoomX", "ZoomY", "Pan", "Tilt"], label);
    if (Object.values(tuple).some((number) => typeof number !== "number" || !Number.isFinite(number))
      || typeof tuple.ZoomX !== "number" || tuple.ZoomX <= 0 || tuple.ZoomX !== tuple.ZoomY) throw new Error(`Invalid ${label} transform.`);
  }
  function freeze<T>(input: T): T {
    if (input !== null && typeof input === "object") {
      for (const nested of Object.values(input)) freeze(nested);
      Object.freeze(input);
    }
    return input;
  }
  const root = object(value, ["schemaVersion", "id", "version", "profileHash", "context", "invariants", "wide", "tight"], "profile");
  if (root.schemaVersion !== "presenter-framing-profile-snapshot/v1") throw new Error("Unsupported framing profile schema.");
  if (typeof root.id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(root.id)) throw new Error("Invalid profile UUID.");
  positiveInteger(root.version, "profile version");
  if (typeof root.profileHash !== "string" || !/^sha256:[a-f0-9]{64}$/u.test(root.profileHash)) throw new Error("Invalid profile hash.");
  const context = object(root.context, ["sourceRaster", "timelineRaster", "resolve", "adapter"], "context");
  const source = object(context.sourceRaster, ["width", "height", "pixelAspect", "orientation", "scalingContext", "frameRate"], "source raster");
  const timeline = object(context.timelineRaster, ["width", "height", "pixelAspect", "frameRate"], "timeline raster");
  for (const raster of [source, timeline]) {
    positiveInteger(raster.width, "raster width");
    positiveInteger(raster.height, "raster height");
    rational(raster.pixelAspect, "pixel aspect");
    rational(raster.frameRate, "frame rate");
  }
  text(source.orientation, "source orientation");
  text(source.scalingContext, "source scaling context");
  const resolve = object(context.resolve, ["product", "version", "build", "apiContext"], "Resolve context");
  const adapter = object(context.adapter, ["release", "sourceIdentity"], "adapter context");
  for (const [label, field] of Object.entries({ ...resolve, ...adapter })) text(field, label);
  const invariants = object(root.invariants, ["TransformEnabled", "DynamicZoomEnabled", "RotationAngle", "AnchorPointX", "AnchorPointY", "FlipX", "FlipY"], "invariants");
  const neutral = { TransformEnabled: true, DynamicZoomEnabled: false, RotationAngle: 0, AnchorPointX: 0, AnchorPointY: 0, FlipX: false, FlipY: false };
  if (Object.entries(neutral).some(([key, expected]) => invariants[key] !== expected)) throw new Error("Framing profile invariants must be neutral.");
  transform(root.wide, "wide");
  transform(root.tight, "tight");
  const snapshot = structuredClone(value) as PresenterFramingProfileSnapshot;
  if (presenterFramingProfileHash(snapshot) !== snapshot.profileHash) throw new Error("Stale framing profile hash.");
  return freeze(snapshot);
}

/** Pin captured raw sample values; this creates data, not native qualification. */
export function snapshotPresenterFramingCalibration(calibration: unknown, prior: PresenterFramingProfileSnapshot | null, id: string): PresenterFramingProfileSnapshot {
  function isPlainObject(value: unknown): value is Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
    const prototype: unknown = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  function assertExactRecord(
    value: unknown,
    keys: readonly string[],
    label: string,
  ): Record<string, unknown> {
    if (!isPlainObject(value)) throw new Error(`Invalid ${label} object.`);
    const ownKeys = Reflect.ownKeys(value);
    if (
      ownKeys.length !== keys.length ||
      ownKeys.some((key) => typeof key !== "string" || !keys.includes(key))
    ) {
      throw new Error(`Unexpected or missing ${label} fields.`);
    }
    for (const key of keys) {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) {
        throw new Error(`Invalid ${label} field ${key}.`);
      }
    }
    return value;
  }

  const cal = assertExactRecord(
    calibration,
    ["status", "message", "context", "observed_transforms", "color_limitations"],
    "calibration result",
  );

  if (cal.status !== "sample_readback_complete") {
    throw new Error("Unsupported calibration status.");
  }
  if (typeof cal.message !== "string") {
    throw new Error("Invalid calibration message.");
  }
  if (
    !Array.isArray(cal.color_limitations) ||
    !cal.color_limitations.every((item) => typeof item === "string")
  ) {
    throw new Error("Invalid color limitations.");
  }

  if (!isPlainObject(cal.context)) {
    throw new Error("Missing captured context.");
  }
  const context = cal.context as unknown as PresenterFramingContext;

  const observedTransforms = assertExactRecord(
    cal.observed_transforms,
    ["wide", "tight"],
    "observed transforms",
  );
  const wideValue = observedTransforms.wide;
  const tightValue = observedTransforms.tight;
  if (!isPlainObject(wideValue) || !isPlainObject(tightValue)) {
    throw new Error("Malformed transform tuple.");
  }
  const wide = wideValue as unknown as PresenterFramingTransform;
  const tight = tightValue as unknown as PresenterFramingTransform;

  const neutrals: PresenterFramingInvariants = {
    TransformEnabled: true,
    DynamicZoomEnabled: false,
    RotationAngle: 0,
    AnchorPointX: 0,
    AnchorPointY: 0,
    FlipX: false,
    FlipY: false,
  };

  let version = 1;
  if (prior !== null) {
    const priorValidated = validatePresenterFramingProfile(prior);
    if (priorValidated.id !== id) {
      throw new Error("Supplied identity does not match prior profile.");
    }
    const nextVersion = priorValidated.version + 1;
    if (!Number.isSafeInteger(nextVersion)) {
      throw new Error("Profile version overflow.");
    }
    version = nextVersion;
  }

  const snapshotWithoutHash = {
    schemaVersion: "presenter-framing-profile-snapshot/v1" as const,
    id,
    version,
    context,
    invariants: neutrals,
    wide,
    tight,
  };

  const profileHash = presenterFramingProfileHash({
    ...snapshotWithoutHash,
    profileHash: "",
  });

  const candidate: PresenterFramingProfileSnapshot = {
    ...snapshotWithoutHash,
    profileHash,
  };

  return validatePresenterFramingProfile(candidate);
}
