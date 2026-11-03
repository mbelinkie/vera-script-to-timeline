import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { URL } from "node:url";

import { progressSourceIdentity, startProgressServer } from "./project-progress-live.mjs";

const fetch = globalThis.fetch.bind(globalThis);
const ISSUE = "https://github.com/mbelinkie/vera-script-to-timeline/issues/401";
const APP_URL = "codex://threads/12345678-1234-1234-1234-123456789abc";
const BROWSER_URL = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc";
const PAGE = `<!doctype html><html lang="en"><body><main class="workflow-queue">
  <div class="wf-next" data-workflow-next="true"><span>Codex</span><span>Implementation ready</span></div>
  <a data-requires-fresh href="/local-session?issue=${encodeURIComponent(ISSUE)}">Open session</a>
  <a href="https://github.com/mbelinkie/vera-script-to-timeline/issues/401">Issue</a>
  <span class="wf-chip" data-workflow-status="approved-current" data-requires-fresh="true"><span>Chat</span><strong>Approved current</strong></span>
  <span class="wf-chip" data-requires-fresh="true"><span>CI</span><strong>Passed</strong></span>
</main></body></html>`;

async function createServer(t, options = {}) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-live-"));
  const outputPath = path.join(directory, "index.html");
  if (options.html !== undefined) await writeFile(outputPath, options.html, "utf8");
  const now = options.now ?? (() => Date.now());
  const server = await startProgressServer({
    outputPath,
    sourceId: progressSourceIdentity(directory, "a".repeat(40)),
    generate: options.generate ?? (async (destination) => writeFile(destination, PAGE, "utf8")),
    now,
    ...(options.refreshIntervalMs ? { refreshIntervalMs: options.refreshIntervalMs } : {}),
    ...(options.initialError !== undefined ? { initialError: options.initialError } : {}),
    ...(options.initialUpdatedAt !== undefined ? { initialUpdatedAt: options.initialUpdatedAt } : {}),
    ...(options.resolveLocalSession ? { resolveLocalSession: options.resolveLocalSession } : {}),
  });
  t.after(async () => {
    await server.close();
    await rm(directory, { recursive: true, force: true });
  });
  return { directory, outputPath, server };
}

async function request(server, route, init) {
  return fetch(new URL(route, server.url), { redirect: "manual", ...init });
}

test("source identity hides the checkout path and changes for another checkout or head", async (t) => {
  const first = await mkdtemp(path.join(os.tmpdir(), "vera-progress-id-"));
  const second = await mkdtemp(path.join(os.tmpdir(), "vera-progress-id-"));
  t.after(async () => {
    await rm(first, { recursive: true, force: true });
    await rm(second, { recursive: true, force: true });
  });
  const id = progressSourceIdentity(first, "a".repeat(40));
  assert.match(id, /^[a-f0-9]{64}$/);
  assert.equal(progressSourceIdentity(first, "a".repeat(40)), id);
  assert.notEqual(progressSourceIdentity(second, "a".repeat(40)), id);
  assert.notEqual(progressSourceIdentity(first, "b".repeat(40)), id);
  assert.equal(id.includes(first), false);
});

test("overlapping refreshes share one atomic write and preserve last-good HTML until rename", async (t) => {
  let now = 100_000;
  let calls = 0;
  let releaseGeneration;
  let startedGeneration;
  const generationStarted = new Promise((resolve) => { startedGeneration = resolve; });
  const generationGate = new Promise((resolve) => { releaseGeneration = resolve; });
  const { outputPath, server } = await createServer(t, {
    now: () => now,
    refreshIntervalMs: 60_000,
    initialUpdatedAt: now,
    html: PAGE,
    generate: async (destination) => {
      calls += 1;
      startedGeneration();
      await generationGate;
      await writeFile(destination, "<html lang=\"en\"><body>new snapshot</body></html>", "utf8");
    },
  });

  const first = server.refresh({ manual: true });
  await generationStarted;
  const second = request(server, "/refresh", {
    method: "POST",
    headers: { "x-vera-refresh": "1" },
  });
  assert.match(await readFile(outputPath, "utf8"), /workflow-queue/);
  releaseGeneration();
  const firstState = await first;
  const secondResponse = await second;
  assert.equal(secondResponse.status, 200);
  assert.equal((await secondResponse.json()).version, 2);
  assert.equal(firstState.version, 2);
  assert.equal(calls, 1);
  assert.match(await readFile(outputPath, "utf8"), /new snapshot/);
});

