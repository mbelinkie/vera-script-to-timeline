/** One saved row edit for an already-authorized Research quote. No fetching or UI authority lives here. */
import { randomUUID } from "node:crypto";

import type {
  ContentSlot,
  NarratedVisualPayloadV2,
  NarrationBlockV2,
  QuoteBoxV2,
  ResearchQuotePictureV2,
  ResearchQuoteProvenanceV2,
  RowGapV2,
  ScriptDocumentV2,
} from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { isCoverageRefusalV2, setVisualRangeV2 } from "./authoring-v2-coverage.js";
import { spliceNarrationTextV2 } from "./authoring-v2-narration-text.js";
import { applyRowEditV2, type RowEditCommandV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { attachVisualToWordsV2 } from "./authoring-v2-visual-lifecycle.js";
import { retypeVisualPayloadV2 } from "./authoring-v2-visual-type.js";

type QuoteRowCommand = Extract<RowEditCommandV2, { kind: "edit_row" | "create_row" }>;

/** The host has already authorized and resolved the quote. The box's fields remain editable per use. */
export type AuthorizedResearchQuoteV2 = Omit<QuoteBoxV2,
  "backgroundPayloadId" | "researchProjectId" | "researchSourceId" | "researchQuoteUseId" | "researchQuoteVersion"> & {
  /** Full words for an insertion; not substituted for the independently editable box display text. */
  spokenText: string;
  researchProjectId: string;
  researchSourceId: string;
  researchQuoteVersion: number;
};

/** Resolved, host-authorized original picture only; a missing picture becomes the existing Need to Find card. */
export type ResearchQuoteBackgroundV2 =
  | { kind: "still_image"; picture: ResearchQuotePictureV2; displayName?: string }
  | null;

export interface ResearchQuotePlacementV2 {
  expectedDocumentRevision: number;
  /** Row fields are required for insert and selected_words destinations, and omitted for a gap. */
  rowId?: string;
  expectedRowVersion?: number;
  expectedSequenceVersion?: number;
  destination:
    | { kind: "gap"; sectionId: string | null; afterRowId: string | null; beforeRowId: string | null }
    | { kind: "insert"; beforeTokenId: string | null }
    | { kind: "selected_words"; startTokenId: string; endTokenId: string };
}

export type PreparedResearchQuotePlacementV2 =
  | { ok: true; command: QuoteRowCommand; document: ScriptDocumentV2 }
  | { ok: false; diagnostics: AuthoringDiagnosticV2[] };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

function refusal(code: string, message: string): PreparedResearchQuotePlacementV2 {
  return { ok: false, diagnostics: [{ code, message, jsonPath: "$", severity: "error" }] };
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function reservedIds(value: unknown, ids = new Set<string>()): Set<string> {
  if (typeof value === "string" && UUID.test(value)) ids.add(value.toLowerCase());
  else if (value && typeof value === "object") for (const child of Object.values(value)) reservedIds(child, ids);
  return ids;
}

function safeText(text: unknown, required: boolean): text is string {
  if (typeof text !== "string" || text.length > 20_000 || text.includes("\0") ||
      required && text.trim().length === 0) return false;
  // JSON and the v2 quote-box validator accept astral characters but not stray UTF-16 surrogates.
  for (let i = 0; i < text.length; i += 1) {
    const unit = text.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (i + 1 >= text.length || text.charCodeAt(i + 1) < 0xdc00 || text.charCodeAt(i + 1) > 0xdfff) return false;
      i += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) return false;
  }
  return true;
}

function validQuotePicture(picture: ResearchQuotePictureV2, projectId: string): boolean {
  const original = picture?.original;
  return !!picture && UUID.test(picture.researchProjectId ?? "") &&
    picture.researchProjectId.toLowerCase() === projectId.toLowerCase() &&
    ["web_capture", "source", "quote"].includes(picture.ownerKind) &&
    UUID.test(picture.ownerId ?? "") && UUID.test(picture.revisionId ?? "") &&
    !!original && safeText(original.versionId, true) &&
    /^[a-f0-9]{64}$/iu.test(original.sha256 ?? "") &&
    Number.isSafeInteger(original.byteCount) && original.byteCount > 0 && original.byteCount <= 20 * 1024 * 1024 &&
    ["image/jpeg", "image/png", "image/webp"].includes(original.mimeType) &&
    Number.isSafeInteger(original.width) && original.width > 0 && original.width <= 8192 &&
    Number.isSafeInteger(original.height) && original.height > 0 && original.height <= 8192 &&
    original.width * original.height <= 16_777_216;
}

function validBackground(background: ResearchQuoteBackgroundV2, quote: AuthorizedResearchQuoteV2): boolean {
  if (background === null) return true;
  if (!background || background.kind !== "still_image" || !validQuotePicture(background.picture, quote.researchProjectId)) return false;
  if (background.picture.ownerKind === "source" &&
      background.picture.ownerId.toLowerCase() !== quote.researchSourceId.toLowerCase()) return false;
  if (background.picture.ownerKind === "quote" &&
      background.picture.ownerId.toLowerCase() !== quote.researchQuoteId.toLowerCase()) return false;
  return background.displayName === undefined || safeText(background.displayName, false);
}

function validGap(destination: Extract<ResearchQuotePlacementV2["destination"], { kind: "gap" }>): boolean {
  return (destination.sectionId === null || UUID.test(destination.sectionId)) &&
    (destination.afterRowId === null || UUID.test(destination.afterRowId)) &&
    (destination.beforeRowId === null || UUID.test(destination.beforeRowId));
}

function quoteForNarration(text: string): string {
  const trimmed = text.trim();
  const alreadyQuoted = (trimmed.startsWith("“") && trimmed.endsWith("”")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'));
  return alreadyQuoted ? trimmed : `“${trimmed}”`;
}

function samePicture(a: ResearchQuotePictureV2 | undefined, b: ResearchQuotePictureV2 | undefined): boolean {
  if (!a || !b) return false;
  return a.researchProjectId.toLowerCase() === b.researchProjectId.toLowerCase() &&
    a.ownerKind === b.ownerKind && a.ownerId.toLowerCase() === b.ownerId.toLowerCase() && a.revisionId === b.revisionId &&
    a.original.versionId === b.original.versionId && a.original.sha256 === b.original.sha256 &&
    a.original.byteCount === b.original.byteCount && a.original.mimeType === b.original.mimeType &&
    a.original.width === b.original.width && a.original.height === b.original.height;
}

function anchorTokenId(value: unknown): string | null {
  if (!record(value) || !record(value.anchor) || typeof value.anchor.tokenId !== "string") return null;
  return value.anchor.tokenId;
}

interface QuoteContinuation {
  slotId: string;
  startTokenId: string;
  payload: NarratedVisualPayloadV2;
}

function backgroundMatches(payload: NarratedVisualPayloadV2, background: ResearchQuoteBackgroundV2): boolean {
  if (background === null) {
    return payload.pictureKind === "unresolved_visual" && payload.source.kind === "unresolved_visual";
  }
  return samePicture(payload.researchQuotePicture, background.picture);
}

function slotStartTokenId(slot: ContentSlot, row: NarrationBlockV2): string | null {
  const words = spokenTokensV2(row);
  const boundary = slot.boundaryBefore;
  if (boundary.kind === "row_start") return words[0]?.id ?? null;
  if (boundary.kind === "spoken_word") return boundary.anchor.tokenId;
  if (boundary.kind === "audible_word_end") {
    const index = words.findIndex((token) => token.id === boundary.anchor.tokenId);
    return index >= 0 ? words[index + 1]?.id ?? null : null;
  }
  return null;
}

/** Only the quote whose final word touches this placement can donate its background. */
function previousQuoteContinuation(
  row: NarrationBlockV2,
  previousTokenId: string | null,
  quote: AuthorizedResearchQuoteV2,
  background: ResearchQuoteBackgroundV2,
): QuoteContinuation | null {
  if (!previousTokenId) return null;
  const adjacent = row.overlayEvents.filter((candidate) => {
    const box = candidate.quoteBox;
    return box?.researchQuoteUseId && box.researchProjectId?.toLowerCase() === quote.researchProjectId.toLowerCase() &&
      box.researchSourceId?.toLowerCase() === quote.researchSourceId.toLowerCase() &&
      anchorTokenId(candidate.timing.end) === previousTokenId;
  });
  if (adjacent.length !== 1 || !adjacent[0]!.quoteBox) return null;
  const event = adjacent[0]!;
  const slot = row.primaryVisualSequence?.slots.find((candidate): candidate is ContentSlot =>
    candidate.kind === "content" && candidate.payload.kind === "visual" &&
    candidate.payload.payloadId === event.quoteBox!.backgroundPayloadId);
  if (!slot || slot.payload.kind !== "visual" || !backgroundMatches(slot.payload, background)) return null;
  const startTokenId = slotStartTokenId(slot, row);
  return startTokenId ? { slotId: slot.id, startTokenId, payload: slot.payload } : null;
}

function unchangedOtherVisuals(
  before: NarrationBlockV2,
  after: readonly (ContentSlot | { kind: "return" })[],
  extendedSlotId: string,
): boolean {
  const visible = (slots: readonly (ContentSlot | { kind: "return" })[]) => slots.filter((slot) =>
    slot.kind === "content" && slot.id !== extendedSlotId && slot.payload.kind !== "on_camera");
  return JSON.stringify(visible(before.primaryVisualSequence!.slots)) === JSON.stringify(visible(after));
}

function tryExtendBackground(
  row: NarrationBlockV2,
  continuation: QuoteContinuation | null,
  endTokenId: string,
): string | null {
  if (!continuation || !row.primaryVisualSequence) return null;
  const extended = setVisualRangeV2(row, continuation.slotId, continuation.startTokenId, endTokenId);
  if (isCoverageRefusalV2(extended)) {
    return extended.code === "RANGE_UNCHANGED" ? continuation.payload.payloadId : null;
  }
  if (extended.unattached.length > 0 || !unchangedOtherVisuals(row, extended.slots, continuation.slotId)) return null;
  row.primaryVisualSequence.slots = extended.slots;
  row.primaryVisualSequence.version += 1;
  return continuation.payload.payloadId;
}

function newNarrationRow(id: string, sequenceId: string, slotId: string): NarrationBlockV2 {
  return {
    type: "narration", id, orderKey: `row-${id}`, text: "", tokens: [],
    primaryVisualSequence: {
      id: sequenceId, version: 1, slots: [{
        id: slotId, kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
        payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1,
      }],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function newBackgroundPayload(
  background: ResearchQuoteBackgroundV2,
  payloadId: string,
  nextId: () => string,
): NarratedVisualPayloadV2 | null {
  if (background === null) {
    const missing = retypeVisualPayloadV2(
      { kind: "undefined", payloadId, description: "Research quote picture not selected." },
      { type: "need_to_find", description: "Find a picture for this Research quote." },
    );
    return missing.ok && missing.payload.kind === "visual" ? missing.payload : null;
  }
  return {
    kind: "visual", payloadId, pictureKind: "image",
    source: { kind: "media_reference", mediaReferenceId: nextId() }, sourceUsage: null, audioPolicy: "mute",
    ...(background.displayName ? { displayName: background.displayName } : {}),
    researchQuotePicture: structuredClone(background.picture),
  };
}

function addQuoteOverlay(
  row: NarrationBlockV2,
  quote: AuthorizedResearchQuoteV2,
  useId: string,
  backgroundPayloadId: string,
  startTokenId: string,
  endTokenId: string,
  nextId: () => string,
): void {
  const startWord = row.tokens.find((token) => token.id === startTokenId)!;
  const endWord = row.tokens.find((token) => token.id === endTokenId)!;
  const box: QuoteBoxV2 = {
    researchQuoteId: quote.researchQuoteId,
    researchProjectId: quote.researchProjectId,
    researchSourceId: quote.researchSourceId,
    researchQuoteUseId: useId,
    researchQuoteVersion: quote.researchQuoteVersion,
    displayText: quote.displayText,
    speakerName: quote.speakerName,
    speakerTitle: quote.speakerTitle,
    citationText: quote.citationText,
    italicSpan: structuredClone(quote.italicSpan),
    templateRevision: quote.templateRevision,
    backgroundPayloadId,
    ...(quote.citationOverridden ? { citationOverridden: true as const } : {}),
  };
  const graphicId = nextId();
  const graphicRevisionId = nextId();
  row.overlayEvents.push({
    id: nextId(), version: 1,
    payload: {
      kind: "visual", payloadId: nextId(), pictureKind: "graphic",
      source: { kind: "graphic_revision", graphicId, revisionId: graphicRevisionId },
      sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
    },
    timing: {
      kind: "timed",
      start: { kind: "word", anchor: {
        blockId: row.id, tokenId: startTokenId, quotedWord: startWord.value,
        affinity: "before", anchorVersion: row.version,
      } },
      end: { kind: "audible_word_end", anchor: {
        blockId: row.id, tokenId: endTokenId, quotedWord: endWord.value,
        affinity: "after", anchorVersion: row.version,
      } },
    },
    quoteBox: box,
  });
}

function attachQuoteBackground(
  row: NarrationBlockV2,
  background: ResearchQuoteBackgroundV2,
  continuation: QuoteContinuation | null,
  startTokenId: string,
  endTokenId: string,
  nextId: () => string,
): string | null {
  const extended = tryExtendBackground(row, continuation, endTokenId);
  if (extended) return extended;
  const payloadId = nextId();
  const slotId = nextId();
  const payload = newBackgroundPayload(background, payloadId, nextId);
  if (!payload) return null;
  row.unattachedVisuals = [...(row.unattachedVisuals ?? []), { slotId, payload, version: 1 }];
  const attached = attachVisualToWordsV2(row, slotId, startTokenId, endTokenId);
  if (isCoverageRefusalV2(attached)) return null;
  return payloadId;
}

function quoteProvenance(quote: AuthorizedResearchQuoteV2, useId: string): ResearchQuoteProvenanceV2 {
  return {
    researchProjectId: quote.researchProjectId,
    researchQuoteId: quote.researchQuoteId,
    researchSourceId: quote.researchSourceId,
    useId,
  };
}

function setInsertedProvenance(
  row: NarrationBlockV2,
  createdTokenIds: readonly string[],
  quote: AuthorizedResearchQuoteV2,
  useId: string,
): string[] {
  const created = new Set(createdTokenIds);
  const inserted = row.tokens.filter((token) => created.has(token.id));
  inserted.forEach((token) => { token.researchQuoteProvenance = quoteProvenance(quote, useId); });
  return inserted.map((token) => token.id);
}

/**
 * Compose and preflight one row edit. Gap placement creates the fully assembled
 * narration row in one create_row command; other targets edit one existing row.
 */
export function prepareResearchQuotePlacementV2(
  document: ScriptDocumentV2,
  quote: AuthorizedResearchQuoteV2,
  background: ResearchQuoteBackgroundV2,
  request: ResearchQuotePlacementV2,
  makeId: () => string = randomUUID,
): PreparedResearchQuotePlacementV2 {
  if (!request || !quote || !safeText(quote.spokenText, true) ||
      (request.destination?.kind !== "selected_words" && /[[\]]/u.test(quote.spokenText)) ||
      !UUID.test(quote.researchQuoteId ?? "") || !UUID.test(quote.researchProjectId ?? "") ||
      !UUID.test(quote.researchSourceId ?? "") || !Number.isSafeInteger(quote.researchQuoteVersion) ||
      quote.researchQuoteVersion < 1 || !safeText(quote.displayText, true) ||
      !safeText(quote.speakerName, false) || !safeText(quote.speakerTitle, false) ||
      !safeText(quote.citationText, false) || !safeText(quote.templateRevision, true) ||
      (quote.citationOverridden !== undefined && quote.citationOverridden !== true) ||
      !validBackground(background, quote)) {
    return refusal("RESEARCH_QUOTE_INVALID", "Provide a current authorized quote and its resolved picture or missing-picture choice.");
  }
  if (!Number.isSafeInteger(request.expectedDocumentRevision) ||
      request.expectedDocumentRevision !== (document.rowEditRevision ?? 0) ||
      request.expectedDocumentRevision === Number.MAX_SAFE_INTEGER) {
    return refusal("ROW_REVISION_STALE", "The script changed before quote placement.");
  }

  const destination = request.destination;
  if (!destination || (destination.kind !== "gap" && destination.kind !== "insert" && destination.kind !== "selected_words")) {
    return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "Choose an exact word gap, row gap, or spoken word range.");
  }
  if (destination.kind === "gap" && !validGap(destination)) {
    return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "Choose a current script row gap.");
  }

  const ids = reservedIds(background, reservedIds(quote, reservedIds(document)));
  const nextId = (): string => {
    const id = makeId();
    if (typeof id !== "string" || !UUID.test(id) || ids.has(id.toLowerCase())) {
      throw new RangeError("A quote placement requires unused UUIDs.");
    }
    ids.add(id.toLowerCase());
    return id;
  };

  try {
    const useId = nextId();
    const insertedText = quoteForNarration(quote.spokenText);

    if (destination.kind === "gap") {
      const row = newNarrationRow(nextId(), nextId(), nextId());
      const splice = spliceNarrationTextV2(row, {
        startOffset: 0, endOffset: 0, insertedText, editId: nextId(),
      }, { documentId: document.id, revision: request.expectedDocumentRevision, reservedIds: ids });
      if (!splice.ok) return refusal(splice.code, splice.message);
      const insertedIds = setInsertedProvenance(splice.row, splice.createdTokenIds, quote, useId);
      if (insertedIds.length === 0 || insertedIds.some((id, index) =>
        splice.row.tokens.findIndex((token) => token.id === id) !== index)) {
        return refusal("RESEARCH_QUOTE_TEXT_INVALID", "The quote did not produce one contiguous spoken word range.");
      }
      const backgroundPayloadId = attachQuoteBackground(
        splice.row, background, null, insertedIds[0]!, insertedIds.at(-1)!, nextId,
      );
      if (!backgroundPayloadId) return refusal("RESEARCH_QUOTE_BACKGROUND_INVALID", "Cannot attach the quote background to its new narration row.");
      addQuoteOverlay(splice.row, quote, useId, backgroundPayloadId, insertedIds[0]!, insertedIds.at(-1)!, nextId);
      const gap: RowGapV2 = {
        sectionId: destination.sectionId,
        afterRowId: destination.afterRowId,
        beforeRowId: destination.beforeRowId,
      };
      const command: QuoteRowCommand = { kind: "create_row", row: splice.row, destination: gap };
      const checked = applyRowEditV2(document, request.expectedDocumentRevision, command);
      return checked.ok ? { ok: true, command, document: checked.document } :
        { ok: false, diagnostics: checked.diagnostics };
    }

    const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 =>
      block.id === request.rowId && block.type === "narration");
    if (!row || row.state !== "active" || row.plainDirection === true || !row.primaryVisualSequence ||
        !Number.isSafeInteger(request.expectedRowVersion) || row.version !== request.expectedRowVersion ||
        !Number.isSafeInteger(request.expectedSequenceVersion) ||
        row.primaryVisualSequence.version !== request.expectedSequenceVersion ||
        row.version === Number.MAX_SAFE_INTEGER || row.primaryVisualSequence.version === Number.MAX_SAFE_INTEGER) {
      return refusal("RESEARCH_QUOTE_SCOPE_STALE", "Choose a current spoken narration row and its exact visual-sequence revision.");
    }

    const words = spokenTokensV2(row);
    let edited = structuredClone(row);
    let startTokenId: string;
    let endTokenId: string;
    let previousTokenId: string | null = null;
    let gapContainsOnlyWhitespace = true;

    if (destination.kind === "selected_words") {
      const startIndex = words.findIndex((token) => token.id === destination.startTokenId);
      const endIndex = words.findIndex((token) => token.id === destination.endTokenId);
      if (startIndex < 0 || endIndex < startIndex) {
        return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "Choose an ordered range of current spoken words.");
      }
      startTokenId = words[startIndex]!.id;
      endTokenId = words[endIndex]!.id;
      previousTokenId = words[startIndex - 1]?.id ?? null;
      if (startIndex > 0) {
        gapContainsOnlyWhitespace = row.text.slice(words[startIndex - 1]!.endOffset, words[startIndex]!.startOffset).trim().length === 0;
      }
    } else {
      const beforeIndex = destination.beforeTokenId === null ? words.length :
        words.findIndex((token) => token.id === destination.beforeTokenId);
      if (beforeIndex < 0 || destination.beforeTokenId !== null && !UUID.test(destination.beforeTokenId)) {
        return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "The insertion word is no longer current.");
      }
      previousTokenId = words[beforeIndex - 1]?.id ?? null;
      const before = destination.beforeTokenId === null ? null : words[beforeIndex];
      const offset = before?.startOffset ?? row.text.length;
      const splice = spliceNarrationTextV2(row, {
        startOffset: offset, endOffset: offset,
        insertedText: `${offset > 0 && !/\s/u.test(row.text[offset - 1]!) ? " " : ""}${insertedText}${offset < row.text.length && !/\s/u.test(row.text[offset]!) ? " " : ""}`,
        editId: nextId(),
      }, { documentId: document.id, revision: request.expectedDocumentRevision, reservedIds: ids });
      if (!splice.ok) return refusal(splice.code, splice.message);
      const inserted = setInsertedProvenance(splice.row, splice.createdTokenIds, quote, useId);
      const firstIndex = splice.row.tokens.findIndex((token) => token.id === inserted[0]);
      if (inserted.length === 0 || inserted.some((id, index) => splice.row.tokens[firstIndex + index]?.id !== id) ||
          inserted.some((id) => splice.row.tokens.find((token) => token.id === id)?.spoken === false)) {
        return refusal("RESEARCH_QUOTE_TEXT_INVALID", "The quote did not produce a distinct, contiguous spoken word range.");
      }
      startTokenId = inserted[0]!;
      endTokenId = inserted.at(-1)!;
      edited = splice.row;
      if (previousTokenId) gapContainsOnlyWhitespace = row.text.slice(
        words[beforeIndex - 1]!.endOffset, offset,
      ).trim().length === 0;
    }

    edited.version = row.version + 1;
    const continuation = gapContainsOnlyWhitespace
      ? previousQuoteContinuation(row, previousTokenId, quote, background)
      : null;
    const backgroundPayloadId = attachQuoteBackground(
      edited, background, continuation, startTokenId, endTokenId, nextId,
    );
    if (!backgroundPayloadId) return refusal("RESEARCH_QUOTE_BACKGROUND_INVALID", "Cannot attach the quote background to its spoken words.");
    addQuoteOverlay(edited, quote, useId, backgroundPayloadId, startTokenId, endTokenId, nextId);

    const command: QuoteRowCommand = { kind: "edit_row", rowId: row.id, row: edited };
    const checked = applyRowEditV2(document, request.expectedDocumentRevision, command);
    return checked.ok ? { ok: true, command, document: checked.document } :
      { ok: false, diagnostics: checked.diagnostics };
  } catch (error) {
    return refusal("RESEARCH_QUOTE_INVALID", error instanceof Error ? error.message : "Cannot place the quote.");
  }
}

/** Convenience for callers without an edit session. Session callers apply the prepared command once. */
export function placeResearchQuoteV2(
  document: ScriptDocumentV2,
  quote: AuthorizedResearchQuoteV2,
  background: ResearchQuoteBackgroundV2,
  request: ResearchQuotePlacementV2,
  makeId: () => string = randomUUID,
): RowEditResultV2 {
  const prepared = prepareResearchQuotePlacementV2(document, quote, background, request, makeId);
  return prepared.ok ? { ok: true, document: prepared.document, diagnostics: [] } :
    { ok: false, document, diagnostics: prepared.diagnostics };
}
