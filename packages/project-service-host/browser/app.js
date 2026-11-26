import { mountAccountPanel } from "./account-panel.js";
import { mountVisualCardMenus, renderRows } from "./view.js";
import { mountRowsEditor, createBlankNarrationRow, rowGaps, rowLabel } from "./rows-editor.js";
import { mountNarration, mountVisualConnectors } from "./narration-editor.js";
import { parseHoldSeconds, planVisualOnlyReorder, visualOnlyIds } from "./visual-only-actions.js";
import { mountResearchPanel, renderFootageUseShortcuts } from "./research-panel.js";
import { mountResearchStillPanel } from "./research-still-panel.js";
import { captureWholeRowStash, createStashActions } from "./stash-actions.js";
import { mountStashPanel } from "./stash-panel.js";
import { selectedSpokenWords } from "./visual-selection.js";

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
const prompterDialog = element("prompter-dialog");
const prompterStatus = element("prompter-status");

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
const visualCommandKinds = new Set([
  "add_visual_on_selection", "change_visual_type", "delete_visual",
  "set_visual_range", "set_on_camera_framing",
  "move_visual_to_row", "attach_visual_to_words",
]);
const revisionedRowCommandKinds = new Set(["move_wordless_visual", "add_visual_to_wordless_row",
  "reorder_visual_only", "set_visual_only_hold", "add_row_transition", "remove_row_transition"]);
let project;
let projectVisualHoldMs;
let activeProjectId;
let scriptDocument;
let flashVisualIds = new Set();
let visualFeedback = "";
let cardFocus = null;
let documentRevision;
let documentDigest;
let pendingDocument;
let documentSaveFailure;
let documentSaving = false;
let documentSaveTask = null;
let pendingExtras;
let extrasRunning = false;
let extrasFailure;
let documentDirty = false;
let commandQueue = Promise.resolve();
let commandsPending = 0;
let visualProjection = null;
let activeReselect = null;
let activeAttach = null;
let projectionGeneration = 0;
let projectionTimer;
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
let rowsCleanup;
let structuralFocus = null;
let lastSplit = null;
let pendingName;
let nameSaveFailure;
let pendingCreate;
let saveTimer;
let saving = false;
let opening = false;
let conflicted = false;
let lastQuoteTarget = null;
const browserRequired = "Open the private link printed by VERA Authoring to connect this browser.";
const sessionKey = "vera.authoring.sessionProof";
let sessionProof = "";
let prompterGeneration = 0;
let prompterPreparing = false;
let preparedPrompter = null;
let researchPanel;
let researchStillPanel;
let sortingTrial = null;
let stashPanel;
let stashScriptDrag = null;

let accountRole = null;
let accountWriteSession = "";
let accountHold = false;
let accountEnded = false;
let accountGeneration = 0;
const canEditAccount = () => !accountPanel.accountMode() ||
  !accountHold && !accountEnded && (accountRole === "producer" || accountRole === "editor");
const accountPanel = mountAccountPanel({
  root: element("account-panel"), request: api,
  onAccess: updateAccountAccess,
  onSessionEnded: () => updateAccountAccess({ denied: true, role: null }),
  beforeSignOut: () => !hasPendingDraft() ||
    window.confirm("Sign out and leave unsaved changes? They will not be sent under another account."),
});
function updateAccountAccess(access) {
  const previous = accountRole;
  accountRole = access.role;
  if (access.denied && !accountEnded) {
    accountEnded = true; accountHold = true; accountGeneration += 1;
    clearTimeout(saveTimer); clearTimeout(renderTimer);
    home.hidden = true; authoring.hidden = true;
    element("account-notice").hidden = true;
    element("account-access-ended").hidden = false;
    element("account-access-ended").querySelector("h1").focus();
  } else if (access.unavailable || access.changed || accountRole === "viewer" && previous && previous !== "viewer") {
    if (!accountHold) accountGeneration += 1;
    accountHold = true;
    clearTimeout(saveTimer); clearTimeout(renderTimer);
    const notice = element("account-notice");
    element("account-notice-title").textContent = access.unavailable ? "Access could not be verified" : "You’re now a Viewer";
    if (notice.hidden) { notice.hidden = false; notice.focus(); }
  }
  if (accountHold) {
    narrationCleanup.forEach((cleanup) => cleanup()); narrationCleanup = [];
    rowsCleanup?.(); rowsCleanup = undefined;
    for (const editable of element("script-rows").querySelectorAll('[contenteditable="true"]')) editable.contentEditable = "false";
    for (const control of element("script-rows").querySelectorAll("button, input, select, textarea")) control.disabled = true;
    researchPanel?.close(); researchStillPanel?.close(); stashPanel?.close(false, true);
  } else if (previous !== accountRole && scriptDocument) renderEditor();
  projectTitle.readOnly = accountRole !== "producer" || accountHold;
  for (const id of ["undo", "open-sorting", "open-stash", "open-footage"]) element(id).hidden = !canEditAccount();
  element("undo-history").closest("details").hidden = !canEditAccount();
  if (!canEditAccount()) retrySave.hidden = true;
}
element("account-discard").addEventListener("click", async () => {
  const button = element("account-discard");
  if (commandsPending || documentSaving || saving || extrasRunning || sortingTrial?.pending) return;
  button.disabled = true;
  try {
    // Explicitly discard every refused mutation and Undo basis before a fresh read.
    accountGeneration += 1;
    pendingDocument = pendingName = pendingExtras = undefined;
    documentSaveFailure = nameSaveFailure = extrasFailure = undefined;
    documentDirty = false; editRefused = false; refusedMessage = "";
    composingRows.clear(); undoStack.length = 0;
    element("discard-edit").hidden = true;
    accountHold = false;
    await showScript(activeProjectId);
    element("account-notice").hidden = true;
  } catch { accountHold = true; element("account-notice-title").textContent = "Couldn’t load the saved script. Try again."; }
  finally { button.disabled = false; }
});
async function accountFetch(path, options = {}) {
  if (accountPanel.accountMode() && options.method && options.method !== "GET" &&
      !path.endsWith("/projection") && !path.endsWith("/prompter-export") &&
      !path.endsWith("/visual-preview") && !path.endsWith("/write-session") && path !== "/authoring/projects" && !canEditAccount()) {
    throw new ApiError(403, { error: "action_not_allowed" });
  }
  const generation = accountGeneration;
  const response = await fetch(path, { ...options, headers: { ...options.headers, ...accountPanel.headers(), "X-VERA-Write-Session": accountWriteSession } });
  if (accountPanel.accountMode() && !path.endsWith("/access") && [401, 403].includes(response.status)) {
    if (options.method && options.method !== "GET") updateAccountAccess({ role: accountRole, unavailable: true });
    void accountPanel.refresh();
  }
  if (options.method && options.method !== "GET" && generation !== accountGeneration) {
    throw new ApiError(403, { error: "access_changed" });
  }
  return response;
}

const editorDocument = () => sortingTrial?.document ?? scriptDocument;
const editorProjection = () => sortingTrial ? sortingTrial.projection : visualProjection;

