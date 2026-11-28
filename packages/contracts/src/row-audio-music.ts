import type { RationalRate } from "./generated/contracts-v2.js";

/** One duration-bearing, active program row in compiled timeline order. */
export interface MusicRowBounds {
  id: string;
  startFrame: number;
  endFrame: number;
  /** Optional independent guards when the caller retains authoring metadata. */
  sectionId?: string;
  active?: boolean;
}

export interface MusicSpanFrames {
  recordRange: { startFrame: number; endFrame: number };
  sourceRange: { startFrame: number; endFrame: number };
  requestedEndFrame: number;
  shorterThanRows: boolean;
  fadeInFrames: number;
  fadeOutFrames: number;
}

export function availableMusicFrames(
  sourceSamples: number,
  sampleRate: number,
  timelineRate: { numerator: number; denominator: number },
): number {
  if (![sourceSamples, sampleRate, timelineRate.numerator, timelineRate.denominator]
    .every((value) => Number.isSafeInteger(value) && value > 0)) {
    throw new RangeError("music requires verified positive sample/rate integers");
  }
  const available = BigInt(sourceSamples) * BigInt(timelineRate.numerator)
    / (BigInt(sampleRate) * BigInt(timelineRate.denominator));
  if (available > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError("music duration exceeds safe frame range");
  }
  return Number(available);
}

/** Quantize an explicit fade upward to whole frames within the delivered cue. */
export function resolveMusicFadeOutFrames(fadeOutMs: number, cueFrames: number, rate: RationalRate): number {
  if (!Number.isSafeInteger(fadeOutMs) || fadeOutMs < 0) {
    throw new RangeError("Music fade-out must be a nonnegative whole number of milliseconds.");
  }
  if (![cueFrames, rate.numerator, rate.denominator].every((value) => Number.isSafeInteger(value) && value > 0)) {
    throw new RangeError("Music fade-out needs a positive exact cue duration and frame rate.");
  }
  const units = 1000n * BigInt(rate.denominator);
  const requested = BigInt(fadeOutMs) * BigInt(rate.numerator);
  if (requested > BigInt(cueFrames) * units) {
    throw new RangeError("Music fade-out is longer than the cue. Shorten the fade or extend the cue.");
  }
  return Number((requested + units - 1n) / units);
}

export function planAnchoredMusicFrames(
  sourceIn: number | undefined,
  sourceOut: number | undefined,
  timelineIn: number | undefined,
  timelineOut: number | undefined,
  sourceLength: number,
  timelineLength: number,
): MusicSpanFrames {
  const points = [sourceIn, sourceOut, timelineIn, timelineOut];
  if (points.filter((point) => point !== undefined).length !== 3) {
    throw new RangeError("Fix exactly three of the four music timing points.");
  }
  // Do the arithmetic exactly even when intermediate sums exceed safe integers.
  const [si, so, ti, to] = points.map((point) => BigInt(point ?? 0)) as [bigint, bigint, bigint, bigint];
  const sourceStart = Number(sourceIn === undefined ? so - (to - ti) : si);
  const sourceEnd = Number(sourceOut === undefined ? si + (to - ti) : so);
  const recordStart = Number(timelineIn === undefined ? to - (so - si) : ti);
  const recordEnd = Number(timelineOut === undefined ? ti + (so - si) : to);
  if (sourceStart < 0 || sourceEnd > sourceLength || sourceEnd <= sourceStart) {
    throw new RangeError("The music window falls outside the source or has no duration. Adjust a source trim or move a timeline pin.");
  }
  if (recordStart < 0 || recordEnd > timelineLength || recordEnd <= recordStart) {
    throw new RangeError("The music cue falls outside the built timeline or has no duration. Move a timeline pin or shorten the source window.");
  }
  const fade = Math.min(6, Math.floor((recordEnd - recordStart) / 2));
  return {
    recordRange: { startFrame: recordStart, endFrame: recordEnd },
    sourceRange: { startFrame: sourceStart, endFrame: sourceEnd },
    requestedEndFrame: recordEnd,
    shorterThanRows: false,
    fadeInFrames: fade,
    fadeOutFrames: fade,
  };
}

/**
 * Project one verified PCM source onto consecutive active rows. Frame ranges
 * are half-open; a partial last audio frame is never passed to Resolve.
 *
 * The compiler selects program rows and validates section membership before
 * calling this pure helper. If supplied, active and sectionId are checked here
 * too. Source metadata must already have passed the local hash/WAV verifier.
 */
export function planMusicSpanFrames(
  rows: readonly MusicRowBounds[],
  startRowId: string,
  endRowId: string,
  sourceSamples: number,
  sampleRate: number,
  timelineRate: { numerator: number; denominator: number },
): MusicSpanFrames | null {
  const ids = new Set<string>();
  for (const row of rows) {
    if (!row.id || ids.has(row.id)) {
      throw new RangeError("music rows need unique, nonempty identities");
    }
    ids.add(row.id);
  }
  const from = rows.findIndex((row) => row.id === startRowId);
  const through = rows.findIndex((row) => row.id === endRowId);
  if (from < 0 || through < from) {
    throw new RangeError("music span endpoints are not ordered active rows");
  }

  const section = rows[from]!.sectionId;
  for (let i = from; i <= through; i++) {
    const row = rows[i]!;
    if (
      row.active === false || row.sectionId !== section ||
      !Number.isSafeInteger(row.startFrame) || !Number.isSafeInteger(row.endFrame) ||
      row.startFrame < 0 || row.endFrame <= row.startFrame ||
      (i > from && rows[i - 1]!.endFrame !== row.startFrame)
    ) {
      throw new RangeError("music span has inactive, cross-section, or noncontiguous row geometry");
    }
  }

  const available = availableMusicFrames(sourceSamples, sampleRate, timelineRate);
  const first = rows[from]!.startFrame;
  const desiredEnd = rows[through]!.endFrame;
  const emittedFrames = Math.min(desiredEnd - first, available);
  if (emittedFrames <= 0) return null;
  const last = first + emittedFrames;
  if (!Number.isSafeInteger(last)) {
    throw new RangeError("music endpoint exceeds safe frame range");
  }
  const fade = Math.min(6, Math.floor(emittedFrames / 2));
  return {
    recordRange: { startFrame: first, endFrame: last },
    sourceRange: { startFrame: 0, endFrame: emittedFrames },
    requestedEndFrame: desiredEnd,
    shorterThanRows: last < desiredEnd,
    fadeInFrames: fade,
    fadeOutFrames: fade,
  };
}
