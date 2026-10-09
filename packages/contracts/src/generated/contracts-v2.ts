/**
 * Generated from /contracts by npm run generate:contracts.
 * Do not edit by hand.
 */
/* eslint-disable @typescript-eslint/no-duplicate-type-constituents -- JSON Schema conditionals repeat shared token fields. */

export type NarrationBlockV2 = {
  [k: string]: unknown;
} & {
  type: "narration";
  id: string;
  orderKey: string;
  text: string;
  /**
   * @minItems 1
   */
  tokens: [NarrationToken, ...NarrationToken[]];
  /**
   * Optional typed narration annotations. Omission is equivalent to an empty array.
   */
  annotations?: NarrationAnnotation[];
  /**
   * Optional explicit performance beats. Omission or an empty array derives deterministic sentence beats at export time.
   */
  performanceBeats?: PerformanceBeat[];
  primaryVisualSequence?: PrimaryVisualSequence;
  overlayEvents: OverlayEventV2[];
  timingPolicy: "narration_spine";
  state: "active" | "excluded";
  notes: string[];
  version: number;
};
export type NarratedVisualPayloadV2 = {
  [k: string]: unknown;
} & {
  kind: "visual";
  payloadId: string;
  pictureKind:
    | "unresolved_visual"
    | "clip"
    | "image"
    | "capture"
    | "graphic"
    | "intentional_placeholder";
  source:
    | MediaReferenceSource
    | CaptureRevisionSource
    | GraphicRevisionSource
    | UnresolvedVisualSource
    | IntentionalPlaceholderSource
    | UrlSource;
  sourceUsage: SourceUsage | null;
  audioPolicy: "mute" | "quiet";
  framingPolicy: "contain" | "cover" | "native";
};
export type TimedPlacement = (
  | {
      start: unknown;
      end: unknown;
      [k: string]: unknown;
    }
  | {
      start: unknown;
      durationMs: unknown;
      [k: string]: unknown;
    }
  | {
      end: unknown;
      durationMs: unknown;
      [k: string]: unknown;
    }
) & {
  kind: "timed";
  start?:
    | {
        kind: "word";
        anchor: WordInpointAnchor;
      }
    | {
        kind: "between_blocks";
        beforeBlockId: string;
        afterBlockId: string;
      }
    | {
        kind: "event_edge";
        eventId: string;
        edge: "start" | "end";
      };
  end?:
    | {
        kind: "word";
        anchor: WordInpointAnchor;
      }
    | {
        kind: "between_blocks";
        beforeBlockId: string;
        afterBlockId: string;
      }
    | {
        kind: "event_edge";
        eventId: string;
        edge: "start" | "end";
      };
  durationMs?: number;
};
export type VisualOnlyBlockV2 = {
  [k: string]: unknown;
} & {
  type: "visual_only";
  id: string;
  orderKey: string;
  payload: StandaloneVisualPayloadV2;
  visualOnlyTiming: VisualOnlyTimingV2;
  version: number;
};
export type StandaloneVisualPayloadV2 = {
  [k: string]: unknown;
} & {
  kind: "visual";
  payloadId: string;
  pictureKind: "clip" | "image" | "capture" | "graphic" | "intentional_placeholder";
  source:
    | MediaReferenceSource
    | CaptureRevisionSource
    | GraphicRevisionSource
    | UnresolvedVisualSource
    | IntentionalPlaceholderSource
    | UrlSource;
  audioPolicy: "mute" | "quiet" | "full";
  framingPolicy: "contain" | "cover" | "native";
};
export type SupportingItemV2 = {
  [k: string]: unknown;
} & {
  id: string;
  version: number;
  orderKey: string;
  role:
    "picture" | "audio_cue" | "citation" | "editor_note" | "draft_note" | "reference";
  content: string;
  pictureKind?:
    | "unresolved_visual"
    | "clip"
    | "image"
    | "capture"
    | "graphic"
    | "intentional_placeholder";
  source?:
    | MediaReferenceSource
    | CaptureRevisionSource
    | GraphicRevisionSource
    | UnresolvedVisualSource
    | IntentionalPlaceholderSource
    | UrlSource;
  placement: UnplacedPlacement | RangePlacement | PointPlacement | TimedPlacement;
  displayAttachment?:
    | TextAnchorRange
    | (
        | {
            kind: "word";
            anchor: WordInpointAnchor;
          }
        | {
            kind: "between_blocks";
            beforeBlockId: string;
            afterBlockId: string;
          }
        | {
            kind: "event_edge";
            eventId: string;
            edge: "start" | "end";
          }
      );
};
export type TokenTimingV2 = {
  [k: string]: unknown;
} & {
  [k: string]: unknown;
} & {
  tokenId: string;
  startOffset: number;
  endOffset: number;
  quotedText: string;
  startTime: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  audibleEnd?: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  endBasis: "evidenced_audible_end" | "next_word_derived" | "unknown";
} & {
  tokenId: string;
  startOffset: number;
  endOffset: number;
  quotedText: string;
  startTime: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  audibleEnd?: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  endBasis: "evidenced_audible_end" | "next_word_derived" | "unknown";
};
export type PreparedMediaBindingV1 = {
  [k: string]: unknown;
} & {
  requirementKey: string;
  mode: "verified_reuse" | "derived_cfr";
  originalSource: {
    mediaReferenceId: string;
    contentHash: string;
    probeHash: string;
  };
  targetRate: RationalRate;
  requestedRange: RequestedPreparationRangeV1;
  profile: PreparationProfileV1;
  timeMapping: PreparationTimeMappingV1;
  verification: PreparedMediaVerificationV1;
  authorizationReference: string;
  artifactLocator: string;
  derivation?: PreparationDerivationV1;
};
export type TimelineEventV2 = {
  [k: string]: unknown;
} & {
  eventId: string;
  kind:
    | "narration"
    | "primary_visual"
    | "overlay_visual"
    | "source_audio"
    | "placeholder"
    | "script_marker";
  trackId: string;
  trackRole:
    | "primary_root"
    | "child"
    | "overlay"
    | "presenter"
    | "narration"
    | "source_audio"
    | "placeholder"
    | "marker"
    | "subtitle";
  recordRange: FrameRangeV2;
  provenance: EventProvenanceV2;
  sourceRange: FrameRangeV2 | null;
  sourceTimeMapping: PreparationTimeMappingV1 | null;
  preparationBindingHash: string | null;
  audio: SourceAudioEventV2 | null;
};
export type SourceAudioEventV2 = {
  [k: string]: unknown;
} & {
  audioPolicy: "quiet" | "full";
  levelPolicyVersion: string;
  gainDb: -18 | 0;
  streamIndex: number;
  audioHash: string;
  sampleRange: FrameRangeV2;
};
export type SupportingItemResultV2 = {
  [k: string]: unknown;
} & {
  itemId: string;
  version: number;
  role:
    "picture" | "audio_cue" | "citation" | "editor_note" | "draft_note" | "reference";
  disposition: "placed" | "unplaced" | "omitted" | "blocked";
  recordRange: FrameRangeV2 | null;
  reason: string | null;
};
/**
 * Versioned report for one frozen v2 build, including typed diagnostics, source sufficiency, preparation state, migration issues, readiness, and recovery actions.
 */
