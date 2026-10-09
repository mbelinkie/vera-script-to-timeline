import { createHash } from "node:crypto";

import { Ajv2020, type ErrorObject } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";

import buildReportSchema from "../../../contracts/build-report-v2.schema.json" with { type: "json" };
import compilerDependenciesSchema from "../../../contracts/compiler-dependencies-v2.schema.json" with { type: "json" };
import timelineManifestSchema from "../../../contracts/timeline-manifest-v2.schema.json" with { type: "json" };
import scriptDocumentSchema from "../../../contracts/script-document-v2.schema.json" with { type: "json" };
import type {
  AuthoringDefaultsV2,
  BoundaryEvidenceV2,
  BuildDiagnosticV2,
  BuildReportV2,
  ContentSlot,
  CompilerDependenciesV2,
  EntityReferenceV2,
  FrameRangeV2,
  NarrationBlockV2,
  NarrationTokenTimingMapV2,
  OccurrenceMediaResolutionV2,
  PreparationTimeMappingV1,
  RequestedPreparationRangeV1,
  PresenterStillReference,
  PointPlacement,
  RationalRate,
  RationalTime,
  ReturnSlot,
  ScriptDocumentV2,
  TimelineEventV2,
  TimelineManifestV2,
  VisualOnlyBlockV2,
  VisualSequenceResolutionV2,
} from "./generated/contracts-v2.js";
import genericTorso from "./assets/generic-torso-v1.json" with { type: "json" };
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { placementAnchorKeyV2, resolveTimedPlacementV2 } from "./authoring-v2-placement.js";
import { projectPrimarySequenceV2 } from "./authoring-v2-projection.js";
import { isWordAnchorCurrentV2, validateScriptDocumentV2 } from "./authoring-v2-validation.js";

export interface CompileDiagnosticV2 {
  code: string;
  message: string;
  jsonPath?: string;
  entityId?: string;
}

export type CompileTimelineResultV2 =
  | { ok: false; diagnostics: CompileDiagnosticV2[] }
  | {
      ok: true;
      manifest: TimelineManifestV2;
      report: BuildReportV2;
      manifestJson: string;
      reportJson: string;
    };

export interface MediaRequirementsInputV2 {
  timing: readonly NarrationTokenTimingMapV2[];
  defaults: AuthoringDefaultsV2;
  sourceDescriptors: readonly OccurrenceMediaResolutionV2[];
  frameRate: RationalRate;
}

export interface MediaRequirementV2 {
  occurrenceKey: string;
  payloadId: string;
  mediaReferenceId: string;
  requirementKey: string | null;
  requestedRange: RequestedPreparationRangeV1;
  sourceRange: FrameRangeV2;
  recordRange: FrameRangeV2;
  requiredSourceRange: FrameRangeV2;
  sourceSufficiency: "sufficient" | "insufficient";
}

export type MediaRequirementsResultV2 =
  | { ok: false; diagnostics: CompileDiagnosticV2[] }
  | { ok: true; requirements: MediaRequirementV2[]; durationFrames: number };

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(scriptDocumentSchema);
ajv.addSchema(compilerDependenciesSchema);
ajv.addSchema(timelineManifestSchema);
ajv.addSchema(buildReportSchema);
const validateDependencies = ajv.compile<CompilerDependenciesV2>(compilerDependenciesSchema);
const validateManifest = ajv.getSchema<TimelineManifestV2>(timelineManifestSchema.$id)!;
const validateReport = ajv.getSchema<BuildReportV2>(buildReportSchema.$id)!;

interface Fraction { n: bigint; d: bigint }
type CutawaySlot = ContentSlot & { relation: Extract<ContentSlot["relation"], { kind: "cutaway" }> };
interface TimedRow {
  kind: "narration";
  block: NarrationBlockV2;
  map: NarrationTokenTimingMapV2;
  startFrame: number;
  durationFrames: number;
  tokenFrames: Map<string, number>;
  tokenTimes: Map<string, { start: Fraction; end: Fraction | null; evidenced: boolean }>;
}
interface VisualOnlyTimedRow {
  kind: "visual_only";
  block: VisualOnlyBlockV2;
  startFrame: number;
  durationFrames: number;
}
type ProgramRow = TimedRow | VisualOnlyTimedRow;

