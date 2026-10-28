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
  void value;
  throw new Error("not implemented");
}
