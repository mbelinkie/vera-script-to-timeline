/*
 * Row authoring controls for the read-only renderer.
 *
 * This module owns DOM state only. Every document change is emitted through
 * `command`; the caller applies the pure contract command and rerenders.
 */

const ROW_TYPES = new Set(["narration", "direction", "note_draft", "visual_only"]);
const GENERATED = "[data-rows-editor-generated]";

function isRow(value) {
  return !!value && typeof value === "object" && ROW_TYPES.has(value.type) && typeof value.id === "string";
}

function blocksOf(scriptDocument) {
  const blocks = scriptDocument?.activeDraft?.blocks;
  return Array.isArray(blocks) ? blocks : [];
}

function shortText(value, fallback) {
  const text = typeof value === "string" ? value.trim().replace(/\s+/gu, " ") : "";
  if (!text) return fallback;
  return text.length > 96 ? `${text.slice(0, 93)}…` : text;
}

/** Content-based labels are stable across insertion, movement and undo. */
export function rowLabel(block) {
  if (!isRow(block)) return "Empty row";
  if (block.type === "visual_only") return "Visual-only row";
  const fallback = block.type === "direction" ? "Empty direction" :
    block.type === "note_draft" ? "Empty draft note" : "Empty narration";
  return shortText(block.text, fallback);
}

/** Return the active rows grouped by the section heading immediately before them. */
export function rowSections(blocks) {
  const result = [];
  let sectionId = null;
  let rows = [];
  const push = () => {
    result.push({ sectionId, rows });
    rows = [];
  };

  for (const block of Array.isArray(blocks) ? blocks : []) {
    if (block?.type === "section") {
      push();
      sectionId = typeof block.id === "string" ? block.id : null;
    } else if (isRow(block)) {
      rows.push(block);
    }
  }
  push();
  return result;
}

function rowIndex(blocks) {
  const index = new Map();
  for (const section of rowSections(blocks)) {
    section.rows.forEach((row, position) => index.set(row.id, {
      row,
      rows: section.rows,
      sectionId: section.sectionId,
      position,
    }));
  }
  return index;
}

/** Select an inclusive contiguous range. Ranges cannot cross a section break. */
export function rowRange(blocks, anchorId, focusId) {
  const index = rowIndex(blocks);
  const anchor = index.get(anchorId);
  const focus = index.get(focusId);
  if (!anchor || !focus || anchor.sectionId !== focus.sectionId) return null;
  const from = Math.min(anchor.position, focus.position);
  const to = Math.max(anchor.position, focus.position);
  return anchor.rows.slice(from, to + 1).map((row) => row.id);
}

/** Every exact insertion gap, including before/after a section's rows. */
export function rowGaps(blocks) {
  return rowSections(blocks).flatMap(({ sectionId, rows }) => {
    const gaps = [];
    for (let position = 0; position <= rows.length; position += 1) {
      gaps.push({
        sectionId,
        afterRowId: rows[position - 1]?.id ?? null,
        beforeRowId: rows[position]?.id ?? null,
      });
    }
    return gaps;
  });
}

function gapKey(gap) {
  return [gap.sectionId ?? "", gap.afterRowId ?? "", gap.beforeRowId ?? ""].join("|");
}

function rowsInRoot(root) {
  return [...root.children].filter((child) => child.classList?.contains("script-row"));
}

function rowNode(root, rowId) {
  return rowsInRoot(root).find((row) => row.dataset.rowId === rowId) ?? null;
}

function button(ownerDocument, className, label, text = label) {
  const element = ownerDocument.createElement("button");
  element.type = "button";
  element.className = className;
  element.setAttribute("aria-label", label);
  element.textContent = text;
  return element;
}

function removeGenerated(root) {
  root.querySelectorAll(GENERATED).forEach((element) => element.remove());
}

function currentRangeIds(state) {
  if (!state.range) return [];
  return rowRange(blocksOf(state.scriptDocument), state.range.anchorId, state.range.focusId) ?? [];
}

