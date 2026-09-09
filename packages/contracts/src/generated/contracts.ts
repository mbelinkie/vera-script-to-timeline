/**
 * Generated from /contracts by npm run generate:contracts.
 * Do not edit by hand.
 */

export type NarrationDependency = {
  [k: string]: unknown;
} & {
  blockId: string;
  blockRevision: number;
  assetId: string;
  status: "ready" | "failed";
  textHash: string;
  audioHash: string;
  audio: NarrationAudio;
  timing: NarrationTiming;
  failureReason?: string;
};
export type ResolvedVisualDependency = {
  [k: string]: unknown;
} & {
  mediaReferenceId: string;
  source: VideoSource | StillSource;
  sourceStartFrame?: number;
  sourceAudio?: ResolvedSourceAudio;
};
/**
 * Closed public-page capture API requests and sanitized views approved by issue 38.
 */
export type PublicPageCaptureApiV1 =
  | CreateCaptureRequest
  | CreateConfigurationVersionRequest
  | RequestCaptureJobRequest
  | CaptureViewMessage
  | CaptureJobViewMessage
  | CaptureRevisionViewMessage
  | RecordRevisionUseDecisionRequest
  | SelectRevisionRequest
  | AddExplicitPinRequest
  | ReleaseExplicitPinRequest
  | AuditEventsViewMessage
  | ApiError;
export type CaptureJobView = {
  [k: string]: unknown;
} & {
  jobId: string;
  projectId: string;
  captureId: string;
  configurationVersion: number;
  trigger: NowTrigger | OnBuildTrigger;
  idempotencyFingerprint: string;
  initiatingAuthorization: AuthorizationDecisionRef;
  settingsDigest: string;
  captureProfileId: string;
  captureProfileVersion: number;
  profileDigest: string;
  retryBudget: number;
  state:
    | "requested"
    | "queued"
    | "leased"
    | "running"
    | "committed_ready"
    | "committed_review_required"
    | "rejected"
    | "failed"
    | "cancelled";
  outputRevisionId: string | null;
  conditionalSelectionResult:
    "not_requested" | "applied" | "conflict" | "blocked_review";
  requestedAt: string;
  enqueuedAt: string | null;
  availableAt: string | null;
  terminalAt: string | null;
  rowVersion: number;
  duplicateDelivery: boolean;
};
export type ArtifactDescriptor = {
  [k: string]: unknown;
} & {
  artifactId: string;
  projectId: string;
  kind: "capture_raster" | "capture_provenance";
  digest: string;
  byteLength: number;
  mimeType: "image/png" | "application/json";
  width?: number;
  height?: number;
  encoding?: "png" | "json";
  color?: "srgb" | "not_applicable";
  alpha?: "opaque" | "present" | "not_applicable";
  verifierProfile: string;
  verifierVersion: number;
  verifiedAt: string;
  accessClass: "project_visual" | "restricted_provenance";
};
/**
 * Closed job-scoped local-worker protocol approved by issue 38.
 */
export type PublicPageCaptureWorkerV1 =
  | ClaimLeaseRequest
  | ClaimLeaseResponse
  | StartAttemptRequest
  | StartAttemptResponse
  | RecordNavigationStartRequest
  | RecordNavigationStartResponse
  | RenewLeaseRequest
  | RenewLeaseResponse
  | RequestStagingGrantsRequest
  | RequestStagingGrantsResponse
  | CommitAttemptRequest
  | CommitAttemptResponse
  | FailAttemptRequest
  | FailAttemptResponse
  | AbandonAttemptRequest
  | AbandonAttemptResponse
  | WorkerError;
export type StagedObjectDescriptor = {
  [k: string]: unknown;
} & {
  stagingObjectId: string;
  grantId: string;
  purpose: "raster" | "provenance";
  digest: string;
  byteLength: number;
  mimeType: "image/png" | "application/json";
  width?: number;
  height?: number;
  encoding?: "png" | "json";
  color?: "srgb" | "not_applicable";
  alpha?: "opaque" | "present" | "not_applicable";
};
/**
 * Immutable observation or terminal-attempt evidence produced by the public-page capture worker.
 */
export type PublicPageCaptureProvenanceV1 = ProvenanceRecord;
export type ProvenanceRecord = {
  [k: string]: unknown;
} & {
  schemaVersion: "public-page-capture-provenance/v1";
  recordType: "revision_observation" | "terminal_attempt_evidence";
  identity: IdentityRecord;
  authorization: AuthorizationRecord;
  request: RequestRecord;
  network: NetworkRecord;
  runtime: RuntimeRecord;
  timing: TimingRecord;
  output: OutputRecord | null;
  change: ChangeSignal1 | null;
  honesty: HonestyRecord;
  terminal: TerminalRecord | null;
};
export type NetworkRecord = {
  [k: string]: unknown;
} & {
  evidenceClass: "live" | "synthetic";
  /**
   * @maxItems 128
   */
  dnsAdmissions: DnsAdmission[];
  /**
   * @maxItems 512
   */
  peerConnections: PeerConnection[];
  tls: TlsObservation;
  /**
   * @minItems 1
   * @maxItems 11
   */
  redirectChain:
    | [RedirectHop]
    | [RedirectHop, RedirectHop]
    | [RedirectHop, RedirectHop, RedirectHop]
    | [RedirectHop, RedirectHop, RedirectHop, RedirectHop]
    | [RedirectHop, RedirectHop, RedirectHop, RedirectHop, RedirectHop]
    | [RedirectHop, RedirectHop, RedirectHop, RedirectHop, RedirectHop, RedirectHop]
    | [
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
      ]
    | [
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
      ]
    | [
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
      ]
    | [
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
      ]
    | [
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
        RedirectHop,
      ];
  finalUrl: string | null;
  redactedFinalUrl: string | null;
  response: ResponseObservation | null;
  frameManifestDigest: string | null;
  subresourceManifestDigest: string | null;
  actualConnectionCount: number;
  denial: NetworkDenial | null;
};
/**
 * Immutable, project-scoped Spotlight OCR evidence records.
 */
