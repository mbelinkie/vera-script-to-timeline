import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  Ajv2020,
  type AnySchemaObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import type {
  BuildReportV2 as PackageBuildReportV2,
  CompilerDependenciesV2 as PackageCompilerDependenciesV2,
  CompilerResultV2 as PackageCompilerResultV2,
  PresenterAlignmentResolutionV1 as PackagePresenterAlignmentResolutionV1,
  TimelineManifestV2 as PackageTimelineManifestV2,
  VeraContractsV2,
} from "@vera/contracts/v2";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const fixturesDirectory = `${repositoryRoot}tests/data/authoring_v2/`;
type DependencyFixture = {
  document: Record<string, unknown>;
  timeline: Record<string, unknown>;
  preparedMedia: Array<Record<string, unknown>>;
  narrationTimingMaps: Array<{
    precision: string;
    tokens: Array<Record<string, unknown>>;
  }>;
};
type ReportFixture = {
  diagnostics: Array<{ evidence: { kind: string } }>;
  recoveryActions: unknown[];
  migrationIssues: Array<{ kind: string }>;
  status: string;
  readiness: { preview: string };
};
type TimelineEventFixture = {
  kind: string;
  trackRole: string;
  audio: unknown;
  sourceRange: unknown;
  sourceTimeMapping: unknown;
  preparationBindingHash: unknown;
};
type ManifestFixture = { events: TimelineEventFixture[] };
const schemaIds = {
  document: "https://schemas.vera.video/contracts/script-document-v2.schema.json",
  settings:
    "https://schemas.vera.video/contracts/authoring-project-settings-v1.schema.json",
  dependencies:
    "https://schemas.vera.video/contracts/compiler-dependencies-v2.schema.json",
  manifest:
    "https://schemas.vera.video/contracts/timeline-manifest-v2.schema.json",
  report: "https://schemas.vera.video/contracts/build-report-v2.schema.json",
};

function readFixture<T>(name: string): T {
  return JSON.parse(readFileSync(`${fixturesDirectory}${name}`, "utf8")) as T;
}

const schemas: AnySchemaObject[] = [
  "script-document-v2.schema.json",
  "authoring-project-settings-v1.schema.json",
  "compiler-dependencies-v2.schema.json",
  "timeline-manifest-v2.schema.json",
  "build-report-v2.schema.json",
].map((name) =>
  JSON.parse(readFileSync(`${repositoryRoot}contracts/${name}`, "utf8")) as AnySchemaObject,
);
const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
for (const schema of schemas) {
  ajv.addSchema(schema);
}

function validator(uri: string): ValidateFunction {
  const found = ajv.getSchema(uri);
  if (!found) {
    throw new Error(`Missing registered schema: ${uri}`);
  }
  return found;
}

const validateDependencies = validator(schemaIds.dependencies);
const validateManifest = validator(schemaIds.manifest);
const validateReport = validator(schemaIds.report);
const validatePresenterAlignmentResolution = validator(
  `${schemaIds.dependencies}#/$defs/PresenterAlignmentResolutionV1`,
);
const validateOccurrenceOwner = validator(
  `${schemaIds.dependencies}#/$defs/OccurrenceOwnerV2`,
);
const validateDiagnosticEvidence = validator(
  `${schemaIds.report}#/$defs/DiagnosticEvidenceV2`,
);
const validateBuildDiagnostic = validator(`${schemaIds.report}#/$defs/BuildDiagnosticV2`);
const validateRecoveryAction = validator(`${schemaIds.report}#/$defs/RecoveryActionV2`);
const validateCompilerResult = validator(`${schemaIds.report}#/$defs/CompilerResultV2`);
const validateTimelineEvent = validator(`${schemaIds.manifest}#/$defs/TimelineEventV2`);
const validateDurationBasis = validator(`${schemaIds.manifest}#/$defs/DurationBasisV2`);
const validateSupportResult = validator(
  `${schemaIds.manifest}#/$defs/SupportingItemResultV2`,
);
const validateBoundaryEvidence = validator(`${schemaIds.manifest}#/$defs/BoundaryEvidenceV2`);
const validateMigrationIssue = validator(`${schemaIds.report}#/$defs/MigrationDiagnosticV2`);

