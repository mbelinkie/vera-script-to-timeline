/** Bounded proof semantics. Native identity is established by the host sidecar. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { canonicalJson, compileTimeline, sha256CanonicalJson } from "./compiler-core.js";
import type { CompilerDependenciesV1, FrameRange, ScriptDocumentV1, TextAnchorRange, TimelineManifestV1, VisualEvent } from "./generated/contracts.js";

type Event = TimelineManifestV1["events"][number];
export interface ObservedItem {
  eventId: string; itemUid: string; mediaUid: string;
  sourcePath: string; sourceHash: string; trackId: string; trackKind: "video" | "audio";
  recordRange: FrameRange; sourceRange: FrameRange | null;
  available: boolean; enabled: boolean; speed: number; linkedUids: string[];
}
export interface ProofObservation {
  schemaVersion: "issue-144-observation/v1";
  evidenceLevel: "synthetic_injected" | "retained_native_observation" | "real_issue145";
  projectUid: string; timelineUid: string;
  timeline: TimelineManifestV1["timeline"]; tracks: TimelineManifestV1["tracks"];
  items: ObservedItem[];
}
export interface VisualProofInputs {
  baselineDocument: ScriptDocumentV1; currentDocument: ScriptDocumentV1;
  dependencies: CompilerDependenciesV1; baselineManifest: TimelineManifestV1;
  baselineObservation: ProofObservation; observationA: ProofObservation; observationB: ProofObservation;
}
interface Proposal {
  id: string; authoringId: string; classification: "supported" | "unsupported";
  operation: "move" | "trim" | "unknown"; reason: string; range: TextAnchorRange | null;
}
export interface VisualProposalReport {
  schemaVersion: "issue-144-proposals/v1";
  evidenceLevel: ProofObservation["evidenceLevel"];
  implementationHash: string;
  bindings: Record<keyof VisualProofInputs, string>;
  status: "ready" | "refused"; refusal: string | null; rows: Proposal[];
}

const equal = (left: unknown, right: unknown): boolean => canonicalJson(left) === canonicalJson(right);
function requireFact(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(message);
}
function exactKeys(value: object, keys: string[]): boolean {
  return equal(Object.keys(value).sort(), [...keys].sort());
}
function validRange(range: FrameRange | null, optional = false): boolean {
  if (range === null) return optional;
  return typeof range === "object" && range !== undefined && exactKeys(range, ["startFrame", "durationFrames"])
    && Number.isSafeInteger(range.startFrame) && range.startFrame >= 0
    && Number.isSafeInteger(range.durationFrames) && range.durationFrames > 0
    && Number.isSafeInteger(range.startFrame + range.durationFrames);
}
function withoutGeometry(item: ObservedItem): object {
  return Object.fromEntries(Object.entries(item).filter(([key]) => key !== "recordRange" && key !== "sourceRange"));
}

function validateObservation(observation: ProofObservation, manifest: TimelineManifestV1): Map<string, ObservedItem> {
  requireFact(exactKeys(observation, ["schemaVersion", "evidenceLevel", "projectUid", "timelineUid", "timeline", "tracks", "items"]), "incomplete observation envelope");
  requireFact(observation.schemaVersion === "issue-144-observation/v1" && ["synthetic_injected", "retained_native_observation", "real_issue145"].includes(observation.evidenceLevel), "unknown evidence lane");
  requireFact(typeof observation.projectUid === "string" && observation.projectUid.length > 0 && typeof observation.timelineUid === "string" && observation.timelineUid.length > 0, "missing project/timeline identity");
  requireFact(equal(observation.timeline, manifest.timeline) && equal(observation.tracks, manifest.tracks), "timeline settings or track inventory changed");
  requireFact(Array.isArray(observation.items) && observation.items.length === manifest.events.length, "missing or additional occurrences");
  const result = new Map<string, ObservedItem>();
  const uids = new Set<string>();
  const sourceUids = new Map<string, string>();
  for (const item of observation.items) {
    requireFact(typeof item === "object" && item !== null && exactKeys(item, ["eventId", "itemUid", "mediaUid", "sourcePath", "sourceHash", "trackId", "trackKind", "recordRange", "sourceRange", "available", "enabled", "speed", "linkedUids"]), "incomplete occurrence facts");
    const event = manifest.events.find((row) => row.id === item.eventId);
    requireFact(event !== undefined && !result.has(item.eventId), "unknown or duplicate managed occurrence");
    requireFact(typeof item.itemUid === "string" && item.itemUid.length > 0 && !uids.has(item.itemUid) && typeof item.mediaUid === "string" && item.mediaUid.length > 0, "duplicate or missing native identity");
    requireFact(item.available === true && item.enabled === true && item.speed === 100, "unavailable, disabled or retimed occurrence");
    requireFact(validRange(item.recordRange) && validRange(item.sourceRange, true), "uncertain fractional or incomplete ranges");
    requireFact(Array.isArray(item.linkedUids) && item.linkedUids.every((uid) => typeof uid === "string" && uid.length > 0 && uid !== item.itemUid) && new Set(item.linkedUids).size === item.linkedUids.length, "ambiguous links");
    const source = manifest.sources.find((row) => row.id === event.sourceId)!;
    const path = source.kind === "placeholder" ? `Media/Placeholders/${source.id}.png` : source.path;
    requireFact(item.sourcePath === path && /^sha256:[a-f0-9]{64}$/.test(item.sourceHash) && (source.kind === "placeholder" || item.sourceHash === source.contentHash), "source identity/bytes changed");
    requireFact(item.trackId === event.trackId && item.trackKind === event.trackKind, "track reassignment is unsupported");
    requireFact((sourceUids.get(event.sourceId) ?? item.mediaUid) === item.mediaUid && ![...sourceUids.entries()].some(([sourceId, uid]) => sourceId !== event.sourceId && uid === item.mediaUid), "source UID alias or replacement");
    sourceUids.set(event.sourceId, item.mediaUid);
    uids.add(item.itemUid); result.set(item.eventId, item);
  }
  requireFact(observation.items.every((item) => item.linkedUids.every((uid) => uids.has(uid))), "links include an unknown occurrence");
  return result;
}

function visuals(document: ScriptDocumentV1): VisualEvent[] {
  return document.activeDraft.blocks.flatMap((block) => block.type === "narration" ? block.visualEvents : block.type === "visual" ? [block.event] : []);
}
function replaceRange(document: ScriptDocumentV1, authoringId: string, range: TextAnchorRange): void {
  const matches = visuals(document).filter((visual) => visual.id === authoringId);
  requireFact(matches.length === 1, "authoring event is missing or ambiguous");
  matches[0]!.range = structuredClone(range); matches[0]!.version += 1;
}
function geometryMatches(event: Event, item: ObservedItem): boolean {
  return equal(event.recordRange, item.recordRange) && equal("sourceRange" in event ? event.sourceRange : null, item.sourceRange)
    && event.trackId === item.trackId && event.trackKind === item.trackKind;
}
function clearance(pair: ObservedItem[], current: Map<string, ObservedItem>): boolean {
  return pair.every((item) => [...current.values()].every((other) => pair.includes(other) || other.trackId !== item.trackId
    || item.recordRange.startFrame + item.recordRange.durationFrames <= other.recordRange.startFrame
    || other.recordRange.startFrame + other.recordRange.durationFrames <= item.recordRange.startFrame));
}
function candidates(input: VisualProofInputs, visual: VisualEvent, pair: ObservedItem[]): TextAnchorRange[] {
  const block = input.currentDocument.activeDraft.blocks.find((row) => row.id === visual.range.blockId);
  requireFact(block?.type === "narration" && block.state === "active", "visual anchor block is unavailable");
  // ponytail: bounded exhaustive compiler calls for <=64 tokens; production
  // reconciliation needs an indexed compiler timing seam, outside this proof.
  requireFact(block.tokens.length <= 64, "proof candidate enumeration requires at most 64 tokens in the anchor block");
  const ranges: TextAnchorRange[] = [];
  for (let start = 0; start < block.tokens.length; start += 1) {
    for (let end = start; end < block.tokens.length; end += 1) {
      const first = block.tokens[start]!; const last = block.tokens[end]!;
      const range: TextAnchorRange = { blockId: block.id, startTokenId: first.id, endTokenId: last.id, startAffinity: "before", endAffinity: "after", quotedText: block.text.slice(first.startOffset, last.endOffset), anchorVersion: visual.range.anchorVersion + 1 };
      const candidate = structuredClone(input.currentDocument);
      replaceRange(candidate, visual.id, range);
      const compiled = compileTimeline(candidate, input.dependencies);
      if (compiled.ok && pair.every((item) => {
        const event = compiled.manifest.events.find((row) => row.id === item.eventId);
        return event !== undefined && geometryMatches(event, item);
      })) ranges.push(range);
    }
  }
  return ranges;
}

export function proposeVisuals(input: VisualProofInputs): VisualProposalReport {
  const report: VisualProposalReport = {
    schemaVersion: "issue-144-proposals/v1", evidenceLevel: input.baselineObservation.evidenceLevel,
    implementationHash: `sha256:${createHash("sha256").update(readFileSync(new URL(import.meta.url))).digest("hex")}`,
    bindings: Object.fromEntries(Object.entries(input).map(([key, value]) => [key, sha256CanonicalJson(value)])) as VisualProposalReport["bindings"],
    status: "ready", refusal: null, rows: [],
  };
  try {
    requireFact(exactKeys(input, ["baselineDocument", "currentDocument", "dependencies", "baselineManifest", "baselineObservation", "observationA", "observationB"]), "unexpected proof inputs");
    requireFact(equal(input.baselineDocument, input.currentDocument), "current script changed since baseline; conflict");
    requireFact(equal(input.observationA, input.observationB), "observation changed between adjacent reads");
    const compiled = compileTimeline(input.baselineDocument, input.dependencies);
    requireFact(compiled.ok && equal(compiled.manifest, input.baselineManifest), "baseline is not the actual compiler result");
    requireFact(input.baselineManifest.timeline.frameRate.numerator === 25 && input.baselineManifest.timeline.frameRate.denominator === 1, "only the qualified 25 fps lane is supported");
    const baseline = validateObservation(input.baselineObservation, input.baselineManifest);
    const current = validateObservation(input.observationA, input.baselineManifest);
    requireFact(input.baselineObservation.projectUid === input.observationA.projectUid && input.baselineObservation.timelineUid === input.observationA.timelineUid && input.baselineObservation.evidenceLevel === input.observationA.evidenceLevel, "wrong target or evidence lane");
    for (const event of input.baselineManifest.events) {
      requireFact(geometryMatches(event, baseline.get(event.id)!), "baseline geometry was not pristine");
      requireFact(equal(withoutGeometry(baseline.get(event.id)!), withoutGeometry(current.get(event.id)!)), "native identity/source/control/link changed");
    }
    const changed = input.baselineManifest.events.filter((event) => !geometryMatches(event, current.get(event.id)!));
    const groups = [...new Set(changed.map((event) => event.provenance.authoringId))].sort();
    for (const authoringId of groups) {
      const row: Omit<Proposal, "id"> = { authoringId, classification: "unsupported", operation: "unknown", reason: "change is outside the linked visual subset", range: null };
      const events = input.baselineManifest.events.filter((event) => event.provenance.authoringId === authoringId);
      const visual = visuals(input.currentDocument).find((event) => event.id === authoringId);
      const pair = events.map((event) => current.get(event.id)!);
      if (visual?.status === "ready" && visual.audioPolicy === "use_source" && events.length === 2 && events.some((event) => event.kind === "video") && events.some((event) => event.kind === "audio") && pair.every((item, index) => equal(item.linkedUids, [pair[1 - index]!.itemUid])) && equal(pair[0]!.recordRange, pair[1]!.recordRange)) {
        const moved = events.every((event) => current.get(event.id)!.recordRange.startFrame === event.recordRange.startFrame + 25 && current.get(event.id)!.recordRange.durationFrames === event.recordRange.durationFrames && equal(current.get(event.id)!.sourceRange, "sourceRange" in event ? event.sourceRange : null));
        const trimmed = events.every((event) => {
          const item = current.get(event.id)!;
          return "sourceRange" in event && item.sourceRange !== null && item.recordRange.startFrame === event.recordRange.startFrame && item.recordRange.durationFrames === event.recordRange.durationFrames - 25 && item.sourceRange.startFrame === event.sourceRange.startFrame && item.sourceRange.durationFrames === event.sourceRange.durationFrames - 25;
        });
        if (moved || trimmed) {
          row.operation = moved ? "move" : "trim";
          row.reason = "video or shared source-audio track has no clearance";
          if (clearance(pair, current)) {
            const matches = candidates(input, visual, pair);
            row.reason = matches.length === 0 ? "no validator-passing compiler range reproduces both endpoints" : "ambiguous token boundaries after frame rounding";
            if (matches.length === 1) { row.classification = "supported"; row.range = matches[0]!; row.reason = "unique canonical token range reproduced by the actual compiler"; }
          }
        }
      }
      report.rows.push({ ...row, id: sha256CanonicalJson({ bindings: report.bindings, row }) });
    }
  } catch (error) {
    report.status = "refused"; report.refusal = error instanceof Error ? error.message : "invalid proof inputs"; report.rows = [];
  }
  return report;
}

function revisionId(seed: string, kind: string): string {
  const bytes = createHash("sha1").update(Buffer.from("14400000000040008000000000000000", "hex")).update(`${seed}\0${kind}`).digest();
  bytes[6] = (bytes[6]! & 15) | 80; bytes[8] = (bytes[8]! & 63) | 128;
  const hex = bytes.toString("hex"); return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}

export function applyVisualDecisions(input: VisualProofInputs, report: VisualProposalReport, decisions: unknown): { status: "rejected" } | { status: "revised"; document: ScriptDocumentV1; dependencies: CompilerDependenciesV1 } {
  requireFact(equal(proposeVisuals(input), report) && report.status === "ready", "stale or refused proposal report");
  requireFact(typeof decisions === "object" && decisions !== null && exactKeys(decisions, ["schemaVersion", "reportHash", "choices"]), "malformed decision envelope");
  const decision = decisions as { schemaVersion: unknown; reportHash: unknown; choices: unknown };
  requireFact(decision.schemaVersion === "issue-144-decisions/v1" && decision.reportHash === sha256CanonicalJson(report) && Array.isArray(decision.choices), "decision report binding differs");
  requireFact(decision.choices.length === report.rows.length, "missing or duplicate decisions");
  const seen = new Set<string>(); const accepted: Proposal[] = [];
  const choices: unknown[] = decision.choices;
  for (const value of choices) {
    requireFact(typeof value === "object" && value !== null && exactKeys(value, ["proposalId", "decision"]), "malformed choice");
    const choice = value as { proposalId: string; decision: unknown };
    const row = report.rows.find((proposal) => proposal.id === choice.proposalId);
    requireFact(row !== undefined && !seen.has(choice.proposalId) && (choice.decision === "accept" || choice.decision === "reject"), "unknown, duplicate or malformed choice");
    seen.add(choice.proposalId);
    if (choice.decision === "accept") { requireFact(row.classification === "supported" && row.range !== null, "unsupported proposal cannot be accepted"); accepted.push(row); }
  }
  if (accepted.length === 0) return { status: "rejected" };
  const document = structuredClone(input.currentDocument);
  for (const row of accepted) replaceRange(document, row.authoringId, row.range!);
  requireFact(Number.isSafeInteger(document.liveHeadSequence + 1), "new revision sequence exceeds exact integer range");
  document.liveHeadSequence += 1; document.liveStateVector = "";
  document.liveContentHash = sha256CanonicalJson(Object.fromEntries(Object.entries(document).filter(([key]) => key !== "liveContentHash")));
  const dependencies = structuredClone(input.dependencies);
  const seed = sha256CanonicalJson({ document, priorDependencies: input.dependencies });
  dependencies.build.buildId = revisionId(seed, "build"); dependencies.build.manifestId = revisionId(seed, "manifest"); dependencies.build.reportId = revisionId(seed, "report");
  const compiled = compileTimeline(document, dependencies);
  requireFact(compiled.ok, `composed accepted revision does not validate/compile: ${compiled.ok ? "" : canonicalJson(compiled.diagnostics)}`);
  for (const row of accepted) {
    const pair = input.baselineManifest.events.filter((event) => event.provenance.authoringId === row.authoringId);
    requireFact(pair.every((event) => { const rebuilt = compiled.manifest.events.find((candidate) => candidate.id === event.id); return rebuilt !== undefined && geometryMatches(rebuilt, input.observationA.items.find((item) => item.eventId === event.id)!); }), "composed revision does not reproduce the accepted geometry");
  }
  return { status: "revised", document, dependencies };
}
