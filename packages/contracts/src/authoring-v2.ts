import type {
  ContentSlot,
  NarratedVisualPayloadV2,
  NarrationTokenTimingMapV2,
  RationalRate,
  RationalTime,
  ScriptDocumentV2,
  SupportingItemV2,
  TimedPlacement,
  WordInpointAnchor,
  WordAudibleEndAnchor,
  NarrationBoundaryEvidenceV1,
} from "./generated/contracts-v2.js";

import type { OnCameraFramingV2 } from "./authoring-v2-coverage.js";

export type { OnCameraFramingV2 } from "./authoring-v2-coverage.js";

export type WordBoundaryAnchorV2 = WordInpointAnchor | WordAudibleEndAnchor;
export {
  stashChecklistV2,
  stashNoteContentStampV2,
  copyStashNoteAsSpokenV2,
  projectStashChecklistV2,
} from "./authoring-v2-stash-checklist.js";
export type { StashChecklistProjectionV2 } from "./authoring-v2-stash-checklist.js";

export interface AuthoringDiagnosticV2 {
  code: string;
  message: string;
  jsonPath: string;
  severity?: "error" | "warning";
  blockId?: string;
  entityId?: string;
}

export interface AuthoringValidationResultV2 {
  valid: boolean;
  diagnostics: AuthoringDiagnosticV2[];
}

export interface LoggedMediaBoundsV2 {
  mediaReferenceId: string;
  contentHash: string;
  loggedStartFrame: number;
  loggedEndExclusiveFrame: number;
  frameRate: RationalRate;
}

export interface PrimarySequenceProjectionOptionsV2 {
  mediaBounds?: readonly LoggedMediaBoundsV2[];
  narrationTimingMaps?: readonly NarrationTokenTimingMapV2[];
  narrationBoundaryEvidence?: readonly NarrationBoundaryEvidenceV1[];
}

export type ProjectedHostStateV2 =
  | "on_camera"
  | "voiceover"
  | "undefined"
  | "unresolved";

export interface ProjectedTokenV2 {
  tokenId: string;
  text: string;
  primarySlotId: string | null;
  payloadId: string | null;
  humanOrdinal: number | null;
  hostState: ProjectedHostStateV2;
  onCameraResumes: boolean;
}

export interface ProjectedAppearanceV2 {
  slotId: string;
  payloadId: string | null;
  structuralIndex: number;
  humanOrdinal: number | null;
  hostState: Exclude<ProjectedHostStateV2, "unresolved">;
  /** Wide or Tight for an On Camera passage; null for every other picture. */
  framing: OnCameraFramingV2 | null;
  startTokenIndex: number;
  endTokenIndexExclusive: number;
  startTokenId: string | null;
  endTokenId: string | null;
  onCameraResumes: boolean;
}

/** One card in the row's stack, in the order the pictures appear. */
export interface ProjectedCardV2 {
  kind: "on_camera" | "visual" | "undefined" | "unattached_visual";
  /** A compact "resumes" card: the same picture returning after a cutaway. Never the first On Camera in a row. */
  compact: boolean;
  slotId: string;
  payloadId: string | null;
  humanOrdinal: number | null;
  framing: OnCameraFramingV2 | null;
  /** The words this card connects to; null only for an unattached visual. */
  startTokenIndex: number | null;
  endTokenIndexExclusive: number | null;
  /** Offered only for a deliberately placed visual that lost its words, never for On Camera. */
  recovery: "attach_to_words" | null;
}

/** The word range a placed visual's brackets enclose, cutaways inside it included. On Camera has none. */
export interface ProjectedBracketV2 {
  slotId: string;
  payloadId: string | null;
  startTokenIndex: number;
  endTokenIndexExclusive: number;
  startTokenId: string | null;
  lastTokenId: string | null;
}

export interface ProjectedUnattachedVisualV2 {
  slotId: string;
  payloadId: string;
  recovery: "attach_to_words";
}

export interface ProjectedPrimarySlotV2 {
  slotId: string;
  payloadId: string | null;
  structuralIndex: number;
  humanOrdinal: number | null;
  relation: "base" | "sequential" | "cutaway";
  parentSlotId: string | null;
  startTokenIndex: number | null;
  payloadKind: "on_camera" | "visual" | "undefined";
}

export interface ProjectedReturnV2 {
  returnSlotId: string;
  parentSlotId: string;
  structuralIndex: number;
  parentOrdinal: number | null;
  startTokenIndex: number | null;
}

export interface ProjectedOverlayV2 {
  overlayEventId: string;
  payloadId: string;
  humanOrdinal: number | null;
  startTokenIndex: number | null;
  endTokenIndex: number | null;
  timing: TimedPlacement;
  parentSlotId: null;
}

