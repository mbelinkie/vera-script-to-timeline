import { createHash } from "node:crypto";
import type {
  ContentSlot,
  NarrationBlockV2,
  NarrationTokenTimingMapV2,
  OverlayEventV2,
  RationalTime,
  ReturnSlot,
  ScriptDocumentV2,
  TimedPlacement,
} from "./generated/contracts-v2.js";
import type {
  AuthoringDiagnosticV2,
  LoggedMediaBoundsV2,
  MediaCutEstimateV2,
  PrimarySequenceProjectionOptionsV2,
  PrimarySequenceProjectionV2,
  PrimarySequenceRowProjectionV2,
  ProjectedAppearanceV2,
  ProjectedHostStateV2,
  ProjectedOverlayV2,
  ProjectedPrimarySlotV2,
  ProjectedReturnV2,
  ProjectedTokenV2,
} from "./authoring-v2.js";
import {
  pointWordIndexV2,
  validateScriptDocumentV2,
  wordIndexV2,
} from "./authoring-v2-validation.js";

type PointAnchor = NonNullable<TimedPlacement["start"]>;
type RootSlot = ContentSlot & {
  relation: Extract<ContentSlot["relation"], { kind: "base" | "sequential" }>;
};

interface RootGroup {
  root: RootSlot;
  rootIndex: number;
  children: ContentSlot[];
  returnIndex?: number;
  returnSlot?: ReturnSlot;
  endIndex: number;
  nextRootIndex?: number;
}

interface OccurrenceOrder {
  id: string;
  kind: "primary" | "overlay";
  start: number | null;
  time: BigFraction | null;
  ordinal: number | null;
}

interface BigFraction {
  n: bigint;
  d: bigint;
}

/** Pure view shared by pointer and keyboard consumers; no ranges or ordinals are serialized. */
export function projectPrimarySequenceV2(
  input: unknown,
  options: PrimarySequenceProjectionOptionsV2 = {},
): PrimarySequenceProjectionV2 {
  const validation = validateScriptDocumentV2(input);
  if (!isDocument(input)) {
    return { rows: [], diagnostics: validation.diagnostics };
  }
  const document = input;
  const rows = document.activeDraft.blocks.flatMap((block) => {
    if (block.type !== "narration" || block.state !== "active") return [];
    return [projectRow(document, block, validation.diagnostics, options)];
  });
  return { rows, diagnostics: validation.diagnostics };
}

