import {
  Ajv2020,
  type ErrorObject,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import scriptDocumentSchema from "../../../contracts/script-document-v2.schema.json" with {
  type: "json",
};
import projectSettingsSchema from "../../../contracts/authoring-project-settings-v1.schema.json" with {
  type: "json",
};
import type {
  ContentSlot,
  NarrationBlockV2,
  ReturnSlot,
  ScriptDocumentV2,
  SupportingItemV2,
  TextAnchorRange,
  TimedPlacement,
  WordInpointAnchor,
} from "./generated/contracts-v2.js";
import type {
  AuthoringDiagnosticV2,
  AuthoringValidationResultV2,
} from "./authoring-v2.js";

type DraftBlock = ScriptDocumentV2["activeDraft"]["blocks"][number];
type PointAnchor = NonNullable<TimedPlacement["start"]>;

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(projectSettingsSchema);
const validateStructure = ajv.compile<ScriptDocumentV2>(scriptDocumentSchema);

/** Validate v2 serialization and authored semantics without repair or inference. */
export function validateScriptDocumentV2(
  input: unknown,
): AuthoringValidationResultV2 {
  if (!validateStructure(input)) {
    return {
      valid: false,
      diagnostics: (validateStructure.errors ?? []).map(schemaDiagnostic),
    };
  }
  const document = input;
  const diagnostics: AuthoringDiagnosticV2[] = [];
  const ids = new Map<string, string>();
  const blocksById = new Map<string, DraftBlock>();
  const overlayIds = new Set(
    document.activeDraft.blocks.flatMap((block) =>
      block.type === "narration" ? block.overlayEvents.map((event) => event.id) : [],
    ),
  );

  const addId = (id: string, path: string, owner?: string): void => {
    const prior = ids.get(id);
    if (prior !== undefined) {
      diagnostics.push({
        code: "ENTITY_ID_DUPLICATE",
        message: `Entity ID duplicates the entity at ${prior}.`,
        jsonPath: path,
        ...(owner ? { blockId: owner } : {}),
        entityId: id,
      });
    } else {
      ids.set(id, path);
    }
  };

  for (const [blockIndex, block] of document.activeDraft.blocks.entries()) {
    const path = `/activeDraft/blocks/${blockIndex}`;
    const prior = blocksById.get(block.id);
    if (prior) {
      diagnostics.push({
        code: "BLOCK_ID_DUPLICATE",
        message: `Block ID duplicates another active block.`,
        jsonPath: `${path}/id`,
        blockId: block.id,
        entityId: block.id,
      });
    } else blocksById.set(block.id, block);
    addId(block.id, `${path}/id`, block.id);
    if (block.type !== "narration") continue;

    validateTokens(block, path, diagnostics, addId);
    block.annotations?.forEach((annotation, annotationIndex) => {
      addId(annotation.id, `${path}/annotations/${annotationIndex}/id`, block.id);
      validateTextRange(
        annotation.range,
        document,
        `${path}/annotations/${annotationIndex}/range`,
        diagnostics,
        block.id,
      );
    });
    block.performanceBeats?.forEach((beat, beatIndex) => {
      addId(beat.id, `${path}/performanceBeats/${beatIndex}/id`, block.id);
      validateTextRange(
        beat.range,
        document,
        `${path}/performanceBeats/${beatIndex}/range`,
        diagnostics,
        block.id,
      );
    });

    const sequence = block.primaryVisualSequence;
    if (block.state === "active" && !sequence) {
      diagnostics.push({
        code: "PRIMARY_SEQUENCE_MISSING",
        message: "An active narration row requires one primary visual sequence.",
        jsonPath: `${path}/primaryVisualSequence`,
        blockId: block.id,
      });
    }
    if (sequence) {
      addId(sequence.id, `${path}/primaryVisualSequence/id`, block.id);
      validateSequence(block, sequence.slots, path, diagnostics, addId);
    }
    block.overlayEvents.forEach((event, eventIndex) => {
      const eventPath = `${path}/overlayEvents/${eventIndex}`;
      overlayIds.add(event.id);
      addId(event.id, `${eventPath}/id`, block.id);
      addId(event.payload.payloadId, `${eventPath}/payload/payloadId`, block.id);
      validateTimedAnchors(
        event.timing,
        document,
        block.id,
        `${eventPath}/timing`,
        diagnostics,
        event.id,
      );
    });
  }

  for (const [itemIndex, item] of document.activeDraft.supportingItems.entries()) {
    const path = `/activeDraft/supportingItems/${itemIndex}`;
    addId(item.id, `${path}/id`);
    validateSupportingItem(item, document, path, diagnostics, overlayIds);
  }

  return {
    valid: diagnostics.every((diagnostic) => diagnostic.severity === "warning"),
    diagnostics,
  };
}

export function isWordAnchorCurrentV2(
  anchor: WordInpointAnchor,
  row: NarrationBlockV2,
): boolean {
  if (anchor.blockId !== row.id) return false;
  const matches = row.tokens.filter((token) => token.id === anchor.tokenId);
  if (matches.length !== 1) return false;
  const token = matches[0]!;
  return token.value === anchor.quotedWord &&
    Number.isSafeInteger(token.startOffset) &&
    Number.isSafeInteger(token.endOffset) &&
    token.startOffset >= 0 &&
    token.endOffset > token.startOffset &&
    token.endOffset <= row.text.length &&
    row.text.slice(token.startOffset, token.endOffset) === token.value;
}

export function wordIndexV2(
  anchor: WordInpointAnchor,
  row: NarrationBlockV2,
): number | null {
  if (!isWordAnchorCurrentV2(anchor, row)) return null;
  return row.tokens.findIndex((token) => token.id === anchor.tokenId);
}

export function pointWordIndexV2(
  anchor: PointAnchor,
  row: NarrationBlockV2,
): number | null {
  return anchor.kind === "word" ? wordIndexV2(anchor.anchor, row) : null;
}

export function wordAnchorForTokenV2(
  row: NarrationBlockV2,
  tokenId: string,
  anchorVersion: number,
): WordInpointAnchor | null {
  const token = row.tokens.find((candidate) => candidate.id === tokenId);
  return token
    ? {
        blockId: row.id,
        tokenId,
        affinity: "before",
        quotedWord: token.value,
        anchorVersion,
      }
    : null;
}

function schemaDiagnostic(error: ErrorObject): AuthoringDiagnosticV2 {
  return {
    code: "SCHEMA_INVALID",
    message: `${error.instancePath || "/"} ${error.message ?? "does not match the v2 schema"}.`,
    jsonPath: error.instancePath || "/",
  };
}

function validateTokens(
  row: NarrationBlockV2,
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  addId: (id: string, path: string, owner?: string) => void,
): void {
  let previousEnd = 0;
  row.tokens.forEach((token, index) => {
    const tokenPath = `${path}/tokens/${index}`;
    addId(token.id, `${tokenPath}/id`, row.id);
    if (
      token.startOffset < previousEnd ||
      token.endOffset <= token.startOffset ||
      token.endOffset > row.text.length ||
      row.text.slice(token.startOffset, token.endOffset) !== token.value
    ) {
      diagnostics.push({
        code: "TOKEN_TEXT_MISMATCH",
        message: "Token offsets must be ordered and quote the exact UTF-16 text slice.",
        jsonPath: tokenPath,
        blockId: row.id,
        entityId: token.id,
      });
    }
    previousEnd = Math.max(previousEnd, token.endOffset);
  });
}

function validateSequence(
  row: NarrationBlockV2,
  slots: (ContentSlot | ReturnSlot)[],
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  addId: (id: string, path: string, owner?: string) => void,
): void {
  const sequencePath = `${path}/primaryVisualSequence`;
  if (slots.length === 0) {
    diagnostics.push({
      code: "PRIMARY_SEQUENCE_EMPTY",
      message: "A primary visual sequence must contain a base content slot.",
      jsonPath: `${sequencePath}/slots`,
      blockId: row.id,
    });
    return;
  }

  const slotById = new Map<string, ContentSlot>();
  const childrenByParent = new Map<string, ContentSlot[]>();
  const roots: ContentSlot[] = [];
  const indexedBoundaries: { index: number; path: string; id: string }[] = [];
  const appendBoundary = (
    anchor: WordInpointAnchor,
    ownerPath: string,
    ownerId: string,
  ): number | null => {
    const index = wordIndexV2(anchor, row);
    if (index === null) {
      diagnostics.push({
        code: "STALE_WORD_ANCHOR",
        message: "The anchor must name this row, a current stable token ID, and its exact spoken text.",
        jsonPath: ownerPath,
        blockId: row.id,
        entityId: ownerId,
      });
      return null;
    }
    indexedBoundaries.push({ index, path: ownerPath, id: ownerId });
    return index;
  };

  let cursor = 0;
  while (cursor < slots.length) {
    const slot = slots[cursor]!;
    const slotPath = `${sequencePath}/slots/${cursor}`;
    if (slot.kind === "return") {
      addId(slot.id, `${slotPath}/id`, row.id);
      diagnostics.push({
        code: "RETURN_WITHOUT_CUTAWAY",
        message: "A return must immediately follow a cutaway group.",
        jsonPath: slotPath,
        blockId: row.id,
        entityId: slot.id,
      });
      cursor += 1;
      continue;
    }

    addId(slot.id, `${slotPath}/id`, row.id);
    slotById.set(slot.id, slot);
    if (slot.payload.kind !== "on_camera") {
      addId(slot.payload.payloadId, `${slotPath}/payload/payloadId`, row.id);
    }
    if (slot.relation.kind === "cutaway") {
      diagnostics.push({
        code: "CUTAWAY_PARENT_ORDER_INVALID",
        message: "A cutaway must follow its root inside that root's one-level group.",
        jsonPath: `${slotPath}/relation`,
        blockId: row.id,
        entityId: slot.id,
      });
      if (!childrenByParent.has(slot.relation.parentSlotId)) {
        childrenByParent.set(slot.relation.parentSlotId, []);
      }
      childrenByParent.get(slot.relation.parentSlotId)!.push(slot);
      if (slot.boundaryBefore.kind === "spoken_word") {
        appendBoundary(slot.boundaryBefore.anchor, `${slotPath}/boundaryBefore/anchor`, slot.id);
      }
      cursor += 1;
      continue;
    }

    const expectedRelation = cursor === 0 ? "base" : "sequential";
    if (slot.relation.kind !== expectedRelation) {
      diagnostics.push({
        code: "ROOT_RELATION_INVALID",
        message: `Root slot ${cursor} must have relation ${expectedRelation}.`,
        jsonPath: `${slotPath}/relation`,
        blockId: row.id,
        entityId: slot.id,
      });
    }
    if (cursor === 0 && slot.boundaryBefore.kind !== "row_start") {
      diagnostics.push({
        code: "BASE_BOUNDARY_INVALID",
        message: "The base slot begins at row_start.",
        jsonPath: `${slotPath}/boundaryBefore`,
        blockId: row.id,
        entityId: slot.id,
      });
    } else if (cursor === 0) {
      indexedBoundaries.push({ index: 0, path: `${slotPath}/boundaryBefore`, id: slot.id });
    } else if (cursor > 0) {
      if (slot.boundaryBefore.kind === "row_start") {
        diagnostics.push({
          code: "ROOT_BOUNDARY_INVALID",
          message: "Only the base slot may begin at row_start.",
          jsonPath: `${slotPath}/boundaryBefore`,
          blockId: row.id,
          entityId: slot.id,
        });
      } else if (slot.boundaryBefore.kind === "spoken_word") {
        appendBoundary(slot.boundaryBefore.anchor, `${slotPath}/boundaryBefore/anchor`, slot.id);
      }
    }
    roots.push(slot);
    cursor += 1;

    const childSlots: ContentSlot[] = [];
    while (cursor < slots.length) {
      const child = slots[cursor]!;
      if (child.kind !== "content" || child.relation.kind !== "cutaway") break;
      const childPath = `${sequencePath}/slots/${cursor}`;
      addId(child.id, `${childPath}/id`, row.id);
      if (child.payload.kind !== "on_camera") {
        addId(child.payload.payloadId, `${childPath}/payload/payloadId`, row.id);
      }
      slotById.set(child.id, child);
      childSlots.push(child);
      childrenByParent.set(slot.id, childSlots);
      if (child.relation.parentSlotId !== slot.id) {
        diagnostics.push({
          code: "CUTAWAY_PARENT_MISMATCH",
          message: "Every child in a cutaway group must name the immediately active root.",
          jsonPath: `${childPath}/relation/parentSlotId`,
          blockId: row.id,
          entityId: child.id,
        });
      }
      if (child.playoutPolicy !== "match_structural_interval") {
        diagnostics.push({
          code: "CUTAWAY_COMPLETE_CLIP_FORBIDDEN",
          message: "Cutaways cannot use complete-clip playout.",
          jsonPath: `${childPath}/playoutPolicy`,
          blockId: row.id,
          entityId: child.id,
        });
      }
      if (child.boundaryBefore.kind === "spoken_word") {
        appendBoundary(child.boundaryBefore.anchor, `${childPath}/boundaryBefore/anchor`, child.id);
      } else {
        diagnostics.push({
          code: "CUTAWAY_BOUNDARY_INVALID",
          message: "A cutaway begins at an exact spoken-word boundary.",
          jsonPath: `${childPath}/boundaryBefore`,
          blockId: row.id,
          entityId: child.id,
        });
      }
      cursor += 1;
    }

    if (childSlots.length > 0) {
      const possibleReturn = slots[cursor];
      if (!possibleReturn || possibleReturn.kind !== "return") {
        diagnostics.push({
          code: "CUTAWAY_RETURN_MISSING",
          message: "A cutaway group requires one return before the next root.",
          jsonPath: `${sequencePath}/slots/${cursor}`,
          blockId: row.id,
          entityId: slot.id,
        });
      } else {
        const returnPath = `${sequencePath}/slots/${cursor}`;
        addId(possibleReturn.id, `${returnPath}/id`, row.id);
        if (possibleReturn.parentSlotId !== slot.id) {
          diagnostics.push({
            code: "RETURN_PARENT_MISMATCH",
            message: "The return must name the root that owns the cutaway group.",
            jsonPath: `${returnPath}/parentSlotId`,
            blockId: row.id,
            entityId: possibleReturn.id,
          });
        }
        if (possibleReturn.inpoint === null) {
          diagnostics.push({
            code: "RETURN_INPOINT_MISSING",
            message: "Choose an exact word to make the cutaway row renderable.",
            jsonPath: `${returnPath}/inpoint`,
            blockId: row.id,
            entityId: possibleReturn.id,
          });
        } else {
          appendBoundary(possibleReturn.inpoint, `${returnPath}/inpoint`, possibleReturn.id);
        }
        cursor += 1;
      }
    }
  }

  for (const [boundaryIndex, boundary] of indexedBoundaries.entries()) {
    const previous = indexedBoundaries[boundaryIndex - 1];
    if (!previous) continue;
    if (boundary.index <= previous.index) {
      diagnostics.push({
        code: boundary.index === previous.index ? "BOUNDARY_DUPLICATE" : "BOUNDARY_ORDER_INVALID",
        message: "Spoken-word structural boundaries must be unique and strictly increasing.",
        jsonPath: boundary.path,
        blockId: row.id,
        entityId: boundary.id,
      });
    }
  }

  for (const root of roots) {
    const children = childrenByParent.get(root.id) ?? [];
    if (root.playoutPolicy !== "complete_logged_clip") continue;
    const rootPosition = roots.indexOf(root);
    const next = roots[rootPosition + 1];
    const validClip = root.payload.kind === "visual" &&
      root.payload.pictureKind === "clip" &&
      root.payload.sourceUsage !== null;
    if (!validClip || children.length > 0 || !next || next.payload.kind !== "visual" || next.payload.pictureKind !== "clip") {
      diagnostics.push({
        code: "COMPLETE_CLIP_SHAPE_INVALID",
        message: "Complete-clip playout requires a child-free root clip followed by another root clip.",
        jsonPath: `${sequencePath}/slots/${slots.indexOf(root)}/playoutPolicy`,
        blockId: row.id,
        entityId: root.id,
      });
    }
    if (
      next &&
      (next.boundaryBefore.kind !== "previous_media_end" || next.boundaryBefore.controllingSlotId !== root.id)
    ) {
      diagnostics.push({
        code: "COMPLETE_CLIP_NEXT_BOUNDARY_INVALID",
        message: "The immediate next root must start at this clip's previous_media_end.",
        jsonPath: `${sequencePath}/slots/${slots.indexOf(next)}/boundaryBefore`,
        blockId: row.id,
        entityId: root.id,
      });
    }
    const previous = roots[rootPosition - 1];
    if (previous?.payload.kind === "on_camera") {
      diagnostics.push({
        code: "COMPLETE_CLIP_ON_CAMERA_ADJACENT",
        message: "A complete-clip root cannot be adjacent to On Camera.",
        jsonPath: `${sequencePath}/slots/${slots.indexOf(root)}/playoutPolicy`,
        blockId: row.id,
        entityId: root.id,
      });
    }
  }

  for (const root of roots) {
    if (root.boundaryBefore.kind !== "previous_media_end") continue;
    const previous = roots[roots.indexOf(root) - 1];
    if (
      !previous ||
      previous.id !== root.boundaryBefore.controllingSlotId ||
      previous.playoutPolicy !== "complete_logged_clip"
    ) {
      diagnostics.push({
        code: "MEDIA_END_CONTROLLER_INVALID",
        message: "A media-end boundary must name the immediately preceding complete-clip root.",
        jsonPath: `${sequencePath}/slots/${slots.indexOf(root)}/boundaryBefore`,
        blockId: row.id,
        entityId: root.id,
      });
    }
  }

  for (const slot of slotById.values()) {
    if (slot.playoutPolicy === "complete_logged_clip" && slot.relation.kind === "cutaway") {
      diagnostics.push({
        code: "COMPLETE_CLIP_CUTAWAY_FORBIDDEN",
        message: "Complete-clip playout cannot be assigned to a child slot.",
        jsonPath: `${sequencePath}/slots/${slots.indexOf(slot)}/playoutPolicy`,
        blockId: row.id,
        entityId: slot.id,
      });
    }
  }
}

function validateSupportingItem(
  item: SupportingItemV2,
  document: ScriptDocumentV2,
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  overlayIds: ReadonlySet<string>,
): void {
  const placement = item.placement;
  if (placement.kind === "unplaced") {
    if (item.role === "picture") {
      diagnostics.push({
        code: "SUPPORTING_PICTURE_UNPLACED",
        message: "This picture has no derived interval until an author explicitly places it.",
        jsonPath: `${path}/placement`,
        severity: "warning",
        entityId: item.id,
      });
    }
    return;
  }
  if (item.role === "picture" && (!item.pictureKind || !item.source)) {
    diagnostics.push({
      code: "SUPPORTING_PICTURE_IDENTITY_MISSING",
      message: "A placed picture requires an explicit subtype and source identity.",
      jsonPath: path,
      entityId: item.id,
    });
  }
  if (placement.kind === "range") {
    validateTextRange(placement.range, document, `${path}/placement/range`, diagnostics, undefined);
  } else if (placement.kind === "point") {
    validatePointAnchor(placement.anchor, document, undefined, `${path}/placement/anchor`, diagnostics, overlayIds);
  } else {
    validateTimedAnchors(placement, document, undefined, `${path}/placement`, diagnostics, undefined, overlayIds);
  }
}

function validateTextRange(
  range: TextAnchorRange,
  document: ScriptDocumentV2,
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  owner?: string,
): void {
  const row = document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.id === range.blockId,
  );
  const start = row?.tokens.find((token) => token.id === range.startTokenId);
  const end = row?.tokens.find((token) => token.id === range.endTokenId);
  const startPosition = start
    ? range.startAffinity === "before" ? start.startOffset : start.endOffset
    : -1;
  const endPosition = end
    ? range.endAffinity === "before" ? end.startOffset : end.endOffset
    : -1;
  if (
    !row ||
    !start ||
    !end ||
    row.tokens.indexOf(start) > row.tokens.indexOf(end) ||
    startPosition >= endPosition ||
    row.text.slice(startPosition, endPosition) !== range.quotedText
  ) {
    diagnostics.push({
      code: "STALE_TEXT_RANGE",
      message: "The text range must resolve to its exact current token text and offsets.",
      jsonPath: path,
      ...(owner ? { blockId: owner } : {}),
      ...(owner ? { entityId: owner } : {}),
    });
  }
}

