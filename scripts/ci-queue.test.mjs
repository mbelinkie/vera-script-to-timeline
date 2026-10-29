import assert from "node:assert/strict";
import { test } from "node:test";
import { URL } from "node:url";
import { readFileSync } from "node:fs";
import { Queue, STATUS, initialState, parseCommand, validateState } from "./ci-queue.mjs";

const A = "a".repeat(40), B = "b".repeat(40), C = "c".repeat(40), D = "d".repeat(40);
const repository = "owner/repo";
const clone = (value) => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

function fixture() {
  const state = initialState(99);
  state.paused = null;
  state.entries = [1, 2].map((pr) => ({ pr, submitted: B, head: B, ready: true, owner: "owner" }));
  const calls = [], comments = [], runs = [];
  const pulls = new Map([1, 2].map((pr) => [pr, { number: pr, state: "open", draft: false, merged: false, base: { ref: "main", repo: { full_name: repository } }, head: { sha: B, ref: `feature-${pr}`, repo: { full_name: repository } } }]));
  let main = A, revision = 0;
  const github = {
    repository,
    async loadState() { return { sha: String(revision), state: clone(state) }; },
    async saveState(next) { Object.assign(state, clone(next)); revision += 1; return { sha: String(revision), state: clone(state) }; },
    async pages(url) { if (url.endsWith("/commits")) return []; assert.match(url, /issues\/99\/comments/); return clone(comments); },
    async api(method, url, body) {
      const suffix = url.replace(`/repos/${repository}`, "");
      calls.push({ method, suffix, body: clone(body) });
      if (suffix === "/graphql") return { data: { repository: { pullRequest: { closingIssuesReferences: { totalCount: 0 } } } } };
      if (suffix === "/git/ref/heads/main") return { object: { sha: main } };
      if (suffix.startsWith("/git/ref/heads/feature-")) return { object: { sha: pulls.get(Number(suffix.split("-").at(-1))).head.sha } };
      if (suffix.includes("/collaborators/")) return { permission: suffix.includes("outsider") ? "read" : "write" };
      if (suffix === "/branches/main/protection/required_status_checks") return { strict: true, contexts: [STATUS] };
      if (suffix.startsWith("/actions/workflows/validate.yml/runs")) {
        const status = new URL(`https://example.com${suffix}`).searchParams.get("status");
        return { workflow_runs: clone(status ? runs.filter((r) => r.status === status) : runs) };
      }
      if (suffix === "/actions/workflows/validate.yml") return { id: 7, path: ".github/workflows/validate.yml", state: "active" };
      if (suffix.endsWith("/dispatches")) return null;
      if (suffix.startsWith("/compare/")) return { status: "ahead" };
      if (suffix === "/issues/99/comments") { comments.push({ id: comments.length + 100, body: body.body, user: { login: "github-actions[bot]" } }); return comments.at(-1); }
      if (suffix.startsWith("/issues/comments/")) { comments.find((c) => c.id === Number(suffix.split("/").at(-1))).body = body.body; return null; }
      if (suffix.startsWith("/statuses/")) return body;
      const merge = /^\/pulls\/(\d+)\/merge$/.exec(suffix);
      if (merge) {
        const pull = pulls.get(Number(merge[1]));
        assert.equal(body.sha, pull.head.sha);
        assert.equal(body.commit_title, `Deliver PR #${merge[1]}`);
        assert.doesNotMatch(body.commit_message, /(?:closes|fixes|resolves) #/i);
        pull.merged = true; pull.state = "closed"; pull.merge_commit_sha = D; main = D;
        return { merged: true, sha: D };
      }
      const pull = /^\/pulls\/(\d+)$/.exec(suffix);
      if (pull) return clone(pulls.get(Number(pull[1])));
      throw new Error(`Unexpected ${method} ${suffix}`);
    },
  };
  let n = 0;
  const queue = new Queue(github, { now: () => 1000000, uuid: () => `transaction-${++n}`, enabled: true });
  async function load() { const saved = await github.loadState(); queue.state = saved.state; queue.sha = saved.sha; }
  function pass() {
    const expected = state.active.expected;
    runs.length = 0;
    runs.push({ id: n + 1000, display_title: expected.title, workflow_id: 7, head_sha: expected.workflowHead, event: "workflow_dispatch", path: ".github/workflows/validate.yml", run_attempt: 1, status: "completed", conclusion: "success", html_url: `https://github.com/owner/repo/actions/runs/${n + 1000}`, actor: { login: "github-actions[bot]" } });
  }
  return { queue, github, state, calls, comments, runs, pulls, load, pass, setMain: (sha) => { main = sha; } };
}

test("queue command grammar binds readiness to a full SHA and distinct validation intent", () => {
  assert.deepEqual(parseCommand(`/queue ready 12 ${B}`), { action: "ready", pr: 12, head: B });
  assert.equal(parseCommand(`/queue validate 12 ${B}`).action, "validate");
  for (const text of ["/queue ready 12 abc", `/queue ready 0 ${B}`, `/queue ready 12 ${B}\nextra`, "/queue resume please", "text /queue resume"]) assert.equal(parseCommand(text), null);
});

test("corrupt durable state cannot silently restart an empty queue", () => {
  for (const state of [{}, { ...initialState(1), entries: [{ pr: 1 }] }, { ...initialState(1), active: {} }, { ...initialState(1), cursor: -1 }]) assert.throws(() => validateState(state));
  const state = initialState(1); assert.equal(validateState(state), state);
});

test("two entries use one exact validation, protected merge, smoke, then next base", async () => {
  const f = fixture(); await f.load();
  await f.queue.advance();
  assert.equal(f.state.active.phase, "validating");
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/dispatches")).length, 1);
  assert.equal(f.state.active.base, A);
  f.pass(); await f.queue.advance();
  assert.equal(f.state.active.phase, "smoke");
  assert.equal(f.state.entries.length, 2);
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/merge")).length, 1);
  assert.equal(f.state.active.mergeSha, D);
  f.pass(); await f.queue.advance();
  assert.equal(f.state.active.pr, 2);
  assert.equal(f.state.active.base, D);
  assert.equal(f.state.completed.length, 1);
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/dispatches")).length, 3);
});

test("author push after readiness stops before dispatch and preserves waiting entries", async () => {
  const f = fixture(); await f.load(); f.pulls.get(1).head.sha = C;
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.match(f.state.paused.reason, /changed after readiness/);
  assert.equal(f.state.entries.length, 2);
  assert.equal(f.calls.some((c) => c.suffix.endsWith("/dispatches")), false);
});

test("a push during validation cannot reuse green and alerts only once across restarts", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); f.pulls.get(1).head.sha = C;
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.match(f.state.paused.reason, /readiness revoked/);
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.equal(f.comments.filter((c) => c.body.includes("vera-queue-pause:")).length, 1);
  assert.equal(f.calls.some((c) => c.suffix.endsWith("/merge")), false);
});