function projectRow(
  document: ScriptDocumentV2,
  row: NarrationBlockV2,
  allDiagnostics: AuthoringDiagnosticV2[],
  options: PrimarySequenceProjectionOptionsV2,
): PrimarySequenceRowProjectionV2 {
  const path = `/activeDraft/blocks/${document.activeDraft.blocks.indexOf(row)}`;
  const diagnostics = allDiagnostics.filter(
    (diagnostic) => diagnostic.blockId === row.id || diagnostic.jsonPath.startsWith(path),
  );
  const sequence = row.primaryVisualSequence;
  if (!sequence) {
    diagnostics.push({
      code: "PRIMARY_SEQUENCE_MISSING",
      message: "The active narration row has no primary visual sequence.",
      jsonPath: `${path}/primaryVisualSequence`,
      blockId: row.id,
    });
    return emptyRow(row.id, diagnostics);
  }

  const occurrenceOrders = buildOccurrenceOrders(document, row, options, diagnostics);
  const orderById = new Map(occurrenceOrders.map((item) => [item.id, item]));
  const groups = rootGroups(sequence.slots);
  const slotViews: ProjectedPrimarySlotV2[] = [];
  const returnViews: ProjectedReturnV2[] = [];
  const rootIntervals = new Map<string, { start: number | null; end: number | null }>();
  const childIntervals = new Map<string, { start: number | null; end: number | null }>();
  const returnTokenIndices = new Map<string, number | null>();

  for (const group of groups) {
    const start = slotStart(group.root, row);
    const nextRoot = group.nextRootIndex === undefined ? undefined : sequence.slots[group.nextRootIndex];
    const end = nextRoot?.kind === "content"
      ? slotStart(nextRoot, row)
      : row.tokens.length;
    rootIntervals.set(group.root.id, { start, end });
    for (let index = 0; index < group.children.length; index += 1) {
      const child = group.children[index]!;
      const childStart = slotStart(child, row);
      const nextChild = group.children[index + 1];
      const childEnd = nextChild
        ? slotStart(nextChild, row)
        : group.returnSlot?.inpoint
          ? wordIndexV2(group.returnSlot.inpoint, row)
          : null;
      childIntervals.set(child.id, { start: childStart, end: childEnd });
    }
    if (group.returnSlot) {
      const returnIndex = group.returnSlot.inpoint
        ? wordIndexV2(group.returnSlot.inpoint, row)
        : null;
      returnTokenIndices.set(group.returnSlot.id, returnIndex);
    }
  }

  const ordinalOrder = orderById;
  sequence.slots.forEach((slot, structuralIndex) => {
    if (slot.kind === "return") {
      const parent = sequence.slots.find(
        (candidate): candidate is RootSlot => candidate.kind === "content" && candidate.id === slot.parentSlotId && candidate.relation.kind !== "cutaway",
      );
      returnViews.push({
        returnSlotId: slot.id,
        parentSlotId: slot.parentSlotId,
        structuralIndex,
        parentOrdinal: parent ? ordinalOrder.get(parent.id)?.ordinal ?? null : null,
        startTokenIndex: returnTokenIndices.get(slot.id) ?? null,
      });
      return;
    }
    slotViews.push({
      slotId: slot.id,
      payloadId: payloadId(slot.payload),
      structuralIndex,
      humanOrdinal: ordinalOrder.get(slot.id)?.ordinal ?? null,
      relation: slot.relation.kind,
      parentSlotId: slot.relation.kind === "cutaway" ? slot.relation.parentSlotId : null,
      startTokenIndex: slotStart(slot, row),
      payloadKind: slot.payload.kind,
    });
  });

  const tokens: ProjectedTokenV2[] = row.tokens.map((token, tokenIndex) => {
    const rootGroup = activeRootAt(groups, row, tokenIndex);
    const rootInterval = rootGroup ? rootIntervals.get(rootGroup.root.id) : undefined;
    if (!rootGroup || !rootInterval || rootInterval.start === null || rootInterval.end === null) {
      return {
        tokenId: token.id,
        text: token.value,
        primarySlotId: null,
        payloadId: null,
        humanOrdinal: null,
        hostState: "unresolved",
        onCameraResumes: false,
      };
    }
    if (tokenIndex < rootInterval.start || tokenIndex >= rootInterval.end) {
      return {
        tokenId: token.id,
        text: token.value,
        primarySlotId: null,
        payloadId: null,
        humanOrdinal: null,
        hostState: "unresolved",
        onCameraResumes: false,
      };
    }
    let visible: ContentSlot = rootGroup.root;
    if (rootGroup.children.length > 0) {
      const child = rootGroup.children.find((candidate) => {
        const interval = childIntervals.get(candidate.id);
        return interval?.start !== null && interval?.start !== undefined &&
          tokenIndex >= interval.start &&
          (interval.end === null || tokenIndex < interval.end);
      });
      if (child) {
        const interval = childIntervals.get(child.id);
        if (interval?.end === null && tokenIndex >= interval.start!) {
          return {
            tokenId: token.id,
            text: token.value,
            primarySlotId: null,
            payloadId: null,
            humanOrdinal: null,
            hostState: "unresolved",
            onCameraResumes: false,
          };
        }
        visible = child;
      } else if (rootGroup.returnSlot?.inpoint === null) {
        const lastChild = rootGroup.children.at(-1);
        const lastStart = lastChild ? childIntervals.get(lastChild.id)?.start : null;
        if (lastStart !== null && lastStart !== undefined && tokenIndex >= lastStart) {
          return {
            tokenId: token.id,
            text: token.value,
            primarySlotId: null,
            payloadId: null,
            humanOrdinal: null,
            hostState: "unresolved",
            onCameraResumes: false,
          };
        }
      }
    }
    return {
      tokenId: token.id,
      text: token.value,
      primarySlotId: visible.id,
      payloadId: payloadId(visible.payload),
      humanOrdinal: ordinalOrder.get(visible.id)?.ordinal ?? null,
      hostState: hostState(visible),
      onCameraResumes: false,
    };
  });

  const slotById = new Map(slotViews.map((slot) => [slot.slotId, slot]));
  for (const group of groups) {
    if (group.root.payload.kind !== "on_camera" || !group.returnSlot) continue;
    const returnIndex = returnTokenIndices.get(group.returnSlot.id);
    const rootStart = rootIntervals.get(group.root.id)?.start;
    const firstChildStart = group.children[0]
      ? childIntervals.get(group.children[0].id)?.start
      : null;
    if (
      returnIndex === null || returnIndex === undefined || returnIndex < 1 ||
      rootStart === null || rootStart === undefined ||
      firstChildStart === null || firstChildStart === undefined ||
      rootStart >= firstChildStart
    ) continue;
    const previous = tokens[returnIndex - 1];
    const previousSlot = previous?.primarySlotId ? slotById.get(previous.primarySlotId) : undefined;
    if (previous?.hostState === "voiceover" && previousSlot?.payloadKind === "visual") {
      const returned = tokens[returnIndex];
      if (returned?.primarySlotId === group.root.id && returned.hostState === "on_camera") {
        tokens[returnIndex] = { ...returned, onCameraResumes: true };
      }
    }
  }

  const appearances = coalesceAppearances(tokens, slotViews);
  const overlays = row.overlayEvents.map((event) => projectOverlay(event, row, orderById));
  const supportingItems = document.activeDraft.supportingItems.map((item) => ({
    itemId: item.id,
    role: item.role,
    placementKind: item.placement.kind,
    placement: item.placement,
    interval: null,
  }));
  const mediaCutEstimates = estimateMediaCuts(row, groups, options, diagnostics);
  const hasErrors = diagnostics.some((diagnostic) => diagnostic.severity !== "warning");
  return {
    blockId: row.id,
    sequenceId: sequence.id,
    renderable: !hasErrors && tokens.every((token) => token.hostState !== "unresolved"),
    tokens,
    appearances,
    slots: slotViews,
    returns: returnViews,
    overlays,
    supportingItems,
    mediaCutEstimates,
    diagnostics,
  };
}

