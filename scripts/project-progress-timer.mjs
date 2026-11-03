const isoTimestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function parseTimestamp(value) {
  if (typeof value !== "string" || !isoTimestamp.test(value)) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function parseExpiry(value) {
  const time = typeof value === "number" ? value : parseTimestamp(value);
  const date = Number.isFinite(time) && time > 0 ? new Date(time) : null;
  return date && Number.isFinite(date.getTime()) ? { time, iso: date.toISOString() } : null;
}

export function formatElapsed(ms) {
  if (!Number.isFinite(ms) || ms < 0) return null;
  const seconds = Math.floor(ms / 1000);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, "0");
  if (h) return `${h}h ${String(m).padStart(2, "0")}m ${s}s`;
  if (m) return `${m}m ${s}s`;
  return `${seconds}s`;
}

function unavailable(expiry = null) {
  return { label: "Timing unavailable", startedAt: null, endAt: null, expiry, mode: "unavailable" };
}

export function timerModel(entry, { now = Date.now(), expiresAt } = {}) {
  if (!entry || !Number.isFinite(now)) return unavailable();
  const expiry = expiresAt === undefined || expiresAt === null ? null : parseExpiry(expiresAt);
  if (expiresAt !== undefined && expiresAt !== null && !expiry) return unavailable();

  const phase = String(entry.phase ?? "").toLowerCase();
  const running = phase === "running" || phase === "in_progress";
  const waiting = phase === "waiting" || phase === "queued" || phase === "pending";
  const completed = ["completed", "success", "failure", "cancelled", "skipped", "timed_out"].includes(phase);
  if (!running && !waiting && !completed) return unavailable(expiry?.iso ?? null);

  const startValue = waiting ? entry.queuedAt : running ? entry.attempt?.startedAt : entry.attempt?.startedAt ?? entry.startedAt;
  const start = parseTimestamp(startValue);
  if (start === null || start > now) return unavailable(expiry?.iso ?? null);
  const checked = entry.checkedAt === undefined || entry.checkedAt === null ? null : parseTimestamp(entry.checkedAt);
  if (entry.checkedAt != null && (checked === null || checked > now)) return unavailable(expiry?.iso ?? null);
  if ((running || waiting) && (checked === null || checked < start)) return unavailable(expiry?.iso ?? null);

  if (expiry && expiry.time <= now) {
    const endValue = completed ? entry.completedAt : entry.checkedAt;
    const end = parseTimestamp(endValue);
    if (end === null || end < start || end > now || checked === null || (completed && checked < end)) return unavailable(expiry.iso);
    const duration = formatElapsed(end - start);
    if (duration === null) return unavailable(expiry.iso);
    return {
      label: `Last checked ${completed ? "" : waiting ? "queued " : ""}${duration}`.trim(),
      startedAt: startValue,
      endAt: endValue,
      expiry: expiry.iso,
      mode: "stale",
    };
  }

  if (waiting || running) {
    if (!expiry) return unavailable();
    const duration = formatElapsed(now - start);
    if (duration === null) return unavailable(expiry.iso);
    return {
      label: waiting ? `Queued ${duration}` : duration,
      startedAt: startValue,
      endAt: entry.checkedAt,
      expiry: expiry.iso,
      mode: waiting ? "waiting" : "running",
    };
  }

  const end = parseTimestamp(entry.completedAt);
  if (end === null || end < start || end > now) return unavailable(expiry?.iso ?? null);
  return {
    label: formatElapsed(end - start) ?? "Timing unavailable",
    startedAt: startValue,
    endAt: entry.completedAt,
    expiry: expiry?.iso ?? null,
    mode: "completed",
  };
}

export const timerClientScript = `(() => {
  const selectors = "[data-ci-timer]";
  const wallStart = Date.now();
  const monoStart = performance.now();
  let clockDrifted = false;
  const read = (value) => {
    const time = typeof value === "string" ? Date.parse(value) : NaN;
    return Number.isFinite(time) ? time : null;
  };
  const elapsed = (ms) => {
    if (!Number.isFinite(ms) || ms < 0) return null;
    const seconds = Math.floor(ms / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const rest = String(seconds % 60).padStart(2, "0");
    if (hours) return hours + "h " + String(minutes).padStart(2, "0") + "m " + rest + "s";
    if (minutes) return minutes + "m " + rest + "s";
    return seconds + "s";
  };
  const show = (element, label) => { if (label && element.textContent !== label) element.textContent = label; };
  function render() {
    const now = Date.now();
    if (Math.abs(now - (wallStart + performance.now() - monoStart)) > 5000) clockDrifted = true;
    document.querySelectorAll(selectors).forEach((element) => {
      const mode = element.dataset.timerMode;
      if (mode === "unavailable") return;
      const start = read(element.dataset.startedAt);
      const expiry = read(element.dataset.expiresAt);
      const end = read(element.dataset.endedAt);
      if (mode === "completed") {
        const duration = end === null || start === null || end < start || end > now ? null : elapsed(end - start);
        if (expiry !== null && expiry <= now) {
          element.dataset.timerMode = "unavailable";
          show(element, duration ? "Last checked " + duration : "Timing needs refresh");
        } else show(element, duration || "Timing needs refresh");
        return;
      }
      if (mode !== "running" && mode !== "waiting") return;
      if (clockDrifted || start === null || expiry === null || start > now) {
        element.dataset.timerMode = "unavailable";
        show(element, "Timing needs refresh");
        return;
      }
      if (expiry <= now) {
        const duration = end === null || end < start || end > now ? null : elapsed(end - start);
        element.dataset.timerMode = "unavailable";
        show(element, duration ? "Last checked " + (mode === "waiting" ? "queued " : "") + duration : "Timing needs refresh");
        return;
      }
      const duration = elapsed(now - start);
      show(element, duration ? (mode === "waiting" ? "Queued " : "") + duration : "Timing needs refresh");
    });
  }
  render();
  setInterval(render, 1000);
  document.addEventListener("visibilitychange", render);
  new MutationObserver(render).observe(document.documentElement, { childList: true, subtree: true });
})();`;
