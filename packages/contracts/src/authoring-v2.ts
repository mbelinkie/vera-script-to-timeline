import type {
  ContentSlot,
  NarrationTokenTimingMapV2,
  RationalRate,
  RationalTime,
  ScriptDocumentV2,
  SupportingItemV2,
  TimedPlacement,
  WordInpointAnchor,
} from "./generated/contracts-v2.js";

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
  startTokenIndex: number;
  endTokenIndexExclusive: number;
  startTokenId: string | null;
  endTokenId: string | null;
  onCameraResumes: boolean;
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
      boundary: WordInpointAnchor;
      slotId: string;
    }
  | {
      kind: "cutaway";
      boundary: WordInpointAnchor;
      parentSlotId: string;
      slotId: string;
      returnSlotId?: string;
    };

export type VisualSequenceEditCommandV2 =
  | {
      kind: "insert_sequential";
      blockId: string;
      boundary: WordInpointAnchor;
      slotId: string;
      payload?: ContentSlot["payload"];
      undefinedPayloadId?: string;
    }
  | {
      kind: "insert_cutaway";
      blockId: string;
      boundary: WordInpointAnchor;
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
    }
  | {
      kind: "swap_payloads";
      blockId: string;
      firstSlotId: string;
      secondSlotId: string;
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
      nextBoundary?: WordInpointAnchor;
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

export interface VisualEditEvidenceV2 {
  kind: VisualSequenceEditCommandV2["kind"];
  blockIds: string[];
  slotIds: string[];
  payloadIds: string[];
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
export { projectPrimarySequenceV2 } from "./authoring-v2-projection.js";
export { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
export {
  placementAnchorKeyV2,
  resolveTimedPlacementV2,
} from "./authoring-v2-placement.js";