export type BuildReportV2 = {
  [k: string]: unknown;
} & {
  schemaVersion: "build-report/v2";
  id: string;
  buildId: string;
  buildClass: "preview" | "release";
  status: "ready" | "blocked";
  document: DocumentBindingV2;
  compiler: CompilerIdentityV2;
  dependenciesHash: string;
  manifest: ManifestReferenceV2;
  timeline: TimelineSettingsV2;
  summary: BuildSummaryV2;
  eventResults: EventResultV2[];
  itemResults: SupportingItemResultV2[];
  diagnostics: BuildDiagnosticV2[];
  recoveryActions: (
    | {
        kind: "repair_document";
        documentId: string;
        entity: EntityReferenceV2;
        instruction: string;
      }
    | {
        kind: "REPLACE_TEMPORARY_PRESENTER";
        documentId: string;
        slotId: string;
        instruction: string;
      }
    | {
        kind: "refresh_timing";
        blockId: string;
        expectedRevision: number;
        instruction: string;
      }
    | {
        kind: "rebind_media";
        occurrenceKey: string;
        mediaReferenceId: string;
        instruction: string;
      }
    | {
        kind: "prepare_media";
        requirementKey: string;
        instruction: string;
      }
    | {
        kind: "reattach_unplaced_item";
        supportingItemId: string;
        instruction: string;
      }
    | {
        kind: "select_supported_profile";
        profileHash: string;
        instruction: string;
      }
    | {
        kind: "retry_stage";
        stage: "narration" | "preparation" | "compilation";
        instruction: string;
      }
    | {
        kind: "manual_review";
        entity: EntityReferenceV2;
        instruction: string;
      }
    | {
        kind: "none";
        instruction: string;
      }
  )[];
  mediaPreparation: MediaPreparationSummaryV2;
  sourceSufficiency: SourceSufficiencyV2[];
  migrationIssues: MigrationDiagnosticV2[];
  readiness: ReadinessV2;
  manualCompletionItems: ManualCompletionItemV2[];
};
export type SourceSufficiencyV2 = {
  [k: string]: unknown;
} & {
  requirementKey: string;
  status: "sufficient" | "insufficient" | "unknown";
  requiredRange: FrameRangeV2;
  availableRange: FrameRangeV2 | null;
  diagnosticId: string | null;
};
/**
 * A refused result has diagnostics and recovery guidance only; a compiled result always carries both a manifest and report, including when the report is blocked.
 */
