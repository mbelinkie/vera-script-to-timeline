/**
 * Generated from /contracts by npm run generate:contracts.
 * Do not edit by hand.
 */

/**
 * Generated aggregate type surface for the three Slice 0.1 contracts.
 */
export interface VeraContractsV1 {
  scriptDocument: ScriptDocumentV1;
  timelineManifest: TimelineManifestV1;
  buildReport: BuildReportV1;
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
  id: "V1" | "V2" | "V3" | "V4" | "V5";
  kind: "video";
  index: number;
  name: string;
}
export interface AudioTrack {
  id: "A1" | "A2" | "A3" | "A4" | "A5";
  kind: "audio";
  index: number;
  name: string;
}
export interface SubtitleTrack {
  id: "S1";
  kind: "subtitle";
  index: 1;
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
  trackId: "V1" | "V2" | "V3" | "V4";
  recordRange: FrameRange;
  sourceRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision: "word" | "sentence" | "cue" | "frame";
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
  trackId: "V1" | "V2" | "V3" | "V4";
  recordRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision: "word" | "sentence" | "cue" | "frame";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface AudioEvent {
  id: string;
  kind: "audio";
  sourceId: string;
  trackId: "A1" | "A2" | "A3" | "A4" | "A5";
  recordRange: FrameRange;
  sourceRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision: "word" | "sentence" | "cue" | "frame";
  alignmentVersion: string;
  provenance: EventProvenance;
}
export interface PlaceholderEvent {
  id: string;
  kind: "placeholder";
  sourceId: string;
  trackId: "V5";
  recordRange: FrameRange;
  /**
   * Honest precision of the alignment used to resolve a semantic anchor into integer frames.
   */
  timingPrecision: "word" | "sentence" | "cue" | "frame";
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
  trackId:
    ("V1" | "V2" | "V3" | "V4" | "V5") | ("A1" | "A2" | "A3" | "A4" | "A5") | "S1";
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