const compareText = (a: string, b: string): number => a < b ? -1 : a > b ? 1 : 0;
const shaText = (text: string): string => `sha256:${createHash("sha256").update(text, "utf8").digest("hex")}`;
const gcd = (a: bigint, b: bigint): bigint => {
  let x = a < 0n ? -a : a;
  let y = b < 0n ? -b : b;
  while (y) [x, y] = [y, x % y];
  return x || 1n;
};
const frac = (n: bigint, d: bigint): Fraction => {
  if (d === 0n) throw new RangeError("zero rational denominator");
  const sign = d < 0n ? -1n : 1n;
  const g = gcd(n, d);
  return { n: n / g * sign, d: d / g * sign };
};
const add = (a: Fraction, b: Fraction): Fraction => frac(a.n * b.d + b.n * a.d, a.d * b.d);
const sub = (a: Fraction, b: Fraction): Fraction => frac(a.n * b.d - b.n * a.d, a.d * b.d);
const compare = (a: Fraction, b: Fraction): number => {
  const v = a.n * b.d - b.n * a.d;
  return v < 0n ? -1 : v > 0n ? 1 : 0;
};
const fromWire = (value: RationalTime): Fraction | null => {
  if (!Number.isSafeInteger(value.numerator) || !Number.isSafeInteger(value.denominator) || value.denominator <= 0) return null;
  const n = BigInt(value.numerator); const d = BigInt(value.denominator);
  if (gcd(n, d) !== 1n) return null;
  return frac(n, d);
};
const wire = (value: Fraction): RationalTime | null => {
  const f = frac(value.n, value.d); const n = Number(f.n); const d = Number(f.d);
  return Number.isSafeInteger(n) && Number.isSafeInteger(d) ? { numerator: n, denominator: d } : null;
};
const wireOrThrow = (value: Fraction, label: string): RationalTime => {
  const result = wire(value);
  if (!result) throw new RangeError(`${label} exceeds exact rational wire bounds`);
  return result;
};
const ceil = (n: bigint, d: bigint): bigint => {
  if (n < 0n || d <= 0n) throw new RangeError("ceil requires a nonnegative numerator and positive denominator");
  return (n + d - 1n) / d;
};
const safe = (n: bigint, label: string): number => {
  if (n < 0n || n > BigInt(Number.MAX_SAFE_INTEGER)) throw new RangeError(`${label} exceeds safe integer bounds`);
  return Number(n);
};
const rateFraction = (rate: RationalRate): Fraction => {
  if (!Number.isSafeInteger(rate.numerator) || !Number.isSafeInteger(rate.denominator) || rate.numerator <= 0 || rate.denominator <= 0) throw new RangeError("frame rate must be positive safe integers");
  return frac(BigInt(rate.numerator), BigInt(rate.denominator));
};
const framesAt = (time: Fraction, rate: Fraction): number => safe(ceil(time.n * rate.n, time.d * rate.d), "record frame");
const durationFramesForSamples = (samples: number, sampleRate: number, rate: RationalRate): number => {
  if (!Number.isSafeInteger(samples) || samples <= 0 || !Number.isSafeInteger(sampleRate) || sampleRate <= 0) throw new RangeError("narration audio duration and sample rate must be positive safe integers");
  return safe(ceil(BigInt(samples) * BigInt(rate.numerator), BigInt(sampleRate) * BigInt(rate.denominator)), "narration frame duration");
};
const recordDurationInSeconds = (recordFrames: number, rate: RationalRate): Fraction => {
  if (!Number.isSafeInteger(recordFrames) || recordFrames <= 0) throw new RangeError("record interval must contain positive safe-integer frames");
  return frac(BigInt(recordFrames) * BigInt(rate.denominator), BigInt(rate.numerator));
};
const sourceDurationInSeconds = (sourceFrames: number, rate: RationalRate): Fraction => {
  if (!Number.isSafeInteger(sourceFrames) || sourceFrames <= 0) throw new RangeError("source interval must contain positive safe-integer frames");
  return frac(BigInt(sourceFrames) * BigInt(rate.denominator), BigInt(rate.numerator));
};
const preparationRange = (sourceInFrame: number, duration: Fraction): RequestedPreparationRangeV1 => {
  const durationWire = wire(duration);
  if (!durationWire || durationWire.numerator <= 0) throw new RangeError("preparation duration exceeds exact positive rational wire bounds");
  return { sourceInFrame, duration: durationWire as RequestedPreparationRangeV1["duration"], preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
};
const entity = (kind: EntityReferenceV2["kind"], id: string | null, path: string | null): EntityReferenceV2 => ({ kind, id, path });
const schemaDiagnostics = (errors: ErrorObject[] | null | undefined, prefix: string): CompileDiagnosticV2[] => (errors ?? []).map((error) => ({
  code: `${prefix}_SCHEMA_INVALID`, message: `${error.instancePath || "/"}: ${error.message ?? "schema validation failed"}`, jsonPath: error.instancePath || "/",
}));
const fail = (...diagnostics: CompileDiagnosticV2[]): CompileTimelineResultV2 => ({ ok: false, diagnostics: diagnostics.sort((a, b) => compareText(a.code, b.code) || compareText(a.entityId ?? "", b.entityId ?? "")) });
const compareDiagnostic = (a: BuildDiagnosticV2, b: BuildDiagnosticV2): number => compareText(a.code, b.code) || compareText(a.entity.id ?? "", b.entity.id ?? "") || compareText(a.id, b.id);
const stableId = (label: string): string => {
  const hex = createHash("sha256").update(label, "utf8").digest("hex").slice(0, 32);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-8${hex.slice(17, 20)}-${hex.slice(20)}`;
};

function diagnostic(code: BuildDiagnosticV2["code"], message: string, target: EntityReferenceV2, evidence?: BuildDiagnosticV2["evidence"], recovery: BuildDiagnosticV2["recoveryActionKinds"] = ["manual_review"], severity: BuildDiagnosticV2["severity"] = "blocking"): BuildDiagnosticV2 {
  return {
    id: stableId(`${code}:${target.kind}:${target.id ?? ""}:${target.path ?? ""}:${message}`), severity, code, message, entity: target,
    evidence: evidence ?? { kind: "details", message }, recoveryActionKinds: recovery,
  };
}

function textHashForRow(block: NarrationBlockV2): string { return shaText(block.text); }

function malformedFrozenText(document: ScriptDocumentV2): CompileDiagnosticV2 | null {
  const wellFormed = (text: string): boolean => Buffer.from(text, "utf8").toString("utf8") === text;
  for (const block of document.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    if (!wellFormed(block.text)) return { code: "DOCUMENT_TEXT_INVALID", message: "Narration text contains an unpaired UTF-16 surrogate.", jsonPath: `/activeDraft/blocks/${block.id}/text`, entityId: block.id };
    for (const token of block.tokens) {
      if (!wellFormed(token.value) || block.text.slice(token.startOffset, token.endOffset) !== token.value) {
        return { code: "DOCUMENT_TOKEN_TEXT_INVALID", message: "Frozen narration tokens must be valid Unicode slices at their exact UTF-16 offsets.", jsonPath: `/activeDraft/blocks/${block.id}/tokens`, entityId: token.id };
      }
    }
  }
  return null;
}

function conflictingNarrationAudioBinding(maps: readonly NarrationTokenTimingMapV2[]): CompileDiagnosticV2 | null {
  const audioByAsset = new Map<string, NonNullable<NarrationTokenTimingMapV2["audio"]>>();
  for (const map of maps) {
    if (!map.audio) continue;
    const previous = audioByAsset.get(map.narrationAssetId);
    if (previous && !sameJson(previous, map.audio)) return {
      code: "NARRATION_AUDIO_BINDING_MISMATCH",
      message: `Narration asset ${map.narrationAssetId} has conflicting immutable audio bindings across timing maps.`,
      jsonPath: "/narrationTimingMaps",
      entityId: map.narrationAssetId,
    };
    audioByAsset.set(map.narrationAssetId, map.audio);
  }
  return null;
}

function buildTimedRows(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2): { rows: ProgramRow[]; diagnostics: BuildDiagnosticV2[] } {
  const diagnostics: BuildDiagnosticV2[] = [];
  const active: Array<NarrationBlockV2 | VisualOnlyBlockV2> = [];
  for (const block of document.activeDraft.blocks) if (block.type === "visual_only" || block.type === "narration" && block.state === "active") active.push(block);
  const maps = new Map<string, NarrationTokenTimingMapV2>();
  for (const map of dependencies.narrationTimingMaps) {
    if (maps.has(map.blockId)) diagnostics.push(diagnostic("STALE_TIMING_MAP", "More than one timing map names this narration row.", entity("block", map.blockId, "narrationTimingMaps"), undefined, ["refresh_timing"]));
    maps.set(map.blockId, map);
  }
  let cursor = 0;
  const rows: ProgramRow[] = [];
  const preserveKnownSpine = (block: NarrationBlockV2, map: NarrationTokenTimingMapV2): void => {
    if (!map.audio) return;
    const durationFrames = durationFramesForSamples(map.audio.durationSamples, map.audio.sampleRate, dependencies.timeline.frameRate);
    rows.push({ kind: "narration", block, map, startFrame: cursor, durationFrames, tokenFrames: new Map(), tokenTimes: new Map() });
    cursor = safe(BigInt(cursor) + BigInt(durationFrames), "timeline duration");
  };
  for (const block of active) {
    if (block.type === "visual_only") {
      const timing = block.visualOnlyTiming;
      let durationFrames: number;
      try {
        if (timing.selectedSourceRange) {
          const descriptor = dependencies.occurrenceResolutions.find((item) => item.payloadId === block.payload.payloadId);
          const sourceRate = descriptor ? rateFraction(descriptor.logicalSourceBounds.frameRate) : null;
          if (!sourceRate) throw new RangeError("visual-only selected source duration has no exact source-rate descriptor");
          const selected = timing.selectedSourceRange;
          if (!Number.isSafeInteger(selected.startFrame) || !Number.isSafeInteger(selected.durationFrames) || selected.durationFrames <= 0) throw new RangeError("visual-only selected source range is invalid");
          const targetRate = rateFraction(dependencies.timeline.frameRate);
          durationFrames = safe(ceil(BigInt(selected.durationFrames) * sourceRate.d * targetRate.n, sourceRate.n * targetRate.d), "visual-only duration");
        } else {
          const durationMs = timing.durationOverrideMs ?? dependencies.authoringDefaults.visualOnlyStillDurationMs;
          if (!Number.isSafeInteger(durationMs) || durationMs <= 0) throw new RangeError("visual-only still duration must be a positive safe integer");
          durationFrames = safe(ceil(BigInt(durationMs) * BigInt(dependencies.timeline.frameRate.numerator), 1000n * BigInt(dependencies.timeline.frameRate.denominator)), "visual-only duration");
        }
        if (durationFrames <= 0) throw new RangeError("visual-only duration collapses to zero frames");
        rows.push({ kind: "visual_only", block, startFrame: cursor, durationFrames });
        cursor = safe(BigInt(cursor) + BigInt(durationFrames), "timeline duration");
      } catch (error) {
        diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", error instanceof Error ? error.message : String(error), entity("block", block.id, "visualOnlyTiming"), undefined, ["repair_document"]));
      }
      continue;
    }
    const target = entity("block", block.id, `/activeDraft/blocks/${block.id}`);
    const map = maps.get(block.id);
    if (!map) {
      diagnostics.push(diagnostic("STALE_TIMING_MAP", "An active narration row has no timing map.", target, undefined, ["refresh_timing"]));
      continue;
    }
    const audio = map.audio;
    if (!audio || audio.narrationAssetId !== map.narrationAssetId || audio.audioHash !== map.audioHash) {
      diagnostics.push(diagnostic("STALE_TIMING_MAP", "Narration timing requires a verified audio binding with matching asset and hash.", target, undefined, ["refresh_timing"]));
      continue;
    }
    if (audio.timingHash !== map.timingHash) {
      diagnostics.push(diagnostic("TIMING_HASH_MISMATCH", "The cached audio binding pins a different narration timing hash.", target, { kind: "reference_mismatch", referenceType: "timing_hash", expected: audio.timingHash, actual: map.timingHash }, ["refresh_timing"]));
      preserveKnownSpine(block, map);
      continue;
    }
    if (map.blockRevision !== block.version || map.textHash !== textHashForRow(block)) {
      diagnostics.push(diagnostic(map.blockRevision !== block.version ? "STALE_TIMING_MAP" : "TEXT_HASH_MISMATCH", "The timing map does not match this frozen narration revision and text.", target, { kind: "reference_mismatch", referenceType: map.blockRevision !== block.version ? "document_revision" : "text_hash", expected: map.blockRevision !== block.version ? String(block.version) : textHashForRow(block), actual: map.blockRevision !== block.version ? String(map.blockRevision) : map.textHash }, ["refresh_timing"]));
      preserveKnownSpine(block, map);
      continue;
    }
    if (map.precision === "sentence_only" || map.precision === "estimated") {
      diagnostics.push(diagnostic("WORD_TIMING_REQUIRED", "Exact spoken-word boundaries require audible word timing.", target, { kind: "anchor_issue", anchorId: block.id, reason: "word_timing_required" }, ["refresh_timing"]));
      preserveKnownSpine(block, map);
      continue;
    }
    if (map.tokenizationVersion !== "script-document/v2-frozen-tokens") {
      diagnostics.push(diagnostic("STALE_TIMING_MAP", "The timing map does not identify the frozen script-document/v2 token sequence.", target, undefined, ["refresh_timing"]));
      preserveKnownSpine(block, map);
      continue;
    }
    if (map.tokens.length !== block.tokens.length || map.tokens.some((timing, i) => {
      const token = block.tokens[i];
      return !token || timing.tokenId !== token.id || timing.startOffset !== token.startOffset || timing.endOffset !== token.endOffset || timing.quotedText !== token.value;
    })) {
      diagnostics.push(diagnostic("STALE_TIMING_MAP", "Timing entries must match frozen token IDs, UTF-16 offsets, and exact text.", target, undefined, ["refresh_timing"]));
      preserveKnownSpine(block, map);
      continue;
    }
    try {
      const tokenTimes = new Map<string, { start: Fraction; end: Fraction | null; evidenced: boolean }>();
      const tokenFrames = new Map<string, number>();
      let prior: Fraction | null = null;
      map.tokens.forEach((item, index) => {
        const start = fromWire(item.startTime);
        const next = map.tokens[index + 1] ? fromWire(map.tokens[index + 1]!.startTime) : null;
        const audibleEnd = item.audibleEnd ? fromWire(item.audibleEnd) : null;
        if (!start || prior && compare(start, prior) <= 0 || audibleEnd && compare(audibleEnd, start) <= 0) throw new RangeError("word timing is non-reduced, non-increasing, or has a collapsed audible support");
        if (item.audibleEnd && !audibleEnd) throw new RangeError("audible end is not a reduced rational");
        if (!item.audibleEnd && item.endBasis === "evidenced_audible_end") throw new RangeError("audible end basis has no audible-end evidence");
        const end = audibleEnd ?? next;
        tokenTimes.set(item.tokenId, { start, end, evidenced: !!audibleEnd && item.endBasis === "evidenced_audible_end" });
        tokenFrames.set(item.tokenId, framesAt(start, rateFraction(dependencies.timeline.frameRate)));
        prior = start;
      });
      const durationFrames = durationFramesForSamples(audio.durationSamples, audio.sampleRate, dependencies.timeline.frameRate);
      if (durationFrames <= 0) throw new RangeError("narration audio collapses to zero frames");
      const audioDuration = frac(BigInt(audio.durationSamples), BigInt(audio.sampleRate));
      if (map.tokens.some((item) => {
        const start = fromWire(item.startTime);
        const audibleEnd = item.audibleEnd ? fromWire(item.audibleEnd) : null;
        return !start || compare(start, audioDuration) >= 0 || item.audibleEnd !== undefined && (!audibleEnd || compare(audibleEnd, audioDuration) > 0);
      })) throw new RangeError("word timing starts at or beyond, or audible support ends beyond, the exact narration audio duration");
    rows.push({ kind: "narration", block, map, startFrame: cursor, durationFrames, tokenFrames, tokenTimes });
      cursor = safe(BigInt(cursor) + BigInt(durationFrames), "timeline duration");
    } catch (error) {
      diagnostics.push(diagnostic("COLLAPSED_BOUNDARY", error instanceof Error ? error.message : String(error), target, undefined, ["refresh_timing"]));
      preserveKnownSpine(block, map);
    }
  }
  for (const id of maps.keys()) if (!active.some((row) => row.type === "narration" && row.state === "active" && row.id === id)) diagnostics.push(diagnostic("STALE_TIMING_MAP", "A timing map does not identify active narration.", entity("block", id, "narrationTimingMaps"), undefined, ["refresh_timing"]));
  return { rows, diagnostics };
}

interface ResolvedPlan {
  timedRows: ProgramRow[];
  events: TimelineEventV2[];
  requirements: MediaRequirementV2[];
  sequenceResolutions: VisualSequenceResolutionV2[];
  boundaryEvidence: TimelineManifestV2["boundaryEvidence"];
  diagnostics: BuildDiagnosticV2[];
  durationFrames: number;
}

function resolvePlan(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, requirePrepared = true): ResolvedPlan {
  const built = buildTimedRows(document, dependencies);
  const diagnostics = [...built.diagnostics];
  const events: TimelineEventV2[] = [];
  const projection = projectPrimarySequenceV2(document, { narrationTimingMaps: dependencies.narrationTimingMaps });
  const requirements: MediaRequirementV2[] = [];
  const sequenceResolutions: VisualSequenceResolutionV2[] = [];
  const boundaryEvidence: TimelineManifestV2["boundaryEvidence"] = [];
  const descriptorByPayload = new Map(dependencies.occurrenceResolutions.map((descriptor) => [descriptor.payloadId, descriptor]));
  const prepared = new Map(dependencies.preparedMedia.map((binding) => [binding.requirementKey, binding]));
  const trackIds = new Set(dependencies.tracks.map((track) => track.id));
  if (requirePrepared) {
    const roleVideoIds = [dependencies.roles.primaryRootTrackId, ...dependencies.roles.childTrackIds, ...dependencies.roles.overlayTrackIds];
    const topologyTracks = roleVideoIds.map((id) => dependencies.tracks.find((track) => track.id === id));
    const duplicateVisualRoles = new Set(roleVideoIds).size !== roleVideoIds.length;
    const ordered = topologyTracks.every((track) => track?.kind === "video") && dependencies.roles.childTrackIds.every((id) => dependencies.tracks.find((track) => track.id === id)!.index > dependencies.tracks.find((track) => track.id === dependencies.roles.primaryRootTrackId)!.index) && dependencies.roles.overlayTrackIds.every((id) => dependencies.tracks.find((track) => track.id === id)!.index > Math.max(dependencies.tracks.find((track) => track.id === dependencies.roles.primaryRootTrackId)!.index, ...dependencies.roles.childTrackIds.map((childId) => dependencies.tracks.find((track) => track.id === childId)!.index)));
    if (duplicateVisualRoles || !ordered) diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", "Primary root, child and overlay roles must be distinct existing video tracks in ascending composition order.", entity("track", dependencies.roles.primaryRootTrackId, "roles")));
    for (const id of [dependencies.roles.presenterTrackId, dependencies.roles.placeholderTrackId, dependencies.roles.markerTrackId, dependencies.roles.narrationTrackId, ...dependencies.roles.sourceAudioTrackIds]) {
      if (!trackIds.has(id)) diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", `Track role ${id} does not identify a configured track.`, entity("track", id, "roles")));
    }
    const narrationTrack = dependencies.tracks.find((track) => track.id === dependencies.roles.narrationTrackId);
    const sourceAudioTracks = dependencies.roles.sourceAudioTrackIds.map((id) => dependencies.tracks.find((track) => track.id === id));
    if (narrationTrack?.kind !== "audio" || new Set(dependencies.roles.sourceAudioTrackIds).size !== dependencies.roles.sourceAudioTrackIds.length || dependencies.roles.sourceAudioTrackIds.includes(dependencies.roles.narrationTrackId) || sourceAudioTracks.some((track) => track?.kind !== "audio")) {
      diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", "Narration and source-audio roles must identify distinct configured audio tracks.", entity("track", dependencies.roles.narrationTrackId, "roles")));
    }
  }
  for (const row of built.rows) {
    if (row.kind === "visual_only") {
      const rowDiagnosticStart = diagnostics.length;
      const rowEvents: TimelineEventV2[] = [];
      const block = row.block;
      const payload = block.payload;
      const range = { startFrame: row.startFrame, endFrame: safe(BigInt(row.startFrame) + BigInt(row.durationFrames), "visual-only end") };
      const eventId = stableId(`event:${document.id}:visual_only:${block.id}:${payload.payloadId}`);
      if (payload.pictureKind === "intentional_placeholder") {
        const text = payload.source.kind === "intentional_placeholder" ? payload.source.text : "";
        rowEvents.push({ eventId, kind: "placeholder", trackId: dependencies.roles.primaryRootTrackId, trackRole: "primary_root", recordRange: range, provenance: { documentId: document.id, blockId: block.id, sequenceId: null, slotId: null, payloadId: payload.payloadId, overlayEventId: null, sourceId: null, originalSourceHash: null, deliveredSourceHash: null, timingMapHash: null, compilerVersion: dependencies.compiler.version }, sourceRange: null, sourceTimeMapping: null, preparationBindingHash: null, audio: null, pictureTreatment: { kind: "slate", purpose: "intentional", text } });
      } else {
        const descriptor = descriptorByPayload.get(payload.payloadId);
        if (!descriptor || descriptor.owner.kind !== "visual_only_block" || descriptor.owner.blockId !== block.id || payload.source.kind === "media_reference" && descriptor.mediaReferenceId !== payload.source.mediaReferenceId || authoredSelectionMismatch(block.visualOnlyTiming.selectedSourceRange, descriptor)) {
          diagnostics.push(diagnostic("MISSING_OCCURRENCE_BINDING", "The visual-only source does not have an exact descriptor for this block and payload.", entity("block", block.id, "occurrenceResolutions"), undefined, ["rebind_media"]));
        } else {
          if (payload.audioPolicy !== "mute" && !verifiedSourceAudioStream(descriptor)) diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "Enabled visual-only source audio has no single verified audio stream.", entity("occurrence", descriptor.payloadId, "sourceAudioStreamMappings"), undefined, ["rebind_media"]));
          const requirementKey = descriptor.preparedMediaRequirementKey;
          const binding = requirementKey ? prepared.get(requirementKey) : undefined;
          const authoredSelection = block.visualOnlyTiming.selectedSourceRange;
          const selected: FrameRangeV2 | null = authoredSelection
            ? { startFrame: authoredSelection.startFrame, endFrame: safe(BigInt(authoredSelection.startFrame) + BigInt(authoredSelection.durationFrames), "visual-only selected range end") }
            : null;
          const isClip = payload.pictureKind === "clip";
          if (!isClip && payload.audioPolicy !== "mute") diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A held still frame cannot carry source audio; use mute or choose a clip.", entity("block", block.id, "audioPolicy"), undefined, ["repair_document"]));
          const sourceIn = selected?.startFrame ?? descriptor.occurrenceSourceInFrame;
          const available = isClip
            ? selected ?? { startFrame: descriptor.logicalSourceBounds.startFrame, endFrame: descriptor.logicalSourceBounds.endFrame }
            : { startFrame: sourceIn, endFrame: safe(BigInt(sourceIn) + 1n, "still source end") };
          const requiredEnd = available.endFrame;
          const exactDuration = isClip && requiredEnd
            ? sourceDurationInSeconds(requiredEnd - sourceIn, descriptor.logicalSourceBounds.frameRate)
            : sourceDurationInSeconds(1, descriptor.logicalSourceBounds.frameRate);
          const deliveredSourceFrames = isClip ? range.endFrame - range.startFrame : 1;
          const p5Range = preparationRange(sourceIn, exactDuration);
          if (!requiredEnd || !Number.isSafeInteger(sourceIn) || sourceIn < descriptor.logicalSourceBounds.startFrame || sourceIn >= descriptor.logicalSourceBounds.endFrame || requiredEnd > available.endFrame || requiredEnd > descriptor.logicalSourceBounds.endFrame) {
            const required = { startFrame: sourceIn, endFrame: requiredEnd ?? available.endFrame };
            requirements.push({ occurrenceKey: occurrenceKey(descriptor), payloadId: payload.payloadId, mediaReferenceId: descriptor.mediaReferenceId, requirementKey, requestedRange: p5Range, sourceRange: available, recordRange: range, requiredSourceRange: required, sourceSufficiency: "insufficient" });
            diagnostics.push(diagnostic("SOURCE_INSUFFICIENT", "The visual-only source does not cover its exact selected duration.", entity("media_reference", descriptor.mediaReferenceId, "sourceSufficiency"), { kind: "source_sufficiency", requiredRange: required, availableRange: available }, ["prepare_media"]));
          } else {
            const required = { startFrame: sourceIn, endFrame: requiredEnd };
            const sufficient = required.startFrame >= available.startFrame && required.endFrame <= available.endFrame;
            requirements.push({ occurrenceKey: occurrenceKey(descriptor), payloadId: payload.payloadId, mediaReferenceId: descriptor.mediaReferenceId, requirementKey, requestedRange: p5Range, sourceRange: available, recordRange: range, requiredSourceRange: required, sourceSufficiency: sufficient ? "sufficient" : "insufficient" });
            if (!sufficient) diagnostics.push(diagnostic("SOURCE_INSUFFICIENT", "The visual-only source does not cover its exact selected duration.", entity("media_reference", descriptor.mediaReferenceId, "sourceSufficiency"), { kind: "source_sufficiency", requiredRange: required, availableRange: available }, ["prepare_media"]));
            if (!binding) {
              if (requirePrepared) diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The visual-only occurrence has no verified preparation binding.", entity("occurrence", descriptor.payloadId, requirementKey ?? "preparedMedia"), undefined, ["prepare_media"]));
            } else if (!validPreparedBinding(descriptor, binding, dependencies.timeline.frameRate, p5Range)) {
              diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The visual-only preparation binding does not match its source identity, mapping, target rate or decoded samples.", entity("occurrence", descriptor.payloadId, requirementKey ?? "preparedMedia"), undefined, ["prepare_media"]));
            } else {
              try {
                const sourceId = deliveredSourceId(descriptor, binding);
                const delivered = deliveredRangeForOriginalRange(descriptor, binding.timeMapping, sourceIn, deliveredSourceFrames);
                const common = { documentId: document.id, blockId: block.id, sequenceId: null, slotId: null, payloadId: payload.payloadId, overlayEventId: null, sourceId, originalSourceHash: descriptor.sourceSnapshot.contentHash, deliveredSourceHash: binding.verification.deliveredHash, timingMapHash: null, compilerVersion: dependencies.compiler.version };
                const pictureTreatment = mediaStillTreatment(payload.pictureKind, payload.framingPolicy);
                rowEvents.push({ eventId, kind: "primary_visual", trackId: dependencies.roles.primaryRootTrackId, trackRole: "primary_root", recordRange: range, provenance: common, sourceRange: delivered, sourceTimeMapping: binding.timeMapping, preparationBindingHash: sha256CanonicalJson(binding), audio: null, ...(pictureTreatment ? { pictureTreatment } : {}) });
                if (payload.audioPolicy !== "mute" && isClip) {
                  const sourceAudioTrack = dependencies.roles.sourceAudioTrackIds[0];
                  if (!sourceAudioTrack || !dependencies.tracks.some((track) => track.id === sourceAudioTrack && track.kind === "audio")) throw new RangeError("enabled source audio requires a configured audio track");
                  rowEvents.push(makeSourceAudioEvent(dependencies, descriptor, binding, payload.audioPolicy, range, sourceIn, exactDuration, common, stableId(`source-audio:${eventId}`), sourceAudioTrack));
                }
              } catch (error) {
                diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", error instanceof Error ? error.message : String(error), entity("occurrence", descriptor.payloadId, "sourceFrameMap"), undefined, ["rebind_media", "prepare_media"]));
              }
            }
          }
        }
      }
      if (!requirePrepared && rowEvents.some((event) => event.kind === "source_audio")) rowEvents.splice(0);
      if (diagnostics.slice(rowDiagnosticStart).some((item) => item.severity === "blocking" || item.severity === "error")) continue;
      events.push(...rowEvents);
      continue;
    }
    const rowDiagnosticStart = diagnostics.length;
    const resolutionStart = sequenceResolutions.length;
    const rowEvents: TimelineEventV2[] = [];
    const block = row.block;
    const sequence = block.primaryVisualSequence;
    if (!sequence) continue;
    const rowProjection = projection.rows.find((item) => item.blockId === block.id);
    const rowStart = row.startFrame;
    const rowEnd = safe(BigInt(rowStart) + BigInt(row.durationFrames), "row end");
    const absoluteToken = (tokenId: string): number | null => {
      const frame = row.tokenFrames.get(tokenId);
      return frame === undefined ? null : safe(BigInt(rowStart) + BigInt(frame), "token frame");
    };
    const unresolvedReturns = sequence.slots.filter((slot): slot is ReturnSlot => slot.kind === "return")
      .filter((returned) => returned.inpoint === null || absoluteToken(returned.inpoint.tokenId) === null);
    if (unresolvedReturns.length > 0) {
      for (const returned of unresolvedReturns) diagnostics.push(diagnostic(
        "STALE_ANCHOR",
        "A structural return requires a current exact word inpoint; the child cannot silently extend to row end.",
        entity("block", block.id, "primaryVisualSequence/returns"),
        { kind: "anchor_issue", anchorId: returned.id, reason: "stale" },
        ["repair_document", "refresh_timing"],
      ));
      continue;
    }
    const slotStarts = new Map<string, number>();
    for (const slot of sequence.slots) {
      if (slot.kind === "return") continue;
      let start: number | null = slot.boundaryBefore.kind === "row_start" ? rowStart
        : slot.boundaryBefore.kind === "spoken_word" ? absoluteToken(slot.boundaryBefore.anchor.tokenId)
          : null;
      if (slot.boundaryBefore.kind === "previous_media_end") {
        const controllingSlotId = slot.boundaryBefore.controllingSlotId;
        const controlled = sequence.slots.find((candidate) => candidate.kind === "content" && candidate.id === controllingSlotId);
        if (controlled?.kind === "content" && controlled.payload.kind === "visual" && controlled.payload.pictureKind === "clip" && controlled.playoutPolicy === "complete_logged_clip") {
          const desc = descriptorByPayload.get(controlled.payload.payloadId);
          const authoredSourceIn = controlled.payload.sourceUsage?.sourceInFrame;
          if (desc && authoredSourceIn === desc.occurrenceSourceInFrame) {
            const sourceRate = rateFraction(desc.logicalSourceBounds.frameRate);
            const targetRate = rateFraction(dependencies.timeline.frameRate);
            const remaining = BigInt(desc.logicalSourceBounds.endFrame - desc.occurrenceSourceInFrame);
            if (remaining > 0n) {
              const duration = frac(remaining * sourceRate.d, sourceRate.n);
              const frames = safe(ceil(duration.n * targetRate.n, duration.d * targetRate.d), "complete clip frames");
              const priorStart = slotStarts.get(controlled.id);
              if (priorStart !== undefined) {
                start = safe(BigInt(priorStart) + BigInt(frames), "media-end boundary");
                const exactAbsoluteTime = add(frac(BigInt(priorStart) * BigInt(targetRate.d), targetRate.n), duration);
                const exactRowTime = frac(BigInt(rowStart) * BigInt(targetRate.d), targetRate.n);
                const exactLocalTime = sub(exactAbsoluteTime, exactRowTime);
                const relation = wordRelationAt(row, exactLocalTime);
                const resolvedLocalTime = frac(BigInt(start - rowStart) * BigInt(targetRate.d), targetRate.n);
                boundaryEvidence.push({
                  entityId: slot.id,
                  kind: "media_end",
                  inputTime: wireOrThrow(exactLocalTime, "media-end input time"),
                  resolvedRecordFrame: start,
                  delta: wireOrThrow(sub(resolvedLocalTime, exactLocalTime), "media-end boundary delta"),
                  precision: relation.wordRelation === "between_words" ? "between_words" : relation.wordRelation === "at_word_start" || relation.wordRelation === "inside_word" ? row.map.precision === "audible_word_marks" ? "audible_word" : "next_word_derived" : "unknown",
                  wordRelation: relation.wordRelation,
                  relatedTokenId: relation.relatedTokenId,
                });
              }
            }
          } else diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A media-end boundary requires its exact source-in and complete logged-clip descriptor.", entity("slot", slot.id, "boundaryBefore"), undefined, ["rebind_media"]));
        } else {
          diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A media-end boundary must follow a complete logged clip.", entity("slot", slot.id, "boundaryBefore"), undefined, ["repair_document"]));
        }
      }
      if (start === null) {
        diagnostics.push(diagnostic("STALE_ANCHOR", "A structural boundary has no current exact timing.", entity("slot", slot.id, `/activeDraft/blocks/${block.id}/primaryVisualSequence`), { kind: "anchor_issue", anchorId: slot.id, reason: "stale" }, ["repair_document", "refresh_timing"]));
      } else slotStarts.set(slot.id, start);
    }
    const content = sequence.slots.filter((slot): slot is ContentSlot => slot.kind === "content");
    const roots = content.filter((slot) => slot.relation.kind === "base" || slot.relation.kind === "sequential");
    const children = content.filter((slot): slot is CutawaySlot => slot.relation.kind === "cutaway");
    const rangeBySlot = new Map<string, FrameRangeV2>();
    roots.forEach((slot, index) => {
      const start = slotStarts.get(slot.id);
      const next = roots[index + 1] ? slotStarts.get(roots[index + 1]!.id) : rowEnd;
      if (start !== undefined && next !== undefined) rangeBySlot.set(slot.id, { startFrame: start, endFrame: next });
    });
    for (const child of children) {
      const start = slotStarts.get(child.id);
      const siblings = children.filter((candidate) => candidate.relation.parentSlotId === child.relation.parentSlotId);
      const childIndex = siblings.findIndex((candidate) => candidate.id === child.id);
      const returnSlot = sequence.slots.find((candidate): candidate is ReturnSlot => candidate.kind === "return" && candidate.parentSlotId === child.relation.parentSlotId);
      const next = siblings[childIndex + 1] ? slotStarts.get(siblings[childIndex + 1]!.id)
        : returnSlot?.inpoint ? absoluteToken(returnSlot.inpoint.tokenId) : null;
      const rowEndFallback = returnSlot?.inpoint === null ? null : rowEnd;
      const end = next ?? rowEndFallback;
      if (start !== undefined && end !== null && end !== undefined) rangeBySlot.set(child.id, { startFrame: start, endFrame: end });
    }
    for (const range of rangeBySlot.values()) if (range.startFrame >= range.endFrame) diagnostics.push(diagnostic("COLLAPSED_BOUNDARY", "Two authored boundaries collapse to the same or reversed record frame.", entity("block", block.id, "primaryVisualSequence"), { kind: "anchor_issue", anchorId: block.id, reason: "collapsed" }, ["repair_document", "refresh_timing"]));
    const badRow = diagnostics.some((item) => item.entity.id === block.id && item.severity === "blocking");
    if (badRow) continue;
    for (const slot of content) {
      const range = rangeBySlot.get(slot.id);
      if (!range) continue;
      const isChild = slot.relation.kind === "cutaway";
      const trackId = isChild ? dependencies.roles.childTrackIds[0] : dependencies.roles.primaryRootTrackId;
      if (!trackId && requirePrepared) {
        diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", "A content slot requires a configured track for its structural role.", entity("slot", slot.id, "roles")));
        continue;
      }
      const structuralTrack = trackId ?? "media-needs";
      const structuralRole = isChild ? "child" as const : "primary_root" as const;
      const payload = slot.payload;
      const payloadId = payload.kind === "on_camera" ? null : payload.payloadId;
      const descriptor = payloadId ? descriptorByPayload.get(payloadId) : undefined;
      const still = payload.kind === "on_camera" ? effectivePresenterStill(document, dependencies) : null;
      const common: TimelineEventV2["provenance"] = {
        documentId: document.id,
        blockId: block.id,
        sequenceId: sequence.id,
        slotId: slot.id,
        payloadId,
        overlayEventId: null,
        sourceId: descriptor?.mediaReferenceId ?? null,
        originalSourceHash: descriptor?.sourceSnapshot.contentHash ?? still?.contentHash ?? null,
        deliveredSourceHash: null,
        timingMapHash: row.map.timingHash,
        compilerVersion: dependencies.compiler.version,
      };
      const eventId = stableId(`event:${document.id}:${block.id}:${slot.id}:${payloadId ?? "presenter"}`);
      let emittedEvent: TimelineEventV2 | null = null;
      let occurrenceRange: FrameRangeV2 | null = null;
      let mapping: PreparationTimeMappingV1 | null = null;
      let requirementKey: string | null = null;
      let presenterChoice: VisualSequenceResolutionV2["presenterChoice"] = "not_applicable";
      if (payload.kind === "on_camera") {
        if (payload.presenterChoiceId !== null) {
          presenterChoice = "recorded";
          const alignment = dependencies.presenterAlignmentResolutions.find((item) => item.slotId === slot.id && item.takeId === payload.presenterChoiceId);
          diagnostics.push(diagnostic(
            "MIGRATION_REVIEW_REQUIRED",
            alignment
              ? "A recorded presenter alignment is present, but this compiler has no qualified recorded-media provider; the generic still fallback is suppressed."
              : "The selected recorded presenter take has no matching verified alignment; the generic still fallback is suppressed.",
            entity("slot", slot.id, "presenterChoiceId"),
            undefined,
            ["manual_review"],
          ));
        } else {
          presenterChoice = "temporary_still";
          emittedEvent = { eventId, kind: "placeholder", trackId: structuralTrack, trackRole: structuralRole, recordRange: range, provenance: common, sourceRange: null, sourceTimeMapping: null, preparationBindingHash: null, audio: null, pictureTreatment: { kind: "still", reference: still!, composition: { framingPolicy: "contain", horizontalAlignment: "center", verticalAlignment: "center", backgroundColor: "#000000", motionPreset: "none" } } };
          diagnostics.push(diagnostic("TEMPORARY_PRESENTER_STILL", "On Camera uses the effective temporary presenter still.", entity("slot", slot.id, "presenterStill"), undefined, ["REPLACE_TEMPORARY_PRESENTER"], "warning"));
        }
      } else if (payload.kind === "undefined" || payload.kind === "visual" && (payload.pictureKind === "intentional_placeholder" || payload.pictureKind === "unresolved_visual")) {
        const intentional = payload.kind === "visual" && payload.pictureKind === "intentional_placeholder";
        const forced = dependencies.build.forcePreviewVisuals === true && dependencies.build.buildClass === "preview";
        const pictureTreatment = payload.kind === "undefined"
          ? { kind: "slate" as const, purpose: "undefined" as const, text: payload.description }
          : { kind: "slate" as const, purpose: intentional ? "intentional" as const : "unresolved" as const, text: payload.source.kind === "intentional_placeholder" ? payload.source.text : payload.source.kind === "unresolved_visual" ? payload.source.description : "Visual request unresolved" };
        if (intentional || forced) emittedEvent = { eventId, kind: "placeholder", trackId: structuralTrack, trackRole: structuralRole, recordRange: range, provenance: common, sourceRange: null, sourceTimeMapping: null, preparationBindingHash: null, audio: null, pictureTreatment };
        if (!intentional) diagnostics.push(diagnostic("VISUAL_UNDEFINED", "A requested visual remains undefined for this build.", entity("slot", slot.id, "payload"), undefined, ["repair_document"], "blocking"));
      } else if (!descriptor || descriptor.owner.kind !== "primary_slot" || descriptor.owner.sequenceId !== sequence.id || descriptor.owner.slotId !== slot.id || payload.source.kind === "media_reference" && descriptor.mediaReferenceId !== payload.source.mediaReferenceId || payload.pictureKind === "clip" && payload.sourceUsage?.sourceInFrame !== descriptor.occurrenceSourceInFrame) {
        diagnostics.push(diagnostic("MISSING_OCCURRENCE_BINDING", "The visual occurrence has no exact descriptor for this sequence slot and source snapshot.", entity("slot", slot.id, "occurrenceResolutions"), undefined, ["rebind_media"]));
      } else {
        requirementKey = descriptor.preparedMediaRequirementKey;
        if (payload.kind === "visual" && payload.audioPolicy === "quiet" && !verifiedSourceAudioStream(descriptor)) diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "Quiet narration source audio has no single verified audio stream.", entity("occurrence", descriptor.payloadId, "sourceAudioStreamMappings"), undefined, ["rebind_media"]));
        const binding = requirementKey ? prepared.get(requirementKey) : undefined;
        const sourceIn = payload.sourceUsage?.sourceInFrame ?? descriptor.occurrenceSourceInFrame;
        const available = { startFrame: descriptor.logicalSourceBounds.startFrame, endFrame: descriptor.logicalSourceBounds.endFrame };
        const isClip = payload.pictureKind === "clip";
        const complete = slot.playoutPolicy === "complete_logged_clip" && isClip;
        if (!isClip && payload.audioPolicy === "quiet") diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A held still frame cannot carry source audio; use mute or choose a clip.", entity("slot", slot.id, "audioPolicy"), undefined, ["repair_document"]));
        const requiredEnd = complete ? descriptor.logicalSourceBounds.endFrame : isClip ? requiredSourceEnd(descriptor, range.endFrame - range.startFrame, dependencies.timeline.frameRate) : safe(BigInt(sourceIn) + 1n, "still source end");
        const required = { startFrame: sourceIn, endFrame: requiredEnd ?? available.endFrame };
        const exactDuration = complete && requiredEnd
          ? sourceDurationInSeconds(requiredEnd - sourceIn, descriptor.logicalSourceBounds.frameRate)
          : isClip ? recordDurationInSeconds(range.endFrame - range.startFrame, dependencies.timeline.frameRate) : sourceDurationInSeconds(1, descriptor.logicalSourceBounds.frameRate);
        const deliveredSourceFrames = isClip ? range.endFrame - range.startFrame : 1;
        const p5Range = preparationRange(sourceIn, exactDuration);
        const sufficient = !!requiredEnd && sourceIn >= available.startFrame && sourceIn < available.endFrame && sourceIn >= descriptor.logicalSourceBounds.startFrame && sourceIn < descriptor.logicalSourceBounds.endFrame && requiredEnd <= available.endFrame && requiredEnd <= descriptor.logicalSourceBounds.endFrame;
        requirements.push({ occurrenceKey: occurrenceKey(descriptor), payloadId: payloadId!, mediaReferenceId: descriptor.mediaReferenceId, requirementKey, requestedRange: p5Range, sourceRange: available, recordRange: range, requiredSourceRange: required, sourceSufficiency: sufficient ? "sufficient" : "insufficient" });
        if (!requiredEnd) diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "The logical source rate or requested source range is invalid.", entity("occurrence", descriptor.payloadId, "sourceFrameMap"), undefined, ["rebind_media"]));
        else if (!sufficient) diagnostics.push(diagnostic("SOURCE_INSUFFICIENT", "The source does not cover the exact requested record duration.", entity("media_reference", descriptor.mediaReferenceId, "sourceSufficiency"), { kind: "source_sufficiency", requiredRange: required, availableRange: available }, ["prepare_media"]));
        if (complete && requiredEnd) {
          const sourceRate = rateFraction(descriptor.logicalSourceBounds.frameRate);
          const exactDuration = frac(BigInt(requiredEnd - sourceIn) * sourceRate.d, sourceRate.n);
          const expectedRecordFrames = safe(ceil(exactDuration.n * BigInt(dependencies.timeline.frameRate.numerator), exactDuration.d * BigInt(dependencies.timeline.frameRate.denominator)), "complete logged clip frames");
          if (range.endFrame - range.startFrame !== expectedRecordFrames) diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A complete logged clip must use its exact terminal-quantized source duration.", entity("slot", slot.id, "playoutPolicy"), undefined, ["repair_document"]));
        }
        if (!binding) {
          if (requirePrepared) diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The source descriptor has no matching verified preparation binding.", entity("occurrence", descriptor.payloadId, requirementKey ?? "preparedMedia"), undefined, ["prepare_media"]));
        } else if (!validPreparedBinding(descriptor, binding, dependencies.timeline.frameRate, p5Range)) {
          diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The verified preparation binding does not match its source identity, mapping, target rate or decoded samples.", entity("occurrence", descriptor.payloadId, requirementKey ?? "preparedMedia"), undefined, ["prepare_media"]));
        } else if (sufficient && requiredEnd) {
          try {
            occurrenceRange = deliveredRangeForOriginalRange(descriptor, binding.timeMapping, sourceIn, deliveredSourceFrames);
            mapping = binding.timeMapping;
            const pictureTreatment = mediaStillTreatment(payload.pictureKind, payload.framingPolicy);
            emittedEvent = { eventId, kind: "primary_visual", trackId: structuralTrack, trackRole: structuralRole, recordRange: range, provenance: { ...common, sourceId: deliveredSourceId(descriptor, binding), deliveredSourceHash: binding.verification.deliveredHash }, sourceRange: occurrenceRange, sourceTimeMapping: binding.timeMapping, preparationBindingHash: sha256CanonicalJson(binding), audio: null, ...(pictureTreatment ? { pictureTreatment } : {}) };
            if (payload.audioPolicy === "quiet" && isClip) {
              const audioTrack = dependencies.roles.sourceAudioTrackIds[0];
              if (!audioTrack || !dependencies.tracks.some((track) => track.id === audioTrack && track.kind === "audio")) throw new RangeError("Quiet source audio requires a configured audio track");
              rowEvents.push(makeSourceAudioEvent(dependencies, descriptor, binding, "quiet", range, sourceIn, exactDuration, common, stableId(`source-audio:${eventId}`), audioTrack));
            }
          } catch (error) {
            diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", error instanceof Error ? error.message : String(error), entity("occurrence", descriptor.payloadId, "sourceFrameMap"), undefined, ["rebind_media", "prepare_media"]));
          }
        }
      }
      if (emittedEvent) rowEvents.push(emittedEvent);
      if (emittedEvent || payload.kind === "on_camera" && payload.presenterChoiceId !== null) {
        const startTime = row.tokenTimes.get(block.tokens.find((token) => row.tokenFrames.get(token.id) === range.startFrame - rowStart)?.id ?? "")?.start ?? frac(BigInt(range.startFrame - rowStart) * BigInt(dependencies.timeline.frameRate.denominator), BigInt(dependencies.timeline.frameRate.numerator));
        const delta = sub(frac(BigInt(range.startFrame - rowStart) * BigInt(dependencies.timeline.frameRate.denominator), BigInt(dependencies.timeline.frameRate.numerator)), startTime);
        sequenceResolutions.push({ documentId: document.id, blockId: block.id, blockRevision: block.version, sequenceId: sequence.id, sequenceVersion: sequence.version, structuralSlotIndex: sequence.slots.findIndex((item) => item.id === slot.id), relation: isChild ? "child" : "root", slotId: slot.id, payloadId, returnSlotId: null, boundaryKind: slot.boundaryBefore.kind === "row_start" ? "word_start" : slot.boundaryBefore.kind === "previous_media_end" ? "media_end" : "word_start", resolvedRecordFrame: range.startFrame, boundaryDelta: wireOrThrow(delta, "sequence boundary delta"), rootRanges: isChild ? [] : [range], childRanges: isChild ? [range] : [], topmostAppearances: emittedEvent ? [{ eventId, recordRange: range }] : [], hostState: payload.kind === "on_camera" ? "on_camera" : "voiceover", visualOrdinal: rowProjection?.slots.find((item) => item.slotId === slot.id)?.humanOrdinal ?? null, eventIds: emittedEvent ? [eventId] : [], sourceRange: occurrenceRange, sourceTimeMapping: mapping, preparationRequirementKey: requirementKey, presenterChoice, alignmentPrecision: row.map.precision === "audible_word_marks" ? "audible_word" : "next_word_derived" });
      }
    }
    for (const returned of sequence.slots.filter((slot) => slot.kind === "return")) {
      const frame = returned.inpoint ? absoluteToken(returned.inpoint.tokenId) : null;
      const root = roots.find((slot) => slot.id === returned.parentSlotId);
      if (!root) {
        diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A return must name an existing root slot in this sequence.", entity("slot", returned.id, "primaryVisualSequence"), undefined, ["repair_document"]));
        continue;
      }
      if (frame === null) {
        diagnostics.push(diagnostic("STALE_ANCHOR", "A return requires a current word inpoint; the row cannot safely fall through to its end.", entity("slot", returned.id, "primaryVisualSequence"), { kind: "anchor_issue", anchorId: returned.id, reason: returned.inpoint ? "stale" : "missing" }, ["repair_document", "refresh_timing"]));
        continue;
      }
      sequenceResolutions.push({ documentId: document.id, blockId: block.id, blockRevision: block.version, sequenceId: sequence.id, sequenceVersion: sequence.version, structuralSlotIndex: sequence.slots.findIndex((item) => item.id === returned.id), relation: "return", slotId: null, payloadId: null, returnSlotId: returned.id, boundaryKind: "word_start", resolvedRecordFrame: frame, boundaryDelta: { numerator: 0, denominator: 1 }, rootRanges: [], childRanges: [], topmostAppearances: [], hostState: "voiceover", visualOrdinal: null, eventIds: [], sourceRange: null, sourceTimeMapping: null, preparationRequirementKey: null, presenterChoice: "not_applicable", alignmentPrecision: "audible_word" });
    }
    for (const overlay of block.overlayEvents) {
      const anchorTimes: Record<string, RationalTime> = {};
      for (const [tokenId, value] of row.tokenTimes) {
        const token = block.tokens.find((item) => item.id === tokenId);
        if (!token) continue;
        const key = placementAnchorKeyV2({ kind: "word", anchor: { blockId: block.id, tokenId, affinity: "before", quotedWord: token.value, anchorVersion: block.version } });
        const t = wire(value.start);
        if (t) anchorTimes[key] = t;
      }
      const placement = resolveTimedPlacementV2(overlay.timing, { document, blockId: block.id, rowBounds: { start: { numerator: 0, denominator: 1 }, end: audioDurationWire(row.map.audio!) }, anchorTimes });
      if (placement.status !== "resolved" || !placement.interval) {
        diagnostics.push(diagnostic("STALE_ANCHOR", placement.diagnostics[0]?.message ?? "Overlay has no exact interval.", entity("overlay_event", overlay.id, "overlayEvents"), { kind: "anchor_issue", anchorId: overlay.id, reason: "stale" }, ["repair_document", "refresh_timing"]));
        continue;
      }
      const start = safe(BigInt(rowStart) + BigInt(framesAt(fromWire(placement.interval.start)!, rateFraction(dependencies.timeline.frameRate))), "overlay start");
      const end = safe(BigInt(rowStart) + BigInt(framesAt(fromWire(placement.interval.end)!, rateFraction(dependencies.timeline.frameRate))), "overlay end");
      if (start >= end) {
        diagnostics.push(diagnostic("COLLAPSED_BOUNDARY", "Overlay boundaries collapse after frame quantization.", entity("overlay_event", overlay.id, "overlayEvents"), { kind: "anchor_issue", anchorId: overlay.id, reason: "collapsed" }, ["repair_document"]));
        continue;
      }
      const descriptor = descriptorByPayload.get(overlay.payload.payloadId);
      if (!descriptor || descriptor.owner.kind !== "overlay_event" || descriptor.owner.blockId !== block.id || descriptor.owner.overlayEventId !== overlay.id || overlay.payload.source.kind === "media_reference" && descriptor.mediaReferenceId !== overlay.payload.source.mediaReferenceId || overlay.payload.pictureKind === "clip" && overlay.payload.sourceUsage?.sourceInFrame !== descriptor.occurrenceSourceInFrame) {
        diagnostics.push(diagnostic("MISSING_OCCURRENCE_BINDING", "The overlay has no verified source descriptor.", entity("overlay_event", overlay.id, "occurrenceResolutions"), undefined, ["rebind_media"]));
        continue;
      }
      const binding = descriptor.preparedMediaRequirementKey ? prepared.get(descriptor.preparedMediaRequirementKey) : undefined;
      if (overlay.payload.audioPolicy === "quiet" && !verifiedSourceAudioStream(descriptor)) diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "Quiet overlay source audio has no single verified audio stream.", entity("overlay_event", overlay.id, "sourceAudioStreamMappings"), undefined, ["rebind_media"]));
      const range = { startFrame: start, endFrame: end };
      const available = { startFrame: descriptor.logicalSourceBounds.startFrame, endFrame: descriptor.logicalSourceBounds.endFrame };
      const sourceIn = overlay.payload.sourceUsage?.sourceInFrame ?? descriptor.occurrenceSourceInFrame;
      const isClip = overlay.payload.pictureKind === "clip";
      if (!isClip && overlay.payload.audioPolicy === "quiet") {
        diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A held still frame cannot carry source audio; use mute or choose a clip.", entity("overlay_event", overlay.id, "audioPolicy"), undefined, ["repair_document"]));
        continue;
      }
      const requiredEnd = isClip ? requiredSourceEnd(descriptor, end - start, dependencies.timeline.frameRate) : safe(BigInt(sourceIn) + 1n, "still source end");
      const required = { startFrame: sourceIn, endFrame: requiredEnd ?? available.endFrame };
      const exactDuration = isClip ? recordDurationInSeconds(end - start, dependencies.timeline.frameRate) : sourceDurationInSeconds(1, descriptor.logicalSourceBounds.frameRate);
      const deliveredSourceFrames = isClip ? end - start : 1;
      const p5Range = preparationRange(sourceIn, exactDuration);
      const sufficient = !!requiredEnd && sourceIn >= available.startFrame && sourceIn < available.endFrame && sourceIn >= descriptor.logicalSourceBounds.startFrame && sourceIn < descriptor.logicalSourceBounds.endFrame && requiredEnd <= available.endFrame && requiredEnd <= descriptor.logicalSourceBounds.endFrame;
      requirements.push({ occurrenceKey: occurrenceKey(descriptor), payloadId: overlay.payload.payloadId, mediaReferenceId: descriptor.mediaReferenceId, requirementKey: descriptor.preparedMediaRequirementKey, requestedRange: p5Range, sourceRange: available, recordRange: range, requiredSourceRange: required, sourceSufficiency: sufficient ? "sufficient" : "insufficient" });
      if (!requiredEnd) {
        diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "The overlay source mapping cannot resolve its exact interval.", entity("overlay_event", overlay.id, "sourceFrameMap"), undefined, ["rebind_media"]));
        continue;
      }
      if (!sufficient) {
        diagnostics.push(diagnostic("SOURCE_INSUFFICIENT", "The overlay source does not cover its exact record interval.", entity("media_reference", descriptor.mediaReferenceId, "sourceSufficiency"), { kind: "source_sufficiency", requiredRange: required, availableRange: available }, ["prepare_media"]));
        continue;
      }
      if (!binding) {
        if (requirePrepared) diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The overlay has no verified preparation binding.", entity("overlay_event", overlay.id, "preparedMedia"), undefined, ["prepare_media"]));
        continue;
      }
      if (!validPreparedBinding(descriptor, binding, dependencies.timeline.frameRate, p5Range)) {
        diagnostics.push(diagnostic("PREPARATION_HASH_MISMATCH", "The overlay preparation binding does not match its source identity, mapping, target rate or decoded samples.", entity("occurrence", descriptor.payloadId, descriptor.preparedMediaRequirementKey ?? "preparedMedia"), undefined, ["prepare_media"]));
        continue;
      }
      const delivered = deliveredRangeForOriginalRange(descriptor, binding.timeMapping, sourceIn, deliveredSourceFrames);
      if (requirePrepared && overlay.payload.audioPolicy === "quiet" && !dependencies.roles.sourceAudioTrackIds[0]) {
        diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", "Quiet overlay source audio requires a configured source-audio track.", entity("overlay_event", overlay.id, "roles")));
        continue;
      }
      const eventId = stableId(`event:${document.id}:${block.id}:${overlay.id}:${overlay.payload.payloadId}`);
      const provenance: TimelineEventV2["provenance"] = { documentId: document.id, blockId: block.id, sequenceId: null, slotId: null, payloadId: overlay.payload.payloadId, overlayEventId: overlay.id, sourceId: deliveredSourceId(descriptor, binding), originalSourceHash: descriptor.sourceSnapshot.contentHash, deliveredSourceHash: binding.verification.deliveredHash, timingMapHash: row.map.timingHash, compilerVersion: dependencies.compiler.version };
      let pictureTreatment: TimelineEventV2["pictureTreatment"];
      try {
        pictureTreatment = mediaStillTreatment(overlay.payload.pictureKind, overlay.payload.framingPolicy);
      } catch (error) {
        diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", error instanceof Error ? error.message : String(error), entity("overlay_event", overlay.id, "pictureTreatment"), undefined, ["repair_document"]));
        continue;
      }
      rowEvents.push({ eventId, kind: "overlay_visual", trackId: dependencies.roles.overlayTrackIds[0] ?? "media-needs", trackRole: "overlay", recordRange: range, provenance, sourceRange: delivered, sourceTimeMapping: binding.timeMapping, preparationBindingHash: sha256CanonicalJson(binding), audio: null, ...(pictureTreatment ? { pictureTreatment } : {}) });
      if (overlay.payload.audioPolicy === "quiet" && requirePrepared) {
        const audioTrack = dependencies.roles.sourceAudioTrackIds[0];
        if (!audioTrack || !dependencies.tracks.some((track) => track.id === audioTrack && track.kind === "audio")) diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", "Quiet overlay source audio requires a configured audio track.", entity("overlay_event", overlay.id, "roles")));
        else {
          try { rowEvents.push(makeSourceAudioEvent(dependencies, descriptor, binding, "quiet", range, sourceIn, exactDuration, provenance, stableId(`source-audio:${eventId}`), audioTrack)); }
          catch (error) { diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", error instanceof Error ? error.message : String(error), entity("overlay_event", overlay.id, "sourceAudio"), undefined, ["rebind_media", "prepare_media"])); }
        }
      }
    }
    for (const evidence of row.map.tokens) {
      const frame = absoluteToken(evidence.tokenId);
      const time = fromWire(evidence.startTime);
      if (frame === null || !time) continue;
      const exactRecordTime = frac(BigInt(frame) * BigInt(dependencies.timeline.frameRate.denominator), BigInt(dependencies.timeline.frameRate.numerator));
      const exactTokenRecordTime = add(frac(BigInt(rowStart) * BigInt(dependencies.timeline.frameRate.denominator), BigInt(dependencies.timeline.frameRate.numerator)), time);
      boundaryEvidence.push({
        entityId: evidence.tokenId,
        kind: "word_start",
        inputTime: wireOrThrow(time, "word-start input time"),
        resolvedRecordFrame: frame,
        delta: wireOrThrow(sub(exactRecordTime, exactTokenRecordTime), "word-start boundary delta"),
        precision: row.map.precision === "audible_word_marks" ? "audible_word" : evidence.endBasis === "next_word_derived" ? "next_word_derived" : "unknown",
      });
    }
    if (diagnostics.slice(rowDiagnosticStart).some((item) => (item.severity === "blocking" || item.severity === "error") && item.code !== "VISUAL_UNDEFINED")) {
      const recordedResolutions = sequenceResolutions.slice(resolutionStart).filter((item) => item.presenterChoice === "recorded");
      sequenceResolutions.splice(resolutionStart);
      sequenceResolutions.push(...recordedResolutions);
    } else events.push(...rowEvents);
  }
  const expectedPayloadIds = new Set<string>();
  for (const block of document.activeDraft.blocks) {
    if (block.type === "visual_only" && block.payload.source.kind !== "intentional_placeholder" && block.payload.source.kind !== "unresolved_visual") expectedPayloadIds.add(block.payload.payloadId);
    if (block.type === "narration" && block.state === "active") {
      for (const slot of block.primaryVisualSequence?.slots ?? []) if (slot.kind === "content" && slot.payload.kind === "visual" && slot.payload.pictureKind !== "intentional_placeholder" && slot.payload.pictureKind !== "unresolved_visual") expectedPayloadIds.add(slot.payload.payloadId);
      for (const overlay of block.overlayEvents) if (overlay.payload.source.kind !== "intentional_placeholder" && overlay.payload.source.kind !== "unresolved_visual") expectedPayloadIds.add(overlay.payload.payloadId);
    }
  }
  const actual = new Set(dependencies.occurrenceResolutions.map((item) => item.payloadId));
  const duplicateDescriptors = dependencies.occurrenceResolutions.map((item) => item.payloadId).filter((id, index, all) => all.indexOf(id) !== index).sort(compareText);
  const missing = [...expectedPayloadIds].filter((id) => !actual.has(id)).sort(compareText);
  const extra = [...actual].filter((id) => !expectedPayloadIds.has(id)).sort(compareText);
  if (duplicateDescriptors.length) diagnostics.push(diagnostic("MISSING_OCCURRENCE_BINDING", "An occurrence payload has more than one source descriptor.", entity("document", document.id, "occurrenceResolutions"), { kind: "occurrence_set_mismatch", missingKeys: [], extraKeys: [...new Set(duplicateDescriptors)] }, ["rebind_media"]));
  if (missing.length || extra.length) diagnostics.push(diagnostic(missing.length ? "MISSING_OCCURRENCE_BINDING" : "EXTRA_OCCURRENCE_BINDING", "Occurrence resolutions do not exactly match required visual payloads.", entity("document", document.id, "occurrenceResolutions"), { kind: "occurrence_set_mismatch", missingKeys: missing, extraKeys: extra }, ["rebind_media"]));
  validateSourceAudioOverlap(events, diagnostics);
  return { timedRows: built.rows, events, requirements, sequenceResolutions, boundaryEvidence, diagnostics: diagnostics.sort(compareDiagnostic), durationFrames: built.rows.reduce((max, row) => Math.max(max, row.startFrame + row.durationFrames), 0) };
}

function audioDurationWire(audio: NonNullable<NarrationTokenTimingMapV2["audio"]>): RationalTime {
  const reduced = frac(BigInt(audio.durationSamples), BigInt(audio.sampleRate));
  const result = wire(reduced);
  if (!result) throw new RangeError("narration audio duration exceeds rational wire bounds");
  return result;
}
function occurrenceKey(descriptor: OccurrenceMediaResolutionV2): string { return `${descriptor.owner.kind}:${descriptor.payloadId}`; }
function deliveredSourceId(descriptor: OccurrenceMediaResolutionV2, binding: CompilerDependenciesV2["preparedMedia"][number]): string {
  return stableId(`delivered-source:${descriptor.mediaReferenceId}:${sha256CanonicalJson(binding)}`);
}

function sameJson(left: unknown, right: unknown): boolean { return canonicalJson(left) === canonicalJson(right); }
function sameRate(left: RationalRate, right: RationalRate): boolean {
  try { return compare(rateFraction(left), rateFraction(right)) === 0; } catch { return false; }
}
function exactLogicalTimeAtFrame(descriptor: OccurrenceMediaResolutionV2, frame: number): Fraction {
  const rate = rateFraction(descriptor.logicalSourceBounds.frameRate);
  const zero = descriptor.sourceFrameMap.packageFrameZeroLogicalFrame;
  const logged = fromWire(descriptor.sourceFrameMap.loggedTimeAtPackageFrameZero);
  if (!logged || !Number.isSafeInteger(zero) || !Number.isSafeInteger(frame)) throw new RangeError("source logical frame mapping is invalid");
  return add(logged, frac(BigInt(frame - zero) * rate.d, rate.n));
}

function authoredSelectionMismatch(
  selection: VisualOnlyBlockV2["visualOnlyTiming"]["selectedSourceRange"],
  descriptor: OccurrenceMediaResolutionV2 | undefined,
): boolean {
  if (!descriptor) return false;
  if (!selection) return descriptor.selectedSourceRange !== null;
  if (!descriptor.selectedSourceRange) return true;
  const endFrame = selection.startFrame + selection.durationFrames;
  return descriptor.occurrenceSourceInFrame !== selection.startFrame || descriptor.selectedSourceRange.startFrame !== selection.startFrame || descriptor.selectedSourceRange.endFrame !== endFrame;
}

function wordRelationAt(
  row: TimedRow,
  time: Fraction,
): { wordRelation: NonNullable<BoundaryEvidenceV2["wordRelation"]>; relatedTokenId: string | null } {
  const words = row.block.tokens.flatMap((token) => {
    const timing = row.tokenTimes.get(token.id);
    return timing ? [{ tokenId: token.id, ...timing }] : [];
  });
  const atStart = words.find((word) => compare(time, word.start) === 0);
  if (atStart) return { wordRelation: "at_word_start", relatedTokenId: atStart.tokenId };
  const inside = words.find((word) => word.evidenced && word.end && compare(time, word.start) > 0 && compare(time, word.end) < 0);
  if (inside) return { wordRelation: "inside_word", relatedTokenId: inside.tokenId };
  for (let index = 0; index + 1 < words.length; index += 1) {
    const previous = words[index]!;
    const next = words[index + 1]!;
    if (previous.evidenced && previous.end && compare(previous.end, time) <= 0 && compare(time, next.start) < 0 && compare(previous.end, next.start) < 0) {
      return { wordRelation: "between_words", relatedTokenId: null };
    }
  }
  return { wordRelation: "derived_or_unknown", relatedTokenId: null };
}

function deliveredRangeForOriginalRange(
  descriptor: OccurrenceMediaResolutionV2,
  mapping: PreparationTimeMappingV1,
  sourceStartFrame: number,
  recordFrames: number,
): FrameRangeV2 {
  const sourceOrigin = fromWire(mapping.sourceOrigin);
  const deliveredOrigin = fromWire(mapping.deliveredOrigin);
  if (!sourceOrigin || !deliveredOrigin) throw new RangeError("preparation origins are not reduced nonnegative rationals");
  const deliveredRate = rateFraction(mapping.deliveredRate);
  const sourceTime = exactLogicalTimeAtFrame(descriptor, sourceStartFrame);
  const deliveredTime = add(deliveredOrigin, sub(sourceTime, sourceOrigin));
  if (compare(deliveredTime, frac(0n, 1n)) < 0) throw new RangeError("mapped delivered source time is negative");
  const startFrame = framesAt(deliveredTime, deliveredRate);
  const endFrame = safe(BigInt(startFrame) + BigInt(recordFrames), "delivered event end frame");
  if (startFrame >= endFrame) throw new RangeError("delivered source interval collapses");
  return { startFrame, endFrame };
}

function effectivePresenterStill(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2): PresenterStillReference {
  return document.scriptSettings?.presenterStillOverride ?? dependencies.authoringDefaults.presenterStill ?? (genericTorso as PresenterStillReference);
}

function mediaStillTreatment(
  pictureKind: string,
  framingPolicy: string,
): TimelineEventV2["pictureTreatment"] {
  if (pictureKind === "clip") return undefined;
  if (pictureKind !== "image" && pictureKind !== "capture" && pictureKind !== "graphic") return undefined;
  if (framingPolicy !== "contain" && framingPolicy !== "cover" && framingPolicy !== "native") throw new RangeError("Media-backed still frames require a supported framing policy.");
  return { kind: "still_frame", pictureKind, framingPolicy };
}

function sourceMappingProblem(descriptor: OccurrenceMediaResolutionV2): string | null {
  try {
    const { startFrame, endFrame, frameRate } = descriptor.logicalSourceBounds;
    const map = descriptor.sourceFrameMap;
    const origin = map.packageFrameZeroLogicalFrame;
    if (!Number.isSafeInteger(startFrame) || !Number.isSafeInteger(endFrame) || startFrame < 0 || endFrame <= startFrame) return "Logical source bounds must be a positive half-open frame interval.";
    if (!Number.isSafeInteger(descriptor.occurrenceSourceInFrame) || descriptor.occurrenceSourceInFrame < startFrame || descriptor.occurrenceSourceInFrame >= endFrame) return "The occurrence source inpoint is outside its logical source bounds.";
    if (!Number.isSafeInteger(origin) || origin < 0 || origin > startFrame) return "The inspected package frame origin does not cover the logical source start.";
    if (!Number.isSafeInteger(map.decodedPackageFrameCount) || map.decodedPackageFrameCount <= 0 || endFrame - origin > map.decodedPackageFrameCount) return "The inspected package frame count does not cover the logical source bounds.";
    if (!sameRate(frameRate, map.decodedPackageFrameRate)) return "The inspected package rate differs from the logical source frame rate.";
    const packagePtsOrigin = fromWire(map.packageVideoPtsOrigin);
    const loggedTimeOrigin = fromWire(map.loggedTimeAtPackageFrameZero);
    if (!packagePtsOrigin || !loggedTimeOrigin || packagePtsOrigin.n < 0n || loggedTimeOrigin.n < 0n) return "Package and logged PTS origins must be exact non-negative rational times.";
    rateFraction(map.packageVideoTimeBase);
    if (!/^sha256:[0-9a-f]{64}$/.test(map.descriptorHash) || !/^sha256:[0-9a-f]{64}$/.test(map.probeHash) || map.probeHash !== descriptor.sourceSnapshot.probeHash) return "The source frame map does not bind the inspected source descriptor and probe.";
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : "The source frame map is invalid.";
  }
}

function validPreparedBinding(
  descriptor: OccurrenceMediaResolutionV2,
  binding: CompilerDependenciesV2["preparedMedia"][number],
  targetRate: RationalRate,
  expectedRange: RequestedPreparationRangeV1,
): boolean {
  try {
    const requested = binding.requestedRange;
    const mapping = binding.timeMapping;
    const verification = binding.verification;
    const duration = fromWire(requested.duration);
    const pre = fromWire(requested.preHandle);
    const post = fromWire(requested.postHandle);
    const sourceOrigin = fromWire(mapping.sourceOrigin);
    const deliveredOrigin = fromWire(mapping.deliveredOrigin);
    if (!duration || !pre || !post || !sourceOrigin || !deliveredOrigin || sourceMappingProblem(descriptor)) return false;
    if (!sameJson(requested, expectedRange)) return false;
    if (binding.originalSource.mediaReferenceId !== descriptor.mediaReferenceId || binding.originalSource.contentHash !== descriptor.sourceSnapshot.contentHash || binding.originalSource.probeHash !== descriptor.sourceSnapshot.probeHash) return false;
    if (!sameJson(mapping.sourceFrameMap, descriptor.sourceFrameMap) || !sameRate(mapping.sourceRate, descriptor.logicalSourceBounds.frameRate) || !sameRate(mapping.deliveredRate, targetRate) || !sameRate(binding.targetRate, targetRate) || !sameRate(verification.decodedFrameRate, targetRate)) return false;
    if (!/^sha256:[0-9a-f]{64}$/.test(mapping.mappingHash) || !/^sha256:[0-9a-f]{64}$/.test(verification.deliveredHash) || !/^sha256:[0-9a-f]{64}$/.test(verification.probeHash)) return false;
    const sourceIn = expectedRange.sourceInFrame;
    if (!Number.isSafeInteger(requested.sourceInFrame) || requested.sourceInFrame !== sourceIn) return false;
    const expectedSourceTime = exactLogicalTimeAtFrame(descriptor, requested.sourceInFrame);
    const expectedOrigin = binding.mode === "verified_reuse"
      ? fromWire(descriptor.sourceFrameMap.loggedTimeAtPackageFrameZero)
      : sub(expectedSourceTime, pre);
    if (!expectedOrigin) return false;
    if (compare(expectedOrigin, sourceOrigin) !== 0) return false;
    const preparedDuration = add(add(duration, pre), post);
    const expectedFrames = binding.mode === "verified_reuse"
      ? descriptor.sourceFrameMap.decodedPackageFrameCount
      : safe(ceil(preparedDuration.n * BigInt(targetRate.numerator), preparedDuration.d * BigInt(targetRate.denominator)), "prepared decoded frame count");
    if (!Number.isSafeInteger(verification.decodedFrameCount) || verification.decodedFrameCount !== expectedFrames) return false;
    const deliveredStartTime = add(deliveredOrigin, sub(expectedSourceTime, sourceOrigin));
    if (deliveredStartTime.n < 0n) return false;
    const deliveredStartFrame = framesAt(deliveredStartTime, rateFraction(targetRate));
    const deliveredRecordFrames = safe(ceil(duration.n * BigInt(targetRate.numerator), duration.d * BigInt(targetRate.denominator)), "prepared record frame count");
    if (deliveredStartFrame < 0 || BigInt(deliveredStartFrame) + BigInt(deliveredRecordFrames) > BigInt(verification.decodedFrameCount)) return false;
    if (!Number.isSafeInteger(verification.videoTimeBase.numerator) || !Number.isSafeInteger(verification.videoTimeBase.denominator) || verification.videoTimeBase.numerator <= 0 || verification.videoTimeBase.denominator <= 0) return false;
    if (binding.mode === "derived_cfr") {
      if (deliveredOrigin.n !== 0n || !binding.derivation || binding.derivation.sourceHash !== descriptor.sourceSnapshot.contentHash || binding.derivation.outputHash !== verification.deliveredHash || binding.derivation.toolHash !== binding.profile.toolHash || binding.derivation.profileHash !== binding.profile.profileHash) return false;
    }
    if (binding.mode === "verified_reuse" && (
      !sameRate(mapping.sourceRate, targetRate) ||
      deliveredOrigin.n !== 0n ||
      !sameRate(verification.videoTimeBase, descriptor.sourceFrameMap.packageVideoTimeBase) ||
      verification.deliveredHash !== descriptor.sourceSnapshot.contentHash ||
      verification.probeHash !== descriptor.sourceSnapshot.probeHash ||
      binding.derivation !== undefined
    )) return false;
    return true;
  } catch { return false; }
}

function sourceAudioSamplesForRange(
  descriptor: OccurrenceMediaResolutionV2,
  stream: OccurrenceMediaResolutionV2["sourceFrameMap"]["sourceAudioStreamMappings"][number],
  sourceStartFrame: number,
  exactDuration: Fraction,
): FrameRangeV2 {
  const rate = BigInt(stream.sampleRate);
  if (!Number.isSafeInteger(stream.sampleRate) || stream.sampleRate <= 0) throw new RangeError("source audio sample rate is invalid");
  const origin = fromWire(stream.loggedTimeAtPackageOrigin);
  if (!origin || !fromWire(stream.packagePtsOrigin)) throw new RangeError("source audio PTS origin is invalid");
  const toSample = (time: Fraction): number => {
    const relative = sub(time, origin);
    if (relative.n < 0n) throw new RangeError("requested source audio begins before the verified audio stream origin");
    return safe(ceil(relative.n * rate, relative.d), "source audio sample endpoint");
  };
  const sourceStart = exactLogicalTimeAtFrame(descriptor, sourceStartFrame);
  const startFrame = toSample(sourceStart);
  const endFrame = toSample(add(sourceStart, exactDuration));
  if (startFrame >= endFrame) throw new RangeError("source audio range collapses at exact sample endpoints");
  return { startFrame, endFrame };
}

function verifiedSourceAudioStream(descriptor: OccurrenceMediaResolutionV2): OccurrenceMediaResolutionV2["sourceFrameMap"]["sourceAudioStreamMappings"][number] | null {
  const streams = descriptor.sourceFrameMap.sourceAudioStreamMappings;
  if (streams.length !== 1) return null;
  const stream = streams[0]!;
  return stream.probeHash === descriptor.sourceSnapshot.probeHash && /^sha256:[0-9a-f]{64}$/.test(stream.audioHash) && Number.isSafeInteger(stream.sampleRate) && stream.sampleRate > 0 ? stream : null;
}

function makeSourceAudioEvent(
  dependencies: CompilerDependenciesV2,
  descriptor: OccurrenceMediaResolutionV2,
  binding: CompilerDependenciesV2["preparedMedia"][number],
  policy: "quiet" | "full",
  recordRange: FrameRangeV2,
  sourceStartFrame: number,
  exactDuration: Fraction,
  provenance: TimelineEventV2["provenance"],
  eventId: string,
  trackId: string,
): TimelineEventV2 {
  const stream = verifiedSourceAudioStream(descriptor);
  if (!stream) throw new RangeError("enabled source audio requires exactly one probe-bound source audio stream");
  const verification = binding.verification.sourceAudio;
  const offset = verification.offset ? fromWire(verification.offset) : null;
  const drift = verification.maxDrift ? fromWire(verification.maxDrift) : null;
  if (verification.status !== "aligned" || verification.sampleRate !== stream.sampleRate || !offset || !drift || compare(offset.n < 0n ? frac(-offset.n, offset.d) : offset, frac(1n, 100n)) > 0 || compare(drift, frac(1n, 200n)) > 0) {
    throw new RangeError("enabled source audio lacks exact aligned-stream sample-rate and sync-drift verification");
  }
  const sourceAudio = sourceAudioSamplesForRange(descriptor, stream, sourceStartFrame, exactDuration);
  const gainDb = policy === "quiet" ? dependencies.authoringDefaults.sourceAudioLevelPolicy.quietGainDb : dependencies.authoringDefaults.sourceAudioLevelPolicy.fullGainDb;
  return {
    eventId,
    kind: "source_audio",
    trackId,
    trackRole: "source_audio",
    recordRange,
    provenance: { ...provenance, sourceId: deliveredSourceId(descriptor, binding), originalSourceHash: stream.audioHash, deliveredSourceHash: binding.verification.deliveredHash },
    sourceRange: null,
    sourceTimeMapping: binding.timeMapping,
    preparationBindingHash: sha256CanonicalJson(binding),
    audio: { audioPolicy: policy, levelPolicyVersion: dependencies.authoringDefaults.sourceAudioLevelPolicy.version, gainDb, streamIndex: stream.streamIndex, audioHash: stream.audioHash, sampleRange: sourceAudio },
  };
}

function supportingPointFrame(
  anchor: PointPlacement["anchor"],
  document: ScriptDocumentV2,
  rows: ProgramRow[],
  events: TimelineEventV2[],
  targetRate: RationalRate,
): { frame: number; blockId: string | null; overlayEventId: string | null } | null {
  if (anchor.kind === "word") {
    const row = rows.find((candidate): candidate is TimedRow => candidate.kind === "narration" && candidate.block.id === anchor.anchor.blockId);
    if (!row || !isWordAnchorCurrentV2(anchor.anchor, row.block)) return null;
    const localFrame = row.tokenFrames.get(anchor.anchor.tokenId);
    if (localFrame === undefined) return null;
    if (anchor.anchor.affinity === "before") return { frame: safe(BigInt(row.startFrame) + BigInt(localFrame), "supporting marker frame"), blockId: row.block.id, overlayEventId: null };
    const timing = row.tokenTimes.get(anchor.anchor.tokenId);
    if (!timing?.evidenced || !timing.end) return null;
    const afterFrame = safe(BigInt(row.startFrame) + ceil(timing.end.n * BigInt(targetRate.numerator), timing.end.d * BigInt(targetRate.denominator)), "supporting marker frame");
    return { frame: afterFrame, blockId: row.block.id, overlayEventId: null };
  }
  if (anchor.kind === "event_edge") {
    const event = events.find((candidate) => candidate.provenance.overlayEventId === anchor.eventId && candidate.kind === "overlay_visual");
    if (!event) return null;
    return { frame: anchor.edge === "start" ? event.recordRange.startFrame : event.recordRange.endFrame, blockId: event.provenance.blockId, overlayEventId: anchor.eventId };
  }
  const blocks = document.activeDraft.blocks;
  const beforeIndex = blocks.findIndex((block) => block.id === anchor.beforeBlockId);
  const afterIndex = blocks.findIndex((block) => block.id === anchor.afterBlockId);
  if (beforeIndex < 0 || afterIndex !== beforeIndex + 1) return null;
  const before = rows.find((candidate) => candidate.block.id === anchor.beforeBlockId);
  const after = rows.find((candidate) => candidate.block.id === anchor.afterBlockId);
  if (!before || !after) return null;
  const beforeFrame = before.startFrame + before.durationFrames;
  const afterFrame = after.startFrame;
  if (beforeFrame !== afterFrame) return null;
  return { frame: beforeFrame, blockId: null, overlayEventId: null };
}

function compileSupportingItems(
  document: ScriptDocumentV2,
  dependencies: CompilerDependenciesV2,
  rows: ProgramRow[],
  existingEvents: TimelineEventV2[],
): { items: BuildReportV2["itemResults"]; events: TimelineEventV2[]; diagnostics: BuildDiagnosticV2[] } {
  const items: BuildReportV2["itemResults"] = [];
  const events: TimelineEventV2[] = [];
  const diagnostics: BuildDiagnosticV2[] = [];
  const programmeEnd = rows.reduce((end, row) => Math.max(end, row.startFrame + row.durationFrames), 0);
  for (const item of document.activeDraft.supportingItems) {
    if (item.role === "picture") {
      const reason = item.placement.kind === "unplaced" ? item.placement.reason : "Supporting pictures must be promoted into the primary visual sequence before compilation.";
      items.push({ itemId: item.id, version: item.version, role: item.role, disposition: item.placement.kind === "unplaced" ? "unplaced" : "blocked", recordRange: null, reason });
      diagnostics.push(diagnostic(
        item.placement.kind === "unplaced" ? "UNPLACED_SUPPORTING_ITEM" : "MIGRATION_REVIEW_REQUIRED",
        item.placement.kind === "unplaced" ? "An unplaced active picture blocks ordinary build readiness." : reason,
        entity("supporting_item", item.id, "supportingItems"),
        item.placement.kind === "unplaced" ? { kind: "anchor_issue", anchorId: item.id, reason: "unplaced" } : undefined,
        item.placement.kind === "unplaced" ? ["reattach_unplaced_item"] : ["repair_document"],
      ));
      continue;
    }
    if (item.role === "audio_cue") {
      const reason = "Audio-cue execution is unavailable in this compiler slice; the cue is retained without mixing.";
      items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "blocked", recordRange: null, reason });
      diagnostics.push(diagnostic("MIGRATION_REVIEW_REQUIRED", reason, entity("supporting_item", item.id, "supportingItems"), undefined, ["manual_review"]));
      continue;
    }
    if (item.role === "editor_note") {
      if (item.placement.kind !== "point") {
        const reason = item.placement.kind === "unplaced" ? item.placement.reason : "Editor notes compile only from an exact point anchor.";
        items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "unplaced", recordRange: null, reason });
        diagnostics.push(diagnostic("UNPLACED_SUPPORTING_ITEM", reason, entity("supporting_item", item.id, "supportingItems"), { kind: "anchor_issue", anchorId: item.id, reason: "unplaced" }, ["repair_document"], "warning"));
        continue;
      }
      const point = supportingPointFrame(item.placement.anchor, document, rows, existingEvents, dependencies.timeline.frameRate);
      if (!point) {
        const reason = "The editor-note point is stale or has no exact timeline time; reattach it to a current anchor.";
        items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "unplaced", recordRange: null, reason });
        diagnostics.push(diagnostic("UNPLACED_SUPPORTING_ITEM", reason, entity("supporting_item", item.id, "supportingItems"), { kind: "anchor_issue", anchorId: item.id, reason: "stale" }, ["repair_document", "refresh_timing"], "warning"));
        continue;
      }
      if (point.frame < 0 || point.frame >= programmeEnd) {
        const reason = "This point is at or beyond the exclusive programme end, which cannot be represented without extending playback.";
        items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "unplaced", recordRange: null, reason });
        diagnostics.push(diagnostic("UNPLACED_SUPPORTING_ITEM", reason, entity("supporting_item", item.id, "supportingItems"), { kind: "anchor_issue", anchorId: item.id, reason: "unplaced" }, ["repair_document"], "warning"));
        continue;
      }
      const trackId = dependencies.roles.markerTrackId;
      if (!dependencies.tracks.some((track) => track.id === trackId)) {
        const reason = "No configured marker track can carry this editor note.";
        items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "blocked", recordRange: null, reason });
        diagnostics.push(diagnostic("TRACK_ROLE_COLLISION", reason, entity("track", trackId, "roles.markerTrackId")));
        continue;
      }
      const recordRange = { startFrame: point.frame, endFrame: safe(BigInt(point.frame) + 1n, "editor marker endpoint") };
      const eventId = stableId(`script-marker:${document.id}:${item.id}:${item.version}`);
      events.push({
        eventId,
        kind: "script_marker",
        trackId,
        trackRole: "marker",
        recordRange,
        provenance: {
          documentId: document.id,
          blockId: point.blockId,
          sequenceId: null,
          slotId: null,
          payloadId: null,
          overlayEventId: point.overlayEventId,
          sourceId: null,
          originalSourceHash: null,
          deliveredSourceHash: null,
          timingMapHash: rows.find((row): row is TimedRow => row.kind === "narration" && row.block.id === point.blockId)?.map.timingHash ?? null,
          compilerVersion: dependencies.compiler.version,
        },
        sourceRange: null,
        sourceTimeMapping: null,
        preparationBindingHash: null,
        audio: null,
        marker: { supportingItemId: item.id, text: item.content },
      });
      items.push({ itemId: item.id, version: item.version, role: item.role, disposition: "placed", recordRange, reason: null });
      continue;
    }
    const reason = item.placement.kind === "unplaced" ? item.placement.reason : null;
    items.push({ itemId: item.id, version: item.version, role: item.role, disposition: item.placement.kind === "unplaced" ? "unplaced" : "omitted", recordRange: null, reason });
  }
  return { items, events, diagnostics };
}

function requiredSourceEnd(descriptor: OccurrenceMediaResolutionV2, recordFrames: number, targetRateWire: RationalRate): number | null {
  try {
    const fs = rateFraction(descriptor.logicalSourceBounds.frameRate); const target = rateFraction(targetRateWire);
    const start = BigInt(descriptor.occurrenceSourceInFrame); const origin = BigInt(descriptor.sourceFrameMap.packageFrameZeroLogicalFrame);
    if (!Number.isSafeInteger(descriptor.occurrenceSourceInFrame) || descriptor.occurrenceSourceInFrame < descriptor.logicalSourceBounds.startFrame) return null;
    const sourceStart = frac((start - origin) * fs.d, fs.n);
    const recordDuration = frac(BigInt(recordFrames) * target.d, target.n);
    const end = add(sourceStart, recordDuration);
    const frameEnd = BigInt(origin) + ceil(end.n * fs.n, end.d * fs.d);
    return safe(frameEnd, "required source end");
  } catch { return null; }
}

function validateSourceAudioOverlap(eventsIn: TimelineEventV2[], diagnostics: BuildDiagnosticV2[]): void {
  const enabled = eventsIn.filter((event) => event.kind === "source_audio" && event.audio !== null).sort((a, b) => a.recordRange.startFrame - b.recordRange.startFrame);
  let furthestPriorEnd = -1;
  for (const current of enabled) {
    if (current.recordRange.startFrame < furthestPriorEnd) diagnostics.push(diagnostic("SOURCE_AUDIO_OVERLAP", "Two enabled source-audio events overlap in record time.", entity("occurrence", current.eventId, "events"), undefined, ["repair_document"]));
    furthestPriorEnd = Math.max(furthestPriorEnd, current.recordRange.endFrame);
  }
}

function makeReport(diagnostics: BuildDiagnosticV2[], manifest: TimelineManifestV2, dependencies: CompilerDependenciesV2, requirements: MediaRequirementV2[], eventResults: BuildReportV2["eventResults"], itemResults: BuildReportV2["itemResults"]): BuildReportV2 {
  const sorted = [...diagnostics].sort(compareDiagnostic);
  const blocked = sorted.some((item) => item.severity === "blocking" || item.severity === "error");
  const recoveryActions: BuildReportV2["recoveryActions"] = [];
  for (const kind of [...new Set(sorted.flatMap((item) => item.recoveryActionKinds))]) {
    if (kind === "repair_document") recoveryActions.push({ kind, documentId: manifest.document.documentId, entity: entity("document", manifest.document.documentId, "document"), instruction: "Repair the authored source and compile again." });
    else if (kind === "refresh_timing") recoveryActions.push({ kind, blockId: sorted.find((item) => item.recoveryActionKinds.includes(kind))?.entity.id ?? manifest.document.documentId, expectedRevision: manifest.document.revision, instruction: "Refresh narration timing for the frozen text." });
    else if (kind === "rebind_media") recoveryActions.push({ kind, occurrenceKey: sorted.find((item) => item.recoveryActionKinds.includes(kind))?.entity.id ?? "unknown", mediaReferenceId: sorted.find((item) => item.recoveryActionKinds.includes(kind))?.entity.id ?? "unknown", instruction: "Bind the exact source snapshot and verify it again." });
    else if (kind === "prepare_media") recoveryActions.push({ kind, requirementKey: requirements.find((item) => item.requirementKey)?.requirementKey ?? "unresolved", instruction: "Prepare the source with the approved profile and verify its bytes." });
    else if (kind === "reattach_unplaced_item") recoveryActions.push({ kind, supportingItemId: sorted.find((item) => item.recoveryActionKinds.includes(kind))?.entity.id ?? manifest.document.documentId, instruction: "Place the supporting picture before building." });
    else if (kind === "select_supported_profile") recoveryActions.push({ kind, profileHash: dependencies.compiler.profileHash, instruction: "Choose a supported media preparation profile." });
    else if (kind === "retry_stage") recoveryActions.push({ kind, stage: "compilation", instruction: "Retry the failed deterministic compilation stage." });
    else if (kind === "REPLACE_TEMPORARY_PRESENTER") recoveryActions.push({ kind, documentId: manifest.document.documentId, slotId: sorted.find((item) => item.recoveryActionKinds.includes(kind))?.entity.id ?? manifest.document.documentId, instruction: "Replace the temporary still with an accepted presenter source when available." });
    else if (kind === "none") recoveryActions.push({ kind, instruction: "No repair action is required." });
    else recoveryActions.push({ kind: "manual_review", entity: entity("document", manifest.document.documentId, "document"), instruction: "Review the compiler diagnostic." });
  }
  const manualCompletionItems: BuildReportV2["manualCompletionItems"] = sorted
    .filter((item) => item.code === "TEMPORARY_PRESENTER_STILL")
    .map((item) => ({ id: stableId(`manual-completion:${manifest.document.documentId}:${item.entity.id ?? "presenter"}`), kind: "placeholder", message: "Replace the temporary presenter still when an accepted presenter source is available.", entity: item.entity }));
  const mediaRequirements: BuildReportV2["mediaPreparation"]["requirements"] = requirements.map((item) => {
    const descriptor = dependencies.occurrenceResolutions.find((candidate) => candidate.payloadId === item.payloadId);
    if (!descriptor) throw new Error(`Media requirement ${item.requirementKey ?? item.payloadId} has no source descriptor for its original hash.`);
    const binding = item.requirementKey ? dependencies.preparedMedia.find((candidate) => candidate.requirementKey === item.requirementKey) : undefined;
    const validBinding = item.sourceSufficiency === "sufficient" && !!binding && validPreparedBinding(descriptor, binding, manifest.timeline.frameRate, item.requestedRange);
    return {
      requirementKey: item.requirementKey ?? `missing:${item.payloadId}`,
      status: !validBinding ? "blocked" : binding.mode === "verified_reuse" ? "reused" : "prepared",
      originalHash: descriptor.sourceSnapshot.contentHash,
      deliveredHash: validBinding ? binding.verification.deliveredHash : null,
      bindingHash: validBinding ? sha256CanonicalJson(binding) : null,
      diagnosticIds: sorted.filter((d) => d.entity.id === item.payloadId || d.entity.id === item.mediaReferenceId).map((d) => d.id),
    };
  });
  const mediaStatus: BuildReportV2["mediaPreparation"]["status"] = requirements.length === 0 ? "not_required" : mediaRequirements.some((item) => item.status === "blocked") ? "blocked" : "complete";
  return {
    schemaVersion: "build-report/v2", id: dependencies.build.reportId, buildId: dependencies.build.buildId, buildClass: dependencies.build.buildClass,
    status: blocked ? "blocked" : "ready", document: dependencies.document, compiler: dependencies.compiler,
    dependenciesHash: sha256CanonicalJson(dependencies), manifest: { id: manifest.id, contentHash: sha256CanonicalJson(manifest) }, timeline: manifest.timeline,
    summary: { sourceCount: manifest.sources.length, eventCount: manifest.events.length, placedCount: eventResults.filter((item) => item.disposition === "placed").length, placeholderCount: eventResults.filter((item) => item.disposition === "placeholder").length, blockedCount: eventResults.filter((item) => item.disposition === "blocked").length + itemResults.filter((item) => item.disposition === "blocked").length, supportingItemCount: itemResults.length, diagnosticCount: sorted.length, recoveryActionCount: recoveryActions.length, manualCompletionCount: manualCompletionItems.length },
    eventResults, itemResults, diagnostics: sorted, recoveryActions,
    mediaPreparation: { status: mediaStatus, requirements: mediaRequirements },
    sourceSufficiency: requirements.map((item) => ({ requirementKey: item.requirementKey ?? `missing:${item.payloadId}`, status: item.sourceSufficiency, requiredRange: item.requiredSourceRange, availableRange: item.sourceRange, diagnosticId: sorted.find((d) => d.code === "SOURCE_INSUFFICIENT" && d.entity.id === item.mediaReferenceId)?.id ?? null })),
    migrationIssues: manifest.supportingItemResults.filter((item) => item.disposition === "unplaced" && (item.role === "picture" || item.role === "editor_note")).map((item) => ({ kind: "unplaced_item", severity: "warning", entity: entity("supporting_item", item.itemId, "supportingItems"), message: item.reason ?? "Unplaced item", recoveryActionKind: "reattach_unplaced_item" })),
    readiness: { preview: blocked ? "blocked" : "ready", release: blocked ? "blocked" : "ready", blockingIssueIds: sorted.filter((item) => item.severity === "blocking" || item.severity === "error").map((item) => item.id) },
    manualCompletionItems,
  };
}

export function compileTimelineV2(documentInput: unknown, dependenciesInput: unknown): CompileTimelineResultV2 {
  const validDocument = validateScriptDocumentV2(documentInput);
  if (!validDocument.valid) return fail(...validDocument.diagnostics.map((item) => ({ code: item.code, message: item.message, jsonPath: item.jsonPath, ...(item.entityId ? { entityId: item.entityId } : {}) })));
  if (!validateDependencies(dependenciesInput)) return fail(...schemaDiagnostics(validateDependencies.errors, "DEPENDENCIES"));
  const document = documentInput as ScriptDocumentV2;
  const dependencies = dependenciesInput;
  const audioBindingProblem = conflictingNarrationAudioBinding(dependencies.narrationTimingMaps);
  if (audioBindingProblem) return fail(audioBindingProblem);
  const seenTrackIds = new Set<string>();
  for (const track of dependencies.tracks) {
    if (seenTrackIds.has(track.id)) return fail({ code: "TRACK_ROLE_COLLISION", message: `Timeline track ID ${track.id} is duplicated.`, jsonPath: "/tracks", entityId: track.id });
    seenTrackIds.add(track.id);
  }
  const seenRequirementKeys = new Set<string>();
  for (const binding of dependencies.preparedMedia) {
    if (seenRequirementKeys.has(binding.requirementKey)) return fail({ code: "PREPARATION_HASH_MISMATCH", message: `Prepared media requirement key ${binding.requirementKey} is duplicated.`, jsonPath: "/preparedMedia", entityId: binding.requirementKey });
    seenRequirementKeys.add(binding.requirementKey);
  }
  for (const descriptor of dependencies.occurrenceResolutions) {
    const mappingProblem = sourceMappingProblem(descriptor);
    if (mappingProblem) return fail({ code: "SOURCE_MAPPING_MISMATCH", message: mappingProblem, jsonPath: `/occurrenceResolutions/${descriptor.payloadId}/sourceFrameMap`, entityId: descriptor.payloadId });
  }
  const malformedText = malformedFrozenText(document);
  if (malformedText) return fail(malformedText);
  const documentTextHash = shaText(document.activeDraft.blocks.filter((item): item is NarrationBlockV2 => item.type === "narration").map((item) => item.text).join("\n"));
  if (dependencies.document.textHash !== documentTextHash) return fail({ code: "DOCUMENT_BINDING_MISMATCH", message: "Compiler dependencies do not bind the exact frozen narration text hash.", jsonPath: "/document/textHash", entityId: document.id });
  for (const block of document.activeDraft.blocks) if (block.type === "narration" && block.state === "active") {
    const map = dependencies.narrationTimingMaps.find((candidate) => candidate.blockId === block.id);
    if (!map?.audio || map.audio.narrationAssetId !== map.narrationAssetId || map.audio.audioHash !== map.audioHash) return fail({ code: "NARRATION_DURATION_UNKNOWN", message: `Active narration ${block.id} has no verified exact audio duration.`, jsonPath: `/narrationTimingMaps/${block.id}/audio`, entityId: block.id });
  }
  if (dependencies.document.documentId !== document.id || dependencies.document.projectId !== document.projectId || dependencies.document.liveHeadSequence !== document.liveHeadSequence || dependencies.document.contentHash !== document.liveContentHash) return fail({ code: "DOCUMENT_BINDING_MISMATCH", message: "Compiler dependencies do not bind to the exact frozen document identity and live head.", jsonPath: "/document" });
  if (dependencies.document.settingsHash !== dependencies.authoringDefaults.settingsHash) return fail({ code: "SETTINGS_BINDING_MISMATCH", message: "Compiler dependencies do not bind the exact frozen authoring-default settings hash.", jsonPath: "/authoringDefaults/settingsHash" });
  if (!document.activeDraft.blocks.some((block) => block.type === "visual_only" || block.type === "narration" && block.state === "active")) return fail({ code: "EMPTY_PROGRAM", message: "The frozen draft has no active duration-bearing blocks.", jsonPath: "/activeDraft/blocks", entityId: document.id });
  try {
    const resolved = resolvePlan(document, dependencies);
    const invalidTopology = resolved.diagnostics.find((item) => item.code === "TRACK_ROLE_COLLISION");
    if (invalidTopology) return fail({ code: invalidTopology.code, message: invalidTopology.message, ...(invalidTopology.entity.id ? { entityId: invalidTopology.entity.id } : {}) });
    const sourcesById = new Map<string, TimelineManifestV2["sources"][number]>();
    for (const map of dependencies.narrationTimingMaps) if (map.audio) sourcesById.set(map.audio.narrationAssetId, { id: map.audio.narrationAssetId, narrationAudio: map.audio });
    for (const descriptor of dependencies.occurrenceResolutions) {
      const binding = descriptor.preparedMediaRequirementKey ? dependencies.preparedMedia.find((item) => item.requirementKey === descriptor.preparedMediaRequirementKey) : undefined;
      if (binding) {
        const id = deliveredSourceId(descriptor, binding);
        sourcesById.set(id, { id, mediaReferenceId: descriptor.mediaReferenceId, originalHash: descriptor.sourceSnapshot.contentHash, originalProbeHash: descriptor.sourceSnapshot.probeHash, deliveredHash: binding.verification.deliveredHash, deliveredProbeHash: binding.verification.probeHash, sourceFrameMap: descriptor.sourceFrameMap, sourceTimeMapping: binding.timeMapping, preparationRequirementKey: descriptor.preparedMediaRequirementKey });
      }
    }
    for (const row of resolved.timedRows) {
      if (row.kind !== "narration") continue;
      const start = row.startFrame; const end = start + row.durationFrames;
      const eventId = stableId(`narration:${document.id}:${row.block.id}:${row.map.audio!.narrationAssetId}`);
      resolved.events.push({ eventId, kind: "narration", trackId: dependencies.roles.narrationTrackId, trackRole: "narration", recordRange: { startFrame: start, endFrame: end }, provenance: { documentId: document.id, blockId: row.block.id, sequenceId: null, slotId: null, payloadId: null, overlayEventId: null, sourceId: row.map.audio!.narrationAssetId, originalSourceHash: row.map.audio!.audioHash, deliveredSourceHash: row.map.audio!.audioHash, timingMapHash: row.map.timingHash, compilerVersion: dependencies.compiler.version }, sourceRange: null, sourceTimeMapping: null, preparationBindingHash: null, audio: null });
    }
    const supporting = compileSupportingItems(document, dependencies, resolved.timedRows, resolved.events);
    resolved.events.push(...supporting.events);
    resolved.diagnostics.push(...supporting.diagnostics);
    const supportingItemResults = supporting.items;
    const firstNarration = resolved.timedRows.find((item): item is TimedRow => item.kind === "narration");
    const onlyVisualOnly = resolved.timedRows.length === 1 && resolved.timedRows[0]?.kind === "visual_only" ? resolved.timedRows[0] : null;
    const standaloneDescriptor = onlyVisualOnly?.block.payload.pictureKind === "clip"
      ? dependencies.occurrenceResolutions.find((item) => item.payloadId === onlyVisualOnly.block.payload.payloadId)
      : undefined;
    const durationKind: TimelineManifestV2["durationBasis"]["kind"] = firstNarration ? "narration_spine" : standaloneDescriptor ? "standalone_clip" : "visual_only_duration";
    const effectiveDefaults = document.activeDraft.blocks.some((item) => item.type === "narration" && item.state === "active" && item.primaryVisualSequence?.slots.some((slot) => slot.kind === "content" && slot.payload.kind === "on_camera"))
      ? { ...dependencies.authoringDefaults, presenterStill: effectivePresenterStill(document, dependencies) }
      : dependencies.authoringDefaults;
    const returnResolutions: TimelineManifestV2["composition"]["returns"] = [];
    for (const resolution of resolved.sequenceResolutions.filter((item) => item.relation === "return")) {
      const row = document.activeDraft.blocks.find((item): item is NarrationBlockV2 => item.type === "narration" && item.id === resolution.blockId);
      const returnSlot = row?.primaryVisualSequence?.slots.find((item): item is ReturnSlot => item.kind === "return" && item.id === resolution.returnSlotId);
      const rootEvent = returnSlot ? resolved.events.find((event) => event.provenance.blockId === resolution.blockId && event.provenance.slotId === returnSlot.parentSlotId && (event.kind === "primary_visual" || event.kind === "placeholder")) : undefined;
      if (!rootEvent) {
        resolved.diagnostics.push(diagnostic("SOURCE_MAPPING_MISMATCH", "A return boundary must reveal its existing advancing root event.", entity("slot", resolution.returnSlotId, "composition.returns"), undefined, ["repair_document"]));
        continue;
      }
      returnResolutions.push({ returnSlotId: resolution.returnSlotId!, rootEventId: rootEvent.eventId, recordFrame: resolution.resolvedRecordFrame, emitsNewSourceEvent: false });
    }
    const manifest: TimelineManifestV2 = {
      schemaVersion: "timeline-manifest/v2", id: dependencies.build.manifestId, buildId: dependencies.build.buildId, buildClass: dependencies.build.buildClass,
      document: dependencies.document, compiler: dependencies.compiler, authoringDefaults: effectiveDefaults, timeline: { ...dependencies.timeline, durationFrames: resolved.durationFrames }, tracks: dependencies.tracks, roles: dependencies.roles,
      sources: [...sourcesById.values()].sort((a, b) => compareText(a.id, b.id)), events: [...resolved.events].sort((a, b) => a.recordRange.startFrame - b.recordRange.startFrame || compareText(a.eventId, b.eventId)),
      visualSequenceResolutions: resolved.sequenceResolutions.sort((a, b) => a.resolvedRecordFrame - b.resolvedRecordFrame || compareText(a.sequenceId, b.sequenceId)), supportingItemResults, preparationBindings: dependencies.preparedMedia,
      durationBasis: { kind: durationKind, entityId: resolved.timedRows[0]?.block.id ?? document.id, recordFrames: resolved.durationFrames, sourceRange: durationKind === "standalone_clip" && standaloneDescriptor ? onlyVisualOnly?.block.visualOnlyTiming.selectedSourceRange
        ? { startFrame: onlyVisualOnly.block.visualOnlyTiming.selectedSourceRange.startFrame, endFrame: safe(BigInt(onlyVisualOnly.block.visualOnlyTiming.selectedSourceRange.startFrame) + BigInt(onlyVisualOnly.block.visualOnlyTiming.selectedSourceRange.durationFrames), "standalone selected range end") }
        : { startFrame: standaloneDescriptor.occurrenceSourceInFrame, endFrame: standaloneDescriptor.logicalSourceBounds.endFrame }
        : null, narrationTimingMapHash: firstNarration?.map.timingHash ?? null },
      composition: { topology: "primary_root_child_overlay", primaryRootTrackId: dependencies.roles.primaryRootTrackId, childTrackIds: dependencies.roles.childTrackIds, overlayTrackIds: dependencies.roles.overlayTrackIds, rootContinuous: true, returns: returnResolutions },
      boundaryEvidence: resolved.boundaryEvidence.sort((a, b) => a.resolvedRecordFrame - b.resolvedRecordFrame || compareText(a.entityId, b.entityId)),
    };
    const report = makeReport(resolved.diagnostics, manifest, dependencies, resolved.requirements, manifest.events.map((event) => {
      const blocked = resolved.diagnostics.some((item) => (item.severity === "blocking" || item.severity === "error") && (item.entity.id === event.provenance.blockId || item.entity.id === event.eventId || item.entity.id === event.provenance.slotId));
      const temporaryPresenter = event.kind === "placeholder" && resolved.diagnostics.some((item) => item.code === "TEMPORARY_PRESENTER_STILL" && item.entity.id === event.provenance.slotId);
      const intentionalSlate = event.kind === "placeholder" && event.pictureTreatment?.kind === "slate" && event.pictureTreatment.purpose === "intentional";
      const disposition = blocked ? "blocked" as const : temporaryPresenter ? "manual_completion" as const : event.kind === "placeholder" && !intentionalSlate ? "placeholder" as const : "placed" as const;
      const markerItem = event.marker ? document.activeDraft.supportingItems.find((item) => item.id === event.marker!.supportingItemId) : undefined;
      const slate = event.pictureTreatment?.kind === "slate" ? event.pictureTreatment : null;
      const message = markerItem ? markerItem.content
        : temporaryPresenter ? "Temporary presenter still requires manual replacement when an accepted presenter source is available."
          : event.kind === "placeholder" && intentionalSlate ? `Intentional picture slate: ${slate?.text ?? ""}`
            : event.kind === "placeholder" ? `Blocked ${slate?.purpose === "undefined" ? "undefined visual" : "unresolved visual request"}; the preview slate is explicit and does not make this row build-ready.`
              : "Compiled from frozen source bindings.";
      return { eventId: event.eventId, kind: event.kind, disposition, sourceId: event.provenance.sourceId, trackId: event.trackId, recordRange: event.recordRange, message };
    }), supportingItemResults);
    if (!validateManifest(manifest)) return fail(...schemaDiagnostics(validateManifest.errors, "MANIFEST"));
    if (!validateReport(report)) return fail(...schemaDiagnostics(validateReport.errors, "REPORT"));
    const manifestJson = canonicalJson(manifest); const reportJson = canonicalJson(report);
    return { ok: true, manifest, report, manifestJson, reportJson };
  } catch (error) {
    return fail({ code: "COMPILATION_PRECONDITION_FAILED", message: error instanceof Error ? error.message : String(error) });
  }
}

export function resolveMediaRequirementsV2(documentInput: unknown, input: MediaRequirementsInputV2): MediaRequirementsResultV2 {
  const validation = validateScriptDocumentV2(documentInput);
  if (!validation.valid) return { ok: false, diagnostics: validation.diagnostics.map((item) => ({ code: item.code, message: item.message, jsonPath: item.jsonPath, ...(item.entityId ? { entityId: item.entityId } : {}) })) };
  try {
    const document = documentInput as ScriptDocumentV2;
    const malformedText = malformedFrozenText(document);
    if (malformedText) return { ok: false, diagnostics: [malformedText] };
    const audioBindingProblem = conflictingNarrationAudioBinding(input.timing);
    if (audioBindingProblem) return { ok: false, diagnostics: [audioBindingProblem] };
    for (const descriptor of input.sourceDescriptors) {
      const mappingProblem = sourceMappingProblem(descriptor);
      if (mappingProblem) return { ok: false, diagnostics: [{ code: "SOURCE_MAPPING_MISMATCH", message: mappingProblem, entityId: descriptor.payloadId }] };
    }
    // Build the same temporal plan as compilation; source preparation consumes these exact intervals.
    const synthetic: CompilerDependenciesV2 = {
      schemaVersion: "compiler-dependencies/v2", build: { buildId: document.id, manifestId: document.id, reportId: document.id, buildClass: "preview" },
      document: { documentId: document.id, projectId: document.projectId, revision: 1, liveHeadSequence: document.liveHeadSequence, contentHash: document.liveContentHash, textHash: shaText(document.activeDraft.blocks.filter((item): item is NarrationBlockV2 => item.type === "narration").map((item) => item.text).join("\n")), settingsHash: input.defaults.settingsHash },
      compiler: { version: "compiler/v2", sourceHash: `sha256:${"0".repeat(64)}`, profileHash: `sha256:${"0".repeat(64)}` }, authoringDefaults: input.defaults,
      timeline: { frameRate: input.frameRate, width: 1, height: 1, audioSampleRate: 48000, startFrame: 0, durationFrames: 1 }, tracks: [{ id: "video", kind: "video", index: 1, name: "video" }],
      roles: { primaryRootTrackId: "video", childTrackIds: [], overlayTrackIds: [], presenterTrackId: "video", placeholderTrackId: "video", narrationTrackId: "video", sourceAudioTrackIds: [], markerTrackId: "video" }, narrationTimingMaps: [...input.timing], occurrenceResolutions: [...input.sourceDescriptors], preparedMedia: [], presenterAlignmentResolutions: [],
    };
    if (!validateDependencies(synthetic)) return { ok: false, diagnostics: schemaDiagnostics(validateDependencies.errors, "DEPENDENCIES") };
      const validRows = buildTimedRows(document, synthetic);
      if (validRows.diagnostics.length) return { ok: false, diagnostics: validRows.diagnostics.map((item) => ({ code: item.code, message: item.message, ...(item.entity.id ? { entityId: item.entity.id } : {}) })) };
    const plan = resolvePlan(document, synthetic, false);
    const hardRefusal = plan.diagnostics.find((item) => ["STALE_ANCHOR", "COLLAPSED_BOUNDARY", "SOURCE_MAPPING_MISMATCH", "SOURCE_INSUFFICIENT", "TRACK_ROLE_COLLISION", "MISSING_OCCURRENCE_BINDING"].includes(item.code));
    if (hardRefusal) return { ok: false, diagnostics: [{ code: hardRefusal.code, message: hardRefusal.message, ...(hardRefusal.entity.id ? { entityId: hardRefusal.entity.id } : {}) }] };
    return { ok: true, requirements: plan.requirements, durationFrames: plan.durationFrames };
  } catch (error) {
    return { ok: false, diagnostics: [{ code: "MEDIA_NEEDS_FAILED", message: error instanceof Error ? error.message : String(error) }] };
  }
}
