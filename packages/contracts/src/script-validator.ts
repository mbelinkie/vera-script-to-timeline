import type {
  HostVisibilitySpan,
  NarrationAnnotation,
  NarrationBlock,
  PerformanceBeat,
  ScriptDocumentV1,
  VisualEvent,
} from "./generated/contracts.js";

import {
  Ajv2020,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";

import scriptDocumentSchema from "../../../contracts/script-document-v1.schema.json" with {
  type: "json",
};

export type ValidationEntityKind =
  | "block"
  | "token"
  | "visibility_span"
  | "visual_event"
  | "annotation"
  | "performance_beat"
  | "anchor";

export interface ValidationDiagnostic {
  code: string;
  message: string;
  jsonPath: string;
  blockIndex?: number;
  orderKey?: string;
  blockId?: string;
  targetBlockIndex?: number;
  targetOrderKey?: string;
  targetBlockId?: string;
  entityKind?: ValidationEntityKind;
  entityId?: string;
  tokenId?: string;
  endTokenId?: string;
}

export interface ValidationResult {
  valid: boolean;
  diagnostics: ValidationDiagnostic[];
}

type DraftBlock = ScriptDocumentV1["activeDraft"]["blocks"][number];

interface BlockReference {
  block: DraftBlock;
  index: number;
}

interface NarrationReference {
  block: NarrationBlock;
  index: number;
}

interface ResolvedRange {
  start: number;
  end: number;
  target: NarrationReference;
}

type AnchoredEntity =
  | HostVisibilitySpan
  | VisualEvent
  | NarrationAnnotation
  | PerformanceBeat;

type AnchoredEntityKind = Exclude<ValidationEntityKind, "block" | "token" | "anchor">;

interface EntityOccurrence<T extends AnchoredEntity> {
  entity: T;
  kind: AnchoredEntityKind;
  jsonPath: string;
  owner: BlockReference;
  nestedNarrationId?: string;
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
const validateStructure = ajv.compile<ScriptDocumentV1>(
  scriptDocumentSchema,
);

const blockSchemaNames = {
  section: "SectionBlock",
  narration: "NarrationBlock",
  direction: "DirectionBlock",
  visual: "VisualBlock",
  note_draft: "NoteDraftBlock",
} as const;

type DraftBlockType = keyof typeof blockSchemaNames;

const blockValidators = Object.fromEntries(
  Object.entries(blockSchemaNames).map(([type, schemaName]) => [
    type,
    ajv.compile({
      $ref: `${scriptDocumentSchema.$id}#/$defs/${schemaName}`,
    }),
  ]),
) as Record<DraftBlockType, ValidateFunction<unknown>>;

/**
 * Validate an unknown ScriptDocument value without I/O, mutation, repair, or
 * inferred defaults. Structural validation always completes before semantics.
 */
export function validateScriptDocument(input: unknown): ValidationResult {
  if (!validateStructure(input)) {
    return invalidResult(structuralDiagnostics(input));
  }

  return semanticValidation(input);
}

function structuralDiagnostics(input: unknown): ValidationDiagnostic[] {
  const diagnostics = (validateStructure.errors ?? [])
    .filter((error) => blockIndexFromPath(error.instancePath) === undefined)
    .map((error) => structuralDiagnostic(input, error));
  const blocks = blocksAt(input);
  if (blocks === undefined) {
    return diagnostics;
  }

  for (const [blockIndex, block] of blocks.entries()) {
    if (!isRecord(block)) {
      diagnostics.push({
        code: "SCHEMA_INVALID",
        message: "type: block must be an object",
        jsonPath: `/activeDraft/blocks/${blockIndex}`,
        blockIndex,
      });
      continue;
    }
    const type = block.type;
    if (!isDraftBlockType(type)) {
      diagnostics.push({
        code: "SCHEMA_INVALID",
        message: `type: must be one of ${Object.keys(blockSchemaNames).join(", ")}`,
        jsonPath: `/activeDraft/blocks/${blockIndex}/type`,
        blockIndex,
        ...(typeof block.orderKey === "string"
          ? { orderKey: block.orderKey }
          : {}),
        ...(typeof block.id === "string" ? { blockId: block.id } : {}),
      });
      continue;
    }

    const validateBlock = blockValidators[type];
    if (!validateBlock(block)) {
      diagnostics.push(
        ...(validateBlock.errors ?? []).map((error) =>
          structuralDiagnostic(
            input,
            prefixSchemaError(error, `/activeDraft/blocks/${blockIndex}`),
          ),
        ),
      );
    }
  }
  return diagnostics;
}

function blocksAt(input: unknown): unknown[] | undefined {
  if (!isRecord(input) || !isRecord(input.activeDraft)) {
    return undefined;
  }
  return Array.isArray(input.activeDraft.blocks)
    ? input.activeDraft.blocks
    : undefined;
}

function isDraftBlockType(value: unknown): value is DraftBlockType {
  return (
    typeof value === "string" &&
    Object.hasOwn(blockSchemaNames, value)
  );
}

function prefixSchemaError(
  error: ErrorObject,
  prefix: string,
): ErrorObject {
  return { ...error, instancePath: `${prefix}${error.instancePath}` };
}

function semanticValidation(document: ScriptDocumentV1): ValidationResult {
  const diagnostics: ValidationDiagnostic[] = [];
  const blockById = new Map<string, BlockReference>();
  const narrationById = new Map<string, NarrationReference>();
  const visibilityOccurrences: EntityOccurrence<HostVisibilitySpan>[] = [];
  const visualOccurrences: EntityOccurrence<VisualEvent>[] = [];
  const annotationOccurrences: EntityOccurrence<NarrationAnnotation>[] = [];
  const beatOccurrences: EntityOccurrence<PerformanceBeat>[] = [];

  for (const [blockIndex, block] of document.activeDraft.blocks.entries()) {
    const path = `/activeDraft/blocks/${blockIndex}`;
    const previousBlock = blockById.get(block.id);
    if (previousBlock === undefined) {
      blockById.set(block.id, { block, index: blockIndex });
    } else {
      diagnostics.push(
        withOwner(
          {
            code: "BLOCK_ID_DUPLICATE",
            message: `Block ID duplicates Row ${previousBlock.index + 1}.`,
            jsonPath: `${path}/id`,
            entityKind: "block",
            entityId: block.id,
          },
          { block, index: blockIndex },
        ),
      );
    }

    if (block.type === "narration") {
      if (!narrationById.has(block.id)) {
        narrationById.set(block.id, { block, index: blockIndex });
      }
      validateTokens(block, blockIndex, diagnostics);
      for (const [spanIndex, entity] of block.hostVisibilitySpans.entries()) {
        visibilityOccurrences.push({
          entity,
          kind: "visibility_span",
          jsonPath: `${path}/hostVisibilitySpans/${spanIndex}`,
          owner: { block, index: blockIndex },
          nestedNarrationId: block.id,
        });
      }
      for (const [eventIndex, entity] of block.visualEvents.entries()) {
        visualOccurrences.push({
          entity,
          kind: "visual_event",
          jsonPath: `${path}/visualEvents/${eventIndex}`,
          owner: { block, index: blockIndex },
          nestedNarrationId: block.id,
        });
      }
      for (const [annotationIndex, entity] of (block.annotations ?? []).entries()) {
        const occurrence = {
          entity,
          kind: "annotation",
          jsonPath: `${path}/annotations/${annotationIndex}`,
          owner: { block, index: blockIndex },
          nestedNarrationId: block.id,
        } satisfies EntityOccurrence<NarrationAnnotation>;
        annotationOccurrences.push(occurrence);
        if (block.state !== "active") {
          diagnostics.push(
            occurrenceDiagnostic(
              occurrence,
              "ANNOTATION_INACTIVE_NARRATION",
              "Narration annotations must belong to an active narration row.",
              occurrence.jsonPath,
            ),
          );
        }
      }
      for (const [beatIndex, entity] of (block.performanceBeats ?? []).entries()) {
        const occurrence = {
          entity,
          kind: "performance_beat",
          jsonPath: `${path}/performanceBeats/${beatIndex}`,
          owner: { block, index: blockIndex },
          nestedNarrationId: block.id,
        } satisfies EntityOccurrence<PerformanceBeat>;
        beatOccurrences.push(occurrence);
        if (block.state !== "active") {
          diagnostics.push(
            occurrenceDiagnostic(
              occurrence,
              "PERFORMANCE_BEAT_INACTIVE_NARRATION",
              "Performance beats must belong to an active narration row.",
              occurrence.jsonPath,
            ),
          );
        }
      }
    } else if (block.type === "visual") {
      visualOccurrences.push({
        entity: block.event,
        kind: "visual_event",
        jsonPath: `${path}/event`,
        owner: { block, index: blockIndex },
      });
    }
  }

  validateOccurrenceIds(
    visibilityOccurrences,
    "VISIBILITY_SPAN_ID_DUPLICATE",
    diagnostics,
  );
  validateOccurrenceIds(
    visualOccurrences,
    "VISUAL_EVENT_ID_DUPLICATE",
    diagnostics,
  );
  validateOccurrenceIds(
    annotationOccurrences,
    "ANNOTATION_ID_DUPLICATE",
    diagnostics,
  );
  validateOccurrenceIds(
    beatOccurrences,
    "PERFORMANCE_BEAT_ID_DUPLICATE",
    diagnostics,
  );

  const resolvedVisibility = new Map<
    EntityOccurrence<HostVisibilitySpan>,
    ResolvedRange
  >();
  for (const occurrence of visibilityOccurrences) {
    const range = resolveAnchor(
      occurrence,
      blockById,
      narrationById,
      diagnostics,
    );
    if (range !== undefined) {
      resolvedVisibility.set(occurrence, range);
    }
  }

  const resolvedVisuals = new Map<
    EntityOccurrence<VisualEvent>,
    ResolvedRange
  >();
  for (const occurrence of visualOccurrences) {
    const range = resolveAnchor(
      occurrence,
      blockById,
      narrationById,
      diagnostics,
    );
    if (range !== undefined) {
      resolvedVisuals.set(occurrence, range);
    }
  }

  const resolvedAnnotations = resolveOccurrences(
    annotationOccurrences,
    blockById,
    narrationById,
    diagnostics,
  );
  const resolvedBeats = resolveOccurrences(
    beatOccurrences,
    blockById,
    narrationById,
    diagnostics,
  );

  for (const narration of narrationById.values()) {
    if (narration.block.state === "active") {
      validateCoverage(
        narration,
        resolvedVisibility,
        resolvedVisuals,
        diagnostics,
      );
      validateAnnotationVisibility(
        narration,
        annotationOccurrences,
        resolvedAnnotations,
        resolvedVisibility,
        diagnostics,
      );
      validatePerformanceBeatCoverage(
        narration,
        beatOccurrences,
        resolvedBeats,
        diagnostics,
      );
    }
  }

  const sortedDiagnostics = sortDiagnostics(diagnostics);
  return {
    valid: sortedDiagnostics.length === 0,
    diagnostics: sortedDiagnostics,
  };
}

function validateTokens(
  block: NarrationBlock,
  blockIndex: number,
  diagnostics: ValidationDiagnostic[],
): void {
  const seenIds = new Map<string, number>();
  let previousEnd = 0;

  for (const [tokenIndex, token] of block.tokens.entries()) {
    const jsonPath = `/activeDraft/blocks/${blockIndex}/tokens/${tokenIndex}`;
    const context = {
      block,
      index: blockIndex,
    } satisfies BlockReference;
    const previousIndex = seenIds.get(token.id);
    if (previousIndex === undefined) {
      seenIds.set(token.id, tokenIndex);
    } else {
      diagnostics.push(
        withOwner(
          {
            code: "TOKEN_ID_DUPLICATE",
            message: `Token ID duplicates token ${previousIndex + 1} in this narration row.`,
            jsonPath: `${jsonPath}/id`,
            entityKind: "token",
            entityId: token.id,
            tokenId: token.id,
          },
          context,
        ),
      );
    }

    const offsetsValid =
      token.startOffset >= 0 &&
      token.startOffset < token.endOffset &&
      token.endOffset <= block.text.length;
    if (!offsetsValid) {
      diagnostics.push(
        withOwner(
          {
            code: "TOKEN_OFFSET_INVALID",
            message: `Token offsets [${token.startOffset}, ${token.endOffset}) are outside the narration text or have no duration.`,
            jsonPath,
            entityKind: "token",
            entityId: token.id,
            tokenId: token.id,
          },
          context,
        ),
      );
    }

    if (tokenIndex > 0 && token.startOffset < previousEnd) {
      diagnostics.push(
        withOwner(
          {
            code: "TOKEN_ORDER_INVALID",
            message: `Token starts at UTF-16 offset ${token.startOffset}, before the previous token ends at ${previousEnd}.`,
            jsonPath,
            entityKind: "token",
            entityId: token.id,
            tokenId: token.id,
          },
          context,
        ),
      );
    }

    if (
      offsetsValid &&
      block.text.slice(token.startOffset, token.endOffset) !== token.value
    ) {
      diagnostics.push(
        withOwner(
          {
            code: "TOKEN_TEXT_MISMATCH",
            message: `Token value does not exactly match narration UTF-16 slice [${token.startOffset}, ${token.endOffset}).`,
            jsonPath: `${jsonPath}/value`,
            entityKind: "token",
            entityId: token.id,
            tokenId: token.id,
          },
          context,
        ),
      );
    }

    previousEnd = Math.max(previousEnd, token.endOffset);
  }
}

function validateOccurrenceIds<T extends AnchoredEntity>(
  occurrences: EntityOccurrence<T>[],
  code:
    | "VISIBILITY_SPAN_ID_DUPLICATE"
    | "VISUAL_EVENT_ID_DUPLICATE"
    | "ANNOTATION_ID_DUPLICATE"
    | "PERFORMANCE_BEAT_ID_DUPLICATE",
  diagnostics: ValidationDiagnostic[],
): void {
  const firstById = new Map<string, EntityOccurrence<T>>();
  for (const occurrence of occurrences) {
    const identity = occurrence.kind === "annotation" || occurrence.kind === "performance_beat"
      ? occurrence.entity.id.toLowerCase()
      : occurrence.entity.id;
    const previous = firstById.get(identity);
    if (previous === undefined) {
      firstById.set(identity, occurrence);
      continue;
    }
    diagnostics.push(
      withOwner(
        {
          code,
          message: `${entityLabel(occurrence.kind)} ID duplicates an occurrence on Row ${previous.owner.index + 1}.`,
          jsonPath: `${occurrence.jsonPath}/id`,
          entityKind: occurrence.kind,
          entityId: occurrence.entity.id,
        },
        occurrence.owner,
      ),
    );
  }
}

function resolveOccurrences<T extends AnchoredEntity>(
  occurrences: EntityOccurrence<T>[],
  blockById: ReadonlyMap<string, BlockReference>,
  narrationById: ReadonlyMap<string, NarrationReference>,
  diagnostics: ValidationDiagnostic[],
): Map<EntityOccurrence<T>, ResolvedRange> {
  const resolved = new Map<EntityOccurrence<T>, ResolvedRange>();
  for (const occurrence of occurrences) {
    const range = resolveAnchor(
      occurrence,
      blockById,
      narrationById,
      diagnostics,
    );
    if (range !== undefined) resolved.set(occurrence, range);
  }
  return resolved;
}

function resolveAnchor<T extends AnchoredEntity>(
  occurrence: EntityOccurrence<T>,
  blockById: ReadonlyMap<string, BlockReference>,
  narrationById: ReadonlyMap<string, NarrationReference>,
  diagnostics: ValidationDiagnostic[],
): ResolvedRange | undefined {
  const { range } = occurrence.entity;
  const anchorPath = `${occurrence.jsonPath}/range`;
  const targetBlock = blockById.get(range.blockId);
  if (targetBlock === undefined) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_BLOCK_NOT_FOUND",
        `Anchor target block ${range.blockId} does not exist in activeDraft.`,
        `${anchorPath}/blockId`,
      ),
    );
    return undefined;
  }
  if (targetBlock.block.type !== "narration") {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_BLOCK_NOT_NARRATION",
        `Anchor target Row ${targetBlock.index + 1} is ${targetBlock.block.type}, not narration.`,
        `${anchorPath}/blockId`,
        targetBlock,
      ),
    );
    return undefined;
  }
  if (
    occurrence.nestedNarrationId !== undefined &&
    range.blockId !== occurrence.nestedNarrationId
  ) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_BLOCK_MISMATCH",
        `${entityLabel(occurrence.kind)} nested in a narration row must target that same row.`,
        `${anchorPath}/blockId`,
        targetBlock,
      ),
    );
    return undefined;
  }

  const target = narrationById.get(range.blockId);
  if (target === undefined) {
    return undefined;
  }
  const tokenIndexById = new Map(
    target.block.tokens.map((token, index) => [token.id, index]),
  );
  const startTokenIndex = tokenIndexById.get(range.startTokenId);
  const endTokenIndex = tokenIndexById.get(range.endTokenId);
  if (startTokenIndex === undefined) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_TOKEN_NOT_FOUND",
        `Anchor start token ${range.startTokenId} does not exist on target Row ${target.index + 1}.`,
        `${anchorPath}/startTokenId`,
        target,
        range.startTokenId,
      ),
    );
  }
  if (endTokenIndex === undefined) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_TOKEN_NOT_FOUND",
        `Anchor end token ${range.endTokenId} does not exist on target Row ${target.index + 1}.`,
        `${anchorPath}/endTokenId`,
        target,
        range.endTokenId,
      ),
    );
  }
  if (startTokenIndex === undefined || endTokenIndex === undefined) {
    return undefined;
  }

  const start =
    startTokenIndex + (range.startAffinity === "after" ? 1 : 0);
  const end = endTokenIndex + (range.endAffinity === "after" ? 1 : 0);
  if (start > end) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_RANGE_REVERSED",
        `Affinity-resolved token interval [${start}, ${end}) is reversed.`,
        anchorPath,
        target,
      ),
    );
    return undefined;
  }
  if (start === end) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_RANGE_EMPTY",
        `Affinity-resolved token interval [${start}, ${end}) is empty.`,
        anchorPath,
        target,
      ),
    );
    if (occurrence.kind === "visual_event") {
      diagnostics.push(
        occurrenceDiagnostic(
          occurrence,
          "VISUAL_EVENT_ZERO_DURATION",
          "Visual events must cover at least one spoken token.",
          anchorPath,
          target,
        ),
      );
    }
    return undefined;
  }

  const selectedTokens = target.block.tokens.slice(start, end);
  const firstToken = selectedTokens[0];
  const lastToken = selectedTokens.at(-1);
  if (firstToken === undefined || lastToken === undefined) {
    return undefined;
  }
  const selectedText = target.block.text.slice(
    firstToken.startOffset,
    lastToken.endOffset,
  );
  if (range.quotedText !== selectedText) {
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANCHOR_QUOTE_MISMATCH",
        `quotedText must exactly equal the selected narration slice ${JSON.stringify(selectedText)}.`,
        `${anchorPath}/quotedText`,
        target,
      ),
    );
  }

  return { start, end, target };
}

