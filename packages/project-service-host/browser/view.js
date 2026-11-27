const visualKinds = {
  undefined: { label: "Visual undefined", art: "placeholder" },
  clip: { label: "Footage", art: "clip" },
  image: { label: "Still image", art: "image" },
  capture: { label: "Web capture", art: "capture" },
  graphic: { label: "Graphic", art: "graphic" },
  intentional_placeholder: { label: "Onscreen placeholder", art: "placeholder" },
  unresolved_visual: { label: "Need to find", art: "placeholder" },
};

function makeElement(document, tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function localImageSource(document, payload) {
  const source = payload && payload.source;
  if (!source || source.kind !== "url" || typeof source.url !== "string") return null;

  try {
    const base = new URL(document.baseURI);
    const url = new URL(source.url, base);
    if ((url.protocol !== "http:" && url.protocol !== "https:") || url.origin !== base.origin) return null;
    return url.href;
  } catch {
    return null;
  }
}

function visualKind(payload) {
  if (!payload || payload.kind !== "visual") return "undefined";
  return visualKinds[payload.pictureKind] ? payload.pictureKind : "unresolved_visual";
}

function visualLabel(payload, researchClip) {
  if (payload && payload.kind === "on_camera") {
    return "On Camera · " + (payload.framing === "tight" ? "Tight" : "Wide");
  }

  if (payload && payload.kind === "undefined") {
    return typeof payload.description === "string" && payload.description.trim()
      ? payload.description.trim()
      : "Visual undefined";
  }

  const source = payload && payload.source;
  if (source && typeof source.text === "string" && source.text.trim()) return source.text.trim();
  if (source && typeof source.description === "string" && source.description.trim()) return source.description.trim();
  if (researchClip && researchClip.video && typeof researchClip.video.title === "string") {
    return researchClip.video.title;
  }
  if (payload?.researchStill && typeof payload.researchStill.title === "string" &&
      payload.researchStill.title.trim()) {
    return payload.researchStill.title.trim();
  }
  if (payload && typeof payload.title === "string" && payload.title.trim()) return payload.title.trim();

  const kind = visualKinds[visualKind(payload)];
  return kind ? kind.label : "Visual";
}

function appendVisualImage(document, target, src, label, artKind) {
  if (!src) {
    target.append(makePlaceholderArt(document, label, artKind));
    return;
  }

  const image = document.createElement("img");
  image.src = src;
  image.alt = "";
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => {
    image.replaceWith(makePlaceholderArt(document, label, artKind));
  }, { once: true });
  target.append(image);
}

function loadQuotePicture(media, payloadId, label, artKind, loader) {
  media.dataset.quotePictureMedia = "";
  let active = true;
  let objectUrl = null;
  const cleanup = () => {
    active = false;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  };
  media.__veraQuotePictureCleanup = cleanup;
  void Promise.resolve().then(() => loader(payloadId)).then((asset) => {
    if (!active || !asset || !/^image\/(?:png|jpeg|webp)$/u.test(asset.mimeType)) return;
    const image = media.ownerDocument.createElement("img");
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    objectUrl = URL.createObjectURL(new Blob([asset.bytes], { type: asset.mimeType }));
    image.src = objectUrl;
    image.addEventListener("error", () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
      if (active) {
        image.replaceWith(makePlaceholderArt(media.ownerDocument, label, artKind));
      }
    }, { once: true });
    if (active) media.replaceChildren(image);
    else URL.revokeObjectURL(objectUrl);
  }).catch(() => undefined);
}

function releaseQuotePictures(root) {
  for (const media of root.querySelectorAll("[data-quote-picture-media]")) {
    media.__veraQuotePictureCleanup?.();
  }
}

function makePlaceholderArt(document, label, artKind) {
  const art = makeElement(document, "div", "visual-art visual-art--" + artKind);
  art.setAttribute("aria-hidden", "true");
  art.append(makeElement(document, "span", "visual-art__caption", label));
  return art;
}

function onCameraControls(document, blockId, slotId, framing, visualCommand) {
  const group = makeElement(document, "div", "visual-card__framing");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "On Camera framing");
  for (const value of ["wide", "tight"]) {
    const button = makeElement(document, "button", "visual-card__framing-choice", value === "wide" ? "Wide" : "Tight");
    button.type = "button";
    button.dataset.visualFraming = value;
    button.setAttribute("aria-pressed", String(framing === value));
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      void visualCommand({ kind: "set_on_camera_framing", blockId, slotId, framing: value },
        `Set On Camera ${value === "wide" ? "Wide" : "Tight"}`);
    });
    group.append(button);
  }
  return group;
}

