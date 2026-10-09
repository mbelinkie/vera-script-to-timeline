import type {
  ContentSlot,
  NarrationBlockV2,
  ReturnSlot,
  ScriptDocumentV2,
  WordInpointAnchor,
} from "./generated/contracts-v2.js";
import {
  isWordAnchorCurrentV2,
  validateScriptDocumentV2,
  wordAnchorForTokenV2,
  wordIndexV2,
} from "./authoring-v2-validation.js";
import type {
  AuthoringDiagnosticV2,
  VisualDestinationV2,
  VisualEditEvidenceV2,
  VisualSequenceEditCommandV2,
  VisualSequenceEditResultV2,
} from "./authoring-v2.js";

type Sequence = NonNullable<NarrationBlockV2["primaryVisualSequence"]>;
type RootSlot = ContentSlot & {
  relation: Extract<ContentSlot["relation"], { kind: "base" | "sequential" }>;
};

interface RootGroup {
  root: RootSlot;
  rootIndex: number;
  children: ContentSlot[];
  returnSlot?: ReturnSlot;
  endIndex: number;
  nextRootIndex?: number;
}

interface MutationResult {
  diagnostics: AuthoringDiagnosticV2[];
  blockIds: string[];
  slotIds: string[];
  payloadIds: string[];
  supportingItemId?: string;
  lineage?: VisualEditEvidenceV2["lineage"];
}

/**
 * Apply one optimistic, immutable v2 edit. Failed edits return the input object
 * unchanged. Success returns a local canonical revision and operation evidence;
 * the application snapshot owner separately acknowledges and advances live
 * collaboration metadata.
 */
export function applyVisualSequenceEditV2(
  document: ScriptDocumentV2,
  expectedSequenceVersion: number,
  command: VisualSequenceEditCommandV2,
): VisualSequenceEditResultV2 {
  const beforeValidation = validateScriptDocumentV2(document);
  if (beforeValidation.diagnostics.some((diagnostic) => diagnostic.code === "SCHEMA_INVALID")) {
    return failure(document, beforeValidation.diagnostics.filter((diagnostic) => diagnostic.code === "SCHEMA_INVALID"));
  }

  const sourceBlockId = sequenceBlockId(command);
  const sourceRow = findRow(document, sourceBlockId);
  const sourceSequence = sourceRow?.primaryVisualSequence;
  if (!sourceRow || !sourceSequence) {
    return failure(document, [diag("PRIMARY_SEQUENCE_MISSING", "The edit row has no primary visual sequence.", sourceBlockId)]);
  }
  if (sourceSequence.version !== expectedSequenceVersion) {
    return failure(document, [diag("SEQUENCE_VERSION_STALE", "The primary sequence changed before this edit.", sourceBlockId)]);
  }

  const working = structuredClone(document);
  const mutation = applyCommand(working, expectedSequenceVersion, command);
  if (mutation.diagnostics.length > 0) return failure(document, mutation.diagnostics);

  const afterValidation = validateScriptDocumentV2(working);
  const newErrors = newlyIntroducedErrors(
    beforeValidation.diagnostics,
    afterValidation.diagnostics,
    command.kind === "insert_cutaway" || command.kind === "convert_sequential_to_cutaway"
      ? new Set(["RETURN_INPOINT_MISSING"])
      : new Set(),
  );
  if (newErrors.length > 0) return failure(document, newErrors);

  const afterVersions: Record<string, number> = {};
  for (const blockId of mutation.blockIds) {
    const sequence = findRow(working, blockId)?.primaryVisualSequence;
    if (sequence) afterVersions[blockId] = sequence.version;
  }
  const beforeVersions: Record<string, number> = {};
  for (const blockId of mutation.blockIds) {
    const sequence = findRow(document, blockId)?.primaryVisualSequence;
    if (sequence) beforeVersions[blockId] = sequence.version;
  }
  const evidence: VisualEditEvidenceV2 = {
    kind: command.kind,
    blockIds: mutation.blockIds,
    slotIds: mutation.slotIds,
    payloadIds: mutation.payloadIds,
    beforeSequenceVersions: beforeVersions,
    afterSequenceVersions: afterVersions,
    ...(mutation.supportingItemId ? { supportingItemId: mutation.supportingItemId } : {}),
    ...(mutation.lineage ? { lineage: mutation.lineage } : {}),
  };
  return { ok: true, document: working, diagnostics: [], evidence };
}

function applyCommand(
  document: ScriptDocumentV2,
  expectedVersion: number,
  command: VisualSequenceEditCommandV2,
): MutationResult {
  switch (command.kind) {
    case "insert_sequential": {
      const payload = command.payload ?? (command.undefinedPayloadId ? {
        kind: "undefined" as const,
        payloadId: command.undefinedPayloadId,
        description: "No visual payload has been assigned to this interval.",
      } : null);
      if (!payload) return refused("INSERT_PAYLOAD_REQUIRED", "Provide a visual payload or a stable ID for the explicit undefined payload.", command.blockId, command.slotId);
      return insertSequential(document, command.blockId, expectedVersion, command.boundary, command.slotId, payload);
    }
    case "insert_cutaway":
      return insertCutaway(document, command.blockId, expectedVersion, command.boundary, command.parentSlotId, command.slotId, command.returnSlotId, command.payload);
    case "convert_sequential_to_cutaway":
      return convertToCutaway(document, command.blockId, expectedVersion, command.slotId, command.returnSlotId);
    case "flatten_cutaway_group":
      return flattenGroup(document, command.blockId, expectedVersion, command.parentSlotId);
    case "move_word_boundary":
      return moveBoundary(document, command.blockId, expectedVersion, command.boundaryOwnerId, command.tokenId);
    case "swap_payloads":
      return swapPayloads(document, command.blockId, expectedVersion, command.firstSlotId, command.secondSlotId);
    case "move_payload":
      return movePayload(document, expectedVersion, command);
    case "delete_slot":
      return deleteSlot(document, command.blockId, expectedVersion, command.slotId, command.childRepair ?? "reject", command.replacementSlotId, command.replacementPayloadId);
    case "set_playout_policy":
      return setPlayoutPolicy(document, command.blockId, expectedVersion, command.slotId, command.policy, command.nextBoundary);
    case "promote_supporting_picture":
      return promoteSupportingPicture(document, command.blockId, expectedVersion, command.supportingItemId, command.destination, command.audioPolicy, command.framingPolicy, command.sourceUsage);
  }
}