export type SpotlightEvidenceV1 =
  | (Base & {
      recordType?: "ocr_attempt_evidence";
      captureRevisionId: string;
      rasterDigest: string;
      profileDigest: string;
      outcome: "succeeded" | "failed";
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "ocr_evidence_batch";
      attemptId: string;
      captureRevisionId: string;
      rasterDigest: string;
      evidenceDigest: string;
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "automated_target_proposal";
      batchId: string;
      /**
       * @minItems 1
       */
      elementIds: [string, ...string[]];
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "manual_geometry_proposal";
      captureRevisionId: string;
      rasterDigest: string;
      region: Rect;
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "author_confirmation";
      proposalId: string;
      captureRevisionId: string;
      rasterDigest: string;
      geometryDigest: string;
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "remap_proposal";
      oldConfirmationId: string;
      newCaptureRevisionId: string;
      outcome:
        | "unique_candidate"
        | "stale_missing"
        | "stale_ambiguous"
        | "stale_contradictory"
        | "stale_incompatible_profile"
        | "stale_manual_redraw_required"
        | "stale_invalid_evidence";
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "remap_decision";
      remapProposalId: string;
      decision: "keep_old" | "accept_remap" | "redraw";
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "spotlight_derivation_record";
      confirmationId: string;
      matteDigest: string;
      matteReceiptDigest: string;
      [k: string]: unknown;
    })
  | (Base & {
      recordType?: "spotlight_build_binding";
      derivationId: string;
      buildReference: string;
      [k: string]: unknown;
    });

/**
 * Generated aggregate type surface for the VERA shared contracts.
 */
export interface VeraContractsV1 {
  scriptDocument: ScriptDocumentV1;
  timelineManifest: TimelineManifestV1;
  buildReport: BuildReportV1;
  compilerDependencies: CompilerDependenciesV1;
  prompterExport: PrompterExportV1;
  publicPageCaptureApi?: PublicPageCaptureApiV1;
  publicPageCaptureWorker?: PublicPageCaptureWorkerV1;
  publicPageCaptureProvenance?: PublicPageCaptureProvenanceV1;
  spotlightEvidence?: SpotlightEvidenceV1;
}
/**
 * Editor-independent canonical ScriptDocument serialization for Phase 1.
 */
export interface ScriptDocumentV1 {
  schemaVersion: "script-document/v1";
  id: string;
  projectId: string;
  title: string;
  activeDraft: ActiveDraft;
  /**
   * Reserved document surface. It is empty until the Phase 3 Ideas contract is introduced.
   *
   * @maxItems 0
   */
  ideaOutline: never[];
  /**
   * Reserved document surface. It is empty until the Phase 3 Extras contract is introduced.
   *
   * @maxItems 0
   */
  extras: never[];
  liveHeadSequence: number;
  /**
   * Base64-encoded acknowledged collaborative state-vector evidence; may be empty before collaboration exists.
   */
  liveStateVector: string;
  liveContentHash: string;
}
export interface ActiveDraft {
  blocks: (
    SectionBlock | NarrationBlock | DirectionBlock | VisualBlock | NoteDraftBlock
  )[];
}
/**
 * A human-readable section heading and optional chapter marker source.
 */
export interface SectionBlock {
  type: "section";
  id: string;
  orderKey: string;
  title: string;
  version: number;
}
export interface NarrationBlock {
  type: "narration";
  id: string;
  orderKey: string;
  text: string;
  /**
   * @minItems 1
   */
  tokens: [NarrationToken, ...NarrationToken[]];
  hostVisibilitySpans: HostVisibilitySpan[];
  visualEvents: VisualEvent[];
  /**
   * Optional typed narration annotations. Omission is equivalent to an empty array.
   */
  annotations?: NarrationAnnotation[];
  /**
   * Optional explicit performance beats. Omission or an empty array derives deterministic sentence beats at export time.
   */
  performanceBeats?: PerformanceBeat[];
  timingPolicy: "narration_spine";
  state: "active" | "excluded";
  notes: string[];
  version: number;
}
/**
 * A stable spoken-token identity plus offsets into NarrationBlock.text. Offset and text agreement is checked semantically in Slice 1.1.
 */