function validateAnnotationVisibility(
  narration: NarrationReference,
  occurrences: readonly EntityOccurrence<NarrationAnnotation>[],
  resolvedAnnotations: ReadonlyMap<
    EntityOccurrence<NarrationAnnotation>,
    ResolvedRange
  >,
  resolvedVisibility: ReadonlyMap<
    EntityOccurrence<HostVisibilitySpan>,
    ResolvedRange
  >,
  diagnostics: ValidationDiagnostic[],
): void {
  const visibilityCount = Array.from(
    { length: narration.block.tokens.length },
    () => 0,
  );
  for (const range of resolvedVisibility.values()) {
    if (range.target.block.id !== narration.block.id) continue;
    for (let index = range.start; index < range.end; index += 1) {
      visibilityCount[index]! += 1;
    }
  }

  for (const occurrence of occurrences) {
    const range = resolvedAnnotations.get(occurrence);
    if (
      range === undefined ||
      range.target.block.id !== narration.block.id ||
      !visibilityCount.slice(range.start, range.end).some((count) => count !== 1)
    ) {
      continue;
    }
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "ANNOTATION_HOST_VISIBILITY_INVALID",
        "Annotation ranges must be covered by exactly one host-visibility state.",
        `${occurrence.jsonPath}/range`,
      ),
    );
  }
}