function insertSequential(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  boundary: WordInpointAnchor,
  slotId: string,
  payload: ContentSlot["payload"],
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  if (!row || !sequence) return refused("PRIMARY_SEQUENCE_MISSING", "The row has no primary sequence.", blockId);
  const index = wordIndexV2(boundary, row);
  if (index === null || index === 0) return refused("INSERT_BOUNDARY_INVALID", "A root insert needs a current exact word after row start.", blockId, slotId);
  if (sequence.slots.some((slot) => boundaryIndex(slot, row) === index)) {
    return refused("BOUNDARY_DUPLICATE", "A structural boundary already uses this word.", blockId, slotId);
  }
  const location = insertionLocation(sequence, row, index);
  if (!location.ok) return refused(location.code, location.message, blockId, slotId);
  const slot: ContentSlot = {
    id: slotId,
    kind: "content",
    relation: { kind: "sequential" },
    boundaryBefore: { kind: "spoken_word", anchor: boundary },
    payload,
    playoutPolicy: "match_structural_interval",
    version: 1,
  };
  sequence.slots.splice(location.index, 0, slot);
  sequence.version += 1;
  return changed([blockId], [slotId], [payloadId(payload)]);
}

function insertCutaway(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  boundary: WordInpointAnchor,
  parentSlotId: string,
  slotId: string,
  returnSlotId: string,
  payload: ContentSlot["payload"],
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  const parent = sequence?.slots.find((slot): slot is RootSlot => slot.kind === "content" && slot.id === parentSlotId && slot.relation.kind !== "cutaway");
  if (!row || !sequence || !parent) return refused("CUTAWAY_PARENT_MISSING", "The cutaway parent must be an existing root.", blockId, parentSlotId);
  if (parent.playoutPolicy === "complete_logged_clip") return refused("COMPLETE_CLIP_CUTAWAY_FORBIDDEN", "Complete-clip roots cannot own cutaways.", blockId, parentSlotId);
  const selected = wordIndexV2(boundary, row);
  const parentStart = boundaryIndex(parent, row);
  if (selected === null || parentStart === null || selected <= parentStart) return refused("CUTAWAY_BOUNDARY_INVALID", "The cutaway must start after its current parent boundary.", blockId, slotId);
  if (sequence.slots.some((slot) => boundaryIndex(slot, row) === selected)) return refused("BOUNDARY_DUPLICATE", "A structural boundary already uses this word.", blockId, slotId);

  const group = groupFor(sequence, parentSlotId);
  if (!group) return refused("CUTAWAY_GROUP_INVALID", "The parent cutaway group cannot be resolved.", blockId, parentSlotId);
  const nextRoot = group.nextRootIndex === undefined ? undefined : sequence.slots[group.nextRootIndex] as RootSlot;
  if (nextRoot?.boundaryBefore.kind === "previous_media_end") return refused("CUTAWAY_BOUNDARY_UNRESOLVED", "A child cannot be inserted across an unresolved media-end root boundary.", blockId, slotId);
  const nextRootStart = nextRoot ? boundaryIndex(nextRoot, row) : row.tokens.length;
  if (nextRootStart === null || selected >= nextRootStart) return refused("CUTAWAY_OUTSIDE_PARENT", "The cutaway word must be before the next root boundary.", blockId, slotId);

  const childSlots = group.children;
  const previousChild = childSlots.at(-1);
  const previousChildStart = previousChild ? boundaryIndex(previousChild, row) : parentStart;
  if (previousChildStart === null || selected <= previousChildStart) return refused("CUTAWAY_BOUNDARY_INVALID", "The cutaway word must be after the preceding child boundary.", blockId, slotId);
  if (group.returnSlot?.inpoint) {
    const returnIndex = wordIndexV2(group.returnSlot.inpoint, row);
    if (returnIndex === null || selected >= returnIndex) return refused("CUTAWAY_BOUNDARY_INVALID", "The new child must start before the existing return.", blockId, slotId);
  }

  const child: ContentSlot = {
    id: slotId,
    kind: "content",
    relation: { kind: "cutaway", parentSlotId },
    boundaryBefore: { kind: "spoken_word", anchor: boundary },
    payload,
    playoutPolicy: "match_structural_interval",
    version: 1,
  };
  const insertionIndex = group.children.length > 0
    ? sequence.slots.indexOf(group.children.at(-1)!) + 1
    : group.rootIndex + 1;
  sequence.slots.splice(insertionIndex, 0, child);
  const createdReturnId = group.returnSlot ? null : returnSlotId;
  if (!group.returnSlot) {
    const returnSlot: ReturnSlot = {
      id: returnSlotId,
      kind: "return",
      parentSlotId,
      inpoint: null,
      version: 1,
    };
    sequence.slots.splice(insertionIndex + 1, 0, returnSlot);
  }
  sequence.version += 1;
  return changed([blockId], [slotId, ...(createdReturnId ? [createdReturnId] : [])], [payloadId(payload)]);
}

