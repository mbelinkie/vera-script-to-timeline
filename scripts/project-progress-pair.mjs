#!/usr/bin/env node

import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { lstat, mkdir, open, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { issueRevision, REPOS } from "./chat-review-current.mjs";
import { publicOwnerKey } from "./ci-notification-origin.mjs";
import { latestClaim } from "./roadmap.mjs";

const exec = promisify(execFile);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const ACTION_HOME = path.join(os.homedir(), "Library", "Application Support", "VERA", "dashboard-actions");
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const PREVIEW_START = Date.parse("2026-11-03T18:03:10.174Z");
const MAX_RECORDS = 2000;
const MAX_JSON = 8 * 1024 * 1024;
const execGh = (args) => exec("gh", ["api", ...args], { cwd: ROOT, timeout: 30_000, maxBuffer: MAX_JSON, encoding: "utf8" });

function issueIdentity(issueUrl) {
  const match = /^https:\/\/github\.com\/([^/]+\/[^/]+)\/issues\/([1-9]\d*)$/.exec(issueUrl ?? "");
  if (!match || !REPOS.has(match[1]) || !Number.isSafeInteger(Number(match[2]))) throw new Error("Canonical VERA issue URL required");
  return { repository: match[1], number: Number(match[2]), url: issueUrl };
}

function privateInfo(info, directory) {
  if (!info.isDirectory() || info.isSymbolicLink() || info.uid !== process.getuid() || (info.mode & 0o077) !== 0) {
    throw new Error(`${directory} must be an owner-only directory`);
  }
}

async function existingPrivateDirectory(directory) {
  const info = await lstat(directory);
  privateInfo(info, directory);
  return directory;
}

async function createPrivateDirectory(directory) {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  return existingPrivateDirectory(directory);
}

async function privateJson(filename) {
  const info = await lstat(filename);
  if (!info.isFile() || info.isSymbolicLink() || info.uid !== process.getuid() || (info.mode & 0o077) !== 0 || info.size > 8192) {
    throw new Error("Dashboard pairing metadata is not private");
  }
  return JSON.parse(await readFile(filename, "utf8"));
}

function currentClaim(comments) {
  if (!Array.isArray(comments) || comments.length > MAX_RECORDS) throw new Error("Claim history exceeds its read limit");
  let previousId = 0;
  for (const comment of comments) {
    if (!Number.isSafeInteger(comment?.id) || comment.id <= previousId || typeof comment.body !== "string") {
      throw new Error("Claim history is incomplete or invalid");
    }
    previousId = comment.id;
  }
  const trusted = comments.filter(comment => comment.user?.login === "mbelinkie"
    && comment.performed_via_github_app === null
    && typeof comment.created_at === "string" && comment.created_at === comment.updated_at
    && Number.isFinite(Date.parse(comment.created_at)));
  if (comments.some(comment => /<!--\s*vera-claim\b/.test(comment.body) && !trusted.includes(comment))) {
    throw new Error("Claim provenance is not trustworthy");
  }
  for (const comment of trusted) {
    const markers = [...comment.body.matchAll(/<!--\s*vera-claim\b/g)].length;
    const parsed = [...comment.body.matchAll(/<!--\s*vera-claim\s+\{.+?\}\s*-->/g)].length;
    if (markers !== parsed || markers && latestClaim([comment]) === undefined) throw new Error("Claim marker is invalid");
  }
  return latestClaim(trusted);
}

function legacyOwnerClaim(threadId, claim) {
  const startedAt = Date.parse(claim?.startedAt);
  return UUID.test(threadId) && claim?.state === "active" && Number.isFinite(startedAt) && startedAt < PREVIEW_START
    && typeof claim.task === "string" && [threadId, publicOwnerKey(threadId)].includes(claim.task)
    && typeof claim.branch === "string" && claim.branch.length > 0 && claim.branch.length <= 255
    && typeof claim.model === "string" && typeof claim.effort === "string";
}

function validStoredPair(pair, issueUrlHash, claim) {
  return pair?.version === 1 && pair.purpose === "dashboard-continuation"
    && pair.issueUrlHash === issueUrlHash && UUID.test(pair.threadId ?? "")
    && pair.claimTask === claim.task && pair.claimBranch === claim.branch && pair.claimStartedAt === claim.startedAt
    && SHA256.test(pair.request ?? "") && Number.isFinite(Date.parse(pair.observedAt));
}

async function pendingIntent(intentsDirectory, request, threadId, issue) {
  await existingPrivateDirectory(intentsDirectory);
  const expectedKey = createHash("sha256").update(JSON.stringify([
    issue.html_url, "pair-owner", issueRevision(issue.title, issue.body), null,
  ])).digest("hex");
  const record = await privateJson(path.join(intentsDirectory, `${expectedKey}.json`));
  if (record.request !== request || record.threadId !== threadId || !["intent", "queued"].includes(record.state)) {
    throw new Error("No pending dashboard pairing request matches this runtime");
  }
}

async function liveIssueAndClaim(identity, threadId) {
  const route = `repos/${identity.repository}/issues/${identity.number}`;
  const issue = JSON.parse((await execGh([route])).stdout);
  if (issue.html_url !== identity.url || issue.repository_url !== `https://api.github.com/repos/${identity.repository}`
      || issue.number !== identity.number || issue.pull_request || issue.state !== "open"
      || !Number.isSafeInteger(issue.comments) || issue.comments < 0 || issue.comments > MAX_RECORDS) {
    throw new Error("The issue is not open or its current identity is invalid");
  }
  const pages = JSON.parse((await execGh(["--paginate", "--slurp", `${route}/comments?per_page=100`])).stdout);
  if (!Array.isArray(pages) || pages.some(page => !Array.isArray(page))) throw new Error("Claim history is unavailable");
  const comments = pages.flat();
  if (comments.length !== issue.comments) throw new Error("Claim history is incomplete");
  const claim = currentClaim(comments);
  if (!legacyOwnerClaim(threadId, claim)) throw new Error("The live legacy claim does not match this original runtime");
  return { issue, claim, threadId };
}

export async function attestLegacyPair({ issueUrl, request, env = process.env, directory = ACTION_HOME, now = new Date() } = {}) {
  const identity = issueIdentity(issueUrl);
  if (!SHA256.test(request ?? "")) throw new Error("Invalid dashboard request receipt");
  if (!env || !UUID.test(env.CODEX_THREAD_ID ?? "")) throw new Error("The actual Codex runtime thread is unavailable");
  const threadId = env.CODEX_THREAD_ID;
  await existingPrivateDirectory(directory);
  const { issue, claim } = await liveIssueAndClaim(identity, threadId);
  await pendingIntent(path.join(directory, "intents"), request, threadId, issue);
  const timestamp = now instanceof Date ? new Date(now.getTime()) : new Date(now);
  if (!Number.isFinite(timestamp.getTime())) throw new Error("Invalid pairing timestamp");
  const issueUrlHash = createHash("sha256").update(identity.url).digest("hex");
  const pair = {
    version: 1,
    purpose: "dashboard-continuation",
    issueUrlHash,
    threadId,
    claimTask: claim.task,
    claimBranch: claim.branch,
    claimStartedAt: claim.startedAt,
    request,
    observedAt: timestamp.toISOString(),
  };
  const pairDirectory = await createPrivateDirectory(path.join(directory, "legacy-pairs"));
  const filename = path.join(pairDirectory, `${issueUrlHash}.json`);
  try {
    const handle = await open(filename, "wx", 0o600);
    try { await handle.writeFile(JSON.stringify(pair)); await handle.sync(); }
    finally { await handle.close(); }
    const folder = await open(pairDirectory, "r");
    try { await folder.sync(); } finally { await folder.close(); }
    return pair;
  } catch (error) {
    if (error?.code !== "EEXIST") throw error;
    const existing = await privateJson(filename);
    if (!validStoredPair(existing, issueUrlHash, claim) || existing.threadId !== threadId) {
      throw new Error("A different private pairing already exists for this issue");
    }
    return existing;
  }
}

async function savedPair(issueUrl, directory) {
  const identity = issueIdentity(issueUrl);
  const issueUrlHash = createHash("sha256").update(identity.url).digest("hex");
  try {
    await existingPrivateDirectory(directory);
    const pairDirectory = await existingPrivateDirectory(path.join(directory, "legacy-pairs"));
    const pair = await privateJson(path.join(pairDirectory, `${issueUrlHash}.json`));
    return pair.issueUrlHash === issueUrlHash && pair.purpose === "dashboard-continuation" ? pair : null;
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}

export async function legacyPairReceipt({ issueUrl, request, threadId, directory = ACTION_HOME }) {
  const pair = await savedPair(issueUrl, directory);
  return pair?.request === request && pair?.threadId === threadId;
}

export async function readLegacyPairRecord({ issueUrl, claim, directory = ACTION_HOME } = {}) {
  if (!claim || claim.state !== "active" || !Number.isFinite(Date.parse(claim.startedAt)) || Date.parse(claim.startedAt) >= PREVIEW_START) return null;
  const pair = await savedPair(issueUrl, directory);
  return pair && validStoredPair(pair, pair.issueUrlHash, claim)
    && [pair.threadId, publicOwnerKey(pair.threadId)].includes(claim.task) ? pair : null;
}

export async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 5 || argv[0] !== "attest" || argv[1] !== "--issue" || argv[3] !== "--request") {
    throw new Error("Usage: project-progress-pair.mjs attest --issue ISSUE_URL --request REQUEST_RECEIPT");
  }
  await attestLegacyPair({ issueUrl: argv[2], request: argv[4] });
  console.log("Legacy pairing recorded for dashboard continuation only. No CI origin, approval, or paid execution was established.");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : "Legacy pairing failed");
    process.exitCode = 1;
  });
}
