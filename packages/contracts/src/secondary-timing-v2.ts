/**
 * Read-only, frame-exact comparison of two independently verified v2 manifests.
 * This does not authenticate a build, validate source sufficiency, or apply an edit:
 * callers must acquire trusted artifacts and perform those checks before mutation.
 */
import type {
  FrameRangeV2,
  RationalRate,
  TimelineEventV2,
  TimelineManifestV2,
  VisualSequenceResolutionV2,
} from "./generated/contracts-v2.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

export type SecondaryTimingProblemCodeV2 =
  | "INVALID_MANIFEST" | "UNSAFE_FRAME" | "DOCUMENT_MISMATCH"
  | "RATE_MISMATCH" | "EVIDENCE_MISMATCH" | "STRUCTURE_CHANGED"
  | "DUPLICATE_OWNER" | "INCONSISTENT_RANGE";

export class SecondaryTimingComparisonErrorV2 extends Error {
  readonly code: SecondaryTimingProblemCodeV2;

  constructor(code: SecondaryTimingProblemCodeV2, detail: string) {
    super(detail);
    this.name = "SecondaryTimingComparisonErrorV2";
    this.code = code;
  }
}

export interface SecondaryBoundaryDifferenceV2 {
  blockId: string;
  sequenceId: string;
  ownerId: string;
  relation: VisualSequenceResolutionV2["relation"];
  boundaryKind: VisualSequenceResolutionV2["boundaryKind"];
  beforeFrame: number;
  afterFrame: number;
  deltaFrames: number;
  beforeRange: FrameRangeV2 | null;
  afterRange: FrameRangeV2 | null;
  durationDeltaFrames: number | null;
  beforeSourceRange: FrameRangeV2 | null;
  afterSourceRange: FrameRangeV2 | null;
  beforePrecision: VisualSequenceResolutionV2["alignmentPrecision"];
  afterPrecision: VisualSequenceResolutionV2["alignmentPrecision"];
  boundaryEvidenceHash: string | null;
}

/** Independent overlays and visual-only rows have no visualSequenceResolution. */
export interface SecondaryVisualEventDifferenceV2 {
  eventId: string;
  blockId: string;
  ownerId: string;
  kind: TimelineEventV2["kind"];
  beforeRange: FrameRangeV2;
  afterRange: FrameRangeV2;
  startDeltaFrames: number;
  endDeltaFrames: number;
  durationDeltaFrames: number;
  beforeSourceRange: FrameRangeV2 | null;
  afterSourceRange: FrameRangeV2 | null;
}

export interface SecondaryTimingComparisonV2 {
  schemaVersion: "secondary-timing-comparison/v1";
  disposition: "proposed_not_applied";
  frameRate: RationalRate;
  before: { revision: number; contentHash: string };
  after: { revision: number; contentHash: string };
  boundaries: SecondaryBoundaryDifferenceV2[];
  visualEvents: SecondaryVisualEventDifferenceV2[];
}

const fail = (code: SecondaryTimingProblemCodeV2, reason: string): never => {
  throw new SecondaryTimingComparisonErrorV2(code, reason);
};
const compareKeys = (a: string, b: string): number => a < b ? -1 : a > b ? 1 : 0;
const safeFrame = (frame: number): number =>
  Number.isSafeInteger(frame) && frame >= 0 ? frame : fail("UNSAFE_FRAME", "Record frames must be nonnegative safe integers");
const safeDelta = (before: number, after: number): number => {
  const delta = BigInt(safeFrame(after)) - BigInt(safeFrame(before));
  if (delta < BigInt(Number.MIN_SAFE_INTEGER) || delta > BigInt(Number.MAX_SAFE_INTEGER)) {
    return fail("UNSAFE_FRAME", "Frame difference exceeds signed safe-integer bounds");
  }
  return Number(delta);
};
const safeRange = (range: FrameRangeV2): FrameRangeV2 => {
  if (safeDelta(range.startFrame, range.endFrame) <= 0) {
    return fail("INCONSISTENT_RANGE", "Collapsed or reversed record/source interval");
  }
  return { startFrame: range.startFrame, endFrame: range.endFrame };
};
const optionalRange = (range: FrameRangeV2 | null): FrameRangeV2 | null => range === null ? null : safeRange(range);
const duration = (range: FrameRangeV2): number => safeDelta(range.startFrame, range.endFrame);