function renderVisualCard(document, payload, researchClip, options = {}) {
  const { blockId, slotId, framing, visualCommand, reselect } = options;
  const quoteBox = options.quoteBox;
  const isOnCamera = payload?.kind === "on_camera";
  const kind = visualKind(payload);
  const definition = visualKinds[kind];
  const kindLabel = quoteBox ? "Quote Box" : payload && payload.kind === "on_camera"
    ? "On Camera"
    : payload && payload.kind === "undefined"
      ? "Visual undefined"
      : definition.label;
  const label = visualLabel(payload, researchClip);
  const imageSource = localImageSource(document, payload);
  // Even source-free visuals have a sample tile at 0% thumbnail size.
  const previewable = true;

  const card = makeElement(document, "figure", "visual-card");
  card.dataset.kind = payload && payload.kind === "on_camera"
    ? "on-camera"
    : payload && payload.kind === "undefined"
      ? "undefined"
      : definition.art;
  card.dataset.previewable = String(previewable);
  card.dataset.slotId = options.slotId ?? "";
  if (options.payloadId) card.dataset.payloadId = options.payloadId;
  if (options.overlayId) card.dataset.overlayId = options.overlayId;
  if (researchClip && options.footagePlacementId) card.dataset.footagePlacement = options.footagePlacementId;
  if (options.draggable && payload?.kind === "visual") {
    card.draggable = true;
    card.dataset.visualDrag = "";
    card.title = options.payloadId ? "Reorder in this row" : "Drag visual to another row";
  }
  if (options.startTokenIndex !== undefined) card.dataset.cueStart = String(options.startTokenIndex);
  if (options.flash) card.classList.add("visual-card--moved");
  card.setAttribute("aria-label", kindLabel + ": " + (quoteBox?.displayText || label));
  if (previewable) card.tabIndex = 0;

  const media = makeElement(document, "div", "visual-card__image");
  media.setAttribute("aria-hidden", "true");
  appendVisualImage(document, media, imageSource, label, definition.art);
  if (!imageSource && payload?.researchQuotePicture && typeof options.quotePicture === "function") {
    loadQuotePicture(media, payload.payloadId, label, definition.art, options.quotePicture);
  }
  card.append(media);

  const meta = makeElement(document, "figcaption", "visual-card__meta");
  meta.append(makeElement(document, "span", "visual-card__type", kindLabel));
  if (!quoteBox && label !== kindLabel) meta.append(makeElement(document, "span", "visual-card__label", label));
  if (quoteBox) {
    const quote = makeElement(document, "blockquote", "visual-card__quote-text", quoteBox.displayText);
    meta.append(quote);
    const speaker = [quoteBox.speakerName, quoteBox.speakerTitle].filter((part) => typeof part === "string" && part.trim()).join(", ");
    if (speaker) meta.append(makeElement(document, "span", "visual-card__quote-speaker", speaker));
    const citation = makeElement(document, "cite", "visual-card__quote-citation");
    const source = quoteBox.citationText ?? "";
    const span = quoteBox.italicSpan;
    const characters = [...source];
    if (span && Number.isSafeInteger(span.start) && Number.isSafeInteger(span.end) &&
        span.start >= 0 && span.end > span.start && span.end <= characters.length) {
      citation.append(document.createTextNode(characters.slice(0, span.start).join("")));
      citation.append(makeElement(document, "em", "", characters.slice(span.start, span.end).join("")));
      citation.append(document.createTextNode(characters.slice(span.end).join("")));
    } else citation.textContent = source;
    if (source) meta.append(citation);
    meta.append(makeElement(document, "span", "visual-card__quote-template", "EV24 Quote Box"));
    if (options.quoteRangeLabel) {
      meta.append(makeElement(document, "span", "visual-card__quote-range", options.quoteRangeLabel));
    }
    if (typeof options.quoteBoxEdit === "function" && options.rowId && options.overlayId) {
      const editor = makeElement(document, "details", "visual-card__quote-editor");
      editor.append(makeElement(document, "summary", "", "Edit quote box"));
      const displayLabel = makeElement(document, "label", "", "Display text");
      const displayInput = makeElement(document, "textarea", "visual-card__quote-input");
      displayInput.value = quoteBox.displayText;
      displayInput.rows = 3;
      displayLabel.append(displayInput);
      const displaySave = makeElement(document, "button", "", "Save display text");
      displaySave.type = "button";
      displaySave.disabled = true;
      displayInput.addEventListener("input", () => { displaySave.disabled = displayInput.value === quoteBox.displayText; });
      displaySave.addEventListener("click", () => {
        void options.quoteBoxEdit({ rowId: options.rowId, overlayId: options.overlayId,
          expectedRowVersion: options.rowVersion, expectedOverlayVersion: options.overlayVersion,
          edit: { displayText: displayInput.value } });
      });
      const citationLabel = makeElement(document, "label", "", "Citation");
      const citationInput = makeElement(document, "textarea", "visual-card__quote-input");
      citationInput.value = source;
      citationInput.rows = 2;
      citationLabel.append(citationInput);
      const citationSave = makeElement(document, "button", "", "Save citation");
      citationSave.type = "button";
      citationSave.disabled = true;
      citationInput.addEventListener("input", () => { citationSave.disabled = citationInput.value === source; });
      citationSave.addEventListener("click", () => {
        void options.quoteBoxEdit({ rowId: options.rowId, overlayId: options.overlayId,
          expectedRowVersion: options.rowVersion, expectedOverlayVersion: options.overlayVersion,
          edit: { citationText: citationInput.value } });
      });
      editor.append(displayLabel, displaySave, citationLabel, citationSave);
      if (typeof options.quoteBoxRangeEdit === "function") {
        const rangeHint = makeElement(document, "p", "visual-card__quote-range-hint",
          "Select spoken words in the narration, then set this box’s range.");
        const rangeButton = makeElement(document, "button", "visual-card__quote-range-edit", "Set range to selected words");
        rangeButton.type = "button";
        rangeButton.dataset.quoteBoxRangeEdit = "";
        rangeButton.addEventListener("click", () => {
          void options.quoteBoxRangeEdit({ rowId: options.rowId, overlayId: options.overlayId,
            expectedRowVersion: options.rowVersion, expectedOverlayVersion: options.overlayVersion });
        });
        editor.append(rangeHint, rangeButton);
      }
      meta.append(editor);
      const remove = makeElement(document, "button", "visual-card__quote-delete", "Delete quote box");
      remove.type = "button";
      remove.addEventListener("click", () => {
        void options.quoteBoxEdit({ rowId: options.rowId, overlayId: options.overlayId,
          expectedRowVersion: options.rowVersion, expectedOverlayVersion: options.overlayVersion,
          edit: { delete: true } });
      });
      meta.append(remove);
    }
  }
  if (researchClip && !payload?.frameBinding) {
    meta.append(makeElement(document, "span", "visual-card__source-state", "Research · Playback unavailable"));
  }
  const researchStill = payload?.researchStill;
  if (researchStill && typeof researchStill === "object") {
    const credit = typeof researchStill.credit === "string" ? researchStill.credit.trim() : "";
    const provenance = researchStill.provenance && typeof researchStill.provenance === "object"
      ? (typeof researchStill.provenance.kind === "string" ? researchStill.provenance.kind : "") :
      typeof researchStill.provenance === "string" ? researchStill.provenance.trim() : "";
    const details = [credit, provenance].filter(Boolean).join(" · ");
    meta.append(makeElement(document, "span", "visual-card__source-state",
      details ? `Saved Research · ${details}` : "Saved Research"));
    if (blockId && slotId && visualCommand) {
      const control = makeElement(document, "label", "visual-card__credit", "Show credit on screen");
      const checkbox = makeElement(document, "input");
      checkbox.type = "checkbox";
      checkbox.checked = payload.showResearchStillCredit === true;
      checkbox.disabled = !credit;
      checkbox.addEventListener("change", () => {
        void visualCommand({ kind: "set_research_still_credit", blockId, slotId,
          payloadId: payload.payloadId, show: checkbox.checked }, "Show still credit");
      });
      control.prepend(checkbox);
      meta.append(control);
    }
  }
  if (isOnCamera && slotId && visualCommand) {
    meta.append(onCameraControls(document, blockId, slotId, framing, visualCommand));
  }
  if (options.waiting) {
    const waiting = makeElement(document, "span", "visual-card__waiting", "Waiting for words");
    const attach = makeElement(document, "button", "visual-card__attach", "Attach to words");
    attach.type = "button";
    attach.dataset.attachVisual = "";
    attach.setAttribute("aria-pressed", String(options.attaching === true));
    meta.append(waiting);
    if (options.attach) {
      attach.addEventListener("click", (event) => {
        event.stopPropagation();
        options.attach(blockId, slotId);
      });
      meta.append(attach);
    }
  }
  if (options.holdSeconds !== undefined) {
    const hold = makeElement(document, "label", "visual-card__hold", "Hold");
    const input = makeElement(document, "input", "visual-card__hold-input");
    input.type = "text";
    input.inputMode = "decimal";
    input.dataset.visualHold = options.payloadId;
    input.value = Number.isInteger(options.holdSeconds) ? options.holdSeconds.toFixed(1) : String(options.holdSeconds);
    input.dataset.savedSeconds = input.value;
    input.setAttribute("aria-label", `Hold in seconds for ${label}`);
    const unit = makeElement(document, "span", "visual-card__hold-unit", "s");
    hold.append(input, unit);
    meta.append(hold);
  }
  if (reselect && blockId && slotId && payload?.kind === "visual") {
    // Keep the menu stationary: exposing the separate hover/focus action may
    // not move the dots under a pointer (S03 D171).
    card.tabIndex = 0;
    const action = makeElement(document, "button", "visual-card__reselect", "Reselect range");
    action.type = "button";
    action.dataset.reselectOpen = "button";
    action.addEventListener("click", (event) => {
      event.stopPropagation();
      reselect(blockId, slotId, "button");
    });
    meta.append(action);
    if (!options.editable) {
      const menuButton = makeElement(document, "button", "visual-card__menu-button", "⋯");
      menuButton.type = "button";
      menuButton.dataset.reselectOpen = "menu";
      menuButton.setAttribute("aria-label", "Visual options");
      menuButton.setAttribute("aria-haspopup", "menu");
      menuButton.setAttribute("aria-expanded", "false");
      const menu = makeElement(document, "div", "visual-card__menu");
      menu.id = `visual-options-${slotId}`;
      menu.setAttribute("role", "menu");
      menuButton.setAttribute("aria-controls", menu.id);
      menu.hidden = true;
      const menuAction = makeElement(document, "button", "visual-card__menu-action", "Reselect range");
      menuAction.type = "button";
      menuAction.setAttribute("role", "menuitem");
      menuAction.addEventListener("click", (event) => {
        event.stopPropagation();
        reselect(blockId, slotId, "menu");
      });
      menu.append(menuAction);
      menuButton.addEventListener("click", (event) => {
        event.stopPropagation();
        menu.hidden = !menu.hidden;
        menuButton.setAttribute("aria-expanded", String(!menu.hidden));
        if (!menu.hidden) menuAction.focus();
      });
      menu.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          menu.hidden = true;
          menuButton.setAttribute("aria-expanded", "false");
          menuButton.focus();
        }
      });
      card.append(menuButton, menu);
    }
  }
  card.append(meta);

  if (options.editable) {
    const actions = makeElement(document, "div", "visual-card__actions");
    const trigger = makeElement(document, "button", "visual-card__trigger", "⋯");
    trigger.type = "button";
    trigger.dataset.visualActionTrigger = "";
    if (reselect && blockId && slotId && payload?.kind === "visual") {
      trigger.dataset.reselectOpen = "menu";
    }
    trigger.setAttribute("aria-label", `Visual actions for ${label}`);
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.setAttribute("aria-expanded", "false");
    const menu = makeElement(document, "div", "visual-card__menu");
    menu.dataset.visualActionMenu = "";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", `Visual actions for ${label}`);
    menu.hidden = true;
    const change = makeElement(document, "button", "", "Change type");
    change.type = "button";
    change.dataset.visualChangeType = "";
    change.setAttribute("role", "menuitem");
    change.setAttribute("aria-haspopup", "menu");
    const remove = makeElement(document, "button", "", "Delete");
    remove.type = "button";
    remove.dataset.visualDelete = "";
    remove.setAttribute("role", "menuitem");
    if (reselect && blockId && slotId && payload?.kind === "visual") {
      const reselectAction = makeElement(document, "button", "visual-card__menu-action", "Reselect range");
      reselectAction.type = "button";
      reselectAction.setAttribute("role", "menuitem");
      reselectAction.addEventListener("click", (event) => {
        event.stopPropagation();
        reselect(blockId, slotId, "menu");
      });
      menu.append(reselectAction);
    }
    menu.append(change);
    if (options.stashable) {
      const stash = makeElement(document, "button", "", "Stash visual");
      stash.type = "button";
      stash.dataset.visualStash = "";
      stash.setAttribute("role", "menuitem");
      menu.append(stash);
    }
    menu.append(remove);
    const types = makeElement(document, "div", "visual-card__types");
    types.dataset.visualTypes = "";
    types.setAttribute("role", "menu");
    types.setAttribute("aria-label", "Change visual type");
    types.hidden = true;
    const current = payload?.kind === "undefined" ? "visual_undefined" :
      payload?.pictureKind === "intentional_placeholder" ? "onscreen_placeholder" :
      payload?.pictureKind === "unresolved_visual" ? "need_to_find" : "";
    for (const [type, label] of [
      ["onscreen_placeholder", "Onscreen Placeholder"],
      ["need_to_find", "Need to Find"],
      ["visual_undefined", "Visual Undefined"],
    ]) {
      const button = makeElement(document, "button", "", label);
      button.type = "button";
      button.dataset.visualNewType = type;
      button.setAttribute("role", "menuitem");
      button.disabled = type === current;
      types.append(button);
    }
    actions.append(trigger, menu, types);
    card.append(actions);
  }

  if (previewable) {
    const preview = makeElement(document, "div", "visual-card__preview");
    preview.setAttribute("aria-hidden", "true");
    appendVisualImage(document, preview, imageSource, label, definition.art);
    card.append(preview);
  }

  return card;
}

