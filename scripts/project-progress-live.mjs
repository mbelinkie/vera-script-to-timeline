import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { realpathSync } from "node:fs";
import { readFile, rename, rm } from "node:fs/promises";
import { URL } from "node:url";

const DEFAULT_REFRESH_INTERVAL_MS = 15 * 60_000;
const RETRY_INTERVAL_MS = 5 * 60_000;
const MANUAL_COOLDOWN_MS = 30_000;
const SNAPSHOT_TTL_MS = 16 * 60_000;
const SERVER_PROTOCOL = "2";
const LOCAL_ISSUE_URL = /^https:\/\/github\.com\/mbelinkie\/(vera-script-to-timeline|vera-research-video-clips)\/issues\/([1-9]\d*)$/;
const LOCAL_APP_URL = /^codex:\/\/threads\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
const BROWSER_URL = /^https:\/\/chatgpt\.com\/c\/[A-Za-z0-9_-]{8,128}$/;

export function progressSourceIdentity(repositoryRoot, headCommit) {
  if (typeof headCommit !== "string" || !/^[a-f0-9]{40,64}$/i.test(headCommit)) {
    throw new Error("Dashboard source revision is invalid");
  }
  return createHash("sha256")
    .update(`${realpathSync(repositoryRoot)}\0${headCommit}\0${SERVER_PROTOCOL}`, "utf8")
    .digest("hex");
}

