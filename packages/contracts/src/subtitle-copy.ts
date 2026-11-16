/** Occurrence-local English subtitle copy backed by an immutable Research snapshot. */
import type { ResearchClipSnapshotV2 } from "./generated/contracts-v2.js";
import {
  snapshotResearchCandidateV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

export interface SubtitleCopySegmentV1 {
  id: string;
  sourceFirstSegmentId: string;
  sourceLastSegmentId: string;
  sourceStartMs: number;
  sourceEndMs: number;
  timingPrecision: "word" | "cue" | "estimated";
  /** Only this viewer-facing text can be edited. The Research baseline stays in source. */
  englishText: string;
  /** Subtitle timing changes are not authorized by #393. */
  timingOverride: null;
  version: number;
}

export interface SubtitleCopyTrackV1 {
  schemaVersion: "subtitle-copy/v1";
  id: string;
  occurrenceId: string;
  version: number;
  sourceLanguage: string;
  /** Exact Research pin, including original text, translation and transcript evidence. */
  source: ResearchClipSnapshotV2;
  reviewState: "needs_review" | "reviewed";
  reviewerId: string | null;
  /** One source-spanning segment until genuinely aligned Research cues exist. */
  segments: SubtitleCopySegmentV1[];
}

const uuid = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/iu;
const MAX_ENGLISH_LENGTH = 16_000;

function hasInvalidControls(value: string): boolean {
  for (const character of value) {
    const code = character.charCodeAt(0);
    if ((code < 32 && code !== 9 && code !== 10) || code === 127) return true;
  }
  return false;
}

const validId = (value: unknown): value is string =>
  typeof value === "string" && uuid.test(value);
const positive = (value: unknown): value is number =>
  Number.isSafeInteger(value) && (value as number) > 0;
const validText = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= MAX_ENGLISH_LENGTH &&
  value.trim().length > 0 && !hasInvalidControls(value);
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function exactKeys(value: Record<string, unknown>, names: readonly string[]): boolean {
  return Object.keys(value).length === names.length && names.every((key) => Object.hasOwn(value, key));
}

/** Recreate the canonical snapshot using the existing Research evidence validator. */
function pinnedSource(value: unknown): ResearchClipSnapshotV2 {
  if (!record(value) || !record(value.video) || !record(value.loggedSelection)) {
    throw new RangeError("Invalid pinned subtitle source");
  }
  const source = value as unknown as ResearchClipSnapshotV2;
  const candidate: ResearchLoggedCandidateInputV2 = {
    id: source.clipId,
    projectId: source.researchProjectId,
    catalogVideoId: source.catalogVideoId,
    version: source.clipVersion,
    ...(source.createdBy === undefined ? {} : { createdBy: source.createdBy }),
    ...(source.createdAt === undefined ? {} : { createdAt: source.createdAt }),
    ...(source.updatedAt === undefined ? {} : { updatedAt: source.updatedAt }),
    video: source.video,
    selection: source.loggedSelection,
    englishText: source.englishText,
    ...(source.originalText === undefined ? {} : { originalText: source.originalText }),
  };
  const canonical = snapshotResearchCandidateV2(candidate);
  if (!sameAuthoringJsonV2(canonical, source) || !validText(canonical.englishText) ||
    !validText(canonical.loggedSelection.text)) {
    throw new RangeError("Invalid pinned subtitle source or English translation");
  }
  return canonical;
}

function languageFor(source: ResearchClipSnapshotV2): string {
  const language = source.video.sourceLanguage?.trim().toLowerCase() || "und";
  // `mul` and `mixed` explicitly represent multilingual speech; `und` is unknown.
  if (!/^(?:[a-z]{2,3}(?:-[a-z0-9]{2,8})*|mixed)$/u.test(language)) {
    throw new RangeError("Invalid subtitle source language");
  }
  if (language === "en" || language.startsWith("en-")) {
    throw new RangeError("English-only source does not require translated subtitle copy");
  }
  return language;
}

/** Fail closed on invalid, retimed or rewritten saved copy before any revision. */
export function assertValidSubtitleCopyV1(value: unknown): asserts value is SubtitleCopyTrackV1 {
  if (!record(value) || !exactKeys(value, [
    "schemaVersion", "id", "occurrenceId", "version", "sourceLanguage",
    "source", "reviewState", "reviewerId", "segments",
  ]) || value.schemaVersion !== "subtitle-copy/v1" ||
    !validId(value.id) || !validId(value.occurrenceId) ||
    value.id.toLowerCase() === value.occurrenceId.toLowerCase() ||
    !positive(value.version) || !Array.isArray(value.segments) || value.segments.length !== 1) {
    throw new RangeError("Invalid subtitle copy track");
  }
  const source = pinnedSource(value.source);
  if (value.sourceLanguage !== languageFor(source)) {
    throw new RangeError("Subtitle language differs from pinned source");
  }
  const segment: unknown = value.segments[0];
  const selection = source.loggedSelection;
  if (!record(segment) || !exactKeys(segment, [
    "id", "sourceFirstSegmentId", "sourceLastSegmentId", "sourceStartMs", "sourceEndMs",
    "timingPrecision", "englishText", "timingOverride", "version",
  ]) || !validId(segment.id) || segment.id.toLowerCase() === value.id.toLowerCase() ||
    segment.id.toLowerCase() === value.occurrenceId.toLowerCase() ||
    segment.sourceFirstSegmentId !== selection.firstSegmentId ||
    segment.sourceLastSegmentId !== selection.lastSegmentId ||
    segment.sourceStartMs !== selection.transcriptStartMs ||
    segment.sourceEndMs !== selection.transcriptEndMs ||
    segment.timingPrecision !== selection.timingPrecision || segment.timingOverride !== null ||
    !validText(segment.englishText) || !positive(segment.version) || segment.version > value.version ||
    (segment.version === 1 && segment.englishText !== source.englishText) ||
    (value.version === 1 && segment.version !== 1)) {
    throw new RangeError("Invalid or retimed subtitle copy segment");
  }
  if ((value.reviewState === "needs_review" && value.reviewerId !== null) ||
    (value.reviewState === "reviewed" && (!validId(value.reviewerId) || value.version < 2)) ||
    (value.reviewState !== "needs_review" && value.reviewState !== "reviewed")) {
    throw new RangeError("Invalid subtitle review attribution");
  }
}

/** Derive from a trusted saved pin, never from guessed timings or live Research text. */
export function deriveSubtitleCopyV1(
  trackId: string,
  occurrenceId: string,
  segmentId: string,
  source: ResearchClipSnapshotV2,
): SubtitleCopyTrackV1 {
  if (!validId(trackId) || !validId(occurrenceId) || !validId(segmentId) ||
    new Set([trackId.toLowerCase(), occurrenceId.toLowerCase(), segmentId.toLowerCase()]).size !== 3) {
    throw new RangeError("Invalid subtitle identity");
  }
  const frozen = pinnedSource(source);
  const language = languageFor(frozen);
  const selection = frozen.loggedSelection;
  return {
    schemaVersion: "subtitle-copy/v1", id: trackId, occurrenceId, version: 1,
    sourceLanguage: language, source: frozen,
    reviewState: "needs_review", reviewerId: null,
    segments: [{
      id: segmentId,
      sourceFirstSegmentId: selection.firstSegmentId,
      sourceLastSegmentId: selection.lastSegmentId,
      sourceStartMs: selection.transcriptStartMs,
      sourceEndMs: selection.transcriptEndMs,
      timingPrecision: selection.timingPrecision,
      englishText: frozen.englishText,
      timingOverride: null,
      version: 1,
    }],
  };
}

function readyForRevision(
  saved: SubtitleCopyTrackV1,
  currentPin: ResearchClipSnapshotV2,
  expectedVersion: number,
  reviewerId: string,
): SubtitleCopyTrackV1 {
  assertValidSubtitleCopyV1(saved);
  const pin = pinnedSource(currentPin);
  if (!positive(expectedVersion) || saved.version !== expectedVersion ||
    !sameAuthoringJsonV2(saved.source, pin)) {
    throw new RangeError("Stale subtitle source or version");
  }
  if (!validId(reviewerId) || saved.version === Number.MAX_SAFE_INTEGER) {
    throw new RangeError("Invalid subtitle reviewer or exhausted revision");
  }
  return structuredClone(saved);
}

/** Edit only English viewer copy; the initial translation and source times never change. */
export function reviseSubtitleCopyV1(
  saved: SubtitleCopyTrackV1,
  currentPin: ResearchClipSnapshotV2,
  expectedVersion: number,
  englishText: string,
  reviewerId: string,
): SubtitleCopyTrackV1 {
  const next = readyForRevision(saved, currentPin, expectedVersion, reviewerId);
  const segment = next.segments[0]!;
  if (!validText(englishText) || segment.englishText === englishText ||
    segment.version === Number.MAX_SAFE_INTEGER) {
    throw new RangeError("Invalid or unchanged subtitle edit");
  }
  segment.englishText = englishText;
  segment.version += 1;
  next.version += 1;
  next.reviewState = "reviewed";
  next.reviewerId = reviewerId;
  return next;
}

/** Explicit approval changes review attribution and track revision, not segment content. */
export function approveSubtitleCopyV1(
  saved: SubtitleCopyTrackV1,
  currentPin: ResearchClipSnapshotV2,
  expectedVersion: number,
  reviewerId: string,
): SubtitleCopyTrackV1 {
  const next = readyForRevision(saved, currentPin, expectedVersion, reviewerId);
  if (next.reviewState === "reviewed") throw new RangeError("Subtitle copy already reviewed");
  next.version += 1;
  next.reviewState = "reviewed";
  next.reviewerId = reviewerId;
  return next;
}