test("failure persists, duplicates cannot advance, explicit resume retries same entry", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); f.runs[0].conclusion = "failure";
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.ok(f.state.paused); assert.equal(f.state.active.pr, 1);
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/dispatches")).length, 1);
  await f.queue.command({ action: "resume" }, "owner"); await f.queue.advance();
  assert.equal(f.state.paused, null); assert.equal(f.state.active.pr, 1);
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/dispatches")).length, 2);
});

test("main smoke failure preserves delivered merge and blocks the second candidate", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); await f.queue.advance(); f.pass(); f.runs[0].conclusion = "timed_out";
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.ok(f.state.paused); assert.equal(f.pulls.get(1).merged, true); assert.equal(f.state.entries.length, 2);
  await f.queue.command({ action: "resume" }, "owner");
  assert.equal(f.state.active.phase, "smoke");
  assert.equal(f.calls.filter((c) => c.suffix.endsWith("/merge")).length, 1);
});

test("late old green event cannot finish the next transaction", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); const old = clone(f.runs[0]); await f.queue.advance();
  f.runs.splice(0, f.runs.length, old); await f.queue.advance();
  assert.equal(f.state.active.phase, "smoke"); assert.equal(f.state.completed.length, 0);
});

test("validation-only draft never merges even after green", async () => {
  const f = fixture(); await f.load(); f.queue.state.entries = [f.queue.state.entries[0]]; f.queue.state.entries[0].ready = false; f.pulls.get(1).draft = true;
  await f.queue.advance(); f.pass(); await f.queue.advance();
  assert.equal(f.state.active, null); assert.equal(f.state.entries.length, 0);
  assert.equal(f.calls.some((c) => c.suffix.endsWith("/merge")), false);
  assert.equal(f.calls.some((c) => c.suffix.startsWith("/statuses/") && c.body.context === STATUS), false);
});