function buildOccurrenceOrders(
  document: ScriptDocumentV2,
  row: NarrationBlockV2,
  options: PrimarySequenceProjectionOptionsV2,
  diagnostics: AuthoringDiagnosticV2[],
): OccurrenceOrder[] {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return [];
  const timingMap = options.narrationTimingMaps?.find(
    (item) => item.blockId === row.id && validPreviewTiming(row, item),
  );
  const candidates: Omit<OccurrenceOrder, "ordinal">[] = [];
  for (const slot of sequence.slots) {
    if (slot.kind === "return" || slot.payload.kind === "on_camera") continue;
    candidates.push({
      id: slot.id,
      kind: "primary",
      start: slotStart(slot, row),
      time: timingMap ? slotTime(slot, row, timingMap, options, new Set()) : null,
    });
  }
  for (const event of row.overlayEvents) {
    const time = timingMap
      ? overlayStartTime(event, row, document, timingMap, new Set())
      : null;
    if (!event.timing.start && event.timing.end && event.timing.durationMs !== undefined && time === null) {
      diagnostics.push({
        code: "OVERLAY_START_UNRESOLVED",
        message: "The overlay has no exact start word; its timed start needs verified narration timing.",
        jsonPath: `/activeDraft/blocks/${row.id}/overlayEvents/${event.id}/timing/start`,
        severity: "warning",
        blockId: row.id,
        entityId: event.id,
      });
    }
    candidates.push({
      id: event.id,
      kind: "overlay",
      start: pointIndex(event.timing.start, event, row, document, new Set()),
      time,
    });
  }
  const timeSortable = timingMap !== undefined && candidates.every((item) => item.time !== null);
  const ordered = candidates.filter((item) => timeSortable ? item.time !== null : item.start !== null).sort((left, right) =>
    (timeSortable ? compare(left.time!, right.time!) : left.start! - right.start!) ||
    (left.kind === right.kind ? 0 : left.kind === "primary" ? -1 : 1) ||
    left.id.localeCompare(right.id),
  );
  const ordinalById = new Map(ordered.map((item, index) => [item.id, index + 1]));
  return candidates.map((item) => ({
    ...item,
    ordinal: item.start === null && !(timeSortable && item.kind === "overlay" && item.time !== null)
      ? null
      : ordinalById.get(item.id) ?? null,
  }));
}

