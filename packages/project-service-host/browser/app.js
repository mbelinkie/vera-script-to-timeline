import { renderRows } from "./view.js";
import { mountRowsEditor, createBlankNarrationRow, rowGaps } from "./rows-editor.js";
import { mountNarration } from "./narration-editor.js";

const element = (id) => document.getElementById(id);
const home = element("home-view");
const homeStatus = element("home-status");
const newForm = element("new-project-form");
const newTitle = element("new-project-title");
const openForm = element("open-project-form");
const openLink = element("open-script-link");
const authoring = element("authoring-view");
const projectTitle = element("project-title");
const saveStatus = element("save-status");
const retrySave = element("retry-save");
const openSaved = element("conflict-open-saved");

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
let project;
let activeProjectId;
let scriptDocument;
let documentRevision;
let pendingDocument;
let documentSaving = false;
let documentDirty = false;
let commandQueue = Promise.resolve();
let commandsPending = 0;
let editRefused = false;
let refusedMessage = "";
let renderRequested = false;
let forceRender = false;
let renderTimer;
const composingRows = new Set();
const undoStack = [];
// A snapshot belongs to the first keystroke of a continuous, adjacent run.
// Boundaries are captured at input time, not after the network response.
let typingGroup = null;
let narrationCleanup = [];
let structuralFocus = null;
let lastSplit = null;
let pendingName;
let pendingCreate;
let saveTimer;
let saving = false;
let opening = false;
let conflicted = false;
const browserRequired = "Open the private link printed by VERA Authoring to connect this browser.";
const sessionKey = "vera.authoring.sessionProof";
let sessionProof = "";

async function api(path, method = "GET", data) {
  await connecting;
  try { sessionProof = localStorage.getItem(sessionKey) ?? sessionProof; } catch { /* Keep the current proof. */ }
  const headers = { "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof };
  if (data) headers["Content-Type"] = "application/json";
  const response = await fetch(`/authoring/projects${path}`, {
    method, headers, body: data && JSON.stringify(data),
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) throw new ApiError(response.status);
  return await response.json();
}

class ApiError extends Error {
  constructor(status) {
    super("Project request failed.");
    this.status = status;
  }
}

function viewPreference(id, property, defaultValue) {
  const input = element(id);
  const key = `vera.authoring.${id}`;
  try { input.value = localStorage.getItem(key) ?? String(defaultValue); } catch {
    input.value = String(defaultValue);
  }
  const update = () => {
    const percent = Number(input.value);
    document.documentElement.style.setProperty(property, String(percent / 100));
    if (id === "thumbnail-size") document.documentElement.dataset.thumbnailScale = String(percent);
    input.setAttribute("aria-valuetext", `${percent}%`);
    const output = authoring.querySelector(`output[for="${id}"]`);
    if (output) output.value = `${percent}%`;
  };
  input.addEventListener("input", () => {
    update();
    try { localStorage.setItem(key, input.value); } catch { /* Current tab still scales. */ }
  });
  update();
}

viewPreference("authoring-size", "--authoring-zoom", 100);
viewPreference("thumbnail-size", "--thumbnail-scale", 22);

function projectLink(projectId) {
  return `/?project=${projectId}`;
}

function readProjectId(text) {
  let candidate = text.trim();
  if (!uuid.test(candidate)) {
    try {
      const url = new URL(candidate, location.origin);
      candidate = url.origin === location.origin && url.pathname === "/" ?
        url.searchParams.get("project") ?? "" : "";
    } catch { return null; }
  }
  return uuid.test(candidate) ? candidate.toLowerCase() : null;
}

async function showScript(projectId) {
  const [{ project: savedProject }, savedScript] = await Promise.all([
    api(`/${projectId}`), api(`/${projectId}/document`),
  ]);
  scriptDocument = savedScript.document;
  documentRevision = savedScript.revision;
  undoStack.length = 0;
  typingGroup = null;
  lastSplit = null;
  structuralFocus = null;
  renderEditor();
  updateUndo();
  project = savedProject;
  activeProjectId = projectId;
  element("script-title").textContent = savedScript.document.title;
  document.title = `${savedScript.document.title} · VERA Authoring`;
  projectTitle.value = project.title;
  openSaved.href = projectLink(projectId);
  history.replaceState(null, "", projectLink(projectId));
  home.hidden = true;
  authoring.hidden = false;
  setSaveStatus("Saved");
  element("script-title").focus();
  void refreshMusicWarnings();
}

async function refreshMusicWarnings() {
  if (!activeProjectId) return;
  const status = element("music-warning-status");
  const list = element("music-warning-list");
  list.replaceChildren();
  try {
    const { report } = await api(`/${activeProjectId}/music-warnings`);
    if (!report) {
      status.textContent = "No completed build report is available for this project yet.";
      return;
    }
    const warnings = report.musicWarnings;
    status.textContent = `Build ${report.buildId.slice(0, 8)} · script revision ${report.documentRevision} · ` +
      (warnings.length ? `${warnings.length} music warning${warnings.length === 1 ? "" : "s"}.` : "no music warnings.");
    for (const warning of warnings) {
      const item = document.createElement("li");
      const code = document.createElement("strong");
      code.textContent = `${warning.code}: `;
      item.append(code, document.createTextNode(warning.message));
      list.append(item);
    }
  } catch {
    status.textContent = "Latest build warnings could not be loaded.";
  }
}

window.addEventListener("focus", () => { void refreshMusicWarnings(); });
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refreshMusicWarnings();
});