function quoteBoxRangeLabel(row, event) {
  const spoken = (row.tokens ?? []).filter((token) => token?.spoken !== false);
  const startId = event.timing?.start?.anchor?.tokenId;
  const endId = event.timing?.end?.anchor?.tokenId;
  const start = spoken.findIndex((token) => token.id === startId);
  const end = spoken.findIndex((token) => token.id === endId);
  return start >= 0 && end >= start ? `Range · words ${start + 1}–${end + 1}` : "Range · words need review";
}

function renderVisuals(document, block, projectedRow, flashIds, visualCommand, reselect, attach, attaching, addWordless, projectVisualHoldMs, allowStash, quoteBoxEdit, quoteBoxRangeEdit, quotePicture) {
  const cell = makeElement(document, "section", "visuals-cell");
  cell.setAttribute("aria-label", "Visuals");
  const list = makeElement(document, "div", "visuals-list");
  if (block.type === "narration") {
    // Only the model's cue projection decides visible coverage and returns.
    // The stored slot array is structural and may contain wordless return slots.
    const slots = new Map((block.primaryVisualSequence?.slots ?? [])
      .filter((slot) => slot.kind === "content").map((slot) => [slot.id, slot.payload]));
    const waiting = new Map((block.unattachedVisuals ?? []).map((item) => [item.slotId, item.payload]));
    const overlays = new Map(block.overlayEvents.map((event) => [event.id, event]));
    const cues = (projectedRow?.cards ?? []).map((card, index) => ({
      card, index, start: card.startTokenIndex ?? Number.POSITIVE_INFINITY,
    }));
    const overlayCues = (projectedRow?.overlays ?? []).map((overlay, index) => ({
      overlay, index, start: overlay.startTokenIndex ?? Number.POSITIVE_INFINITY,
    }));
    const ordered = [...cues, ...overlayCues].sort((a, b) =>
      a.start - b.start || (a.card ? -1 : 1) - (b.card ? -1 : 1) || a.index - b.index);
    for (const entry of projectedRow?.renderable ? ordered : []) {
      if (entry.overlay) {
        const event = overlays.get(entry.overlay.overlayEventId);
        if (event) list.append(renderVisualCard(document, event.payload, event.payload.researchClip, {
          slotId: entry.overlay.overlayEventId, startTokenIndex: entry.overlay.startTokenIndex,
          footagePlacementId: entry.overlay.overlayEventId, quoteBox: event.quoteBox,
          rowId: block.id, rowVersion: block.version, overlayId: event.id,
          overlayVersion: event.version, quoteBoxEdit, quoteBoxRangeEdit, quotePicture,
          quoteRangeLabel: event.quoteBox ? quoteBoxRangeLabel(block, event) : null,
        }));
        continue;
      }
      const card = entry.card;
      if (card.compact) {
        const returning = slots.get(card.slotId) ?? waiting.get(card.slotId);
        const label = card.kind === "on_camera" ? "OC" : visualLabel(returning);
        const chip = makeElement(document, "div", "visual-return", `↩ ${label} resumes`);
        chip.dataset.slotId = card.slotId;
        chip.dataset.kind = card.kind;
        chip.dataset.compact = "true";
        chip.setAttribute("aria-label", `${label} resumes`);
        if (card.kind === "on_camera" && visualCommand) {
          chip.append(onCameraControls(document, block.id, card.slotId, card.framing ?? "wide", visualCommand));
        }
        list.append(chip);
        continue;
      }
      const payload = card.kind === "on_camera" ? { kind: "on_camera", framing: card.framing } :
        slots.get(card.slotId) ?? waiting.get(card.slotId);
      if (!payload) continue;
      list.append(renderVisualCard(document, payload, payload.researchClip, {
        blockId: block.id,
        slotId: card.slotId,
        footagePlacementId: card.slotId,
        framing: card.framing ?? "wide",
        visualCommand,
        reselect: projectedRow.brackets?.some((bracket) => bracket.slotId === card.slotId) ? reselect : null,
        startTokenIndex: card.startTokenIndex,
        flash: flashIds?.has(card.slotId),
        draggable: Boolean(visualCommand) && (card.kind === "visual" || card.kind === "unattached_visual"),
        waiting: card.kind === "unattached_visual",
        attaching: attaching?.rowId === block.id && attaching.slotId === card.slotId,
        attach, quotePicture,
        editable: Boolean(visualCommand) && (card.kind === "visual" || card.kind === "undefined" || card.kind === "unattached_visual"),
        stashable: allowStash && payload.kind === "visual",
      }));
    }
    if (!projectedRow?.renderable) {
      // A failed read-only projection must not hide previously saved art.
      const byId = new Map((block.primaryVisualSequence?.slots ?? []).map((slot) => [slot.id, slot]));
      for (const slot of block.primaryVisualSequence?.slots ?? []) {
        if (slot.kind === "content") {
          list.append(renderVisualCard(document, slot.payload, slot.payload.researchClip, {
            footagePlacementId: slot.id, quotePicture,
          }));
        } else if (slot.kind === "return") {
          const parent = byId.get(slot.parentSlotId);
          const payload = parent?.kind === "content" ? parent.payload : null;
          const label = payload?.kind === "on_camera" ? "OC" : visualLabel(payload);
          list.append(makeElement(document, "div", "visual-return", `↩ ${label} resumes`));
        }
      }
      for (const event of block.overlayEvents ?? []) {
        list.append(renderVisualCard(document, event.payload, event.payload.researchClip, {
          footagePlacementId: event.id, quoteBox: event.quoteBox,
          rowId: block.id, rowVersion: block.version, overlayId: event.id,
          overlayVersion: event.version, quoteBoxEdit, quoteBoxRangeEdit, quotePicture,
          quoteRangeLabel: event.quoteBox ? quoteBoxRangeLabel(block, event) : null,
        }));
      }
      for (const { slotId, payload } of block.unattachedVisuals ?? []) {
        list.append(renderVisualCard(document, payload, payload.researchClip, { footagePlacementId: slotId }));
      }
    }
  }
  if (block.type === "visual_only") {
    const implicitHoldMs = block.additionalVisuals?.length ? 4000 : projectVisualHoldMs;
    for (const visual of [block, ...(block.additionalVisuals ?? [])]) {
      const timing = visual.visualOnlyTiming;
      list.append(renderVisualCard(document, visual.payload, visual.researchClip, {
        payloadId: visual.payload.payloadId, draggable: Boolean(visualCommand),
        footagePlacementId: visual === block ? block.id : visual.payload.payloadId,
        holdSeconds: visualCommand && timing && !timing.matchAudioDuration && !timing.selectedSourceRange &&
          visual.payload.pictureKind !== "clip" ? (timing.durationOverrideMs ?? implicitHoldMs) / 1000 : undefined,
      }));
    }
  }

  if (!list.childElementCount) {
    cell.append(makeElement(document, "div", "visuals-empty"));
  } else {
    cell.append(list);
  }
  // A blank narration row promotes to a real visual-only row on the first add.
  // Never offer a wordless action on a row with spoken narration.
  if (addWordless && (block.type === "visual_only" ||
      block.type === "narration" && block.state === "active" && block.text === "" &&
      block.tokens.length === 0 && !block.plainDirection && !block.attachedFootage &&
      !block.notes.length && !block.overlayEvents.length && !block.annotations?.length &&
      !block.performanceBeats?.length && !block.unattachedVisuals?.length &&
      block.primaryVisualSequence?.slots.length === 1 &&
      block.primaryVisualSequence.slots[0]?.kind === "content" &&
      block.primaryVisualSequence.slots[0].relation.kind === "base" &&
      block.primaryVisualSequence.slots[0].boundaryBefore.kind === "row_start" &&
      block.primaryVisualSequence.slots[0].playoutPolicy === "match_structural_interval")) {
    const actions = makeElement(document, "div", "visuals-wordless-actions");
    const button = makeElement(document, "button", "visuals-wordless-add", "+ Visual");
    button.type = "button";
    button.dataset.wordlessAdd = "";
    button.setAttribute("aria-expanded", "false");
    const choices = makeElement(document, "div", "visuals-wordless-choices");
    choices.hidden = true;
    choices.setAttribute("role", "menu");
    choices.setAttribute("aria-label", "Add wordless visual");
    for (const [type, label] of [["onscreen_placeholder", "Onscreen Placeholder"], ["need_to_find", "Need to Find"]]) {
      const choice = makeElement(document, "button", "", label);
      choice.type = "button";
      choice.setAttribute("role", "menuitem");
      choice.dataset.wordlessType = type;
      choice.addEventListener("click", () => addWordless(block.id, type));
      choices.append(choice);
    }
    button.addEventListener("click", () => {
      choices.hidden = !choices.hidden;
      button.setAttribute("aria-expanded", String(!choices.hidden));
      if (!choices.hidden) choices.querySelector("button")?.focus();
    });
    actions.append(button, choices);
    cell.append(actions);
  }
  return cell;
}