function slotTime(
  slot: ContentSlot,
  row: NarrationBlockV2,
  timing: NarrationTokenTimingMapV2,
  options: PrimarySequenceProjectionOptionsV2,
  visiting: Set<string>,
): BigFraction | null {
  if (visiting.has(slot.id)) return null;
  const boundary = slot.boundaryBefore;
  if (boundary.kind === "row_start") return fraction(0n, 1n);
  if (boundary.kind === "spoken_word") {
    const index = wordIndexV2(boundary.anchor, row);
    return index === null ? null : wireFraction(timing.tokens[index]?.startTime);
  }
  const controllerId = boundary.controllingSlotId;
  visiting.add(slot.id);
  const controller = row.primaryVisualSequence?.slots.find(
    (candidate): candidate is ContentSlot => candidate.kind === "content" && candidate.id === controllerId,
  );
  const payload = controller?.payload;
  if (!controller || payload?.kind !== "visual" || payload.pictureKind !== "clip" || payload.sourceUsage === null || payload.source.kind !== "media_reference") return null;
  const controllerStart = slotTime(controller, row, timing, options, visiting);
  const mediaReferenceId = payload.source.mediaReferenceId;
  const sourceInFrame = payload.sourceUsage.sourceInFrame;
  const bounds = options.mediaBounds?.find((item) => item.mediaReferenceId === mediaReferenceId);
  if (!controllerStart || !bounds || !validBounds(bounds, sourceInFrame)) return null;
  return add(controllerStart, fraction(
    BigInt(bounds.loggedEndExclusiveFrame - sourceInFrame) * BigInt(bounds.frameRate.denominator),
    BigInt(bounds.frameRate.numerator),
  ));
}

function overlayStartTime(
  event: OverlayEventV2,
  row: NarrationBlockV2,
  document: ScriptDocumentV2,
  timing: NarrationTokenTimingMapV2,
  visiting: Set<string>,
): BigFraction | null {
  if (event.timing.start) return pointTime(event.timing.start, row, document, timing, visiting);
  if (!event.timing.end || event.timing.durationMs === undefined || event.timing.durationMs <= 0) return null;
  const end = pointTime(event.timing.end, row, document, timing, visiting);
  if (!end) return null;
  const start = subtract(end, fraction(BigInt(event.timing.durationMs), 1000n));
  return start.n < 0n ? null : start;
}