function validatePerformanceBeatCoverage(
  narration: NarrationReference,
  occurrences: readonly EntityOccurrence<PerformanceBeat>[],
  resolvedBeats: ReadonlyMap<EntityOccurrence<PerformanceBeat>, ResolvedRange>,
  diagnostics: ValidationDiagnostic[],
): void {
  const owned = occurrences.filter(
    ({ owner }) => owner.index === narration.index,
  );
  if (owned.length === 0) return;

  const assignments: Array<EntityOccurrence<PerformanceBeat>[]> = Array.from(
    { length: narration.block.tokens.length },
    () => [],
  );
  let previousStart = -1;
  for (const occurrence of owned) {
    const range = resolvedBeats.get(occurrence);
    if (range === undefined || range.target.block.id !== narration.block.id) {
      continue;
    }
    if (range.start < previousStart) {
      diagnostics.push(
        occurrenceDiagnostic(
          occurrence,
          "PERFORMANCE_BEAT_ORDER_INVALID",
          "Performance beats must be ordered by their resolved token ranges.",
          occurrence.jsonPath,
        ),
      );
    }
    previousStart = range.start;
    for (let index = range.start; index < range.end; index += 1) {
      assignments[index]!.push(occurrence);
    }
  }

  for (const occurrence of owned) {
    const range = resolvedBeats.get(occurrence);
    if (
      range === undefined ||
      !assignments
        .slice(range.start, range.end)
        .some((items) => items.length > 1)
    ) {
      continue;
    }
    diagnostics.push(
      occurrenceDiagnostic(
        occurrence,
        "PERFORMANCE_BEAT_OVERLAP",
        "Performance beats must not overlap.",
        occurrence.jsonPath,
      ),
    );
  }

  for (const [start, end] of contiguousRanges(
    assignments.map((items) => items.length === 0),
  )) {
    const firstToken = narration.block.tokens[start]!;
    const lastToken = narration.block.tokens[end - 1]!;
    diagnostics.push(
      withOwner(
        {
          code: "PERFORMANCE_BEAT_COVERAGE_GAP",
          message: "Explicit performance beats must cover every spoken token exactly once.",
          jsonPath: `/activeDraft/blocks/${narration.index}/performanceBeats`,
          entityKind: "token",
          tokenId: firstToken.id,
          endTokenId: lastToken.id,
        },
        narration,
      ),
    );
  }
}

