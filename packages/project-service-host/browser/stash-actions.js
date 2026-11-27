import { createBlankNarrationRow, rowGaps, rowLabel, rowSections } from "./rows-editor.js";
import { selectedDropPlacement, selectedSpokenWords } from "./visual-selection.js";

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
  const groups = new Map((documentModel?.stashGroups ?? []).flatMap((group) =>
    group.rowIds.map((rowId, index) => [rowId, { id: group.id, index, size: group.rowIds.length }])));
  const children = new Map();
  for (const entry of outline) {
    const siblings = children.get(entry.parentRowId) ?? [];
    siblings.push(entry.rowId);
    children.set(entry.parentRowId, siblings);
  }
  function branch(id) {
    const seen = new Set();
    const pending = [id];
    while (pending.length) {
      const next = pending.pop();
      if (seen.has(next)) continue;
      seen.add(next);
      pending.push(...(children.get(next) ?? []));
    }
    return [...seen];
  }
  for (const entry of outline) {
    const item = saved.get(entry.rowId);
    if (item) bySection.get(entry.sectionId)?.entries.push({
      ...entry, row: item.row, bundleId: item.bundle.id,
      originalDraft: originalDraftLocation(documentModel, item.bundle),
      hasDescendants: (children.get(entry.rowId) ?? []).length > 0,
      ...(groups.has(entry.rowId) ? { group: groups.get(entry.rowId) } : {}),
      groupRestricted: branch(entry.rowId).some((id) => groups.has(id)),
    });
  }
  return sections;
}

export const documentStashSnapshot = (documentModel) => JSON.stringify([
  documentModel?.stash, documentModel?.stashOutline, documentModel?.stashSections, documentModel?.stashGroups,
]);

function queueStashCommand(queueCommand, queueExtras, getDocument, makeId, command, label, useExtras = false, expectedModel) {
  const model = getDocument();
  if (!model || expectedModel && model !== expectedModel) return Promise.resolve(false);
  const projectId = model.projectId;
  const documentId = model.id;
  const snapshot = documentStashSnapshot(model);
  const queue = useExtras ? queueExtras : queueCommand;
  return queue ? queue((current) => {
    if (current.projectId !== projectId || current.id !== documentId ||
      documentStashSnapshot(current) !== snapshot) {
      throw new Error("The saved Stash changed. Choose the item again.");
    }
    return typeof command === "function" ? command(current, makeId) : command;
  }, label, ...(useExtras ? [] : [{ structural: true }])) : Promise.resolve(false);
}

function outlineFor(documentModel) {
  if (documentModel?.stashOutline) return structuredClone(documentModel.stashOutline);
  return projectStash(documentModel).flatMap((section) => section.entries.map(({ rowId, kind, parentRowId, sectionId }) =>
    ({ rowId, kind, parentRowId, sectionId })));
}

function descendantsOf(outline, rootIds) {
  const roots = new Set(rootIds);
  const children = new Map();
  for (const entry of outline) {
    const list = children.get(entry.parentRowId) ?? [];
    list.push(entry.rowId);
    children.set(entry.parentRowId, list);
  }
  const included = new Set();
  const todo = [...roots];
  while (todo.length) {
    const rowId = todo.pop();
    if (included.has(rowId)) continue;
    included.add(rowId);
    todo.push(...(children.get(rowId) ?? []));
  }
  return included;
}

