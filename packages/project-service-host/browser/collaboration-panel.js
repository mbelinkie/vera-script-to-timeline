// A read-only view of the collaboration binding. No document, awareness or
// transport writes belong here; retry is the sole injected action.
const syncLabels = {
  "local changes": "Local changes",
  syncing: "Saving…",
  synced: "Synced",
  "sync failed": "Sync failed",
};

/**
 * binding.read() returns { state: SyncState, hasUnsyncedChanges, role, hold,
 * recoverableFailure, actorId, roster: RosterEntry[], presence: Activity[] }.
 * The binding projects ephemeral awareness into Activity records keyed by
 * verified roster actorId: { actorId, selectedRowId?, selectedCardId?, cursor?,
 * recentEdit? }. recentEdit is supplied only for an observed accepted edit.
 * Labels are looked up through authorized metadata, never awareness names.
 * binding.subscribe(listener) returns an unsubscribe function.
 */
export function mountCollaborationPanel({ root, binding, labelForActor, labelForRow, labelForCard }) {
  const doc = root.ownerDocument;
  const win = doc.defaultView;
  const node = (tag, className, text = "") => {
    const el = doc.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
  };
  const panel = node("div", "collaboration-panel");
  const sync = node("span", "collaboration-panel__sync");
  const retry = node("button", "collaboration-panel__retry", "Try again");
  retry.type = "button";
  const presence = node("span", "collaboration-panel__presence");
  presence.setAttribute("role", "group");
  const presenceText = node("span", "collaboration-panel__presence-text");
  presenceText.setAttribute("aria-hidden", "true");
  const reveal = node("span", "collaboration-panel__reveal");
  reveal.setAttribute("role", "tooltip");
  reveal.setAttribute("aria-hidden", "true"); // Full accessible name is on the trigger.
  reveal.hidden = true;
  presence.append(presenceText, reveal);
  const live = node("span", "collaboration-panel__live");
  live.setAttribute("role", "status");
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  panel.append(sync, retry, presence, live);
  root.append(panel);

  let disposed = false, retryPending = false, canRetry = false;
  let lastAnnouncement = "", lastPresence = "";
  let hovered = false, focused = false, dismissed = false;
  const label = actor => labelForActor?.(actor)?.trim() || actor;

  function measure() {
    if (disposed) return;
    const clipped = !presence.hidden && presenceText.scrollWidth > presenceText.clientWidth;
    if (clipped) presence.tabIndex = 0;
    else presence.removeAttribute("tabindex");
    reveal.hidden = !(clipped && !dismissed && (hovered || focused));
    if (!reveal.hidden) {
      const left = presence.getBoundingClientRect().left;
      const available = win.innerWidth - reveal.offsetWidth - 8;
      reveal.style.left = `${Math.max(8, Math.min(left, available)) - left}px`;
    }
  }
  function enter() { hovered = true; dismissed = false; measure(); }
  function leave() { hovered = false; measure(); }
  function focus() { focused = true; dismissed = false; measure(); }
  function blur() { focused = false; measure(); }
  function key(event) {
    if (event.key === "Escape" && !reveal.hidden) {
      dismissed = true;
      measure();
      event.stopPropagation();
    }
  }
  presence.addEventListener("mouseenter", enter);
  presence.addEventListener("mouseleave", leave);
  presence.addEventListener("focus", focus);
  presence.addEventListener("blur", blur);
  doc.addEventListener("keydown", key);
  const resize = new win.ResizeObserver(measure);
  resize.observe(presenceText);
  win.addEventListener("resize", measure);

  function activityLabel(member, activity) {
    const name = label(member.actorId);
    const row = activity?.selectedRowId && labelForRow?.(activity.selectedRowId);
    const card = activity?.selectedCardId && labelForCard?.(activity.selectedCardId);
    if (row && member.canEdit && activity.recentEdit === true) return name + " edited " + row + " · just now";
    if (row && member.canEdit && Number.isInteger(activity.cursor) && activity.cursor >= 0) {
      return name + " is editing " + row;
    }
    if (card) return name + " selected " + card;
    if (row) return name + " selected " + row;
    return name + " is present";
  }

  function render() {
    if (disposed) return;
    const snapshot = binding.read();
    const { state, role, hold, hasUnsyncedChanges } = snapshot;
    const status = state === "offline"
      ? (hasUnsyncedChanges ? "Offline · changes kept here" : "Offline")
      : syncLabels[state];
    sync.textContent = status;
    sync.dataset.state = state;
    // Failed storage is not necessarily retryable (e.g. a revoked edit lease).
    canRetry = state === "sync failed" && snapshot.recoverableFailure === true &&
      hasUnsyncedChanges && !hold && (role === "editor" || role === "producer");
    if (!canRetry) retryPending = false;
    retry.hidden = !canRetry;
    retry.disabled = retryPending;

    const activities = new Map((snapshot.presence ?? []).map(item => [item.actorId, item]));
    const peers = [...new Map(snapshot.roster.map(member => [member.actorId, member])).values()]
      .filter(member => member.actorId !== snapshot.actorId);
    const message = peers.map(member => activityLabel(member, activities.get(member.actorId))).join(" · ");
    if (message !== lastPresence) {
      presenceText.textContent = message;
      reveal.textContent = message;
      presence.setAttribute("aria-label", message);
      lastPresence = message;
      dismissed = false;
    }
    presence.hidden = !message;
    const announcement = [status, message].filter(Boolean).join(". ");
    if (announcement !== lastAnnouncement) {
      live.textContent = announcement;
      lastAnnouncement = announcement;
    }
    measure();
  }

  function onRetry() {
    if (!canRetry || retryPending || disposed) return;
    retryPending = true;
    retry.disabled = true;
    try {
      binding.retry();
    } catch {
      // A synchronous adapter failure has not started an attempt.
      retryPending = false;
      if (!disposed) render();
    }
  }
  retry.addEventListener("click", onRetry);
  const unsubscribe = binding.subscribe(render);
  render();

  return {
    destroy() {
      if (disposed) return;
      disposed = true;
      unsubscribe();
      resize.disconnect();
      win.removeEventListener("resize", measure);
      doc.removeEventListener("keydown", key);
      presence.removeEventListener("mouseenter", enter);
      presence.removeEventListener("mouseleave", leave);
      presence.removeEventListener("focus", focus);
      presence.removeEventListener("blur", blur);
      retry.removeEventListener("click", onRetry);
      panel.remove();
    },
  };
}