function errorText(error) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function nextAllowedRetry(error, currentTime) {
  const snapshot = error?.snapshot;
  const snapshotReset = Date.parse(snapshot?.resetAt ?? "");
  const typedRetryAfter = Number(snapshot?.retryAfter);
  const typedDeadlines = [];
  if (Number.isFinite(snapshotReset)) typedDeadlines.push(snapshotReset);
  if (Number.isSafeInteger(typedRetryAfter) && typedRetryAfter > 0) {
    typedDeadlines.push(Math.min(currentTime + typedRetryAfter * 1000, 8_640_000_000_000_000));
  }
  if (typedDeadlines.length) return Math.max(...typedDeadlines);

  const text = errorText(error);
  const reset = text.match(/Safe retry:\s*at or after\s+(\S+)|Do not retry before that reset\s*\((\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z)/i);
  const resetAt = Date.parse(reset?.[1] ?? reset?.[2] ?? "");
  if (Number.isFinite(resetAt)) return resetAt;

  const retryAfter = text.match(/Do not retry for at least\s+(\d+)s\b/i);
  const seconds = Number(retryAfter?.[1]);
  if (Number.isSafeInteger(seconds) && seconds > 0) {
    return Math.min(currentTime + seconds * 1000, 8_640_000_000_000_000);
  }
  return currentTime + RETRY_INTERVAL_MS;
}

function publicRefreshError(message) {
  const text = errorText(message).toLowerCase();
  if (text.includes("secondary rate limit") || text.includes("do not retry for at least")) {
    return "GitHub is rate limiting dashboard refreshes; the saved view may be stale.";
  }
  if (text.includes("graphql budget") || text.includes("rate_limited") || text.includes("rate limit")) {
    return "GitHub's read budget is unavailable; the saved view may be stale.";
  }
  return "GitHub refresh failed; the saved view may be stale.";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setHtmlAttribute(tag, name, value) {
  const attribute = new RegExp(`\\s${name}(?=\\s|=|>)(?:=(?:"[^"]*"|'[^']*'|[^\\s>]+))?`, "i");
  const clean = tag.replace(attribute, "");
  return `${clean.slice(0, -1)} ${name}="${escapeHtml(value)}">`;
}

function staleWorkflowContent(html) {
  const openingTags = /<([a-z][a-z0-9:-]*)\b[^>]*>/gi;
  let result = "";
  let cursor = 0;
  let match;
  while ((match = openingTags.exec(html))) {
    const hasWorkflowStatus = /\bdata-workflow-status(?=\s|=|>)/i.test(match[0]);
    const hasWorkflowNext = /\bdata-workflow-next(?=\s|=|>)/i.test(match[0]);
    const freshChip = /\bclass=["'][^"']*\bwf-chip\b[^"']*["']/i.test(match[0])
      && /\bdata-requires-fresh(?=\s|=|>)/i.test(match[0]);
    if (!hasWorkflowStatus && !hasWorkflowNext && !freshChip) continue;
    const tagName = match[1];
    const tagPattern = new RegExp(`<\\/?${tagName}\\b[^>]*>`, "gi");
    tagPattern.lastIndex = openingTags.lastIndex;
    let depth = 1;
    let endTag;
    let closeStart;
    while ((endTag = tagPattern.exec(html))) {
      if (endTag[0].startsWith("</")) depth -= 1;
      else if (!endTag[0].endsWith("/>")) depth += 1;
      if (depth === 0) {
        closeStart = endTag.index;
        break;
      }
    }
    if (closeStart === undefined) continue;
    result += html.slice(cursor, match.index);
    const marker = hasWorkflowNext ? "data-workflow-next" : "data-workflow-status";
    const text = hasWorkflowNext ? "Unknown · Refresh sources before acting." : "Stale · needs refresh";
    result += `${setHtmlAttribute(match[0], marker, "stale")}${text}</${tagName}>`;
    cursor = tagPattern.lastIndex;
    openingTags.lastIndex = cursor;
  }
  return result + html.slice(cursor);
}

function markWorkflowStale(html) {
  let document = html.replace(/<html\b[^>]*>/i, (tag) => setHtmlAttribute(tag, "data-snapshot-stale", "true"));
  document = document.replace(/<[a-z][a-z0-9:-]*\b[^>]*>/gi, (tag) =>
    /\bclass=["'][^"']*\bworkflow-queue\b[^"']*["']/i.test(tag)
      ? setHtmlAttribute(tag, "data-stale", "true")
      : tag);
  document = document.replace(/<a\b[^>]*\bdata-requires-fresh(?=\s|=|>)(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?[^>]*>/gi, (tag) => {
    const withoutHref = tag.replace(/\s+href=(?:"[^"]*"|'[^']*'|[^\s>]+)/i, "");
    return setHtmlAttribute(setHtmlAttribute(withoutHref, "aria-disabled", "true"), "tabindex", "-1");
  });
  return staleWorkflowContent(document);
}

function staleBanner(state) {
  const reason = state.error ?? "The saved dashboard is older than 16 minutes.";
  const updated = state.updatedAt ? ` Last successful refresh: ${state.updatedAt}.` : " No successful refresh is saved yet.";
  return `<div role="status" data-dashboard-stale-banner="true" style="padding:12px 20px;background:#75551a;color:#fff;font:14px/1.5 system-ui,sans-serif;overflow-wrap:anywhere">${escapeHtml(reason + updated)} Refresh to verify current workflow status.</div>`;
}

function localSessionTarget(result, surface) {
  if (result?.status === "verified-local") {
    if (surface === "browser") return BROWSER_URL.test(result.browserUrl ?? "") ? result.browserUrl : null;
    return LOCAL_APP_URL.test(result.appUrl ?? "") ? result.appUrl : null;
  }
  if (result?.status === "web-only" && surface !== "app") {
    return BROWSER_URL.test(result.browserUrl ?? "") ? result.browserUrl : null;
  }
  return null;
}

function waitingPage() {
  // Unlike a saved progress snapshot, this status page is available before the
  // first successful GitHub download. All error text is inserted as textContent.
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VERA Progress — Waiting for GitHub</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { max-width: 720px; margin: 10vh auto; padding: 24px; line-height: 1.6; }
    h1 { margin-bottom: 4px; }
    #status { white-space: pre-wrap; overflow-wrap: anywhere; }
    .note { opacity: .8; }
  </style>
</head>
<body>
  <h1>VERA Progress</h1>
  <p>No dashboard snapshot is saved yet. The local server is running; GitHub data is temporarily unavailable.</p>
  <p id="status" role="status">Checking status…</p>
  <p class="note">This page will automatically switch to your dashboard after a successful refresh.</p>
  <script>
    const loadedVersion = Number(document.documentElement.dataset.snapshotVersion || 1);
    async function checkStatus() {
      if (document.hidden) return;
      try {
        const reply = await fetch('/status', { cache: 'no-store' });
        if (!reply.ok) throw new Error('Status endpoint unavailable');
        const state = await reply.json();
        if (state.version > loadedVersion) { location.reload(); return; }
        document.getElementById('status').textContent = state.refreshing
          ? 'Checking GitHub…'
          : (state.error || (state.stale ? 'The saved dashboard is stale.' : 'Waiting for the first successful download…'));
      } catch {
        document.getElementById('status').textContent = 'Dashboard connection unavailable.';
      }
    }
    document.addEventListener('visibilitychange', checkStatus);
    window.addEventListener('focus', checkStatus);
    setInterval(checkStatus, 20000);
    void checkStatus();
  </script>
</body>
</html>`;
}

/**
 * Serve a locally generated VERA dashboard. GitHub reads occur only during
 * initial generation, when a browser is watching, or on manual refresh.
 * Failures retain the last good snapshot and respect the GraphQL retry budget.
 *
 * @param {{outputPath:string, sourceId:string, generate:(destination:string)=>Promise<unknown>,
 *   resolveLocalSession?:(issueUrl:string)=>Promise<object>,
 *   refreshIntervalMs?:number, now?:()=>number, port?:number, host?:string,
 *   initialError?:unknown, initialUpdatedAt?:number|null}} options
 */
export async function startProgressServer(options) {
  const {
    outputPath,
    sourceId,
    generate,
    resolveLocalSession,
    refreshIntervalMs = DEFAULT_REFRESH_INTERVAL_MS,
    now = Date.now,
    port = 0,
    host = "127.0.0.1",
    initialError = null,
    initialUpdatedAt,
  } = options;
  if (!Number.isInteger(refreshIntervalMs) || refreshIntervalMs < 60_000) {
    throw new Error("Dashboard refresh interval must be at least one minute");
  }
  if (typeof sourceId !== "string" || !/^[a-f0-9]{64}$/.test(sourceId)) {
    throw new Error("Dashboard source identity is invalid");
  }
  if (initialUpdatedAt !== undefined && initialUpdatedAt !== null && !Number.isFinite(initialUpdatedAt)) {
    throw new Error("Dashboard snapshot time is invalid");
  }

  let version = 1;
  let lastUpdated = initialUpdatedAt === undefined
    ? (initialError ? null : now())
    : initialUpdatedAt;
  let lastAttempt = now();
  let lastManual = -Infinity;
  let error = initialError === null ? null : publicRefreshError(initialError);
  let retryNotBefore = initialError === null ? 0 : nextAllowedRetry(initialError, now());
  let pending = null;
  const tempPath = `${outputPath}.refresh-${process.pid}`;

  function snapshot() {
    const age = lastUpdated === null ? Infinity : now() - lastUpdated;
    return {
      version,
      updatedAt: lastUpdated === null ? null : new Date(lastUpdated).toISOString(),
      refreshing: pending !== null,
      error,
      stale: error !== null || !Number.isFinite(age) || age < 0 || age > SNAPSHOT_TTL_MS,
      retryAt: retryNotBefore > now() ? new Date(retryNotBefore).toISOString() : null,
      sourceId,
      serverProtocol: SERVER_PROTOCOL,
      refreshIntervalSeconds: Math.round(refreshIntervalMs / 1000),
    };
  }

  // Single-flight: concurrent tabs and clicks share one refresh. Writing to a
  // temporary path prevents partially written HTML from reaching any browser.
  function refresh({ manual = false } = {}) {
    if (pending) {
      const current = pending;
      return current.then(() => snapshot());
    }
    const time = now();
    if (time < retryNotBefore) return Promise.resolve(snapshot());
    if (manual) {
      if (time - lastManual < MANUAL_COOLDOWN_MS) return Promise.resolve(snapshot());
      lastManual = time;
    } else if (time - lastAttempt < (error ? RETRY_INTERVAL_MS : refreshIntervalMs)) {
      return Promise.resolve(snapshot());
    }
    lastAttempt = time;
    pending = (async () => {
      try {
        await generate(tempPath);
        await rename(tempPath, outputPath);
        version += 1;
        lastUpdated = now();
        error = null;
        retryNotBefore = 0;
      } catch (cause) {
        error = publicRefreshError(cause);
        retryNotBefore = nextAllowedRetry(cause, now());
        await rm(tempPath, { force: true }).catch(() => {});
      }
    })();
    const current = pending;
    return current.then(() => {
      if (pending === current) pending = null;
      return snapshot();
    });
  }

  const server = createServer(async (request, response) => {
    response.setHeader("Cache-Control", "no-store, max-age=0");
    response.setHeader("X-Content-Type-Options", "nosniff");
    try {
      const port = server.address()?.port;
      const authorities = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
      if (!authorities.has(request.headers.host)
        || (request.headers.origin && ![...authorities].some((host) => request.headers.origin === `http://${host}`))) {
        response.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Local dashboard origin required.");
        return;
      }
      const route = new URL(request.url ?? "/", "http://localhost").pathname;
      if (request.method === "GET" && route === "/") {
        // Version travels with the served snapshot, not with a later status
        // request, so a racing refresh cannot strand stale content.
        const servedVersion = version;
        const state = snapshot();
        let html;
        let hasSnapshot = true;
        try {
          html = await readFile(outputPath, "utf8");
        } catch (cause) {
          if (cause?.code !== "ENOENT") throw cause;
          hasSnapshot = false;
          html = waitingPage();
        }
        if (hasSnapshot && state.stale) {
          html = markWorkflowStale(html).replace(/(<body\b[^>]*>)/i, (_, bodyTag) => bodyTag + staleBanner(state));
        }
        const document = html.replace(/<html\b[^>]*>/i, (tag) => {
          const withVersion = setHtmlAttribute(tag, "data-snapshot-version", String(servedVersion));
          return state.stale && !hasSnapshot
            ? setHtmlAttribute(withVersion, "data-snapshot-stale", "true")
            : withVersion;
        });
        response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        response.end(document);
      } else if (request.method === "GET" && route === "/status") {
        void refresh(); // Browser polling triggers refresh only when due.
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify(snapshot()));
      } else if (request.method === "POST" && route === "/refresh"
        && request.headers["x-vera-refresh"] === "1") {
        const result = await refresh({ manual: true });
        response.writeHead(result.stale ? 503 : 200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify(result));
      } else if (request.method === "GET" && route === "/local-session") {
        response.setHeader("Referrer-Policy", "no-referrer");
        const target = new URL(request.url ?? "/local-session", "http://localhost");
        const issues = target.searchParams.getAll("issue");
        const surfaces = target.searchParams.getAll("surface");
        const issueMatch = issues.length === 1 ? LOCAL_ISSUE_URL.exec(issues[0]) : null;
        const issueNumber = Number(issueMatch?.[2]);
        const knownParameters = [...target.searchParams.keys()].every((key) => ["issue", "surface"].includes(key));
        if (!issueMatch || !Number.isSafeInteger(issueNumber) || !knownParameters
          || surfaces.length > 1 || (surfaces.length === 1 && !["app", "browser"].includes(surfaces[0]))) {
          response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
          response.end("Invalid local session request.");
          return;
        }
        const state = snapshot();
        if (state.stale || state.refreshing || !resolveLocalSession) {
          response.writeHead(409, { "Content-Type": "text/plain; charset=utf-8" });
          response.end("Local session link unavailable; refresh the dashboard and try again.");
          return;
        }
        let result;
        try {
          result = await resolveLocalSession(issues[0]);
        } catch {
          response.writeHead(409, { "Content-Type": "text/plain; charset=utf-8" });
          response.end("Local session link unavailable; refresh the dashboard and try again.");
          return;
        }
        const destination = localSessionTarget(result, surfaces[0] ?? null);
        if (!destination) {
          response.writeHead(409, { "Content-Type": "text/plain; charset=utf-8" });
          response.end("Local session link unavailable; refresh the dashboard and try again.");
          return;
        }
        response.writeHead(303, { Location: destination, "Referrer-Policy": "no-referrer" });
        response.end();
      } else {
        response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Not found");
      }
    } catch {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Dashboard unavailable.");
    }
  });

  try {
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, host, () => {
        server.off("error", reject);
        resolve();
      });
    });
  } catch (cause) {
    server.close();
    throw cause;
  }
  const address = server.address();
  return {
    url: `http://${host}:${address.port}/`,
    snapshot,
    refresh,
    close: () => new Promise((resolve, reject) => {
      server.close((cause) => cause ? reject(cause) : resolve());
    }),
  };
}
