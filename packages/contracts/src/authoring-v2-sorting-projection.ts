import type {
  RowAudioSpanIntentV2,
  RowTransitionIntentV2,
  RowStashBundleV2,
  ScriptDocumentV2,
  StashRowGroupV2,
  StashOriginV2,
  StashOutlineEntryV2,
  SupportingItemV2,
  VisualOnlyBlockV2,
} from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { sameAuthoringJsonV2 as sameJson } from "./authoring-v2-json.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { stashGroupLocationProblemV2 } from "./authoring-v2-stash-groups.js";
import { parkAttachedFootageForSortingV2, presentAttachedFootageForSortingV2, type RowEditCommandV2, type RowEditResultV2 } from "./authoring-v2-rows.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;

type RowSlot =
  | { surface: "draft"; sectionId: string | null; afterRowId: string | null; beforeRowId: string | null }
  | {
      surface: "stash";
      bundleId: string;
      bundleOriginalGap?: RowStashBundleV2["originalGap"];
      entry: StashOutlineEntryV2;
      afterSiblingRowId: string | null;
      beforeSiblingRowId: string | null;
    };

interface Birth {
  rowId: string;
  row: Row;
  slot: RowSlot;
  lastSlot: RowSlot;
  present: boolean;
  bundleOriginalGap?: RowStashBundleV2["originalGap"];
}

interface Tombstone {
  rowId: string;
  slot: RowSlot;
  origin?: StashOriginV2;
}

interface StoredSlot {
  rowId: string;
  slot: RowSlot;
}

interface DetachedPlacement {
  noteRowId: string;
  clipRowId: string;
}

interface GroupRemoval {
  groupId: string;
  classification: "edit" | "organization";
}

interface GroupSaveBirth {
  groupId: string;
  rowId: string;
}

/** Serializable sidecar for composing the four Sorting outcomes by stable row identity. */
export interface SortingProjectionV2 {
  baseline: ScriptDocumentV2;
  births: Birth[];
  tombstones: Tombstone[];
  stableSlots: StoredSlot[];
  ghostFallbacks: StoredSlot[];
  convertedEditedIds: string[];
  identityConflicts: string[];
  /** Sorting (not content) converted a pre-existing embedded clip into a standalone row. */
  detachedPlacements: DetachedPlacement[];
  /** A removed group can be restored in sorting-only only when removal deleted authored members. */
  groupRemovals: GroupRemoval[];
  /** New authored members added by one-Save remain with baseline groups in edits-only. */
  groupSaveBirths: GroupSaveBirth[];
  /** A removed group ID cannot acquire a second, potentially unrelated meaning in one trial. */
  groupIdentityConflicts: string[];
}

const diagnostic = (code: string, message: string): AuthoringDiagnosticV2 => ({
  code,
  message,
  jsonPath: "/activeDraft",
});

function rowMap(document: ScriptDocumentV2): Map<string, Row> {
  const rows = new Map<string, Row>();
  for (const block of document.activeDraft.blocks) if (block.type !== "section") rows.set(block.id, structuredClone(block));
  for (const bundle of document.stash ?? []) for (const row of bundle.rows) rows.set(row.id, structuredClone(row));
  return rows;
}

function sectionRows(document: ScriptDocumentV2): Map<string | null, string[]> {
  const result = new Map<string | null, string[]>([[null, []]]);
  let sectionId: string | null = null;
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      sectionId = block.id;
      result.set(sectionId, []);
    } else result.get(sectionId)!.push(block.id);
  }
  return result;
}

function effectiveOutline(document: ScriptDocumentV2): StashOutlineEntryV2[] {
  if (document.stashOutline) return structuredClone(document.stashOutline);
  const rows = (document.stash ?? []).flatMap((bundle) => bundle.rows);
  const sectionForRow = new Map((document.stashSections ?? []).flatMap((section) => section.rowIds.map((rowId) => [rowId, section.id] as const)));
  const assigned = new Set(sectionForRow.keys());
  return [
    ...rows.filter((row) => !assigned.has(row.id)).map((row) => ({ rowId: row.id, kind: "row" as const, parentRowId: null, sectionId: null })),
    ...(document.stashSections ?? []).flatMap((section) => section.rowIds.flatMap((rowId) => rows.some((row) => row.id === rowId)
      ? [{ rowId, kind: "row" as const, parentRowId: null, sectionId: section.id }]
      : [])),
  ];
}

function slotFor(document: ScriptDocumentV2, rowId: string): RowSlot | null {
  const activeRows = sectionRows(document);
  for (const [sectionId, ids] of activeRows) {
    const index = ids.indexOf(rowId);
    if (index >= 0) return {
      surface: "draft",
      sectionId,
      afterRowId: ids[index - 1] ?? null,
      beforeRowId: ids[index + 1] ?? null,
    };
  }
  const entries = effectiveOutline(document);
  const index = entries.findIndex((entry) => entry.rowId === rowId);
  if (index < 0) return null;
  const entry = entries[index]!;
  const siblings = entries.filter((candidate) => candidate.parentRowId === entry.parentRowId && candidate.sectionId === entry.sectionId);
  const siblingIndex = siblings.findIndex((candidate) => candidate.rowId === rowId);
  const bundle = document.stash?.find((candidate) => candidate.rows.some((row) => row.id === rowId));
  if (!bundle) return null;
  return {
    surface: "stash",
    bundleId: bundle.id,
    ...(bundle.originalGap ? { bundleOriginalGap: structuredClone(bundle.originalGap) } : {}),
    entry: structuredClone(entry),
    afterSiblingRowId: siblings[siblingIndex - 1]?.rowId ?? null,
    beforeSiblingRowId: siblings[siblingIndex + 1]?.rowId ?? null,
  };
}

function sameSlot(left: RowSlot | undefined, right: RowSlot | undefined): boolean {
  return !!left && !!right && sameJson(left, right);
}

function slotRecords(document: ScriptDocumentV2): Map<string, RowSlot> {
  const result = new Map<string, RowSlot>();
  for (const rowId of rowMap(document).keys()) {
    const slot = slotFor(document, rowId);
    if (slot) result.set(rowId, slot);
  }
  return result;
}

function subtreeRows(document: ScriptDocumentV2, roots: string[]): string[] {
  const entries = effectiveOutline(document);
  const byId = new Map(entries.map((entry) => [entry.rowId, entry]));
  const rootSet = new Set(roots);
  const isDescendant = (rowId: string, root: string): boolean => {
    let parent = byId.get(rowId)?.parentRowId ?? null;
    while (parent !== null) {
      if (parent === root) return true;
      parent = byId.get(parent)?.parentRowId ?? null;
    }
    return false;
  };
  return entries.filter((entry) => rootSet.has(entry.rowId) || roots.some((root) => isDescendant(entry.rowId, root))).map((entry) => entry.rowId);
}

