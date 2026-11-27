/** Pure, one-revision bridge from an authorized Research kept still to narration words. */
import { randomUUID } from "node:crypto";

import type {
  NarratedVisualPayloadV2,
  ResearchStillSnapshotV2,
  ScriptDocumentV2,
} from "./generated/contracts-v2.js";
import { isCoverageRefusalV2 } from "./authoring-v2-coverage.js";
import { applyRowEditV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { attachVisualToWordsV2 } from "./authoring-v2-visual-lifecycle.js";

export interface ResearchStillBrowserInsertV2 {
  expectedDocumentRevision: number;
  researchProjectId: string;
  itemId: string;
  itemVersion: number;
  placement: {
    rowId: string;
    expectedRowVersion: number;
    expectedSequenceVersion: number;
  } & ({ kind: "selected_words"; startTokenId: string; endTokenId: string } | { kind: "unattached" });
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

function refused(document: ScriptDocumentV2, code: string, message: string): RowEditResultV2 {
  return { ok: false, document, diagnostics: [{ code, message, severity: "error", jsonPath: "$" }] };
}

function reservedIds(value: unknown, ids = new Set<string>()): Set<string> {
  if (typeof value === "string" && UUID.test(value)) ids.add(value.toLowerCase());
  else if (value && typeof value === "object") {
    for (const child of Object.values(value)) reservedIds(child, ids);
  }
  return ids;
}

/** The host supplies the authoritative snapshot only after its Research checks. */
export function insertResearchStillBrowserV2(
  document: ScriptDocumentV2,
  snapshot: ResearchStillSnapshotV2,
  request: ResearchStillBrowserInsertV2,
  makeId: () => string = randomUUID,
): RowEditResultV2 {
  if (!request || !snapshot ||
      !UUID.test(request.researchProjectId ?? "") || !UUID.test(request.itemId ?? "") ||
      request.researchProjectId.toLowerCase() !== snapshot.researchProjectId?.toLowerCase() ||
      request.itemId.toLowerCase() !== snapshot.itemId?.toLowerCase() ||
      !Number.isSafeInteger(request.itemVersion) || request.itemVersion < 1 ||
      request.itemVersion !== snapshot.itemVersion) {
    return refused(document, "RESEARCH_STILL_STALE", "The saved Research still changed.");
  }
  if (!Number.isSafeInteger(request.expectedDocumentRevision) ||
      request.expectedDocumentRevision !== (document.rowEditRevision ?? 0) ||
      request.expectedDocumentRevision === Number.MAX_SAFE_INTEGER) {
    return refused(document, "ROW_REVISION_STALE", "The script changed before still placement.");
  }
  const placement = request.placement;
  if (!placement || placement.kind !== "selected_words" && placement.kind !== "unattached") {
    return refused(document, "STILL_PLACEMENT_INVALID", "Select spoken words for this still.");
  }

  const row = document.activeDraft.blocks.find((block) =>
    block.id === placement.rowId && block.type === "narration");
  if (!row || row.type !== "narration" || !row.primaryVisualSequence ||
      row.version !== placement.expectedRowVersion ||
      row.primaryVisualSequence.version !== placement.expectedSequenceVersion ||
      row.version === Number.MAX_SAFE_INTEGER ||
      placement.expectedSequenceVersion === Number.MAX_SAFE_INTEGER) {
    return refused(document, "SEQUENCE_VERSION_STALE", "Selected narration changed.");
  }

  const ids = reservedIds(snapshot, reservedIds(document));
  const nextId = (): string => {
    const id = makeId();
    if (typeof id !== "string" || !UUID.test(id) || ids.has(id.toLowerCase())) {
      throw new RangeError("A new still needs unused UUIDs.");
    }
    ids.add(id.toLowerCase());
    return id;
  };

  try {
    const payloadId = nextId();
    const slotId = nextId();
    const mediaReferenceId = nextId();
    const payload: NarratedVisualPayloadV2 = {
      kind: "visual",
      payloadId,
      pictureKind: "image",
      source: { kind: "media_reference", mediaReferenceId },
      sourceUsage: null,
      audioPolicy: "mute",
      displayName: snapshot.title,
      researchStill: structuredClone(snapshot),
    };
    const edited = structuredClone(row);
    edited.unattachedVisuals = [...(edited.unattachedVisuals ?? []), { slotId, payload, version: 1 }];
    if (placement.kind === "selected_words") {
      const attached = attachVisualToWordsV2(edited, slotId, placement.startTokenId, placement.endTokenId);
      if (isCoverageRefusalV2(attached)) return refused(document, attached.code, attached.message);
    } else {
      edited.primaryVisualSequence!.version += 1;
    }
    edited.version += 1;
    return applyRowEditV2(document, request.expectedDocumentRevision, {
      kind: "edit_row",
      rowId: edited.id,
      row: edited,
    });
  } catch (error) {
    return refused(
      document,
      "RESEARCH_STILL_INSERT_INVALID",
      error instanceof Error ? error.message : "Cannot place this still.",
    );
  }
}
