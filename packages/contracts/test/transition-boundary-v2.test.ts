import { describe, expect, it } from "vitest";

import {
  decideTransitionBoundary,
  requestedTransitionFrames,
} from "../src/transition-boundary-v2.js";

const adjacent = {
  boundaryId: "pair-A-B",
  boundaryFrame: 72,
  outgoingEndFrame: 72,
  incomingStartFrame: 72,
  outgoingDurationFrames: 72,
  incomingDurationFrames: 72,
  outgoingRightHandleFrames: 24,
  incomingLeftHandleFrames: 24,
};

describe("#88 exact transition duration and boundary planning", () => {
  it("converts authored frames and exact rational seconds without rounding", () => {
    expect(requestedTransitionFrames({ durationFrames: 24 }, { numerator: 24000, denominator: 1001 })).toBe(24);
    expect(requestedTransitionFrames({ durationSeconds: { numerator: 1, denominator: 1 } }, { numerator: 24, denominator: 1 })).toBe(24);
    expect(requestedTransitionFrames({ durationSeconds: { numerator: 1001, denominator: 1000 } }, { numerator: 24000, denominator: 1001 })).toBe(24);
    expect(() => requestedTransitionFrames({ durationSeconds: { numerator: 1, denominator: 1 } }, { numerator: 24000, denominator: 1001 })).toThrow(/whole frames/);
    expect(() => requestedTransitionFrames({ durationFrames: 24, durationSeconds: { numerator: 1, denominator: 1 } }, { numerator: 24, denominator: 1 })).toThrow(/exactly one/);
    expect(() => requestedTransitionFrames({}, { numerator: 24, denominator: 1 })).toThrow(/exactly one/);
  });

  it("rejects unknown settings, invalid rates, unsafe and odd durations", () => {
    const rate = { numerator: 24, denominator: 1 };
    expect(() => requestedTransitionFrames({ durationFrames: 23 }, rate)).toThrow(/even frame/);
    expect(() => requestedTransitionFrames({ durationFrames: 0 }, rate)).toThrow(/positive safe integer/);
    expect(() => requestedTransitionFrames({ durationFrames: Number.MAX_SAFE_INTEGER + 1 }, rate)).toThrow(/positive safe integer/);
    expect(() => requestedTransitionFrames({ durationFrames: 24 }, { numerator: 0, denominator: 1 })).toThrow(/rate numerator/);
    expect(() => requestedTransitionFrames({ durationSeconds: { numerator: 1, denominator: 0 } }, rate)).toThrow(/seconds denominator/);
    expect(() => requestedTransitionFrames({ durationSeconds: { numerator: 1, denominator: 1, unit: "ms" } } as never, rate)).toThrow(/unknown durationSeconds field/);
    expect(() => requestedTransitionFrames({ durationFrames: 24, blend: 1 } as never, rate)).toThrow(/unknown transition setting/);
    expect(() => requestedTransitionFrames({ durationFrames: 24, alignment: "middle" } as never, rate)).toThrow(/alignment/);
    expect(() => requestedTransitionFrames({ durationSeconds: { numerator: Number.MAX_SAFE_INTEGER, denominator: 1 } }, { numerator: 48, denominator: 1 })).toThrow(/even frame count/);
  });

  it("matches measured left/center/right native transition spans", () => {
    expect(decideTransitionBoundary(adjacent, 24)).toEqual({ kind: "apply", startFrame: 60, endFrame: 84, durationFrames: 24 });
    expect(decideTransitionBoundary(adjacent, 24, "left")).toEqual({ kind: "apply", startFrame: 48, endFrame: 72, durationFrames: 24 });
    expect(decideTransitionBoundary(adjacent, 24, "right")).toEqual({ kind: "apply", startFrame: 72, endFrame: 96, durationFrames: 24 });
  });

  it("requires the appropriate delivered handle on each side of the cut", () => {
    expect(decideTransitionBoundary({ ...adjacent, outgoingRightHandleFrames: 0, incomingLeftHandleFrames: 24 }, 24, "left").kind).toBe("apply");
    expect(decideTransitionBoundary({ ...adjacent, outgoingRightHandleFrames: 24, incomingLeftHandleFrames: 0 }, 24, "right").kind).toBe("apply");
    for (const geometry of [
      { ...adjacent, outgoingRightHandleFrames: 2, incomingLeftHandleFrames: 2 },
      { ...adjacent, outgoingDurationFrames: 23 },
      { ...adjacent, incomingDurationFrames: 23 },
      { ...adjacent, boundaryFrame: 8, outgoingEndFrame: 8, incomingStartFrame: 8 },
    ]) {
      expect(decideTransitionBoundary(geometry, 24)).toMatchObject({ kind: "cut_insufficient_handles", durationFrames: 24 });
    }
  });

  it("refuses a gap, unknown handles, invalid geometry and unsafe endpoints", () => {
    expect(() => decideTransitionBoundary({ ...adjacent, incomingStartFrame: 78 }, 24)).toThrow(/adjacent cut/);
    expect(() => decideTransitionBoundary({ ...adjacent, incomingLeftHandleFrames: -1 }, 24)).toThrow(/unknown or invalid/);
    expect(() => decideTransitionBoundary({ ...adjacent, outgoingRightHandleFrames: Number.NaN }, 24)).toThrow(/unknown or invalid/);
    expect(() => decideTransitionBoundary(adjacent, 23)).toThrow(/invalid transition/);
    expect(() => decideTransitionBoundary({ ...adjacent, boundaryFrame: Number.MAX_SAFE_INTEGER, outgoingEndFrame: Number.MAX_SAFE_INTEGER, incomingStartFrame: Number.MAX_SAFE_INTEGER }, 24)).toThrow(/endpoint overflow/);
    expect(() => decideTransitionBoundary(adjacent, 24, "middle" as never)).toThrow(/invalid transition/);
  });
});