function selectedRows(document: ScriptDocumentV2, command: RowEditCommandV2): string[] {
  switch (command.kind) {
    case "move_rows":
    case "stash_rows":
    case "restore_stash_rows":
    case "move_stash_rows":
    case "stash_group_rows":
    case "group_stash_rows":
      return command.rowIds;
    case "move_stash_group":
    case "ungroup_stash_group":
    case "delete_stash_group":
    case "place_stash_group":
      return document.stashGroups?.find((group) => group.id === command.groupId)?.rowIds ?? [];
    case "save_stash_group":
      return [...new Set([...(document.stashGroups?.find((group) => group.id === command.groupId)?.rowIds ?? []),
        ...command.members.map((member) => member.id)])];
    case "place_stash_rows":
      return subtreeRows(document, command.rowIds);
    case "restore_stash":
      return document.stash?.find((bundle) => bundle.id === command.bundleId)?.rows.map((row) => row.id) ?? [];
    case "move_section": {
      let sectionId: string | null = null;
      return document.activeDraft.blocks.flatMap((block) => {
        if (block.type === "section") sectionId = block.id;
        return block.type !== "section" && sectionId === command.sectionId ? [block.id] : [];
      });
    }
    case "set_stash_outline": {
      const before = slotRecords(document);
      const afterIds = command.entries.map((entry) => entry.rowId);
      return afterIds.filter((rowId) => {
        const nextEntry = command.entries.find((entry) => entry.rowId === rowId)!;
        const oldSlot = before.get(rowId);
        return !oldSlot || oldSlot.surface !== "stash" || oldSlot.entry.parentRowId !== nextEntry.parentRowId ||
          oldSlot.entry.sectionId !== nextEntry.sectionId || oldSlot.entry.kind !== nextEntry.kind ||
          oldSlot.afterSiblingRowId !== (command.entries.filter((entry) => entry.parentRowId === nextEntry.parentRowId && entry.sectionId === nextEntry.sectionId)[command.entries.filter((entry) => entry.parentRowId === nextEntry.parentRowId && entry.sectionId === nextEntry.sectionId).findIndex((entry) => entry.rowId === rowId) - 1]?.rowId ?? null) ||
          oldSlot.beforeSiblingRowId !== (command.entries.filter((entry) => entry.parentRowId === nextEntry.parentRowId && entry.sectionId === nextEntry.sectionId)[command.entries.filter((entry) => entry.parentRowId === nextEntry.parentRowId && entry.sectionId === nextEntry.sectionId).findIndex((entry) => entry.rowId === rowId) + 1]?.rowId ?? null);
      });
    }
    default:
      return [];
  }
}

function destinationRows(command: RowEditCommandV2): string[] {
  switch (command.kind) {
    case "move_rows":
    case "restore_stash_rows":
    case "place_stash_rows":
    case "place_stash_group":
    case "move_stash_group":
    case "create_row":
      return command.kind === "move_stash_group" ? [command.afterRowId].filter((id): id is string => id !== null) :
        [command.destination.afterRowId, command.destination.beforeRowId].filter((id): id is string => id !== null);
    default:
      return [];
  }
}

export function createSortingProjectionV2(baseline: ScriptDocumentV2): SortingProjectionV2 {
  const snapshot = structuredClone(baseline);
  const stableSlots = [...slotRecords(snapshot)].map(([rowId, slot]) => ({ rowId, slot }));
  return { baseline: snapshot, births: [], tombstones: [], stableSlots, ghostFallbacks: [], convertedEditedIds: [], identityConflicts: [], detachedPlacements: [], groupRemovals: [], groupSaveBirths: [], groupIdentityConflicts: [] };
}

/** Record identities and placement causes after a successful public operation; never replays it. */
export function updateSortingProjectionV2(
  state: SortingProjectionV2,
  before: ScriptDocumentV2,
  after: ScriptDocumentV2,
  command: RowEditCommandV2,
): SortingProjectionV2 {
  const next = structuredClone(state);
  const beforeRows = rowMap(before);
  const afterRows = rowMap(after);
  const beforeSlots = slotRecords(before);
  const afterSlots = slotRecords(after);
  const baselineRows = rowMap(next.baseline);

  if (command.kind === "save_stash_group") {
    for (const member of command.members) {
      if (!beforeRows.has(member.id) && !next.groupSaveBirths.some((item) => item.rowId === member.id)) {
        next.groupSaveBirths.push({ groupId: command.groupId, rowId: member.id });
      }
    }
  }
  const priorGroupIds = new Set((before.stashGroups ?? []).map((group) => group.id));
  const remainingGroupIds = new Set((after.stashGroups ?? []).map((group) => group.id));
  for (const groupId of priorGroupIds) {
    if (remainingGroupIds.has(groupId)) continue;
    const classification = command.kind === "delete_stash_group" || command.kind === "save_stash_group" ? "edit" : "organization";
    next.groupRemovals = [...next.groupRemovals.filter((item) => item.groupId !== groupId), { groupId, classification }];
  }
  for (const groupId of remainingGroupIds) {
    if (!priorGroupIds.has(groupId) && next.groupRemovals.some((item) => item.groupId === groupId)) {
      next.groupIdentityConflicts = [...new Set([...next.groupIdentityConflicts, groupId])];
    }
    next.groupRemovals = next.groupRemovals.filter((item) => item.groupId !== groupId);
  }

  if (command.kind === "place_attached_footage") {
    const note = beforeRows.get(command.noteRowId);
    const original = baselineRows.get(command.noteRowId);
    const clipId = note?.type === "narration" ? note.attachedFootage?.clip.id : undefined;
    if (clipId && original?.type === "narration" && original.attachedFootage?.clip.id === clipId &&
      !next.detachedPlacements.some((item) => item.clipRowId === clipId)) {
      next.detachedPlacements.push({ noteRowId: command.noteRowId, clipRowId: clipId });
    }
  }

  for (const [rowId, row] of afterRows) {
    if (beforeRows.has(rowId)) continue;
    const oldBirth = next.births.find((birth) => birth.rowId === rowId);
    if (oldBirth) {
      if (!oldBirth.present) next.identityConflicts = [...new Set([...next.identityConflicts, rowId])];
      continue;
    }
    if (baselineRows.has(rowId)) {
      if (next.tombstones.some((tombstone) => tombstone.rowId === rowId)) next.identityConflicts = [...new Set([...next.identityConflicts, rowId])];
      continue;
    }
    const slot = afterSlots.get(rowId);
    if (!slot) continue;
    next.births.push({
      rowId,
      row: structuredClone(row),
      slot: structuredClone(slot),
      lastSlot: structuredClone(slot),
      present: true,
      ...(slot.surface === "stash" && slot.bundleOriginalGap ? { bundleOriginalGap: structuredClone(slot.bundleOriginalGap) } : {}),
    });
  }

  for (const rowId of beforeRows.keys()) {
    if (afterRows.has(rowId)) continue;
    const birthIndex = next.births.findIndex((birth) => birth.rowId === rowId);
    if (birthIndex >= 0) {
      next.births[birthIndex]!.present = false;
      const lastSlot = beforeSlots.get(rowId);
      if (lastSlot) next.births[birthIndex]!.lastSlot = structuredClone(lastSlot);
      continue;
    }
    if (baselineRows.has(rowId) && !next.tombstones.some((tombstone) => tombstone.rowId === rowId)) {
      const slot = beforeSlots.get(rowId);
      const origin = beforeRows.get(rowId)?.stashOrigin;
      if (slot) next.tombstones.push({ rowId, slot: structuredClone(slot), ...(origin ? { origin: structuredClone(origin) } : {}) });
    }
  }

  const selected = new Set(selectedRows(before, command));
  const bornIds = new Set(next.births.map((birth) => birth.rowId));
  const targets = destinationRows(command);
  const commandGhostTarget = targets.length > 0 && targets.every((rowId) => bornIds.has(rowId));
  for (const rowId of selected) {
    const oldSlot = beforeSlots.get(rowId);
    const newSlot = afterSlots.get(rowId);
    if (!oldSlot || !newSlot || sameSlot(oldSlot, newSlot)) continue;
    if (bornIds.has(rowId)) {
      const birth = next.births.find((item) => item.rowId === rowId);
      if (birth) birth.lastSlot = structuredClone(newSlot);
      continue;
    }
    const stable = next.stableSlots.find((item) => item.rowId === rowId)?.slot ?? oldSlot;
    const ghostTarget = commandGhostTarget || ["set_stash_outline", "move_stash_group"].includes(command.kind) && slotDependsOnBirth(newSlot, bornIds);
    if (ghostTarget) {
      if (!next.ghostFallbacks.some((item) => item.rowId === rowId)) next.ghostFallbacks.push({ rowId, slot: structuredClone(stable) });
    } else {
      const stableRecord = next.stableSlots.find((item) => item.rowId === rowId);
      if (stableRecord) stableRecord.slot = structuredClone(newSlot);
      else next.stableSlots.push({ rowId, slot: structuredClone(newSlot) });
      next.ghostFallbacks = next.ghostFallbacks.filter((item) => item.rowId !== rowId);
    }
  }

  const editedRowId = command.kind === "edit_row" ? command.rowId :
    "blockId" in command && typeof command.blockId === "string" ? command.blockId : undefined;
  if (editedRowId && beforeSlots.get(editedRowId)?.surface === "draft" && beforeRows.get(editedRowId)?.stashOrigin) {
    if (!next.convertedEditedIds.includes(editedRowId)) next.convertedEditedIds.push(editedRowId);
  }

  return next;
}

