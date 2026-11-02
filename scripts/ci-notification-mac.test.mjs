import assert from "node:assert/strict";
import { test } from "node:test";
import { Buffer } from "node:buffer";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { initialState } from "./ci-queue.mjs";
import { captureOrigin, saveOrigin, bindOrigin, publicBinding, loadDeliveryAudit } from "./ci-notification-origin.mjs";
import { LocalGitHub, readManualEvent, registerPublicOrigin } from "./ci-notification-mac.mjs";
import { verifiedEvent } from "./ci-notification-verify.mjs";

const repo = "mbelinkie/vera-script-to-timeline", A = "a".repeat(40), B = "b".repeat(40), S = "c".repeat(40), D = "d".repeat(40);
const threadId = "11111111-1111-4111-8111-111111111111";
const blob = (data, sha = A) => ({ encoding: "base64", sha, content: Buffer.from(JSON.stringify(data)).toString("base64") });

test("outbound Mac client uses existing sign-in, bounded fixed argv and GET-only report access", async () => {
  const calls = [];
  const client = new LocalGitHub({ runner(executable, args, options) {
    calls.push({ executable, args, options });
    return { status: 0, stdout: "{}" };
  } });
  await client.api("GET", `/repos/${repo}/pulls/408`);
  assert.equal(calls[0].executable, "gh");
  assert.equal(calls[0].options.timeout, 30000);
  assert.deepEqual(calls[0].args.slice(0, 3), ["api", "--method", "GET"]);
  await assert.rejects(client.api("PUT", `/repos/${repo}/pulls/408/merge`, {}));
  await assert.rejects(client.api("GET", "/repos/attacker/repo/issues/1"));
  assert.equal(calls.length, 1);
});

test("full manual read revalidates source, binds exact private origin and persists without a model turn", async () => {
  const parent = mkdtempSync(path.join(os.tmpdir(), "vera398-mac-")), directory = path.join(parent, "private");
  try {
    const now = Date.now() - 10000;
    let origin = captureOrigin({ repository: repo, issue: 398, branch: "codex/398-ci-origin-handoff", approvalCommentId: 10,
      approvalRevision: "f".repeat(64), authorizedScope: { manualReviewOnly: true }, env: { CODEX_THREAD_ID: threadId }, now });
    await saveOrigin(origin, directory); origin = bindOrigin(origin, 408, directory);
    const binding = publicBinding(origin), state = initialState(361);
    state.entries = [{ pr: 408, submitted: B, head: B, ready: true, owner: "mbelinkie" }];
    state.active = { id: "queue-one", pr: 408, phase: "validating", candidate: B, base: A,
      expected: { title: `vera-queue:dispatch-one:pr:${B}:${A}`, workflowId: 7, workflowHead: A, startedAt: now - 2000, timeoutMs: 100000 } };
    const run = { id: 900, run_attempt: 1, display_title: state.active.expected.title, workflow_id: 7, head_sha: A,
      event: "workflow_dispatch", path: ".github/workflows/validate.yml", status: "completed", conclusion: "success",
      html_url: `https://github.com/${repo}/actions/runs/900`, actor: { login: "github-actions[bot]" }, repository: { full_name: repo }, run_started_at: new Date(now - 1000).toISOString() };
    const jobs = ["Classify PR changes", "TypeScript and Python", "Docs only", "Main smoke", "Queue completion"].map((name, i) => ({
      id: i + 1, name, run_id: 900, run_attempt: 1, status: "completed", conclusion: i === 2 || i === 3 ? "skipped" : "success", completed_at: new Date(now).toISOString(),
    }));
    const event = verifiedEvent({ state, stateSha: S, run, jobs, runs: [run], binding, bindingSha: D, now });
    const calls = [];
    const github = { repository: repo, async api(method, url) {
      calls.push([method, url]); assert.equal(method, "GET");
      if (url.includes("/contents/events/")) return blob(event);
      if (url.includes("/commits?path=events/")) return [{ sha: A, author: { login: "github-actions[bot]" } }];
      if (url.includes("/compare/")) return { status: "ahead" };
      if (url.includes("/contents/queue.json")) return blob(state);
      if (url.includes("/contents/registrations/")) return blob(binding, D);
      if (url.includes("/git/blobs/")) return blob(binding, D);
      if (url.includes("/jobs?")) return { jobs };
      if (url.includes("/actions/workflows/")) return { workflow_runs: [run] };
      if (url.endsWith("/attempts/1")) return run;
      if (url.endsWith("/pulls/408")) return { head: { ref: origin.branch } };
      throw new Error("Unexpected read");
    } };
    const first = await readManualEvent(event.eventId, { github, directory });
    assert.equal(first.result.status, "manual_disabled");
    assert.equal(first.result.outcome, "persisted");
    assert.equal(first.result.navigation, `codex://threads/${threadId}`);
    const audit = loadDeliveryAudit(event.eventId, directory);
    assert.equal(audit.entries[0].states.queued, null);
    assert.equal(audit.entries[0].states.ack_observed, null);
    assert.equal(audit.entries[0].states.accepted, null);
    assert.ok(!first.report.includes(threadId));
    const replay = await readManualEvent(event.eventId, { github, directory });
    assert.equal(replay.result.outcome, "already_persisted");
    assert.ok(calls.every(([method]) => method === "GET"));
    jobs[1].conclusion = "failure";
    const refused = await readManualEvent(event.eventId, { github, directory });
    assert.equal(refused.result.outcome, "verification_failed");
    assert.match(refused.report, /not been independently verified/);
    assert.doesNotMatch(refused.report, /conclusion: success/);
    await assert.rejects(registerPublicOrigin(origin.launchId, { github, directory, env: { CODEX_THREAD_ID: "wrong" } }), /original runtime/);
  } finally { rmSync(parent, { recursive: true, force: true }); }
});