export type CompilerResultV2 =
  | {
      kind: "compiled";
      manifest: TimelineManifestV2;
      report: BuildReportV2;
    }
  | {
      kind: "refused";
      /**
       * @minItems 1
       */
      diagnostics: [BuildDiagnosticV2, ...BuildDiagnosticV2[]];
      recoveryActions: (
        | {
            kind: "repair_document";
            documentId: string;
            entity: EntityReferenceV2;
            instruction: string;
          }
        | {
            kind: "REPLACE_TEMPORARY_PRESENTER";
            documentId: string;
            slotId: string;
            instruction: string;
          }
        | {
            kind: "refresh_timing";
            blockId: string;
            expectedRevision: number;
            instruction: string;
          }
        | {
            kind: "rebind_media";
            occurrenceKey: string;
            mediaReferenceId: string;
            instruction: string;
          }
        | {
            kind: "prepare_media";
            requirementKey: string;
            instruction: string;
          }
        | {
            kind: "reattach_unplaced_item";
            supportingItemId: string;
            instruction: string;
          }
        | {
            kind: "select_supported_profile";
            profileHash: string;
            instruction: string;
          }
        | {
            kind: "retry_stage";
            stage: "narration" | "preparation" | "compilation";
            instruction: string;
          }
        | {
            kind: "manual_review";
            entity: EntityReferenceV2;
            instruction: string;
          }
        | {
            kind: "none";
            instruction: string;
          }
      )[];
    };

/**
 * Generated aggregate type surface for the VERA shared contracts.
 */
export interface VeraContractsV2 {
  scriptDocument: ScriptDocumentV2;
  authoringProjectSettings: AuthoringProjectSettingsV1;
  compilerDependencies: CompilerDependenciesV2;
  timelineManifest: TimelineManifestV2;
  buildReport: BuildReportV2;
  compilerResult: CompilerResultV2;
}
/**
 * Editor-independent ScriptDocument with structural primary visuals and independent overlay timing.
 */
export interface ScriptDocumentV2 {
  schemaVersion: "script-document/v2";
  id: string;
  projectId: string;
  title: string;
  scriptSettings?: ScriptSettings;
  activeDraft: ActiveDraft;
  /**
   * Reserved document surface; it remains empty until its owning contract is introduced.
   *
   * @maxItems 0
   */
  ideaOutline: never[];
  /**
   * Reserved document surface; it remains empty until its owning contract is introduced.
   *
   * @maxItems 0
   */
  extras: never[];
  liveHeadSequence: number;
  /**
   * Base64-encoded acknowledged collaborative state-vector evidence; it may be empty before collaboration exists.
   */
  liveStateVector: string;
  liveContentHash: string;
}
export interface ScriptSettings {
  presenterStillOverride?: PresenterStillReference;
}
export interface PresenterStillReference {
  mediaReferenceId: string;
  artifactId: string;
  artifactVersion: number;
  contentHash: string;
  /**
   * Canonical slash-separated project-relative locator; absolute paths and dot segments are not accepted.
   */
  projectRelativeLocator: string;
  width: number;
  height: number;
  provenance: LocalImportProvenance | CapturedFrameProvenance;
}
export interface LocalImportProvenance {
  origin: "local_import";
  originalFilename: string;
}
export interface CapturedFrameProvenance {
  origin: "captured_frame";
  sourceMediaReferenceId: string;
  sourceFrame: number;
}
export interface ActiveDraft {
  blocks: (
    | SectionBlock
    | NarrationBlockV2
    | DirectionBlock
    | VisualOnlyBlockV2
    | NoteDraftBlock
  )[];
  supportingItems: SupportingItemV2[];
}
export interface SectionBlock {
  type: "section";
  id: string;
  orderKey: string;
  title: string;
  version: number;
}
/**
 * Stable spoken-token identity plus UTF-16 offsets into NarrationBlockV2.text; text and offset agreement remains semantic validation.
 */