function slotDependsOnBirth(slot: RowSlot, births: Set<string>): boolean {
  if (slot.surface === "stash" && slot.entry.parentRowId !== null && births.has(slot.entry.parentRowId)) return true;
  const anchors = slot.surface === "draft"
    ? [slot.afterRowId, slot.beforeRowId].filter((id): id is string => id !== null)
    : [slot.afterSiblingRowId, slot.beforeSiblingRowId].filter((id): id is string => id !== null);
  return anchors.length > 0 && anchors.every((id) => births.has(id));
}

function ensureOutline(document: ScriptDocumentV2): StashOutlineEntryV2[] {
  if (!document.stashOutline) {
    document.stashOutline = effectiveOutline(document);
    if (document.stashSections) document.stashSections = document.stashSections.map((section) => ({ ...section, rowIds: [] }));
  }
  return document.stashOutline;
}

function outlineSubtreeEnd(entries: StashOutlineEntryV2[], rowId: string): number {
  const byId = new Map(entries.map((entry) => [entry.rowId, entry]));
  const isDescendant = (entry: StashOutlineEntryV2): boolean => {
    let parent = entry.parentRowId;
    while (parent !== null) {
      if (parent === rowId) return true;
      parent = byId.get(parent)?.parentRowId ?? null;
    }
    return false;
  };
  let end = entries.findIndex((entry) => entry.rowId === rowId);
  for (let index = end + 1; index < entries.length; index += 1) if (isDescendant(entries[index]!)) end = index;
  return end;
}

function insertOutlineEntry(document: ScriptDocumentV2, slot: Extract<RowSlot, { surface: "stash" }>): boolean {
  const entries = ensureOutline(document);
  const siblings = entries.filter((entry) => entry.parentRowId === slot.entry.parentRowId && entry.sectionId === slot.entry.sectionId);
  const afterIndex = slot.afterSiblingRowId === null ? -1 : siblings.findIndex((entry) => entry.rowId === slot.afterSiblingRowId);
  const beforeIndex = slot.beforeSiblingRowId === null ? -1 : siblings.findIndex((entry) => entry.rowId === slot.beforeSiblingRowId);
  if (slot.entry.sectionId !== null && !(document.stashSections ?? []).some((section) => section.id === slot.entry.sectionId)) return false;
  if (slot.entry.parentRowId !== null) {
    const parent = entries.find((entry) => entry.rowId === slot.entry.parentRowId);
    if (!parent || parent.kind !== "note" || parent.sectionId !== slot.entry.sectionId) return false;
  }
  if (slot.afterSiblingRowId !== null && afterIndex < 0 || slot.beforeSiblingRowId !== null && beforeIndex < 0) return false;
  if (afterIndex >= 0 && beforeIndex >= 0 && beforeIndex !== afterIndex + 1) return false;
  if (afterIndex < 0 && beforeIndex >= 0 && beforeIndex !== 0) return false;
  if (afterIndex >= 0 && beforeIndex < 0 && afterIndex !== siblings.length - 1) return false;
  if (afterIndex < 0 && beforeIndex < 0 && siblings.length > 0) return false;

  let insertAt: number;
  if (afterIndex >= 0) insertAt = outlineSubtreeEnd(entries, slot.afterSiblingRowId!) + 1;
  else if (beforeIndex >= 0) insertAt = entries.findIndex((entry) => entry.rowId === slot.beforeSiblingRowId);
  else if (slot.entry.parentRowId !== null) insertAt = outlineSubtreeEnd(entries, slot.entry.parentRowId) + 1;
  else {
    const sectionOrder = (sectionId: string | null) => sectionId === null ? -1 : (document.stashSections ?? []).findIndex((section) => section.id === sectionId);
    const targetOrder = sectionOrder(slot.entry.sectionId);
    const nextSection = entries.findIndex((entry) => entry.parentRowId === null && sectionOrder(entry.sectionId) > targetOrder);
    insertAt = nextSection < 0 ? entries.length : nextSection;
  }
  entries.splice(insertAt, 0, structuredClone(slot.entry));
  return true;
}

function draftGapIndex(document: ScriptDocumentV2, slot: Extract<RowSlot, { surface: "draft" }>): number | null {
  const blocks = document.activeDraft.blocks;
  const sectionStart = slot.sectionId === null ? 0 : blocks.findIndex((block) => block.type === "section" && block.id === slot.sectionId) + 1;
  if (sectionStart < 0 || slot.sectionId !== null && !blocks.some((block) => block.type === "section" && block.id === slot.sectionId)) return null;
  let sectionEnd = blocks.length;
  if (slot.sectionId === null) sectionEnd = blocks.findIndex((block) => block.type === "section") < 0 ? blocks.length : blocks.findIndex((block) => block.type === "section");
  else {
    const nextSection = blocks.findIndex((block, index) => index >= sectionStart && block.type === "section");
    if (nextSection >= 0) sectionEnd = nextSection;
  }
  const rows = blocks.slice(sectionStart, sectionEnd).filter((block) => block.type !== "section");
  const gap = rows.findIndex((row, index) => (rows[index - 1]?.id ?? null) === slot.afterRowId && row.id === slot.beforeRowId);
  if (gap >= 0) return sectionStart + gap;
  if (slot.beforeRowId === null && (rows.at(-1)?.id ?? null) === slot.afterRowId) return sectionEnd;
  if (slot.afterRowId === null && (rows[0]?.id ?? null) === slot.beforeRowId) return sectionStart;
  if (slot.afterRowId === null && slot.beforeRowId === null && rows.length === 0) return sectionStart;
  return null;
}

function removeRow(document: ScriptDocumentV2, rowId: string): Row | null {
  const index = document.activeDraft.blocks.findIndex((block) => block.id === rowId && block.type !== "section");
  if (index >= 0) return document.activeDraft.blocks.splice(index, 1)[0] as Row;
  const bundle = document.stash?.find((item) => item.rows.some((row) => row.id === rowId));
  if (!bundle) return null;
  const rowIndex = bundle.rows.findIndex((row) => row.id === rowId);
  const [row] = bundle.rows.splice(rowIndex, 1);
  if (document.stashOutline) document.stashOutline = document.stashOutline.filter((entry) => entry.rowId !== rowId);
  if (document.stashSections) document.stashSections = document.stashSections.map((section) => ({ ...section, rowIds: section.rowIds.filter((id) => id !== rowId) }));
  if (bundle.rows.length === 0) document.stash = document.stash!.filter((item) => item !== bundle);
  return row ?? null;
}

