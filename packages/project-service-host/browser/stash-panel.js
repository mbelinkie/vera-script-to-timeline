import { captureStashNoteDrop, captureSavedPlacement, draftGapChoices, savedPlacementCommand } from "./stash-actions.js";
import { mountStashRowEditor } from "./stash-row-editor.js";
import { mountFootagePlayer } from "./footage-player.js";

const dragType = "application/x-vera-stash-note";
const itemDragType = "application/x-vera-stash-item";
const scriptRowsDragType = "application/x-vera-script-rows";
const scriptVisualDragType = "application/x-vera-visual";
const make = (doc, tag, text) => {
  const node = doc.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
};

function interiorTokens(row) {
  if (row.type !== "narration" || row.state !== "active" || row.plainDirection) return [];
  return row.tokens.filter((token, index) => index > 0 &&
    token.spoken !== false && row.tokens[index - 1]?.spoken !== false);
}

function noteGaps(model, noteId) {
  return (model?.activeDraft?.blocks ?? []).flatMap((row, index) => {
    const tokens = interiorTokens(row);
    const first = tokens.length && captureStashNoteDrop(model, noteId, row.id, tokens[0].id);
    return !first ? [] : tokens.map((token) => ({
      intent: { ...first, beforeTokenId: token.id },
      label: `Row ${index + 1}: before “${token.value}” (character ${token.startOffset + 1}) in ${row.text.slice(0, 45)}`,
    }));
  });
}

function hiddenStashRows(model, hide) {
  if (!hide) return new Set();
  const rows = new Map((model?.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row])));
  const outline = model?.stashOutline ?? [...rows.keys()].map((rowId) => ({ rowId, parentRowId: null }));
  const children = new Map();
  for (const entry of outline) if (entry.parentRowId !== null) {
    const list = children.get(entry.parentRowId) ?? [];
    list.push(entry.rowId);
    children.set(entry.parentRowId, list);
  }
  const visible = new Set();
  const needed = (rowId) => {
    const row = rows.get(rowId);
    if (!row) return false;
    const unfinished = row.stashChecklist?.completed !== true;
    const childNeeded = (children.get(rowId) ?? []).map(needed).some(Boolean);
    if (unfinished || childNeeded) visible.add(rowId);
    return unfinished || childNeeded;
  };
  for (const entry of outline) if (entry.parentRowId === null) needed(entry.rowId);
  return new Set(outline.filter((entry) => !visible.has(entry.rowId)).map((entry) => entry.rowId));
}

function caretRect(editor, offset) {
  const doc = editor.ownerDocument;
  const walker = doc.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (offset < node.length) {
      const range = doc.createRange();
      range.setStart(node, offset);
      range.collapse(true);
      return range.getBoundingClientRect();
    }
    offset -= node.length;
  }
  return null;
}

