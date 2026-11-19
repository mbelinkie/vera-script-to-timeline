import { mountVisualCardMenus, renderRows } from "./view.js";
import { mountRowsEditor, createBlankNarrationRow, rowGaps } from "./rows-editor.js";
import { mountNarration } from "./narration-editor.js";
import { parseHoldSeconds, planVisualOnlyReorder, visualOnlyIds } from "./visual-only-actions.js";

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
const visualCommandKinds = new Set([
  "add_visual_on_selection", "change_visual_type", "delete_visual",
  "set_visual_range", "set_on_camera_framing",
  "move_visual_to_row", "attach_visual_to_words",
]);
const wordlessCommandKinds = new Set(["move_wordless_visual", "add_visual_to_wordless_row",
  "reorder_visual_only", "set_visual_only_hold"]);
let project;
let activeProjectId;
let scriptDocument;
let flashVisualIds = new Set();
let visualFeedback = "";
let cardFocus = null;
let documentRevision;
let pendingDocument;
let documentSaving = false;
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
  flashVisualIds = new Set();
  visualFeedback = "";
  documentRevision = savedScript.revision;
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
  const root = element("script-rows");
  const requestedFocus = structuralFocus;
  structuralFocus = null;
  const requestedCardFocus = cardFocus;
  cardFocus = null;
  const active = document.activeElement;
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
  renderRows(root, scriptDocument, {
    projection: visualProjection, visualCommand: queueVisualCommand, reselect: beginReselect,
    attach: beginAttach, attaching: activeAttach,
    addWordless: addWordlessVisual,
    flashIds: flashVisualIds,
  });
  flashVisualIds = new Set();
  narrationCleanup.push(mountVisualCardMenus(root, (command, label, focus) =>
    queueCommand(command, label, { structural: true, cardFocus: focus })));
  narrationCleanup.push(mountVisualCardDragging(root));
  narrationCleanup.push(mountWordlessControls(root));
  mountRowsEditor(root, scriptDocument, {
    createBlankRow: createBlankNarrationRow,
    command: (command, label) => queueCommand(command, label, { structural: true }),
  });
  root.querySelectorAll('.script-row .narration-cell').forEach((cell) => {
    narrationCleanup.push(mountNarration(cell, scriptDocument, queueCommand, {
      projection: projectedPrimaryRow(cell.closest("[data-row-id]")?.dataset.rowId),
      visualCommand: queueVisualCommand,
      reselect: activeReselect?.rowId === cell.closest("[data-row-id]")?.dataset.rowId ? activeReselect : null,
      cancelReselect,
      commitReselect,
      previewReselect,
      attaching: activeAttach?.rowId === cell.closest("[data-row-id]")?.dataset.rowId ? activeAttach : null,
      finishAttach, cancelAttach,
      compositionChange(rowId, active) {
        if (active) composingRows.add(rowId);
        else { composingRows.delete(rowId); scheduleRender(); }
      },
      requestRender: scheduleRender,
    }));
  });
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
}