function addRow(document: ScriptDocumentV2, row: Row, slot: RowSlot): boolean {
  const working = structuredClone(document);
  if (slot.surface === "draft") {
    const index = draftGapIndex(working, slot);
    if (index === null) return false;
    working.activeDraft.blocks.splice(index, 0, structuredClone(row));
    Object.assign(document, working);
    return true;
  }
  const existing = working.stash?.find((bundle) => bundle.id === slot.bundleId);
  if (existing?.rows.some((item) => item.id === row.id)) return false;
  if (!insertOutlineEntry(working, slot)) return false;
  if (existing) {
    existing.rows.push(structuredClone(row));
  } else {
    (working.stash ??= []).push({
      id: slot.bundleId,
      rows: [structuredClone(row)],
      supportingItems: [],
      ...(slot.bundleOriginalGap ? { originalGap: structuredClone(slot.bundleOriginalGap) } : {}),
    });
  }
  Object.assign(document, working);
  return true;
}

function moveRow(document: ScriptDocumentV2, rowId: string, slot: RowSlot): boolean {
  const working = structuredClone(document);
  const row = removeRow(working, rowId);
  if (!row) return false;
  const clean = structuredClone(row);
  if (slot.surface === "stash") delete clean.stashOrigin;
  if (!addRow(working, clean, slot)) return false;
  Object.assign(document, working);
  return true;
}

function uniqueOrder(nodes: string[], constraints: [string, string][], ignoredIds: ReadonlySet<string> = new Set()): string[] | null {
  const present = new Set(nodes);
  if (present.size !== nodes.length) return null;
  const outgoing = new Map(nodes.map((id) => [id, new Set<string>()]));
  const incoming = new Map(nodes.map((id) => [id, 0]));
  for (const [before, after] of constraints) {
    if (!present.has(before) || !present.has(after) || before === after) return null;
    const edges = outgoing.get(before)!;
    if (edges.has(after)) continue;
    edges.add(after);
    incoming.set(after, incoming.get(after)! + 1);
  }
  const remaining = new Set(nodes);
  const result: string[] = [];
  while (remaining.size > 0) {
    const ready = [...remaining].filter((id) => incoming.get(id) === 0);
    const hiddenReady = ready.filter((id) => ignoredIds.has(id));
    const next = hiddenReady.length > 0 ? hiddenReady : ready;
    if (next.length === 0 || hiddenReady.length === 0 && next.length !== 1) return null;
    for (const id of next) {
      result.push(id);
      remaining.delete(id);
      for (const child of outgoing.get(id)!) incoming.set(child, incoming.get(child)! - 1);
    }
  }
  return result;
}

function restoreDraftBatch(document: ScriptDocumentV2, rows: Map<string, Row>, tombstones: Tombstone[], ignoredIds: ReadonlySet<string>): boolean {
  interface Segment { sectionId: string | null; heading?: Extract<Block, { type: "section" }>; rows: Row[] }
  const segments: Segment[] = [{ sectionId: null, rows: [] }];
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") segments.push({ sectionId: block.id, heading: block, rows: [] });
    else segments[segments.length - 1]!.rows.push(block);
  }
  const groups = new Map<string | null, Tombstone[]>();
  for (const tombstone of tombstones) {
    if (tombstone.slot.surface !== "draft") return false;
    const group = groups.get(tombstone.slot.sectionId) ?? [];
    group.push(tombstone);
    groups.set(tombstone.slot.sectionId, group);
  }
  const rebuilt: Block[] = [];
  for (const segment of segments) {
    if (segment.heading) rebuilt.push(segment.heading);
    const group = groups.get(segment.sectionId);
    if (!group?.length) { rebuilt.push(...segment.rows); continue; }
    const nodes = [...segment.rows.map((row) => row.id), ...group.map((item) => item.rowId)];
    const constraints: [string, string][] = [];
    for (let index = 1; index < segment.rows.length; index += 1) constraints.push([segment.rows[index - 1]!.id, segment.rows[index]!.id]);
    for (const tombstone of group) {
      const slot = tombstone.slot;
      if (slot.surface !== "draft" || slot.sectionId !== segment.sectionId) return false;
      if (slot.afterRowId !== null) constraints.push([slot.afterRowId, tombstone.rowId]);
      if (slot.beforeRowId !== null) constraints.push([tombstone.rowId, slot.beforeRowId]);
    }
    const order = uniqueOrder(nodes, constraints, ignoredIds);
    if (!order) return false;
    const byId = new Map(segment.rows.map((row) => [row.id, row]));
    for (const tombstone of group) {
      const row = rows.get(tombstone.rowId);
      if (!row) return false;
      byId.set(tombstone.rowId, structuredClone(row));
    }
    rebuilt.push(...order.map((rowId) => byId.get(rowId)!));
    groups.delete(segment.sectionId);
  }
  if (groups.size > 0) return false;
  document.activeDraft.blocks = rebuilt;
  return true;
}

function restoreStashSiblingBatch(document: ScriptDocumentV2, rows: Map<string, Row>, group: Tombstone[], ignoredIds: ReadonlySet<string>): boolean {
  const first = group[0]!.slot;
  if (first.surface !== "stash") return false;
  const sectionId = first.entry.sectionId;
  const parentRowId = first.entry.parentRowId;
  if (group.some((item) => item.slot.surface !== "stash" || item.slot.entry.sectionId !== sectionId || item.slot.entry.parentRowId !== parentRowId)) return false;
  if (sectionId !== null && !(document.stashSections ?? []).some((section) => section.id === sectionId)) return false;
  const entries = ensureOutline(document);
  if (parentRowId !== null && !entries.some((entry) => entry.rowId === parentRowId)) return false;
  const siblings = entries.filter((entry) => entry.parentRowId === parentRowId && entry.sectionId === sectionId);
  const nodes = [...siblings.map((entry) => entry.rowId), ...group.map((item) => item.rowId)];
  const constraints: [string, string][] = [];
  for (let index = 1; index < siblings.length; index += 1) constraints.push([siblings[index - 1]!.rowId, siblings[index]!.rowId]);
  for (const tombstone of group) {
    const slot = tombstone.slot;
    if (slot.surface !== "stash") return false;
    for (const anchor of [slot.afterSiblingRowId, slot.beforeSiblingRowId]) {
      if (anchor !== null && !nodes.includes(anchor)) return false;
    }
    if (slot.afterSiblingRowId !== null) constraints.push([slot.afterSiblingRowId, tombstone.rowId]);
    if (slot.beforeSiblingRowId !== null) constraints.push([tombstone.rowId, slot.beforeSiblingRowId]);
  }
  const order = uniqueOrder(nodes, constraints, ignoredIds);
  if (!order) return false;

  const chunks = new Map<string, StashOutlineEntryV2[]>();
  for (const sibling of siblings) {
    const start = entries.findIndex((entry) => entry.rowId === sibling.rowId);
    const end = outlineSubtreeEnd(entries, sibling.rowId);
    chunks.set(sibling.rowId, entries.slice(start, end + 1));
  }
  for (const tombstone of group) {
    const slot = tombstone.slot;
    if (slot.surface !== "stash") return false;
    chunks.set(tombstone.rowId, [structuredClone(slot.entry)]);
  }
  const removeIds = new Set<string>();
  for (const sibling of siblings) for (const entry of chunks.get(sibling.rowId)!) removeIds.add(entry.rowId);
  const remaining = entries.filter((entry) => !removeIds.has(entry.rowId));
  let insertAt: number;
  if (parentRowId !== null) {
    const parentIndex = remaining.findIndex((entry) => entry.rowId === parentRowId);
    if (parentIndex < 0) return false;
    insertAt = parentIndex + 1;
  } else {
    const sectionOrder = (id: string | null) => id === null ? -1 : (document.stashSections ?? []).findIndex((section) => section.id === id);
    const targetOrder = sectionOrder(sectionId);
    const nextSection = remaining.findIndex((entry) => entry.parentRowId === null && sectionOrder(entry.sectionId) > targetOrder);
    insertAt = nextSection < 0 ? remaining.length : nextSection;
  }
  remaining.splice(insertAt, 0, ...order.flatMap((rowId) => chunks.get(rowId)!));
  document.stashOutline = remaining;

  for (const rowId of order) {
    const tombstone = group.find((item) => item.rowId === rowId);
    if (!tombstone) continue;
    const row = rows.get(tombstone.rowId);
    const slot = tombstone.slot;
    if (!row || slot.surface !== "stash") return false;
    const cleanRow = structuredClone(row);
    delete cleanRow.stashOrigin;
    const existing = document.stash?.find((bundle) => bundle.id === slot.bundleId);
    if (existing) {
      if (existing.rows.some((item) => item.id === tombstone.rowId)) return false;
      existing.rows.push(cleanRow);
    } else {
      (document.stash ??= []).push({
        id: slot.bundleId,
        rows: [cleanRow],
        supportingItems: [],
        ...(slot.bundleOriginalGap ? { originalGap: structuredClone(slot.bundleOriginalGap) } : {}),
      });
    }
  }
  return true;
}