function appendNarrationText(document, paragraph, block) {
  const text = typeof block.text === "string" ? block.text : "";
  const tokens = Array.isArray(block.tokens) ? block.tokens : [];
  let cursor = 0;

  for (const token of tokens) {
    const rawStart = Number(token && token.startOffset);
    const rawEnd = Number(token && token.endOffset);
    if (!Number.isInteger(rawStart) || !Number.isInteger(rawEnd)) continue;

    const start = Math.max(cursor, Math.max(0, Math.min(rawStart, text.length)));
    const end = Math.max(start, Math.max(0, Math.min(rawEnd, text.length)));
    if (end <= cursor) continue;

    if (start > cursor) paragraph.append(document.createTextNode(text.slice(cursor, start)));
    const tokenText = text.slice(start, end);
    if (token.spoken === false) {
      paragraph.append(makeElement(document, "span", "narration-token--direction", tokenText));
    } else {
      paragraph.append(document.createTextNode(tokenText));
    }
    cursor = end;
  }

  if (cursor < text.length) paragraph.append(document.createTextNode(text.slice(cursor)));
}

function shortContent(text, fallback) {
  const clean = typeof text === "string" ? text.trim().replace(/\s+/g, " ") : "";
  if (!clean) return fallback;
  return clean.length > 96 ? clean.slice(0, 93) + "…" : clean;
}