/** The panel only projects saved state; all writes go through the ordinary editor queue. */
export function mountStashPanel({ root, script, actions, getDocument, onOpen, readOnly = () => false,
  getScriptDrag = () => null, clearScriptDrag = () => {}, applyCommand, fetchProjection, loadClip, pickClip = () => {}, sorting = () => false }) {
  const doc = root.ownerDocument;
  const toggle = doc.getElementById("open-stash");
  const form = root.querySelector("[data-stash-form]");
  const input = root.querySelector("#stash-note");
  const section = root.querySelector("#stash-section");
  const entries = root.querySelector("[data-stash-entries]");
  const status = root.querySelector("[data-stash-status]");
  const place = root.querySelector("[data-stash-place]");
  const destinations = root.querySelector("#stash-destination");
  const savedPlace = root.querySelector("[data-stash-saved-place]");
  const savedDestinations = root.querySelector("#stash-saved-destination");
  const savedConfirm = root.querySelector("[data-stash-saved-confirm]");
  const includeDescendants = root.querySelector("[data-stash-include-descendants]");
  const includeLabel = root.querySelector("[data-stash-include-label]");
  const hideCompleted = root.querySelector("[data-stash-hide-completed]");
  const textSize = root.querySelector("[data-stash-text-size]");
  const addSection = root.querySelector("[data-stash-add-section]");
  const addClip = root.querySelector("[data-stash-add-clip]");
  const editorHost = root.querySelector("[data-stash-editor-host]");
  const marker = make(doc, "span");
  marker.className = "stash-drop-cursor";
  marker.hidden = true;
  marker.setAttribute("aria-hidden", "true");
  doc.body.append(marker);
  const playerRoot = make(doc, "section");
  playerRoot.className = "footage-panel__preview stash-panel__preview";
  playerRoot.setAttribute("aria-label", "Stash saved footage preview");
  playerRoot.hidden = true;
  const playerHeading = make(doc, "div");
  playerHeading.className = "footage-panel__preview-heading";
  playerHeading.append(make(doc, "h3"), make(doc, "button", "Close preview"));
  playerHeading.lastChild.type = "button";
  playerHeading.lastChild.setAttribute("data-footage-preview-close", "");
  playerHeading.lastChild.addEventListener("click", () => stashPlayer.hide());
  playerRoot.append(playerHeading, make(doc, "p"), make(doc, "div"), make(doc, "p"), make(doc, "div"));
  playerHeading.firstChild.dataset.footagePreviewTitle = "";
  playerRoot.children[1].dataset.footagePreviewRange = "";
  playerRoot.children[1].className = "footage-panel__hint";
  playerRoot.children[2].dataset.footagePlayerMount = "";
  playerRoot.children[2].className = "footage-panel__player-mount";
  playerRoot.children[3].dataset.footagePlayerStatus = "";
  playerRoot.children[3].className = "footage-panel__hint";
  playerRoot.children[3].setAttribute("role", "status");
  playerRoot.children[3].setAttribute("aria-live", "polite");
  const playerControls = make(doc, "div");
  playerControls.className = "footage-panel__player-controls";
  playerControls.append(make(doc, "button", "Play saved range"), make(doc, "button", "Replay from start"));
  playerControls.firstChild.type = playerControls.lastChild.type = "button";
  playerControls.firstChild.dataset.footagePlay = "";
  playerControls.lastChild.dataset.footageReplay = "";
  playerRoot.append(playerControls);
  root.append(playerRoot);
  const stashPlayer = mountFootagePlayer(playerRoot);
  let rendered = "";
  let drag = null;
  let preview = null;
  let choices = [];
  let chosen = null;
  let savedChoice = null;
  let pending = false;
  let generation = 0;
  let internalDropTarget = null;
  let externalDropTarget = null;
  let editNoteRow = null;
  let rowEditor = null;
  try { hideCompleted.checked = localStorage.getItem("vera.authoring.stash-hide-completed") === "true"; } catch { /* Current tab preference still works. */ }
  try { textSize.value = localStorage.getItem("vera.authoring.stash-size") ?? "100"; } catch { textSize.value = "100"; }
  const setTextSize = () => {
    const percent = Math.max(80, Math.min(200, Number(textSize?.value) || 100));
    root.style.setProperty("--stash-text-scale", String(percent / 100));
    textSize?.setAttribute("aria-valuetext", `${percent}%`);
    try { localStorage.setItem("vera.authoring.stash-size", String(percent)); } catch { /* Current tab still scales. */ }
  };
  setTextSize();
  if (applyCommand && editorHost) rowEditor = mountStashRowEditor({ host: editorHost, getDocument,
    applyCommand, fetchProjection, onSave: actions.saveMembers });
  const clearDrag = () => {
    drag = null;
    preview = null;
    internalDropTarget = null;
    externalDropTarget = null;
    marker.hidden = true;
    marker.style.width = "3px";
    marker.style.height = "";
  };
  const cancelPlace = () => { chosen = null; choices = []; place.hidden = true; };

  const cancelSaved = () => { savedChoice = null; savedPlace.hidden = true; };
  function focusOpener(opener, rowId, action) {
    if (opener?.isConnected) { opener.focus(); return; }
    const entry = [...entries.querySelectorAll("[data-stash-row-id]")]
      .find((item) => item.dataset.stashRowId === rowId);
    (entry?.querySelector(`[data-saved-action="${action}"]`) ?? toggle).focus();
  }

  function close(focus = true, reset = false) {
    generation += 1;
    root.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    clearDrag();
    stashPlayer.hide();
    clearScriptDrag();
    externalDropTarget = null;
    internalDropTarget = null;
    cancelPlace();
    cancelSaved();
    if (reset) { input.value = ""; section.value = ""; }
    status.textContent = "";
    if (focus) toggle.focus();
  }

  function open() {
    if (!root.hidden) { update(); return; }
    onOpen();
    root.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    rendered = "";
    update();
    toggle.focus();
  }

  function choose(noteId, opener) {
    cancelSaved();
    chosen = { noteId, opener };
    choices = noteGaps(getDocument(), noteId);
    destinations.replaceChildren(...choices.map(({ label }, index) => {
      const option = make(doc, "option", label);
      option.value = String(index);
      return option;
    }));
    place.hidden = !choices.length;
    if (!choices.length) {
      status.textContent = "No interior spoken-word insertion point is available.";
      cancelPlace();
      return;
    }
    destinations.focus();
  }

  function chooseSaved(entry, kind, opener, rowIds = entry.group ?
    getDocument()?.stashGroups?.find((group) => group.id === entry.group.id)?.rowIds ?? [entry.rowId] : [entry.rowId]) {
    if (readOnly() || pending) return;
    cancelPlace();
    cancelSaved();
    const model = getDocument();
    const gaps = draftGapChoices(model);
    const include = kind === "place_stash_rows" ? Boolean(includeDescendants?.checked) : undefined;
    const first = gaps.length && captureSavedPlacement(model, kind, rowIds, gaps[0].gap, include);
    if (!first) {
      status.textContent = "No exact Draft destination is available.";
      return;
    }
    // Every option shares the source and Draft snapshots captured at opening,
    // rather than recomputing an intent against a possibly changed head.
    const options = gaps.map(({ gap, label }) => ({
      label, intent: Object.freeze({ ...first, destination: gap }),
    }));
    const original = entry.originalDraft;
    const originalIndex = original.available ? options.findIndex(({ intent }) =>
      JSON.stringify(intent.destination) === JSON.stringify(original.gap)) : -1;
    savedChoice = { rowId: entry.rowId, rowIds: [...rowIds], opener, kind, options,
      includeEnabled: kind === "place_stash_rows", branch: entry.kind === "note" };
    const action = kind === "duplicate_stash_rows" ? "Duplicate as new" :
      kind === "place_stash_rows" ? "Place in script" : "Restore";
    root.querySelector("[data-stash-saved-description]").textContent =
      kind === "duplicate_stash_rows" ? "Create new authored identities; keep the saved original." :
        kind === "place_stash_rows" ? "Place this branch: notes are copied and checked; unfinished rows and clips move." :
          "Move the saved row back into Draft with its original identity.";
    if (includeLabel) includeLabel.hidden = !savedChoice.includeEnabled || !savedChoice.branch || !entry.hasDescendants;
    savedConfirm.textContent = action;
    const placeholder = make(doc, "option", "Choose an exact Draft gap…");
    placeholder.value = "";
    savedDestinations.replaceChildren(placeholder, ...options.map(({ label }, index) => {
      const option = make(doc, "option", label);
      option.value = String(index);
      return option;
    }));
    savedDestinations.value = originalIndex < 0 ? "" : String(originalIndex);
    savedPlace.hidden = false;
    status.textContent = original.available ? "" : "Original gap unavailable. Choose a current Draft location.";
    savedDestinations.focus();
  }

  function chooseGroup(entry, opener) {
    if (readOnly() || pending || !entry.group) return;
    cancelPlace();
    cancelSaved();
    const model = getDocument();
    const group = model?.stashGroups?.find((item) => item.id === entry.group.id);
    const options = draftGapChoices(model).map(({ gap, label }) => ({ label, intent: { destination: gap } }));
    if (!group || !options.length) {
      status.textContent = "No exact Draft destination is available.";
      return;
    }
    savedChoice = { rowId: entry.rowId, rowIds: [...group.rowIds], groupId: group.id,
      model, opener, kind: "place_stash_group", options };
    root.querySelector("[data-stash-saved-description]").textContent = `Move all ${group.rowIds.length} group rows into Draft as one group.`;
    savedConfirm.textContent = "Place group";
    if (includeLabel) includeLabel.hidden = true;
    const placeholder = make(doc, "option", "Choose an exact Draft gap…");
    placeholder.value = "";
    savedDestinations.replaceChildren(placeholder, ...options.map(({ label }, index) => {
      const option = make(doc, "option", label);
      option.value = String(index);
      return option;
    }));
    savedDestinations.value = "";
    savedPlace.hidden = false;
    status.textContent = "";
    savedDestinations.focus();
  }

  async function placeSaved() {
    if (readOnly() || pending || !savedChoice || savedDestinations.value === "") return;
    const selection = savedChoice;
    if (selection.kind === "place_stash_group") {
      const destination = selection.options[Number(savedDestinations.value)]?.intent.destination;
      if (!destination || getDocument() !== selection.model) {
        cancelSaved();
        status.textContent = "The saved group or destination changed. Choose again.";
        focusOpener(selection.opener, selection.rowId, selection.kind);
        return;
      }
      pending = true;
      const started = generation;
      const ok = await actions.placeGroup(selection.groupId, destination, selection.model);
      pending = false;
      if (generation !== started) return;
      cancelSaved();
      update();
      status.textContent = ok ? "Group placed in Draft." : "Group was not placed. Review saved references or script status.";
      focusOpener(selection.opener, selection.rowId, selection.kind);
      return;
    }
    const baseIntent = selection.options[Number(savedDestinations.value)]?.intent;
    const model = getDocument();
    const include = selection.includeEnabled ? Boolean(includeDescendants?.checked) : undefined;
    const intent = baseIntent && selection.includeEnabled ? captureSavedPlacement(model, selection.kind,
      selection.rowIds, baseIntent.destination, include) : baseIntent;
    if (!intent) return;
    if (selection.includeEnabled && (intent.stashSnapshot !== baseIntent.stashSnapshot ||
      intent.draftSnapshot !== baseIntent.draftSnapshot)) {
      cancelSaved();
      status.textContent = "The saved material or destination changed. Choose again.";
      focusOpener(selection.opener, selection.rowId, selection.kind);
      return;
    }
    try {
      savedPlacementCommand(getDocument(), intent);
    } catch {
      cancelSaved();
      status.textContent = "The saved material or destination changed. Choose again.";
      focusOpener(selection.opener, selection.rowId, selection.kind);
      return;
    }
    pending = true;
    const started = generation;
    const ok = await actions.placeSaved(intent);
    pending = false;
    if (generation !== started) return;
    cancelSaved();
    update();
    status.textContent = ok ? (selection.kind === "duplicate_stash_rows" ?
      "New copy placed; original kept in Stash." : "Saved material placed in Draft.") :
      "Placement not confirmed. Review saved references or script status before trying again.";
    focusOpener(selection.opener, selection.rowId, selection.kind);
  }

  async function insert(intent) {
    if (readOnly() || pending || !intent) return;
    cancelSaved();
    const current = captureStashNoteDrop(getDocument(), intent.noteRowId, intent.rowId, intent.beforeTokenId);
    if (JSON.stringify(current) !== JSON.stringify(intent)) {
      status.textContent = "The note or its receiving row changed. Choose the point again.";
      return;
    }
    pending = true;
    const started = generation;
    const ok = await actions.dropNote(intent.noteRowId, intent.rowId, intent.beforeTokenId);
    pending = false;
    if (generation !== started) return;
    if (ok) {
      cancelPlace();
      update();
      toggle.focus();
    }
    status.textContent = ok ? "Note copied into narration." : "Note was not inserted. See script status.";
  }

  async function runMutation(action, success, failure, rowId) {
    if (readOnly() || pending) return false;
    pending = true;
    const started = generation;
    const ok = await (typeof action === "function" ? action() : action);
    pending = false;
    if (generation !== started) return false;
    rendered = "";
    update();
    status.textContent = ok ? success : failure;
    if (rowId) focusOpener(null, rowId, "");
    return ok;
  }

  function openSavedEditor(entry) {
    if (!rowEditor || readOnly()) return;
    const model = getDocument();
    const group = entry.group && model?.stashGroups?.find((item) => item.id === entry.group.id);
    const rowIds = group?.rowIds ?? [entry.rowId];
    const rows = new Map((model?.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row])));
    const members = rowIds.map((id) => rows.get(id)).filter(Boolean);
    if (members.length !== rowIds.length) {
      status.textContent = "The saved material changed. Reopen Stash and choose it again.";
      return;
    }
    rowEditor.open({ row: entry.row, members, groupId: group?.id ?? null,
      expectedRevision: model.rowEditRevision ?? 0, expectedRowIds: rowIds, onSave: actions.saveMembers });
  }

  function sectionNameForm(sectionId = null, currentTitle = "") {
    if (readOnly()) return null;
    const formNode = make(doc, "form");
    formNode.className = "stash-section-name-form";
    const field = make(doc, "input");
    field.type = "text";
    field.required = true;
    field.maxLength = 120;
    field.value = currentTitle;
    field.setAttribute("aria-label", sectionId ? "Stash section name" : "New Stash section name");
    const save = make(doc, "button", "Save");
    save.type = "submit";
    const cancel = make(doc, "button", "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => {
      formNode.remove();
      if (sectionId) { rendered = ""; update(); }
    });
    formNode.append(field, save, cancel);
    formNode.addEventListener("submit", async (event) => {
      event.preventDefault();
      const title = field.value;
      const ok = await runMutation(() => sectionId ? actions.renameSection(sectionId, title) : actions.createSection(title),
        sectionId ? "Section renamed." : "Section added.", "Section was not saved. See script status.");
      if (ok) formNode.remove();
    });
    return formNode;
  }

  function loggedRange(snapshot) {
    const range = snapshot?.loggedSelection;
    if (!Number.isFinite(range?.exportStartMs) || !Number.isFinite(range?.exportEndMs)) return "Logged range unavailable";
    return `Logged range ${(range.exportStartMs / 1000).toFixed(3)}–${(range.exportEndMs / 1000).toFixed(3)} s`;
  }

  async function previewStashClip(snapshot, opener) {
    if (!snapshot || !loadClip) {
      status.textContent = `${snapshot?.video?.title ?? "This clip"} · ${loggedRange(snapshot)} · Playback unavailable here.`;
      return;
    }
    const started = generation;
    const owner = getDocument();
    const current = () => !root.hidden && generation === started && opener?.isConnected &&
      getDocument()?.projectId === owner?.projectId && getDocument()?.id === owner?.id;
    status.textContent = `Checking ${snapshot.video.title}…`;
    try {
      const clip = await loadClip(snapshot);
      if (!current()) return;
      if (!clip) {
        status.textContent = `${snapshot.video.title} is unavailable from Research. ${loggedRange(snapshot)}. You can still place it.`;
        return;
      }
      stashPlayer.show(clip);
      playerRoot.hidden = false;
      if (opener?.isConnected) playerRoot.querySelector("[data-footage-preview-close]")?.addEventListener("click", () => opener.focus(), { once: true });
    } catch {
      if (!current()) return;
      status.textContent = `Research could not load ${snapshot.video.title}. ${loggedRange(snapshot)}. You can still place it.`;
    }
  }

  function chooseLoggedClip(options) {
    if (!readOnly() && !pending) pickClip(options);
  }

  addSection?.addEventListener("click", () => {
    const formNode = sectionNameForm();
    if (!formNode) return;
    entries.before(formNode);
    formNode.querySelector("input")?.focus();
  });
  addClip?.addEventListener("click", () => chooseLoggedClip({ sectionId: null, from: addClip }));
  hideCompleted?.addEventListener("change", () => {
    try { localStorage.setItem("vera.authoring.stash-hide-completed", String(hideCompleted.checked)); } catch { /* Current tab preference still works. */ }
    rendered = "";
    update();
  });
  textSize?.addEventListener("input", setTextSize);

  async function saveNote(rowId, text, opener) {
    const ok = await runMutation(() => actions.editNote(rowId, text), "Note saved.", "Note was not saved. See script status.");
    if (ok) editNoteRow = null;
    rendered = "";
    update();
    focusOpener(opener, rowId, "edit-note");
  }

  function update() {
    if (root.hidden) return;
    const sections = actions.view();
    const readonly = readOnly();
    const model = getDocument();
    form.hidden = readonly;
    if (readonly && !pending) { cancelPlace(); cancelSaved(); clearDrag(); }
    const signature = JSON.stringify([readonly, sections, Boolean(hideCompleted?.checked), editNoteRow]);
    if (signature === rendered) return;
    rendered = signature;
    const previous = section.value;
    const focusedId = doc.activeElement?.closest?.("[data-stash-row-id]")?.dataset.stashRowId;
    section.replaceChildren(...sections.map((item) => {
      const option = make(doc, "option", item.title);
      option.value = item.id ?? "";
      return option;
    }));
    section.value = sections.some((item) => (item.id ?? "") === previous) ? previous : "";
    const all = sections.flatMap((item) => item.entries);
    const counts = {
      notes: all.filter((entry) => entry.kind === "note").length,
      clips: all.filter((entry) => entry.kind === "clip").length + all.filter((entry) => entry.kind === "note" && entry.row.attachedFootage?.clip).length,
      rows: all.filter((entry) => entry.kind === "row").length,
    };
    const total = counts.notes + counts.clips + counts.rows;
    const countLabel = (value, singular, plural) => `${value} ${value === 1 ? singular : plural}`;
    root.querySelector("[data-stash-count]").textContent = `· ${total} (${countLabel(counts.notes, "note", "notes")}, ${countLabel(counts.clips, "clip", "clips")}, ${countLabel(counts.rows, "saved row", "saved rows")})`;
    if (hideCompleted) hideCompleted.disabled = readonly;
    if (addSection) addSection.disabled = readonly;
    if (addClip) addClip.disabled = readonly;
    const hiddenRows = hiddenStashRows(model, Boolean(hideCompleted?.checked));
    entries.replaceChildren(...sections.map((item) => {
      const sectionNode = make(doc, "section");
      sectionNode.dataset.stashSection = item.id ?? "";
      const heading = make(doc, "div");
      heading.className = "stash-section-heading";
      heading.append(make(doc, "h3", item.title));
      if (item.id && !readonly) {
        const rename = make(doc, "button", "Rename section");
        rename.type = "button";
        rename.addEventListener("click", () => { heading.replaceChildren(sectionNameForm(item.id, item.title)); heading.querySelector("input")?.focus(); });
        const remove = make(doc, "button", "Delete section");
        remove.type = "button";
        remove.addEventListener("click", () => void runMutation(() => actions.deleteSection(item.id),
          "Section deleted; its items moved to Unsectioned.", "Section was not deleted. See script status."));
        heading.append(rename, remove);
      }
      const addNote = make(doc, "button", `Add note to ${item.title}`);
      addNote.type = "button";
      addNote.disabled = readonly;
      addNote.addEventListener("click", () => { section.value = item.id ?? ""; input.focus(); });
      heading.append(addNote);
      if (item.id && !readonly) {
        const addSectionClip = make(doc, "button", `Add clip to ${item.title}`);
        addSectionClip.type = "button";
        addSectionClip.addEventListener("click", () => chooseLoggedClip({ sectionId: item.id, from: addSectionClip }));
        heading.append(addSectionClip);
      }
      sectionNode.append(heading);
      const list = make(doc, "ul");
      list.dataset.stashDropSection = item.id ?? "";
      const parents = new Map(item.entries.map((entry) => [entry.rowId, entry.parentRowId]));
      for (const entry of item.entries) {
        if (entry.group && entry.group.index > 0) continue;
        if (hiddenRows.has(entry.rowId)) continue;
        const li = make(doc, "li");
        li.dataset.stashRowId = entry.rowId;
        li.dataset.stashKind = entry.kind;
        li.dataset.parentRowId = entry.parentRowId ?? "";
        if (entry.group) li.dataset.stashGroupId = entry.group.id;
        let depth = 0;
        for (let parent = entry.parentRowId; parent && depth < item.entries.length; parent = parents.get(parent)) depth++;
        li.style.setProperty("--stash-depth", String(Math.min(depth, 5)));
        const row = entry.row;
        const label = row.text ?? row.title ?? row.researchClip?.video?.title ?? row.researchClip?.title ?? "Saved visual";
        const actionButton = (kind, caption) => {
          const button = make(doc, "button", caption);
          button.type = "button";
          button.dataset.savedAction = kind;
          button.setAttribute("aria-label", `${caption}: ${label}`);
          button.addEventListener("click", () => chooseSaved(entry, kind, button));
          li.append(button);
        };
        if (entry.kind === "note") {
          const check = make(doc, "input");
          check.type = "checkbox";
          check.checked = row.stashChecklist?.completed === true;
          check.disabled = readonly;
          check.setAttribute("aria-label", `${check.checked ? "Mark incomplete" : "Mark complete"}: ${label}`);
          check.addEventListener("change", () => void runMutation(() => actions.setCompletion(entry.rowId, check.checked),
            check.checked ? "Note completed." : "Note reopened.", "Completion was not saved. See script status.", entry.rowId));
          const checkLabel = make(doc, "label");
          checkLabel.className = "stash-note-check";
          const noteText = make(doc, "span", label);
          noteText.className = "stash-entry-text";
          checkLabel.append(check, noteText);
          li.classList.toggle("stash-entry--completed", check.checked);
          li.append(checkLabel);
          if (!readonly) {
            const placeNote = make(doc, "button", "Place in script…");
            placeNote.type = "button";
            placeNote.setAttribute("aria-label", `Place note ${label} in script`);
            placeNote.addEventListener("click", () => choose(entry.rowId, placeNote));
            li.append(placeNote);
            const edit = make(doc, "button", "Edit note");
            edit.type = "button";
            edit.dataset.savedAction = "edit-note";
            edit.addEventListener("click", () => { editNoteRow = entry.rowId; rendered = ""; update(); entries.querySelector(`[data-stash-row-id="${entry.rowId}"] textarea`)?.focus(); });
            li.append(edit);
          }
        } else {
          li.append(make(doc, "span", entry.kind === "clip" ? "Clip · " : "Saved row · "));
          const savedText = make(doc, "span", label);
          savedText.className = "stash-entry-text";
          li.append(savedText);
        }
        if (entry.group?.index === 0) {
          li.append(make(doc, "span", `Saved group · ${entry.group.size} rows`));
          const members = item.entries.filter((candidate) => candidate.group?.id === entry.group.id);
          const memberList = make(doc, "ul");
          memberList.dataset.stashGroupMembers = entry.group.id;
          for (const member of members) {
            const memberRow = make(doc, "li", member.row.text ?? member.row.title ?? member.row.researchClip?.title ?? "Saved row");
            memberRow.dataset.stashGroupMemberId = member.rowId;
            memberList.append(memberRow);
          }
          li.append(memberList);
          if (!readonly) {
            const editGroup = make(doc, "button", "Edit group…");
            editGroup.type = "button";
            editGroup.addEventListener("click", () => openSavedEditor(entry));
            li.append(editGroup);
            const placeGroup = make(doc, "button", "Place group in script…");
            placeGroup.type = "button";
            placeGroup.dataset.savedAction = "place_stash_group";
            placeGroup.addEventListener("click", () => chooseGroup(entry, placeGroup));
            li.append(placeGroup);
          }
        } else if (!entry.group && entry.kind !== "note" && !readonly) {
          const editRow = make(doc, "button", "Edit saved row…");
          editRow.type = "button";
          editRow.addEventListener("click", () => openSavedEditor(entry));
          li.append(editRow);
        }
        if (editNoteRow === entry.rowId && entry.kind === "note") {
          const editForm = make(doc, "form");
          editForm.className = "stash-note-edit";
          const editor = make(doc, "textarea");
          editor.value = row.text ?? "";
          editor.rows = 3;
          editor.setAttribute("aria-label", `Edit note: ${label}`);
          const save = make(doc, "button", "Save note");
          save.type = "submit";
          const cancel = make(doc, "button", "Cancel");
          cancel.type = "button";
          cancel.addEventListener("click", () => { editNoteRow = null; rendered = ""; update(); focusOpener(null, entry.rowId, "edit-note"); });
          editForm.append(editor, save, cancel);
          editForm.addEventListener("submit", (event) => { event.preventDefault(); void saveNote(entry.rowId, editor.value, null); });
          editForm.addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") event.stopPropagation(); });
          li.append(editForm);
        }
        if (entry.kind === "note" && row.attachedFootage?.clip) {
          const clip = row.attachedFootage.clip;
          const clipSnapshot = clip.researchClip;
          const strip = make(doc, "div", `Attached footage · ${clipSnapshot?.video?.title ?? clip.payload?.displayName ?? "Saved clip"} · ${loggedRange(clipSnapshot)}`);
          strip.className = "stash-attached-footage";
          li.append(strip);
          if (clipSnapshot) {
            const preview = make(doc, "button", "Preview attached footage");
            preview.type = "button";
            preview.addEventListener("click", () => void previewStashClip(clipSnapshot, preview));
            li.append(preview);
          }
          if (!readonly) {
            const replace = make(doc, "button", "Choose logged clip…");
            replace.type = "button";
            replace.addEventListener("click", () => chooseLoggedClip({ noteRowId: entry.rowId, from: replace }));
            li.append(replace);
            const detach = make(doc, "button", "Detach footage");
            detach.type = "button";
            detach.addEventListener("click", () => void runMutation(() => actions.detachFootage(entry.rowId),
              "Footage detached to Stash.", "Footage was not detached. See script status.", entry.rowId));
            li.append(detach);
          }
        } else if (entry.kind === "note" && !readonly) {
          const attach = make(doc, "button", "Choose logged clip…");
          attach.type = "button";
          attach.addEventListener("click", () => chooseLoggedClip({ noteRowId: entry.rowId, from: attach }));
          li.append(attach);
        } else if (entry.kind === "clip" && row.researchClip) {
          li.append(make(doc, "span", `${loggedRange(row.researchClip)} · `));
          const preview = make(doc, "button", "Preview clip");
          preview.type = "button";
          preview.addEventListener("click", () => void previewStashClip(row.researchClip, preview));
          li.append(preview);
        }
        const origin = make(doc, "span", `Original Draft: ${entry.originalDraft.label} · ${entry.originalDraft.available ? "Original gap available" : "Choose a current gap"}`);
        origin.className = "stash-entry-origin";
        if (entry.kind !== "note" || entry.originalDraft.gap) li.append(origin);
        if (!readonly) {
          if (!entry.group && entry.kind === "note" && entry.hasDescendants) actionButton("place_stash_rows", "Place note and items below…");
          else if (!entry.group && entry.kind !== "note") {
            const needsPlacement = entry.kind !== "row" || entry.parentRowId !== null || entry.hasDescendants || Boolean(entry.group);
            actionButton(needsPlacement ? "place_stash_rows" : "restore_stash_rows", needsPlacement ? "Place in script…" : "Restore…");
            if (!entry.group && !sorting()) actionButton("duplicate_stash_rows", "Duplicate as new…");
          }
          const controls = make(doc, "div");
          controls.className = "stash-outline-controls";
          const groupIds = entry.group ? model.stashGroups?.find((group) => group.id === entry.group.id)?.rowIds ?? [] : [];
          const movingIds = groupIds.length ? groupIds : [entry.rowId];
          const first = item.entries.findIndex((candidate) => candidate.rowId === movingIds[0]);
          const sibling = (candidate) => candidate?.parentRowId === entry.parentRowId && !movingIds.includes(candidate.rowId);
          const previous = [...item.entries.slice(0, Math.max(0, first))].reverse().find(sibling);
          const next = item.entries.slice(first + movingIds.length).find(sibling);
          const prevPrev = previous && [...item.entries.slice(0, item.entries.indexOf(previous))].reverse().find(sibling);
          const move = (caption, destination) => {
            const button = make(doc, "button", caption);
            button.type = "button";
            button.disabled = !destination;
            button.addEventListener("click", () => destination && void runMutation(() => actions.moveOutline(entry.rowId, destination),
              "Stash order updated.", "Stash order was not changed. See script status.", entry.rowId));
            controls.append(button);
          };
          move("Move up", previous ? { sectionId: item.id, parentRowId: entry.parentRowId, afterRowId: prevPrev?.rowId ?? null } : null);
          move("Move down", next ? { sectionId: item.id, parentRowId: entry.parentRowId, afterRowId: next.rowId } : null);
          const parent = entry.parentRowId && item.entries.find((candidate) => candidate.rowId === entry.parentRowId);
          move("Move out", parent ? { sectionId: item.id, parentRowId: parent.parentRowId, afterRowId: parent.rowId } : null);
          const previousNote = [...item.entries.slice(0, Math.max(0, first))].reverse().find((candidate) =>
            candidate.kind === "note" && candidate.parentRowId === entry.parentRowId && !movingIds.includes(candidate.rowId));
          move("Nest under previous note", previousNote ? { sectionId: item.id, parentRowId: previousNote.rowId, afterRowId: null } : null);
          li.append(controls);
        }
        li.draggable = !readonly;
        list.append(li);
      }
      sectionNode.append(list);
      return sectionNode;
    }));
    if (focusedId && !chosen && !savedChoice) {
      const focused = [...entries.querySelectorAll("[data-stash-row-id]")].find((item) => item.dataset.stashRowId === focusedId);
      (focused?.querySelector("button, input") ?? toggle).focus();
    }
  }

  function target(event) {
    if (!drag || root.hidden || ![...(event.dataTransfer?.types ?? [])].includes(dragType)) return null;
    const model = getDocument();
    if (model?.projectId !== drag.projectId) return null;
    const editor = event.target.closest?.("[data-narration-editor]");
    const rowId = editor?.closest("[data-row-id]")?.dataset.rowId;
    const row = model.activeDraft.blocks.find((item) => item.id === rowId);
    if (!editor || row?.type !== "narration" || editor.textContent !== row.text) return null;
    const tokens = interiorTokens(row);
    // The browser resolves the pointer to the actual text offset (including
    // wrapped lines and UTF-16). Snap that caret to the nearest interior gap.
    const caret = doc.caretRangeFromPoint?.(event.clientX, event.clientY);
    if (!caret || !editor.contains(caret.startContainer) || !tokens.length) return null;
    const prefix = caret.cloneRange();
    prefix.selectNodeContents(editor);
    prefix.setEnd(caret.startContainer, caret.startOffset);
    const offset = prefix.toString().length;
    const token = tokens.reduce((best, candidate) =>
      Math.abs(candidate.startOffset - offset) < Math.abs(best.startOffset - offset) ? candidate : best);
    const intent = captureStashNoteDrop(model, drag.id, rowId, token.id);
    const rect = intent && caretRect(editor, token.startOffset);
    return rect && intent.noteSnapshot === drag.snapshot ? { intent, rect } : null;
  }

  script.addEventListener("dragover", (event) => {
    if (!drag) return;
    const next = target(event);
    marker.hidden = !next;
    preview = next?.intent ?? null;
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
    Object.assign(marker.style, { left: `${next.rect.x}px`, top: `${next.rect.y}px`, height: `${next.rect.height}px` });
  }, true);
  script.addEventListener("dragleave", () => { marker.hidden = true; });
  script.addEventListener("drop", (event) => {
    if (!drag || ![...(event.dataTransfer?.types ?? [])].includes(dragType)) return;
    event.preventDefault();
    event.stopPropagation();
    const next = event.dataTransfer.getData(dragType) === drag.id ? target(event) : null;
    const exact = next && JSON.stringify(preview) === JSON.stringify(next.intent);
    clearDrag();
    if (exact) void insert(next.intent);
    else status.textContent = "The drop point changed. Drag the note again.";
  }, true);
  toggle.addEventListener("click", () => root.hidden ? open() : close());
  root.querySelector("[data-stash-close]").addEventListener("click", () => close());
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (savedChoice) {
        const { opener, rowId, kind } = savedChoice;
        cancelSaved();
        focusOpener(opener, rowId, kind);
      } else if (chosen) { const opener = chosen.opener; cancelPlace(); opener.focus(); }
      else close();
    }
    // Native text Undo belongs to the unsaved note field, not the script.
    if (event.target === input && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") event.stopPropagation();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (readOnly() || pending || !input.value.trim()) return;
    pending = true;
    const text = input.value;
    const started = generation;
    const ok = await actions.addNote(text, { sectionId: section.value || null });
    pending = false;
    if (generation !== started) return;
    if (ok) {
      if (input.value === text) input.value = "";
      update();
    }
    status.textContent = ok ? "Note added." : "Note was not saved. See script status.";
  });
  savedPlace.addEventListener("submit", (event) => {
    event.preventDefault();
    void placeSaved();
  });
  root.querySelector("[data-stash-saved-cancel]").addEventListener("click", () => {
    if (!savedChoice) return;
    const { opener, rowId, kind } = savedChoice;
    cancelSaved();
    focusOpener(opener, rowId, kind);
  });
  place.addEventListener("submit", (event) => {
    event.preventDefault();
    if (chosen) void insert(choices[Number(destinations.value)]?.intent);
  });
  root.querySelector("[data-stash-cancel]").addEventListener("click", () => {
    const opener = chosen?.opener;
    cancelPlace();
    opener?.focus();
  });
  return { open, close, update };
}
