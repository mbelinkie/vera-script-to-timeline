import { createBlankNarrationRow, rowGaps, rowLabel, rowSections } from "./rows-editor.js";
import { selectedSpokenWords } from "./visual-selection.js";

const sameGap = (a, b) => !!a && !!b &&
  a.sectionId === b.sectionId && a.afterRowId === b.afterRowId && a.beforeRowId === b.beforeRowId;
const copyGap = ({ sectionId, afterRowId, beforeRowId }) =>
  Object.freeze({ sectionId, afterRowId, beforeRowId });
const draftBlocks = (model) => model?.activeDraft?.blocks ?? [];
const sectionTitle = (blocks, sectionId, missing) => sectionId === null ? "Before first section" :
  blocks.find((block) => block.type === "section" && block.id === sectionId)?.title ?? missing;
const stashSnapshot = (model) =>
  JSON.stringify([model.stash, model.stashOutline, model.stashSections, model.stashGroups]);
const validRowIds = (ids) => Array.isArray(ids) && ids.length > 0 && ids.length <= 4096 &&
  ids.every((id) => typeof id === "string") && new Set(ids).size === ids.length;

/** Provenance is the original Draft gap, not the current Stash section. */
export function originalDraftLocation(model, bundle) {
  const gap = bundle?.originalGap;
  if (!gap) return { label: "Original section not recorded", gap: null, available: false };
  const blocks = draftBlocks(model);
  return {
    label: sectionTitle(blocks, gap.sectionId, "Original section unavailable"),
    gap: copyGap(gap),
    available: rowGaps(blocks).some((candidate) => sameGap(candidate, gap)),
  };
}

export function draftGapChoices(model) {
  const blocks = draftBlocks(model);
  const byId = new Map(blocks.map((block) => [block.id, block]));
  return rowGaps(blocks).map((gap) => {
    const after = byId.get(gap.afterRowId);
    const before = byId.get(gap.beforeRowId);
    const position = after && before ? `Between ${rowLabel(after)} and ${rowLabel(before)}` :
      after ? `After ${rowLabel(after)}` : before ? `Before ${rowLabel(before)}` : "Empty section";
    return { gap: copyGap(gap), label: `${sectionTitle(blocks, gap.sectionId, "Section unavailable")} — ${position}` };
  });
}

/** Capture the displayed source and its context, including supporting items. */
export function captureWholeRowStash(model, rowIds) {
  if (!model || !validRowIds(rowIds)) return null;
  const section = rowSections(draftBlocks(model)).find(({ rows }) => {
    const index = rows.findIndex((row) => row.id === rowIds[0]);
    return index >= 0 && rowIds.every((id, offset) => rows[index + offset]?.id === id);
  });
  if (!section) return null;
  // Conservative: changes elsewhere in Draft or Stash can affect supporting
  // edges or an existing return origin. Re-select rather than guessing.
  return Object.freeze({
    projectId: model.projectId, documentId: model.id, sectionId: section.sectionId,
    rowIds: Object.freeze([...rowIds]), draftSnapshot: JSON.stringify(model.activeDraft),
    stashSnapshot: stashSnapshot(model),
  });
}

export function wholeRowStashCommand(model, intent, makeId = uuid) {
  const fresh = captureWholeRowStash(model, intent?.rowIds);
  if (!fresh || JSON.stringify(fresh) !== JSON.stringify(intent)) {
    throw new Error("The rows or their section changed. Select them again.");
  }
  return { kind: "stash_rows", rowIds: [...intent.rowIds], bundleId: makeId() };
}

/** The chooser captures these snapshots before the writer chooses a gap. */
export function captureSavedPlacement(model, kind, rowIds, destination, includeDescendants) {
  if (!model || !["restore_stash_rows", "place_stash_rows", "duplicate_stash_rows"].includes(kind) ||
      !validRowIds(rowIds) || (includeDescendants !== undefined &&
        (kind !== "place_stash_rows" || typeof includeDescendants !== "boolean"))) return null;
  const saved = new Set((model.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => row.id)));
  if (!rowIds.every((id) => saved.has(id)) ||
      !rowGaps(draftBlocks(model)).some((gap) => sameGap(gap, destination))) return null;
  return Object.freeze({
    projectId: model.projectId, documentId: model.id, kind,
    rowIds: Object.freeze([...rowIds]), destination: copyGap(destination),
    ...(includeDescendants === undefined ? {} : { includeDescendants }),
    stashSnapshot: stashSnapshot(model), draftSnapshot: JSON.stringify(model.activeDraft),
  });
}