function validateTimedAnchors(
  placement: TimedPlacement,
  document: ScriptDocumentV2,
  ownerBlockId: string | undefined,
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  ownerId?: string,
  overlayIds?: ReadonlySet<string>,
): void {
  for (const edge of ["start", "end"] as const) {
    const anchor = placement[edge];
    if (!anchor) continue;
    validatePointAnchor(
      anchor,
      document,
      ownerBlockId,
      `${path}/${edge}`,
      diagnostics,
      overlayIds,
      ownerId,
    );
    if (anchor.kind === "event_edge" && anchor.eventId === ownerId) {
      diagnostics.push({
        code: "EVENT_EDGE_SELF_REFERENCE",
        message: "A timed placement cannot resolve one of its own event edges.",
        jsonPath: `${path}/${edge}`,
        ...(ownerBlockId ? { blockId: ownerBlockId } : {}),
        ...(ownerId ? { entityId: ownerId } : {}),
      });
    }
  }
}

function validatePointAnchor(
  anchor: PointAnchor,
  document: ScriptDocumentV2,
  ownerBlockId: string | undefined,
  path: string,
  diagnostics: AuthoringDiagnosticV2[],
  overlayIds: ReadonlySet<string> = new Set(),
  ownerId?: string,
): void {
  let current: boolean;
  if (anchor.kind === "word") {
    const row = document.activeDraft.blocks.find(
      (block): block is NarrationBlockV2 => block.type === "narration" && block.id === anchor.anchor.blockId,
    );
    current = !!row &&
      (!ownerBlockId || ownerBlockId === row.id) &&
      isWordAnchorCurrentV2(anchor.anchor, row);
  } else if (anchor.kind === "between_blocks") {
    const blocks = document.activeDraft.blocks;
    const before = blocks.findIndex((block) => block.id === anchor.beforeBlockId);
    const after = blocks.findIndex((block) => block.id === anchor.afterBlockId);
    current = before >= 0 && after === before + 1;
  } else {
    current = overlayIds.has(anchor.eventId);
  }
  if (!current) {
    diagnostics.push({
      code: "STALE_PLACEMENT_ANCHOR",
      message: "The placement anchor must identify a current exact row, token, adjacent block pair, or event edge.",
      jsonPath: path,
      ...(ownerBlockId ? { blockId: ownerBlockId } : {}),
      ...(ownerId ? { entityId: ownerId } : {}),
    });
  }
}