test("unauthorized public comments cannot enqueue or resume", async () => {
  const f = fixture(); f.state.paused = { id: "hold", reason: "manual" };
  f.comments.push({ id: 1, body: `/queue ready 3 ${B}`, user: { login: "outsider" } }, { id: 2, body: "/queue resume", user: { login: "outsider" } });
  await f.queue.run({ eventName: "issue_comment", event: { issue: { number: 99 } } });
  assert.equal(f.state.entries.length, 2); assert.equal(f.state.paused.reason, "manual");
});

test("interrupted integration is retained and pauses instead of repeating a side effect", async () => {
  const f = fixture(); f.state.active = { id: "interrupted", pr: 1, phase: "integrating", base: A };
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.match(f.state.paused.reason, /Interrupted side effect/);
  assert.equal(f.calls.some((c) => c.suffix === "/merges"), false);
});

test("manual run blocks dispatch; unprotected main blocks automatic delivery", async () => {
  const f = fixture(); await f.load(); f.runs.push({ id: 4, status: "in_progress" });
  await f.queue.advance(); assert.equal(f.state.active, null); assert.equal(f.state.paused, null);
  f.runs.length = 0;
  const api = f.github.api.bind(f.github);
  f.github.api = (method, url, body) => url.endsWith("/required_status_checks") ? Promise.resolve({ strict: false, contexts: [] }) : api(method, url, body);
  await assert.rejects(f.queue.advance(), /Main must require strict/);
});

test("changed base blocks merge even for the exact green head", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); f.setMain(C);
  await assert.rejects(f.queue.advance(), /readiness revoked/);
  assert.equal(f.calls.some((c) => c.suffix.endsWith("/merge")), false);
});

test("integration accepts only the clean two-parent controller result", async () => {
  const f = fixture(); await f.load();
  const api = f.github.api.bind(f.github);
  f.github.api = async (method, url, body) => {
    if (url.includes("/compare/")) return { status: "diverged" };
    if (url.endsWith("/merges")) {
      f.pulls.get(1).head.sha = C;
      return { sha: C, parents: [{ sha: B }, { sha: A }], commit: { message: body.commit_message } };
    }
    return api(method, url, body);
  };
  await f.queue.advance();
  assert.equal(f.state.entries[0].submitted, B);
  assert.equal(f.state.entries[0].head, C);
  assert.equal(f.state.active.candidate, C);
});

test("external failure pauses once; delayed duplicate cannot undo explicit recovery", async () => {
  const f = fixture(); f.state.initializedAt = 0; f.state.entries = [];
  const event = { workflow_run: { id: 8123, display_title: "Manual validation", created_at: "2026-10-29T00:00:00Z", conclusion: "failure" } };
  await f.queue.run({ eventName: "workflow_run", event });
  assert.match(f.state.paused.reason, /outside the transaction failed/);
  await f.queue.command({ action: "resume" }, "owner");
  await f.queue.run({ eventName: "workflow_run", event });
  assert.equal(f.state.paused, null);
});

test("an issue-closing PR body cannot be authorized for automatic merge", async () => {
  const f = fixture(); await f.load(); f.pulls.get(1).body = "Fixes #359";
  await assert.rejects(f.queue.command({ action: "ready", pr: 1, head: B }, "owner"), /auto-closing PR keywords/);
  f.pulls.get(1).body = "CLOSES: #359";
  await assert.rejects(f.queue.command({ action: "ready", pr: 1, head: B }, "owner"), /auto-closing PR keywords/);
});