function convertToCutaway(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  slotId: string,
  returnSlotId: string,
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  const structuralIndex = sequence?.slots.findIndex((slot) => slot.kind === "content" && slot.id === slotId && slot.relation.kind === "sequential") ?? -1;
  const target = structuralIndex < 0 ? undefined : sequence?.slots[structuralIndex];
  if (!row || !sequence || !target || target.kind !== "content" || target.relation.kind !== "sequential") return refused("SEQUENTIAL_SLOT_MISSING", "Only an existing sequential root can become a cutaway.", blockId, slotId);
  const rootGroups = groups(sequence);
  const groupIndex = rootGroups.findIndex((group) => group.root.id === slotId);
  const parentGroup = rootGroups[groupIndex - 1];
  if (!parentGroup) return refused("CUTAWAY_PREVIOUS_ROOT_MISSING", "A cutaway needs a preceding root parent.", blockId, slotId);
  if ((rootGroups[groupIndex]?.children.length ?? 0) > 0) return refused("CUTAWAY_TARGET_HAS_CHILDREN", "A root with children cannot be converted to a cutaway.", blockId, slotId);
  if (parentGroup.root.playoutPolicy === "complete_logged_clip") return refused("COMPLETE_CLIP_CUTAWAY_FORBIDDEN", "Complete-clip roots cannot parent cutaways.", blockId, slotId);
  if (target.boundaryBefore.kind !== "spoken_word") return refused("CUTAWAY_BOUNDARY_UNRESOLVED", "A converted slot must retain its exact word boundary.", blockId, slotId);
  const boundaryIndex = wordIndexV2(target.boundaryBefore.anchor, row);
  if (boundaryIndex === null) return refused("STALE_WORD_ANCHOR", "The converted slot boundary is stale and cannot be inferred.", blockId, slotId);

  const existingReturn = parentGroup.returnSlot;
  if (parentGroup.children.length > 0 && (!existingReturn || !existingReturn.inpoint)) {
    return refused("RETURN_INPOINT_MISSING", "Repair the parent's existing return before merging this root into its cutaway group.", blockId, parentGroup.root.id);
  }
  if (existingReturn?.inpoint) {
    const priorReturnIndex = wordIndexV2(existingReturn.inpoint, row);
    if (priorReturnIndex === null || priorReturnIndex >= boundaryIndex) return refused("CUTAWAY_BOUNDARY_ORDER_INVALID", "The converted root must follow the existing return boundary.", blockId, slotId);
    sequence.slots.splice(sequence.slots.indexOf(existingReturn), 1);
  }
  const currentStructuralIndex = sequence.slots.findIndex((slot) => slot.kind === "content" && slot.id === target.id);
  if (currentStructuralIndex < 0) return refused("SEQUENTIAL_SLOT_MISSING", "The converted slot was removed during parent-return repair.", blockId, slotId);
  sequence.slots[currentStructuralIndex] = {
    ...target,
    relation: { kind: "cutaway", parentSlotId: parentGroup.root.id },
    version: target.version + 1,
  };
  sequence.slots.splice(currentStructuralIndex + 1, 0, {
    id: returnSlotId,
    kind: "return",
    parentSlotId: parentGroup.root.id,
    inpoint: null,
    version: 1,
  });
  sequence.version += 1;
  return changed([blockId], [slotId, returnSlotId], [payloadId(target.payload)]);
}

function flattenGroup(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  parentSlotId: string,
): MutationResult {
  const sequence = findRow(document, blockId)?.primaryVisualSequence;
  const group = sequence && groupFor(sequence, parentSlotId);
  if (!sequence || !group || group.children.length === 0 || !group.returnSlot) {
    return refused("CUTAWAY_GROUP_MISSING", "Flatten requires an existing cutaway group and return.", blockId, parentSlotId);
  }
  for (const child of group.children) {
    child.relation = { kind: "sequential" };
    child.version += 1;
  }
  sequence.slots.splice(sequence.slots.indexOf(group.returnSlot), 1);
  sequence.version += 1;
  return changed([blockId], [parentSlotId, ...group.children.map((child) => child.id), group.returnSlot.id], group.children.map((child) => payloadId(child.payload)));
}

function moveBoundary(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  boundaryOwnerId: string,
  tokenId: string,
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  if (!row || !sequence) return refused("PRIMARY_SEQUENCE_MISSING", "The row has no primary sequence.", blockId);
  const targetIndex = row.tokens.findIndex((token) => token.id === tokenId);
  if (targetIndex < 0) return refused("BOUNDARY_TOKEN_MISSING", "Choose an existing stable spoken-token ID.", blockId, boundaryOwnerId);
  const ownerIndex = sequence.slots.findIndex((slot) => slot.id === boundaryOwnerId);
  const owner = sequence.slots[ownerIndex];
  if (!owner) return refused("BOUNDARY_OWNER_MISSING", "The structural boundary no longer exists.", blockId, boundaryOwnerId);
  const priorBoundary = previousBoundary(sequence, row, ownerIndex);
  const nextBoundary = nextBoundaryAfter(sequence, row, ownerIndex);
  if (!priorBoundary || !nextBoundary) return refused("BOUNDARY_NEIGHBOR_UNRESOLVED", "The exact legal word interval is unknown because a neighboring boundary is stale or media-derived.", blockId, boundaryOwnerId);
  if (targetIndex <= priorBoundary.index || targetIndex >= nextBoundary.index) {
    return refused("BOUNDARY_CROSSED_OR_COLLAPSED", `Choose a word strictly after token index ${priorBoundary.index} and before token index ${nextBoundary.index}.`, blockId, boundaryOwnerId);
  }
  const anchor = wordAnchorForTokenV2(row, tokenId, currentAnchorVersion(owner) + 1);
  if (!anchor) return refused("BOUNDARY_TOKEN_MISSING", "Choose an existing stable spoken-token ID.", blockId, boundaryOwnerId);
  if (owner.kind === "return") {
    owner.inpoint = anchor;
    owner.version += 1;
  } else {
    if (owner.boundaryBefore.kind !== "spoken_word") return refused("BOUNDARY_FIXED", "The base and media-derived boundaries cannot be moved as exact word anchors.", blockId, boundaryOwnerId);
    owner.boundaryBefore = { kind: "spoken_word", anchor };
    owner.version += 1;
  }
  sequence.version += 1;
  return changed([blockId], [boundaryOwnerId], []);
}

