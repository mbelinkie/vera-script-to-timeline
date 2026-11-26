import { createHmac, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { readFile } from "node:fs/promises";
import {
  applyRowEditV2, captureResearchStashItemV2, captureResearchQuoteBoxV2, consumeResearchStashItemV2, researchQuoteBoxForStashV2, applyVisualSequenceEditV2, createRowEditSessionV2, createSortingTrialV2,
  LEGACY_VISUAL_HOLD_MS, placeResearchQuoteV2, projectPrimarySequenceV2, spokenTokensV2, validateScriptDocumentV2,
  type ResearchQuoteBoxCaptureV2, type ResearchStashLocationV2, type ResearchQuotePlacementV2, type RowEditCommandV2, type RowEditResultV2, type VisualSequenceEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type { ResearchQuotePictureV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "@vera/contracts/v2";
import { EV24_QUOTE_BOX_TEMPLATE_REVISION } from "@vera/contracts/compiler-core-v2";
import { editCitationText } from "@vera/contracts/research-quote-citations";
import { prepareSavedPrompter } from "./prompter-authoring.js";
import {
  publicResearchQuote, ResearchReadError, type createResearchClient, type ResearchQuoteRecord,
} from "@vera/contracts/research-clip-client";
import {
  insertResearchClipBrowserV2, type ResearchClipBrowserInsertV2,
} from "@vera/contracts/research-clip-browser-insert";
import {
  insertResearchStillBrowserV2, type ResearchStillBrowserInsertV2,
} from "@vera/contracts/research-still-browser-insert";
import { ProjectAuthError } from "@vera/project-authorization";

export const DEFAULT_AUTHORING_PORT = "38429";

const ASSETS = new Map<string, readonly [string, string]>([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/authoring.css", ["authoring.css", "text/css; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/stash-actions.js", ["stash-actions.js", "text/javascript; charset=utf-8"]],
  ["/stash-panel.js", ["stash-panel.js", "text/javascript; charset=utf-8"]],
  ["/stash-row-editor.js", ["stash-row-editor.js", "text/javascript; charset=utf-8"]],
  ["/stash-row-editor.css", ["stash-row-editor.css", "text/css; charset=utf-8"]],
  ["/research-panel.js", ["research-panel.js", "text/javascript; charset=utf-8"]],
  ["/research-still-panel.js", ["research-still-panel.js", "text/javascript; charset=utf-8"]],
  ["/footage-player.js", ["footage-player.js", "text/javascript; charset=utf-8"]],
  ["/research-search.js", ["research-search.js", "text/javascript; charset=utf-8"]],
  ["/view.js", ["view.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.js", ["rows-editor.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.css", ["rows-editor.css", "text/css; charset=utf-8"]],
  ["/narration-editor.js", ["narration-editor.js", "text/javascript; charset=utf-8"]],
  ["/range-proposal.js", ["range-proposal.js", "text/javascript; charset=utf-8"]],
  ["/narration-editor.css", ["narration-editor.css", "text/css; charset=utf-8"]],
  ["/visual-selection.js", ["visual-selection.js", "text/javascript; charset=utf-8"]],
  ["/visual-only-actions.js", ["visual-only-actions.js", "text/javascript; charset=utf-8"]],
]);
const PROJECT = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(\/document)?$/u;
const VISUAL_HOLD_DEFAULT = /^\/projects\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/visual-hold-default$/u;
const EXTRAS = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/document\/extras-operations$/u;
const RESEARCH = /^\/research\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/projects(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/clips(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}))?)?$/iu;
const RESEARCH_STILLS = /^\/research\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/projects\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/stills(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/thumbnail)?$/iu;
const RESEARCH_QUOTES = /^\/research\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/projects\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/quotes(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/thumbnail)?$/iu;
const MUSIC_WARNINGS = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/music-warnings$/u;
const RESEARCH_QUOTE_PICTURE = /^\/research\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/quote-pictures\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$/iu;
const PROMPTER_EXPORT = /^\/projects\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/prompter-export$/u;
const SORTING_TRIAL = /^\/projects\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/sorting-trial$/u;
const SAVED_DIGEST = /^sha256:[0-9a-f]{64}$/u;
const PROOF = /^[0-9a-f]{64}$/u;
const RESEARCH_INSERT = "/research-insert";
// #66 is allowed to change ranges and OC framing, not to create/move/delete
// pictures. Other visual operations belong to separate browser stories.
const AUTHORING_VISUAL_KINDS = new Set<VisualSequenceEditCommandV2["kind"]>([
  "set_visual_range", "swap_ranges", "set_on_camera_framing",
]);

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function id(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 256;
}

function uuid(value: unknown): value is string {
  return typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(value);
}

function revision(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function quoteText(value: unknown): value is string {
  return typeof value === "string" && value.length <= 20_000 && !/[\0\p{Surrogate}]/u.test(value);
}

function quotePlacementRequest(value: unknown) {
  if (!record(value) || !exact(value, ["timelineProjectId", "document", "researchProjectId", "quoteId", "quoteVersion",
    "expectedDocumentRevision", "placement"]) || !uuid(value.timelineProjectId) || !uuid(value.researchProjectId) ||
      !uuid(value.quoteId) || !revision(value.quoteVersion) || value.quoteVersion < 1 ||
      !revision(value.expectedDocumentRevision) || !validateScriptDocumentV2(value.document).valid ||
      !record(value.placement)) return null;
  const document = value.document as ScriptDocumentV2;
  if (document.projectId?.toLowerCase() !== value.timelineProjectId.toLowerCase()) return null;
  const p = value.placement;
  const expectedDocumentRevision = value.expectedDocumentRevision;
  let request: ResearchQuotePlacementV2;
  if (p.kind === "gap") {
    const gap = p.destination;
    if (!exact(p, ["kind", "destination"]) || !record(gap) ||
        !exact(gap, ["sectionId", "afterRowId", "beforeRowId"]) ||
        ![gap.sectionId, gap.afterRowId, gap.beforeRowId].every((target) => target === null || uuid(target))) return null;
    request = { expectedDocumentRevision, destination: { kind: "gap",
      sectionId: gap.sectionId as string | null, afterRowId: gap.afterRowId as string | null,
      beforeRowId: gap.beforeRowId as string | null,
    } };
  } else {
    if (!uuid(p.rowId) || !revision(p.expectedRowVersion) || !revision(p.expectedSequenceVersion)) return null;
    const row = { expectedDocumentRevision, rowId: p.rowId,
      expectedRowVersion: p.expectedRowVersion, expectedSequenceVersion: p.expectedSequenceVersion };
    const keys = ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion"];
    if (p.kind === "insert" && exact(p, [...keys, "beforeTokenId"]) &&
        (p.beforeTokenId === null || uuid(p.beforeTokenId))) {
      request = { ...row, destination: { kind: "insert", beforeTokenId: p.beforeTokenId } };
    } else if (p.kind === "selected_words" && exact(p, [...keys, "startTokenId", "endTokenId"]) &&
        uuid(p.startTokenId) && uuid(p.endTokenId)) {
      request = { ...row, destination: { kind: "selected_words", startTokenId: p.startTokenId, endTokenId: p.endTokenId } };
    } else return null;
  }
  return { request, document, timelineProjectId: value.timelineProjectId.toLowerCase(),
    researchProjectId: value.researchProjectId.toLowerCase(), quoteId: value.quoteId.toLowerCase(),
    quoteVersion: value.quoteVersion };
}

function editQuoteBoxRequest(value: unknown) {
  if (!record(value) || !exact(value, ["document", "expectedDocumentRevision", "rowId", "expectedRowVersion",
    "overlayId", "expectedOverlayVersion", "edit"]) || !revision(value.expectedDocumentRevision) ||
      !uuid(value.rowId) || !uuid(value.overlayId) || !revision(value.expectedRowVersion) ||
      !revision(value.expectedOverlayVersion) || !record(value.edit) ||
      !validateScriptDocumentV2(value.document).valid) return null;
  const { edit } = value;
  let change: { displayText: string } | { citationText: string } | { delete: true } |
    { range: { startTokenId: string; endTokenId: string } };
  if (exact(edit, ["displayText"]) && quoteText(edit.displayText) && edit.displayText.trim()) {
    change = { displayText: edit.displayText };
  } else if (exact(edit, ["citationText"]) && quoteText(edit.citationText)) {
    change = { citationText: edit.citationText };
  } else if (exact(edit, ["delete"]) && edit.delete === true) {
    change = { delete: true };
  } else if (exact(edit, ["range"]) && record(edit.range) &&
      exact(edit.range, ["startTokenId", "endTokenId"]) &&
      uuid(edit.range.startTokenId) && uuid(edit.range.endTokenId)) {
    change = { range: { startTokenId: edit.range.startTokenId, endTokenId: edit.range.endTokenId } };
  } else return null;
  return { document: value.document as ScriptDocumentV2, expectedDocumentRevision: value.expectedDocumentRevision,
    rowId: value.rowId, expectedRowVersion: value.expectedRowVersion, overlayId: value.overlayId,
    expectedOverlayVersion: value.expectedOverlayVersion, edit: change };
}

/** Only Draft row moves belong to this browser trial. */
function sortingMove(value: unknown): value is Extract<RowEditCommandV2, { kind: "move_rows" }> {
  return record(value) && exact(value, ["kind", "rowIds", "destination"]) &&
    value.kind === "move_rows" && Array.isArray(value.rowIds) &&
    value.rowIds.length > 0 && value.rowIds.every(uuid) &&
    new Set(value.rowIds).size === value.rowIds.length &&
    record(value.destination) && exact(value.destination, ["sectionId", "afterRowId", "beforeRowId"]) &&
    Object.values(value.destination).every((item) => item === null || uuid(item));
}

type SortingOperation =
  | { kind: "command"; command: RowEditCommandV2 }
  | { kind: "visual"; command: VisualSequenceEditCommandV2; expectedSequenceVersion: number }
  | { kind: "undo" }
  | { kind: "batch"; operations: Array<Exclude<SortingOperation, { kind: "batch" | "undo" }>> };

function sortingOperation(value: unknown): SortingOperation | null {
  if (!record(value) || typeof value.kind !== "string") return null;
  if (value.kind === "undo") return exact(value, ["kind"]) ? { kind: "undo" } : null;
  if (value.kind === "command") {
    return exact(value, ["kind", "command"]) && record(value.command)
      ? { kind: "command", command: value.command as RowEditCommandV2 } : null;
  }
  if (value.kind === "visual") {
    if (!exact(value, ["kind", "command", "expectedSequenceVersion"]) ||
        !Number.isSafeInteger(value.expectedSequenceVersion) || (value.expectedSequenceVersion as number) < 0) return null;
    const command = visualCommand(value.command);
    return command ? { kind: "visual", command, expectedSequenceVersion: value.expectedSequenceVersion as number } : null;
  }
  if (value.kind === "batch") {
    if (!exact(value, ["kind", "operations"]) || !Array.isArray(value.operations) ||
        value.operations.length === 0 || value.operations.length > 1000) return null;
    const operations: Array<Exclude<SortingOperation, { kind: "batch" | "undo" }>> = [];
    for (const item of value.operations) {
      if (!record(item) || (item.kind !== "command" && item.kind !== "visual")) return null;
      const operation = sortingOperation(item);
      if (!operation || operation.kind === "batch" || operation.kind === "undo") return null;
      operations.push(operation);
    }
    return { kind: "batch", operations };
  }
  return null;
}

function researchReadNumber(params: URLSearchParams, thumbnail: boolean): number | null {
  if (!thumbnail && params.size === 0) return 0;
  const raw = params.get(thumbnail ? "version" : "offset");
  if (params.size !== 1 || raw === null || !/^\d+$/u.test(raw)) return null;
  const number = Number(raw);
  return Number.isSafeInteger(number) && (thumbnail ? number > 0 : number <= 100_000) ? number : null;
}

/** The exported script is confidential, including validation and denial responses. */
function prompterReply(body: unknown, status: number): Response {
  return Response.json(body, { status, headers: {
    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
  } });
}

/** Reject client-supplied Research records, frame bindings and arbitrary row commands. */
function researchInsertRequest(value: unknown): (ResearchClipBrowserInsertV2 & { timelineProjectId: string;
  document: ScriptDocumentV2 }) | null {
  if (!record(value) || !exact(value, ["timelineProjectId", "document", "researchProjectId", "clipId",
    "clipVersion", "expectedDocumentRevision", "placement"]) ||
    !uuid(value.timelineProjectId) || !uuid(value.researchProjectId) || !uuid(value.clipId) ||
    !Number.isSafeInteger(value.clipVersion) || (value.clipVersion as number) < 1 ||
    !Number.isSafeInteger(value.expectedDocumentRevision) || (value.expectedDocumentRevision as number) < 0 ||
    !validateScriptDocumentV2(value.document).valid ||
    (value.document as ScriptDocumentV2).projectId?.toLowerCase() !== value.timelineProjectId.toLowerCase() ||
    !record(value.placement)) return null;
  const placement = value.placement;
  if (placement.kind === "gap") {
    const destination = placement.destination;
    if (!exact(placement, ["kind", "destination"]) || !record(destination) ||
        !exact(destination, ["sectionId", "afterRowId", "beforeRowId"]) ||
        !["sectionId", "afterRowId", "beforeRowId"].every((key) =>
          destination[key] === null || uuid(destination[key]))) return null;
  } else if (placement.kind === "stash") {
    if (!exact(placement, ["kind", "sectionId", "noteRowId", "replace"]) ||
        !(placement.sectionId === null || uuid(placement.sectionId)) ||
        !(placement.noteRowId === null || uuid(placement.noteRowId)) ||
        typeof placement.replace !== "boolean") return null;
  } else if (placement.kind === "unattached" || placement.kind === "selected_words") {
    if (!exact(placement, placement.kind === "unattached"
      ? ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion"]
      : ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion", "startTokenId", "endTokenId"]) ||
      !uuid(placement.rowId) || !Number.isSafeInteger(placement.expectedRowVersion) ||
      (placement.expectedRowVersion as number) < 0 ||
      !Number.isSafeInteger(placement.expectedSequenceVersion) ||
      (placement.expectedSequenceVersion as number) < 0 ||
      (placement.kind === "selected_words" && (!uuid(placement.startTokenId) || !uuid(placement.endTokenId)))) return null;
  } else return null;
  return value as unknown as ResearchClipBrowserInsertV2 & {
    timelineProjectId: string; document: ScriptDocumentV2;
  };
}

function stillInsertRequest(value: unknown): (ResearchStillBrowserInsertV2 & {
  timelineProjectId: string; document: ScriptDocumentV2;
}) | null {
  if (!record(value) || !exact(value, ["timelineProjectId", "document", "researchProjectId", "itemId",
    "itemVersion", "expectedDocumentRevision", "placement"]) || !uuid(value.timelineProjectId) ||
    !uuid(value.researchProjectId) || !uuid(value.itemId) || !Number.isSafeInteger(value.itemVersion) ||
    (value.itemVersion as number) < 1 || !Number.isSafeInteger(value.expectedDocumentRevision) ||
    (value.expectedDocumentRevision as number) < 0 || !validateScriptDocumentV2(value.document).valid ||
    (value.document as ScriptDocumentV2).projectId?.toLowerCase() !== value.timelineProjectId.toLowerCase() ||
    !record(value.placement)) return null;
  const p = value.placement;
  if (!exact(p, ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion", "startTokenId", "endTokenId"]) ||
      p.kind !== "selected_words" || !uuid(p.rowId) || !uuid(p.startTokenId) || !uuid(p.endTokenId) ||
      !Number.isSafeInteger(p.expectedRowVersion) || (p.expectedRowVersion as number) < 0 ||
      !Number.isSafeInteger(p.expectedSequenceVersion) || (p.expectedSequenceVersion as number) < 0) return null;
  return value as unknown as NonNullable<ReturnType<typeof stillInsertRequest>>;
}

function researchStashRequest(value: unknown) {
  if (!record(value) || !uuid(value.timelineProjectId) || !revision(value.expectedDocumentRevision) ||
      !validateScriptDocumentV2(value.document).valid ||
      (value.document as ScriptDocumentV2).projectId?.toLowerCase() !== value.timelineProjectId.toLowerCase()) return null;
  const common = { timelineProjectId: value.timelineProjectId.toLowerCase(), document: value.document as ScriptDocumentV2,
    expectedDocumentRevision: value.expectedDocumentRevision };
  const keys = ["action", "timelineProjectId", "document", "expectedDocumentRevision"];
  if (value.action === "place") {
    if (!exact(value, [...keys, "itemId", "placement"]) || !uuid(value.itemId)) return null;
    const item = common.document.stashResearchItems?.find(({ id }) => id === value.itemId);
    if (!item) return null;
    if (item.kind === "quote") {
      const parsed = quotePlacementRequest({ ...common, researchProjectId: item.quote.researchProjectId,
        quoteId: item.quote.researchQuoteId, quoteVersion: item.quote.researchQuoteVersion, placement: value.placement });
      return parsed ? { ...common, action: "place" as const, item, target: { kind: "quote" as const, request: parsed.request } } : null;
    }
    const parsed = stillInsertRequest({ ...common, researchProjectId: item.still.researchProjectId,
      itemId: item.still.itemId, itemVersion: item.still.itemVersion, placement: value.placement });
    return parsed ? { ...common, action: "place" as const, item, target: { kind: "still" as const,
      placement: parsed.placement, expectedDocumentRevision: common.expectedDocumentRevision } } : null;
  }
  if (!record(value.location) || !exact(value.location, ["sectionId", "noteRowId", "afterItemId"]) ||
      ![value.location.sectionId, value.location.noteRowId, value.location.afterItemId].every((v) => v === null || uuid(v))) return null;
  const { sectionId, noteRowId, afterItemId } = value.location as ResearchStashLocationV2 & { afterItemId: string | null };
  const location = { sectionId, noteRowId };
  if (value.action === "capture_quote_box") {
    if (!exact(value, [...keys, "location", "rowId", "expectedRowVersion", "overlayId", "expectedOverlayVersion"]) ||
        !uuid(value.rowId) || !uuid(value.overlayId) || !revision(value.expectedRowVersion) || !revision(value.expectedOverlayVersion)) return null;
    const boxRequest: ResearchQuoteBoxCaptureV2 = { expectedDocumentRevision: common.expectedDocumentRevision,
      rowId: value.rowId, overlayId: value.overlayId, expectedRowVersion: value.expectedRowVersion, expectedOverlayVersion: value.expectedOverlayVersion };
    return { ...common, action: "capture_quote_box" as const, location, afterItemId, boxRequest };
  }
  if ((value.action !== "capture_quote" && value.action !== "capture_still") ||
      !exact(value, [...keys, "location", "researchProjectId", "itemId", "itemVersion"]) ||
      !uuid(value.researchProjectId) || !uuid(value.itemId) || !revision(value.itemVersion) || value.itemVersion < 1) return null;
  return { ...common, action: value.action === "capture_quote" ? "capture_quote" as const : "capture_still" as const, location, afterItemId, researchProjectId: value.researchProjectId.toLowerCase(),
    itemId: value.itemId.toLowerCase(), itemVersion: value.itemVersion };
}

const VISUAL_KINDS = new Set([
  "add_visual_on_selection", "change_visual_type", "delete_visual",
  "set_visual_range", "set_on_camera_framing", "move_visual_to_row", "attach_visual_to_words",
]);
const REVISIONED_ROW_KINDS = new Set([
  "add_visual_to_wordless_row", "move_wordless_visual", "reorder_visual_only", "set_visual_only_hold",
  "add_row_transition", "remove_row_transition",
]);

/** Only the commands this browser editor can issue, with exact JSON shapes. */
function visualCommand(value: unknown): VisualSequenceEditCommandV2 | null {
  if (!record(value) || !VISUAL_KINDS.has(String(value.kind)) || !id(value.blockId) || !id(value.slotId)) return null;
  switch (value.kind) {
    case "move_visual_to_row": {
      const keys = ["kind", "blockId", "slotId", "destinationBlockId"];
      if (Object.hasOwn(value, "expectedDestinationRowVersion")) keys.push("expectedDestinationRowVersion");
      if (!exact(value, keys) || !uuid(value.blockId) || !uuid(value.slotId) ||
          !uuid(value.destinationBlockId) ||
          (Object.hasOwn(value, "expectedDestinationRowVersion") &&
            (!Number.isSafeInteger(value.expectedDestinationRowVersion) ||
              (value.expectedDestinationRowVersion as number) < 0))) return null;
      break;
    }
    case "attach_visual_to_words":
      if (!exact(value, ["kind", "blockId", "slotId", "startTokenId", "endTokenId"]) ||
          !uuid(value.blockId) || !uuid(value.slotId) ||
          !uuid(value.startTokenId) || !uuid(value.endTokenId)) return null;
      break;
    case "add_visual_on_selection":
      if (!exact(value, ["kind", "blockId", "slotId", "payloadId", "startTokenId", "endTokenId", "visualType"]) ||
          !id(value.payloadId) || !id(value.startTokenId) || !id(value.endTokenId) ||
          !["onscreen_placeholder", "need_to_find", "visual_undefined"].includes(String(value.visualType))) return null;
      break;
    case "set_visual_range":
      if (!exact(value, ["kind", "blockId", "slotId", "startTokenId", "endTokenId"]) ||
          !id(value.startTokenId) || !id(value.endTokenId)) return null;
      break;
    case "set_on_camera_framing":
      if (!exact(value, ["kind", "blockId", "slotId", "framing"]) ||
          (value.framing !== "wide" && value.framing !== "tight")) return null;
      break;
    case "delete_visual":
      if (!exact(value, ["kind", "blockId", "slotId"])) return null;
      break;
    case "change_visual_type": {
      if (!exact(value, ["kind", "blockId", "slotId", "to"]) || !record(value.to)) return null;
      const to = value.to;
      if (to.type === "visual_undefined") {
        if (!exact(to, ["type"])) return null;
      } else if (to.type === "onscreen_placeholder" || to.type === "need_to_find") {
        const optional = to.type === "onscreen_placeholder" ? "text" : "description";
        if (!exact(to, Object.hasOwn(to, optional) ? ["type", optional] : ["type"]) ||
            (Object.hasOwn(to, optional) && (typeof to[optional] !== "string" || to[optional].length > 4096))) return null;
      } else return null; // Media-bearing type changes wait for the media-picker issues.
      break;
    }
  }
  return value as VisualSequenceEditCommandV2;
}

/** Only a legacy singleton with an implicit fixed hold uses the project setting. */
function usesProjectVisualHold(row: ScriptDocumentV2["activeDraft"]["blocks"][number] | undefined): row is VisualOnlyBlockV2 {
  return row?.type === "visual_only" && !row.additionalVisuals?.length &&
    row.payload.pictureKind !== "clip" && !row.visualOnlyTiming.selectedSourceRange &&
    !row.visualOnlyTiming.matchAudioDuration && row.visualOnlyTiming.durationOverrideMs === undefined;
}

/** Strictly bounded revisioned Draft operations; the model still owns all state changes/refusals. */
function revisionedRowCommand(value: unknown): RowEditCommandV2 | null {
  if (!record(value) || !REVISIONED_ROW_KINDS.has(String(value.kind))) return null;
  switch (value.kind) {
    case "add_row_transition":
    case "remove_row_transition":
      if (!exact(value, ["kind", "transitionId", "fromRowId", "toRowId", "expectedFromVersion", "expectedToVersion"]) ||
          !uuid(value.transitionId) || !uuid(value.fromRowId) || !uuid(value.toRowId) ||
          !Number.isSafeInteger(value.expectedFromVersion) || (value.expectedFromVersion as number) <= 0 ||
          !Number.isSafeInteger(value.expectedToVersion) || (value.expectedToVersion as number) <= 0) return null;
      break;
    case "add_visual_to_wordless_row":
      if (!exact(value, ["kind", "rowId", "payloadId", "slotId", "visualType"]) ||
          !uuid(value.rowId) || !uuid(value.payloadId) || !uuid(value.slotId) ||
          (value.visualType !== "onscreen_placeholder" && value.visualType !== "need_to_find")) return null;
      break;
    case "move_wordless_visual": {
      const keys = ["kind", "sourceRowId", "payloadId", "destinationRowId"];
      for (const optional of ["destinationSlotId", "replacementPayloadId", "expectedDestinationSequenceVersion"]) {
        if (Object.hasOwn(value, optional)) keys.push(optional);
      }
      if (!exact(value, keys) || !uuid(value.sourceRowId) || !uuid(value.payloadId) ||
          !uuid(value.destinationRowId) ||
          (Object.hasOwn(value, "destinationSlotId") && !uuid(value.destinationSlotId)) ||
          (Object.hasOwn(value, "replacementPayloadId") && !uuid(value.replacementPayloadId)) ||
          (Object.hasOwn(value, "expectedDestinationSequenceVersion") &&
            (!Number.isSafeInteger(value.expectedDestinationSequenceVersion) ||
              (value.expectedDestinationSequenceVersion as number) < 0))) return null;
      break;
    }
    case "reorder_visual_only":
      if (!exact(value, ["kind", "rowId", "payloadIds"]) || !uuid(value.rowId) ||
          !Array.isArray(value.payloadIds) || !value.payloadIds.every(uuid)) return null;
      break;
    case "set_visual_only_hold":
      if (!exact(value, ["kind", "rowId", "payloadId", "holdSeconds"]) ||
          !uuid(value.rowId) || !uuid(value.payloadId) ||
          typeof value.holdSeconds !== "number" || !Number.isFinite(value.holdSeconds)) return null;
      break;
  }
  return value as RowEditCommandV2;
}

function matchesProof(value: string | null | undefined, expected: Buffer): boolean {
  return !!value && PROOF.test(value) && timingSafeEqual(Buffer.from(value, "hex"), expected);
}

function quoteDefaultProof(authorization: string, encoded: string): Buffer {
  return createHmac("sha256", authorization).update("vera-quote-default-undo:").update(encoded).digest();
}

interface QuoteDefaultUndo {
  timelineProjectId: string;
  rowId: string;
  overlayId: string;
  researchProjectId: string;
  researchQuoteId: string;
  before: string;
  after: string;
  revision: number;
}

/** Host-only Research authority. No request transport or bearer reaches the browser. */
type ResearchClient = ReturnType<typeof createResearchClient>;
export type AuthoringResearchCatalog = Pick<ResearchClient, "projects" | "clips" | "clip"> &
  Partial<Pick<ResearchClient, "stills" | "still" | "stillThumbnail" | "quotes" | "quote" | "setQuoteDisplayText"> & {
    quotePicture(projectId: string, quote: ResearchQuoteRecord): Promise<ResearchQuotePictureV2 | null>;
    retainedQuotePicture(picture: ResearchQuotePictureV2): Promise<Uint8Array | null>;
    quoteThumbnail(projectId: string, quote: ResearchQuoteRecord): Promise<{
      bytes: Uint8Array; mimeType: ResearchQuotePictureV2["original"]["mimeType"];
    } | null>;
  }>;

/** Shared catalog conversion for Library insert and Stash capture. */
async function resolveResearchQuote(
  catalog: AuthoringResearchCatalog, researchProjectId: string, quoteId: string, quoteVersion: number,
) {
  if (!catalog.quote) throw new ResearchReadError(503, "Research quote unavailable.");
  const quote = await catalog.quote(researchProjectId, quoteId);
  if (quote.researchProjectId !== researchProjectId || quote.itemId !== quoteId || !uuid(quote.sourceId)) {
    throw new ResearchReadError(503, "Research quote identity mismatch.");
  }
  if (quote.itemVersion !== quoteVersion) throw new ResearchReadError(409, "Research quote changed.");
  let picture: ResearchQuotePictureV2 | null = null;
  try {
    picture = await catalog.quotePicture?.(researchProjectId, quote) ?? null;
  } catch (error) {
    if (error instanceof ResearchReadError && [401, 403].includes(error.status)) throw error;
    // An unverifiable or unavailable asset cannot become a saved pin.
  }
  if (picture && (picture.researchProjectId !== researchProjectId ||
      picture.ownerKind === "source" && picture.ownerId !== quote.sourceId ||
      picture.ownerKind === "quote" && picture.ownerId !== quoteId)) picture = null;
  return {
    quote: {
      researchQuoteId: quoteId, researchProjectId, researchSourceId: quote.sourceId,
      researchQuoteVersion: quoteVersion,
      spokenText: /[[\]]/u.test(quote.displayText) ? quote.text : quote.displayText,
      displayText: quote.displayText, speakerName: quote.speakerName ?? "", speakerTitle: quote.speakerTitle ?? "",
      citationText: quote.citationText, italicSpan: quote.italicSpan, templateRevision: EV24_QUOTE_BOX_TEMPLATE_REVISION,
      ...(quote.citationOverridden ? { citationOverridden: true as const } : {}),
    },
    background: picture ? { kind: "still_image" as const, picture,
      ...(quote.sourceTitle ? { displayName: quote.sourceTitle } : {}) } : null,
  };
}

export interface AuthoringResearchAccess {
  catalog: AuthoringResearchCatalog;
  /** A Research read needs view permission; a script insertion needs edit permission. */
  authorizeTimelineProject(projectId: string, action?: "view_document" | "edit_document"): Promise<void>;
}

const RESEARCH_HEADERS = {
  "Cache-Control": "no-store", "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
};

function researchResponse(status: number, body: unknown): Response {
  return Response.json(body, { status, headers: RESEARCH_HEADERS });
}

function researchStillError(error: unknown): Response {
  if (error instanceof ResearchReadError) {
    if (error.status === 404) return researchResponse(404, { error: "research_still_unavailable" });
    if (error.status === 409) return researchResponse(409, { error: "research_still_changed" });
    if (error.status === 422) return researchResponse(422, { error: "research_still_size_unsupported" });
    if (error.status === 401 || error.status === 403) {
      return researchResponse(403, { error: "research_project_forbidden" });
    }
  }
  return researchResponse(503, { error: "research_unavailable" });
}

function researchQuoteError(error: unknown): Response {
  if (error instanceof ResearchReadError) {
    if (error.status === 404) return researchResponse(404, { error: "research_quote_unavailable" });
    if (error.status === 409) return researchResponse(409, { error: "research_quote_changed" });
    if (error.status === 401 || error.status === 403) {
      return researchResponse(403, { error: "research_project_forbidden" });
    }
  }
  return researchResponse(503, { error: "research_unavailable" });
}

/** Project-scoped transcript DTO only: upstream extras never reach the browser. */
function publicResearchClip(candidate: Awaited<ReturnType<AuthoringResearchCatalog["clip"]>>) {
  const { id, projectId, catalogVideoId, version, createdBy, createdAt, updatedAt,
    englishText, originalText } = candidate;
  const { youtubeVideoId, canonicalUrl, title, channel, sourceLanguage } = candidate.video;
  const { trackId, transcriptVersion, firstSegmentId, lastSegmentId, firstTokenId, lastTokenId,
    transcriptStartMs, transcriptEndMs, exportStartMs, exportEndMs, text, timingPrecision } = candidate.selection;
  return {
    id, projectId, catalogVideoId, version,
    ...(createdBy === undefined ? {} : { createdBy }),
    ...(createdAt === undefined ? {} : { createdAt }),
    ...(updatedAt === undefined ? {} : { updatedAt }),
    video: { youtubeVideoId, canonicalUrl, title,
      ...(channel === undefined ? {} : { channel }),
      ...(sourceLanguage === undefined ? {} : { sourceLanguage }) },
    selection: { trackId, transcriptVersion, firstSegmentId, lastSegmentId,
      ...(firstTokenId === undefined ? {} : { firstTokenId }),
      ...(lastTokenId === undefined ? {} : { lastTokenId }),
      transcriptStartMs, transcriptEndMs, exportStartMs, exportEndMs, text, timingPrecision },
    englishText, ...(originalText === undefined ? {} : { originalText }),
  };
}

/** Same-origin access to only the single-writer project/document routes. */
export function createAuthoringHandler(
  origin: string,
  authorization: string,
  projects: (request: Request) => Promise<Response>,
  research?: AuthoringResearchAccess,
) {
  const launchProof = randomBytes(32);
  // Keep the enrolled browser working after host restart. Tie it to the
  // configured identity and port without giving the browser the API token.
  const browserProof = createHmac("sha256", authorization).update(`vera-authoring:${origin}`).digest();
  // D124 is session history, not a property of the submitted document. Keep
  // exactly one server-owned split and require its opaque proof and *whole*
  // resulting document before using the model's exact restoration path.
  let lastSplit: {
    proof: string;
    rowId: string;
    newRowId: string;
    documentJson: string;
    session: ReturnType<typeof createRowEditSessionV2>;
  } | null = null;
  async function projectVisualHoldMs(projectId: string): Promise<number> {
    const response = await projects(new Request(`${origin}/v1/projects/${projectId}/settings`, {
      headers: { authorization },
    }));
    if (response.status === 404) return LEGACY_VISUAL_HOLD_MS;
    if (!response.ok) throw new Error("Project visual hold setting is unavailable.");
    const { settings } = await response.json() as { settings: { visualOnlyStillDurationMs?: number } };
    return settings.visualOnlyStillDurationMs ?? LEGACY_VISUAL_HOLD_MS;
  }
  const handle = async (request: Request): Promise<Response | undefined> => {
    const url = new URL(request.url);
    const asset = request.method === "GET" ? ASSETS.get(url.pathname) : undefined;
    if (asset) {
      const [file, mime] = asset;
      const contents = await readFile(new URL(`../browser/${file}`, import.meta.url), "utf8");
      return new Response(contents, { headers: {
        "Content-Type": mime,
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; " +
          "connect-src 'self'; frame-src https://www.youtube-nocookie.com; " +
          "img-src 'self' data: blob: https://i.ytimg.com; font-src 'self' data:; " +
          "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Referrer-Policy": "no-referrer",
      } });
    }
    if (!url.pathname.startsWith("/authoring/")) return undefined;
    const path = url.pathname.slice("/authoring".length);
    const route = PROJECT.exec(path);
    const visualHoldDefault = request.method === "GET" ? VISUAL_HOLD_DEFAULT.exec(path) : null;
    const stillRoute = RESEARCH_STILLS.exec(path);
    const quoteRoute = RESEARCH_QUOTES.exec(path);
    const quotePictureRoute = RESEARCH_QUOTE_PICTURE.exec(path);
    const researchRoute = stillRoute ?? quoteRoute ?? quotePictureRoute ?? RESEARCH.exec(path);
    const researchNumber = stillRoute || quoteRoute
      ? researchReadNumber(url.searchParams, Boolean(stillRoute?.[3] || quoteRoute?.[3]))
      : null;
    const musicWarnings = MUSIC_WARNINGS.test(path);
    const prompterRoute = PROMPTER_EXPORT.exec(path);
    const isPrompterExport = !!prompterRoute && request.method === "POST";
    const sortingRoute = SORTING_TRIAL.exec(path);
    const isSortingTrial = !!sortingRoute && request.method === "POST";
    const isExtrasOperation = EXTRAS.test(path) && request.method === "POST";
    const startsSession = path === "/session" && request.method === "POST";
    const isCommand = path === "/command" && request.method === "POST";
    const isVisualCommand = path === "/visual-command" && request.method === "POST";
    const isVisualPreview = path === "/visual-preview" && request.method === "POST";
    const isProjection = path === "/projection" && request.method === "POST";
    const isResearchInsert = path === RESEARCH_INSERT && request.method === "POST";
    const isStillInsert = path === "/research-still-insert" && request.method === "POST";
    const isQuoteInsert = path === "/research-quote-insert" && request.method === "POST";
    const isResearchStash = path === "/research-stash" && request.method === "POST";
    const isQuoteBoxEdit = path === "/research-quote-box-edit" && request.method === "POST";
    const isQuoteDisplayDefault = path === "/research-quote-display-default" && request.method === "POST";
    const allowed = path === "/projects" ? request.method === "POST" :
      (route && (request.method === "GET" || request.method === (route[1] ? "PUT" : "PATCH"))) ||
      visualHoldDefault || (musicWarnings && request.method === "GET") ||
      (researchRoute && request.method === "GET" && request.body === null);
    if ((!allowed && !startsSession && !isCommand && !isVisualCommand && !isVisualPreview &&
        !isProjection && !isPrompterExport && !isResearchInsert && !isStillInsert && !isQuoteInsert &&
        !isResearchStash && !isQuoteBoxEdit && !isQuoteDisplayDefault && !isSortingTrial && !isExtrasOperation) ||
        (stillRoute || quoteRoute ? researchNumber === null : url.search)) {
      return isPrompterExport ? prompterReply({ error: "not_found" }, 404) :
        Response.json({ error: "not_found" }, { status: 404 });
    }

    // Cross-origin browser code cannot set this header without a successful
    // CORS preflight. Fetch Metadata also excludes other sites and local ports.
    const suppliedOrigin = request.headers.get("origin");
    if (request.headers.get("sec-fetch-site") !== "same-origin" ||
        request.headers.get("x-vera-authoring") !== "1" ||
        (suppliedOrigin !== null && suppliedOrigin !== origin)) {
      return isPrompterExport ? prompterReply({ error: "same_origin_required" }, 403) :
        Response.json({ error: "same_origin_required" }, { status: 403 });
    }
    if (startsSession && matchesProof(request.headers.get("x-vera-launch"), launchProof)) {
      return Response.json({ sessionProof: browserProof.toString("hex") });
    }
    if (startsSession || !matchesProof(request.headers.get("x-vera-session"), browserProof)) {
      return isPrompterExport ? prompterReply({ error: "authoring_browser_required" }, 401) :
        Response.json({ error: "authoring_browser_required" }, { status: 401 });
    }
    if (visualHoldDefault) {
      try {
        return Response.json({ milliseconds: await projectVisualHoldMs(visualHoldDefault[1]!) });
      } catch {
        return Response.json({ error: "visual_hold_default_unavailable" }, { status: 503 });
      }
    }
    if (isExtrasOperation && request.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase() !== "application/json") {
      return Response.json({ error: "invalid_request" }, { status: 400 });
    }
    if (isSortingTrial) {
      let body: unknown;
      try { body = await request.json(); } catch { body = null; }
      const legacy = record(body) && exact(body, ["expectedRevision", "expectedDigest", "moves", "action"]);
      const current = record(body) && (exact(body, ["expectedRevision", "expectedDigest", "operations", "action"]) ||
        exact(body, ["expectedRevision", "expectedDigest", "operations", "action", "outcome"]));
      const withinBodyLimit = !!body && record(body) && JSON.stringify(body).length <= 5_000_000;
      const operationList: unknown[] | null = record(body) && Array.isArray(body.operations) ? body.operations : null;
      const withinOperationLimit = !!operationList && operationList.length <= 1000 &&
        operationList.reduce<number>((count, item) => count + (record(item) && item.kind === "batch" && Array.isArray(item.operations)
          ? item.operations.length : 1), 0) <= 1000;
      if (!record(body) || (!legacy && !current) ||
          !Number.isSafeInteger(body.expectedRevision) || (body.expectedRevision as number) < 0 ||
          typeof body.expectedDigest !== "string" || !SAVED_DIGEST.test(body.expectedDigest) ||
          !["preview", "accept", "discard"].includes(body.action as string) ||
          (legacy ? !Array.isArray(body.moves) || body.moves.length > 1000 || !body.moves.every(sortingMove) :
            !withinBodyLimit || !withinOperationLimit ||
            !operationList || !operationList.every((item) => sortingOperation(item) !== null) ||
            body.action === "accept" && Object.hasOwn(body, "outcome") &&
              !["all", "edits_only", "sorting_only"].includes(body.outcome as string) ||
            body.action !== "accept" && Object.hasOwn(body, "outcome")) ||
          !withinBodyLimit) {
        return researchResponse(400, { error: "invalid_sorting_trial" });
      }
      try {
        // Rebuild from the exact authorized saved head every time; browser
        // commands cannot replace content and trial requests never write.
        const projectId = sortingRoute[1]!;
        const saved = await projects(new Request(`${origin}/v1/projects/${projectId}/document`, {
          method: "GET", headers: { authorization },
        }));
        if (!saved.ok) {
          return researchResponse([401, 403, 404].includes(saved.status) ? saved.status : 503,
            { error: "saved_script_unavailable" });
        }
        const head: unknown = await saved.json();
        if (!record(head) || head.projectId !== projectId ||
            !validateScriptDocumentV2(head.document).valid ||
            (head.document as ScriptDocumentV2).projectId !== projectId) {
          return researchResponse(503, { error: "saved_script_unavailable" });
        }
        if (head.revision !== body.expectedRevision || head.digest !== body.expectedDigest) {
          return researchResponse(409, { ok: false, diagnostics: [{
            code: "SORTING_BASELINE_CHANGED", jsonPath: "/activeDraft",
            message: "The saved script changed. Discard this trial and reload before sorting again.",
          }] });
        }
        const baseline = head.document as ScriptDocumentV2;
        const operations: SortingOperation[] = legacy
          ? (body.moves as unknown[]).map((move) => ({ kind: "command", command: move as RowEditCommandV2 }))
          : body.operations as SortingOperation[];
        const flat = operations.flatMap((item) => item.kind === "batch" ? item.operations : [item]);
        const needsProjectHold = flat.some((item) => item.kind === "visual"
          ? item.command.kind === "move_visual_to_row"
          : item.kind === "command" && ["add_visual_to_wordless_row", "move_wordless_visual"].includes(item.command.kind));
        const projectHoldMs = needsProjectHold ? await projectVisualHoldMs(projectId) : LEGACY_VISUAL_HOLD_MS;
        const trial = createSortingTrialV2(baseline, projectHoldMs);
        const maxOperations = (items: SortingOperation[]): number => items.reduce((count, item) =>
          count + (item.kind === "batch" ? item.operations.length : 1), 0);
        if (maxOperations(operations) > 1000) return researchResponse(400, { error: "invalid_sorting_trial" });
        let placementCounts: RowEditResultV2["placementCounts"];
        const apply = (item: SortingOperation): RowEditResultV2 | null => {
          if (item.kind === "batch") {
            for (const nested of item.operations) {
              const result = apply(nested);
              if (result && !result.ok) return result;
            }
            return null;
          }
          if (item.kind === "undo") return trial.undo();
          const result = item.kind === "visual"
            ? trial.applyVisual(item.command, item.expectedSequenceVersion)
            : trial.apply(item.command);
          if (result.ok) placementCounts = result.placementCounts;
          return result;
        };
        for (const operation of operations) {
          const result = apply(operation);
          if (result && !result.ok) return researchResponse(200, result);
        }
        if (body.action === "preview") {
          const document = trial.preview();
          return researchResponse(200, { ok: true, document, movedRowIds: trial.movedRowIds,
            undoDepth: trial.undoDepth, projection: projectPrimarySequenceV2(document),
            ...(placementCounts ? { placementCounts } : {}) });
        }
        if (body.action === "discard") {
          const result = trial.discard(baseline);
          return researchResponse(200, { ...result, changed: false, movedRowIds: [],
            projection: projectPrimarySequenceV2(baseline) });
        }
        // The normal authorized document PUT still uses the original revision.
        const outcome = body.outcome as "all" | "edits_only" | "sorting_only" | undefined;
        return researchResponse(200, trial.accept(baseline, outcome ?? (legacy ? "sorting_only" : "all")));
      } catch {
        return researchResponse(503, { error: "sorting_trial_unavailable" });
      }
    }
    if (isPrompterExport) {
      // Never accept a client-supplied document. The project API owns current
      // saved-head reads, pending-collaboration flush and view_document permission.
      let body: unknown;
      try {
        if (!/^application\/json(?:\s*;|\s*$)/iu.test(request.headers.get("content-type") ?? "")) {
          return prompterReply({ error: "invalid_prompter_export" }, 400);
        }
        body = await request.json();
      } catch {
        return prompterReply({ error: "invalid_prompter_export" }, 400);
      }
      if (!record(body) ||
          !exact(body, Object.hasOwn(body, "settings") ?
            ["expectedRevision", "expectedDigest", "settings"] : ["expectedRevision", "expectedDigest"]) ||
          !Number.isSafeInteger(body.expectedRevision) || (body.expectedRevision as number) < 0 ||
          typeof body.expectedDigest !== "string" || !SAVED_DIGEST.test(body.expectedDigest)) {
        return prompterReply({ error: "invalid_prompter_export" }, 400);
      }
      const requestedSettings = body.settings;
      if (requestedSettings !== undefined &&
          (!record(requestedSettings) ||
            !exact(requestedSettings, ["includeSectionNavigation", "includeBeatNumbers"]) ||
            typeof requestedSettings.includeSectionNavigation !== "boolean" ||
            typeof requestedSettings.includeBeatNumbers !== "boolean")) {
        return prompterReply({ error: "invalid_prompter_export" }, 400);
      }
      const settings = requestedSettings === undefined ?
        { includeSectionNavigation: false, includeBeatNumbers: false } :
        requestedSettings as { includeSectionNavigation: boolean; includeBeatNumbers: boolean };
      try {
        const saved = await projects(new Request(`${origin}/v1/projects/${prompterRoute[1]}/document`, {
          method: "GET", headers: { authorization },
        }));
        if (!saved.ok) {
          // Preserve the permission/not-found status without reflecting a
          // possibly sensitive project API error body to the browser.
          const status = [401, 403, 404].includes(saved.status) ? saved.status : 503;
          return prompterReply({ error: "saved_script_unavailable" }, status);
        }
        const result = prepareSavedPrompter(await saved.json() as unknown, {
          projectId: prompterRoute[1]!, revision: body.expectedRevision as number,
          digest: body.expectedDigest,
        }, settings);
        return prompterReply(result.body, result.status);
      } catch {
        return prompterReply({ error: "saved_script_unavailable" }, 503);
      }
    }
    if (researchRoute) {
      if (!research) return researchResponse(503, { error: "research_unavailable" });
      const timelineProjectId = researchRoute[1]!;
      const researchProjectId = researchRoute[2];
      const clipId = researchRoute[3];
      // The browser session proves only that this is the local editor. It never
      // substitutes for a fresh Timeline membership/permission check.
      try {
        await research.authorizeTimelineProject(timelineProjectId);
      } catch (error) {
        if (error instanceof ProjectAuthError) {
          return researchResponse(error.status, { error: error.code });
        }
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      try {
        // Independently recheck Research visibility on EVERY catalog/clip read;
        // neither a UUID supplied by the browser nor a previous list is proof.
        const visible = await research.catalog.projects();
        if (quotePictureRoute) {
          if (!research.catalog.retainedQuotePicture) return researchResponse(503, { error: "research_unavailable" });
          const saved = await projects(new Request(`${origin}/v1/projects/${timelineProjectId.toLowerCase()}/document`, {
            headers: { authorization },
          }));
          if (!saved.ok) return researchResponse(404, { error: "research_quote_picture_unavailable" });
          const head: unknown = await saved.json();
          if (!record(head) || !validateScriptDocumentV2(head.document).valid) {
            return researchResponse(503, { error: "saved_script_unavailable" });
          }
          const doc = head.document as ScriptDocumentV2;
          if (doc.projectId !== timelineProjectId.toLowerCase()) return researchResponse(404, { error: "not_found" });
          const payloadId = quotePictureRoute[2]!.toLowerCase();
          const picture = doc.activeDraft.blocks.flatMap((row) => {
            if (row.type !== "narration" || row.state !== "active") return [];
            return (row.primaryVisualSequence?.slots ?? []).flatMap((slot) =>
              slot.kind === "content" && slot.payload.kind === "visual" && slot.payload.payloadId === payloadId &&
              slot.payload.researchQuotePicture ? [slot.payload.researchQuotePicture] : []);
          })[0];
          if (!picture) return researchResponse(404, { error: "research_quote_picture_unavailable" });
          if (!visible.some(({ id }) => id.toLowerCase() === picture.researchProjectId.toLowerCase())) {
            return researchResponse(403, { error: "research_project_forbidden" });
          }
          const bytes = await research.catalog.retainedQuotePicture(picture);
          if (!bytes) return researchResponse(404, { error: "research_quote_picture_unavailable" });
          return new Response(Buffer.from(bytes), { headers: { ...RESEARCH_HEADERS,
            "Content-Type": picture.original.mimeType, "Cross-Origin-Resource-Policy": "same-origin" } });
        }
        if (!researchProjectId) {
          return researchResponse(200, { projects: visible.map(({ id, name }) => ({ id, name })) });
        }
        if (!visible.some(({ id }) => id.toLowerCase() === researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        if (quoteRoute && researchNumber !== null) {
          const quoteId = quoteRoute[3]?.toLowerCase();
          if (quoteId) {
            if (!research.catalog.quote || !research.catalog.quoteThumbnail) {
              return researchResponse(503, { error: "research_unavailable" });
            }
            const quote = await research.catalog.quote(researchProjectId, quoteId);
            if (quote.itemId !== quoteId || quote.researchProjectId !== researchProjectId.toLowerCase()) {
              return researchResponse(404, { error: "research_quote_unavailable" });
            }
            if (quote.itemVersion !== researchNumber) return researchResponse(409, { error: "research_quote_changed" });
            const image = await research.catalog.quoteThumbnail(researchProjectId, quote);
            if (!image) return researchResponse(404, { error: "research_quote_picture_unavailable" });
            return new Response(Buffer.from(image.bytes), { headers: { ...RESEARCH_HEADERS,
              "Content-Type": image.mimeType, "Cross-Origin-Resource-Policy": "same-origin" } });
          }
          if (!research.catalog.quotes) return researchResponse(503, { error: "research_unavailable" });
          const { quotes, nextOffset } = await research.catalog.quotes(researchProjectId, researchNumber);
          return researchResponse(200, { quotes: quotes.map(publicResearchQuote), nextOffset });
        }
        if (stillRoute && researchNumber !== null) {
          const stillId = stillRoute[3];
          if (stillId && research.catalog.stillThumbnail) {
            const { bytes, mimeType } = await research.catalog.stillThumbnail(researchProjectId, stillId, researchNumber);
            return new Response(Buffer.from(bytes), { headers: { ...RESEARCH_HEADERS, "Content-Type": mimeType,
              "Cross-Origin-Resource-Policy": "same-origin" } });
          }
          if (!stillId && research.catalog.stills) {
            return researchResponse(200, await research.catalog.stills(researchProjectId, researchNumber));
          }
          return researchResponse(503, { error: "research_unavailable" });
        }
        if (clipId) {
          return researchResponse(200, { clip: publicResearchClip(
            await research.catalog.clip(researchProjectId, clipId),
          ) });
        }
        return researchResponse(200, { clips: (await research.catalog.clips(researchProjectId))
          .map(publicResearchClip) });
      } catch (error) {
        // Research's errors and headers can contain user data or credentials.
        if (quoteRoute || quotePictureRoute) return researchQuoteError(error);
        return stillRoute ? researchStillError(error) : researchResponse(503, { error: "research_unavailable" });
      }
    }
    if (isResearchStash) {
      let body: ReturnType<typeof researchStashRequest>;
      try { body = researchStashRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_research_stash" });
      if (!research) return researchResponse(503, { error: "research_unavailable" });
      try {
        await research.authorizeTimelineProject(body.timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      const { document, expectedDocumentRevision } = body;
      if (expectedDocumentRevision !== (document.rowEditRevision ?? 0) ||
          expectedDocumentRevision === Number.MAX_SAFE_INTEGER) return researchResponse(409, { error: "research_stash_changed" });
      const source = body.action === "capture_quote_box" ? researchQuoteBoxForStashV2(document, body.boxRequest) : null;
      if (body.action === "capture_quote_box" && !source) return researchResponse(409, { error: "quote_box_changed" });
      const researchProjectId = body.action === "capture_quote_box" ? source!.box.researchProjectId! :
        body.action === "place" ? (body.item.kind === "quote" ? body.item.quote.researchProjectId : body.item.still.researchProjectId) :
          body.researchProjectId;
      const stillAction = body.action === "capture_still" || body.action === "place" && body.item.kind === "still";
      try {
        const catalog = research.catalog;
        if (!(await catalog.projects()).some(({ id }) => id.toLowerCase() === researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        let result: RowEditResultV2;
        if (body.action === "capture_quote") {
          const snapshot = await resolveResearchQuote(catalog, researchProjectId, body.itemId, body.itemVersion);
          result = captureResearchStashItemV2(document, expectedDocumentRevision,
            { ...body.location, id: randomUUID(), kind: "quote", ...snapshot }, body.afterItemId);
        } else if (body.action === "capture_still") {
          if (!catalog.still) return researchResponse(503, { error: "research_unavailable" });
          const still = await catalog.still(researchProjectId, body.itemId, body.itemVersion);
          if (still.researchProjectId !== researchProjectId || still.itemId !== body.itemId || still.itemVersion !== body.itemVersion) {
            return researchResponse(409, { error: "research_still_changed" });
          }
          result = captureResearchStashItemV2(document, expectedDocumentRevision,
            { ...body.location, id: randomUUID(), kind: "still", still }, body.afterItemId);
        } else if (body.action === "capture_quote_box") {
          if (!catalog.quote) return researchResponse(503, { error: "research_unavailable" });
          const box = source!.box;
          const quote = await catalog.quote(researchProjectId, box.researchQuoteId);
          if (quote.researchProjectId !== researchProjectId || quote.itemId !== box.researchQuoteId ||
              quote.sourceId !== box.researchSourceId || quote.itemVersion < box.researchQuoteVersion!) {
            return researchResponse(409, { error: "research_quote_changed" });
          }
          result = captureResearchQuoteBoxV2(document, body.boxRequest, body.location, randomUUID(), quote.text, body.afterItemId);
        } else if (body.action === "place") {
          const item = body.item;
          if (item.kind === "quote") {
            if (!catalog.quote) return researchResponse(503, { error: "research_unavailable" });
            const quote = await catalog.quote(researchProjectId, item.quote.researchQuoteId);
            // A later Library display edit must not replace the frozen box fields.
            if (quote.researchProjectId !== researchProjectId || quote.itemId !== item.quote.researchQuoteId ||
                quote.sourceId !== item.quote.researchSourceId || quote.itemVersion < item.quote.researchQuoteVersion) {
              return researchResponse(409, { error: "research_quote_changed" });
            }
            if (item.background && (!catalog.retainedQuotePicture ||
                !await catalog.retainedQuotePicture(item.background.picture))) {
              return researchResponse(404, { error: "research_quote_picture_unavailable" });
            }
          } else {
            if (!catalog.still) return researchResponse(503, { error: "research_unavailable" });
            const current = await catalog.still(researchProjectId, item.still.itemId, item.still.itemVersion);
            if (!isDeepStrictEqual(current, item.still)) return researchResponse(409, { error: "research_still_changed" });
          }
          result = consumeResearchStashItemV2(document, item.id, body.target);
        } else return researchResponse(400, { error: "invalid_research_stash" });
        if (result.ok) lastSplit = null;
        return researchResponse(200, result);
      } catch (error) {
        return stillAction ? researchStillError(error) : researchQuoteError(error);
      }
    }
    if (isQuoteInsert) {
      let body: ReturnType<typeof quotePlacementRequest>;
      try { body = quotePlacementRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_research_insert" });
      if (!research?.catalog.quote) return researchResponse(503, { error: "research_unavailable" });
      try {
        await research.authorizeTimelineProject(body.timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      try {
        const { researchProjectId, quoteId, quoteVersion, document } = body;
        const visible = await research.catalog.projects();
        if (!visible.some(({ id }) => id.toLowerCase() === researchProjectId)) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        const { quote, background } = await resolveResearchQuote(research.catalog, researchProjectId, quoteId, quoteVersion);
        const result = placeResearchQuoteV2(document, quote, background, body.request);
        if (result.ok) lastSplit = null;
        return researchResponse(200, result);
      } catch (error) {
        return researchQuoteError(error);
      }
    }
    if (isQuoteBoxEdit) {
      let body: ReturnType<typeof editQuoteBoxRequest>;
      try { body = editQuoteBoxRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_quote_box_edit" });
      const { document, rowId, overlayId, edit } = body;
      const row = document.activeDraft.blocks.find(({ id }) => id === rowId);
      if (row?.type !== "narration" || row.state !== "active" || row.version !== body.expectedRowVersion) {
        return researchResponse(409, { error: "quote_box_changed" });
      }
      const overlay = row.overlayEvents.find(({ id }) => id === overlayId);
      if (!overlay?.quoteBox || overlay.version !== body.expectedOverlayVersion ||
          overlay.version === Number.MAX_SAFE_INTEGER) return researchResponse(409, { error: "quote_box_changed" });
      let timing = overlay.timing;
      if ("range" in edit) {
        const words = spokenTokensV2(row);
        const start = words.findIndex(({ id }) => id === edit.range.startTokenId);
        const end = words.findIndex(({ id }) => id === edit.range.endTokenId);
        if (start < 0 || end < start) return researchResponse(409, { error: "quote_range_changed" });
        const anchor = <Affinity extends "before" | "after">(index: number, affinity: Affinity) => ({
          blockId: rowId, tokenId: words[index]!.id, quotedWord: words[index]!.value, affinity, anchorVersion: row.version,
        });
        timing = { kind: "timed", start: { kind: "word", anchor: anchor(start, "before") },
          end: { kind: "audible_word_end", anchor: anchor(end, "after") } };
      }
      const overlayEvents = "delete" in edit ? row.overlayEvents.filter((event) => event !== overlay)
        : row.overlayEvents.map((event) => {
          if (event !== overlay || !event.quoteBox) return event;
          const quoteBox = "displayText" in edit
            ? { ...event.quoteBox, displayText: edit.displayText }
            : "citationText" in edit
              ? { ...event.quoteBox, ...editCitationText(event.quoteBox, edit.citationText), citationOverridden: true as const }
              : event.quoteBox;
          return { ...event, version: event.version + 1, quoteBox, timing };
        });
      const result = applyRowEditV2(document, body.expectedDocumentRevision, {
        kind: "edit_row", rowId, row: { ...row, overlayEvents },
      });
      if (result.ok) lastSplit = null;
      return researchResponse(200, result);
    }
    if (isQuoteDisplayDefault) {
      let body: unknown;
      try { body = await request.json(); } catch { body = null; }
      const displayKeys = ["timelineProjectId", "rowId", "overlayId", "expectedRevision", "expectedDigest"];
      if (!record(body) || !exact(body, Object.hasOwn(body, "undo") ? [...displayKeys, "undo"] : displayKeys) ||
          !uuid(body.timelineProjectId) || !uuid(body.rowId) || !uuid(body.overlayId) ||
          !revision(body.expectedRevision) || typeof body.expectedDigest !== "string" ||
          !SAVED_DIGEST.test(body.expectedDigest)) return researchResponse(400, { error: "invalid_quote_box_edit" });
      let undo: QuoteDefaultUndo | undefined;
      if (Object.hasOwn(body, "undo")) {
        const wire = typeof body.undo === "string" && body.undo.length <= 400_000
          ? /^([A-Za-z0-9_-]+)\.([a-f0-9]{64})$/u.exec(body.undo) : null;
        if (!wire || !matchesProof(wire[2], quoteDefaultProof(authorization, wire[1]!))) {
          return researchResponse(400, { error: "invalid_quote_box_edit" });
        }
        undo = JSON.parse(Buffer.from(wire[1]!, "base64url").toString("utf8")) as QuoteDefaultUndo;
      }
      if (!research?.catalog.quote || !research.catalog.setQuoteDisplayText) {
        return researchResponse(503, { error: "research_unavailable" });
      }
      const { timelineProjectId, rowId, overlayId, expectedRevision, expectedDigest } = body;
      try {
        await research.authorizeTimelineProject(timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      try {
        const saved = await projects(new Request(`${origin}/v1/projects/${timelineProjectId}/document`, {
          method: "GET", headers: { authorization },
        }));
        if (!saved.ok) return researchResponse(503, { error: "saved_script_unavailable" });
        const head: unknown = await saved.json();
        if (!record(head) || head.projectId !== timelineProjectId || !validateScriptDocumentV2(head.document).valid) {
          return researchResponse(503, { error: "saved_script_unavailable" });
        }
        if (head.revision !== expectedRevision || head.digest !== expectedDigest) {
          return researchResponse(409, { error: "quote_box_changed" });
        }
        const row = (head.document as ScriptDocumentV2).activeDraft.blocks.find(({ id }) => id === rowId);
        const box = row?.type === "narration" && row.state === "active"
          ? row.overlayEvents.find(({ id }) => id === overlayId)?.quoteBox : undefined;
        if (!box?.researchProjectId || !box.researchSourceId || !quoteText(box.displayText)) {
          return researchResponse(404, { error: "research_quote_unavailable" });
        }
        const { researchProjectId, researchQuoteId } = box;
        const visible = await research.catalog.projects();
        if (!visible.some(({ id }) => id.toLowerCase() === researchProjectId)) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        const current = await research.catalog.quote(researchProjectId, researchQuoteId);
        if (current.researchProjectId !== researchProjectId || current.itemId !== researchQuoteId ||
            current.sourceId !== box.researchSourceId) return researchResponse(409, { error: "research_quote_changed" });
        if (undo) {
          if (undo.timelineProjectId !== timelineProjectId || undo.rowId !== rowId || undo.overlayId !== overlayId ||
              undo.researchProjectId !== researchProjectId || undo.researchQuoteId !== researchQuoteId ||
              undo.revision >= expectedRevision || box.displayText.trim() === undo.after ||
              current.displayText !== undo.after) return researchResponse(409, { error: "research_quote_changed" });
          await research.catalog.setQuoteDisplayText(researchProjectId, researchQuoteId, current.itemVersion, undo.before);
          return new Response(null, { status: 204, headers: RESEARCH_HEADERS });
        }
        if (current.displayText !== box.displayText) {
          const after = box.displayText.trim();
          if (after === current.displayText) return new Response(null, { status: 204, headers: RESEARCH_HEADERS });
          await research.catalog.setQuoteDisplayText(researchProjectId, researchQuoteId, current.itemVersion, after);
          const receipt: QuoteDefaultUndo = { timelineProjectId, rowId, overlayId,
            researchProjectId, researchQuoteId, before: current.displayText, after, revision: expectedRevision };
          const encoded = Buffer.from(JSON.stringify(receipt)).toString("base64url");
          return researchResponse(200, { undo: `${encoded}.${quoteDefaultProof(authorization, encoded).toString("hex")}` });
        }
        return new Response(null, { status: 204, headers: RESEARCH_HEADERS });
      } catch (error) {
        return researchQuoteError(error);
      }
    }
    if (isStillInsert) {
      let body: ReturnType<typeof stillInsertRequest>;
      try { body = stillInsertRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_research_insert" });
      if (!research?.catalog.still) return researchResponse(503, { error: "research_unavailable" });
      try {
        await research.authorizeTimelineProject(body.timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      try {
        const projects = await research.catalog.projects();
        const { document, researchProjectId, itemId, itemVersion } = body;
        if (!projects.some(({ id }) => id.toLowerCase() === researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        const snapshot = await research.catalog.still(researchProjectId, itemId, itemVersion);
        const result = insertResearchStillBrowserV2(document, snapshot, body);
        if (result.ok) lastSplit = null;
        return researchResponse(200, result);
      } catch (error) {
        return researchStillError(error);
      }
    }
    if (isResearchInsert) {
      let body: ReturnType<typeof researchInsertRequest>;
      try { body = researchInsertRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_research_insert" });
      if (!research) return researchResponse(503, { error: "research_unavailable" });
      try {
        await research.authorizeTimelineProject(body.timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      let candidate: Awaited<ReturnType<AuthoringResearchCatalog["clip"]>>;
      try {
        // A previous GET/list is never sufficient authorization to mutate a script.
        const projects = await research.catalog.projects();
        if (!projects.some(({ id }) => id.toLowerCase() === body.researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        candidate = await research.catalog.clip(body.researchProjectId, body.clipId);
      } catch {
        return researchResponse(503, { error: "research_unavailable" });
      }
      const result = insertResearchClipBrowserV2(body.document, candidate, body);
      if (result.ok) lastSplit = null;
      return researchResponse(200, result);
    }
    if (isProjection) {
      try {
        const body: unknown = await request.json();
        if (!record(body) || !exact(body, ["document"]) ||
            !validateScriptDocumentV2(body.document).valid) {
          return Response.json({ error: "invalid_projection" }, { status: 400 });
        }
        // Read-only: a projection cannot create, redeem or invalidate D124 split context.
        return Response.json({ projection: projectPrimarySequenceV2(body.document) });
      } catch {
        return Response.json({ error: "invalid_projection" }, { status: 400 });
      }
    }
    if (isCommand) {
      try {
        const body = await request.json() as { document: ScriptDocumentV2; command: RowEditCommandV2;
          splitProof?: string; expectedSequenceVersion?: unknown; expectedRowEditRevision?: unknown };
        const { command, document, splitProof } = body;
        if (record(command) && VISUAL_KINDS.has(String(command.kind))) {
          const visual = visualCommand(command);
          if (!visual || !record(body) || !exact(body, ["document", "command", "expectedSequenceVersion"]) ||
              !Number.isSafeInteger(body.expectedSequenceVersion) ||
              (body.expectedSequenceVersion as number) < 0 ||
              !validateScriptDocumentV2(document).valid) {
            return Response.json({ error: "invalid_command" }, { status: 400 });
          }
          const projectHoldMs = visual.kind === "move_visual_to_row" &&
            usesProjectVisualHold(document.activeDraft.blocks.find((block) => block.id === visual.destinationBlockId))
            ? await projectVisualHoldMs(document.projectId) : undefined;
          const result = applyVisualSequenceEditV2(document, body.expectedSequenceVersion as number, visual, projectHoldMs);
          if (result.ok) lastSplit = null; // Any successful visual edit breaks immediate split restoration.
          return Response.json(result);
        }
        if (record(command) && REVISIONED_ROW_KINDS.has(String(command.kind))) {
          const rowCommand = revisionedRowCommand(command);
          if (!rowCommand || !record(body) || !exact(body, ["document", "command", "expectedRowEditRevision"]) ||
              !Number.isSafeInteger(body.expectedRowEditRevision) || (body.expectedRowEditRevision as number) < 0 ||
              !validateScriptDocumentV2(document).valid) {
            return Response.json({ error: "invalid_command" }, { status: 400 });
          }
          let needsProjectHold = false;
          const blocks = document.activeDraft.blocks;
          if (rowCommand.kind === "add_visual_to_wordless_row") {
            needsProjectHold = usesProjectVisualHold(blocks.find((block) => block.id === rowCommand.rowId));
          } else if (rowCommand.kind === "move_wordless_visual") {
            const source = blocks.find((block) => block.id === rowCommand.sourceRowId);
            const destination = blocks.find((block) => block.id === rowCommand.destinationRowId);
            const wordlessDestination = destination?.type === "visual_only" ||
              destination?.type === "narration" && destination.text === "";
            needsProjectHold = usesProjectVisualHold(destination) ||
              wordlessDestination && usesProjectVisualHold(source) && source.payload.payloadId === rowCommand.payloadId;
          }
          const projectHoldMs = needsProjectHold ? await projectVisualHoldMs(document.projectId) : undefined;
          const result = applyRowEditV2(document, body.expectedRowEditRevision as number, rowCommand, projectHoldMs);
          if (result.ok) lastSplit = null;
          return Response.json(result);
        }
        if (!record(command) || typeof command.kind !== "string" ||
            Object.hasOwn(body, "expectedSequenceVersion") || Object.hasOwn(body, "expectedRowEditRevision")) {
          return Response.json({ error: "invalid_command" }, { status: 400 });
        }
        if (splitProof !== undefined) {
          const validProof = typeof splitProof === "string" && PROOF.test(splitProof) && lastSplit &&
            timingSafeEqual(Buffer.from(splitProof, "hex"), Buffer.from(lastSplit.proof, "hex"));
          const validJoin = command?.kind === "join_rows" && command.direction === "previous" &&
            command.rowId === lastSplit?.newRowId && command.words === null;
          const validDocument = lastSplit && JSON.stringify(document) === lastSplit.documentJson &&
            document.rowEditRevision === lastSplit.session.revision;
          if (!validProof || !validJoin || !validDocument) {
            return Response.json({ ok: false, document, diagnostics: [{
              code: "ROW_SPLIT_CONTEXT_STALE", jsonPath: "/activeDraft",
              message: "The immediate split restoration is no longer available.",
            }] });
          }
          const session = lastSplit!.session;
          lastSplit = null;
          return Response.json(session.apply(command));
        }
        if (command?.kind === "split_row") {
          const session = createRowEditSessionV2(document);
          const result = session.apply(command);
          if (!result.ok) return Response.json(result);
          const proof = randomBytes(32).toString("hex");
          lastSplit = {
            proof, rowId: command.rowId, newRowId: command.newRowId,
            documentJson: JSON.stringify(result.document), session,
          };
          return Response.json({ ...result, splitProof: proof });
        }
        const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
        if (result.ok) lastSplit = null;
        return Response.json(result);
      } catch {
        return Response.json({ error: "invalid_command" }, { status: 400 });
      }
    }
    if (isVisualCommand || isVisualPreview) {
      try {
        const body = await request.json() as {
          document?: ScriptDocumentV2;
          command?: VisualSequenceEditCommandV2;
          expectedSequenceVersion?: number;
        };
        const { document, command, expectedSequenceVersion } = body;
        if (!record(body) || !exact(body, ["document", "command", "expectedSequenceVersion"]) ||
            !document || !validateScriptDocumentV2(document).valid || !record(command) ||
            !AUTHORING_VISUAL_KINDS.has(command.kind) ||
            !Number.isSafeInteger(expectedSequenceVersion) || expectedSequenceVersion! < 0) {
          return Response.json({ error: "invalid_visual_command" }, { status: 400 });
        }
        const result = applyVisualSequenceEditV2(document, expectedSequenceVersion!, command);
        // Read-only Reselect previews must not consume the one-time proof for
        // immediately restoring a split. Only a committed edit breaks it.
        if (result.ok && isVisualCommand) lastSplit = null;
        return Response.json(result.ok ? { ...result, projection: projectPrimarySequenceV2(result.document) } : result);
      } catch {
        return Response.json({ error: "invalid_visual_command" }, { status: 400 });
      }
    }
    const headers = new Headers({ authorization });
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    return await projects(new Request(`${origin}/v1${path}`, {
      method: request.method,
      headers,
      body: request.body ? await request.arrayBuffer() : null,
    }));
  };
  return { launchCode: launchProof.toString("hex"), handle };
}