function restoreStashBatch(document: ScriptDocumentV2, rows: Map<string, Row>, tombstones: Tombstone[], ignoredIds: ReadonlySet<string>): boolean {
  const pending = [...tombstones];
  while (pending.length > 0) {
    const entries = effectiveOutline(document);
    const ready = pending.filter((item) => stashParentReady(item.slot, entries));
    if (ready.length === 0) return false;
    const groups = new Map<string, Tombstone[]>();
    for (const item of ready) {
      if (item.slot.surface !== "stash") return false;
      const key = `${item.slot.entry.sectionId ?? ""}\0${item.slot.entry.parentRowId ?? ""}`;
      const group = groups.get(key) ?? [];
      group.push(item);
      groups.set(key, group);
    }
    for (const group of groups.values()) {
      if (!restoreStashSiblingBatch(document, rows, group, ignoredIds)) return false;
      const restoredIds = new Set(group.map((item) => item.rowId));
      for (let index = pending.length - 1; index >= 0; index -= 1) if (restoredIds.has(pending[index]!.rowId)) pending.splice(index, 1);
    }
  }
  return true;
}

function stashParentReady(slot: RowSlot, entries: StashOutlineEntryV2[]): boolean {
  return slot.surface === "stash" && (slot.entry.parentRowId === null || entries.some((entry) => entry.rowId === slot.entry.parentRowId));
}

function restoreTombstoneBatches(document: ScriptDocumentV2, rows: Map<string, Row>, tombstones: Tombstone[], ignoredIds: ReadonlySet<string> = new Set()): boolean {
  const draft = tombstones.filter((item) => item.slot.surface === "draft");
  const stash = tombstones.filter((item) => item.slot.surface === "stash");
  if (draft.length > 0 && !restoreDraftBatch(document, rows, draft, ignoredIds)) return false;
  if (stash.length > 0 && !restoreStashBatch(document, rows, stash, ignoredIds)) return false;
  return true;
}

function slotRowReferences(slot: RowSlot): string[] {
  if (slot.surface === "draft") return [slot.afterRowId, slot.beforeRowId].filter((id): id is string => id !== null);
  return [slot.entry.parentRowId, slot.afterSiblingRowId, slot.beforeSiblingRowId].filter((id): id is string => id !== null);
}

function deletedBirthDependencies(state: SortingProjectionV2, slots: RowSlot[], dependencyPlacement: "birth" | "last"): Birth[] {
  const births = new Map(state.births.map((birth) => [birth.rowId, birth]));
  const needed = new Set<string>();
  const pending = slots.flatMap(slotRowReferences);
  while (pending.length > 0) {
    const rowId = pending.pop()!;
    const birth = births.get(rowId);
    if (!birth || birth.present || needed.has(rowId)) continue;
    needed.add(rowId);
    pending.push(...slotRowReferences(dependencyPlacement === "birth" ? birth.slot : birth.lastSlot));
  }
  return state.births.filter((birth) => needed.has(birth.rowId));
}

function editsOnlyBirths(state: SortingProjectionV2): Birth[] {
  const present = state.births.filter((birth) => birth.present);
  const dependencies = deletedBirthDependencies(state, present.map((birth) => birth.slot), "birth");
  const selected = new Set([...present, ...dependencies].map((birth) => birth.rowId));
  return state.births.filter((birth) => selected.has(birth.rowId));
}

function contentRow(row: Row): Row {
  const copy = structuredClone(row);
  delete copy.stashOrigin;
  return copy;
}

function rowsByLocation(document: ScriptDocumentV2): Map<string, RowSlot> {
  return slotRecords(document);
}

function originForSlot(slot: Extract<RowSlot, { surface: "stash" }>): StashOriginV2 {
  return {
    kind: slot.entry.kind,
    parentRowId: slot.entry.parentRowId,
    sectionId: slot.entry.sectionId,
    afterSiblingRowId: slot.afterSiblingRowId,
    beforeSiblingRowId: slot.beforeSiblingRowId,
    returnEligible: true,
  };
}

function normalizeRowForLocation(
  row: Row,
  rowId: string,
  slot: RowSlot,
  baseline: ScriptDocumentV2,
  baselineSlot: RowSlot | undefined,
  changed: boolean,
  mode: "edits_only" | "sorting_only",
  layoutOrigin?: StashOriginV2,
): Row {
  const result = structuredClone(row);
  if (slot.surface === "stash") {
    delete result.stashOrigin;
  } else if (mode === "sorting_only") {
    const original = rowMap(baseline).get(rowId);
    const origin = layoutOrigin ?? original?.stashOrigin ?? (baselineSlot?.surface === "stash" ? originForSlot(baselineSlot) : undefined);
    if (origin) result.stashOrigin = {
      ...structuredClone(origin),
      kind: baselineSlot?.surface === "stash" ? baselineSlot.entry.kind : original?.stashOrigin?.kind ?? origin.kind,
      returnEligible: baselineSlot?.surface === "stash" ? true : original?.stashOrigin?.returnEligible ?? true,
    };
    else delete result.stashOrigin;
  } else {
    const original = rowMap(baseline).get(rowId);
    if (original?.stashOrigin) result.stashOrigin = { ...original.stashOrigin, returnEligible: changed ? false : original.stashOrigin.returnEligible };
    else if (changed && result.stashOrigin) result.stashOrigin.returnEligible = false;
    else if (!original?.stashOrigin) delete result.stashOrigin;
  }
  return result;
}

function sourceAttachedClip(document: ScriptDocumentV2, noteId: string, clipId: string): VisualOnlyBlockV2 | undefined {
  const row = rowMap(document).get(noteId);
  return row?.type === "narration" && row.attachedFootage?.clip.id === clipId ? row.attachedFootage.clip : undefined;
}

function clipOwnershipIds(document: ScriptDocumentV2): Set<string> {
  const ids = new Set<string>();
  for (const row of rowMap(document).values()) {
    if (row.type === "visual_only") ids.add(row.id);
    if (row.type === "narration" && row.attachedFootage) ids.add(row.attachedFootage.clip.id);
  }
  return ids;
}