function rate(rate: RationalRate): RationalRate {
  if (!Number.isSafeInteger(rate.numerator) || !Number.isSafeInteger(rate.denominator) ||
      rate.numerator <= 0 || rate.denominator <= 0) {
    return fail("RATE_MISMATCH", "Record rate must be a positive rational of safe integers");
  }
  return { numerator: rate.numerator, denominator: rate.denominator };
}

function ownerId(item: VisualSequenceResolutionV2): string {
  const id = item.relation === "return" ? item.returnSlotId : item.slotId;
  if (typeof id !== "string" || !id) return fail("STRUCTURE_CHANGED", "Missing stable structural owner");
  return id;
}
function ownerKey(item: VisualSequenceResolutionV2): string {
  return JSON.stringify([item.blockId, ownerId(item)]);
}
function structuralRange(item: VisualSequenceResolutionV2): FrameRangeV2 | null {
  if (item.relation === "return") {
    if (item.slotId !== null || item.payloadId !== null || item.rootRanges.length || item.childRanges.length ||
        item.eventIds.length || item.topmostAppearances.length || item.sourceRange !== null || item.sourceTimeMapping !== null) {
      return fail("INCONSISTENT_RANGE", "Return is not a new source or visible interval");
    }
    return null;
  }
  if (item.returnSlotId !== null ||
      (item.relation === "root" ? item.rootRanges.length !== 1 || item.childRanges.length !== 0
        : item.childRanges.length !== 1 || item.rootRanges.length !== 0)) {
    return fail("INCONSISTENT_RANGE", "Root/child range ownership is ambiguous");
  }
  const candidate = item.relation === "root" ? item.rootRanges[0]! : item.childRanges[0]!;
  const range = safeRange(candidate);
  if (range.startFrame !== item.resolvedRecordFrame) {
    return fail("INCONSISTENT_RANGE", "Owner boundary differs from the structural range start");
  }
  return range;
}

function indexEvents(manifest: TimelineManifestV2): Map<string, TimelineEventV2> {
  const result = new Map<string, TimelineEventV2>();
  for (const event of manifest.events) {
    if (!event.eventId || result.has(event.eventId)) fail("DUPLICATE_OWNER", "Duplicate or missing event ID");
    safeRange(event.recordRange);
    optionalRange(event.sourceRange);
    if (event.provenance.documentId !== manifest.document.documentId) fail("EVIDENCE_MISMATCH", "Event document identity differs");
    result.set(event.eventId, event);
  }
  return result;
}

function indexOwners(manifest: TimelineManifestV2, events: Map<string, TimelineEventV2>): Map<string, VisualSequenceResolutionV2> {
  const owners = new Map<string, VisualSequenceResolutionV2>();
  const rootIntervals = new Map<string, FrameRangeV2[]>();
  const children = new Map<string, FrameRangeV2[]>();
  for (const item of manifest.visualSequenceResolutions) {
    if (!item.blockId || !item.sequenceId || item.documentId !== manifest.document.documentId ||
        !Number.isSafeInteger(item.structuralSlotIndex) || item.structuralSlotIndex < 0) {
      fail("STRUCTURE_CHANGED", "Invalid sequence owner or structural index");
    }
    safeFrame(item.resolvedRecordFrame);
    const key = ownerKey(item);
    if (owners.has(key)) fail("DUPLICATE_OWNER", "Duplicate visual sequence owner");
    owners.set(key, item);
    const range = structuralRange(item);
    optionalRange(item.sourceRange);
    if (item.relation === "return") {
      const matches = manifest.composition.returns.filter((entry) => entry.returnSlotId === ownerId(item));
      if (matches.length !== 1 || matches[0]!.recordFrame !== item.resolvedRecordFrame || matches[0]!.emitsNewSourceEvent !== false ||
          !events.has(matches[0]!.rootEventId)) {
        fail("INCONSISTENT_RANGE", "Return does not reveal its recorded root");
      }
    } else if (range) {
      const group = JSON.stringify([item.blockId, item.sequenceId]);
      const bucket = item.relation === "root" ? rootIntervals : children;
      bucket.set(group, [...bucket.get(group) ?? [], range]);
      for (const eventId of item.eventIds) {
        const event = events.get(eventId);
        if (!event || event.provenance.slotId !== item.slotId || !sameAuthoringJsonV2(event.recordRange, range)) {
          fail("INCONSISTENT_RANGE", "Visible event does not match its owner interval");
        }
      }
      for (const appearance of item.topmostAppearances) {
        const event = events.get(appearance.eventId);
        if (!event || !item.eventIds.includes(appearance.eventId) || !sameAuthoringJsonV2(appearance.recordRange, event.recordRange)) {
          fail("INCONSISTENT_RANGE", "Topmost appearance lacks its recorded event");
        }
      }
    }
  }
  for (const [group, intervals] of rootIntervals) {
    const sorted = [...intervals].sort((a, b) => a.startFrame - b.startFrame);
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i - 1]!.endFrame !== sorted[i]!.startFrame) fail("INCONSISTENT_RANGE", "Primary roots have a gap or overlap");
    }
    for (const child of children.get(group) ?? []) {
      if (!sorted.some((root) => root.startFrame <= child.startFrame && child.endFrame <= root.endFrame)) {
        fail("INCONSISTENT_RANGE", "Child does not fit inside a continuously advancing root");
      }
    }
  }
  if ([...children.keys()].some((group) => !rootIntervals.has(group))) {
    fail("INCONSISTENT_RANGE", "Child has no continuously advancing parent root");
  }
  if (manifest.composition.returns.length !== [...owners.values()].filter((item) => item.relation === "return").length) {
    fail("INCONSISTENT_RANGE", "Unowned composition return or missing return evidence");
  }
  return owners;
}

