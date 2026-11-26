/** Pure, one-revision bridge from an authorized Research candidate to a script picture. */
import { randomUUID } from "node:crypto";

import type { RowGapV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import { createResearchClipOccurrenceV2, type ResearchLoggedCandidateInputV2 } from "./authoring-v2-research-snapshot.js";
import { isCoverageRefusalV2 } from "./authoring-v2-coverage.js";
import { applyRowEditV2, type RowEditCommandV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { attachVisualToWordsV2 } from "./authoring-v2-visual-lifecycle.js";
import { toNarratedPlacementV2, wordlessPlacementsV2 } from "./authoring-v2-wordless.js";

export type ResearchClipBrowserDestinationV2 =
  | { kind: "gap"; destination: RowGapV2 }
  | { kind: "stash"; sectionId: string | null; noteRowId: string | null; replace: boolean }
  | { kind: "unattached"; rowId: string; expectedRowVersion: number; expectedSequenceVersion: number }
  | { kind: "selected_words"; rowId: string; expectedRowVersion: number; expectedSequenceVersion: number;
      startTokenId: string; endTokenId: string };

/** The caller supplies identity/version expectations, NOT the clip contents or frame binding. */
export interface ResearchClipBrowserInsertV2 {
  expectedDocumentRevision: number;
  researchProjectId: string;
  clipId: string;
  clipVersion: number;
  placement: ResearchClipBrowserDestinationV2;
}

function refused(document: ScriptDocumentV2, code: string, message: string): RowEditResultV2 {
  return { ok: false, document, diagnostics: [{ code, message, severity: "error", jsonPath: "$" }] };
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

function reservedIds(value: unknown, ids = new Set<string>()): Set<string> {
  if (typeof value === "string" && uuid.test(value)) ids.add(value.toLowerCase());
  else if (value && typeof value === "object") {
    for (const child of Object.values(value)) reservedIds(child, ids);
  }
  return ids;
}

/** A refused insertion returns the exact original document object, never a partially edited clone. */
export function insertResearchClipBrowserV2(
  document: ScriptDocumentV2,
  candidate: ResearchLoggedCandidateInputV2,
  request: ResearchClipBrowserInsertV2,
  makeId: () => string = randomUUID,
): RowEditResultV2 & { rowCommands?: RowEditCommandV2[] } {
  if (!request || !candidate || !uuid.test(request.researchProjectId ?? "") ||
      !uuid.test(request.clipId ?? "") || !Number.isSafeInteger(request.clipVersion) || request.clipVersion < 1 ||
      request.researchProjectId.toLowerCase() !== candidate.projectId?.toLowerCase() ||
      request.clipId.toLowerCase() !== candidate.id?.toLowerCase() || request.clipVersion !== candidate.version) {
    return refused(document, "RESEARCH_CLIP_STALE", "The authorized Research clip identity, project or version has changed.");
  }
  if (!Number.isSafeInteger(request.expectedDocumentRevision) ||
      request.expectedDocumentRevision !== (document.rowEditRevision ?? 0) ||
      request.expectedDocumentRevision === Number.MAX_SAFE_INTEGER) {
    return refused(document, "ROW_REVISION_STALE", "The script changed before this clip was chosen.");
  }
  const placement = request.placement;
  if (!placement || !["gap", "stash", "unattached", "selected_words"].includes(placement.kind)) {
    return refused(document, "RESEARCH_PLACEMENT_INVALID", "Choose a current script gap or narration row.");
  }

  let row: Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }> | undefined;
  if (placement.kind === "selected_words" || placement.kind === "unattached") {
    row = document.activeDraft.blocks.find((block) => block.id === placement.rowId && block.type === "narration") as typeof row;
    if (!row) return refused(document, "ROW_NOT_FOUND", "Choose an active narration row, not a saved Stash row.");
    if (row.version !== placement.expectedRowVersion ||
        row.primaryVisualSequence?.version !== placement.expectedSequenceVersion ||
        placement.expectedSequenceVersion === Number.MAX_SAFE_INTEGER || row.version === Number.MAX_SAFE_INTEGER) {
      return refused(document, "SEQUENCE_VERSION_STALE", "The narration row or picture sequence changed before insertion.");
    }
  }

  // Reserve every UUID in the document (including Stash, payloads and tokens)
  // and the candidate. A bad ID factory is a refusal, not an accidental retarget.
  const ids = reservedIds(candidate, reservedIds(document));
  const nextId = (): string => {
    const id = makeId();
    if (typeof id !== "string" || !uuid.test(id) || ids.has(id.toLowerCase())) {
      throw new RangeError("A new Research picture needs an unused UUID.");
    }
    ids.add(id.toLowerCase());
    return id;
  };
  try {
    const occurrence = createResearchClipOccurrenceV2({
      rowId: nextId(), payloadId: nextId(), orderKey: `research-${nextId()}`, candidate,
      // No frameBinding or selectedRange: logged milliseconds are not media frames.
    });
    if (placement.kind === "gap") {
      return applyRowEditV2(document, request.expectedDocumentRevision, {
        kind: "create_row", row: occurrence, destination: placement.destination,
      });
    }

    if (placement.kind === "stash") {
      const note = placement.noteRowId === null ? null : (document.stash ?? [])
        .flatMap((bundle) => bundle.rows).find((item) => item.id === placement.noteRowId);
      if ((placement.noteRowId !== null && (note?.type !== "narration" ||
          (note.attachedFootage !== undefined) !== placement.replace)) ||
          (placement.noteRowId === null && placement.replace)) {
        return refused(document, "STASH_ATTACHMENT_CHANGED", "The Stash note or its footage changed. Choose the clip again.");
      }
      const create: RowEditCommandV2 = {
        kind: "create_stash_clip", row: occurrence, bundleId: nextId(),
        sectionId: placement.sectionId, parentRowId: null, afterRowId: null,
      };
      const added = applyRowEditV2(document, request.expectedDocumentRevision, create);
      if (!added.ok) return added;
      if (!note) return { ...added, rowCommands: [create] };
      const attach: RowEditCommandV2 = placement.replace
        ? { kind: "replace_stash_footage", noteRowId: note.id, clipRowId: occurrence.id, releasedBundleId: nextId() }
        : { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: occurrence.id };
      const result = applyRowEditV2(added.document, added.document.rowEditRevision!, attach);
      return result.ok ? { ...result, rowCommands: [create, attach] } : { ...result, document };
    }

    const converted = toNarratedPlacementV2(wordlessPlacementsV2(occurrence)[0]!);
    if (!("value" in converted)) return refused(document, converted.code, converted.message);
    const updated = structuredClone(row!);
    const slotId = nextId();
    updated.unattachedVisuals = [...(updated.unattachedVisuals ?? []), {
      slotId, payload: converted.value, version: 1,
    }];
    if (placement.kind === "selected_words") {
      const attached = attachVisualToWordsV2(updated, slotId, placement.startTokenId, placement.endTokenId);
      if (isCoverageRefusalV2(attached)) return refused(document, attached.code, attached.message);
    } else {
      updated.primaryVisualSequence!.version += 1;
    }
    updated.version += 1;
    return applyRowEditV2(document, request.expectedDocumentRevision, {
      kind: "edit_row", rowId: updated.id, row: updated,
    });
  } catch (error) {
    return refused(document, "RESEARCH_INSERT_INVALID", error instanceof Error ? error.message : "Cannot create this Research picture.");
  }
}
