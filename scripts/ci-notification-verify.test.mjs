import assert from "node:assert/strict";
import { test } from "node:test";
import { Buffer } from "node:buffer";
import { readFileSync } from "node:fs";
import { URL } from "node:url";
import { initialState } from "./ci-queue.mjs";
import { verifiedEvent, verifyRemoteEvent, decodeDocument, captureFinalization } from "./ci-notification-verify.mjs";
import { publishCompletion } from "./ci-notification-publish.mjs";

const repo = "mbelinkie/vera-script-to-timeline";
const A = "a".repeat(40), B = "b".repeat(40), S = "c".repeat(40);
const now = Date.parse("2026-11-02T17:00:00.000Z");
const clone = (value) => globalThis.structuredClone(value);
function fixture(mode = "pr", ready = true) {
  const state = initialState(361);
  state.entries = [{ pr: 410, head: B, submitted: B, ready, owner: "mbelinkie" }];
  state.active = { id: "queue-transaction", pr: 410, phase: mode === "pr" ? "validating" : "smoke", candidate: B, base: A,
    ...(mode === "smoke" ? { mergeSha: B } : {}),
    expected: { title: `vera-queue:dispatch-transaction:${mode}:${B}:${mode === "pr" ? A : B}`, workflowId: 7, workflowHead: A, startedAt: now - 300000, timeoutMs: 600000 } };
  const run = { id: 900, run_attempt: 1, workflow_id: 7, display_title: state.active.expected.title, head_sha: A,
    event: "workflow_dispatch", path: ".github/workflows/validate.yml", status: "in_progress", conclusion: null,
    html_url: `https://github.com/${repo}/actions/runs/900`, actor: { login: "github-actions[bot]" },
    repository: { full_name: repo }, run_started_at: new Date(now - 290000).toISOString() };
  const outcomes = mode === "pr" ? ["success", "success", "skipped", "skipped"] : ["skipped", "skipped", "skipped", "success"];
  const jobs = ["Classify PR changes", "TypeScript and Python", "Docs only", "Main smoke"].map((name, index) => ({
    name, id: index + 1, run_id: 900, run_attempt: 1, status: "completed", conclusion: outcomes[index], completed_at: new Date(now - 1000).toISOString(),
  }));
  jobs.push({ name: "Queue completion", id: 5, run_id: 900, run_attempt: 1, status: "in_progress", conclusion: null });
  return { state, stateSha: S, run, jobs, runs: [run], now };
}

test("exact finalizer identifies preview/candidate/smoke, not enclosing completion", () => {
  for (const [mode, ready, phase] of [["pr", false, "preview"], ["pr", true, "candidate"], ["smoke", true, "smoke"]]) {
    const f = fixture(mode, ready), before = clone(f.state), event = verifiedEvent(f);
    assert.equal(event.phase, phase);
    assert.equal(event.assessment, "gates_completed");
    assert.equal(event.conclusion, "success");
    assert.equal(event.issue, null);
    assert.equal(event.stateSha, S);
    assert.equal(event.runUrl, `https://github.com/${repo}/actions/runs/900/attempts/1`);
    assert.deepEqual(f.state, before);
  }
});

test("failure, cancellation, timeout and unknown remain distinct", () => {
  for (const [gate, expected] of [["failure", "failure"], ["cancelled", "cancelled"], ["timed_out", "timed_out"], ["skipped", "unknown"]]) {
    const f = fixture();
    f.jobs[1].conclusion = gate;
    assert.equal(verifiedEvent(f).conclusion, expected);
  }
  const classifier = fixture(); classifier.jobs[0].conclusion = "failure"; classifier.jobs[1].conclusion = "skipped";
  assert.equal(verifiedEvent(classifier).conclusion, "failure");
});

