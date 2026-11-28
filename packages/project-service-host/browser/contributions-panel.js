// #779: presentation only. The adapter owns evidence, authorization, filtering
// and durable review. This module never derives a cutoff from visible rows.
const ranges = [
  ["rev", "Since last reviewed"], ["visit", "Since last visit"],
  ["d1", "Past 24 hours"], ["d7", "Past 7 days"],
  ["all", "All time"], ["custom", "Custom range"],
];
const defaultRemoved = range => ["rev", "visit", "d1"].includes(range);
let instance = 0;

export function mountContributionsPanel({
  root, projection, role, setFilter, acknowledge, focusTarget,
  autoOpen = true, sorting = false,
}) {
  const doc = root.ownerDocument;
  const name = "contributions-range-" + ++instance;
  const panel = doc.createElement("div");
  panel.className = "contributions-panel";
  root.append(panel);
  let choice = null, range = "rev", actorId = null, showRemoved = true;
  let from = "", to = "", timeframeOpen = false, index = 0;
  let frozen = null, reviewed = null, busy = false, message = "";
  let disposed = false, filterVersion = 0, awaitingProjection = false;

  const open = () => !sorting && (choice ?? (autoOpen && projection.pendingCount > 0));
  const capture = () => {
    if (open() && !frozen && projection.boundaryToken && projection.boundaryToken !== reviewed) {
      frozen = projection.boundaryToken;
    }
  };
  const dates = () => {
    if (range !== "custom") return { from: null, to: null, valid: true };
    const start = Date.parse(from), end = Date.parse(to);
    if (!from || !to || !Number.isFinite(start) || !Number.isFinite(end) || start > end) {
      return { from: null, to: null, valid: false };
    }
    // datetime-local is minute precision, and both endpoints are inclusive.
    return { from: new Date(start).toISOString(), to: new Date(end + 59999).toISOString(), valid: true };
  };
  const filter = () => ({
    range, actorId, showRemoved, ...dates(), boundaryToken: frozen,
    active: open() && !!actorId && dates().valid && !awaitingProjection,
  });
  const authors = () => awaitingProjection || !dates().valid ? [] :
    projection.contributors.filter(person => range !== "rev" || person.actorId !== projection.selfActorId);
  const references = () => !open() || !actorId || awaitingProjection || !dates().valid ? [] :
    projection.visibleReferences.filter(ref => ref.actorId === actorId && (showRemoved || !ref.removed));
  const canReview = () => open() && (role === "editor" || role === "producer") &&
    range === "rev" && projection.pendingCount > 0 && !!frozen && frozen !== reviewed &&
    projection.coverage !== "unavailable";
  const node = (tag, text = "", className = "") => {
    const el = doc.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
  };
  const button = (text, key, action, label = text) => {
    const el = node("button", text);
    el.type = "button";
    el.dataset.contributionControl = key;
    el.setAttribute("aria-label", label);
    el.addEventListener("click", action);
    return el;
  };
  const focus = key => [...panel.querySelectorAll("[data-contribution-control]")]
    .find(el => el.dataset.contributionControl === key)?.focus({ preventScroll: true });

  function acceptProjection(next) {
    projection = next;
    awaitingProjection = false;
    capture();
    if (actorId && !authors().some(person => person.actorId === actorId)) {
      actorId = null; index = 0;
    }
    index = Math.min(index, Math.max(0, references().length - 1));
  }
  // A caller can return a projection (including asynchronously), or publish
  // one via update(). Old asynchronous filter results cannot win a newer query.
  function publish(needsProjection = false) {
    if (disposed) return;
    if (needsProjection) awaitingProjection = true;
    const version = ++filterVersion;
    render();
    const requested = filter();
    // The adapter must not issue an unbounded custom read when valid is false.
    // It still receives inactive state so existing highlights can be cleared.
    try {
      const result = setFilter({ ...requested, active: open() && !!actorId && requested.valid });
      if (result && typeof result.then === "function") {
        Promise.resolve(result).then(next => {
          if (disposed || version !== filterVersion || !next) return;
          acceptProjection(next); render();
        }, () => {
          if (disposed || version !== filterVersion) return;
          message = "Couldn’t load contributions. Try changing the filter again."; render();
        });
      } else if (result) {
        acceptProjection(result); render();
      }
    } catch {
      message = "Couldn’t load contributions. Try changing the filter again."; render();
    }
  }
  function toggle() {
    if (sorting) return;
    choice = !open();
    if (choice) { frozen = null; capture(); }
    timeframeOpen = false; message = "";
    publish();
    focus("toggle");
  }
  function close() {
    choice = false; timeframeOpen = false; message = "";
    publish(); focus("toggle");
  }
  function selectRange(next) {
    range = next; actorId = null; index = 0; showRemoved = defaultRemoved(next);
    message = ""; publish(true);
  }
  function selectAuthor(id) {
    actorId = actorId === id ? null : id;
    index = 0; message = ""; publish();
  }
  function navigate(delta) {
    const list = references();
    if (!list.length) return;
    index = (index + delta + list.length) % list.length;
    focusTarget(list[index]); render();
  }
  async function markReviewed() {
    if (!canReview() || busy) return;
    const token = frozen;
    busy = true; message = ""; render();
    try {
      const next = await acknowledge(token);
      if (disposed) return;
      // A successful write only acknowledges its exact submitted boundary.
      // Counts remain authoritative, including changes arriving during the save.
      reviewed = token;
      frozen = null; actorId = null; index = 0;
      ++filterVersion;
      if (next) acceptProjection(next);
      else capture();
      message = "Marked reviewed. Anything later stays pending.";
    } catch {
      if (disposed) return;
      message = "Couldn’t save your review. Nothing was marked reviewed. Try again.";
    } finally {
      if (!disposed) { busy = false; publish(); }
    }
  }

  function render() {
    if (disposed) return;
    const previous = panel.contains(doc.activeElement) ? doc.activeElement.dataset.contributionControl : null;
    const children = [];
    const pending = projection.pendingCount;
    const expanded = open();
    // Sorting hides the bar, but the pending alert remains and is not an ack.
    const trigger = button("Show contributions", "toggle", toggle,
      "Show contributions" + (pending ? ", " + pending + " unreviewed changes by others" : ""));
    trigger.setAttribute("aria-expanded", String(expanded));
    trigger.disabled = sorting;
    trigger.hidden = sorting && pending === 0;
    if (pending) trigger.append(node("span", String(pending), "contributions-panel__badge contributions-panel__badge--green"));
    children.push(trigger);
    if (sorting && pending) {
      children.push(node("span", "Highlights are paused while Sorting. Accept or Discard doesn’t mark anything reviewed.",
        "contributions-panel__paused"));
    }
    if (expanded) {
      const bar = node("section", "", "contributions-panel__bar");
      bar.setAttribute("aria-label", "Contributions");
      const dismiss = button("×", "close", close, "Hide the contributions bar. Nothing is marked reviewed.");
      dismiss.className = "contributions-panel__close";
      bar.append(dismiss);
      const top = node("div", "", "contributions-panel__line");
      top.append(node("strong", "See contributions"));
      for (const person of authors()) {
        const self = person.actorId === projection.selfActorId;
        const label = self ? "You" : person.displayName.trim().split(/\s+/)[0];
        const chip = button(label, "actor:" + person.actorId, () => selectAuthor(person.actorId),
          (self ? "You" : person.displayName) + ", " + person.count + " changes");
        chip.className = "contributions-panel__chip";
        chip.setAttribute("aria-pressed", String(actorId === person.actorId));
        chip.append(node("span", String(person.count), "contributions-panel__badge"));
        top.append(chip);
      }
      if (!authors().length && !awaitingProjection && dates().valid && projection.coverage === "complete") {
        top.append(node("span", "Nothing in this range"));
      }
      const label = ranges.find(([key]) => key === range)[1];
      const rangeCount = range === "rev" ? pending : projection.rangeCount;
      const timeframe = button(label + " ▾", "timeframe", () => {
        timeframeOpen = !timeframeOpen; render(); focus("timeframe");
      }, "Timeframe: " + label + (rangeCount && !awaitingProjection ? ", " + rangeCount + " changes" : ""));
      timeframe.setAttribute("aria-expanded", String(timeframeOpen));
      if (rangeCount && !awaitingProjection) {
        const green = choice === null && range === "rev" && pending > 0;
        timeframe.append(node("span", String(rangeCount), "contributions-panel__badge" +
          (green ? " contributions-panel__badge--green" : "")));
      }
      top.append(timeframe);
      if (canReview()) {
        const ack = button(busy ? "Saving…" : "Mark all reviewed", "review", markReviewed);
        ack.className = "contributions-panel__review";
        ack.disabled = busy;
        top.append(ack);
      }
      bar.append(top);
      if (timeframeOpen) {
        const options = node("div", "", "contributions-panel__options");
        options.setAttribute("role", "radiogroup");
        options.setAttribute("aria-label", "Timeframe");
        for (const [key, text] of ranges) {
          const option = node("label", "");
          const input = node("input");
          input.type = "radio"; input.name = name; input.value = key; input.checked = range === key;
          input.dataset.contributionControl = "range:" + key;
          input.addEventListener("change", () => selectRange(key));
          option.append(input, doc.createTextNode(text)); options.append(option);
        }
        if (range === "custom") {
          for (const [key, value, caption] of [["from", from, "From"], ["to", to, "To"]]) {
            const field = node("label", caption);
            const input = node("input");
            input.type = "datetime-local"; input.value = value; input.dataset.contributionControl = key;
            input.addEventListener("change", () => {
              if (key === "from") from = input.value; else to = input.value;
              actorId = null; index = 0; publish(true);
            });
            field.append(input); options.append(field);
          }
        }
        bar.append(options);
      }
      if (!dates().valid) bar.append(node("p", "Choose both endpoints, with From no later than To."));
      else if (awaitingProjection) bar.append(node("p", "Loading contributions…"));
      if (projection.coverage !== "complete") {
        bar.append(node("p", projection.coverage === "partial" ?
          "Some contribution evidence is not available in this view." : "Contribution evidence is unavailable."));
      }
      const person = authors().find(item => item.actorId === actorId);
      if (person) {
        const list = references(), current = list[index];
        const nav = node("div", "", "contributions-panel__line contributions-panel__navigation");
        const position = node("span", (actorId === projection.selfActorId ? "You" : person.displayName) +
          " · change " + (list.length ? index + 1 : 0) + " of " + list.length);
        position.setAttribute("role", "status");
        const prev = button("‹ Previous", "previous", () => navigate(-1), "Previous change");
        const next = button("Next ›", "next", () => navigate(1), "Next change");
        prev.disabled = next.disabled = !list.length;
        nav.append(position, prev, next);
        if (current?.label) nav.append(node("span", current.label));
        const removal = node("label", "");
        const check = node("input");
        check.type = "checkbox"; check.checked = showRemoved; check.dataset.contributionControl = "removed";
        check.addEventListener("change", () => { showRemoved = check.checked; index = 0; publish(); });
        removal.append(check, doc.createTextNode("Show removed")); nav.append(removal);
        bar.append(nav);
        for (const summary of projection.overwrittenSummaries.filter(item => item.actorId === actorId)) {
          bar.append(node("p", summary.text, "contributions-panel__summary"));
        }
      }
      children.push(bar);
    }
    const status = node("p", message, "contributions-panel__status");
    status.setAttribute("role", "status");
    children.push(status);
    panel.replaceChildren(...children);
    if (previous) focus(previous);
  }
  panel.addEventListener("keydown", event => {
    if (event.key !== "Escape" || !open()) return;
    event.preventDefault();
    if (timeframeOpen) { timeframeOpen = false; render(); focus("timeframe"); }
    else close();
  });
  capture();
  publish();
  return {
    update(next) {
      if (disposed) return;
      const wasOpen = open(), wasSorting = sorting;
      if (next.role !== undefined) role = next.role;
      if (next.sorting !== undefined) sorting = next.sorting;
      if (next.autoOpen !== undefined) autoOpen = next.autoOpen;
      if (next.projection) { ++filterVersion; acceptProjection(next.projection); }
      capture();
      if (wasOpen !== open() || wasSorting !== sorting) publish();
      else render();
    },
    destroy() {
      disposed = true; ++filterVersion; panel.remove();
    },
  };
}
