import { filterResearchLibraryItems, libraryFilterOptions } from "./research-search.js";
import { mountFootagePlayer } from "./footage-player.js";

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
      if (quote) add(quote.researchProjectId, quote.researchQuoteId, quote.researchQuoteUseId, row.id);
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

/** Sidebar & quick picker share one authorized catalog and one cancellation path. */
export function mountResearchPanel({ root, catalog, quotesCatalog = async () => ({ quotes: [], nextOffset: null }),
  quoteThumbnail, getDocument, insert, insertQuote, onPlaceQuote, gapChoices, rowChoices, onStatus }) {
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
  let clips = [];
  let quotes = [];
  let quotesNextOffset = null;
  let quoteLoadError = false;
  let clipLoadError = false;
  let accessDenied = false;
  let quoteLoadKey = null;
  let quoteSearchGeneration = 0;
  let chosen = null;
  let chosenQuote = null;
  let quoteOpenerId = "";
  let quotePreviewGeneration = 0;
  let quotePreviewUrl = null;
  let mode = "browse";
  let selection = null;
  let opener = openButton;
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
  const denyResearchAccess = () => {
    ++generation;
    ++quoteSearchGeneration;
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
    quoteLoadKey = null;
    chosen = null;
    clearQuoteChoice();
    selection = null;
    chooser.hidden = true;
    root.hidden = true;
    results.replaceChildren();
    loadMore.hidden = true;
    openButton.setAttribute("aria-expanded", "false");
    if (opener?.isConnected) opener.focus();
    else openButton.focus();
  };
  const currentUsage = () => [
    ...footageUsage(getDocument()).map((item) => ({ ...item, kind: "footage", itemId: item.clipId })),
    ...researchQuoteUsage(getDocument(), projects.value),
  ];
  const usageOf = (kind, item) => currentUsage().find((entry) =>
    entry.kind === kind && entry.researchProjectId.toLowerCase() ===
      String(kind === "quote" ? item.researchProjectId : item.projectId).toLowerCase() &&
    entry.itemId.toLowerCase() === String(kind === "quote" ? item.itemId : item.id).toLowerCase());
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
          if (placement?.kind === "selected_words") void commit(clip, selection.placement);
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
  const chooseQuoteRow = (quote) => {
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
  const render = () => {
    if (!visible) return;
    releaseQuotePreview();
    results.replaceChildren();
    chooser.hidden = !chosen;
    quoteChooser.hidden = !chosenQuote;
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
    const found = filterResearchLibraryItems(clips, quotes, usage, filters);
    const footageCount = found.filter((entry) => entry.kind === "footage").length;
    const quoteCount = found.filter((entry) => entry.kind === "quote").length;
    if (currentKind() === "all") {
      status.textContent = `${found.length} Library item${found.length === 1 ? "" : "s"} · ${footageCount} footage · ${quoteCount} quotes`;
    } else {
      const label = currentKind() === "quotes" ? "quote" : "footage";
      status.textContent = `${found.length} ${label}${found.length === 1 ? "" : "s"}`;
    }
    if (found.length) {
      for (const entry of found) entry.kind === "quote" ? renderQuote(entry.item) : renderClip(entry.item);
    } else {
      const all = filterResearchLibraryItems(clips, quotes, usage, {
        ...filters, query: "", logger: "", topic: "", seed: "", showUsed: true,
      });
      if (currentKind() === "footage" && clipLoadError) {
        status.textContent = "Saved footage is unavailable. Quotes may still be available.";
      } else if (currentKind() === "quotes" && quoteLoadError) {
        status.textContent = "Saved quotes are temporarily unavailable. Footage can still be used.";
      } else if (currentKind() === "all" && quoteLoadError && clips.length === 0) {
        status.textContent = "Quotes are temporarily unavailable. Choose Footage to retry saved clips.";
      } else if (clips.length === 0 && quotes.length === 0) {
        status.textContent = currentKind() === "quotes" ? "No saved quotes in this Research project."
          : currentKind() === "footage" ? "No saved footage in this Research project."
            : "No saved footage or quotes in this Research project.";
      } else if (hasQuoteSearch() && quotesNextOffset !== null && quoteCount === 0) {
        status.textContent = `No matches in the ${quotes.length} loaded quotes. Search more quotes to include older items.`;
      } else if (all.length && !search.value.trim() && !logger.value && !topic.value && !showUsed.checked) {
        status.textContent = "No unused items. Show used to see all Library items.";
      } else status.textContent = "No Library items match these filters.";
    }
    loadMore.hidden = quotesNextOffset === null || quoteLoadError || currentKind() === "footage";
    const loadingQuotes = quoteLoadKey === quoteSearchKey();
    loadMore.disabled = committing || loadingQuotes;
    loadMore.textContent = loadingQuotes ? "Searching quotes…" : hasQuoteSearch() ? "Search more quotes" : "Load more quotes";
    if (quoteLoadError && currentKind() !== "quotes" && currentKind() !== "footage") {
      status.textContent += " · Quotes temporarily unavailable";
    } else if (hasQuoteSearch() && quotesNextOffset !== null && !loadingQuotes && found.length) {
      status.textContent += " · More quotes are available";
    }
    if (clipLoadError && currentKind() !== "footage") status.textContent += " · Footage temporarily unavailable";
    for (const button of kindButtons) {
      const selected = button.dataset.footageKind === currentKind();
      button.setAttribute("aria-pressed", String(selected));
    }
    if (chosenQuote) quoteSelected.textContent = `Place “${String(chosenQuote.displayText || chosenQuote.text || "").slice(0, 70)}”`;
  };
  const populateFilters = () => {
    const previousLogger = logger.value;
    const previousTopic = topic.value;
    const options = libraryFilterOptions(clips, quotes);
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
  const loadMoreQuotes = async () => {
    if (quotesNextOffset === null || loadMore.dataset.loading === "true") return;
    const request = generation;
    const projectId = projects.value;
    const offset = quotesNextOffset;
    loadMore.dataset.loading = "true";
    render();
    try {
      const response = await quotesCatalog(projectId, offset);
      if (request !== generation || !visible || projectId !== projects.value) return;
      const seen = new Set(quotes.map((quote) => quote.itemId.toLowerCase()));
      quotes.push(...(Array.isArray(response.quotes) ? response.quotes : [])
        .filter((quote) => !seen.has(String(quote.itemId).toLowerCase())));
      quotesNextOffset = Number.isSafeInteger(response.nextOffset) && response.nextOffset > offset
        ? response.nextOffset : null;
      populateFilters();
      render();
    } catch {
      if (request !== generation || !visible || projectId !== projects.value) return;
      clips = [];
      quotes = [];
      quotesNextOffset = null;
      quoteLoadError = true;
      results.replaceChildren();
      render();
    } finally {
      loadMore.dataset.loading = "false";
      render();
    }
  };
  const loadProject = async () => {
    const request = ++generation;
    releaseQuotePreview();
    player.hide();
    const projectId = projects.value;
    clips = [];
    quotes = [];
    quotesNextOffset = null;
    quoteLoadError = false;
    chosen = null;
    chooser.hidden = true;
    clearQuoteChoice();
    results.replaceChildren();
    status.textContent = "Loading authorized Library items…";
    if (!projectId) { render(); return; }
    try {
      const [clipResponse, quoteResponse] = await Promise.all([
        catalog(projectId), quotesCatalog(projectId, 0),
      ]);
      if (request !== generation || !visible || projectId !== projects.value) return;
      clips = Array.isArray(clipResponse.clips) ? clipResponse.clips : [];
      quotes = Array.isArray(quoteResponse.quotes) ? quoteResponse.quotes : [];
      quotesNextOffset = Number.isSafeInteger(quoteResponse.nextOffset) && quoteResponse.nextOffset > 0
        ? quoteResponse.nextOffset : null;
      populateFilters();
      render();
    } catch {
      if (request !== generation || !visible || projectId !== projects.value) return;
      clips = [];
      quotes = [];
      quotesNextOffset = null;
      quoteLoadError = true;
      results.replaceChildren();
      render();
    }
  };
  const open = async ({ quick = false, placement = null, seed = "", from = openButton } = {}) => {
    player.hide();
    opener = from;
    mode = quick ? "quick" : "browse";
    selection = quick ? { placement, seed } : null;
    if (quick) setKind("all");
    visible = true;
    root.hidden = false;
    openButton.setAttribute("aria-expanded", "true");
    root.querySelector("[data-footage-heading]").textContent = quick ? "Choose from Library" : "Library";
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
    } catch {
      if (request === generation && visible) status.textContent = "Research projects could not be loaded. Close and retry.";
    }
  };
  const refresh = () => projects.value ? loadProject() : Promise.resolve();
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
  search.addEventListener("input", render);
  sort.addEventListener("change", render);
  logger.addEventListener("change", render);
  topic.addEventListener("change", render);
  showUsed.addEventListener("change", render);
  kindButtons.forEach((button) => button.addEventListener("click", () => {
    setKind(button.dataset.footageKind);
    render();
  }));
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
      if (!quoteChooser.hidden) { clearQuoteChoice(true); return; }
      if (!chooser.hidden) { chosen = null; chooser.hidden = true; player.hide(); search.focus(); return; }
      close();
    }
  });
  return { open, close, update: render, refresh, dropClip, dropQuote, currentProject: () => projects.value };
}