function reconcileAttachmentPresentation(row: Row, slot: RowSlot): Row | null {
  if (row.type !== "narration" || !row.attachedFootage) return row;
  const copy = structuredClone(row);
  const visual = copy.primaryVisualSequence?.slots[0];
  if (copy.primaryVisualSequence?.slots.length !== 1 || visual?.kind !== "content") return null;
  if (slot.surface === "draft" && visual.payload.kind === "on_camera" && !presentAttachedFootageForSortingV2(copy)) return null;
  if (slot.surface === "stash" && visual.payload.kind === "visual" && !parkAttachedFootageForSortingV2(copy)) return null;
  return copy;
}

function supportingRows(item: SupportingItemV2, rows: Row[]): Set<string> {
  const result = new Set<string>();
  const visit = (value: unknown): void => {
    if (!value || typeof value !== "object") return;
    for (const [key, child] of Object.entries(value)) {
      if (["blockId", "beforeBlockId", "afterBlockId"].includes(key) && typeof child === "string") result.add(child);
      else if (key === "eventId" && typeof child === "string") {
        const owner = rows.find((row) => row.type === "narration" && row.overlayEvents.some((event) => event.id === child));
        result.add(owner?.id ?? child);
      } else visit(child);
    }
  };
  visit(item.placement);
  visit(item.displayAttachment);
  return result;
}

interface LocatedItem { item: SupportingItemV2; bundleId: string | null }

function supportingItems(document: ScriptDocumentV2): Map<string, LocatedItem> {
  const result = new Map<string, LocatedItem>();
  for (const item of document.activeDraft.supportingItems) result.set(item.id, { item: structuredClone(item), bundleId: null });
  for (const bundle of document.stash ?? []) for (const item of bundle.supportingItems) result.set(item.id, { item: structuredClone(item), bundleId: bundle.id });
  return result;
}

function routeSupportingItems(
  output: ScriptDocumentV2,
  baseline: ScriptDocumentV2,
  current: ScriptDocumentV2,
  mode: "edits_only" | "sorting_only",
  droppedIds: Set<string>,
): string | null {
  const baselineItems = supportingItems(baseline);
  const currentItems = supportingItems(current);
  const selected = mode === "edits_only" ? currentItems : baselineItems;
  const outputSlots = rowsByLocation(output);
  output.activeDraft.supportingItems = [];
  for (const bundle of output.stash ?? []) bundle.supportingItems = [];
  for (const [id, located] of selected) {
    const refs = supportingRows(located.item, [...rowMap(baseline).values(), ...rowMap(current).values()]);
    const missing = [...refs].filter((rowId) => !outputSlots.has(rowId));
    if (missing.length > 0) {
      if (missing.every((rowId) => droppedIds.has(rowId)) && missing.length === refs.size) continue;
      return `Supporting item ${id} points to a row that the selected result removes.`;
    }
    let owner: string | null | undefined;
    if (refs.size > 0) {
      for (const rowId of refs) {
        const slot = outputSlots.get(rowId)!;
        const nextOwner = slot.surface === "draft" ? null : slot.bundleId;
        if (owner !== undefined && owner !== nextOwner) return `Supporting item ${id} crosses rows that the selected result places in different locations.`;
        owner = nextOwner;
      }
    } else {
      owner = located.bundleId;
      if (owner !== null && !output.stash?.some((bundle) => bundle.id === owner)) return `Supporting item ${id} has no row anchor and its saved Stash bundle no longer exists.`;
    }
    if (owner === undefined || owner === null) output.activeDraft.supportingItems.push(structuredClone(located.item));
    else {
      const bundle = output.stash?.find((candidate) => candidate.id === owner);
      if (!bundle) return `Supporting item ${id} has no unambiguous saved Stash bundle.`;
      bundle.supportingItems.push(structuredClone(located.item));
    }
  }
  return null;
}

function mergeById<T extends { id: string }>(baseline: T[] | undefined, current: T[] | undefined, useCurrent: boolean): T[] {
  const result = new Map((baseline ?? []).map((item) => [item.id, structuredClone(item)]));
  for (const item of current ?? []) if (useCurrent || !result.has(item.id)) result.set(item.id, structuredClone(item));
  return [...result.values()];
}

function applyRelationships(output: ScriptDocumentV2, baseline: ScriptDocumentV2, current: ScriptDocumentV2, mode: "edits_only" | "sorting_only"): void {
  const useCurrent = mode === "sorting_only";
  const rows = rowMap(output);
  const transitions = mergeById<RowTransitionIntentV2>(baseline.rowTransitions, current.rowTransitions, useCurrent);
  const spans = mergeById<RowAudioSpanIntentV2>(baseline.rowAudioSpans, current.rowAudioSpans, useCurrent);
  const references = mergeById<NonNullable<ScriptDocumentV2["rowReferences"]>[number]>(baseline.rowReferences, current.rowReferences, true);
  output.rowTransitions = transitions.filter((item) => rows.has(item.fromRowId) && rows.has(item.toRowId));
  output.rowAudioSpans = spans.filter((item) => rows.has(item.startRowId) && rows.has(item.endRowId));
  output.rowReferences = references.filter((item) => rows.has(item.rowId));
  if (output.rowTransitions.length === 0) delete output.rowTransitions;
  if (output.rowAudioSpans.length === 0) delete output.rowAudioSpans;
  if (output.rowReferences.length === 0) delete output.rowReferences;
}

/** Reconcile *complete* group records after row projection, never replay partial group commands.
 * A Save's new members are authored births; a group's location/order is organization.
 * Any incompatible mixture refuses rather than silently ungrouping surviving members.
 */
function projectStashGroups(
  output: ScriptDocumentV2,
  baseline: ScriptDocumentV2,
  current: ScriptDocumentV2,
  state: SortingProjectionV2,
  mode: "edits_only" | "sorting_only",
): string | null {
  const baselineGroups = new Map((baseline.stashGroups ?? []).map((group) => [group.id, group]));
  const currentGroups = new Map((current.stashGroups ?? []).map((group) => [group.id, group]));
  const outputSavedIds = new Set((output.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => row.id)));
  const outputActiveIds = new Set(output.activeDraft.blocks.map((row) => row.id));
  const entries = output.stashOutline ?? [];
  const index = new Map(entries.map((entry, position) => [entry.rowId, position]));
  const candidates = mode === "edits_only" ? [...baselineGroups.values()] : [
    ...currentGroups.values(),
    ...[...baselineGroups.values()].filter((group) => !currentGroups.has(group.id) &&
      state.groupRemovals.some((item) => item.groupId === group.id && item.classification === "edit")),
  ];
  const result: StashRowGroupV2[] = [];
  const claimed = new Set<string>();
  for (const group of candidates) {
    const baselineGroup = baselineGroups.get(group.id);
    const members = new Set(group.rowIds);
    if (mode === "edits_only") {
      for (const addition of state.groupSaveBirths) if (addition.groupId === group.id) members.add(addition.rowId);
    } else if (baselineGroup) {
      // A member deleted by Save is an edit: Sorting-only restores its canonical
      // content and membership if the group still exists, or was removed by Save.
      for (const rowId of baselineGroup.rowIds) members.add(rowId);
    }
    const activeMembers = [...members].filter((rowId) => outputActiveIds.has(rowId));
    if (activeMembers.length > 0) return `Group ${group.id} has members on the active Draft after selective projection: ${activeMembers.join(", ")}.`;
    const rowIds = [...members].filter((rowId) => outputSavedIds.has(rowId))
      .sort((left, right) => (index.get(left) ?? Infinity) - (index.get(right) ?? Infinity));
    if (rowIds.length < 2) continue; // One/zero members normalize to ordinary rows.
    if (rowIds.some((rowId) => !index.has(rowId) || claimed.has(rowId))) {
      return `Group ${group.id} has an unlocated or multiply owned member.`;
    }
    const candidate: StashRowGroupV2 = { ...structuredClone(group), rowIds: rowIds as [string, string, ...string[]] };
    // Group conversion to ordinary rows is organization, even for originally
    // compact notes/clips whose baseline kinds normalize back in Sorting-only.
    if (mode === "sorting_only") for (const entry of entries) if (members.has(entry.rowId)) entry.kind = "row";
    const invalid = stashGroupLocationProblemV2(output, candidate);
    if (invalid) return `Group ${group.id} cannot be projected atomically: ${invalid}`;
    rowIds.forEach((rowId) => claimed.add(rowId));
    result.push(candidate);
  }
  if (result.length > 0) output.stashGroups = result;
  else delete output.stashGroups;
  return null;
}