export interface ProjectedSupportingItemV2 {
  itemId: string;
  role: SupportingItemV2["role"];
  placementKind: SupportingItemV2["placement"]["kind"];
  placement: SupportingItemV2["placement"];
  interval: null;
}

export interface MediaCutEstimateV2 {
  policy: "media_cut_estimate/v1";
  label: "Estimated media-timed cut";
  controllerSlotId: string;
  nextSlotId: string;
  timingSource: "verified_preview" | "400ms_per_token_fallback";
  estimatedCutSeconds: RationalTime;
  tokenWindow: string[];
  inputHash: string;
  numberedCapsOmitted: true;
}

export interface PrimarySequenceRowProjectionV2 {
  blockId: string;
  sequenceId: string | null;
  renderable: boolean;
  tokens: ProjectedTokenV2[];
  appearances: ProjectedAppearanceV2[];
  cards: ProjectedCardV2[];
  brackets: ProjectedBracketV2[];
  unattached: ProjectedUnattachedVisualV2[];
  slots: ProjectedPrimarySlotV2[];
  returns: ProjectedReturnV2[];
  overlays: ProjectedOverlayV2[];
  supportingItems: ProjectedSupportingItemV2[];
  mediaCutEstimates: MediaCutEstimateV2[];
  diagnostics: AuthoringDiagnosticV2[];
}

export interface PrimarySequenceProjectionV2 {
  rows: PrimarySequenceRowProjectionV2[];
  diagnostics: AuthoringDiagnosticV2[];
}

export interface PlacementBoundsV2 {
  start: RationalTime;
  end: RationalTime;
}

export interface PlacementResolutionContextV2 {
  document: ScriptDocumentV2;
  blockId: string;
  rowBounds: PlacementBoundsV2;
  anchorTimes: Readonly<Record<string, RationalTime>>;
}

export interface ResolvedPlacementV2 {
  start: RationalTime;
  end: RationalTime;
  duration: RationalTime;
}

export interface PlacementResolutionResultV2 {
  status: "resolved" | "unplaced" | "refused";
  interval: ResolvedPlacementV2 | null;
  diagnostics: AuthoringDiagnosticV2[];
}

export type VisualDestinationV2 =
  | {
      kind: "sequential";
      boundary: WordBoundaryAnchorV2;
      slotId: string;
    }
  | {
      kind: "cutaway";
      boundary: WordBoundaryAnchorV2;
      parentSlotId: string;
      slotId: string;
      returnSlotId?: string;
    };

export type VisualSequenceEditCommandV2 =
  | {
      kind: "insert_sequential";
      blockId: string;
      boundary: WordBoundaryAnchorV2;
      slotId: string;
      payload?: ContentSlot["payload"];
      undefinedPayloadId?: string;
    }
  | {
      kind: "insert_cutaway";
      blockId: string;
      boundary: WordBoundaryAnchorV2;
      parentSlotId: string;
      slotId: string;
      returnSlotId: string;
      payload: ContentSlot["payload"];
    }
  | {
      kind: "convert_sequential_to_cutaway";
      blockId: string;
      slotId: string;
      returnSlotId: string;
    }
  | {
      kind: "flatten_cutaway_group";
      blockId: string;
      parentSlotId: string;
    }
  | {
      kind: "move_word_boundary";
      blockId: string;
      boundaryOwnerId: string;
      tokenId: string;
      affinity?: "before" | "after";
    }
  | {
      kind: "swap_payloads";
      blockId: string;
      firstSlotId: string;
      secondSlotId: string;
    }
  | {
      /** Swap ranges: two placed visuals exchange word anchors; sources, trims and comments stay with each visual. */
      kind: "swap_ranges";
      blockId: string;
      firstSlotId: string;
      secondSlotId: string;
    }
  | {
      /**
       * Give a placed visual the whole selection, first to last word inclusive.
       * Neighbouring visuals make room, On Camera fills every word left
       * uncovered, and returns are recalculated in the same edit.
       */
      kind: "set_visual_range";
      blockId: string;
      slotId: string;
      startTokenId: string;
      endTokenId: string;
    }
  | {
      /** The only authored On Camera choice: Wide or Tight for one passage. */
      kind: "set_on_camera_framing";
      blockId: string;
      slotId: string;
      framing: OnCameraFramingV2;
    }
  | {
      /**
       * Drag a visual card to another row (D87, D88). The visual keeps its
       * source and trim. In a row with narration it lands with no words,
       * waiting for Attach to words; in a row with no narration it is simply
       * that row's picture (D146). On Camera fills the words it leaves.
       */
      kind: "move_visual_to_row";
      blockId: string;
      slotId: string;
      destinationBlockId: string;
      /** Mandatory when receiving into a true visuals-only row; guards its independent revision. */
      expectedDestinationRowVersion?: number;
    }
  | {
      /** Add one source-free visual on selected spoken words, with all range changes in one Undo step (D94). */
      kind: "add_visual_on_selection";
      blockId: string;
      slotId: string;
      payloadId: string;
      startTokenId: string;
      endTokenId: string;
      visualType: "onscreen_placeholder" | "need_to_find" | "visual_undefined";
    }
  | {
      /** Attach to words (D113): give a waiting visual the whole selection; neighbours make room as for a range change. */
      kind: "attach_visual_to_words";
      blockId: string;
      slotId: string;
      startTokenId: string;
      endTokenId: string;
    }
  | {
      /**
       * Change type (D93, D100). The visual keeps its words, its identity and
       * so its comments. Anything the new type cannot hold is listed in
       * `evidence.dropped`. Choosing On Camera removes the visual, because On
       * Camera is what fills words no visual covers.
       */
      kind: "change_visual_type";
      blockId: string;
      slotId: string;
      to: VisualTypeChangeV2;
    }
  | {
      /**
       * Delete a visual (D100). On Camera fills its words. Deleting the row's
       * last visual leaves a Visual Undefined card on those words instead.
       */
      kind: "delete_visual";
      blockId: string;
      slotId: string;
    }
  | {
      kind: "move_payload";
      sourceBlockId: string;
      sourceSlotId: string;
      sourceRepair: "reject" | "delete_children";
      destinationBlockId: string;
      expectedDestinationSequenceVersion: number;
      replacementSlotId?: string;
      replacementPayloadId?: string;
      destination: VisualDestinationV2;
    }
  | {
      kind: "delete_slot";
      blockId: string;
      slotId: string;
      childRepair?: "reject" | "delete_children";
      replacementSlotId?: string;
      replacementPayloadId?: string;
    }
  | {
      kind: "set_playout_policy";
      blockId: string;
      slotId: string;
      policy: ContentSlot["playoutPolicy"];
      nextBoundary?: WordBoundaryAnchorV2;
    }
  | {
      kind: "promote_supporting_picture";
      blockId: string;
      supportingItemId: string;
      destination: VisualDestinationV2;
      audioPolicy: "mute" | "quiet";
      framingPolicy: "contain" | "cover" | "native";
      sourceUsage: { sourceInFrame: number } | null;
    };

