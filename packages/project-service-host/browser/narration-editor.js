const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const FOCUS_HINT = "Return: paragraph · Tab: split row · Esc: leave text";

function newId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === "function") globalThis.crypto.getRandomValues(bytes);
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256);
  bytes[6] = bytes[6] & 0x0f | 0x40;
  bytes[8] = bytes[8] & 0x3f | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function element(document, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function narrationRow(documentModel, root) {
  const rowId = root.closest("[data-row-id]")?.dataset.rowId;
  if (!rowId) return null;
  const blocks = documentModel?.activeDraft?.blocks;
  if (!Array.isArray(blocks)) return null;
  const row = blocks.find((block) => block && block.id === rowId);
  return row?.type === "narration" ? row : null;
}

function textAtPoint(root, node, offset) {
  if (!node || !root.contains(node) && node !== root) return null;
  try {
    const range = root.ownerDocument.createRange();
    range.selectNodeContents(root);
    range.setEnd(node, Math.max(0, offset));
    return range.toString().length;
  } catch {
    return null;
  }
}

function pointAtTextOffset(root, wanted) {
  const document = root.ownerDocument;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  let cursor = 0;
  let last = null;
  while ((node = walker.nextNode())) {
    last = node;
    const end = cursor + node.nodeValue.length;
    if (wanted <= end) return { node, offset: Math.max(0, wanted - cursor) };
    cursor = end;
  }
  if (last) return { node: last, offset: last.nodeValue.length };
  return { node: root, offset: 0 };
}

function selectionInside(root, selection) {
  if (!selection || selection.rangeCount === 0) return false;
  return root.contains(selection.anchorNode) && root.contains(selection.focusNode);
}

function rangeSelection(root) {
  const selection = root.ownerDocument.getSelection();
  if (!selectionInside(root, selection) || selection.isCollapsed) return null;
  const anchor = textAtPoint(root, selection.anchorNode, selection.anchorOffset);
  const focus = textAtPoint(root, selection.focusNode, selection.focusOffset);
  if (anchor === null || focus === null || anchor === focus) return null;
  return {
    start: Math.min(anchor, focus),
    end: Math.max(anchor, focus),
    backward: anchor > focus,
  };
}

function setSelection(root, start, end, backward = false) {
  const selection = root.ownerDocument.getSelection();
  if (!selection) return;
  const from = pointAtTextOffset(root, start);
  const to = pointAtTextOffset(root, end);
  try {
    selection.removeAllRanges();
    if (typeof selection.setBaseAndExtent === "function") {
      if (backward) selection.setBaseAndExtent(to.node, to.offset, from.node, from.offset);
      else selection.setBaseAndExtent(from.node, from.offset, to.node, to.offset);
      return;
    }
    const range = root.ownerDocument.createRange();
    range.setStart(from.node, from.offset);
    range.setEnd(to.node, to.offset);
    selection.addRange(range);
  } catch {
    // A browser may discard a selection while a command rerenders the row.
  }
}

function setCaret(root, offset) {
  setSelection(root, offset, offset);
}

function directionRuns(row) {
  if (!row || row.plainDirection === true) return [];
  const text = typeof row.text === "string" ? row.text : "";
  const tokens = Array.isArray(row.tokens) ? row.tokens : [];
  const runs = [];
  for (let index = 0; index < tokens.length;) {
    if (tokens[index]?.spoken !== false) {
      index += 1;
      continue;
    }
    const startIndex = index;
    index += 1;
    while (index < tokens.length && tokens[index]?.spoken === false &&
      !/[\[\]]/u.test(text.slice(tokens[index - 1].endOffset, tokens[index].startOffset))) index += 1;
    const endIndexExclusive = index;
    const first = tokens[startIndex];
    const last = tokens[endIndexExclusive - 1];
    const openOffset = first.startOffset - 1;
    const closeOffset = last.endOffset;
    if (text[openOffset] === "[" && text[closeOffset] === "]") {
      runs.push({ startIndex, endIndexExclusive, openOffset, closeOffset });
    }
  }
  return runs;
}

function appendNarration(editor, row) {
  const document = editor.ownerDocument;
  const text = typeof row.text === "string" ? row.text : "";
  const tokens = Array.isArray(row.tokens) ? row.tokens : [];
  let cursor = 0;
  for (const token of tokens) {
    const start = Number.isSafeInteger(token?.startOffset) ? Math.max(cursor, Math.min(token.startOffset, text.length)) : cursor;
    const end = Number.isSafeInteger(token?.endOffset) ? Math.max(start, Math.min(token.endOffset, text.length)) : start;
    if (start > cursor) editor.append(document.createTextNode(text.slice(cursor, start)));
    if (end > start) {
      const value = text.slice(start, end);
      if (token.spoken === false) editor.append(element(document, "span", "narration-token--direction", value));
      else editor.append(document.createTextNode(value));
    }
    cursor = Math.max(cursor, end);
  }
  if (cursor < text.length) editor.append(document.createTextNode(text.slice(cursor)));
  if (!editor.childNodes.length) editor.append(document.createTextNode(""));
}

function renderEditor(editor, row) {
  editor.replaceChildren();
  appendNarration(editor, row);
  const text = typeof row.text === "string" ? row.text : "";
  const label = text.trim() || (row.plainDirection ? "Empty stage direction" : "Empty narration");
  editor.setAttribute("aria-label", `${row.plainDirection ? "Stage direction" : "Narration"}: ${label}`);
}

function textRangeForSelection(row, selection) {
  if (!selection || !Array.isArray(row.tokens)) return null;
  const tokens = row.tokens.filter((token) => Number.isSafeInteger(token?.startOffset) && Number.isSafeInteger(token?.endOffset));
  const selected = tokens.filter((token) => token.endOffset > selection.start && token.startOffset < selection.end);
  if (!selected.length) return null;
  return {
    start: selected[0].startOffset,
    end: selected[selected.length - 1].endOffset,
    firstIndex: row.tokens.indexOf(selected[0]),
    lastIndex: row.tokens.indexOf(selected[selected.length - 1]),
  };
}

function snapSelection(root, row, savedSelection) {
  const selection = rangeSelection(root);
  if (!selection) return savedSelection;
  const snapped = textRangeForSelection(row, selection);
  if (!snapped) return { ...selection };
  const next = { ...selection, start: snapped.start, end: snapped.end };
  if (next.start !== selection.start || next.end !== selection.end) setSelection(root, next.start, next.end, next.backward);
  return next;
}

function selectedAction(row, selection) {
  if (!selection || !Array.isArray(row.tokens)) return null;
  if (row.plainDirection === true) {
    const first = row.tokens[0];
    const last = row.tokens[row.tokens.length - 1];
    if (first && last && selection.start <= first.startOffset && selection.end >= last.endOffset) {
      return { kind: "make_spoken", startOffset: 0, endOffset: row.text.length, text: row.text };
    }
    return null;
  }
  const range = textRangeForSelection(row, selection);
  if (!range) return null;
  const runs = directionRuns(row);
  const direction = runs.find((run) => run.startIndex === range.firstIndex && run.endIndexExclusive - 1 === range.lastIndex);
  if (direction) {
    const text = row.text.slice(direction.openOffset, direction.closeOffset + 1);
    return { kind: "make_spoken", startOffset: direction.openOffset, endOffset: direction.closeOffset + 1, text };
  }
  const chosen = row.tokens.slice(range.firstIndex, range.lastIndex + 1);
  if (chosen.length && chosen.every((token) => token.spoken !== false)) {
    return { kind: "make_stage_direction", startOffset: range.start, endOffset: range.end, text: row.text.slice(range.start, range.end) };
  }
  return null;
}

function directionDelimiterAt(row, start, end, text) {
  if (end - start !== 1) return null;
  const removed = text.slice(start, end);
  if (removed !== "[" && removed !== "]") return null;
  return directionRuns(row).some((run) => run.openOffset === start || run.closeOffset === start) ? start : null;
}

function changedRange(oldText, newText) {
  let start = 0;
  while (start < oldText.length && start < newText.length && oldText[start] === newText[start]) start += 1;
  let oldEnd = oldText.length;
  let newEnd = newText.length;
  while (oldEnd > start && newEnd > start && oldText[oldEnd - 1] === newText[newEnd - 1]) {
    oldEnd -= 1;
    newEnd -= 1;
  }
  return { startOffset: start, endOffset: oldEnd, insertedText: newText.slice(start, newEnd) };
}

function targetRange(event, editor) {
  try {
    const range = event.getTargetRanges?.()[0];
    if (range) {
      const start = textAtPoint(editor, range.startContainer, range.startOffset);
      const end = textAtPoint(editor, range.endContainer, range.endOffset);
      if (start !== null && end !== null) return { startOffset: start, endOffset: end };
    }
  } catch {
    // Fall through to the live selection.
  }
  const selection = editor.ownerDocument.getSelection();
  if (!selectionInside(editor, selection)) return null;
  const start = textAtPoint(editor, selection.anchorNode, selection.anchorOffset);
  const end = textAtPoint(editor, selection.focusNode, selection.focusOffset);
  if (start === null || end === null) return null;
  return { startOffset: Math.min(start, end), endOffset: Math.max(start, end) };
}

function deletionRange(event, editor, oldText) {
  const range = targetRange(event, editor);
  if (!range) return null;
  if (range.startOffset !== range.endOffset) return range;
  if (event.inputType === "deleteContentBackward" && range.startOffset > 0) {
    const candidate = range.startOffset - 1;
    const startOffset = candidate > 0 && /[\uDC00-\uDFFF]/u.test(oldText[candidate]) && /[\uD800-\uDBFF]/u.test(oldText[candidate - 1])
      ? candidate - 1 : candidate;
    return { startOffset, endOffset: range.endOffset };
  }
  if (event.inputType === "deleteContentForward" && range.endOffset < oldText.length) {
    const candidate = range.endOffset + 1;
    const endOffset = candidate < oldText.length && /[\uD800-\uDBFF]/u.test(oldText[range.endOffset]) && /[\uDC00-\uDFFF]/u.test(oldText[candidate])
      ? candidate + 1 : candidate;
    return { startOffset: range.startOffset, endOffset };
  }
  return range;
}

/** Install the writing controls for one existing narration cell. */
export function mountNarration(root, scriptDocument, command, rerender) {
  if (!root || !root.ownerDocument || typeof command !== "function") return () => undefined;
  const row = narrationRow(scriptDocument, root);
  if (!row) return () => undefined;
  const document = root.ownerDocument;
  const editor = element(document, "p", "narration-text narration-editor");
  editor.dataset.narrationEditor = "true";
  editor.contentEditable = "true";
  editor.setAttribute("role", "textbox");
  editor.setAttribute("aria-multiline", "true");
  editor.spellcheck = true;
  renderEditor(editor, row);

  const hint = element(document, "p", "narration-focus-hint", FOCUS_HINT);
  hint.hidden = true;
  hint.setAttribute("aria-live", "polite");

  const actions = element(document, "div", "narration-editor__actions");
  actions.hidden = true;
  actions.setAttribute("role", "toolbar");
  const stageButton = element(document, "button", "narration-editor__action", "Make stage direction");
  stageButton.type = "button";
  const spokenButton = element(document, "button", "narration-editor__action", "Make spoken");
  spokenButton.type = "button";
  actions.append(stageButton, spokenButton);
  root.replaceChildren(editor, actions, hint);

  let knownText = typeof row.text === "string" ? row.text : "";
  let composing = false;
  let compositionText = knownText;
  let savedSelection = null;
  let selectionGuard = false;
  let queue = Promise.resolve();
  let pendingDispatches = 0;
  let rerenderTimer = 0;
  let editingBlocked = false;
  let rerenderAllowed = true;

  function requestRerender() {
    if (rerenderTimer || typeof rerender !== "function") return;
    rerenderTimer = setTimeout(() => {
      rerenderTimer = 0;
      // Keep the live editor in place until all queued keystrokes have reached
      // the model; otherwise a fast paste/type sequence loses its caret.
      if (!rerenderAllowed) return;
      if (pendingDispatches) {
        requestRerender();
        return;
      }
      rerender();
    }, 0);
  }

  function currentSelection() {
    const selection = rangeSelection(editor);
    if (selection) savedSelection = snapSelection(editor, row, selection);
    return savedSelection;
  }

  function updateActions() {
    const action = selectedAction(row, savedSelection);
    actions.hidden = !action;
    stageButton.hidden = !action || action.kind !== "make_stage_direction";
    spokenButton.hidden = !action || action.kind !== "make_spoken";
    if (!action) return;
    const quoted = action.text.trim().replace(/\s+/gu, " ").slice(0, 80);
    const suffix = quoted ? ` for “${quoted}”` : "";
    (action.kind === "make_spoken" ? spokenButton : stageButton).setAttribute(
      "aria-label", `${action.kind === "make_spoken" ? "Make spoken" : "Make stage direction"}${suffix}`,
    );
  }

  function dispatch(payload, label) {
    pendingDispatches += 1;
    const task = queue.then(async () => {
      let successful = false;
      try {
        const result = await command(payload, label, () => {
          requestRerender();
        });
        successful = result !== false && result?.ok !== false;
      } finally {
        pendingDispatches -= 1;
        if (successful) requestRerender();
        else {
          // Keep a refused/conflicted draft visible, but do not apply another
          // edit against a document the model did not accept.
          editingBlocked = true;
          rerenderAllowed = false;
          if (rerenderTimer) {
            clearTimeout(rerenderTimer);
            rerenderTimer = 0;
          }
        }
      }
    });
    queue = task.catch(() => undefined);
    return task;
  }

  function replaceText(startOffset, endOffset, insertedText, label = "Edit narration", sourceText = editor.textContent ?? "") {
    const oldText = sourceText;
    if (startOffset < 0 || endOffset < startOffset || endOffset > oldText.length) return;
    const nextText = oldText.slice(0, startOffset) + insertedText + oldText.slice(endOffset);
    if (nextText === oldText) return;
    if ((editor.textContent ?? "") !== nextText) editor.textContent = nextText;
    knownText = nextText;
    setCaret(editor, startOffset + insertedText.length);
    const delimiterOffset = directionDelimiterAt(row, startOffset, endOffset, oldText);
    if (delimiterOffset !== null) {
      void dispatch({ kind: "delete_direction_delimiter", blockId: row.id, offset: delimiterOffset }, "Remove stage direction");
      return;
    }
    void dispatch({
      kind: "edit_narration_text", rowId: row.id, startOffset, endOffset, insertedText, editId: newId(),
    }, label);
  }

  function fallbackInput() {
    if (composing || editingBlocked) return;
    const nextText = editor.textContent ?? "";
    if (nextText === knownText) return;
    const oldText = knownText;
    const edit = changedRange(oldText, nextText);
    replaceText(edit.startOffset, edit.endOffset, edit.insertedText, "Edit narration", oldText);
  }

  function onBeforeInput(event) {
    if (editingBlocked) {
      event.preventDefault();
      return;
    }
    if (composing || event.isComposing) return;
    const type = event.inputType || "";
    if (type === "insertLineBreak" || type === "insertParagraph" || type === "insertFromPaste" || type === "insertFromDrop") {
      // Paragraphs and paste parsing belong to #620; do not let the browser
      // create an unmodelled newline or HTML fragment in this slice.
      event.preventDefault();
      return;
    }
    const insertion = type === "insertText" || type === "insertReplacementText";
    const deletion = type.startsWith("delete");
    if (!insertion && !deletion) return;
    const oldText = editor.textContent ?? "";
    const range = deletion ? deletionRange(event, editor, oldText) : targetRange(event, editor);
    if (!range) return;
    const insertedText = insertion ? (event.data ?? (type === "insertLineBreak" || type === "insertParagraph" ? "\n" : "")) : "";
    event.preventDefault();
    replaceText(range.startOffset, range.endOffset, insertedText);
  }

  function onCompositionStart() {
    if (editingBlocked) return;
    composing = true;
    compositionText = knownText;
  }

  function onCompositionEnd() {
    if (editingBlocked) return;
    composing = false;
    const nextText = editor.textContent ?? "";
    if (nextText === compositionText) return;
    const edit = changedRange(compositionText, nextText);
    knownText = compositionText;
    replaceText(edit.startOffset, edit.endOffset, edit.insertedText, "Edit narration", compositionText);
  }

  function performAction(action) {
    if (!action) return;
    const payload = { kind: action.kind, blockId: row.id, startOffset: action.startOffset, endOffset: action.endOffset };
    void dispatch(payload, action.kind === "make_spoken" ? "Make spoken" : "Make stage direction");
    actions.hidden = true;
  }

  function preserveActionSelection(event) {
    event.preventDefault();
    currentSelection();
  }

  function activateAction() {
    const action = selectedAction(row, savedSelection);
    performAction(action);
  }

  function leaveText(event) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    editor.blur();
    hint.hidden = true;
    const rowElement = root.closest("[data-row-id]");
    const card = rowElement?.querySelector(".visual-card");
    if (card) {
      if (!card.hasAttribute("tabindex")) card.tabIndex = 0;
      card.focus();
    } else {
      root.tabIndex = -1;
      root.focus();
    }
  }

  function onSelectionChange() {
    if (selectionGuard || !selectionInside(editor, document.getSelection())) return;
    const selection = rangeSelection(editor);
    if (!selection) {
      updateActions();
      return;
    }
    selectionGuard = true;
    try { savedSelection = snapSelection(editor, row, selection); }
    finally { selectionGuard = false; }
    updateActions();
  }

  editor.addEventListener("beforeinput", onBeforeInput);
  editor.addEventListener("input", fallbackInput);
  editor.addEventListener("compositionstart", onCompositionStart);
  editor.addEventListener("compositionend", onCompositionEnd);
  editor.addEventListener("keydown", leaveText);
  editor.addEventListener("focus", () => { hint.hidden = false; });
  editor.addEventListener("blur", () => { hint.hidden = true; });
  editor.addEventListener("paste", (event) => event.preventDefault());
  stageButton.addEventListener("mousedown", preserveActionSelection);
  spokenButton.addEventListener("mousedown", preserveActionSelection);
  stageButton.addEventListener("click", activateAction);
  spokenButton.addEventListener("click", activateAction);
  document.addEventListener("selectionchange", onSelectionChange);

  return () => {
    editor.removeEventListener("beforeinput", onBeforeInput);
    editor.removeEventListener("input", fallbackInput);
    editor.removeEventListener("compositionstart", onCompositionStart);
    editor.removeEventListener("compositionend", onCompositionEnd);
    editor.removeEventListener("keydown", leaveText);
    document.removeEventListener("selectionchange", onSelectionChange);
    stageButton.removeEventListener("mousedown", preserveActionSelection);
    spokenButton.removeEventListener("mousedown", preserveActionSelection);
    stageButton.removeEventListener("click", activateAction);
    spokenButton.removeEventListener("click", activateAction);
    if (rerenderTimer) clearTimeout(rerenderTimer);
  };
}

