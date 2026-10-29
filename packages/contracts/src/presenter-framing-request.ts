import type { ShootRegistrationProjectV1 } from "./generated/contracts.js";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { presenterFramingProfileContentJson, validatePresenterFramingProfile } from "./presenter-framing.js";

export interface PresenterPictureInterval {
  eventId: string;
  framingKey: "wide" | "tight";
  recordStart: number;
  recordEnd: number;
  sourceStart: number;
  sourceEnd: number;
  visible: boolean;
}

export interface ProcessedDialoguePlacement {
  eventId: string;
  mediaHash: string;
  processingProfileHash: string;
  synchronizationEvidenceHash: string;
  recordStart: number;
  recordEnd: number;
  sourceStartSample: number;
  sourceEndSample: number;
  sampleRate: number;
}

export interface PresenterFramingRequestInput {
  registration: ShootRegistrationProjectV1;
  sessionId: string;
  sourceId: string;
  profile: unknown;
  observedContext: unknown;
  /** Explicit upstream source intervals; #44 owns producing their master-time mapping. */
  mappingEvidence: unknown[];
  intervals: PresenterPictureInterval[];
  reviewedColor: { profileHash: string; reviewEvidenceHash: string };
  dialogue: ProcessedDialoguePlacement;
}

/** Freeze a picture-only adapter request, without creating or qualifying native work. */
export function createPresenterFramingRequest(input: PresenterFramingRequestInput) {
  const profile = validatePresenterFramingProfile(input.profile);
  if (canonicalJson(profile.context) !== canonicalJson(input.observedContext)) throw new Error("Framing raster/context mismatch.");
  const sessions = input.registration.sessions.filter(({ id }) => id === input.sessionId);
  const sources = sessions.flatMap(({ sources }) => sources).filter(({ id }) => id === input.sourceId);
  if (sessions.length !== 1 || sources.length !== 1) throw new Error("Framing needs one registered source in one session.");
  const source = sources[0]!;
  if (source.authorization !== "authorized_local" || source.status !== "ready") throw new Error("Presenter source is not authorized and ready.");
  const video = source.inspection.videoStreams;
  const raster = profile.context.sourceRaster;
  const timelineRate = profile.context.timelineRaster.frameRate;
  if (BigInt(raster.frameRate.numerator) * BigInt(timelineRate.denominator)
    !== BigInt(timelineRate.numerator) * BigInt(raster.frameRate.denominator)) throw new Error("Native framing requires matching source/timeline rates.");
  if (video.length !== 1 || video[0].width !== raster.width || video[0].height !== raster.height
    || video[0].frameRate !== `${raster.frameRate.numerator}/${raster.frameRate.denominator}`) throw new Error("Registered presenter raster/rate differs from calibration.");
  const hash = (value: unknown) => typeof value === "string" && /^sha256:[a-f0-9]{64}$/u.test(value);
  if (![source.mediaHash, input.reviewedColor.profileHash, input.reviewedColor.reviewEvidenceHash,
    input.dialogue.mediaHash, input.dialogue.processingProfileHash, input.dialogue.synchronizationEvidenceHash].every(hash)) throw new Error("Missing immutable source, mapping, reviewed color or dialogue evidence.");
  const frame = (value: number) => Number.isSafeInteger(value) && value >= 0;
  const eventId = (value: string) => value.length > 0 && !/\s/u.test(value);
  const ids = new Set<string>();
  if (input.intervals.length === 0) throw new Error("Presenter intervals are empty.");
  if (input.mappingEvidence.length !== input.intervals.length) throw new Error("Every presenter interval needs its verified #44 mapping handoff.");
  for (const [index, interval] of input.intervals.entries()) {
    if (!eventId(interval.eventId) || ids.has(interval.eventId)) throw new Error("Presenter event identity is missing or repeated.");
    ids.add(interval.eventId);
    if (!["wide", "tight"].includes(interval.framingKey) || typeof interval.visible !== "boolean"
      || ![interval.recordStart, interval.recordEnd, interval.sourceStart, interval.sourceEnd].every(frame)
      || interval.recordEnd <= interval.recordStart || interval.sourceEnd <= interval.sourceStart) throw new Error("Invalid presenter interval.");
    // Native item splitting at the qualified boundary uses exact 1:1 frames only.
    if (interval.sourceEnd - interval.sourceStart !== interval.recordEnd - interval.recordStart) throw new Error("Framing adapter requires exact 1:1 source intervals.");
    const previous = input.intervals[index - 1];
    if (previous && (previous.recordEnd !== interval.recordStart || previous.sourceEnd !== interval.sourceStart)) throw new Error("Presenter source/record intervals are not contiguous.");
    const mapping = input.mappingEvidence[index];
    if (mapping === null || typeof mapping !== "object" || Array.isArray(mapping)) throw new Error("Missing #44 mapping evidence.");
    const evidence = mapping as Record<string, unknown>;
    const start = evidence.startBoundary as Record<string, unknown> | undefined;
    const end = evidence.endBoundary as Record<string, unknown> | undefined;
    const range = evidence.frameRange as Record<string, unknown> | undefined;
    if (evidence.method !== "frame-index-identity/v1" || evidence.projectId !== input.registration.projectId
      || evidence.sourceId !== source.id || evidence.sourceContentHash !== source.mediaHash
      || typeof evidence.generationIdentity !== "string" || !/^[a-f0-9]{64}$/u.test(evidence.generationIdentity)
      || !hash(evidence.sourceProbeHash)
      || !["proxy", "master"].includes(String(evidence.videoSource))
      || (evidence.videoSource === "proxy" ? !hash(evidence.mappingHash) : evidence.mappingHash !== null)
      || canonicalJson(evidence.sourceRate) !== canonicalJson(raster.frameRate)
      || range?.startInclusive !== interval.sourceStart || range.endExclusive !== interval.sourceEnd
      || start?.sourceFrameIndex !== interval.sourceStart || end?.sourceFrameIndex !== interval.sourceEnd
      || start.reviewFrameIndex !== interval.sourceStart || end.reviewFrameIndex !== interval.sourceEnd) throw new Error("Verified #44 mapping differs from the registered presenter interval.");
    const firstMapping = input.mappingEvidence[0] as Record<string, unknown>;
    if (evidence.generationIdentity !== firstMapping.generationIdentity || evidence.mappingHash !== firstMapping.mappingHash
      || evidence.sourceProbeHash !== firstMapping.sourceProbeHash) throw new Error("Presenter intervals use different mapping generations.");
  }
  const dialogue = input.dialogue;
  const first = input.intervals[0]!;
  const last = input.intervals.at(-1)!;
  if (!eventId(dialogue.eventId) || ids.has(dialogue.eventId)
    || ![dialogue.recordStart, dialogue.recordEnd, dialogue.sourceStartSample, dialogue.sourceEndSample, dialogue.sampleRate].every(frame)
    || dialogue.sampleRate === 0 || dialogue.sourceEndSample <= dialogue.sourceStartSample
    || dialogue.recordStart !== first.recordStart || dialogue.recordEnd !== last.recordEnd) throw new Error("One independent synchronized dialogue placement must cover the presenter interval.");
  if (BigInt(dialogue.sourceEndSample - dialogue.sourceStartSample) * BigInt(timelineRate.numerator)
    !== BigInt(last.recordEnd - first.recordStart) * BigInt(dialogue.sampleRate) * BigInt(timelineRate.denominator)) throw new Error("Dialogue duration does not match the exact presenter interval.");
  const payload = structuredClone({
    schemaVersion: "presenter-framing-request/v1" as const,
    status: "requested" as const,
    masterPolicy: "create_new_protected_master" as const,
    projectId: input.registration.projectId,
    sessionId: input.sessionId,
    sourceId: source.id,
    sourceHash: source.mediaHash,
    mappingEvidence: input.mappingEvidence,
    mappingEvidenceHash: sha256CanonicalJson(input.mappingEvidence),
    reviewedColor: input.reviewedColor,
    profile,
    profileContentJson: presenterFramingProfileContentJson(profile),
    intervals: input.intervals.map((interval) => ({ ...interval,
      name: `OC ${interval.framingKey.toUpperCase()} ${interval.eventId}`,
      color: interval.framingKey === "wide" ? "Blue" : "Orange",
    })),
    dialogue,
  });
  return { ...payload, requestContentJson: canonicalJson(payload), requestHash: sha256CanonicalJson(payload) };
}
