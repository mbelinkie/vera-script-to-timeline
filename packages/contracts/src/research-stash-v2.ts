/** Compact Research occurrences are saved independently of row/footage ownership. */
import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { applyRowEditV2, serializeAuthoringDocumentV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { placeResearchQuoteV2, type ResearchQuotePlacementV2 } from "./research-quote-placement.js";
import { insertResearchStillBrowserV2, type ResearchStillBrowserInsertV2 } from "./research-still-browser-insert.js";
import { readKeptOriginalAsset, readKeptStillProvenance } from "./research-still-records.js";
import { liftVisualV2 } from "./authoring-v2-visual-lifecycle.js";
import { isCoverageRefusalV2 } from "./authoring-v2-coverage.js";

export type StashResearchItemV2 = NonNullable<ScriptDocumentV2["stashResearchItems"]>[number];

export type ResearchStashLocationV2 = Pick<StashResearchItemV2, "sectionId" | "noteRowId">;

export type ResearchStashCommandV2 =
  | { kind: "move_stash_research_item"; itemId: string; sectionId: string | null; noteRowId: string | null; afterItemId: string | null }
  | { kind: "delete_stash_research_item"; itemId: string };

const uuid = (value: unknown): value is string => typeof value === "string" &&
  /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu.test(value);

export function isResearchStashCommandV2(value: unknown): value is ResearchStashCommandV2 {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const command = value as Record<string, unknown>;
  const keys = Object.keys(command);
  if (!uuid(command.itemId)) return false;
  if (command.kind === "delete_stash_research_item") return keys.length === 2;
  return command.kind === "move_stash_research_item" && keys.length === 5 &&
    [command.sectionId, command.noteRowId, command.afterItemId].every((id) => id === null || uuid(id));
}

function noteEntry(document: ScriptDocumentV2, noteRowId: string) {
  const row = document.stash?.flatMap((bundle) => bundle.rows).find((row) => row.id === noteRowId);
  return row?.type === "narration"
    ? document.stashOutline?.find((entry) => entry.rowId === noteRowId && entry.kind === "note") : undefined;
}

function sectionExists(document: ScriptDocumentV2, sectionId: string | null): boolean {
  return sectionId === null || !!document.stashSections?.some((section) => section.id === sectionId);
}

function sameLocation(left: ResearchStashLocationV2, right: ResearchStashLocationV2): boolean {
  return left.sectionId === right.sectionId && left.noteRowId === right.noteRowId;
}

export function researchStashLocationProblemV2(document: ScriptDocumentV2, item: ResearchStashLocationV2): string | null {
  if (!sectionExists(document, item.sectionId)) return "Choose an existing Stash section.";
  if (item.noteRowId !== null) {
    const entry = noteEntry(document, item.noteRowId);
    if (!entry || entry.sectionId !== item.sectionId) return "An attached Research item needs a saved note in its own section.";
  }
  return null;
}

const safeText = (text: string, required = false): boolean =>
  text.length <= 20_000 && !/[\0\p{Surrogate}]/u.test(text) && (!required || !!text.trim());

/** Called after strict schema validation: no invented audio shape or live catalog access. */
export function researchStashSnapshotProblemV2(item: StashResearchItemV2): string | null {
  if (item.kind === "quote") {
    const q = item.quote;
    if (!safeText(q.spokenText, true) || !safeText(q.displayText, true) || !safeText(q.speakerName) ||
      !safeText(q.speakerTitle) || !safeText(q.citationText) || !safeText(q.templateRevision, true)) {
      return "The saved quote must retain complete, bounded text and template metadata.";
    }
    if (q.italicSpan && (q.italicSpan.start >= q.italicSpan.end ||
        q.italicSpan.end > [...q.citationText.trim()].length)) return "The quote's italic range must be within its citation.";
    if (item.background) {
      const { picture, displayName } = item.background;
      if (picture.researchProjectId.toLowerCase() !== q.researchProjectId.toLowerCase() ||
          picture.ownerKind === "quote" && picture.ownerId.toLowerCase() !== q.researchQuoteId.toLowerCase() ||
          picture.ownerKind === "source" && picture.ownerId.toLowerCase() !== q.researchSourceId.toLowerCase() ||
          displayName !== undefined && !safeText(displayName)) return "The kept picture must belong to this quote or source.";
      try { readKeptOriginalAsset(picture.original); } catch { return "The quote picture pin is invalid."; }
    }
  } else {
    const s = item.still;
    if (!safeText(s.title, true) || [s.credit, s.licence, s.usageNote, s.provenance.altText].some(
      (text) => text !== undefined && !safeText(text))) return "The still must retain bounded saved metadata.";
    try {
      readKeptOriginalAsset(s.original);
      readKeptStillProvenance(s.provenance);
    } catch { return "The kept still pin or provenance is invalid."; }
  }
  return null;
}

const problem = (message: string): AuthoringDiagnosticV2 => ({
  code: "RESEARCH_STASH_INVALID", message, jsonPath: "/stashResearchItems",
});

function insertAtLocation(items: StashResearchItemV2[], item: StashResearchItemV2, afterItemId: string | null): boolean {
  const index = afterItemId === null
    ? items.findIndex((candidate) => sameLocation(candidate, item))
    : items.findIndex((candidate) => candidate.id === afterItemId && sameLocation(candidate, item));
  if (afterItemId !== null && index < 0) return false;
  items.splice(index < 0 ? items.length : index + (afterItemId === null ? 0 : 1), 0, item);
  return true;
}

/** An ordinary row operation may move the owner, but cannot discard or detach it implicitly. */
export function reconcileResearchStashLocationsV2(document: ScriptDocumentV2): string | null {
  for (const item of document.stashResearchItems ?? []) {
    if (item.noteRowId !== null) {
      const owner = noteEntry(document, item.noteRowId);
      if (!owner) return "Detach saved Research items before removing their Stash note.";
      item.sectionId = owner.sectionId;
    } else if (!sectionExists(document, item.sectionId)) item.sectionId = null;
  }
  return null;
}

/** Internal mutation of a row-edit working copy; the caller owns revision and validation. */
export function editResearchStashItemsV2(document: ScriptDocumentV2, command: ResearchStashCommandV2): string | null {
  const items = document.stashResearchItems ?? [];
  const index = items.findIndex((item) => item.id === command.itemId);
  if (index < 0) return "Choose an existing saved Research occurrence.";
  const [item] = items.splice(index, 1);
  if (command.kind === "move_stash_research_item") {
    const moved = { ...item!, sectionId: command.sectionId, noteRowId: command.noteRowId };
    const error = researchStashLocationProblemV2(document, moved);
    if (error) return error;
    if (!insertAtLocation(items, moved, command.afterItemId)) return "Choose a current Research item in the same Stash location.";
  }
  if (items.length === 0) delete document.stashResearchItems;
  return null;
}

/** Host-only acquisition: caller resolves and authorizes the frozen snapshot. No generic row command accepts it. */
export function captureResearchStashItemV2(
  document: ScriptDocumentV2,
  expectedRevision: number,
  item: StashResearchItemV2,
  afterItemId?: string | null,
): RowEditResultV2 {
  const refuse = (message: string): RowEditResultV2 => ({ ok: false, document, diagnostics: [problem(message)] });
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) ||
      expectedRevision === Number.MAX_SAFE_INTEGER) return {
    ok: false, document, diagnostics: [{ code: "ROW_REVISION_STALE", message: "The script changed before Stash capture.", jsonPath: "/stashResearchItems" }],
  };
  try {
    // Reuse the canonical saved JSON boundary for legacy as well as new records.
    const working = JSON.parse(serializeAuthoringDocumentV2(document)) as ScriptDocumentV2;
    if (!uuid(item.id)) return refuse("Use a new Research occurrence ID.");
    const occupied = (value: unknown): boolean => typeof value === "string" ? value.toLowerCase() === item.id.toLowerCase() :
      !!value && typeof value === "object" && Object.values(value).some(occupied);
    if (occupied(document) || occupied(Object.fromEntries(Object.entries(item).filter(([key]) => key !== "id")))) {
      return refuse("Use a new Research occurrence ID.");
    }
    const items = working.stashResearchItems ??= [];
    const error = researchStashLocationProblemV2(working, item);
    if (error) return refuse(error);
    if (afterItemId === undefined) items.push(structuredClone(item));
    else if (!insertAtLocation(items, structuredClone(item), afterItemId)) return refuse("Choose a current Research item in the same Stash location.");
    working.rowEditRevision = expectedRevision + 1;
    const saved = JSON.parse(serializeAuthoringDocumentV2(working)) as ScriptDocumentV2;
    return { ok: true, document: saved, diagnostics: [] };
  } catch {
    return refuse("The Research occurrence must be losslessly representable as valid saved JSON.");
  }
}

