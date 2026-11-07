/**
 * Pure bridge from Research's persisted ClipCandidate DTO to a Timeline occurrence.
 * No Research API, frame-rate conversion, media discovery, or readiness claim lives here.
 */
import type {
  ResearchClipSnapshotV2,
  ResearchFrameBindingV2,
  VisualOnlyBlockV2,
} from "./generated/contracts-v2.js";

/** Fields actually persisted on Research's ClipCandidate; unrelated DTO fields may be present. */
export interface ResearchLoggedCandidateInputV2 {
  id: string;
  projectId: string;
  catalogVideoId: string;
  version: number;
  createdBy?: string;
  createdAt?: string;
  updatedAt?: string;
  video: {
    youtubeVideoId: string;
    canonicalUrl: string;
    title: string;
    channel?: string;
    sourceLanguage?: string;
  };
  selection: {
    trackId: string;
    transcriptVersion: number;
    firstSegmentId: string;
    lastSegmentId: string;
    firstTokenId?: string;
    lastTokenId?: string;
    transcriptStartMs: number;
    transcriptEndMs: number;
    exportStartMs: number;
    exportEndMs: number;
    text: string;
    timingPrecision: "word" | "cue" | "estimated";
  };
  englishText: string;
  originalText?: string;
}

export interface FrameIntervalV2 {
  startFrame: number;
  endFrame: number; // exclusive
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const goodId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
const positive = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) > 0;
const nonnegative = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const nonempty = (value: unknown): value is string => typeof value === "string" && value.length > 0;

function optionalString(value: unknown, label: string): void {
  if (value !== undefined && typeof value !== "string") throw new RangeError(`Invalid Research ${label}`);
}

function optionalId(value: unknown, label: string): void {
  if (value !== undefined && !goodId(value)) throw new RangeError(`Invalid Research ${label}`);
}

/** Copy immutable Research evidence, not a mutable reference into the catalog. */
export function snapshotResearchCandidateV2(input: ResearchLoggedCandidateInputV2): ResearchClipSnapshotV2 {
  const candidate = input;
  const v = candidate?.video;
  const s = candidate?.selection;
  if (!candidate || !v || !s ||
    !goodId(candidate.id) || !goodId(candidate.projectId) || !goodId(candidate.catalogVideoId) ||
    !positive(candidate.version) || !goodId(s.trackId) || !positive(s.transcriptVersion) ||
    !goodId(s.firstSegmentId) || !goodId(s.lastSegmentId) ||
    !nonempty(v.youtubeVideoId) || !nonempty(v.canonicalUrl) || !nonempty(v.title) ||
    !nonnegative(s.exportStartMs) || !nonnegative(s.transcriptStartMs) ||
    !nonnegative(s.transcriptEndMs) || !nonnegative(s.exportEndMs) ||
    s.exportStartMs > s.transcriptStartMs || s.transcriptStartMs >= s.transcriptEndMs ||
    s.transcriptEndMs > s.exportEndMs ||
    typeof s.text !== "string" || typeof candidate.englishText !== "string" ||
    !(["word", "cue", "estimated"] as const).includes(s.timingPrecision)) {
    throw new RangeError("Invalid Research logged clip candidate or selection");
  }
  optionalId(candidate.createdBy, "creator");
  optionalId(s.firstTokenId, "first token");
  optionalId(s.lastTokenId, "last token");
  optionalString(candidate.originalText, "original text");
  optionalString(v.channel, "channel");
  optionalString(v.sourceLanguage, "source language");
  for (const key of ["createdAt", "updatedAt"] as const) {
    const value = candidate[key];
    if (value !== undefined && (typeof value !== "string" ||
      !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value) ||
      Number.isNaN(Date.parse(value)))) {
      throw new RangeError(`Invalid Research ${key}`);
    }
  }
  const snapshot: ResearchClipSnapshotV2 = {
    researchProjectId: candidate.projectId,
    clipId: candidate.id,
    clipVersion: candidate.version,
    catalogVideoId: candidate.catalogVideoId,
    ...(candidate.createdBy === undefined ? {} : { createdBy: candidate.createdBy }),
    ...(candidate.createdAt === undefined ? {} : { createdAt: candidate.createdAt }),
    ...(candidate.updatedAt === undefined ? {} : { updatedAt: candidate.updatedAt }),
    video: {
      youtubeVideoId: v.youtubeVideoId, canonicalUrl: v.canonicalUrl, title: v.title,
      ...(v.channel === undefined ? {} : { channel: v.channel }),
      ...(v.sourceLanguage === undefined ? {} : { sourceLanguage: v.sourceLanguage }),
    },
    loggedSelection: {
      trackId: s.trackId, transcriptVersion: s.transcriptVersion,
      firstSegmentId: s.firstSegmentId, lastSegmentId: s.lastSegmentId,
      ...(s.firstTokenId === undefined ? {} : { firstTokenId: s.firstTokenId }),
      ...(s.lastTokenId === undefined ? {} : { lastTokenId: s.lastTokenId }),
      transcriptStartMs: s.transcriptStartMs, transcriptEndMs: s.transcriptEndMs,
      exportStartMs: s.exportStartMs, exportEndMs: s.exportEndMs,
      text: s.text, timingPrecision: s.timingPrecision,
    },
    englishText: candidate.englishText,
    ...(candidate.originalText === undefined ? {} : { originalText: candidate.originalText }),
  };
  return structuredClone(snapshot);
}

