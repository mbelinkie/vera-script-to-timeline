import { createBlankNarrationRow } from "./rows-editor.js";
import { mountNarration } from "./narration-editor.js";
import { mountVisualCardMenus, renderRows } from "./view.js";

const rowKinds = new Set(["narration", "direction", "note_draft", "visual_only"]);
const markerTitle = "Saved rows";

function clone(value) {
  return structuredClone(value);
}

function isRow(value) {
  return value && typeof value === "object" && rowKinds.has(value.type) && typeof value.id === "string";
}

function newId() {
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    throw new Error("A UUID factory is required to add a saved row.");
  }
  return globalThis.crypto.randomUUID();
}

/** Build a private model on which the existing row editor commands can operate. */
export function createStashRowEditorDocument(documentModel, members, groupId = null) {
  if (!documentModel || !Array.isArray(members) || !members.length ||
      members.some((row) => !isRow(row)) || new Set(members.map((row) => row.id)).size !== members.length) {
    throw new TypeError("Choose one or more saved rows to edit.");
  }
  const expectedIds = members.map((row) => row.id);
  const savedRows = new Map((documentModel.stash ?? []).flatMap((bundle) =>
    (bundle.rows ?? []).map((row) => [row.id, row])));
  if (expectedIds.some((id, index) => !savedRows.has(id) ||
      JSON.stringify(savedRows.get(id)) !== JSON.stringify(members[index]))) {
    throw new Error("The saved rows changed. Reopen them before editing.");
  }

  const groupedIds = new Set((documentModel.stashGroups ?? []).flatMap((group) => group.rowIds));
  if (groupId) {
    const group = (documentModel.stashGroups ?? []).find((candidate) => candidate.id === groupId);
    if (!group || JSON.stringify(group.rowIds) !== JSON.stringify(expectedIds)) {
      throw new Error("The saved group membership changed. Reopen it before editing.");
    }
  } else if (members.length !== 1 || groupedIds.has(expectedIds[0])) {
    throw new Error("Edit a saved group as a group.");
  }

  const staged = clone(documentModel);
  const stagedIds = new Set(expectedIds);
  staged.stash = (staged.stash ?? []).flatMap((bundle) => {
    const rows = (bundle.rows ?? []).filter((row) => !stagedIds.has(row.id));
    return rows.length || bundle.supportingItems?.length ? [{ ...bundle, rows }] : [];
  });
  if (!staged.stash.length) delete staged.stash;
  if (Array.isArray(staged.stashOutline)) {
    staged.stashOutline = staged.stashOutline.filter((entry) => !stagedIds.has(entry.rowId));
  }
  if (Array.isArray(staged.stashSections)) {
    staged.stashSections = staged.stashSections.map((section) => ({
      ...section,
      ...(Array.isArray(section.rowIds) ? { rowIds: section.rowIds.filter((id) => !stagedIds.has(id)) } : {}),
    }));
  }
  staged.stashGroups = (staged.stashGroups ?? []).filter((group) => group.id !== groupId);
  if (!staged.stashGroups.length) delete staged.stashGroups;

  const markerId = newId();
  staged.activeDraft.blocks = [
    ...(staged.activeDraft.blocks ?? []),
    { type: "section", id: markerId, title: markerTitle, orderKey: `editor-${markerId}`, version: 1 },
    ...clone(members),
  ];
  return staged;
}

function stagedRows(documentModel) {
  const blocks = documentModel?.activeDraft?.blocks ?? [];
  const marker = blocks.findLastIndex((block) => block.type === "section" && block.title === markerTitle);
  if (marker < 0) return [];
  return blocks.slice(marker + 1).filter(isRow);
}

function selectionOffset(root, selection) {
  if (!selection?.rangeCount || !root.contains(selection.anchorNode)) return null;
  try {
    const range = root.ownerDocument.createRange();
    range.selectNodeContents(root);
    range.setEnd(selection.anchorNode, selection.anchorOffset);
    return range.toString().length;
  } catch { return null; }
}