function renderRow(document, block, projectedRow, flashIds, visualCommand, reselect, attach, attaching, addWordless, projectVisualHoldMs, allowStash, quoteBoxEdit, quoteBoxRangeEdit, quotePicture) {
  const row = makeElement(document, "article", "script-row");
  row.dataset.rowId = block.id || "";
  row.dataset.rowKind = block.type;
  if (block.state) row.dataset.state = block.state;

  const narration = makeElement(document, "div", "narration-cell");
  if (block.type === "narration" || (block.type === "visual_only" && block.clearedNarration)) {
    const paragraph = makeElement(document, "p", "narration-text");
    if (block.plainDirection) paragraph.classList.add("narration-text--plain-direction");
    appendNarrationText(document, paragraph, block);
    narration.append(paragraph);
    row.setAttribute("aria-label", "Narration: " + shortContent(block.text, "Empty narration"));
  } else if (block.type === "direction") {
    narration.append(makeElement(document, "p", "narration-text narration-text--direction", block.text || ""));
    row.setAttribute("aria-label", "Direction: " + shortContent(block.text, "Empty direction"));
  } else if (block.type === "note_draft") {
    narration.append(makeElement(document, "p", "narration-text narration-text--note", block.text || ""));
    row.setAttribute("aria-label", "Draft note: " + shortContent(block.text, "Empty draft note"));
  } else {
    narration.append(makeElement(document, "span", "screen-reader-only", "Visual-only row"));
    row.setAttribute("aria-label", "Visual-only row");
  }

  row.append(narration);
  row.append(renderVisuals(document, block, projectedRow, flashIds, visualCommand, reselect, attach, attaching, addWordless, projectVisualHoldMs, allowStash, quoteBoxEdit, quoteBoxRangeEdit, quotePicture));
  return row;
}

