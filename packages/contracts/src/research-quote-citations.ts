import type { QuoteBoxV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import { formatMlaCitation, type MlaSource } from "./mla-citation.js";

type Citation = Pick<QuoteBoxV2, "citationText" | "italicSpan">;

export interface ResearchQuoteCitationDetails {
  location?: string;
  citationOverride?: string;
}

function checkedCitationText(text: string): string {
  if (text.length > 20_000 || /[\0\p{Surrogate}]/u.test(text)) {
    throw new Error("Research citation text is invalid or too long.");
  }
  return text.trim();
}

export function activeResearchQuoteUses(document: ScriptDocumentV2) {
  return document.activeDraft.blocks.flatMap((block) => {
    if (block.type !== "narration" || block.state !== "active") return [];
    return block.overlayEvents.flatMap(({ id, quoteBox }) => quoteBox ? [{ id, quoteBox }] : []);
  });
}

/** Keep the original italic title when an editor changes the surrounding text. */
export function editCitationText(previous: Citation, text: string): Citation {
  const citationText = checkedCitationText(text);
  if (!previous.italicSpan) return { citationText, italicSpan: null };
  const { start, end } = previous.italicSpan;
  const before = [...previous.citationText.trim()];
  const after = [...citationText];
  if (start < 0 || start >= end || end > before.length) return { citationText, italicSpan: null };

  const unchangedThroughTitle = before.slice(0, end).join("");
  if (citationText.startsWith(unchangedThroughTitle)) {
    return { citationText, italicSpan: { start, end } };
  }
  const unchangedAfterTitleStart = before.slice(start).join("");
  if (citationText.endsWith(unchangedAfterTitleStart)) {
    const offset = after.length - before.length;
    return { citationText, italicSpan: { start: start + offset, end: end + offset } };
  }
  const title = before.slice(start, end).join("");
  const index = citationText.indexOf(title);
  if (index < 0 || index !== citationText.lastIndexOf(title)) return { citationText, italicSpan: null };
  const newStart = [...citationText.slice(0, index)].length;
  return { citationText, italicSpan: { start: newStart, end: newStart + end - start } };
}

/** Source authors are bibliography data, independent of the box's attribution. */
export function researchQuoteCitation(source: MlaSource, quote: ResearchQuoteCitationDetails): Citation {
  const generated = formatMlaCitation(source, quote.location === undefined ? {} : { location: quote.location });
  return quote.citationOverride === undefined ? generated : editCitationText(generated, quote.citationOverride);
}

function updateQuoteUses(
  document: ScriptDocumentV2,
  update: (box: QuoteBoxV2, eventId: string) => QuoteBoxV2,
): ScriptDocumentV2 {
  const blocks = document.activeDraft.blocks.map((block) => {
    if (block.type !== "narration" || block.state !== "active") return block;
    let changed = false;
    const overlayEvents = block.overlayEvents.map((event) => {
      if (!event.quoteBox) return event;
      const quoteBox = update(event.quoteBox, event.id);
      if (quoteBox === event.quoteBox) return event;
      changed = true;
      return { ...event, quoteBox, version: event.version + 1 };
    });
    // Citation edits leave the narration revision and its frozen timing valid.
    return changed ? { ...block, overlayEvents } : block;
  });
  if (blocks.every((block, index) => block === document.activeDraft.blocks[index])) return document;
  return { ...document, activeDraft: { ...document.activeDraft, blocks } };
}

export function refreshResearchQuoteCitations(
  document: ScriptDocumentV2,
  citations: ReadonlyMap<string, Citation>,
  legacyProjectId?: string,
): ScriptDocumentV2 {
  return updateQuoteUses(document, (box) => {
    const id = box.researchQuoteId.toLowerCase();
    const projectId = box.researchProjectId ?? legacyProjectId;
    const key = projectId ? `${projectId.toLowerCase()}\u0000${id}` : id;
    const citation = citations.get(key) ?? citations.get(id);
    if (!citation || box.citationOverridden || (
      box.citationText === citation.citationText &&
      box.italicSpan?.start === citation.italicSpan?.start && box.italicSpan?.end === citation.italicSpan?.end
    )) return box;
    return { ...box, ...citation };
  });
}

export function editResearchQuoteUseCitation(
  document: ScriptDocumentV2,
  overlayId: string,
  edit: { text: string } | { reset: Citation },
): ScriptDocumentV2 {
  let found = false;
  const edited = updateQuoteUses(document, (box, eventId) => {
    if (eventId !== overlayId) return box;
    found = true;
    if ("text" in edit) {
      const citation = editCitationText(box, edit.text);
      return { ...box, ...citation, citationOverridden: true };
    }
    const reset = { ...box, ...edit.reset };
    delete reset.citationOverridden;
    return reset;
  });
  if (!found) throw new Error("Research quote box ID must name a use in an active script row.");
  return edited;
}