function pointTime(
  point: PointAnchor,
  row: NarrationBlockV2,
  document: ScriptDocumentV2,
  timing: NarrationTokenTimingMapV2,
  visiting: Set<string>,
): BigFraction | null {
  if (point.kind === "word") {
    const index = wordIndexV2(point.anchor, row);
    return index === null ? null : wireFraction(timing.tokens[index]?.startTime);
  }
  if (point.kind === "between_blocks") {
    const before = document.activeDraft.blocks.findIndex((block) => block.id === point.beforeBlockId);
    const after = document.activeDraft.blocks.findIndex((block) => block.id === point.afterBlockId);
    const rowIndex = document.activeDraft.blocks.findIndex((block) => block.id === row.id);
    if (before === rowIndex - 1 && after === rowIndex) return fraction(0n, 1n);
    if (before === rowIndex && after === rowIndex + 1) {
      const lastIndex = timing.tokens.length - 1;
      const last = timing.tokens[lastIndex];
      return last ? wireFraction(timingEnd(timing, lastIndex)) : null;
    }
    return null;
  }
  if (visiting.has(point.eventId)) return null;
  visiting.add(point.eventId);
  const target = row.overlayEvents.find((candidate) => candidate.id === point.eventId);
  if (!target) return null;
  if (point.edge === "start") return overlayStartTime(target, row, document, timing, visiting);
  return target.timing.end
    ? pointTime(target.timing.end, row, document, timing, visiting)
    : null;
}

function wireFraction(value: RationalTime | undefined): BigFraction | null {
  return value && validTime(value)
    ? fraction(BigInt(value.numerator), BigInt(value.denominator))
    : null;
}

function projectOverlay(
  event: OverlayEventV2,
  row: NarrationBlockV2,
  orders: ReadonlyMap<string, OccurrenceOrder>,
): ProjectedOverlayV2 {
  return {
    overlayEventId: event.id,
    payloadId: event.payload.payloadId,
    humanOrdinal: orders.get(event.id)?.ordinal ?? null,
    startTokenIndex: event.timing.start ? pointWordIndexV2(event.timing.start, row) : null,
    endTokenIndex: event.timing.end ? pointWordIndexV2(event.timing.end, row) : null,
    timing: event.timing,
    parentSlotId: null,
  };
}

function pointIndex(
  point: PointAnchor | undefined,
  event: OverlayEventV2,
  row: NarrationBlockV2,
  document: ScriptDocumentV2,
  visiting: Set<string>,
): number | null {
  if (!point) return null;
  if (point.kind === "word") return wordIndexV2(point.anchor, row);
  if (point.kind === "between_blocks") {
    const before = document.activeDraft.blocks.findIndex((block) => block.id === point.beforeBlockId);
    const after = document.activeDraft.blocks.findIndex((block) => block.id === point.afterBlockId);
    const rowIndex = document.activeDraft.blocks.findIndex((block) => block.id === row.id);
    if (before === rowIndex - 1 && after === rowIndex) return 0;
    if (before === rowIndex && after === rowIndex + 1) return row.tokens.length;
    return null;
  }
  if (visiting.has(point.eventId) || point.eventId === event.id) return null;
  visiting.add(point.eventId);
  const target = row.overlayEvents.find((candidate) => candidate.id === point.eventId);
  if (!target) return null;
  return point.edge === "start"
    ? pointIndex(target.timing.start, target, row, document, visiting)
    : target.timing.end
      ? pointIndex(target.timing.end, target, row, document, visiting)
      : null;
}

function rootGroups(slots: (ContentSlot | ReturnSlot)[]): RootGroup[] {
  return slots.flatMap((slot, rootIndex) => {
    if (slot.kind !== "content" || slot.relation.kind === "cutaway") return [];
    const root = slot as RootSlot;
    const children: ContentSlot[] = [];
    let cursor = rootIndex + 1;
    while (cursor < slots.length) {
      const candidate = slots[cursor]!;
      if (candidate.kind !== "content" || candidate.relation.kind !== "cutaway" || candidate.relation.parentSlotId !== root.id) break;
      children.push(candidate);
      cursor += 1;
    }
    const possibleReturn = children.length > 0 ? slots[cursor] : undefined;
    const returnSlot = possibleReturn?.kind === "return" && possibleReturn.parentSlotId === root.id
      ? possibleReturn
      : undefined;
    const nextIndex = returnSlot ? cursor + 1 : cursor;
    const nextRootIndex = nextIndex < slots.length && slots[nextIndex]!.kind === "content" && slots[nextIndex]!.relation.kind !== "cutaway"
      ? nextIndex
      : undefined;
    return [{
      root,
      rootIndex,
      children,
      ...(returnSlot ? { returnSlot, returnIndex: cursor } : {}),
      endIndex: returnSlot ? cursor : cursor - 1,
      ...(nextRootIndex !== undefined ? { nextRootIndex } : {}),
    }];
  });
}

