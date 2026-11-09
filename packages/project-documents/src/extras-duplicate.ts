import { randomUUID } from "node:crypto";
import { isDeepStrictEqual } from "node:util";

import { serializeAuthoringDocumentV2, validateScriptDocumentV2, type RowEditResultV2 } from "@vera/contracts/authoring-v2";
import type { RowGapV2, ScriptDocumentV2, SupportingItemV2 } from "@vera/contracts/v2";

type DraftBlock = ScriptDocumentV2["activeDraft"]["blocks"][number];
type SavedRow = Exclude<DraftBlock, { type: "section" }>;
type Ref = { id: string; assign: (id: string) => void };

export type ExtrasDuplicateCommand = {
  kind: "duplicate_stash_rows";
  /** Roots of consecutive sibling subtrees, or one ordinary saved row. */
  rowIds: string[];
  destination: RowGapV2;
};

const UUID = /^[a-f\d]{8}-(?:[a-f\d]{4}-){3}[a-f\d]{12}$/iu;
const fatal = new Set([
  "SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID",
  "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID", "STASH_GROUP_INVALID",
]);

function refusal(document: ScriptDocumentV2, code: string, message: string): RowEditResultV2 {
  return { ok: false, document, diagnostics: [{ code, message, jsonPath: "/stash" }] };
}

/** Only a CURRENT exact Draft gap is usable: no automatic fallback to a former sibling. */
function draftInsertion(blocks: DraftBlock[], gap: RowGapV2): number | null {
  let section: string | null = null;
  let start = 0;
  const sections: { id: string | null; start: number; end: number }[] = [];
  blocks.forEach((block, index) => {
    if (block.type === "section") {
      sections.push({ id: section, start, end: index });
      section = block.id;
      start = index + 1;
    }
  });
  sections.push({ id: section, start, end: blocks.length });
  const target = sections.find((entry) => entry.id === gap.sectionId);
  if (!target) return null;
  const rows = blocks.slice(target.start, target.end);
  for (let index = 0; index <= rows.length; index++) {
    if ((rows[index - 1]?.id ?? null) === gap.afterRowId &&
        (rows[index]?.id ?? null) === gap.beforeRowId) return target.start + index;
  }
  return null;
}

/** Explicit inventory: these, and only these, are authored identities in saved rows. */
function inventory(rows: SavedRow[], items: SupportingItemV2[]): Ref[] {
  const refs: Ref[] = [];
  const own = (obj: { id: string }, key: "id" = "id") => {
    refs.push({ id: obj[key], assign: (value) => { obj[key] = value; } });
  };
  const payload = (obj: { payloadId: string }) => {
    refs.push({ id: obj.payloadId, assign: (value) => { obj.payloadId = value; } });
  };
  const visit = (row: SavedRow): void => {
    own(row);
    if (row.type === "visual_only") {
      payload(row.payload);
    } else if (row.type === "narration") {
      row.tokens.forEach((token) => own(token));
      row.annotations?.forEach((annotation) => own(annotation));
      row.performanceBeats?.forEach((beat) => own(beat));
      if (row.primaryVisualSequence) {
        own(row.primaryVisualSequence);
        row.primaryVisualSequence.slots.forEach((slot) => {
          own(slot);
          if (slot.kind === "content" && slot.payload.kind !== "on_camera") payload(slot.payload);
        });
      }
      row.overlayEvents.forEach((event) => { own(event); payload(event.payload); });
      if (row.attachedFootage) visit(row.attachedFootage.clip);
    }
  };
  rows.forEach(visit);
  items.forEach((item) => own(item));
  return refs;
}

/** Catch unknown newly-introduced nested owned identities instead of silently aliasing them. */
function hasUnknownIdentity(value: unknown, recognized: Set<string>): boolean {
  let unknown = false;
  const walk = (obj: unknown): void => {
    if (!obj || typeof obj !== "object") return;
    for (const [key, child] of Object.entries(obj)) {
      if ((key === "id" || key === "payloadId") && typeof child === "string" && !recognized.has(child)) unknown = true;
      else if (typeof child === "object") walk(child);
    }
  };
  walk(value);
  return unknown;
}