export interface NarrationToken {
  id: string;
  value: string;
  startOffset: number;
  endOffset: number;
}
/**
 * Typed, exact-range pronunciation or performance metadata. It is never spoken narration or provider syntax.
 */
export interface NarrationAnnotation {
  id: string;
  kind: "pronunciation_alias" | "pronunciation_phoneme" | "performance_note";
  range: TextAnchorRange;
  value: string;
  includeInPrompter: boolean;
  version: number;
}
/**
 * Exact authored text range. Token existence, order and quoted-text agreement remain semantic validation.
 */
export interface TextAnchorRange {
  blockId: string;
  startTokenId: string;
  endTokenId: string;
  startAffinity: "before" | "after";
  endAffinity: "before" | "after";
  quotedText: string;
  anchorVersion: number;
}
/**
 * Stable recording-take identity over an exact narration token range.
 */
export interface PerformanceBeat {
  id: string;
  range: TextAnchorRange;
  version: number;
}
export interface PrimaryVisualSequence {
  id: string;
  slots: (ContentSlot | ReturnSlot)[];
  version: number;
}
export interface ContentSlot {
  id: string;
  kind: "content";
  relation:
    | {
        kind: "base";
      }
    | {
        kind: "sequential";
      }
    | {
        kind: "cutaway";
        parentSlotId: string;
      };
  boundaryBefore:
    | {
        kind: "row_start";
      }
    | {
        kind: "spoken_word";
        anchor: WordInpointAnchor;
      }
    | {
        kind: "previous_media_end";
        controllingSlotId: string;
      };
  payload:
    | {
        kind: "on_camera";
        presenterChoiceId: string | null;
      }
    | NarratedVisualPayloadV2
    | {
        kind: "undefined";
        payloadId: string;
        description: string;
      };
  playoutPolicy: "match_structural_interval" | "complete_logged_clip";
  version: number;
}
export interface WordInpointAnchor {
  blockId: string;
  tokenId: string;
  affinity: "before";
  quotedWord: string;
  anchorVersion: number;
}
export interface MediaReferenceSource {
  kind: "media_reference";
  mediaReferenceId: string;
}
export interface CaptureRevisionSource {
  kind: "capture_revision";
  captureId: string;
  revisionId: string;
}
export interface GraphicRevisionSource {
  kind: "graphic_revision";
  graphicId: string;
  revisionId: string;
}
export interface UnresolvedVisualSource {
  kind: "unresolved_visual";
  description: string;
}
export interface IntentionalPlaceholderSource {
  kind: "intentional_placeholder";
  text: string;
}
export interface UrlSource {
  kind: "url";
  url: string;
}
export interface SourceUsage {
  sourceInFrame: number;
}
export interface ReturnSlot {
  id: string;
  kind: "return";
  parentSlotId: string;
  inpoint: WordInpointAnchor | null;
  version: number;
}
export interface OverlayEventV2 {
  id: string;
  payload: NarratedVisualPayloadV2;
  timing: TimedPlacement;
  version: number;
}
export interface DirectionBlock {
  type: "direction";
  id: string;
  orderKey: string;
  text: string;
  buildBehavior: "none" | "timeline_marker";
  version: number;
}
export interface VisualOnlyTimingV2 {
  kind: "visual_only";
  durationOverrideMs?: number;
  selectedSourceRange?: {
    startFrame: number;
    durationFrames: number;
  };
}
export interface NoteDraftBlock {
  type: "note_draft";
  id: string;
  orderKey: string;
  text: string;
  state: "excluded";
  version: number;
}
export interface UnplacedPlacement {
  kind: "unplaced";
  reason: string;
  priorAnchor?:
    | WordInpointAnchor
    | TextAnchorRange
    | (
        | {
            kind: "word";
            anchor: WordInpointAnchor;
          }
        | {
            kind: "between_blocks";
            beforeBlockId: string;
            afterBlockId: string;
          }
        | {
            kind: "event_edge";
            eventId: string;
            edge: "start" | "end";
          }
      );
  sourceOrderKey?: string;
  /**
   * @maxItems 2
   */
  neighboringBlockIds?: [] | [string] | [string, string];
}
export interface RangePlacement {
  kind: "range";
  range: TextAnchorRange;
}
export interface PointPlacement {
  kind: "point";
  anchor:
    | {
        kind: "word";
        anchor: WordInpointAnchor;
      }
    | {
        kind: "between_blocks";
        beforeBlockId: string;
        afterBlockId: string;
      }
    | {
        kind: "event_edge";
        eventId: string;
        edge: "start" | "end";
      };
}
/**
 * Narrow project-level authoring defaults with immutable presenter-still identity.
 */
