import { Buffer } from "node:buffer";
import { assessRun } from "./ci-queue-policy.ts";
import { validateState } from "./ci-queue.mjs";
import { canonicalEvent, validateEvent, REPOSITORY } from "./ci-notification-outbox.mjs";

const SHA = /^[0-9a-f]{40}$/;
const TITLE = /^vera-queue:([A-Za-z0-9._-]{1,64}):(pr|smoke):([0-9a-f]{40}):([0-9a-f]{40})$/;
const GATES = ["Classify PR changes", "TypeScript and Python", "Docs only", "Main smoke"];
const OUTCOMES = new Set(["success", "failure", "cancelled", "timed_out", "skipped", "neutral", "action_required", "stale"]);
const positive = (n) => Number.isSafeInteger(n) && n > 0;
const root = `/repos/${REPOSITORY}`;

export function decodeDocument(blob) {
  if (blob?.encoding !== "base64" || typeof blob.content !== "string" || blob.content.length > 2_000_000) throw new Error("Invalid notification source blob");
  const encoded = blob.content.replace(/\s/g, "");
  const bytes = Buffer.from(encoded, "base64");
  if (bytes.toString("base64") !== encoded) throw new Error("Invalid notification source encoding");
  return JSON.parse(bytes.toString("utf8"));
}

export function validateBinding(binding, { pr, branch } = {}) {
  if (binding?.version !== 1 || binding.repository !== REPOSITORY || !positive(binding.issue) || !positive(binding.pr) ||
      typeof binding.launchId !== "string" || !/^[0-9a-f]{64}$/.test(binding.launchId) || typeof binding.branch !== "string" || !/^codex\/[A-Za-z0-9._/-]+$/.test(binding.branch) ||
      !positive(binding.approvalCommentId) || typeof binding.approvalRevision !== "string" || !/^[0-9a-f]{64}$/.test(binding.approvalRevision) ||
      !Number.isFinite(Date.parse(binding.registeredAt)) || (pr !== undefined && binding.pr !== pr) || (branch !== undefined && binding.branch !== branch)) {
    throw new Error("Invalid registered CI origin binding");
  }
  const keys = ["version", "repository", "issue", "pr", "launchId", "branch", "registeredAt", "approvalCommentId", "approvalRevision"];
  if (Object.keys(binding).some((key) => !keys.includes(key))) throw new Error("Private or unsupported fields in public origin binding");
  return binding;
}