function confirmDelete(state, rowIds) {
  if (typeof state.confirmDelete === "function") return state.confirmDelete(rowIds);
  if (typeof globalThis.confirm !== "function") return true;
  const subject = rowIds.length === 1 ? "this row" : `${rowIds.length} selected rows`;
  return globalThis.confirm(`Delete ${subject}?`);
}

function setFocusedRow(root, rowId) {
  for (const row of rowsInRoot(root)) row.tabIndex = row.dataset.rowId === rowId ? 0 : -1;
}

function focusRow(root, rowId) {
  const row = rowNode(root, rowId);
  if (!row) return;
  row.focus();
  row.scrollIntoView?.({ block: "nearest" });
}

function focusRowMenu(root, rowId) {
  rowNode(root, rowId)?.querySelector("[data-row-action-trigger]")?.focus();
}

function rangeSummary(state, ids) {
  const index = rowIndex(blocksOf(state.scriptDocument));
  const first = index.get(ids[0]);
  const last = index.get(ids.at(-1));
  if (!first || !last) return `${ids.length} ${ids.length === 1 ? "row" : "rows"} selected`;
  return `${ids.length} ${ids.length === 1 ? "row" : "rows"} selected, from “${rowLabel(first.row)}” to “${rowLabel(last.row)}”`;
}

function closeMenus(root) {
  root.querySelectorAll("[data-row-action-menu]").forEach((menu) => { menu.hidden = true; });
  root.querySelectorAll("[data-row-action-trigger]").forEach((trigger) => {
    trigger.setAttribute("aria-expanded", "false");
  });
}

function makeRowActions(state, rowElement) {
  const rowId = rowElement.dataset.rowId;
  const row = rowIndex(blocksOf(state.scriptDocument)).get(rowId)?.row;
  const label = rowLabel(row);
  const actions = state.root.ownerDocument.createElement("div");
  actions.className = "row-actions";
  actions.dataset.rowsEditorGenerated = "true";

  const trigger = button(state.root.ownerDocument, "", "⋯");
  trigger.className = "row-actions__trigger";
  trigger.dataset.rowActionTrigger = "true";
  trigger.draggable = true;
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-label", `Row actions for “${label}”`);
  actions.append(trigger);

  const menu = state.root.ownerDocument.createElement("div");
  menu.className = "row-actions__menu";
  menu.dataset.rowActionMenu = "true";
  menu.setAttribute("role", "menu");
  menu.hidden = true;

  const deleteButton = button(state.root.ownerDocument, "", "Delete row");
  deleteButton.dataset.rowDelete = rowId;
  deleteButton.dataset.rowAction = "delete";
  deleteButton.setAttribute("role", "menuitem");
  menu.append(deleteButton);

  const selectButton = button(state.root.ownerDocument, "", "Select range");
  selectButton.dataset.rowSelectRange = rowId;
  selectButton.dataset.rowAction = "select-range";
  selectButton.setAttribute("role", "menuitem");
  menu.append(selectButton);

  const groupDelete = button(state.root.ownerDocument, "", "Delete group");
  groupDelete.dataset.rowRangeAction = "delete-group";
  groupDelete.dataset.rowAction = "delete-group";
  groupDelete.setAttribute("role", "menuitem");
  menu.append(groupDelete);

  const newRange = button(state.root.ownerDocument, "", "Select new range");
  newRange.dataset.rowRangeAction = "new-range";
  newRange.dataset.rowSelectRange = rowId;
  newRange.dataset.rowAction = "new-range";
  newRange.setAttribute("role", "menuitem");
  menu.append(newRange);

  actions.append(menu);
  rowElement.append(actions);
}

function updateRowActions(state, selected) {
  for (const row of rowsInRoot(state.root)) {
    const isSelected = selected.has(row.dataset.rowId);
    row.classList.toggle("script-row--selected", isSelected);
    row.dataset.rangeSelected = String(isSelected);
    row.querySelectorAll("[data-row-range-action]").forEach((action) => {
      action.hidden = !isSelected || !state.range?.confirmed;
    });
    row.querySelectorAll("[data-row-action='delete'], [data-row-action='select-range']").forEach((action) => {
      action.hidden = isSelected && !!state.range?.confirmed;
    });
  }
}

