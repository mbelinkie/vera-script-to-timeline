/** Synthetic semantic composition. The host separately proves and accepts audio.
 * The restored visual projection is transient; it is never an observation artifact.
 */
import { canonicalJson, compileTimeline, sha256CanonicalJson } from "./compiler-core.js";
import type { FrameRange } from "./generated/contracts.js";
import { applyVisualDecisions, proposeVisuals } from "./issue-144-semantics.js";
import type { ObservedItem, ProofObservation, VisualProofInputs } from "./issue-144-semantics.js";
import { applyAcceptedOmission } from "./issue-144-text-revision.js";
import type { AcceptedOmission, OmissionRevision } from "./issue-144-text-revision.js";
import { validateScriptDocument } from "./script-validator.js";

type RawItem = Omit<ObservedItem, "eventId">;
interface RawObservation extends Omit<ProofObservation, "schemaVersion" | "items"> {
  schemaVersion: "issue-144-omission-observation/v1";
  items: RawItem[];
  programControls: unknown;
  audioControls: unknown;
}
export interface CompositionInputs extends Omit<VisualProofInputs, "observationA" | "observationB"> {
  rowId: string;
  observationA: RawObservation;
  observationB: RawObservation;
}

const equal = (left: unknown, right: unknown): boolean => canonicalJson(left) === canonicalJson(right);
function fact(condition: boolean, message: string): asserts condition { if (!condition) throw new Error(message); }
function keys(value: object, expected: string[]): boolean { return equal(Object.keys(value).sort(), [...expected].sort()); }
function range(value: FrameRange | null): void {
  if (value === null) return;
  fact(typeof value === "object" && keys(value, ["startFrame", "durationFrames"])
    && Number.isSafeInteger(value.startFrame) && value.startFrame >= 0
    && Number.isSafeInteger(value.durationFrames) && value.durationFrames > 0
    && Number.isSafeInteger(value.startFrame + value.durationFrames), "uncertain composition geometry");
}
function sourceBinding(item: RawItem | ObservedItem): unknown[] {
  return [item.mediaUid, item.sourcePath, item.sourceHash, item.trackId, item.trackKind];
}

function visualInputs(input: CompositionInputs): VisualProofInputs {
  fact(keys(input, ["rowId", "baselineDocument", "currentDocument", "dependencies", "baselineManifest", "baselineObservation", "observationA", "observationB"]), "unexpected composition inputs");
  fact(equal(input.observationA, input.observationB), "composition observations changed between adjacent reads");
  const row = input.currentDocument.activeDraft.blocks.find(block => block.id === input.rowId);
  fact(row?.type === "narration" && row.state === "active", "one active composition row required");
  const primary = input.baselineManifest.events.filter(event => event.kind === "audio" && event.provenance.authoringKind === "narration_block" && event.provenance.blockId === row.id);
  fact(primary.length === 1, "unique compiled composition narration required");
  const old = input.baselineObservation.items;
  const narration = old.find(item => item.eventId === primary[0]!.id);
  fact(narration !== undefined, "missing baseline narration identity");
  const companions = old.filter(item => item.trackKind === "video" && equal(item.linkedUids, [narration.itemUid])
    && input.baselineManifest.events.some(event => event.id === item.eventId && event.provenance.blockId === row.id)
    && row.visualEvents.some(visual => visual.id === item.eventId && visual.audioPolicy === "mute"));
  fact(companions.length === 1, "unique muted proof-linked composition companion required");
  const companion = companions[0]!;
  fact(equal(narration.linkedUids, [companion.itemUid]) && equal(narration.recordRange, companion.recordRange)
    && equal(narration.sourceRange, companion.sourceRange), "pristine composition pair differs");
  const selected = [narration, companion];
  const selectedIds = new Set(selected.map(item => item.eventId));
  const observation = input.observationA;
  fact(keys(observation, ["schemaVersion", "evidenceLevel", "projectUid", "timelineUid", "timeline", "tracks", "items", "programControls", "audioControls"])
    && observation.schemaVersion === "issue-144-omission-observation/v1" && observation.evidenceLevel === "synthetic_injected"
    && observation.projectUid === input.baselineObservation.projectUid && observation.timelineUid === input.baselineObservation.timelineUid
    && equal(observation.timeline, input.baselineManifest.timeline) && equal(observation.tracks, input.baselineManifest.tracks), "composition target/settings/lane differs");
  fact(Array.isArray(observation.items) && observation.items.length <= old.length + 128, "bounded complete composition inventory required");
  const groups = new Map(old.map(item => [item.eventId, [] as RawItem[]]));
  const byUid = new Map<string, RawItem>();
  for (const item of observation.items) {
    fact(keys(item, ["itemUid", "mediaUid", "sourcePath", "sourceHash", "trackId", "trackKind", "recordRange", "sourceRange", "available", "enabled", "speed", "linkedUids"])
      && typeof item.itemUid === "string" && item.itemUid.length > 0 && !byUid.has(item.itemUid), "unknown or duplicate composition occurrence");
    range(item.recordRange); fact(item.recordRange !== null, "missing composition record geometry"); range(item.sourceRange);
    const birth = old.filter(candidate => candidate.itemUid === item.itemUid);
    const candidates = birth.length ? birth : selected.filter(candidate => equal(sourceBinding(candidate), sourceBinding(item)));
    fact(candidates.length === 1 && equal(sourceBinding(candidates[0]!), sourceBinding(item)), "unknown/ambiguous composition source association");
    const original = candidates[0]!;
    fact(item.available === original.available && item.enabled === original.enabled && item.speed === original.speed, "composition control changed");
    groups.get(original.eventId)!.push(item); byUid.set(item.itemUid, item);
  }
  for (const original of old) fact(groups.get(original.eventId)!.length > 0 && (selectedIds.has(original.eventId) || groups.get(original.eventId)!.length === 1), "missing/extra untouched composition occurrence");
  const audio = groups.get(narration.eventId)!; const video = groups.get(companion.eventId)!;
  fact(audio.length === video.length, "composition split pair inventory differs");
  for (const item of audio) {
    fact(Array.isArray(item.linkedUids) && item.linkedUids.length === 1, "composition split companion missing");
    const peer = byUid.get(item.linkedUids[0]!);
    fact(peer !== undefined && video.includes(peer) && equal(peer.linkedUids, [item.itemUid])
      && equal(peer.recordRange, item.recordRange) && equal(peer.sourceRange, item.sourceRange), "composition split pair is not reciprocal/equal");
  }
  // Only semantic enumeration sees these restored facts. Raw capture and full
  // program evidence remain unchanged and must independently pass in the host.
  const projected: ProofObservation = {
    schemaVersion: "issue-144-observation/v1", evidenceLevel: observation.evidenceLevel,
    projectUid: observation.projectUid, timelineUid: observation.timelineUid,
    timeline: observation.timeline, tracks: observation.tracks,
    items: old.map(original => selectedIds.has(original.eventId) ? structuredClone(original)
      : { eventId: original.eventId, ...structuredClone(groups.get(original.eventId)![0]!) }),
  };
  return { baselineDocument: input.baselineDocument, currentDocument: input.currentDocument, dependencies: input.dependencies,
    baselineManifest: input.baselineManifest, baselineObservation: input.baselineObservation,
    observationA: projected, observationB: structuredClone(projected) };
}