function validateCoverage(
  narration: NarrationReference,
  resolvedVisibility: ReadonlyMap<
    EntityOccurrence<HostVisibilitySpan>,
    ResolvedRange
  >,
  resolvedVisuals: ReadonlyMap<EntityOccurrence<VisualEvent>, ResolvedRange>,
  diagnostics: ValidationDiagnostic[],
): void {
  const tokenCount = narration.block.tokens.length;
  const visibilityByToken: HostVisibilitySpan[][] = Array.from(
    { length: tokenCount },
    () => [],
  );
  for (const [occurrence, range] of resolvedVisibility) {
    if (range.target.block.id !== narration.block.id) {
      continue;
    }
    for (let index = range.start; index < range.end; index += 1) {
      visibilityByToken[index]!.push(occurrence.entity);
    }
  }

  for (const [start, end] of contiguousRanges(
    visibilityByToken.map((assignments) => assignments.length === 0),
  )) {
    diagnostics.push(
      coverageDiagnostic(
        narration,
        "HOST_VISIBILITY_GAP",
        "Every active spoken token must have exactly one authored host-visibility state.",
        "hostVisibilitySpans",
        start,
        end,
      ),
    );
  }
  const overlapKinds = visibilityByToken.map(hostVisibilityOverlapKind);
  for (const kind of ["duplicate", "contradictory"] as const) {
    for (const [start, end] of contiguousRanges(
      overlapKinds.map((candidate) => candidate === kind),
    )) {
      diagnostics.push(
        coverageDiagnostic(
          narration,
          "HOST_VISIBILITY_OVERLAP",
          kind === "contradictory"
            ? "Spoken tokens have contradictory on-camera and voiceover assignments."
            : "Spoken tokens have duplicate host-visibility assignments.",
          "hostVisibilitySpans",
          start,
          end,
        ),
      );
    }
  }

  const qualifyingVisualByToken = Array.from(
    { length: tokenCount },
    () => false,
  );
  for (const [occurrence, range] of resolvedVisuals) {
    if (
      range.target.block.id !== narration.block.id ||
      !qualifiesForVoiceoverCoverage(occurrence.entity)
    ) {
      continue;
    }
    for (let index = range.start; index < range.end; index += 1) {
      qualifyingVisualByToken[index] = true;
    }
  }
  const uncoveredVoiceover = visibilityByToken.map(
    (assignments, index) =>
      assignments.some(({ state }) => state === "voiceover") &&
      !qualifyingVisualByToken[index],
  );
  for (const [start, end] of contiguousRanges(uncoveredVoiceover)) {
    diagnostics.push(
      coverageDiagnostic(
        narration,
        "VOICEOVER_VISUAL_GAP",
        "Voiceover tokens require ready full-frame local media or an unresolved full-frame visual placeholder.",
        "visualEvents",
        start,
        end,
      ),
    );
  }
}