test("only explicit navigation resolves private sessions; ordinary reads wait for the interval", async (t) => {
  let calls = 0;
  let sessionCalls = 0;
  const { server } = await createServer(t, {
    html: PAGE,
    generate: async (destination) => {
      calls += 1;
      await writeFile(destination, PAGE, "utf8");
    },
    resolveLocalSession: async () => {
      sessionCalls += 1;
      return { status: "verified-local", appUrl: APP_URL };
    },
  });

  assert.equal((await request(server, "/")).status, 200);
  const status = await request(server, "/status");
  assert.equal(status.status, 200);
  const statusBody = await status.json();
  assert.equal(statusBody.stale, false);
  assert.match(statusBody.sourceId, /^[a-f0-9]{64}$/);
  assert.equal(statusBody.serverProtocol, "2");
  assert.equal((await request(server, "/unknown")).status, 404);
  assert.equal((await request(server, "/refresh")).status, 404);
  assert.equal((await request(server, "/refresh", { method: "POST" })).status, 404);
  assert.equal((await request(server, "/status", { method: "POST" })).status, 404);
  assert.equal((await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}`, { method: "POST" })).status, 404);
  const refresh = await request(server, "/refresh", {
    method: "POST",
    headers: { "x-vera-refresh": "1" },
  });
  assert.equal(refresh.status, 200);
  assert.equal(calls, 1);
  assert.equal(sessionCalls, 0);
});

test("explicit local-session navigation validates issue, status, destination, and referrer policy", async (t) => {
  const sessionCalls = [];
  const { server } = await createServer(t, {
    html: PAGE,
    resolveLocalSession: async (issueUrl) => {
      sessionCalls.push(issueUrl);
      if (issueUrl.endsWith("/402")) return { status: "web-only", browserUrl: BROWSER_URL };
      if (issueUrl.endsWith("/403")) return { status: "wrong-device", browserUrl: BROWSER_URL };
      if (issueUrl.endsWith("/404")) return { status: "verified-local", appUrl: "javascript:alert(1)" };
      if (issueUrl.endsWith("/405")) return { status: "missing", reason: "private mapping detail" };
      if (issueUrl.endsWith("/406")) return { status: "stale", reason: "private mapping detail" };
      if (issueUrl.endsWith("/407")) throw new Error("private /Users path and thread 12345678-1234-1234-1234-123456789abc");
      return { status: "verified-local", appUrl: APP_URL, browserUrl: BROWSER_URL };
    },
  });

  const app = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}`);
  assert.equal(app.status, 303);
  assert.equal(app.headers.get("location"), APP_URL);
  assert.equal(app.headers.get("referrer-policy"), "no-referrer");
  assert.equal(await app.text(), "");

  const browser = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}&surface=browser`);
  assert.equal(browser.status, 303);
  assert.equal(browser.headers.get("location"), BROWSER_URL);

  const webOnly = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/402"))}`);
  assert.equal(webOnly.status, 303);
  assert.equal(webOnly.headers.get("location"), BROWSER_URL);

  for (const issueUrl of [
    "https://github.com/mbelinkie/vera-script-to-timeline/issues/0",
    "https://github.com/other/vera-script-to-timeline/issues/401",
    "https://github.com/mbelinkie/vera-script-to-timeline/pull/401",
    `${ISSUE}?x=1`,
  ]) {
    const invalid = await request(server, `/local-session?issue=${encodeURIComponent(issueUrl)}`);
    assert.equal(invalid.status, 400);
  }

  const wrongDevice = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/403"))}&surface=browser`);
  assert.equal(wrongDevice.status, 409);
  const unsafeApp = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/404"))}`);
  assert.equal(unsafeApp.status, 409);
  const missing = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/405"))}`);
  const stale = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/406"))}`);
  const unavailable = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE.replace("/401", "/407"))}`);
  assert.equal(missing.status, 409);
  assert.equal(stale.status, 409);
  assert.equal(unavailable.status, 409);
  assert.doesNotMatch(await wrongDevice.text(), /12345678|wrong-device/);
  assert.doesNotMatch(await missing.text(), /private mapping/);
  assert.doesNotMatch(await unavailable.text(), /Users|12345678/);
  assert.equal(sessionCalls.length, 8);
});

test("stale snapshots disable workflow links and replace current approval labels", async (t) => {
  const now = Date.now();
  const privateFailure = "GitHub GraphQL budget exhausted at /Users/private; codex://threads/12345678-1234-1234-1234-123456789abc token=secret";
  const { server } = await createServer(t, {
    html: PAGE,
    initialUpdatedAt: now,
    now: () => now,
    generate: async () => { throw new Error(privateFailure); },
  });

  const refresh = await request(server, "/refresh", {
    method: "POST",
    headers: { "x-vera-refresh": "1" },
  });
  assert.equal(refresh.status, 503);
  const state = await refresh.json();
  assert.equal(state.stale, true);
  assert.match(state.error, /GitHub/);
  assert.doesNotMatch(JSON.stringify(state), /Users\/private|12345678|secret/);

  const page = await request(server, "/");
  const html = await page.text();
  assert.match(html, /data-snapshot-stale="true"/);
  assert.match(html, /class="workflow-queue" data-stale="true"/);
  assert.match(html, /data-workflow-next="stale">Unknown · Refresh sources before acting\.<\/div>/);
  assert.doesNotMatch(html, /Implementation ready/);
  assert.match(html, /data-workflow-status="stale"[^>]*>Stale · needs refresh<\/span>/);
  assert.doesNotMatch(html, /Approved current/);
  assert.doesNotMatch(html, /Passed/);
  assert.match(html, /data-requires-fresh[^>]*aria-disabled="true"[^>]*tabindex="-1"/);
  assert.doesNotMatch(html, /href="\/local-session/);
  assert.ok(html.includes('href="https://github.com/mbelinkie/vera-script-to-timeline/issues/401"'));
  assert.ok(html.includes(">Issue</a>"));
  assert.doesNotMatch(html, /Users\/private|12345678|secret/);
});

test("staleness follows the 16-minute TTL even without a refresh error", async (t) => {
  const now = Date.now();
  let calls = 0;
  const { server } = await createServer(t, {
    html: PAGE,
    initialUpdatedAt: now - 17 * 60_000,
    now: () => now,
    generate: async (destination) => {
      calls += 1;
      await writeFile(destination, PAGE, "utf8");
    },
    resolveLocalSession: async () => {
      calls += 100;
      return { status: "verified-local", appUrl: APP_URL };
    },
  });

  const status = await (await request(server, "/status")).json();
  assert.equal(status.stale, true);
  assert.equal(status.error, null);
  const page = await request(server, "/");
  assert.match(await page.text(), /data-snapshot-stale="true"/);
  const session = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}`);
  assert.equal(session.status, 409);
  assert.equal(calls, 0);
});

