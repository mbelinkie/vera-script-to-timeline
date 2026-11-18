import { createBlankNarrationRow, rowGaps } from "./rows-editor.js";

const FOCUS_HINT = "Return: paragraph · Tab: split row · Esc: leave text";

/** Pure clipboard grammar: a single LF stays within a row; a blank line separates rows. */
export function pasteParagraphBlocks(text) {
  if (typeof text !== "string") throw new TypeError("Plain-text paste requires text.");
  return text.replace(/\r\n?/gu, "\n").split(/\n{2,}/u);
}

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
  if (row?.type === "narration") return row;
  return row?.type === "visual_only" && row.clearedNarration ? { ...row, type: "narration", text: "", tokens: [] } : null;
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

function lexicalTokens(text, directionRanges = []) {
  const words = [...text.matchAll(/[^\s[\]]+/gu)];
  // Match the model's literal-punctuation fallback: when a row has no
  // ordinary lexeme, standalone brackets remain editable token text instead
  // of disappearing from the optimistic selection model.
  const matches = words.length > 0 ? words : [...text.matchAll(/\S+/gu)];
  return matches.map((match) => {
    const startOffset = match.index;
    const endOffset = startOffset + match[0].length;
    const direction = directionRanges.some(({ openOffset, closeOffset }) =>
      openOffset < startOffset && endOffset <= closeOffset);
    return { value: match[0], startOffset, endOffset, ...(direction ? { spoken: false } : {}) };
  });
}

function translateDirectionRanges(row, startOffset, endOffset, insertedText) {
  const delta = insertedText.length - (endOffset - startOffset);
  return directionRuns(row).flatMap(({ openOffset, closeOffset }) => {
    const removesOpen = startOffset <= openOffset && openOffset < endOffset;
    const removesClose = startOffset <= closeOffset && closeOffset < endOffset;
    if (removesOpen || removesClose) return [];
    return [{
      openOffset: openOffset < startOffset ? openOffset : openOffset + delta,
      closeOffset: closeOffset < startOffset ? closeOffset : closeOffset + delta,
    }];
  });
}

function normalizedTextEdit(row, startOffset, endOffset, insertedText) {
  let editStart = startOffset;
  let editEnd = endOffset;
  let replacement = insertedText;
  for (const { openOffset, closeOffset } of directionRuns(row)) {
    if (openOffset < editStart && editEnd <= closeOffset) {
      const inner = row.text.slice(openOffset + 1, editStart) + replacement + row.text.slice(editEnd, closeOffset);
      if (!inner.trim()) {
        editStart = openOffset;
        editEnd = closeOffset + 1;
        replacement = "";
        continue;
      }
      if (editStart === openOffset + 1) {
        replacement = replacement.trimStart();
        if (!replacement) while (/\s/u.test(row.text[editEnd] ?? "")) editEnd += 1;
      }
      if (editEnd === closeOffset) {
        replacement = replacement.trimEnd();
        if (!replacement) while (/\s/u.test(row.text[editStart - 1] ?? "")) editStart -= 1;
      }
    }
  }
  return { startOffset: editStart, endOffset: editEnd, insertedText: replacement };
}

function localTextEdit(row, startOffset, endOffset, insertedText) {
  const edit = normalizedTextEdit(row, startOffset, endOffset, insertedText);
  const rawText = row.text.slice(0, edit.startOffset) + edit.insertedText + row.text.slice(edit.endOffset);
  const text = rawText.trim() ? rawText : "";
  const directions = translateDirectionRanges(row, edit.startOffset, edit.endOffset, edit.insertedText);
  return { ...row, text, tokens: lexicalTokens(text, directions) };
}

function localSpokenEdit(row, run) {
  const text = `${row.text.slice(0, run.openOffset)}${row.text.slice(run.openOffset + 1, run.closeOffset)}${row.text.slice(run.closeOffset + 1)}`;
  const directions = directionRuns(row)
    .filter((item) => item.openOffset !== run.openOffset || item.closeOffset !== run.closeOffset)
    .map(({ openOffset, closeOffset }) => ({
      openOffset: openOffset > run.closeOffset ? openOffset - 2 : openOffset,
      closeOffset: closeOffset > run.closeOffset ? closeOffset - 2 : closeOffset,
    }));
  return { ...row, text, tokens: lexicalTokens(text, directions) };
}