function newErrors(baseline: ScriptDocumentV2, projected: ScriptDocumentV2): AuthoringDiagnosticV2[] {
  const key = (item: AuthoringDiagnosticV2) => `${item.code}\0${item.entityId ?? ""}\0${item.blockId ?? ""}\0${item.message}`;
  const prior = new Map<string, number>();
  for (const item of validateScriptDocumentV2(baseline).diagnostics) if (item.severity !== "warning") prior.set(key(item), (prior.get(key(item)) ?? 0) + 1);
  return validateScriptDocumentV2(projected).diagnostics.filter((item) => {
    if (item.severity === "warning") return false;
    const signature = key(item);
    const count = prior.get(signature) ?? 0;
    if (count === 0) return true;
    prior.set(signature, count - 1);
    return false;
  });
}

function refuse(current: ScriptDocumentV2, code: string, message: string): RowEditResultV2 {
  return { ok: false, document: current, diagnostics: [diagnostic(code, message)] };
}

/** Compose one selective outcome from stable identities and complete organization snapshots. */
export function projectSortingDocumentV2(
  state: SortingProjectionV2,
  current: ScriptDocumentV2,
  mode: "edits_only" | "sorting_only",
): RowEditResultV2 {
  try {
    if (state.identityConflicts.length > 0) return refuse(current, "SORTING_PROJECTION_IDENTITY_AMBIGUOUS", `Row IDs were reused after deletion: ${state.identityConflicts.join(", ")}. Start a new Sorting trial before selective acceptance.`);
    if (state.groupIdentityConflicts.length > 0) return refuse(current, "SORTING_PROJECTION_IDENTITY_AMBIGUOUS", `Group IDs were reused after removal: ${state.groupIdentityConflicts.join(", ")}. Accept all changes or start a new trial.`);
    const baseline = state.baseline;
    const baselineRows = rowMap(baseline);
    const currentRows = rowMap(current);
    const baselineSlots = slotRecords(baseline);
    const detached = new Map(state.detachedPlacements.map((item) => [item.clipRowId, item.noteRowId]));
    const independentDetached = new Set([...detached.keys()].filter((clipId) => currentRows.get(clipId)?.type === "visual_only"));
    const originalDetached = new Map([...independentDetached].flatMap((clipId) => {
      const noteId = detached.get(clipId)!;
      const clip = sourceAttachedClip(baseline, noteId, clipId);
      return clip ? [[clipId, clip] as const] : [];
    }));
    const output = structuredClone(mode === "edits_only" ? baseline : current);
    const droppedIds = new Set<string>();

    if (mode === "edits_only") {
      const birthsToRestore = editsOnlyBirths(state).filter((birth) => !detached.has(birth.rowId));
      const restoreRows = new Map(baselineRows);
      for (const birth of birthsToRestore) {
        const row = currentRows.get(birth.rowId) ?? (!birth.present ? birth.row : undefined);
        if (!row) return refuse(current, "SORTING_PROJECTION_ROW_MISSING", `New row ${birth.rowId} has no content snapshot for the selected result.`);
        restoreRows.set(birth.rowId, structuredClone(row));
      }
      const birthPlacements = birthsToRestore.map((birth) => {
        const groupBirth = state.groupSaveBirths.find((item) => item.rowId === birth.rowId);
        const baselineGroup = groupBirth && baseline.stashGroups?.find((group) => group.id === groupBirth.groupId);
        if (!baselineGroup || birth.slot.surface !== "stash") return { rowId: birth.rowId, slot: birth.slot };
        // The stage may have inserted this row before/among reordered members.
        // Edits-only rejects that organization, but retains the authored new
        // member directly after the baseline group, without moving old members.
        const lastBaseline = baselineGroup.rowIds.at(-1)!;
        const groupEnd = slotFor(baseline, lastBaseline);
        if (!groupEnd || groupEnd.surface !== "stash") return { rowId: birth.rowId, slot: birth.slot };
        const otherBirths = state.groupSaveBirths.filter((item) => item.groupId === baselineGroup.id);
        const birthIndex = otherBirths.findIndex((item) => item.rowId === birth.rowId);
        return { rowId: birth.rowId, slot: {
          ...birth.slot,
          entry: { rowId: birth.rowId, kind: "row" as const,
            sectionId: groupEnd.entry.sectionId, parentRowId: groupEnd.entry.parentRowId },
          afterSiblingRowId: birthIndex > 0 ? otherBirths[birthIndex - 1]!.rowId : lastBaseline,
          beforeSiblingRowId: groupEnd.beforeSiblingRowId,
        } };
      });
      const ignoredIds = new Set([
        ...state.tombstones.map((tombstone) => tombstone.rowId),
        ...state.births.filter((birth) => !birth.present).map((birth) => birth.rowId),
      ]);
      if (!restoreTombstoneBatches(output, restoreRows, birthPlacements, ignoredIds)) return refuse(current, "SORTING_PROJECTION_DESTINATION_INVALID", "A new row's original section, Stash parent, or exact birth gap no longer exists.");
      for (const tombstone of state.tombstones) {
        if (removeRow(output, tombstone.rowId)) droppedIds.add(tombstone.rowId);
      }
      for (const birth of state.births) {
        if (!birth.present && removeRow(output, birth.rowId)) droppedIds.add(birth.rowId);
      }
    } else {
      const ghostByRow = new Map(state.ghostFallbacks.map((fallback) => [fallback.rowId, fallback.slot]));
      const tombstones = state.tombstones.map((item) => ghostByRow.has(item.rowId)
        ? { ...item, slot: structuredClone(ghostByRow.get(item.rowId)!) }
        : item);
      const neededBirths = deletedBirthDependencies(state, tombstones.map((item) => item.slot), "last");
      const restoreRows = new Map(baselineRows);
      for (const birth of state.births) {
        const row = currentRows.get(birth.rowId);
        if (row) restoreRows.set(birth.rowId, structuredClone(row));
      }
      for (const birth of neededBirths) if (!restoreRows.has(birth.rowId)) restoreRows.set(birth.rowId, structuredClone(birth.row));
      const birthPlacements = neededBirths.map((birth) => ({ rowId: birth.rowId, slot: birth.lastSlot }));
      const ignoredIds = new Set(state.births.map((birth) => birth.rowId));
      if (!restoreTombstoneBatches(output, restoreRows, [...tombstones, ...birthPlacements], ignoredIds)) return refuse(current, "SORTING_PROJECTION_DESTINATION_INVALID", "A deleted row's last section, Stash parent, or exact slot no longer exists.");
      for (const birth of state.births) {
        if (!independentDetached.has(birth.rowId) && removeRow(output, birth.rowId)) droppedIds.add(birth.rowId);
      }
      const restoredFromFallback = new Set(tombstones.filter((item) => ghostByRow.has(item.rowId)).map((item) => item.rowId));
      const pendingFallbacks = state.ghostFallbacks.filter((fallback) => !restoredFromFallback.has(fallback.rowId) && outputRowsHas(output, fallback.rowId));
      while (pendingFallbacks.length > 0) {
        let moved = false;
        for (let index = 0; index < pendingFallbacks.length; index += 1) {
          const fallback = pendingFallbacks[index]!;
          if (!moveRow(output, fallback.rowId, fallback.slot)) continue;
          pendingFallbacks.splice(index--, 1);
          moved = true;
        }
        if (!moved) return refuse(current, "SORTING_PROJECTION_DEPENDENCY_INVALID", "A move targeted a new row that Sorting-only discards, and the row's previous exact slot is no longer available.");
      }
    }

    const outputSlots = slotRecords(output);
    const outputRowIds = new Set(outputSlots.keys());
    for (const rowId of outputRowIds) {
      const baselineRow = baselineRows.get(rowId);
      const latestRow = currentRows.get(rowId);
      const birth = state.births.find((item) => item.rowId === rowId);
      const changed = !!baselineRow && !!latestRow && !sameJson(contentRow(baselineRow), contentRow(latestRow));
      let selectedRow: Row | undefined;
      if (mode === "sorting_only") selectedRow = baselineRow ?? originalDetached.get(rowId);
      else selectedRow = birth ? latestRow : changed ? latestRow : baselineRow;
      if (!selectedRow) return refuse(current, "SORTING_PROJECTION_ROW_MISSING", `Row ${rowId} has no content snapshot for the selected result.`);

      if (selectedRow.type === "narration") {
        const conversion = state.detachedPlacements.find((item) => item.noteRowId === rowId && independentDetached.has(item.clipRowId));
        if (conversion && mode === "sorting_only") {
          // The original clip's content is retained in the separately placed row;
          // its old embedded edge is organization, not a second copy.
          selectedRow = structuredClone(selectedRow);
          delete selectedRow.attachedFootage;
        } else if (conversion && mode === "edits_only" && !selectedRow.attachedFootage) {
          // Reject the Sorting placement while retaining any authored use-range edit.
          // This restores one clip owner on the baseline note, not a ghost Draft row.
          const independent = currentRows.get(conversion.clipRowId);
          if (independent?.type !== "visual_only") return refuse(current, "SORTING_PROJECTION_ATTACHMENT_INVALID", "The detached clip has no authoritative content to restore to its original note.");
          selectedRow = structuredClone(selectedRow);
          const clip = structuredClone(independent);
          delete clip.stashOrigin;
          selectedRow.attachedFootage = { clip };
        }
      }

      const slot = outputSlots.get(rowId)!;
      const priorSlot = baselineSlots.get(rowId);
      const layoutOrigin = latestRow?.stashOrigin ?? state.tombstones.find((tombstone) => tombstone.rowId === rowId)?.origin;
      if (mode === "sorting_only" && slot.surface === "draft" && layoutOrigin &&
        [layoutOrigin.parentRowId, layoutOrigin.afterSiblingRowId, layoutOrigin.beforeSiblingRowId].some((id) => id !== null && state.births.some((birth) => birth.rowId === id))) {
        return refuse(current, "SORTING_PROJECTION_DEPENDENCY_INVALID", "The row's Stash return location depends on a new row that sorting-only removes.");
      }
      const normalized = normalizeRowForLocation(selectedRow, rowId, slot, baseline, priorSlot, changed || !!birth && !!latestRow && !sameJson(contentRow(birth.row), contentRow(latestRow)), mode, layoutOrigin);
      const presented = reconcileAttachmentPresentation(normalized, slot);
      if (!presented) return refuse(current, "SORTING_PROJECTION_ATTACHMENT_INVALID", `Row ${rowId}'s attached footage has an incompatible visual slot for the selected location.`);
      replaceRow(output, rowId, presented);
    }

    const shapeProblem = normalizeOutlineKinds(output, baseline, current, state, mode);
    if (shapeProblem) return refuse(current, "SORTING_PROJECTION_DEPENDENCY_INVALID", shapeProblem);
    const groupProblem = projectStashGroups(output, baseline, current, state, mode);
    if (groupProblem) return refuse(current, "SORTING_PROJECTION_GROUP_INVALID", groupProblem);
    const supportProblem = routeSupportingItems(output, baseline, current, mode, droppedIds);
    if (supportProblem) return refuse(current, "SORTING_PROJECTION_ATTACHMENT_INVALID", supportProblem);
    applyRelationships(output, baseline, current, mode);
    const originalClipIds = clipOwnershipIds(baseline);
    const currentClipIds = clipOwnershipIds(current);
    const outputClipIds = clipOwnershipIds(output);
    // Moving a clip between an embedded owner and an ordinary row must not
    // silently discard an identity that survives in both valid endpoints.
    for (const clipId of originalClipIds) {
      if (currentClipIds.has(clipId) && !outputClipIds.has(clipId)) {
        return refuse(current, "SORTING_PROJECTION_ATTACHMENT_INVALID", `The selected Sorting outcome loses existing clip ${clipId}; accept all changes or separate the conflicting edits.`);
      }
    }
    const errors = newErrors(baseline, output);
    if (errors.length > 0) return { ok: false, document: current, diagnostics: errors };
    return { ok: true, document: output, diagnostics: [] };
  } catch (error) {
    return refuse(current, "SORTING_PROJECTION_INVALID", error instanceof Error ? error.message : "The selective Sorting result could not be composed safely.");
  }
}

