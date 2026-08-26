import { createHash } from "node:crypto";

import { Ajv2020, type ErrorObject } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";

import buildReportSchema from "../../../contracts/build-report-v1.schema.json" with { type: "json" };
import compilerDependenciesSchema from "../../../contracts/compiler-dependencies-v1.schema.json" with { type: "json" };
import scriptDocumentSchema from "../../../contracts/script-document-v1.schema.json" with { type: "json" };
import timelineManifestSchema from "../../../contracts/timeline-manifest-v1.schema.json" with { type: "json" };
import type {
  AudioEvent,
  AudioSource,
  BuildIssue,
  BuildReportV1,
  CompilerDependenciesV1,
  EventBuildResult,
  HardCutTransition,
  HostVisibilitySpan,
  ManualCompletionItem,
  NarrationBlock,
  PlaceholderEvent,
  RationalRate,
  ScriptDocumentV1,
  TextAnchorRange,
  TimelineManifestV1,
  VisualEvent,
} from "./generated/contracts.js";
import { validateScriptDocument } from "./script-validator.js";

export interface CompileDiagnostic {
  code: string;
  message: string;
  jsonPath?: string;
  entityId?: string;
}

export type CompileResult =
  | { ok: false; diagnostics: CompileDiagnostic[] }
  | {
      ok: true;
      manifest: TimelineManifestV1;
      report: BuildReportV1;
      manifestJson: string;
      reportJson: string;
    };

interface VisualOccurrence {
  event: VisualEvent;
  ownerBlockId: string;
}

interface BlockTiming {
  block: NarrationBlock;
  dependency: CompilerDependenciesV1["narration"][number];
  startFrame: number;
  durationFrames: number;
  endFrame: number;
  resolver?: AnchorResolver;
  failure?: string;
}

interface ResolvedAnchor {
  startFrame: number;
  durationFrames: number;
  precision: "word_start_with_derived_end" | "sentence_start_with_derived_end";
  alignmentVersion: string;
}

type AnchorResolver = (range: TextAnchorRange) => ResolvedAnchor;
type MediaSource = TimelineManifestV1["sources"][number];
type TimelineEvent = TimelineManifestV1["events"][number];
type TimelineMarker = TimelineManifestV1["markers"][number];
type Track = TimelineManifestV1["tracks"][number];
type TimingPrecision = TimelineEvent["timingPrecision"];

const UUID_NAMESPACE = "66fa94c2-6f38-5fc2-8aef-daa876c9f45e";

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(scriptDocumentSchema);
ajv.addSchema(timelineManifestSchema);
ajv.addSchema(buildReportSchema);
const validateDependencies = ajv.compile<CompilerDependenciesV1>(compilerDependenciesSchema);
const validateManifest = ajv.getSchema<TimelineManifestV1>(timelineManifestSchema.$id)!;
const validateReport = ajv.getSchema<BuildReportV1>(buildReportSchema.$id)!;

function checkedInteger(value: number, label: string): bigint {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new RangeError(`${label} must be a nonnegative safe integer`);
  }
  return BigInt(value);
}

function asSafeNumber(value: bigint, label: string): number {
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError(`${label} exceeds JavaScript's safe integer range`);
  }
  return Number(value);
}

export function ceilDivide(numerator: bigint, denominator: bigint): bigint {
  if (numerator < 0n || denominator <= 0n) {
    throw new RangeError("ceilDivide accepts a nonnegative numerator and positive denominator");
  }
  return (numerator + denominator - 1n) / denominator;
}

export function frameAtMilliseconds(milliseconds: number, rate: RationalRate): number {
  const time = checkedInteger(milliseconds, "milliseconds");
  const numerator = checkedInteger(rate.numerator, "frame-rate numerator");
  const denominator = checkedInteger(rate.denominator, "frame-rate denominator");
  if (numerator === 0n || denominator === 0n) throw new RangeError("frame rate must be positive");
  return asSafeNumber(ceilDivide(time * numerator, 1000n * denominator), "compiled frame boundary");
}