export function renderRows(root, document, { projection, flashIds = new Set(), visualCommand, reselect, attach, attaching, addWordless, projectVisualHoldMs = 3000, allowStash = false, quoteBoxEdit, quoteBoxRangeEdit, quotePicture } = {}) {
  if (!root || !root.ownerDocument) return;
  const ownerDocument = root.ownerDocument;
  const blocks = document && document.activeDraft && Array.isArray(document.activeDraft.blocks)
    ? document.activeDraft.blocks
    : [];
  const projectedRows = new Map((projection?.rows ?? []).map((row) => [row.blockId, row]));

  releaseQuotePictures(root);
  root.replaceChildren();
  let rowCount = 0;

  for (const block of blocks) {
    if (!block || typeof block !== "object") continue;
    if (block.type === "section") {
      const heading = makeElement(ownerDocument, "h2", "script-section-heading");
      heading.dataset.sectionId = block.id;
      heading.append(makeElement(ownerDocument, "span", "script-section-heading__title", block.title || "Untitled section"));
      root.append(heading);
      continue;
    }
    if (block.type === "narration" || block.type === "direction" || block.type === "note_draft" || block.type === "visual_only") {
      root.append(renderRow(ownerDocument, block, projectedRows.get(block.id), flashIds, visualCommand, reselect, attach, attaching, addWordless, projectVisualHoldMs, allowStash, quoteBoxEdit, quoteBoxRangeEdit, quotePicture));
      rowCount += 1;
    }
  }

  if (rowCount === 0) root.append(makeElement(ownerDocument, "p", "script-empty", "This script has no rows yet."));
}