/** Anchor variants and structural slot edges; external Research/media IDs are never rewritten. */
function remapRefs(rows: SavedRow[], items: SupportingItemV2[], ids: Map<string, string>): boolean {
  let valid = true;
  const remap = (id: string): string => {
    const newId = ids.get(id);
    if (!newId) valid = false;
    return newId ?? id;
  };
  const range = (value: { blockId: string; startTokenId: string; endTokenId: string }) => {
    value.blockId = remap(value.blockId);
    value.startTokenId = remap(value.startTokenId);
    value.endTokenId = remap(value.endTokenId);
  };
  const word = (value: { blockId: string; tokenId: string }) => {
    value.blockId = remap(value.blockId);
    value.tokenId = remap(value.tokenId);
  };
  const anchor = (value: unknown): void => {
    if (!value || typeof value !== "object" || !("kind" in value)) { valid = false; return; }
    switch (value.kind) {
      case "word":
      case "audible_word_end":
        if (!("anchor" in value) || !value.anchor || typeof value.anchor !== "object") { valid = false; return; }
        word(value.anchor as { blockId: string; tokenId: string });
        break;
      case "between_blocks": {
        const pair = value as unknown as { beforeBlockId: string; afterBlockId: string };
        pair.beforeBlockId = remap(pair.beforeBlockId);
        pair.afterBlockId = remap(pair.afterBlockId);
        break;
      }
      case "event_edge": {
        const edge = value as unknown as { eventId: string };
        edge.eventId = remap(edge.eventId);
        break;
      }
      default: valid = false;
    }
  };
  const timed = (value: { start?: unknown; end?: unknown }) => {
    if (value.start) anchor(value.start);
    if (value.end) anchor(value.end);
    if (!value.start && !value.end) valid = false; // at least one proved owner anchor
  };
  const visit = (row: SavedRow): void => {
    if (row.type !== "narration") return;
    row.annotations?.forEach((entry) => range(entry.range));
    row.performanceBeats?.forEach((entry) => range(entry.range));
    row.primaryVisualSequence?.slots.forEach((slot) => {
      if (slot.kind === "return") {
        slot.parentSlotId = remap(slot.parentSlotId);
        if (slot.inpoint) word(slot.inpoint);
      } else {
        if (slot.relation.kind === "cutaway") slot.relation.parentSlotId = remap(slot.relation.parentSlotId);
        if (slot.boundaryBefore.kind === "previous_media_end") slot.boundaryBefore.controllingSlotId = remap(slot.boundaryBefore.controllingSlotId);
        if (slot.boundaryBefore.kind === "spoken_word" || slot.boundaryBefore.kind === "audible_word_end") word(slot.boundaryBefore.anchor);
      }
    });
    row.overlayEvents.forEach((event) => timed(event.timing));
    if (row.attachedFootage) visit(row.attachedFootage.clip);
  };
  rows.forEach(visit);
  items.forEach((item) => {
    const placement = item.placement;
    if (placement.kind === "unplaced") valid = false;
    else if (placement.kind === "range") range(placement.range);
    else if (placement.kind === "point") anchor(placement.anchor);
    else timed(placement);
    if (item.displayAttachment) {
      if ("kind" in item.displayAttachment) anchor(item.displayAttachment);
      else range(item.displayAttachment);
    }
  });
  return valid;
}

/** Collect typed supporting-item row edges, including event-owned rows. */
function supportingEdges(item: SupportingItemV2, eventOwners: Map<string, string>): string[] | null {
  const result: string[] = [];
  let invalid = false;
  const walk = (value: unknown): void => {
    if (!value || typeof value !== "object") return;
    for (const [key, child] of Object.entries(value)) {
      if (["blockId", "beforeBlockId", "afterBlockId"].includes(key) && typeof child === "string") result.push(child);
      else if (key === "eventId" && typeof child === "string") {
        const row = eventOwners.get(child);
        if (!row) invalid = true;
        else result.push(row);
      } else if (typeof child === "object") walk(child);
    }
  };
  if (item.placement.kind === "unplaced" || item.placement.kind === "timed" && !item.placement.start && !item.placement.end) invalid = true;
  walk(item.placement);
  walk(item.displayAttachment);
  return invalid || !result.length ? null : result;
}