test("a changed author head must be explicitly reauthorized after pause", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); f.pulls.get(1).head.sha = C;
  await f.queue.run({ eventName: "workflow_run", event: {} });
  await f.queue.command({ action: "ready", pr: 1, head: C }, "owner");
  await f.queue.command({ action: "resume" }, "owner"); await f.queue.advance();
  assert.equal(f.state.active.candidate, C);
});

test("dispatch intent survives a transport uncertainty without being retried", async () => {
  const f = fixture(); const api = f.github.api.bind(f.github);
  let dispatched = 0;
  f.github.api = async (method, url, body) => {
    if (url.endsWith("/dispatches")) {
      dispatched += 1;
      assert.equal(f.state.active.phase, "validating");
      assert.ok(f.state.active.expected.title.includes(B));
      throw new Error("Uncertain transport");
    }
    return api(method, url, body);
  };
  await f.queue.run({ eventName: "workflow_run", event: {} });
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.equal(dispatched, 1); assert.ok(f.state.paused); assert.equal(f.state.entries.length, 2);
});

test("privileged workflow executes only default branch code and no candidate artifacts", () => {
  const workflow = readFileSync(new URL("../.github/workflows/ci-queue.yml", import.meta.url), "utf8");
  assert.match(workflow, /pull_request_target:/);
  assert.match(workflow, /ref: \$\{\{ github\.event\.repository\.default_branch \}\}/);
  assert.match(workflow, /persist-credentials: false/);
  assert.match(workflow, /group: vera-ci-queue-controller\n {2}cancel-in-progress: false/);
  assert.doesNotMatch(workflow, /download-artifact|cache:|npm ci|pull_request\.head|schedule:/);
  assert.match(workflow, /run: node scripts\/ci-queue\.mjs/);
  assert.match(workflow, /workflows: \[Validate\]/);
});

test("fix-forward recovery requires the explicit repaired main and preserves original delivery", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); await f.queue.advance(); f.pass(); f.runs[0].conclusion = "failure";
  await f.queue.run({ eventName: "workflow_run", event: {} }); f.setMain(C);
  await assert.rejects(f.queue.command({ action: "recover", head: B }, "owner"), /exact current main/);
  await f.queue.command({ action: "recover", head: C }, "owner");
  assert.equal(f.state.active.deliveredSha, D); assert.equal(f.state.active.mergeSha, C); assert.equal(f.state.paused, null);
  f.pass(); await f.queue.advance();
  assert.equal(f.state.completed[0].mergeSha, D); assert.equal(f.state.completed[0].smokeSha, C);
});

test("enabled queue publications have no validation jobs and cannot occupy the delivery slot", async () => {
  const f = fixture(); await f.load();
  f.runs.push({ id: 900, event: "pull_request", status: "in_progress" });
  await f.queue.advance();
  assert.equal(f.state.active.phase, "validating");
  f.pass(); f.runs.push({ id: 901, event: "pull_request", status: "in_progress" });
  await f.queue.advance();
  assert.equal(f.state.active.phase, "smoke");
});

test("manually linked closing issues block readiness even without body keywords", async () => {
  const f = fixture(); await f.load(); const api = f.github.api.bind(f.github);
  f.github.api = (method, url, body) => url === "/graphql"
    ? Promise.resolve({ data: { repository: { pullRequest: { closingIssuesReferences: { totalCount: 1 } } } } })
    : api(method, url, body);
  await assert.rejects(f.queue.command({ action: "ready", pr: 1, head: B }, "owner"), /sidebar links/);
});

test("command scans use a durable timestamp window rather than all historical comments", async () => {
  const f = fixture(); await f.load(); f.queue.state.cursorSince = 0;
  f.comments.push({ id: 1, body: "/queue inspect", user: { login: "owner" }, created_at: new Date(1000000).toISOString() });
  const requests = [], pages = f.github.pages.bind(f.github);
  f.github.pages = (url) => { requests.push(url); return pages(url); };
  await f.queue.commands();
  assert.match(requests[0], /since=1970-01-01T00%3A00%3A00\.000Z/);
  assert.equal(f.state.cursorSince, 999000);
});

