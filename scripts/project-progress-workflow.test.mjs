import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { clearTimeout, setTimeout as setTimer } from "node:timers";

import { issueRevision } from "./chat-review-current.mjs";
import { defaultInstallationIdPath } from "./codex-session-register-lib.mjs";
import { deriveWorkflow, loadWorkflowEvidence, resolveLocalSession } from "./project-progress-workflow.mjs";

const REPO = "mbelinkie/vera-script-to-timeline";
const ISSUE = `https://github.com/${REPO}/issues/42`;
const PR_URL = `https://github.com/${REPO}/pull/52`;
const NOW = "2026-11-02T17:00:00.000Z";
const MAIN = "b".repeat(40);
const HEAD = "a".repeat(40);
const WRONG = "d".repeat(40);
const INSTALLATION = "11111111-2222-4333-8444-555555555555";
const THREAD = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";

function item(overrides = {}) {
  return {
    url: ISSUE,
    number: 42,
    title: "A bounded work item",
    body: "Issue body",
    labels: [],
    status: "Ready",
    queueOrder: 1,
    acceptance: "External",
    dependencies: [],
    dependenciesVerified: true,
    snapshotAt: NOW,
    ...overrides,
  };
}

function queueState(overrides = {}) {
  return {
    version: 1,
    controlIssue: 361,
    initializedAt: Date.parse(NOW),
    cursorSince: Date.parse(NOW) - 60_000,
    failureCursor: 0,
    processedRuns: [],
    cursor: 0,
    entries: [],
    active: null,
    paused: null,
    completed: [],
    ...overrides,
  };
}

function queueContents(state) {
  const encoded = Buffer.from(JSON.stringify(state), "utf8");
  return {
    name: "queue.json",
    path: "queue.json",
    sha: "c".repeat(40),
    size: encoded.length,
    type: "file",
    encoding: "base64",
    content: encoded.toString("base64"),
    html_url: `https://github.com/${REPO}/blob/vera-ci-queue-state/queue.json`,
  };
}

function reviewIssue(row, labels = row.labels) {
  return {
    number: row.number,
    repository_url: `https://api.github.com/repos/${REPO}`,
    html_url: row.url,
    title: row.title,
    body: row.body,
    state: "open",
    labels: labels.map((name) => ({ name })),
    comments: row.comments ?? 1,
  };
}

function reviewComment(row, revision = issueRevision(row.title, row.body)) {
  const id = 874;
  return {
    id,
    user: { login: "mbelinkie" },
    body: `<!-- VERA_CHAT_REVIEW_V1 ${JSON.stringify({
      producer: "mbelinkie",
      promptVersion: "1",
      reviewedAt: NOW,
      revision,
    })} -->`,
    created_at: NOW,
    updated_at: NOW,
    performed_via_github_app: null,
    html_url: `${ISSUE}#issuecomment-${id}`,
  };
}