function hostVisibilityOverlapKind(
  assignments: readonly HostVisibilitySpan[],
): "none" | "duplicate" | "contradictory" {
  if (assignments.length < 2) {
    return "none";
  }
  return new Set(assignments.map(({ state }) => state)).size > 1
    ? "contradictory"
    : "duplicate";
}

function qualifiesForVoiceoverCoverage(event: VisualEvent): boolean {
  if (event.presentationMode !== "full_frame") {
    return false;
  }
  if (event.source.kind === "local_media") {
    return event.status === "ready";
  }
  return event.source.unresolvedVisual && event.status === "unresolved";
}

function contiguousRanges(flags: readonly boolean[]): [number, number][] {
  const ranges: [number, number][] = [];
  let start: number | undefined;
  for (let index = 0; index <= flags.length; index += 1) {
    if (flags[index] === true && start === undefined) {
      start = index;
    } else if (flags[index] !== true && start !== undefined) {
      ranges.push([start, index]);
      start = undefined;
    }
  }
  return ranges;
}

function coverageDiagnostic(
  narration: NarrationReference,
  code: "HOST_VISIBILITY_GAP" | "HOST_VISIBILITY_OVERLAP" | "VOICEOVER_VISUAL_GAP",
  message: string,
  collection: "hostVisibilitySpans" | "visualEvents",
  start: number,
  end: number,
): ValidationDiagnostic {
  const firstToken = narration.block.tokens[start]!;
  const lastToken = narration.block.tokens[end - 1]!;
  return withOwner(
    {
      code,
      message,
      jsonPath: `/activeDraft/blocks/${narration.index}/${collection}`,
      entityKind: "token",
      tokenId: firstToken.id,
      endTokenId: lastToken.id,
    },
    narration,
  );
}