export function savedPlacementCommand(model, intent) {
  const fresh = intent && captureSavedPlacement(model, intent.kind, intent.rowIds,
    intent.destination, intent.includeDescendants);
  if (!fresh || JSON.stringify(fresh) !== JSON.stringify(intent)) {
    throw new Error("The saved material or destination changed. Choose again.");
  }
  return { kind: intent.kind, rowIds: [...intent.rowIds], destination: { ...intent.destination },
    ...(intent.includeDescendants === undefined ? {} : { includeDescendants: intent.includeDescendants }) };
}

/** Read the saved Stash without reshaping its entries or changing their identities. */
export function projectStash(documentModel) {
  const sections = [
    { id: null, title: "Unsectioned", entries: [] },
    ...(documentModel?.stashSections ?? []).map((section) => ({
      id: section.id, title: section.title, entries: [],
    })),
  ];
  const bySection = new Map(sections.map((section) => [section.id, section]));
  const saved = new Map((documentModel?.stash ?? []).flatMap((bundle) =>
    bundle.rows.map((row) => [row.id, { row, bundle }])));
  // Older saved documents can lack the explicit outline. The model derives
  // the same unsectioned fallback; don't assign IDs or mutate the document.
  const legacySections = new Map((documentModel?.stashSections ?? []).flatMap((section) =>
    section.rowIds.map((rowId) => [rowId, section.id])));
  const outline = documentModel?.stashOutline ?? [...saved.keys()].map((rowId) => ({
    rowId, kind: "row", parentRowId: null, sectionId: legacySections.get(rowId) ?? null,
  }));
  for (const entry of outline) {
    const item = saved.get(entry.rowId);
    if (item) bySection.get(entry.sectionId)?.entries.push({
      ...entry, row: item.row, bundleId: item.bundle.id,
      originalDraft: originalDraftLocation(documentModel, item.bundle),
    });
  }
  return sections;
}

function activeRow(documentModel, id) {
  const row = documentModel?.activeDraft?.blocks?.find((block) => block.id === id);
  return row?.type === "narration" && row.state === "active" && row.plainDirection !== true ? row : null;
}

function stashNote(documentModel, noteRowId) {
  if (!documentModel?.stashOutline?.some((entry) => entry.rowId === noteRowId && entry.kind === "note")) return null;
  const row = (documentModel.stash ?? []).flatMap((bundle) => bundle.rows).find((item) => item.id === noteRowId);
  return row?.type === "narration" && row.plainDirection === true ? row : null;
}

const uuid = () => crypto.randomUUID();

/** Raw note text, including literal brackets and surrounding whitespace, is never normalized. */
export function createStashNoteCommand(documentModel, text, location = {}, makeId = uuid) {
  if (typeof text !== "string" || !text.trim()) throw new Error("Enter a note before saving it in Stash.");
  const { sectionId = null, parentRowId = null, afterRowId = null } = location;
  if (sectionId !== null && !(documentModel?.stashSections ?? []).some((section) => section.id === sectionId)) {
    throw new Error("The selected Stash section is no longer available.");
  }
  if (parentRowId !== null && !documentModel?.stashOutline?.some((entry) =>
    entry.rowId === parentRowId && entry.kind === "note" && entry.sectionId === sectionId)) {
    throw new Error("The parent Stash note is no longer available.");
  }
  const sibling = documentModel?.stashOutline?.find((entry) => entry.rowId === afterRowId);
  if (afterRowId !== null && (!sibling || sibling.parentRowId !== parentRowId || sibling.sectionId !== sectionId)) {
    throw new Error("The Stash insertion position changed.");
  }
  const row = createBlankNarrationRow({ idFactory: makeId });
  row.text = text;
  const matches = [...text.matchAll(/[^\s[\]]+/gu)];
  const words = matches.length ? matches : [...text.matchAll(/\S+/gu)];
  row.tokens = words.map((match) => ({
    id: makeId(), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  }));
  return { kind: "create_stash_note", bundleId: makeId(), row,
    sectionId, parentRowId, afterRowId };
}