function activeRootAt(groups: RootGroup[], row: NarrationBlockV2, tokenIndex: number): RootGroup | undefined {
  let active: RootGroup | undefined;
  for (const group of groups) {
    const start = slotStart(group.root, row);
    if (start === null) return undefined;
    if (start > tokenIndex) break;
    active = group;
  }
  if (!active) return undefined;
  return active;
}

function slotStart(slot: ContentSlot, row: NarrationBlockV2): number | null {
  if (slot.boundaryBefore.kind === "row_start") return 0;
  return slot.boundaryBefore.kind === "spoken_word"
    ? wordIndexV2(slot.boundaryBefore.anchor, row)
    : null;
}

function hostState(slot: ContentSlot): Exclude<ProjectedHostStateV2, "unresolved"> {
  if (slot.payload.kind === "on_camera") return "on_camera";
  if (slot.payload.kind === "undefined") return "undefined";
  return "voiceover";
}

function payloadId(payload: ContentSlot["payload"]): string | null {
  return payload.kind === "on_camera" ? null : payload.payloadId;
}

function coalesceAppearances(
  tokens: ProjectedTokenV2[],
  slots: ProjectedPrimarySlotV2[],
): ProjectedAppearanceV2[] {
  const slotById = new Map(slots.map((slot) => [slot.slotId, slot]));
  const appearances: ProjectedAppearanceV2[] = [];
  for (let start = 0; start < tokens.length;) {
    const token = tokens[start]!;
    if (!token.primarySlotId || token.hostState === "unresolved") {
      start += 1;
      continue;
    }
    let end = start + 1;
    while (end < tokens.length && tokens[end]!.primarySlotId === token.primarySlotId) end += 1;
    const slot = slotById.get(token.primarySlotId);
    if (slot) {
      appearances.push({
        slotId: slot.slotId,
        payloadId: slot.payloadId,
        structuralIndex: slot.structuralIndex,
        humanOrdinal: slot.humanOrdinal,
        hostState: token.hostState,
        startTokenIndex: start,
        endTokenIndexExclusive: end,
        startTokenId: tokens[start]?.tokenId ?? null,
        endTokenId: tokens[end]?.tokenId ?? null,
        onCameraResumes: token.onCameraResumes,
      });
    }
    start = end;
  }
  return appearances;
}

