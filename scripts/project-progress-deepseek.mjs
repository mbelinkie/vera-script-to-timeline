import { accessSync, closeSync, constants, fstatSync, lstatSync, openSync, readFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import path from "node:path";
import { REPOS } from "./chat-review-current.mjs";

const REPOSITORY = "mbelinkie/vera-script-to-timeline";
const MAX_RECEIPTS = 256;
const MAX_RECEIPT_BYTES = 64 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;

function names(item) {
  const labels = item?.labels ?? item?.content?.labels;
  return new Set(Array.isArray(labels) ? labels.map(label => typeof label === "string" ? label : label?.name)
    .filter(label => typeof label === "string") : []);
}

function hasActiveOwner(item, labels) {
  const workflow = item?.workflow ?? {};
  return [...labels].some(label => /^owner:[a-z0-9-]+$/.test(label))
    || [item?.codex?.state, item?.claim?.state, workflow.codex?.state].includes("claimed")
    || item?.ownerBound === true || item?.activeTurn === true
    || Boolean(item?.pullRequest || item?.pr || (Array.isArray(workflow.links) && workflow.links.some(link => link?.label === "PR")));
}

export function deepseekRouteForIssue(item) {
  const url = item?.url ?? item?.content?.url;
  const identity = typeof url === "string" ? /^https:\/\/github\.com\/([^/]+\/[^/]+)\/issues\/([1-9][0-9]*)$/.exec(url) : null;
  if (!identity || !REPOS.has(identity[1]) || !Number.isSafeInteger(Number(identity[2]))
      || (identity[1] === REPOSITORY && Number(identity[2]) === 411) || item?.status === "Done") return null;
  if (/^design\s/i.test(item?.title ?? item?.content?.title ?? "")) return null;
  const labels = names(item);
  const types = [...labels].filter(label => label.startsWith("type:"));
  if (types.length !== 1 || !["type:implementation", "type:bug"].includes(types[0])) return null;
  if (["deepseek-excluded", "execution:codex", "execution:design", "execution:human",
    "type:design", "type:ux", "type:research", "type:product"].some(label => labels.has(label))
      || hasActiveOwner(item, labels)) return null;
  return "chat";
}

function owned(stat) {
  const uid = process.getuid?.();
  return uid !== undefined && stat.uid === uid;
}

function directoryState(file, { privateOnly = true } = {}) {
  try {
    const stat = lstatSync(file);
    return stat.isDirectory() && !stat.isSymbolicLink() && owned(stat)
      && (stat.mode & 0o700) === 0o700
      && (stat.mode & (privateOnly ? 0o077 : 0o022)) === 0;
  } catch { return false; }
}

function installedRunner(home) {
  const codex = path.join(home, ".codex");
  const bin = path.join(codex, "bin");
  const runner = path.join(bin, "vera-deepseek-runner");
  if (!directoryState(codex) || !directoryState(bin, { privateOnly: false })) {
    try { lstatSync(runner); } catch (error) { return error?.code === "ENOENT" ? { state: "off" } : { state: "unknown" }; }
    return { state: "unknown" };
  }
  let stat;
  try { stat = lstatSync(runner); } catch (error) {
    return error?.code === "ENOENT" ? { state: "off" } : { state: "unknown" };
  }
  if (!stat.isFile() || stat.isSymbolicLink() || !owned(stat) || (stat.mode & 0o077) !== 0
      || (stat.mode & 0o500) !== 0o500) return { state: "unknown" };
  try { accessSync(runner, constants.R_OK | constants.X_OK); } catch { return { state: "unknown" }; }

  let fd;
  try {
    fd = openSync(runner, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
    const opened = fstatSync(fd);
    if (!opened.isFile() || !owned(opened) || opened.dev !== stat.dev || opened.ino !== stat.ino
        || (opened.mode & 0o077) !== 0 || (opened.mode & 0o500) !== 0o500
        || opened.size < 1 || opened.size > 32 * 1024 * 1024) return { state: "unknown" };
    const digest = createHash("sha256").update(readFileSync(fd)).digest("hex");
    const after = fstatSync(fd);
    if (after.dev !== opened.dev || after.ino !== opened.ino || after.size !== opened.size || after.mtimeMs !== opened.mtimeMs) {
      return { state: "unknown" };
    }
    return { state: "installed", digest };
  } catch { return { state: "unknown" }; }
  finally { if (fd !== undefined) closeSync(fd); }
}

function safeReceipt(file) {
  let fd;
  try {
    const before = lstatSync(file);
    if (!before.isFile() || before.isSymbolicLink() || !owned(before) || (before.mode & 0o077) !== 0
        || (before.mode & 0o400) !== 0o400 || before.size < 2 || before.size > MAX_RECEIPT_BYTES) return null;
    fd = openSync(file, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
    const opened = fstatSync(fd);
    if (!opened.isFile() || !owned(opened) || opened.dev !== before.dev || opened.ino !== before.ino
        || (opened.mode & 0o077) !== 0 || (opened.mode & 0o400) !== 0o400 || opened.size !== before.size) return null;
    const record = JSON.parse(readFileSync(fd, "utf8"));
    const after = fstatSync(fd);
    if (after.dev !== opened.dev || after.ino !== opened.ino || after.size !== opened.size || after.mtimeMs !== opened.mtimeMs) return null;
    return record && typeof record === "object" && !Array.isArray(record) ? record : null;
  } catch { return null; }
  finally { if (fd !== undefined) closeSync(fd); }
}

function recordState(record, issueNumber, adapterDigest) {
  const validRecord = record?.schema === 1 && record.issue === issueNumber
    && Number.isSafeInteger(record.commentId) && record.commentId > 0
    && SHA256.test(record.manifest_sha256 || "") && /^[a-f0-9]{40}$/.test(record.source_sha || "")
    && record.adapter_sha256 === adapterDigest;
  if (validRecord && record.state === "candidate_ready_for_review" && record.invocation_may_have_started === true
      && record.provider_calls === 1 && record.response_retained === true
      && Number.isSafeInteger(record.review_comment_id) && record.review_comment_id > 0) {
    return { state: "candidate", reason: "A bounded candidate receipt was recorded; its current integration status is not inferred." };
  }
  return { state: "unknown", reason: "The local record does not establish a supported current job state." };
}

function nowIso(now) {
  const date = Number.isFinite(now) ? new Date(now) : null;
  return date && Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

export async function loadDeepSeekDashboardEvidence({ now = Date.now(), env = process.env } = {}) {
  const checkedAt = nowIso(now);
  if (!checkedAt || !env || typeof env !== "object") {
    return { installation: { state: "unknown", checkedAt }, byIssue: {} };
  }
  const home = typeof env.HOME === "string" && path.isAbsolute(env.HOME) ? env.HOME : homedir();
  const runner = installedRunner(home);
  const installation = { state: runner.state, checkedAt };
  const byIssue = {};
  const root = path.join(home, ".codex", "deepseek-dispatch-receipts");
  if (runner.state !== "installed" || !directoryState(root)) return { installation, byIssue };
  let entries;
  try { entries = readdirSync(root).filter(name => /^issue-[1-9][0-9]*$/.test(name)).slice(0, MAX_RECEIPTS); }
  catch { return { installation, byIssue };
  }
  for (const name of entries) {
    const issueNumber = Number(name.slice("issue-".length));
    if (!Number.isSafeInteger(issueNumber) || issueNumber === 411) continue;
    const issueDirectory = path.join(root, name);
    const url = `https://github.com/${REPOSITORY}/issues/${issueNumber}`;
    if (!directoryState(issueDirectory)) {
      byIssue[url] = { state: "unknown", reason: "The local receipt directory cannot be verified safely." };
      continue;
    }
    byIssue[url] = recordState(safeReceipt(path.join(issueDirectory, "receipt.json")), issueNumber, runner.digest);
  }
  return { installation, byIssue };
}