export interface AuthoringProjectSettingsV1 {
  schemaVersion: "authoring-project-settings/v1";
  id: string;
  projectId: string;
  version: number;
  settingsHash: string;
  presenterStill?: PresenterStillReference1;
  visualOnlyStillDurationMs?: number;
}
export interface PresenterStillReference1 {
  mediaReferenceId: string;
  artifactId: string;
  artifactVersion: number;
  contentHash: string;
  /**
   * Canonical slash-separated project-relative locator; absolute paths and dot segments are not accepted.
   */
  projectRelativeLocator: string;
  width: number;
  height: number;
  provenance: LocalImportProvenance1 | CapturedFrameProvenance1;
}
export interface LocalImportProvenance1 {
  origin: "local_import";
  originalFilename: string;
}
export interface CapturedFrameProvenance1 {
  origin: "captured_frame";
  sourceMediaReferenceId: string;
  sourceFrame: number;
}
/**
 * Frozen v2 compiler inputs with occurrence-specific source maps, token timing, and verified preparation attestations.
 */
export interface CompilerDependenciesV2 {
  schemaVersion: "compiler-dependencies/v2";
  build: BuildIdentityV2;
  document: DocumentBindingV2;
  compiler: CompilerIdentityV2;
  authoringDefaults: AuthoringDefaultsV2;
  timeline: TimelineSettingsV2;
  /**
   * @minItems 1
   */
  tracks: [TrackV2, ...TrackV2[]];
  roles: TrackRolesV2;
  narrationTimingMaps: NarrationTokenTimingMapV2[];
  occurrenceResolutions: OccurrenceMediaResolutionV2[];
  preparedMedia: PreparedMediaBindingV1[];
  presenterAlignmentResolutions: PresenterAlignmentResolutionV1[];
}
export interface BuildIdentityV2 {
  buildId: string;
  manifestId: string;
  reportId: string;
  buildClass: "preview" | "release";
}
export interface DocumentBindingV2 {
  documentId: string;
  projectId: string;
  revision: number;
  liveHeadSequence: number;
  contentHash: string;
  textHash: string;
  settingsHash: string;
}
export interface CompilerIdentityV2 {
  version: string;
  sourceHash: string;
  profileHash: string;
}
export interface AuthoringDefaultsV2 {
  settingsHash: string;
  visualOnlyStillDurationMs: number;
  presenterStill: PresenterStillReference | null;
  sourceAudioLevelPolicy: {
    version: string;
    quietGainDb: -18;
    fullGainDb: 0;
  };
}
export interface TimelineSettingsV2 {
  frameRate: RationalRate;
  width: number;
  height: number;
  audioSampleRate: number;
  startFrame: number;
  durationFrames: number;
}
export interface RationalRate {
  numerator: number;
  denominator: number;
}
export interface TrackV2 {
  id: string;
  kind: "video" | "audio" | "subtitle";
  index: number;
  name: string;
}
export interface TrackRolesV2 {
  primaryRootTrackId: string;
  childTrackIds: string[];
  overlayTrackIds: string[];
  presenterTrackId: string;
  placeholderTrackId: string;
  narrationTrackId: string;
  sourceAudioTrackIds: string[];
  markerTrackId: string;
}
export interface NarrationTokenTimingMapV2 {
  blockId: string;
  blockRevision: number;
  textHash: string;
  tokenizationVersion: string;
  narrationAssetId: string;
  audioHash: string;
  timingHash: string;
  alignmentVersion: string;
  precision: "audible_word_marks" | "next_word_derived" | "sentence_only" | "estimated";
  /**
   * @minItems 1
   */
  tokens: [TokenTimingV2, ...TokenTimingV2[]];
}
/**
 * A reduced signed fraction of seconds. Reduction is checked by the compiler; this schema validates its safe-integer wire shape.
 */