function claimComment(id, claim, overrides = {}) {
  return {
    id,
    body: `<!-- vera-claim ${JSON.stringify(claim)} -->`,
    user: { login: "mbelinkie" },
    performed_via_github_app: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

function pull(number, overrides = {}) {
  return {
    number,
    html_url: `https://github.com/${REPO}/pull/${number}`,
    state: "open",
    draft: false,
    merged: false,
    merge_commit_sha: null,
    base: { ref: "main", sha: MAIN, repo: { full_name: REPO } },
    head: { sha: HEAD, ref: "feature", repo: { full_name: REPO } },
    ...overrides,
  };
}

function timelineFor(number = 52) {
  return [{
    event: "cross-referenced",
    source: {
      type: "issue",
      issue: {
        number,
        html_url: `https://github.com/${REPO}/pull/${number}`,
        pull_request: { url: `https://api.github.com/repos/${REPO}/pulls/${number}` },
      },
    },
  }];
}

function baseApi({ state = queueState(), pullOverrides = {}, timeline = timelineFor(), extra = {} } = {}) {
  const calls = [];
  const api = async (endpoint) => {
    calls.push(endpoint);
    if (endpoint === "rate_limit") return { resources: { core: { remaining: 5000 } } };
    if (endpoint === `repos/${REPO}/contents/queue.json?ref=vera-ci-queue-state`) return queueContents(state);
    if (endpoint === `repos/${REPO}/git/ref/heads/main`) return { object: { sha: MAIN } };
    if (endpoint === `repos/${REPO}/issues/42/timeline?per_page=100`) return timeline;
    if (endpoint === `repos/${REPO}/issues/42`) return reviewIssue(extra.issue ?? item());
    if (endpoint === `repos/${REPO}/issues/42/comments?per_page=100&page=1`) return extra.claimComments ?? [reviewComment(extra.issue ?? item())];
    const pullMatch = new RegExp(`^repos/${REPO}/pulls/([1-9][0-9]*)$`).exec(endpoint);
    if (pullMatch) return pull(Number(pullMatch[1]), pullOverrides);
    const runList = endpoint.match(/^repos\/.+\/actions\/workflows\/validate\.yml\/runs\?/);
    if (runList) return { workflow_runs: extra.workflowRuns ?? [] };
    if (endpoint === `repos/${REPO}/actions/workflows/validate.yml`) return { id: 9, path: ".github/workflows/validate.yml", state: "active" };
    if (endpoint === `repos/${REPO}/actions/runs/77/attempts/1/jobs?per_page=100&page=1`) return { jobs: [] };
    throw new Error(`Unexpected read endpoint: ${endpoint}`);
  };
  const readGh = (args) => {
    assert.equal(args[0], "api");
    assert.equal(args.some((arg) => ["POST", "PATCH", "PUT", "DELETE"].includes(arg)), false);
    const pathIndex = args.findIndex((arg) => typeof arg === "string" && arg.startsWith("repos/"));
    const endpoint = args[pathIndex];
    if (args.includes("--paginate")) {
      assert.match(endpoint, /\/issues\/42\/comments\?per_page=100$/);
      return JSON.stringify([[extra.comment ?? reviewComment(extra.issue ?? item())]]);
    }
    if (endpoint === `repos/${REPO}/issues/42`) return JSON.stringify(reviewIssue(extra.issue ?? item()));
    throw new Error("Unexpected canonical review read");
  };
  return { calls, readApi: api, readGh };
}

function evidenceFor(row, overrides = {}) {
  const source = { snapshotAt: NOW, lastError: null };
  return {
    snapshotAt: NOW,
    lastError: null,
    chat: { state: "approved", url: `${row.url}#issuecomment-874`, reason: "Current review verified." },
    codex: { state: "unknown", reason: "No verified claim." },
    deepseek: { state: "off", reason: "Not connected." },
    review: { state: "unknown", reason: "No canonical exact-head review receipt." },
    ci: { state: "waiting", reason: "Waiting for the slot." },
    session: { status: "missing", reason: "No mapping.", hasBrowser: false },
    acceptance: { state: "unknown", reason: "Not recorded." },
    sources: { project: source, workflow: source, ci: source, session: source },
    ...overrides,
  };
}

test("uses the canonical current Chat verifier, keeps DeepSeek off, and emits only safe public links", async () => {
  const row = item({ labels: ["chat-reviewed"] });
  const fake = baseApi({
    state: queueState({ entries: [{ pr: 52, submitted: HEAD, head: HEAD, ready: true, owner: "mbelinkie" }] }),
    extra: { issue: row },
  });
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });

  assert.equal(evidence.issues[ISSUE].chat.state, "approved");
  assert.equal(evidence.issues[ISSUE].deepseek.state, "off");
  assert.deepEqual(evidence.issues[ISSUE].pr, { url: PR_URL, number: 52, head: HEAD, base: MAIN });
  assert.equal(evidence.issues[ISSUE].ci.state, "waiting");
  assert.equal(evidence.issues[ISSUE].review.state, "unknown");
  assert.ok(fake.calls.every((endpoint) => !/dispatches|statuses|\/merge|POST|PATCH|PUT|DELETE/i.test(endpoint)));
  assert.doesNotMatch(JSON.stringify(evidence), /vera-ci-queue-state\/queue\.json|codex:\/\/threads/);

  const derived = deriveWorkflow(row, evidence.issues[ISSUE], new Date(NOW));
  assert.equal(derived.group, "working");
  assert.equal(derived.actor, "CI");
  assert.equal(derived.deepseek.state, "off");
  assert.ok(derived.chips.every((chip) => ["ok", "active", "wait", "attention", "blocked", "unknown", "na"].includes(chip.tone)));
  assert.deepEqual(derived.links.map((link) => link.url), [ISSUE, PR_URL, `${ISSUE}#issuecomment-874`]);
});