function swapPayloads(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  firstSlotId: string,
  secondSlotId: string,
): MutationResult {
  const sequence = findRow(document, blockId)?.primaryVisualSequence;
  const first = sequence?.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.id === firstSlotId);
  const second = sequence?.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.id === secondSlotId);
  if (!sequence || !first || !second) return refused("SWAP_SLOT_MISSING", "Both swap targets must be existing content slots in this row.", blockId);
  if (first.id === second.id) return refused("SWAP_TARGETS_IDENTICAL", "Choose two different content slots.", blockId, first.id);
  const firstPayload = first.payload;
  const secondPayload = second.payload;
  if (!acceptsPolicy(first, secondPayload) || !acceptsPolicy(second, firstPayload)) {
    return refused("SWAP_PLAYOUT_INCOMPATIBLE", "A payload cannot satisfy the target slot's fixed structural playout policy.", blockId);
  }
  first.payload = secondPayload;
  second.payload = firstPayload;
  first.version += 1;
  second.version += 1;
  sequence.version += 1;
  return changed([blockId], [first.id, second.id], [payloadId(firstPayload), payloadId(secondPayload)]);
}

function movePayload(
  document: ScriptDocumentV2,
  expectedVersion: number,
  command: Extract<VisualSequenceEditCommandV2, { kind: "move_payload" }>,
): MutationResult {
  if (command.sourceBlockId === command.destinationBlockId) {
    return refused("CROSS_ROW_REQUIRED", "Use a payload swap for same-row card movement.", command.sourceBlockId);
  }
  const source = findRow(document, command.sourceBlockId);
  const destination = findRow(document, command.destinationBlockId);
  const sourceSequence = source?.primaryVisualSequence;
  const destinationSequence = destination?.primaryVisualSequence;
  const sourceSlot = sourceSequence?.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.id === command.sourceSlotId);
  if (!source || !destination || !sourceSequence || !destinationSequence || !sourceSlot) {
    return refused("MOVE_SOURCE_OR_DESTINATION_MISSING", "The source and destination rows, sequence, and source slot must exist.", command.sourceBlockId, command.sourceSlotId);
  }
  if (sourceSequence.version !== expectedVersion || destinationSequence.version !== command.expectedDestinationSequenceVersion) {
    return refused("SEQUENCE_VERSION_STALE", "The source or destination sequence changed before this move.", command.destinationBlockId);
  }
  if (sourceSlot.playoutPolicy === "complete_logged_clip" && command.destination.kind === "cutaway") {
    return refused("COMPLETE_CLIP_CUTAWAY_FORBIDDEN", "A complete-clip root cannot move into a cutaway.", command.sourceBlockId, sourceSlot.id);
  }

  const sourceVersionBefore = sourceSequence.version;
  const destinationResult = insertMovedPayload(destination, command.destination, sourceSlot.payload);
  if (destinationResult.diagnostics.length > 0) return destinationResult;
  const sourceRepair = removeSlotForMove(source, sourceSlot, command.sourceRepair, command.replacementSlotId, command.replacementPayloadId);
  if (sourceRepair.diagnostics.length > 0) return sourceRepair;
  if (sourceSequence.version === sourceVersionBefore) sourceSequence.version += 1;
  return {
    diagnostics: [],
    blockIds: [command.sourceBlockId, command.destinationBlockId],
    slotIds: [...new Set([...sourceRepair.slotIds, ...destinationResult.slotIds])],
    payloadIds: [...new Set([...sourceRepair.payloadIds, ...destinationResult.payloadIds].filter((id): id is string => id !== null))],
  };
}

function removeSlotForMove(
  row: NarrationBlockV2,
  target: ContentSlot,
  childRepair: "reject" | "delete_children",
  replacementSlotId?: string,
  replacementPayloadId?: string,
): MutationResult {
  const sequence = row.primaryVisualSequence!;
  const group = groupFor(sequence, target.relation.kind === "cutaway" ? target.relation.parentSlotId : target.id);
  if (!group) return refused("SOURCE_REPAIR_UNRESOLVED", "The source cutaway group cannot be resolved.", row.id, target.id);
  if (target.relation.kind === "cutaway") {
    const siblings = group.children;
    const index = sequence.slots.indexOf(target);
    sequence.slots.splice(index, 1);
    if (siblings.length === 1 && group.returnSlot) sequence.slots.splice(sequence.slots.indexOf(group.returnSlot), 1);
    return changed([row.id], [target.id, ...(siblings.length === 1 && group.returnSlot ? [group.returnSlot.id] : [])], [payloadId(target.payload)]);
  }
  if (group.root.id === target.id && group.root.relation.kind === "base") {
    return deleteSlot(documentFromRow(row), row.id, sequence.version, target.id, "reject", replacementSlotId, replacementPayloadId);
  }
  if (group.children.length > 0 && childRepair !== "delete_children") {
    return refused("ROOT_CHILDREN_REPAIR_REQUIRED", "Moving a root with children requires an explicit delete_children repair or a separate child move.", row.id, target.id);
  }
  if (target.playoutPolicy === "complete_logged_clip") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "Switch the complete-clip root back to an exact word boundary before moving it.", row.id, target.id);
  if (target.boundaryBefore.kind === "previous_media_end") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "A root controlled by a media-end boundary must be repaired before moving.", row.id, target.id);
  const removeIds = new Set([target.id, ...group.children.map((child) => child.id), ...(group.returnSlot ? [group.returnSlot.id] : [])]);
  sequence.slots = sequence.slots.filter((slot) => !removeIds.has(slot.id));
  return changed([row.id], [...removeIds], [payloadId(target.payload), ...group.children.map((child) => payloadId(child.payload))]);
}