function outputRowsHas(document: ScriptDocumentV2, rowId: string): boolean {
  return rowMap(document).has(rowId);
}

function replaceRow(document: ScriptDocumentV2, rowId: string, replacement: Row): void {
  const activeIndex = document.activeDraft.blocks.findIndex((block) => block.id === rowId && block.type !== "section");
  if (activeIndex >= 0) {
    document.activeDraft.blocks[activeIndex] = structuredClone(replacement);
    return;
  }
  for (const bundle of document.stash ?? []) {
    const index = bundle.rows.findIndex((row) => row.id === rowId);
    if (index >= 0) {
      bundle.rows[index] = structuredClone(replacement);
      return;
    }
  }
}

function normalizeOutlineKinds(
  output: ScriptDocumentV2,
  baseline: ScriptDocumentV2,
  current: ScriptDocumentV2,
  state: SortingProjectionV2,
  mode: "edits_only" | "sorting_only",
): string | null {
  if (!output.stashOutline) return null;
  const baselineRows = rowMap(baseline);
  const currentRows = rowMap(current);
  for (const entry of output.stashOutline) {
    const baselineRow = baselineRows.get(entry.rowId);
    const currentRow = currentRows.get(entry.rowId);
    const birth = state.births.find((item) => item.rowId === entry.rowId);
    const changed = baselineRow && currentRow && !sameJson(contentRow(baselineRow), contentRow(currentRow));
    const bornChanged = birth && currentRow && !sameJson(contentRow(birth.row), contentRow(currentRow));
    const baselineSlot = slotFor(baseline, entry.rowId);
    const original = baselineRows.get(entry.rowId);
    if (mode === "sorting_only") {
      entry.kind = baselineSlot?.surface === "stash"
        ? baselineSlot.entry.kind
        : original?.stashOrigin?.returnEligible ? original.stashOrigin.kind : "row";
    } else if (birth) {
      entry.kind = state.convertedEditedIds.includes(entry.rowId) && bornChanged
        ? "row"
        : birth.slot.surface === "stash" ? birth.slot.entry.kind : "row";
    } else if (state.convertedEditedIds.includes(entry.rowId) && changed) entry.kind = "row";
    const parent = entry.parentRowId === null ? undefined : output.stashOutline.find((candidate) => candidate.rowId === entry.parentRowId);
    if (parent && parent.kind !== "note") return `Row ${entry.rowId} cannot remain under ${parent.rowId} after its parent becomes an ordinary row.`;
  }
  return null;
}
