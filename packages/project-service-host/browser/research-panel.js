import { filterResearchLibraryItems, libraryFilterOptions } from "./research-search.js";
import { normalizeResearchStillPage } from "./research-still-panel.js";
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

/** Count each active Draft quote placement once, even when its words and box both retain provenance. */
export function researchQuoteUsage(model, fallbackProjectId = "") {
  const uses = new Map();
  const add = (projectId, quoteId, useId, rowId) => {
    if (!quoteId) return;
    const project = String(projectId || fallbackProjectId).toLowerCase();
    const quote = String(quoteId).toLowerCase();
    const use = String(useId || rowId || quote).toLowerCase();
    if (!project) return;
    const key = JSON.stringify([project, quote, use]);
    if (!uses.has(key)) uses.set(key, { project, quote, use, rowId });
  };
  for (const row of model?.activeDraft?.blocks ?? []) {
    if (row.type !== "narration") continue;
    for (const token of row.tokens ?? []) {
      const provenance = token.researchQuoteProvenance;
      if (provenance) add(provenance.researchProjectId, provenance.researchQuoteId, provenance.useId, row.id);
    }
    for (const event of row.overlayEvents ?? []) {
      const quote = event.quoteBox;
      if (quote) add(quote.researchProjectId || row.tokens?.find((token) =>
        token.researchQuoteProvenance?.researchQuoteId === quote.researchQuoteId &&
        token.researchQuoteProvenance?.useId === quote.researchQuoteUseId)?.researchQuoteProvenance?.researchProjectId,
      quote.researchQuoteId, quote.researchQuoteUseId, row.id);
    }
  }
  const entries = new Map();
  for (const use of uses.values()) {
    const key = JSON.stringify([use.project, use.quote]);
    if (!entries.has(key)) entries.set(key, {
      kind: "quote", researchProjectId: use.project, itemId: use.quote, scriptCount: 0, scriptUses: [],
    });
    const entry = entries.get(key);
    if (use.rowId && !entry.scriptUses.some((item) => item.rowId === use.rowId && item.useId === use.use)) {
      entry.scriptUses.push({ rowId: use.rowId, useId: use.use });
      entry.scriptCount = entry.scriptUses.length;
    }
  }
  return [...entries.values()];
}

/** Count saved Draft image occurrences, not quote pictures or parked rows. */
export function researchStillUsage(model) {
  const entries = new Map();
  const seen = new Set();
  function add(rowId, placementId, payload) {
    const still = payload?.researchStill;
    if (payload?.kind !== "visual" || !still?.researchProjectId ||
        !still.itemId || !payload.payloadId) return;
    const project = still.researchProjectId.toLowerCase();
    const item = still.itemId.toLowerCase();
    const key = JSON.stringify([project, item]);
    const occurrence = JSON.stringify([project, item, payload.payloadId.toLowerCase()]);
    if (seen.has(occurrence)) return;
    seen.add(occurrence);
    if (!entries.has(key)) entries.set(key, {
      kind: "still", researchProjectId: project, itemId: item,
      scriptCount: 0, scriptUses: [],
    });
    const entry = entries.get(key);
    entry.scriptUses.push({ rowId, placementId });
    entry.scriptCount = entry.scriptUses.length;
  }
  for (const row of model?.activeDraft?.blocks ?? []) {
    if (row.type !== "narration") continue;
    for (const slot of row.primaryVisualSequence?.slots ?? []) {
      if (slot.kind === "content") add(row.id, slot.id, slot.payload);
    }
    for (const loose of row.unattachedVisuals ?? []) add(row.id, loose.slotId, loose.payload);
    for (const overlay of row.overlayEvents ?? []) add(row.id, overlay.id, overlay.payload);
  }
  return [...entries.values()];
}