function deleteSlot(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  slotId: string,
  childRepair: "reject" | "delete_children",
  replacementSlotId?: string,
  replacementPayloadId?: string,
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  const target = sequence?.slots.find((slot) => slot.id === slotId);
  if (!row || !sequence || !target) return refused("DELETE_SLOT_MISSING", "The content or return slot no longer exists.", blockId, slotId);
  if (target.kind === "return") return refused("RETURN_DELETE_FORBIDDEN", "A return is removed by flattening the group or deleting its final child.", blockId, slotId);

  if (target.relation.kind === "cutaway") {
    const group = groupFor(sequence, target.relation.parentSlotId);
    if (!group) return refused("CUTAWAY_GROUP_INVALID", "The child group cannot be resolved.", blockId, slotId);
    const onlyChild = group.children.length === 1;
    sequence.slots.splice(sequence.slots.indexOf(target), 1);
    if (onlyChild && group.returnSlot) sequence.slots.splice(sequence.slots.indexOf(group.returnSlot), 1);
    sequence.version += 1;
    return changed([blockId], [slotId, ...(onlyChild && group.returnSlot ? [group.returnSlot.id] : [])], [payloadId(target.payload)]);
  }

  const group = groupFor(sequence, target.id);
  if (!group) return refused("ROOT_GROUP_INVALID", "The root and its cutaway group cannot be resolved.", blockId, slotId);
  if (target.relation.kind === "base") {
    if (group.children.length > 0) {
      const returned = group.returnSlot?.inpoint;
      if (!group.returnSlot || !returned || wordIndexV2(returned, row) === null) {
        return refused("BASE_DELETE_RETURN_UNRESOLVED", "Base deletion needs the exact former return word to preserve the child group's outpoint.", blockId, slotId);
      }
      const formerReturnIndex = wordIndexV2(returned, row)!;
      const nextRoot = group.nextRootIndex === undefined ? undefined : sequence.slots[group.nextRootIndex] as RootSlot;
      const nextRootIndex = nextRoot?.boundaryBefore.kind === "spoken_word" ? wordIndexV2(nextRoot.boundaryBefore.anchor, row) : null;
      const existingRootAtReturn = nextRootIndex === formerReturnIndex;
      if (!existingRootAtReturn && (!replacementSlotId || !replacementPayloadId)) {
        return refused("BASE_DELETE_REPLACEMENT_IDS_REQUIRED", "Supply stable slot and payload IDs for the new undefined outpoint.", blockId, slotId);
      }
      const removed = new Set([target.id, group.returnSlot.id]);
      sequence.slots = sequence.slots.filter((slot) => !removed.has(slot.id));
      group.children.forEach((child, index) => {
        child.relation = index === 0 ? { kind: "base" } : { kind: "sequential" };
        if (index === 0) child.boundaryBefore = { kind: "row_start" };
        child.version += 1;
      });
      if (!existingRootAtReturn) {
        const undefinedSlot: ContentSlot = {
          id: replacementSlotId!,
          kind: "content",
          relation: { kind: "sequential" },
          boundaryBefore: { kind: "spoken_word", anchor: returned },
          payload: { kind: "undefined", payloadId: replacementPayloadId!, description: "The former cutaway outpoint is preserved without guessing a replacement visual." },
          playoutPolicy: "match_structural_interval",
          version: 1,
        };
        const insertion = nextRoot ? sequence.slots.indexOf(nextRoot) : sequence.slots.length;
        sequence.slots.splice(insertion, 0, undefinedSlot);
      }
      sequence.version += 1;
      return changed([blockId], [slotId, group.returnSlot.id, ...group.children.map((child) => child.id), ...(existingRootAtReturn ? [] : [replacementSlotId!])], [payloadId(target.payload), ...group.children.map((child) => payloadId(child.payload)), ...(existingRootAtReturn ? [] : [replacementPayloadId!])]);
    }
    if (target.playoutPolicy === "complete_logged_clip") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "Switch the complete-clip root back to an exact word boundary before deleting it.", blockId, slotId);
    const nextRoot = group.nextRootIndex === undefined ? undefined : sequence.slots[group.nextRootIndex] as RootSlot;
    if (nextRoot?.boundaryBefore.kind === "previous_media_end") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "The following root depends on this media end; choose its exact word boundary first.", blockId, slotId);
    sequence.slots.splice(sequence.slots.indexOf(target), 1);
    if (nextRoot) {
      nextRoot.relation = { kind: "base" };
      nextRoot.boundaryBefore = { kind: "row_start" };
      nextRoot.version += 1;
    } else {
      if (!replacementSlotId || !replacementPayloadId) return refused("BASE_DELETE_REPLACEMENT_IDS_REQUIRED", "Supply stable slot and payload IDs for the new undefined base.", blockId, slotId);
      sequence.slots.push({
        id: replacementSlotId,
        kind: "content",
        relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: { kind: "undefined", payloadId: replacementPayloadId, description: "The row has no remaining primary visual." },
        playoutPolicy: "match_structural_interval",
        version: 1,
      });
    }
    sequence.version += 1;
    return changed([blockId], [slotId, ...(nextRoot ? [nextRoot.id] : [replacementSlotId!])], [payloadId(target.payload), ...(nextRoot ? [payloadId(nextRoot.payload)] : [replacementPayloadId!])]);
  }

  if (group.children.length > 0 && childRepair !== "delete_children") {
    return refused("ROOT_CHILDREN_REPAIR_REQUIRED", "Choose delete_children or keep the root with its children.", blockId, slotId);
  }
  if (target.playoutPolicy === "complete_logged_clip") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "Switch the complete-clip root back to an exact word boundary before deleting it.", blockId, slotId);
  const nextRoot = group.nextRootIndex === undefined ? undefined : sequence.slots[group.nextRootIndex] as RootSlot;
  if (nextRoot?.boundaryBefore.kind === "previous_media_end") return refused("COMPLETE_CLIP_REPAIR_REQUIRED", "The next root depends on this media end; choose its exact word boundary first.", blockId, slotId);
  const removeIds = new Set([target.id, ...group.children.map((child) => child.id), ...(group.returnSlot ? [group.returnSlot.id] : [])]);
  sequence.slots = sequence.slots.filter((slot) => !removeIds.has(slot.id));
  sequence.version += 1;
  return changed([blockId], [...removeIds], [payloadId(target.payload), ...group.children.map((child) => payloadId(child.payload))]);
}