test("stale canonical Chat digest stays pending and has no approval link", async () => {
  const row = item({ labels: ["chat-reviewed"] });
  const fake = baseApi({ extra: { issue: row, comment: reviewComment(row, "0".repeat(64)) } });
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });

  assert.equal(evidence.issues[ISSUE].chat.state, "pending");
  assert.equal(evidence.issues[ISSUE].chat.url, undefined);
  assert.equal(deriveWorkflow(row, evidence.issues[ISSUE], new Date(NOW)).group, "you");
});

test("a current CI run with the wrong workflow head remains unknown", async () => {
  const row = item({ labels: ["chat-reviewed"] });
  const transaction = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
  const title = `vera-queue:${transaction}:pr:${HEAD}:${MAIN}`;
  const state = queueState({
    entries: [{ pr: 52, submitted: HEAD, head: HEAD, ready: true, owner: "mbelinkie" }],
    active: {
      id: transaction, pr: 52, phase: "validating", base: MAIN, candidate: HEAD,
      expected: { title, workflowId: 9, workflowHead: MAIN, startedAt: Date.parse(NOW) - 30_000, timeoutMs: 6_000_000 },
    },
  });
  const run = {
    id: 77, display_title: title, workflow_id: 9, head_sha: WRONG, event: "workflow_dispatch",
    path: ".github/workflows/validate.yml", run_attempt: 1, status: "in_progress", conclusion: null,
    html_url: `https://github.com/${REPO}/actions/runs/77`, actor: { login: "github-actions[bot]" },
  };
  const fake = baseApi({ state, extra: { issue: row, workflowRuns: [run] } });
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });

  assert.equal(evidence.issues[ISSUE].ci.state, "unknown");
  assert.equal(evidence.issues[ISSUE].ci.url, undefined);
  assert.equal(evidence.ciQueue.active.runUrl, null);
  const derived = deriveWorkflow(row, evidence.issues[ISSUE], new Date(NOW));
  assert.equal(derived.group, "stuck");
  assert.equal(derived.actor, "Unknown");
  assert.notEqual(derived.actor, "CI");
});

test("CI waiting evidence fails closed when the current PR head differs from the queued SHA", async () => {
  const state = queueState({ entries: [{ pr: 52, submitted: HEAD, head: HEAD, ready: true, owner: "mbelinkie" }] });
  const fake = baseApi({ state, pullOverrides: { head: { sha: WRONG, ref: "feature", repo: { full_name: REPO } } } });
  const evidence = await loadWorkflowEvidence(process.cwd(), [item()], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });

  assert.equal(evidence.issues[ISSUE].ci.state, "unknown");
  assert.equal(evidence.ciQueue.ready, 0);
  assert.equal(evidence.ciQueue.lastError, "Some queue PR heads or bases no longer match saved queue evidence.");
});

test("stale, future, and invalid per-source timestamps never preserve Approved or a next action", () => {
  const row = item();
  for (const snapshotAt of ["2026-11-02T16:43:59.000Z", "2026-11-02T17:00:01.000Z", "not-a-date"]) {
    const record = evidenceFor(row, { sources: {
      project: { snapshotAt: NOW, lastError: null },
      workflow: { snapshotAt, lastError: null },
      ci: { snapshotAt: NOW, lastError: null },
    } });
    const derived = deriveWorkflow(row, record, new Date(NOW));
    assert.equal(derived.chat.state, "unknown");
    assert.equal(derived.group, "stuck");
    assert.equal(derived.actor, "Unknown");
    assert.ok(derived.disabled.length > 0);
    assert.equal(derived.links.some((link) => link.label === "Verified Chat review"), false);
  }
});

test("stale Project labels cannot make a DeepSeek candidate potential or preserve an injected pass", () => {
  const candidate = item({ labels: ["deepseek-eligible"] });
  const stale = deriveWorkflow(candidate, evidenceFor(candidate, {
    deepseek: { state: "verified-pass", reason: "untrusted stale pass" },
    sources: {
      project: { snapshotAt: "2026-11-02T16:43:59.000Z", lastError: null },
      workflow: { snapshotAt: NOW, lastError: null },
      ci: { snapshotAt: NOW, lastError: null },
    },
  }), new Date(NOW));
  assert.equal(stale.deepseek.state, "off");
  assert.doesNotMatch(JSON.stringify(stale), /verified-pass|stale pass/);
});