function restoreCaret(root, offset) {
  if (offset === null || offset === undefined) { root.focus(); return; }
  const document = root.ownerDocument;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  let remaining = offset;
  while ((node = walker.nextNode())) {
    if (remaining <= node.length) {
      const range = document.createRange();
      range.setStart(node, remaining);
      range.collapse(true);
      const selection = document.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      root.focus();
      return;
    }
    remaining -= node.length;
  }
  root.focus();
}

/** Detached saved-row/group editor. No command writes the canonical document. */
export function mountStashRowEditor({ host, getDocument, applyCommand, fetchProjection, onSave }) {
  if (!host?.ownerDocument || typeof getDocument !== "function" || typeof applyCommand !== "function") {
    throw new TypeError("The saved-row editor needs a host, document reader and command adapter.");
  }
  const document = host.ownerDocument;
  const dialog = document.createElement("dialog");
  dialog.className = "stash-row-editor";
  dialog.setAttribute("aria-labelledby", "stash-row-editor-heading");
  const header = document.createElement("header");
  header.className = "stash-row-editor__header";
  const heading = document.createElement("h2");
  heading.id = "stash-row-editor-heading";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "stash-row-editor__close";
  close.setAttribute("aria-label", "Close saved row editor");
  close.textContent = "×";
  header.append(heading, close);

  const rowsRoot = document.createElement("div");
  rowsRoot.className = "stash-row-editor__rows";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "stash-row-editor__add";
  add.textContent = "Add row";
  const status = document.createElement("p");
  status.className = "stash-row-editor__status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const footer = document.createElement("footer");
  footer.className = "stash-row-editor__footer";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  const save = document.createElement("button");
  save.type = "button";
  save.className = "stash-row-editor__save";
  save.textContent = "Save";
  footer.append(cancel, save);

  const prompt = document.createElement("div");
  prompt.className = "stash-row-editor__prompt";
  prompt.hidden = true;
  prompt.setAttribute("role", "group");
  prompt.setAttribute("aria-label", "Unsaved saved-row changes");
  const promptText = document.createElement("span");
  promptText.textContent = "Save your changes to this row?";
  const promptSave = document.createElement("button");
  promptSave.type = "button";
  promptSave.textContent = "Save";
  const discard = document.createElement("button");
  discard.type = "button";
  discard.textContent = "Don’t save";
  const keep = document.createElement("button");
  keep.type = "button";
  keep.textContent = "Keep editing";
  prompt.append(promptText, promptSave, discard, keep);
  dialog.append(header, rowsRoot, add, status, footer, prompt);
  document.body.append(dialog);

  let session = null;
  let stageDocument = null;
  let baselineMembers = [];
  let inactiveIds = new Set();
  let projection = null;
  let cleanup = [];
  let pending = false;
  let queued = Promise.resolve();
  let closeAfterSave = false;
  let reopenAfterClose = null;
  let requestedFocus = null;

  const allStageRows = () => stagedRows(stageDocument);
  const currentMembers = () => allStageRows().filter((row) => !inactiveIds.has(row.id));
  const dirty = () => JSON.stringify(currentMembers()) !== JSON.stringify(baselineMembers);
  const label = () => session?.groupId ? "this group" : "this row";

  function captureFocus() {
    const active = document.activeElement;
    if (!active?.matches?.("[data-narration-editor]")) return null;
    return { rowId: active.closest("[data-row-id]")?.dataset.rowId,
      offset: selectionOffset(active, document.getSelection()) };
  }

  function focusCaptured(focus) {
    if (!focus?.rowId) return;
    const editor = [...rowsRoot.querySelectorAll("[data-narration-editor]")]
      .find((item) => item.closest("[data-row-id]")?.dataset.rowId === focus.rowId);
    if (editor) restoreCaret(editor, focus.offset);
  }

  function render() {
    cleanup.forEach((dispose) => dispose?.());
    cleanup = [];
    const visibleMembers = currentMembers();
    const renderedDocument = { ...stageDocument,
      activeDraft: { ...stageDocument.activeDraft, blocks: clone(visibleMembers) } };
    renderRows(rowsRoot, renderedDocument, { projection,
      visualCommand: (command, caption) => stageCommand(command, caption),
    });
    cleanup.push(mountVisualCardMenus(rowsRoot, (command, caption) => stageCommand(command, caption)));
    for (const cell of rowsRoot.querySelectorAll(".script-row .narration-cell")) {
      cleanup.push(mountNarration(cell, renderedDocument,
        (command, caption, meta) => stageCommand(command, caption, meta), {
          projection: projection?.rows?.find((row) => row.blockId === cell.closest("[data-row-id]")?.dataset.rowId),
          visualCommand: (command, caption) => stageVisualCommand(command, caption),
          requestRender: () => {
            const focus = captureFocus();
            void refreshProjection().then(() => {
              render();
              focusCaptured(focus);
            });
          },
        }));
    }

    for (const row of visibleMembers) {
      const rowElement = [...rowsRoot.querySelectorAll("[data-row-id]")]
        .find((item) => item.dataset.rowId === row.id);
      if (!rowElement || !session?.groupId) continue;
      const controls = document.createElement("div");
      controls.className = "stash-row-editor__row-controls";
      const insert = document.createElement("button");
      insert.type = "button";
      insert.textContent = "Add row below";
      insert.setAttribute("aria-label", `Add row below ${row.text || "saved row"}`);
      insert.addEventListener("click", () => addRow(row.id));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove from group";
      remove.setAttribute("aria-label", `Remove ${row.text || "saved row"} from group`);
      remove.addEventListener("click", () => removeRow(row.id));
      controls.append(insert, remove);
      rowElement.append(controls);
    }
    add.hidden = !session?.groupId;
    if (visibleMembers.length === 0) {
      const empty = document.createElement("p");
      empty.className = "stash-row-editor__empty";
      empty.textContent = "This group has no rows. Add a row or save to remove the group.";
      rowsRoot.append(empty);
    }
    if (requestedFocus) {
      const focus = requestedFocus;
      requestedFocus = null;
      queueMicrotask(() => {
        const target = [...rowsRoot.querySelectorAll("[data-row-id]")]
          .find((item) => item.dataset.rowId === focus.rowId);
        const editor = target?.querySelector("[data-narration-editor]");
        if (editor) restoreCaret(editor, focus.offset ?? 0);
      });
    }
  }

  function projectedSequenceVersion(command) {
    const id = command.blockId ?? command.rowId ?? command.sourceRowId;
    return allStageRows().find((row) => row.id === id)?.primaryVisualSequence?.version;
  }

  function syncMembersFromModel() {
    const presentIds = new Set(allStageRows().map((row) => row.id));
    inactiveIds = new Set([...inactiveIds].filter((id) => presentIds.has(id)));
  }

  async function stageCommand(command, caption, meta = {}) {
    const sessionAtInput = session;
    const focusAtInput = captureFocus();
    const task = queued.then(async () => {
      if (!sessionAtInput || session !== sessionAtInput) return false;
      const splitProof = command.kind === "join_rows" ? sessionAtInput.splitProof : undefined;
      try {
        const result = await applyCommand(stageDocument, command, splitProof,
          projectedSequenceVersion(command));
        if (session !== sessionAtInput) return false;
        if (!result?.ok || !result.document) throw new Error("The saved row edit was refused.");
        stageDocument = result.document;
        sessionAtInput.splitProof = result.splitProof;
        syncMembersFromModel();
        if (["split_row", "join_rows"].includes(command.kind) && meta.focusAfter) {
          requestedFocus = { rowId: meta.focusAfter.rowId, offset: meta.focusAfter.offset };
        }
        const textOnly = ["edit_narration_text", "delete_direction_delimiter"].includes(command.kind) &&
          document.activeElement?.matches?.("[data-narration-editor]");
        if (!textOnly) {
          await refreshProjection();
          render();
          if (!requestedFocus) focusCaptured(focusAtInput);
        }
        status.textContent = `${caption} staged. Save to keep the changes.`;
        return true;
      } catch (error) {
        status.textContent = error?.message || "The saved row edit was refused.";
        await refreshProjection();
        render();
        focusCaptured(focusAtInput);
        return false;
      }
    });
    queued = task.catch(() => false);
    return task;
  }

  function stageVisualCommand(command, caption) {
    return stageCommand(command, caption);
  }

  function handleVisualChange(event) {
    const input = event.target.closest?.("[data-visual-hold]");
    if (!input) return;
    const rowId = input.closest("[data-row-id]")?.dataset.rowId;
    const row = allStageRows().find((item) => item.id === rowId);
    const value = Number(input.value);
    if (!row || !Number.isFinite(value) || value <= 0) {
      status.textContent = "Enter a positive hold time.";
      return;
    }
    void stageCommand({ kind: "set_visual_only_hold", rowId, payloadId: input.dataset.visualHold,
      holdSeconds: value }, "Set visual hold");
  }

  async function refreshProjection() {
    if (typeof fetchProjection !== "function") return;
    const snapshot = stageDocument;
    try {
      const next = await fetchProjection(snapshot);
      if (stageDocument === snapshot) projection = next;
    } catch {
      projection = null;
      status.textContent = "The visual preview could not be refreshed. Row text remains staged.";
    }
  }

  function addRow(afterRowId = null) {
    if (!session?.groupId || pending) return;
    try {
      const row = createBlankNarrationRow();
      const blocks = [...stageDocument.activeDraft.blocks];
      const anchorIndex = afterRowId ? blocks.findIndex((item) => item.id === afterRowId) : -1;
      const insertAt = anchorIndex >= 0 ? anchorIndex + 1 : blocks.length;
      blocks.splice(insertAt, 0, row);
      stageDocument = { ...stageDocument, activeDraft: { ...stageDocument.activeDraft, blocks } };
      void refreshProjection().then(() => render());
      status.textContent = "Blank row added to this group.";
    } catch (error) { status.textContent = error.message; }
  }

  function removeRow(rowId) {
    if (!session?.groupId || pending) return;
    inactiveIds.add(rowId);
    render();
    status.textContent = "Row removed from the staged group. Save to keep the change.";
    add.focus();
  }

  function closeNow() {
    closeAfterSave = false;
    prompt.hidden = true;
    footer.hidden = false;
    rowsRoot.inert = false;
    close.disabled = false;
    if (dialog.open) dialog.close();
    cleanup.forEach((dispose) => dispose?.());
    cleanup = [];
    session = null;
    stageDocument = null;
    baselineMembers = [];
    inactiveIds = new Set();
    projection = null;
    pending = false;
    if (reopenAfterClose) {
      const next = reopenAfterClose;
      reopenAfterClose = null;
      open(next);
    }
  }

  function requestClose(reopen = null) {
    if (!session) return;
    reopenAfterClose = reopen;
    if (!dirty()) { closeNow(); return; }
    promptText.textContent = `Save your changes to ${label()}?`;
    prompt.hidden = false;
    footer.hidden = true;
    add.hidden = true;
    rowsRoot.inert = true;
    close.disabled = true;
    promptKeepFocus();
  }

  function promptKeepFocus() { keep.focus(); }

  async function commit() {
    if (!session || pending) return false;
    if (!dirty()) {
      closeNow();
      return true;
    }
    const current = getDocument();
    const actualRevision = current?.rowEditRevision ?? 0;
    const members = clone(currentMembers());
    const expectedRowIds = [...session.expectedRowIds];
    const expected = new Set(expectedRowIds);
    const currentStashRows = new Map((current?.stash ?? []).flatMap((bundle) =>
      (bundle.rows ?? []).map((row) => [row.id, row])));
    const currentGroup = (current?.stashGroups ?? []).find((group) => group.id === session.groupId);
    const membershipCurrent = session.groupId
      ? currentGroup && JSON.stringify(currentGroup.rowIds) === JSON.stringify(expectedRowIds)
      : members.length === 1 && currentStashRows.has(expectedRowIds[0]);
    if (actualRevision !== session.expectedRevision || !membershipCurrent ||
        [...expected].some((id) => !currentStashRows.has(id))) {
      status.textContent = "The saved rows changed while you were editing. Reopen them before saving.";
      return false;
    }
    const saveHandler = session.onSave ?? onSave;
    if (typeof saveHandler !== "function") {
      status.textContent = "Save is unavailable for this saved row.";
      return false;
    }
    pending = true;
    save.disabled = promptSave.disabled = true;
    status.textContent = "Saving saved rows…";
    try {
      const result = await saveHandler(members, {
        groupId: session.groupId ?? null,
        expectedRevision: session.expectedRevision,
        expectedRowIds,
      });
      if (session) {
        if (result === false) {
          status.textContent = "The saved rows were not changed. Review the save status and try again.";
          return false;
        }
        status.textContent = "Saved rows updated.";
        if (closeAfterSave) closeNow();
        else {
          baselineMembers = clone(members);
          prompt.hidden = true;
          render();
        }
      }
      return true;
    } catch (error) {
      status.textContent = error?.message || "The saved rows could not be saved.";
      return false;
    } finally {
      pending = false;
      save.disabled = promptSave.disabled = false;
    }
  }

  function open(options = {}) {
    const next = { ...options };
    if (session) { requestClose(next); return; }
    const current = getDocument();
    const members = clone(next.members ?? (next.row ? [next.row] : []));
    try {
      stageDocument = createStashRowEditorDocument(current, members, next.groupId ?? null);
    } catch (error) {
      next.onStatus?.(error.message);
      return false;
    }
    session = {
      groupId: next.groupId ?? null,
      expectedRevision: next.expectedRevision ?? (current.rowEditRevision ?? 0),
      expectedRowIds: next.expectedRowIds ? [...next.expectedRowIds] : members.map((row) => row.id),
      onSave: next.onSave,
      onStatus: next.onStatus,
      splitProof: undefined,
    };
    if (JSON.stringify(session.expectedRowIds) !== JSON.stringify(members.map((row) => row.id))) {
      session = null;
      stageDocument = null;
      next.onStatus?.("The saved group membership changed. Reopen it before editing.");
      return false;
    }
    baselineMembers = clone(members);
    inactiveIds = new Set();
    heading.textContent = session.groupId ? "Edit saved rows" : "Edit saved row";
    prompt.hidden = true;
    status.textContent = "Changes are staged until Save.";
    render();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    queueMicrotask(() => rowsRoot.querySelector("[data-narration-editor]")?.focus());
    void refreshProjection().then(() => { if (session) render(); });
    return true;
  }

  function closeEditor() { requestClose(); }

  close.addEventListener("click", () => requestClose());
  cancel.addEventListener("click", closeNow);
  save.addEventListener("click", () => { closeAfterSave = false; void commit(); });
  promptSave.addEventListener("click", () => { closeAfterSave = true; void commit(); });
  discard.addEventListener("click", closeNow);
  keep.addEventListener("click", () => {
    prompt.hidden = true;
    footer.hidden = false;
    add.hidden = !session?.groupId;
    rowsRoot.inert = false;
    close.disabled = false;
    reopenAfterClose = null;
  });
  add.addEventListener("click", () => addRow(currentMembers().at(-1)?.id ?? null));
  rowsRoot.addEventListener("change", handleVisualChange);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    requestClose();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) requestClose();
  });
  return {
    open,
    close: closeEditor,
    isOpen: () => dialog.open,
    destroy() {
      cleanup.forEach((dispose) => dispose?.());
      if (dialog.open) dialog.close();
      dialog.remove();
      session = null;
      stageDocument = null;
    },
  };
}