export type ResearchStashDraftTargetV2 =
  | { kind: "quote"; request: ResearchQuotePlacementV2 }
  | { kind: "still"; placement: ResearchStillBrowserInsertV2["placement"]; expectedDocumentRevision: number };

function refuseResearchStash(document: ScriptDocumentV2, message: string): RowEditResultV2 {
  return { ok: false, document, diagnostics: [problem(message)] };
}

/** The host has checked the saved source. Keep the occurrence reserved until placement succeeds. */
export function consumeResearchStashItemV2(
  document: ScriptDocumentV2, itemId: string, target: ResearchStashDraftTargetV2,
): RowEditResultV2 {
  const items = document.stashResearchItems?.filter((item) => item.id === itemId) ?? [];
  if (items.length !== 1) return refuseResearchStash(document, "Choose one current saved Research occurrence.");
  const item = items[0]!;
  const result = item.kind === "quote" && target.kind === "quote"
    ? placeResearchQuoteV2(document, item.quote, item.background, target.request)
    : item.kind === "still" && target.kind === "still"
      ? insertResearchStillBrowserV2(document, item.still, {
        expectedDocumentRevision: target.expectedDocumentRevision, researchProjectId: item.still.researchProjectId,
        itemId: item.still.itemId, itemVersion: item.still.itemVersion, placement: target.placement,
      })
      : refuseResearchStash(document, "Choose a destination for this saved Research item kind.");
  if (!result.ok) return { ...result, document };
  if (result.document.rowEditRevision !== (document.rowEditRevision ?? 0) + 1 ||
      JSON.stringify(result.document.stashResearchItems) !== JSON.stringify(document.stashResearchItems)) {
    return refuseResearchStash(document, "The Research placement did not preserve the saved occurrences.");
  }
  const working = structuredClone(result.document);
  working.stashResearchItems = working.stashResearchItems!.filter((candidate) => candidate.id !== itemId);
  if (!working.stashResearchItems.length) delete working.stashResearchItems;
  try {
    return { ...result, document: JSON.parse(serializeAuthoringDocumentV2(working)) as ScriptDocumentV2 };
  } catch {
    return refuseResearchStash(document, "The Research placement could not be saved atomically.");
  }
}