const ids = {
  document: "00000000-0000-4000-8000-000000000001",
  block: "00000000-0000-4000-8000-000000000006",
  sequence: "00000000-0000-4000-8000-000000000009",
  slot: "00000000-0000-4000-8000-000000000010",
  payload: "00000000-0000-4000-8000-000000000011",
  take: "00000000-0000-4000-8000-000000000012",
  master: "00000000-0000-4000-8000-000000000013",
  token: "00000000-0000-4000-8000-000000000014",
  event: "00000000-0000-4000-8000-000000000016",
};

const frameRange = { startFrame: 0, endFrame: 10 };
const entity = { kind: "document", id: ids.document, path: "document" };

function expectValid(validate: ValidateFunction, value: unknown): void {
  expect(validate(value), JSON.stringify(validate.errors, null, 2)).toBe(true);
}

describe("v2 compiler, timeline, and build report contracts", () => {
  it("compiles the Draft 2020-12 schemas together and accepts frozen synthetic roots", () => {
    const dependencies = readFixture("compiler-dependencies-v2.json");
    const manifest = readFixture<PackageTimelineManifestV2>(
      "timeline-manifest-v2.json",
    );
    const report = readFixture<PackageBuildReportV2>("build-report-v2.json");

    expectValid(validateDependencies, dependencies);
    expectValid(validateManifest, manifest);
    expectValid(validateReport, report);
  });

  it("types presenter alignment while leaving word matching to semantic validation", () => {
    const dependencies = readFixture<PackageCompilerDependenciesV2>(
      "compiler-dependencies-v2.json",
    );
    const resolution: PackagePresenterAlignmentResolutionV1 = {
      schemaVersion: "presenter-alignment/v1",
      slotId: ids.slot,
      takeId: ids.take,
      masterIdentity: {
        masterId: ids.master,
        contentHash: `sha256:${"1".repeat(64)}`,
        probeHash: `sha256:${"2".repeat(64)}`,
        frameRate: { numerator: 30, denominator: 1 },
      },
      sourceStartFrame: 17,
      alignmentVersion: "presenter-alignment/v1",
      precision: "audible_word",
      expectedWord: { tokenId: ids.token, text: "Hello" },
      recognizedWord: { text: "Hello" },
    };

    expectValid(validatePresenterAlignmentResolution, resolution);
    const recordedDependencies = structuredClone(dependencies);
    recordedDependencies.presenterAlignmentResolutions = [resolution];
    expectValid(validateDependencies, recordedDependencies);

    const mismatchedWords = structuredClone(resolution);
    mismatchedWords.recognizedWord.text = "Hullo";
    expectValid(validatePresenterAlignmentResolution, mismatchedWords);

    const missingAlignmentPort = structuredClone(dependencies);
    delete (missingAlignmentPort as Partial<PackageCompilerDependenciesV2>)
      .presenterAlignmentResolutions;
    expect(validateDependencies(missingAlignmentPort)).toBe(false);

    const unsafeSourceFrame = structuredClone(resolution);
    unsafeSourceFrame.sourceStartFrame = Number.MAX_SAFE_INTEGER + 1;
    expect(validatePresenterAlignmentResolution(unsafeSourceFrame)).toBe(false);
  });

  it("pins the fixture source, compiler, and preparation profile hashes", () => {
    const descriptor = readFixture<{
      compiler: { sourceHash: string; profileHash: string };
      source: { contentHash: string; probeHash: string; descriptorHash: string };
      preparation: {
        requirementKey: string;
        policyHash: string;
        toolHash: string;
        profileHash: string;
        mappingHash: string;
        deliveredHash: string;
        probeHash: string;
      };
    }>("source-tool-profile.json");
    const dependencies = readFixture<PackageCompilerDependenciesV2>(
      "compiler-dependencies-v2.json",
    );
    const binding = dependencies.preparedMedia[0];
    const occurrence = dependencies.occurrenceResolutions[0];
    if (!binding || !occurrence) {
      throw new Error("Fixture must include source and preparation records");
    }

    expect(descriptor.compiler.sourceHash).toBe(dependencies.compiler.sourceHash);
    expect(descriptor.compiler.profileHash).toBe(dependencies.compiler.profileHash);
    expect(descriptor.source.contentHash).toBe(occurrence.sourceSnapshot.contentHash);
    expect(descriptor.source.probeHash).toBe(occurrence.sourceSnapshot.probeHash);
    expect(descriptor.source.descriptorHash).toBe(occurrence.sourceFrameMap.descriptorHash);
    expect(descriptor.preparation.requirementKey).toBe(binding.requirementKey);
    expect(descriptor.preparation.policyHash).toBe(binding.profile.policyHash);
    expect(descriptor.preparation.toolHash).toBe(binding.profile.toolHash);
    expect(descriptor.preparation.profileHash).toBe(binding.profile.profileHash);
    expect(descriptor.preparation.mappingHash).toBe(binding.timeMapping.mappingHash);
    expect(descriptor.preparation.deliveredHash).toBe(binding.verification.deliveredHash);
    expect(descriptor.preparation.probeHash).toBe(binding.verification.probeHash);
  });

  it("exposes generated TypeScript roots and the compiled-result union from @vera/contracts/v2", () => {
    type V2PackageRoots = Pick<
      VeraContractsV2,
      "compilerDependencies" | "timelineManifest" | "buildReport" | "compilerResult"
    >;
    const dependencies = readFixture<PackageCompilerDependenciesV2>(
      "compiler-dependencies-v2.json",
    );
    const manifest = readFixture<PackageTimelineManifestV2>(
      "timeline-manifest-v2.json",
    );
    const report = readFixture<PackageBuildReportV2>("build-report-v2.json");
    const compilerResult: PackageCompilerResultV2 = {
      kind: "compiled",
      manifest,
      report,
    };
    const roots: V2PackageRoots = {
      compilerDependencies: dependencies,
      timelineManifest: manifest,
      buildReport: report,
      compilerResult,
    };

    expect(roots.compilerResult.kind).toBe("compiled");
    expect(roots.compilerDependencies.schemaVersion).toBe("compiler-dependencies/v2");
  });

  it("keeps semantic mismatches representable as typed diagnostic evidence", () => {
    const report = readFixture<ReportFixture>("build-report-v2.json");
    const kinds = report.diagnostics.map(
      (diagnostic: { evidence: { kind: string } }) => diagnostic.evidence.kind,
    );

    expect(kinds).toContain("reference_mismatch");
    expect(kinds).toContain("rational_not_reduced");
    expect(kinds).toContain("source_mapping_mismatch");
    expect(kinds).toContain("occurrence_set_mismatch");
    for (const evidence of [
      { kind: "anchor_issue", anchorId: ids.block, reason: "stale" },
      {
        kind: "source_sufficiency",
        requiredRange: frameRange,
        availableRange: null,
      },
      { kind: "details", message: "Synthetic typed diagnostic detail" },
    ]) {
      expectValid(validateDiagnosticEvidence, evidence);
    }
    expect(report.migrationIssues[0]?.kind).toBe("legacy_state_requires_review");
  });

  it("accepts every occurrence owner, recovery action, and compiler result variant", () => {
    for (const owner of [
      { kind: "primary_slot", sequenceId: ids.sequence, slotId: ids.slot },
      { kind: "overlay_event", blockId: ids.block, overlayEventId: ids.event },
      { kind: "visual_only_block", blockId: ids.block },
    ]) {
      expectValid(validateOccurrenceOwner, owner);
    }

    const recoveryActions = [
      { kind: "repair_document", documentId: ids.document, entity, instruction: "Repair" },
      { kind: "refresh_timing", blockId: ids.block, expectedRevision: 1, instruction: "Refresh" },
      { kind: "rebind_media", occurrenceKey: "visual:1", mediaReferenceId: ids.payload, instruction: "Rebind" },
      { kind: "prepare_media", requirementKey: "prep:1", instruction: "Prepare" },
      { kind: "reattach_unplaced_item", supportingItemId: ids.event, instruction: "Reattach" },
      { kind: "select_supported_profile", profileHash: `sha256:${"a".repeat(64)}`, instruction: "Select" },
      { kind: "retry_stage", stage: "compilation", instruction: "Retry" },
      { kind: "manual_review", entity, instruction: "Review" },
      {
        kind: "REPLACE_TEMPORARY_PRESENTER",
        documentId: ids.document,
        slotId: ids.slot,
        instruction: "Choose a recorded take or temporary still",
      },
      { kind: "none", instruction: "No action" },
    ];
    for (const action of recoveryActions) {
      expectValid(validateRecoveryAction, action);
    }

    const manifest = readFixture<PackageTimelineManifestV2>(
      "timeline-manifest-v2.json",
    );
    const report = readFixture<PackageBuildReportV2>("build-report-v2.json");
    expectValid(validateCompilerResult, { kind: "compiled", manifest, report });
    expectValid(validateCompilerResult, {
      kind: "refused",
      diagnostics: report.diagnostics.slice(0, 1),
      recoveryActions: report.recoveryActions,
    });
  });

  it("retains typed presenter diagnostics and their recovery action", () => {
    for (const [code, severity] of [
      ["PRESENTER_ALIGNMENT_UNRESOLVED", "blocking"],
      ["TEMPORARY_PRESENTER_STILL", "info"],
    ]) {
      expectValid(validateBuildDiagnostic, {
        id: ids.event,
        severity,
        code,
        message: "Synthetic presenter evidence",
        entity: { kind: "slot", id: ids.slot, path: "presenterAlignment" },
        evidence: { kind: "details", message: "Expected/recognized word evidence is retained" },
        recoveryActionKinds: ["REPLACE_TEMPORARY_PRESENTER"],
      });
    }
  });

  it("covers event, duration, support-item, and migration discriminants", () => {
    const manifest = readFixture<ManifestFixture>("timeline-manifest-v2.json");
    const event = manifest.events[0];
    if (!event) {
      throw new Error("Fixture must include a timeline event");
    }
    const eventKinds = [
      "narration",
      "primary_visual",
      "overlay_visual",
      "source_audio",
      "placeholder",
      "script_marker",
    ];
    for (const kind of eventKinds) {
      const candidate = structuredClone(event);
      candidate.kind = kind;
      if (kind === "source_audio") {
        candidate.trackRole = "source_audio";
        candidate.audio = {
          audioPolicy: "quiet",
          levelPolicyVersion: "source-audio-level/v1",
          gainDb: -18,
          streamIndex: 0,
          audioHash: `sha256:${"f".repeat(64)}`,
          sampleRange: frameRange,
        };
      } else {
        candidate.audio = null;
      }
      if (kind !== "primary_visual" && kind !== "overlay_visual") {
        candidate.sourceRange = null;
        candidate.sourceTimeMapping = null;
        candidate.preparationBindingHash = null;
      }
      expectValid(validateTimelineEvent, candidate);
    }
    const fullAudioEvent = structuredClone(event);
    fullAudioEvent.kind = "source_audio";
    fullAudioEvent.trackRole = "source_audio";
    fullAudioEvent.audio = {
      audioPolicy: "full",
      levelPolicyVersion: "source-audio-level/v1",
      gainDb: 0,
      streamIndex: 0,
      audioHash: `sha256:${"f".repeat(64)}`,
      sampleRange: frameRange,
    };
    expectValid(validateTimelineEvent, fullAudioEvent);

    for (const kind of ["narration_spine", "visual_only_duration", "standalone_clip"]) {
      expectValid(validateDurationBasis, {
        kind,
        entityId: ids.block,
        recordFrames: 10,
        sourceRange: kind === "standalone_clip" ? frameRange : null,
        narrationTimingMapHash:
          kind === "narration_spine" ? `sha256:${"b".repeat(64)}` : null,
      });
    }
    for (const [disposition, recordRange, reason] of [
      ["placed", frameRange, null],
      ["unplaced", null, "Needs a placement"],
      ["omitted", null, null],
      ["blocked", null, "Blocked by source availability"],
    ]) {
      expectValid(validateSupportResult, {
        itemId: ids.event,
        version: 1,
        role: "picture",
        disposition,
        recordRange,
        reason,
      });
    }
    for (const kind of [
      "unplaced_item",
      "legacy_state_requires_review",
      "legacy_audio_policy_requires_repair",
    ]) {
      expectValid(validateMigrationIssue, {
        kind,
        severity: "warning",
        entity,
        message: "Synthetic migration diagnostic only",
        recoveryActionKind: "manual_review",
      });
    }
    for (const kind of [
      "word_start",
      "word_end",
      "media_end",
      "visual_only_duration",
      "complete_clip_duration",
      "independent_timing",
    ]) {
      expectValid(validateBoundaryEvidence, {
        entityId: ids.block,
        kind,
        inputTime: { numerator: 1, denominator: 2 },
        resolvedRecordFrame: 12,
        delta: { numerator: 0, denominator: 1 },
        precision: "unknown",
      });
    }
    for (const precision of [
      "audible_word",
      "next_word_derived",
      "between_words",
      "unknown",
      "visual_only_default",
      "complete_clip_quantized",
    ]) {
      expectValid(validateBoundaryEvidence, {
        entityId: ids.block,
        kind: "word_start",
        inputTime: { numerator: 1, denominator: 2 },
        resolvedRecordFrame: 12,
        delta: { numerator: 0, denominator: 1 },
        precision,
      });
    }
  });

  it("rejects missing bindings, unsafe integers, and invalid preparation modes", () => {
    const dependencies = readFixture<DependencyFixture>("compiler-dependencies-v2.json");
    const missingRevision = structuredClone(dependencies);
    delete missingRevision.document.revision;
    expect(validateDependencies(missingRevision)).toBe(false);

    const unsafeInteger = structuredClone(dependencies);
    unsafeInteger.timeline.durationFrames = Number.MAX_SAFE_INTEGER + 1;
    expect(validateDependencies(unsafeInteger)).toBe(false);

    const wrongPreparationMode = structuredClone(dependencies);
    const wrongModeBinding = wrongPreparationMode.preparedMedia[0];
    if (!wrongModeBinding) {
      throw new Error("Fixture must include a prepared-media binding");
    }
    wrongModeBinding.mode = "derived_cfr";
    expect(validateDependencies(wrongPreparationMode)).toBe(false);

    const derivedPreparation = structuredClone(dependencies);
    const derivedBinding = derivedPreparation.preparedMedia[0];
    if (!derivedBinding) {
      throw new Error("Fixture must include a prepared-media binding");
    }
    derivedBinding.mode = "derived_cfr";
    derivedBinding.derivation = {
      method: "cfr_sample/v1",
      sourceHash: `sha256:${"a".repeat(64)}`,
      outputHash: `sha256:${"b".repeat(64)}`,
      toolHash: `sha256:${"c".repeat(64)}`,
      profileHash: `sha256:${"d".repeat(64)}`,
      commandHash: `sha256:${"e".repeat(64)}`,
    };
    expectValid(validateDependencies, derivedPreparation);

    for (const precision of [
      "audible_word_marks",
      "next_word_derived",
      "sentence_only",
      "estimated",
    ]) {
      const variant = structuredClone(dependencies);
      const timingMap = variant.narrationTimingMaps[0];
      if (!timingMap) {
        throw new Error("Fixture must include a narration timing map");
      }
      timingMap.precision = precision;
      expectValid(validateDependencies, variant);
    }
    for (const endBasis of ["next_word_derived", "unknown"]) {
      const variant = structuredClone(dependencies);
      const token = variant.narrationTimingMaps[0]?.tokens[0];
      if (!token) {
        throw new Error("Fixture must include token timing");
      }
      token.endBasis = endBasis;
      delete token.audibleEnd;
      expectValid(validateDependencies, variant);
    }

    const report = readFixture<ReportFixture>("build-report-v2.json");
    const refusedReportRoot = structuredClone(report);
    refusedReportRoot.status = "refused";
    expect(validateReport(refusedReportRoot)).toBe(false);

    const readyReport = structuredClone(report);
    readyReport.status = "ready";
    readyReport.readiness.preview = "ready";
    expectValid(validateReport, readyReport);

    const staleReadiness = structuredClone(report);
    staleReadiness.status = "ready";
    expect(validateReport(staleReadiness)).toBe(false);
  });
});