type VisualSourceV2 = NarratedVisualPayloadV2["source"];

/**
 * The type list of D93. A type that shows media takes its source here; when
 * `source` is left out the visual keeps its current source if the new type can
 * show it, and otherwise becomes Need to Find until one is chosen.
 */
export type VisualTypeChangeV2 =
  | { type: "footage"; source?: Extract<VisualSourceV2, { kind: "media_reference" }>; sourceInFrame?: number }
  | { type: "still_image"; source?: Extract<VisualSourceV2, { kind: "media_reference" }> }
  | { type: "web_capture"; source?: Extract<VisualSourceV2, { kind: "capture_revision" }> }
  | { type: "graphic"; source?: Extract<VisualSourceV2, { kind: "graphic_revision" }> }
  | { type: "onscreen_placeholder"; text?: string }
  | { type: "need_to_find"; description?: string }
  | { type: "visual_undefined" }
  | { type: "on_camera" };

/** One thing a Change type could not carry over, in words the writer can read. */
export interface DroppedVisualDetailV2 {
  what: "source" | "trim" | "research_clip" | "image_motion" | "source_audio" | "visual";
  message: string;
}

export interface VisualEditEvidenceV2 {
  kind: VisualSequenceEditCommandV2["kind"];
  blockIds: string[];
  slotIds: string[];
  payloadIds: string[];
  /** Change type only: what the new type could not keep. Empty when nothing was lost. */
  dropped?: DroppedVisualDetailV2[];
  supportingItemId?: string;
  lineage?: { fromSupportingItemId: string; toPayloadId: string };
  beforeSequenceVersions: Record<string, number>;
  afterSequenceVersions: Record<string, number>;
}

export interface VisualSequenceEditResultV2 {
  ok: boolean;
  document: ScriptDocumentV2;
  diagnostics: AuthoringDiagnosticV2[];
  evidence?: VisualEditEvidenceV2;
}

export { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
export {
  compareSecondaryTimingV2,
  SecondaryTimingComparisonErrorV2,
  type SecondaryTimingComparisonV2,
  type SecondaryBoundaryDifferenceV2,
  type SecondaryVisualEventDifferenceV2,
  type SecondaryTimingProblemCodeV2,
} from "./secondary-timing-v2.js";
export {
  previewSecondaryTimingReconcileV2,
  type SecondaryTimingReconcileCodeV2,
  type SecondaryTimingReconcileCommandV2,
  type SecondaryTimingReconcileResultV2,
} from "./secondary-timing-reconcile-v2.js";
export {
  snapshotResearchCandidateV2,
  inwardUseRangeV2,
  createResearchClipOccurrenceV2,
  withResearchClipUseRangeV2,
  trimResearchClipOccurrenceV2,
  findPrimaryResearchOwnerV2,
  resetResearchClipOccurrenceV2,
  type ResearchClipTrimChangeV2,
  type ResearchLoggedCandidateInputV2,
  type ResearchClipOccurrenceInputV2,
  type FrameIntervalV2,
} from "./authoring-v2-research-snapshot.js";
export {
  insertResearchClipBrowserV2,
  type ResearchClipBrowserDestinationV2,
  type ResearchClipBrowserInsertV2,
} from "./research-clip-browser-insert.js";
export {
  indexResearchClipUsageV2,
  type ResearchClipLocationKindV2,
  type ResearchClipUseLocationV2,
  type ResearchClipUsageV2,
} from "./research-clip-usage-v2.js";
export {
  createCommentStateV2, applyCommentOperationV2, serializeCommentStateV2, deserializeCommentStateV2,
  type CommentAnchorV2, type CommentAttachmentV2, type CommentMessageV2, type CommentThreadV2,
  type CommentOperationV2, type CommentStateV2, type CommentResultV2,
} from "./authoring-v2-comments.js";
export { projectPrimarySequenceV2 } from "./authoring-v2-projection.js";
export {
  spliceNarrationTextV2,
  type NarrationTextReplacementV2,
  type NarrationTextIdentityV2,
  type NarrationTextSpliceResultV2,
} from "./authoring-v2-narration-text.js";
export { LEGACY_VISUAL_HOLD_MS } from "./authoring-v2-wordless.js";
export { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
export {
  prepareResearchQuotePlacementV2,
  placeResearchQuoteV2,
  type AuthorizedResearchQuoteV2,
  type ResearchQuoteBackgroundV2,
  type ResearchQuotePlacementV2,
  type PreparedResearchQuotePlacementV2,
} from "./research-quote-placement.js";
export { visualTypeLabelV2 } from "./authoring-v2-visual-type.js";
export {
  applyStageDirectionEditV2,
  undoStageDirectionEditV2,
  type StageDirectionEditCommandV2,
  type StageDirectionEditResultV2,
  type StageDirectionUndoV2,
} from "./authoring-v2-stage-direction-edits.js";
export {
  inspectStageDirectionsV2,
  maskStageDirectionsV2,
  commentQuoteV2,
  spokenNarrationViewV2,
  spokenTokensV2,
  type StageDirectionIssueV2,
  type StageDirectionRunV2,
  type SpokenNarrationViewV2,
} from "./authoring-v2-stage-directions.js";
export { createSortingTrialV2, resumeSortingTrialV2, type SortingAcceptanceV2, type SortingResultV2 } from "./authoring-v2-sorting.js";
export { resolveSortingCommentsV2, type SortingCommentContextV2 } from "./authoring-v2-sorting-comments.js";
export { applyStashRowEditV2, type StashRowEditCommandV2, type StashedRowV2 } from "./authoring-v2-stash.js";
export type { StashRowGroupV2 } from "./generated/contracts-v2.js";
export {
  stashGroupLocationProblemV2, stashGroupMembershipProblemV2,
  beginStashGroupMemberStageV2, stageStashGroupMembersV2,
  cancelStashGroupMemberStageV2, saveStashGroupStageCommandV2,
  type StashGroupMemberStageV2, type StashGroupMemberV2, type SaveStashGroupCommandV2,
} from "./authoring-v2-stash-groups.js";
export {
  applyRowEditV2,
  selectRowRangeV2,
  createRowEditSessionV2,
  serializeAuthoringDocumentV2,
  deserializeAuthoringDocumentV2,
  parkAttachedFootageForSortingV2,
  presentAttachedFootageForSortingV2,
  type RowEditCommandV2,
  type StashFootageCommandV2,
  type StashGroupCommandV2,
  type RowEditResultV2,
  type RowGapV2,
} from "./authoring-v2-rows.js";
export type { JoinRowsCommandV2, RowWordSelectionV2, SplitRowCommandV2 } from "./authoring-v2-row-split-join.js";
export { cutNarrationWordRangeV2 } from "./authoring-v2-row-split-join.js";
export {
  isStashSelectedWordsCommandV2, prepareStashWordCutV2,
  isInsertStashNoteWordsCommandV2, spliceSpokenStashNoteV2,
  type StashSelectedWordsCommandV2, type InsertStashNoteWordsCommandV2,
} from "./authoring-v2-stash-words.js";
export {
  placementAnchorKeyV2,
  resolveTimedPlacementV2,
} from "./authoring-v2-placement.js";