export interface ResearchQuoteBoxCaptureV2 {
  expectedDocumentRevision: number;
  rowId: string;
  expectedRowVersion: number;
  overlayId: string;
  expectedOverlayVersion: number;
}

/** Read the actual authored box, not an independently edited Library display. */
export function researchQuoteBoxForStashV2(document: ScriptDocumentV2, request: ResearchQuoteBoxCaptureV2) {
  const row = document.activeDraft.blocks.find(({ id }) => id === request.rowId);
  if (row?.type !== "narration" || row.state !== "active" || row.version !== request.expectedRowVersion) return null;
  const event = row.overlayEvents.find(({ id }) => id === request.overlayId);
  const box = event?.quoteBox;
  if (!event || !box?.researchProjectId || !box.researchSourceId || !box.researchQuoteVersion ||
      event.version !== request.expectedOverlayVersion) return null;
  const payloads = [
    ...(row.primaryVisualSequence?.slots ?? []).flatMap((slot) => slot.kind === "content" ? [slot.payload] : []),
    ...(row.unattachedVisuals ?? []).map(({ payload }) => payload),
  ];
  const payload = payloads.find((candidate) => "payloadId" in candidate && candidate.payloadId === box.backgroundPayloadId);
  const background = payload?.kind === "visual" && payload.researchQuotePicture
    ? { kind: "still_image" as const, picture: payload.researchQuotePicture,
      ...(payload.displayName ? { displayName: payload.displayName } : {}) } : null;
  // Only the exact contiguous words attributed to this use can recover an
  // inserted quote independently of a newer Library version or display edit.
  const attributed = row.tokens.filter((token) => box.researchQuoteUseId &&
    token.researchQuoteProvenance?.useId === box.researchQuoteUseId);
  const first = attributed[0];
  const last = attributed.at(-1);
  let spokenText: string | null = null;
  const firstIndex = first ? row.tokens.indexOf(first) : -1;
  if (first && last && attributed.every((token, index) => row.tokens[firstIndex + index] === token)) {
    const text = row.text.slice(first.startOffset, last.endOffset);
    if ((text.startsWith("“") && text.endsWith("”")) || (text.startsWith('"') && text.endsWith('"'))) {
      spokenText = text.slice(1, -1);
    }
  }
  return { row, event, box, background, spokenText };
}

