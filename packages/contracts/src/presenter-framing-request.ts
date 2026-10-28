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
  mappingHash: string;
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
  if (video.length !== 1 || video[0]!.width !== raster.width || video[0]!.height !== raster.height
    || video[0]!.frameRate !== `${raster.frameRate.numerator}/${raster.frameRate.denominator}`) throw new Error("Registered presenter raster/rate differs from calibration.");
  const hash = (value: unknown) => typeof value === "string" && /^sha256:[a-f0-9]{64}$/u.test(value);
  if (![source.mediaHash, input.mappingHash, input.reviewedColor.profileHash, input.reviewedColor.reviewEvidenceHash,
    input.dialogue.mediaHash, input.dialogue.processingProfileHash, input.dialogue.synchronizationEvidenceHash].every(hash)) throw new Error("Missing immutable source, mapping, reviewed color or dialogue evidence.");
  const frame = (value: number) => Number.isSafeInteger(value) && value >= 0;
  const ids = new Set<string>();
  if (input.intervals.length === 0) throw new Error("Presenter intervals are empty.");
  for (const [index, interval] of input.intervals.entries()) {
    if (!interval.eventId.trim() || ids.has(interval.eventId)) throw new Error("Presenter event identity is missing or repeated.");
    ids.add(interval.eventId);
    if (!["wide", "tight"].includes(interval.framingKey) || typeof interval.visible !== "boolean"
      || ![interval.recordStart, interval.recordEnd, interval.sourceStart, interval.sourceEnd].every(frame)
      || interval.recordEnd <= interval.recordStart || interval.sourceEnd <= interval.sourceStart) throw new Error("Invalid presenter interval.");
    // Native item splitting at the qualified boundary uses exact 1:1 frames only.
    if (interval.sourceEnd - interval.sourceStart !== interval.recordEnd - interval.recordStart) throw new Error("Framing adapter requires exact 1:1 source intervals.");
    const previous = input.intervals[index - 1];
    if (previous && (previous.recordEnd !== interval.recordStart || previous.sourceEnd !== interval.sourceStart)) throw new Error("Presenter source/record intervals are not contiguous.");
  }
  const dialogue = input.dialogue;
  const first = input.intervals[0]!;
  const last = input.intervals.at(-1)!;
  if (!dialogue.eventId.trim() || ids.has(dialogue.eventId)
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
    mappingHash: input.mappingHash,
    reviewedColor: input.reviewedColor,
    profile,
    profileContentJson: presenterFramingProfileContentJson(profile),
    intervals: input.intervals.map((interval) => ({ ...interval,
      name: `OC ${interval.framingKey.toUpperCase()} ${interval.eventId}`,
      color: interval.framingKey === "wide" ? "Blue" : "Orange",
    })),
    dialogue,
  });
  return { ...payload, requestHash: sha256CanonicalJson(payload) };
}