function setPlayoutPolicy(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  slotId: string,
  policy: ContentSlot["playoutPolicy"],
  nextBoundary?: WordInpointAnchor,
): MutationResult {
  const row = findRow(document, blockId);
  const sequence = row?.primaryVisualSequence;
  const slot = sequence?.slots.find((candidate): candidate is RootSlot => candidate.kind === "content" && candidate.id === slotId && candidate.relation.kind !== "cutaway");
  if (!row || !sequence || !slot) return refused("PLAYOUT_ROOT_MISSING", "Playout mode applies to an existing root slot.", blockId, slotId);
  if (slot.playoutPolicy === policy) return refused("PLAYOUT_MODE_UNCHANGED", "The root already uses this playout mode.", blockId, slotId);
  const roots = groups(sequence);
  const position = roots.findIndex((group) => group.root.id === slot.id);
  const group = roots[position];
  const next = roots[position + 1];
  const prior = roots[position - 1];
  if (!group || !next) return refused("COMPLETE_CLIP_FINAL_FORBIDDEN", "Complete-clip mode needs an immediate following root.", blockId, slotId);
  if (group.children.length > 0) return refused("COMPLETE_CLIP_CHILDREN_FORBIDDEN", "A complete-clip root cannot own cutaways.", blockId, slotId);

  if (policy === "complete_logged_clip") {
    if (!isClip(slot) || slot.payload.kind !== "visual" || slot.payload.sourceUsage === null) return refused("COMPLETE_CLIP_SOURCE_REQUIRED", "Complete-clip mode needs a clip with an occurrence source inpoint.", blockId, slotId);
    if (!isClip(next.root)) return refused("COMPLETE_CLIP_NEXT_CLIP_REQUIRED", "The immediate following root must also be B-roll footage.", blockId, next.root.id);
    if (prior?.root.payload.kind === "on_camera") return refused("COMPLETE_CLIP_ON_CAMERA_ADJACENT", "Complete-clip mode cannot border an On Camera root.", blockId, slotId);
    slot.playoutPolicy = "complete_logged_clip";
    slot.version += 1;
    next.root.boundaryBefore = { kind: "previous_media_end", controllingSlotId: slot.id };
    next.root.version += 1;
  } else {
    if (!nextBoundary) return refused("PLAYOUT_WORD_BOUNDARY_REQUIRED", "Switching back requires a newly chosen exact word boundary.", blockId, next.root.id);
    if (!isWordAnchorCurrentV2(nextBoundary, row)) return refused("STALE_WORD_ANCHOR", "The replacement boundary must name a current token and exact spoken text in this row.", blockId, next.root.id);
    const startIndex = boundaryIndex(slot, row);
    const selectedIndex = wordIndexV2(nextBoundary, row);
    const followingRoot = roots[position + 2]?.root;
    let followingIndex: number | null = row.tokens.length;
    if (followingRoot?.boundaryBefore.kind === "previous_media_end") {
      const remainsControlledByCompleteClip =
        next.root.playoutPolicy === "complete_logged_clip" &&
        followingRoot.boundaryBefore.controllingSlotId === next.root.id;
      if (!remainsControlledByCompleteClip) {
        return refused("BOUNDARY_NEIGHBOR_UNRESOLVED", "The following media-end boundary has no exact word position after this mode switch.", blockId, followingRoot.id);
      }
      // The next root remains complete and still owns this media-end link. Its
      // exact timing is resolved by the compiler; the edit only places the
      // next root at the caller's exact word anchor.
    } else if (followingRoot) {
      followingIndex = boundaryIndex(followingRoot, row);
    }
    if (startIndex === null || selectedIndex === null || followingIndex === null || selectedIndex <= startIndex || selectedIndex >= followingIndex) {
      return refused("BOUNDARY_CROSSED_OR_COLLAPSED", "The replacement word must follow the controller start and precede the next exact word boundary when one is available.", blockId, next.root.id);
    }
    slot.playoutPolicy = "match_structural_interval";
    slot.version += 1;
    next.root.boundaryBefore = { kind: "spoken_word", anchor: nextBoundary };
    next.root.version += 1;
  }
  sequence.version += 1;
  return changed([blockId], [slot.id, next.root.id], [payloadId(slot.payload), payloadId(next.root.payload)]);
}

