import { execFile } from "node:child_process";
import { promisify, TextDecoder } from "node:util";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";
import { Worker } from "node:worker_threads";
import { URL } from "node:url";
import { clearTimeout, setTimeout as setTimer } from "node:timers";

import { verifyReviewFromGh } from "./chat-review-github.mjs";
import { REPOS } from "./chat-review-current.mjs";
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
    && /^repos\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/(?:contents\/queue\.json\?ref=vera-ci-queue-state|issues\/[1-9][0-9]*(?:\/timeline\?per_page=100|\/comments\?per_page=100(?:&page=[1-9][0-9]*)?)?|pulls\/[1-9][0-9]*(?:\/reviews\?per_page=100)?|actions\/workflows\/validate\.yml(?:\/runs\?[^#]+)?|actions\/runs\/[1-9][0-9]*(?:\/attempts\/[1-9][0-9]*\/jobs\?per_page=100&page=1)?|git\/ref\/heads\/main)$/.test(value)
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

function chatPromptLink(issueUrl) {
  const prompt = `Review the exact current issue and the sources it links to. Check whether the scope, evidence, dependencies, and acceptance criteria are clear. Report useful findings, then wait for the Producer's decision. Do not record or imply Producer approval, and do not change external state. Issue: ${issueUrl}`;
  return { label: "Open Chat review prompt", url: "https://chatgpt.com/", prompt };
}

function blankIssueRecord(snapshotAt, lastError = null) {
  return {
    snapshotAt,
    lastError,
    chat: { state: "unknown", reason: "Current Chat review evidence is unavailable." },
    codex: { state: "unknown", reason: "No independently verified issue claim is connected." },
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

function deepseekForIssue(item) {
  const labels = labelsForStatus(issueLabelNames(item));
  const excluded = ["deepseek-excluded", "owner:codex", "owner:claude", "type:security",
    "type:design", "type:ux", "type:research", "type:product", "execution:codex", "execution:design", "execution:human"];
  const types = [...labels].filter((label) => label.startsWith("type:"));
  if (excluded.some((label) => labels.has(label))
    || (types.length > 0 && (types.length !== 1 || !["type:implementation", "type:bug"].includes(types[0])))) {
    return { state: "excluded", reason: "Issue routing excludes this work from DeepSeek." };
  }
  if (labels.has("deepseek-eligible") || labels.has("deepseek-ready") || labels.has("deepseek-dispatch")) {
    return { state: "potential", reason: "This issue is marked as a DeepSeek candidate, but the global route is off and no job is authorized." };
  }
  return { state: "off", reason: "DeepSeek execution is not connected or authorized." };
}

async function claimForIssue(item, issue, get) {
  const current = await get(`repos/${issue.repository}/issues/${issue.number}`);
  if (current?.number !== issue.number || current.html_url !== issue.url
      || current.repository_url !== `https://api.github.com/repos/${issue.repository}`
      || current.state !== "open" || current.title !== item.title || current.body !== item.body
      || !Number.isSafeInteger(current.comments) || current.comments < 0 || current.comments > 10_000) {
    return { state: "unknown", reason: "Current issue claim history could not be matched to the Project snapshot." };
  }
  if (current.comments === 0) return { state: "unknown", reason: "No active issue claim was found." };
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
    return { state: "claimed", reason: "A current roadmap claim exists; this does not verify that an agent is running." };
  }
  if (page > 1 && !trustedComments.some((comment) => /<!--\s*vera-claim\s+\{/.test(comment.body))) {
    return { state: "unknown", reason: "The latest comment page has no claim marker; older claim history is not inferred." };
  }
  return { state: "unknown", reason: "No active issue claim was found." };
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

function queueEnvelope(snapshotAt, lastError = null) {
  return {
    snapshotAt,
    lastError,
    state: "unknown",
    slot: null,
    paused: false,
    active: null,
    waiting: [],
    ready: 0,
    delivered: 0,
    lastDelivered: null,
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
  };
  const rows = Array.isArray(items) ? items : [];
  const identities = rows.map((item) => ({ item, identity: repoForIssue(item?.url) }))
    .filter(({ item, identity }) => identity && identity.number === item.number);
  for (const { item, identity } of identities) {
    const record = blankIssueRecord(snapshotAt);
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
  const plannedReads = 720 + 42 * Math.min(chatTargets.length, 100);

  try {
    const limit = await get("rate_limit");
    const remaining = limit?.resources?.core?.remaining;
    if (!Number.isSafeInteger(remaining) || remaining < plannedReads) {
      throw new Error("rate_budget");
    }
  } catch {
    evidence.lastError = "GitHub read budget could not be verified; workflow sources remain unknown.";
    evidence.ciQueue.lastError = evidence.lastError;
    for (const record of Object.values(evidence.issues)) record.lastError = evidence.lastError;
    return evidence;
  }

  const chatResults = await mapLimit(chatTargets.slice(0, 100), 2, async ({ item, identity }) => {
    const record = evidence.issues[identity.url];
    record.chat = readGh
      ? chatForIssue(item, readGh)
      : await chatForIssueInWorker(item, repositoryRoot, options.ghExecutable ?? "gh");
    return record.chat;
  });
  for (let index = 0; index < chatTargets.length; index += 1) {
    if (index >= 100) {
      const { identity } = chatTargets[index];
      evidence.issues[identity.url].chat = { state: "unknown", reason: "Current Chat review verification exceeded the refresh bound." };
    } else if (!chatResults[index]) {
      const { identity } = chatTargets[index];
      evidence.issues[identity.url].chat = { state: "unknown", reason: "Canonical Chat review could not be refreshed." };
    }
  }

  const claimResults = await mapLimit(claimTargets, 4, async ({ item, identity }) => {
    const claim = await claimForIssue(item, identity, get);
    evidence.issues[identity.url].codex = claim;
    return claim;
  });
  for (const { item, identity } of identities) evidence.issues[identity.url].deepseek = deepseekForIssue(item);
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
    if (linked?.complete && linked.numbers.length === 1) prNumbers.add(linked.numbers[0]);
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
  let mainSha = null;
  if (state) {
    try {
      const responses = await Promise.all([
        get(`repos/${REPOSITORY}/git/ref/heads/main`),
        workflowNeeded ? get(`repos/${REPOSITORY}/actions/workflows/validate.yml`) : Promise.resolve(null),
      ]);
      mainSha = validSha(responses[0]?.object?.sha) ? responses[0].object.sha.toLowerCase() : null;
      workflow = responses[1];
      if (!mainSha || (workflowNeeded && (!Number.isSafeInteger(workflow?.id)
        || workflow.path !== ".github/workflows/validate.yml" || workflow.state !== "active"))) {
        throw new Error("queue_identity");
      }
    } catch {
      evidence.ciQueue.lastError ??= "Current main or the queue workflow identity could not be verified.";
    }
  }

  const queueRecords = [];
  const verificationFailures = new Set();

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
      if (!verified) verificationFailures.add(entry.pr);
      queueRecords.push({
        pr: entry.pr,
        phase: isActive ? state.active.phase : "waiting",
        head: pull?.head ?? entry.head.toLowerCase(),
        base: pull?.base ?? (isActive ? state.active.base?.toLowerCase() ?? null : null),
        ready: entry.ready,
        verified,
        url: pull?.url ?? null,
        runUrl: null,
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
    const assessment = assessRun(expected, matches, now.getTime());
    if (assessment.kind === "pause") return { run, expected, assessment, valid: false };
    const url = safeRunUrl(assessment.url, assessment.runId, REPOSITORY);
    if (!url) return null;
    if (assessment.kind === "passed") {
      const jobs = await get(`repos/${REPOSITORY}/actions/runs/${run.id}/attempts/${run.run_attempt}/jobs?per_page=100&page=1`);
      if (!verifyJobSet(jobs?.jobs, run.id, run.run_attempt, expected.mode, false)) return null;
    }
    return { run, expected, assessment, valid: true, url };
  }

  let verifiedActiveRun = null;
  if (state?.active && ["validating", "merging", "smoke"].includes(state.active.phase)) {
    try { verifiedActiveRun = await activeRun(state.active); }
    catch { evidence.ciQueue.lastError ??= "The active queue run could not be verified."; }
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
    const result = passed ? {
      pr: delivery.pr,
      head: validSha(delivery.candidate) ? delivery.candidate.toLowerCase() : null,
      base: delivery.mergeSha.toLowerCase(),
      runId: delivery.runId,
      url: runUrl,
    } : null;
    deliveryChecks.set(delivery.pr, result);
    return result;
  });

  const verifiedDeliveries = [...deliveryChecks.values()].filter(Boolean);
  if (state) {
    const waiting = queueRecords.filter((entry) => state.active?.pr !== entry.pr);
    const active = queueRecords.find((entry) => state.active?.pr === entry.pr) ?? null;
    const lastDelivery = [...(state.completed ?? [])].reverse()
      .map((entry) => deliveryChecks.get(entry.pr))
      .find(Boolean) ?? null;
    evidence.ciQueue = {
      ...evidence.ciQueue,
      state: evidence.ciQueue.lastError ? "unknown"
        : state.paused ? "failed-paused"
          : active ? active.phase === "smoke" ? "smoke-running" : active.phase === "integrating" ? "waiting" : "validating"
            : waiting.length ? "waiting" : "idle",
      slot: active ? { pr: active.pr, phase: active.phase, head: active.head, base: active.base, url: active.url, runUrl: verifiedActiveRun?.valid ? verifiedActiveRun.url : null } : null,
      paused: Boolean(state.paused),
      active: active ? { ...active, runUrl: verifiedActiveRun?.valid ? verifiedActiveRun.url : null } : null,
      waiting,
      ready: queueRecords.filter((entry) => entry.ready && entry.verified).length,
      delivered: verifiedDeliveries.length,
      lastDelivered: lastDelivery,
      snapshotAt,
      url: `https://github.com/${REPOSITORY}/issues/${QUEUE_CONTROL_ISSUE}`,
    };
    if (!evidence.ciQueue.lastError && queueRecords.some((entry) => !entry.verified)) {
      evidence.ciQueue.lastError = "Some queue PR heads or bases no longer match saved queue evidence.";
      evidence.ciQueue.state = "unknown";
    }
  }

  const sessionByIssue = new Map();
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
      const selected = queued.length === 1 ? queued[0]
        : queued.length > 1 ? null
          : !allLinkedPullsVerified ? null
            : explicit.length === 1 ? explicit[0]
            : explicit.length > 1 ? null
              : open.length === 1 ? open[0]
                : linked.numbers.length === 1 ? candidates[0] ?? null : null;
      if (!selected) {
        record.review = { state: "unknown", reason: "More than one linked PR needs manual selection." };
        record.ci = unknownCi("More than one linked PR needs manual selection.");
      } else {
        const number = selected.number;
        const pull = pulls.get(number);
        if (!pull) {
          record.review = { state: "unknown", reason: "The linked PR could not be verified." };
          record.ci = unknownCi("The linked PR could not be verified.");
        } else {
          record.pr = { url: pull.url, number, head: pull.head, base: pull.base };
          record.review = { state: "unknown", reason: "Independent Claude CLI review evidence is not connected to a verifiable exact-head source.", url: pull.url };
          const entry = state && queueEntryByPr(state, number);
          const delivered = state && matchingCompleted(state, number);
          const queueRecord = queueRecords.find((candidate) => candidate.pr === number);
          if (delivered) {
            const verified = deliveryChecks.get(number);
            record.ci = verified
              ? { state: "delivered", reason: "Queue delivery and exact post-merge smoke were verified.", url: verified.url }
              : unknownCi("The saved delivery does not match the current PR and verified smoke run.");
          } else if (entry && queueRecord?.verified && state) {
            if (state.paused) {
              record.ci = { state: "failed-paused", reason: "The CI queue is paused; its entries are retained." };
            } else if (state.active?.pr === number) {
            const run = verifiedActiveRun;
            if (state.active.phase === "integrating") {
              record.ci = { state: "waiting", reason: "The queue is integrating this exact PR head with current main before validation." };
            } else if (!run?.valid) {
                record.ci = unknownCi("The active CI run did not match the exact queued PR, head, base, and workflow.");
              } else if (state.active.phase === "smoke") {
                record.ci = { state: "smoke-running", reason: run.assessment.kind === "passed"
                  ? "Smoke passed; the queue has not yet recorded delivery." : "Post-merge smoke is running.", url: run.url };
              } else if (state.active.phase === "validating" && !entry.ready && run.assessment.kind === "passed") {
                record.ci = { state: "validation-only", reason: "Preview validation passed without granting merge readiness.", url: run.url };
              } else {
                record.ci = { state: "validating", reason: run.assessment.kind === "passed"
                  ? "Validation passed; the controller has not recorded the next delivery step." : "The single CI slot is validating this exact PR head.", url: run.url };
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
    record.sources = {
      project: {
        snapshotAt: item.snapshotAt ?? options.projectSnapshotAt ?? snapshotAt,
        lastError: item.projectLastError || options.projectLastError ? "Project evidence could not be refreshed." : null,
      },
      workflow: { snapshotAt: record.snapshotAt, lastError: record.lastError },
      chat: { snapshotAt, lastError: record.chat.state === "unknown" ? "Canonical Chat review could not be verified." : null },
      codex: { snapshotAt, lastError: record.codex.state === "unknown" && /could not be refreshed|history|marker/.test(record.codex.reason) ? "Issue claim evidence could not be verified." : null },
      review: { snapshotAt, lastError: null },
      pr: { snapshotAt, lastError: linked?.complete === false ? "Linked PR history is incomplete." : null },
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
    claimed: ["Claimed", "active"],
    off: ["Off", "na"],
    excluded: ["Excluded", "na"],
    potential: ["Potential", "wait"],
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

function acceptanceActor(owner) {
  return ["Producer", "External", "Automated"].includes(owner) ? owner : "You";
}

function acceptanceAction(owner) {
  if (owner === "Producer") return "Review verified delivery evidence and record Producer acceptance.";
  if (owner === "External") return "Complete the required external acceptance check on the delivered change.";
  if (owner === "Automated") return "Confirm the merged change and required smoke evidence.";
  return "Confirm who owns acceptance, then review the delivered change.";
}

function dependenciesBlock(item) {
  if (item.dependenciesVerified !== true) return "Dependencies have not been verified from both issue sources.";
  if (!Array.isArray(item.dependencies)) return "Dependency evidence is incomplete.";
  if (item.dependencies.some((dependency) => dependency?.invalid === true || dependency?.isOpen === true)) {
    return "One or more verified dependencies remain open or invalid.";
  }
  return null;
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
  const deepseek = projectFresh ? deepseekForIssue(item) : { state: "off", reason: "DeepSeek candidate labels are stale; the global route remains off." };
  const review = reviewFresh ? record?.review ?? { state: "unknown", reason: "Review evidence is unavailable." }
    : { state: "unknown", reason: "Workflow evidence is stale or failed; refresh before relying on it." };
  const ci = ciFresh ? record?.ci ?? { state: "unknown", reason: "CI evidence is unavailable." }
    : { state: "unknown", reason: "CI queue evidence is stale or unavailable." };
  const session = sessionFresh ? record?.session ?? { status: "missing", reason: "No verified local session is linked.", hasBrowser: false }
    : { status: "unknown", reason: "Session evidence is stale or unavailable.", hasBrowser: false };
  const acceptance = record?.acceptance ?? { state: "unknown", reason: "Producer acceptance is recorded separately after delivery." };
  const links = [];
  if (identity) links.push({ label: "Issue", url: identity.url });
  if (prFresh && record?.pr && safePullUrl(record.pr.url, record.pr.number)) {
    links.push({ label: "PR", url: record.pr.url });
  }
  if (chatFresh && chat.state === "approved" && identity && safeIssueCommentUrl(chat.url, identity, Number(chat.url?.match(/#issuecomment-(\d+)$/)?.[1]))) {
    links.push({ label: "Verified Chat review", url: chat.url });
  }
  if (ciFresh && ci.url && identity && safeRunUrl(ci.url, Number(ci.url.match(/\/actions\/runs\/(\d+)$/)?.[1]))) {
    links.push({ label: "CI run", url: ci.url });
  }
  const chips = [
    chip("Chat", chat.state, chat.reason),
    chip("DeepSeek", deepseek.state, deepseek.reason),
    chip("Codex", codex.state, codex.reason),
    chip("Review", review.state, review.reason),
    chip("CI", ci.state, ci.reason),
  ];
  const disabled = [];
  const depProblem = dependenciesBlock(item ?? {});
  let group;
  let actor;
  let action;
  let filter;
  const status = item?.status;

  if (!now || !identity || !projectFresh || item?.evidenceConflict === true) {
    group = "stuck";
    actor = !now || !identity || !projectFresh ? "Unknown" : "You";
    action = !projectFresh ? "Refresh Project evidence before acting." : "Resolve conflicting roadmap evidence before acting.";
    filter = "blocked";
    disabled.push("Actions are disabled until current, consistent Project evidence is available.");
  } else if (identity.repository === REPOSITORY && identity.number === QUEUE_CONTROL_ISSUE) {
    group = "working";
    actor = "CI";
    action = "This issue controls the CI queue; use its documented status and owner commands.";
    filter = "working";
    disabled.push("Queue controls remain on issue #361; this dashboard does not submit or resume queue work.");
  } else if (status === "Done") {
    group = "done";
    actor = acceptanceActor(item.acceptance);
    action = "The Project marks this Done; this source does not prove a separate acceptance record.";
    filter = "done";
  } else if (depProblem) {
    group = "stuck";
    actor = "You";
    action = depProblem;
    filter = "blocked";
    disabled.push(depProblem);
  } else if (status === "Blocked") {
    group = "stuck";
    actor = "You";
    action = "Resolve the recorded blocker before starting work.";
    filter = "blocked";
  } else if (!workflowFresh && status === "Ready") {
    group = "stuck";
    actor = "Unknown";
    action = "Refresh Chat, PR, CI, and session evidence before choosing a next step.";
    filter = "blocked";
    disabled.push("Workflow-dependent actions are disabled while their source is stale or unavailable.");
  } else if (["Ready", "In review", "In progress"].includes(status) && ciFresh && record?.pr
      && safePullUrl(record.pr.url, record.pr.number)
      && ["waiting", "validating", "smoke-running"].includes(ci.state)) {
    group = "working";
    actor = "CI";
    action = ci.state === "waiting" ? "The verified PR is waiting for the CI queue."
      : ci.state === "validating" ? "CI is validating the verified PR head."
        : "CI is running post-merge smoke; delivery is not recorded yet.";
    filter = "working";
    disabled.push("Acceptance remains unavailable until queue delivery and post-merge smoke are verified.");
  } else if (["Ready", "In review", "In progress"].includes(status) && ciFresh && ci.state === "failed-paused") {
    group = "stuck";
    actor = "You";
    action = "Resolve the paused CI queue on its control issue before acceptance.";
    filter = "blocked";
    disabled.push("The paused queue has not delivered this PR.");
  } else if (status === "Ready") {
    if (chat.state === "pending") {
      group = "you";
      const labels = issueLabelNames(item);
      const kind = labels.find((label) => label.startsWith("type:"))?.slice(5);
      const researchGap = (item.body ?? "").match(/^\s*#{1,4}\s*(?:Research question|Research gap|Open questions?)\s*\r?\n([\s\S]*?)(?=\n#{1,4}\s|$)/im)?.[1] ?? "";
      const hasResearchGap = researchGap.replace(/[\s#*`-]/g, "").length >= 40;
      const chatWork = ["investigation", "research", "design"].includes(kind) && hasResearchGap;
      actor = chatWork ? "Chat" : "Producer";
      action = chatWork ? "Review this bounded research question in Chat." : "Complete Producer Chat approval for this exact issue revision.";
      filter = chatWork ? "chat" : "approval";
      if (identity) links.push(chatPromptLink(identity.url));
      disabled.push("Codex and DeepSeek launches are not available from this dashboard.");
    } else if (chat.state !== "approved") {
      group = "stuck";
      actor = "Unknown";
      action = "Verify the current Producer Chat review.";
      filter = "blocked";
      disabled.push("The current Chat review could not be verified.");
    } else if (!prFresh || (record?.pr && !ciFresh)) {
      group = "stuck";
      actor = "Unknown";
      action = "Refresh PR and CI evidence before choosing a next step.";
      filter = "blocked";
      disabled.push("PR and CI sources are stale or unavailable.");
    } else if (record?.pr && ci.state === "unknown") {
      group = "stuck";
      actor = "Unknown";
      action = "Verify exact PR and CI queue evidence before choosing a next step.";
      filter = "blocked";
      disabled.push("The linked PR has no verified CI queue state.");
    } else if (record?.pr && review.state === "unknown") {
      group = "you";
      actor = "You";
      action = "Verify the independent review for the current PR head.";
      filter = "approval";
      disabled.push("The dashboard has no canonical exact-head Claude review receipt.");
    } else if (!record?.pr && deepseek.state === "potential" && codex.state !== "claimed") {
      group = "you";
      actor = "Producer";
      action = "DeepSeek is a potential route; dispatch is off. Choose a separately authorized manual route.";
      filter = "deepseek";
      disabled.push("DeepSeek eligibility does not authorize a job or a Codex launch; dashboard execution is disabled.");
    } else {
      group = "launch";
      actor = "Codex";
      action = session.status === "verified-local"
        ? "Open the linked existing Codex thread; it will not start a turn."
        : "Open the approved issue and choose a manual start route.";
      filter = "codex";
      disabled.push("Starting Codex or DeepSeek work from the dashboard is not implemented.");
    }
  } else if (status === "In review") {
    if (ci.state === "delivered" && ciFresh) {
      group = "you";
      actor = acceptanceActor(item.acceptance);
      action = acceptanceAction(item.acceptance);
      filter = "approval";
    } else {
      group = "stuck";
      actor = ci.state === "failed-paused" ? "You" : "Unknown";
      action = ci.state === "failed-paused"
        ? "Resolve the paused CI queue on its control issue before acceptance."
        : "Refresh and verify CI delivery and post-merge smoke before recording acceptance.";
      filter = "blocked";
      disabled.push("Validation alone does not establish delivery or Producer acceptance.");
    }
  } else if (status === "In progress") {
    group = "working";
    actor = codex.state === "claimed" ? "Codex" : "Unknown";
    action = "The roadmap says work is in progress; agent activity is not verified.";
    filter = "working";
    if (codex.state !== "claimed") disabled.push("No verified issue claim is available; this status does not prove an agent is running.");
  } else {
    group = "you";
    actor = "You";
    action = "Triage or refine this issue before it is ready to start.";
    filter = "approval";
  }

  if (record?.pr && ciFresh && ci.state === "unknown") disabled.push("CI delivery actions are disabled until exact PR, head, base, and run evidence is verified.");
  if (session.status !== "verified-local" && status === "Ready" && chat.state === "approved") {
    disabled.push("No verified existing local Codex thread is linked.");
  }
  return {
    group,
    actor,
    action,
    filter,
    chips,
    links,
    disabled,
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