function localStageEdit(row, action) {
  if (action.kind === "make_stage_direction") {
    if (row.plainDirection === true) {
      const next = { ...row, tokens: lexicalTokens(row.text).map((token) => ({ ...token, spoken: false })) };
      delete next.plainDirection;
      return next;
    }
    if (row.text[action.startOffset] === "[" && row.text[action.endOffset - 1] === "]") {
      const directions = [...translateDirectionRanges(row, action.startOffset, action.endOffset, row.text.slice(action.startOffset, action.endOffset)),
        { openOffset: action.startOffset, closeOffset: action.endOffset - 1 }];
      return { ...row, tokens: lexicalTokens(row.text, directions) };
    }
    const text = `${row.text.slice(0, action.startOffset)}[${row.text.slice(action.startOffset, action.endOffset)}]${row.text.slice(action.endOffset)}`;
    const startOffset = action.startOffset;
    const endOffset = action.endOffset + 2;
    const directions = [...translateDirectionRanges(row, action.startOffset, action.endOffset, `[${row.text.slice(action.startOffset, action.endOffset)}]`),
      { openOffset: startOffset, closeOffset: endOffset - 1 }];
    return { ...row, text, tokens: lexicalTokens(text, directions) };
  }
  if (action.kind === "make_spoken") {
    const run = directionRuns(row).find(({ openOffset, closeOffset }) =>
      openOffset === action.startOffset && closeOffset + 1 === action.endOffset);
    if (!run) return { ...row, plainDirection: undefined, tokens: lexicalTokens(row.text) };
    return localSpokenEdit(row, run);
  }
  return row;
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

function includeLiteralDirectionPair(row, range) {
  if (range.start <= 0 || range.end >= row.text.length ||
      row.text[range.start - 1] !== "[" || row.text[range.end] !== "]") return range;
  const expanded = { ...range, start: range.start - 1, end: range.end + 1 };
  // Do not turn a nested or unmatched literal bracket sequence into a
  // semantic pair; the model deliberately refuses those ranges.
  if (row.text[expanded.start - 1] === "[" || row.text[expanded.end] === "]") return null;
  return expanded;
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
    if (chosen.some((token) => /[\[\]]/u.test(token.value))) return null;
    // A stage selection may wrap one adjacent literal pair, but it must never
    // reinterpret brackets embedded between otherwise spoken words.
    if (/[\[\]]/u.test(row.text.slice(range.start, range.end))) return null;
    const stageRange = includeLiteralDirectionPair(row, range);
    if (!stageRange) return null;
    const hasOpen = row.text[range.start - 1] === "[";
    const hasClose = row.text[range.end] === "]";
    if (hasOpen !== hasClose) return null;
    return { kind: "make_stage_direction", startOffset: stageRange.start, endOffset: stageRange.end, text: row.text.slice(stageRange.start, stageRange.end) };
  }
  return null;
}

/** Mirror the model's stage-direction boundary snapping before offering row actions. */
function selectionWords(row, selection) {
  if (row.plainDirection || !Array.isArray(row.tokens)) return null;
  const range = textRangeForSelection(row, selection);
  if (!range) return null;
  const runs = directionRuns(row);
  const snap = (boundary) => runs.find((run) =>
    run.startIndex < boundary && boundary < run.endIndexExclusive)?.endIndexExclusive ?? boundary;
  const from = snap(range.firstIndex);
  const to = snap(range.lastIndex + 1);
  if (from >= to) return null;
  return { from, to, first: from === 0, last: to === row.tokens.length };
}