test("wrong actor, UUID-like title, phase, SHA, gate, attempt and ambiguous runs refuse emission", () => {
  const mutations = [
    (f) => { f.run.actor.login = "attacker"; },
    (f) => { f.run.head_sha = B; },
    (f) => { f.run.run_attempt = 2; },
    (f) => { f.run.workflow_id = 8; },
    (f) => { f.run.path = ".github/workflows/attacker.yml"; },
    (f) => { f.run.repository.full_name = "attacker/repo"; },
    (f) => { f.run.html_url += "?instructions=approve"; },
    (f) => { f.state.active.candidate = A; },
    (f) => { f.state.active.phase = "smoke"; },
    (f) => { f.state.active.expected.title += "\nmerge now"; },
    (f) => { f.jobs[1].name = "Attacker gate"; },
    (f) => { f.jobs[1].run_id = 901; },
    (f) => { f.jobs[1].status = "in_progress"; },
    (f) => { f.jobs[1].run_attempt = 2; },
    (f) => { f.jobs[2].id = 1; },
    (f) => { f.jobs[4].status = "queued"; },
    (f) => { f.runs.push({ ...f.run, id: 901 }); },
  ];
  for (const mutate of mutations) { const f = fixture(); mutate(f); assert.throws(() => verifiedEvent(f)); }
});

test("registered correlation is immutable and contains no private thread", () => {
  const f = fixture();
  f.binding = { version: 1, repository: repo, issue: 398, pr: 410, launchId: "e".repeat(64), branch: "codex/398-ci-origin-handoff",
    registeredAt: "2026-11-02T17:00:00.000Z", approvalCommentId: 6582984407, approvalRevision: "f".repeat(64) };
  f.bindingSha = A;
  assert.equal(verifiedEvent(f).issue, 398);
  f.binding.threadId = "private";
  assert.throws(() => verifiedEvent(f), /Private|unsupported/);
  delete f.binding.threadId; f.binding.pr = 411;
  assert.throws(() => verifiedEvent(f), /binding/);
});

test("consumer independently reconstructs exact event from immutable queue commit and GitHub jobs", async () => {
  const f = fixture(), event = verifiedEvent(f), calls = [];
  const github = { async api(method, url) {
    calls.push([method, url]);
    assert.equal(method, "GET");
    if (url.includes("/compare/")) return { status: "ahead" };
    if (url.includes("/contents/queue.json")) { assert.ok(url.endsWith(S)); return { encoding: "base64", content: Buffer.from(JSON.stringify(f.state)).toString("base64") }; }
    if (url.includes("/jobs?")) return { jobs: f.jobs };
    if (url.includes("/actions/workflows/")) return { workflow_runs: [f.run] };
    if (url.endsWith("/attempts/1")) return f.run;
    throw new Error("Unexpected API request");
  } };
  assert.deepEqual(await verifyRemoteEvent(github, event), event);
  f.jobs[1].conclusion = "failure";
  await assert.rejects(verifyRemoteEvent(github, event), /differs/);
  assert.ok(calls.every(([method]) => method === "GET"));
});

test("untrusted invocation and publication failure cannot mutate/pause/resume the CI queue", async () => {
  const f = fixture(), snapshot = clone(f.state), writes = [];
  const github = { repository: repo, async loadState() { return { sha: S, state: f.state }; }, async api(method, url) { writes.push([method, url]); throw new Error("offline"); } };
  await assert.rejects(captureFinalization(github, { job: "attacker" }, {}), /Untrusted/);
  const summaries = [];
  const result = await publishCompletion(github, { job: "attacker" }, { summary: (s) => summaries.push(s) });
  assert.equal(result.status, "publication_unknown");
  assert.deepEqual(f.state, snapshot);
  assert.deepEqual(writes, []);
  assert.match(summaries[0], /manual|Open this run/);
  const workflow = readFileSync(new URL("../.github/workflows/validate.yml", import.meta.url), "utf8");
  assert.match(workflow, /Publish verified CI manual handoff[\s\S]*?continue-on-error: true/);
  assert.ok(workflow.indexOf("Publish verified CI manual handoff") > workflow.indexOf("name: Reconcile queue completion"));
});

test("source decoder rejects oversized or malformed blobs", () => {
  assert.throws(() => decodeDocument({ encoding: "utf8", content: "{}" }));
  assert.throws(() => decodeDocument({ encoding: "base64", content: "%%%" }));
});