test("incomplete PR history cannot turn an approved Ready issue into a Codex launch", () => {
  const row = item();
  const derived = deriveWorkflow(row, evidenceFor(row, {
    chat: { state: "approved", url: `${ISSUE}#issuecomment-874`, reason: "Current." },
    sources: {
      project: { snapshotAt: NOW, lastError: null },
      workflow: { snapshotAt: NOW, lastError: null },
      pr: { snapshotAt: NOW, lastError: "Linked PR history could not be refreshed." },
      ci: { snapshotAt: NOW, lastError: null },
    },
  }), new Date(NOW));
  assert.equal(derived.group, "stuck");
  assert.equal(derived.actor, "Unknown");
  assert.doesNotMatch(JSON.stringify(derived), /manual start route/);
});

test("conflicting Project evidence and unverified dependencies block a Ready row", () => {
  const conflicted = deriveWorkflow(item({ evidenceConflict: true }), evidenceFor(item()), new Date(NOW));
  assert.equal(conflicted.group, "stuck");
  const unresolved = deriveWorkflow(item({ dependenciesVerified: false }), evidenceFor(item()), new Date(NOW));
  assert.equal(unresolved.group, "stuck");
  const done = deriveWorkflow(item({ status: "Done", dependenciesVerified: false }), evidenceFor(item()), new Date(NOW));
  assert.equal(done.group, "done");
});

test("an active roadmap claim is displayed as claimed, never as agent-running, and its task stays private", async () => {
  const row = item({ status: "In progress" });
  const privateTask = "private task path /secret/agent-claim";
  const fake = baseApi({ extra: { issue: row, claimComments: [claimComment(875, {
    state: "active", model: "gpt-6-luna", effort: "max", task: privateTask,
    branch: "codex/private-branch", startedAt: NOW,
  })] } });
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });
  const record = evidence.issues[ISSUE];
  const derived = deriveWorkflow(row, record, new Date(NOW));

  assert.equal(record.codex.state, "claimed");
  assert.match(record.codex.reason, /does not verify that an agent is running/);
  assert.equal(derived.group, "working");
  assert.equal(derived.actor, "Codex");
  assert.doesNotMatch(JSON.stringify(record), /private task path|private-branch/);
  assert.doesNotMatch(JSON.stringify(derived), /private task path|private-branch/);
});

test("claim markers from outsiders, GitHub Apps, and edited or invalid-time comments are ignored", async () => {
  const row = item({ status: "In progress" });
  const marker = { state: "active", model: "gpt-6-luna", effort: "max", task: "private", branch: "codex/private", startedAt: NOW };
  const untrusted = [
    { name: "outsider", overrides: { user: { login: "attacker" } } },
    { name: "GitHub App", overrides: { performed_via_github_app: { slug: "automation" } } },
    { name: "edited", overrides: { updated_at: "2026-11-02T17:01:00.000Z" } },
    { name: "invalid timestamp", overrides: { created_at: "invalid", updated_at: "invalid" } },
  ];
  for (const { name, overrides } of untrusted) {
    const fake = baseApi({ extra: { issue: row, claimComments: [claimComment(875, marker, overrides)] } });
    const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
      now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
    });
    assert.equal(evidence.issues[ISSUE].codex.state, "unknown", name);
  }
});

test("a latest malformed trusted claim marker fails closed", async () => {
  const row = item({ status: "In progress" });
  const marker = { state: "active", model: "gpt-6-luna", effort: "max", task: "private", branch: "codex/private", startedAt: NOW };
  const fake = baseApi({ extra: { issue: { ...row, comments: 2 }, claimComments: [
    claimComment(874, marker),
    claimComment(875, marker, { body: "<!-- vera-claim {not-json} -->" }),
  ] } });
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });
  assert.equal(evidence.issues[ISSUE].codex.state, "unknown");
  assert.match(evidence.issues[ISSUE].codex.reason, /marker is invalid/);
});