function occurrenceDiagnostic<T extends AnchoredEntity>(
  occurrence: EntityOccurrence<T>,
  code: string,
  message: string,
  jsonPath: string,
  target?: BlockReference,
  tokenId?: string,
): ValidationDiagnostic {
  const diagnostic = withOwner(
    {
      code,
      message,
      jsonPath,
      entityKind: occurrence.kind,
      entityId: occurrence.entity.id,
      ...(tokenId === undefined ? {} : { tokenId }),
    },
    occurrence.owner,
  );
  if (target === undefined || target.index === occurrence.owner.index) {
    return diagnostic;
  }
  return {
    ...diagnostic,
    targetBlockIndex: target.index,
    targetOrderKey: target.block.orderKey,
    targetBlockId: target.block.id,
  };
}

function structuralDiagnostic(
  input: unknown,
  error: ErrorObject,
): ValidationDiagnostic {
  const jsonPath = schemaErrorPath(error);
  const blockIndex = blockIndexFromPath(jsonPath);
  const block = blockAt(input, blockIndex);
  return {
    code: "SCHEMA_INVALID",
    message: `${error.keyword}: ${error.message ?? "schema validation failed"}`,
    jsonPath,
    ...(blockIndex === undefined ? {} : { blockIndex }),
    ...(typeof block?.orderKey === "string" ? { orderKey: block.orderKey } : {}),
    ...(typeof block?.id === "string" ? { blockId: block.id } : {}),
  };
}

