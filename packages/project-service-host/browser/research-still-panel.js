/*
 * Narrow selected-words picker for already-kept Research stills.
 *
 * The panel deliberately owns only display state (page, thumbnail URLs and
 * the selected opener).  The app supplies the authenticated catalog/thumbnail
 * ports and the queued insert callback, which makes this seam independently
 * testable without a browser session or a Research service.
 */

const make = (doc, tag, className, content) => {
  const node = doc.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
};

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
const stillKey = (still) => `${String(still?.itemId ?? "").toLowerCase()}:${still?.itemVersion}`;

/**
 * A small pure boundary for browser and Zodex-style tests.  The host owns the
 * authoritative shape; malformed entries are ignored rather than rendered as
 * arbitrary DOM text.
 */
export function normalizeResearchStillPage(value) {
  const stills = Array.isArray(value?.stills) ? value.stills.filter((still) =>
    still && typeof still.itemId === "string" && uuid.test(still.itemId) &&
    Number.isSafeInteger(still.itemVersion) && still.itemVersion > 0 &&
    typeof still.title === "string" && still.title.length > 0) : [];
  const nextOffset = value?.nextOffset === null ||
    Number.isSafeInteger(value?.nextOffset) && value.nextOffset >= 0 ? value.nextOffset : null;
  return { stills, nextOffset };
}

/**
 * Mount the selected-words still picker.
 *
 * @param {{root: HTMLElement, catalog: (projectId: string, offset: number) => Promise<unknown>,
 * thumbnail: (projectId: string, itemId: string, itemVersion: number) => Promise<{mimeType: string, bytes: ArrayBuffer|Uint8Array}>,
 * insert: (still: object, placement: unknown, projectId: string) => Promise<boolean>,
 * stashStill?: (still: object, projectId: string) => Promise<boolean>,
 * dragStill?: (event: DragEvent, still: object, projectId: string) => void,
 * onClose?: () => void, onStatus?: (message: string) => void}} ports
 */
