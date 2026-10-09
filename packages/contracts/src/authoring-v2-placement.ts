import type {
  NarrationBlockV2,
  ScriptDocumentV2,
  UnplacedPlacement,
  TimedPlacement,
  RationalTime,
} from "./generated/contracts-v2.js";
import { isWordAnchorCurrentV2 } from "./authoring-v2-validation.js";
import type {
  AuthoringDiagnosticV2,
  PlacementResolutionContextV2,
  PlacementResolutionResultV2,
} from "./authoring-v2.js";

interface Fraction {
  n: bigint;
  d: bigint;
}

type PointAnchor = NonNullable<TimedPlacement["start"]>;

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left;
  let b = right < 0n ? -right : right;
  while (b !== 0n) [a, b] = [b, a % b];
  return a === 0n ? 1n : a;
}

function fraction(n: bigint, d: bigint): Fraction {
  if (d === 0n) throw new RangeError("zero denominator");
  const sign = d < 0n ? -1n : 1n;
  const divisor = gcd(n, d);
  return { n: (n / divisor) * sign, d: (d / divisor) * sign };
}

function fromWire(value: RationalTime): Fraction | null {
  if (
    !Number.isSafeInteger(value.numerator) ||
    value.numerator < 0 ||
    !Number.isSafeInteger(value.denominator) ||
    value.denominator <= 0
  ) {
    return null;
  }
  if (gcd(BigInt(value.numerator), BigInt(value.denominator)) !== 1n) return null;
  return fraction(BigInt(value.numerator), BigInt(value.denominator));
}

function toWire(value: Fraction): RationalTime | null {
  const reduced = fraction(value.n, value.d);
  const numerator = Number(reduced.n);
  const denominator = Number(reduced.d);
  return Number.isSafeInteger(numerator) &&
    Number.isSafeInteger(denominator) &&
    numerator >= 0 &&
    denominator > 0
    ? { numerator, denominator }
    : null;
}

function add(left: Fraction, right: Fraction): Fraction {
  return fraction(left.n * right.d + right.n * left.d, left.d * right.d);
}

function subtract(left: Fraction, right: Fraction): Fraction {
  return fraction(left.n * right.d - right.n * left.d, left.d * right.d);
}

