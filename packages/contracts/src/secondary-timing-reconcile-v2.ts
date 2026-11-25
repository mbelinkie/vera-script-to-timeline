/**
 * Pure, fail-closed feasibility for representable v2 timing edits. The output is
 * a proposed authoring document, NEVER a saved revision or a build receipt.
 * The API layer must verify trusted baseline artifacts and authorize/CAS writes.
 */
import type { CompilerDependenciesV2, FrameRangeV2, NarrationBlockV2, ScriptDocumentV2, TimelineManifestV2 } from "./generated/contracts-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "./compiler-core-v2.js";
import type { CompileDiagnosticV2, MediaRequirementV2 } from "./compiler-core-v2.js";
import { compareSecondaryTimingV2, SecondaryTimingComparisonErrorV2 } from "./secondary-timing-v2.js";
import type { SecondaryTimingComparisonV2 } from "./secondary-timing-v2.js";

export type SecondaryTimingReconcileCommandV2 =
  | { kind: "visual_only_duration"; blockId: string; expectedBlockVersion: number;
      expectedRange: FrameRangeV2; durationOverrideMs: number }
  | { kind: "overlay_duration"; blockId: string; overlayEventId: string; expectedEventVersion: number;
      expectedRange: FrameRangeV2; durationMs: number }
  | { kind: "primary_frame_offset"; blockId: string; slotId: string; expectedSequenceVersion: number;
      expectedBaselineFrame: number; deltaFrames: number };

export type SecondaryTimingReconcileCodeV2 =
  | "INVALID_INPUT" | "BASELINE_UNVERIFIED" | "STALE_TARGET" | "STALE_TIMING_MAP"
  | "PRIMARY_FRAME_OVERRIDE_UNREPRESENTABLE" | "UNSUPPORTED_TIMING_EDIT"
  | "INVALID_DURATION" | "NO_FRAME_CHANGE" | "SOURCE_INSUFFICIENT"
  | "RECONCILIATION_UNSAFE" | "COMPILATION_REFUSED";

export type SecondaryTimingReconcileResultV2 =
  | { ok: true; disposition: "proposed_not_applied"; candidateDocument: ScriptDocumentV2;
      comparison: SecondaryTimingComparisonV2; mediaRequirements: MediaRequirementV2[] }
  | { ok: false; disposition: "refused"; code: SecondaryTimingReconcileCodeV2;
      diagnostics: CompileDiagnosticV2[]; sourceSufficiency?: { requiredRange: FrameRangeV2; availableRange: FrameRangeV2 | null }[];
      proposedFrame?: number };

const refusal = (code: SecondaryTimingReconcileCodeV2, message: string, diagnostics: CompileDiagnosticV2[] = [],
  extra: { sourceSufficiency?: { requiredRange: FrameRangeV2; availableRange: FrameRangeV2 | null }[]; proposedFrame?: number } = {}): SecondaryTimingReconcileResultV2 =>
  ({ ok: false, disposition: "refused", code, diagnostics: diagnostics.length ? diagnostics : [{ code, message }], ...extra });

const isPositiveSafe = (value: number): boolean => Number.isSafeInteger(value) && value > 0;
const isSafeFrame = (value: number): boolean => Number.isSafeInteger(value) && value >= 0;
const sameRange = (a: FrameRangeV2, b: FrameRangeV2): boolean => !!b &&
  isSafeFrame(b.startFrame) && isSafeFrame(b.endFrame) && b.startFrame < b.endFrame &&
  a.startFrame === b.startFrame && a.endFrame === b.endFrame;
const mediaInput = (deps: CompilerDependenciesV2) => ({
  timing: deps.narrationTimingMaps,
  ...(deps.narrationBoundaryEvidence ? { boundaryEvidence: deps.narrationBoundaryEvidence } : {}),
  compilerVersion: deps.compiler.version,
    quietGapEvidence: deps.narrationQuietGapEvidence ?? [],
  defaults: deps.authoringDefaults,
  sourceDescriptors: deps.occurrenceResolutions,
  frameRate: deps.timeline.frameRate,
});