/** Build a safe complete outline move, keeping every selected branch together. */
export function stashOutlineMoveCommand(documentModel, rowId, destination) {
  const outline = outlineFor(documentModel);
  const source = outline.find((entry) => entry.rowId === rowId);
  if (!source || !destination || typeof destination !== "object") throw new Error("Choose a current Stash item and destination.");
  const group = documentModel.stashGroups?.find((item) => item.rowIds.includes(rowId));
  const roots = group ? [...group.rowIds] : [rowId];
  const movingIds = descendantsOf(outline, roots);
  if (destination.parentRowId !== null) {
    const parent = outline.find((entry) => entry.rowId === destination.parentRowId);
    if (!parent || parent.kind !== "note" || parent.sectionId !== destination.sectionId) {
      throw new Error("Items can nest only under a note in the same section.");
    }
    if (movingIds.has(parent.rowId)) throw new Error("An item cannot be nested inside itself.");
  }
  if (destination.afterRowId !== null) {
    const after = outline.find((entry) => entry.rowId === destination.afterRowId);
    if (!after || movingIds.has(after.rowId) || after.parentRowId !== destination.parentRowId ||
      after.sectionId !== destination.sectionId) throw new Error("Choose a current sibling position.");
  }
  const sections = [null, ...(documentModel.stashSections ?? []).map((item) => item.id)];
  if (destination.sectionId !== null && !sections.includes(destination.sectionId)) {
    throw new Error("The Stash section is no longer available.");
  }
  const moved = outline.filter((entry) => movingIds.has(entry.rowId)).map((entry) => ({ ...entry,
    sectionId: destination.sectionId,
    ...(roots.includes(entry.rowId) ? { parentRowId: destination.parentRowId } : {}),
  }));
  const remaining = outline.filter((entry) => !movingIds.has(entry.rowId));
  const remainingMap = new Map(remaining.map((entry) => [entry.rowId, entry]));
  const descendantsIn = (id) => {
    const ids = new Set([id]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const entry of remaining) if (entry.parentRowId !== null && ids.has(entry.parentRowId) && !ids.has(entry.rowId)) {
        ids.add(entry.rowId); changed = true;
      }
    }
    return ids;
  };
  let insertAt;
  if (destination.afterRowId !== null) {
    const tail = descendantsIn(destination.afterRowId);
    insertAt = remaining.reduce((last, entry, index) => tail.has(entry.rowId) ? index + 1 : last, -1);
  } else if (destination.parentRowId !== null) {
    const parentIndex = remaining.findIndex((entry) => entry.rowId === destination.parentRowId);
    insertAt = parentIndex + 1;
  } else {
    const sectionRank = sections.indexOf(destination.sectionId);
    insertAt = remaining.findIndex((entry) => entry.parentRowId === null && entry.sectionId === destination.sectionId);
    if (insertAt < 0) insertAt = remaining.findIndex((entry) => sections.indexOf(entry.sectionId) > sectionRank);
    if (insertAt < 0) insertAt = remaining.length;
  }
  if (insertAt < 0) throw new Error("Choose a current Stash destination.");
  return { kind: "set_stash_outline", entries: [
    ...remaining.slice(0, insertAt), ...moved, ...remaining.slice(insertAt),
  ] };
}

export function captureStashGroupPlacement(documentModel, groupId, destination) {
  const group = documentModel?.stashGroups?.find((item) => item.id === groupId);
  if (!group || !validRowIds(group.rowIds) || !rowGaps(draftBlocks(documentModel)).some((gap) => sameGap(gap, destination))) return null;
  return Object.freeze({ projectId: documentModel.projectId, documentId: documentModel.id, groupId,
    rowIds: Object.freeze([...group.rowIds]), destination: copyGap(destination),
    stashSnapshot: stashSnapshot(documentModel), draftSnapshot: JSON.stringify(documentModel.activeDraft) });
}

export function stashGroupPlacementCommand(documentModel, intent) {
  const fresh = intent && captureStashGroupPlacement(documentModel, intent.groupId, intent.destination);
  if (!fresh || JSON.stringify(fresh) !== JSON.stringify(intent)) throw new Error("The saved group or Draft destination changed. Choose again.");
  return { kind: "place_stash_group", groupId: intent.groupId, destination: { ...intent.destination } };
}

