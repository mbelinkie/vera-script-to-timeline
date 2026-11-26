import { filterLoggedResearchClips } from "./research-search.js";
import { mountFootagePlayer, mountVerifiedFootagePlayer } from "./footage-player.js";

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

function jumpToScriptUse(target, focus) {
  target.scrollIntoView({ block: "center" });
  focus.focus({ preventScroll: true });
}

export function renderFootageUseShortcuts(root, model, { focusedCard, highlightedCard }) {
  const key = (rowId, placementId) => JSON.stringify([rowId, placementId]);
  const cardKey = (card) => key(card.closest("[data-row-id]").dataset.rowId, card.dataset.footagePlacement);
  const cards = new Map([...root.querySelectorAll("[data-footage-placement]")].map((card) =>
    [cardKey(card), card]));
  if (!cards.size) return;

  const doc = root.ownerDocument;
  const rowNumbers = new Map([...root.querySelectorAll("[data-row-id]")].map((row, index) =>
    [row.dataset.rowId, index + 1]));
  const highlight = "visual-card--footage-use-target";
  for (const { scriptUses } of footageUsage(model)) {
    // Legacy attachments can exist in the Library list without a rendered script card.
    const uses = scriptUses.filter((use) => cards.has(key(use.rowId, use.placementId)));
    if (uses.length < 2) continue;
    for (const [index, use] of uses.entries()) {
      const card = cards.get(key(use.rowId, use.placementId));
      const returnsToFirst = index === uses.length - 1;
      const next = uses[(index + 1) % uses.length];
      const ordinal = `Use ${index + 1} of ${uses.length}`;
      const action = returnsToFirst ? "Back to use 1" : "Next use";
      const group = make(doc, "div", "visual-card__footage-use");
      const shortcut = make(doc, "button", "", `${action} ${returnsToFirst ? "↺" : "→"}`);
      shortcut.type = "button";
      shortcut.dataset.footageUse = "";
      shortcut.title = `${action}, row ${rowNumbers.get(next.rowId)}`;
      shortcut.setAttribute("aria-label", `${ordinal}. ${shortcut.title}`);
      shortcut.addEventListener("keydown", (event) => {
        if (event.key === "Enter") event.stopPropagation();
      });
      shortcut.addEventListener("click", (event) => {
        event.stopPropagation();
        const target = cards.get(key(next.rowId, next.placementId));
        root.querySelector(`.${highlight}`)?.classList.remove(highlight);
        target.classList.add(highlight);
        jumpToScriptUse(target, target.querySelector("[data-footage-use]"));
      });
      group.append(make(doc, "span", "", ordinal), shortcut);
      card.querySelector(".visual-card__meta").append(group);
    }
  }

  const highlighted = highlightedCard && cards.get(cardKey(highlightedCard));
  if (highlighted?.querySelector("[data-footage-use]")) highlighted.classList.add(highlight);
  const focused = focusedCard && cards.get(cardKey(focusedCard));
  (focused?.querySelector("[data-footage-use]") ?? focused)?.focus({ preventScroll: true });
}