/** Capture exact word IDs at selection time; refuse if queued typing changes the source. */
export function captureStashWords(documentModel, rowId, selection) {
  const row = activeRow(documentModel, rowId);
  const words = row && selectedSpokenWords(row, selection, true);
  if (!words) return null;
  return { rowId, rowVersion: row.version, text: row.text, rowSnapshot: JSON.stringify(row),
    words: { startTokenId: words.startTokenId, endTokenId: words.endTokenId } };
}

export function stashWordsCommand(documentModel, intent, makeId = uuid) {
  const row = activeRow(documentModel, intent?.rowId);
  if (!row || row.version !== intent.rowVersion || row.text !== intent.text ||
    JSON.stringify(row) !== intent.rowSnapshot ||
    !row.tokens.some((token) => token.id === intent.words?.startTokenId) ||
    !row.tokens.some((token) => token.id === intent.words?.endTokenId)) {
    throw new Error("The selected words changed before they could be stashed.");
  }
  return { kind: "stash_selected_words", rowId: intent.rowId, words: { ...intent.words },
    bundleId: makeId(), stashRowId: makeId() };
}

/** A drop addresses one real interior gap by its right-hand token, not an offset. */
export function captureStashNoteDrop(documentModel, noteRowId, rowId, beforeTokenId) {
  const note = stashNote(documentModel, noteRowId);
  const row = activeRow(documentModel, rowId);
  const boundary = row?.tokens.findIndex((token) => token.id === beforeTokenId) ?? -1;
  if (!note || !row || boundary < 1 || row.tokens[boundary - 1]?.spoken === false ||
    row.tokens[boundary]?.spoken === false) return null;
  return { noteRowId, rowId, beforeTokenId,
    noteSnapshot: JSON.stringify(note), rowSnapshot: JSON.stringify(row) };
}

export function insertStashNoteCommand(documentModel, intent) {
  const note = stashNote(documentModel, intent?.noteRowId);
  const row = activeRow(documentModel, intent?.rowId);
  if (!note || !row || JSON.stringify(note) !== intent.noteSnapshot ||
    JSON.stringify(row) !== intent.rowSnapshot ||
    !row.tokens.some((token) => token.id === intent.beforeTokenId)) {
    throw new Error("The note or its receiving row changed before insertion.");
  }
  return { kind: "insert_stash_note_words", noteRowId: intent.noteRowId,
    rowId: intent.rowId, beforeTokenId: intent.beforeTokenId };
}

/** All three mutations use the editor's existing queue -> authorized host -> CAS save -> Undo. */
export function createStashActions(queueCommand, getDocument, makeId = uuid, queueExtras) {
  return {
    view: () => projectStash(getDocument()),
    stashRow: (rowId) => {
      const intent = captureWholeRowStash(getDocument(), [rowId]);
      return intent && queueExtras ? queueExtras((current) => wholeRowStashCommand(current, intent, makeId),
        "Stash row") : Promise.resolve(false);
    },
    addNote: (text, location) => queueCommand(
      (current) => createStashNoteCommand(current, text, location, makeId), "Add Stash note", { structural: true }),
    stashWords: (rowId, selection) => {
      const intent = captureStashWords(getDocument(), rowId, selection);
      return intent ? queueCommand((current) => stashWordsCommand(current, intent, makeId),
        "Stash words", { structural: true }) : Promise.resolve(false);
    },
    dropNote: (noteRowId, rowId, beforeTokenId) => {
      const intent = captureStashNoteDrop(getDocument(), noteRowId, rowId, beforeTokenId);
      return intent ? queueCommand((current) => insertStashNoteCommand(current, intent),
        "Insert Stash note", { structural: true }) : Promise.resolve(false);
    },
  };
}