function selectionRowActions(row, selection, documentModel) {
  const range = selectionWords(row, selection);
  if (!range || !range.first && !range.last) return [];
  const blocks = documentModel?.activeDraft?.blocks ?? [];
  const index = blocks.findIndex((block) => block.id === row.id);
  if (index < 0) return [];
  const options = [];
  if (!(range.first && range.last)) options.push({ kind: "split_row" });
  for (const [direction, edge, neighbour] of [
    ["previous", range.first, blocks[index - 1]],
    ["next", range.last, blocks[index + 1]],
  ]) {
    if (!edge || !neighbour) continue;
    if (neighbour.type === "section") options.push({ kind: `join_${direction}`, disabled: true });
    else if (neighbour.type === "narration") options.push({ kind: `join_${direction}` });
  }
  return options;
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
  // Diffing UTF-16 code units can stop between the two units of a shared
  // surrogate pair (for example, 😀 -> 😃). Expand both sides before emitting
  // the replacement so the model always receives scalar-aligned old spans and
  // complete inserted text.
  const scalarStart = (text, offset) => offset > 0 && offset < text.length &&
    /[\uD800-\uDBFF]/u.test(text[offset - 1]) && /[\uDC00-\uDFFF]/u.test(text[offset]) ? offset - 1 : offset;
  const scalarEnd = (text, offset) => offset > 0 && offset < text.length &&
    /[\uD800-\uDBFF]/u.test(text[offset - 1]) && /[\uDC00-\uDFFF]/u.test(text[offset]) ? offset + 1 : offset;
  start = Math.min(scalarStart(oldText, start), scalarStart(newText, start));
  oldEnd = scalarEnd(oldText, oldEnd);
  newEnd = scalarEnd(newText, newEnd);
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
export function mountNarration(root, scriptDocument, command, options = {}) {
  if (!root || !root.ownerDocument || typeof command !== "function") return () => undefined;
  const row = narrationRow(scriptDocument, root);
  if (!row) return () => undefined;
  const { compositionChange, requestRender } = options && typeof options === "object" ? options : {};
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
  const actionDivider = element(document, "span", "narration-editor__divider");
  actionDivider.setAttribute("aria-hidden", "true");
  const rowButtons = [
    ["split_row", "Split into new row"],
    ["join_previous", "Join to previous row"],
    ["join_next", "Join to next row"],
  ].map(([kind, label]) => {
    const button = element(document, "button", "narration-editor__action", label);
    button.type = "button";
    button.dataset.rowSelectionAction = kind;
    return button;
  });
  actions.append(stageButton, spokenButton, actionDivider, ...rowButtons);
  root.replaceChildren(editor, actions, hint);

  let knownText = typeof row.text === "string" ? row.text : "";
  let localRow = { ...row, tokens: Array.isArray(row.tokens) ? row.tokens.map((token) => ({ ...token })) : [] };
  let composing = false;
  let compositionText = knownText;
  let savedSelection = null;
  let selectionGuard = false;
  let editingBlocked = false;
  let mounted = true;
  const typingSession = newId();
  let typingBoundary = 0;
  let expectedCaret = null;

  function currentSelection() {
    const selection = rangeSelection(editor);
    if (selection) savedSelection = snapSelection(editor, localRow, selection);
    return savedSelection;
  }

  function updateActions() {
    const action = selectedAction(localRow, savedSelection);
    const rowActions = selectionRowActions(localRow, savedSelection, scriptDocument);
    actions.hidden = !action && rowActions.length === 0;
    stageButton.hidden = !action || action.kind !== "make_stage_direction";
    spokenButton.hidden = !action || action.kind !== "make_spoken";
    actionDivider.hidden = !action || rowActions.length === 0;
    rowButtons.forEach((button) => {
      const option = rowActions.find((entry) => entry.kind === button.dataset.rowSelectionAction);
      button.hidden = !option;
      button.disabled = option?.disabled === true;
      button.title = option?.disabled ? "Rows cannot be joined across a section break." : "";
      if (option?.disabled) button.setAttribute("aria-label", `${button.textContent} — unavailable across a section break`);
      else button.removeAttribute("aria-label");
    });
    if (!action) return;
    const quoted = action.text.trim().replace(/\s+/gu, " ").slice(0, 80);
    const suffix = quoted ? ` for “${quoted}”` : "";
    (action.kind === "make_spoken" ? spokenButton : stageButton).setAttribute(
      "aria-label", `${action.kind === "make_spoken" ? "Make spoken" : "Make stage direction"}${suffix}`,
    );
  }

  function expectedRow(rowSnapshot) {
    return {
      id: rowSnapshot.id,
      text: rowSnapshot.text,
      plainDirection: rowSnapshot.plainDirection === true,
    };
  }

  function dispatch(payload, label, rowSnapshot, meta = {}) {
    if (editingBlocked) return Promise.resolve(false);
    let result;
    try {
      // Invoke the app command immediately at the input event. The app owns
      // serialization and the document-wide refusal/render policy.
      result = command(payload, label, { expectedRow: expectedRow(rowSnapshot), ...meta });
    } catch {
      editingBlocked = true;
      return Promise.resolve(false);
    }
    return Promise.resolve(result).then((accepted) => {
      if (accepted === false && !meta.structural) editingBlocked = true;
      return accepted === true;
    }, () => {
      if (!meta.structural) editingBlocked = true;
      return false;
    });
  }

  function replaceText(startOffset, endOffset, insertedText, label = "Edit narration", sourceText = editor.textContent ?? "") {
    const oldText = sourceText;
    if (startOffset < 0 || endOffset < startOffset || endOffset > oldText.length) return;
    const priorRow = localRow;
    const delimiterOffset = directionDelimiterAt(priorRow, startOffset, endOffset, oldText);
    if (delimiterOffset !== null && insertedText === "") {
      typingBoundary += 1;
      const run = directionRuns(priorRow).find(({ openOffset, closeOffset }) =>
        openOffset === delimiterOffset || closeOffset === delimiterOffset);
      if (!run) return;
      // The model's delimiter command removes only the paired brackets; the
      // words between them remain ordinary narration in the optimistic view.
      localRow = localSpokenEdit(priorRow, run);
      knownText = localRow.text;
      renderEditor(editor, localRow);
      setCaret(editor, startOffset <= run.openOffset ? startOffset : Math.max(0, startOffset - 2));
      savedSelection = null;
      updateActions();
      return dispatch({ kind: "delete_direction_delimiter", blockId: priorRow.id, offset: delimiterOffset }, "Remove stage direction", priorRow);
    }
    const nextText = oldText.slice(0, startOffset) + insertedText + oldText.slice(endOffset);
    if (nextText === oldText) return;
    localRow = localTextEdit(priorRow, startOffset, endOffset, insertedText);
    // Match the model's direction-edge whitespace normalization and blank-row
    // canonicalization before the next input is diffed against this draft.
    if (localRow.text === priorRow.text) {
      knownText = priorRow.text;
      renderEditor(editor, priorRow);
      const noOpEdit = normalizedTextEdit(priorRow, startOffset, endOffset, insertedText);
      setCaret(editor, Math.min(noOpEdit.startOffset + noOpEdit.insertedText.length, priorRow.text.length));
      savedSelection = null;
      updateActions();
      return;
    }
    knownText = localRow.text;
    renderEditor(editor, localRow);
    const localEdit = normalizedTextEdit(priorRow, startOffset, endOffset, insertedText);
    expectedCaret = Math.min(localEdit.startOffset + localEdit.insertedText.length, localRow.text.length);
    setCaret(editor, expectedCaret);
    savedSelection = null;
    updateActions();
    return dispatch({
      kind: "edit_narration_text", rowId: priorRow.id, startOffset, endOffset, insertedText, editId: newId(),
    }, nextText === "" ? "Cleared narration" : label, priorRow,
    label === "Edit narration" ? { typingSession, typingBoundary } : {});
  }

  function fallbackInput() {
    if (composing || editingBlocked) return;
    const nextText = editor.textContent ?? "";
    if (nextText === knownText) return;
    const oldText = knownText;
    const edit = changedRange(oldText, nextText);
    replaceText(edit.startOffset, edit.endOffset, edit.insertedText, "Edit narration", oldText);
  }

  function paragraphBreak(range) {
    if (!range || editingBlocked) return;
    // At the first character Return only offers the Tab hint (S03 D114).
    if (range.startOffset === 0 && range.endOffset === 0) return;
    void replaceText(range.startOffset, range.endOffset, "\n", "New paragraph");
  }

  function pastePlainText(text) {
    if (editingBlocked || composing || !text) return;
    const range = targetRange({}, editor);
    if (!range) return;
    const blocks = pasteParagraphBlocks(text);
    const insertedText = blocks.join("\n\n");
    const priorRow = localRow;
    const nextRow = localTextEdit(priorRow, range.startOffset, range.endOffset, insertedText);
    if (nextRow.text === priorRow.text && blocks.length === 1) return;
    localRow = nextRow;
    knownText = nextRow.text;
    renderEditor(editor, localRow);
    setCaret(editor, Math.min(range.startOffset + insertedText.length, localRow.text.length));
    savedSelection = null;
    updateActions();
    // A structural paste may replace this editor with several rows. Prevent
    // further local typing until the model has accepted and rendered it;
    // refusals retain this visible draft for explicit discard.
    void dispatch({ kind: "paste_plain_text", rowId: priorRow.id,
      startOffset: range.startOffset, endOffset: range.endOffset, blocks },
    "Paste text", priorRow, { paste: true });
    editingBlocked = true;
  }

  function splitAtCaret(offset) {
    if (editingBlocked) return;
    const before = localRow;
    const newRowId = newId();
    // Resolve token identity *after* queued typing has been accepted. The
    // optimistic tokenizer does not own IDs and must not invent them.
    const intent = (currentDocument) => {
      const blocks = currentDocument.activeDraft.blocks;
      const actual = blocks.find((block) => block.id === before.id);
      if (!actual || actual.type !== "narration") throw new Error("The row changed before the split.");
      const index = actual.tokens.findIndex((token) => token.endOffset > offset);
      const boundary = index < 0 ? actual.tokens.length : index;
      if (boundary === 0 || boundary === actual.tokens.length) {
        const atStart = boundary === 0;
        const gap = rowGaps(blocks).find((item) => atStart
          ? item.beforeRowId === before.id : item.afterRowId === before.id);
        if (!gap) throw new Error("The insertion gap changed before the split.");
        return { kind: "create_row", row: createBlankNarrationRow({ id: newRowId }), destination: gap };
      }
      return { kind: "split_row", rowId: before.id, newRowId, at: { beforeTokenId: actual.tokens[boundary].id } };
    };
    void dispatch(intent, "Split row", before, {
      structural: true, splitCaret: offset, focusAfter: { rowId: newRowId, offset: 0 },
    });
  }

  function joinPrevious() {
    if (editingBlocked) return;
    const before = localRow;
    // A neighbouring section is a hard boundary. Let the model give the
    // exact refusal, without changing the optimistic editor's text.
    void dispatch({ kind: "join_rows", rowId: before.id, direction: "previous", words: null },
      "Join rows", before, { structural: true, focusPrevious: true });
  }

  function onStructuralKey(event) {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) typingBoundary += 1;
    if (event.key === "Escape") return leaveText(event);
    if (editingBlocked || composing || event.isComposing || event.altKey || event.metaKey || event.ctrlKey) return;
    if (event.key === "Enter") {
      event.preventDefault();
      paragraphBreak(targetRange(event, editor));
    } else if (event.key === "Tab" && !event.shiftKey) {
      event.preventDefault();
      const range = targetRange(event, editor);
      if (range) splitAtCaret(range.endOffset);
    } else if (event.key === "Backspace") {
      const range = targetRange(event, editor);
      if (range?.startOffset === 0 && range.endOffset === 0) {
        event.preventDefault();
        joinPrevious();
      }
    }
  }

  function onBeforeInput(event) {
    if (editingBlocked) {
      event.preventDefault();
      return;
    }
    if (composing || event.isComposing) return;
    const type = event.inputType || "";
    if (type === "insertLineBreak" || type === "insertParagraph") {
      event.preventDefault();
      paragraphBreak(targetRange(event, editor));
      return;
    }
    if (type === "insertFromPaste" || type === "insertFromDrop") {
      event.preventDefault();
      if (type === "insertFromPaste" && !editingBlocked) {
        const plain = event.dataTransfer?.getData?.("text/plain");
        if (typeof plain === "string" && plain) pastePlainText(plain);
      }
      return;
    }
    const insertion = type === "insertText" || type === "insertReplacementText";
    const deletion = type.startsWith("delete");
    if (!insertion && !deletion) return;
    const oldText = editor.textContent ?? "";
    const range = deletion ? deletionRange(event, editor, oldText) : targetRange(event, editor);
    if (!range) return;
    let insertedText = "";
    if (insertion) {
      insertedText = event.data;
      if (insertedText === null || insertedText === undefined) {
        if (type !== "insertReplacementText") return;
        try {
          const transferred = event.dataTransfer?.getData?.("text/plain");
          if (typeof transferred !== "string" || !transferred) return;
          insertedText = transferred;
        } catch {
          return;
        }
      }
    }
    event.preventDefault();
    replaceText(range.startOffset, range.endOffset, insertedText);
  }

  function onCompositionStart() {
    if (editingBlocked) return;
    typingBoundary += 1;
    composing = true;
    compositionText = knownText;
    if (typeof compositionChange === "function") compositionChange(row.id, true);
  }

  function onCompositionEnd() {
    const wasComposing = composing;
    composing = false;
    if (editingBlocked) {
      if (wasComposing && typeof compositionChange === "function") compositionChange(row.id, false);
      return;
    }
    const nextText = editor.textContent ?? "";
    if (nextText !== compositionText) {
      const edit = changedRange(compositionText, nextText);
      knownText = compositionText;
      replaceText(edit.startOffset, edit.endOffset, edit.insertedText, "Edit narration", compositionText);
    }
    typingBoundary += 1;
    if (wasComposing && typeof compositionChange === "function") compositionChange(row.id, false);
  }

  function onPaste(event) {
    event.preventDefault();
    const plain = event.clipboardData?.getData("text/plain");
    if (typeof plain === "string") pastePlainText(plain);
  }

  function performAction(action) {
    if (!action || editingBlocked) return;
    const priorRow = localRow;
    localRow = localStageEdit(priorRow, action);
    knownText = localRow.text;
    renderEditor(editor, localRow);
    if (action.kind === "make_stage_direction") {
      const existingPair = priorRow.text[action.startOffset] === "[" && priorRow.text[action.endOffset - 1] === "]";
      setSelection(editor, action.startOffset + 1, existingPair ? action.endOffset - 1 : action.endOffset + 1);
    }
    else if (action.kind === "make_spoken") {
      const removedPair = directionRuns(priorRow).some(({ openOffset, closeOffset }) =>
        openOffset === action.startOffset && closeOffset + 1 === action.endOffset);
      setSelection(editor, action.startOffset, removedPair ? Math.max(action.startOffset, action.endOffset - 2) : action.endOffset);
    }
    const payload = { kind: action.kind, blockId: priorRow.id, startOffset: action.startOffset, endOffset: action.endOffset };
    void dispatch(payload, action.kind === "make_spoken" ? "Make spoken" : "Make stage direction", priorRow);
    actions.hidden = true;
  }

  function performRowSelection(kind) {
    if (editingBlocked || composing || !savedSelection) return;
    const selection = { ...savedSelection };
    const options = selectionRowActions(localRow, selection, scriptDocument);
    if (!options.some((option) => option.kind === kind && !option.disabled)) return;
    const before = localRow;
    const newRowId = newId();
    const index = scriptDocument.activeDraft.blocks.findIndex((block) => block.id === before.id);
    const neighbour = scriptDocument.activeDraft.blocks[index + (kind === "join_previous" ? -1 : 1)];
    const focusAfter = kind === "split_row" ? { rowId: newRowId, offset: 0 }
      : { rowId: neighbour.id, offset: kind === "join_previous" ? neighbour.text.length : 0 };
    // Use the committed model's IDs, never IDs from the optimistic tokenizer.
    // Resolution runs in app.js after earlier queued typing has committed.
    const intent = (latest) => {
      const actual = latest.activeDraft.blocks.find((block) => block.id === before.id);
      if (!actual || actual.type !== "narration") throw new Error("The selected row changed.");
      const current = selectionWords(actual, selection);
      const allowed = selectionRowActions(actual, selection, latest);
      if (!current || !allowed.some((option) => option.kind === kind && !option.disabled)) {
        throw new Error("The selection is no longer available.");
      }
      const words = { startTokenId: actual.tokens[current.from].id, endTokenId: actual.tokens[current.to - 1].id };
      return kind === "split_row" ? { kind, rowId: before.id, newRowId, at: words }
        : { kind: "join_rows", rowId: before.id, direction: kind === "join_previous" ? "previous" : "next", words };
    };
    const label = kind === "split_row" ? "Split selection" : "Join selected words";
    void dispatch(intent, label, before, { structural: true, focusAfter }).then((accepted) => {
      if (!accepted) editingBlocked = false;
    });
    editingBlocked = true;
    actions.hidden = true;
  }

  function preserveActionSelection(event) {
    event.preventDefault();
    currentSelection();
  }

  function activateAction() {
    const action = selectedAction(localRow, savedSelection);
    performAction(action);
  }

  function leaveText(event) {
    if (event.key !== "Escape" || composing) return;
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

  function onFocus() {
    hint.hidden = false;
  }

  function onBlur() {
    hint.hidden = true;
    const rowElement = root.closest("[data-row-id]");
    const requestIfExternal = () => {
      if (!mounted || rowElement?.contains(document.activeElement)) return;
      savedSelection = null;
      updateActions();
      if (typeof requestRender === "function") requestRender();
    };
    // Let Escape/card and toolbar focus transitions settle before deciding
    // whether the row is really leaving the editor.
    queueMicrotask(requestIfExternal);
  }

  function onSelectionChange() {
    if (selectionGuard || !selectionInside(editor, document.getSelection())) return;
    const selection = rangeSelection(editor);
    if (!selection) {
      const focusInEditor = document.activeElement === editor || editor.contains(document.activeElement);
      if (focusInEditor) savedSelection = null;
      updateActions();
      return;
    }
    if (expectedCaret !== null && (selection.startOffset !== expectedCaret || selection.endOffset !== expectedCaret)) {
      typingBoundary += 1;
    }
    expectedCaret = selection.endOffset;
    selectionGuard = true;
    try { savedSelection = snapSelection(editor, localRow, selection); }
    finally { selectionGuard = false; }
    updateActions();
  }

  function onTypingPointer() {
    typingBoundary += 1;
  }

  editor.addEventListener("beforeinput", onBeforeInput);
  editor.addEventListener("input", fallbackInput);
  editor.addEventListener("compositionstart", onCompositionStart);
  editor.addEventListener("compositionend", onCompositionEnd);
  editor.addEventListener("keydown", onStructuralKey);
  editor.addEventListener("pointerdown", onTypingPointer);
  editor.addEventListener("focus", onFocus);
  editor.addEventListener("blur", onBlur);
  editor.addEventListener("paste", onPaste);
  stageButton.addEventListener("mousedown", preserveActionSelection);
  spokenButton.addEventListener("mousedown", preserveActionSelection);
  stageButton.addEventListener("click", activateAction);
  spokenButton.addEventListener("click", activateAction);
  const rowActionListeners = rowButtons.map((button) => {
    const onClick = () => performRowSelection(button.dataset.rowSelectionAction);
    button.addEventListener("mousedown", preserveActionSelection);
    button.addEventListener("click", onClick);
    return { button, onClick };
  });
  document.addEventListener("selectionchange", onSelectionChange);

  return () => {
    mounted = false;
    editor.removeEventListener("beforeinput", onBeforeInput);
    editor.removeEventListener("input", fallbackInput);
    editor.removeEventListener("compositionstart", onCompositionStart);
    editor.removeEventListener("compositionend", onCompositionEnd);
    editor.removeEventListener("keydown", onStructuralKey);
    editor.removeEventListener("pointerdown", onTypingPointer);
    editor.removeEventListener("focus", onFocus);
    editor.removeEventListener("blur", onBlur);
    editor.removeEventListener("paste", onPaste);
    document.removeEventListener("selectionchange", onSelectionChange);
    stageButton.removeEventListener("mousedown", preserveActionSelection);
    spokenButton.removeEventListener("mousedown", preserveActionSelection);
    stageButton.removeEventListener("click", activateAction);
    spokenButton.removeEventListener("click", activateAction);
    for (const { button, onClick } of rowActionListeners) {
      button.removeEventListener("mousedown", preserveActionSelection);
      button.removeEventListener("click", onClick);
    }
    if (composing && typeof compositionChange === "function") compositionChange(row.id, false);
  };
}

