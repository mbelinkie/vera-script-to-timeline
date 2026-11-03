import assert from "node:assert/strict";
import { access, chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, URL } from "node:url";
import { request as httpRequest } from "node:http";
import { setTimeout } from "node:timers";

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
    ...(options.initialRefresh !== undefined ? { initialRefresh: options.initialRefresh } : {}),
    ...(options.resolveLocalSession ? { resolveLocalSession: options.resolveLocalSession } : {}),
  });
  t.after(async () => {
    await server.close();
    await rm(directory, { recursive: true, force: true });
  });
  return { directory, outputPath, server };
}

async function request(server, route, init) {
  return fetch(new URL(route, server.url), {
    redirect: "manual",
    ...init,
    headers: { "Sec-Fetch-Site": "same-origin", ...(init?.headers ?? {}) },
  });
}

function pageWithExpiry(expiresAt) {
  return PAGE.replace('class="workflow-queue"', `class="workflow-queue" data-workflow-queue data-workflow-expires-at="${expiresAt}"`);
}

async function waitFor(predicate, message, timeoutMs = 5_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.fail(message);
}

test("foreign origins and rebinding hosts cannot refresh or inspect private links", async (t) => {
  let calls = 0;
  const { server } = await createServer(t, { html: PAGE, resolveLocalSession: async () => {
    calls += 1;
    return { status: "verified-local", appUrl: APP_URL };
  } });
  const rebound = await new Promise((resolve, reject) => {
    const req = httpRequest(new URL(`/local-session?issue=${encodeURIComponent(ISSUE)}`, server.url), {
      headers: { Host: "attacker.example" },
    }, (response) => { response.resume(); resolve(response.statusCode); });
    req.on("error", reject);
    req.end();
  });
  assert.equal(rebound, 403);
  for (const headers of [{ Origin: "https://attacker.example" }]) {
    const result = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}`, { headers });
    assert.equal(result.status, 403);
    assert.equal(result.headers.get("location"), null);
    assert.doesNotMatch(await result.text(), /codex:|12345678/);
  }
  assert.equal(calls, 0);
  assert.equal((await request(server, "/status")).status, 200);
});

test("cross-site and metadata-free requests cannot inspect or trigger private dashboard reads", async (t) => {
  let generations = 0;
  let sessionCalls = 0;
  const { server } = await createServer(t, {
    html: PAGE,
    generate: async (destination) => {
      generations += 1;
      await writeFile(destination, PAGE, "utf8");
    },
    resolveLocalSession: async () => {
      sessionCalls += 1;
      return { status: "verified-local", appUrl: APP_URL };
    },
  });
  const requests = [
    ["GET", "/status"],
    ["GET", `/local-session?issue=${encodeURIComponent(ISSUE)}`],
    ["POST", "/refresh", { "x-vera-refresh": "1" }],
  ];
  for (const [method, route, extraHeaders = {}] of requests) {
    for (const fetchSite of ["cross-site", "same-site"]) {
      const response = await request(server, route, {
        method,
        headers: { ...extraHeaders, "Sec-Fetch-Site": fetchSite },
      });
      assert.equal(response.status, 403);
    }
    const response = await fetch(new URL(route, server.url), {
      method,
      redirect: "manual",
      headers: extraHeaders,
    });
    assert.equal(response.status, 403);
  }
  assert.equal(generations, 0);
  assert.equal(sessionCalls, 0);
});

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

test("server serves a stale saved snapshot while the first background refresh is delayed", async (t) => {
  const now = Date.now();
  let releaseGeneration;
  let startedGeneration;
  const generationStarted = new Promise((resolve) => { startedGeneration = resolve; });
  const generationGate = new Promise((resolve) => { releaseGeneration = resolve; });
  const saved = pageWithExpiry(now - 1_000).replace(">Issue</a>", ">Saved issue snapshot</a>");
  const { outputPath, server } = await createServer(t, {
    now: () => now,
    html: saved,
    initialUpdatedAt: now - 17 * 60_000,
    initialRefresh: true,
    generate: async (destination) => {
      startedGeneration();
      await generationGate;
      await writeFile(destination, pageWithExpiry(now + 15 * 60_000), "utf8");
    },
  });
  await generationStarted;

  const status = await (await request(server, "/status")).json();
  assert.equal(status.refreshing, true);
  assert.equal(status.stale, true);
  const page = await request(server, "/");
  assert.match(await page.text(), /Saved issue snapshot/);
  assert.match(await readFile(outputPath, "utf8"), /Saved issue snapshot/);

  releaseGeneration();
  const refreshed = await server.refresh({ manual: true });
  assert.equal(refreshed.refreshing, false);
  assert.equal(refreshed.stale, false);
  assert.equal(refreshed.version, 2);
  assert.match(await readFile(outputPath, "utf8"), /Implementation ready/);
});

test("manual refresh is available immediately after an initial non-rate-limit failure", async (t) => {
  let calls = 0;
  const { server } = await createServer(t, {
    initialRefresh: true,
    generate: async (destination) => {
      calls += 1;
      if (calls === 1) throw new Error("Temporary network failure");
      await writeFile(destination, PAGE, "utf8");
    },
  });
  await waitFor(() => {
    const state = server.snapshot();
    return calls === 1 && state.error !== null && !state.refreshing;
  }, "The initial generation did not fail");

  const refreshed = await server.refresh({ manual: true });
  assert.equal(calls, 2);
  assert.equal(refreshed.stale, false);
  assert.equal(refreshed.error, null);
});

test("CLI serves and prints its URL before the first GitHub generation completes", async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-cli-"));
  const binDirectory = path.join(directory, "bin");
  await mkdir(binDirectory);
  const startedPath = path.join(directory, "gh-started");
  const releasePath = path.join(directory, "gh-release");
  const donePath = path.join(directory, "gh-done");
  const fakeGhPath = path.join(binDirectory, "gh");
  await writeFile(fakeGhPath, [
    "#!/bin/sh",
    'printf started > "$VERA_PROGRESS_TEST_STARTED"',
    'while [ ! -e "$VERA_PROGRESS_TEST_RELEASE" ]; do sleep 0.02; done',
    'printf done > "$VERA_PROGRESS_TEST_DONE"',
    "exit 1",
    "",
  ].join("\n"), "utf8");
  await chmod(fakeGhPath, 0o755);

  let stdout = "";
  const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const child = spawn(process.execPath, [path.join(repositoryRoot, "scripts", "project-progress.mjs"), "--serve"], {
    cwd: repositoryRoot,
    env: {
      ...process.env,
      PATH: `${binDirectory}${path.delimiter}${process.env.PATH ?? ""}`,
      VERA_PROGRESS_REFRESH_MINUTES: "15",
      VERA_PROGRESS_TEST_STARTED: startedPath,
      VERA_PROGRESS_TEST_RELEASE: releasePath,
      VERA_PROGRESS_TEST_DONE: donePath,
    },
    stdio: ["ignore", "pipe", "ignore"],
  });
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => { stdout += chunk; });
  const childExited = new Promise((resolve) => child.once("exit", resolve));
  t.after(async () => {
    await writeFile(releasePath, "");
    await waitFor(async () => {
      try { await access(donePath); return true; } catch { return false; }
    }, "The fake GitHub command did not stop during cleanup", 2_000).catch(() => {});
    if (child.exitCode === null) child.kill("SIGTERM");
    await Promise.race([childExited, new Promise((resolve) => setTimeout(resolve, 2_000))]);
    await rm(directory, { recursive: true, force: true });
  });

  await waitFor(() => stdout.includes("Dashboard: http://127.0.0.1:"), "The CLI did not print a listening dashboard URL");
  await waitFor(async () => {
    try { await access(startedPath); return true; } catch { return false; }
  }, "The first generation did not reach the delayed GitHub command");
  const url = stdout.match(/Dashboard: (http:\/\/127\.0\.0\.1:\d+\/)/)?.[1];
  assert.ok(url);
  const response = await fetch(new URL("status", url), { headers: { "Sec-Fetch-Site": "none" } });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).refreshing, true);
});

test("slow generation schedules the next refresh before evidence expiry", async (t) => {
  const startedAt = 1_800_000_000_000;
  let now = startedAt;
  let calls = 0;
  const expiresAt = startedAt + 16 * 60_000;
  const { server } = await createServer(t, {
    now: () => now,
    refreshIntervalMs: 15 * 60_000,
    generate: async (destination) => {
      calls += 1;
      if (calls === 1) now += 2 * 60_000;
      await writeFile(destination, pageWithExpiry(calls === 1 ? expiresAt : now + 16 * 60_000), "utf8");
    },
  });

  await server.refresh({ manual: true });
  now = startedAt + 12 * 60_000 + 59_000;
  const beforeDue = await (await request(server, "/status")).json();
  assert.equal(beforeDue.refreshing, false);
  assert.equal(calls, 1);

  now = startedAt + 13 * 60_000;
  const atDue = await (await request(server, "/status")).json();
  assert.equal(atDue.refreshing, true);
  await server.refresh();
  assert.equal(calls, 2);
});

test("refresh intervals cannot reach or exceed the evidence TTL", async () => {
  for (const refreshIntervalMs of [16 * 60_000, 30 * 60_000]) {
    await assert.rejects(startProgressServer({
      outputPath: "/tmp/vera-progress-invalid-interval.html",
      sourceId: "a".repeat(64),
      generate: async () => {},
      refreshIntervalMs,
    }), /below the 16-minute evidence TTL/);
  }
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

  const app = await request(server, `/local-session?issue=${encodeURIComponent(ISSUE)}`, {
    headers: { "Sec-Fetch-Site": "none" },
  });
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