function estimateMediaCuts(
  row: NarrationBlockV2,
  groups: RootGroup[],
  options: PrimarySequenceProjectionOptionsV2,
  diagnostics: AuthoringDiagnosticV2[],
): MediaCutEstimateV2[] {
  const estimates: MediaCutEstimateV2[] = [];
  for (const group of groups) {
    const controller = group.root;
    const next = group.nextRootIndex === undefined
      ? undefined
      : row.primaryVisualSequence!.slots[group.nextRootIndex];
    if (controller.playoutPolicy !== "complete_logged_clip" || next?.kind !== "content") continue;
    const payload = controller.payload;
    if (payload.kind !== "visual" || payload.pictureKind !== "clip" || payload.sourceUsage === null || payload.source.kind !== "media_reference") continue;
    const mediaReferenceId = payload.source.mediaReferenceId;
    const bounds = options.mediaBounds?.find((item) => item.mediaReferenceId === mediaReferenceId);
    if (!bounds || !validBounds(bounds, payload.sourceUsage.sourceInFrame)) continue;
    const startIndex = slotStart(controller, row);
    if (startIndex === null) continue;
    const timingMap = options.narrationTimingMaps?.find((item) => item.blockId === row.id);
    const preview = timingMap && validPreviewTiming(row, timingMap) ? timingMap : null;
    const source = preview ? "verified_preview" : "400ms_per_token_fallback";
    const tokenTimes = preview ? previewTokenTimes(row, preview) : fallbackTokenTimes(row);
    const startTime = startIndex === 0
      ? fraction(0n, 1n)
      : tokenTimes[startIndex]?.start ?? null;
    if (!startTime) continue;
    const sourceDuration = fraction(
      BigInt(bounds.loggedEndExclusiveFrame - payload.sourceUsage.sourceInFrame) * BigInt(bounds.frameRate.denominator),
      BigInt(bounds.frameRate.numerator),
    );
    const cutTime = add(startTime, sourceDuration);
    const nextToken = tokenTimes.findIndex((time) => compare(time.end, cutTime) > 0);
    const windowStart = nextToken < 0
      ? row.tokens.length
      : Math.max(0, Math.min(nextToken - 2, row.tokens.length - 5));
    const window = nextToken < 0 ? [] : row.tokens.slice(windowStart, Math.min(windowStart + 5, row.tokens.length)).map((token) => token.id);
    const cutWire = fractionToWire(cutTime);
    if (!cutWire) {
      diagnostics.push({
        code: "MEDIA_CUT_ESTIMATE_OVERFLOW",
        message: "The display estimate exceeds the rational time range.",
        jsonPath: `/activeDraft/blocks/${row.id}/primaryVisualSequence`,
        severity: "warning",
        blockId: row.id,
        entityId: controller.id,
      });
      continue;
    }
    const hashInput = JSON.stringify({
      policy: "media_cut_estimate/v1",
      blockId: row.id,
      blockVersion: row.version,
      text: row.text,
      tokens: row.tokens.map((token) => [token.id, token.value, token.startOffset, token.endOffset]),
      controllerSlotId: controller.id,
      payloadId: payload.payloadId,
      boundaryBefore: controller.boundaryBefore,
      playoutPolicy: controller.playoutPolicy,
      sourceInFrame: payload.sourceUsage.sourceInFrame,
      bounds,
      previewTimingHash: preview?.timingHash ?? null,
      tokenTimes: preview ? preview.tokens.map((token) => [token.tokenId, token.startTime, token.audibleEnd ?? null, token.endBasis]) : null,
    });
    estimates.push({
      policy: "media_cut_estimate/v1",
      label: "Estimated media-timed cut",
      controllerSlotId: controller.id,
      nextSlotId: next.id,
      timingSource: source,
      estimatedCutSeconds: cutWire,
      tokenWindow: window,
      inputHash: sha256(hashInput),
      numberedCapsOmitted: true,
    });
  }
  return estimates;
}

function validPreviewTiming(row: NarrationBlockV2, timing: NarrationTokenTimingMapV2): boolean {
  if (
    timing.blockRevision !== row.version ||
    timing.textHash !== sha256(row.text) ||
    !/^sha256:[a-f0-9]{64}$/u.test(timing.timingHash) ||
    !["audible_word_marks", "next_word_derived"].includes(timing.precision) ||
    timing.tokens.length !== row.tokens.length
  ) return false;
  return row.tokens.every((token, index) => {
    const timed = timing.tokens[index];
    const end = timingEnd(timing, index);
    return timed?.tokenId === token.id &&
      timed.startOffset === token.startOffset &&
      timed.endOffset === token.endOffset &&
      timed.quotedText === token.value &&
      validTime(timed.startTime) &&
      end !== undefined && validTime(end) &&
      compare(
        fraction(BigInt(end.numerator), BigInt(end.denominator)),
        fraction(BigInt(timed.startTime.numerator), BigInt(timed.startTime.denominator)),
      ) > 0;
  });
}