/** Frame arithmetic is lawful ONLY with a separately supplied source-frame mapping. */
export function inwardUseRangeV2(logged: FrameIntervalV2, selected: FrameIntervalV2): {
  startFrame: number;
  durationFrames: number;
} {
  if (!nonnegative(logged?.startFrame) || !nonnegative(logged?.endFrame) ||
    !nonnegative(selected?.startFrame) || !nonnegative(selected?.endFrame) ||
    logged.startFrame >= logged.endFrame ||
    selected.startFrame < logged.startFrame || selected.endFrame > logged.endFrame ||
    selected.startFrame >= selected.endFrame) {
    throw new RangeError("Selection must stay inside the evidenced logged frame range");
  }
  return { startFrame: selected.startFrame, durationFrames: selected.endFrame - selected.startFrame };
}

export interface ResearchClipOccurrenceInputV2 {
  rowId: string;
  payloadId: string;
  orderKey: string;
  candidate: ResearchLoggedCandidateInputV2;
  /** Caller-supplied evidence, never inferred from millisecond transcript/export bounds. */
  frameBinding?: ResearchFrameBindingV2;
  /** Optional occurrence-local in/out; only legal when frameBinding exists. */
  selectedRange?: FrameIntervalV2;
}

/** Save an unresolved clip when no verified Timeline media/frame binding is available. */
export function createResearchClipOccurrenceV2(input: ResearchClipOccurrenceInputV2): VisualOnlyBlockV2 {
  if (!goodId(input.rowId) || !goodId(input.payloadId) || input.rowId === input.payloadId ||
    !nonempty(input.orderKey)) throw new RangeError("Invalid occurrence identity");
  const researchClip = snapshotResearchCandidateV2(input.candidate);
  const binding = input.frameBinding;
  if (binding === undefined) {
    if (input.selectedRange !== undefined) throw new RangeError("Cannot select frames without a verified binding");
    return {
      type: "visual_only", id: input.rowId, orderKey: input.orderKey, version: 1,
      researchClip,
      payload: {
        kind: "visual", payloadId: input.payloadId, pictureKind: "unresolved_visual",
        source: { kind: "unresolved_visual", description: "Research clip lacks verified Timeline media/frame binding" },
        audioPolicy: "mute", framingPolicy: "contain",
      },
      visualOnlyTiming: { kind: "visual_only" },
    };
  }
  if (!goodId(binding.mediaReferenceId) || !goodId(binding.clipId) || !positive(binding.clipVersion) ||
    binding.clipId !== researchClip.clipId || binding.clipVersion !== researchClip.clipVersion) {
    throw new RangeError("Frame binding is for a different Research clip revision");
  }
  const logged = { startFrame: binding.loggedStartFrame, endFrame: binding.loggedEndFrame };
  const use = inwardUseRangeV2(logged, input.selectedRange ?? logged);
  return {
    type: "visual_only", id: input.rowId, orderKey: input.orderKey, version: 1,
    researchClip,
    frameBinding: structuredClone(binding),
    payload: {
      kind: "visual", payloadId: input.payloadId, pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: binding.mediaReferenceId },
      audioPolicy: "mute", framingPolicy: "contain",
    },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: use },
  };
}

/** Pure use-range change: clearing out restores logged end, never a guessed file end. */
export function withResearchClipUseRangeV2(
  row: VisualOnlyBlockV2,
  range: FrameIntervalV2 | null,
): VisualOnlyBlockV2 {
  const binding = row.frameBinding;
  if (!binding || !row.researchClip || row.payload.pictureKind !== "clip") {
    throw new RangeError("A verified Research frame binding is required for trimming");
  }
  if (binding.clipId !== row.researchClip.clipId || binding.clipVersion !== row.researchClip.clipVersion ||
    row.payload.source.kind !== "media_reference" ||
    row.payload.source.mediaReferenceId !== binding.mediaReferenceId) {
    throw new RangeError("Cannot trim stale or mismatched Research media evidence");
  }
  const logged = { startFrame: binding.loggedStartFrame, endFrame: binding.loggedEndFrame };
  const current = row.visualOnlyTiming.selectedSourceRange;
  if (!current) throw new RangeError("Missing selected clip range");
  const selected = range ?? { startFrame: current.startFrame, endFrame: binding.loggedEndFrame };
  const newRange = inwardUseRangeV2(logged, selected);
  const copy = structuredClone(row);
  copy.visualOnlyTiming.selectedSourceRange = newRange;
  return copy;
}
