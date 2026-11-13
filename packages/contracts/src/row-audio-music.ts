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

  if (![sourceSamples, sampleRate, timelineRate.numerator, timelineRate.denominator]
    .every((value) => Number.isSafeInteger(value) && value > 0)) {
    throw new RangeError("music requires verified positive sample/rate integers");
  }
  const available = BigInt(sourceSamples) * BigInt(timelineRate.numerator)
    / (BigInt(sampleRate) * BigInt(timelineRate.denominator));
  if (available > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError("music duration exceeds safe frame range");
  }
  const first = rows[from]!.startFrame;
  const desiredEnd = rows[through]!.endFrame;
  const emittedFrames = Math.min(desiredEnd - first, Number(available));
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