test("DeepSeek candidate and exclusion labels never imply an authorized or passing job", () => {
  const candidate = item({ labels: ["deepseek-eligible"] });
  const untrusted = evidenceFor(candidate, {
    deepseek: { state: "verified-pass", reason: "untrusted stale pass" },
  });
  const potential = deriveWorkflow(candidate, untrusted, new Date(NOW));
  assert.equal(potential.deepseek.state, "potential");
  assert.match(potential.deepseek.reason, /global route is off/);
  assert.doesNotMatch(JSON.stringify(potential), /verified-pass|stale pass/);

  const excluded = deriveWorkflow(item({ labels: ["deepseek-eligible", "deepseek-excluded"] }), untrusted, new Date(NOW));
  assert.equal(excluded.deepseek.state, "excluded");
  for (const labels of [["deepseek-eligible", "owner:codex"], ["deepseek-eligible", "type:security"], ["deepseek-eligible", "type:design"]]) {
    assert.equal(deriveWorkflow(item({ labels }), untrusted, new Date(NOW)).deepseek.state, "excluded");
  }
});

test("Chat prompts are limited to explicit research gaps and never record approval", () => {
  const implementation = item();
  const needsApproval = deriveWorkflow(implementation, evidenceFor(implementation, {
    chat: { state: "pending", reason: "Current Producer approval is required." },
  }), new Date(NOW));
  assert.equal(needsApproval.actor, "Producer");
  assert.equal(needsApproval.filter, "approval");
  const approvalPrompt = needsApproval.links.find((link) => link.label === "Open Chat review prompt");
  assert.ok(approvalPrompt);
  assert.equal(decodeURIComponent(approvalPrompt.url).includes("wait for the Producer's decision"), true);
  assert.equal(decodeURIComponent(approvalPrompt.url).includes("Do not record or imply Producer approval"), true);

  const research = item({
    labels: ["type:research"],
    body: "## Research gap\n\nCompare the documented alternatives and identify their remaining evidence gaps.",
  });
  const prompt = deriveWorkflow(research, evidenceFor(research, {
    chat: { state: "pending", reason: "Current Producer approval is required." },
  }), new Date(NOW));
  assert.equal(prompt.filter, "chat");
  assert.equal(prompt.actor, "Chat");
  const link = prompt.links.find((candidate) => candidate.label === "Open Chat review prompt");
  assert.match(link.url, /^https:\/\/chatgpt\.com\/\?q=/);
  assert.match(decodeURIComponent(link.url), /exact current issue and the sources it links to/);
  assert.match(decodeURIComponent(link.url), /wait for the Producer's decision/);
  assert.match(decodeURIComponent(link.url), /Do not record or imply Producer approval/);
});

test("verified CI queue work owns Ready, In progress and In review rows before acceptance", () => {
  const row = item();
  for (const state of ["waiting", "validating", "smoke-running"]) {
    const evidence = evidenceFor(row, {
      pr: { url: PR_URL, number: 52, head: HEAD, base: MAIN },
      ci: { state, reason: "Verified queue state.", url: `https://github.com/${REPO}/actions/runs/77` },
    });
    const ready = deriveWorkflow(row, evidence, new Date(NOW));
    assert.equal(ready.group, "working", state);
    assert.equal(ready.actor, "CI", state);
    assert.match(ready.action, /queue|validating|smoke/i);
    const inProgress = deriveWorkflow(item({ status: "In progress" }), evidence, new Date(NOW));
    assert.equal(inProgress.actor, "CI", state);
    assert.equal(inProgress.group, "working", state);

    const inReview = deriveWorkflow(item({ status: "In review" }), evidence, new Date(NOW));
    assert.equal(inReview.group, "working", state);
    assert.equal(inReview.actor, "CI", state);
    assert.equal(inReview.acceptance.state, "unknown");
  }

  const paused = deriveWorkflow(row, evidenceFor(row, {
    pr: { url: PR_URL, number: 52, head: HEAD, base: MAIN },
    ci: { state: "failed-paused", reason: "Paused." },
  }), new Date(NOW));
  assert.equal(paused.group, "stuck");
  assert.equal(paused.actor, "You");

  const readyToStart = deriveWorkflow(row, evidenceFor(row), new Date(NOW));
  assert.equal(readyToStart.group, "launch");
  assert.equal(readyToStart.actor, "Codex");
});

test("CI control issue is not routed as ordinary claimable work", () => {
  const control = item({
    number: 361,
    url: `https://github.com/${REPO}/issues/361`,
    labels: [],
    status: "In progress",
    dependenciesVerified: false,
    dependencies: undefined,
  });
  const derived = deriveWorkflow(control, evidenceFor(control), new Date(NOW));
  assert.equal(derived.group, "working");
  assert.equal(derived.actor, "CI");
  assert.match(derived.action, /controls the CI queue/);
  assert.equal(derived.filter, "working");
});

test("source failures expose only safe errors and do not perform mutations", async () => {
  const row = item({ labels: ["chat-reviewed"] });
  const fake = baseApi();
  fake.readApi = async () => { throw new Error("failed /private/home/secret-thread-uuid"); };
  const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
    now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
  });
  const output = JSON.stringify(evidence);
  assert.equal(evidence.issues[ISSUE].chat.state, "unknown");
  assert.doesNotMatch(output, /secret-thread-uuid|\/private\/home/);
  assert.ok(fake.calls.every((endpoint) => !/dispatches|statuses|\/merge/i.test(endpoint)));
});