function updateRangeState(state) {
  const ids = currentRangeIds(state);
  const selected = new Set(ids);
  updateRowActions(state, selected);
  state.root.querySelectorAll(GENERATED).forEach((element) => {
    if (element.classList.contains("row-range-toolbar")) element.remove();
  });
  if (!state.range) {
    delete state.root.dataset.rowRangeMode;
    setFocusedRow(state.root, "");
    return;
  }

  state.root.dataset.rowRangeMode = state.range.confirmed ? "confirmed" : "choosing";
  const toolbar = state.root.ownerDocument.createElement("div");
  toolbar.className = "row-range-toolbar";
  toolbar.dataset.rowsEditorGenerated = "true";
  toolbar.setAttribute("role", "status");
  toolbar.setAttribute("aria-live", "polite");

  const hint = state.root.ownerDocument.createElement("span");
  hint.className = "row-range-toolbar__hint";
  hint.textContent = state.range.confirmed ? rangeSummary(state, ids) :
    "Select the last row in the range. Escape cancels.";
  toolbar.append(hint);

  if (ids.length > 0 && state.range.confirmed) {
    const deleteButton = button(state.root.ownerDocument, "row-range-toolbar__delete", "Delete selected rows", "Delete group");
    deleteButton.dataset.rowRangeDelete = "true";
    toolbar.append(deleteButton);
  }
  const cancelButton = button(state.root.ownerDocument, "row-range-toolbar__cancel", "Cancel row range", "Cancel");
  cancelButton.dataset.rowRangeCancel = "true";
  toolbar.append(cancelButton);
  state.root.prepend(toolbar);
  setFocusedRow(state.root, state.range.focusId);
}

function decorateGaps(state) {
  state.root.querySelectorAll(".row-divider[data-rows-editor-generated]").forEach((element) => element.remove());
  const blocks = blocksOf(state.scriptDocument);
  const rows = new Map(rowsInRoot(state.root).map((row) => [row.dataset.rowId, row]));
  const headings = [...state.root.children].filter((child) => child.classList?.contains("script-section-heading"));
  const headingBySection = new Map();
  let headingIndex = 0;
  for (const section of rowSections(blocks)) {
    if (section.sectionId !== null) headingBySection.set(section.sectionId, headings[headingIndex++] ?? null);
  }

  for (const gap of rowGaps(blocks)) {
    const divider = state.root.ownerDocument.createElement("div");
    divider.className = "row-divider";
    divider.dataset.rowsEditorGenerated = "true";
    divider.dataset.rowGap = gapKey(gap);
    divider.dataset.sectionId = gap.sectionId ?? "";
    if (gap.afterRowId) divider.dataset.afterRowId = gap.afterRowId;
    if (gap.beforeRowId) divider.dataset.beforeRowId = gap.beforeRowId;
    const add = button(state.root.ownerDocument, "row-divider__add", "Add row", "+ Add row");
    add.dataset.rowAdd = "true";
    divider.append(add);

    const before = gap.beforeRowId ? rows.get(gap.beforeRowId) : null;
    const after = gap.afterRowId ? rows.get(gap.afterRowId) : null;
    if (before) before.before(divider);
    else if (after) after.after(divider);
    else if (gap.sectionId !== null && headingBySection.get(gap.sectionId)) headingBySection.get(gap.sectionId).after(divider);
    else {
      const firstHeading = headings[0];
      if (firstHeading) firstHeading.before(divider);
      else state.root.append(divider);
    }
  }
}

function decorate(state) {
  removeGenerated(state.root);
  for (const row of rowsInRoot(state.root)) makeRowActions(state, row);
  decorateGaps(state);
  if (state.range && !rowRange(blocksOf(state.scriptDocument), state.range.anchorId, state.range.focusId)) state.range = null;
  updateRangeState(state);
}

function eventElement(event) {
  const target = event.target;
  return target && typeof target.closest === "function" ? target : null;
}

function rowFromEvent(event) {
  return eventElement(event)?.closest(".script-row") ?? null;
}