function beginAttach(rowId, slotId) {
  const row = scriptDocument?.activeDraft.blocks.find((item) => item.id === rowId);
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
    dragging = null;
    target = null;
    reorderMarker = null;
  };
  const rowFor = (id, doc = scriptDocument) => doc?.activeDraft.blocks.find((row) => row.id === id);
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
  const row = scriptDocument?.activeDraft.blocks.find((item) => item.id === rowId);
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
  const snapshot = scriptDocument;
  const row = snapshot?.activeDraft.blocks.find((item) => item.id === state?.rowId);
  if (!state || row?.type !== "narration" || row.text !== state.text ||
      row.primaryVisualSequence?.version !== state.version) {
    throw new Error("The narration changed; start Reselect again.");
  }
  const result = await authoringVisualPost("visual-preview", {
    document: snapshot, command, expectedSequenceVersion: state.version,
  });
  if (activeReselect !== state || scriptDocument !== snapshot) {
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
    if (!renderRequested || editRefused || conflicted || commandsPending || composingRows.size) return;
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
  if (renderRequested) scheduleRender();
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
    void refreshMusicWarnings();
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

async function applyBrowserCommand(document, command, splitProof, expectedSequenceVersion) {
  const response = await fetch("/authoring/command", {
    method: "POST", headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    body: JSON.stringify({ document, command, ...(splitProof ? { splitProof } : {}),
      ...(expectedSequenceVersion === undefined ? {} : { expectedSequenceVersion }),
      ...(wordlessCommandKinds.has(command.kind) ? { expectedRowEditRevision: document.rowEditRevision ?? 0 } : {}) }),
    signal: AbortSignal.timeout(12_000),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.diagnostics?.[0]?.message || "Edit could not be applied.");
  return result;
}

async function authoringVisualPost(path, body) {
  await connecting;
  try { sessionProof = localStorage.getItem(sessionKey) ?? sessionProof; } catch { /* Keep enrolled proof. */ }
  const response = await fetch(`/authoring/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12_000),
  });
  const result = await response.json();
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
  const response = await fetch(path, {
    headers: { "X-VERA-Authoring": "1", "X-VERA-Session": sessionProof },
    signal: AbortSignal.timeout(12_000),
  });
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the footage list.");
  if (!response.ok) throw new Error("Research footage is unavailable or no longer authorized.");
  const catalog = await response.json();
  if (timelineId !== activeProjectId) throw new Error("The open script changed. Reload the footage list.");
  return catalog;
}

/** Resolves placement only after earlier typing has produced actual current token IDs. */
export function queueResearchClipInsert({ researchProjectId, clipId, clipVersion, placement }) {
  const projectId = activeProjectId;
  return queueCommand((latest) => ({ researchProjectId, clipId, clipVersion,
    placement: typeof placement === "function" ? placement(latest) : placement,
  }), "Add footage", { structural: true, research: true, expectedProjectId: projectId });
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
  return visualProjection?.rows?.find((row) => row.blockId === rowId) ?? null;
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
    if (options.expectedProjectId && (activeProjectId !== options.expectedProjectId ||
        scriptDocument?.projectId !== options.expectedProjectId)) {
      throw new Error("The open script changed before the footage was inserted.");
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
    if (options.research) {
      typingGroup = null;
      const prior = scriptDocument;
      const result = await authoringVisualPost("research-insert", {
        timelineProjectId: options.expectedProjectId, document: prior,
        expectedDocumentRevision: prior.rowEditRevision ?? 0, ...resolved,
      });
      if (activeProjectId !== options.expectedProjectId || scriptDocument !== prior) {
        throw new Error("The open script changed before the footage was inserted.");
      }
      if (JSON.stringify(result.document) === JSON.stringify(prior)) {
        throw new Error("Footage insertion did not change the script.");
      }
      undoStack.push({ document: prior, label });
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      lastSplit = null;
      updateUndo();
      documentDirty = true;
      void saveDocument();
      void refreshProjection(scriptDocument, true, previousProjection);
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
        scheduleRender(true);
        return true;
      }
      undoStack.push({ document: scriptDocument, label });
      const previousProjection = visualProjection;
      scriptDocument = result.document;
      invalidateProjection(false);
      lastSplit = null;
      structuralFocus = result.focusAfter;
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
    if (options.cardFocus) cardFocus = options.cardFocus;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    void refreshProjection(scriptDocument, options.structural, previousProjection);
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
  activeAttach = null;
  typingGroup = null;
  commandsPending += 1;
  commandQueue = commandQueue.then(() => {
    // Earlier requests may have completed after Undo was queued, restoring
    // a typing group. Undo is a history boundary at *execution* as well.
    typingGroup = null;
    if (conflicted || editRefused || !undoStack.length) return;
    const previousProjection = visualProjection;
    scriptDocument = undoStack.pop().document;
    invalidateProjection(false);
    visualFeedback = "";
    lastSplit = null;
    structuralFocus = null;
    updateUndo();
    documentDirty = true;
    void saveDocument();
    void refreshProjection(scriptDocument, true, previousProjection);
  }).finally(() => {
    commandsPending -= 1;
    if (editRefused && commandsPending === 0) element("discard-edit").disabled = false;
    if (renderRequested) scheduleRender();
  });
}
element("undo").addEventListener("click", undo);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !event.isComposing && !event.defaultPrevented && activeAttach) {
    event.preventDefault();
    cancelAttach();
    return;
  }
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
  else if (message === "Saved" && visualFeedback) message = `Saved · ${visualFeedback}`;
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