function compare(left: Fraction, right: Fraction): number {
  const difference = left.n * right.d - right.n * left.d;
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

function same(left: Fraction, right: Fraction): boolean {
  return compare(left, right) === 0;
}

export function placementAnchorKeyV2(anchor: PointAnchor): string {
  switch (anchor.kind) {
    case "word":
      return JSON.stringify([
        "word",
        anchor.anchor.blockId,
        anchor.anchor.tokenId,
        anchor.anchor.affinity,
        anchor.anchor.quotedWord,
        anchor.anchor.anchorVersion,
      ]);
    case "between_blocks":
      return JSON.stringify([
        "between_blocks",
        anchor.beforeBlockId,
        anchor.afterBlockId,
      ]);
    case "event_edge":
      return JSON.stringify(["event_edge", anchor.eventId, anchor.edge]);
  }
}

export function resolveTimedPlacementV2(
  placement: TimedPlacement | UnplacedPlacement,
  context: PlacementResolutionContextV2,
): PlacementResolutionResultV2 {
  if (placement.kind === "unplaced") {
    return { status: "unplaced", interval: null, diagnostics: [] };
  }
  if (placement.kind !== "timed") {
    return refused("PLACEMENT_NOT_TIMED", "A timed placement is required.");
  }

  const durationMs = placement.durationMs;
  if (
    durationMs !== undefined &&
    (!Number.isSafeInteger(durationMs) || durationMs <= 0)
  ) {
    return refused(
      "PLACEMENT_DURATION_INVALID",
      "Duration must be a positive safe integer number of milliseconds.",
    );
  }
  if (durationMs !== undefined && !placement.start && !placement.end) {
    const diagnostic: AuthoringDiagnosticV2 = {
      code: "PLACEMENT_DURATION_ONLY",
      message: "A duration without an authored anchor does not define an interval.",
      jsonPath: "/placement",
      blockId: context.blockId,
    };
    return { status: "unplaced", interval: null, diagnostics: [diagnostic] };
  }

  const row = context.document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 =>
      block.type === "narration" && block.id === context.blockId && block.state === "active",
  );
  if (!row) {
    return refused(
      "PLACEMENT_ROW_NOT_FOUND",
      "The placement row is not an active narration block.",
    );
  }

  const rowStart = fromWire(context.rowBounds.start);
  const rowEnd = fromWire(context.rowBounds.end);
  if (!rowStart || !rowEnd || compare(rowStart, rowEnd) >= 0) {
    return refused(
      "PLACEMENT_ROW_BOUNDS_INVALID",
      "The narration row bounds must be non-negative, exact, and increasing.",
    );
  }

  const start = placement.start
    ? anchorTime(placement.start, context, row)
    : null;
  const end = placement.end ? anchorTime(placement.end, context, row) : null;
  if (placement.start && !start) {
    return refused(
      "PLACEMENT_START_UNRESOLVED",
      "The authored start anchor is stale or has no exact time binding.",
    );
  }
  if (placement.end && !end) {
    return refused(
      "PLACEMENT_END_UNRESOLVED",
      "The authored end anchor is stale or has no exact time binding.",
    );
  }

  const duration =
    durationMs === undefined
      ? null
      : fraction(BigInt(durationMs), 1000n);

  let resolvedStart = start;
  let resolvedEnd = end;
  let resolvedDuration = duration;
  if (start && end && duration) {
    if (!same(subtract(end, start), duration)) {
      return refused(
        "PLACEMENT_THREE_POINT_MISMATCH",
        "Start, end, and duration do not agree at exact rational time.",
      );
    }
  } else if (start && end) {
    resolvedDuration = subtract(end, start);
  } else if (start && duration) {
    resolvedEnd = add(start, duration);
  } else if (end && duration) {
    resolvedStart = subtract(end, duration);
  } else {
    return refused(
      "PLACEMENT_TWO_FACTS_REQUIRED",
      "Two of start, end, and duration are required.",
    );
  }

  if (!resolvedStart || !resolvedEnd || !resolvedDuration) {
    return refused(
      "PLACEMENT_TWO_FACTS_REQUIRED",
      "Two of start, end, and duration are required.",
    );
  }
  if (
    resolvedStart.n < 0n ||
    resolvedEnd.n < 0n ||
    resolvedDuration.n <= 0n ||
    compare(resolvedStart, resolvedEnd) >= 0
  ) {
    return refused(
      "PLACEMENT_INTERVAL_INVALID",
      "The resolved interval must have positive duration and non-negative endpoints.",
    );
  }
  if (
    compare(resolvedStart, rowStart) < 0 ||
    compare(resolvedEnd, rowEnd) > 0
  ) {
    return refused(
      "PLACEMENT_OUT_OF_ROW",
      "The resolved interval must remain within the narration row.",
    );
  }

  const wireStart = toWire(resolvedStart);
  const wireEnd = toWire(resolvedEnd);
  const wireDuration = toWire(resolvedDuration);
  if (!wireStart || !wireEnd || !wireDuration) {
    return refused(
      "PLACEMENT_TIME_OVERFLOW",
      "The exact interval exceeds the safe rational wire range.",
    );
  }

  return {
    status: "resolved",
    interval: {
      start: wireStart,
      end: wireEnd,
      duration: wireDuration,
    },
    diagnostics: [],
  };
}

function anchorTime(
  anchor: PointAnchor,
  context: PlacementResolutionContextV2,
  row: Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }>,
): Fraction | null {
  if (anchor.kind === "word") {
    if (!isWordAnchorCurrentV2(anchor.anchor, row)) return null;
  } else if (anchor.kind === "between_blocks") {
    const blocks = context.document.activeDraft.blocks;
    const before = blocks.findIndex((block) => block.id === anchor.beforeBlockId);
    const after = blocks.findIndex((block) => block.id === anchor.afterBlockId);
    if (before < 0 || after !== before + 1) return null;
  } else if (!row.overlayEvents.some((event) => event.id === anchor.eventId)) {
    return null;
  }

  const value = context.anchorTimes[placementAnchorKeyV2(anchor)];
  return value ? fromWire(value) : null;
}

function refused(code: string, message: string): PlacementResolutionResultV2 {
  const diagnostic: AuthoringDiagnosticV2 = {
    code,
    message,
    jsonPath: "/placement",
  };
  return { status: "refused", interval: null, diagnostics: [diagnostic] };
}