/** Sidebar & quick picker share one authorized catalog and one cancellation path. */
export function mountResearchPanel({ root, catalog, getDocument, insert, gapChoices, rowChoices, onStatus, onOpen }) {
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
  const player = mountFootagePlayer(root.querySelector("[data-footage-preview]"));
  let visible = false;
  let generation = 0;
  let clips = [];
  let chosen = null;
  let mode = "browse";
  let selection = null;
  let opener = openButton;
  let committing = false;

  const close = () => {
    ++generation;
    player.hide();
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
  const pickClip = (clip) => {
    player.show(clip);
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
    if (committing) return;
    committing = true;
    const started = generation;
    place.disabled = true;
    render();
    try {
      const success = await insert(clip, placement);
      if (success) {
        if (generation === started) close();
        onStatus("Footage added to script.");
      } else onStatus("Footage was not added. The source or script may have changed.");
    } catch {
      onStatus("Footage was not added. The source or script may have changed.");
    } finally {
      committing = false;
      place.disabled = false;
      render();
    }
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
      title.disabled = committing;
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
      const preview = make(doc, "button", "footage-item__preview", "Preview");
      preview.type = "button";
      preview.disabled = committing;
      preview.setAttribute("aria-label", `Preview footage: ${clip.video.title}`);
      preview.addEventListener("click", () => {
        // Inspecting a different source must not leave a stale "Place" choice
        // pointing at the previously previewed clip.
        chosen = null;
        chooser.hidden = true;
        player.show(clip);
      });
      card.append(title, transcript, pill, preview);
      if (count) {
        const navigation = make(doc, "div", "footage-item__links");
        for (const [index, use] of usage.scriptUses.entries()) {
          const link = make(doc, "button", "footage-item__jump", `Jump to use ${index + 1}`);
          link.type = "button";
          link.addEventListener("click", () => {
            const row = [...doc.querySelectorAll("#script-rows [data-row-id]")]
              .find((item) => item.dataset.rowId === use.rowId);
            if (!row) return;
            row.tabIndex = 0;
            jumpToScriptUse(row, row);
          });
          navigation.append(link);
        }
        card.append(navigation);
      }
      results.append(card);
    }
  };
  const loadClips = async () => {
    const request = ++generation;
    player.hide();
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
    onOpen?.();
    player.hide();
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
  const dropClip = (clipId) => clips.find((clip) => clip.id === clipId &&
    clip.projectId.toLowerCase() === projects.value.toLowerCase()) ?? null;
  openButton.addEventListener("click", () => visible ? close() : void open());
  closeButton.addEventListener("click", close);
  cancel.addEventListener("click", () => { chosen = null; chooser.hidden = true; player.hide(); search.focus(); });
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
    if (!chosen || committing) return;
    const gap = root.querySelector("[data-footage-gap-choice]").checked;
    if (gap && gaps.value) void commit(chosen, { kind: "gap", destination: JSON.parse(gaps.value) });
    else if (!gap && rows.value) {
      const rowId = rows.value;
      void commit(chosen, (latest) => {
        const row = latest.activeDraft.blocks.find((item) => item.id === rowId);
        if (row?.type !== "narration") throw new Error("The narration row is no longer available.");
        return { kind: "unattached", rowId: row.id, expectedRowVersion: row.version,
          expectedSequenceVersion: row.primaryVisualSequence.version };
      });
    }
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (!chooser.hidden) { chosen = null; chooser.hidden = true; player.hide(); search.focus(); }
      else close();
    }
  });
  return { open, close, update: render, dropClip, currentProject: () => projects.value };
}

// Resolve the rendered card against the current document, never against a
// catalog candidate. Resolve an attached mirror to its one authoritative owner.
function occurrenceFor(model, rowId, placementId) {
  const row = model?.activeDraft?.blocks.find(item => item.id === rowId);
  if (row?.type === "visual_only") {
    if (row.id === placementId) return { snapshot: row.researchClip, owner: row };
    const visual = row.additionalVisuals?.find(item => item.payload.payloadId === placementId);
    return visual && { snapshot: visual.researchClip };
  }
  if (row?.type !== "narration") return null;
  const slots = row.primaryVisualSequence?.slots ?? [];
  const slot = slots.find(item => item.id === placementId && item.kind === "content");
  const waiting = row.unattachedVisuals?.find(item => item.slotId === placementId);
  const payload = slot?.payload ?? waiting?.payload ??
    row.overlayEvents?.find(item => item.id === placementId)?.payload;
  const clip = row.attachedFootage?.clip;
  const range = clip?.visualOnlyTiming?.selectedSourceRange;
  const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
  const mirror = clip && slot && slots.length === 1 && payload?.kind === "visual" &&
    payload.pictureKind === clip.payload.pictureKind &&
    payload.framingPolicy === clip.payload.framingPolicy &&
    payload.audioPolicy === (clip.payload.audioPolicy === "quiet" ? "quiet" : "mute") &&
    same(payload.source, clip.payload.source) && same(payload.researchClip, clip.researchClip) &&
    same(payload.frameBinding, clip.frameBinding) && same(payload.selectedSourceRange, range) &&
    same(payload.sourceUsage, range ? { sourceInFrame: range.startFrame } : null);
  if (mirror) return { snapshot: clip.researchClip, owner: clip, attachment: true,
    fixedNarration: slot.playoutPolicy === "match_structural_interval" };
  if ((slot || waiting) && payload?.kind === "visual") return {
    snapshot: payload.researchClip,
    selector: { payloadId: payload.payloadId },
    owner: { researchClip: payload.researchClip, payload, frameBinding: payload.frameBinding,
      visualOnlyTiming: { selectedSourceRange: payload.selectedSourceRange } },
    fixedNarration: slot?.playoutPolicy === "match_structural_interval",
  };
  return { snapshot: payload?.researchClip };
}