export interface RationalTime {
  numerator: number;
  denominator: number;
}
export interface OccurrenceMediaResolutionV2 {
  payloadId: string;
  owner:
    | {
        kind: "primary_slot";
        sequenceId: string;
        slotId: string;
      }
    | {
        kind: "overlay_event";
        blockId: string;
        overlayEventId: string;
      }
    | {
        kind: "visual_only_block";
        blockId: string;
      };
  mediaReferenceId: string;
  sourceSnapshot: {
    system: "research" | "local_import" | "captured_frame" | "graphic_asset";
    snapshotId: string;
    version: number;
    packageId: string;
    contentHash: string;
    probeHash: string;
  };
  logicalSourceBounds: LogicalSourceBoundsV2;
  sourceFrameMap: SourceFrameMapV1;
  occurrenceSourceInFrame: number;
  selectedSourceRange: FrameRangeV2 | null;
  preparedMediaRequirementKey: string | null;
}
export interface LogicalSourceBoundsV2 {
  startFrame: number;
  endFrame: number;
  frameRate: RationalRate;
}
export interface SourceFrameMapV1 {
  packageFrameZeroLogicalFrame: number;
  packageVideoPtsOrigin: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  loggedTimeAtPackageFrameZero: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  decodedPackageFrameRate: RationalRate;
  decodedPackageFrameCount: number;
  packageVideoTimeBase: RationalRate;
  sourceAudioStreamMappings: SourceAudioStreamMappingV1[];
  descriptorHash: string;
  probeHash: string;
}
export interface SourceAudioStreamMappingV1 {
  streamIndex: number;
  sampleRate: number;
  packagePtsOrigin: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  loggedTimeAtPackageOrigin: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  audioHash: string;
  probeHash: string;
}
export interface FrameRangeV2 {
  startFrame: number;
  endFrame: number;
}
export interface RequestedPreparationRangeV1 {
  sourceInFrame: number;
  duration: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  preHandle: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  postHandle: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
}
export interface PreparationProfileV1 {
  policyHash: string;
  profileHash: string;
  toolHash: string;
  profileVersion: string;
}
export interface PreparationTimeMappingV1 {
  sourceOrigin: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  deliveredOrigin: RationalTime & {
    numerator?: number;
    [k: string]: unknown;
  };
  sourceRate: RationalRate;
  deliveredRate: RationalRate;
  sourceFrameMap: SourceFrameMapV1;
  mappingHash: string;
}
export interface PreparedMediaVerificationV1 {
  deliveredHash: string;
  probeHash: string;
  decodedFrameCount: number;
  decodedFrameRate: RationalRate;
  videoTimeBase: RationalRate;
  sourceAudio: {
    status: "aligned" | "absent" | "not_applicable" | "failed";
    offset: RationalTime | null;
    maxDrift:
      | (RationalTime & {
          numerator?: number;
          [k: string]: unknown;
        })
      | null;
    sampleRate: number | null;
  };
}
export interface PreparationDerivationV1 {
  method: "cfr_sample/v1";
  sourceHash: string;
  outputHash: string;
  toolHash: string;
  profileHash: string;
  commandHash: string;
}
export interface PresenterAlignmentResolutionV1 {
  schemaVersion: "presenter-alignment/v1";
  slotId: string;
  takeId: string;
  masterIdentity: {
    masterId: string;
    contentHash: string;
    probeHash: string;
    frameRate: RationalRate;
  };
  sourceStartFrame: number;
  alignmentVersion: string;
  precision: "audible_word" | "next_word_derived" | "between_words";
  expectedWord: {
    tokenId: string;
    text: string;
  };
  recognizedWord: {
    text: string;
  };
}
/**
 * Deterministic integer-frame v2 timeline with frozen source, timing, preparation, sequence, and boundary evidence.
 */