function renderEditor() {
  const root = element("script-rows");
  const requestedFocus = structuralFocus;
  structuralFocus = null;
  const active = document.activeElement;
  const rowId = active?.matches("[data-narration-editor]") ? active.closest("[data-row-id]")?.dataset.rowId : null;
  let caret = null;
  if (rowId && document.getSelection()?.rangeCount) {
    const selection = document.getSelection().getRangeAt(0);
    const prefix = selection.cloneRange();
    prefix.selectNodeContents(active);
    prefix.setEnd(selection.endContainer, selection.endOffset);
    caret = prefix.toString().length;
  }
  narrationCleanup.forEach((cleanup) => cleanup());
  narrationCleanup = [];
  renderRows(root, scriptDocument);
  mountRowsEditor(root, scriptDocument, {
    createBlankRow: createBlankNarrationRow,
    command: (command, label) => queueCommand(command, label, { structural: true }),
  });
  root.querySelectorAll('.script-row .narration-cell').forEach((cell) => {
    narrationCleanup.push(mountNarration(cell, scriptDocument, queueCommand, {
      compositionChange(rowId, active) {
        if (active) composingRows.add(rowId);
        else { composingRows.delete(rowId); scheduleRender(); }
      },
      requestRender: scheduleRender,
    }));
  });
  const targetRowId = requestedFocus?.rowId ?? rowId;
  const targetCaret = requestedFocus?.offset ?? caret;
  if (targetRowId && targetCaret !== null) {
    const row = [...root.querySelectorAll("[data-row-id]")].find((item) => item.dataset.rowId === targetRowId);
    const editor = row?.querySelector("[data-narration-editor]");
    if (editor) {
      editor.focus();
      const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
      let remaining = targetCaret;
      let node = walker.nextNode();
      while (node && remaining > node.length) { remaining -= node.length; node = walker.nextNode(); }
      const range = document.createRange();
      if (node) range.setStart(node, Math.min(remaining, node.length));
      else range.selectNodeContents(editor);
      range.collapse(!node ? false : true);
      document.getSelection().removeAllRanges();
      document.getSelection().addRange(range);
    }
  }
}

function scheduleRender(force = false) {
  renderRequested = true;
  forceRender ||= force === true;
  if (renderTimer) return;
  renderTimer = setTimeout(() => {
    renderTimer = undefined;
    if (!renderRequested || editRefused || conflicted || commandsPending || composingRows.size) return;
    if (!forceRender && element("script-rows").contains(document.activeElement)) return;
    renderRequested = false;
    forceRender = false;
    renderEditor();
  }, 0);
}

element("script-rows").addEventListener("focusout", () => {
  if (renderRequested) setTimeout(() => scheduleRender(), 0);
});

async function saveDocument() {
  if (!project || documentSaving || conflicted || (!documentDirty && !pendingDocument)) return;
  if (!pendingDocument) {
    pendingDocument = { expectedRevision: documentRevision, clientMutationId: crypto.randomUUID(), document: scriptDocument };
    documentDirty = false;
  }
  documentSaving = true;
  setSaveStatus("Saving…");
  try {
    const receipt = await api(`/${project.projectId}/document`, "PUT", pendingDocument);
    documentRevision = receipt.revision;
    pendingDocument = undefined;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      conflicted = true;
      setSaveStatus("A newer script was saved elsewhere. Your unsaved changes are still here.", "conflict");
    } else setSaveStatus("Couldn’t save the script. Your unsaved changes are still here.", "retry");
    return;
  } finally { documentSaving = false; }
  if (documentDirty) void saveDocument();
  else if (!editRefused && !conflicted) setSaveStatus("Saved");
}