function schemaErrorPath(error: ErrorObject): string {
  if (error.keyword === "required") {
    const missingProperty = (error.params as { missingProperty?: unknown })
      .missingProperty;
    return typeof missingProperty === "string"
      ? `${error.instancePath}/${escapeJsonPointer(missingProperty)}`
      : error.instancePath;
  }
  if (error.keyword === "additionalProperties") {
    const additionalProperty = (
      error.params as { additionalProperty?: unknown }
    ).additionalProperty;
    return typeof additionalProperty === "string"
      ? `${error.instancePath}/${escapeJsonPointer(additionalProperty)}`
      : error.instancePath;
  }
  return error.instancePath;
}

function escapeJsonPointer(value: string): string {
  return value.replaceAll("~", "~0").replaceAll("/", "~1");
}

function blockIndexFromPath(jsonPath: string): number | undefined {
  const match = /^\/activeDraft\/blocks\/(\d+)/u.exec(jsonPath);
  return match?.[1] === undefined ? undefined : Number(match[1]);
}

function blockAt(
  input: unknown,
  blockIndex: number | undefined,
): Record<string, unknown> | undefined {
  if (blockIndex === undefined || !isRecord(input)) {
    return undefined;
  }
  const activeDraft = input.activeDraft;
  if (!isRecord(activeDraft) || !Array.isArray(activeDraft.blocks)) {
    return undefined;
  }
  const block: unknown = activeDraft.blocks[blockIndex];
  return isRecord(block) ? block : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function withOwner(
  diagnostic: ValidationDiagnostic,
  owner: BlockReference,
): ValidationDiagnostic {
  return {
    ...diagnostic,
    blockIndex: owner.index,
    orderKey: owner.block.orderKey,
    blockId: owner.block.id,
  };
}

function entityLabel(kind: AnchoredEntityKind): string {
  const labels: Record<AnchoredEntityKind, string> = {
    visibility_span: "Visibility span",
    visual_event: "Visual event",
    annotation: "Annotation",
    performance_beat: "Performance beat",
  };
  return labels[kind];
}

function invalidResult(
  diagnostics: ValidationDiagnostic[],
): ValidationResult {
  return { valid: false, diagnostics: sortDiagnostics(diagnostics) };
}

function sortDiagnostics(
  diagnostics: ValidationDiagnostic[],
): ValidationDiagnostic[] {
  return diagnostics.toSorted((left, right) => {
    const leftRow = left.blockIndex ?? Number.MAX_SAFE_INTEGER;
    const rightRow = right.blockIndex ?? Number.MAX_SAFE_INTEGER;
    return (
      leftRow - rightRow ||
      compareStrings(left.jsonPath, right.jsonPath) ||
      compareStrings(left.code, right.code) ||
      compareStrings(left.entityId ?? "", right.entityId ?? "") ||
      compareStrings(left.message, right.message)
    );
  });
}

function compareStrings(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}
