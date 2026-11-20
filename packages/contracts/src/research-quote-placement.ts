/** One saved row edit for an already-authorized Research quote. No fetching or UI authority lives here. */
import { randomUUID } from "node:crypto";

import type {
  NarratedVisualPayloadV2,
  NarrationBlockV2,
  QuoteBoxV2,
  ScriptDocumentV2,
} from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { isCoverageRefusalV2 } from "./authoring-v2-coverage.js";
import { spliceNarrationTextV2 } from "./authoring-v2-narration-text.js";
import { applyRowEditV2, type RowEditCommandV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { attachVisualToWordsV2 } from "./authoring-v2-visual-lifecycle.js";
import { retypeVisualPayloadV2 } from "./authoring-v2-visual-type.js";

type RowCommand = Extract<RowEditCommandV2, { kind: "edit_row" }>;
type VisualSource = NarratedVisualPayloadV2["source"];

/** The host has already authorized and resolved the quote. The box's fields remain editable per use. */
export type AuthorizedResearchQuoteV2 = Omit<QuoteBoxV2, "backgroundPayloadId"> & {
  /** Full words for an insertion; not substituted for the independently editable box display text. */
  spokenText: string;
};

/** Resolved, host-authorized picture only; a missing picture becomes the existing Need to Find card. */
export type ResearchQuoteBackgroundV2 =
  | { kind: "still_image"; source: Extract<VisualSource, { kind: "media_reference" }>; displayName?: string }
  | { kind: "web_capture"; source: Extract<VisualSource, { kind: "capture_revision" }> }
  | null;

export interface ResearchQuotePlacementV2 {
  expectedDocumentRevision: number;
  rowId: string;
  expectedRowVersion: number;
  expectedSequenceVersion: number;
  destination:
    | { kind: "insert"; beforeTokenId: string | null }
    | { kind: "selected_words"; startTokenId: string; endTokenId: string };
}

export type PreparedResearchQuotePlacementV2 =
  | { ok: true; command: RowCommand; document: ScriptDocumentV2 }
  | { ok: false; diagnostics: AuthoringDiagnosticV2[] };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

function refusal(code: string, message: string): PreparedResearchQuotePlacementV2 {
  return { ok: false, diagnostics: [{ code, message, jsonPath: "$", severity: "error" }] };
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

function validBackground(background: ResearchQuoteBackgroundV2): boolean {
  if (background === null) return true;
  if (!background || typeof background !== "object") return false;
  if (background.kind === "still_image") {
    return background.source?.kind === "media_reference" && UUID.test(background.source.mediaReferenceId) &&
      (background.displayName === undefined || safeText(background.displayName, false));
  }
  return background.kind === "web_capture" && background.source?.kind === "capture_revision" &&
    UUID.test(background.source.captureId) && UUID.test(background.source.revisionId);
}

/**
 * Compose and preflight one ordinary edit_row command. A row session can apply
 * the command once and record precisely one Undo entry; the preflight does not
 * mutate or revise the caller's document. No visual or text partial result is exposed.
 */
export function prepareResearchQuotePlacementV2(
  document: ScriptDocumentV2,
  quote: AuthorizedResearchQuoteV2,
  background: ResearchQuoteBackgroundV2,
  request: ResearchQuotePlacementV2,
  makeId: () => string = randomUUID,
): PreparedResearchQuotePlacementV2 {
  if (!request || !quote || !safeText(quote.spokenText, true) ||
      (quote.spokenText.includes("[") || quote.spokenText.includes("]")) || !UUID.test(quote.researchQuoteId ?? "") ||
      !safeText(quote.displayText, true) || !safeText(quote.speakerName, false) ||
      !safeText(quote.speakerTitle, false) || !safeText(quote.citationText, false) ||
      !safeText(quote.templateRevision, true) ||
      (quote.citationOverridden !== undefined && quote.citationOverridden !== true) ||
      !validBackground(background)) {
    return refusal("RESEARCH_QUOTE_INVALID", "Provide an authorized quote and a resolved picture or a missing-picture choice.");
  }
  if (!Number.isSafeInteger(request.expectedDocumentRevision) ||
      request.expectedDocumentRevision !== (document.rowEditRevision ?? 0) ||
      request.expectedDocumentRevision === Number.MAX_SAFE_INTEGER) {
    return refusal("ROW_REVISION_STALE", "The script changed before quote placement.");
  }
  const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 =>
    block.id === request.rowId && block.type === "narration");
  if (!row || row.state !== "active" || row.plainDirection === true || !row.primaryVisualSequence ||
      row.version !== request.expectedRowVersion ||
      row.primaryVisualSequence.version !== request.expectedSequenceVersion ||
      !Number.isSafeInteger(row.version) || row.version === Number.MAX_SAFE_INTEGER ||
      !Number.isSafeInteger(row.primaryVisualSequence.version) ||
      row.primaryVisualSequence.version === Number.MAX_SAFE_INTEGER) {
    return refusal("RESEARCH_QUOTE_SCOPE_STALE", "Choose a current spoken narration row and its exact visual-sequence revision.");
  }

  const destination = request.destination;
  const words = spokenTokensV2(row);
  if (!destination || (destination.kind !== "insert" && destination.kind !== "selected_words")) {
    return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "Choose an exact word gap or spoken word range.");
  }
  let edited = structuredClone(row);
  let startTokenId: string;
  let endTokenId: string;
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
    if (destination.kind === "selected_words") {
      const startIndex = words.findIndex((token) => token.id === destination.startTokenId);
      const endIndex = words.findIndex((token) => token.id === destination.endTokenId);
      if (startIndex < 0 || endIndex < startIndex) {
        return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "Choose an ordered range of current spoken words.");
      }
      startTokenId = words[startIndex]!.id;
      endTokenId = words[endIndex]!.id;
    } else {
      const before = destination.beforeTokenId === null ? null :
        words.find((token) => token.id === destination.beforeTokenId);
      if (destination.beforeTokenId !== null && !before) {
        return refusal("RESEARCH_QUOTE_ANCHOR_INVALID", "The insertion word is no longer current.");
      }
      const offset = before?.startOffset ?? row.text.length;
      const insertedText = `${offset > 0 && !/\s/u.test(row.text[offset - 1]!) ? " " : ""}${quote.spokenText.trim()}${offset < row.text.length && !/\s/u.test(row.text[offset]!) ? " " : ""}`;
      const splice = spliceNarrationTextV2(row, {
        startOffset: offset, endOffset: offset, insertedText, editId: nextId(),
      }, { documentId: document.id, revision: request.expectedDocumentRevision, reservedIds: ids });
      if (!splice.ok) return refusal(splice.code, splice.message);
      const inserted = splice.row.tokens.filter((token) => splice.createdTokenIds.includes(token.id));
      const firstIndex = splice.row.tokens.findIndex((token) => token.id === inserted[0]?.id);
      if (inserted.length === 0 || inserted.some((token) => token.spoken === false) ||
          inserted.some((token, index) => splice.row.tokens[firstIndex + index]?.id !== token.id)) {
        return refusal("RESEARCH_QUOTE_TEXT_INVALID", "The quote did not produce a distinct, contiguous spoken word range.");
      }
      edited = splice.row;
      startTokenId = inserted[0]!.id;
      endTokenId = inserted[inserted.length - 1]!.id;
    }

    const backgroundPayloadId = nextId();
    const slotId = nextId();
    let backgroundPayload: NarratedVisualPayloadV2;
    if (background === null) {
      const missing = retypeVisualPayloadV2(
        { kind: "undefined", payloadId: backgroundPayloadId, description: "Research quote picture not selected." },
        { type: "need_to_find", description: "Find a picture for this Research quote." },
      );
      if (!missing.ok || missing.payload.kind !== "visual") return refusal("RESEARCH_QUOTE_BACKGROUND_INVALID", "Cannot create a Need to Find background.");
      backgroundPayload = missing.payload;
    } else {
      backgroundPayload = {
        kind: "visual", payloadId: backgroundPayloadId,
        pictureKind: background.kind === "still_image" ? "image" : "capture",
        source: structuredClone(background.source), sourceUsage: null, audioPolicy: "mute",
        ...(background.kind === "web_capture" ? { framingPolicy: "contain" as const } : {}),
        ...(background.kind === "still_image" && background.displayName ? { displayName: background.displayName } : {}),
      };
    }

    edited.version = row.version + 1;
    edited.unattachedVisuals = [...(edited.unattachedVisuals ?? []), { slotId, payload: backgroundPayload, version: 1 }];
    const attached = attachVisualToWordsV2(edited, slotId, startTokenId, endTokenId);
    if (isCoverageRefusalV2(attached)) return refusal(attached.code, attached.message);

    const startWord = edited.tokens.find((token) => token.id === startTokenId)!;
    const endWord = edited.tokens.find((token) => token.id === endTokenId)!;
    const graphicPayloadId = nextId();
    const graphicId = nextId();
    const graphicRevisionId = nextId();
    const box: QuoteBoxV2 = {
      researchQuoteId: quote.researchQuoteId,
      displayText: quote.displayText,
      speakerName: quote.speakerName,
      speakerTitle: quote.speakerTitle,
      citationText: quote.citationText,
      italicSpan: structuredClone(quote.italicSpan),
      templateRevision: quote.templateRevision,
      backgroundPayloadId,
      ...(quote.citationOverridden ? { citationOverridden: true as const } : {}),
    };
    edited.overlayEvents.push({
      id: nextId(), version: 1,
      payload: {
        kind: "visual", payloadId: graphicPayloadId, pictureKind: "graphic",
        source: { kind: "graphic_revision", graphicId, revisionId: graphicRevisionId },
        sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
      },
      timing: {
        kind: "timed",
        start: { kind: "word", anchor: {
          blockId: row.id, tokenId: startTokenId, quotedWord: startWord.value,
          affinity: "before", anchorVersion: edited.version,
        } },
        end: { kind: "audible_word_end", anchor: {
          blockId: row.id, tokenId: endTokenId, quotedWord: endWord.value,
          affinity: "after", anchorVersion: edited.version,
        } },
      },
      quoteBox: box,
    });

    const command: RowCommand = { kind: "edit_row", rowId: row.id, row: edited };
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