function rowIdFromEvent(event) {
  return rowFromEvent(event)?.dataset.rowId ?? null;
}

function gapFromDivider(divider) {
  return {
    sectionId: divider.dataset.sectionId || null,
    afterRowId: divider.dataset.afterRowId ?? null,
    beforeRowId: divider.dataset.beforeRowId ?? null,
  };
}

function destinationForDrop(state, rowIds, targetId, placeBefore) {
  const blocks = blocksOf(state.scriptDocument);
  const target = rowIndex(blocks).get(targetId);
  if (!target || rowIds.some((id) => !rowIndex(blocks).has(id))) return null;
  const remaining = target.rows.filter((row) => !rowIds.includes(row.id));
  const targetPosition = remaining.findIndex((row) => row.id === targetId);
  if (targetPosition < 0) return null;
  const position = placeBefore ? targetPosition : targetPosition + 1;
  return {
    sectionId: target.sectionId,
    afterRowId: remaining[position - 1]?.id ?? null,
    beforeRowId: remaining[position]?.id ?? null,
  };
}

function destinationForGap(state, rowIds, gap) {
  const section = rowSections(blocksOf(state.scriptDocument)).find((part) => part.sectionId === gap.sectionId);
  if (!section || !section.rows.some((row) => row.id === gap.afterRowId) && gap.afterRowId !== null ||
      !section.rows.some((row) => row.id === gap.beforeRowId) && gap.beforeRowId !== null) return null;
  const remaining = section.rows.filter((row) => !rowIds.includes(row.id));
  const position = gap.beforeRowId === null
    ? remaining.length
    : remaining.findIndex((row) => row.id === gap.beforeRowId);
  if (position < 0) return null;
  return {
    sectionId: gap.sectionId,
    afterRowId: remaining[position - 1]?.id ?? null,
    beforeRowId: remaining[position]?.id ?? null,
  };
}

function clearRange(state) {
  state.range = null;
  closeMenus(state.root);
  updateRangeState(state);
}

async function emit(state, command, label) {
  if (state.busy || typeof state.command !== "function") return false;
  state.busy = true;
  closeMenus(state.root);
  try {
    const result = await state.command(command, label);
    const failed = result === false || result?.ok === false;
    if (!failed) {
      state.range = null;
      updateRangeState(state);
    }
    return !failed;
  } catch (error) {
    state.onCommandError?.(error, command, label);
    return false;
  } finally {
    state.busy = false;
  }
}

function randomId(state) {
  if (typeof state.idFactory === "function") return state.idFactory();
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
  throw new Error("A UUID factory is required to add a row in this browser.");
}

function beginRange(state, rowId) {
  if (!rowIndex(blocksOf(state.scriptDocument)).has(rowId)) return;
  state.range = { anchorId: rowId, focusId: rowId, confirmed: false };
  decorate(state);
  focusRow(state.root, rowId);
}

function finishPointerRange(state, rowId) {
  if (!state.range || !rowId) return;
  const ids = rowRange(blocksOf(state.scriptDocument), state.range.anchorId, rowId);
  if (!ids) return;
  state.range.focusId = rowId;
  state.range.confirmed = true;
  updateRangeState(state);
}

function moveRangeFocus(state, direction) {
  if (!state.range) return;
  const info = rowIndex(blocksOf(state.scriptDocument)).get(state.range.focusId);
  const next = info?.rows[info.position + direction];
  if (!next) return;
  state.range.focusId = next.id;
  state.range.confirmed = false;
  updateRangeState(state);
  focusRow(state.root, next.id);
}