/** Capture the overlay and retire only its unshared generated missing-picture placeholder. */
export function captureResearchQuoteBoxV2(
  document: ScriptDocumentV2, request: ResearchQuoteBoxCaptureV2, location: ResearchStashLocationV2,
  itemId: string, spokenText: string | null, afterItemId: string | null,
): RowEditResultV2 {
  const source = researchQuoteBoxForStashV2(document, request);
  if (!source) return refuseResearchStash(document, "The quote box changed before Stash capture.");
  const { row, event, box, background } = source;
  const frozenSpokenText = source.spokenText ?? spokenText;
  if (!frozenSpokenText) return refuseResearchStash(document, "The original quote wording is unavailable. Keep the quote box until its wording can be verified.");
  const editedRow = structuredClone(row);
  editedRow.overlayEvents = editedRow.overlayEvents.filter(({ id }) => id !== event.id);
  // A real or author-replaced background is an independent visual. Only the
  // automatically generated, no-longer-shared Need to Find is retired, since
  // its quote-specific build-slate exception disappears with the overlay.
  if (!editedRow.overlayEvents.some(({ quoteBox }) => quoteBox?.backgroundPayloadId === box.backgroundPayloadId)) {
    const slot = editedRow.primaryVisualSequence?.slots.find((candidate) =>
      candidate.kind === "content" && candidate.payload.kind === "visual" &&
      candidate.payload.payloadId === box.backgroundPayloadId);
    const waiting = editedRow.unattachedVisuals?.find(({ payload }) => payload.kind === "visual" &&
      payload.payloadId === box.backgroundPayloadId);
    const payload = slot?.kind === "content" ? slot.payload : waiting?.payload;
    if (payload?.kind === "visual" && payload.pictureKind === "unresolved_visual" &&
        payload.source.kind === "unresolved_visual" && payload.source.description === "Find a picture for this Research quote." &&
        !payload.source.wantedPictureKind) {
      const removed = liftVisualV2(editedRow, slot?.id ?? waiting!.slotId, "stashed");
      if (isCoverageRefusalV2(removed)) return refuseResearchStash(document, removed.message);
    }
  }
  const fields = {
    researchQuoteId: box.researchQuoteId, displayText: box.displayText,
    speakerName: box.speakerName, speakerTitle: box.speakerTitle,
    citationText: box.citationText, italicSpan: box.italicSpan, templateRevision: box.templateRevision,
    ...(box.citationOverridden ? { citationOverridden: true as const } : {}),
  };
  const captured = captureResearchStashItemV2(document, request.expectedDocumentRevision, {
    ...location, id: itemId, kind: "quote", background,
    quote: { ...fields, researchProjectId: box.researchProjectId!, researchSourceId: box.researchSourceId!,
      researchQuoteVersion: box.researchQuoteVersion!, spokenText: frozenSpokenText },
  }, afterItemId);
  if (!captured.ok) return captured;
  // The private intermediate is never published. The ordinary row edit owns the sole revision advance.
  captured.document.rowEditRevision = request.expectedDocumentRevision;
  const edited = applyRowEditV2(captured.document, request.expectedDocumentRevision, {
    kind: "edit_row", rowId: row.id, row: editedRow,
  });
  return edited.ok ? edited : { ...edited, document };
}