export interface NarrationToken {
  id: string;
  value: string;
  startOffset: number;
  endOffset: number;
}
export interface HostVisibilitySpan {
  id: string;
  range: TextAnchorRange;
  state: "on_camera" | "voiceover";
  /**
   * The authoring source of the span; Phase 1 does not infer missing state.
   */
  source: "authored";
  version: number;
}
/**
 * A semantic range whose boundaries attach before or after stable tokens. Token existence, order, and quoted-text agreement are semantic validation concerns.
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
export interface VisualEvent {
  id: string;
  range: TextAnchorRange;
  source: LocalMediaVisualSource | PlaceholderVisualSource;
  presentationMode: "full_frame" | "overlay";
  framingPolicy: "contain" | "cover" | "native";
  /**
   * Phase 1 supports no authored motion preset.
   */
  motionPreset: "none";
  audioPolicy: "mute" | "use_source";
  layer: number;
  transitionIn: HardCut | null;
  transitionOut: HardCut | null;
  /**
   * Explicit frame overrides arrive in Phase 5 and are unavailable in Phase 1.
   */
  timingOverrides: null;
  status: "ready" | "unresolved" | "failed";
  version: number;
}
export interface LocalMediaVisualSource {
  kind: "local_media";
  mediaReferenceId: string;
  mediaKind: "still" | "video";
  label: string;
}
export interface PlaceholderVisualSource {
  kind: "placeholder";
  description: string;
  unresolvedVisual: true;
}
export interface HardCut {
  kind: "hard_cut";
  durationFrames: 0;
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
 * Stable recording-take identity over an exact narration token range.
 */
export interface PerformanceBeat {
  id: string;
  range: TextAnchorRange;
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
/**
 * A readable standalone visual row whose event remains anchored to narration text.
 */
export interface VisualBlock {
  type: "visual";
  id: string;
  orderKey: string;
  event: VisualEvent;
  version: number;
}
export interface NoteDraftBlock {
  type: "note_draft";
  id: string;
  orderKey: string;
  text: string;
  state: "excluded";
  version: number;
}
/**
 * Editor-neutral, integer-frame canonical timeline manifest shared by Free and Studio delivery adapters.
 */
export interface TimelineManifestV1 {
  schemaVersion: "timeline-manifest/v1";
  id: string;
  buildId: string;
  sourceDocument: DocumentReference;
  timeline: TimelineSettings;
  /**
   * @minItems 1
   */
  tracks: [
    VideoTrack | AudioTrack | SubtitleTrack,
    ...(VideoTrack | AudioTrack | SubtitleTrack)[],
  ];
  sources: (VideoSource | StillSource | AudioSource | PlaceholderSource)[];
  events: (VideoEvent | StillEvent | AudioEvent | PlaceholderEvent)[];
  transitions: HardCutTransition[];
  markers: (PlacedMarker | UnplacedMarker)[];
}
/**
 * Immutable identity evidence for the ScriptDocument materialization consumed by a build.
 */
export interface DocumentReference {
  documentId: string;
  projectId: string;
  liveHeadSequence: number;
  contentHash: string;
}
export interface TimelineSettings {
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
export interface VideoTrack {
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  id: string;
  kind: "video";
  index: number;
  name: string;
}
export interface AudioTrack {
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  id: string;
  kind: "audio";
  index: number;
  name: string;
}
export interface SubtitleTrack {
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  id: string;
  kind: "subtitle";
  index: number;
  name: string;
}
export interface VideoSource {
  id: string;
  kind: "video";
  /**
   * POSIX-style project-relative locator. Identity comes from the content hash, never this path.
   */
  path: string;
  contentHash: string;
  durationFrames: number;
  frameRate: RationalRate;
  width: number;
  height: number;
  audioChannels: number;
}
export interface StillSource {
  id: string;
  kind: "still";
  /**
   * POSIX-style project-relative locator. Identity comes from the content hash, never this path.
   */
  path: string;
  contentHash: string;
  width: number;
  height: number;
}
export interface AudioSource {
  id: string;
  kind: "audio";
  /**
   * POSIX-style project-relative locator. Identity comes from the content hash, never this path.
   */
  path: string;
  contentHash: string;
  durationFrames: number;
  sampleRate: number;
  channels: number;
}
export interface PlaceholderSource {
  id: string;
  kind: "placeholder";
  label: string;
  reason: string;
}
export interface VideoEvent {
  id: string;
  kind: "video";
  sourceId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  trackId: string;
  trackKind: "video";
  recordRange: FrameRange;
  sourceRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision:
    | "word"
    | "sentence"
    | "cue"
    | "frame"
    | "word_start_with_derived_end"
    | "sentence_start_with_derived_end"
    | "unavailable";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface FrameRange {
  startFrame: number;
  durationFrames: number;
}
export interface EventProvenance {
  documentId: string;
  blockId: string;
  authoringKind: "visual_event" | "narration_block";
  authoringId: string;
}
export interface StillEvent {
  id: string;
  kind: "still";
  sourceId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  trackId: string;
  trackKind: "video";
  recordRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision:
    | "word"
    | "sentence"
    | "cue"
    | "frame"
    | "word_start_with_derived_end"
    | "sentence_start_with_derived_end"
    | "unavailable";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface AudioEvent {
  id: string;
  kind: "audio";
  sourceId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  trackId: string;
  trackKind: "audio";
  recordRange: FrameRange;
  sourceRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision:
    | "word"
    | "sentence"
    | "cue"
    | "frame"
    | "word_start_with_derived_end"
    | "sentence_start_with_derived_end"
    | "unavailable";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface PlaceholderEvent {
  id: string;
  kind: "placeholder";
  sourceId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  trackId: string;
  trackKind: "video";
  recordRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision:
    | "word"
    | "sentence"
    | "cue"
    | "frame"
    | "word_start_with_derived_end"
    | "sentence_start_with_derived_end"
    | "unavailable";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface HardCutTransition {
  id: string;
  kind: "hard_cut";
  fromEventId: string;
  toEventId: string;
  atFrame: number;
  durationFrames: 0;
}
export interface PlacedMarker {
  id: string;
  state: "placed";
  frame: number;
  name: string;
  note: string;
  color: string;
  provenance: MarkerProvenance;
}
export interface MarkerProvenance {
  documentId: string;
  blockId: string;
  authoringKind: "script_marker";
  authoringId: string;
}
export interface UnplacedMarker {
  id: string;
  state: "unplaced";
  name: string;
  note: string;
  color: string;
  reason: string;
  provenance: MarkerProvenance;
}
/**
 * Human-traceable structured report for one immutable Phase 1 timeline build.
 */
export interface BuildReportV1 {
  schemaVersion: "build-report/v1";
  id: string;
  buildId: string;
  buildClass: "preview" | "release";
  status: "ready" | "ready_with_warnings" | "blocked" | "failed";
  /**
   * True when any temporary synthetic speech remains in the build.
   */
  temporaryNarration: boolean;
  sourceDocument: DocumentReference;
  manifest: ManifestReference;
  timeline: TimelineSettings;
  summary: BuildSummary;
  eventResults: EventBuildResult[];
  issues: BuildIssue[];
  manualCompletionItems: ManualCompletionItem[];
}
export interface ManifestReference {
  id: string;
  contentHash: string;
}
export interface BuildSummary {
  sourceCount: number;
  eventCount: number;
  markerCount: number;
  placedCount: number;
  placeholderCount: number;
  manualCompletionCount: number;
  warningCount: number;
  errorCount: number;
}
export interface EventBuildResult {
  eventId: string;
  disposition: "placed" | "placeholder" | "manual_completion" | "blocked";
  sourceId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  trackId: string;
  trackKind: "video" | "audio" | "subtitle";
  recordRange: FrameRange;
  message: string;
}
export interface BuildIssue {
  id: string;
  severity: "info" | "warning" | "error" | "blocking";
  code: string;
  message: string;
  entity: EntityReference;
}
export interface EntityReference {
  kind:
    | "document"
    | "block"
    | "visual_event"
    | "timeline_event"
    | "source"
    | "marker"
    | "build";
  id: string;
}
export interface ManualCompletionItem {
  id: string;
  code: string;
  description: string;
  action: string;
  entity: EntityReference;
}
/**
 * Verified build dependencies consumed by the pure Slice 1.3 compiler.
 */
export interface CompilerDependenciesV1 {
  schemaVersion: "compiler-dependencies/v1";
  build: BuildContext;
  /**
   * @minItems 1
   */
  tracks: [
    VideoTrack | AudioTrack | SubtitleTrack,
    ...(VideoTrack | AudioTrack | SubtitleTrack)[],
  ];
  roles: TrackRoles;
  narration: NarrationDependency[];
  resolvedVisuals: ResolvedVisualDependency[];
}
export interface BuildContext {
  buildId: string;
  manifestId: string;
  reportId: string;
  buildClass: "preview" | "release";
  timeline: CompilerTimelineSettings;
}
export interface CompilerTimelineSettings {
  frameRate: RationalRate;
  width: number;
  height: number;
  audioSampleRate: number;
  startFrame: number;
}
export interface TrackRoles {
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  presenterTrackId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  placeholderTrackId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  narrationTrackId: string;
  /**
   * Stable opaque track identity. Media kind and ordering are separate structural fields; consumers must not infer either from this string.
   */
  sourceAudioTrackId: string;
}
export interface NarrationAudio {
  /**
   * POSIX-style project-relative locator. Identity comes from the content hash, never this path.
   */
  locator: string;
  durationSamples: number;
  sampleRate: number;
  channels: number;
}
export interface NarrationTiming {
  recordVersion: string;
  contentHash: string;
  alignmentVersion: string;
  precision: "word_start_with_derived_end" | "sentence_start" | "none";
  marks: TimingMark[];
}
export interface TimingMark {
  kind: "word" | "sentence";
  timeMs: number;
  startUtf16: number;
  endUtf16: number;
  value: string;
}
export interface ResolvedSourceAudio {
  source: AudioSource;
  sourceStartFrame: number;
}
/**
 * Canonical deterministic sidecar for a narration-only prompter text artifact.
 */
export interface PrompterExportV1 {
  schemaVersion: "prompter-export/v1";
  sourceDocument: DocumentReference;
  settings: {
    includeSectionNavigation: boolean;
    includeBeatNumbers: boolean;
  };
  textSha256: string;
  beats: PrompterBeat[];
}
export interface PrompterBeat {
  id: string;
  expectedText: string;
  hostVisibility: "on_camera" | "voiceover";
  navigationCues: string[];
  annotations: PrompterBeatAnnotation[];
}
export interface PrompterBeatAnnotation {
  id: string;
  kind: "pronunciation_alias" | "pronunciation_phoneme" | "performance_note";
  value: string;
  visibleInPrompter: boolean;
}
export interface CreateCaptureRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "create_capture";
  projectId: string;
  clientRequestId: string;
  idempotencyKey: string;
  requestedUrl: string;
  regionIntent: FullViewportRegion | RectangleRegion;
  acquisitionPolicy: ExecutableAcquisitionPolicy | ReservedPeriodicPolicy;
  captureProfileId: string;
  captureProfileVersion: number;
}
export interface FullViewportRegion {
  kind: "full_viewport";
}
export interface RectangleRegion {
  kind: "rectangle";
  x: number;
  y: number;
  width: number;
  height: number;
}
export interface ExecutableAcquisitionPolicy {
  kind: "now" | "on_build";
}
export interface ReservedPeriodicPolicy {
  kind: "periodic_reserved";
  execution: "disabled";
}
export interface CreateConfigurationVersionRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "create_configuration_version";
  projectId: string;
  captureId: string;
  clientRequestId: string;
  idempotencyKey: string;
  expectedCaptureRowVersion: number;
  requestedUrl: string;
  regionIntent: FullViewportRegion | RectangleRegion;
  acquisitionPolicy: ExecutableAcquisitionPolicy | ReservedPeriodicPolicy;
  captureProfileId: string;
  captureProfileVersion: number;
}
export interface RequestCaptureJobRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "request_capture_job";
  projectId: string;
  captureId: string;
  clientRequestId: string;
  idempotencyKey: string;
  expectedCaptureRowVersion: number;
  trigger: NowTrigger | OnBuildTrigger;
}
export interface NowTrigger {
  kind: "now";
  commandId: string;
  selectionIntent: NoSelectionIntent | ConditionalSelectionIntent;
}
export interface NoSelectionIntent {
  kind: "none";
}
export interface ConditionalSelectionIntent {
  kind: "conditional";
  target: DraftOccurrenceReference | VersionedExternalReference;
  expectedPreviousSelectionId: string | null;
}
export interface DraftOccurrenceReference {
  projectId: string;
  kind: "draft_occurrence";
  resourceId: string;
  resourceVersionDigest: string;
  occurrenceId: string;
}
export interface VersionedExternalReference {
  projectId: string;
  kind:
    | "document_revision"
    | "document_checkpoint"
    | "preview_build"
    | "release_build"
    | "selection_evidence"
    | "review_hold"
    | "integrity_hold";
  resourceId: string;
  resourceVersionDigest: string;
}
export interface OnBuildTrigger {
  kind: "on_build";
  buildSnapshot: BuildSnapshotReference;
}
export interface BuildSnapshotReference {
  projectId: string;
  kind: "preview_build" | "release_build";
  resourceId: string;
  resourceVersionDigest: string;
}
export interface CaptureViewMessage {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "capture_view";
  requestId: string;
  capture: CaptureView;
}
export interface CaptureView {
  captureId: string;
  projectId: string;
  lifecycle: "draft" | "active" | "paused" | "retired";
  currentConfigurationVersion: number;
  rowVersion: number;
  createdBy: PrincipalRef;
  createdAt: string;
  updatedAt: string;
  configuration: CaptureConfigurationView;
}
export interface PrincipalRef {
  principalKind: "user" | "service";
  principalId: string;
}
export interface CaptureConfigurationView {
  captureId: string;
  configurationVersion: number;
  requestedUrl: RedactedUrl;
  regionIntent: FullViewportRegion | RectangleRegion;
  acquisitionPolicy: ExecutableAcquisitionPolicy | ReservedPeriodicPolicy;
  captureProfileId: string;
  captureProfileVersion: number;
  settingsDigest: string;
  previousConfigurationDigest?: string;
  createdBy: PrincipalRef;
  createdAt: string;
}
export interface RedactedUrl {
  display: string;
  canonicalDigest: string;
  /**
   * @maxItems 32
   */
  queryKeys: string[];
}
export interface CaptureJobViewMessage {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "capture_job_view";
  requestId: string;
  job: CaptureJobView;
}
export interface AuthorizationDecisionRef {
  decisionId: string;
  action: string;
  principal: PrincipalRef;
  projectId: string;
  role: "producer" | "editor" | "viewer" | "service";
  membershipVersion?: number;
  decidedAt: string;
  recheckMode: "every_request" | "commit_time" | "immutable_reference";
}
export interface CaptureRevisionViewMessage {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "capture_revision_view";
  requestId: string;
  revision: CaptureRevisionView;
}
export interface CaptureRevisionView {
  revisionId: string;
  projectId: string;
  captureId: string;
  configurationVersion: number;
  jobId: string;
  winningAttemptId: string;
  revisionNumber: number;
  artifact: ArtifactDescriptor;
  provenance: ArtifactDescriptor;
  changeSignal: ChangeSignal;
  status: "ready" | "review_required";
  /**
   * @maxItems 64
   */
  warningCodes: string[];
  settingsDigest: string;
  profileDigest: string;
  committedAt: string;
  observationStatement: "Stored bytes and provenance are reproducible; the live page may later differ.";
}
export interface ChangeSignal {
  changeSignalId: string;
  captureId: string;
  currentRevisionId: string;
  baselineRevisionId: string | null;
  currentArtifactId: string;
  baselineArtifactId: string | null;
  signal:
    | "initial_observation"
    | "same_exact_bytes"
    | "different_exact_bytes"
    | "not_comparable";
  differences: {
    finalUrl: boolean | null;
    redirectChain: boolean | null;
    profile: boolean | null;
    region: boolean | null;
    warnings: boolean | null;
    loadEvidence: boolean | null;
  };
  algorithm: "exact_bytes_and_provenance";
  algorithmVersion: number;
  computedAt: string;
  materiality: "non_semantic_no_automatic_replacement_selection_or_notification";
}
export interface RecordRevisionUseDecisionRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "record_revision_use_decision";
  projectId: string;
  revisionId: string;
  clientRequestId: string;
  idempotencyKey: string;
  context: DraftOccurrenceReference | VersionedExternalReference;
  decision: "preview_acknowledged" | "release_accepted";
}
export interface SelectRevisionRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "select_revision";
  projectId: string;
  revisionId: string;
  clientRequestId: string;
  idempotencyKey: string;
  target: DraftOccurrenceReference | VersionedExternalReference;
  expectedPreviousSelectionId: string | null;
  reason: "manual" | "capture_and_use" | "checkpoint_restore";
  requiredUseDecisionId: string | null;
}
export interface AddExplicitPinRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "add_explicit_pin";
  projectId: string;
  revisionId: string;
  clientRequestId: string;
  idempotencyKey: string;
  source: DraftOccurrenceReference | VersionedExternalReference;
}
export interface ReleaseExplicitPinRequest {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "release_explicit_pin";
  projectId: string;
  pinId: string;
  clientRequestId: string;
  idempotencyKey: string;
  reason: string;
}
export interface AuditEventsViewMessage {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "audit_events_view";
  requestId: string;
  /**
   * @maxItems 1000
   */
  events: CaptureAuditEventView[];
}
export interface CaptureAuditEventView {
  eventId: string;
  projectId: string;
  primaryObjectKind: string;
  primaryObjectId: string;
  objectSequence: number;
  eventType: string;
  principal: PrincipalRef;
  requestId: string;
  correlationId: string;
  policyVersion: number;
  profileVersion: number;
  beforeState: string | null;
  afterState: string | null;
  resultCode: string;
  safeDetails: {
    [k: string]: string | number | boolean | null;
  };
  correctedEventId: string | null;
  serverTime: string;
}
export interface ApiError {
  schemaVersion: "public-page-capture-api/v1";
  messageType: "error";
  requestId: string;
  code:
    | "request_invalid"
    | "authentication_required"
    | "action_not_allowed"
    | "resource_not_found"
    | "version_conflict"
    | "idempotency_key_reused"
    | "selection_conflict"
    | "revision_requires_review"
    | "job_not_committable"
    | "capture_resource_limit"
    | "capture_request_denied"
    | "authorization_unavailable"
    | "capture_worker_unavailable"
    | "object_verification_unavailable";
  safeMessage: string;
  retryable: boolean;
  /**
   * @maxItems 32
   */
  fieldPaths: string[];
  denialFingerprint?: string;
}
export interface ClaimLeaseRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "claim_lease";
  clientRequestId: string;
  workerInstallationId: string;
  /**
   * @minItems 1
   * @maxItems 32
   */
  supportedProfileDigests: [string, ...string[]];
}
export interface ClaimLeaseResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "lease_claimed";
  requestId: string;
  assignment: LeaseAssignment;
}
export interface LeaseAssignment {
  projectId: string;
  captureId: string;
  configurationVersion: number;
  jobId: string;
  leaseId: string;
  leaseEpoch: number;
  attemptId: null;
  leaseCapability: string;
  capabilityJtiDigest: string;
  capabilityScopeDigest: string;
  commitNonce: string;
  issuedAt: string;
  expiresAt: string;
  exactRequestedUrl: string;
  settingsDigest: string;
  profile: CaptureProfileV1;
}
export interface CaptureProfileV1 {
  profileId: string;
  profileVersion: number;
  adapterVersion: string;
  securityPolicyVersion: string;
  profileDigest: string;
  network: {
    schemes: unknown[];
    ports: unknown[];
    methods: unknown[];
    idna: "uts46_nontransitional";
    rejectMixedDns: true;
    pinResolvedAddresses: true;
    verifyActualPeer: true;
    revalidateRedirects: true;
    revalidateFrames: true;
    revalidateSubresources: true;
    directBrowserNetworkFallback: false;
    webSocket: "blocked";
    webRtc: "blocked";
    referrer: "none";
  };
  isolation: {
    disposableContext: true;
    importedState: false;
    cookies: "empty_and_discarded";
    storage: "empty_and_discarded";
    cache: "ephemeral";
    extensions: "blocked";
    downloads: "blocked";
    permissions: "none";
    filesystem: "page_inaccessible";
    localNetwork: "blocked";
    inboundListeners: "blocked";
    attachedBrowser: false;
    credentialEnvironment: "allowlist_only";
  };
  render: {
    javaScript: "disabled" | "sandboxed_bounded";
    viewportWidth: number;
    viewportHeight: number;
    deviceScaleFactor: number;
    region: FullViewportRegion | RectangleRegion;
    encoding: "png";
    color: "srgb";
    background: "opaque_white";
    locale: string;
    timezone: string;
    userAgent: string;
    animations: "disabled";
    reducedMotion: "reduce";
    fonts: "system_only_no_webfonts";
    media: "blocked";
    popups: "blocked";
    forms: "blocked";
    interaction: "none";
  };
  stability: {
    waitUntil: "domcontentloaded";
    settleMilliseconds: number;
    hardDeadlineMilliseconds: number;
  };
  warningPolicy: {
    anyWarningRequiresReview: true;
    /**
     * @minItems 1
     * @maxItems 64
     */
    hardFailureCodes: [string, ...string[]];
  };
  limits: {
    urlBytes: number;
    redirects: number;
    dnsAnswers: number;
    connectionAttemptsPerRequest: number;
    topLevelRequests: number;
    frameRequests: number;
    subresourceRequests: number;
    totalRequests: number;
    responseBytes: number;
    totalBytes: number;
    frameDepth: number;
    popups: 0;
    navigationMilliseconds: number;
    stabilityMilliseconds: number;
    scriptCpuMilliseconds: number;
    attemptMilliseconds: number;
    memoryMiB: number;
    processes: number;
    workerConcurrency: number;
    outputPixels: number;
    rasterBytes: number;
    diagnostics: number;
    diagnosticFieldBytes: number;
    retries: number;
    leaseMilliseconds: number;
    heartbeatMilliseconds: number;
  };
}
export interface StartAttemptRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "start_attempt";
  clientRequestId: string;
  lease: LeaseProof;
  cleanProfileId: string;
  browserBuild: string;
  adapterVersion: string;
  securityPolicyVersion: string;
}
export interface LeaseProof {
  workerInstallationId: string;
  jobId: string;
  leaseId: string;
  leaseEpoch: number;
  attemptId: string | null;
  leaseCapability: string;
}
export interface StartAttemptResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "attempt_started";
  requestId: string;
  attemptId: string;
  jobId: string;
  leaseId: string;
  leaseEpoch: number;
  startedAt: string;
  browserLaunchAuthorized: true;
}
export interface RecordNavigationStartRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "record_navigation_start";
  clientRequestId: string;
  lease: LeaseProof;
  navigationStartedAt: string;
  initialUrlDigest: string;
}
export interface RecordNavigationStartResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "navigation_start_recorded";
  requestId: string;
  attemptId: string;
  recordedAt: string;
}
export interface RenewLeaseRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "renew_lease";
  clientRequestId: string;
  lease: LeaseProof;
}
export interface RenewLeaseResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "lease_renewed";
  requestId: string;
  leaseId: string;
  leaseEpoch: number;
  expiresAt: string;
  renewedAt: string;
}
export interface RequestStagingGrantsRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "request_staging_grants";
  clientRequestId: string;
  lease: LeaseProof;
  purposes: unknown[];
}
export interface RequestStagingGrantsResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "staging_grants_issued";
  requestId: string;
  /**
   * @minItems 2
   * @maxItems 2
   */
  grants: [StagingGrant, StagingGrant];
}
export interface StagingGrant {
  grantId: string;
  purpose: "raster" | "provenance";
  rawGrant: string;
  grantDigest: string;
  attemptId: string;
  leaseEpoch: number;
  maxBytes: number;
  mimeType: "image/png" | "application/json";
  issuedAt: string;
  expiresAt: string;
}
export interface CommitAttemptRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "commit_attempt";
  clientRequestId: string;
  lease: LeaseProof;
  commitNonce: string;
  raster: StagedObjectDescriptor;
  provenanceObject: StagedObjectDescriptor;
  /**
   * @maxItems 64
   */
  warningCodes: string[];
  reviewClassification: "ready" | "review_required";
}
export interface CommitAttemptResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "attempt_committed";
  requestId: string;
  job: CaptureJobView;
  revision: CaptureRevisionView;
  recoveredExistingOutcome: boolean;
}
export interface FailAttemptRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "fail_attempt";
  clientRequestId: string;
  lease: LeaseProof;
  terminalCode: string;
  navigationStarted: boolean;
  retryable: boolean;
  terminalEvidenceObject: StagedObjectDescriptor;
}
export interface FailAttemptResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "attempt_failed";
  requestId: string;
  jobId: string;
  attemptId: string;
  jobState: "queued" | "failed";
  recordedAt: string;
}
export interface AbandonAttemptRequest {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "abandon_attempt";
  clientRequestId: string;
  lease: LeaseProof;
  terminalCode: string;
  terminalEvidenceObject: StagedObjectDescriptor;
}
export interface AbandonAttemptResponse {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "attempt_abandoned";
  requestId: string;
  jobId: string;
  attemptId: string;
  recordedAt: string;
}
export interface WorkerError {
  schemaVersion: "public-page-capture-worker/v1";
  messageType: "worker_error";
  requestId: string;
  code:
    | "request_invalid"
    | "authentication_required"
    | "action_not_allowed"
    | "invalid_or_expired_job_capability"
    | "job_not_committable"
    | "capture_resource_limit"
    | "capture_request_denied"
    | "authorization_unavailable"
    | "capture_worker_unavailable"
    | "object_verification_unavailable";
  safeMessage: string;
  retryable: boolean;
  /**
   * @maxItems 32
   */
  fieldPaths: string[];
}
export interface IdentityRecord {
  projectId: string;
  captureId: string;
  configurationVersionId: string;
  jobId: string;
  leaseEpoch: number;
  attemptId: string;
  revisionId: string | null;
}
export interface AuthorizationRecord {
  principal: PrincipalRef1;
  role: "producer" | "editor" | "viewer" | "service";
  action:
    | "capture.create"
    | "capture.configure"
    | "capture.request.now"
    | "capture.request.on_build"
    | "capture.commit";
  decisionId: string;
  decision: "allowed";
  decidedAt: string;
  commitRecheck: true;
  originReference: OriginReference | null;
}
export interface PrincipalRef1 {
  principalId: string;
  principalKind: "user" | "service";
}
export interface OriginReference {
  kind: "timeline" | "shot" | "media_occurrence" | "preview_build" | "release_build";
  referenceId: string;
  revision: number;
}
export interface RequestRecord {
  triggerKind: "now" | "on_build";
  requestedUrl: string;
  redactedRequestedUrl: string;
  requestedUrlDigest: string;
  requestedUrlFingerprint: string;
  /**
   * @maxItems 64
   */
  queryKeyNames: string[];
  settingsDigest: string;
  captureProfileId: "vera-public-page-capture-v1";
  captureProfileDigest: string;
  regionIntent:
    | {
        kind: "full_viewport";
      }
    | {
        kind: "element";
        selector: string;
      };
  idempotencyScopeDigest: string;
  idempotencyKeyDigest: string;
  requestedAt: string;
  enqueuedAt: string;
}
export interface DnsAdmission {
  host: string;
  resolver: string;
  resolvedAt: string;
  /**
   * @maxItems 64
   */
  answers: {
    address: {
      [k: string]: unknown;
    } & string;
    family: 4 | 6;
    addressClass:
      | "public"
      | "loopback"
      | "private"
      | "link_local"
      | "multicast"
      | "unspecified"
      | "reserved";
  }[];
  admitted: boolean;
}
export interface PeerConnection {
  host: string;
  address: {
    [k: string]: unknown;
  } & string;
  port: 80 | 443;
  addressClass: "public";
  matchedAdmission: true;
  connectedAt: string;
}
export interface TlsObservation {
  availability: "available" | "unavailable" | "not_applicable";
  protocol: string | null;
  cipher: string | null;
  peerCertificateSha256: string | null;
  unavailableReason: string | null;
}
export interface RedirectHop {
  sequence: number;
  url: string;
  redactedUrl: string;
  urlDigest: string;
  status: number | null;
  locationDigest: string | null;
  admitted: boolean;
}
export interface ResponseObservation {
  status: number;
  contentType: string | null;
  contentLength: number | null;
  title: string | null;
  headerDigest: string;
}
export interface NetworkDenial {
  phase:
    "url_parse" | "dns" | "connect" | "redirect" | "frame" | "subresource" | "response";
  code: string;
  sanitizedMessage: string;
  navigationStarted: boolean;
}
export interface RuntimeRecord {
  workerBuildId: string;
  workerBuildDigest: string;
  installationId: string;
  os: string;
  sandbox: "process" | "container" | "synthetic_fixture";
  browser: "chromium" | "synthetic_fixture";
  browserVersion: string;
  adapterVersion: string;
  policyDigest: string;
  cleanProfileId: string;
  importedState: false;
  initialCookieCount: 0;
  finalCookieCount: 0;
  persistedStateDiscarded: true;
  javascriptMode: "disabled" | "sandboxed_bounded";
  locale: "en-US";
  timezone: "UTC";
  userAgentProfile: "vera-public-page-capture-v1";
  viewport: {
    width: 1920;
    height: 1080;
  };
  deviceScaleFactor: 2;
  colorProfile: "srgb";
  outputFormat: "png";
  /**
   * @minItems 8
   */
  blockedCapabilities: [
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    (
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    ),
    ...(
      | "downloads"
      | "file_access"
      | "local_network"
      | "popups"
      | "printing"
      | "web_rtc"
      | "web_sockets"
      | "write_clipboard"
      | "forms"
      | "permissions"
    )[],
  ];
}
export interface TimingRecord {
  serverStartedAt: string;
  workerStartedAt: string;
  workerFinishedAt: string;
  durationMilliseconds: number;
  settleOutcome: "quiet_window" | "timeout" | "not_reached";
  settleMilliseconds: number;
  navigationDeadlineMilliseconds: number;
  jobDeadlineMilliseconds: number;
  retryNumber: number;
  retryBudget: 2;
  /**
   * @minItems 1
   * @maxItems 32
   */
  leaseHistory: [LeaseHistoryEntry, ...LeaseHistoryEntry[]];
  /**
   * @minItems 1
   * @maxItems 16
   */
  milestones:
    | [Milestone]
    | [Milestone, Milestone]
    | [Milestone, Milestone, Milestone]
    | [Milestone, Milestone, Milestone, Milestone]
    | [Milestone, Milestone, Milestone, Milestone, Milestone]
    | [Milestone, Milestone, Milestone, Milestone, Milestone, Milestone]
    | [Milestone, Milestone, Milestone, Milestone, Milestone, Milestone, Milestone]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ]
    | [
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
        Milestone,
      ];
  captureInstant: string | null;
}
export interface LeaseHistoryEntry {
  event:
    | "claimed"
    | "started"
    | "renewed"
    | "expired"
    | "committed"
    | "failed"
    | "abandoned";
  leaseEpoch: number;
  at: string;
  deadline: string;
  workerInstallationId: string;
}
export interface Milestone {
  name:
    | "lease_claimed"
    | "attempt_started"
    | "navigation_started"
    | "dom_content_loaded"
    | "load"
    | "fonts_ready"
    | "settled"
    | "rasterized"
    | "staged"
    | "committed"
    | "terminal";
  wallAt: string;
  monotonicMilliseconds: number;
}
export interface OutputRecord {
  raster: ArtifactDescriptor1;
  encoding: "png";
  width: 3840;
  height: 2160;
  capturedRegion: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  decoder: string;
  byteIdentity: "new_raster" | "exact_byte_reuse";
  baselineRevisionId: string | null;
  reusedRasterArtifactId: string | null;
  stagedAt: string;
  committedAt: string;
}
export interface ArtifactDescriptor1 {
  artifactId: string;
  digest: string;
  byteLength: number;
  mediaType: "image/png" | "application/json";
}
export interface ChangeSignal1 {
  classification: "first_observation" | "no_change" | "changed" | "uncertain";
  baselineRevisionId: string | null;
  pixelChanged: boolean | null;
  byteChanged: boolean | null;
  reviewRequired: boolean;
  /**
   * @maxItems 32
   */
  signals: {
    code: string;
    severity: "info" | "warning";
    message: string;
  }[];
}
export interface HonestyRecord {
  statement: "Observed facts and unavailable facts are explicitly distinguished.";
  classification: "complete" | "partial" | "terminal_denial" | "terminal_failure";
  partialReason: string | null;
  /**
   * @maxItems 32
   */
  warnings: {
    code: string;
    message: string;
  }[];
  /**
   * @maxItems 64
   */
  unavailableObservations: UnavailableObservation[];
  redactionPolicyVersion: "vera-url-redaction-v1";
}
export interface UnavailableObservation {
  field: string;
  reason: string;
}
export interface TerminalRecord {
  outcome: "denied" | "failed" | "abandoned";
  code: string;
  sanitizedMessage: string;
  phase:
    | "policy"
    | "dns"
    | "connect"
    | "navigation"
    | "render"
    | "stage"
    | "commit"
    | "lease";
  retryable: boolean;
  navigationStarted: boolean;
  leaseDisposition: "released" | "expired" | "consumed";
}
export interface Base {
  schemaVersion: "spotlight-evidence/v1";
  recordType: string;
  recordId: string;
  projectId: string;
  createdAt: string;
  payloadDigest: string;
  [k: string]: unknown;
}
export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}