/** Compiles BOTH frozen inputs; no caller-provided manifest is trusted as a result. */
export function previewSecondaryTimingReconcileV2(
  document: ScriptDocumentV2,
  dependencies: CompilerDependenciesV2,
  baseline: TimelineManifestV2,
  command: SecondaryTimingReconcileCommandV2,
): SecondaryTimingReconcileResultV2 {
  if (!command || typeof command !== "object" || typeof command.kind !== "string") {
    return refusal("INVALID_INPUT", "A typed timing command is required.");
  }
  const validated = validateScriptDocumentV2(document);
  if (!validated.valid) return refusal("INVALID_INPUT", "The authored document is invalid.", validated.diagnostics);
  const original = compileTimelineV2(document, dependencies);
  if (!original.ok) return refusal("BASELINE_UNVERIFIED", "The frozen inputs cannot be compiled.", original.diagnostics);
  if (!sameAuthoringJsonV2(baseline, original.manifest)) {
    return refusal("BASELINE_UNVERIFIED", "Baseline manifest differs from the exactly recompiled frozen inputs.");
  }
  if (original.report.readiness.preview !== "ready") {
    return refusal("BASELINE_UNVERIFIED", "Baseline build has blocking diagnostics.",
      original.report.diagnostics.map((item) => ({ code: item.code, message: item.message })));
  }
  const originalNeeds = resolveMediaRequirementsV2(document, mediaInput(dependencies));
  if (!originalNeeds.ok) return refusal("BASELINE_UNVERIFIED", "Baseline source/anchor requirements are invalid.", originalNeeds.diagnostics);

  // Even preview-only primary frame nudges require the correct owner/version/frame,
  // but the approved closed content-slot contract cannot persist that offset.
  if (command.kind === "primary_frame_offset") {
    const row = document.activeDraft.blocks.find((item): item is NarrationBlockV2 => item.type === "narration" && item.id === command.blockId);
    const slot = row?.primaryVisualSequence?.slots.find((item) => item.id === command.slotId);
    const owner = baseline.visualSequenceResolutions.find((item) => item.blockId === command.blockId && item.slotId === command.slotId);
    if (!row || !slot || slot.kind !== "content" || row.primaryVisualSequence?.version !== command.expectedSequenceVersion ||
        !owner || owner.sequenceVersion !== command.expectedSequenceVersion || owner.resolvedRecordFrame !== command.expectedBaselineFrame ||
        !isSafeFrame(command.expectedBaselineFrame) || !Number.isSafeInteger(command.deltaFrames)) {
      return refusal("STALE_TARGET", "Primary owner, sequence version or compiled boundary is stale.");
    }
    const proposed = BigInt(command.expectedBaselineFrame) + BigInt(command.deltaFrames);
    if (proposed < 0n || proposed > BigInt(Number.MAX_SAFE_INTEGER)) {
      return refusal("INVALID_DURATION", "Proposed record boundary exceeds the safe frame range.");
    }
    return refusal("PRIMARY_FRAME_OVERRIDE_UNREPRESENTABLE",
      "A primary word/media-end boundary has no approved persisted frame-offset field; semantic anchors cannot be moved as a substitute.",
      [], { proposedFrame: Number(proposed) });
  }

  const candidate = structuredClone(document);
  let affectedEventId: string | null = null;
  if (command.kind === "visual_only_duration") {
    const block = candidate.activeDraft.blocks.find((item) => item.id === command.blockId);
    const event = baseline.events.find((item) => item.provenance.blockId === command.blockId &&
      item.provenance.slotId === null && (item.kind === "placeholder" || item.kind === "primary_visual"));
    if (block?.type !== "visual_only" || !event || block.version !== command.expectedBlockVersion ||
        !sameRange(event.recordRange, command.expectedRange)) return refusal("STALE_TARGET", "Visual-only owner, version or frame range is stale.");
    if (block.payload.pictureKind === "clip" || block.payload.pictureKind === "unresolved_visual" ||
        block.visualOnlyTiming.selectedSourceRange || block.researchClip) {
      return refusal("UNSUPPORTED_TIMING_EDIT", "Selected/complete clips cannot be stretched using a still-duration override.");
    }
    if (block.visualOnlyTiming.matchAudioDuration) {
      return refusal("UNSUPPORTED_TIMING_EDIT", "A visual matched to music derives its duration from the cue; clear the match before editing its fixed hold.");
    }
    if (!isPositiveSafe(command.durationOverrideMs)) return refusal("INVALID_DURATION", "Still duration must be positive safe integer milliseconds.");
    if (!isPositiveSafe(block.version) || block.version === Number.MAX_SAFE_INTEGER) {
      return refusal("INVALID_INPUT", "The visual-only row cannot advance its version safely.");
    }
    block.visualOnlyTiming.durationOverrideMs = command.durationOverrideMs;
    block.version += 1;
    affectedEventId = event.eventId;
  } else if (command.kind === "overlay_duration") {
    const row = candidate.activeDraft.blocks.find((item): item is NarrationBlockV2 => item.type === "narration" && item.id === command.blockId);
    const overlay = row?.overlayEvents.find((item) => item.id === command.overlayEventId);
    const event = baseline.events.find((item) => item.provenance.blockId === command.blockId &&
      item.provenance.overlayEventId === command.overlayEventId && item.kind === "overlay_visual");
    if (!overlay || !event || overlay.version !== command.expectedEventVersion ||
        !sameRange(event.recordRange, command.expectedRange)) return refusal("STALE_TARGET", "Overlay owner, version or frame range is stale.");
    if (!isPositiveSafe(command.durationMs)) return refusal("INVALID_DURATION", "Overlay duration must be positive safe integer milliseconds.");
    if (!((overlay.timing.start && !overlay.timing.end) || (!overlay.timing.start && overlay.timing.end))) {
      return refusal("UNSUPPORTED_TIMING_EDIT", "Overlay requires exactly one preserved authored anchor plus duration; two anchored edges cannot be retimed.");
    }
    if (!isPositiveSafe(overlay.version) || overlay.version === Number.MAX_SAFE_INTEGER) {
      return refusal("INVALID_INPUT", "The overlay cannot advance its version safely.");
    }
    overlay.timing.durationMs = command.durationMs;
    overlay.version += 1;
    affectedEventId = event.eventId;
  } else {
    return refusal("INVALID_INPUT", "Unknown secondary timing operation.");
  }

  const validatedCandidate = validateScriptDocumentV2(candidate);
  if (!validatedCandidate.valid) return refusal("INVALID_INPUT", "Proposed authoring structure is invalid.", validatedCandidate.diagnostics);
  // Resolve with compiler-core's *same* exact rational source mapping and
  // source-in / logical-end tests, before considering any edit representable.
  const needs = resolveMediaRequirementsV2(candidate, mediaInput(dependencies));
  const compiled = compileTimelineV2(candidate, dependencies);
  const blocked = compiled.ok ? compiled.report.sourceSufficiency.filter((item) => item.status !== "sufficient") : [];
  const sources = blocked.map((item) => ({ requiredRange: item.requiredRange, availableRange: item.availableRange }));
  if (!needs.ok || sources.length) {
    const diagnostics = needs.ok ? compiled.ok ? compiled.report.diagnostics.filter((item) => item.code === "SOURCE_INSUFFICIENT")
      .map((item) => ({ code: item.code, message: item.message })) : [] : needs.diagnostics;
    const short = sources.length || diagnostics.some((item) => item.code === "SOURCE_INSUFFICIENT");
    return refusal(short ? "SOURCE_INSUFFICIENT" : "RECONCILIATION_UNSAFE", "Exact media/anchor requirements refused the proposal.", diagnostics,
      sources.length ? { sourceSufficiency: sources } : {});
  }
  if (!compiled.ok) return refusal("COMPILATION_REFUSED", "The candidate did not compile with verified frozen inputs.", compiled.diagnostics);
  if (compiled.report.readiness.preview !== "ready") {
    return refusal("COMPILATION_REFUSED", "Candidate compiler found blocking build requirements.",
      compiled.report.diagnostics.map((item) => ({ code: item.code, message: item.message })));
  }
  try {
    const comparison = compareSecondaryTimingV2(baseline, compiled.manifest);
    if (comparison.boundaries.some((item) => item.deltaFrames !== 0 ||
        (item.durationDeltaFrames !== null && item.durationDeltaFrames !== 0)) ||
        comparison.visualEvents.some((item) => {
          if (item.eventId === affectedEventId) return false;
          if (item.startDeltaFrames === 0 && item.endDeltaFrames === 0 && item.durationDeltaFrames === 0) return false;
          // Later unanchored visual-only rows may translate rigidly when an
          // earlier still's duration changes; narration/overlays never may.
          const row = document.activeDraft.blocks.find((block) => block.id === item.blockId);
          return command.kind !== "visual_only_duration" || row?.type !== "visual_only" ||
            item.durationDeltaFrames !== 0 || item.startDeltaFrames !== item.endDeltaFrames;
        })) {
      return refusal("RECONCILIATION_UNSAFE", "A secondary edit would move a different visual owner or a structural anchor.");
    }
    const affected = comparison.visualEvents.find((item) => item.eventId === affectedEventId);
    if (!affected || affected.durationDeltaFrames === 0) return refusal("NO_FRAME_CHANGE", "The proposed duration quantizes to the same record interval.");
    if (command.kind === "overlay_duration" && affected.startDeltaFrames !== 0 && affected.endDeltaFrames !== 0) {
      return refusal("RECONCILIATION_UNSAFE", "Overlay duration edit moved both authored endpoints.");
    }
    return { ok: true, disposition: "proposed_not_applied", candidateDocument: candidate, comparison, mediaRequirements: needs.requirements };
  } catch (error) {
    if (error instanceof SecondaryTimingComparisonErrorV2) {
      return refusal("RECONCILIATION_UNSAFE", `${error.code}: ${error.message}`);
    }
    throw error;
  }
}