/** Sidebar & quick picker share one authorized catalog and one cancellation path. */
export function mountResearchPanel({ root, catalog, quotesCatalog = async () => ({ quotes: [], nextOffset: null }),
  quoteThumbnail, stillsCatalog = async () => ({ stills: [], nextOffset: null }), stillThumbnail,
  getDocument, insert, insertQuote, onPlaceQuote, insertStill, onPlaceStill, gapChoices, rowChoices, onStatus, onOpen }) {
  const doc = root.ownerDocument;
  const openButton = doc.getElementById("open-footage");
  const closeButton = root.querySelector("[data-footage-close]");
  const projects = root.querySelector("[data-footage-project]");
  const search = root.querySelector("[data-footage-search]");
  const sort = root.querySelector("[data-footage-sort]");
  const showUsed = root.querySelector("[data-footage-used]");
  const logger = root.querySelector("[data-footage-logger]");
  const topic = root.querySelector("[data-footage-topic]");
  const kindButtons = [...root.querySelectorAll("[data-footage-kind]")];
  const results = root.querySelector("[data-footage-results]");
  const status = root.querySelector("[data-footage-status]");
  const loadMore = root.querySelector("[data-footage-load-more]");
  const stillMore = root.querySelector("[data-still-load-more]");
  const stillChooser = root.querySelector("[data-still-placement]");
  const stillRows = root.querySelector("[data-still-rows]");
  const stillPlace = root.querySelector("[data-still-place]");
  const chooser = root.querySelector("[data-footage-placement]");
  const gaps = root.querySelector("[data-footage-gaps]");
  const rows = root.querySelector("[data-footage-rows]");
  const place = root.querySelector("[data-footage-place]");
  const cancel = root.querySelector("[data-footage-cancel]");
  const quoteChooser = root.querySelector("[data-quote-placement]");
  const quoteSelected = root.querySelector("[data-quote-selected]");
  const quoteRows = root.querySelector("[data-quote-rows]");
  const quotePlace = root.querySelector("[data-quote-place]");
  const quoteCancel = root.querySelector("[data-quote-cancel]");
  const player = mountFootagePlayer(root.querySelector("[data-footage-preview]"));
  let visible = false;
  let generation = 0;
  let stills = [];
  let stillsNextOffset = null;
  let stillLoading = false;
  let stillError = false;
  let chosenStill = null;
  const stillPreviews = new Map();
  let clips = [];
  let quotes = [];
  let quotesNextOffset = null;
  let quoteLoadError = false;
  let clipLoadError = false;
  let accessDenied = false;
  let quoteLoadKey = null;
  let quoteLoading = false;
  let quoteSearchGeneration = 0;
  let quoteSearchPages = 0;
  let searchTimer = null;
  let chosen = null;
  let chosenQuote = null;
  let quoteOpenerId = "";
  let quotePreviewGeneration = 0;
  let quotePreviewUrl = null;
  let mode = "browse";
  let selection = null;
  let opener = openButton;
  let returnToStash = null;
  let committing = false;

  const currentKind = () => kindButtons.find((button) => button.getAttribute("aria-pressed") === "true")?.dataset.footageKind ?? "all";
  const setKind = (value) => kindButtons.forEach((button) =>
    button.setAttribute("aria-pressed", String(button.dataset.footageKind === value)));
  const hasQuoteSearch = () => Boolean(search.value.trim() || logger.value || topic.value);
  const quoteSearchKey = () => JSON.stringify([projects.value, search.value.trim(), logger.value, topic.value]);
  const isDenied = (error) => [401, 403].includes(Number(error?.status ?? error?.response?.status));
  const releaseQuotePreview = () => {
    ++quotePreviewGeneration;
    if (quotePreviewUrl) URL.revokeObjectURL(quotePreviewUrl);
    quotePreviewUrl = null;
    for (const image of root.querySelectorAll("[data-quote-preview-image]")) image.remove();
    for (const cue of root.querySelectorAll("[data-quote-preview-cue]")) cue.hidden = false;
  };
  const clearQuoteChoice = (focus = false) => {
    chosenQuote = null;
    quoteChooser.hidden = true;
    quoteRows.replaceChildren();
    releaseQuotePreview();
    if (focus) {
      const button = [...root.querySelectorAll("[data-quote-place-id]")]
        .find((item) => item.dataset.quotePlaceId === quoteOpenerId);
      (button?.isConnected ? button : search).focus();
    }
  };
  const clearStillChoice = () => {
    chosenStill = null;
    stillChooser.hidden = true;
    stillRows.replaceChildren();
  };
  const resetStills = () => {
    stills = [];
    stillsNextOffset = null;
    stillLoading = false;
    stillError = false;
    clearStillChoice();
    stillMore.hidden = true;
    for (const preview of stillPreviews.values()) if (preview.url) URL.revokeObjectURL(preview.url);
    stillPreviews.clear();
  };
  const denyResearchAccess = () => {
    ++generation;
    resetStills();
    ++quoteSearchGeneration;
    quoteLoading = false;
    quoteSearchPages = 0;
    quoteLoadKey = null;
    releaseQuotePreview();
    player.hide();
    clips = [];
    quotes = [];
    quotesNextOffset = null;
    quoteLoadError = false;
    clipLoadError = false;
    accessDenied = true;
    chosen = null;
    chooser.hidden = true;
    clearQuoteChoice();
    results.replaceChildren();
    render();
  };

  const close = () => {
    ++generation;
    resetStills();
    releaseQuotePreview();
    player.hide();
    visible = false;
    clips = [];
    quotes = [];
    quotesNextOffset = null;
    quoteLoadError = false;
    clipLoadError = false;
    accessDenied = false;
    ++quoteSearchGeneration;
    quoteLoading = false;
    quoteLoadKey = null;
    clearTimeout(searchTimer);
    quoteSearchPages = 0;
    chosen = null;
    clearQuoteChoice();
    selection = null;
    chooser.hidden = true;
    root.hidden = true;
    results.replaceChildren();
    loadMore.hidden = true;
    openButton.setAttribute("aria-expanded", "false");
    const restoreStash = returnToStash;
    returnToStash = null;
    if (restoreStash) restoreStash();
    else if (opener?.isConnected) opener.focus();
    else openButton.focus();
  };
  const currentUsage = () => [
    ...footageUsage(getDocument()).map((item) => ({ ...item, kind: "footage", itemId: item.clipId })),
    ...researchQuoteUsage(getDocument(), projects.value),
    ...researchStillUsage(getDocument()),
  ];
  const usageOf = (kind, item) => currentUsage().find((entry) =>
    entry.kind === kind && entry.researchProjectId.toLowerCase() ===
      String(kind === "footage" ? item.projectId : item.researchProjectId).toLowerCase() &&
    entry.itemId.toLowerCase() === String(kind === "footage" ? item.id : item.itemId).toLowerCase());
  const renderUsageJumps = (card, usage) => {
    const count = usage?.scriptCount ?? 0;
    card.append(make(doc, "span", "footage-item__usage", count ? `Used ${count}×` : "Unused"));
    if (!count) return;
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
    if (navigation.childNodes.length) card.append(navigation);
  };
  const videoIdOf = (clip) => String(clip.video?.youtubeVideoId ?? "");
  const clipThumbnail = (clip) => {
    const media = make(doc, "div", "footage-item__thumbnail");
    const cue = make(doc, "span", "footage-item__type-cue", "▶");
    cue.setAttribute("aria-hidden", "true");
    media.append(cue);
    const videoId = videoIdOf(clip);
    if (/^[A-Za-z0-9_-]{11}$/u.test(videoId)) {
      const image = make(doc, "img");
      image.src = `https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`;
      image.alt = "";
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      image.addEventListener("load", () => { cue.hidden = true; }, { once: true });
      image.addEventListener("error", () => image.remove(), { once: true });
      media.append(image);
    }
    return media;
  };
  const previewQuote = async (quote, media, button) => {
    if (!quoteThumbnail || Number(doc.documentElement.dataset.thumbnailScale ?? 22) === 0) return;
    releaseQuotePreview();
    const request = quotePreviewGeneration;
    const projectId = projects.value;
    button.disabled = true;
    try {
      const asset = await quoteThumbnail(quote);
      if (request !== quotePreviewGeneration || !visible || projectId !== projects.value ||
          !asset || !/^image\/(?:png|jpeg|webp)$/u.test(asset.mimeType)) return;
      const image = make(doc, "img");
      image.dataset.quotePreviewImage = "";
      image.alt = "";
      const url = URL.createObjectURL(new Blob([asset.bytes], { type: asset.mimeType }));
      image.src = url;
      image.addEventListener("error", () => {
        if (quotePreviewUrl === url) {
          URL.revokeObjectURL(url);
          quotePreviewUrl = null;
        }
        image.remove();
        const cue = media.querySelector("[data-quote-preview-cue]");
        if (cue) cue.hidden = false;
      }, { once: true });
      quotePreviewUrl = url;
      media.querySelector("[data-quote-preview-cue]").hidden = true;
      media.append(image);
    } catch (error) {
      if (isDenied(error)) denyResearchAccess();
      // A quote can have no kept picture; its local quote cue remains useful.
    } finally {
      button.disabled = false;
    }
  };
  const renderQuote = (quote) => {
    const card = make(doc, "article", "footage-item footage-item--quote");
    const media = make(doc, "div", "footage-item__thumbnail footage-item__thumbnail--quote");
    const cue = make(doc, "span", "footage-item__type-cue", "“");
    cue.dataset.quotePreviewCue = "";
    cue.setAttribute("aria-hidden", "true");
    media.append(cue);
    const preview = make(doc, "button", "footage-item__preview", "Preview picture");
    preview.type = "button";
    preview.dataset.quotePicturePreview = "";
    preview.disabled = committing;
    preview.addEventListener("click", () => { void previewQuote(quote, media, preview); });
    const copy = make(doc, "div", "footage-item__copy");
    const title = quote.sourceTitle || quote.speakerName || "Research quote";
    copy.append(make(doc, "h3", "footage-item__title", title));
    copy.append(make(doc, "p", "footage-item__transcript", quote.displayText || quote.text || ""));
    const speaker = [quote.speakerName, quote.speakerTitle].filter(Boolean).join(" · ");
    if (speaker) copy.append(make(doc, "p", "footage-item__speaker", speaker));
    if (quote.sourceTitle && quote.speakerName) copy.append(make(doc, "p", "footage-item__source", "From " + quote.sourceTitle));
    if (quote.citationText) copy.append(make(doc, "p", "footage-item__citation", quote.citationText));
    const action = make(doc, "button", "footage-item__quote-place", "Place in script…");
    action.type = "button";
    action.disabled = committing;
    action.dataset.quotePlaceId = quote.itemId;
    action.draggable = true;
    action.setAttribute("aria-label", "Place quote from " + title + " in script");
    action.addEventListener("dragstart", (event) => {
      event.dataTransfer?.setData("application/x-vera-research-quote", quote.itemId);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    });
    action.addEventListener("click", () => {
      if (mode === "quick" && selection) void commitQuote(quote, selection.placement, true);
      else void placeQuoteFromCard(quote, action);
    });
    card.append(media, copy);
    renderUsageJumps(card, usageOf("quote", quote));
    card.append(preview, action);
    results.append(card);
  };
  const renderClip = (clip) => {
    const titleText = String(clip.video?.title ?? "Saved footage");
    const card = make(doc, "article", "footage-item footage-item--clip");
    const title = make(doc, "button", "footage-item__title", titleText);
    title.type = "button";
    title.disabled = committing;
    title.draggable = true;
    title.dataset.footageDrag = clip.id;
    title.setAttribute("aria-label", "Choose footage: " + titleText);
    title.addEventListener("dragstart", (event) => {
      event.dataTransfer?.setData("application/x-vera-research-clip", clip.id);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    });
    title.addEventListener("click", () => {
      if (mode === "quick" && selection) {
        try {
          const placement = typeof selection.placement === "function"
            ? selection.placement(getDocument()) : selection.placement;
          if (placement?.kind === "selected_words" || placement?.kind === "stash") void commit(clip, selection.placement);
          else pickClip(clip);
        } catch {
          onStatus("The selected script target changed. Choose the words again.");
        }
      } else pickClip(clip);
    });
    const copy = make(doc, "div", "footage-item__copy");
    copy.append(title, make(doc, "p", "footage-item__transcript",
      clip.englishText || clip.selection?.text || "No saved transcript"));
    const preview = make(doc, "button", "footage-item__preview", "Preview");
    preview.type = "button";
    preview.disabled = committing;
    preview.setAttribute("aria-label", "Preview footage: " + titleText);
    preview.addEventListener("click", () => {
      chosen = null;
      chooser.hidden = true;
      player.show(clip);
    });
    card.append(clipThumbnail(clip), copy);
    renderUsageJumps(card, usageOf("footage", clip));
    card.append(preview);
    results.append(card);
  };
  const pickClip = (clip) => {
    clearStillChoice();
    clearQuoteChoice();
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
        onStatus(placement?.kind === "stash" ? "Footage added to Stash." : "Footage added to script.");
      } else onStatus("Footage was not added. The source or script may have changed.");
    } catch {
      onStatus("Footage was not added. The source or script may have changed.");
    } finally {
      committing = false;
      place.disabled = false;
      render();
    }
  };
  const chooseQuoteRow = (quote) => {
    clearStillChoice();
    chosen = null;
    chooser.hidden = true;
    chosenQuote = quote;
    quoteSelected.textContent = `Place “${String(quote.displayText || quote.text || "").slice(0, 70)}”`;
    quoteRows.replaceChildren();
    for (const { label, rowId } of rowChoices()) {
      const option = make(doc, "option", "", label);
      option.value = rowId;
      quoteRows.append(option);
    }
    quoteChooser.hidden = false;
    if (quoteRows.options.length) quoteRows.focus();
    else status.textContent = "No narration row is available. Drag the quote onto a script target.";
  };
  const finishQuoteAttempt = async (attempt, quick) => {
    if (committing) return;
    committing = true;
    quotePlace.disabled = true;
    render();
    try {
      const success = await attempt;
      if (success) {
        onStatus(quick ? "Quote added to script." : "Quote placed in script.");
        if (quick) close();
        else {
          const placedId = chosenQuote?.itemId ?? quoteOpenerId;
          clearQuoteChoice();
          quoteOpenerId = placedId;
          render();
          const button = [...root.querySelectorAll("[data-quote-place-id]")]
            .find((item) => item.dataset.quotePlaceId === placedId);
          button?.focus();
        }
      } else onStatus("Quote was not added. The source or script may have changed.");
    } catch {
      onStatus("Quote was not added. The source or script may have changed.");
    } finally {
      committing = false;
      quotePlace.disabled = false;
      render();
    }
  };
  const placeQuoteFromCard = async (quote) => {
    quoteOpenerId = quote.itemId;
    let attempt;
    try { attempt = onPlaceQuote?.(quote); }
    catch {
      onStatus("Quote was not added. The source or script may have changed.");
      return;
    }
    if (attempt === null || attempt === undefined) {
      chooseQuoteRow(quote);
      return;
    }
    await finishQuoteAttempt(Promise.resolve(attempt), false);
  };
  const commitQuote = (quote, placement, quick = false) => {
    if (committing || !insertQuote) return;
    void finishQuoteAttempt(Promise.resolve().then(() => insertQuote(quote, placement)), quick);
  };
  const stillDragKey = (still) => JSON.stringify([generation, projects.value, still.itemId, still.itemVersion]);
  const dropStill = (key) => visible && !accessDenied && !committing &&
    selection?.placement?.kind !== "stash" ? stills.find((still) => stillDragKey(still) === key) ?? null : null;
  const renderStill = (still) => {
    const card = make(doc, "article", "footage-item footage-item--still");
    const media = make(doc, "div", "footage-item__thumbnail");
    const cue = make(doc, "span", "footage-item__type-cue", "▧");
    media.append(cue);
    const key = stillDragKey(still);
    const attach = (url) => {
      if (!media.isConnected || !url) return;
      const image = make(doc, "img");
      image.alt = "";
      image.src = url;
      image.loading = "lazy";
      image.addEventListener("load", () => { cue.hidden = true; }, { once: true });
      image.addEventListener("error", () => image.remove(), { once: true });
      media.append(image);
    };
    const copy = make(doc, "div", "footage-item__copy");
    copy.append(make(doc, "h3", "footage-item__title", still.title));
    if (still.credit) copy.append(make(doc, "p", "footage-item__source", still.credit));
    const action = make(doc, "button", "footage-item__quote-place", "Place in script…");
    action.type = "button";
    action.disabled = committing;
    action.draggable = true;
    action.dataset.stillPlaceId = still.itemId;
    action.setAttribute("aria-label", "Place still " + still.title + " in script");
    action.addEventListener("dragstart", (event) => {
      event.dataTransfer?.setData("application/x-vera-research-still", key);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    });
    action.addEventListener("click", () => {
      clearStillChoice();
      if (mode === "quick" && selection) void commitStill(still, selection.stillPlacement ?? selection.placement, true);
      else {
        const attempt = onPlaceStill?.(still);
        if (attempt != null) void finishStill(attempt, false);
        else {
          chosen = null;
          chooser.hidden = true;
          clearQuoteChoice();
          chosenStill = still;
          stillChooser.hidden = false;
          root.querySelector("[data-still-selected]").textContent = "Place " + still.title;
          stillRows.replaceChildren();
          for (const { label, rowId } of rowChoices()) {
            const option = make(doc, "option", "", label);
            option.value = rowId;
            stillRows.append(option);
          }
          stillPlace.disabled = !stillRows.options.length;
          stillRows.focus();
        }
      }
    });
    card.append(media, copy);
    renderUsageJumps(card, usageOf("still", still));
    card.append(action);
    results.append(card);
    if (!stillThumbnail || Number(doc.documentElement.dataset.thumbnailScale ?? 22) === 0) return;
    let preview = stillPreviews.get(key);
    if (!preview) {
      const request = generation;
      preview = { url: null, promise: null };
      stillPreviews.set(key, preview);
      preview.promise = Promise.resolve().then(() => stillThumbnail(still.researchProjectId, still.itemId, still.itemVersion))
        .then((asset) => {
          if (request !== generation || !visible || !/^image\/(?:png|jpeg|webp)$/u.test(asset?.mimeType)) return null;
          preview.url = URL.createObjectURL(new Blob([asset.bytes], { type: asset.mimeType }));
          return preview.url;
        }).catch((error) => {
          if (request === generation && visible && isDenied(error)) denyResearchAccess();
          return null;
        });
    }
    if (preview.url) attach(preview.url);
    else void preview.promise.then(attach);
  };
  const finishStill = async (attempt, quick) => {
    if (committing) return;
    committing = true;
    const started = generation;
    render();
    try {
      if (await attempt) {
        onStatus("Still added to script.");
        if (started === generation) {
          clearStillChoice();
          if (quick) close();
          else search.focus();
        }
      } else onStatus("Still was not added. The source or script may have changed.");
    } catch {
      onStatus("Still was not added. The source or script may have changed.");
    } finally {
      committing = false;
      render();
    }
  };
  const commitStill = (still, placement, quick = false) => {
    if (committing || !insertStill) return;
    void finishStill(Promise.resolve().then(() => insertStill(still, placement)), quick);
  };
  const render = () => {
    if (!visible) return;
    releaseQuotePreview();
    results.replaceChildren();
    chooser.hidden = !chosen;
    quoteChooser.hidden = !chosenQuote;
    stillChooser.hidden = !chosenStill;
    stillPlace.disabled = committing || !stillRows.options.length;
    if (accessDenied) {
      status.textContent = "Research access is unavailable. Choose a project to retry.";
      loadMore.hidden = true;
      return;
    }
    if (!projects.value) {
      status.textContent = projects.options.length > 1 ? "Choose a Research project." : "No authorized Research projects are available.";
      loadMore.hidden = true;
      return;
    }
    const filters = {
      kind: currentKind(), projectId: projects.value, query: search.value,
      logger: logger.value, topic: topic.value, showUsed: showUsed.checked, sort: sort.value,
      seed: mode === "quick" ? selection?.seed : "",
    };
    const usage = currentUsage();
    const found = filterResearchLibraryItems(clips, quotes, usage, filters, stills);
    const footageCount = found.filter((entry) => entry.kind === "footage").length;
    const quoteCount = found.filter((entry) => entry.kind === "quote").length;
    const stillCount = found.filter((entry) => entry.kind === "still").length;
    if (currentKind() === "all") {
      status.textContent = `${found.length} Library item${found.length === 1 ? "" : "s"} · ${footageCount} footage · ${quoteCount} quotes · ${stillCount} stills`;
    } else {
      const label = currentKind() === "quotes" ? "quote" : currentKind() === "stills" ? "still" : "footage";
      status.textContent = `${found.length} ${label}${found.length === 1 ? "" : "s"}`;
    }
    if (found.length) {
      for (const entry of found) entry.kind === "quote" ? renderQuote(entry.item) : entry.kind === "still" ? renderStill(entry.item) : renderClip(entry.item);
    } else {
      const all = filterResearchLibraryItems(clips, quotes, usage, {
        ...filters, query: "", logger: "", topic: "", seed: "", showUsed: true,
      }, stills);
      if (currentKind() === "stills" && stillError) {
        status.textContent = "Saved stills are temporarily unavailable.";
      } else if (currentKind() === "stills" && stillsNextOffset !== null) {
        status.textContent = "No matches in loaded stills. Search more stills to include older items.";
      } else if (currentKind() === "footage" && clipLoadError) {
        status.textContent = "Saved footage is unavailable. Quotes may still be available.";
      } else if (currentKind() === "quotes" && quoteLoadError) {
        status.textContent = "Saved quotes are temporarily unavailable. Footage can still be used.";
      } else if (currentKind() === "all" && quoteLoadError && clipLoadError && stillError) {
        status.textContent = "The footage and quote catalogs are temporarily unavailable.";
      } else if (currentKind() === "all" && quoteLoadError) {
        status.textContent = "Quotes are temporarily unavailable. Saved footage remains available when present.";
      } else if (clips.length === 0 && quotes.length === 0 && stills.length === 0) {
        status.textContent = currentKind() === "quotes" ? "No saved quotes in this Research project."
          : currentKind() === "footage" ? "No saved footage in this Research project."
            : currentKind() === "stills" ? "No saved stills in this Research project." : "No saved Library items in this Research project.";
      } else if (["all", "quotes"].includes(currentKind()) && quoteLoadKey === quoteSearchKey() && quoteLoading) {
        status.textContent = `Searching older quotes after ${quotes.length} loaded…`;
      } else if (["all", "quotes"].includes(currentKind()) && hasQuoteSearch() && quotesNextOffset !== null && quoteCount === 0) {
        status.textContent = `No matches in the ${quotes.length} loaded quotes. Search more quotes to include older items.`;
      } else if (all.length && !search.value.trim() && !logger.value && !topic.value && !showUsed.checked) {
        status.textContent = "No unused items. Show used to see all Library items.";
      } else status.textContent = "No Library items match these filters.";
    }
    loadMore.hidden = quotesNextOffset === null || quoteLoadError || !["all", "quotes"].includes(currentKind());
    const loadingQuotes = quoteLoading && (!quoteLoadKey || quoteLoadKey === quoteSearchKey());
    loadMore.disabled = committing || loadingQuotes;
    loadMore.textContent = loadingQuotes
      ? quoteLoadKey ? "Searching quotes…" : "Loading quotes…"
      : hasQuoteSearch() ? "Search more quotes" : "Load more quotes";
    if (quoteLoadError && currentKind() === "all") {
      status.textContent += " · Quotes temporarily unavailable";
    } else if (["all", "quotes"].includes(currentKind()) && hasQuoteSearch() && quotesNextOffset !== null && !loadingQuotes && found.length) {
      status.textContent += " · More quotes are available";
    }
    const showStills = ["all", "stills"].includes(currentKind()) && selection?.placement?.kind !== "stash";
    stillMore.hidden = !showStills || stillsNextOffset === null;
    stillMore.disabled = committing || stillLoading;
    stillMore.textContent = stillLoading ? "Loading stills…" : hasQuoteSearch() ? "Search more stills" : "Load more stills";
    if (showStills && stillsNextOffset !== null) status.textContent += " · More stills are available";
    if (showStills && stillError && currentKind() !== "stills") status.textContent += " · Stills temporarily unavailable";
    if (clipLoadError && currentKind() === "all") status.textContent += " · Footage temporarily unavailable";
    for (const button of kindButtons) {
      const selected = button.dataset.footageKind === currentKind();
      button.setAttribute("aria-pressed", String(selected));
    }
    if (chosenQuote) quoteSelected.textContent = `Place “${String(chosenQuote.displayText || chosenQuote.text || "").slice(0, 70)}”`;
  };
  const populateFilters = () => {
    const previousLogger = logger.value;
    const previousTopic = topic.value;
    const options = libraryFilterOptions(clips, quotes, stills);
    logger.replaceChildren(make(doc, "option", "", "Any logger"));
    logger.firstChild.value = "";
    for (const [id, label] of options.loggers) {
      const option = make(doc, "option", "", label);
      option.value = id;
      logger.append(option);
    }
    topic.replaceChildren(make(doc, "option", "", "Any topic"));
    topic.firstChild.value = "";
    for (const label of options.topics) {
      const option = make(doc, "option", "", label);
      option.value = label;
      topic.append(option);
    }
    logger.value = [...logger.options].some((option) => option.value === previousLogger) ? previousLogger : "";
    topic.value = [...topic.options].some((option) => option.value.toLowerCase() === previousTopic.toLowerCase())
      ? previousTopic : "";
  };
  const loadMoreQuotes = async ({ auto = false, searchRequest = null } = {}) => {
    if (quotesNextOffset === null || quoteLoading) return;
    const projectId = projects.value;
    const searchKey = hasQuoteSearch() ? quoteSearchKey() : null;
    const activeSearchRequest = searchRequest ?? ++quoteSearchGeneration;
    quoteLoadKey = searchKey;
    quoteLoading = true;
    const pageBudget = auto
      ? Math.min(5, Math.max(0, 25 - quoteSearchPages))
      : searchKey ? 5 : 1;
    render();
    for (let page = 0; page < pageBudget && quotesNextOffset !== null; page += 1) {
      const request = generation;
      const offset = quotesNextOffset;
      try {
        const response = await quotesCatalog(projectId, offset);
        if (request !== generation || activeSearchRequest !== quoteSearchGeneration || !visible ||
            projectId !== projects.value || (searchKey !== null && searchKey !== quoteSearchKey())) return;
        const seen = new Set(quotes.map((quote) => quote.itemId.toLowerCase()));
        quotes.push(...(Array.isArray(response.quotes) ? response.quotes : [])
          .filter((quote) => !seen.has(String(quote.itemId).toLowerCase())));
        quotesNextOffset = Number.isSafeInteger(response.nextOffset) && response.nextOffset > offset
          ? response.nextOffset : null;
        if (auto) quoteSearchPages += 1;
        populateFilters();
        quoteLoadError = false;
        if (auto) status.textContent = `Searching older quotes after ${quotes.length} loaded…`;
      } catch (error) {
        if (request !== generation || activeSearchRequest !== quoteSearchGeneration || !visible || projectId !== projects.value) return;
        if (isDenied(error)) denyResearchAccess();
        else {
          quoteLoadError = true;
          render();
        }
        break;
      }
    }
    if (activeSearchRequest === quoteSearchGeneration) {
      quoteLoadKey = null;
      quoteLoading = false;
    }
    render();
    if (auto && activeSearchRequest === quoteSearchGeneration && searchKey && quotesNextOffset !== null &&
        quoteSearchPages < 25 && !quoteLoadError) {
      searchTimer = setTimeout(() => {
        if (activeSearchRequest === quoteSearchGeneration && searchKey === quoteSearchKey() && visible) {
          void loadMoreQuotes({ auto: true, searchRequest: activeSearchRequest });
        }
      }, 180);
    }
  };
  const addStillPage = (response, projectId, offset) => {
    const page = normalizeResearchStillPage(response);
    const seen = new Set(stills.map((still) => still.itemId.toLowerCase()));
    for (const still of page.stills) {
      if (still.researchProjectId && still.researchProjectId.toLowerCase() !== projectId.toLowerCase()) continue;
      if (seen.has(still.itemId.toLowerCase())) continue;
      seen.add(still.itemId.toLowerCase());
      stills.push({ ...still, researchProjectId: projectId });
    }
    stillsNextOffset = page.nextOffset > offset ? page.nextOffset : null;
  };
  const loadMoreStills = async () => {
    if (stillLoading || stillsNextOffset === null) return;
    const request = generation;
    const projectId = projects.value;
    stillLoading = true;
    render();
    try {
      const offset = stillsNextOffset;
      const response = await stillsCatalog(projectId, offset);
      if (request !== generation || !visible || projectId !== projects.value) return;
      addStillPage(response, projectId, offset);
      stillError = false;
      populateFilters();
    } catch (error) {
      if (request !== generation || !visible) return;
      if (isDenied(error)) denyResearchAccess();
      else stillError = true;
    } finally {
      if (request === generation) { stillLoading = false; render(); }
    }
  };
  const loadProject = async () => {
    const request = ++generation;
    resetStills();
    ++quoteSearchGeneration;
    quoteLoading = false;
    quoteSearchPages = 0;
    quoteLoadKey = null;
    clearTimeout(searchTimer);
    releaseQuotePreview();
    player.hide();
    const projectId = projects.value;
    clips = [];
    quotes = [];
    quotesNextOffset = null;
    quoteLoadError = false;
    clipLoadError = false;
    accessDenied = false;
    chosen = null;
    chooser.hidden = true;
    clearQuoteChoice();
    results.replaceChildren();
    status.textContent = "Loading authorized Library items…";
    if (!projectId) { render(); return; }
    const [clipResult, quoteResult, stillResult] = await Promise.allSettled([
      catalog(projectId), quotesCatalog(projectId, 0),
      selection?.placement?.kind === "stash" ? Promise.resolve({ stills: [], nextOffset: null }) : stillsCatalog(projectId, 0),
    ]);
    if (request !== generation || !visible || projectId !== projects.value) return;
    const errors = [clipResult, quoteResult, stillResult].filter((result) => result.status === "rejected")
      .map((result) => result.reason);
    if (errors.some(isDenied)) { denyResearchAccess(); return; }
    if (clipResult.status === "fulfilled") {
      clips = Array.isArray(clipResult.value.clips) ? clipResult.value.clips : [];
    } else clipLoadError = true;
    if (quoteResult.status === "fulfilled") {
      quotes = Array.isArray(quoteResult.value.quotes) ? quoteResult.value.quotes : [];
      quotesNextOffset = Number.isSafeInteger(quoteResult.value.nextOffset) && quoteResult.value.nextOffset > 0
        ? quoteResult.value.nextOffset : null;
    } else quoteLoadError = true;
    if (stillResult.status === "fulfilled") addStillPage(stillResult.value, projectId, 0);
    else stillError = true;
    populateFilters();
    render();
  };
  const scheduleQuoteSearch = () => {
    ++quoteSearchGeneration;
    quoteSearchPages = 0;
    quoteLoading = false;
    quoteLoadKey = null;
    clearTimeout(searchTimer);
    render();
    if (!hasQuoteSearch() || !["all", "quotes"].includes(currentKind()) || quoteLoadError || quotesNextOffset === null) return;
    searchTimer = setTimeout(() => {
      if (visible && quotesNextOffset !== null) void loadMoreQuotes({ auto: true, searchRequest: quoteSearchGeneration });
    }, 180);
  };
  const open = async ({ quick = false, placement = null, stillPlacement = null, seed = "", from = openButton, onClose = null } = {}) => {
    onOpen?.();
    player.hide();
    opener = from;
    returnToStash = onClose;
    mode = quick ? "quick" : "browse";
    selection = quick ? { placement, stillPlacement, seed } : null;
    kindButtons.forEach((button) => { button.disabled = placement?.kind === "stash" && button.dataset.footageKind !== "footage"; });
    if (placement?.kind === "stash") {
      setKind("footage");
      search.value = "";
      showUsed.checked = true;
    } else if (quick) setKind("all");
    visible = true;
    root.hidden = false;
    openButton.setAttribute("aria-expanded", "true");
    root.querySelector("[data-footage-heading]").textContent = placement?.kind === "stash"
      ? "Choose logged footage for Stash" : quick ? "Choose from Library" : "Library";
    chooser.hidden = true;
    clearQuoteChoice();
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
      if (projects.value) await loadProject();
      else render();
      if (visible) search.focus();
    } catch (error) {
      if (request === generation && visible && isDenied(error)) denyResearchAccess();
      else if (request === generation && visible) status.textContent = "Research projects could not be loaded. Close and retry.";
    }
  };
  const refresh = () => visible && projects.value ? loadProject() : Promise.resolve();
  const dropClip = (clipId) => clips.find((clip) => clip.id === clipId &&
    clip.projectId.toLowerCase() === projects.value.toLowerCase()) ?? null;
  const dropQuote = (quoteId) => quotes.find((quote) =>
    quote.itemId.toLowerCase() === String(quoteId ?? "").toLowerCase() &&
    quote.researchProjectId.toLowerCase() === projects.value.toLowerCase()) ?? null;
  openButton.addEventListener("click", () => visible ? close() : void open());
  closeButton.addEventListener("click", close);
  cancel.addEventListener("click", () => { chosen = null; chooser.hidden = true; player.hide(); search.focus(); });
  quoteCancel.addEventListener("click", () => clearQuoteChoice(true));
  projects.addEventListener("change", () => { void loadProject(); });
  search.addEventListener("input", scheduleQuoteSearch);
  sort.addEventListener("change", render);
  logger.addEventListener("change", scheduleQuoteSearch);
  topic.addEventListener("change", scheduleQuoteSearch);
  showUsed.addEventListener("change", scheduleQuoteSearch);
  kindButtons.forEach((button) => button.addEventListener("click", () => {
    if (selection?.placement?.kind === "stash" && button.dataset.footageKind !== "footage") return;
    setKind(button.dataset.footageKind);
    scheduleQuoteSearch();
  }));
  stillMore.addEventListener("click", () => { void loadMoreStills(); });
  root.querySelector("[data-still-cancel]").addEventListener("click", () => { clearStillChoice(); search.focus(); });
  stillPlace.addEventListener("click", () => {
    if (!chosenStill || !stillRows.value || committing) return;
    const attempt = onPlaceStill?.(chosenStill, { rowId: stillRows.value });
    if (attempt != null) void finishStill(attempt, false);
  });
  loadMore.addEventListener("click", () => { void loadMoreQuotes(); });
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
  quotePlace.addEventListener("click", () => {
    if (!chosenQuote || !quoteRows.value || committing) return;
    const quote = chosenQuote;
    let attempt;
    try { attempt = onPlaceQuote?.(quote, { kind: "row-end", rowId: quoteRows.value }); }
    catch {
      onStatus("Quote was not added. The source or script may have changed.");
      return;
    }
    if (attempt === null || attempt === undefined) {
      status.textContent = "The narration row changed. Choose another row or drop the quote on a script target.";
      return;
    }
    void finishQuoteAttempt(Promise.resolve(attempt), false);
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (!stillChooser.hidden) { clearStillChoice(); search.focus(); return; }
      if (!quoteChooser.hidden) { clearQuoteChoice(true); return; }
      if (!chooser.hidden) { chosen = null; chooser.hidden = true; player.hide(); search.focus(); return; }
      close();
    }
  });
  return { open, close, update: render, refresh, dropClip, dropQuote, dropStill, currentProject: () => projects.value };
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
  if (mirror) return { snapshot: clip.researchClip, owner: clip,
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
  switch (error?.body?.error) {
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
  const selectionRail = find("selection");
  const reset = find("reset");
  const bindButton = find("bind");
  const play = find("play");
  const replay = find("replay");
  const scrub = find("scrub");
  const previous = find("previous");
  const next = find("next");
  const setIn = find("set-in");
  const setOut = find("set-out");
  const clearOut = find("clear-out");
  const feedback = find("feedback");
  const rangeLabel = find("range");
  const status = find("player-status");
  const transcript = find("transcript");
  const fullTranscript = find("transcript-full");
  const timingNote = find("timing");
  let showFullTranscript = false;
  let wordDrag = null;
  let focusWordEdge = null;
  let selected, model, occurrence, interval, basis, descriptor, lookup, lookupError, playhead, gesture;
  let frameRequest = null;
  let scrubbing = false;
  let panelPosition = null;
  let moving = null;
  let openTrim = false;
  let pending = false;
  let playing = false;
  let cardRoot = null;
  let cardScope = null;

  const selectorFor = entry => entry.selector ?? (entry.owner ? { clipRowId: entry.owner.id } : null);
  const owner = () => selectorFor(occurrence);
  const player = mountVerifiedFootagePlayer(find("player-mount"),
    (action, options) => mediaRequest(basis, owner(), action, options),
    frame => { playhead = frame; renderTransport(); highlightWord(); },
    message => { status.textContent = message; },
    value => { playing = value; renderPlayLabel(); });

  const win = root.ownerDocument.defaultView;
  function cardFor(entry) {
    return [...root.ownerDocument.querySelectorAll("[data-footage-placement]")].find(node =>
      node.dataset.footagePlacement === entry.placementId &&
      node.closest("[data-row-id]")?.dataset.rowId === entry.rowId);
  }

  const cardObserver = new win.IntersectionObserver(entries => {
    const scope = cardScope;
    if (!scope) return;
    for (const { target, isIntersecting } of entries) {
      if (!isIntersecting || !cardRoot?.contains(target)) continue;
      cardObserver.unobserve(target);
      const entry = cardEntry(target, scope);
      if (entry && !scope.cards.has(entry.key) && !scope.queue.has(entry.key)) {
        scope.queue.set(entry.key, entry);
      }
    }
    void loadCardTiming(scope);
  });

  function cardEntry(card, scope) {
    const rowId = card.closest("[data-row-id]")?.dataset.rowId;
    const placementId = card.dataset.footagePlacement;
    const entry = occurrenceFor(scope.basis.document, rowId, placementId);
    const bounds = boundInterval(entry?.owner);
    const selector = entry && selectorFor(entry);
    if (bounds && selector) return { rowId, placementId, bounds, selector, key: JSON.stringify([rowId, placementId]) };
  }

  function observeCards(editor = cardRoot, rendered = false) {
    const current = getBasis();
    if (current?.projectId !== cardScope?.basis.projectId ||
        current?.document !== cardScope?.basis.document ||
        current?.revision !== cardScope?.basis.revision ||
        current?.digest !== cardScope?.basis.digest) {
      cardScope?.controller.abort();
      cardScope = current && { basis: current, controller: new AbortController(), cards: new Map(), queue: new Map() };
    } else if (editor === cardRoot && !rendered) {
      return;
    }
    cardRoot = editor;
    scanCards();
  }

  function scanCards() {
    cardObserver.disconnect();
    const scope = cardScope;
    if (!scope || !cardRoot) return;
    for (const card of cardRoot.querySelectorAll("[data-footage-placement]")) {
      const entry = cardEntry(card, scope);
      if (!entry) continue;
      if (!scope.cards.has(entry.key)) cardObserver.observe(card);
      else writeCardTiming(card, scope.cards.get(entry.key), entry.bounds);
    }
  }

  async function loadCardTiming(scope) {
    if (scope.loading || scope.controller.signal.aborted) return;
    scope.loading = true;
    try {
      for (const [key, entry] of scope.queue) {
        if (scope !== cardScope) return;
        try {
          const result = await mediaRequest(scope.basis, entry.selector, "describe", { signal: scope.controller.signal });
          if (scope !== cardScope) return;
          scope.cards.set(key, result.transcriptTiming ?? null);
          writeCardTiming(cardFor(entry), result.transcriptTiming, entry.bounds);
        } catch (error) {
          if (scope !== cardScope) return;
          scope.cards.set(key, null);
          if (error?.body?.error === "research_media_unconfigured") {
            for (const queued of scope.queue.keys()) scope.cards.set(queued, null);
            scope.queue.clear();
            cardObserver.disconnect();
            return;
          }
        }
        scope.queue.delete(key);
      }
    } finally {
      scope.loading = false;
    }
  }

  function position() {
    if (!selected || gesture || scrubbing) return;
    const card = cardFor(selected)?.getBoundingClientRect();
    if (!card) return;
    const edge = 12;
    const width = root.offsetWidth;
    const stageBottom = root.ownerDocument.querySelector(".script-stage")?.getBoundingClientRect().bottom ?? win.innerHeight;
    const viewportBottom = Math.min(stageBottom, win.innerHeight) - edge;
    const left = card.left - width - edge;
    const preferredLeft = panelPosition?.left ?? (left >= edge ? left : card.right + edge);
    const editorTop = root.ownerDocument.querySelector(".app-bar")?.getBoundingClientRect().bottom ?? 0;
    const top = Math.max(editorTop + edge, Math.min(panelPosition?.top ?? card.top, viewportBottom - root.offsetHeight));
    const clampedLeft = Math.max(edge, Math.min(preferredLeft, win.innerWidth - width - edge));
    root.style.left = `${clampedLeft}px`;
    root.style.setProperty("--occurrence-top", `${top}px`);
    root.style.setProperty("--occurrence-stage-space", `${viewportBottom - top}px`);
    root.style.maxWidth = `${win.innerWidth - clampedLeft - edge}px`;
  }
  win.addEventListener("resize", position);
  const heading = find("preview-title").parentElement;
  heading.addEventListener("pointerdown", event => {
    if (event.button !== 0 || event.target.closest("button")) return;
    const bounds = root.getBoundingClientRect();
    moving = { x: event.clientX - bounds.x, y: event.clientY - bounds.y };
    heading.setPointerCapture(event.pointerId);
  });
  heading.addEventListener("pointermove", event => {
    if (!moving) return;
    panelPosition = { left: event.clientX - moving.x, top: event.clientY - moving.y };
    position();
  });
  heading.addEventListener("lostpointercapture", () => { moving = null; });

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
    wordDrag = focusWordEdge = null;
    showFullTranscript = false;
    pending = false;
    moving = panelPosition = null;
    invalidateMedia();
    root.style.removeProperty("width");
    root.style.removeProperty("height");
    root.style.removeProperty("max-width");
    root.hidden = true;
    if (!restoreFocus || !prior) return;
    cardFor(prior)?.querySelector("[data-inspect-footage]")?.focus();
  }

  const whole = () => interval?.start === interval?.min && interval?.end === interval?.max;
  const ready = () => Boolean(descriptor?.bound && interval && basis && !pending);
  const overlapsRange = (entry, start, end) => entry.startFrame < end && entry.endFrame > start;
  const overlapsSaved = entry => overlapsRange(entry, interval.start, interval.end);
  function writeCardTiming(card, timing, bounds) {
    const summary = card?.querySelector(".visual-card__source-transcript");
    if (!summary || !timing) return;
    const entries = timing.entries.filter(entry => overlapsRange(entry, bounds.start, bounds.end));
    summary.textContent = entries.map(entry => entry.text).join(" ") ||
      (timing.precision === "word" ? "No timed words in the selected range." : "No timed captions in the selected range.");
    summary.title = timing.precision === "cue" ? "Approximate excerpt from caption timing" : "Words in this occurrence’s saved range";
  }

  function renderCardExcerpt() {
    const timing = descriptor?.transcriptTiming;
    if (!selected || !interval || !timing) return;
    writeCardTiming(cardFor(selected), timing, interval);
  }

  function highlightWord() {
    for (const span of transcript.querySelectorAll("[data-occurrence-word]")) {
      span.toggleAttribute("data-occurrence-playing-word",
        playhead != null && Number(span.dataset.activeStart) <= playhead && playhead < Number(span.dataset.end));
    }
  }

  function bracket(edge) {
    const button = make(root.ownerDocument, "button", "occurrence-footage__word-bracket", edge === "in" ? "⟦" : "⟧");
    button.type = "button";
    button.dataset.occurrenceWordEdge = edge;
    button.setAttribute("aria-label", edge === "in" ? "Transcript in bracket" : "Transcript out bracket");
    button.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight Home End");
    return button;
  }

  function renderExcerpt() {
    const pin = occurrence.snapshot;
    const fullText = pin.englishText || pin.loggedSelection.text || "No saved transcript";
    const timing = descriptor?.transcriptTiming;
    fullTranscript.hidden = !timing || !interval || openTrim && timing.precision === "word";
    fullTranscript.textContent = showFullTranscript ? "Show trimmed transcript" : "Show full transcript";
    if (!timing || !interval) {
      const result = excerpt(null, pin.loggedSelection.exportStartMs, pin.loggedSelection.exportEndMs, fullText);
      transcript.textContent = result.text;
      timingNote.textContent = `${result.note} Showing the full transcript.`;
      return;
    }
    const selectedEntries = timing.entries.filter(overlapsSaved);
    if (timing.precision === "cue" || (showFullTranscript && !openTrim)) {
      const body = [
        selectedEntries.some(entry => entry.startFrame < interval.start) ? "…" : "",
        ...selectedEntries.map(entry => entry.text),
        selectedEntries.some(entry => entry.endFrame > interval.end) ? "…" : "",
      ].filter(Boolean).join(" ");
      transcript.textContent = showFullTranscript ? fullText : body || "No timed captions in the selected range.";
      timingNote.textContent = showFullTranscript ? "" : "Approximate excerpt from caption timing.";
      return;
    }
    const entries = openTrim ? timing.entries : selectedEntries;
    if (!entries.length) {
      transcript.textContent = "No timed words in the selected range.";
      timingNote.textContent = "";
      return;
    }
    const first = selectedEntries[0];
    const last = selectedEntries.at(-1);
    const nodes = [];
    for (const entry of entries) {
      if (openTrim && entry === first) nodes.push(bracket("in"));
      const word = make(root.ownerDocument, "button", "occurrence-footage__word", entry.text);
      word.type = "button";
      word.dataset.occurrenceWord = "";
      word.dataset.start = String(entry.startFrame);
      word.dataset.activeStart = String(entry.activeStartFrame);
      word.dataset.end = String(entry.endFrame);
      word.toggleAttribute("data-occurrence-word-outside", openTrim && !overlapsSaved(entry));
      nodes.push(word);
      if (openTrim && entry === last) nodes.push(bracket("out"));
      nodes.push(" ");
    }
    if (openTrim && !first) nodes.unshift(bracket("in"), bracket("out"), " ");
    transcript.replaceChildren(...nodes);
    timingNote.textContent = openTrim ? "Transcript brackets adjust the trim by word." : "";
    highlightWord();
    if (focusWordEdge) {
      transcript.querySelector(`[data-occurrence-word-edge="${focusWordEdge}"]`)?.focus({ preventScroll: true });
      focusWordEdge = null;
    }
  }

  fullTranscript.addEventListener("click", () => {
    showFullTranscript = !showFullTranscript;
    renderExcerpt();
  });

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
    inputIn.max = String(interval.max);
    inputOut.min = String(interval.min);
    inputOut.max = String(interval.max);
    inputIn.value = String(interval.start);
    inputOut.value = String(interval.end);
    inputIn.setAttribute("aria-valuetext", `Source frame ${interval.start}`);
    inputOut.setAttribute("aria-valuetext", `Source frame ${interval.end}, exclusive`);
    drawSelection(interval.start, interval.end);
  }

  function drawSelection(start, end) {
    const span = interval.max - interval.min;
    selectionRail.style.setProperty("--selected-start", `${(start - interval.min) / span * 100}%`);
    selectionRail.style.setProperty("--selected-end", `${(end - interval.min) / span * 100}%`);
  }

  function render() {
    const editable = ready();
    const currentOwner = owner();
    renderTransport();
    renderCardExcerpt();
    renderPlayLabel();
    toggle.textContent = openTrim ? "Hide trim" : "Trim";
    find("preview-range").textContent = openTrim ? "Full logged cut" : "Saved occurrence";
    rangeLabel.textContent = interval ?
      `Frames ${interval.start}–${interval.end} (end exclusive) · Logged ${interval.min}–${interval.max}` :
      "This occurrence has no saved frame range.";
    controls.hidden = !openTrim || !interval;
    toggle.disabled = !interval;
    bindButton.hidden = !currentOwner || Boolean(interval) ||
      !(descriptor?.bindable || lookupError?.body?.bindable);
    bindButton.disabled = pending || !basis;
    inputIn.disabled = inputOut.disabled = !editable;
    reset.disabled = !editable || whole();
    clearOut.disabled = !editable || interval?.end === interval?.max;
    find("anchor-note").hidden = !occurrence.fixedNarration;
  }

  function renderPlayLabel() {
    play.textContent = playing ? "Pause" : openTrim ? "Play logged cut" : "Play saved range";
  }

  async function describe(current) {
    const started = new AbortController();
    lookup = started;
    status.textContent = "Checking verified media…";
    try {
      const result = await mediaRequest(current, owner(), "describe", { signal: started.signal });
      if (lookup !== started) return;
      descriptor = result;
      renderExcerpt();
      status.textContent = descriptor.bound ? "" : descriptor.bindable ?
        "Bind verified media to play or trim this occurrence." :
        "Verified media binding is unavailable for this placement.";
    } catch (error) {
      if (lookup !== started) return;
      lookupError = error;
      status.textContent = mediaUnavailable(error);
    }
    render();
  }

  function update() {
    observeCards();
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
    position();
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
      if (selected === target) position();
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
    renderExcerpt();
    render();
    position();
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
    const focused = root.contains(root.ownerDocument.activeElement);
    focusWordEdge = root.ownerDocument.activeElement?.dataset?.occurrenceWordEdge ?? null;
    pending = true;
    feedback.textContent = "Saving trim…";
    render();
    if (focused && !root.contains(root.ownerDocument.activeElement)) toggle.focus();
    try {
      const ok = await commit(proof, { kind: "trim_research_clip", ...owner(), ...command });
      if (selected === target) feedback.textContent = ok ? "Trim updated." : "Trim not applied. Reopen or finish saving the script.";
    } finally {
      if (selected === target) { pending = false; resetInputs(); update(); position(); }
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
      input.value = String(input === inputIn ? Math.min(Number(input.value), interval.end - 1) :
        Math.max(Number(input.value), interval.start + 1));
      input.setAttribute("aria-valuetext", `Source frame ${input.value}${input === inputOut ? ", exclusive" : ""}`);
      drawSelection(Number(inputIn.value), Number(inputOut.value));
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
  clearOut.addEventListener("click", () => void apply({
    edge: "range", startFrame: interval.start, endFrame: interval.max,
  }, basis));
  function wordProposal(edge, frame) {
    if (!interval) return null;
    const startFrame = edge === "in" ? frame : interval.start;
    const endFrame = edge === "out" ? frame : interval.end;
    return interval.min <= startFrame && startFrame < endFrame && endFrame <= interval.max
      ? { edge: "range", startFrame, endFrame } : null;
  }

  transcript.addEventListener("click", event => {
    const word = event.target.closest("[data-occurrence-word]");
    if (!word || !ready()) return;
    const min = openTrim ? interval.min : interval.start;
    const max = openTrim ? interval.max : interval.end;
    const first = Number(word.dataset.activeStart);
    const frame = first < Number(word.dataset.end) ? first : Number(word.dataset.start);
    void playback("frame", Math.max(min, Math.min(max - 1, frame)));
  });

  function drawWordProposal(edge, proposal, target) {
    const start = proposal?.startFrame ?? interval.start;
    const end = proposal?.endFrame ?? interval.end;
    for (const word of transcript.querySelectorAll("[data-occurrence-word]")) {
      word.toggleAttribute("data-occurrence-word-outside",
        !overlapsRange({ startFrame: Number(word.dataset.start), endFrame: Number(word.dataset.end) }, start, end));
      word.toggleAttribute("data-occurrence-proposed-in", word === target && edge === "in");
      word.toggleAttribute("data-occurrence-proposed-out", word === target && edge === "out");
    }
    transcript.toggleAttribute("data-occurrence-word-drag", Boolean(target));
    drawSelection(start, end);
  }

  transcript.addEventListener("keydown", event => {
    const edge = event.target.dataset.occurrenceWordEdge;
    const timing = descriptor?.transcriptTiming;
    if (!edge || !openTrim || !ready() || timing?.precision !== "word" ||
        !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = edge === "in" ? interval.start : interval.end;
    const frames = [...new Set(timing.entries.map(entry => edge === "in" ? entry.startFrame : entry.endFrame))]
      .filter(frame => wordProposal(edge, frame)).sort((a, b) => a - b);
    const frame = event.key === "Home" ? frames[0] : event.key === "End" ? frames.at(-1) :
      event.key === "ArrowLeft" ? frames.findLast(value => value < current) : frames.find(value => value > current);
    if (frame !== undefined && frame !== current) void apply(wordProposal(edge, frame), basis);
  });

  transcript.addEventListener("pointerdown", event => {
    const edge = event.target.dataset.occurrenceWordEdge;
    if (!edge || event.button !== 0 || !openTrim || !ready()) return;
    begin();
    if (!gesture) return;
    event.target.focus({ preventScroll: true });
    event.target.setPointerCapture(event.pointerId);
    wordDrag = { edge, proposal: null };
  });
  transcript.addEventListener("pointermove", event => {
    if (!wordDrag || !gesture) return;
    const word = root.ownerDocument.elementFromPoint(event.clientX, event.clientY)?.closest("[data-occurrence-word]");
    if (!word || !transcript.contains(word)) return;
    const frame = Number(wordDrag.edge === "in" ? word.dataset.start : word.dataset.end);
    wordDrag.proposal = wordProposal(wordDrag.edge, frame);
    drawWordProposal(wordDrag.edge, wordDrag.proposal, wordDrag.proposal ? word : null);
    if (!wordDrag.proposal) { feedback.textContent = ""; return; }
    const { startFrame, endFrame } = wordDrag.proposal;
    feedback.textContent = `Proposed frames ${startFrame}–${endFrame}`;
  });
  transcript.addEventListener("pointerup", () => {
    const proof = gesture;
    const proposed = wordDrag?.proposal;
    if (!wordDrag) return;
    gesture = wordDrag = null;
    drawWordProposal(null, null, null);
    resetInputs();
    if (proposed && (proposed.startFrame !== interval.start || proposed.endFrame !== interval.end)) void apply(proposed, proof);
  });
  transcript.addEventListener("pointercancel", () => {
    if (!wordDrag) return;
    gesture = wordDrag = null;
    feedback.textContent = "";
    drawWordProposal(null, null, null);
    resetInputs();
  });
  root.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (gesture) {
        if (wordDrag) drawWordProposal(null, null, null);
        gesture = wordDrag = null;
        feedback.textContent = "";
        resetInputs();
      }
      else close();
    } else if (openTrim && !event.altKey && !event.ctrlKey && !event.metaKey &&
        ["i", "o"].includes(event.key.toLowerCase())) {
      event.preventDefault();
      setAtPlayhead(event.key.toLowerCase() === "i" ? "in" : "out");
    }
  });
  return { show, close, update, observeCards(editor) { observeCards(editor, true); } };
}
