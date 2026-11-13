/** Pure frame math for a declared picture transition; no Resolve or media I/O. */
export interface V2Rate {
  numerator: number;
  denominator: number;
}

export interface V2Seconds {
  numerator: number;
  denominator: number;
}

export type V2TransitionAlignment = "left" | "center" | "right";

export interface V2TransitionSettings {
  durationFrames?: number;
  durationSeconds?: V2Seconds;
  alignment?: V2TransitionAlignment;
}

function positiveInteger(value: unknown, label: string): bigint {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    throw new RangeError(`${label} must be a positive safe integer`);
  }
  return BigInt(value);
}

/**
 * Durations are exact rational frame counts: never round a request before
 * attesting it or let Resolve silently shorten it. The measured native route
 * supports even frame durations only.
 */
export function requestedTransitionFrames(
  settings: V2TransitionSettings,
  rate: V2Rate,
): number {
  if (!settings || typeof settings !== "object" || Array.isArray(settings)) {
    throw new RangeError("transition settings must be an object");
  }
  if (Object.keys(settings).some((key) => !["durationFrames", "durationSeconds", "alignment"].includes(key))) {
    throw new RangeError("unknown transition setting");
  }
  if (settings.alignment !== undefined && !["left", "center", "right"].includes(settings.alignment)) {
    throw new RangeError("unknown transition alignment");
  }
  if ((settings.durationFrames === undefined) === (settings.durationSeconds === undefined)) {
    throw new RangeError("exactly one duration unit is required");
  }

  const rateNumerator = positiveInteger(rate?.numerator, "rate numerator");
  const rateDenominator = positiveInteger(rate?.denominator, "rate denominator");
  let frames: bigint;
  if (settings.durationFrames !== undefined) {
    frames = positiveInteger(settings.durationFrames, "durationFrames");
  } else {
    const seconds = settings.durationSeconds;
    if (!seconds || typeof seconds !== "object" || Array.isArray(seconds)) {
      throw new RangeError("durationSeconds must be a positive rational object");
    }
    if (Object.keys(seconds).some((key) => key !== "numerator" && key !== "denominator")) {
      throw new RangeError("unknown durationSeconds field");
    }
    const secondsNumerator = positiveInteger(seconds.numerator, "seconds numerator");
    const secondsDenominator = positiveInteger(seconds.denominator, "seconds denominator");
    const numerator = secondsNumerator * rateNumerator;
    const denominator = secondsDenominator * rateDenominator;
    if (numerator % denominator !== 0n) {
      throw new RangeError("transition seconds do not map to whole frames");
    }
    frames = numerator / denominator;
  }

  if (frames > BigInt(Number.MAX_SAFE_INTEGER) || frames % 2n !== 0n) {
    throw new RangeError("requested transition duration is not a supported even frame count");
  }
  return Number(frames);
}

/** Handles must describe the *delivered* clips, never just logical source bounds. */
export interface V2BoundaryGeometry {
  boundaryId: string;
  boundaryFrame: number;
  outgoingEndFrame: number;
  incomingStartFrame: number;
  outgoingDurationFrames: number;
  incomingDurationFrames: number;
  outgoingRightHandleFrames: number;
  incomingLeftHandleFrames: number;
}

export type V2BoundaryDecision =
  | { kind: "apply"; startFrame: number; endFrame: number; durationFrames: number }
  | { kind: "cut_insufficient_handles"; reason: string; durationFrames: number };

export function decideTransitionBoundary(
  geometry: V2BoundaryGeometry,
  frames: number,
  alignment: V2TransitionAlignment = "center",
): V2BoundaryDecision {
  if (
    !geometry || typeof geometry.boundaryId !== "string" || !geometry.boundaryId ||
    !Number.isSafeInteger(geometry.boundaryFrame) || geometry.boundaryFrame < 0 ||
    !Number.isSafeInteger(frames) || frames <= 0 || frames % 2 !== 0 ||
    !["left", "center", "right"].includes(alignment)
  ) {
    throw new RangeError("invalid transition boundary or requested duration");
  }
  if (
    geometry.outgoingEndFrame !== geometry.boundaryFrame ||
    geometry.incomingStartFrame !== geometry.boundaryFrame
  ) {
    throw new RangeError("transition boundary is not an exact adjacent cut");
  }
  const quantities = [
    geometry.outgoingDurationFrames,
    geometry.incomingDurationFrames,
    geometry.outgoingRightHandleFrames,
    geometry.incomingLeftHandleFrames,
  ];
  if (quantities.some((value) => !Number.isSafeInteger(value) || value < 0)) {
    throw new RangeError("transition geometry/handles are unknown or invalid");
  }

  const left = alignment === "left" ? frames : alignment === "center" ? frames / 2 : 0;
  const right = alignment === "right" ? frames : alignment === "center" ? frames / 2 : 0;
  const startFrame = geometry.boundaryFrame - left;
  const endFrame = geometry.boundaryFrame + right;
  if (!Number.isSafeInteger(endFrame)) {
    throw new RangeError("transition frame endpoint overflow");
  }
  if (
    geometry.outgoingDurationFrames < frames ||
    geometry.incomingDurationFrames < frames ||
    geometry.outgoingRightHandleFrames < right ||
    geometry.incomingLeftHandleFrames < left ||
    startFrame < 0
  ) {
    return {
      kind: "cut_insufficient_handles",
      reason: "delivered source handles or adjacent clip duration cannot cover exact effect",
      durationFrames: frames,
    };
  }
  return { kind: "apply", startFrame, endFrame, durationFrames: frames };
}