function handleClick(state, event) {
  const target = eventElement(event);
  if (!target) return;

  const trigger = target.closest("[data-row-action-trigger]");
  if (trigger) {
    const menu = trigger.parentElement?.querySelector("[data-row-action-menu]");
    const open = !!menu && menu.hidden;
    closeMenus(state.root);
    if (menu) {
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) menu.querySelector("button:not([hidden])")?.focus();
    }
    event.stopPropagation();
    return;
  }

  const add = target.closest("[data-row-add]");
  if (add) {
    const divider = add.closest("[data-row-gap]");
    const destination = divider ? gapFromDivider(divider) : null;
    if (!destination || typeof state.createBlankRow !== "function") return;
    const row = state.createBlankRow({ id: randomId(state), destination, scriptDocument: state.scriptDocument });
    if (row) void emit(state, { kind: "create_row", row, destination }, "Add row");
    return;
  }

  const deleteButton = target.closest("[data-row-delete]");
  if (deleteButton) {
    const rowId = deleteButton.dataset.rowDelete;
    if (rowId && confirmDelete(state, [rowId])) void emit(state, { kind: "delete_rows", rowIds: [rowId] }, "Delete row");
    return;
  }

  const select = target.closest("[data-row-select-range]");
  if (select) {
    const rowId = select.dataset.rowSelectRange;
    if (!rowId) return;
    if (select.dataset.rowAction === "new-range") clearRange(state);
    beginRange(state, rowId);
    return;
  }

  const groupDelete = target.closest("[data-row-range-delete], [data-row-range-action='delete-group']");
  if (groupDelete) {
    const ids = currentRangeIds(state);
    if (ids.length && confirmDelete(state, ids)) void emit(state, { kind: "delete_rows", rowIds: ids }, "Delete group");
    return;
  }

  if (target.closest("[data-row-range-cancel]")) {
    clearRange(state);
    return;
  }

  if (state.range && target.closest(".script-row") && !target.closest("[data-row-actions]")) {
    finishPointerRange(state, rowIdFromEvent(event));
    return;
  }
  if (!target.closest("[data-row-actions], .row-divider")) closeMenus(state.root);
}

function handleKeydown(state, event) {
  if (event.key === "Escape") {
    if (state.range) {
      event.preventDefault();
      clearRange(state);
    } else if (eventElement(event)?.closest("[data-row-action-menu]")) {
      event.preventDefault();
      closeMenus(state.root);
    }
    return;
  }
  if (!state.range || eventElement(event)?.closest("[contenteditable], textarea, input, select, [data-row-action-menu], [data-row-action-trigger]")) return;
  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveRangeFocus(state, -1);
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    moveRangeFocus(state, 1);
  } else if (event.key === "Enter") {
    event.preventDefault();
    state.range.confirmed = true;
    updateRangeState(state);
    const ids = currentRangeIds(state);
    if (ids[0]) focusRowMenu(state.root, ids[0]);
  }
}

function handleDragstart(state, event) {
  const trigger = eventElement(event)?.closest("[data-row-action-trigger]");
  if (!trigger || !event.dataTransfer) return;
  const sourceId = rowIdFromEvent(event);
  if (!sourceId) return;
  const selected = currentRangeIds(state);
  const rowIds = state.range && selected.includes(sourceId) ? selected : [sourceId];
  state.drag = { rowIds };
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", JSON.stringify({ rowIds }));
  rowIds.forEach((id) => rowNode(state.root, id)?.classList.add("script-row--dragging"));
}

function clearDrag(state) {
  rowsInRoot(state.root).forEach((row) => row.classList.remove("script-row--dragging", "script-row--drop-target"));
  state.root.querySelectorAll(".row-divider--drop-target").forEach((divider) => divider.classList.remove("row-divider--drop-target"));
  state.drag = null;
  state.dropDestination = null;
}

function handleDragover(state, event) {
  if (!state.drag) return;
  const target = eventElement(event);
  const targetRow = target?.closest(".script-row");
  const divider = target?.closest("[data-row-gap]");
  const rowIds = state.drag.rowIds;
  let destination = divider ? destinationForGap(state, rowIds, gapFromDivider(divider)) : null;
  if (targetRow && !divider) {
    const rect = targetRow.getBoundingClientRect();
    destination = destinationForDrop(state, rowIds, targetRow.dataset.rowId, event.clientY < rect.top + rect.height / 2);
  }
  if (!destination || rowIds.some((id) => destination.afterRowId === id || destination.beforeRowId === id)) {
    clearDragTargets(state);
    return;
  }
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
  clearDragTargets(state);
  targetRow?.classList.add("script-row--drop-target");
  divider?.classList.add("row-divider--drop-target");
  state.dropDestination = destination;
}