function boundInterval(owner) {
  const b = owner?.frameBinding;
  const s = owner?.visualOnlyTiming?.selectedSourceRange;
  const pin = owner?.researchClip;
  if (!b || !s || !pin || b.clipId !== pin.clipId || b.clipVersion !== pin.clipVersion ||
    owner.payload.pictureKind !== "clip" || owner.payload.source.kind !== "media_reference" ||
    owner.payload.source.mediaReferenceId !== b.mediaReferenceId ||
    ![b.loggedStartFrame, b.loggedEndFrame, s.startFrame, s.durationFrames,
      s.startFrame + s.durationFrames].every(Number.isSafeInteger) ||
    b.loggedStartFrame < 0 || s.startFrame < b.loggedStartFrame || s.durationFrames <= 0 ||
    s.startFrame + s.durationFrames > b.loggedEndFrame) return null;
  return { min: b.loggedStartFrame, max: b.loggedEndFrame, start: s.startFrame, end: s.startFrame + s.durationFrames };
}

const mediaUnavailable = error => {
  switch (error?.body) {
    case "research_media_missing": return "Verified media is missing. Prepare media or restore the cut, then reopen this footage.";
    case "research_media_unconfigured": return "Verified media is unavailable for this project.";
    case "research_media_changed":
    case "research_pin_changed": return "The Research cut changed. Resolve the saved footage before playing it.";
    case "research_media_stale": return "The saved script changed. Reopen this footage.";
    default: return error?.status === 403 ? "You do not have access to this footage."
      : "Verified playback is unavailable for this footage.";
  }
};