export function frameDurationForSamples(
  durationSamples: number,
  sampleRate: number,
  rate: RationalRate,
): number {
  const samples = checkedInteger(durationSamples, "duration samples");
  const samplesPerSecond = checkedInteger(sampleRate, "sample rate");
  const numerator = checkedInteger(rate.numerator, "frame-rate numerator");
  const denominator = checkedInteger(rate.denominator, "frame-rate denominator");
  if (samplesPerSecond === 0n || numerator === 0n || denominator === 0n) {
    throw new RangeError("sample rate and frame rate must be positive");
  }
  return asSafeNumber(
    ceilDivide(samples * numerator, samplesPerSecond * denominator),
    "compiled frame duration",
  );
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => compareText(left, right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON does not allow non-finite numbers");
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return `${JSON.stringify(canonicalize(value), null, 2)}\n`;
}

export function sha256CanonicalJson(value: unknown): string {
  return `sha256:${createHash("sha256").update(canonicalJson(value), "utf8").digest("hex")}`;
}

function sha256Text(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function uuidBytes(value: string): Buffer {
  return Buffer.from(value.replaceAll("-", ""), "hex");
}

function stableUuid(name: string): string {
  const bytes = createHash("sha1").update(uuidBytes(UUID_NAMESPACE)).update(name, "utf8").digest().subarray(0, 16);
  bytes[6] = (bytes[6]! & 0x0f) | 0x50;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function schemaDiagnostics(errors: ErrorObject[] | null | undefined, prefix: string): CompileDiagnostic[] {
  return (errors ?? []).map((error) => ({
    code: `${prefix}_SCHEMA_INVALID`,
    message: `${error.instancePath || "/"}: ${error.message ?? "schema validation failed"}`,
    jsonPath: error.instancePath || "/",
  }));
}

function fail(...diagnostics: CompileDiagnostic[]): CompileResult {
  return { ok: false, diagnostics: diagnostics.sort(compareDiagnostic) };
}

function compareDiagnostic(left: CompileDiagnostic, right: CompileDiagnostic): number {
  return compareText(left.code, right.code) || compareText(left.entityId ?? "", right.entityId ?? "") || compareText(left.message, right.message);
}

export function compileTimeline(documentInput: unknown, dependenciesInput: unknown): CompileResult {
  const documentValidation = validateScriptDocument(documentInput);
  if (!documentValidation.valid) {
    return fail(...documentValidation.diagnostics.map((item) => ({
      code: item.code,
      message: item.message,
      jsonPath: item.jsonPath,
      ...(item.entityId === undefined ? {} : { entityId: item.entityId }),
    })));
  }
  if (!validateDependencies(dependenciesInput)) {
    return fail(...schemaDiagnostics(validateDependencies.errors, "DEPENDENCIES"));
  }

  const document = documentInput as ScriptDocumentV1;
  const dependencies = dependenciesInput;
  const preconditions = validatePreconditions(document, dependencies);
  if (preconditions.length > 0) return fail(...preconditions);

  try {
    return compileValidated(document, dependencies);
  } catch (error) {
    return fail({
      code: "COMPILATION_PRECONDITION_FAILED",
      message: error instanceof Error ? error.message : String(error),
    });
  }
}

function validatePreconditions(document: ScriptDocumentV1, dependencies: CompilerDependenciesV1): CompileDiagnostic[] {
  const diagnostics: CompileDiagnostic[] = [];
  const blocks = [...document.activeDraft.blocks].sort((a, b) => compareText(a.orderKey, b.orderKey));
  const orderKeys = new Set<string>();
  for (const block of blocks) {
    if (orderKeys.has(block.orderKey)) diagnostics.push(diag("ORDER_KEY_DUPLICATE", `Duplicate orderKey ${block.orderKey}.`, block.id));
    orderKeys.add(block.orderKey);
  }

  const activeNarration = blocks.filter((block): block is NarrationBlock => block.type === "narration" && block.state === "active");
  if (activeNarration.length === 0) diagnostics.push(diag("NO_ACTIVE_NARRATION", "The active draft contains no active narration block.", document.id));

  const narrationById = uniqueMap(dependencies.narration, (item) => item.blockId, "NARRATION_DEPENDENCY_DUPLICATE", diagnostics);
  const activeIds = new Set(activeNarration.map((block) => block.id));
  for (const block of activeNarration) {
    const dependency = narrationById.get(block.id);
    if (!dependency) {
      diagnostics.push(diag("NARRATION_DEPENDENCY_MISSING", `Narration dependency is missing for block ${block.id}.`, block.id));
      continue;
    }
    if (dependency.blockRevision !== block.version) diagnostics.push(diag("NARRATION_REVISION_MISMATCH", `Narration dependency revision ${dependency.blockRevision} does not match block revision ${block.version}.`, block.id));
    if (dependency.textHash !== sha256Text(block.text)) diagnostics.push(diag("NARRATION_TEXT_HASH_MISMATCH", `Narration dependency text hash does not match block ${block.id}.`, block.id));
    if (dependency.audio.sampleRate !== dependencies.build.timeline.audioSampleRate) diagnostics.push(diag("NARRATION_SAMPLE_RATE_MISMATCH", `Narration block ${block.id} is not normalized to the build sample rate.`, block.id));
  }
  for (const dependency of dependencies.narration) {
    if (!activeIds.has(dependency.blockId)) diagnostics.push(diag("NARRATION_DEPENDENCY_UNEXPECTED", `Narration dependency ${dependency.blockId} does not identify an active narration block.`, dependency.blockId));
  }

  validateTracks(dependencies, diagnostics);

  const occurrences = visualOccurrences(document);
  const narrationStates = new Map(
    document.activeDraft.blocks
      .filter((block): block is NarrationBlock => block.type === "narration")
      .map((block) => [block.id, block.state]),
  );
  for (const occurrence of occurrences) {
    if (narrationStates.get(occurrence.event.range.blockId) === "excluded") {
      diagnostics.push(diag("ANCHOR_TARGET_EXCLUDED", `Visual event ${occurrence.event.id} targets excluded narration ${occurrence.event.range.blockId}.`, occurrence.event.id));
    }
  }

  const visualById = uniqueMap(dependencies.resolvedVisuals, (item) => item.mediaReferenceId, "VISUAL_DEPENDENCY_DUPLICATE", diagnostics);
  const requiredVisualIds = new Set<string>();
  for (const { event } of occurrences) {
    if (event.status !== "ready" || event.source.kind !== "local_media") continue;
    requiredVisualIds.add(event.source.mediaReferenceId);
    const resolved = visualById.get(event.source.mediaReferenceId);
    if (!resolved) diagnostics.push(diag("VISUAL_DEPENDENCY_MISSING", `Resolved media is missing for visual event ${event.id}.`, event.id));
    else if (resolved.source.kind !== event.source.mediaKind) diagnostics.push(diag("VISUAL_MEDIA_KIND_MISMATCH", `Resolved media kind does not match visual event ${event.id}.`, event.id));
  }
  for (const resolved of dependencies.resolvedVisuals) {
    if (!requiredVisualIds.has(resolved.mediaReferenceId)) diagnostics.push(diag("VISUAL_DEPENDENCY_UNEXPECTED", `Resolved visual ${resolved.mediaReferenceId} is not required by an active ready visual.`, resolved.mediaReferenceId));
  }
  return diagnostics.sort(compareDiagnostic);
}

function validateTracks(dependencies: CompilerDependenciesV1, diagnostics: CompileDiagnostic[]): void {
  const byId = uniqueMap(dependencies.tracks, (track) => track.id, "TRACK_ID_DUPLICATE", diagnostics);
  const kindIndices = new Set<string>();
  for (const track of dependencies.tracks) {
    const key = `${track.kind}:${track.index}`;
    if (kindIndices.has(key)) diagnostics.push(diag("TRACK_INDEX_DUPLICATE", `Duplicate ${track.kind} track index ${track.index}.`, track.id));
    kindIndices.add(key);
  }
  const bindings = [
    ["presenterTrackId", dependencies.roles.presenterTrackId, "video"],
    ["placeholderTrackId", dependencies.roles.placeholderTrackId, "video"],
    ["narrationTrackId", dependencies.roles.narrationTrackId, "audio"],
    ["sourceAudioTrackId", dependencies.roles.sourceAudioTrackId, "audio"],
  ] as const;
  if (new Set(bindings.map(([, id]) => id)).size !== bindings.length) diagnostics.push(diag("TRACK_ROLE_COLLISION", "Track role targets must be pairwise distinct.", dependencies.build.buildId));
  for (const [role, id, kind] of bindings) {
    const track = byId.get(id);
    if (!track) diagnostics.push(diag("TRACK_ROLE_MISSING", `${role} references missing track ${id}.`, id));
    else if (track.kind !== kind) diagnostics.push(diag("TRACK_ROLE_KIND_MISMATCH", `${role} must reference a ${kind} track.`, id));
  }
}

function uniqueMap<T>(items: T[], key: (item: T) => string, code: string, diagnostics: CompileDiagnostic[]): Map<string, T> {
  const result = new Map<string, T>();
  for (const item of items) {
    const id = key(item);
    if (result.has(id)) diagnostics.push(diag(code, `Duplicate dependency identity ${id}.`, id));
    else result.set(id, item);
  }
  return result;
}

function diag(code: string, message: string, entityId: string): CompileDiagnostic {
  return { code, message, entityId };
}

function visualOccurrences(document: ScriptDocumentV1): VisualOccurrence[] {
  const result: VisualOccurrence[] = [];
  for (const block of document.activeDraft.blocks) {
    if (block.type === "narration") {
      for (const event of block.visualEvents) result.push({ event, ownerBlockId: block.id });
    } else if (block.type === "visual") {
      result.push({ event: block.event, ownerBlockId: block.id });
    }
  }
  return result;
}

function compileValidated(document: ScriptDocumentV1, dependencies: CompilerDependenciesV1): CompileResult {
  const blocks = [...document.activeDraft.blocks].sort((a, b) => compareText(a.orderKey, b.orderKey));
  const active = blocks.filter((block): block is NarrationBlock => block.type === "narration" && block.state === "active");
  const dependencyByBlock = new Map(dependencies.narration.map((item) => [item.blockId, item]));
  const occurrences = visualOccurrences(document);
  const occurrencesByTarget = new Map<string, VisualOccurrence[]>();
  for (const occurrence of occurrences) {
    const list = occurrencesByTarget.get(occurrence.event.range.blockId) ?? [];
    list.push(occurrence);
    occurrencesByTarget.set(occurrence.event.range.blockId, list);
  }

  let cursor = dependencies.build.timeline.startFrame;
  const timingByBlock = new Map<string, BlockTiming>();
  for (const block of active) {
    const dependency = dependencyByBlock.get(block.id)!;
    const durationFrames = frameDurationForSamples(dependency.audio.durationSamples, dependency.audio.sampleRate, dependencies.build.timeline.frameRate);
    const timing: BlockTiming = { block, dependency, startFrame: cursor, durationFrames, endFrame: cursor + durationFrames };
    const requiredRanges: TextAnchorRange[] = [
      ...block.hostVisibilitySpans.map((span) => span.range),
      ...(occurrencesByTarget.get(block.id) ?? []).map((item) => item.event.range),
    ];
    if (dependency.status === "failed") timing.failure = dependency.failureReason ?? "Narration generation failed.";
    else {
      try {
        timing.resolver = makeAnchorResolver(timing, requiredRanges, dependencies.build.timeline.frameRate);
        for (const range of requiredRanges) timing.resolver(range);
      } catch (error) {
        timing.failure = error instanceof Error ? error.message : String(error);
      }
    }
    timingByBlock.set(block.id, timing);
    cursor += durationFrames;
  }

  const sources: MediaSource[] = [];
  const events: TimelineEvent[] = [];
  const markers: TimelineMarker[] = [];
  const eventResults: EventBuildResult[] = [];
  const issues: BuildIssue[] = [];
  const manualCompletionItems: ManualCompletionItem[] = [];
  const resolvedVisuals = new Map(dependencies.resolvedVisuals.map((item) => [item.mediaReferenceId, item]));

  let markerCursor = dependencies.build.timeline.startFrame;
  for (const block of blocks) {
    if (block.type === "section") markers.push(makeMarker(document.id, block.id, markerCursor, block.title, `Section: ${block.title}`, "Blue"));
    else if (block.type === "direction" && block.buildBehavior === "timeline_marker") markers.push(makeMarker(document.id, block.id, markerCursor, "Direction", block.text, "Yellow"));
    else if (block.type === "narration" && block.state === "active") markerCursor = timingByBlock.get(block.id)!.endFrame;
  }

  for (const timing of timingByBlock.values()) {
    compileNarration(timing, document, dependencies, sources, events, eventResults);
    const targetOccurrences = occurrencesByTarget.get(timing.block.id) ?? [];
    if (timing.failure) {
      compileTimingFailure(timing, targetOccurrences, document, dependencies, sources, events, eventResults, issues, manualCompletionItems);
      continue;
    }
    for (const span of timing.block.hostVisibilitySpans) {
      if (span.state === "on_camera") compilePresenter(span, timing, document, dependencies, sources, events, eventResults, issues, manualCompletionItems);
    }
    for (const occurrence of targetOccurrences) {
      compileVisual(occurrence, timing, document, dependencies, resolvedVisuals, sources, events, eventResults, issues, manualCompletionItems);
    }
  }

  issues.push(makeIssue("TEMPORARY_NARRATION", "warning", "Temporary synthetic narration remains in this build.", "build", dependencies.build.buildId));
  sortAndValidateEvents(events, dependencies.tracks);
  deduplicateSources(sources);
  const transitions = buildHardCuts(events);
  sources.sort((a, b) => compareText(a.id, b.id));
  markers.sort((a, b) => (("frame" in a ? a.frame : Number.MAX_SAFE_INTEGER) - ("frame" in b ? b.frame : Number.MAX_SAFE_INTEGER)) || compareText(a.id, b.id));
  eventResults.sort((a, b) => a.recordRange.startFrame - b.recordRange.startFrame || compareText(a.eventId, b.eventId));
  issues.sort((a, b) => compareText(a.id, b.id));
  manualCompletionItems.sort((a, b) => compareText(a.id, b.id));

  const sourceDocument = {
    documentId: document.id,
    projectId: document.projectId,
    liveHeadSequence: document.liveHeadSequence,
    contentHash: document.liveContentHash,
  };
  const timeline = { ...dependencies.build.timeline, durationFrames: cursor - dependencies.build.timeline.startFrame };
  const manifest: TimelineManifestV1 = {
    schemaVersion: "timeline-manifest/v1",
    id: dependencies.build.manifestId,
    buildId: dependencies.build.buildId,
    sourceDocument,
    timeline,
    tracks: sortTracks(dependencies.tracks),
    sources,
    events,
    transitions,
    markers,
  };
  assertSchema(validateManifest(manifest) as boolean, validateManifest.errors, "compiler emitted an invalid TimelineManifest");
  const blocking = issues.some((issue) => issue.severity === "blocking" || issue.severity === "error");
  const warnings = issues.some((issue) => issue.severity === "warning");
  const report: BuildReportV1 = {
    schemaVersion: "build-report/v1",
    id: dependencies.build.reportId,
    buildId: dependencies.build.buildId,
    buildClass: dependencies.build.buildClass,
    status: blocking ? "blocked" : warnings ? "ready_with_warnings" : "ready",
    temporaryNarration: true,
    sourceDocument,
    manifest: { id: manifest.id, contentHash: sha256CanonicalJson(manifest) },
    timeline,
    summary: {
      sourceCount: sources.length,
      eventCount: events.length,
      markerCount: markers.length,
      placedCount: eventResults.filter((item) => item.disposition === "placed").length,
      placeholderCount: eventResults.filter((item) => item.disposition === "placeholder").length,
      manualCompletionCount: manualCompletionItems.length,
      warningCount: issues.filter((item) => item.severity === "warning").length,
      errorCount: issues.filter((item) => item.severity === "error" || item.severity === "blocking").length,
    },
    eventResults,
    issues,
    manualCompletionItems,
  };
  assertSchema(validateReport(report) as boolean, validateReport.errors, "compiler emitted an invalid BuildReport");
  return { ok: true, manifest, report, manifestJson: canonicalJson(manifest), reportJson: canonicalJson(report) };
}

function makeAnchorResolver(timing: BlockTiming, requiredRanges: TextAnchorRange[], rate: RationalRate): AnchorResolver {
  const { block, dependency } = timing;
  const isAtOrAfterAudioEnd = (timeMs: number): boolean =>
    BigInt(timeMs) * BigInt(dependency.audio.sampleRate) >=
    BigInt(dependency.audio.durationSamples) * 1000n;
  if (dependency.timing.precision === "none") throw new Error(`Narration block ${block.id} has no usable text alignment.`);
  if (dependency.timing.precision === "word_start_with_derived_end") {
    const marks = dependency.timing.marks.filter((mark) => mark.kind === "word");
    if (marks.length !== block.tokens.length) throw new Error(`Narration block ${block.id} does not have one word mark per token.`);
    const timeByToken = new Map<string, [number, number | undefined]>();
    let priorTime = -1;
    let priorEnd = -1;
    for (const [index, token] of block.tokens.entries()) {
      const mark = marks[index]!;
      if (mark.timeMs <= priorTime || mark.startUtf16 < priorEnd || mark.endUtf16 <= mark.startUtf16 || mark.startUtf16 !== token.startOffset || mark.endUtf16 !== token.endOffset || isAtOrAfterAudioEnd(mark.timeMs)) {
        throw new Error(`Narration block ${block.id} has malformed or token-mismatched word marks.`);
      }
      const nextStart = marks[index + 1]?.timeMs;
      if (nextStart !== undefined && nextStart <= mark.timeMs) throw new Error(`Narration block ${block.id} has nonmonotonic word marks.`);
      timeByToken.set(token.id, [mark.timeMs, nextStart]);
      priorTime = mark.timeMs;
      priorEnd = mark.endUtf16;
    }
    return (range) => resolveRange(block, range, timeByToken, timing.startFrame, timing.endFrame, rate, "word_start_with_derived_end", dependency.timing.alignmentVersion);
  }

  const marks = dependency.timing.marks.filter((mark) => mark.kind === "sentence");
  if (marks.length === 0) throw new Error(`Narration block ${block.id} has no sentence marks.`);
  let priorTime = -1;
  let priorEnd = -1;
  const sentenceTokenRanges: Array<{ first: number; last: number; startMs: number; endMs?: number }> = [];
  for (const [index, mark] of marks.entries()) {
    if (mark.timeMs <= priorTime || mark.startUtf16 < priorEnd || mark.endUtf16 <= mark.startUtf16 || mark.endUtf16 > block.text.length || isAtOrAfterAudioEnd(mark.timeMs)) {
      throw new Error(`Narration block ${block.id} has malformed sentence marks.`);
    }
    const intersected = block.tokens.map((token, tokenIndex) => ({ token, tokenIndex })).filter(({ token }) => token.endOffset > mark.startUtf16 && token.startOffset < mark.endUtf16);
    if (intersected.some(({ token }) => token.startOffset < mark.startUtf16 || token.endOffset > mark.endUtf16)) throw new Error(`Narration block ${block.id} has a sentence mark that cuts through a token.`);
    const covered = intersected;
    if (covered.length === 0) throw new Error(`Narration block ${block.id} has a sentence mark with no complete token coverage.`);
    const first = covered[0]!.tokenIndex;
    const last = covered.at(-1)!.tokenIndex;
    if (last - first + 1 !== covered.length) throw new Error(`Narration block ${block.id} has noncontiguous sentence token coverage.`);
    sentenceTokenRanges.push({ first, last, startMs: mark.timeMs, ...(marks[index + 1] === undefined ? {} : { endMs: marks[index + 1]!.timeMs }) });
    priorTime = mark.timeMs;
    priorEnd = mark.endUtf16;
  }
  return (range) => {
    const [first, last] = selectedTokenIndices(block, range);
    const covered = sentenceTokenRanges.filter((item) => item.first >= first && item.last <= last);
    if (covered.length === 0 || covered[0]!.first !== first || covered.at(-1)!.last !== last) throw new Error(`Anchor ${range.startTokenId}-${range.endTokenId} is not complete sentence coverage.`);
    for (let index = 1; index < covered.length; index += 1) if (covered[index]!.first !== covered[index - 1]!.last + 1) throw new Error(`Anchor ${range.startTokenId}-${range.endTokenId} crosses noncontiguous sentence marks.`);
    return frameRange(timing.startFrame, timing.endFrame, covered[0]!.startMs, covered.at(-1)!.endMs, rate, "sentence_start_with_derived_end", dependency.timing.alignmentVersion);
  };
}

function selectedTokenIndices(block: NarrationBlock, range: TextAnchorRange): [number, number] {
  let first = block.tokens.findIndex((token) => token.id === range.startTokenId);
  let last = block.tokens.findIndex((token) => token.id === range.endTokenId);
  if (range.startAffinity === "after") first += 1;
  if (range.endAffinity === "before") last -= 1;
  if (first < 0 || last >= block.tokens.length || first > last) throw new Error(`Anchor ${range.startTokenId}-${range.endTokenId} resolves to an empty token interval.`);
  return [first, last];
}

function resolveRange(
  block: NarrationBlock,
  range: TextAnchorRange,
  timeByToken: Map<string, [number, number | undefined]>,
  blockStart: number,
  blockEnd: number,
  rate: RationalRate,
  precision: ResolvedAnchor["precision"],
  alignmentVersion: string,
): ResolvedAnchor {
  const [first, last] = selectedTokenIndices(block, range);
  const start = timeByToken.get(block.tokens[first]!.id);
  const end = timeByToken.get(block.tokens[last]!.id);
  if (!start || !end) throw new Error(`Anchor ${range.startTokenId}-${range.endTokenId} has no timing marks.`);
  return frameRange(blockStart, blockEnd, start[0], end[1], rate, precision, alignmentVersion);
}

function frameRange(blockStart: number, blockEnd: number, startMs: number, endMs: number | undefined, rate: RationalRate, precision: ResolvedAnchor["precision"], alignmentVersion: string): ResolvedAnchor {
  const startFrame = blockStart + frameAtMilliseconds(startMs, rate);
  const endFrame = endMs === undefined ? blockEnd : blockStart + frameAtMilliseconds(endMs, rate);
  if (endFrame <= startFrame) throw new Error("An authored anchor collapses to zero frames at the build frame rate.");
  return { startFrame, durationFrames: endFrame - startFrame, precision, alignmentVersion };
}

function compileNarration(
  timing: BlockTiming,
  document: ScriptDocumentV1,
  dependencies: CompilerDependenciesV1,
  sources: MediaSource[],
  events: TimelineEvent[],
  results: EventBuildResult[],
): void {
  const sourceId = stableUuid(`narration-source:${timing.dependency.assetId}`);
  const eventId = stableUuid(`narration-event:${timing.block.id}`);
  const precision: TimingPrecision = timing.failure ? "unavailable" : "frame";
  const source: AudioSource = {
    id: sourceId,
    kind: "audio",
    path: timing.dependency.audio.locator,
    contentHash: timing.dependency.audioHash,
    durationFrames: timing.durationFrames,
    sampleRate: timing.dependency.audio.sampleRate,
    channels: timing.dependency.audio.channels,
  };
  const event: AudioEvent = {
    id: eventId,
    kind: "audio",
    sourceId,
    trackId: dependencies.roles.narrationTrackId,
    trackKind: "audio",
    recordRange: { startFrame: timing.startFrame, durationFrames: timing.durationFrames },
    sourceRange: { startFrame: 0, durationFrames: timing.durationFrames },
    timingPrecision: precision,
    alignmentVersion: timing.dependency.timing.alignmentVersion,
    provenance: { documentId: document.id, blockId: timing.block.id, authoringKind: "narration_block", authoringId: timing.block.id },
  };
  sources.push(source);
  events.push(event);
  results.push({
    eventId,
    disposition: "placed",
    sourceId,
    trackId: event.trackId,
    trackKind: "audio",
    recordRange: event.recordRange,
    message: `Narration "${timing.block.text}" frames ${timing.startFrame}-${timing.endFrame}; precision=${precision}; alignment=${timing.dependency.timing.alignmentVersion}.`,
  });
}

function compileTimingFailure(
  timing: BlockTiming,
  occurrences: VisualOccurrence[],
  document: ScriptDocumentV1,
  dependencies: CompilerDependenciesV1,
  sources: MediaSource[],
  events: TimelineEvent[],
  results: EventBuildResult[],
  issues: BuildIssue[],
  manual: ManualCompletionItem[],
): void {
  const eventId = stableUuid(`timing-placeholder-event:${timing.block.id}`);
  const sourceId = stableUuid(`placeholder-source:timing:${timing.block.id}`);
  const reason = `Narration block ${timing.block.id} has no usable text alignment.`;
  const range = { startFrame: timing.startFrame, durationFrames: timing.durationFrames };
  sources.push({ id: sourceId, kind: "placeholder", label: `TIMING UNAVAILABLE: ${timing.block.text}`, reason });
  events.push({ id: eventId, kind: "placeholder", sourceId, trackId: dependencies.roles.placeholderTrackId, trackKind: "video", recordRange: range, timingPrecision: "unavailable", alignmentVersion: timing.dependency.timing.alignmentVersion, provenance: { documentId: document.id, blockId: timing.block.id, authoringKind: "narration_block", authoringId: timing.block.id } });
  results.push({ eventId, disposition: "placeholder", sourceId, trackId: dependencies.roles.placeholderTrackId, trackKind: "video", recordRange: range, message: reason });
  issues.push(makeIssue("NARRATION_TIMING_UNAVAILABLE", "blocking", `${reason} ${timing.failure}`, "block", timing.block.id));
  manual.push(makeManual("PROVIDE_ALIGNED_NARRATION", "Provide usable aligned narration timing.", "Regenerate or provide aligned narration for this block.", "block", timing.block.id));
  for (const span of timing.block.hostVisibilitySpans) if (span.state === "on_camera") issues.push(makeIssue("ANCHORED_EVENT_SUPPRESSED", "blocking", `Presenter span ${span.id} was suppressed because narration timing is unavailable.`, "block", span.id));
  for (const occurrence of occurrences) issues.push(makeIssue("ANCHORED_EVENT_SUPPRESSED", "blocking", `Visual event ${occurrence.event.id} was suppressed because narration timing is unavailable.`, "visual_event", occurrence.event.id));
}

function compilePresenter(
  span: HostVisibilitySpan,
  timing: BlockTiming,
  document: ScriptDocumentV1,
  dependencies: CompilerDependenciesV1,
  sources: MediaSource[],
  events: TimelineEvent[],
  results: EventBuildResult[],
  issues: BuildIssue[],
  manual: ManualCompletionItem[],
): void {
  const resolved = timing.resolver!(span.range);
  const eventId = stableUuid(`presenter-event:${span.id}`);
  const sourceId = stableUuid(`placeholder-source:presenter:${span.id}`);
  const reason = `Presenter/A-roll footage is unresolved for on-camera span ${span.id}.`;
  sources.push({ id: sourceId, kind: "placeholder", label: `PRESENTER: ${span.range.quotedText}`, reason });
  const event: PlaceholderEvent = { id: eventId, kind: "placeholder", sourceId, trackId: dependencies.roles.presenterTrackId, trackKind: "video", recordRange: rangeOf(resolved), timingPrecision: resolved.precision, alignmentVersion: resolved.alignmentVersion, provenance: { documentId: document.id, blockId: timing.block.id, authoringKind: "narration_block", authoringId: span.id } };
  events.push(event);
  results.push(resultFor(event, "placeholder", reason));
  issues.push(makeIssue("PRESENTER_FOOTAGE_UNRESOLVED", "warning", reason, "timeline_event", eventId));
  manual.push(makeManual("REPLACE_PRESENTER_PLACEHOLDER", reason, "Replace this placeholder with presenter/A-roll footage.", "timeline_event", eventId));
}

function compileVisual(
  occurrence: VisualOccurrence,
  timing: BlockTiming,
  document: ScriptDocumentV1,
  dependencies: CompilerDependenciesV1,
  resolvedVisuals: Map<string, CompilerDependenciesV1["resolvedVisuals"][number]>,
  sources: MediaSource[],
  events: TimelineEvent[],
  results: EventBuildResult[],
  issues: BuildIssue[],
  manual: ManualCompletionItem[],
): void {
  const { event: authored } = occurrence;
  const resolved = timing.resolver!(authored.range);
  if (authored.status !== "ready") {
    const failed = authored.status === "failed";
    const description = authored.source.kind === "local_media" ? authored.source.label : authored.source.description;
    const sourceId = stableUuid(`placeholder-source:visual:${authored.id}`);
    const reason = failed ? `Authored visual event ${authored.id} has status failed.` : `Authored visual event ${authored.id} is unresolved.`;
    sources.push({ id: sourceId, kind: "placeholder", label: `${failed ? "FAILED VISUAL" : "UNRESOLVED VISUAL"}: ${description}`, reason });
    const event: PlaceholderEvent = { id: authored.id, kind: "placeholder", sourceId, trackId: dependencies.roles.placeholderTrackId, trackKind: "video", recordRange: rangeOf(resolved), timingPrecision: resolved.precision, alignmentVersion: resolved.alignmentVersion, provenance: { documentId: document.id, blockId: occurrence.ownerBlockId, authoringKind: "visual_event", authoringId: authored.id } };
    events.push(event);
    results.push(resultFor(event, "placeholder", reason));
    issues.push(makeIssue(failed ? "VISUAL_FAILED" : "VISUAL_UNRESOLVED", "warning", reason, "visual_event", authored.id));
    manual.push(makeManual("RESOLVE_OR_REPLACE_VISUAL", reason, "Resolve or replace this authored visual.", "visual_event", authored.id));
    return;
  }
  if (authored.source.kind !== "local_media") throw new Error(`Ready visual event ${authored.id} does not identify local media.`);
  const dependency = resolvedVisuals.get(authored.source.mediaReferenceId)!;
  const videoTrack = dependencies.tracks.find((track) => track.kind === "video" && track.index === authored.layer);
  if (!videoTrack) throw new Error(`Visual event ${authored.id} requires missing video layer ${authored.layer}.`);
  sources.push(dependency.source);
  const provenance = { documentId: document.id, blockId: occurrence.ownerBlockId, authoringKind: "visual_event" as const, authoringId: authored.id };
  if (dependency.source.kind === "still") {
    const event: TimelineEvent = { id: authored.id, kind: "still", sourceId: dependency.source.id, trackId: videoTrack.id, trackKind: "video", recordRange: rangeOf(resolved), timingPrecision: resolved.precision, alignmentVersion: resolved.alignmentVersion, provenance };
    events.push(event);
    results.push(resultFor(event, "placed", `Placed visual "${authored.source.label}".`));
    return;
  }
  const sourceStart = dependency.sourceStartFrame!;
  if (!sameRate(dependency.source.frameRate, dependencies.build.timeline.frameRate)) throw new Error(`Video source for ${authored.id} requires unsupported retiming.`);
  if (sourceStart + resolved.durationFrames > dependency.source.durationFrames) throw new Error(`Video source for ${authored.id} is too short for its authored range.`);
  const event: TimelineEvent = { id: authored.id, kind: "video", sourceId: dependency.source.id, trackId: videoTrack.id, trackKind: "video", recordRange: rangeOf(resolved), sourceRange: { startFrame: sourceStart, durationFrames: resolved.durationFrames }, timingPrecision: resolved.precision, alignmentVersion: resolved.alignmentVersion, provenance };
  events.push(event);
  results.push(resultFor(event, "placed", `Placed visual "${authored.source.label}".`));
  if (authored.audioPolicy === "use_source") {
    if (!dependency.sourceAudio) throw new Error(`Visual event ${authored.id} requests source audio but none was resolved.`);
    if (dependency.sourceAudio.sourceStartFrame + resolved.durationFrames > dependency.sourceAudio.source.durationFrames) throw new Error(`Source audio for ${authored.id} is too short for its authored range.`);
    sources.push(dependency.sourceAudio.source);
    const audioEvent: AudioEvent = { id: stableUuid(`source-audio-event:${authored.id}`), kind: "audio", sourceId: dependency.sourceAudio.source.id, trackId: dependencies.roles.sourceAudioTrackId, trackKind: "audio", recordRange: rangeOf(resolved), sourceRange: { startFrame: dependency.sourceAudio.sourceStartFrame, durationFrames: resolved.durationFrames }, timingPrecision: resolved.precision, alignmentVersion: resolved.alignmentVersion, provenance };
    events.push(audioEvent);
    results.push(resultFor(audioEvent, "placed", `Placed source audio for visual "${authored.source.label}".`));
  }
}

function sameRate(left: RationalRate, right: RationalRate): boolean {
  return BigInt(left.numerator) * BigInt(right.denominator) === BigInt(right.numerator) * BigInt(left.denominator);
}

function rangeOf(resolved: ResolvedAnchor): { startFrame: number; durationFrames: number } {
  return { startFrame: resolved.startFrame, durationFrames: resolved.durationFrames };
}

function resultFor(event: TimelineEvent, disposition: EventBuildResult["disposition"], message: string): EventBuildResult {
  return { eventId: event.id, disposition, sourceId: event.sourceId, trackId: event.trackId, trackKind: event.trackKind, recordRange: event.recordRange, message };
}

function makeMarker(documentId: string, blockId: string, frame: number, name: string, note: string, color: string): TimelineMarker {
  return { id: stableUuid(`marker:${blockId}`), state: "placed", frame, name, note, color, provenance: { documentId, blockId, authoringKind: "script_marker", authoringId: blockId } };
}

function makeIssue(code: string, severity: BuildIssue["severity"], message: string, kind: BuildIssue["entity"]["kind"], id: string): BuildIssue {
  return { id: stableUuid(`issue:${code}:${kind}:${id}`), severity, code, message, entity: { kind, id } };
}

function makeManual(code: string, description: string, action: string, kind: ManualCompletionItem["entity"]["kind"], id: string): ManualCompletionItem {
  return { id: stableUuid(`manual:${code}:${kind}:${id}`), code, description, action, entity: { kind, id } };
}

function sortTracks(tracks: Track[]): TimelineManifestV1["tracks"] {
  const kindRank = { video: 0, audio: 1, subtitle: 2 } as const;
  return [...tracks].sort((a, b) => kindRank[a.kind] - kindRank[b.kind] || a.index - b.index || compareText(a.id, b.id)) as TimelineManifestV1["tracks"];
}

function sortAndValidateEvents(events: TimelineEvent[], tracks: Track[]): void {
  const trackPosition = new Map(sortTracks(tracks).map((track, index) => [track.id, index]));
  events.sort((a, b) => a.recordRange.startFrame - b.recordRange.startFrame || (trackPosition.get(a.trackId)! - trackPosition.get(b.trackId)!) || compareText(a.id, b.id));
  const lastEnd = new Map<string, number>();
  const eventIds = new Set<string>();
  for (const event of events) {
    if (eventIds.has(event.id)) throw new Error(`Timeline event ID ${event.id} is duplicated.`);
    eventIds.add(event.id);
    const priorEnd = lastEnd.get(event.trackId);
    if (priorEnd !== undefined && event.recordRange.startFrame < priorEnd) throw new Error(`Timeline events overlap on track ${event.trackId}.`);
    lastEnd.set(event.trackId, event.recordRange.startFrame + event.recordRange.durationFrames);
  }
}

function deduplicateSources(sources: MediaSource[]): void {
  const byId = new Map<string, MediaSource>();
  for (const source of sources) {
    const prior = byId.get(source.id);
    if (prior && canonicalJson(prior) !== canonicalJson(source)) throw new Error(`Media source ID ${source.id} resolves to conflicting records.`);
    byId.set(source.id, source);
  }
  sources.splice(0, sources.length, ...byId.values());
}

function buildHardCuts(events: TimelineEvent[]): HardCutTransition[] {
  const byTrack = new Map<string, TimelineEvent[]>();
  for (const event of events) {
    if (event.trackKind !== "video") continue;
    const list = byTrack.get(event.trackId) ?? [];
    list.push(event);
    byTrack.set(event.trackId, list);
  }
  const transitions: HardCutTransition[] = [];
  for (const [trackId, trackEvents] of byTrack) {
    trackEvents.sort((a, b) => a.recordRange.startFrame - b.recordRange.startFrame || compareText(a.id, b.id));
    for (let index = 1; index < trackEvents.length; index += 1) {
      const from = trackEvents[index - 1]!;
      const to = trackEvents[index]!;
      const boundary = from.recordRange.startFrame + from.recordRange.durationFrames;
      if (boundary === to.recordRange.startFrame) transitions.push({ id: stableUuid(`hard-cut:${trackId}:${from.id}:${to.id}:${boundary}`), kind: "hard_cut", fromEventId: from.id, toEventId: to.id, atFrame: boundary, durationFrames: 0 });
    }
  }
  return transitions.sort((a, b) => a.atFrame - b.atFrame || compareText(a.id, b.id));
}

function assertSchema(valid: boolean, errors: ErrorObject[] | null | undefined, message: string): asserts valid {
  if (!valid) throw new Error(`${message}: ${JSON.stringify(errors ?? [])}`);
}