export function inspectComposition(input: CompositionInputs) {
  const visual = visualInputs(input);
  const visualReport = proposeVisuals(visual);
  const row = input.currentDocument.activeDraft.blocks.find(block => block.id === input.rowId);
  fact(row?.type === "narration" && visualReport.status === "ready" && visualReport.rows.length === 2
    && equal(visualReport.rows.map(proposal => proposal.operation).sort(), ["move", "trim"])
    && visualReport.rows.every(proposal => proposal.classification === "supported" && proposal.range !== null
      && row.visualEvents.some(event => event.id === proposal.authoringId)), "exact supported same-row move/trim required");
  const applied = applyVisualDecisions(visual, visualReport, { schemaVersion: "issue-144-decisions/v1", reportHash: sha256CanonicalJson(visualReport), choices: visualReport.rows.map(proposal => ({ proposalId: proposal.id, decision: "accept" })) });
  fact(applied.status === "revised", "actual visual revision required");
  const compiled = compileTimeline(applied.document, applied.dependencies);
  fact(compiled.ok, "actual composed visual preview refused");
  return { visualReport, visualManifest: compiled.manifest };
}

export function composeEdits(input: CompositionInputs, edit: AcceptedOmission): OmissionRevision {
  fact(edit.blockId === input.rowId, "composition omission row differs");
  const { visualReport } = inspectComposition(input);
  const revised = applyAcceptedOmission(input.currentDocument, edit);
  const row = revised.document.activeDraft.blocks.find(block => block.id === input.rowId);
  fact(row?.type === "narration", "revised composition row missing");
  for (const proposal of visualReport.rows) {
    const visual = row.visualEvents.find(event => event.id === proposal.authoringId)!;
    const candidate = proposal.range!;
    const first = row.tokens.find(word => word.id === candidate.startTokenId);
    const last = row.tokens.find(word => word.id === candidate.endTokenId);
    fact(first !== undefined && last !== undefined && candidate.startAffinity === "before" && candidate.endAffinity === "after", "composition visual endpoint removed");
    fact(Number.isSafeInteger(visual.version + 1) && Number.isSafeInteger(visual.range.anchorVersion + 1), "composition version overflow");
    visual.range = { ...structuredClone(candidate), quotedText: row.text.slice(first.startOffset, last.endOffset), anchorVersion: visual.range.anchorVersion + 1 };
    visual.version += 1;
  }
  revised.document.liveContentHash = sha256CanonicalJson(Object.fromEntries(Object.entries(revised.document).filter(([key]) => key !== "liveContentHash")));
  fact(validateScriptDocument(revised.document).valid, "actual composed script validator refused");
  revised.documentJson = canonicalJson(revised.document);
  // No compile with old narration deps. The host's actual whole-row handoff
  // supplies new audio/marks before finalization and the durable fresh build.
  return revised;
}