function clearDragTargets(state) {
  rowsInRoot(state.root).forEach((row) => row.classList.remove("script-row--drop-target"));
  state.root.querySelectorAll(".row-divider--drop-target").forEach((divider) => divider.classList.remove("row-divider--drop-target"));
  state.dropDestination = null;
}

function handleDrop(state, event) {
  if (!state.drag || !state.dropDestination) return;
  event.preventDefault();
  const rowIds = [...state.drag.rowIds];
  const destination = { ...state.dropDestination };
  clearDrag(state);
  void emit(state, { kind: "move_rows", rowIds, destination }, rowIds.length > 1 ? "Move rows" : "Move row");
}

function install(state) {
  state.root.addEventListener("click", state.onClick);
  state.root.addEventListener("keydown", state.onKeydown);
  state.root.addEventListener("dragstart", state.onDragstart);
  state.root.addEventListener("dragover", state.onDragover);
  state.root.addEventListener("drop", state.onDrop);
  state.root.addEventListener("dragend", state.onDragend);
}

function uninstall(state) {
  state.root.removeEventListener("click", state.onClick);
  state.root.removeEventListener("keydown", state.onKeydown);
  state.root.removeEventListener("dragstart", state.onDragstart);
  state.root.removeEventListener("dragover", state.onDragover);
  state.root.removeEventListener("drop", state.onDrop);
  state.root.removeEventListener("dragend", state.onDragend);
}

const instances = new WeakMap();

/**
 * Decorate current `.script-row` elements and their dividers with authoring
 * controls. The callback may return a Promise; false or `{ ok: false }` keeps
 * range state in place. A successful callback should apply the contract
 * command and rerender before resolving.
 */
export function mountRowsEditor(root, scriptDocument, options = {}) {
  if (!root || !root.ownerDocument) return () => {};
  let state = instances.get(root);
  if (!state) {
    state = {
      root,
      scriptDocument,
      command: options.command,
      createBlankRow: options.createBlankRow,
      confirmDelete: options.confirmDelete,
      idFactory: options.idFactory,
      onCommandError: options.onCommandError,
      range: null,
      drag: null,
      dropDestination: null,
      busy: false,
    };
    state.onClick = (event) => handleClick(state, event);
    state.onKeydown = (event) => handleKeydown(state, event);
    state.onDragstart = (event) => handleDragstart(state, event);
    state.onDragover = (event) => handleDragover(state, event);
    state.onDrop = (event) => handleDrop(state, event);
    state.onDragend = () => clearDrag(state);
    install(state);
    state.destroy = () => {
      clearDrag(state);
      uninstall(state);
      instances.delete(root);
    };
    instances.set(root, state);
  } else {
    state.scriptDocument = scriptDocument;
    Object.assign(state, options);
  }
  decorate(state);
  return state.destroy;
}

export function deleteRowsCommand(rowIds) {
  return { kind: "delete_rows", rowIds: [...rowIds] };
}

export function moveRowsCommand(rowIds, destination) {
  return { kind: "move_rows", rowIds: [...rowIds], destination: { ...destination } };
}

export function createRowCommand(row, destination) {
  return { kind: "create_row", row, destination: { ...destination } };
}

/**
 * Make the smallest valid authored blank row for the Add row control. The
 * contract keeps an empty narration row's single base picture, so new rows
 * start on the default On Camera passage until words are entered.
 */
export function createBlankNarrationRow({ id, idFactory } = {}) {
  const makeId = typeof idFactory === "function" ? idFactory : () => {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
    throw new Error("A UUID factory is required to create a blank row in this browser.");
  };
  const rowId = id ?? makeId();
  return {
    type: "narration",
    id: rowId,
    orderKey: `row-${rowId}`,
    text: "",
    tokens: [],
    primaryVisualSequence: {
      id: makeId(),
      slots: [{
        id: makeId(),
        kind: "content",
        relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval",
        version: 1,
      }],
      version: 1,
    },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "active",
    notes: [],
    version: 1,
  };
}
