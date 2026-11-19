import { filterLoggedResearchClips } from "./research-search.js";

const make = (doc, tag, className, content) => {
  const node = doc.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
};

/** Derived from saved placements, not a mutable catalog or a DOM count. Stash alone is not Used. */
export function footageUsage(model) {
  const entries = new Map();
  const add = (snapshot, rowId, placementId, surface) => {
    if (!snapshot?.researchProjectId || !snapshot.clipId) return;
    const key = JSON.stringify([snapshot.researchProjectId.toLowerCase(), snapshot.clipId.toLowerCase()]);
    if (!entries.has(key)) entries.set(key, { researchProjectId: snapshot.researchProjectId,
      clipId: snapshot.clipId, scriptCount: 0, stashCount: 0, scriptUses: [], stashUses: [] });
    const item = entries.get(key);
    const kind = surface === "script" ? "script" : "stash";
    item[`${kind}Count`] += 1;
    item[`${kind}Uses`].push({ rowId, placementId });
  };
  const visit = (row, surface) => {
    if (row.type === "visual_only") {
      add(row.researchClip, row.id, row.id, surface);
      for (const visual of row.additionalVisuals ?? []) add(visual.researchClip, row.id, visual.payload?.payloadId, surface);
    } else if (row.type === "narration") {
      for (const slot of row.primaryVisualSequence?.slots ?? []) {
        if (slot.kind === "content" && slot.payload?.kind === "visual")
          add(slot.payload.researchClip, row.id, slot.id, surface);
      }
      for (const loose of row.unattachedVisuals ?? []) add(loose.payload?.researchClip, row.id, loose.slotId, surface);
      for (const overlay of row.overlayEvents ?? []) add(overlay.payload?.researchClip, row.id, overlay.id, surface);
      if (row.attachedFootage?.clip?.researchClip) {
        // #589's legacy attached owner can mirror the single base primary slot.
        const clip = row.attachedFootage.clip;
        const slot = row.primaryVisualSequence?.slots?.length === 1 ? row.primaryVisualSequence.slots[0] : null;
        const payload = slot?.kind === "content" ? slot.payload : null;
        const same = (left, right) => JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
        const range = clip.visualOnlyTiming?.selectedSourceRange;
        const mirror = payload?.kind === "visual" &&
          payload.pictureKind === clip.payload?.pictureKind &&
          payload.framingPolicy === clip.payload?.framingPolicy &&
          payload.audioPolicy === (clip.payload?.audioPolicy === "quiet" ? "quiet" : "mute") &&
          same(payload.source, clip.payload?.source) && same(payload.researchClip, clip.researchClip) &&
          same(payload.frameBinding, clip.frameBinding) && same(payload.selectedSourceRange, range) &&
          same(payload.sourceUsage, range ? { sourceInFrame: range.startFrame } : null);
        if (!mirror) add(row.attachedFootage.clip.researchClip, row.id, row.attachedFootage.clip.id, surface);
      }
    }
  };
  for (const row of model?.activeDraft?.blocks ?? []) visit(row, "script");
  const parked = (model?.stash ?? []).flatMap((bundle) => bundle.rows ?? []);
  if (model?.stashOutline) {
    const byId = new Map(parked.map((row) => [row.id, row]));
    const visited = new Set();
    for (const item of model.stashOutline) {
      const row = byId.get(item.rowId);
      if (row && !visited.has(row.id)) { visit(row, "stash"); visited.add(row.id); }
    }
  } else for (const row of parked) visit(row, "stash");
  return [...entries.values()];
}