/** Saved attached clips must already have one provable, non-full-audio Draft mirror. */
function safeAttachedMirror(row: SavedRow): boolean {
  if (row.type !== "narration" || !row.attachedFootage) return true;
  const clip = row.attachedFootage.clip;
  const slot = row.primaryVisualSequence?.slots[0];
  if (clip.payload.audioPolicy === "full" || row.primaryVisualSequence?.slots.length !== 1 ||
      !slot || slot.kind !== "content" || slot.relation.kind !== "base" ||
      slot.boundaryBefore.kind !== "row_start" || slot.playoutPolicy !== "match_structural_interval" ||
      slot.payload.kind !== "visual") return false;
  const payload = slot.payload;
  const selected = clip.visualOnlyTiming.selectedSourceRange;
  return payload.pictureKind === clip.payload.pictureKind &&
    payload.audioPolicy === clip.payload.audioPolicy &&
    payload.framingPolicy === clip.payload.framingPolicy &&
    isDeepStrictEqual(payload.source, clip.payload.source) &&
    isDeepStrictEqual(payload.researchClip, clip.researchClip) &&
    isDeepStrictEqual(payload.frameBinding, clip.frameBinding) &&
    isDeepStrictEqual(payload.selectedSourceRange, selected) &&
    isDeepStrictEqual(payload.sourceUsage, selected ? { sourceInFrame: selected.startFrame } : null);
}

