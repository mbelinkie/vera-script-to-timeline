import { renderRows } from "./view.js";
import { mountRowsEditor, createBlankNarrationRow } from "./rows-editor.js";
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
let scriptDocument;
let documentRevision;
let pendingDocument;
let documentSaving = false;
let documentDirty = false;
let commandQueue = Promise.resolve();
let commandsPending = 0;
let editRefused = false;
let renderRequested = false;
let forceRender = false;
let renderTimer;
const composingRows = new Set();
const undoStack = [];
let narrationCleanup = [];
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
  renderEditor();
  updateUndo();
  project = savedProject;
  element("script-title").textContent = savedScript.document.title;
  document.title = `${savedScript.document.title} · VERA Authoring`;
  projectTitle.value = project.title;
  openSaved.href = projectLink(projectId);
  history.replaceState(null, "", projectLink(projectId));
  home.hidden = true;
  authoring.hidden = false;
  setSaveStatus("Saved");
  element("script-title").focus();
}

function renderEditor() {
  const root = element("script-rows");
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
  if (rowId && caret !== null) {
    const row = [...root.querySelectorAll("[data-row-id]")].find((item) => item.dataset.rowId === rowId);
    const editor = row?.querySelector("[data-narration-editor]");
    if (editor) {
      editor.focus();
      const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
      let remaining = caret;
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
    if (!forceRender && document.activeElement?.matches("[data-narration-editor]")) return;
    renderRequested = false;
    forceRender = false;
    renderEditor();
  }, 0);
}

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

function queueCommand(command, label, options = {}) {
  if (options.structural && composingRows.size) return Promise.resolve(false);
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
    const response = await fetch("/authoring/command", {
      method: "POST", headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
      body: JSON.stringify({ document: scriptDocument, command }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.diagnostics?.[0]?.message || "Edit could not be applied.");
    undoStack.push({ document: scriptDocument, label });
    scriptDocument = result.document;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    scheduleRender(options.structural);
    return true;
  }).catch((error) => {
    if (options.expectedRow) editRefused = true;
    setSaveStatus(error.message || "Edit could not be applied.");
    return false;
  }).finally(() => { commandsPending -= 1; if (renderRequested) scheduleRender(); });
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
  commandsPending += 1;
  commandQueue = commandQueue.then(() => {
    if (conflicted || editRefused || !undoStack.length) return;
    scriptDocument = undoStack.pop().document;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    scheduleRender(true);
  }).finally(() => { commandsPending -= 1; if (renderRequested) scheduleRender(); });
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
  saveStatus.textContent = message;
  retrySave.hidden = action !== "retry";
  openSaved.hidden = action !== "conflict";
}

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