/** Sidebar & quick picker share one authorized catalog and one cancellation path. */
export function mountResearchPanel({ root, catalog, getDocument, insert, gapChoices, rowChoices, onStatus }) {
  const doc = root.ownerDocument;
  const openButton = doc.getElementById("open-footage");
  const closeButton = root.querySelector("[data-footage-close]");
  const projects = root.querySelector("[data-footage-project]");
  const search = root.querySelector("[data-footage-search]");
  const sort = root.querySelector("[data-footage-sort]");
  const showUsed = root.querySelector("[data-footage-used]");
  const results = root.querySelector("[data-footage-results]");
  const status = root.querySelector("[data-footage-status]");
  const chooser = root.querySelector("[data-footage-placement]");
  const gaps = root.querySelector("[data-footage-gaps]");
  const rows = root.querySelector("[data-footage-rows]");
  const place = root.querySelector("[data-footage-place]");
  const cancel = root.querySelector("[data-footage-cancel]");
  let visible = false;
  let generation = 0;
  let clips = [];
  let chosen = null;
  let mode = "browse";
  let selection = null;
  let opener = openButton;

  const close = () => {
    ++generation;
    visible = false;
    clips = [];
    chosen = null;
    selection = null;
    chooser.hidden = true;
    root.hidden = true;
    openButton.setAttribute("aria-expanded", "false");
    if (opener?.isConnected) opener.focus();
    else openButton.focus();
  };
  const currentUsage = () => footageUsage(getDocument());
  const usageOf = (clip) => currentUsage().find((item) =>
    item.researchProjectId.toLowerCase() === clip.projectId.toLowerCase() &&
    item.clipId.toLowerCase() === clip.id.toLowerCase());
  const jump = (rowId) => {
    const row = [...doc.querySelectorAll("#script-rows [data-row-id]")].find((item) => item.dataset.rowId === rowId);
    if (!row) return;
    row.scrollIntoView({ block: "center" });
    row.tabIndex = 0;
    row.focus();
  };
  const pickClip = (clip) => {
    chosen = clip;
    chooser.hidden = false;
    gaps.replaceChildren();
    rows.replaceChildren();
    for (const { label, destination } of gapChoices()) {
      const option = make(doc, "option", "", label);
      option.value = JSON.stringify(destination);
      gaps.append(option);
    }
    for (const { label, rowId } of rowChoices()) {
      const option = make(doc, "option", "", label);
      option.value = rowId;
      rows.append(option);
    }
    root.querySelector("[data-footage-selected]").textContent = `Place “${clip.video.title}”`;
    root.querySelector("[data-footage-gap-choice]").checked = true;
    rows.disabled = true;
    gaps.disabled = false;
    gaps.focus();
  };
  const commit = async (clip, placement) => {
    const success = await insert(clip, placement);
    if (success) { close(); onStatus("Footage added to script."); }
    else { onStatus("Footage was not added. The source or script may have changed."); update(); }
  };
  const render = () => {
    if (!visible) return;
    results.replaceChildren();
    chooser.hidden = !chosen;
    if (!projects.value) {
      status.textContent = projects.options.length > 1 ? "Choose a Research project." : "No logged Research projects are available.";
      return;
    }
    const found = filterLoggedResearchClips(clips, currentUsage(), {
      projectId: projects.value, query: search.value, showUsed: showUsed.checked, sort: sort.value,
      seed: mode === "quick" ? selection?.seed : "",
    });
    status.textContent = found.length ? `${found.length} logged clip${found.length === 1 ? "" : "s"}` :
      clips.length === 0 ? "No logged clips in this Research project." :
        showUsed.checked || search.value.trim() ? "No clips match your search." : "No unused clips. Show used to see all footage.";
    for (const clip of found) {
      const card = make(doc, "article", "footage-item");
      const title = make(doc, "button", "footage-item__title", clip.video.title);
      title.type = "button";
      title.draggable = true;
      title.dataset.footageDrag = clip.id;
      title.setAttribute("aria-label", `Choose footage: ${clip.video.title}`);
      title.addEventListener("dragstart", (event) => {
        event.dataTransfer?.setData("application/x-vera-research-clip", clip.id);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
      });
      title.addEventListener("click", () => {
        if (mode === "quick" && selection) void commit(clip, selection.placement);
        else pickClip(clip);
      });
      const transcript = make(doc, "p", "footage-item__transcript", clip.englishText || clip.selection?.text || "No saved transcript");
      const usage = usageOf(clip);
      const count = usage?.scriptCount ?? 0;
      const pill = make(doc, "span", "footage-item__usage", count ? `Used ${count}×` : "Unused");
      card.append(title, transcript, pill);
      if (count) {
        const navigation = make(doc, "div", "footage-item__links");
        for (const [index, use] of usage.scriptUses.entries()) {
          const link = make(doc, "button", "footage-item__jump", `Jump to use ${index + 1}`);
          link.type = "button";
          link.addEventListener("click", () => jump(use.rowId));
          navigation.append(link);
        }
        card.append(navigation);
      }
      results.append(card);
    }
  };
  const loadClips = async () => {
    const request = ++generation;
    const projectId = projects.value;
    clips = [];
    status.textContent = "Loading logged footage…";
    results.replaceChildren();
    chooser.hidden = true;
    chosen = null;
    if (!projectId) { render(); return; }
    try {
      const response = await catalog(projectId);
      if (request !== generation || !visible) return;
      clips = Array.isArray(response.clips) ? response.clips : [];
      render();
    } catch {
      if (request !== generation || !visible) return;
      status.textContent = "Research footage is unavailable or you do not have permission. Retry by choosing a project.";
    }
  };
  const open = async ({ quick = false, placement = null, seed = "", from = openButton } = {}) => {
    opener = from;
    mode = quick ? "quick" : "browse";
    selection = quick ? { placement, seed } : null;
    visible = true;
    root.hidden = false;
    openButton.setAttribute("aria-expanded", "true");
    root.querySelector("[data-footage-heading]").textContent = quick ? "Choose footage for words" : "Footage";
    search.value = "";
    showUsed.checked = false;
    chooser.hidden = true;
    status.textContent = "Loading Research projects…";
    const request = ++generation;
    try {
      const response = await catalog();
      if (request !== generation || !visible) return;
      const previously = projects.value;
      projects.replaceChildren(make(doc, "option", "", "Choose project…"));
      projects.firstChild.value = "";
      for (const item of response.projects ?? []) {
        const option = make(doc, "option", "", item.name);
        option.value = item.id;
        projects.append(option);
      }
      projects.value = previously && [...projects.options].some((option) => option.value === previously) ? previously :
        response.projects?.length === 1 ? response.projects[0].id : "";
      if (projects.value) await loadClips();
      else render();
      if (visible) search.focus();
    } catch {
      if (request === generation && visible) status.textContent = "Research projects could not be loaded. Close and retry.";
    }
  };
  const dropClip = (clipId) => clips.find((clip) => clip.id === clipId && clip.projectId === projects.value) ?? null;
  openButton.addEventListener("click", () => visible ? close() : void open());
  closeButton.addEventListener("click", close);
  cancel.addEventListener("click", () => { chosen = null; chooser.hidden = true; search.focus(); });
  projects.addEventListener("change", () => { void loadClips(); });
  search.addEventListener("input", render);
  sort.addEventListener("change", render);
  showUsed.addEventListener("change", render);
  root.querySelectorAll('[name="footage-destination"]').forEach((radio) => radio.addEventListener("change", () => {
    const gap = root.querySelector("[data-footage-gap-choice]").checked;
    gaps.disabled = !gap;
    rows.disabled = gap;
  }));
  place.addEventListener("click", () => {
    if (!chosen) return;
    const gap = root.querySelector("[data-footage-gap-choice]").checked;
    if (gap && gaps.value) void commit(chosen, { kind: "gap", destination: JSON.parse(gaps.value) });
    else if (!gap && rows.value) void commit(chosen, (latest) => {
      const row = latest.activeDraft.blocks.find((item) => item.id === rows.value);
      if (row?.type !== "narration") throw new Error("The narration row is no longer available.");
      return { kind: "unattached", rowId: row.id, expectedRowVersion: row.version,
        expectedSequenceVersion: row.primaryVisualSequence.version };
    });
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (!chooser.hidden) { chosen = null; chooser.hidden = true; search.focus(); }
      else close();
    }
  });
  return { open, close, update: render, dropClip, currentProject: () => projects.value };
}
