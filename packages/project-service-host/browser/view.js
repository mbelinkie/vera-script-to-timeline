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
  const { blockId, slotId, framing, visualCommand } = options;
  const isOnCamera = payload?.kind === "on_camera";
  const kind = visualKind(payload);
  const definition = visualKinds[kind];
  const kindLabel = payload && payload.kind === "on_camera"
    ? "On Camera"
    : payload && payload.kind === "undefined"
      ? "Visual undefined"
      : definition.label;
  const label = visualLabel(payload, researchClip);
  const imageSource = localImageSource(document, payload);
  const canUseSampleTile = kind === "clip" || kind === "image" || kind === "capture" || kind === "graphic";
  const previewable = payload && payload.kind === "visual" &&
    kind !== "unresolved_visual" &&
    kind !== "intentional_placeholder" &&
    (Boolean(imageSource) || canUseSampleTile);

  const card = makeElement(document, "figure", "visual-card");
  if (slotId) card.dataset.slotId = slotId;
  card.dataset.kind = payload && payload.kind === "on_camera"
    ? "on-camera"
    : payload && payload.kind === "undefined"
      ? "undefined"
      : definition.art;
  card.dataset.previewable = String(previewable);
  card.setAttribute("aria-label", kindLabel + ": " + label);
  if (previewable) card.tabIndex = 0;

  const media = makeElement(document, "div", "visual-card__image");
  media.setAttribute("aria-hidden", "true");
  if (payload && payload.kind === "visual") {
    appendVisualImage(document, media, imageSource, label, definition.art);
  }
  card.append(media);

  const meta = makeElement(document, "figcaption", "visual-card__meta");
  meta.append(makeElement(document, "span", "visual-card__type", kindLabel));
  if (label !== kindLabel) meta.append(makeElement(document, "span", "visual-card__label", label));
  if (isOnCamera && slotId && visualCommand) {
    meta.append(onCameraControls(document, blockId, slotId, framing, visualCommand));
  }
  card.append(meta);

  if (previewable) {
    const preview = makeElement(document, "div", "visual-card__preview");
    preview.setAttribute("aria-hidden", "true");
    appendVisualImage(document, preview, imageSource, label, definition.art);
    card.append(preview);
  }

  return card;
}

function renderVisuals(document, block, projectedRow, visualCommand) {
  const cell = makeElement(document, "section", "visuals-cell");
  cell.setAttribute("aria-label", "Visuals");
  const list = makeElement(document, "div", "visuals-list");
  const slots = block.primaryVisualSequence && Array.isArray(block.primaryVisualSequence.slots)
    ? block.primaryVisualSequence.slots
    : [];
  const orderedSlots = slots.filter((slot) => slot && typeof slot === "object");
  const slotsById = new Map(orderedSlots.map((slot) => [slot.id, slot]));

  if (projectedRow?.renderable && block.type === "narration") {
    const unattachedBySlot = new Map((block.unattachedVisuals ?? []).map((item) => [item.slotId, item]));
    for (const card of projectedRow.cards) {
      const slot = slotsById.get(card.slotId);
      const unattached = unattachedBySlot.get(card.slotId);
      const payload = card.kind === "on_camera"
        ? { kind: "on_camera", framing: card.framing ?? "wide" }
        : slot?.kind === "content" ? slot.payload : unattached?.payload;
      if (!payload) continue;
      if (card.compact) {
        const label = card.kind === "on_camera" ? "OC resumes" : `${visualLabel(payload, unattached?.researchClip)} resumes`;
        const returnCard = makeElement(document, "div", "visual-return", "↩ " + label);
        returnCard.dataset.slotId = card.slotId;
        returnCard.dataset.kind = card.kind;
        returnCard.setAttribute("aria-label", "Return to " + visualLabel(payload, unattached?.researchClip));
        if (card.kind === "on_camera" && visualCommand) {
          returnCard.append(onCameraControls(document, block.id, card.slotId, card.framing ?? "wide", visualCommand));
        }
        list.append(returnCard);
      } else {
        list.append(renderVisualCard(document, payload, unattached?.researchClip ?? payload.researchClip, {
          blockId: block.id, slotId: card.slotId, framing: card.framing ?? "wide", visualCommand,
        }));
      }
    }
  } else {
    // Until the first valid projection arrives, preserve saved cards and previews.
    for (const slot of orderedSlots) {
      if (slot.kind === "return") {
        const parent = slotsById.get(slot.parentSlotId);
        const parentPayload = parent && parent.kind === "content" ? parent.payload : null;
        const parentLabel = visualLabel(parentPayload);
        const returnLabel = parentPayload && parentPayload.kind === "on_camera"
          ? "OC resumes"
          : parentLabel + " resumes";
        const returnCard = makeElement(document, "div", "visual-return", "↩ " + returnLabel);
        returnCard.setAttribute("aria-label", "Return to " + parentLabel);
        list.append(returnCard);
        continue;
      }

      if (slot.kind === "content") list.append(renderVisualCard(document, slot.payload, slot.payload.researchClip));
    }
  }

  if (block.type === "narration") {
    for (const { payload } of block.overlayEvents) {
      list.append(renderVisualCard(document, payload, payload.researchClip));
    }
    if (!projectedRow?.renderable) for (const { payload } of block.unattachedVisuals ?? []) {
      list.append(renderVisualCard(document, payload, payload.researchClip));
    }
  }
  if (block.type === "visual_only") {
    list.append(renderVisualCard(document, block.payload, block.researchClip));
    for (const visual of block.additionalVisuals ?? []) {
      list.append(renderVisualCard(document, visual.payload, visual.researchClip));
    }
  }

  if (!list.childElementCount) {
    cell.append(makeElement(document, "div", "visuals-empty"));
  } else {
    cell.append(list);
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

function renderRow(document, block, projectedRow, visualCommand) {
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
  row.append(renderVisuals(document, block, projectedRow, visualCommand));
  return row;
}

export function renderRows(root, document, { projection, visualCommand } = {}) {
  if (!root || !root.ownerDocument) return;
  const ownerDocument = root.ownerDocument;
  const blocks = document && document.activeDraft && Array.isArray(document.activeDraft.blocks)
    ? document.activeDraft.blocks
    : [];
  const projectedById = new Map((projection?.rows ?? []).map((row) => [row.blockId, row]));

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
      root.append(renderRow(ownerDocument, block, projectedById.get(block.id), visualCommand));
      rowCount += 1;
    }
  }

  if (rowCount === 0) root.append(makeElement(ownerDocument, "p", "script-empty", "This script has no rows yet."));
}