test("coalesced completion events cannot hide a failed manual validation", async () => {
  const f = fixture(); await f.load(); f.queue.state.initializedAt = 0;
  f.runs.push({ id: 123, event: "workflow_dispatch", status: "completed", conclusion: "failure", created_at: "2026-10-29T00:00:00Z" });
  await f.queue.save();
  await f.queue.run({ eventName: "issue_comment", event: { issue: { number: 99 } } });
  assert.match(f.state.paused.reason, /Validate failed/);
  assert.equal(f.state.active, null);
  await f.queue.command({ action: "resume" }, "owner"); await f.queue.advance();
  assert.equal(f.state.active.pr, 1); assert.equal(f.state.failureCursor, 123);
});

test("closure changes cannot leave a merge-required success before the closure guard", async () => {
  const f = fixture(); await f.load(); await f.queue.advance(); f.pass(); f.pulls.get(1).body = "Fixes: #42";
  await assert.rejects(f.queue.advance(), /auto-closing PR keywords/);
  assert.equal(f.calls.some((c) => c.suffix.startsWith("/statuses/") && c.body.context === STATUS && c.body.state === "success"), false);
});

test("clean integration trusts the exact branch ref while the PR API still shows its old head", async () => {
  const f = fixture(); await f.load(); const api = f.github.api.bind(f.github);
  f.github.api = async (method, url, body) => {
    if (url.includes("/compare/")) return { status: "diverged" };
    if (url.endsWith("/merges")) return { sha: C, parents: [{ sha: B }, { sha: A }], commit: { message: body.commit_message } };
    if (url.endsWith("/git/ref/heads/feature-1")) return { object: { sha: C } };
    return api(method, url, body);
  };
  await f.queue.advance();
  assert.equal(f.state.active.candidate, C); assert.equal(f.state.active.phase, "validating");
  assert.equal(f.pulls.get(1).head.sha, B);
});

test("a failed manual rerun is a new attempt even when its older run ID was acknowledged", async () => {
  const f = fixture(); f.state.initializedAt = 100; f.state.failureCursor = 999; f.state.processedRuns = ["12:1"]; f.state.entries = [];
  const event = { workflow_run: { id: 12, run_attempt: 2, display_title: "Manual", created_at: "1970-01-01T00:00:00Z", run_started_at: "2026-10-29T00:00:00Z", conclusion: "failure" } };
  await f.queue.run({ eventName: "workflow_run", event });
  assert.ok(f.state.paused); assert.ok(f.state.processedRuns.includes("12:2"));
  await f.queue.command({ action: "resume" }, "owner"); await f.queue.run({ eventName: "workflow_run", event });
  assert.equal(f.state.paused, null);
});

test("a coalesced failed rerun beyond the first history page still pauses delivery", async () => {
  const f = fixture(); f.state.initializedAt = 100; f.state.failureCursor = 20000;
  const api = f.github.api.bind(f.github);
  f.github.api = async (method, url, body) => {
    if (url.includes("/runs?per_page=100&page=1")) return { workflow_runs: Array.from({ length: 100 }, (_, i) => ({ id: 10000 - i, run_attempt: 1, status: "completed", conclusion: "success", created_at: "1970-01-01T00:00:00Z" })) };
    if (url.includes("/runs?per_page=100&page=2")) return { workflow_runs: [{ id: 12, run_attempt: 2, status: "completed", conclusion: "failure", created_at: "1970-01-01T00:00:00Z", run_started_at: "2026-10-29T00:00:00Z" }] };
    return api(method, url, body);
  };
  await f.queue.run({ eventName: "workflow_run", event: {} });
  assert.match(f.state.paused.reason, /Validate failed/);
  assert.equal(f.state.active, null);
});

test("removing a waiting entry preserves the active transaction", async () => {
  const f = fixture(); await f.load(); await f.queue.advance();
  const transaction = f.state.active.id;
  await f.queue.command({ action: "remove", pr: 2 }, "owner");
  assert.deepEqual(f.state.entries.map((entry) => entry.pr), [1]);
  assert.equal(f.state.active.id, transaction);
  await assert.rejects(f.queue.command({ action: "remove", pr: 1 }, "owner"), /Active entry cannot be removed/);
  assert.equal(f.state.active.id, transaction);
});