test("startup failure without a last-good file serves a generic stale waiting page", async (t) => {
  const now = Date.now();
  const privateFailure = "GitHub auth failed at /Users/private/.config with token=secret";
  const { server } = await createServer(t, {
    initialError: privateFailure,
    initialUpdatedAt: null,
    now: () => now,
  });
  const status = await (await request(server, "/status")).json();
  assert.equal(status.stale, true);
  assert.doesNotMatch(JSON.stringify(status), /Users\/private|secret/);
  const page = await request(server, "/");
  const html = await page.text();
  assert.equal(page.status, 200);
  assert.match(html, /No dashboard snapshot is saved yet/);
  assert.match(html, /data-snapshot-stale="true"/);
  assert.doesNotMatch(html, /Users\/private|secret/);
});

test("canonical safe-retry, reset, and Retry-After messages gate every refresh path", async (t) => {
  const start = Date.now();
  const cases = [
    [`Insufficient GitHub GraphQL budget. Safe retry: at or after ${new Date(start + 60_000).toISOString()} (in 60s).`, start + 60_000],
    [`GitHub GraphQL budget is exhausted. Do not retry before that reset (${new Date(start + 90_000).toISOString()}; in 90s).`, start + 90_000],
    ["GitHub secondary rate limit is active. Do not retry for at least 120s; no request attempted.", start + 120_000],
    [Object.assign(new Error("GitHub secondary rate limit is active."), {
      snapshot: { resetAt: new Date(start + 30_000).toISOString(), retryAfter: 180 },
    }), start + 180_000],
  ];
  for (const [message, deadline] of cases) {
    let now = start;
    let calls = 0;
    const { server } = await createServer(t, {
      initialError: message,
      initialUpdatedAt: start - 17 * 60_000,
      now: () => now,
      generate: async (destination) => {
        calls += 1;
        await writeFile(destination, PAGE, "utf8");
      },
    });
    const before = await server.refresh({ manual: true });
    assert.equal(before.stale, true);
    assert.equal(before.retryAt, new Date(deadline).toISOString());
    assert.equal(calls, 0);
    now = deadline - 1;
    await server.refresh({ manual: true });
    assert.equal(calls, 0);
    now = deadline + 1;
    const after = await server.refresh({ manual: true });
    assert.equal(calls, 1);
    assert.equal(after.stale, false);
    assert.equal(after.error, null);
  }
});