async function api(path, method = "GET", data) {
  await connecting;
  try { sessionProof = localStorage.getItem(sessionKey) ?? sessionProof; } catch { /* Keep the current proof. */ }
  const headers = { "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof };
  if (data) headers["Content-Type"] = "application/json";
  const response = await accountFetch(`/authoring/projects${path}`, {
    method, headers, body: data && JSON.stringify(accountPanel.accountMode() &&
      (method === "PUT" && path.endsWith("/document") || method === "POST" && path.endsWith("/extras-operations"))
      ? { ...data, writeSessionId: accountWriteSession } : data),
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) throw new ApiError(response.status, await response.json().catch(() => null));
  return await response.json();
}

class ApiError extends Error {
  constructor(status, body) {
    super("Project request failed.");
    this.status = status;
    this.body = body;
  }
}

const savedDigestPattern = /^sha256:[0-9a-f]{64}$/u;

function prompterReady() {
  return Boolean(project && activeProjectId === project.projectId && scriptDocument &&
    Number.isSafeInteger(documentRevision) && savedDigestPattern.test(documentDigest ?? "") &&
    !opening && !saving && !pendingName && !pendingCreate && !conflicted && !editRefused &&
    !documentSaving && !documentDirty && !pendingDocument && !pendingExtras && !commandsPending &&
    !composingRows.size && !sortingTrial && projectTitle.value.trim() === project.title);
}

function currentPrompterPair() {
  return preparedPrompter && prompterReady() &&
    preparedPrompter.projectId === activeProjectId &&
    preparedPrompter.revision === documentRevision &&
    preparedPrompter.digest === documentDigest ? preparedPrompter : null;
}

function updatePrompterControls() {
  const ready = prompterReady();
  if (sortingTrial) updateSortingControls();
  else element("open-sorting").disabled = !ready;
  element("open-prompter").disabled = !ready;
  element("open-prompter").title = ready ? "Export the saved script" : "Save your script before exporting";
  element("prepare-prompter").disabled = !ready || prompterPreparing;
  const pair = currentPrompterPair();
  element("download-prompter-text").disabled = !pair;
  element("download-prompter-sidecar").disabled = !pair;
  element("prompter-ready").hidden = !pair;
}

function clearPreparedPrompter(message = "") {
  ++prompterGeneration;
  preparedPrompter = null;
  prompterStatus.textContent = message;
  updatePrompterControls();
}

function prompterDiagnostics(error) {
  if (error?.status === 409) return "The saved script changed. Reload the script, finish saving and prepare again.";
  if (error?.status === 422) {
    const diagnostics = error.body?.diagnostics;
    if (Array.isArray(diagnostics) && diagnostics.length) {
      return `Prompter validation failed: ${diagnostics.map((item) =>
        typeof item?.message === "string" ? item.message : String(item?.code ?? "Invalid script")).join("; ")}`;
    }
    return "Prompter validation failed. Resolve the incomplete or conflicting narration and try again.";
  }
  if (error?.status === 401 || error?.status === 403) return "Access to this saved script was refused. Reconnect your browser or check permissions.";
  if (error?.status === 404) return "The saved script is no longer available. Reload to check its status.";
  return "Couldn’t prepare the prompter files. Check the saved script and the local service, then try again.";
}

async function preparePrompter() {
  if (prompterPreparing) return;
  clearPreparedPrompter();
  // Queued edits and their saves must settle before we pin a saved head;
  // never fall back to the current, potentially unsaved, browser document.
  await commandQueue;
  if (!prompterReady() || !prompterDialog.open) {
    prompterStatus.textContent = "Save your script before preparing an export.";
    return;
  }
  const projectId = activeProjectId;
  const revision = documentRevision;
  const digest = documentDigest;
  const generation = prompterGeneration;
  prompterPreparing = true;
  prompterStatus.textContent = `Preparing saved revision ${revision}…`;
  updatePrompterControls();
  const current = () => generation === prompterGeneration && prompterDialog.open &&
    prompterReady() && activeProjectId === projectId &&
    documentRevision === revision && documentDigest === digest;
  try {
    const pair = await api(`/${projectId}/prompter-export`, "POST", {
      expectedRevision: revision, expectedDigest: digest,
      settings: {
        includeSectionNavigation: element("prompter-sections").checked,
        includeBeatNumbers: element("prompter-beats").checked,
      },
    });
    if (!current()) return;
    if (pair.projectId !== projectId || pair.revision !== revision || pair.digest !== digest ||
        typeof pair.text !== "string" || typeof pair.sidecarJson !== "string" ||
        !savedDigestPattern.test(pair.textSha256) || !savedDigestPattern.test(pair.sidecarSha256)) {
      throw new Error("Invalid saved prompter export response");
    }
    preparedPrompter = Object.freeze({ projectId, revision, digest,
      text: pair.text, sidecarJson: pair.sidecarJson,
      textSha256: pair.textSha256, sidecarSha256: pair.sidecarSha256 });
    element("prompter-snapshot").textContent = `Saved revision ${revision} · ${digest}`;
    element("prompter-text-hash").textContent = pair.textSha256;
    element("prompter-sidecar-hash").textContent = pair.sidecarSha256;
    prompterStatus.textContent = pair.text ? "Both files are ready to download separately." :
      "This saved script has no spoken narration. The empty text and matching sidecar are ready.";
  } catch (error) {
    if (current()) prompterStatus.textContent = prompterDiagnostics(error);
  } finally {
    prompterPreparing = false;
    updatePrompterControls();
  }
}

function downloadPrompter(kind) {
  const pair = currentPrompterPair();
  if (!pair) return;
  const content = kind === "text" ? pair.text : pair.sidecarJson;
  const file = kind === "text" ? "txt" : "beats.json";
  const objectUrl = URL.createObjectURL(new Blob([content], { type: kind === "text" ?
    "text/plain;charset=utf-8" : "application/json;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `vera-prompter-r${pair.revision}.${file}`;
  link.click();
  // Chrome must have time to take the blob before its object URL is revoked.
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

element("open-prompter").addEventListener("click", () => {
  if (!prompterReady()) return;
  clearPreparedPrompter();
  prompterDialog.showModal();
  element("prepare-prompter").focus();
});
element("close-prompter").addEventListener("click", () => prompterDialog.close());
prompterDialog.addEventListener("close", () => {
  clearPreparedPrompter();
  element("open-prompter").focus();
});
for (const name of ["prompter-sections", "prompter-beats"]) {
  element(name).addEventListener("change", () => clearPreparedPrompter("Settings changed. Prepare again to download the new files."));
}
element("prepare-prompter").addEventListener("click", () => { void preparePrompter(); });
element("download-prompter-text").addEventListener("click", () => downloadPrompter("text"));
element("download-prompter-sidecar").addEventListener("click", () => downloadPrompter("sidecar"));

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
  await connecting;
  activeProjectId = projectId;
  await accountPanel.setProject(projectId);
  if (accountEnded || accountHold) throw new ApiError(403, { error: "access_changed" });
  accountWriteSession = "";
  if (accountPanel.accountMode() && canEditAccount()) {
    ({ writeSessionId: accountWriteSession } = await api(`/${projectId}/write-session`, "POST", {}));
  }
  sortingTrial = null;
  setSortingMode(false);
  clearPreparedPrompter();
  if (prompterDialog.open) prompterDialog.close();
  const [{ project: savedProject }, savedScript, { milliseconds }] = await Promise.all([
    api(`/${projectId}`), api(`/${projectId}/document`), api(`/${projectId}/visual-hold-default`),
  ]);
  scriptDocument = savedScript.document;
  lastQuoteTarget = null;
  projectVisualHoldMs = milliseconds;
  flashVisualIds = new Set();
  visualFeedback = "";
  documentRevision = savedScript.revision;
  documentDigest = savedScript.digest;
  // Finish the initial projection before exposing editable rows. Otherwise a
  // late projection response remounts the entire row list just as the user
  // selects words, composes text or reaches for an Add row control.
  const generation = ++projectionGeneration;
  clearTimeout(projectionTimer);
  visualProjection = null;
  try {
    const projection = await fetchProjection(scriptDocument);
    if (generation !== projectionGeneration) return;
    visualProjection = projection;
  } catch {
    // Projection is derived decoration; an unavailable service must not block
    // access to the saved script.
  }
  undoStack.length = 0;
  typingGroup = null;
  lastSplit = null;
  structuralFocus = null;
  activeReselect = null;
  activeAttach = null;
  researchPanel?.close();
  researchStillPanel?.close();
  stashPanel?.close(false, true);
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
  if (accountPanel.accountMode()) updateAccountAccess({ role: accountRole });
  element("script-title").focus();
  void refreshMusicWarnings();
}

const musicWarningLabels = {
  MUSIC_SOURCE_SHORTER: "Music ends early",
  MUSIC_FILE_MISSING: "Music file missing",
  MUSIC_SPAN_INVALID: "Music cue can’t be placed",
  MUSIC_SETTINGS_UNSUPPORTED: "Music settings aren’t supported",
  MORE_MUSIC_WARNINGS: "Additional warnings",
};
let musicWarningRequest = 0;

async function refreshMusicWarnings() {
  if (!activeProjectId) return;
  const projectId = activeProjectId;
  const request = ++musicWarningRequest;
  const current = () => projectId === activeProjectId && request === musicWarningRequest;
  const status = element("music-warning-status");
  const list = element("music-warning-list");
  try {
    const { report } = await api(`/${projectId}/music-warnings`);
    if (!current()) return;
    list.replaceChildren();
    if (!report) {
      status.textContent = "No completed build report is available for this project yet.";
      return;
    }
    const warnings = report.musicWarnings;
    const overflow = warnings.some((warning) => warning.code === "MORE_MUSIC_WARNINGS");
    const version = report.documentRevision === documentRevision ? "saved script" : "earlier script version";
    status.textContent = `Build ${report.buildId.slice(0, 8)} · ${version} · ` +
      (overflow ? "music warnings." : warnings.length ? `${warnings.length} music warning${warnings.length === 1 ? "" : "s"}.` : "no music warnings.");
    for (const warning of warnings) {
      const item = document.createElement("li");
      const label = document.createElement("strong");
      label.textContent = `${musicWarningLabels[warning.code] ?? "Music warning"}: `;
      item.append(label, document.createTextNode(warning.message));
      list.append(item);
    }
  } catch {
    if (!current()) return;
    list.replaceChildren();
    status.textContent = "Latest build warnings could not be loaded.";
  }
}

window.addEventListener("focus", () => { void refreshMusicWarnings(); });
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refreshMusicWarnings();
});

function renderEditor() {
  stashPanel?.update();
  const root = element("script-rows");
  const model = editorDocument();
  if (sortingTrial?.preview || !canEditAccount()) {
    narrationCleanup.forEach((cleanup) => cleanup());
    narrationCleanup = [];
    rowsCleanup?.();
    rowsCleanup = undefined;
    renderRows(root, model, { projection: editorProjection(), quotePicture: researchPlacedQuotePictureGet });
    return;
  }
  const requestedFocus = structuralFocus;
  structuralFocus = null;
  const requestedCardFocus = cardFocus;
  cardFocus = null;
  const active = document.activeElement;
  const focusedCard = active?.matches("[data-footage-use]") ? active.closest("[data-footage-placement]") : null;
  const highlightedCard = root.querySelector(".visual-card--footage-use-target");
  const rowId = active?.matches("[data-narration-editor]") ? active.closest("[data-row-id]")?.dataset.rowId : null;
  const framingFocus = active?.matches("[data-visual-framing]") ? {
    rowId: active.closest("[data-row-id]")?.dataset.rowId,
    slotId: active.closest("[data-slot-id]")?.dataset.slotId,
    framing: active.dataset.visualFraming,
  } : null;
  const bracketFocus = active?.matches("[data-range-slot]") ? {
    rowId: active.closest("[data-row-id]")?.dataset.rowId,
    slotId: active.dataset.rangeSlot,
    edge: active.dataset.rangeEdge,
  } : null;
  const reselectFocus = active?.matches("[data-reselect-open]") ? {
    rowId: active.closest("[data-row-id]")?.dataset.rowId,
    slotId: active.closest("[data-slot-id]")?.dataset.slotId,
    opener: active.dataset.reselectOpen,
  } : null;
  const transitionFocus = active?.matches("[data-row-transition]")
    ? active.closest("[data-row-gap]")?.dataset.rowGap : null;
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
  renderRows(root, model, {
    projection: editorProjection(), visualCommand: queueVisualCommand, reselect: beginReselect,
    attach: beginAttach, attaching: activeAttach,
    addWordless: addWordlessVisual, projectVisualHoldMs, allowStash: true,
    quoteBoxEdit: sortingTrial ? undefined : queueResearchQuoteBoxEdit,
    quoteBoxRangeEdit: sortingTrial ? undefined : queueQuoteBoxRangeEdit,
    quotePicture: researchPlacedQuotePictureGet,
    flashIds: flashVisualIds,
  });
  if (!sortingTrial) renderFootageUseShortcuts(root, model, { focusedCard, highlightedCard });
  flashVisualIds = new Set();
  narrationCleanup.push(mountVisualCardMenus(root,
    (command, label, focus) => queueCommand(command, label, { structural: true, cardFocus: focus }),
    stashVisual));

  narrationCleanup.push(mountVisualCardDragging(root));
  if (!sortingTrial) narrationCleanup.push(mountResearchDragging(root));
  narrationCleanup.push(mountWordlessControls(root));
  rowsCleanup = mountRowsEditor(root, model, {
    createBlankRow: createBlankNarrationRow,
    command: (command, label) => queueCommand(command, label, { structural: true }),
    stashRow: async (rowId) => {
      const ok = await stashActions.stashRow(rowId);
      if (ok) stashPanel.open();
      return ok;
    },
    stashGroup,
    onRowDrag(rowIds) {
      stashScriptDrag = rowIds ? { kind: "rows", rowIds, snapshot: model } : null;
    },
  });
  root.querySelectorAll('.script-row .narration-cell').forEach((cell) => {
    narrationCleanup.push(mountNarration(cell, model, queueCommand, {
      projection: projectedPrimaryRow(cell.closest("[data-row-id]")?.dataset.rowId),
      visualCommand: queueVisualCommand,
      reselect: activeReselect?.rowId === cell.closest("[data-row-id]")?.dataset.rowId ? activeReselect : null,
      cancelReselect,
      commitReselect,
      previewReselect,
      attaching: activeAttach?.rowId === cell.closest("[data-row-id]")?.dataset.rowId ? activeAttach : null,
      finishAttach, cancelAttach,
      compositionChange(rowId, active) {
        if (active) { composingRows.add(rowId); clearPreparedPrompter("Save your script before exporting."); }
        else { composingRows.delete(rowId); scheduleRender(); }
        updatePrompterControls();
      },
      requestRender: scheduleRender,
      chooseFootage: sortingTrial ? undefined : openFootageForWords,
      chooseStill: sortingTrial ? undefined : openStillForWords,
      stashWords(rowId, selection, displayedText) {
        const row = editorDocument()?.activeDraft.blocks.find((item) => item.id === rowId);
        if (row?.text !== displayedText) {
          setSaveStatus("Finish saving the current narration before stashing words.");
          return;
        }
        const projectId = activeProjectId;
        void stashActions.stashWords(rowId, selection).then((ok) => {
          if (ok && activeProjectId === projectId) stashPanel.open();
        });
      },
    }));
  });
  if (sortingTrial) decorateSortingRows(root, model);
  if (requestedCardFocus) {
    const row = [...root.querySelectorAll("[data-row-id]")]
      .find((item) => item.dataset.rowId === requestedCardFocus.rowId);
    const card = [...(row?.querySelectorAll(".visual-card") ?? [])]
      .find((item) => item.dataset.slotId === requestedCardFocus.slotId);
    (card?.querySelector("[data-visual-action-trigger]") ??
      row?.querySelector("[data-visual-action-trigger]") ??
      row?.querySelector(".visual-card"))?.focus();
    return;
  }
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
  if (framingFocus) {
    const button = [...root.querySelectorAll("[data-visual-framing]")].find((item) =>
      item.dataset.visualFraming === framingFocus.framing &&
      item.closest("[data-row-id]")?.dataset.rowId === framingFocus.rowId &&
      item.closest("[data-slot-id]")?.dataset.slotId === framingFocus.slotId);
    button?.focus();
  }
  if (bracketFocus) {
    const handle = [...root.querySelectorAll("[data-range-slot]")].find((item) =>
      item.dataset.rangeSlot === bracketFocus.slotId && item.dataset.rangeEdge === bracketFocus.edge &&
      item.closest("[data-row-id]")?.dataset.rowId === bracketFocus.rowId);
    handle?.focus();
  }
  if (reselectFocus) focusReselectOpener(reselectFocus);
  if (transitionFocus) {
    const divider = [...root.querySelectorAll("[data-row-gap]")]
      .find((item) => item.dataset.rowGap === transitionFocus);
    (divider?.querySelector("[data-row-transition]") ?? divider?.querySelector("[data-row-add]"))?.focus();
  }
}

async function stashGroup(rowIds) {
  const expected = captureWholeRowStash(editorDocument(), rowIds);
  if (!expected) return false;
  const ok = await queueCommand((current) => {
    if (JSON.stringify(captureWholeRowStash(current, rowIds)) !== JSON.stringify(expected)) {
      throw new Error("The selected rows or their Stash location changed.");
    }
    return { kind: "stash_group_rows", rowIds, bundleId: crypto.randomUUID(),
      groupId: crypto.randomUUID(), sectionId: null, parentRowId: null, afterRowId: null };
  }, "Stash group", { structural: true });
  if (ok && expected.projectId === activeProjectId) stashPanel.open();
  return ok;
}

async function stashVisual(rowId, slotId) {
  const expected = editorDocument();
  const ok = await queueCommand((current) => {
    if (current !== expected) throw new Error("The visual or its Stash location changed.");
    return { kind: "stash_visual", rowId, slotId, bundleId: crypto.randomUUID(),
      stashRowId: crypto.randomUUID(), sectionId: null, parentRowId: null, afterRowId: null };
  }, "Stash visual", { structural: true });
  if (ok && expected.projectId === activeProjectId) stashPanel.open();
}

function beginAttach(rowId, slotId) {
  const row = editorDocument()?.activeDraft.blocks.find((item) => item.id === rowId);
  if (row?.type !== "narration" || !row.unattachedVisuals?.some((item) => item.slotId === slotId)) {
    setSaveStatus("The visual is no longer waiting for words.");
    return;
  }
  activeReselect = null;
  activeAttach = { rowId, slotId, projectId: activeProjectId };
  renderEditor();
  const editor = [...element("script-rows").querySelectorAll("[data-narration-editor]")]
    .find((item) => item.closest("[data-row-id]")?.dataset.rowId === rowId);
  editor?.focus();
  setSaveStatus("Select the spoken words for this visual, then choose Attach visual. Esc cancels.");
}

function cancelAttach() {
  if (!activeAttach) return;
  activeAttach = null;
  renderEditor();
  setSaveStatus("Attach cancelled. The visual is still waiting for words.");
}

function finishAttach(state) {
  if (activeAttach !== state) return;
  activeAttach = null;
  renderEditor();
}

function addWordlessVisual(rowId, visualType) {
  const projectId = activeProjectId;
  const payloadId = crypto.randomUUID();
  const slotId = crypto.randomUUID();
  void queueCommand((latest) => {
    if (projectId !== activeProjectId) throw new Error("The project changed before adding the picture.");
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    if (row?.type !== "visual_only" &&
        !(row?.type === "narration" && row.text === "" && row.tokens.length === 0 && !row.plainDirection)) {
      throw new Error("Add pictures only to rows without narration.");
    }
    return { kind: "add_visual_to_wordless_row", rowId, payloadId, slotId, visualType };
  }, "Add visual", { structural: true });
}

function mountWordlessControls(root) {
  const commitHold = (input) => {
    if (input.dataset.holdCommitting) return;
    const rowId = input.closest("[data-row-id]")?.dataset.rowId;
    const payloadId = input.dataset.visualHold;
    if (!rowId || !payloadId) return;
    const seconds = parseHoldSeconds(input.value);
    if (seconds === null) {
      input.value = input.dataset.savedSeconds;
      setSaveStatus(`Hold must be a positive number of seconds (up to three decimal places). Kept ${input.dataset.savedSeconds} s.`);
      return;
    }
    if (seconds === Number(input.dataset.savedSeconds)) {
      input.value = input.dataset.savedSeconds;
      return;
    }
    input.dataset.holdCommitting = "true";
    const projectId = activeProjectId;
    void queueCommand((latest) => {
      if (projectId !== activeProjectId) throw new Error("The project changed before saving the hold.");
      const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
      if (!visualOnlyIds(row)?.includes(payloadId)) throw new Error("The picture is no longer in the row.");
      return { kind: "set_visual_only_hold", rowId, payloadId, holdSeconds: seconds };
    }, "Set visual hold", { structural: true }).then((ok) => {
      if (input.isConnected) {
        delete input.dataset.holdCommitting;
        if (!ok) input.value = input.dataset.savedSeconds;
      }
    });
  };
  const onKeydown = (event) => {
    const input = event.target.closest("[data-visual-hold]");
    if (input && event.key === "Enter") {
      event.preventDefault();
      commitHold(input);
    } else if (input && event.key === "Escape") {
      event.preventDefault();
      input.value = input.dataset.savedSeconds;
      input.blur();
    } else if (event.key === "Escape") {
      const menu = event.target.closest(".visuals-wordless-choices");
      if (menu && !menu.hidden) {
        event.preventDefault();
        event.stopPropagation();
        menu.hidden = true;
        const trigger = menu.previousElementSibling;
        trigger.setAttribute("aria-expanded", "false");
        trigger.focus();
      }
    }
  };
  const onBlur = (event) => {
    const input = event.target.closest("[data-visual-hold]");
    if (input) commitHold(input);
  };
  root.addEventListener("keydown", onKeydown);
  root.addEventListener("focusout", onBlur);
  return () => {
    root.removeEventListener("keydown", onKeydown);
    root.removeEventListener("focusout", onBlur);
  };
}

// Native picture dragging is deliberately independent of rows-editor's row
// handle and gap drag state. No model edit occurs before a valid cross-row drop.
function mountVisualCardDragging(root) {
  let dragging = null;
  let target = null;
  let reorderMarker = null;
  const clear = () => {
    target?.classList.remove("script-row--visual-drop-target");
    reorderMarker?.classList.remove("visual-card--reorder-before");
    root.querySelectorAll(".visual-card--dragging").forEach((card) => card.classList.remove("visual-card--dragging"));
    if (dragging) stashScriptDrag = null;
    dragging = null;
    target = null;
    reorderMarker = null;
  };
  const rowFor = (id, doc = editorDocument()) => doc?.activeDraft.blocks.find((row) => row.id === id);
  const onStart = (event) => {
    if (event.target.closest("button, input, [contenteditable]")) return;
    const card = event.target.closest("[data-visual-drag]");
    const rowId = card?.closest("[data-row-id]")?.dataset.rowId;
    const row = rowFor(rowId);
    if (!card || !event.dataTransfer || !row || row.type !== "narration" && row.type !== "visual_only") return;
    const slotId = card.dataset.slotId;
    const payloadId = card.dataset.payloadId;
    const content = row.type === "narration" && (row.primaryVisualSequence?.slots.some((slot) =>
      slot.kind === "content" && slot.id === slotId && slot.payload.kind === "visual") ||
      row.unattachedVisuals?.some((item) => item.slotId === slotId && item.payload.kind === "visual"));
    if (row.type === "narration" && !content || row.type === "visual_only" &&
      (!payloadId || !visualOnlyIds(row)?.includes(payloadId))) return;
    dragging = { rowId, slotId, payloadId, projectId: activeProjectId, sourceType: row.type };
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-vera-visual", "picture");
    if (row.type === "narration") {
      stashScriptDrag = { kind: "visual", rowId, slotId, payloadId, snapshot: editorDocument() };
    } else if (!row.additionalVisuals?.length) {
      stashScriptDrag = { kind: "rows", rowIds: [rowId], snapshot: editorDocument() };
      event.dataTransfer.setData("application/x-vera-script-rows", "rows");
    }
    if (stashScriptDrag) event.dataTransfer.setDragImage(card, -12, -12);
    card.classList.add("visual-card--dragging");
  };
  const destination = (event) => {
    const row = event.target.closest(".script-row");
    const id = row?.dataset.rowId;
    const model = rowFor(id);
    return dragging && id && (id !== dragging.rowId || dragging.sourceType === "visual_only") &&
      (model?.type === "narration" || model?.type === "visual_only") ? row : null;
  };
  const reorderBefore = (event, row) => {
    const card = event.target.closest(".visual-card[data-payload-id]");
    if (!card || !row.contains(card)) return null;
    const box = card.getBoundingClientRect();
    if (event.clientY <= box.top + box.height / 2) return card.dataset.payloadId;
    return card.nextElementSibling?.matches(".visual-card[data-payload-id]")
      ? card.nextElementSibling.dataset.payloadId : null;
  };
  const onOver = (event) => {
    if (!dragging) return;
    const next = destination(event);
    reorderMarker?.classList.remove("visual-card--reorder-before");
    reorderMarker = null;
    if (target !== next) {
      target?.classList.remove("script-row--visual-drop-target");
      target = next;
      target?.classList.add("script-row--visual-drop-target");
    }
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    if (next.dataset.rowId === dragging.rowId) {
      const before = reorderBefore(event, next);
      reorderMarker = before ? [...next.querySelectorAll(".visual-card[data-payload-id]")]
        .find((card) => card.dataset.payloadId === before) : null;
      reorderMarker?.classList.add("visual-card--reorder-before");
    }
    event.dataTransfer.dropEffect = "move";
  };
  const onDrop = (event) => {
    if (!dragging) return;
    const next = destination(event);
    const from = dragging;
    const before = next && next.dataset.rowId === from.rowId ? reorderBefore(event, next) : null;
    clear();
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    const destinationId = next.dataset.rowId;
    if (destinationId === from.rowId) {
      // A drop back in its original position is cancellation, not a refused
      // model edit or a new Undo entry.
      if (!planVisualOnlyReorder(rowFor(from.rowId), from.payloadId, before)) return;
      const projectId = from.projectId;
      void queueCommand((latest) => {
        if (activeProjectId !== projectId) throw new Error("The project changed during the reorder.");
        const source = rowFor(from.rowId, latest);
        const plan = planVisualOnlyReorder(source, from.payloadId, before);
        if (!plan) throw new Error("The visual order was unchanged or is no longer available.");
        return plan;
      }, "Reorder visuals", { structural: true });
      return;
    }
    const freshSlotId = crypto.randomUUID();
    const replacementPayloadId = crypto.randomUUID();
    const intent = (latest) => {
      if (activeProjectId !== from.projectId) throw new Error("The script changed while dragging the visual.");
      const source = rowFor(from.rowId, latest);
      const dest = rowFor(destinationId, latest);
      if (source?.type !== from.sourceType || !dest ||
          dest.type !== "narration" && dest.type !== "visual_only") {
        throw new Error("The source or destination row changed during the drag.");
      }
      if (source.type === "narration") return {
        kind: "move_visual_to_row", blockId: from.rowId, slotId: from.slotId,
        destinationBlockId: destinationId,
        ...(dest.type === "visual_only" ? { expectedDestinationRowVersion: dest.version } : {}),
      };
      const ids = visualOnlyIds(source);
      if (!ids?.includes(from.payloadId)) throw new Error("The dragged picture is no longer in its source row.");
      const mapped = source.clearedNarration?.slots.some((item) => item.visualId === from.payloadId);
      return { kind: "move_wordless_visual", sourceRowId: from.rowId, payloadId: from.payloadId,
        destinationRowId: destinationId,
        ...(ids.length === 1 ? { replacementPayloadId } : {}),
        ...(!mapped && (dest.type === "narration" || dest.clearedNarration) ? { destinationSlotId: freshSlotId } : {}),
        ...(dest.type === "narration" ? { expectedDestinationSequenceVersion: dest.primaryVisualSequence?.version } : {}),
      };
    };
    void queueCommand(intent, "Move visual", { structural: true });
  };
  const onKey = (event) => {
    if (event.key !== "Escape" || !dragging) return;
    event.preventDefault();
    event.stopPropagation();
    clear();
    setSaveStatus("Visual move cancelled.");
  };
  root.addEventListener("dragstart", onStart);
  root.addEventListener("dragover", onOver);
  root.addEventListener("drop", onDrop);
  root.addEventListener("dragend", clear);
  root.addEventListener("keydown", onKey, true);
  return () => {
    clear();
    root.removeEventListener("dragstart", onStart);
    root.removeEventListener("dragover", onOver);
    root.removeEventListener("drop", onDrop);
    root.removeEventListener("dragend", clear);
    root.removeEventListener("keydown", onKey, true);
  };
}

function reselectOpener(state) {
  return [...element("script-rows").querySelectorAll("[data-reselect-open]")].find((button) =>
    button.dataset.reselectOpen === state.opener &&
    button.closest("[data-row-id]")?.dataset.rowId === state.rowId &&
    button.closest("[data-slot-id]")?.dataset.slotId === state.slotId);
}

function focusReselectOpener(state) {
  const opener = reselectOpener(state);
  // The distinct hover/focus action is not visible until its card receives
  // focus; focusing a CSS-hidden button directly does nothing in Chromium.
  opener?.closest(".visual-card")?.focus();
  opener?.focus();
}

function beginReselect(rowId, slotId, opener) {
  const row = editorDocument()?.activeDraft.blocks.find((item) => item.id === rowId);
  const projection = projectedPrimaryRow(rowId);
  if (row?.type !== "narration" || !projection?.renderable ||
      !projection.brackets?.some((bracket) => bracket.slotId === slotId)) {
    setSaveStatus("That visual's word range is not available to reselect.");
    return;
  }
  activeAttach = null;
  activeReselect = { rowId, slotId, opener, version: row.primaryVisualSequence?.version, text: row.text };
  renderEditor();
}

function cancelReselect() {
  if (!activeReselect) return;
  const state = activeReselect;
  activeReselect = null;
  renderEditor();
  focusReselectOpener(state);
  setSaveStatus("Reselect cancelled. The range didn’t change.");
}

async function commitReselect(command, label) {
  if (!activeReselect) return false;
  const state = activeReselect;
  const accepted = await queueVisualCommand((latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === state.rowId);
    if (row?.type !== "narration" || row.text !== state.text ||
        row.primaryVisualSequence?.version !== state.version) {
      throw new Error("The narration or visual range changed; start Reselect again.");
    }
    return command;
  }, label);
  if (accepted && activeReselect === state) {
    activeReselect = null;
    renderEditor();
    focusReselectOpener(state);
  }
  return accepted;
}

// A visual-command endpoint computes on a private document copy. Calling it
// for review has no save/Undo side effect, and the exact immutable snapshot
// is checked again before any later confirmation is committed.
async function previewReselect(command) {
  const state = activeReselect;
  const snapshot = editorDocument();
  const row = snapshot?.activeDraft.blocks.find((item) => item.id === state?.rowId);
  if (!state || row?.type !== "narration" || row.text !== state.text ||
      row.primaryVisualSequence?.version !== state.version) {
    throw new Error("The narration changed; start Reselect again.");
  }
  const result = await authoringVisualPost("visual-preview", {
    document: snapshot, command, expectedSequenceVersion: state.version,
  });
  if (activeReselect !== state || editorDocument() !== snapshot) {
    throw new Error("The narration changed while checking this range.");
  }
  const oldCards = projectedPrimaryRow(state.rowId)?.cards ?? [];
  const newCards = result.projection?.rows?.find((entry) => entry.blockId === state.rowId)?.cards ?? [];
  const returns = (cards) => cards.filter((card) => card.compact).map((card) => card.slotId);
  const beforeReturns = returns(oldCards);
  const afterReturns = returns(newCards);
  const removed = beforeReturns.filter((slotId) => !afterReturns.includes(slotId)).length;
  const created = afterReturns.filter((slotId) => !beforeReturns.includes(slotId)).length;
  const oc = (cards) => cards.filter((card) => card.kind === "on_camera" &&
    Number.isInteger(card.startTokenIndex) && Number.isInteger(card.endTokenIndexExclusive))
    .reduce((count, card) => count + card.endTokenIndexExclusive - card.startTokenIndex, 0);
  const beforeOc = oc(oldCards);
  const afterOc = oc(newCards);
  const parts = [];
  if (created) parts.push(`${created} return ${created === 1 ? "point is" : "points are"} added.`);
  if (removed) parts.push(`${removed} return ${removed === 1 ? "point is" : "points are"} removed.`);
  if (afterOc !== beforeOc) parts.push(`On Camera changes from ${beforeOc} to ${afterOc} spoken words.`);
  if (!parts.length) parts.push("The projected On Camera and return coverage remains coherent.");
  return parts.join(" ");
}

function scheduleRender(force = false) {
  renderRequested = true;
  forceRender ||= force === true;
  if (renderTimer) return;
  renderTimer = setTimeout(() => {
    renderTimer = undefined;
    if (!renderRequested || pendingExtras || editRefused || conflicted || commandsPending ||
        sortingTrial?.pending || sortingTrial?.busy || composingRows.size) return;
    const root = element("script-rows");
    const selection = document.getSelection();
    // Programmatic word selections do not necessarily focus the textbox, and
    // pointer-driven row controls need to survive a pending projection refresh.
    // Defer only decorative redraws; a committed structural edit still renders.
    if (!forceRender && (root.contains(document.activeElement) || root.matches(":hover") ||
        selection && !selection.isCollapsed && root.contains(selection.anchorNode) &&
        root.contains(selection.focusNode))) return;
    renderRequested = false;
    forceRender = false;
    renderEditor();
  }, 0);
}

element("script-rows").addEventListener("focusout", () => {
  if (renderRequested) setTimeout(() => scheduleRender(), 0);
});
element("script-rows").addEventListener("pointerleave", () => {
  if (renderRequested) scheduleRender();
});
document.addEventListener("selectionchange", () => {
  const target = selectedNarrationTarget();
  if (target && document.activeElement?.matches?.("[data-narration-editor]")) lastQuoteTarget = target;
  if (renderRequested) scheduleRender();
});

function saveDocument() {
  if (documentSaveTask) return documentSaveTask;
  if (!canEditAccount() || !project || pendingExtras || conflicted || (!documentDirty && !pendingDocument)) return;
  clearPreparedPrompter("Save your script before exporting.");
  if (!pendingDocument) {
    pendingDocument = { expectedRevision: documentRevision, clientMutationId: crypto.randomUUID(), document: scriptDocument };
    documentDirty = false;
  }
  documentSaving = true;
  setSaveStatus();
  documentSaveTask = api(`/${project.projectId}/document`, "PUT", pendingDocument).then((receipt) => {
    documentRevision = receipt.revision;
    documentDigest = receipt.digest;
    const last = undoStack.at(-1)?.durable;
    if (last && last.document === pendingDocument.document) {
      // Undoing a later text edit saved the exact earlier snapshot again.
      last.revision = receipt.revision;
      last.digest = receipt.digest;
    }
    void refreshMusicWarnings();
    pendingDocument = undefined;
    documentSaveFailure = undefined;
  }).catch((error) => {
    if (error instanceof ApiError && error.status === 409) {
      conflicted = true;
      documentSaveFailure = { message: "A newer script was saved elsewhere. Your unsaved changes are still here.", action: "conflict" };
    } else documentSaveFailure = { message: "Couldn’t save the script. Your unsaved changes are still here.", action: "retry" };
  }).finally(() => {
    documentSaving = false;
    documentSaveTask = null;
    setSaveStatus();
    if (!documentSaveFailure && documentDirty) void saveDocument();
  });
  return documentSaveTask;
}

async function waitForDocumentSave() {
  while (project && !documentSaveFailure && !conflicted && !pendingExtras) {
    if (!documentSaving && !documentDirty && !pendingDocument) return true;
    await saveDocument();
  }
  return false;
}

async function updateQuoteDisplayDefaultAfterSave({ projectId, rowId, overlayId, displayText }) {
  if (!await waitForDocumentSave() || activeProjectId !== projectId) return;
  const row = scriptDocument?.activeDraft?.blocks.find((item) => item.id === rowId);
  const use = row?.type === "narration" ? row.overlayEvents.find((item) => item.id === overlayId) : null;
  if (use?.quoteBox?.displayText !== displayText) return;
  try {
    const result = await authoringVisualPost("research-quote-display-default", {
      timelineProjectId: projectId, rowId, overlayId,
      expectedRevision: documentRevision, expectedDigest: documentDigest,
    });
    void researchPanel?.refresh?.();
    if (result.undo) return { projectId, rowId, overlayId, undo: result.undo };
  } catch {
    if (activeProjectId === projectId) setSaveStatus("Quote box saved. Its latest Library display text did not update.");
  }
}

async function applyBrowserCommand(document, command, splitProof, expectedSequenceVersion) {
  const response = await accountFetch("/authoring/command", {
    method: "POST", headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    body: JSON.stringify({ document, command, ...(splitProof ? { splitProof } : {}),
      ...(expectedSequenceVersion === undefined ? {} : { expectedSequenceVersion }),
      ...(revisionedRowCommandKinds.has(command.kind) ? { expectedRowEditRevision: document.rowEditRevision ?? 0 } : {}) }),
    signal: AbortSignal.timeout(12_000),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.diagnostics?.[0]?.message || "Edit could not be applied.");
  return result;
}

async function authoringVisualPost(path, body) {
  await connecting;
  try { sessionProof = localStorage.getItem(sessionKey) ?? sessionProof; } catch { /* Keep enrolled proof. */ }
  const response = await accountFetch(`/authoring/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12_000),
  });
  const result = response.status === 204 ? {} : await response.json();
  if (!response.ok || result.ok === false) {
    throw new Error(result.diagnostics?.[0]?.message || result.error || "Visual edit could not be applied.");
  }
  return result;
}

/** The browser never connects to Research's port or receives its bearer. */
export async function researchCatalogGet(researchProjectId, clipId) {
  const timelineId = activeProjectId;
  if (!uuid.test(timelineId ?? "") ||
      (researchProjectId !== undefined && !uuid.test(researchProjectId)) ||
      (clipId !== undefined && (!researchProjectId || !uuid.test(clipId)))) {
    throw new Error("Choose a current script and Research project.");
  }
  await connecting;
  const path = `/authoring/research/${timelineId}/projects` +
    (researchProjectId ? `/${researchProjectId}/clips${clipId ? `/${clipId}` : ""}` : "");
  const response = await accountFetch(path, {
    headers: { "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    signal: AbortSignal.timeout(12_000),
  });
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the footage list.");
  if (!response.ok) {
    const error = new Error("Research footage is unavailable or no longer authorized.");
    error.status = response.status;
    throw error;
  }
  const catalog = await response.json();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the footage list.");
  return catalog;
}

/** The browser sees only quotes exposed by the current authorized Research project. */
export async function researchQuoteCatalogGet(researchProjectId, offset = 0) {
  const timelineId = activeProjectId;
  if (!uuid.test(timelineId ?? "") || !uuid.test(researchProjectId ?? "") ||
      !Number.isSafeInteger(offset) || offset < 0) {
    throw new Error("Choose a current script and Research project.");
  }
  const response = await researchStillRequest(
    `/authoring/research/${timelineId}/projects/${researchProjectId}/quotes?offset=${offset}`);
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the quote list.");
  const page = await response.json();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the quote list.");
  return page;
}

class ResearchStillApiError extends Error {
  constructor(status, body) {
    super("Saved Research still request failed.");
    this.status = status;
    this.body = body;
  }
}

function researchStillRequestHeaders() {
  try { sessionProof = localStorage.getItem(sessionKey) ?? sessionProof; } catch { /* Keep the current proof. */ }
  return { "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof };
}

async function researchStillRequest(path) {
  await connecting;
  const response = await accountFetch(path, {
    headers: researchStillRequestHeaders(),
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) {
    throw new ResearchStillApiError(response.status, await response.json().catch(() => null));
  }
  return response;
}

/** The browser never connects to Research's port or receives its bearer. */
export async function researchStillCatalogGet(researchProjectId, offset = 0) {
  const timelineId = activeProjectId;
  if (!uuid.test(timelineId ?? "") || !uuid.test(researchProjectId ?? "") ||
      !Number.isSafeInteger(offset) || offset < 0) {
    throw new Error("Choose a current script and Research project.");
  }
  const path = `/authoring/research/${timelineId}/projects/${researchProjectId}/stills?offset=${offset}`;
  const response = await researchStillRequest(path);
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the still list.");
  const page = await response.json();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the still list.");
  return page;
}

/** Fetch a kept thumbnail through the same-origin authoring session. */
export async function researchStillThumbnailGet(researchProjectId, itemId, itemVersion) {
  const timelineId = activeProjectId;
  if (!uuid.test(timelineId ?? "") || !uuid.test(researchProjectId ?? "") ||
      !uuid.test(itemId ?? "") || !Number.isSafeInteger(itemVersion) || itemVersion < 1) {
    throw new Error("Choose a current script and saved Research still.");
  }
  const query = new URLSearchParams({ version: String(itemVersion) });
  const response = await researchStillRequest(
    `/authoring/research/${timelineId}/projects/${researchProjectId}/stills/${itemId}/thumbnail?${query}`);
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the still list.");
  const bytes = await response.arrayBuffer();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the still list.");
  return {
    mimeType: response.headers.get("content-type")?.split(";", 1)[0] || "application/octet-stream",
    bytes,
  };
}

/** Fetches a kept quote thumbnail through the same-origin Authoring session. */
export async function researchQuoteThumbnailGet(quote) {
  const timelineId = activeProjectId;
  const researchProjectId = quote?.researchProjectId;
  const itemId = quote?.itemId;
  const itemVersion = quote?.itemVersion;
  if (!uuid.test(timelineId ?? "") || !uuid.test(researchProjectId ?? "") ||
      !uuid.test(itemId ?? "") || !Number.isSafeInteger(itemVersion) || itemVersion < 1) {
    throw new Error("Choose a current script and saved Research quote.");
  }
  const query = new URLSearchParams({ version: String(itemVersion) });
  const response = await researchStillRequest(
    `/authoring/research/${timelineId}/projects/${researchProjectId}/quotes/${itemId}/thumbnail?${query}`);
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the quote list.");
  const bytes = await response.arrayBuffer();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the quote list.");
  return {
    mimeType: response.headers.get("content-type")?.split(";", 1)[0] || "application/octet-stream",
    bytes,
  };
}

/** Reads a placed quote picture through the host, which resolves the exact saved Research pin. */
export async function researchPlacedQuotePictureGet(payloadId) {
  const timelineId = activeProjectId;
  if (!uuid.test(timelineId ?? "") || !uuid.test(payloadId ?? "")) {
    throw new Error("Choose a current script and retained quote picture.");
  }
  if (!await waitForDocumentSave() || timelineId !== activeProjectId) {
    throw new Error("Save the quote picture before loading its thumbnail.");
  }
  const pin = (scriptDocument?.activeDraft?.blocks ?? []).flatMap((row) => row.type === "narration"
    ? (row.primaryVisualSequence?.slots ?? []).flatMap((slot) => slot.kind === "content" ? [slot.payload] : [])
    : []).find((payload) => payload.payloadId === payloadId)?.researchQuotePicture;
  if (!pin) throw new Error("The retained quote picture is no longer in the saved script.");
  const response = await researchStillRequest(`/authoring/research/${timelineId}/quote-pictures/${payloadId}`);
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the picture.");
  const bytes = await response.arrayBuffer();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the picture.");
  return { mimeType: response.headers.get("content-type")?.split(";", 1)[0] || pin.original.mimeType, bytes };
}

/** Resolves placement only after earlier typing has produced actual current token IDs. */
export function queueResearchClipInsert({ researchProjectId, clipId, clipVersion, placement }) {
  const projectId = activeProjectId;
  const toStash = placement?.kind === "stash";
  return queueCommand((latest) => ({ researchProjectId, clipId, clipVersion,
    placement: typeof placement === "function" ? placement(latest) : placement,
  }), toStash ? "Add footage to Stash" : "Add footage", {
    structural: true, research: true, stashFootage: toStash, expectedProjectId: projectId,
  });
}

/** Resolves selected words only after earlier typing has produced current IDs. */
export function queueResearchStillInsert({ researchProjectId, itemId, itemVersion, placement }) {
  const projectId = activeProjectId;
  return queueCommand((latest) => ({ researchProjectId, itemId, itemVersion,
    placement: typeof placement === "function" ? placement(latest) : placement,
  }), "Add still", { structural: true, researchStill: true, expectedProjectId: projectId });
}

export function queueResearchQuoteInsert({ quote, placement }) {
  const projectId = activeProjectId;
  return queueCommand((latest) => ({ researchProjectId: quote.researchProjectId,
    quoteId: quote.itemId, quoteVersion: quote.itemVersion,
    placement: typeof placement === "function" ? placement(latest) : placement,
  }), "Add quote", { structural: true, researchQuote: true, expectedProjectId: projectId });
}

export function queueResearchQuoteBoxEdit({ rowId, overlayId, expectedRowVersion,
  expectedOverlayVersion, edit }) {
  const projectId = activeProjectId;
  return queueCommand((latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    const overlay = row?.type === "narration" ? row.overlayEvents.find((item) => item.id === overlayId) : null;
    if (row?.type !== "narration" || row.version !== expectedRowVersion ||
        overlay?.version !== expectedOverlayVersion || !overlay.quoteBox) {
      throw new Error("This quote box changed. Reload the script before editing it.");
    }
    return { rowId, expectedRowVersion: row.version, overlayId,
      expectedOverlayVersion: overlay.version, edit };
  }, edit?.delete === true ? "Delete quote box" : "Edit quote box",
  { structural: true, researchQuoteBox: true, expectedProjectId: projectId });
}

function queueQuoteBoxRangeEdit({ rowId, overlayId, expectedRowVersion, expectedOverlayVersion }) {
  const projectId = activeProjectId;
  const target = selectedNarrationTarget() ?? lastQuoteTarget;
  if (!target?.selected || target.rowId !== rowId) {
    setSaveStatus("Select the words for this quote box range first.");
    return Promise.resolve(false);
  }
  return queueCommand((latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    const overlay = row?.type === "narration" ? row.overlayEvents.find((item) => item.id === overlayId) : null;
    if (row?.type !== "narration" || row.version !== expectedRowVersion || target.rowVersion !== row.version ||
        target.text !== row.text || overlay?.version !== expectedOverlayVersion || !overlay.quoteBox) {
      throw new Error("The quote box or selected narration changed. Select the words again.");
    }
    const selected = selectedSpokenWords(row, target.selection, true);
    if (!selected) throw new Error("Select current spoken words for the quote box range.");
    return { rowId, expectedRowVersion: row.version, overlayId, expectedOverlayVersion: overlay.version,
      edit: { range: { startTokenId: selected.startTokenId, endTokenId: selected.endTokenId } } };
  }, "Adjust quote box range", { structural: true, researchQuoteBox: true, expectedProjectId: projectId });
}

function openFootageForWords({ rowId, text, selection, seed, from }) {
  stashPanel.close(false);
  const selectedRow = scriptDocument?.activeDraft?.blocks.find((item) => item.id === rowId);
  const expectedRowVersion = selectedRow?.type === "narration" ? selectedRow.version : null;
  const expectedSequenceVersion = selectedRow?.type === "narration" ? selectedRow.primaryVisualSequence?.version : null;
  void researchPanel.open({ quick: true, seed, from, placement: (latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    if (row?.type !== "narration" || row.text !== text || row.version !== expectedRowVersion ||
        row.primaryVisualSequence?.version !== expectedSequenceVersion) {
      throw new Error("The selected narration changed. Choose the words again.");
    }
    const words = selectedSpokenWords(row, selection, true);
    if (!words) throw new Error("The selected spoken words are no longer available.");
    return { kind: "selected_words", rowId, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence.version,
      startTokenId: words.startTokenId, endTokenId: words.endTokenId };
  } });
}

function openStashClipPicker({ sectionId = null, noteRowId = null, from }) {
  const projectId = activeProjectId;
  const expected = editorDocument();
  const note = noteRowId && (expected.stash ?? []).flatMap((bundle) => bundle.rows)
    .find((row) => row.id === noteRowId);
  const placement = Object.assign((latest) => {
    if (latest !== expected) throw new Error("The script or Stash changed. Choose the clip again.");
    return { kind: "stash", sectionId, noteRowId, replace: Boolean(note?.attachedFootage) };
  }, { kind: "stash" });
  stashPanel.close(false);
  void researchPanel.open({ quick: true, placement, onClose: () => {
    if (projectId !== activeProjectId) return;
    stashPanel.open();
    if (from?.isConnected) from.focus();
  } });
}

function openLibraryAtCaret(snapshot, from) {
  stashPanel.close(false);
  void researchPanel.open({ quick: true, from, placement: quotePlacementFromSelection(snapshot) });
}

function selectedNarrationTarget() {
  const selection = document.getSelection();
  if (!selection?.rangeCount || !selection.anchorNode || !selection.focusNode) return null;
  const elementFor = (node) => node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  const editor = elementFor(selection.anchorNode)?.closest?.("[data-narration-editor]");
  if (!editor || !editor.contains(selection.focusNode)) return null;
  const rowId = editor.closest("[data-row-kind='narration']")?.dataset.rowId;
  const row = scriptDocument?.activeDraft?.blocks.find((item) => item.id === rowId);
  if (row?.type !== "narration" || editor.textContent !== row.text || composingRows.has(row.id)) return null;
  const range = selection.getRangeAt(0);
  const offsetAt = (node, offset) => {
    try {
      const prefix = document.createRange();
      prefix.selectNodeContents(editor);
      prefix.setEnd(node, offset);
      return prefix.toString().length;
    } catch { return null; }
  };
  const start = offsetAt(range.startContainer, range.startOffset);
  const end = offsetAt(range.endContainer, range.endOffset);
  if (start === null || end === null) return null;
  const selectedTokens = selection.isCollapsed ? [] : (row.tokens ?? []).filter((token) => token?.spoken !== false &&
    Number.isSafeInteger(token.startOffset) && Number.isSafeInteger(token.endOffset) &&
    token.endOffset > start && token.startOffset < end);
  if (!selection.isCollapsed && !selectedTokens.length) return null;
  return { rowId, text: row.text, rowVersion: row.version,
    sequenceVersion: row.primaryVisualSequence?.version,
    selection: { start, end }, selected: !selection.isCollapsed,
    rects: selectedTokens.flatMap((token) => narrationTokenRects(editor, token)) };
}

function textPointAtOffset(root, wanted) {
  const walker = root.ownerDocument.createTreeWalker(root, root.ownerDocument.defaultView.NodeFilter.SHOW_TEXT);
  let node;
  let cursor = 0;
  let last = null;
  while ((node = walker.nextNode())) {
    last = node;
    const end = cursor + node.nodeValue.length;
    if (wanted <= end) return { node, offset: Math.max(0, wanted - cursor) };
    cursor = end;
  }
  return last ? { node: last, offset: last.nodeValue.length } : { node: root, offset: 0 };
}

function narrationTokenRects(editor, token) {
  try {
    const range = editor.ownerDocument.createRange();
    const start = textPointAtOffset(editor, token.startOffset);
    const end = textPointAtOffset(editor, token.endOffset);
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, end.offset);
    return [...range.getClientRects()].filter((rect) => rect.width && rect.height).map((rect) => ({
      left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
    }));
  } catch { return []; }
}

function pointInQuoteRects(rects, x, y) {
  return rects?.some((rect) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) ?? false;
}

function narrationTokenAtPoint(row, editor, x, y) {
  return (row.tokens ?? []).find((token) => token?.spoken !== false && typeof token?.id === "string" &&
    token.id && pointInQuoteRects(narrationTokenRects(editor, token), x, y)) ?? null;
}

function quoteInsertBoundary(row, offset) {
  const words = (row.tokens ?? []).filter((token) => token?.spoken !== false &&
    typeof token?.id === "string" && token.id && Number.isSafeInteger(token.startOffset) &&
    Number.isSafeInteger(token.endOffset));
  if (!words.length) return null;
  const boundaries = words.flatMap((token, index) => [
    { offset: token.startOffset, beforeTokenId: token.id },
    { offset: token.endOffset, beforeTokenId: words[index + 1]?.id ?? null },
  ]);
  return boundaries.reduce((best, candidate) =>
    Math.abs(candidate.offset - offset) < Math.abs(best.offset - offset) ? candidate : best).beforeTokenId;
}

function quotePlacementFromSelection(snapshot) {
  return (latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === snapshot.rowId);
    if (row?.type !== "narration" || row.text !== snapshot.text || row.version !== snapshot.rowVersion ||
        row.primaryVisualSequence?.version !== snapshot.sequenceVersion ||
        !Number.isSafeInteger(row.primaryVisualSequence?.version)) {
      throw new Error("The script changed before the quote was placed. Choose the target again.");
    }
    const base = { rowId: row.id, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence.version };
    if (snapshot.selected) {
      const words = selectedSpokenWords(row, snapshot.selection, true);
      if (!words) throw new Error("The selected spoken words are no longer available.");
      return { kind: "selected_words", ...base,
        startTokenId: words.startTokenId, endTokenId: words.endTokenId };
    }
    return { kind: "insert", ...base, beforeTokenId: quoteInsertBoundary(row, snapshot.selection.start) };
  };
}

function quoteRowEndPlacement(rowId) {
  return (latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    if (row?.type !== "narration" || !Number.isSafeInteger(row.primaryVisualSequence?.version)) {
      throw new Error("The destination narration changed before the quote was placed.");
    }
    return { kind: "insert", rowId: row.id, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence.version, beforeTokenId: null };
  };
}

function quoteGapPlacement(gap) {
  return (latest) => {
    const current = rowGaps(latest.activeDraft.blocks).find((item) =>
      item.sectionId === gap.sectionId && item.afterRowId === gap.afterRowId && item.beforeRowId === gap.beforeRowId);
    if (!current) throw new Error("The script gap moved before the quote was placed.");
    return { kind: "gap", destination: current };
  };
}

function placeLibraryQuote(quote, destination) {
  const target = destination ? null : selectedNarrationTarget() ?? lastQuoteTarget;
  if (!destination && !target) return null;
  const placement = destination?.kind === "row-end" ? quoteRowEndPlacement(destination.rowId) :
    destination?.kind === "gap" ? quoteGapPlacement(destination.destination) :
      target ? quotePlacementFromSelection(target) : null;
  if (!placement) return null;
  lastQuoteTarget = null;
  return queueResearchQuoteInsert({ quote, placement });
}

function openStillForWords({ rowId, text, selection, from }) {
  stashPanel.close(false);
  void researchStillPanel.open({ from, placement: (latest) => {
    const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
    if (row?.type !== "narration" || row.text !== text) {
      throw new Error("The selected narration changed. Choose the words again.");
    }
    const words = selectedSpokenWords(row, selection, true);
    if (!words) throw new Error("The selected spoken words are no longer available.");
    return { kind: "selected_words", rowId, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence.version,
      startTokenId: words.startTokenId, endTokenId: words.endTokenId };
  } });
}

function availableGaps() {
  const blocks = scriptDocument?.activeDraft?.blocks ?? [];
  return rowGaps(blocks).map((destination, index) => ({
    destination, label: `Gap ${index + 1} · ${destination.afterRowId ? "after row" : "section start"}`,
  }));
}

function availableNarrationRows() {
  return (scriptDocument?.activeDraft?.blocks ?? []).filter((row) => row.type === "narration")
    .map((row, index) => ({ rowId: row.id, label: `Row ${index + 1}: ${(row.text || "Blank narration").slice(0, 45)}` }));
}

function caretOffsetAtPoint(editor, x, y) {
  const ownerDocument = editor.ownerDocument;
  let range = ownerDocument.caretRangeFromPoint?.(x, y) ?? null;
  if (!range && ownerDocument.caretPositionFromPoint) {
    const point = ownerDocument.caretPositionFromPoint(x, y);
    if (point) {
      range = ownerDocument.createRange();
      range.setStart(point.offsetNode, point.offset);
      range.collapse(true);
    }
  }
  if (!range || !editor.contains(range.startContainer)) return null;
  try {
    const prefix = ownerDocument.createRange();
    prefix.selectNodeContents(editor);
    prefix.setEnd(range.startContainer, range.startOffset);
    return prefix.toString().length;
  } catch { return null; }
}

function mountResearchDragging(root) {
  let target = null;
  let cue = null;
  let quoteSelection = null;
  const ownerDocument = root.ownerDocument;
  const clear = () => {
    target?.classList.remove("script-row--footage-target", "row-divider--footage-target");
    cue?.remove();
    target = null;
    cue = null;
  };
  const destinationNode = (event) => event.target.closest?.("[data-row-gap], .script-row[data-row-kind='narration']");
  const draggingFootage = (event) => [...(event.dataTransfer?.types ?? [])].includes("application/x-vera-research-clip");
  const draggingQuote = (event) => [...(event.dataTransfer?.types ?? [])].includes("application/x-vera-research-quote");
  const quoteDestination = (event) => {
    const gap = event.target.closest?.("[data-row-gap]");
    if (gap) return { target: gap, mode: "insert", placement: quoteGapPlacement({
      sectionId: gap.dataset.sectionId || null,
      afterRowId: gap.dataset.afterRowId || null,
      beforeRowId: gap.dataset.beforeRowId || null,
    }) };
    const rowNode = event.target.closest?.(".script-row[data-row-kind='narration']");
    if (!rowNode) return null;
    if (quoteSelection?.rowId === rowNode.dataset.rowId && quoteSelection.selected &&
        pointInQuoteRects(quoteSelection.rects, event.clientX, event.clientY)) {
      return { target: rowNode, mode: "attach", placement: quotePlacementFromSelection(quoteSelection) };
    }
    const editor = rowNode.querySelector("[data-narration-editor]");
    const row = scriptDocument?.activeDraft?.blocks.find((item) => item.id === rowNode.dataset.rowId);
    if (!editor || !row || row.type !== "narration") return null;
    const token = narrationTokenAtPoint(row, editor, event.clientX, event.clientY);
    if (token) return { target: rowNode, mode: "attach", placement: quotePlacementFromSelection({
      rowId: row.id, text: row.text, rowVersion: row.version,
      sequenceVersion: row.primaryVisualSequence?.version,
      selection: { start: token.startOffset, end: token.endOffset }, selected: true,
    }) };
    const offset = caretOffsetAtPoint(editor, event.clientX, event.clientY);
    if (offset === null) return null;
    return { target: rowNode, mode: "insert", placement: quotePlacementFromSelection({
      rowId: row.id, text: row.text, rowVersion: row.version,
      sequenceVersion: row.primaryVisualSequence?.version,
      selection: { start: offset, end: offset }, selected: false,
    }) };
  };
  const showCue = (next, mode) => {
    clear();
    target = next;
    target.classList.add(target.matches("[data-row-gap]") ? "row-divider--footage-target" : "script-row--footage-target");
    cue = ownerDocument.createElement("span");
    cue.className = "research-quote-drop-cue";
    cue.dataset.quoteDropMode = mode;
    cue.textContent = mode === "attach" ? "Attach quote · narration unchanged" :
      target.matches("[data-row-gap]") ? "Insert quote as new row" : "Insert quote";
    cue.setAttribute("role", "status");
    cue.setAttribute("aria-live", "polite");
    (target.matches("[data-row-gap]") ? target : target.querySelector(".narration-cell"))?.append(cue);
  };
  const captureQuoteSelection = (event) => {
    quoteSelection = draggingQuote(event) ? selectedNarrationTarget() ?? lastQuoteTarget : null;
  };
  const rememberQuoteTarget = (event) => {
    const targetNode = event.target?.nodeType === Node.ELEMENT_NODE ? event.target : event.target?.parentElement;
    if (targetNode?.closest?.(".visual-card__quote-editor, [data-quote-box-range-edit]")) return;
    const target = targetNode?.closest?.("#open-footage, #footage-panel, [data-narration-editor]");
    if (target?.matches("#open-footage")) {
      lastQuoteTarget = selectedNarrationTarget();
    } else if (target?.matches("#footage-panel")) {
      lastQuoteTarget = targetNode.closest("[data-quote-place-id]")
        ? selectedNarrationTarget() ?? lastQuoteTarget : null;
    } else lastQuoteTarget = null;
  };
  const endDrag = () => { clear(); quoteSelection = null; };
  const over = (event) => {
    if (draggingQuote(event)) {
      const next = quoteDestination(event);
      if (!next) { clear(); return; }
      event.preventDefault();
      event.stopPropagation();
      showCue(next.target, next.mode);
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
      return;
    }
    if (!draggingFootage(event)) return;
    const next = destinationNode(event);
    clear();
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    target = next;
    target.classList.add(next.matches("[data-row-gap]") ? "row-divider--footage-target" : "script-row--footage-target");
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  };
  const drop = (event) => {
    if (draggingQuote(event)) {
      const next = quoteDestination(event);
      const quote = researchPanel.dropQuote(event.dataTransfer?.getData("application/x-vera-research-quote"));
      clear();
      quoteSelection = null;
      if (!next || !quote) return;
      event.preventDefault();
      event.stopPropagation();
      const currentProject = activeProjectId;
      void queueResearchQuoteInsert({ quote, placement: (latest) => {
        if (currentProject !== activeProjectId) throw new Error("The open script changed during the drag.");
        return next.placement(latest);
      } }).then((success) => { if (success) researchPanel.update(); });
      return;
    }
    if (!draggingFootage(event)) return;
    const next = destinationNode(event);
    const clip = researchPanel.dropClip(event.dataTransfer?.getData("application/x-vera-research-clip"));
    clear();
    if (!next || !clip) return;
    event.preventDefault();
    event.stopPropagation();
    const currentProject = activeProjectId;
    const targetRowId = next.dataset.rowId;
    const expected = targetRowId ? scriptDocument.activeDraft.blocks.find((row) => row.id === targetRowId) : null;
    const gap = targetRowId ? null : {
      sectionId: next.dataset.sectionId || null,
      afterRowId: next.dataset.afterRowId || null, beforeRowId: next.dataset.beforeRowId || null,
    };
    void queueResearchClipInsert({ researchProjectId: clip.projectId, clipId: clip.id, clipVersion: clip.version,
      placement: (latest) => {
        if (currentProject !== activeProjectId) throw new Error("The open script changed during the drag.");
        if (gap) {
          if (!rowGaps(latest.activeDraft.blocks).some((candidate) =>
            candidate.sectionId === gap.sectionId && candidate.afterRowId === gap.afterRowId &&
            candidate.beforeRowId === gap.beforeRowId)) throw new Error("The script gap moved during the drag.");
          return { kind: "gap", destination: gap };
        }
        const row = latest.activeDraft.blocks.find((item) => item.id === targetRowId);
        if (row?.type !== "narration" || row.version !== expected?.version) {
          throw new Error("The destination narration changed during the drag.");
        }
        return { kind: "unattached", rowId: row.id, expectedRowVersion: row.version,
          expectedSequenceVersion: row.primaryVisualSequence.version };
      },
    }).then((success) => { if (success) researchPanel.update(); });
  };
  ownerDocument.addEventListener("pointerdown", rememberQuoteTarget, true);
  ownerDocument.addEventListener("dragstart", captureQuoteSelection);
  ownerDocument.addEventListener("dragend", endDrag);
  root.addEventListener("dragover", over, true);
  root.addEventListener("drop", drop, true);
  root.addEventListener("dragend", clear, true);
  return () => {
    clear();
    ownerDocument.removeEventListener("pointerdown", rememberQuoteTarget, true);
    ownerDocument.removeEventListener("dragstart", captureQuoteSelection);
    ownerDocument.removeEventListener("dragend", endDrag);
    root.removeEventListener("dragover", over, true);
    root.removeEventListener("drop", drop, true);
    root.removeEventListener("dragend", clear, true);
  };
}

// Projection is derived, never saved. In-flight responses are tied to the
// exact object snapshot and generation; an older network response cannot
// redraw brackets or On Camera after an edit, Undo or project switch.
function invalidateProjection(refresh = true) {
  ++projectionGeneration;
  const snapshot = scriptDocument;
  visualProjection = null;
  clearTimeout(projectionTimer);
  if (!snapshot || !refresh) return;
  projectionTimer = setTimeout(() => {
    projectionTimer = undefined;
    void refreshProjection(snapshot, Boolean(activeReselect));
  }, 30);
}

export function projectedPrimaryRow(rowId) {
  return editorProjection()?.rows?.find((row) => row.blockId === rowId) ?? null;
}

// A UI intent can be a function: resolve it *inside* the serialized queue,
// after any typing or paragraph action has returned real current token IDs.
export function queueVisualCommand(intent, label) {
  return queueCommand(intent, label, { visual: true, structural: true });
}

async function fetchProjection(documentModel) {
  const result = await authoringVisualPost("projection", { document: documentModel });
  if (!Array.isArray(result.projection?.rows)) throw new Error("Visual cues were not returned by the editor.");
  return result.projection;
}

function changedCueIds(before, after) {
  const previous = new Map();
  for (const row of before?.rows ?? []) {
    row.cards.forEach((card, index) => {
      if (card.kind !== "on_camera" && !card.compact) {
        previous.set(`${row.blockId}:${card.slotId}`, { index, start: card.startTokenIndex });
        previous.set(`slot:${card.slotId}`, { rowId: row.blockId });
      }
    });
  }
  const moved = new Set();
  for (const row of after.rows) {
    row.cards.forEach((card, index) => {
      const prior = previous.get(`${row.blockId}:${card.slotId}`);
      const former = previous.get(`slot:${card.slotId}`);
      if (prior && (prior.index !== index || prior.start !== card.startTokenIndex) ||
          former && former.rowId !== row.blockId) moved.add(card.slotId);
    });
  }
  return moved;
}

async function refreshProjection(documentModel, force, previousProjection = visualProjection) {
  const generation = projectionGeneration;
  try {
    const next = await fetchProjection(documentModel);
    // Typing and Undo can overtake a projection request. Never display a
    // read response for an older document (or an earlier open project).
    if (scriptDocument !== documentModel || generation !== projectionGeneration) return;
    flashVisualIds = changedCueIds(previousProjection, next);
    visualProjection = next;
  } catch (error) {
    if (scriptDocument !== documentModel || generation !== projectionGeneration) return;
    visualProjection = null;
    setSaveStatus(error.message || "Couldn’t refresh visual cues. Reload to try again.");
  }
  scheduleRender(force);
}

// Every intermediate document is private to this queued operation: a refusal
// or failed request discards *all* steps without a save or an Undo snapshot.
async function applyPlainPaste(document, intent, apply = applyBrowserCommand) {
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
    const edited = await apply(working, {
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
      const result = await apply(working, {
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
    const withoutBreak = await apply(working, {
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
    const created = await apply(working, {
      kind: "create_row", row: createBlankNarrationRow({ id: newRowId }), destination: gap,
    });
    working = created.document;
    if (!above) { currentRowId = newRowId; caret = 0; }
  }
  return { document: working, focusAfter: { rowId: currentRowId, offset: Math.max(0, caret) } };
}

// Sorting is a separate, in-memory working view of a pinned saved head.
export function currentSortingTrial() {
  return sortingTrial && {
    document: sortingTrial.document, movedRowIds: [...sortingTrial.movedRowIds],
    busy: sortingTrial.busy,
  };
}

export function beginSortingTrial() {
  if (!prompterReady()) return false;
  sortingTrial = {
    projectId: activeProjectId, revision: documentRevision, digest: documentDigest,
    baseline: scriptDocument, document: scriptDocument, projection: visualProjection,
    operations: [], history: [], movedRowIds: [], expanded: new Set(), busy: false, pending: 0, queue: Promise.resolve(),
  };
  typingGroup = null;
  clearPreparedPrompter();
  return true;
}

function sortingBaselineCurrent(trial) {
  return sortingTrial === trial && activeProjectId === trial.projectId &&
    scriptDocument === trial.baseline && documentRevision === trial.revision &&
    documentDigest === trial.digest && !conflicted && !editRefused &&
    !documentSaving && !documentDirty && !pendingDocument && !commandsPending;
}

async function sortingRequest(trial, operations, action, outcome) {
  try {
    const result = await api(`/${trial.projectId}/sorting-trial`, "POST", {
      expectedRevision: trial.revision, expectedDigest: trial.digest, operations, action,
      ...(outcome ? { outcome } : {}),
    });
    if (!result.ok) throw new Error(result.diagnostics?.[0]?.message || "Sorting could not be applied.");
    return result;
  } catch (error) {
    throw new Error(error.body?.diagnostics?.[0]?.message || error.message || "Sorting could not be applied.");
  }
}

async function updateSortingDocument(trial, operations, result) {
  if (!sortingBaselineCurrent(trial)) return false;
  const projection = result.projection ?? await fetchProjection(result.document).catch(() => null);
  if (!sortingBaselineCurrent(trial)) return false;
  trial.projection = projection;
  trial.operations = operations;
  trial.document = result.document;
  trial.movedRowIds = result.movedRowIds;
  return true;
}

function queueSortingCommand(command, label, options) {
  if (!canEditAccount()) return Promise.resolve(false);
  const trial = sortingTrial;
  if (editRefused || trial.preview || trial.busy || trial.acceptance || options.structural && composingRows.size) return Promise.resolve(false);
  trial.pending++;
  updateSortingControls();
  trial.queue = trial.queue.then(async () => {
    if (!sortingBaselineCurrent(trial)) return false;
    const before = trial.document;
    if (options.prepareSplitInput) {
      const next = options.prepareSplitInput(before);
      if (!next) return true;
      ({ command, label, options } = next);
    }
    if (options.expectedRow) {
      const expected = options.expectedRow;
      const row = before.activeDraft.blocks.find((block) => block.id === expected.id);
      const matches = row?.type === "narration" && row.text === expected.text &&
        Boolean(row.plainDirection) === expected.plainDirection;
      const cleared = row?.type === "visual_only" && row.clearedNarration &&
        expected.text === "" && !expected.plainDirection;
      if (!matches && !cleared) throw new Error("The row changed while you were typing.");
    }
    const resolved = typeof command === "function" ? command(before) : command;
    const operations = [...trial.operations];
    const apply = (operation) => {
      operations.push(operation);
      return sortingRequest(trial, operations, "preview");
    };
    let latest;
    if (options.research && options.stashFootage) {
      const prepared = await authoringVisualPost("research-insert", {
        timelineProjectId: trial.projectId, document: before,
        expectedDocumentRevision: before.rowEditRevision ?? 0, ...resolved,
      });
      if (!sortingBaselineCurrent(trial)) return false;
      if (!Array.isArray(prepared.rowCommands) || prepared.rowCommands.length === 0) {
        throw new Error("The authorized footage is unavailable.");
      }
      const additions = prepared.rowCommands.map((item) => ({ kind: "command", command: item }));
      latest = await apply(additions.length === 1 ? additions[0] : { kind: "batch", operations: additions });
    } else if (options.research || options.researchStill) {
      throw new Error("Choose existing Stash material while Sorting.");
    } else if (options.paste) {
      const pasted = await applyPlainPaste(before, resolved, async (_model, part) => {
        latest = await apply({ kind: "command", command: part });
        return latest;
      });
      if (pasted.document !== before) structuralFocus = pasted.focusAfter;
    } else {
      const operation = options.visual ? {
        kind: "visual", command: resolved,
        expectedSequenceVersion: before.activeDraft.blocks.find((row) => row.id === resolved.blockId)?.primaryVisualSequence?.version,
      } : { kind: "command", command: resolved };
      latest = await apply(operation);
    }
    if (latest) {
      const originalLength = trial.operations.length;
      if (!await updateSortingDocument(trial, operations, latest)) return false;
      trial.history.push(originalLength);
    }
    if (options.focusAfter) structuralFocus = options.focusAfter;
    if (options.cardFocus) cardFocus = options.cardFocus;
    options.onSplitApplied?.(trial.document, structuralFocus);
    sortingStatus(label);
    if (!options.renderAfterAction) scheduleRender(options.structural || options.paste || Boolean(options.onSplitApplied));
    return true;
  }).catch((error) => {
    if (sortingTrial === trial) {
      sortingStatus(error.message);
      if (options.expectedRow && (!options.structural || options.paste)) {
        editRefused = true;
        refusedMessage = `${error.message} Your unsaved text is still here. Copy it or discard the text to continue.`;
        element("discard-edit").hidden = false;
        setSaveStatus();
      }
    }
    options.onSplitRefused?.(error);
    return false;
  }).finally(() => {
    trial.pending--;
    if (sortingTrial === trial) {
      if (editRefused) element("discard-edit").disabled = trial.pending > 0;
      updateSortingControls();
      stashPanel?.update();
      if (renderRequested) scheduleRender();
    }
  });
  return trial.queue;
}

export function moveSortingTrial(command) {
  return command?.kind === "move_rows" ? queueSortingCommand(command, "Move rows", { structural: true, renderAfterAction: true }) : Promise.resolve(false);
}

export function discardSortingTrial() {
  if (!sortingTrial) return false;
  sortingTrial = null;
  updatePrompterControls();
  return true;
}

export async function acceptSortingTrial(outcome = "all") {
  if (!canEditAccount()) return false;
  const trial = sortingTrial;
  if (!trial || trial.busy || trial.pending || !sortingBaselineCurrent(trial)) return false;
  trial.busy = true;
  try {
    if (!trial.acceptance) {
      const result = await sortingRequest(trial, trial.operations, "accept", outcome);
      if (!sortingBaselineCurrent(trial)) return false;
      if (!result.changed) { sortingTrial = null; return true; }
      trial.acceptance = { body: { expectedRevision: trial.revision, clientMutationId: crypto.randomUUID(),
        document: result.document }, receipt: null };
    }
    // Keep the original CAS basis and mutation ID if the response is lost.
    const acceptance = trial.acceptance;
    const path = `/${trial.projectId}/document`;
    if (!acceptance.receipt) {
      const receipt = await api(path, "PUT", acceptance.body);
      if (receipt.projectId !== trial.projectId || receipt.clientMutationId !== acceptance.body.clientMutationId ||
          receipt.revision !== trial.revision + 1 || !savedDigestPattern.test(receipt.digest)) {
        throw new Error("The save receipt could not be verified.");
      }
      acceptance.receipt = receipt;
    }
    const saved = await api(path);
    if (!sortingBaselineCurrent(trial)) return false;
    if (saved.revision !== acceptance.receipt.revision || saved.digest !== acceptance.receipt.digest ||
        saved.document?.id !== trial.baseline.id || saved.document?.projectId !== trial.projectId) {
      trial.acceptance = null;
      throw new Error("The saved script changed after acceptance. Reload to see the latest script.");
    }
    undoStack.push({ document: scriptDocument, label: "Sort rows",
      durable: { revision: saved.revision, digest: saved.digest, document: saved.document },
      sortingBasis: { revision: trial.revision, digest: trial.digest } });
    scriptDocument = saved.document;
    documentRevision = saved.revision;
    documentDigest = saved.digest;
    sortingTrial = null;
    lastSplit = null;
    const previousProjection = visualProjection;
    invalidateProjection(false);
    updateUndo();
    setSaveStatus("Saved");
    void refreshMusicWarnings();
    void refreshProjection(scriptDocument, true, previousProjection);
    return true;
  } catch (error) {
    if (!trial.acceptance) throw error;
    if (!trial.acceptance.receipt && error.status >= 400 && error.status < 500) {
      trial.acceptance = null;
      if (error.status === 409) throw new Error("The saved script changed. Discard this trial and reload before sorting again.");
      throw new Error("Saving was refused. Your Sorting changes are still pending.");
    }
    throw new Error("The save could not be confirmed. Retry acceptance to check the same save.");
  } finally { trial.busy = false; }
}

// Sorting and preview share the script renderer with the saved Draft.
function setSortingMode(active) {
  const preview = active && sortingTrial.preview;
  authoring.classList.toggle("sorting-mode", active);
  element("sorting-view").hidden = !active;
  authoring.classList.toggle("sorting-edit", active && !preview);
  projectTitle.readOnly = active;
  if (!active) {
    stashScriptDrag = null;
    element("script-rows").inert = false;
  }
  for (const id of ["undo", "open-footage", "open-prompter"]) element(id).hidden = active;
  element("undo").parentElement.querySelector(".undo-menu").hidden = active;
  const toggle = element("open-sorting");
  toggle.textContent = preview ? "Return to Sorting" : active ? "← Back to script" : "Sort rows";
  toggle.setAttribute("aria-expanded", String(active));
  if (!active) {
    showSortingChoices(false);
    element("sorting-accept").textContent = "Accept";
  }
}

function leaveSorting() {
  if (!sortingTrial || sortingTrial.busy || sortingTrial.pending || sortingTrial.acceptance || composingRows.size) return;
  if ((sortingTrial.operations.length || editRefused) &&
      !window.confirm("Discard this Sorting trial and return to the script?")) return;
  finishSorting(false);
}

function finishSorting(accepted) {
  if (!accepted && (sortingTrial?.acceptance || !discardSortingTrial())) return;
  if (editRefused) {
    editRefused = false;
    refusedMessage = "";
    element("discard-edit").hidden = true;
    setSaveStatus();
  }
  setSortingMode(false);
  renderEditor();
  stashPanel?.update();
  updatePrompterControls();
  // Accept may start a save, so focus the script heading while the toggle is disabled.
  (element("open-sorting").disabled ? element("script-title") : element("open-sorting")).focus();
}

function sortingStatus(message) {
  element("sorting-status").textContent = message;
}

function sortingButton(label, text) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  button.setAttribute("aria-label", label);
  return button;
}

function updateSortingControls() {
  if (!sortingTrial) return;
  const { busy, pending, preview, operations } = sortingTrial;
  const waiting = busy || pending > 0 || composingRows.size > 0;
  element("script-rows").inert = Boolean(busy || sortingTrial.acceptance);
  element("open-sorting").disabled = waiting || editRefused;
  element("sorting-accept").disabled = waiting || editRefused || !operations.length;
  element("sorting-accept").textContent = sortingTrial.acceptance ? "Retry acceptance" : "Accept";
  element("sorting-outcomes").disabled = waiting || editRefused || !operations.length || !!sortingTrial.acceptance;
  if (element("sorting-outcomes").disabled) showSortingChoices(false);
  element("sorting-discard").disabled = waiting || !!sortingTrial.acceptance;
  element("sorting-undo").disabled = waiting || editRefused || preview || !operations.length || !!sortingTrial.acceptance;
}

function decorateSortingRows(root, model) {
  const trial = sortingTrial;
  const gaps = rowGaps(model.activeDraft.blocks);
  const rows = new Map(model.activeDraft.blocks.map((row) => [row.id, row]));
  const headings = [...root.querySelectorAll("[data-section-id].script-section-heading")];
  headings.forEach((heading, index) => {
    const sectionId = heading.dataset.sectionId;
    const menu = heading.querySelector("[data-section-action-menu]");
    const move = (label, after, before) => {
      const button = sortingButton(label, label);
      button.setAttribute("role", "menuitem");
      button.addEventListener("click", () => {
        menu.hidden = true;
        const destination = { afterSectionId: after?.dataset.sectionId ?? null,
          beforeSectionId: before?.dataset.sectionId ?? null };
        void queueSortingCommand({ kind: "move_section", sectionId, destination }, label, { structural: true });
      });
      menu.append(button);
    };
    if (index > 0) move("Move section up", headings[index - 2], headings[index - 1]);
    if (index + 1 < headings.length) move("Move section down", headings[index + 1], headings[index + 2]);
  });
  for (const item of root.querySelectorAll(".script-row")) {
    const row = rows.get(item.dataset.rowId);
    item.dataset.sortingRowId = row.id;
    const expanded = trial.expanded.has(row.id);
    item.classList.toggle("sorting-row--collapsed", !expanded);
    let cleanConnectors;
    const mountConnectors = () => {
      if (row.type !== "narration" || cleanConnectors) return;
      cleanConnectors = mountVisualConnectors(item, row);
      narrationCleanup.push(cleanConnectors);
    };
    item.classList.toggle("sorting-row--moved", trial.movedRowIds.includes(row.id));
    const controls = document.createElement("div");
    controls.className = "sorting-row-controls";
    const label = rowLabel(row);
    const expand = sortingButton(`${expanded ? "Collapse" : "Expand"} ${label}`, expanded ? "▾" : "▸");
    expand.setAttribute("aria-expanded", String(expanded));
    expand.addEventListener("click", () => {
      if (trial.pending || trial.busy) return;
      if (trial.expanded.delete(row.id)) {
        item.classList.add("sorting-row--collapsed");
        expand.textContent = "▸";
      } else {
        trial.expanded.add(row.id);
        item.classList.remove("sorting-row--collapsed");
        mountConnectors();
        expand.textContent = "▾";
      }
      expand.setAttribute("aria-expanded", String(trial.expanded.has(row.id)));
      expand.setAttribute("aria-label", `${trial.expanded.has(row.id) ? "Collapse" : "Expand"} ${label}`);
    });
    const summary = document.createElement("span");
    summary.textContent = label;
    controls.append(expand, summary);
    const before = gaps.findIndex((gap) => gap.beforeRowId === row.id);
    const after = gaps.findIndex((gap) => gap.afterRowId === row.id);
    for (const [step, destination] of [["up", gaps[before - 1]], ["down", gaps[after + 1]]]) {
      const button = sortingButton(`Move ${label} ${step}`, step === "up" ? "↑" : "↓");
      button.dataset.sortingMove = step;
      button.disabled = !destination;
      button.addEventListener("click", () => {
        if (trial.pending || trial.busy) return;
        void runSortingAction(() => moveSortingTrial({ kind: "move_rows", rowIds: [row.id], destination }), row.id, step);
      });
      controls.append(button);
    }
    item.prepend(controls);
    if (expanded) mountConnectors();
  }
}

function renderSorting(focusRowId, direction) {
  if (!sortingTrial) return;
  renderEditor();
  updateSortingControls();
  if (focusRowId) {
    const row = [...element("script-rows").querySelectorAll("[data-sorting-row-id]")]
      .find((item) => item.dataset.sortingRowId === focusRowId);
    const buttons = [...(row?.querySelectorAll(".sorting-row-controls button[data-sorting-move]:not(:disabled)") ?? [])];
    (buttons.find((button) => button.dataset.sortingMove === direction) ?? buttons[0] ?? element("sorting-discard")).focus();
  }
}

async function runSortingAction(action, rowId, direction) {
  const trial = sortingTrial;
  if (!trial || trial.busy || trial.pending || editRefused || composingRows.size) return;
  const pending = action();
  updateSortingControls();
  sortingStatus("Checking trial…");
  try {
    if (!await pending) sortingStatus("The saved script changed. Discard this trial and reload before sorting again.");
    else if (!sortingTrial) { finishSorting(true); return; }
    else sortingStatus("Trial only. Accept to save this order, or discard to keep the original.");
  } catch (error) { sortingStatus(error.message); }
  if (sortingTrial === trial) {
    renderSorting(rowId, direction);
    if (!rowId) element("sorting-accept").focus();
  }
}

element("open-sorting").addEventListener("click", () => {
  if (sortingTrial) {
    if (!element("footage-panel").hidden) researchPanel?.close();
    sortingTrial.preview = !sortingTrial.preview;
    setSortingMode(true);
    if (sortingTrial.preview) renderEditor();
    else renderSorting();
    sortingStatus(sortingTrial.preview ? "Previewing the pending script. Return to Sorting to make changes." :
      "Trial only. Your saved Draft is unchanged.");
    stashPanel?.update();
    return;
  }
  if (!beginSortingTrial()) return;
  researchPanel?.close();
  researchStillPanel?.close();
  activeAttach = null;
  activeReselect = null;
  setSortingMode(true);
  sortingStatus("Trial only. Your saved Draft is unchanged.");
  renderSorting();
  element("sorting-heading").focus();
});
element("sorting-discard").addEventListener("click", leaveSorting);
element("sorting-accept").addEventListener("click", () => { void runSortingAction(acceptSortingTrial); });

function showSortingChoices(open) {
  const choices = element("sorting-choices");
  choices.hidden = !open;
  element("sorting-outcomes").setAttribute("aria-expanded", String(open));
  if (open) choices.querySelector("button").focus();
}
element("sorting-outcomes").addEventListener("click", () => {
  showSortingChoices(element("sorting-choices").hidden);
});
element("sorting-choices").addEventListener("click", (event) => {
  const outcome = event.target.closest("[data-sorting-outcome]")?.dataset.sortingOutcome;
  if (outcome) void runSortingAction(() => acceptSortingTrial(outcome));
});
element("sorting-choices").addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  event.preventDefault();
  showSortingChoices(false);
  element("sorting-outcomes").focus();
});
function undoSorting() {
  const trial = sortingTrial;
  if (!trial || trial.preview || trial.acceptance || !trial.operations.length) return;
  void runSortingAction(async () => {
    trial.busy = true;
    try {
      const operations = trial.operations.slice(0, trial.history.at(-1));
      if (!await updateSortingDocument(trial, operations, await sortingRequest(trial, operations, "preview"))) return false;
      trial.history.pop();
      return true;
    } finally { trial.busy = false; }
  });
}
element("sorting-undo").addEventListener("click", undoSorting);

// Own the saved-head lane until an exact receipt and readback agree.
function lockExtrasEditor(locked) {
  for (const id of ["script-rows", "stash-panel", "footage-panel", "research-still-panel"]) {
    element(id).inert = locked;
  }
  projectTitle.readOnly = locked || accountPanel.accountMode() && (accountRole !== "producer" || !canEditAccount());
  for (const id of ["open-footage", "open-stash"]) element(id).disabled = locked;
  updateUndo();
}

element("project-home").addEventListener("click", (event) => {
  if (pendingExtras) event.preventDefault();
});

export function queueExtrasOperation(resolve, label) {
  if (!canEditAccount()) return Promise.resolve(false);
  if (sortingTrial) return queueSortingCommand(resolve, label, { structural: true });
  return startExtrasWrite(resolve, label, false);
}

function startExtrasWrite(resolve, label, isUndo, sortingBasis) {
  if (!prompterReady() || prompterDialog.open) {
    setSaveStatus("Finish saving the script before using Stash.");
    return Promise.resolve(false);
  }
  extrasFailure = undefined;
  const prior = scriptDocument;
  let operation;
  try {
    operation = resolve(prior);
  } catch (error) {
    setSaveStatus(error.message || "Choose the Stash material again.");
    return Promise.resolve(false);
  }
  const body = Object.freeze({ expectedRevision: documentRevision, clientMutationId: crypto.randomUUID(),
    ...(isUndo ? { document: operation } : { operation }) });
  pendingExtras = { projectId: activeProjectId, prior, body, digest: documentDigest,
    label, isUndo, sortingBasis, receipt: null, uncertain: false };
  clearPreparedPrompter("Save your script before exporting.");
  lockExtrasEditor(true);
  setSaveStatus();
  return retryExtrasWrite();
}

function retryExtrasWrite() {
  if (!pendingExtras || extrasRunning) return Promise.resolve(false);
  extrasRunning = true;
  extrasFailure = undefined;
  commandsPending += 1;
  const pending = pendingExtras;
  setSaveStatus();
  commandQueue = commandQueue.then(async () => {
    const { projectId, prior, body, digest, label, isUndo } = pending;
    const path = `/${projectId}/document`;
    const sameBasis = () => activeProjectId === projectId && scriptDocument === prior &&
      documentRevision === body.expectedRevision && documentDigest === digest &&
      !documentSaving && !documentDirty && !pendingDocument;
    if (!sameBasis()) {
      pendingExtras = undefined;
      extrasFailure = { message: "The open script changed. Reload the saved script.", action: "conflict" };
      conflicted = true;
      return false;
    }
    if (!pending.receipt) {
      const receipt = await api(isUndo ? path : path + "/extras-operations", isUndo ? "PUT" : "POST", body);
      if (receipt.projectId !== projectId || receipt.clientMutationId !== body.clientMutationId ||
          receipt.revision !== body.expectedRevision + 1 || !savedDigestPattern.test(receipt.digest)) {
        throw new Error("The saved Stash receipt could not be verified.");
      }
      pending.receipt = receipt;
    }
    const saved = await api(path);
    if (!sameBasis() || saved.document?.projectId !== projectId || saved.document.id !== prior.id ||
        saved.revision !== pending.receipt.revision || saved.digest !== pending.receipt.digest) {
      conflicted = true;
      undoStack.length = 0;
      pendingExtras = undefined;
      extrasFailure = { message: "The saved head changed. Open the saved script to continue.", action: "conflict" };
      return false;
    }
    const previousProjection = visualProjection;
    scriptDocument = saved.document;
    documentRevision = saved.revision;
    documentDigest = saved.digest;
    if (isUndo && pending.sortingBasis) {
      undoStack.pop();
      // The exact pre-Sorting document is saved again at a new revision.
      const earlier = undoStack.at(-1)?.durable;
      if (earlier?.revision === pending.sortingBasis.revision && earlier.digest === pending.sortingBasis.digest) {
        earlier.revision = saved.revision;
        earlier.digest = saved.digest;
        earlier.document = saved.document;
      }
    } else {
      // Older snapshots cannot cross a whole-row Extras mutation boundary.
      undoStack.length = 0;
      if (!isUndo) undoStack.push({ document: prior, label,
        durable: { revision: saved.revision, digest: saved.digest, document: saved.document } });
    }
    typingGroup = null;
    lastSplit = null;
    structuralFocus = null;
    activeAttach = null;
    activeReselect = null;
    visualFeedback = "";
    pendingExtras = undefined;
    invalidateProjection(false);
    researchPanel?.update();
    researchStillPanel?.update();
    void refreshProjection(scriptDocument, true, previousProjection);
    void refreshMusicWarnings();
    scheduleRender(true);
    return true;
  }).catch((error) => {
    if (!pending.receipt && !pending.uncertain && error instanceof ApiError &&
        [400, 401, 403, 404, 409].includes(error.status)) {
      pendingExtras = undefined;
      if (error.status === 409) {
        conflicted = true;
        undoStack.length = 0;
        extrasFailure = { message: "A newer script was saved elsewhere. Open the saved script to continue.", action: "conflict" };
      } else {
        extrasFailure = { message: "Stash change refused. The saved script was not changed." };
      }
    } else {
      pending.uncertain = true;
      extrasFailure = { message: pending.receipt ?
        "Stash change was saved, but its saved script could not be read. Retry readback." :
        "Stash delivery is unconfirmed. Retry the same change.", action: "retry" };
    }
    return false;
  }).finally(() => {
    extrasRunning = false;
    commandsPending -= 1;
    lockExtrasEditor(Boolean(pendingExtras));
    if (!pendingExtras && !extrasFailure && !pending.isUndo) stashPanel.open();
    setSaveStatus();
    if (renderRequested) scheduleRender();
  });
  return commandQueue;
}

function queueCommand(command, label, options = {}) {
  if (!canEditAccount()) return Promise.resolve(false);
  if (sortingTrial) return queueSortingCommand(command, label, options);
  if (pendingExtras || options.structural && composingRows.size) return Promise.resolve(false);
  if (extrasFailure && !extrasFailure.action) extrasFailure = undefined;
  const inputAt = performance.now();
  commandsPending += 1;
  clearPreparedPrompter("Save your script before exporting.");
  setSaveStatus();
  let commandError;
  commandQueue = commandQueue.then(async () => {
    if (!canEditAccount() || conflicted || editRefused) return false;
    // Input arriving during a Tab split occupies its normal place in this
    // queue, but must be resolved against the accepted destination row.
    if (options.prepareSplitInput) {
      const next = options.prepareSplitInput(scriptDocument);
      if (!next) return true;
      ({ command, label, options } = next);
    }
    if (options.expectedProjectId && (activeProjectId !== options.expectedProjectId ||
        scriptDocument?.projectId !== options.expectedProjectId)) {
      throw new Error(`The open script changed before the ${options.researchQuote ? "quote" : options.researchStill ? "still" : "footage"} was inserted.`);
    }
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
    if (options.research || options.researchStill || options.researchQuote) {
      typingGroup = null;
      const prior = scriptDocument;
      const quote = options.researchQuote === true;
      const path = quote ? "research-quote-insert" :
        options.researchStill ? "research-still-insert" : "research-insert";
      const result = await authoringVisualPost(path, {
        timelineProjectId: options.expectedProjectId, document: prior,
        expectedDocumentRevision: prior.rowEditRevision ?? 0, ...resolved,
      });
      if (activeProjectId !== options.expectedProjectId || scriptDocument !== prior) {
        throw new Error(`The open script changed before the ${quote ? "quote" : options.researchStill ? "still" : "footage"} was inserted.`);
      }
      if (JSON.stringify(result.document) === JSON.stringify(prior)) {
        throw new Error(`${quote ? "Quote" : options.researchStill ? "Still" : "Footage"} insertion did not change the script.`);
      }
      undoStack.push({ document: prior, label });
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      researchPanel?.update();
      researchStillPanel?.update();
      lastSplit = null;
      updateUndo();
      documentDirty = true;
      void saveDocument();
      void refreshProjection(scriptDocument, true, previousProjection);
      return true;
    }
    if (options.researchQuoteBox) {
      typingGroup = null;
      const prior = scriptDocument;
      const result = await authoringVisualPost("research-quote-box-edit", {
        document: prior, expectedDocumentRevision: prior.rowEditRevision ?? 0, ...resolved,
      });
      if (activeProjectId !== options.expectedProjectId || scriptDocument !== prior) {
        throw new Error("The open script changed before the quote box was edited.");
      }
      if (JSON.stringify(result.document) === JSON.stringify(prior)) {
        throw new Error("The quote box edit did not change the script.");
      }
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      const undoEntry = { document: prior, label };
      undoStack.push(undoEntry);
      researchPanel?.update();
      lastSplit = null;
      updateUndo();
      documentDirty = true;
      void saveDocument();
      void refreshProjection(scriptDocument, true, previousProjection);
      if (typeof resolved.edit?.displayText === "string") {
        undoEntry.quoteDefault = updateQuoteDisplayDefaultAfterSave({ projectId: options.expectedProjectId,
          rowId: resolved.rowId, overlayId: resolved.overlayId, displayText: resolved.edit.displayText });
      }
      return true;
    }
    if (options.visual) {
      typingGroup = null;
      const row = scriptDocument.activeDraft.blocks.find((item) => item.id === resolved?.blockId);
      if (!row?.primaryVisualSequence) throw new Error("The visual's row is no longer available.");
      const prior = scriptDocument;
      const result = await authoringVisualPost("visual-command", {
        document: prior, command: resolved, expectedSequenceVersion: row.primaryVisualSequence.version,
      });
      if (JSON.stringify(result.document) === JSON.stringify(prior)) {
        throw new Error("This visual edit did not change the script.");
      }
      undoStack.push({ document: prior, label });
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      lastSplit = null;
      ++projectionGeneration;
      clearTimeout(projectionTimer);
      visualProjection = result.projection ?? null;
      flashVisualIds = visualProjection ? changedCueIds(previousProjection, visualProjection) : new Set();
      if (!visualProjection) invalidateProjection();
      updateUndo();
      documentDirty = true;
      void saveDocument();
      scheduleRender(true);
      return true;
    }
    const sequenceVersion = visualCommandKinds.has(resolved?.kind) ? (() => {
      const row = scriptDocument.activeDraft.blocks.find((item) => item.id === resolved.blockId);
      if (row?.type !== "narration" || !Number.isSafeInteger(row.primaryVisualSequence?.version)) {
        throw new Error("The selected visual sequence is no longer available.");
      }
      return row.primaryVisualSequence.version;
    })() : undefined;
    if (options.paste) {
      typingGroup = null;
      const result = await applyPlainPaste(scriptDocument, resolved);
      if (result.document === scriptDocument) {
        options.onSplitApplied?.(scriptDocument, structuralFocus);
        scheduleRender(true);
        return true;
      }
      undoStack.push({ document: scriptDocument, label });
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      invalidateProjection(false);
      lastSplit = null;
      structuralFocus = result.focusAfter;
      options.onSplitApplied?.(scriptDocument, structuralFocus);
      updateUndo();
      documentDirty = true;
      void saveDocument();
      void refreshProjection(scriptDocument, true, previousProjection);
      return true;
    }
    const replay = resolved.kind === "join_rows" && resolved.direction === "previous" &&
      resolved.words === null && lastSplit?.newRowId === resolved.rowId &&
      lastSplit.revision === scriptDocument.rowEditRevision ? lastSplit : null;
    const previous = options.focusPrevious ? scriptDocument.activeDraft.blocks[
      scriptDocument.activeDraft.blocks.findIndex((item) => item.id === resolved.rowId) - 1
    ] : null;
    const result = await applyBrowserCommand(scriptDocument, resolved, replay?.proof, sequenceVersion);
    if (resolved.kind === "move_visual_to_row" || resolved.kind === "move_wordless_visual") activeAttach = null;
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
    const previousProjection = visualProjection;
    scriptDocument = result.document;
    invalidateProjection(false);
    visualFeedback = Array.isArray(result.evidence?.dropped) && result.evidence.dropped.length
      ? result.evidence.dropped.map((item) => item.message).join(" ") : "";
    lastSplit = resolved.kind === "split_row" && typeof result.splitProof === "string" ? {
      proof: result.splitProof, newRowId: resolved.newRowId, originalRowId: resolved.rowId,
      revision: scriptDocument.rowEditRevision, caret: options.splitCaret,
    } : null;
    if (options.focusAfter) structuralFocus = options.focusAfter;
    else if (previous?.type === "narration") structuralFocus = replay
      ? { rowId: replay.originalRowId, offset: replay.caret }
      : { rowId: previous.id, offset: previous.text.length + (previous.text.endsWith("\n") ? 0 : 1) };
    options.onSplitApplied?.(scriptDocument, structuralFocus);
    if (options.cardFocus) cardFocus = options.cardFocus;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    // Clearing narration can change the row's controls while its editor still has focus.
    const clearedNarration = resolved.kind === "edit_narration_text" && resolved.insertedText === "" &&
      scriptDocument.activeDraft.blocks.some((row) => row.id === resolved.rowId && row.type === "visual_only");
    void refreshProjection(scriptDocument, options.structural || Boolean(options.onSplitApplied) || clearedNarration, previousProjection);
    return true;
  }).catch((error) => {
    typingGroup = null;
    options.onSplitRefused?.(error);
    if (options.expectedRow && (!options.structural || options.paste)) {
      editRefused = true;
      refusedMessage = `${error.message || "Edit could not be applied."} Your unsaved text is still here; copy it or discard it to continue.`;
      element("discard-edit").hidden = false;
      element("discard-edit").disabled = true;
    }
    commandError = refusedMessage || error.message || "Edit could not be applied.";
    return false;
  }).finally(() => {
    commandsPending -= 1;
    setSaveStatus(commandError);
    if (editRefused && commandsPending === 0) element("discard-edit").disabled = false;
    if (renderRequested) scheduleRender();
  });
  return commandQueue;
}

function updateUndo() {
  const button = element("undo");
  button.disabled = Boolean(pendingExtras) || undoStack.length === 0;
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
  if (!canEditAccount()) return;
  if (pendingExtras || sortingTrial || prompterDialog.open || composingRows.size) return;
  const entry = undoStack.at(-1);
  if (entry?.durable) {
    if (entry.durable.revision !== documentRevision || entry.durable.digest !== documentDigest) {
      setSaveStatus("This Stash Undo no longer matches the saved head.");
      return;
    }
    void startExtrasWrite(() => entry.document, "Undo " + entry.label, true, entry.sortingBasis);
    return;
  }
  clearPreparedPrompter("Save your script before exporting.");
  activeAttach = null;
  typingGroup = null;
  commandsPending += 1;
  setSaveStatus();
  commandQueue = commandQueue.then(async () => {
    // Earlier requests may have completed after Undo was queued, restoring
    // a typing group. Undo is a history boundary at *execution* as well.
    typingGroup = null;
    if (conflicted || editRefused || !undoStack.length || undoStack.at(-1)?.durable) return;
    const undone = undoStack.at(-1);
    const restoreQuoteDefault = await undone.quoteDefault;
    if (conflicted || editRefused || undoStack.at(-1) !== undone) return;
    const previousProjection = visualProjection;
    scriptDocument = undoStack.pop().document;
    researchPanel?.update();
    invalidateProjection(false);
    visualFeedback = "";
    lastSplit = null;
    structuralFocus = null;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    void refreshProjection(scriptDocument, true, previousProjection);
    if (restoreQuoteDefault && await waitForDocumentSave() && activeProjectId === restoreQuoteDefault.projectId) {
      const { projectId, rowId, overlayId, undo } = restoreQuoteDefault;
      try {
        await authoringVisualPost("research-quote-display-default", {
          timelineProjectId: projectId, rowId, overlayId, undo,
          expectedRevision: documentRevision, expectedDigest: documentDigest,
        });
        void researchPanel?.refresh?.();
      } catch {
        setSaveStatus("Quote box undo saved. The Library display default could not be restored.");
      }
    }
  }).finally(() => {
    commandsPending -= 1;
    setSaveStatus();
    if (editRefused && commandsPending === 0) element("discard-edit").disabled = false;
    if (renderRequested) scheduleRender();
  });
}
element("undo").addEventListener("click", undo);
document.addEventListener("keydown", (event) => {
  // Modal controls own keys while the editor behind them is inactive.
  if (document.querySelector("dialog[open]") || pendingExtras) return;
  if (sortingTrial) {
    if (!event.isComposing && (event.metaKey || event.ctrlKey) && !event.shiftKey &&
        event.key.toLowerCase() === "z" && !event.defaultPrevented) {
      event.preventDefault();
      undoSorting();
    }
    if (event.key === "Escape" && !event.isComposing && !event.defaultPrevented) {
      event.preventDefault();
      if (!sortingTrial.busy) leaveSorting();
    }
    return;
  }
  if (event.key === "Escape" && !event.isComposing && !event.defaultPrevented && activeAttach) {
    event.preventDefault();
    cancelAttach();
    return;
  }
  if (!event.isComposing && (event.metaKey || event.ctrlKey) && !event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    undo();
  }
  if (!event.isComposing && (event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "f") {
    event.preventDefault();
    if (!activeProjectId) return;
    const selection = document.getSelection();
    const text = selection && !selection.isCollapsed ? selection.toString().trim() : "";
    const editor = selection?.anchorNode?.parentElement?.closest?.("[data-narration-editor]");
    if (editor && editor.contains(selection.focusNode)) {
      const rowId = editor.closest("[data-row-kind='narration']")?.dataset.rowId;
      const row = scriptDocument?.activeDraft.blocks.find((item) => item.id === rowId);
      const target = selectedNarrationTarget();
      if (row?.type === "narration" && target?.selected && text) {
        const range = selection.getRangeAt(0);
        const prefix = range.cloneRange();
        prefix.selectNodeContents(editor);
        prefix.setEnd(range.startContainer, range.startOffset);
        openFootageForWords({ rowId, text: row.text, selection: {
          start: prefix.toString().length, end: prefix.toString().length + range.toString().length,
        }, seed: text, from: editor });
        return;
      }
      if (row?.type === "narration" && target && !target.selected) {
        openLibraryAtCaret(target, editor);
        return;
      }
    }
    if (text && editor && editor.contains(selection.focusNode)) {
      const range = selection.getRangeAt(0);
      const prefix = range.cloneRange();
      prefix.selectNodeContents(editor);
      prefix.setEnd(range.startContainer, range.startOffset);
      const rowId = editor.closest("[data-row-id]")?.dataset.rowId;
      const row = scriptDocument?.activeDraft.blocks.find((item) => item.id === rowId);
      if (row?.type === "narration") {
        openFootageForWords({ rowId, text: row.text, selection: {
          start: prefix.toString().length, end: prefix.toString().length + range.toString().length,
        }, seed: text, from: editor });
        return;
      }
    }
    stashPanel.close(false);
    void researchPanel.open({ from: document.activeElement });
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
  if (opening || pendingExtras || sortingTrial?.acceptance) return;
  opening = true;
  homeStatus.textContent = "Opening script…";
  try { await showScript(projectId); } catch (error) { showOpenError(error); }
  finally { opening = false; updatePrompterControls(); }
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
  if (opening || pendingExtras) return;
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
    updatePrompterControls();
  }
});

openForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const id = readProjectId(openLink.value);
  if (id) void openScript(id);
  else homeStatus.textContent = "Enter a saved script link or project ID.";
});

function setSaveStatus(message = "Saved") {
  // A failure belongs to its outstanding mutation, not the last UI event.
  // A conflict prevents either retry; otherwise document Retry takes priority.
  const failure = [extrasFailure, documentSaveFailure, nameSaveFailure].find((item) => item?.action === "conflict") ??
    documentSaveFailure ?? nameSaveFailure ?? extrasFailure;
  let action;
  if (failure) ({ message, action } = failure);
  else if (editRefused) message = refusedMessage;
  else if (message === "Saved") {
    if (pendingExtras || documentSaving || saving || commandsPending) message = "Saving…";
    else if (project && !projectTitle.value.trim()) message = "Project name is required. Your change is unsaved.";
    else if (pendingDocument || documentDirty || pendingName || composingRows.size ||
        (project && projectTitle.value.trim() !== project.title)) message = "Unsaved changes";
    else if (visualFeedback) message = `Saved · ${visualFeedback}`;
  }
  saveStatus.textContent = message;
  retrySave.hidden = action !== "retry" || !canEditAccount();
  openSaved.hidden = action !== "conflict";
  updatePrompterControls();
}

element("discard-edit").addEventListener("click", () => {
  if (!editRefused || commandsPending || sortingTrial?.pending || !window.confirm("Discard the unsaved text? Copy anything you want to keep first.")) return;
  if (accountPanel.accountMode()) { element("account-discard").click(); return; }
  editRefused = false;
  refusedMessage = "";
  element("discard-edit").hidden = true;
  forceRender = false;
  renderRequested = false;
  renderEditor();
  setSaveStatus();
});

async function saveName() {
  clearTimeout(saveTimer);
  if (accountPanel.accountMode() && (accountRole !== "producer" || !canEditAccount())) return;
  if (!project || pendingExtras || saving || conflicted) return;
  const title = projectTitle.value.trim();
  if (!pendingName) {
    if (!title) {
      setSaveStatus();
      return;
    }
    if (title === project.title) {
      setSaveStatus();
      return;
    }
    pendingName = {
      title, expectedProjectVersion: project.projectVersion, clientMutationId: crypto.randomUUID(),
    };
  }
  saving = true;
  setSaveStatus();
  try {
    ({ project } = await api(`/${project.projectId}`, "PATCH", pendingName));
    pendingName = undefined;
    nameSaveFailure = undefined;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      conflicted = true;
      nameSaveFailure = { message: "A newer project name was saved elsewhere. Your unsaved name is still here.", action: "conflict" };
    } else if (error instanceof ApiError && error.status === 401) {
      nameSaveFailure = { message: "Your unsaved name is still here. Open the private VERA launch link in another tab, then retry here.", action: "retry" };
    } else {
      nameSaveFailure = { message: "Couldn’t save the project name. Your unsaved name is still here.", action: "retry" };
    }
    return;
  } finally {
    saving = false;
    setSaveStatus();
  }
  // Replay the same receipt after a failed request. Any newer typing is saved
  // only after that request confirms the next project version.
  if (projectTitle.value.trim() !== project.title) void saveName();
}

projectTitle.addEventListener("input", () => {
  clearPreparedPrompter("Save your script before exporting.");
  if (saving || conflicted || pendingName) return;
  clearTimeout(saveTimer);
  setSaveStatus();
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
retrySave.addEventListener("click", () => {
  if (pendingExtras) void retryExtrasWrite();
  else if (documentSaveFailure) void saveDocument();
  else if (nameSaveFailure) void saveName();
});

function hasPendingDraft() {
  return Boolean(sortingTrial?.operations.length || sortingTrial?.pending || sortingTrial?.busy ||
    sortingTrial?.acceptance || pendingExtras || pendingCreate || pendingName || pendingDocument || documentDirty ||
    documentSaving || commandsPending || editRefused || accountHold || composingRows.size ||
    project && projectTitle.value.trim() !== project.title);
}
function protectDraft(event) {
  if (hasPendingDraft()) { event.preventDefault(); event.returnValue = ""; }
}

window.addEventListener("beforeunload", protectDraft);
async function connectBrowser() {
  await accountPanel.connect();
  if (accountPanel.accountMode()) return;
  try { sessionProof = localStorage.getItem(sessionKey) ?? ""; } catch { /* The current page can still connect. */ }
  const launchCode = new URLSearchParams(location.hash.slice(1)).get("launch");
  if (!launchCode) return;
  history.replaceState(null, "", location.pathname + location.search);
  try {
    const response = await accountFetch("/authoring/session", {
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
const stashActions = createStashActions((command, label, options) => {
  const projectId = activeProjectId;
  return queueCommand((current) => {
    if (current.projectId !== projectId) throw new Error("The open script changed.");
    return command(current);
  }, label, options);
}, editorDocument, undefined, queueExtrasOperation);
stashPanel = mountStashPanel({
  root: element("stash-panel"), script: element("script-rows"), actions: stashActions,
  getDocument: editorDocument, sorting: () => Boolean(sortingTrial), readOnly: () => Boolean(sortingTrial?.preview || sortingTrial?.acceptance || pendingExtras || editRefused || !canEditAccount()),
  applyCommand: applyBrowserCommand, fetchProjection, pickClip: openStashClipPicker,
  loadClip: async ({ researchProjectId, clipId, clipVersion }) => {
    const { clip } = await researchCatalogGet(researchProjectId, clipId);
    return clip?.version === clipVersion ? clip : null;
  },
  getScriptDrag: () => stashScriptDrag, clearScriptDrag: () => { stashScriptDrag = null; },
  onOpen: () => {
    if (!element("footage-panel").hidden) researchPanel.close();
    if (!element("research-still-panel").hidden) researchStillPanel.close();
  },
});
element("open-footage").addEventListener("click", () => stashPanel.close(false));
researchPanel = mountResearchPanel({
  root: element("footage-panel"),
  catalog: researchCatalogGet,
  quotesCatalog: researchQuoteCatalogGet,
  quoteThumbnail: researchQuoteThumbnailGet,
  getDocument: editorDocument,
  insert: (clip, placement) => queueResearchClipInsert({ researchProjectId: clip.projectId,
    clipId: clip.id, clipVersion: clip.version, placement }),
  insertQuote: (quote, placement) => queueResearchQuoteInsert({ quote, placement }),
  onPlaceQuote: placeLibraryQuote,
  gapChoices: availableGaps, rowChoices: availableNarrationRows,
  onStatus: (message) => setSaveStatus(message),
});
researchStillPanel = mountResearchStillPanel({
  root: element("research-still-panel"),
  catalog: async (researchProjectId, offset) => researchProjectId === undefined
    ? await researchCatalogGet() : await researchStillCatalogGet(researchProjectId, offset),
  thumbnail: researchStillThumbnailGet,
  insert: (still, placement, researchProjectId) => queueResearchStillInsert({
    researchProjectId,
    itemId: still.itemId, itemVersion: still.itemVersion, placement,
  }),
  onStatus: (message) => setSaveStatus(message),
});
const initialProject = new URLSearchParams(location.search).get("project");
if (initialProject !== null) {
  openLink.value = initialProject;
  if (uuid.test(initialProject)) void openScript(initialProject.toLowerCase());
  else homeStatus.textContent = "Enter a saved script link or project ID.";
}