/** One pure Draft insertion; the original Stash, groups, outline and provenance are unchanged. */
export function duplicateExtrasRows(
  document: ScriptDocumentV2,
  command: ExtrasDuplicateCommand,
  allocateId: () => string = randomUUID,
): RowEditResultV2 {
  const preflight = validateScriptDocumentV2(document);
  if (preflight.diagnostics.some((diagnostic) => fatal.has(diagnostic.code))) {
    return refusal(document, "EXTRAS_DUPLICATE_INVALID", "Resolve invalid saved identities or references before duplication.");
  }
  const revision = document.rowEditRevision ?? 0;
  if (!Number.isSafeInteger(revision) || revision < 0 || revision === Number.MAX_SAFE_INTEGER) {
    return refusal(document, "ROW_REVISION_STALE", "The document row revision cannot advance.");
  }
  const index = draftInsertion(document.activeDraft.blocks, command.destination);
  if (index === null) return refusal(document, "ROW_DESTINATION_INVALID", "Choose an exact current Draft gap.");

  const saved = (document.stash ?? []).flatMap((bundle) => bundle.rows);
  const savedById = new Map(saved.map((row) => [row.id, row]));
  const entries = document.stashOutline ?? saved.map((row) => ({ rowId: row.id, kind: "row" as const, parentRowId: null, sectionId: null }));
  const selected = new Set<string>();
  const roots = command.rowIds.map((id) => entries.find((entry) => entry.rowId === id));
  if (roots.some((entry) => !entry)) return refusal(document, "ROW_SELECTION_INVALID", "Select existing saved rows.");
  const parent = roots[0]!.parentRowId;
  const section = roots[0]!.sectionId;
  const siblings = entries.filter((entry) => entry.parentRowId === parent && entry.sectionId === section);
  const positions = command.rowIds.map((id) => siblings.findIndex((entry) => entry.rowId === id));
  if (positions.some((pos, i) => pos < 0 || i > 0 && pos !== positions[i - 1]! + 1)) {
    return refusal(document, "ROW_SELECTION_INVALID", "Duplicate one complete branch or consecutive sibling branches.");
  }
  const children = (id: string): void => {
    if (selected.has(id)) return;
    selected.add(id);
    for (const entry of entries) if (entry.parentRowId === id) children(entry.rowId);
  };
  command.rowIds.forEach(children);
  if (command.rowIds.some((id) => entries.find((entry) => entry.rowId === id)?.parentRowId !== parent) ||
      (document.stashGroups ?? []).some((group) => group.rowIds.some((id) => selected.has(id)) && group.rowIds.some((id) => !selected.has(id)))) {
    return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "The selection crosses a saved group or branch boundary.");
  }
  const originals = entries.filter((entry) => selected.has(entry.rowId)).map((entry) => savedById.get(entry.rowId));
  if (originals.length !== selected.size || originals.some((row) => !row)) {
    return refusal(document, "ROW_SELECTION_INVALID", "The saved branch has missing rows.");
  }
  if (originals.some((row) => !safeAttachedMirror(row!))) {
    return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "Attached footage must have one exact muted or quiet visual mirror before duplication.");
  }

  const allRows = [...document.activeDraft.blocks, ...saved];
  const knownRows = new Set(allRows.map((row) => row.id));
  const eventOwners = new Map(allRows.flatMap((row) => row.type === "narration"
    ? row.overlayEvents.map((event) => [event.id, row.id] as const) : []));
  const copiedItems: SupportingItemV2[] = [];
  for (const bundle of document.stash ?? []) {
    const selectedInBundle = bundle.rows.some((row) => selected.has(row.id));
    for (const item of bundle.supportingItems) {
      const edges = supportingEdges(item, eventOwners);
      if (!edges || edges.some((id) => !knownRows.has(id))) {
        if (selectedInBundle) return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "Saved supporting items need unambiguous current anchors.");
        continue;
      }
      const touches = edges.some((id) => selected.has(id));
      if (touches && (!selectedInBundle || edges.some((id) => !selected.has(id)))) {
        return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "A citation or anchor crosses the duplicate boundary.");
      }
      if (touches) copiedItems.push(item);
    }
  }
  // Opaque row references and audio-span effects cannot safely become new authored intent.
  if ((document.rowReferences ?? []).some((ref) => selected.has(ref.rowId)) ||
      (document.rowAudioSpans ?? []).some((span) => selected.has(span.startRowId) || selected.has(span.endRowId)) ||
      (document.rowTransitions ?? []).some((pair) => selected.has(pair.fromRowId) || selected.has(pair.toRowId))) {
    return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "Review external row references and audio/transition effects before duplicating.");
  }

  try {
    const rows = structuredClone(originals as SavedRow[]);
    const items = structuredClone(copiedItems);
    rows.forEach((row) => { delete row.stashOrigin; if (row.type === "narration" && row.attachedFootage) delete row.attachedFootage.clip.stashOrigin; });
    const owned = inventory(rows, items);
    const oldIds = new Set(owned.map((entry) => entry.id));
    if (oldIds.size !== owned.length || hasUnknownIdentity(rows, oldIds) || hasUnknownIdentity(items, oldIds)) {
      return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "The selected branch contains unrecognized owned identities.");
    }
    const existing = new Set<string>();
    const collect = (value: unknown): void => {
      if (!value || typeof value !== "object") return;
      for (const [key, child] of Object.entries(value)) {
        // Never allocate an authored ID that aliases even a shared external media/source ID.
        if (typeof child === "string" && UUID.test(child) && (key === "id" || key.endsWith("Id"))) existing.add(child);
        else if (typeof child === "object") collect(child);
      }
    };
    collect(document);
    const mapping = new Map<string, string>();
    for (const ref of owned) {
      const next = allocateId();
      if (typeof next !== "string" || !UUID.test(next) || existing.has(next)) {
        return refusal(document, "EXTRAS_DUPLICATE_ID_COLLISION", "The trusted allocator returned an invalid or already-owned ID.");
      }
      existing.add(next);
      mapping.set(ref.id, next);
    }
    if (!remapRefs(rows, items, mapping)) {
      return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "An internal anchor or slot edge cannot be resolved inside the selected branch.");
    }
    owned.forEach((ref) => ref.assign(mapping.get(ref.id)!));
    const working = structuredClone(document);
    working.activeDraft.blocks.splice(index, 0, ...rows);
    working.activeDraft.supportingItems.push(...items);
    working.rowEditRevision = revision + 1;
    // Canonical validator catches stale token quotes, visual mirrors, orphan anchors and ownership.
    const savedDocument = JSON.parse(serializeAuthoringDocumentV2(working)) as ScriptDocumentV2;
    const after = validateScriptDocumentV2(savedDocument);
    if (!after.valid) {
      const reasons = after.diagnostics.filter((entry) => entry.severity !== "warning").slice(0, 3)
        .map((entry) => `${entry.code} at ${entry.jsonPath}`).join("; ");
      return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", `The duplicated Draft needs reference review: ${reasons}`);
    }
    return { ok: true, document: savedDocument, diagnostics: [] };
  } catch {
    return refusal(document, "EXTRAS_DUPLICATE_REVIEW_REQUIRED", "The selected branch cannot be cloned and validated losslessly.");
  }
}