function evidenceKey(item: TimelineManifestV2["boundaryEvidence"][number], index: number): string {
  // Independent overlay timing can emit both start and end for the same owner.
  return JSON.stringify([item.entityId, item.kind, item.relatedTokenId ?? null,
    item.kind === "independent_timing" ? index : 0]);
}

function indexEvidence(manifest: TimelineManifestV2): Map<string, TimelineManifestV2["boundaryEvidence"][number]> {
  const result = new Map<string, TimelineManifestV2["boundaryEvidence"][number]>();
  const occurrences = new Map<string, number>();
  for (const item of manifest.boundaryEvidence) {
    safeFrame(item.resolvedRecordFrame);
    const base = JSON.stringify([item.entityId, item.kind, item.relatedTokenId ?? null]);
    const next = occurrences.get(base) ?? 0;
    occurrences.set(base, next + 1);
    if (next > 0 && item.kind !== "independent_timing" || next > 1) fail("DUPLICATE_OWNER", "Duplicate boundary evidence key");
    const key = evidenceKey(item, next);
    if (result.has(key)) fail("DUPLICATE_OWNER", "Duplicate timing evidence");
    result.set(key, item);
  }
  return result;
}

function sameInventory<T>(before: Map<string, T>, after: Map<string, T>): boolean {
  return before.size === after.size && [...before.keys()].every((key) => after.has(key));
}

