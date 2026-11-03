import { execFile } from "node:child_process";
import { promisify, TextDecoder } from "node:util";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";
import { Worker } from "node:worker_threads";
import { URL } from "node:url";
import { clearTimeout, setTimeout as setTimer } from "node:timers";

import { verifyReviewFromGh } from "./chat-review-github.mjs";
import { issueRevision, REPOS } from "./chat-review-current.mjs";
import {
  canonicalIssueKey,
  linksForIssue,
  loadLocalCodexSessionMap,
} from "./codex-session-links.mjs";
import {
  defaultInstallationIdPath,
  readLocalInstallationId,
} from "./codex-session-register-lib.mjs";
import { validateState } from "./ci-queue.mjs";
import { derivePrimaryAction } from "./project-progress-actions.mjs";
import { deepseekRouteForIssue, loadDeepSeekDashboardEvidence } from "./project-progress-deepseek.mjs";
import { localOrigins, matchOrigin, matchesOwnerClaim, readProducerChecklist } from "./project-progress-transport.mjs";
import { assessRun } from "./ci-queue-policy.ts";
import { latestClaim } from "./roadmap.mjs";

const execFileAsync = promisify(execFile);
const REPOSITORY = "mbelinkie/vera-script-to-timeline";
const QUEUE_BRANCH = "vera-ci-queue-state";
const QUEUE_FILE = "queue.json";
const QUEUE_CONTROL_ISSUE = 361;
const MAX_AGE_MS = 16 * 60 * 1000;
const MAX_QUEUE_ENTRIES = 100;
const MAX_LINKED_ISSUES = 100;
const MAX_GH_OUTPUT = 4 * 1024 * 1024;
const GH_TIMEOUT_MS = 15_000;
const CHAT_REVIEW_TIMEOUT_MS = 60_000;
const ACTIVE_RUN_STATUSES = Object.freeze(["queued", "in_progress", "waiting", "requested", "pending"]);
const MAX_VALIDATE_RUN_PAGES = 100;
const MAX_OTHER_RUNS = 100;
const MAX_EVENT_COMMENT_LOOKUPS = (MAX_QUEUE_ENTRIES + 1) * 2;
// Producer grandfathered work already started before the Nov 3 restart.
const CONTINUATION_CUTOFF = Date.parse("2026-11-03T07:30:00Z");
const SHA = /^[0-9a-f]{40}$/i;
const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const RUN_TITLE = /^vera-queue:([0-9a-f-]{36}):(pr|smoke):([0-9a-f]{40}):([0-9a-f]{40})$/;
const JOB_GATES = Object.freeze({
  "Classify PR changes": { pr: ["success"], smoke: ["skipped"] },
  "TypeScript and Python": { pr: ["success"], smoke: ["skipped"] },
  "Docs only": { pr: ["success", "skipped"], smoke: ["skipped"] },
  "Main smoke": { pr: ["skipped"], smoke: ["success"] },
});
const CHAT_REVIEW_WORKER = `
const { parentPort, workerData } = require("node:worker_threads");
const { execFileSync } = require("node:child_process");

(async () => {
  try {
    const { verifyReviewFromGh } = await import(workerData.verifierUrl);
    const readGh = (args) => {
      try {
        return execFileSync(workerData.ghExecutable, ["api", ...args.slice(1)], {
          cwd: workerData.repositoryRoot,
          encoding: "utf8",
          maxBuffer: workerData.maxGhOutput,
          timeout: workerData.ghTimeoutMs,
        });
      } catch {
        const error = new Error("GitHub read unavailable");
        error.workflowSourceError = true;
        throw error;
      }
    };
    const result = verifyReviewFromGh(readGh, workerData.repository, workerData.number, workerData.snapshot);
    parentPort.postMessage({ result });
  } catch (error) {
    parentPort.postMessage({
      sourceError: error?.workflowSourceError === true,
      message: error?.workflowSourceError === true ? "GitHub read unavailable" : error instanceof Error ? error.message : "",
    });
  } finally {
    parentPort.close();
  }
})();
`;

const execGh = async (args, cwd) => {
  try {
    const { stdout } = await execFileAsync("gh", ["api", ...args], {
      cwd,
      encoding: "utf8",
      maxBuffer: MAX_GH_OUTPUT,
      timeout: GH_TIMEOUT_MS,
    });
    return stdout;
  } catch {
    throw new WorkflowSourceError();
  }
};

class WorkflowSourceError extends Error {
  constructor() {
    super("GitHub read unavailable");
    this.workflowSourceError = true;
  }
}

function timestamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

function clockValue(value) {
  const resolved = typeof value === "function" ? value() : value;
  const date = resolved instanceof Date ? resolved : new Date(resolved ?? Date.now());
  return Number.isFinite(date.getTime()) ? date : null;
}

function json(raw) {
  return typeof raw === "string" ? JSON.parse(raw) : raw;
}

function repoForIssue(raw) {
  const key = canonicalIssueKey(raw);
  if (!key) return null;
  const [repository, issueNumber] = key.split("#");
  return REPOS.has(repository) ? { repository, number: Number(issueNumber), url: `https://github.com/${repository}/issues/${issueNumber}` } : null;
}

function safeApiPath(value) {
  return typeof value === "string"
    && !value.startsWith("/")
    && !value.includes("..")
    && /^repos\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/(?:contents\/queue\.json\?ref=vera-ci-queue-state|issues\/[1-9][0-9]*(?:\/timeline\?per_page=100|\/comments\?per_page=100(?:&page=[1-9][0-9]*)?)?|pulls\/[1-9][0-9]*(?:\/reviews\?per_page=100)?|actions\/workflows\/validate\.yml(?:\/runs\?(?:event=workflow_dispatch&head_sha=[0-9a-f]{40}&per_page=100&page=1|per_page=100&status=(?:queued|in_progress|waiting|requested|pending)|per_page=100&page=[1-9][0-9]*))?|actions\/runs\/[1-9][0-9]*(?:\/attempts\/[1-9][0-9]*\/jobs\?per_page=100&page=1)?|git\/ref\/heads\/main)$/.test(value)
    || value === "rate_limit";
}

function issueLabelNames(item) {
  if (!Array.isArray(item?.labels)) return [];
  return item.labels.map((label) => typeof label === "string" ? label : label?.name).filter((label) => typeof label === "string");
}

function validSha(value) {
  return typeof value === "string" && SHA.test(value);
}

function safeIssueCommentUrl(value, issue, commentId) {
  return value === `${issue.url}#issuecomment-${commentId}` ? value : null;
}

function safePullUrl(value, number, repository = REPOSITORY) {
  const expected = `https://github.com/${repository}/pull/${number}`;
  return value === expected ? expected : null;
}

function safeRunUrl(value, runId, repository = REPOSITORY) {
  const expected = `https://github.com/${repository}/actions/runs/${runId}`;
  return value === expected ? expected : null;
}

function blankIssueRecord(snapshotAt, lastError = null) {
  return {
    snapshotAt,
    lastError,
    chat: { state: "unknown", reason: "Current Chat review evidence is unavailable." },
    codex: { state: "unknown", reason: "No independently verified issue claim is connected.", ownerBound: false },
    deepseek: { state: "off", reason: "DeepSeek execution is not connected or authorized." },
    review: { state: "unknown", reason: "Independent Claude review evidence is not connected to a verifiable PR head." },
    ci: { state: "unknown", reason: "CI queue evidence is unavailable for this issue." },
    session: { status: "missing", reason: "No verified local Codex session is linked.", hasBrowser: false },
    acceptance: { state: "unknown", reason: "Producer acceptance is recorded separately after delivery." },
  };
}

function contentState(body) {
  if (!body || body.path !== QUEUE_FILE || body.name !== QUEUE_FILE || body.type !== "file"
      || body.encoding !== "base64" || !SHA.test(body.sha ?? "")
      || !Number.isSafeInteger(body.size) || body.size < 1 || body.size > 1024 * 1024
      || typeof body.content !== "string") throw new Error("invalid_queue_contents");
  const encoded = body.content.replace(/\s/g, "");
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw new Error("invalid_queue_contents");
  }
  const buffer = Buffer.from(encoded, "base64");
  if (buffer.length > 1024 * 1024 || buffer.toString("base64") !== encoded) throw new Error("invalid_queue_contents");
  const html = `https://github.com/${REPOSITORY}/blob/${QUEUE_BRANCH}/${QUEUE_FILE}`;
  if (body.html_url !== html) throw new Error("invalid_queue_contents");
  if (buffer.length !== body.size) throw new Error("invalid_queue_contents");
  const state = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buffer));
  validateState(state);
  if (state.controlIssue !== QUEUE_CONTROL_ISSUE || state.entries.length > MAX_QUEUE_ENTRIES) {
    throw new Error("invalid_queue_state");
  }
  return state;
}