/** The card DOM is ephemeral; one delegated menu handler survives rerenders. */
export function mountVisualCardMenus(root, command, stashVisual) {
  const close = () => {
    for (const actions of root.querySelectorAll(".visual-card__actions")) {
      actions.querySelector("[data-visual-action-menu]").hidden = true;
      actions.querySelector("[data-visual-types]").hidden = true;
      actions.querySelector("[data-visual-action-trigger]").setAttribute("aria-expanded", "false");
    }
  };
  const onClick = (event) => {
    const button = event.target.closest("button");
    const actions = button?.closest(".visual-card__actions");
    if (!actions) return;
    const trigger = actions.querySelector("[data-visual-action-trigger]");
    const menu = actions.querySelector("[data-visual-action-menu]");
    const types = actions.querySelector("[data-visual-types]");
    const card = actions.closest(".visual-card");
    const rowId = card?.closest("[data-row-id]")?.dataset.rowId;
    const slotId = card?.dataset.slotId;
    if (!rowId || !slotId || button.disabled) return;
    if (button === trigger) {
      const opening = menu.hidden && types.hidden;
      close();
      menu.hidden = !opening;
      trigger.setAttribute("aria-expanded", String(opening));
      if (opening) menu.querySelector("[role='menuitem']")?.focus();
    } else if (button.matches("[data-visual-change-type]")) {
      menu.hidden = true;
      types.hidden = false;
      types.querySelector("[role='menuitem']:not(:disabled)")?.focus();
    } else if (button.matches("[data-visual-stash]")) {
      close();
      void stashVisual?.(rowId, slotId);
    } else if (button.matches("[data-visual-delete], [data-visual-new-type]")) {
      const type = button.dataset.visualNewType;
      close();
      // The model owns coverage, identities and atomic refusal. Never edit JSON here.
      void command(type ? { kind: "change_visual_type", blockId: rowId, slotId, to: { type } } :
        { kind: "delete_visual", blockId: rowId, slotId }, type ? "Change visual type" : "Delete visual", { rowId, slotId });
    }
  };
  const onKeydown = (event) => {
    if (event.key !== "Escape") return;
    const actions = event.target.closest(".visual-card__actions");
    if (!actions || actions.querySelector("[data-visual-action-menu]").hidden &&
      actions.querySelector("[data-visual-types]").hidden) return;
    event.preventDefault();
    event.stopPropagation();
    close();
    actions.querySelector("[data-visual-action-trigger]").focus();
  };
  const onPointer = (event) => {
    if (!event.target.closest(".visual-card__actions")) close();
  };
  const onFocusout = (event) => {
    const actions = event.target.closest(".visual-card__actions");
    if (actions && !actions.contains(event.relatedTarget)) close();
  };
  root.addEventListener("click", onClick);
  root.addEventListener("keydown", onKeydown);
  root.addEventListener("focusout", onFocusout);
  root.ownerDocument.addEventListener("pointerdown", onPointer);
  return () => {
    root.removeEventListener("click", onClick);
    root.removeEventListener("keydown", onKeydown);
    root.removeEventListener("focusout", onFocusout);
    root.ownerDocument.removeEventListener("pointerdown", onPointer);
  };
}
