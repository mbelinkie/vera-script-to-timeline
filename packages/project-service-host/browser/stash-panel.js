import { captureStashNoteDrop } from "./stash-actions.js";

const dragType = "application/x-vera-stash-note";
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
export function mountStashPanel({ root, script, actions, getDocument, onOpen }) {
  const doc = root.ownerDocument;
  const toggle = doc.getElementById("open-stash");
  const form = root.querySelector("[data-stash-form]");
  const input = root.querySelector("#stash-note");
  const section = root.querySelector("#stash-section");
  const entries = root.querySelector("[data-stash-entries]");
  const status = root.querySelector("[data-stash-status]");
  const place = root.querySelector("[data-stash-place]");
  const destinations = root.querySelector("#stash-destination");
  const marker = make(doc, "span");
  marker.className = "stash-drop-cursor";
  marker.hidden = true;
  marker.setAttribute("aria-hidden", "true");
  doc.body.append(marker);
  let rendered = "";
  let drag = null;
  let preview = null;
  let choices = [];
  let chosen = null;
  let pending = false;
  let generation = 0;
  const clearDrag = () => { drag = null; preview = null; marker.hidden = true; };
  const cancelPlace = () => { chosen = null; choices = []; place.hidden = true; };

  function close(focus = true, reset = false) {
    generation += 1;
    root.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    clearDrag();
    cancelPlace();
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

  async function insert(intent) {
    if (pending || !intent) return;
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

  function update() {
    if (root.hidden) return;
    const sections = actions.view();
    const signature = JSON.stringify(sections);
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
    const counts = ["note", "clip", "row"].map((kind) =>
      `${all.filter((entry) => entry.kind === kind).length} ${kind}s`);
    root.querySelector("[data-stash-count]").textContent = `· ${all.length} (${counts.join(", ")})`;
    entries.replaceChildren(...sections.map((item) => {
      const group = make(doc, "section");
      group.dataset.stashSection = item.id ?? "";
      group.append(make(doc, "h3", item.title));
      const list = make(doc, "ul");
      const parents = new Map(item.entries.map((entry) => [entry.rowId, entry.parentRowId]));
      for (const entry of item.entries) {
        const li = make(doc, "li");
        li.dataset.stashRowId = entry.rowId;
        let depth = 0;
        for (let parent = entry.parentRowId; parent && depth < item.entries.length; parent = parents.get(parent)) depth++;
        li.style.setProperty("--stash-depth", String(Math.min(depth, 5)));
        const row = entry.row;
        const label = row.text ?? row.title ?? row.researchClip?.title ?? "Saved visual";
        const text = make(doc, "span", label);
        text.className = "stash-entry-text";
        if (entry.kind === "note") {
          const checked = make(doc, "span", row.stashChecklist?.completed ? "☑" : "☐");
          checked.setAttribute("aria-label", row.stashChecklist?.completed ? "Completed" : "Not completed");
          li.append(checked, text);
          const button = make(doc, "button", "Place in script…");
          button.type = "button";
          button.setAttribute("aria-label", `Place note ${label} in script`);
          button.addEventListener("click", () => choose(entry.rowId, button));
          li.append(button);
          li.draggable = true;
          li.addEventListener("dragstart", (event) => {
            drag = { id: entry.rowId, snapshot: JSON.stringify(row), projectId: getDocument()?.projectId };
            event.dataTransfer.setData(dragType, entry.rowId);
            event.dataTransfer.effectAllowed = "copy";
          });
          li.addEventListener("dragend", clearDrag);
        } else {
          li.append(make(doc, "span", entry.kind === "clip" ? "Clip · " : "Saved row · "), text);
        }
        list.append(li);
      }
      group.append(list);
      return group;
    }));
    if (focusedId && !chosen) {
      const focused = [...entries.querySelectorAll("[data-stash-row-id]")]
        .find((item) => item.dataset.stashRowId === focusedId);
      (focused?.querySelector("button") ?? toggle).focus();
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
      if (chosen) { const opener = chosen.opener; cancelPlace(); opener.focus(); }
      else close();
    }
    // Native text Undo belongs to the unsaved note field, not the script.
    if (event.target === input && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") event.stopPropagation();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (pending || !input.value.trim()) return;
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