export function mountOccurrenceFootage({ root, getDocument, getBasis, commit, mediaRequest, bind, excerpt }) {
  const find = name => root.querySelector(`[data-occurrence-${name}]`);
  const toggle = find("toggle");
  const controls = root.querySelector("#occurrence-trim-controls");
  const inputIn = find("in");
  const inputOut = find("out");
  const reset = find("reset");
  const bindButton = find("bind");
  const play = find("play");
  const replay = find("replay");
  const scrub = find("scrub");
  const previous = find("previous");
  const next = find("next");
  const setIn = find("set-in");
  const setOut = find("set-out");
  const feedback = find("feedback");
  const rangeLabel = find("range");
  const status = find("player-status");
  let selected, model, occurrence, interval, basis, descriptor, lookup, lookupError, playhead, gesture;
  let frameRequest = null;
  let scrubbing = false;
  let openTrim = false;
  let pending = false;

  const owner = () => occurrence.selector ?? (occurrence.owner ? { clipRowId: occurrence.owner.id } : null);
  const player = mountVerifiedFootagePlayer(find("player-mount"),
    (action, options) => mediaRequest(basis, owner(), action, options),
    frame => { playhead = frame; renderTransport(); },
    message => { status.textContent = message; });

  function invalidateMedia() {
    lookup?.abort();
    lookup = null;
    basis = descriptor = lookupError = playhead = null;
    frameRequest = null;
    scrubbing = false;
    player.clear();
  }

  function close(restoreFocus = true) {
    const prior = selected;
    selected = null;
    gesture = null;
    pending = false;
    invalidateMedia();
    root.hidden = true;
    if (!restoreFocus || !prior) return;
    const card = [...root.ownerDocument.querySelectorAll("[data-footage-placement]")].find(node =>
      node.dataset.footagePlacement === prior.placementId &&
      node.closest("[data-row-id]")?.dataset.rowId === prior.rowId);
    card?.querySelector("[data-inspect-footage]")?.focus();
  }

  const whole = () => interval?.start === interval?.min && interval?.end === interval?.max;
  const ready = () => Boolean(descriptor?.bound && interval && basis && !pending);
  function renderExcerpt() {
    const pin = occurrence.snapshot;
    const fullText = pin.englishText || pin.loggedSelection.text || "No saved transcript";
    const result = excerpt(null, pin.loggedSelection.exportStartMs, pin.loggedSelection.exportEndMs, fullText);
    find("transcript").textContent = result.text;
    find("timing").textContent = `${result.note} Showing the full transcript.`;
  }

  function renderTransport() {
    const enabled = ready();
    play.disabled = !enabled;
    replay.hidden = !enabled;
    previous.setAttribute("aria-disabled", String(!enabled || frameRequest !== null || (playhead ?? interval?.min) <= interval?.min));
    next.setAttribute("aria-disabled", String(!enabled || frameRequest !== null || (playhead ?? interval?.min) >= interval?.max - 1));
    scrub.disabled = !enabled;
    setIn.disabled = !enabled || playhead == null || playhead >= interval?.end || playhead === interval?.start;
    setOut.disabled = !enabled || playhead == null || playhead <= interval?.start || playhead === interval?.end;
    if (interval) {
      scrub.min = String(interval.min);
      scrub.max = String(interval.max - 1);
      if (!scrubbing) scrub.value = String(playhead ?? interval.min);
    }
    find("playhead").textContent = playhead == null ? "" : `Frame ${playhead}`;
  }

  function resetInputs() {
    if (!interval) return;
    inputIn.min = String(interval.min);
    inputIn.max = String(interval.end - 1);
    inputOut.min = String(interval.start + 1);
    inputOut.max = String(interval.max);
    inputIn.value = String(interval.start);
    inputOut.value = String(interval.end);
    inputIn.setAttribute("aria-valuetext", `Source frame ${interval.start}`);
    inputOut.setAttribute("aria-valuetext", `Source frame ${interval.end}, exclusive`);
  }

  function render() {
    const editable = ready();
    const currentOwner = owner();
    renderTransport();
    play.textContent = openTrim ? "Play logged cut" : "Play saved range";
    find("preview-range").textContent = openTrim ? "Full logged cut" : "Saved occurrence";
    rangeLabel.textContent = interval ?
      `Frames ${interval.start}–${interval.end} (end exclusive) · Logged ${interval.min}–${interval.max}` :
      "This occurrence has no saved frame range.";
    controls.hidden = !openTrim || !interval;
    toggle.disabled = !interval;
    bindButton.hidden = !currentOwner || occurrence.attachment || Boolean(interval) ||
      !(descriptor || lookupError?.body === "research_media_missing");
    bindButton.disabled = pending || !basis;
    inputIn.disabled = inputOut.disabled = !editable;
    reset.disabled = !editable || whole();
    find("anchor-note").hidden = !occurrence.fixedNarration;
  }

  async function describe(current) {
    const started = new AbortController();
    lookup = started;
    status.textContent = "Checking verified media…";
    try {
      const result = await mediaRequest(current, owner(), "describe", { signal: started.signal });
      if (lookup !== started) return;
      descriptor = result;
      status.textContent = descriptor.bound ? "" : occurrence.attachment ?
        "This attached occurrence needs an existing verified media binding." :
        "Bind verified media to play or trim this occurrence.";
    } catch (error) {
      if (lookup !== started) return;
      lookupError = error;
      status.textContent = mediaUnavailable(error);
    }
    render();
  }

  function update() {
    if (!selected) return;
    const current = getDocument();
    if (current?.projectId !== model?.projectId) { close(false); return; }
    const nextBasis = getBasis();
    if (current !== model || basis?.revision !== nextBasis?.revision || basis?.digest !== nextBasis?.digest) {
      const nextOccurrence = occurrenceFor(current, selected.rowId, selected.placementId);
      if (!nextOccurrence?.snapshot) { close(false); return; }
      model = current;
      occurrence = nextOccurrence;
      interval = boundInterval(occurrence.owner);
      gesture = null;
      invalidateMedia();
      basis = nextBasis;
      resetInputs();
      renderExcerpt();
      if (basis && owner()) void describe(basis);
      else status.textContent = pending ? "" : owner() ?
        "Finish saving before inspecting verified media." : "Verified playback is unavailable for this placement.";
    }
    render();
  }

  function show(rowId, placementId) {
    close(false);
    const current = getDocument();
    occurrence = occurrenceFor(current, rowId, placementId);
    if (!occurrence?.snapshot) return;
    openTrim = false;
    selected = { rowId, placementId };
    root.hidden = false;
    toggle.setAttribute("aria-expanded", "false");
    feedback.textContent = "";
    find("preview-title").textContent = occurrence.snapshot.video.title;
    model = current;
    interval = boundInterval(occurrence.owner);
    basis = getBasis();
    status.textContent = !owner() ? "Verified playback is unavailable for this placement." :
      "Finish saving before inspecting verified media.";
    if (basis && owner()) void describe(basis);
    resetInputs();
    renderExcerpt();
    render();
    (toggle.disabled ? find("preview-close") : toggle).focus();
  }

  async function playback(action, frame) {
    if (!ready()) return;
    const target = selected;
    const savedBasis = basis;
    const bounds = action === "saved" ? interval : { start: interval.min, end: interval.max };
    const stepping = action === "frame" ? Symbol() : null;
    frameRequest = stepping;
    try {
      await player.load(action, bounds, descriptor.sourceFrameMap.decodedPackageFrameRate, frame);
    } catch (error) {
      if (selected === target && basis === savedBasis) status.textContent = mediaUnavailable(error);
    } finally {
      if (stepping !== null && frameRequest === stepping) {
        frameRequest = null;
        renderTransport();
      }
    }
  }
  play.addEventListener("click", () => {
    if (!player.toggle()) void playback(openTrim ? "logged" : "saved");
  });
  replay.addEventListener("click", () => void playback(openTrim ? "logged" : "saved"));
  find("preview-close").addEventListener("click", () => close());
  for (const [button, step] of [[previous, -1], [next, 1]]) {
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-disabled") === "false") void playback("frame", (playhead ?? interval.min) + step);
    });
  }
  scrub.addEventListener("pointerdown", () => { scrubbing = true; });
  scrub.addEventListener("pointerup", () => { scrubbing = false; });
  scrub.addEventListener("pointercancel", () => { scrubbing = false; renderTransport(); });
  scrub.addEventListener("change", () => {
    scrubbing = false;
    void playback("frame", Number(scrub.value));
  });
  // Space or Enter on the rail decodes its current frame, including frame zero.
  scrub.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void playback("frame", Number(scrub.value));
    }
  });
  toggle.addEventListener("click", () => {
    openTrim = !openTrim;
    gesture = null;
    feedback.textContent = "";
    player.clear();
    frameRequest = null;
    scrubbing = false;
    playhead = null;
    toggle.setAttribute("aria-expanded", String(openTrim));
    resetInputs();
    render();
  });

  bindButton.addEventListener("click", async () => {
    if (!basis || pending || !owner()) return;
    const target = selected;
    pending = true;
    feedback.textContent = "Binding verified footage…";
    try {
      const ok = await bind(basis, owner());
      if (selected === target) feedback.textContent = ok ? "Verified footage bound." : "The binding could not be saved.";
    } catch (error) {
      if (selected === target) feedback.textContent = mediaUnavailable(error);
    } finally {
      if (selected === target) { pending = false; update(); }
    }
  });

  const begin = () => {
    if (!gesture && ready()) gesture = basis;
  };
  async function apply(command, proof) {
    if (!selected || !proof || basis !== proof || !ready() || getDocument() !== model) {
      resetInputs();
      return;
    }
    const target = selected;
    pending = true;
    feedback.textContent = "Saving trim…";
    render();
    try {
      const ok = await commit(proof, { kind: "trim_research_clip", ...owner(), ...command });
      if (selected === target) feedback.textContent = ok ? "Trim updated." : "Trim not applied. Reopen or finish saving the script.";
    } finally {
      if (selected === target) { pending = false; resetInputs(); update(); }
    }
  }

  function setAtPlayhead(edge) {
    if (!openTrim || !ready() || playhead == null) return;
    const startFrame = edge === "in" ? playhead : interval.start;
    const endFrame = edge === "out" ? playhead : interval.end;
    if (startFrame < endFrame && (startFrame !== interval.start || endFrame !== interval.end)) {
      void apply({ edge: "range", startFrame, endFrame }, basis);
    }
  }
  setIn.addEventListener("click", () => setAtPlayhead("in"));
  setOut.addEventListener("click", () => setAtPlayhead("out"));
  for (const input of [inputIn, inputOut]) {
    input.addEventListener("pointerdown", begin);
    input.addEventListener("keydown", event => {
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) begin();
    });
    input.addEventListener("input", () => {
      if (!gesture) { resetInputs(); return; }
      input.setAttribute("aria-valuetext", `Source frame ${input.value}${input === inputOut ? ", exclusive" : ""}`);
      feedback.textContent = `Proposed frames ${inputIn.value}–${inputOut.value} (not yet saved)`;
    });
    const cancel = () => {
      if (gesture) feedback.textContent = "";
      gesture = null;
      resetInputs();
    };
    input.addEventListener("pointercancel", cancel);
    input.addEventListener("blur", cancel);
    input.addEventListener("keyup", () => { if (gesture) cancel(); });
    input.addEventListener("change", () => {
      const proof = gesture;
      gesture = null;
      const startFrame = Number(inputIn.value), endFrame = Number(inputOut.value);
      if (interval && (startFrame !== interval.start || endFrame !== interval.end)) {
        void apply({ edge: "range", startFrame, endFrame }, proof);
      }
    });
  }
  reset.addEventListener("click", () => void apply({ edge: "reset" }, basis));
  root.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (gesture) { gesture = null; feedback.textContent = ""; resetInputs(); }
      else close();
    } else if (openTrim && !event.altKey && !event.ctrlKey && !event.metaKey &&
        ["i", "o"].includes(event.key.toLowerCase())) {
      event.preventDefault();
      setAtPlayhead(event.key.toLowerCase() === "i" ? "in" : "out");
    }
  });
  return { show, close, update };
}