export interface TimelineManifestV2 {
  schemaVersion: "timeline-manifest/v2";
  id: string;
  buildId: string;
  buildClass: "preview" | "release";
  document: DocumentBindingV2;
  compiler: CompilerIdentityV2;
  authoringDefaults: AuthoringDefaultsV2;
  timeline: TimelineSettingsV2;
  /**
   * @minItems 1
   */
  tracks: [TrackV2, ...TrackV2[]];
  roles: TrackRolesV2;
  sources: ManifestSourceV2[];
  events: TimelineEventV2[];
  visualSequenceResolutions: VisualSequenceResolutionV2[];
  supportingItemResults: SupportingItemResultV2[];
  preparationBindings: PreparedMediaBindingV1[];
  durationBasis: DurationBasisV2;
  composition: CompositionEvidenceV2;
  boundaryEvidence: BoundaryEvidenceV2[];
}
export interface ManifestSourceV2 {
  id: string;
  mediaReferenceId: string;
  originalHash: string;
  originalProbeHash: string;
  deliveredHash: string;
  deliveredProbeHash: string;
  sourceFrameMap: SourceFrameMapV1;
  sourceTimeMapping: PreparationTimeMappingV1;
  preparationRequirementKey: string | null;
}
export interface EventProvenanceV2 {
  documentId: string;
  blockId: string | null;
  sequenceId: string | null;
  slotId: string | null;
  payloadId: string | null;
  overlayEventId: string | null;
  sourceId: string | null;
  originalSourceHash: string | null;
  deliveredSourceHash: string | null;
  timingMapHash: string | null;
  compilerVersion: string;
}
export interface VisualSequenceResolutionV2 {
  documentId: string;
  blockId: string;
  blockRevision: number;
  sequenceId: string;
  sequenceVersion: number;
  structuralSlotIndex: number;
  relation: "root" | "child" | "return";
  slotId: string | null;
  payloadId: string | null;
  returnSlotId: string | null;
  boundaryKind:
    | "word_start"
    | "word_end"
    | "between_blocks"
    | "event_edge"
    | "media_end"
    | "visual_only_start";
  resolvedRecordFrame: number;
  boundaryDelta: RationalTime;
  rootRanges: FrameRangeV2[];
  childRanges: FrameRangeV2[];
  topmostAppearances: {
    eventId: string;
    recordRange: FrameRangeV2;
  }[];
  hostState: "on_camera" | "voiceover";
  visualOrdinal: number | null;
  eventIds: string[];
  sourceRange: FrameRangeV2 | null;
  sourceTimeMapping: PreparationTimeMappingV1 | null;
  preparationRequirementKey: string | null;
  presenterChoice: "temporary_still" | "recorded" | "not_applicable";
  alignmentPrecision:
    | "audible_word"
    | "next_word_derived"
    | "between_words"
    | "unknown"
    | "not_applicable";
}
export interface DurationBasisV2 {
  kind: "narration_spine" | "visual_only_duration" | "standalone_clip";
  entityId: string;
  recordFrames: number;
  sourceRange: FrameRangeV2 | null;
  narrationTimingMapHash: string | null;
}
export interface CompositionEvidenceV2 {
  topology: "primary_root_child_overlay";
  primaryRootTrackId: string;
  childTrackIds: string[];
  overlayTrackIds: string[];
  rootContinuous: boolean;
  returns: ReturnResolutionV2[];
}
export interface ReturnResolutionV2 {
  returnSlotId: string;
  rootEventId: string;
  recordFrame: number;
  emitsNewSourceEvent: false;
}
export interface BoundaryEvidenceV2 {
  entityId: string;
  kind:
    | "word_start"
    | "word_end"
    | "media_end"
    | "visual_only_duration"
    | "complete_clip_duration"
    | "independent_timing";
  inputTime: RationalTime;
  resolvedRecordFrame: number;
  delta: RationalTime;
  precision:
    | "audible_word"
    | "next_word_derived"
    | "between_words"
    | "unknown"
    | "visual_only_default"
    | "complete_clip_quantized";
}
export interface ManifestReferenceV2 {
  id: string;
  contentHash: string;
}
export interface BuildSummaryV2 {
  sourceCount: number;
  eventCount: number;
  placedCount: number;
  placeholderCount: number;
  blockedCount: number;
  supportingItemCount: number;
  diagnosticCount: number;
  recoveryActionCount: number;
  manualCompletionCount: number;
}
export interface EventResultV2 {
  eventId: string;
  kind:
    | "narration"
    | "primary_visual"
    | "overlay_visual"
    | "source_audio"
    | "placeholder"
    | "script_marker";
  disposition: "placed" | "placeholder" | "manual_completion" | "blocked";
  sourceId: string | null;
  trackId: string | null;
  recordRange: FrameRangeV2 | null;
  message: string;
}
export interface BuildDiagnosticV2 {
  id: string;
  severity: "info" | "warning" | "error" | "blocking";
  code:
    | "INVALID_DOCUMENT"
    | "STALE_DOCUMENT_REVISION"
    | "DOCUMENT_HASH_MISMATCH"
    | "TEXT_HASH_MISMATCH"
    | "STALE_TIMING_MAP"
    | "TIMING_HASH_MISMATCH"
    | "WORD_TIMING_REQUIRED"
    | "MISSING_OCCURRENCE_BINDING"
    | "EXTRA_OCCURRENCE_BINDING"
    | "STALE_MEDIA_HASH"
    | "PREPARATION_HASH_MISMATCH"
    | "RATIONAL_NOT_REDUCED"
    | "SOURCE_MAPPING_MISMATCH"
    | "SOURCE_INSUFFICIENT"
    | "UNSUPPORTED_FRAME_RATE"
    | "STALE_ANCHOR"
    | "COLLAPSED_BOUNDARY"
    | "UNPLACED_SUPPORTING_ITEM"
    | "VISUAL_UNDEFINED"
    | "SOURCE_AUDIO_OVERLAP"
    | "TRACK_ROLE_COLLISION"
    | "MIGRATION_REVIEW_REQUIRED"
    | "PRESENTER_ALIGNMENT_UNRESOLVED"
    | "TEMPORARY_PRESENTER_STILL";
  message: string;
  entity: EntityReferenceV2;
  evidence:
    | {
        kind: "reference_mismatch";
        referenceType:
          | "document_revision"
          | "document_hash"
          | "text_hash"
          | "timing_hash"
          | "media_hash"
          | "preparation_hash";
        expected: string;
        actual: string;
      }
    | {
        kind: "rational_not_reduced";
        numerator: number;
        denominator: number;
        greatestCommonDivisor: number;
      }
    | {
        kind: "source_mapping_mismatch";
        expectedSourceTime: RationalTime;
        actualSourceTime: RationalTime;
        frameIndex: number;
      }
    | {
        kind: "occurrence_set_mismatch";
        missingKeys: string[];
        extraKeys: string[];
      }
    | {
        kind: "source_sufficiency";
        requiredRange: FrameRangeV2;
        availableRange: FrameRangeV2 | null;
      }
    | {
        kind: "anchor_issue";
        anchorId: string;
        reason: "missing" | "stale" | "collapsed" | "word_timing_required" | "unplaced";
      }
    | {
        kind: "details";
        message: string;
      };
  recoveryActionKinds: (
    | "repair_document"
    | "refresh_timing"
    | "rebind_media"
    | "prepare_media"
    | "reattach_unplaced_item"
    | "select_supported_profile"
    | "retry_stage"
    | "manual_review"
    | "REPLACE_TEMPORARY_PRESENTER"
    | "none"
  )[];
}
export interface EntityReferenceV2 {
  kind:
    | "document"
    | "block"
    | "token"
    | "sequence"
    | "slot"
    | "overlay_event"
    | "supporting_item"
    | "media_reference"
    | "occurrence"
    | "preparation"
    | "track"
    | "settings"
    | "build";
  id: string | null;
  path: string | null;
}
export interface MediaPreparationSummaryV2 {
  status: "complete" | "blocked" | "not_required";
  requirements: {
    requirementKey: string;
    status: "reused" | "prepared" | "blocked" | "refused";
    originalHash: string;
    deliveredHash: string | null;
    bindingHash: string | null;
    diagnosticIds: string[];
  }[];
}
export interface MigrationDiagnosticV2 {
  kind:
    | "unplaced_item"
    | "legacy_state_requires_review"
    | "legacy_audio_policy_requires_repair";
  severity: "warning" | "blocking";
  entity: EntityReferenceV2;
  message: string;
  recoveryActionKind: "reattach_unplaced_item" | "repair_document" | "manual_review";
}
export interface ReadinessV2 {
  preview: "ready" | "blocked";
  release: "ready" | "blocked";
  blockingIssueIds: string[];
}
export interface ManualCompletionItemV2 {
  id: string;
  kind: "placeholder" | "manual_operation" | "editor_review";
  message: string;
  entity: EntityReferenceV2;
}
