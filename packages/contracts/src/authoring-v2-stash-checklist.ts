import type { NarrationBlockV2, ScriptDocumentV2, StashChecklistV2, StashOutlineEntryV2 } from "./generated/contracts-v2.js";

type StashRow = NonNullable<ScriptDocumentV2["stash"]>[number]["rows"][number];

/** Old saved documents never had checkboxes: omission means unchecked, with no manual history. */
export function stashChecklistV2(row: StashRow): StashChecklistV2 {
  return row.type === "narration" || row.type === "visual_only"
    ? structuredClone(row.stashChecklist ?? { completed: false, manualRevision: 0 })
    : { completed: false, manualRevision: 0 };
}

/** Exact snapshot, not a hash: an authored source or attached-footage edit cannot collide. */
export function stashNoteContentStampV2(note: NarrationBlockV2): string {
  const copy = structuredClone(note);
  delete copy.stashChecklist;
  delete copy.stashOrigin;
  return JSON.stringify(copy);
}

/** A link broken by an authored source edit stays broken even if the author
 * later restores the exact prior bytes. Completion changes are not source edits. */
export function invalidateChangedStashSourceLinksV2(before: ScriptDocumentV2, after: ScriptDocumentV2): void {
  const oldRows = new Map((before.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row] as const)));
  const newRows = new Map((after.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row] as const)));
  const changed = new Set<string>();
  for (const entry of before.stashOutline ?? []) {
    if (entry.kind !== "note") continue;
    const original = oldRows.get(entry.rowId);
    const current = newRows.get(entry.rowId);
    if (original?.type !== "narration") continue;
    if (current?.type !== "narration" || stashNoteContentStampV2(original) !== stashNoteContentStampV2(current)) {
      changed.add(entry.rowId);
    }
  }
  if (!changed.size) return;
  for (const row of after.activeDraft.blocks) {
    if (row.type === "narration" && row.stashOrigin?.sourceNoteRowId && changed.has(row.stashOrigin.sourceNoteRowId)) {
      row.stashOrigin.returnEligible = false;
    }
  }
}

/** Stable UUIDs for replay of one optimistic edit, distinct for every insertion. */
function copyUuid(seed: string, ordinal: number): string {
  const input = `${seed}:${ordinal}`;
  const pieces = [2166136261, 0x9e3779b9, 0x85ebca6b, 0xc2b2ae35].map((initial, offset) => {
    let hash = initial >>> 0;
    for (let index = 0; index < input.length; index += 1) {
      hash = Math.imul(hash ^ (input.charCodeAt(index) + offset), 16777619) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  });
  const hex = pieces.join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-8${hex.slice(17, 20)}-${hex.slice(20)}`;
}

/** Every owned identity and anchor is independent; media references still point at the same footage. */
export function copyStashNoteAsSpokenV2(note: NarrationBlockV2, seed: string): NarrationBlockV2 {
  const owned = new Map<string, string>();
  let next = 0;
  const own = (id: string | undefined): void => {
    if (id && !owned.has(id)) owned.set(id, copyUuid(seed, next++));
  };
  own(note.id);
  note.tokens.forEach((token) => own(token.id));
  own(note.primaryVisualSequence?.id);
  note.primaryVisualSequence?.slots.forEach((slot) => {
    own(slot.id);
    if (slot.kind === "content" && slot.payload.kind === "visual") own(slot.payload.payloadId);
  });
  note.overlayEvents.forEach((event) => { own(event.id); own(event.payload.payloadId); });
  note.annotations?.forEach((annotation) => own(annotation.id));
  note.performanceBeats?.forEach((beat) => own(beat.id));
  note.unattachedVisuals?.forEach((visual) => { own(visual.slotId); own(visual.payload.payloadId); });
  own(note.attachedFootage?.clip.id);
  own(note.attachedFootage?.clip.payload.payloadId);

  const identityKeys = new Set(["id", "payloadId", "slotId", "blockId", "tokenId", "startTokenId", "endTokenId", "eventId"]);
  const replace = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(replace);
    if (value === null || typeof value !== "object") return value;
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
      typeof item === "string" && identityKeys.has(key) && owned.has(item) ? owned.get(item)! : replace(item),
    ]));
  };
  const copied = replace(note) as NarrationBlockV2;
  copied.orderKey = `stash-copy-${copied.id}`;
  delete copied.stashOrigin;
  delete copied.stashChecklist;
  delete copied.plainDirection;
  // D84: copied brackets are literal spoken text, not an implicit Make stage direction.
  for (const token of copied.tokens) delete token.spoken;
  if (copied.attachedFootage) {
    delete copied.attachedFootage.clip.stashOrigin;
    delete copied.attachedFootage.clip.stashChecklist;
  }
  return copied;
}

export interface StashChecklistProjectionV2 {
  visibleRowIds: string[];
  hiddenRowIds: string[];
  hiddenNotes: number;
  hiddenClips: number;
  hiddenSavedRows: number;
  hiddenAttachedFootage: number;
}

/** Hide checked leaves, but keep a checked note as context for unfinished descendants. */
export function projectStashChecklistV2(document: ScriptDocumentV2, hideCompleted = false): StashChecklistProjectionV2 {
  const rows = new Map((document.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row] as const)));
  const outline: StashOutlineEntryV2[] = document.stashOutline ?? [
    ...(document.stash ?? []).flatMap((bundle) => bundle.rows).map((row) => ({
      rowId: row.id, kind: "row" as const, parentRowId: null, sectionId: null,
    })),
  ];
  const children = new Map<string, string[]>();
  for (const entry of outline) if (entry.parentRowId !== null) {
    children.set(entry.parentRowId, [...(children.get(entry.parentRowId) ?? []), entry.rowId]);
  }
  const visible = new Set<string>();
  const needed = (rowId: string): boolean => {
    const row = rows.get(rowId);
    if (!row) return false;
    const unfinished = !stashChecklistV2(row).completed;
    const hasUnfinishedDescendant = (children.get(rowId) ?? []).some(needed);
    if (!hideCompleted || unfinished || hasUnfinishedDescendant) visible.add(rowId);
    return unfinished || hasUnfinishedDescendant;
  };
  for (const entry of outline) if (entry.parentRowId === null) needed(entry.rowId);
  const shown = outline.filter((entry) => visible.has(entry.rowId));
  const hidden = outline.filter((entry) => !visible.has(entry.rowId));
  return {
    visibleRowIds: shown.map((entry) => entry.rowId),
    hiddenRowIds: hidden.map((entry) => entry.rowId),
    hiddenNotes: hidden.filter((entry) => entry.kind === "note").length,
    hiddenClips: hidden.filter((entry) => entry.kind === "clip").length,
    hiddenSavedRows: hidden.filter((entry) => entry.kind === "row").length,
    hiddenAttachedFootage: hidden.filter((entry) => rows.get(entry.rowId)?.type === "narration" && (rows.get(entry.rowId) as NarrationBlockV2).attachedFootage).length,
  };
}