test("production canonical Chat verification runs off the main event loop", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "vera-chat-worker-"));
  const ghExecutable = path.join(temporary, "gh.mjs");
  const row = item({ labels: ["chat-reviewed"] });
  const comment = reviewComment(row);
  const issue = reviewIssue(row);
  await writeFile(ghExecutable, `#!/usr/bin/env node
const args = process.argv.slice(2);
await new Promise((resolve) => setTimeout(resolve, 100));
if (args[0] !== "api") process.exit(2);
console.log(JSON.stringify(args.includes("--paginate") ? [[${JSON.stringify(comment)}]] : ${JSON.stringify(issue)}));
`, { mode: 0o700 });
  try {
    const fake = baseApi({ extra: { issue: row } });
    let timerRan = false;
    const timer = setTimer(() => { timerRan = true; }, 0);
    const evidence = await loadWorkflowEvidence(process.cwd(), [row], {
      now: new Date(NOW), repository: REPO, readApi: fake.readApi, ghExecutable,
    });
    clearTimeout(timer);
    assert.equal(timerRan, true);
    assert.equal(evidence.issues[ISSUE].chat.state, "approved");
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("derived links reject untrusted PR, Chat comment, and Actions destinations", () => {
  const row = item();
  const record = evidenceFor(row, {
    pr: { url: "https://github.com.attacker.example/owner/repo/pull/52", number: 52, head: HEAD, base: MAIN },
    chat: { state: "approved", reason: "Injected record", url: "https://attacker.example/review" },
    ci: { state: "delivered", reason: "Injected record", url: "https://attacker.example/actions/runs/77" },
  });
  const derived = deriveWorkflow(row, record, new Date(NOW));
  assert.deepEqual(derived.links, [{ label: "Issue", url: ISSUE }]);
});

test("local session output omits raw links in public evidence and resolves them only on demand", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "vera-workflow-"));
  const privateDirectory = path.join(temporary, "codex-session-links");
  const mappingPath = path.join(privateDirectory, "codex-thread-map.v1.json");
  const installationIdPath = defaultInstallationIdPath(mappingPath);
  await mkdir(privateDirectory, { mode: 0o700 });
  const mapping = {
    version: 1,
    installationId: INSTALLATION,
    mappings: [{
      issueUrl: ISSUE,
      role: "primary",
      surface: "codex-local",
      deepLink: `codex://threads/${THREAD}`,
      threadId: THREAD,
      provenance: { method: "desktop-copy-deeplink", confirmedBy: "producer", capturedAt: NOW },
      verification: { state: "producer-confirmed-existing", checkedAt: NOW },
    }],
  };
  await writeFile(mappingPath, JSON.stringify(mapping), { mode: 0o600 });
  await writeFile(installationIdPath, INSTALLATION, { mode: 0o600 });
  try {
    const fake = baseApi();
    const evidence = await loadWorkflowEvidence(process.cwd(), [item()], {
      now: new Date(NOW), repository: REPO, readApi: fake.readApi, readGh: fake.readGh,
      local: true, mappingPath, installationIdPath,
    });
    const publicRow = evidence.issues[ISSUE];
    assert.equal(publicRow.session.status, "verified-local");
    assert.equal(publicRow.session.hasBrowser, false);
    assert.doesNotMatch(JSON.stringify(publicRow), new RegExp(THREAD));
    assert.doesNotMatch(JSON.stringify(publicRow), /codex:\/\/threads/);

    const resolved = await resolveLocalSession(ISSUE, { mappingPath, installationIdPath });
    assert.equal(resolved.status, "verified-local");
    assert.equal(resolved.appUrl, `codex://threads/${THREAD}`);
    assert.equal(resolved.browserUrl, undefined);
    assert.equal(resolved.threadId, undefined);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});