export function mountResearchStillPanel({ root, catalog, thumbnail, insert, stashStill, dragStill, onClose, onStatus = () => undefined }) {
  if (!root?.ownerDocument || typeof catalog !== "function" ||
      typeof thumbnail !== "function" || typeof insert !== "function") {
    return { open: async () => undefined, close: () => undefined, update: () => undefined, currentProject: () => "" };
  }
  const doc = root.ownerDocument;
  const openButton = doc.getElementById("open-footage");
  const closeButton = root.querySelector("[data-research-still-close]");
  const projects = root.querySelector("[data-research-still-project]");
  const results = root.querySelector("[data-research-still-results]");
  const status = root.querySelector("[data-research-still-status]");
  const loadMore = root.querySelector("[data-research-still-load-more]");
  let visible = false;
  let generation = 0;
  let currentProject = "";
  let stills = [];
  let nextOffset = null;
  let opener = null;
  let placement = null;
  let committing = false;
  const thumbnailUrls = new Map();
  const thumbnailLoads = new Set();
  const thumbnailTargets = new Map();

  const revokeThumbnails = () => {
    for (const url of thumbnailUrls.values()) URL.revokeObjectURL(url);
    thumbnailUrls.clear();
    thumbnailLoads.clear();
    thumbnailTargets.clear();
  };

  const close = () => {
    ++generation;
    visible = false;
    currentProject = "";
    stills = [];
    nextOffset = null;
    placement = null;
    committing = false;
    revokeThumbnails();
    root.hidden = true;
    onClose?.();
    if (opener?.isConnected) opener.focus();
    else openButton?.focus();
    opener = null;
  };

  const showStatus = (message) => {
    status.textContent = message;
  };

  const thumbnailError = (error) => {
    if (error?.status === 403) return "You don’t have access to this Research project.";
    if (error?.status === 404) return "This saved still is no longer available.";
    if (error?.status === 409) return "This saved still changed. Close and choose it again.";
    if (error?.status === 422) return "This saved still is too large for a Timeline build.";
    return "Saved Research thumbnails are unavailable right now.";
  };

  const loadThumbnail = (still, request) => {
    const key = stillKey(still);
    if (thumbnailUrls.has(key) || thumbnailLoads.has(key)) return;
    thumbnailLoads.add(key);
    void thumbnail(currentProject, still.itemId, still.itemVersion).then(({ mimeType, bytes }) => {
      if (request !== generation || !visible || currentProject === "") return;
      const blob = new Blob([bytes], { type: mimeType || "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      thumbnailUrls.set(key, url);
      const target = thumbnailTargets.get(key);
      if (target?.isConnected) {
        const image = doc.createElement("img");
        image.src = url;
        image.alt = "";
        image.loading = "lazy";
        image.decoding = "async";
        target.replaceChildren(image);
      } else render();
    }).catch((error) => {
      if (request === generation && visible) {
        // Keep the item selectable; a missing preview must not turn into an
        // arbitrary public URL or prevent the saved identity from being used.
        showStatus(thumbnailError(error));
      }
    }).finally(() => {
      thumbnailLoads.delete(key);
    });
  };

  const render = () => {
    if (!visible) return;
    projects.disabled = committing;
    results.replaceChildren();
    thumbnailTargets.clear();
    loadMore.hidden = nextOffset === null;
    loadMore.disabled = committing;
    if (!currentProject) {
      showStatus(projects.options.length > 1 ? "Choose a Research project." :
        "No logged Research projects are available.");
      return;
    }
    if (!stills.length && nextOffset !== null) {
      showStatus("No kept stills on this page. Load more to continue.");
    } else if (!stills.length) {
      showStatus("No saved Research stills in this project.");
    } else {
      showStatus(`${stills.length} saved Research still${stills.length === 1 ? "" : "s"}`);
    }
    const request = generation;
    for (const still of stills) {
      const card = make(doc, "article", "research-still-item");
      card.setAttribute("role", "listitem");
      const choose = make(doc, "button", "research-still-item__choose");
      choose.type = "button";
      choose.disabled = committing;
      choose.dataset.researchStillId = still.itemId;
      choose.draggable = !committing;
      choose.addEventListener("dragstart", (event) => {
        dragStill?.(event, still, currentProject);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
      });
      choose.setAttribute("aria-label", `Choose saved Research still: ${still.title}`);
      const art = make(doc, "span", "research-still-item__thumbnail");
      art.setAttribute("aria-hidden", "true");
      thumbnailTargets.set(stillKey(still), art);
      const url = thumbnailUrls.get(stillKey(still));
      if (url) {
        const image = doc.createElement("img");
        image.src = url;
        image.alt = "";
        image.loading = "lazy";
        image.decoding = "async";
        art.append(image);
      } else {
        art.append(make(doc, "span", "research-still-item__thumbnail-empty", "Still"));
        loadThumbnail(still, request);
      }
      const copy = make(doc, "span", "research-still-item__copy");
      copy.append(make(doc, "span", "research-still-item__title", still.title));
      if (typeof still.credit === "string" && still.credit.trim()) {
        copy.append(make(doc, "span", "research-still-item__credit", still.credit.trim()));
      }
      choose.append(art, copy);
      choose.addEventListener("click", () => {
        if (committing) return;
        if (!placement) { void stashStill?.(still, currentProject); return; }
        const selectedProject = currentProject;
        const started = generation;
        committing = true;
        loadMore.disabled = true;
        render();
        void insert(still, placement, selectedProject).then((success) => {
          if (started !== generation || !visible || currentProject !== selectedProject) return;
          if (success) {
            close();
            onStatus("Saved Research still added to script.");
          } else {
            committing = false;
            render();
            showStatus("Saved Research still was not added. The script or source may have changed.");
          }
        }).catch(() => {
          if (started !== generation || !visible || currentProject !== selectedProject) return;
          committing = false;
          render();
          showStatus("Saved Research still was not added. The script or source may have changed.");
        });
      });
      card.append(choose);
      if (stashStill && placement) {
        const stash = make(doc, "button", "", "Add still to Stash");
        stash.type = "button";
        stash.disabled = committing;
        stash.addEventListener("click", () => void stashStill(still, currentProject));
        card.append(stash);
      }
      results.append(card);
    }
  };

  const loadPage = async (offset, append = false) => {
    const request = ++generation;
    if (!append) {
      stills = [];
      nextOffset = null;
      revokeThumbnails();
    }
    showStatus(append ? "Loading more saved stills…" : "Loading saved Research stills…");
    results.replaceChildren();
    loadMore.disabled = true;
    try {
      const page = normalizeResearchStillPage(await catalog(currentProject, offset));
      if (request !== generation || !visible) return;
      stills = append ? [...stills, ...page.stills] : page.stills;
      nextOffset = page.nextOffset;
      render();
    } catch (error) {
      if (request !== generation || !visible) return;
      nextOffset = null;
      showStatus(error?.status === 403 ? "You don’t have access to this Research project." :
        error?.status === 404 ? "No saved Research stills are available in this project." :
          "Saved Research stills are unavailable right now. Close and retry.");
      loadMore.hidden = true;
    } finally {
      if (request === generation) loadMore.disabled = false;
    }
  };

  const loadProjects = async () => {
    const request = ++generation;
    showStatus("Loading Research projects…");
    try {
      const response = await catalog();
      if (request !== generation || !visible) return;
      projects.replaceChildren(make(doc, "option", "", "Choose project…"));
      projects.firstChild.value = "";
      for (const project of response?.projects ?? []) {
        if (typeof project?.id !== "string" || !uuid.test(project.id) || typeof project?.name !== "string") continue;
        projects.append(make(doc, "option", "", project.name));
        projects.lastChild.value = project.id;
      }
      const remembered = currentProject && [...projects.options].some((option) => option.value === currentProject);
      currentProject = remembered ? currentProject : projects.options.length === 2 ? projects.options[1].value : "";
      projects.value = currentProject;
      if (currentProject) await loadPage(0);
      else render();
      if (!visible) return;
      projects.focus();
    } catch (error) {
      if (request !== generation || !visible) return;
      projects.replaceChildren(make(doc, "option", "", "Choose project…"));
      currentProject = "";
      showStatus(error?.status === 503 ? "Research is unavailable right now. Close and retry." :
        "Research projects could not be loaded. Close and retry.");
    }
  };

  const open = async ({ placement: selectedPlacement, from = doc.activeElement } = {}) => {
    committing = false;
    projects.disabled = false;
    opener = from;
    placement = selectedPlacement;
    visible = true;
    root.hidden = false;
    root.setAttribute("aria-busy", "true");
    closeButton?.focus();
    await loadProjects();
    root.removeAttribute("aria-busy");
  };

  closeButton?.addEventListener("click", close);
  projects.addEventListener("change", () => {
    currentProject = projects.value;
    void loadPage(0);
  });
  loadMore.addEventListener("click", () => {
    if (nextOffset !== null && !loadMore.disabled) void loadPage(nextOffset, true);
  });
  root.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    close();
  });

  return { open, close, update: render, currentProject: () => currentProject };
}