function promoteSupportingPicture(
  document: ScriptDocumentV2,
  blockId: string,
  expectedVersion: number,
  supportingItemId: string,
  destination: VisualDestinationV2,
  audioPolicy: "mute" | "quiet",
  framingPolicy: "contain" | "cover" | "native",
  sourceUsage: { sourceInFrame: number } | null,
): MutationResult {
  const itemIndex = document.activeDraft.supportingItems.findIndex((item) => item.id === supportingItemId);
  const item = document.activeDraft.supportingItems[itemIndex];
  const row = findRow(document, blockId);
  if (!item || !row || !row.primaryVisualSequence) return refused("SUPPORTING_ITEM_MISSING", "The supporting picture and destination row must exist.", blockId, supportingItemId);
  if (item.role !== "picture" || item.placement.kind !== "unplaced" || !item.pictureKind || !item.source) {
    return refused("SUPPORTING_PICTURE_NOT_PROMOTABLE", "Only an Unplaced picture with an explicit subtype and source can move into the primary sequence.", blockId, supportingItemId);
  }
  if (item.pictureKind === "clip" ? sourceUsage === null : sourceUsage !== null) {
    return refused("SUPPORTING_SOURCE_USAGE_REQUIRED", "A clip promotion needs an explicit source inpoint; still-like pictures must not acquire one.", blockId, supportingItemId);
  }
  const payload: ContentSlot["payload"] = {
    kind: "visual",
    payloadId: item.id,
    pictureKind: item.pictureKind,
    source: item.source,
    sourceUsage,
    audioPolicy,
    framingPolicy,
  };
  const inserted = insertMovedPayload(row, destination, payload);
  if (inserted.diagnostics.length > 0) return inserted;
  document.activeDraft.supportingItems.splice(itemIndex, 1);
  return {
    diagnostics: [],
    blockIds: [blockId],
    slotIds: inserted.slotIds,
    payloadIds: [item.id],
    supportingItemId: item.id,
    lineage: { fromSupportingItemId: item.id, toPayloadId: item.id },
  };
}

function insertionLocation(
  sequence: Sequence,
  row: NarrationBlockV2,
  index: number,
): { ok: true; index: number } | { ok: false; code: string; message: string } {
  const rootGroups = groups(sequence);
  const previous = [...rootGroups].reverse().find((group) => (boundaryIndex(group.root, row) ?? -1) < index);
  const next = rootGroups.find((group) => {
    const boundary = group.root.boundaryBefore;
    return boundary.kind === "previous_media_end" || (boundaryIndex(group.root, row) ?? Infinity) > index;
  });
  if (!previous) return { ok: false, code: "BASE_START_FIXED", message: "A root insert cannot replace or precede the base slot." };
  if (previous.root.playoutPolicy === "complete_logged_clip") return { ok: false, code: "COMPLETE_CLIP_REPAIR_REQUIRED", message: "Choose an exact word boundary for the media-led cut before inserting a root." };
  if (previous.children.length > 0) {
    const returnIndex = previous.returnSlot?.inpoint ? wordIndexV2(previous.returnSlot.inpoint, row) : null;
    if (returnIndex === null) return { ok: false, code: "RETURN_INPOINT_MISSING", message: "Repair the cutaway return before inserting a later root." };
    if (index <= returnIndex) return { ok: false, code: "INSERT_INSIDE_CUTAWAY_GROUP", message: "A new root must follow the complete cutaway group." };
  }
  if (next?.root.boundaryBefore.kind === "previous_media_end") return { ok: false, code: "MEDIA_BOUNDARY_UNRESOLVED", message: "The next root's media-end boundary has no exact word position." };
  return { ok: true, index: next ? sequence.slots.indexOf(next.root) : previous.endIndex + 1 };
}

function insertMovedPayload(
  row: NarrationBlockV2,
  destination: VisualDestinationV2,
  payload: ContentSlot["payload"],
): MutationResult {
  const document = documentFromRow(row);
  if (destination.kind === "sequential") {
    return insertSequential(document, row.id, row.primaryVisualSequence!.version, destination.boundary, destination.slotId, payload);
  }
  if (!destination.returnSlotId) {
    const sequence = row.primaryVisualSequence!;
    const group = groupFor(sequence, destination.parentSlotId);
    if (!group?.returnSlot) return refused("CUTAWAY_RETURN_ID_REQUIRED", "A new cutaway group needs a stable return ID.", row.id, destination.slotId);
  }
  return insertCutaway(document, row.id, row.primaryVisualSequence!.version, destination.boundary, destination.parentSlotId, destination.slotId, destination.returnSlotId ?? "", payload);
}

function groupFor(sequence: Sequence, rootId: string): RootGroup | null {
  const rootIndex = sequence.slots.findIndex((slot) => isRootSlot(slot) && slot.id === rootId);
  if (rootIndex < 0) return null;
  const rootValue = sequence.slots[rootIndex];
  if (!rootValue || !isRootSlot(rootValue)) return null;
  const root = rootValue;
  const children: ContentSlot[] = [];
  let cursor = rootIndex + 1;
  while (cursor < sequence.slots.length) {
    const candidate = sequence.slots[cursor]!;
    if (candidate.kind !== "content" || candidate.relation.kind !== "cutaway") break;
    if (candidate.relation.parentSlotId !== rootId) break;
    children.push(candidate);
    cursor += 1;
  }
  const possibleReturn = children.length > 0 ? sequence.slots[cursor] : undefined;
  const returnSlot = possibleReturn?.kind === "return" && possibleReturn.parentSlotId === rootId ? possibleReturn : undefined;
  const endIndex = returnSlot ? cursor : cursor - 1;
  const nextIndex = returnSlot ? cursor + 1 : cursor;
  const nextRootIndex = nextIndex < sequence.slots.length && isRootSlot(sequence.slots[nextIndex]!)
    ? nextIndex
    : undefined;
  return { root, rootIndex, children, ...(returnSlot ? { returnSlot } : {}), endIndex, ...(nextRootIndex !== undefined ? { nextRootIndex } : {}) };
}