function previewTokenTimes(row: NarrationBlockV2, timing: NarrationTokenTimingMapV2): { start: BigFraction; end: BigFraction }[] {
  return row.tokens.map((_, index) => {
    const timed = timing.tokens[index]!;
    const start = fraction(BigInt(timed.startTime.numerator), BigInt(timed.startTime.denominator));
    const endWire = timingEnd(timing, index);
    const end = fraction(BigInt(endWire!.numerator), BigInt(endWire!.denominator));
    return { start, end };
  });
}

function timingEnd(timing: NarrationTokenTimingMapV2, index: number): RationalTime | undefined {
  const token = timing.tokens[index];
  if (token?.endBasis === "evidenced_audible_end") return token.audibleEnd;
  if (token?.endBasis === "next_word_derived") return timing.tokens[index + 1]?.startTime;
  return undefined;
}

function fallbackTokenTimes(row: NarrationBlockV2): { start: BigFraction; end: BigFraction }[] {
  return row.tokens.map((_, index) => ({
    start: fraction(BigInt(index * 400), 1000n),
    end: fraction(BigInt((index + 1) * 400), 1000n),
  }));
}

function validBounds(bounds: LoggedMediaBoundsV2, sourceInFrame: number): boolean {
  return Number.isSafeInteger(bounds.loggedStartFrame) &&
    Number.isSafeInteger(bounds.loggedEndExclusiveFrame) &&
    bounds.loggedEndExclusiveFrame > bounds.loggedStartFrame &&
    Number.isSafeInteger(sourceInFrame) &&
    sourceInFrame >= bounds.loggedStartFrame &&
    sourceInFrame < bounds.loggedEndExclusiveFrame &&
    Number.isSafeInteger(bounds.frameRate.numerator) &&
    bounds.frameRate.numerator > 0 &&
    Number.isSafeInteger(bounds.frameRate.denominator) &&
    bounds.frameRate.denominator > 0 &&
    /^sha256:[a-f0-9]{64}$/u.test(bounds.contentHash);
}

function validTime(value: RationalTime): boolean {
  return Number.isSafeInteger(value.numerator) &&
    value.numerator >= 0 &&
    Number.isSafeInteger(value.denominator) &&
    value.denominator > 0;
}

function fraction(n: bigint, d: bigint): BigFraction {
  const divisor = gcd(n, d);
  return { n: n / divisor, d: d / divisor };
}

function subtract(left: BigFraction, right: BigFraction): BigFraction {
  return fraction(left.n * right.d - right.n * left.d, left.d * right.d);
}

function add(left: BigFraction, right: BigFraction): BigFraction {
  return fraction(left.n * right.d + right.n * left.d, left.d * right.d);
}

function compare(left: BigFraction, right: BigFraction): number {
  const value = left.n * right.d - right.n * left.d;
  return value < 0n ? -1 : value > 0n ? 1 : 0;
}

function fractionToWire(value: BigFraction): RationalTime | null {
  const numerator = Number(value.n);
  const denominator = Number(value.d);
  return Number.isSafeInteger(numerator) && Number.isSafeInteger(denominator)
    ? { numerator, denominator }
    : null;
}

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left;
  let b = right < 0n ? -right : right;
  while (b !== 0n) [a, b] = [b, a % b];
  return a || 1n;
}

function sha256(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function emptyRow(blockId: string, diagnostics: AuthoringDiagnosticV2[]): PrimarySequenceRowProjectionV2 {
  return {
    blockId,
    sequenceId: null,
    renderable: false,
    tokens: [],
    appearances: [],
    slots: [],
    returns: [],
    overlays: [],
    supportingItems: [],
    mediaCutEstimates: [],
    diagnostics,
  };
}

function isDocument(value: unknown): value is ScriptDocumentV2 {
  return typeof value === "object" && value !== null &&
    "schemaVersion" in value &&
    value.schemaVersion === "script-document/v2" &&
    "activeDraft" in value &&
    typeof value.activeDraft === "object" && value.activeDraft !== null &&
    "blocks" in value.activeDraft && Array.isArray(value.activeDraft.blocks);
}