function editedNoteCommand(documentModel, rowId, text, makeId) {
  const entry = outlineFor(documentModel).find((item) => item.rowId === rowId && item.kind === "note");
  const row = (documentModel.stash ?? []).flatMap((bundle) => bundle.rows).find((item) => item.id === rowId);
  if (!entry || row?.type !== "narration" || row.plainDirection !== true || typeof text !== "string" ||
    !text.trim() && !row.attachedFootage) {
    throw new Error("Enter text or keep attached footage on this Stash note.");
  }
  if (!text.trim() && row.attachedFootage) {
    return { kind: "cleanup_blank_stash_note", noteRowId: rowId, clipBundleId: makeId(), clearText: true };
  }
  if (row.version >= Number.MAX_SAFE_INTEGER) throw new Error("This note cannot be edited again.");
  const replacement = structuredClone(row);
  replacement.text = text;
  replacement.tokens = [...text.matchAll(/\S+/gu)].map((match) => ({
    id: makeId(), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length, spoken: false,
  }));
  replacement.version += 1;
  return { kind: "edit_row", rowId, row: replacement };
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
// Both transforms operate on private documents. Only the queue publishes
// the final result; no intermediate Stash removal, save or Undo is visible.
export async function applySelectedStashTransfer(prior, insert, snapshot, applyCommand, assertCurrent) {
  const placement = selectedDropPlacement(prior, snapshot);
  if (!placement || insert.kind !== "insert_stash_visual" || insert.destinationRowId !== placement.rowId) {
    throw new Error("Choose the highlighted words again.");
  }
  const sameDocument = (model) => model?.projectId === prior.projectId && model.id === prior.id;
  const findRow = (model) => model?.activeDraft.blocks.find((row) => row.id === placement.rowId);
  const sourceGone = (model) => !(model.stash ?? []).some((bundle) => bundle.rows.some((row) => row.id === insert.stashRowId));
  const original = findRow(prior);
  const sameWords = (row) => row?.type === "narration" && row.text === original.text &&
    JSON.stringify(row.tokens) === JSON.stringify(original.tokens);
  assertCurrent();
  const staged = await applyCommand(prior, insert);
  assertCurrent();
  const row = findRow(staged?.document);
  if (!staged?.ok || !sameDocument(staged.document) || !sameWords(row) ||
      !sourceGone(staged.document) || !Number.isSafeInteger(row.primaryVisualSequence?.version) ||
      !row.unattachedVisuals?.some((item) => item.slotId === insert.destinationSlotId)) {
    throw new Error("The saved visual could not be moved.");
  }
  const attached = await applyCommand(staged.document, {
    kind: "attach_visual_to_words", blockId: row.id, slotId: insert.destinationSlotId,
    startTokenId: placement.startTokenId, endTokenId: placement.endTokenId,
  }, undefined, row.primaryVisualSequence.version);
  assertCurrent();
  const finalRow = findRow(attached?.document);
  if (!attached?.ok || !sameDocument(attached.document) || !sameWords(finalRow) ||
      !sourceGone(attached.document) ||
      finalRow.unattachedVisuals?.some((item) => item.slotId === insert.destinationSlotId) ||
      !finalRow.primaryVisualSequence?.slots.some((slot) => slot.id === insert.destinationSlotId)) {
    throw new Error("The saved visual could not be attached.");
  }
  return attached;
}

export function createStashActions(queueCommand, getDocument, makeId = uuid, queueExtras) {
  return {
    view: () => projectStash(getDocument()),
    stashRow: (rowId) => {
      const intent = captureWholeRowStash(getDocument(), [rowId]);
      return intent && queueExtras ? queueExtras((current) => wholeRowStashCommand(current, intent, makeId),
        "Stash row") : Promise.resolve(false);
    },
    placeSaved: (intent) => {
      const label = intent?.kind === "duplicate_stash_rows" ? "Duplicate saved row" :
        intent?.kind === "place_stash_rows" ? "Place saved material" : "Restore saved row";
      return intent && queueExtras ? queueExtras((current) => savedPlacementCommand(current, intent), label) :
        Promise.resolve(false);
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
    createSection: (title) => {
      const sectionId = makeId();
      return queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
        (current) => {
          if (typeof title !== "string" || !title.trim()) throw new Error("Enter a section name.");
          return { kind: "create_stash_section", sectionId, title: title.trim() };
        }, "Add Stash section");
    },
    renameSection: (sectionId, title) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current) => {
        if (!(current.stashSections ?? []).some((item) => item.id === sectionId) || typeof title !== "string" || !title.trim()) {
          throw new Error("Choose a current section and enter a name.");
        }
        return { kind: "rename_stash_section", sectionId, title: title.trim() };
      }, "Rename Stash section"),
    deleteSection: (sectionId) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current) => {
        if (!(current.stashSections ?? []).some((item) => item.id === sectionId)) throw new Error("The Stash section is no longer available.");
        return { kind: "delete_stash_section", sectionId };
      }, "Delete Stash section"),
    setCompletion: (rowId, completed) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current) => {
        if (typeof completed !== "boolean" || !outlineFor(current).some((item) => item.rowId === rowId && item.kind === "note")) {
          throw new Error("Choose a current Stash note.");
        }
        return { kind: "set_stash_completion", rowId, completed };
      }, completed ? "Complete Stash note" : "Reopen Stash note"),
    editNote: (rowId, text) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current, idFactory) => editedNoteCommand(current, rowId, text, idFactory), "Edit Stash note"),
    moveOutline: (rowId, destination) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current) => stashOutlineMoveCommand(current, rowId, destination), "Organize Stash"),
    deleteSaved: (rowId) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current) => {
        const outline = outlineFor(current);
        if (!outline.some((entry) => entry.rowId === rowId)) throw new Error("Choose a current saved item.");
        const group = current.stashGroups?.find((item) => item.rowIds.includes(rowId));
        const selected = descendantsOf(outline, group?.rowIds ?? [rowId]);
        const rowIds = outline.filter((entry) => selected.has(entry.rowId)).map((entry) => entry.rowId);
        const attachedClipIds = (current.stash ?? []).flatMap((bundle) => bundle.rows).flatMap((row) =>
          selected.has(row.id) && row.type === "narration" && row.attachedFootage ? [row.attachedFootage.clip.id] : []);
        return { kind: "delete_rows", rowIds, stashBranch: { attachedClipIds } };
      }, "Delete saved Stash material"),
    stashRows: (rowIds, destination, expectedModel) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current, idFactory) => {
        if (!Array.isArray(rowIds) || !rowIds.length || !rowIds.every((id) => typeof id === "string") ||
          new Set(rowIds).size !== rowIds.length) throw new Error("Choose a valid row selection.");
        const source = rowSections(current.activeDraft?.blocks ?? []).find(({ rows }) => {
          const start = rows.findIndex((row) => row.id === rowIds[0]);
          return start >= 0 && rowIds.every((id, offset) => rows[start + offset]?.id === id);
        });
        if (!source) throw new Error("The script rows changed. Select them again.");
        return { kind: "stash_rows", rowIds: [...rowIds], bundleId: idFactory(),
          ...(destination ? { destination: { ...destination } } : {}) };
      }, rowIds?.length > 1 ? "Stash rows" : "Stash row", true, expectedModel),
    stashVisual: (rowId, slotId, destination, expectedModel) => queueStashCommand(queueCommand, queueExtras,
      getDocument, makeId, (current, idFactory) => {
        const row = current.activeDraft?.blocks.find((item) => item.type === "narration" && item.id === rowId);
        const slot = row?.primaryVisualSequence?.slots.find((item) => item.kind === "content" && item.id === slotId);
        const unattached = row?.unattachedVisuals?.find((item) => item.slotId === slotId);
        const visual = slot?.payload?.kind === "visual" ? slot.payload : unattached?.payload;
        if (!row || !visual || visual.pictureKind === "on_camera") throw new Error("Choose a current storable visual.");
        return { kind: "stash_visual", rowId, slotId, bundleId: idFactory(), stashRowId: idFactory(),
          sectionId: destination?.sectionId ?? null, parentRowId: destination?.parentRowId ?? null,
          afterRowId: destination?.afterRowId ?? null };
      }, "Stash visual", false, expectedModel),
    insertStashVisual: (stashRowId, destinationRowId, destinationSlotId, expectedModel, selectedDrop) => {
      const model = getDocument();
      if (!model || expectedModel && model !== expectedModel ||
          selectedDrop && (!selectedDropPlacement(model, selectedDrop) || selectedDrop.rowId !== destinationRowId)) return Promise.resolve(false);
      const projectId = model.projectId;
      const documentId = model.id;
      const snapshot = documentStashSnapshot(model);
      const draft = JSON.stringify(model.activeDraft);
      return queueCommand((current) => {
        if (current.projectId !== projectId || current.id !== documentId ||
          documentStashSnapshot(current) !== snapshot || JSON.stringify(current.activeDraft) !== draft ||
          selectedDrop && !selectedDropPlacement(current, selectedDrop)) {
          throw new Error("The Stash item or script row changed. Drag again.");
        }
        return { kind: "insert_stash_visual", stashRowId, destinationRowId, destinationSlotId };
      }, "Add Stash visual", { structural: true, ...(selectedDrop ? { selectedStashDrop: selectedDrop } : {}) });
    },
    attachFootage: (noteRowId, clipRowId, replace = false) => queueStashCommand(queueCommand, queueExtras,
      getDocument, makeId, (current, idFactory) => {
        const note = projectStash(current).flatMap((section) => section.entries)
          .find((entry) => entry.rowId === noteRowId && entry.kind === "note");
        const clip = projectStash(current).flatMap((section) => section.entries)
          .find((entry) => entry.rowId === clipRowId && entry.kind === "clip");
        if (!note || !clip || Boolean(note.row.attachedFootage) !== replace) {
          throw new Error("Choose a current note and independent saved clip.");
        }
        return { kind: replace ? "replace_stash_footage" : "attach_stash_footage",
          noteRowId, clipRowId, ...(replace ? { releasedBundleId: idFactory() } : {}) };
      }, replace ? "Replace Stash footage" : "Attach Stash footage"),
    detachFootage: (noteRowId, destination, expectedModel) => queueStashCommand(queueCommand, queueExtras, getDocument, makeId,
      (current, idFactory) => {
        const note = projectStash(current).flatMap((section) => section.entries)
          .find((entry) => entry.rowId === noteRowId && entry.kind === "note");
        if (!note?.row.attachedFootage) throw new Error("This note has no attached footage.");
        return { kind: "detach_stash_footage", noteRowId, bundleId: idFactory(),
          ...(destination ? { destination } : {}) };
      }, "Detach Stash footage", false, expectedModel),
    placeAttached: (noteRowId, destination, expectedModel) => queueStashCommand(queueCommand, queueExtras,
      getDocument, makeId, { kind: "place_attached_footage", noteRowId, destination }, "Place attached footage", false, expectedModel),
    stashGroup: (rowIds, sectionId = null, parentRowId = null, afterRowId = null) => {
      const current = getDocument();
      const intent = captureWholeRowStash(current, rowIds);
      if (!intent) return Promise.resolve(false);
      const groupId = makeId();
      return queueCommand((latest) => {
        if (latest.projectId !== intent.projectId || latest.id !== intent.documentId ||
          JSON.stringify(latest.activeDraft) !== intent.draftSnapshot || documentStashSnapshot(latest) !== intent.stashSnapshot) {
          throw new Error("The rows or Stash changed. Select them again.");
        }
        return { kind: "stash_group_rows", rowIds: [...intent.rowIds], bundleId: makeId(), groupId,
          sectionId, parentRowId, afterRowId };
      }, "Stash group", { structural: true });
    },
    placeGroup: (groupId, destination, expectedModel) => {
      const model = getDocument();
      if (!model || expectedModel && model !== expectedModel) return Promise.resolve(false);
      const intent = captureStashGroupPlacement(model, groupId, destination);
      if (!intent) return Promise.resolve(false);
      return queueCommand((current) => stashGroupPlacementCommand(current, intent), "Place Stash group", { structural: true });
    },
    saveMembers: (members, metadata) => {
      const model = getDocument();
      if (!model || !Array.isArray(members) || !metadata ||
        metadata.expectedRevision !== (model.rowEditRevision ?? 0) || !Array.isArray(metadata.expectedRowIds)) {
        return Promise.resolve(false);
      }
      const snapshot = documentStashSnapshot(model);
      const projectId = model.projectId;
      const documentId = model.id;
      return queueCommand((current) => {
        if (current.projectId !== projectId || current.id !== documentId ||
          documentStashSnapshot(current) !== snapshot || (current.rowEditRevision ?? 0) !== metadata.expectedRevision) {
          throw new Error("The Stash group changed. Reopen the editor and review it again.");
        }
        if (metadata.groupId === null) {
          if (members.length !== 1 || metadata.expectedRowIds.length !== 1 ||
            members[0]?.id !== metadata.expectedRowIds[0]) throw new Error("Choose one current saved row to edit.");
          return { kind: "edit_row", rowId: members[0].id, row: members[0] };
        }
        if (members.length > 4096 || members.some((member) => !member || typeof member.id !== "string")) {
          throw new Error("Review the saved group members and try again.");
        }
        return { kind: "save_stash_group", groupId: metadata.groupId,
          expectedRevision: metadata.expectedRevision, expectedRowIds: [...metadata.expectedRowIds],
          members: structuredClone(members) };
      }, metadata.groupId === null ? "Edit saved row" : "Save Stash group", { structural: true });
    },
  };
}