/** Only the trusted finalizer's independently fetched jobs supply a verdict. */
export function verifiedEvent({ state, stateSha, run, jobs, runs, binding = null, bindingSha = null, now = Date.now() }) {
  validateState(state);
  const active = state.active;
  const entry = state.entries.find((item) => item.pr === active?.pr);
  const match = TITLE.exec(active?.expected?.title ?? "");
  if (!SHA.test(stateSha ?? "") || !entry || !match || !["validating", "smoke"].includes(active.phase) ||
      match[2] !== (active.phase === "smoke" ? "smoke" : "pr") || match[3] !== active.candidate ||
      match[4] !== (active.phase === "smoke" ? active.mergeSha : active.base)) throw new Error("Invalid notification transaction snapshot");
  if (!run || !positive(run.id) || !positive(run.run_attempt) || !["in_progress", "completed"].includes(run.status) ||
      (run.status === "in_progress" && run.conclusion !== null)) throw new Error("Invalid finalizer run state");
  const assessment = assessRun(active.expected, [{ ...run, status: "completed", conclusion: "success" }], Math.min(now, active.expected.startedAt + active.expected.timeoutMs));
  if (assessment.kind !== "passed" || run.html_url !== `https://github.com/${REPOSITORY}/actions/runs/${run.id}` ||
      run.repository?.full_name !== REPOSITORY) throw new Error("Notification run identity mismatch");
  const matches = runs.filter((item) => item.display_title === active.expected.title);
  if (matches.length !== 1 || matches[0].id !== run.id || matches[0].run_attempt !== run.run_attempt) throw new Error("Ambiguous notification run identity");
  const byName = new Map();
  const ids = new Set();
  for (const job of jobs) {
    if (!positive(job.id) || ids.has(job.id) || byName.has(job.name) || job.run_id !== run.id ||
        (job.run_attempt !== undefined && job.run_attempt !== run.run_attempt)) throw new Error("Invalid notification job identity");
    ids.add(job.id);
    byName.set(job.name, job);
  }
  const callback = byName.get("Queue completion");
  byName.delete("CI notification");
  if (byName.size !== 5 || !callback || callback.status !== "completed" || callback.conclusion !== "success") throw new Error("Missing successful trusted notification finalizer");
  for (const name of GATES) {
    const gate = byName.get(name);
    if (!gate || gate.status !== "completed" || !OUTCOMES.has(gate.conclusion)) throw new Error("Incomplete notification gate assessment");
  }
  const mode = match[2];
  const conclusions = GATES.map((name) => byName.get(name).conclusion);
  let selected;
  if (mode === "smoke") {
    if (conclusions.slice(0, 3).some((value) => value !== "skipped")) throw new Error("Wrong smoke gate identity");
    selected = [conclusions[3]];
  } else {
    if (conclusions[3] !== "skipped") throw new Error("Wrong candidate gate identity");
    // The full job also succeeds as a no-op for docs; Docs only is authoritative when selected.
    if (conclusions[0] === "success") selected = [conclusions[1], conclusions[2] === "skipped" ? conclusions[1] : conclusions[2]];
    else selected = [conclusions[0]];
  }
  const conclusion = selected.every((value) => value === "success") ? "success" :
    selected.includes("timed_out") ? "timed_out" : selected.includes("failure") ? "failure" : selected.includes("cancelled") ? "cancelled" : "unknown";
  const times = jobs.filter((job) => GATES.includes(job.name)).map((job) => Date.parse(job.completed_at)).filter(Number.isFinite);
  const timestamp = times.length ? Math.max(...times) : Date.parse(run.run_started_at);
  if (!Number.isFinite(timestamp) || timestamp > now + 60_000 || timestamp < active.expected.startedAt - 60_000) throw new Error("Invalid notification assessment time");
  if (binding !== null) validateBinding(binding, { pr: active.pr });
  if ((binding === null) !== (bindingSha === null) || (bindingSha !== null && !SHA.test(bindingSha))) throw new Error("Invalid notification binding reference");
  return canonicalEvent({
    version: 1, repository: REPOSITORY, issue: binding?.issue ?? null, pr: active.pr,
    launchId: binding?.launchId ?? null, bindingSha, stateSha,
    transaction: match[1], queueTransaction: active.id,
    runId: run.id, runAttempt: run.run_attempt, workflowId: run.workflow_id, workflowHead: run.head_sha,
    candidate: match[3], base: match[4], mergeSha: mode === "smoke" ? active.mergeSha : null,
    phase: mode === "smoke" ? "smoke" : entry.ready ? "candidate" : "preview", conclusion,
    assessment: "gates_completed", emittedAt: new Date(timestamp).toISOString(),
    expiresAt: new Date(timestamp + 7 * 86400000).toISOString(),
    runUrl: `https://github.com/${REPOSITORY}/actions/runs/${run.id}/attempts/${run.run_attempt}`,
  });
}

export async function readJobs(github, runId, attempt) {
  const jobs = [];
  for (let page = 1; page <= 10; page++) {
    const result = await github.api("GET", `${root}/actions/runs/${runId}/attempts/${attempt}/jobs?per_page=100&page=${page}`);
    if (!Array.isArray(result.jobs)) throw new Error("Missing notification jobs");
    jobs.push(...result.jobs);
    if (result.jobs.length < 100) return jobs;
  }
  throw new Error("Notification jobs exceeded bound");
}

