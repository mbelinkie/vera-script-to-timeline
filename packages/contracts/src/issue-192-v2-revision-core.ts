/** Explicit pure commands only; #192/#190 authenticate native/media/provider facts. */
import { createHash } from "node:crypto";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { compileTimelineV2 } from "./compiler-core-v2.js";
import { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { applyAcceptedOmissionV2, type AcceptedOmissionV2 } from "./issue-189-v2-omission.js";
import { finalizeReplacementV2, type RowHandoffV2, type RowRequestV2 } from "./issue-189-v2-replacement.js";
import type { CompilerDependenciesV2, OccurrenceMediaResolutionV2, PreparedMediaBindingV1, ScriptDocumentV2, TimelineManifestV2, TimelineEventV2 } from "./generated/contracts-v2.js";

export interface RevisionCommandsV2 {
  boundary: {
    kind: "move_word_boundary"; blockId: string; boundaryOwnerId: string;
    tokenId: string; affinity: "before" | "after"; expectedSequenceVersion: number;
  } | null;
  trim: {
    blockId: string; expectedBlockVersion: number;
    expectedSelectedRange: { startFrame: number; durationFrames: number };
    durationFrames: number;
  } | null;
  omission: AcceptedOmissionV2 | null;
}
export interface RevisionRequestV2 {
  commands: RevisionCommandsV2;
  preparedMedia: PreparedMediaBindingV1[];
  handoff: RowHandoffV2 | null;
}
export interface RevisionDecisionV2 {
  schemaVersion: "issue-202-v2-decision/v1";
  proposalHash: string;
  historyHash: string;
  outcome: "accept" | "reject";
}
export interface RevisionComparisonV2 {
  label: string;
  before: unknown;
  after: unknown;
}
const equal = (a: unknown, b: unknown) => canonicalJson(a) === canonicalJson(b);
function fact(value: boolean, reason: string): asserts value { if (!value) throw new Error(reason); }
function keys(value: object, expected: string) {
  fact(value !== null && typeof value === "object" && !Array.isArray(value) &&
    equal(Object.keys(value).sort(), expected.split(" ").sort()), "unsupported pure input fields");
}
function next(value: number) {
  fact(Number.isSafeInteger(value) && value >= 0 && Number.isSafeInteger(value + 1), "unsafe revision increment");
  return value + 1;
}
const textHash = (s: string) => `sha256:${createHash("sha256").update(s).digest("hex")}`;
function stamp(document: ScriptDocumentV2, prior: ScriptDocumentV2) {
  document.liveHeadSequence = next(prior.liveHeadSequence);
  document.liveStateVector = "";
  document.liveContentHash = sha256CanonicalJson(Object.fromEntries(Object.entries(document).filter(([key]) => key !== "liveContentHash")));
}
function ready(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2) {
  const compiled = compileTimelineV2(document, dependencies);
  if (!compiled.ok) throw new Error(`pure revision compile refused: ${canonicalJson(compiled.diagnostics.map((d) => d.code))}`);
  if (compiled.report.status !== "ready") throw new Error(`pure revision compile refused: ${canonicalJson(compiled.report.diagnostics.map((d) => d.code))}`);
  return compiled;
}

/** Bind #191 to these inputs after preparing media for the actual fresh row duration. */
export function prepareRevisionInputsV2(
  input: ScriptDocumentV2, prior: CompilerDependenciesV2,
  commands: RevisionCommandsV2, preparedMedia: PreparedMediaBindingV1[],
) {
  fact(validateScriptDocumentV2(input).valid, "invalid baseline document");
  ready(input, prior);
  keys(commands, "boundary trim omission");
  fact(commands.boundary !== null || commands.trim !== null || commands.omission !== null, "empty revision");
  fact(Array.isArray(preparedMedia), "preparation replacements must be an array");
  let document = structuredClone(input);
  const dependencies = structuredClone(prior);
  const affected = new Set<string>();
  if (commands.boundary !== null) {
    const command = commands.boundary;
    keys(command, "kind blockId boundaryOwnerId tokenId affinity expectedSequenceVersion");
    fact(command.kind === "move_word_boundary" && (command.affinity === "before" || command.affinity === "after") &&
      Number.isSafeInteger(command.expectedSequenceVersion), "invalid boundary command");
    const { expectedSequenceVersion, ...edit } = command;
    const result = applyVisualSequenceEditV2(document, expectedSequenceVersion, edit);
    fact(result.ok, `exact boundary command refused: ${canonicalJson(result.diagnostics)}`);
    document = result.document;
    affected.add(command.blockId);
  }
  if (commands.trim !== null) {
    const trim = commands.trim;
    keys(trim, "blockId expectedBlockVersion expectedSelectedRange durationFrames");
    keys(trim.expectedSelectedRange, "startFrame durationFrames");
    const block = document.activeDraft.blocks.find((b) => b.id === trim.blockId);
    fact(block?.type === "visual_only" && block.payload.kind === "visual" && block.payload.pictureKind === "clip" &&
      (block.payload.audioPolicy === "full" || block.payload.audioPolicy === "quiet"), "linked standalone AV clip required");
    fact(block.version === trim.expectedBlockVersion && equal(block.visualOnlyTiming.selectedSourceRange, trim.expectedSelectedRange), "stale selected source/block version");
    fact(block.visualOnlyTiming.durationOverrideMs === undefined && Number.isSafeInteger(trim.durationFrames) &&
      trim.durationFrames > 0 && trim.durationFrames < trim.expectedSelectedRange.durationFrames &&
      Number.isSafeInteger(trim.expectedSelectedRange.startFrame + trim.durationFrames), "end trim must shorten an exact selected range");
    const payloadId = block.payload.payloadId;
    const descriptors = dependencies.occurrenceResolutions.filter((d) => d.payloadId === payloadId);
    fact(descriptors.length === 1, "ambiguous trim occurrence");
    const descriptor = descriptors[0]!;
    fact(descriptor.owner.kind === "visual_only_block" && descriptor.owner.blockId === block.id &&
      equal(descriptor.selectedSourceRange, { startFrame: trim.expectedSelectedRange.startFrame,
        endFrame: trim.expectedSelectedRange.startFrame + trim.expectedSelectedRange.durationFrames }), "trim occurrence owner/range differs");
    block.visualOnlyTiming.selectedSourceRange = { startFrame: trim.expectedSelectedRange.startFrame, durationFrames: trim.durationFrames };
    block.version = next(block.version);
    descriptor.selectedSourceRange = { startFrame: trim.expectedSelectedRange.startFrame, endFrame: trim.expectedSelectedRange.startFrame + trim.durationFrames };
    affected.add(block.id);
  }
  if (commands.boundary !== null || commands.trim !== null) stamp(document, input);
  let regeneration: RowRequestV2 | null = null;
  if (commands.omission !== null) {
    const omission = applyAcceptedOmissionV2(document, commands.omission);
    document = omission.document;
    regeneration = omission.regeneration;
    affected.add(commands.omission.blockId);
  }
  fact(validateScriptDocumentV2(document).valid, "invalid staged revision");
  const affectedOccurrences = dependencies.occurrenceResolutions.filter((d) => {
    const owner = d.owner;
    if (d.preparedMediaRequirementKey === null) return false;
    if (owner.kind === "visual_only_block" || owner.kind === "overlay_event") return affected.has(owner.blockId);
    return document.activeDraft.blocks.some((b) => b.type === "narration" && affected.has(b.id) && b.primaryVisualSequence?.id === owner.sequenceId);
  });
  // A preparation's requirementKey is the identity of its inputs (requestedRange included), so an honest
  // replacement carries its OWN key. It is matched to exactly one affected occurrence by what the occurrence
  // pins (original source, profile, rate, authorization, mode) and then adopted, along with its key.
  const resolved = new Set<OccurrenceMediaResolutionV2>();
  for (const replacement of preparedMedia) {
    const priorFor = (d: OccurrenceMediaResolutionV2) => dependencies.preparedMedia.find((b) => b.requirementKey === d.preparedMediaRequirementKey);
    const matching = affectedOccurrences.filter((d) => d.mediaReferenceId === replacement.originalSource.mediaReferenceId &&
      equal(priorFor(d)?.originalSource, replacement.originalSource));
    fact(matching.length === 1 && !resolved.has(matching[0]!), "unrelated/duplicate preparation replacement");
    const old = priorFor(matching[0]!);
    fact(old !== undefined, "ambiguous prior preparation binding");
    fact(equal(old.profile, replacement.profile) && equal(old.targetRate, replacement.targetRate) &&
      old.authorizationReference === replacement.authorizationReference && old.mode === replacement.mode,
      "preparation source/profile/authorization changed");
    const occurrence = matching[0]!;
    resolved.add(occurrence);
    const oldKey = occurrence.preparedMediaRequirementKey;
    const oldIndex = dependencies.preparedMedia.findIndex((b) => b.requirementKey === oldKey);
    fact(replacement.requirementKey === oldKey || !dependencies.preparedMedia.some((b) => b.requirementKey === replacement.requirementKey),
      "replacement preparation key duplicates an existing binding");
    occurrence.preparedMediaRequirementKey = replacement.requirementKey;
    const shared = dependencies.occurrenceResolutions.some((d) => d !== occurrence && d.preparedMediaRequirementKey === oldKey);
    if (shared) dependencies.preparedMedia.push(structuredClone(replacement));
    else dependencies.preparedMedia[oldIndex] = structuredClone(replacement);
  }
  return { document, dependencies, regeneration };
}

function bindRevision(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, request: RevisionRequestV2) {
  dependencies.document = { ...dependencies.document, revision: next(dependencies.document.revision),
    contentHash: document.liveContentHash, liveHeadSequence: document.liveHeadSequence,
    textHash: textHash(document.activeDraft.blocks.filter((b) => b.type === "narration").map((b) => b.text).join("\n")) };
  const seed = sha256CanonicalJson({ document, dependencies, request });
  const id = (suffix: string) => {
    const h = createHash("sha256").update(`${seed}:${suffix}`).digest("hex");
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-8${h.slice(17, 20)}-${h.slice(20, 32)}`;
  };
  dependencies.build = { ...dependencies.build, buildId: id("build"), manifestId: id("manifest"), reportId: id("report") };
}
function eventImpact(event: TimelineEventV2 | undefined) {
  if (!event) return null;
  return { kind: event.kind, blockId: event.provenance.blockId, slotId: event.provenance.slotId,
    record: event.recordRange, source: event.sourceRange, media: event.provenance.deliveredSourceHash,
    timing: event.provenance.timingMapHash, audio: event.audio, picture: event.pictureTreatment ?? null,
    sourceTimeMapping: event.sourceTimeMapping, preparationBindingHash: event.preparationBindingHash,
    trackId: event.trackId, sourceId: event.provenance.sourceId };
}
function blockLabel(document: ScriptDocumentV2, blockId: string | null, slotId?: string | null): string {
  const index = document.activeDraft.blocks.findIndex((b) => b.id === blockId);
  const block = document.activeDraft.blocks[index];
  if (!block) return "Programme";
  const slot = block.type === "narration" ? block.primaryVisualSequence?.slots.findIndex((s) => s.id === slotId) : undefined;
  return `Block ${index + 1} (${block.type})${slot !== undefined && slot >= 0 ? `, slot ${slot + 1}` : ""}`;
}
function comparison(document: ScriptDocumentV2, before: TimelineManifestV2, after: TimelineManifestV2): RevisionComparisonV2[] {
  const rows: RevisionComparisonV2[] = [{ label: "Programme frames", before: before.timeline.durationFrames, after: after.timeline.durationFrames }];
  const ids = [...new Set([...before.events, ...after.events].map((e) => e.eventId))].sort();
  for (const id of ids) {
    const a = eventImpact(before.events.find((e) => e.eventId === id));
    const b = eventImpact(after.events.find((e) => e.eventId === id));
    if (!equal(a, b)) {
      const event = b ?? a!;
      rows.push({ label: `${blockLabel(document, event.blockId, event.slotId)}: ${event.kind}`, before: a, after: b });
    }
  }
  const sources = [...new Set([...before.sources, ...after.sources].map((s) => s.id))].sort();
  for (const id of sources) {
    const a = before.sources.find((s) => s.id === id) ?? null;
    const b = after.sources.find((s) => s.id === id) ?? null;
    if (!equal(a, b)) rows.push({ label: `Source ${id}`, before: a, after: b });
  }
  return rows;
}
const escapeCell = (text: string) => text.replace(/\\/gu, "\\\\").replace(/\|/gu, "\\|").replace(/[\r\n]+/gu, " ");
function readable(value: unknown): string {
  if (value === null) return "Absent";
  if (typeof value === "string") return value;
  if (typeof value !== "object") return canonicalJson(value);
  if ("record" in value) {
    const e = value as ReturnType<typeof eventImpact> & object;
    return `record [${e.record.startFrame},${e.record.endFrame}), source ${e.source ? `[${e.source.startFrame},${e.source.endFrame})` : "none"}; track ${e.trackId}; media ${e.media ?? "none"}; timing ${e.timing ?? "none"}; audio ${e.audio ? `${e.audio.audioPolicy}, ${e.audio.gainDb} dB, samples [${e.audio.sampleRange.startFrame},${e.audio.sampleRange.endFrame})` : "none"}; picture ${canonicalJson(e.picture)}; mapping ${sha256CanonicalJson(e.sourceTimeMapping)}; preparation ${e.preparationBindingHash ?? "none"}`;
  }
  if ("narrationAudio" in value) {
    const s = value as Extract<TimelineManifestV2["sources"][number], { narrationAudio: unknown }>;
    return `Narration asset ${s.narrationAudio.narrationAssetId}; audio ${s.narrationAudio.audioHash}; ${s.narrationAudio.durationSamples} samples at ${s.narrationAudio.sampleRate} Hz`;
  }
  if ("deliveredHash" in value) {
    const s = value as Extract<TimelineManifestV2["sources"][number], { deliveredHash: unknown }>;
    return `Media ${s.mediaReferenceId}; original ${s.originalHash}; delivered ${s.deliveredHash}; mapping ${sha256CanonicalJson(s.sourceTimeMapping)}`;
  }
  return canonicalJson(value);
}
export function createRevisionProposalV2(input: ScriptDocumentV2, prior: CompilerDependenciesV2, request: RevisionRequestV2) {
  keys(request, "commands preparedMedia handoff");
  const before = ready(input, prior);
  const stage = prepareRevisionInputsV2(input, prior, request.commands, request.preparedMedia);
  let dependencies = stage.dependencies;
  if (stage.regeneration !== null) {
    fact(request.handoff !== null && equal(request.handoff.request, stage.regeneration), "matching whole-row handoff required");
    dependencies = finalizeReplacementV2(stage.document, dependencies, request.handoff).dependencies;
  } else {
    fact(request.handoff === null, "unexpected whole-row handoff");
    bindRevision(stage.document, dependencies, request);
  }
  const preview = ready(stage.document, dependencies);
  // Package inputs require one frozen timeline across dependencies, manifest and report.
  dependencies.timeline = structuredClone(preview.manifest.timeline);
  const compiled = ready(stage.document, dependencies);
  const repeated = ready(stage.document, dependencies);
  fact(equal(compiled.manifest.timeline, dependencies.timeline) && equal(compiled.report.timeline, dependencies.timeline) &&
    compiled.report.dependenciesHash === sha256CanonicalJson(dependencies), "package timeline/dependency identity differs");
  fact(compiled.manifestJson === repeated.manifestJson && compiled.reportJson === repeated.reportJson, "nondeterministic revision");
  fact(dependencies.build.buildId !== prior.build.buildId && dependencies.build.manifestId !== prior.build.manifestId &&
    dependencies.build.reportId !== prior.build.reportId, "fresh build identities required");
  const rows = comparison(input, before.manifest, compiled.manifest);
  const textRows: RevisionComparisonV2[] = [];
  for (const block of input.activeDraft.blocks) {
    const revised = stage.document.activeDraft.blocks.find((b) => b.id === block.id);
    if (block.type === "narration" && revised?.type === "narration" && block.text !== revised.text) {
      textRows.push({ label: `${blockLabel(input, block.id)}: narration text`, before: block.text, after: revised.text });
    }
  }
  const value = {
    schemaVersion: "issue-202-v2-proposal/v1" as const,
    baselineDocumentHash: sha256CanonicalJson(input), baselineDependenciesHash: sha256CanonicalJson(prior),
    baselineLiveHeadSequence: input.liveHeadSequence, request: structuredClone(request),
    document: stage.document, dependencies, manifest: compiled.manifest, report: compiled.report,
    manifestJson: compiled.manifestJson, reportJson: compiled.reportJson, comparison: [...textRows, ...rows],
    comparisonText: `| Change | Before | After |\n| --- | --- | --- |\n${[...textRows, ...rows].map((r) => `| ${escapeCell(r.label)} | ${escapeCell(readable(r.before))} | ${escapeCell(readable(r.after))} |`).join("\n")}`,
  };
  return { ...value, proposalHash: sha256CanonicalJson(value) };
}

/** Caller atomically persists returned history with revision; this core performs no effects. */
export function decideRevisionV2(
  input: ScriptDocumentV2, prior: CompilerDependenciesV2,
  proposal: ReturnType<typeof createRevisionProposalV2>, decision: RevisionDecisionV2, history: string[],
) {
  keys(decision, "schemaVersion proposalHash historyHash outcome");
  fact(decision.schemaVersion === "issue-202-v2-decision/v1" && (decision.outcome === "accept" || decision.outcome === "reject"), "unsupported decision");
  fact(Array.isArray(history) && history.every((h) => /^sha256:[a-f0-9]{64}$/u.test(h)) && new Set(history).size === history.length &&
    decision.historyHash === sha256CanonicalJson(history), "stale/malformed decision history");
  fact(!history.includes(proposal.proposalHash), "proposal already decided");
  fact(proposal.baselineDocumentHash === sha256CanonicalJson(input) && proposal.baselineDependenciesHash === sha256CanonicalJson(prior) &&
    proposal.baselineLiveHeadSequence === input.liveHeadSequence, "stale document/dependencies/live head");
  const current = createRevisionProposalV2(input, prior, proposal.request);
  fact(equal(current, proposal) && decision.proposalHash === current.proposalHash, "proposal/decision identity changed");
  return { outcome: decision.outcome, document: decision.outcome === "accept" ? current.document : input,
    dependencies: decision.outcome === "accept" ? current.dependencies : prior,
    decisionHash: sha256CanonicalJson(decision), history: [...history, current.proposalHash] };
}