/** Compare structural and event boundaries only; the result is never a write receipt. */
export function compareSecondaryTimingV2(before: TimelineManifestV2, after: TimelineManifestV2): SecondaryTimingComparisonV2 {
  if (before.schemaVersion !== "timeline-manifest/v2" || after.schemaVersion !== "timeline-manifest/v2") {
    fail("INVALID_MANIFEST", "Expected two v2 manifests");
  }
  const aRate = rate(before.timeline.frameRate);
  const bRate = rate(after.timeline.frameRate);
  if (BigInt(aRate.numerator) * BigInt(bRate.denominator) !== BigInt(bRate.numerator) * BigInt(aRate.denominator)) {
    fail("RATE_MISMATCH", "Record frame rates differ");
  }
  if (before.document.documentId !== after.document.documentId || before.document.projectId !== after.document.projectId ||
      before.document.textHash !== after.document.textHash || before.document.settingsHash !== after.document.settingsHash) {
    fail("DOCUMENT_MISMATCH", "Document, text or settings authority differs");
  }
  if (!sameAuthoringJsonV2(before.compiler, after.compiler) ||
      !sameAuthoringJsonV2(before.authoringDefaults, after.authoringDefaults) ||
      !sameAuthoringJsonV2(before.sources, after.sources) ||
      !sameAuthoringJsonV2(before.preparationBindings, after.preparationBindings) ||
      !sameAuthoringJsonV2(before.tracks, after.tracks) || !sameAuthoringJsonV2(before.roles, after.roles) ||
      !sameAuthoringJsonV2(before.supportingItemResults, after.supportingItemResults) ||
      !sameAuthoringJsonV2(before.transitions ?? [], after.transitions ?? [])) {
    fail("EVIDENCE_MISMATCH", "Compiler, prepared source or ancillary authority changed");
  }
  for (const manifest of [before, after]) {
    safeFrame(manifest.timeline.startFrame);
    safeFrame(manifest.timeline.durationFrames);
    if (manifest.timeline.durationFrames !== manifest.durationBasis.recordFrames) fail("INCONSISTENT_RANGE", "Duration basis differs from record clock");
  }
  if (before.timeline.startFrame !== after.timeline.startFrame || before.timeline.width !== after.timeline.width ||
      before.timeline.height !== after.timeline.height || before.timeline.audioSampleRate !== after.timeline.audioSampleRate ||
      before.durationBasis.kind !== after.durationBasis.kind || before.durationBasis.entityId !== after.durationBasis.entityId ||
      before.durationBasis.narrationTimingMapHash !== after.durationBasis.narrationTimingMapHash ||
      !sameAuthoringJsonV2(before.durationBasis.sourceRange, after.durationBasis.sourceRange) ||
      before.durationBasis.kind === "narration_spine" && before.timeline.durationFrames !== after.timeline.durationFrames) {
    fail("EVIDENCE_MISMATCH", "Frozen narration spine, duration basis or record settings changed");
  }
  const oldEvents = indexEvents(before), newEvents = indexEvents(after);
  const oldOwners = indexOwners(before, oldEvents), newOwners = indexOwners(after, newEvents);
  if (!sameInventory(oldOwners, newOwners) || !sameInventory(oldEvents, newEvents)) {
    fail("STRUCTURE_CHANGED", "Event or visual owner inventory changed");
  }
  if (before.composition.topology !== after.composition.topology ||
      before.composition.rootContinuous !== true || after.composition.rootContinuous !== true ||
      !sameAuthoringJsonV2(before.composition.primaryRootTrackId, after.composition.primaryRootTrackId) ||
      !sameAuthoringJsonV2(before.composition.childTrackIds, after.composition.childTrackIds) ||
      !sameAuthoringJsonV2(before.composition.overlayTrackIds, after.composition.overlayTrackIds) ||
      !sameAuthoringJsonV2(before.composition.returns.map(({ returnSlotId, rootEventId }) => ({ returnSlotId, rootEventId })).sort((a,b) => compareKeys(a.returnSlotId,b.returnSlotId)),
        after.composition.returns.map(({ returnSlotId, rootEventId }) => ({ returnSlotId, rootEventId })).sort((a,b) => compareKeys(a.returnSlotId,b.returnSlotId)))) {
    fail("STRUCTURE_CHANGED", "Root/child/return topology changed");
  }
  const oldEvidence = indexEvidence(before), newEvidence = indexEvidence(after);
  if (!sameInventory(oldEvidence, newEvidence)) fail("EVIDENCE_MISMATCH", "Timing evidence inventory changed");
  for (const [key, original] of oldEvidence) {
    const candidate = newEvidence.get(key)!;
    const independent = original.kind === "independent_timing";
    if (original.precision !== candidate.precision || original.boundaryEvidenceHash !== candidate.boundaryEvidenceHash ||
        original.boundaryEvidenceMethod !== candidate.boundaryEvidenceMethod ||
        original.wordRelation !== candidate.wordRelation ||
        !independent && (!sameAuthoringJsonV2(original.inputTime, candidate.inputTime) ||
          original.resolvedRecordFrame !== candidate.resolvedRecordFrame || !sameAuthoringJsonV2(original.delta, candidate.delta))) {
      fail("EVIDENCE_MISMATCH", "Narration anchor, evidence hash or precision changed");
    }
  }
  const boundaries = [...oldOwners.entries()].sort(([a],[b]) => compareKeys(a,b)).map(([key, a]) => {
    const b = newOwners.get(key)!;
    if (a.relation !== b.relation || a.sequenceId !== b.sequenceId || a.boundaryKind !== b.boundaryKind ||
        a.structuralSlotIndex !== b.structuralSlotIndex || a.payloadId !== b.payloadId ||
        a.hostState !== b.hostState || a.presenterChoice !== b.presenterChoice ||
        a.boundaryEvidenceHash !== b.boundaryEvidenceHash || a.boundaryEvidenceMethod !== b.boundaryEvidenceMethod ||
        a.alignmentPrecision !== b.alignmentPrecision ||
        !sameAuthoringJsonV2(a.eventIds, b.eventIds) ||
        !sameAuthoringJsonV2(a.sourceTimeMapping, b.sourceTimeMapping) ||
        a.preparationRequirementKey !== b.preparationRequirementKey) {
      fail("STRUCTURE_CHANGED", "Boundary grammar, precision or source ownership changed");
    }
    if ((a.sourceRange === null) !== (b.sourceRange === null) ||
        a.sourceRange && b.sourceRange && a.sourceRange.startFrame !== b.sourceRange.startFrame) {
      fail("EVIDENCE_MISMATCH", "A visual cut cannot silently change its source inpoint");
    }
    const left = structuralRange(a), right = structuralRange(b);
    return {
      blockId: a.blockId, sequenceId: a.sequenceId, ownerId: ownerId(a), relation: a.relation,
      boundaryKind: a.boundaryKind,
      beforeFrame: a.resolvedRecordFrame, afterFrame: b.resolvedRecordFrame,
      deltaFrames: safeDelta(a.resolvedRecordFrame, b.resolvedRecordFrame),
      beforeRange: left, afterRange: right,
      durationDeltaFrames: left && right ? safeDelta(duration(left), duration(right)) : null,
      beforeSourceRange: optionalRange(a.sourceRange), afterSourceRange: optionalRange(b.sourceRange),
      beforePrecision: a.alignmentPrecision, afterPrecision: b.alignmentPrecision,
      boundaryEvidenceHash: a.boundaryEvidenceHash ?? null,
    } satisfies SecondaryBoundaryDifferenceV2;
  });
  const visualEvents: SecondaryVisualEventDifferenceV2[] = [];
  for (const [key, a] of [...oldEvents.entries()].sort(([x],[y]) => compareKeys(x,y))) {
    const b = newEvents.get(key)!;
    if (a.kind !== b.kind || a.trackRole !== b.trackRole || a.trackId !== b.trackId ||
        !sameAuthoringJsonV2(a.provenance, b.provenance) ||
        !sameAuthoringJsonV2(a.sourceTimeMapping, b.sourceTimeMapping) ||
        a.preparationBindingHash !== b.preparationBindingHash ||
        !sameAuthoringJsonV2(a.audio, b.audio) || !sameAuthoringJsonV2(a.pictureTreatment, b.pictureTreatment)) {
      fail("EVIDENCE_MISMATCH", "Event source, audio or delivery authority changed");
    }
    if ((a.sourceRange === null) !== (b.sourceRange === null) ||
        a.sourceRange && b.sourceRange && a.sourceRange.startFrame !== b.sourceRange.startFrame) {
      fail("EVIDENCE_MISMATCH", "Event source inpoint changed");
    }
    const visual = a.kind === "primary_visual" || a.kind === "overlay_visual" || a.kind === "placeholder";
    if (!visual && (!sameAuthoringJsonV2(a.recordRange, b.recordRange) || !sameAuthoringJsonV2(a.sourceRange, b.sourceRange))) {
      fail("EVIDENCE_MISMATCH", "Narration, audio or marker changed outside visual timing");
    }
    if (!visual) continue;
    const blockId = a.provenance.blockId || fail("STRUCTURE_CHANGED", "Visual event lacks stable block");
    const ownerId = a.provenance.overlayEventId ?? a.provenance.slotId ?? a.provenance.payloadId ??
      fail("STRUCTURE_CHANGED", "Visual event lacks stable owner");
    visualEvents.push({
      eventId: a.eventId, blockId, ownerId, kind: a.kind,
      beforeRange: safeRange(a.recordRange), afterRange: safeRange(b.recordRange),
      startDeltaFrames: safeDelta(a.recordRange.startFrame, b.recordRange.startFrame),
      endDeltaFrames: safeDelta(a.recordRange.endFrame, b.recordRange.endFrame),
      durationDeltaFrames: safeDelta(duration(a.recordRange), duration(b.recordRange)),
      beforeSourceRange: optionalRange(a.sourceRange), afterSourceRange: optionalRange(b.sourceRange),
    });
  }
  return {
    schemaVersion: "secondary-timing-comparison/v1", disposition: "proposed_not_applied",
    frameRate: aRate,
    before: { revision: before.document.revision, contentHash: before.document.contentHash },
    after: { revision: after.document.revision, contentHash: after.document.contentHash },
    boundaries, visualEvents,
  };
}