function validPull(pull, number, repository = REPOSITORY) {
  const url = safePullUrl(pull?.html_url, number, repository);
  return Boolean(url && pull?.number === number
    && pull?.base?.repo?.full_name === repository
    && pull?.head?.repo?.full_name === repository
    && typeof pull.base.ref === "string"
    && typeof pull.state === "string"
    && typeof pull.draft === "boolean"
    && validSha(pull.head.sha)
    && validSha(pull.base.sha));
}

function decodePull(pull, number, repository = REPOSITORY) {
  if (!validPull(pull, number, repository)) return null;
  return {
    url: safePullUrl(pull.html_url, number, repository),
    number,
    title: pull.title,
    body: typeof pull.body === "string" ? pull.body : "",
    createdAt: pull.created_at,
    headRef: pull.head.ref,
    head: pull.head.sha.toLowerCase(),
    base: pull.base.sha.toLowerCase(),
    baseRef: pull.base.ref,
    state: pull.state,
    draft: pull.draft,
    merged: pull.merged === true,
    mergeSha: validSha(pull.merge_commit_sha) ? pull.merge_commit_sha.toLowerCase() : null,
  };
}

async function mapLimit(values, limit, mapper) {
  const result = new Array(values.length);
  let cursor = 0;
  async function worker() {
    while (cursor < values.length) {
      const index = cursor++;
      try { result[index] = await mapper(values[index], index); }
      catch { result[index] = null; }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
  return result;
}

function labelsForStatus(labels) {
  return new Set(labels);
}

async function claimForIssue(item, issue, get) {
  const current = await get(`repos/${issue.repository}/issues/${issue.number}`);
  if (current?.number !== issue.number || current.html_url !== issue.url
      || current.repository_url !== `https://api.github.com/repos/${issue.repository}`
      || current.state !== "open" || current.title !== item.title || current.body !== item.body
      || !Number.isSafeInteger(current.comments) || current.comments < 0 || current.comments > 10_000) {
    return { state: "unknown", reason: "Current issue claim history could not be matched to the Project snapshot." };
  }
  if (current.comments === 0) return { state: "unclaimed", reason: "No active issue claim was found." };
  const page = Math.ceil(current.comments / 100);
  const comments = await get(`repos/${issue.repository}/issues/${issue.number}/comments?per_page=100&page=${page}`);
  const expectedLength = current.comments - (page - 1) * 100;
  if (!Array.isArray(comments) || comments.length !== expectedLength) {
    return { state: "unknown", reason: "The latest issue claim history page is incomplete." };
  }
  let previousId = 0;
  for (const comment of comments) {
    if (!Number.isSafeInteger(comment?.id) || comment.id <= previousId || typeof comment.body !== "string") {
      return { state: "unknown", reason: "The latest issue claim history page is invalid." };
    }
    previousId = comment.id;
  }
  const trustedComments = comments.filter((comment) => comment.user?.login === "mbelinkie"
    && comment.performed_via_github_app === null
    && typeof comment.created_at === "string" && typeof comment.updated_at === "string"
    && comment.created_at === comment.updated_at
    && Number.isFinite(Date.parse(comment.created_at)));
  let claim;
  try {
    for (const comment of trustedComments) {
      const markers = [...comment.body.matchAll(/<!--\s*vera-claim\b/g)].length;
      const parsedMarkers = [...comment.body.matchAll(/<!--\s*vera-claim\s+\{.+?\}\s*-->/g)].length;
      if (markers !== parsedMarkers) throw new Error("Malformed claim marker");
      if (markers && latestClaim([comment]) === undefined) throw new Error("Malformed claim marker");
    }
    claim = latestClaim(trustedComments);
  }
  catch { return { state: "unknown", reason: "The latest issue claim marker is invalid." }; }
  if (claim?.state === "active" && typeof claim.model === "string" && typeof claim.effort === "string"
      && typeof claim.task === "string" && typeof claim.branch === "string"
      && typeof claim.startedAt === "string" && Number.isFinite(Date.parse(claim.startedAt))) {
    return { state: "claimed", startedAt: claim.startedAt,
      reason: "A current roadmap claim exists; this does not verify that an agent is running.",
      originClaim: { state: "active", task: claim.task, branch: claim.branch } };
  }
  if (page > 1 && !trustedComments.some((comment) => /<!--\s*vera-claim\s+\{/.test(comment.body))) {
    return { state: "unknown", reason: "The latest comment page has no claim marker; older claim history is not inferred." };
  }
  return page === 1
    ? { state: "unclaimed", reason: "No active issue claim was found." }
    : { state: "unknown", reason: "No active issue claim was found on the latest page; older claim history is not inferred." };
}

function chatVerificationTarget(item) {
  const labels = labelsForStatus(issueLabelNames(item));
  if (item.status === "Done" || item.state?.toLowerCase() === "closed") {
    return { result: { state: "done", reason: "This roadmap issue is marked Done." } };
  }
  if (!labels.has("chat-reviewed")) {
    return { result: labels.has("chat-review-pending")
      ? { state: "pending", reason: "Producer Chat review is pending." }
      : { state: "pending", reason: "A current Producer Chat review is required before work starts." } };
  }
  const issueIdentity = repoForIssue(item.url);
  if (!issueIdentity || issueIdentity.number !== item.number) {
    return { result: { state: "unknown", reason: "The issue identity does not match the verified GitHub URL." } };
  }
  return { identity: issueIdentity };
}

function chatVerificationResult(issueIdentity, verified) {
  const url = safeIssueCommentUrl(verified.url, issueIdentity, verified.commentId);
  return verified.approved && url
    ? { state: "approved", url, reason: "Current Producer Chat review verified for this issue revision." }
    : { state: "unknown", reason: "The verified Chat review did not provide a safe comment link." };
}

function chatVerificationError(error) {
  if (error?.workflowSourceError || error?.sourceError) {
    return { state: "unknown", reason: "GitHub could not refresh the canonical Chat review history." };
  }
  const message = error instanceof Error ? error.message : typeof error?.message === "string" ? error.message : "";
  if (/^(?:Valid current Producer Chat review missing|Producer Chat review is stale|Current Producer Chat review label required)$/.test(message)) {
    return { state: "pending", reason: "The latest Producer Chat review is missing, stale, or superseded." };
  }
  return { state: "unknown", reason: "Canonical Chat review history could not be verified completely." };
}

function chatForIssue(item, readGh) {
  const target = chatVerificationTarget(item);
  if (target.result) return target.result;
  const sourceRead = (args) => {
    try {
      const value = readGh(args);
      return typeof value === "string" ? value : JSON.stringify(value);
    } catch {
      throw new WorkflowSourceError();
    }
  };
  try {
    const verified = verifyReviewFromGh(sourceRead, target.identity.repository, target.identity.number, {
      title: item.title,
      body: item.body,
      labels: item.labels,
    });
    return chatVerificationResult(target.identity, verified);
  } catch (error) { return chatVerificationError(error); }
}

function verifyChatReviewInWorker(item, identity, repositoryRoot, ghExecutable) {
  return new Promise((resolve) => {
    const worker = new Worker(CHAT_REVIEW_WORKER, {
      eval: true,
      workerData: {
        verifierUrl: new URL("./chat-review-github.mjs", import.meta.url).href,
        repositoryRoot,
        ghExecutable,
        repository: identity.repository,
        number: identity.number,
        snapshot: { title: item.title, body: item.body, labels: item.labels },
        maxGhOutput: MAX_GH_OUTPUT,
        ghTimeoutMs: GH_TIMEOUT_MS,
      },
    });
    let settled = false;
    const timer = setTimer(() => finish({ sourceError: true }, true), CHAT_REVIEW_TIMEOUT_MS);
    const finish = (result, terminate = false) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (terminate) void worker.terminate();
      resolve(result);
    };
    worker.once("message", (result) => finish(result));
    worker.once("error", () => finish({ sourceError: true }, true));
    worker.once("exit", () => {
      if (!settled) finish({ sourceError: true });
    });
  });
}

async function chatForIssueInWorker(item, repositoryRoot, ghExecutable) {
  const target = chatVerificationTarget(item);
  if (target.result) return target.result;
  try {
    const result = await verifyChatReviewInWorker(item, target.identity, repositoryRoot, ghExecutable);
    return result && result.result
      ? chatVerificationResult(target.identity, result.result)
      : chatVerificationError(result ?? { sourceError: true });
  } catch (error) { return chatVerificationError(error); }
}

function linkedPullNumbers(timeline, issue) {
  if (!Array.isArray(timeline) || timeline.length >= 100) return { numbers: [], complete: false };
  const numbers = new Set();
  for (const event of timeline) {
    const source = event?.source?.issue;
    if (event?.event !== "cross-referenced" || !source?.pull_request) continue;
    const match = /^https:\/\/github\.com\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)\/pull\/([1-9][0-9]*)$/.exec(source.html_url ?? "");
    if (match && `${match[1]}/${match[2]}`.toLowerCase() === issue.repository.toLowerCase()) {
      numbers.add(Number(match[3]));
    }
  }
  return { numbers: [...numbers], complete: true };
}

function queueEntryByPr(state, pr) {
  return state?.entries.find((entry) => entry.pr === pr) ?? null;
}

function matchingCompleted(state, pr) {
  return [...(state?.completed ?? [])].reverse().find((entry) => entry.pr === pr) ?? null;
}

function verifyJobSet(raw, runId, runAttempt, mode, requireCompletion) {
  if (!Array.isArray(raw) || raw.length >= 100) return false;
  const byName = new Map();
  const ids = new Set();
  for (const job of raw) {
    if (!Number.isSafeInteger(job?.id) || job.id < 1 || ids.has(job.id) || job.run_id !== runId
        || (job.run_attempt !== undefined && job.run_attempt !== runAttempt)
        || typeof job.name !== "string" || byName.has(job.name)) return false;
    ids.add(job.id);
    byName.set(job.name, job);
  }
  byName.delete("CI notification");
  if (byName.size !== Object.keys(JOB_GATES).length + 1) return false;
  for (const [name, outcomes] of Object.entries(JOB_GATES)) {
    const job = byName.get(name);
    if (job?.status !== "completed" || !outcomes[mode]?.includes(job.conclusion)) return false;
  }
  const completion = byName.get("Queue completion");
  return requireCompletion
    ? completion?.status === "completed" && completion.conclusion === "success"
    : ["in_progress", "completed"].includes(completion?.status);
}

function acceptedGateCompletedAt(raw, mode) {
  if (!Array.isArray(raw) || raw.length >= 100) return null;
  const expected = [...Object.keys(JOB_GATES), "Queue completion"];
  const byName = new Map(raw.filter((job) => job?.name !== "CI notification").map((job) => [job?.name, job]));
  if (byName.size !== expected.length || expected.some((name) => !byName.has(name))) return null;
  const times = [];
  for (const name of expected) {
    const job = byName.get(name);
    if (job.status !== "completed" || !JOB_GATES[name]?.[mode]?.includes(job.conclusion)
        && name !== "Queue completion") return null;
    const value = Date.parse(job.completed_at ?? "");
    if (!Number.isFinite(value)) return null;
    times.push(value);
  }
  const completion = byName.get("Queue completion");
  if (completion.status !== "completed" || completion.conclusion !== "success") return null;
  return timestamp(Math.max(...times));
}

function eventIdFromComments(comments, runId, runAttempt) {
  if (!Array.isArray(comments) || comments.length >= 100) return null;
  let previousId = 0;
  const matches = new Set();
  for (const comment of comments) {
    if (!Number.isSafeInteger(comment?.id) || comment.id <= previousId) return null;
    previousId = comment.id;
    if (comment.user?.login !== "github-actions[bot]" || comment.created_at !== comment.updated_at
        || !Number.isFinite(Date.parse(comment.created_at ?? ""))
        || typeof comment.body !== "string") continue;
    const markers = [...comment.body.matchAll(/<!-- vera-ci-event:([0-9a-f]{64}) -->/g)];
    const references = [...comment.body.matchAll(/^Run: ([1-9][0-9]*), attempt ([1-9][0-9]*); workflow: ([1-9][0-9]*)\.$/gm)];
    if (markers.length === 1 && references.length === 1
        && Number(references[0][1]) === runId && Number(references[0][2]) === runAttempt) {
      matches.add(markers[0][1]);
    }
  }
  return matches.size === 1 ? [...matches][0] : null;
}

function expectedForActive(active) {
  const expected = active?.expected;
  const title = RUN_TITLE.exec(expected?.title ?? "");
  if (!title || !UUID.test(title[1]) || !validSha(title[3]) || !validSha(title[4])
      || !Number.isSafeInteger(expected.workflowId) || expected.workflowId < 1
      || !validSha(expected.workflowHead) || !Number.isFinite(expected.startedAt)
      || !Number.isFinite(expected.timeoutMs) || expected.timeoutMs <= 0) return null;
  const mode = active.phase === "smoke" ? "smoke" : active.phase === "validating" || active.phase === "merging" ? "pr" : null;
  if (!mode || title[2] !== mode) return null;
  const candidate = mode === "smoke" ? active.mergeSha : active.candidate;
  const base = mode === "smoke" ? active.mergeSha : active.base;
  if (!validSha(candidate) || !validSha(base) || title[3].toLowerCase() !== candidate.toLowerCase()
      || title[4].toLowerCase() !== base.toLowerCase()) return null;
  return { ...expected, title: expected.title, candidate: candidate.toLowerCase(), base: base.toLowerCase(), mode };
}

async function validateRunInventory(get, workflowId) {
  const runs = new Map();
  const addRuns = (batch, expectedStatus = null) => {
    if (!Array.isArray(batch)) throw new Error("Invalid Validate run inventory");
    for (const run of batch) {
      if (!Number.isSafeInteger(run?.id) || run.id < 1) throw new Error("Invalid Validate run identity");
      if (!expectedStatus && runs.has(run.id)) continue;
      if (typeof run.status !== "string" || typeof run.event !== "string"
          || !Number.isSafeInteger(run.run_attempt) || run.run_attempt < 1
          || (expectedStatus && run.status !== expectedStatus)) throw new Error("Invalid Validate run status");
      if (run.status === "completed" || run.event === "pull_request") continue;
      if (run.workflow_id !== workflowId) {
        throw new Error("Unverified active Validate run");
      }
      const url = safeRunUrl(run.html_url, run.id, REPOSITORY);
      if (!url) throw new Error("Invalid Validate run URL");
      const previous = runs.get(run.id);
      if (previous && (previous.status !== run.status || previous.attempt.number !== run.run_attempt)) {
        throw new Error("Validate run changed during inventory");
      }
      if (!previous) runs.set(run.id, {
        id: run.id,
        status: run.status,
        attempt: { number: run.run_attempt, startedAt: timestamp(run.run_started_at) },
        url,
      });
    }
  };

  let complete = false;
  try {
    if (!Number.isSafeInteger(workflowId) || workflowId < 1) throw new Error("Validate workflow is unknown");
    for (const status of ACTIVE_RUN_STATUSES) {
      const response = await get(`repos/${REPOSITORY}/actions/workflows/validate.yml/runs?per_page=100&status=${status}`);
      const batch = response?.workflow_runs;
      if (!Number.isSafeInteger(response?.total_count) || response.total_count < 0
          || !Array.isArray(batch) || batch.length !== response.total_count) {
        throw new Error("Incomplete Validate status result");
      }
      addRuns(batch, status);
      if (batch.length >= 100) throw new Error("Validate status result exceeded bound");
    }
    let historyCount = null;
    for (let page = 1; page <= MAX_VALIDATE_RUN_PAGES; page += 1) {
      const response = await get(`repos/${REPOSITORY}/actions/workflows/validate.yml/runs?per_page=100&page=${page}`);
      const batch = response?.workflow_runs;
      if (!Number.isSafeInteger(response?.total_count) || response.total_count < 0 || !Array.isArray(batch)) {
        throw new Error("Incomplete Validate run page");
      }
      if (historyCount === null) historyCount = response.total_count;
      if (response.total_count !== historyCount) throw new Error("Validate run count changed during inventory");
      const expectedLength = Math.max(0, Math.min(100, historyCount - (page - 1) * 100));
      if (batch.length !== expectedLength) throw new Error("Validate run page does not match total_count");
      addRuns(batch);
      if (batch.length < 100) {
        complete = true;
        break;
      }
    }
  } catch { /* A partial inventory must never imply an idle slot. */ }
  const observed = [...runs.values()];
  return { complete, runs: observed.slice(0, MAX_OTHER_RUNS), truncated: observed.length > MAX_OTHER_RUNS };
}

function queueEnvelope(snapshotAt, lastError = null) {
  return {
    snapshotAt,
    lastError,
    state: "unknown",
    slot: { phase: "unknown" },
    slotUnknown: true,
    otherRuns: [],
    otherRunsTruncated: false,
    paused: false,
    active: null,
    waiting: [],
    ready: 0,
    delivered: 0,
    lastDelivered: null,
    recentDeliveries: [],
    url: `https://github.com/${REPOSITORY}/issues/${QUEUE_CONTROL_ISSUE}`,
  };
}

function unknownCi(reason) {
  return { state: "unknown", reason };
}

/** Re-read the independent private identity and mapping before a local navigation. */
export async function resolveLocalSession(issueUrl, options = {}) {
  const issue = repoForIssue(issueUrl);
  if (!issue) return { status: "invalid", reason: "Invalid GitHub issue identity" };
  const mappingPath = options.mappingPath;
  const installationIdPath = options.installationIdPath ?? defaultInstallationIdPath(mappingPath);
  const loadMap = options.loadLocalCodexSessionMap ?? loadLocalCodexSessionMap;
  const readIdentity = options.readLocalInstallationId ?? readLocalInstallationId;
  try {
    const [mapping, installationId] = await Promise.all([
      loadMap(mappingPath),
      readIdentity(installationIdPath),
    ]);
    const resolved = linksForIssue(issue.url, mapping, installationId);
    const safe = { ...resolved };
    delete safe.threadId;
    return {
      status: safe.status,
      reason: safe.reason,
      ...(safe.status === "verified-local" && typeof safe.appUrl === "string" ? { appUrl: safe.appUrl } : {}),
      ...(typeof safe.browserUrl === "string" ? { browserUrl: safe.browserUrl } : {}),
    };
  } catch {
    return { status: "invalid", reason: "Local Codex session evidence is unavailable or invalid" };
  }
}

/** Refresh read-only workflow sources once. The returned value is inert renderer data. */
export async function loadWorkflowEvidence(repositoryRoot, items, options = {}) {
  const now = clockValue(options.now);
  const snapshotAt = timestamp(now ?? new Date());
  const evidence = {
    snapshotAt,
    lastError: null,
    issues: {},
    ciQueue: queueEnvelope(snapshotAt),
    deepseek: { installation: { state: "unknown", checkedAt: snapshotAt } },
  };
  const rows = Array.isArray(items) ? items : [];
  const identities = rows.map((item) => ({ item, identity: repoForIssue(item?.url) }))
    .filter(({ item, identity }) => identity && identity.number === item.number);
  let deepseekEvidence;
  try {
    deepseekEvidence = await loadDeepSeekDashboardEvidence({
      now: now?.getTime() ?? Number.NaN,
      env: options.env ?? process.env,
    });
    evidence.deepseek = { installation: deepseekEvidence.installation };
  } catch {
    deepseekEvidence = { installation: { state: "unknown", checkedAt: snapshotAt }, byIssue: {} };
    evidence.deepseek = { installation: deepseekEvidence.installation };
  }
  for (const { item, identity } of identities) {
    const record = blankIssueRecord(snapshotAt);
    const deepseekRoute = deepseekRouteForIssue(item);
    const localState = deepseekEvidence.byIssue?.[identity.url];
    record.deepseek = localState
      ? { ...localState, route: deepseekRoute }
      : deepseekRoute === "chat"
        ? { state: "route-to-chat", route: "chat",
          reason: "ChatGPT prepares the task. A paid run requires separate exact task approval." }
        : { state: "excluded", route: null, reason: "This ticket does not use the default new coding route." };
    if (item.status === "Done" || item.state?.toLowerCase() === "closed") {
      record.chat = { state: "done", reason: "This roadmap issue is marked Done." };
    } else if (!issueLabelNames(item).includes("chat-reviewed")) {
      record.chat = issueLabelNames(item).includes("chat-review-pending")
        ? { state: "pending", reason: "Producer Chat review is pending." }
        : { state: "pending", reason: "A current Producer Chat review is required before work starts." };
    }
    evidence.issues[identity.url] = record;
  }

  if (!now) {
    evidence.lastError = "Workflow evidence timestamp is invalid.";
    for (const record of Object.values(evidence.issues)) record.lastError = evidence.lastError;
    evidence.ciQueue.lastError = evidence.lastError;
    return evidence;
  }

  let repository = options.repository;
  if (!repository) {
    try {
      const config = JSON.parse(await readFile(`${repositoryRoot}/.github/vera-roadmap.json`, "utf8"));
      repository = config.repository;
    } catch {
      repository = REPOSITORY;
    }
  }
  if (repository !== REPOSITORY) {
    evidence.lastError = "The configured CI repository is not supported.";
    evidence.ciQueue.lastError = evidence.lastError;
    for (const record of Object.values(evidence.issues)) record.lastError = evidence.lastError;
    return evidence;
  }

  const readApi = options.readApi ?? (async (apiPath) => json(await execGh([apiPath], repositoryRoot)));
  const readGh = options.readGh;
  const apiCache = new Map();
  const get = (apiPath) => {
    if (!safeApiPath(apiPath)) return Promise.reject(new WorkflowSourceError());
    if (!apiCache.has(apiPath)) {
      apiCache.set(apiPath, Promise.resolve().then(() => readApi(apiPath)).then(json));
    }
    return apiCache.get(apiPath);
  };

  const chatTargets = identities.filter(({ item }) => item.status !== "Done"
    && item.number !== QUEUE_CONTROL_ISSUE && item.state?.toLowerCase() !== "closed"
    && issueLabelNames(item).includes("chat-reviewed"));
  const claimTargets = identities.filter(({ item }) => item.status !== "Done"
    && item.number !== QUEUE_CONTROL_ISSUE && item.state?.toLowerCase() !== "closed").slice(0, MAX_LINKED_ISSUES);
  const timelineTargets = identities.filter(({ item, identity }) => identity.repository === REPOSITORY
    && item.number !== QUEUE_CONTROL_ISSUE && item.status !== "Done"
    && item.state?.toLowerCase() !== "closed").slice(0, MAX_LINKED_ISSUES);
  const baseReads = 721 + ACTIVE_RUN_STATUSES.length + MAX_VALIDATE_RUN_PAGES + MAX_EVENT_COMMENT_LOOKUPS;
  let chatLimit;

  try {
    const limit = await get("rate_limit");
    const remaining = limit?.resources?.core?.remaining;
    if (!Number.isSafeInteger(remaining) || remaining < baseReads) {
      throw new Error("rate_budget");
    }
    chatLimit = Math.min(100, Math.floor((remaining - baseReads) / 42));
  } catch {
    evidence.lastError = "GitHub read budget could not be verified; workflow sources remain unknown.";
    evidence.ciQueue.lastError = evidence.lastError;
    for (const record of Object.values(evidence.issues)) record.lastError = evidence.lastError;
    return evidence;
  }

  const chatResults = await mapLimit(chatTargets.slice(0, chatLimit), 2, async ({ item, identity }) => {
    const record = evidence.issues[identity.url];
    record.chat = readGh
      ? chatForIssue(item, readGh)
      : await chatForIssueInWorker(item, repositoryRoot, options.ghExecutable ?? "gh");
    return record.chat;
  });
  for (let index = 0; index < chatTargets.length; index += 1) {
    if (index >= chatLimit) {
      const { identity } = chatTargets[index];
      evidence.issues[identity.url].chat = { state: "unknown", reason: "Current Chat review verification exceeded the refresh bound." };
    } else if (!chatResults[index]) {
      const { identity } = chatTargets[index];
      evidence.issues[identity.url].chat = { state: "unknown", reason: "Canonical Chat review could not be refreshed." };
    }
  }

  const privateClaimByIssue = new Map();
  const claimResults = await mapLimit(claimTargets, 4, async ({ item, identity }) => {
    const claim = await claimForIssue(item, identity, get);
    const { originClaim, ...publicClaim } = claim;
    if (originClaim) privateClaimByIssue.set(identity.url, originClaim);
    evidence.issues[identity.url].codex = publicClaim;
    return publicClaim;
  });
  for (let index = 0; index < claimTargets.length; index += 1) {
    if (!claimResults[index]) {
      const { identity } = claimTargets[index];
      evidence.issues[identity.url].codex = { state: "unknown", reason: "Current issue claim evidence could not be refreshed." };
    }
  }
  const verifiedClaimUrls = new Set(claimTargets.map(({ identity }) => identity.url));
  for (const { item, identity } of identities) {
    if (!verifiedClaimUrls.has(identity.url) && item.status !== "Done") {
      evidence.issues[identity.url].codex = { state: "unknown", reason: "Claim verification exceeded the refresh bound." };
    }
  }

  let state;
  try {
    state = contentState(await get(`repos/${REPOSITORY}/contents/${QUEUE_FILE}?ref=${QUEUE_BRANCH}`));
  } catch {
    evidence.ciQueue.lastError = "The authoritative CI queue state could not be verified.";
    evidence.ciQueue.state = "unknown";
  }

  const timelineResults = await mapLimit(timelineTargets, 4, async ({ identity }) => {
    const timeline = await get(`repos/${identity.repository}/issues/${identity.number}/timeline?per_page=100`);
    return linkedPullNumbers(timeline, identity);
  });
  const linkedByIssue = new Map();
  const prNumbers = new Set();
  for (let index = 0; index < timelineTargets.length; index += 1) {
    const { identity } = timelineTargets[index];
    const linked = timelineResults[index];
    linkedByIssue.set(identity.url, linked);
    if (linked?.complete) for (const number of linked.numbers) prNumbers.add(number);
  }
  if (state) for (const entry of state.entries) prNumbers.add(entry.pr);
  const prList = [...prNumbers].filter((number) => Number.isSafeInteger(number) && number > 0).slice(0, 200);
  const pullResults = await mapLimit(prList, 4, async (number) => {
    const pull = await get(`repos/${REPOSITORY}/pulls/${number}`);
    return [number, decodePull(pull, number)];
  });
  const pulls = new Map(pullResults.filter(Boolean));

  const workflowNeeded = Boolean(state?.active && ["validating", "merging", "smoke"].includes(state.active.phase))
    || Boolean(state?.completed?.length);
  let workflow = null;
  let workflowId = null;
  let mainSha = null;
  const [mainResult, workflowResult] = await Promise.allSettled([
    state ? get(`repos/${REPOSITORY}/git/ref/heads/main`) : Promise.resolve(null),
    get(`repos/${REPOSITORY}/actions/workflows/validate.yml`),
  ]);
  if (state && mainResult.status === "fulfilled" && validSha(mainResult.value?.object?.sha)) {
    mainSha = mainResult.value.object.sha.toLowerCase();
  } else if (state && !state.paused) {
    evidence.ciQueue.lastError ??= "Current main could not be verified.";
  }
  if (workflowResult.status === "fulfilled" && Number.isSafeInteger(workflowResult.value?.id)
      && workflowResult.value.id > 0 && workflowResult.value.path === ".github/workflows/validate.yml") {
    workflowId = workflowResult.value.id;
    if (workflowResult.value.state === "active") workflow = workflowResult.value;
  }
  if (state && workflowNeeded && !workflow && !state.paused) {
    evidence.ciQueue.lastError ??= "The queue workflow identity could not be verified.";
  }

  const queueRecords = [];
  if (state) {
    for (const entry of state.entries) {
      const pull = pulls.get(entry.pr);
      const isActive = state.active?.pr === entry.pr;
      let verified = Boolean(pull && pull.state === "open" && pull.baseRef === "main"
        && pull.head === entry.head.toLowerCase() && (!entry.ready || !pull.draft));
      if (isActive && ["integrating", "validating", "merging"].includes(state.active.phase)) {
        verified = verified && pull.head === (state.active.candidate ?? entry.head).toLowerCase()
          && pull.base === state.active.base?.toLowerCase() && mainSha === state.active.base?.toLowerCase();
      }
      if (isActive && state.active.phase === "smoke") {
        verified = Boolean(pull?.merged && pull.mergeSha === state.active.mergeSha?.toLowerCase()
          && mainSha === state.active.mergeSha?.toLowerCase());
      }
      queueRecords.push({
        pr: entry.pr,
        title: pull?.title ?? null,
        phase: isActive ? state.active.phase : "waiting",
        head: pull?.head ?? entry.head.toLowerCase(),
        base: pull?.base ?? (isActive ? state.active.base?.toLowerCase() ?? null : null),
        ready: entry.ready && verified,
        verified,
        url: pull?.url ?? null,
        runUrl: null,
        runStatus: null,
        queuedAt: null,
        checkedAt: snapshotAt,
        attempt: null,
        completedAt: null,
        eventId: null,
      });
    }
  }

  async function activeRun(active) {
    const expected = expectedForActive(active);
    if (!expected || !workflow || workflow.id !== active.expected.workflowId || !mainSha) return null;
    const runPath = `repos/${REPOSITORY}/actions/workflows/validate.yml/runs?event=workflow_dispatch&head_sha=${expected.workflowHead}&per_page=100&page=1`;
    const response = await get(runPath);
    if (!Array.isArray(response?.workflow_runs) || response.workflow_runs.length >= 100) return null;
    const matches = response.workflow_runs.filter((run) => run.display_title === expected.title);
    if (matches.length !== 1) return null;
    const run = matches[0];
    if (!Number.isSafeInteger(run?.id) || run.id < 1 || !Number.isSafeInteger(run.run_attempt)
        || run.run_attempt < 1 || run.workflow_id !== workflow.id
        || run.path !== ".github/workflows/validate.yml" || run.event !== "workflow_dispatch"
        || run.head_sha?.toLowerCase() !== expected.workflowHead.toLowerCase()) return null;
    const url = safeRunUrl(run.html_url, run.id, REPOSITORY);
    if (!url) return null;
    const attempt = { number: run.run_attempt, startedAt: timestamp(run.run_started_at) };
    const failureVerified = Boolean(state?.paused && run.status === "completed"
      && run.conclusion !== "success");
    const assessment = assessRun(expected, matches, now.getTime());
    if (assessment.kind === "pause") {
      const identityVerified = Boolean(state?.paused
        && assessRun(expected, matches, expected.startedAt).kind === "wait"
        && url);
      return { run, expected, assessment, valid: false, identityVerified, failureVerified, url, attempt };
    }
    if (assessment.runId !== run.id || safeRunUrl(assessment.url, assessment.runId, REPOSITORY) !== url) return null;
    if (assessment.kind === "passed") {
      const jobs = await get(`repos/${REPOSITORY}/actions/runs/${run.id}/attempts/${run.run_attempt}/jobs?per_page=100&page=1`);
      if (!verifyJobSet(jobs?.jobs, run.id, run.run_attempt, expected.mode, false)) return null;
      const completedAt = acceptedGateCompletedAt(jobs.jobs, expected.mode);
      return { run, expected, assessment, valid: true, url, attempt, completedAt,
        completionSource: completedAt ? "accepted-gates" : null };
    }
    return { run, expected, assessment, valid: true, url, attempt };
  }

  let verifiedActiveRun = null;
  if (state?.active && ["validating", "merging", "smoke"].includes(state.active.phase)) {
    try { verifiedActiveRun = await activeRun(state.active); }
    catch { if (!state.paused) evidence.ciQueue.lastError ??= "The active queue run could not be verified."; }
  }

  const deliveryChecks = new Map();
  const deliveries = (state?.completed ?? []).slice(-MAX_QUEUE_ENTRIES);
  await mapLimit(deliveries, 3, async (delivery) => {
    const pull = pulls.get(delivery.pr);
    if (!pull || !pull.merged || !validSha(delivery.mergeSha)
        || pull.mergeSha !== delivery.mergeSha.toLowerCase()
        || !validSha(delivery.smokeSha) || delivery.smokeSha.toLowerCase() !== delivery.mergeSha.toLowerCase()
        || !Number.isSafeInteger(delivery.runId) || !workflow) {
      deliveryChecks.set(delivery.pr, null);
      return null;
    }
    const run = await get(`repos/${REPOSITORY}/actions/runs/${delivery.runId}`);
    const title = RUN_TITLE.exec(run?.display_title ?? "");
    const runUrl = safeRunUrl(run?.html_url, delivery.runId, REPOSITORY);
    const validRun = Boolean(title && UUID.test(title[1]) && title[2] === "smoke"
      && title[3].toLowerCase() === delivery.smokeSha.toLowerCase()
      && title[4].toLowerCase() === delivery.smokeSha.toLowerCase()
      && run.id === delivery.runId && run.workflow_id === workflow.id
      && run.path === ".github/workflows/validate.yml" && run.event === "workflow_dispatch"
      && run.run_attempt === 1 && run.head_sha?.toLowerCase() === delivery.smokeSha.toLowerCase()
      && run.status === "completed" && run.conclusion === "success" && run.actor?.login === "github-actions[bot]" && runUrl);
    if (!validRun) {
      deliveryChecks.set(delivery.pr, null);
      return null;
    }
    const jobs = await get(`repos/${REPOSITORY}/actions/runs/${delivery.runId}/attempts/1/jobs?per_page=100&page=1`);
    const passed = verifyJobSet(jobs?.jobs, delivery.runId, 1, "smoke", true);
    const completedAt = passed ? acceptedGateCompletedAt(jobs.jobs, "smoke") : null;
    const result = passed ? {
      pr: delivery.pr,
      head: validSha(delivery.candidate) ? delivery.candidate.toLowerCase() : null,
      base: delivery.mergeSha.toLowerCase(),
      runId: delivery.runId,
      url: runUrl,
      checkedAt: snapshotAt,
      attempt: { number: 1, startedAt: timestamp(run.run_started_at) },
      completedAt,
      completionSource: completedAt ? "accepted-gates" : null,
      runStatus: run.status,
    } : null;
    deliveryChecks.set(delivery.pr, result);
    return result;
  });

  const verifiedDeliveries = [...deliveryChecks.values()].filter(Boolean);
  const activeFailure = verifiedActiveRun?.failureVerified ? {
    pr: state.active.pr,
    runId: verifiedActiveRun.run.id,
    attempt: verifiedActiveRun.attempt.number,
    url: verifiedActiveRun.url,
  } : null;
  const eventTargets = new Map();
  for (const delivery of verifiedDeliveries) {
    eventTargets.set(`${delivery.runId}:${delivery.attempt.number}`, {
      pr: delivery.pr, issue: null, runId: delivery.runId, attempt: delivery.attempt.number,
    });
  }
  if (activeFailure) eventTargets.set(`${activeFailure.runId}:${activeFailure.attempt}`, { ...activeFailure, issue: null });
  const issueNumbersByPr = new Map();
  for (const { identity } of timelineTargets) {
    const linked = linkedByIssue.get(identity.url);
    if (!linked?.complete) continue;
    for (const pr of linked.numbers) {
      const values = issueNumbersByPr.get(pr) ?? new Set();
      values.add(identity.number);
      issueNumbersByPr.set(pr, values);
    }
  }
  for (const target of eventTargets.values()) {
    const issues = issueNumbersByPr.get(target.pr);
    target.issue = issues?.size === 1 ? [...issues][0] : null;
  }
  const eventIds = new Map();
  await mapLimit([...eventTargets.values()].slice(0, MAX_EVENT_COMMENT_LOOKUPS), 3, async (target) => {
    try {
      let comments = await get(`repos/${REPOSITORY}/issues/${target.pr}/comments?per_page=100&page=1`);
      let eventId = eventIdFromComments(comments, target.runId, target.attempt);
      if (!eventId && target.issue) {
        comments = await get(`repos/${REPOSITORY}/issues/${target.issue}/comments?per_page=100&page=1`);
        eventId = eventIdFromComments(comments, target.runId, target.attempt);
      }
      if (eventId) eventIds.set(`${target.runId}:${target.attempt}`, eventId);
    } catch { /* An event locator is optional; a failed read never changes delivery evidence. */ }
    return null;
  });
  for (const delivery of verifiedDeliveries) {
    delivery.eventId = eventIds.get(`${delivery.runId}:${delivery.attempt.number}`) ?? null;
  }
  for (const record of queueRecords) {
    if (state?.active?.pr !== record.pr) continue;
    const run = verifiedActiveRun;
    if (!run || !(run.valid || run.identityVerified || run.failureVerified)) continue;
    record.runUrl = run.url;
    record.runStatus = run.run.status;
    record.attempt = run.attempt;
    record.completedAt = run.completedAt ?? null;
    if (run.completionSource) record.completionSource = run.completionSource;
    if (run.failureVerified) record.eventId = eventIds.get(`${run.run.id}:${run.attempt.number}`) ?? null;
  }
  const recentDeliveries = verifiedDeliveries.slice(-MAX_QUEUE_ENTRIES).map((delivery) => ({
    pr: delivery.pr,
    title: pulls.get(delivery.pr)?.title ?? null,
    runId: delivery.runId,
    runUrl: delivery.url,
    checkedAt: delivery.checkedAt,
    attempt: delivery.attempt,
    completedAt: delivery.completedAt ?? null,
    ...(delivery.completionSource ? { completionSource: delivery.completionSource } : {}),
    eventId: delivery.eventId,
  }));
  const runInventory = await validateRunInventory(get, workflowId);
  const verifiedActiveRunKey = (verifiedActiveRun?.valid || verifiedActiveRun?.identityVerified)
    && verifiedActiveRun.run.status !== "completed"
    ? `${verifiedActiveRun.run.id}:${verifiedActiveRun.attempt.number}` : null;
  const otherRuns = runInventory.runs.filter((run) => `${run.id}:${run.attempt.number}` !== verifiedActiveRunKey);
  const queueRunMissing = !state?.paused && ["validating", "smoke"].includes(state?.active?.phase)
    && !verifiedActiveRun?.run && otherRuns.length === 0;
  const slotUnknown = !runInventory.complete || runInventory.truncated || queueRunMissing;
  const queueSlotRun = verifiedActiveRunKey === null
    ? null : runInventory.runs.find((run) => `${run.id}:${run.attempt.number}` === verifiedActiveRunKey) ?? null;
  const otherSlotRun = otherRuns.find((run) => run.status === "in_progress") ?? otherRuns[0] ?? null;
  const queueSlotEntry = queueSlotRun && queueRecords.find((entry) => entry.pr === state?.active?.pr);
  const slot = slotUnknown ? { phase: "unknown" }
    : queueSlotRun ? {
      phase: "queue-active",
      url: queueSlotRun.url,
      runUrl: queueSlotRun.url,
      ...(queueSlotEntry?.verified ? {
        pr: queueSlotEntry.pr,
        head: queueSlotEntry.head,
        base: queueSlotEntry.base,
      } : {}),
    }
      : otherSlotRun ? {
        phase: "other-active",
        id: otherSlotRun.id,
        status: otherSlotRun.status,
        url: otherSlotRun.url,
        runUrl: otherSlotRun.url,
      }
        : { phase: "idle" };
  evidence.ciQueue.slot = slot;
  evidence.ciQueue.slotUnknown = slotUnknown;
  evidence.ciQueue.otherRuns = otherRuns;
  evidence.ciQueue.otherRunsTruncated = runInventory.truncated;
  if (state) {
    const waiting = queueRecords.filter((entry) => state.active?.pr !== entry.pr);
    const active = queueRecords.find((entry) => state.active?.pr === entry.pr) ?? null;
    const lastDelivery = [...(state.completed ?? [])].reverse()
      .map((entry) => deliveryChecks.get(entry.pr))
      .find(Boolean) ?? null;
    evidence.ciQueue = {
      ...evidence.ciQueue,
      state: state.paused ? "failed-paused"
        : evidence.ciQueue.lastError ? "unknown"
          : active ? verifiedActiveRun?.valid && verifiedActiveRun.run.status === "in_progress"
            ? active.phase === "smoke" ? "smoke-running" : "validating"
            : "waiting"
            : waiting.length ? "waiting" : "idle",
      paused: Boolean(state.paused),
      active: active ? { ...active, runUrl: verifiedActiveRun?.url ?? null,
        runStatus: verifiedActiveRun?.run?.status ?? null, attempt: verifiedActiveRun?.attempt ?? null } : null,
      waiting,
      ready: queueRecords.filter((entry) => entry.ready && entry.verified).length,
      delivered: verifiedDeliveries.length,
      lastDelivered: lastDelivery,
      recentDeliveries,
      snapshotAt,
      url: `https://github.com/${REPOSITORY}/issues/${QUEUE_CONTROL_ISSUE}`,
    };
  }

  const sessionByIssue = new Map();
  const pairableIssues = new Set();
  if (options.local === true) {
    const mappingPath = options.mappingPath;
    const installationIdPath = options.installationIdPath ?? defaultInstallationIdPath(mappingPath);
    try {
      const [mapping, installationId] = await Promise.all([
        loadLocalCodexSessionMap(mappingPath),
        readLocalInstallationId(installationIdPath),
      ]);
      for (const { identity } of identities) {
        const session = linksForIssue(identity.url, mapping, installationId);
        if (session.status === "verified-local"
            && matchesOwnerClaim(session.threadId, privateClaimByIssue.get(identity.url))) pairableIssues.add(identity.url);
        sessionByIssue.set(identity.url, {
          status: session.status,
          reason: session.reason,
          hasBrowser: typeof session.browserUrl === "string",
        });
      }
    } catch {
      for (const { identity } of identities) sessionByIssue.set(identity.url, {
        status: "invalid", reason: "Local Codex session evidence is unavailable or invalid.", hasBrowser: false,
      });
    }
  }

  let origins = [];
  if (options.local === true) {
    try { origins = await localOrigins(options.originDirectory); }
    catch { origins = []; }
  }

  for (const { item, identity } of identities) {
    const record = evidence.issues[identity.url];
    const linked = linkedByIssue.get(identity.url);
    if (linked && !linked.complete) {
      record.review = { state: "unknown", reason: "Linked PR history exceeded the verification bound." };
      record.ci = unknownCi("Linked PR history could not be read completely.");
    } else if (!linked) {
      record.review = { state: "unknown", reason: "Linked PR history could not be refreshed." };
      record.ci = unknownCi("Linked PR history could not be refreshed.");
    } else if (linked.numbers.length > 0) {
      const candidates = linked.numbers.map((number) => pulls.get(number)).filter(Boolean);
      const queued = candidates.filter((pull) => state?.entries.some((entry) => entry.pr === pull.number)
        || state?.completed.some((entry) => entry.pr === pull.number));
      const explicit = candidates.filter((pull) => {
        const issueRef = new RegExp(`(?:https://github\\.com/${identity.repository}/issues/${identity.number}\\b|(?:${identity.repository})?#${identity.number}(?![0-9]))`, "i");
        return issueRef.test(`${pull.title}\n${pull.body}`);
      });
      const open = candidates.filter((pull) => pull.state === "open" && !pull.draft);
      const allLinkedPullsVerified = candidates.length === linked.numbers.length;
      const explicitOpen = open.filter((pull) => explicit.some((candidate) => candidate.number === pull.number));
      const latestVerifiedDelivery = [...(state?.completed ?? [])].reverse()
        .find((delivery) => linked.numbers.includes(delivery.pr) && deliveryChecks.get(delivery.pr)) ?? null;
      const latestDeliveredPull = latestVerifiedDelivery
        ? candidates.find((pull) => pull.number === latestVerifiedDelivery.pr) ?? null : null;
      const selected = !allLinkedPullsVerified ? null
        : explicitOpen.length === 1 ? explicitOpen[0]
          : explicitOpen.length > 1 ? null
            : open.length === 1 ? open[0]
              : open.length > 1 ? null
                : latestDeliveredPull ?? (explicit.length === 1 ? explicit[0]
                  : queued.length === 1 ? queued[0]
                    : linked.numbers.length === 1 ? candidates[0] ?? null : null);
      if (!selected) {
        const reason = !allLinkedPullsVerified
          ? "One or more linked PRs could not be verified completely."
          : "More than one linked PR needs manual selection.";
        record.review = { state: "unknown", reason };
        record.ci = unknownCi(reason);
      } else {
        const number = selected.number;
        const pull = pulls.get(number);
        if (!pull) {
          record.review = { state: "unknown", reason: "The linked PR could not be verified." };
          record.ci = unknownCi("The linked PR could not be verified.");
        } else {
          record.pr = { url: pull.url, number, head: pull.head, base: pull.base };
          record.continuation = (pull.state === "open" || pull.merged)
            && Number.isFinite(Date.parse(pull.createdAt)) && Date.parse(pull.createdAt) <= CONTINUATION_CUTOFF
            && new RegExp(`^(?:codex|claude)/${identity.number}-`, "i").test(pull.headRef ?? "");
          record.review = { state: "unknown", reason: "Independent Claude CLI review evidence is not connected to a verifiable exact-head source.", url: pull.url };
          const entry = state && queueEntryByPr(state, number);
          const delivered = state && matchingCompleted(state, number);
          const queueRecord = queueRecords.find((candidate) => candidate.pr === number);
          if (delivered) {
            const verified = deliveryChecks.get(number);
            record.ci = verified
              ? { state: "delivered", reason: "Queue delivery and exact post-merge smoke were verified.",
                url: verified.url, runUrl: verified.url, runId: verified.runId, runStatus: verified.runStatus,
                checkedAt: verified.checkedAt, attempt: verified.attempt, completedAt: verified.completedAt ?? null,
                ...(verified.completionSource ? { completionSource: verified.completionSource } : {}),
                eventId: verified.eventId ?? null }
              : unknownCi("The saved delivery does not match the current PR and verified smoke run.");
          } else if (entry && state) {
            if (state.paused) {
              record.ci = { state: "failed-paused", reason: queueRecord?.verified
                ? "The CI queue is paused; its entries are retained."
                : "The CI queue is paused; this entry remains visible, but its PR head is unverified.",
                runId: activeFailure?.pr === number ? activeFailure.runId : null,
                runUrl: queueRecord?.runUrl ?? null, runStatus: queueRecord?.runStatus ?? null,
                checkedAt: snapshotAt, attempt: queueRecord?.attempt ?? null,
                completedAt: queueRecord?.completedAt ?? null, eventId: queueRecord?.eventId ?? null };
            } else if (!queueRecord?.verified) {
              record.ci = unknownCi("This queue entry does not match the current PR head or base.");
            } else if (state.active?.pr === number) {
              const run = verifiedActiveRun;
              if (state.active.phase === "integrating") {
                record.ci = { state: "waiting", reason: "The queue is integrating this exact PR head with current main before validation." };
              } else if (!run?.valid) {
                record.ci = unknownCi("The active CI run did not match the exact queued PR, head, base, and workflow.");
              } else if (state.active.phase === "smoke" && run.run.status === "in_progress") {
                record.ci = { state: "smoke-running", reason: run.assessment.kind === "passed"
                  ? "Smoke passed; the queue has not yet recorded delivery." : "Post-merge smoke is running.",
                  url: run.url, runUrl: run.url, runId: run.run.id, runStatus: run.run.status,
                  checkedAt: snapshotAt, attempt: run.attempt, completedAt: run.completedAt ?? null,
                  ...(run.completionSource ? { completionSource: run.completionSource } : {}) };
              } else if (state.active.phase === "validating" && !entry.ready && run.assessment.kind === "passed") {
                record.ci = { state: "validation-only", reason: "Preview validation passed without granting merge readiness.",
                  url: run.url, runUrl: run.url, runId: run.run.id, runStatus: run.run.status,
                  checkedAt: snapshotAt, attempt: run.attempt, completedAt: run.completedAt ?? null,
                  ...(run.completionSource ? { completionSource: run.completionSource } : {}) };
              } else if (run.run.status === "in_progress") {
                record.ci = { state: "validating", reason: run.assessment.kind === "passed"
                  ? "Validation passed; the controller has not recorded the next delivery step." : "The single CI slot is validating this exact PR head.",
                  url: run.url, runUrl: run.url, runId: run.run.id, runStatus: run.run.status,
                  checkedAt: snapshotAt, attempt: run.attempt, completedAt: run.completedAt ?? null,
                  ...(run.completionSource ? { completionSource: run.completionSource } : {}) };
              } else {
                record.ci = { state: "waiting", reason: "The exact run is not currently in progress; refresh for the queue's next recorded step.",
                  url: run.url, runUrl: run.url, runId: run.run.id, runStatus: run.run.status,
                  checkedAt: snapshotAt, attempt: run.attempt, completedAt: run.completedAt ?? null,
                  ...(run.completionSource ? { completionSource: run.completionSource } : {}) };
              }
            } else {
              record.ci = { state: "waiting", reason: entry.ready
                ? "This exact PR head is waiting for the single CI slot." : "Preview validation is waiting for the single CI slot." };
            }
          } else {
            record.ci = unknownCi("No verified CI queue entry or delivered run is linked to this PR.");
          }
        }
      }
    } else {
      record.review = { state: "unknown", reason: "No linked PR is available for exact-head review verification." };
      record.ci = unknownCi("No linked PR is available in the verified CI queue.");
    }
    record.session = sessionByIssue.get(identity.url) ?? {
      status: "missing", reason: options.local === true
        ? "No verified local Codex thread is linked." : "Local session links are available only from the live dashboard.",
      hasBrowser: false,
    };
    const ownerOrigin = options.local === true ? matchOrigin(origins, {
      repository: identity.repository,
      number: identity.number,
      claim: privateClaimByIssue.get(identity.url),
      pr: record.pr?.number ?? null,
    }) : null;
    record.codex = { ...record.codex, ownerBound: Boolean(ownerOrigin), canPair: pairableIssues.has(identity.url) };
    record.producerChecklist = ownerOrigin && item.acceptance === "Producer" && record.pr
      ? await readProducerChecklist({
        issueUrl: identity.url,
        revision: issueRevision(item.title, item.body),
        pr: { number: record.pr.number, head: record.pr.head },
        origin: ownerOrigin,
      })
      : null;
    const prLastError = !linked
      ? "Linked PR history could not be refreshed."
      : !linked.complete
        ? "Linked PR history is incomplete."
        : linked.numbers.length > 0 && !record.pr
          ? "Linked PR history could not be resolved to one verified PR."
          : null;
    record.sources = {
      project: {
        snapshotAt: item.snapshotAt ?? options.projectSnapshotAt ?? snapshotAt,
        lastError: item.projectLastError || options.projectLastError ? "Project evidence could not be refreshed." : null,
      },
      workflow: { snapshotAt: record.snapshotAt, lastError: record.lastError },
      chat: { snapshotAt, lastError: record.chat.state === "unknown" ? "Canonical Chat review could not be verified." : null },
      codex: { snapshotAt, lastError: record.codex.state === "unknown" && /could not be refreshed|history|marker/.test(record.codex.reason) ? "Issue claim evidence could not be verified." : null },
      review: { snapshotAt, lastError: null },
      pr: { snapshotAt, lastError: prLastError },
      ci: { snapshotAt: evidence.ciQueue.snapshotAt, lastError: evidence.ciQueue.lastError },
      session: { snapshotAt, lastError: null },
    };
  }
  return evidence;
}

function sourceFresh(source, now) {
  if (!source || source.lastError) return false;
  const value = typeof source.snapshotAt === "string" ? Date.parse(source.snapshotAt) : NaN;
  return Number.isFinite(value) && value <= now.getTime() && now.getTime() - value <= MAX_AGE_MS;
}

function chip(name, state, reason, requiresFresh = true) {
  const map = {
    approved: ["Approved", "ok"],
    done: ["Done", "na"],
    pending: ["Pending", "wait"],
    grandfathered: ["Grandfathered", "na"],
    claimed: ["Claimed", "active"],
    off: ["Off", "na"],
    excluded: ["Excluded", "na"],
    potential: ["Potential", "wait"],
    "route-to-chat": ["Via ChatGPT", "wait"],
    "awaiting-approval": ["Approval needed", "wait"],
    requested: ["Requested", "wait"],
    running: ["Running", "active"],
    candidate: ["Candidate", "wait"],
    verified: ["Verified", "ok"],
    changes: ["Changes", "attention"],
    "stale-head": ["Stale head", "blocked"],
    waiting: ["Waiting", "wait"],
    validating: ["Validating", "active"],
    "validation-only": ["Preview passed", "ok"],
    "smoke-running": ["Smoke", "active"],
    delivered: ["Delivered", "ok"],
    "failed-paused": ["Paused", "blocked"],
    unknown: ["Unknown", "unknown"],
  };
  const [label, tone] = map[state] ?? ["Unknown", "unknown"];
  return { name, state, label, tone, detail: reason, requiresFresh };
}

/** Pure next-action derivation. It performs no reads and never authorizes a launch. */
export function deriveWorkflow(item, evidence, nowValue = new Date(0)) {
  const now = clockValue(nowValue);
  const identity = repoForIssue(item?.url);
  const key = identity?.url ?? item?.url;
  const wholeEvidence = evidence?.issues && evidence?.ciQueue ? evidence : null;
  const record = wholeEvidence
    ? wholeEvidence.issues[key] ?? wholeEvidence.issues[item?.url] ?? null
    : evidence ?? null;
  const projectEnvelope = wholeEvidence?.project ?? {};
  const rawProjectSource = record?.sources?.project ?? {
    snapshotAt: item?.snapshotAt ?? projectEnvelope.snapshotAt ?? wholeEvidence?.snapshotAt ?? record?.snapshotAt,
    lastError: item?.projectLastError ?? projectEnvelope.lastError ?? null,
  };
  const rawWorkflowSource = record?.sources?.workflow ?? { snapshotAt: record?.snapshotAt, lastError: record?.lastError ?? null };
  const rawChatSource = record?.sources?.chat ?? rawWorkflowSource;
  const rawCodexSource = record?.sources?.codex ?? rawWorkflowSource;
  const rawPrSource = record?.sources?.pr ?? rawWorkflowSource;
  const rawReviewSource = record?.sources?.review ?? rawPrSource;
  const rawSessionSource = record?.sources?.session ?? rawWorkflowSource;
  const rawQueueSource = record?.sources?.ci ?? {
    snapshotAt: wholeEvidence?.ciQueue?.snapshotAt,
    lastError: wholeEvidence?.ciQueue?.lastError ?? null,
  };
  const safeSource = (source, name) => ({
    snapshotAt: source?.snapshotAt,
    lastError: source?.lastError ? `${name} source could not be verified.` : null,
  });
  const projectSource = safeSource(rawProjectSource, "Project");
  const workflowSource = safeSource(rawWorkflowSource, "Workflow");
  const chatSource = safeSource(rawChatSource, "Chat");
  const codexSource = safeSource(rawCodexSource, "Claim");
  const prSource = safeSource(rawPrSource, "PR history");
  const reviewSource = safeSource(rawReviewSource, "Review");
  const sessionSource = safeSource(rawSessionSource, "Local session");
  const queueSource = safeSource(rawQueueSource, "CI queue");
  const projectFresh = Boolean(now && sourceFresh(projectSource, now));
  const workflowFresh = Boolean(now && sourceFresh(workflowSource, now));
  const chatFresh = Boolean(now && workflowFresh && sourceFresh(chatSource, now));
  const codexFresh = Boolean(now && workflowFresh && sourceFresh(codexSource, now));
  const prFresh = Boolean(now && workflowFresh && sourceFresh(prSource, now));
  const reviewFresh = Boolean(now && prFresh && sourceFresh(reviewSource, now));
  const sessionFresh = Boolean(now && projectFresh && workflowFresh && sourceFresh(sessionSource, now));
  const queueFresh = Boolean(now && sourceFresh(queueSource, now));
  const ciFresh = Boolean(queueFresh && prFresh);
  const chat = chatFresh ? record?.chat ?? { state: "unknown", reason: "Chat review evidence is unavailable." }
    : { state: "unknown", reason: "Workflow evidence is stale or failed; refresh before relying on it." };
  const codex = codexFresh ? record?.codex ?? { state: "unknown", reason: "No claim evidence is available." }
    : { state: "unknown", reason: "Workflow evidence is stale or failed; refresh before relying on it." };
  const deepseek = projectFresh && record?.deepseek ? record.deepseek
    : { state: "unknown", reason: "Current DeepSeek routing evidence could not be verified." };
  const review = reviewFresh ? record?.review ?? { state: "unknown", reason: "Review evidence is unavailable." }
    : { state: "unknown", reason: "Workflow evidence is stale or failed; refresh before relying on it." };
  const ci = ciFresh ? record?.ci ?? { state: "unknown", reason: "CI evidence is unavailable." }
    : { state: "unknown", reason: "CI queue evidence is stale or unavailable." };
  const session = sessionFresh ? record?.session ?? { status: "missing", reason: "No verified local session is linked.", hasBrowser: false }
    : { status: "unknown", reason: "Session evidence is stale or unavailable.", hasBrowser: false };
  const acceptance = record?.acceptance ?? { state: "unknown", reason: "Producer acceptance is recorded separately after delivery." };
  const links = [];
  if (identity) links.push({ label: "Issue", url: identity.url });
  if (prFresh && record?.pr && safePullUrl(record.pr.url, record.pr.number, identity?.repository)) {
    links.push({ label: "PR", url: record.pr.url });
  }
  if (chatFresh && chat.state === "approved" && identity && safeIssueCommentUrl(chat.url, identity, Number(chat.url?.match(/#issuecomment-(\d+)$/)?.[1]))) {
    links.push({ label: "Verified Chat review", url: chat.url });
  }
  if (ciFresh && ci.url && identity && safeRunUrl(ci.url, Number(ci.url.match(/\/actions\/runs\/(\d+)$/)?.[1]))) {
    links.push({ label: "CI run", url: ci.url });
  }
  const existingWork = ["Ready", "In progress", "In review"].includes(item?.status)
    && ((codex.state === "claimed" && Number.isFinite(Date.parse(codex.startedAt))
      && Date.parse(codex.startedAt) <= CONTINUATION_CUTOFF)
      || (prFresh && record?.continuation === true && record?.pr && safePullUrl(record.pr.url, record.pr.number, identity?.repository)));
  const chips = [
    existingWork && chat.state !== "approved"
      ? chip("Chat", "grandfathered", "Work has already started; continuing it does not require a new Chat review.")
      : chip("Chat", chat.state, chat.reason),
    chip("DeepSeek", deepseek.state, deepseek.reason),
    chip("Codex", codex.state, codex.reason),
    chip("Review", review.state, review.reason),
    chip("CI", ci.state, ci.reason),
  ];
  const primaryAction = derivePrimaryAction(item, { chat, codex, deepseek, ci, links, chips }, {
    projectFresh, workflowFresh, chatFresh, codexFresh, prFresh, ciFresh,
    ownerBound: sessionFresh && record?.codex?.ownerBound === true,
    canPair: sessionFresh && record?.codex?.canPair === true,
    activeTurnFresh: false,
    eventId: ciFresh ? record?.ci?.eventId : undefined,
    hasProducerChecklist: sessionFresh && Boolean(record?.producerChecklist),
  });
  if (primaryAction.kind === "start-codex") primaryAction.approvalUrl = chat.url;
  const producerChecklist = primaryAction.kind === "review-producer" ? record.producerChecklist : null;
  if (producerChecklist) primaryAction.checklistDigest = producerChecklist.digest;
  if (prFresh && record?.pr) primaryAction.pr = record.pr.number;
  return {
    primaryAction,
    pr: prFresh && record?.pr ? { number: record.pr.number } : null,
    producerChecklist: producerChecklist ? { url: producerChecklist.url, steps: producerChecklist.steps } : null,
    group: primaryAction.group,
    actor: primaryAction.actor,
    action: primaryAction.reason,
    filter: primaryAction.filter,
    chips,
    links,
    sources: [
      { name: "Project", ...projectSource },
      { name: "Chat", ...chatSource },
      { name: "Claim", ...codexSource },
      { name: "PR history", ...prSource },
      { name: "Review", ...reviewSource },
      { name: "CI queue", ...queueSource },
      { name: "Local session", ...sessionSource },
    ],
    chat,
    codex,
    deepseek,
    review,
    ci,
    session: { ...session, hasBrowser: session.hasBrowser === true },
    acceptance,
  };
}

export const WORKFLOW_FRESHNESS_MS = MAX_AGE_MS;