async function readMatchingRuns(github, title) {
  const runs = [];
  for (let page = 1; page <= 100; page++) {
    const result = await github.api("GET", `${root}/actions/workflows/validate.yml/runs?per_page=100&page=${page}`);
    if (!Array.isArray(result.workflow_runs)) throw new Error("Missing notification run history");
    runs.push(...result.workflow_runs.filter((run) => run.display_title === title));
    if (result.workflow_runs.length < 100) return runs;
  }
  throw new Error("Notification run history exceeded bound");
}

export async function verifyRemoteEvent(github, event) {
  validateEvent(event);
  const ancestry = await github.api("GET", `${root}/compare/${event.stateSha}...vera-ci-queue-state`);
  if (!["ahead", "identical"].includes(ancestry.status)) throw new Error("Notification snapshot is outside trusted queue history");
  const snapshot = decodeDocument(await github.api("GET", `${root}/contents/queue.json?ref=${event.stateSha}`));
  const run = await github.api("GET", `${root}/actions/runs/${event.runId}/attempts/${event.runAttempt}`);
  const jobs = await readJobs(github, event.runId, event.runAttempt);
  const runs = await readMatchingRuns(github, snapshot.active?.expected?.title);
  const binding = event.bindingSha === null ? null : decodeDocument(await github.api("GET", `${root}/git/blobs/${event.bindingSha}`));
  if (binding) {
    const registered = await github.api("GET", `${root}/contents/registrations/pr-${event.pr}.json?ref=vera-ci-notification-outbox`);
    if (registered.sha !== event.bindingSha) throw new Error("Origin registration changed after notification");
    const pull = await github.api("GET", `${root}/pulls/${event.pr}`);
    validateBinding(binding, { pr: event.pr, branch: pull.head?.ref });
  }
  const verified = verifiedEvent({ state: snapshot, stateSha: event.stateSha, run, jobs, runs, binding, bindingSha: event.bindingSha });
  if (JSON.stringify(verified) !== JSON.stringify(canonicalEvent(event))) throw new Error("Notification differs from independent finalization evidence");
  return verified;
}

export async function captureFinalization(github, context, outbox) {
  if (github.repository !== REPOSITORY || context.job !== "ci-notification" || context.actor !== "github-actions[bot]" ||
      context.workflowRef !== `${REPOSITORY}/.github/workflows/validate.yml@refs/heads/main` || context.ref !== "refs/heads/main" ||
      !positive(Number(context.runId)) || !positive(Number(context.runAttempt)) || !["pr", "smoke"].includes(context.mode)) throw new Error("Untrusted notification invocation");
  if (!SHA.test(context.stateSha ?? "")) throw new Error("Missing immutable finalizer source state");
  const loaded = { sha: context.stateSha, state: decodeDocument(await github.api("GET", `${root}/contents/queue.json?ref=${context.stateSha}`)) };
  if (!loaded.state.active?.expected) return null;
  const run = await github.api("GET", `${root}/actions/runs/${context.runId}/attempts/${context.runAttempt}`);
  if (run.display_title !== loaded.state.active.expected.title) return null;
  if (!run.display_title.includes(`:${context.mode}:`)) throw new Error("Notification mode mismatch");
  const jobs = await readJobs(github, run.id, run.run_attempt);
  const finalizer = jobs.find((job) => job.name === "Queue completion");
  if (finalizer?.status !== "completed" || finalizer.conclusion !== "success") throw new Error("Trusted finalizer has not completed successfully");
  const runs = await readMatchingRuns(github, run.display_title);
  const document = await outbox.readDocument(`registrations/pr-${loaded.state.active.pr}.json`);
  const binding = document?.data ?? null;
  if (binding) {
    const pull = await github.api("GET", `${root}/pulls/${loaded.state.active.pr}`);
    validateBinding(binding, { pr: loaded.state.active.pr, branch: pull.head?.ref });
  }
  const event = verifiedEvent({ state: loaded.state, stateSha: loaded.sha, run, jobs, runs, binding, bindingSha: document?.sha ?? null });
  try { return { event, result: await outbox.publish(event) }; }
  catch { return { event, result: { status: "publication_unknown" } }; }
}