function groups(sequence: Sequence): RootGroup[] {
  return sequence.slots.flatMap((slot) => {
    if (slot.kind !== "content" || slot.relation.kind === "cutaway") return [];
    const group = groupFor(sequence, slot.id);
    return group ? [group] : [];
  });
}

function previousBoundary(
  sequence: Sequence,
  row: NarrationBlockV2,
  targetIndex: number,
): { index: number } | null {
  for (let index = targetIndex - 1; index >= 0; index -= 1) {
    const slot = sequence.slots[index]!;
    if (slot.kind === "return") {
      if (!slot.inpoint) return null;
      const word = wordIndexV2(slot.inpoint, row);
      return word === null ? null : { index: word };
    }
    if (slot.boundaryBefore.kind === "previous_media_end") return null;
    const word = boundaryIndex(slot, row);
    if (word !== null) return { index: word };
  }
  return { index: 0 };
}

function nextBoundaryAfter(
  sequence: Sequence,
  row: NarrationBlockV2,
  targetIndex: number,
): { index: number } | null {
  for (let index = targetIndex + 1; index < sequence.slots.length; index += 1) {
    const slot = sequence.slots[index]!;
    if (slot.kind === "return") {
      if (!slot.inpoint) return null;
      const word = wordIndexV2(slot.inpoint, row);
      return word === null ? null : { index: word };
    }
    if (slot.boundaryBefore.kind === "previous_media_end") return null;
    const word = boundaryIndex(slot, row);
    if (word !== null) return { index: word };
  }
  return { index: row.tokens.length };
}

function boundaryIndex(slot: ContentSlot | ReturnSlot, row: NarrationBlockV2): number | null {
  if (slot.kind === "return") return slot.inpoint ? wordIndexV2(slot.inpoint, row) : null;
  if (slot.boundaryBefore.kind === "row_start") return 0;
  return slot.boundaryBefore.kind === "spoken_word"
    ? wordIndexV2(slot.boundaryBefore.anchor, row)
    : null;
}

function isRootSlot(slot: ContentSlot | ReturnSlot): slot is RootSlot {
  return slot.kind === "content" && slot.relation.kind !== "cutaway";
}

function currentAnchorVersion(slot: ContentSlot | ReturnSlot): number {
  return slot.kind === "return"
    ? slot.inpoint?.anchorVersion ?? slot.version
    : slot.boundaryBefore.kind === "spoken_word"
      ? slot.boundaryBefore.anchor.anchorVersion
      : slot.version;
}

function acceptsPolicy(slot: ContentSlot, payload: ContentSlot["payload"]): boolean {
  return slot.playoutPolicy !== "complete_logged_clip" ||
    (payload.kind === "visual" && payload.pictureKind === "clip" && payload.sourceUsage !== null);
}

function isClip(slot: ContentSlot): boolean {
  return slot.payload.kind === "visual" && slot.payload.pictureKind === "clip";
}

function findRow(document: ScriptDocumentV2, blockId: string): NarrationBlockV2 | undefined {
  return document.activeDraft.blocks.find(
    (block): block is NarrationBlockV2 => block.type === "narration" && block.id === blockId,
  );
}

function sequenceBlockId(command: VisualSequenceEditCommandV2): string {
  return command.kind === "move_payload" ? command.sourceBlockId : command.blockId;
}

function documentFromRow(row: NarrationBlockV2): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: "00000000-0000-4000-8000-000000000001",
    projectId: "00000000-0000-4000-8000-000000000002",
    title: "temporary",
    activeDraft: { blocks: [row], supportingItems: [] },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 1,
    liveStateVector: "",
    liveContentHash: `sha256:${"0".repeat(64)}`,
  };
}

function newlyIntroducedErrors(
  before: AuthoringDiagnosticV2[],
  after: AuthoringDiagnosticV2[],
  allowedNewCodes: ReadonlySet<string>,
): AuthoringDiagnosticV2[] {
  const priorCounts = new Map<string, number>();
  for (const diagnostic of before) {
    if (diagnostic.severity === "warning") continue;
    const key = `${diagnostic.code}\0${diagnostic.entityId ?? ""}`;
    priorCounts.set(key, (priorCounts.get(key) ?? 0) + 1);
  }
  const seenCounts = new Map<string, number>();
  return after.filter((diagnostic) => {
    if (diagnostic.severity === "warning" || allowedNewCodes.has(diagnostic.code)) return false;
    const key = `${diagnostic.code}\0${diagnostic.entityId ?? ""}`;
    const seen = (seenCounts.get(key) ?? 0) + 1;
    seenCounts.set(key, seen);
    return seen > (priorCounts.get(key) ?? 0);
  });
}

function payloadId(payload: ContentSlot["payload"]): string | null {
  return payload.kind === "on_camera" ? null : payload.payloadId;
}

function changed(blockIds: string[], slotIds: string[], payloadIds: (string | null)[]): MutationResult {
  return { diagnostics: [], blockIds, slotIds, payloadIds: payloadIds.filter((id): id is string => id !== null) };
}

function refused(
  code: string,
  message: string,
  blockId: string,
  entityId?: string,
): MutationResult {
  return {
    diagnostics: [diag(code, message, blockId, entityId)],
    blockIds: [blockId],
    slotIds: entityId ? [entityId] : [],
    payloadIds: [],
  };
}

function diag(
  code: string,
  message: string,
  blockId: string,
  entityId?: string,
): AuthoringDiagnosticV2 {
  return {
    code,
    message,
    jsonPath: blockId ? `/activeDraft/blocks/${blockId}` : "/activeDraft",
    ...(blockId ? { blockId } : {}),
    ...(entityId ? { entityId } : {}),
  };
}

function failure(
  document: ScriptDocumentV2,
  diagnostics: AuthoringDiagnosticV2[],
): VisualSequenceEditResultV2 {
  return { ok: false, document, diagnostics };
}