async function applyBrowserCommand(document, command, splitProof) {
  const response = await fetch("/authoring/command", {
    method: "POST", headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    body: JSON.stringify({ document, command, ...(splitProof ? { splitProof } : {}) }),
    signal: AbortSignal.timeout(12_000),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.diagnostics?.[0]?.message || "Edit could not be applied.");
  return result;
}

// Every intermediate document is private to this queued operation: a refusal
// or failed request discards *all* steps without a save or an Undo snapshot.
async function applyPlainPaste(document, intent) {
  const { rowId, startOffset, endOffset, blocks } = intent;
  const row = document.activeDraft.blocks.find((item) => item.id === rowId);
  const editableRow = row?.type === "narration" || row?.type === "visual_only" && row.clearedNarration;
  if (!editableRow || !Array.isArray(blocks) || !blocks.length ||
      blocks.some((block) => typeof block !== "string")) throw new Error("The paste target changed.");
  const insertedText = blocks.join("\n\n");
  const boundaries = [];
  for (let index = 0, offset = 0; index < blocks.length - 1; index += 1) {
    offset += blocks[index].length;
    boundaries.push({ start: startOffset + offset, end: startOffset + offset + 2 });
    offset += 2;
  }

  let working = document;
  // Always retokenize the complete first write before resolving any split:
  // later commands MUST use the token IDs returned by the actual model.
  const oldText = row.type === "narration" ? row.text : "";
  if (oldText.slice(startOffset, endOffset) !== insertedText) {
    const edited = await applyBrowserCommand(working, {
      kind: "edit_narration_text", rowId, startOffset, endOffset, insertedText, editId: crypto.randomUUID(),
    });
    working = edited.document;
  }
  let currentRowId = rowId;
  let shifted = 0;
  let caret = startOffset + insertedText.length;
  for (const boundary of boundaries) {
    const current = working.activeDraft.blocks.find((item) => item.id === currentRowId);
    if (current?.type !== "narration") throw new Error("The pasted row cannot be split safely.");
    const from = boundary.start - shifted;
    const to = boundary.end - shifted;
    if (current.text.slice(from, to) !== "\n\n") throw new Error("The pasted row boundary changed.");
    const hasLeftWords = current.tokens.some((token) => token.endOffset <= from);
    const firstRight = current.tokens.find((token) => token.startOffset >= to);
    if (hasLeftWords && firstRight) {
      const newRowId = crypto.randomUUID();
      const result = await applyBrowserCommand(working, {
        kind: "split_row", rowId: currentRowId, newRowId, at: { beforeTokenId: firstRight.id },
      });
      working = result.document;
      const created = working.activeDraft.blocks.find((item) => item.id === newRowId);
      if (created?.type !== "narration" || !current.text.endsWith(created.text)) {
        throw new Error("The model changed the pasted row boundary.");
      }
      const removed = current.text.length - created.text.length;
      shifted += removed;
      caret -= removed;
      currentRowId = newRowId;
      continue;
    }
    // The pure split command rightly refuses wordless halves. Remove the
    // separator with a model edit, then use the existing exact-gap Add row.
    // This also preserves the existing row's token/visual identities.
    const withoutBreak = await applyBrowserCommand(working, {
      kind: "edit_narration_text", rowId: currentRowId, startOffset: from,
      endOffset: to, insertedText: "", editId: crypto.randomUUID(),
    });
    working = withoutBreak.document;
    shifted += to - from;
    caret -= to - from;
    const above = !hasLeftWords;
    const gap = rowGaps(working.activeDraft.blocks).find((item) => above
      ? item.beforeRowId === currentRowId : item.afterRowId === currentRowId);
    if (!gap) throw new Error("The paste insertion gap changed.");
    const newRowId = crypto.randomUUID();
    const created = await applyBrowserCommand(working, {
      kind: "create_row", row: createBlankNarrationRow({ id: newRowId }), destination: gap,
    });
    working = created.document;
    if (!above) { currentRowId = newRowId; caret = 0; }
  }
  return { document: working, focusAfter: { rowId: currentRowId, offset: Math.max(0, caret) } };
}

function queueCommand(command, label, options = {}) {
  if (options.structural && composingRows.size) return Promise.resolve(false);
  const inputAt = performance.now();
  commandsPending += 1;
  commandQueue = commandQueue.then(async () => {
    if (conflicted || editRefused) return false;
    if (options.expectedRow) {
      const expected = options.expectedRow;
      const row = scriptDocument.activeDraft.blocks.find((item) => item.id === expected.id);
      const matchesNarration = row?.type === "narration" && row.text === expected.text &&
        Boolean(row.plainDirection) === expected.plainDirection;
      const matchesCleared = row?.type === "visual_only" && row.clearedNarration &&
        expected.text === "" && !expected.plainDirection;
      if (!matchesNarration && !matchesCleared) {
        throw new Error("The script changed while you were typing. Your unsaved text is still here.");
      }
    }
    // A keyboard structural intent is resolved against the latest document,
    // after any earlier typed words have received their real model token IDs.
    const resolved = typeof command === "function" ? command(scriptDocument) : command;
    if (options.paste) {
      typingGroup = null;
      const result = await applyPlainPaste(scriptDocument, resolved);
      if (result.document === scriptDocument) {
        scheduleRender(true);
        return true;
      }
      undoStack.push({ document: scriptDocument, label });
      scriptDocument = result.document;
      lastSplit = null;
      structuralFocus = result.focusAfter;
      updateUndo();
      documentDirty = true;
      void saveDocument();
      scheduleRender(true);
      return true;
    }
    const replay = resolved.kind === "join_rows" && resolved.direction === "previous" &&
      resolved.words === null && lastSplit?.newRowId === resolved.rowId &&
      lastSplit.revision === scriptDocument.rowEditRevision ? lastSplit : null;
    const previous = options.focusPrevious ? scriptDocument.activeDraft.blocks[
      scriptDocument.activeDraft.blocks.findIndex((item) => item.id === resolved.rowId) - 1
    ] : null;
    const result = await applyBrowserCommand(scriptDocument, resolved, replay?.proof);
    // Never join a paragraph, paste, selection replacement, stage action or
    // structural command to typing. Consecutive scalar insertions/backspaces
    // at the same caret are eligible; a changed cursor/session breaks the run.
    const plainTyping = options.typingSession && resolved.kind === "edit_narration_text" &&
      !options.structural && !options.paste && typeof resolved.insertedText === "string";
    const deleted = plainTyping && resolved.insertedText === "" &&
      resolved.endOffset > resolved.startOffset && resolved.endOffset - resolved.startOffset <= 2;
    const inserted = plainTyping && resolved.startOffset === resolved.endOffset &&
      resolved.insertedText.length > 0 && resolved.insertedText.length <= 2 && !resolved.insertedText.includes("\n");
    const editKind = inserted ? "insert" : deleted ? "delete" : null;
    const last = typingGroup;
    const adjacent = editKind === "insert" && last?.endOffset === resolved.startOffset ||
      editKind === "delete" && (last?.startOffset === resolved.startOffset || last?.startOffset === resolved.endOffset);
    const merge = !!(editKind && last && last.kind === editKind && adjacent &&
      last.rowId === resolved.rowId && last.session === options.typingSession &&
      last.boundary === options.typingBoundary && inputAt >= last.at && inputAt - last.at <= 1000);
    if (!merge) undoStack.push({ document: scriptDocument, label });
    typingGroup = editKind ? {
      kind: editKind, rowId: resolved.rowId, startOffset: resolved.startOffset,
      endOffset: resolved.startOffset + resolved.insertedText.length,
      session: options.typingSession, boundary: options.typingBoundary, at: inputAt,
    } : null;
    scriptDocument = result.document;
    lastSplit = resolved.kind === "split_row" && typeof result.splitProof === "string" ? {
      proof: result.splitProof, newRowId: resolved.newRowId, originalRowId: resolved.rowId,
      revision: scriptDocument.rowEditRevision, caret: options.splitCaret,
    } : null;
    if (options.focusAfter) structuralFocus = options.focusAfter;
    else if (previous?.type === "narration") structuralFocus = replay
      ? { rowId: replay.originalRowId, offset: replay.caret }
      : { rowId: previous.id, offset: previous.text.length + (previous.text.endsWith("\n") ? 0 : 1) };
    updateUndo();
    documentDirty = true;
    void saveDocument();
    scheduleRender(options.structural);
    return true;
  }).catch((error) => {
    typingGroup = null;
    if (options.expectedRow && (!options.structural || options.paste)) {
      editRefused = true;
      refusedMessage = `${error.message || "Edit could not be applied."} Your unsaved text is still here; copy it or discard it to continue.`;
      element("discard-edit").hidden = false;
      element("discard-edit").disabled = true;
    }
    setSaveStatus(refusedMessage || error.message || "Edit could not be applied.");
    return false;
  }).finally(() => {
    commandsPending -= 1;
    if (editRefused && commandsPending === 0) element("discard-edit").disabled = false;
    if (renderRequested) scheduleRender();
  });
  return commandQueue;
}

function updateUndo() {
  const button = element("undo");
  button.disabled = undoStack.length === 0;
  button.textContent = undoStack.length ? `↶ Undo ${undoStack[undoStack.length - 1].label}` : "↶ Undo";
  button.setAttribute("aria-label", undoStack.length ? `Undo ${undoStack[undoStack.length - 1].label}` : "Undo");
  button.title = undoStack.length ? button.textContent : "Nothing to undo in this session";
  const history = element("undo-history");
  history.replaceChildren(...undoStack.slice(-10).reverse().map(({ label }) => {
    const item = document.createElement("li");
    item.textContent = label;
    return item;
  }));
  if (!history.childElementCount) {
    const item = document.createElement("li");
    item.textContent = "Nothing to undo in this session";
    history.append(item);
  }
}

function undo() {
  if (composingRows.size) return;
  typingGroup = null;
  commandsPending += 1;
  commandQueue = commandQueue.then(() => {
    // Earlier requests may have completed after Undo was queued, restoring
    // a typing group. Undo is a history boundary at *execution* as well.
    typingGroup = null;
    if (conflicted || editRefused || !undoStack.length) return;
    scriptDocument = undoStack.pop().document;
    lastSplit = null;
    structuralFocus = null;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    scheduleRender(true);
  }).finally(() => {
    commandsPending -= 1;
    if (editRefused && commandsPending === 0) element("discard-edit").disabled = false;
    if (renderRequested) scheduleRender();
  });
}
element("undo").addEventListener("click", undo);
document.addEventListener("keydown", (event) => {
  if (!event.isComposing && (event.metaKey || event.ctrlKey) && !event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    undo();
  }
});

function showOpenError(error) {
  if (error instanceof ApiError && error.status === 401) {
    homeStatus.textContent = browserRequired;
    return;
  }
  homeStatus.textContent = error instanceof ApiError && [403, 404].includes(error.status) ?
    "Couldn’t open that script. Check the link or project ID." :
    "Couldn’t load the script. Check that VERA Authoring is running and try again.";
}

async function openScript(projectId) {
  if (opening) return;
  opening = true;
  homeStatus.textContent = "Opening script…";
  try { await showScript(projectId); } catch (error) { showOpenError(error); }
  finally { opening = false; }
}

function newScript(title) {
  const projectId = crypto.randomUUID();
  return {
    projectId, title, clientRequestId: crypto.randomUUID(),
    document: {
      schemaVersion: "script-document/v2", id: crypto.randomUUID(), projectId, title,
      activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
      liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"0".repeat(64)}`,
    },
  };
}

newForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (opening) return;
  const title = newTitle.value.trim();
  if (!title) {
    homeStatus.textContent = "Enter a name for the new script.";
    return;
  }
  opening = true;
  newTitle.readOnly = true;
  homeStatus.textContent = "Saving new script…";
  if (pendingCreate?.title !== title) pendingCreate = newScript(title);
  let created = false;
  try {
    await api("", "POST", pendingCreate);
    created = true;
    await showScript(pendingCreate.projectId);
    pendingCreate = undefined;
  } catch (error) {
    homeStatus.textContent = error instanceof ApiError && error.status === 401 ? browserRequired : created ?
      "Script saved. Couldn’t open it. Try Start script again." :
      "Couldn’t save the new script. Its name is still here. Try Start script again.";
  } finally {
    newTitle.readOnly = false;
    opening = false;
  }
});

openForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const id = readProjectId(openLink.value);
  if (id) void openScript(id);
  else homeStatus.textContent = "Enter a saved script link or project ID.";
});

function setSaveStatus(message, action) {
  if (editRefused) message = refusedMessage;
  saveStatus.textContent = message;
  retrySave.hidden = action !== "retry";
  openSaved.hidden = action !== "conflict";
}

element("discard-edit").addEventListener("click", () => {
  if (!editRefused || commandsPending || !window.confirm("Discard the unsaved text? Copy anything you want to keep first.")) return;
  editRefused = false;
  refusedMessage = "";
  element("discard-edit").hidden = true;
  forceRender = false;
  renderRequested = false;
  renderEditor();
  if (conflicted) setSaveStatus("A newer script was saved elsewhere. Your unsaved changes are still here.", "conflict");
  else if (pendingDocument || documentDirty) setSaveStatus("Couldn’t save the script. Your unsaved changes are still here.", "retry");
  else setSaveStatus("Saved");
});

async function saveName() {
  clearTimeout(saveTimer);
  if (!project || saving || conflicted) return;
  const title = projectTitle.value.trim();
  if (!pendingName) {
    if (!title) {
      setSaveStatus("Project name is required. Your change is unsaved.");
      return;
    }
    if (title === project.title) {
      setSaveStatus("Saved");
      return;
    }
    pendingName = {
      title, expectedProjectVersion: project.projectVersion, clientMutationId: crypto.randomUUID(),
    };
  }
  saving = true;
  setSaveStatus("Saving…");
  try {
    ({ project } = await api(`/${project.projectId}`, "PATCH", pendingName));
    pendingName = undefined;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      conflicted = true;
      setSaveStatus("A newer project name was saved elsewhere. Your unsaved name is still here.", "conflict");
    } else if (error instanceof ApiError && error.status === 401) {
      setSaveStatus("Your unsaved name is still here. Open the private VERA launch link in another tab, then retry here.", "retry");
    } else {
      setSaveStatus("Couldn’t save the project name. Your unsaved name is still here.", "retry");
    }
    return;
  } finally { saving = false; }
  // Replay the same receipt after a failed request. Any newer typing is saved
  // only after that request confirms the next project version.
  if (projectTitle.value.trim() !== project.title) void saveName();
  else setSaveStatus("Saved");
}

projectTitle.addEventListener("input", () => {
  if (saving || conflicted || pendingName) return;
  clearTimeout(saveTimer);
  setSaveStatus("Unsaved changes");
  saveTimer = setTimeout(() => { void saveName(); }, 350);
});
projectTitle.addEventListener("blur", () => {
  if (!pendingName) void saveName();
});
projectTitle.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    projectTitle.blur();
  }
});
retrySave.addEventListener("click", () => { if (pendingDocument || documentDirty) void saveDocument(); else void saveName(); });

function protectDraft(event) {
  if (pendingCreate || pendingName || pendingDocument || documentDirty || documentSaving || commandsPending || editRefused || composingRows.size || (project && projectTitle.value.trim() !== project.title)) {
    event.preventDefault();
    event.returnValue = true;
  }
}

window.addEventListener("beforeunload", protectDraft);
async function connectBrowser() {
  try { sessionProof = localStorage.getItem(sessionKey) ?? ""; } catch { /* The current page can still connect. */ }
  const launchCode = new URLSearchParams(location.hash.slice(1)).get("launch");
  if (!launchCode) return;
  history.replaceState(null, "", location.pathname + location.search);
  try {
    const response = await fetch("/authoring/session", {
      method: "POST", headers: { "X-VERA-Authoring": "1", "X-VERA-Launch": launchCode },
      signal: AbortSignal.timeout(12_000),
    });
    if (response.ok) {
      ({ sessionProof } = await response.json());
      try { localStorage.setItem(sessionKey, sessionProof); } catch { /* Keep the proof in this page. */ }
      return;
    }
  } catch { /* Show the same recovery for an unavailable host. */ }
  if (!sessionProof) homeStatus.textContent = browserRequired;
}

const connecting = connectBrowser();
const initialProject = new URLSearchParams(location.search).get("project");
if (initialProject !== null) {
  openLink.value = initialProject;
  if (uuid.test(initialProject)) void openScript(initialProject.toLowerCase());
  else homeStatus.textContent = "Enter a saved script link or project ID.";
}
