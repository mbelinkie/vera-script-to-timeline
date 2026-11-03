#!/usr/bin/env node

import { createHash, randomBytes } from "node:crypto";
import {
  closeSync, constants as fsConstants, fstatSync, fsyncSync, linkSync,
  lstatSync, mkdirSync, openSync, readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { issueRevision, REPOS } from "./chat-review-current.mjs";
import { verifyReviewFromGh } from "./chat-review-github.mjs";

export const VERA_REPOSITORY = "mbelinkie/vera-script-to-timeline";
export const DEFAULT_DIRECTORY = path.join(os.homedir(), "Library", "Application Support", "VERA", "ci-notifications");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ORIGIN_SURFACE = "codex-desktop";
const PROVENANCE_METHOD = "runtime-thread-environment";
const STATUS = "manual-review-only";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const LAUNCH_ID_PATTERN = /^[0-9a-f]{64}$/;
const EVENT_ID_PATTERN = /^[0-9a-f]{64}$/;
const REVISION_PATTERN = /^[0-9a-f]{64}$/;
const noFollow = fsConstants.O_NOFOLLOW ?? 0;

function isPositiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function hasControlCharacter(value) {
  return [...value].some(character => character.charCodeAt(0) < 0x20 || character.charCodeAt(0) === 0x7f);
}

function assertText(value, name, maxLength = 512) {
  if (typeof value !== "string" || !value || value.length > maxLength || hasControlCharacter(value)) throw new Error(`Invalid ${name}`);
}

function assertThreadId(value) {
  if (typeof value !== "string" || !UUID_PATTERN.test(value)) throw new Error("CODEX_THREAD_ID must be the runtime UUID");
  return value;
}

export function publicOwnerKey(threadId) {
  assertThreadId(threadId);
  return "codex-owner-" + createHash("sha256").update(VERA_REPOSITORY + "\0" + threadId).digest("hex");
}

function cloneScope(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)) {
    throw new Error("Authorized scope must be a JSON object");
  }
  let serialized;
  try { serialized = JSON.stringify(value); }
  catch (error) { throw new Error("Authorized scope must be JSON-safe", { cause: error }); }
  if (!serialized || serialized.length > 2_000_000) throw new Error("Authorized scope is invalid or too large");
  const cloned = JSON.parse(serialized);
  if (!cloned || typeof cloned !== "object" || Array.isArray(cloned)) throw new Error("Authorized scope must be a JSON object");
  return cloned;
}

function registeredAt(now) {
  const date = now instanceof Date ? new Date(now.getTime()) : new Date(now);
  if (!Number.isFinite(date.getTime())) throw new Error("Invalid registration time");
  return date.toISOString();
}

export function captureOrigin({
  repository,
  issue,
  branch,
  approvalCommentId,
  approvalRevision,
  authorizedScope,
  env = process.env,
  now = new Date(),
} = {}) {
  if (repository !== VERA_REPOSITORY || !REPOS.has(repository)) throw new Error("Unsupported VERA repository");
  if (!isPositiveInteger(issue)) throw new Error("Invalid issue number");
  assertText(branch, "branch", 255);
  if (!isPositiveInteger(approvalCommentId)) throw new Error("Invalid approval comment ID");
  if (typeof approvalRevision !== "string" || !REVISION_PATTERN.test(approvalRevision)) throw new Error("Invalid approval revision");
  if (!env || typeof env !== "object") throw new Error("Runtime thread environment unavailable");
  const threadId = assertThreadId(env.CODEX_THREAD_ID);
  const scope = cloneScope(authorizedScope);
  const timestamp = registeredAt(now);
  const launchId = randomBytes(32).toString("hex");

  return {
    version: 1,
    launchId,
    threadId,
    originSurface: ORIGIN_SURFACE,
    provenance: {
      method: PROVENANCE_METHOD,
      approval: {
        kind: "current-producer-chat-review",
        commentId: approvalCommentId,
        revision: approvalRevision,
      },
    },
    repository,
    issue,
    branch,
    authorizedScope: scope,
    status: STATUS,
    pr: null,
    approvalCommentId,
    approvalRevision,
    registeredAt: timestamp,
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function exactKeys(value, names) {
  const keys = Object.keys(value).sort();
  const expected = [...names].sort();
  return keys.length === expected.length && keys.every((key, index) => key === expected[index]);
}

function assertOrigin(record, { allowBound = false } = {}) {
  if (!record || typeof record !== "object" || Array.isArray(record) ||
      !exactKeys(record, ["version", "launchId", "threadId", "originSurface", "provenance", "repository", "issue", "branch", "authorizedScope", "status", "pr", "approvalCommentId", "approvalRevision", "registeredAt"]) ||
      !exactKeys(record.provenance ?? {}, ["method", "approval"]) ||
      !exactKeys(record.provenance?.approval ?? {}, ["kind", "commentId", "revision"]) ||
      record.version !== 1 || typeof record.launchId !== "string" || !LAUNCH_ID_PATTERN.test(record.launchId) ||
      typeof record.threadId !== "string" || !UUID_PATTERN.test(record.threadId) ||
      record.originSurface !== ORIGIN_SURFACE || record.status !== STATUS ||
      record.repository !== VERA_REPOSITORY || !REPOS.has(record.repository) ||
      !isPositiveInteger(record.issue) || typeof record.branch !== "string" ||
      !record.branch || record.branch.length > 255 || hasControlCharacter(record.branch) ||
      !record.authorizedScope || typeof record.authorizedScope !== "object" || Array.isArray(record.authorizedScope) ||
      !isPositiveInteger(record.approvalCommentId) || typeof record.approvalRevision !== "string" ||
      !REVISION_PATTERN.test(record.approvalRevision) ||
      typeof record.registeredAt !== "string" || !Number.isFinite(Date.parse(record.registeredAt)) ||
      new Date(record.registeredAt).toISOString() !== record.registeredAt ||
      !record.provenance || typeof record.provenance !== "object" ||
      record.provenance.method !== PROVENANCE_METHOD ||
      record.provenance.approval?.kind !== "current-producer-chat-review" ||
      record.provenance.approval.commentId !== record.approvalCommentId ||
      record.provenance.approval.revision !== record.approvalRevision ||
      (record.pr !== null && (!allowBound || !isPositiveInteger(record.pr)))) {
    throw new Error("Invalid CI notification origin record");
  }
  return record;
}

function assertPrivateDirectory(directory, { create = false } = {}) {
  const absolute = path.resolve(directory);
  if (create) {
    try {
      mkdirSync(absolute, { recursive: true, mode: 0o700 });
    } catch (error) {
      throw new Error("Could not create private CI notification registry", { cause: error });
    }
  }
  let stat;
  try {
    stat = lstatSync(absolute);
  } catch (error) {
    if (error?.code === "ENOENT" && !create) return null;
    throw new Error("CI notification registry is unavailable", { cause: error });
  }
  const uid = typeof process.getuid === "function" ? process.getuid() : null;
  if (stat.isSymbolicLink() || !stat.isDirectory() || uid === null || stat.uid !== uid || (stat.mode & 0o777) !== 0o700) {
    throw new Error("CI notification registry must be an owned mode-0700 directory");
  }
  let parent;
  try {
    parent = lstatSync(path.dirname(absolute));
  } catch (error) {
    throw new Error("CI notification registry parent is unavailable", { cause: error });
  }
  if (parent.isSymbolicLink() || !parent.isDirectory() ||
      (parent.uid !== uid && !(parent.uid === 0 && (parent.mode & 0o1000) !== 0)) ||
      ((parent.mode & 0o022) !== 0 && (parent.mode & 0o1000) === 0)) {
    throw new Error("CI notification registry parent is unsafe");
  }
  return absolute;
}

function assertPrivateFile(fd, description) {
  const stat = fstatSync(fd);
  const uid = typeof process.getuid === "function" ? process.getuid() : null;
  if (!stat.isFile() || uid === null || stat.uid !== uid || (stat.mode & 0o777) !== 0o600 || stat.nlink !== 1) {
    throw new Error(`${description} must be an owned mode-0600 regular file`);
  }
}

function recoverTemporaryLink(file, fd, description) {
  const target = fstatSync(fd);
  if (target.nlink === 1) return;
  const uid = typeof process.getuid === "function" ? process.getuid() : null;
  const invalid = () => new Error(`${description} must be an owned mode-0600 regular file`);
  if (!target.isFile() || uid === null || target.uid !== uid || (target.mode & 0o777) !== 0o600 || target.nlink !== 2) {
    throw invalid();
  }
  const directory = path.dirname(file);
  const names = readdirSync(directory);
  if (names.length > 5000) throw new Error(`${description} has too many registry entries`);
  let twins;
  try {
    twins = names.filter(name => /^\.origin-[0-9a-f]{32}\.tmp$/.test(name)).filter(name => {
      const stat = lstatSync(path.join(directory, name));
      return stat.isFile() && stat.uid === uid && (stat.mode & 0o777) === 0o600 &&
        stat.nlink === 2 && stat.dev === target.dev && stat.ino === target.ino;
    });
  } catch (error) {
    if (error?.code !== "ENOENT" || fstatSync(fd).nlink !== 1) throw error;
    return;
  }
  if (twins.length !== 1) {
    if (fstatSync(fd).nlink === 1) return;
    throw invalid();
  }
  const twin = path.join(directory, twins[0]);
  let current;
  try { current = lstatSync(twin); }
  catch (error) {
    if (error?.code === "ENOENT" && fstatSync(fd).nlink === 1) return;
    throw error;
  }
  if (!current.isFile() || current.dev !== target.dev || current.ino !== target.ino ||
      current.uid !== target.uid || (current.mode & 0o777) !== 0o600 || current.nlink !== 2) {
    throw new Error(`${description} has an unsafe temporary link`);
  }
  try { unlinkSync(twin); }
  catch (error) {
    if (error?.code !== "ENOENT" || fstatSync(fd).nlink !== 1) throw error;
  }
  const directoryFd = openSync(directory, fsConstants.O_RDONLY);
  try { fsyncSync(directoryFd); } finally { closeSync(directoryFd); }
  if (fstatSync(fd).nlink !== 1) throw new Error(`${description} has an unresolved temporary link`);
}

function readJsonFile(file, description) {
  let fd;
  try {
    fd = openSync(file, fsConstants.O_RDONLY | noFollow);
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw new Error(`${description} is unavailable or unsafe`, { cause: error });
  }
  try {
    recoverTemporaryLink(file, fd, description);
    assertPrivateFile(fd, description);
    return JSON.parse(readFileSync(fd, "utf8"));
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error(`${description} is invalid JSON`, { cause: error });
    throw error;
  } finally {
    closeSync(fd);
  }
}

function writeJsonAtomically(file, value, directory, { replace = false } = {}) {
  const temporary = path.join(directory, `.origin-${randomBytes(16).toString("hex")}.tmp`);
  let fd;
  try {
    fd = openSync(temporary, fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_EXCL | noFollow, 0o600);
    assertPrivateFile(fd, "Temporary registry file");
    writeFileSync(fd, `${JSON.stringify(value)}\n`, "utf8");
    fsyncSync(fd);
    closeSync(fd);
    fd = undefined;
    if (replace) renameSync(temporary, file);
    else {
      linkSync(temporary, file);
      try { unlinkSync(temporary); }
      catch (error) { if (error?.code !== "ENOENT") throw error; }
    }
    const parentFd = openSync(directory, fsConstants.O_RDONLY);
    try { fsyncSync(parentFd); } finally { closeSync(parentFd); }
  } catch (error) {
    if (error?.code === "EEXIST") throw error;
    throw new Error("Could not atomically write private CI notification registry data", { cause: error });
  } finally {
    if (fd !== undefined) closeSync(fd);
    try { unlinkSync(temporary); } catch { /* the link may not have been created */ }
  }
}

function acquireRegistryLock(directory) {
  const file = path.join(directory, ".registry.lock");
  let fd;
  try {
    fd = openSync(file, fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_EXCL | noFollow, 0o600);
    assertPrivateFile(fd, "Registry lock");
    writeFileSync(fd, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }), "utf8");
    fsyncSync(fd);
  } catch (error) {
    if (fd !== undefined) closeSync(fd);
    throw new Error(error?.code === "EEXIST" ? "CI notification registry is locked" : "Could not lock CI notification registry", { cause: error });
  }
  const locked = fstatSync(fd);
  closeSync(fd);
  return () => {
    try {
      const current = lstatSync(file);
      if (current.isFile() && current.dev === locked.dev && current.ino === locked.ino && current.uid === process.getuid()) {
        unlinkSync(file);
      }
    } catch { /* do not remove a lock that no longer belongs to this operation */ }
  };
}

function withRegistryLock(directory, operation) {
  const release = acquireRegistryLock(directory);
  try { return operation(); } finally { release(); }
}

function originPath(directory, launchId) {
  if (typeof launchId !== "string" || !LAUNCH_ID_PATTERN.test(launchId)) throw new Error("Invalid launch ID");
  return path.join(directory, `${launchId}.json`);
}

function bindingPath(directory, launchId) {
  return path.join(directory, `${launchId}.binding.json`);
}

function deliveryAuditPath(directory, eventId) {
  if (typeof eventId !== "string" || !EVENT_ID_PATTERN.test(eventId)) throw new Error("Invalid CI event ID");
  return path.join(directory, `delivery-audit-${eventId}.json`);
}

function assertBinding(binding, record) {
  if (!binding || !exactKeys(binding, ["version", "launchId", "repository", "issue", "pr", "branch", "boundAt"]) ||
      binding.version !== 1 || binding.launchId !== record.launchId ||
      binding.repository !== record.repository || binding.issue !== record.issue ||
      binding.branch !== record.branch || !isPositiveInteger(binding.pr) ||
      typeof binding.boundAt !== "string" || !Number.isFinite(Date.parse(binding.boundAt)) ||
      new Date(binding.boundAt).toISOString() !== binding.boundAt) {
    throw new Error("CI notification PR binding is invalid");
  }
  return binding;
}

function sameOrigin(left, right) {
  return canonicalJson(left) === canonicalJson(right);
}

export async function saveOrigin(record, directory = DEFAULT_DIRECTORY) {
  assertOrigin(record);
  const safeDirectory = assertPrivateDirectory(directory, { create: true });
  return withRegistryLock(safeDirectory, () => {
    const file = originPath(safeDirectory, record.launchId);
    const existing = readJsonFile(file, "CI notification origin");
    if (existing) {
      assertOrigin(existing);
      if (!sameOrigin(existing, record)) throw new Error("Launch origin is immutable and already registered");
      return existing;
    }
    try {
      writeJsonAtomically(file, record, safeDirectory);
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      const raced = readJsonFile(file, "CI notification origin");
      if (!raced || !sameOrigin(raced, record)) throw new Error("Launch origin is immutable and already registered", { cause: error });
      return raced;
    }
    return record;
  });
}

export function loadOrigin(launchId, directory = DEFAULT_DIRECTORY) {
  const file = originPath(path.resolve(directory), launchId);
  const safeDirectory = assertPrivateDirectory(directory);
  if (!safeDirectory) return null;
  const base = readJsonFile(file, "CI notification origin");
  if (!base) return null;
  assertOrigin(base);
  const binding = readJsonFile(bindingPath(safeDirectory, launchId), "CI notification PR binding");
  if (!binding) return base;
  assertBinding(binding, base);
  return { ...base, pr: binding.pr };
}

export function loadDeliveryAudit(eventId, directory = DEFAULT_DIRECTORY) {
  const file = deliveryAuditPath(path.resolve(directory), eventId);
  const safeDirectory = assertPrivateDirectory(directory);
  return safeDirectory ? readJsonFile(file, "CI delivery audit") : null;
}

export async function saveDeliveryAudit(eventId, audit, previous, directory = DEFAULT_DIRECTORY) {
  deliveryAuditPath(directory, eventId);
  const safeDirectory = assertPrivateDirectory(directory, { create: true });
  const file = deliveryAuditPath(safeDirectory, eventId);
  const value = cloneScope(audit);
  return withRegistryLock(safeDirectory, () => {
    const current = readJsonFile(file, "CI delivery audit");
    if (previous !== undefined) {
      const expected = previous === null ? { version: 1, entries: [] } : cloneScope(previous);
      if (!sameOrigin(current ?? { version: 1, entries: [] }, expected)) return { status: "writer_conflict" };
    }
    writeJsonAtomically(file, value, safeDirectory, { replace: true });
    return true;
  });
}

export function bindOrigin(record, pr, directory = DEFAULT_DIRECTORY) {
  assertOrigin(record, { allowBound: true });
  if (!isPositiveInteger(pr)) throw new Error("Invalid pull request number");
  const safeDirectory = assertPrivateDirectory(directory, { create: true });
  return withRegistryLock(safeDirectory, () => {
    const stored = readJsonFile(originPath(safeDirectory, record.launchId), "CI notification origin");
    if (!stored) throw new Error("Launch origin is not registered");
    assertOrigin(stored);
    const requestedBase = { ...record, pr: null };
    if (!sameOrigin(stored, requestedBase)) throw new Error("Launch origin does not match the immutable registration");
    if (record.pr !== null && record.pr !== pr) throw new Error("Launch origin is already bound to another pull request");

    const file = bindingPath(safeDirectory, record.launchId);
    const existing = readJsonFile(file, "CI notification PR binding");
    if (existing) {
      assertBinding(existing, stored);
      if (existing.pr !== pr) throw new Error("Launch origin is already bound to another pull request");
      return { ...stored, pr };
    }
    const binding = {
      version: 1,
      launchId: stored.launchId,
      repository: stored.repository,
      issue: stored.issue,
      pr,
      branch: stored.branch,
      boundAt: new Date().toISOString(),
    };
    try {
      writeJsonAtomically(file, binding, safeDirectory);
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      const raced = readJsonFile(file, "CI notification PR binding");
      assertBinding(raced, stored);
      if (raced.pr !== pr) throw new Error("Launch origin is already bound to another pull request", { cause: error });
    }
    return { ...stored, pr };
  });
}

export function findOriginForEvent(event, directory = DEFAULT_DIRECTORY) {
  if (!event || typeof event !== "object" || Array.isArray(event) ||
      typeof event.launchId !== "string" || !LAUNCH_ID_PATTERN.test(event.launchId) ||
      typeof event.repository !== "string" || !isPositiveInteger(event.issue) ||
      !isPositiveInteger(event.pr) || typeof event.branch !== "string") return null;
  const record = loadOrigin(event.launchId, directory);
  if (!record || record.pr === null || record.repository !== event.repository ||
      record.issue !== event.issue || record.pr !== event.pr || record.branch !== event.branch) return null;
  return record;
}

export function publicBinding(record) {
  assertOrigin(record, { allowBound: true });
  if (!isPositiveInteger(record.pr)) throw new Error("Origin must have a pull request binding before publication");
  return {
    version: 1,
    repository: record.repository,
    issue: record.issue,
    pr: record.pr,
    launchId: record.launchId,
    branch: record.branch,
    registeredAt: record.registeredAt,
    approvalCommentId: record.approvalCommentId,
    approvalRevision: record.approvalRevision,
  };
}

export function privateNavigationUrl(record) {
  assertOrigin(record, { allowBound: true });
  return `codex://threads/${record.threadId}`;
}

function readGh(args) {
  const result = spawnSync("gh", args, {
    cwd: root,
    encoding: "utf8",
    env: process.env,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error || result.signal || result.status !== 0) throw new Error("GitHub read failed; no origin was registered");
  return result.stdout;
}

function parseJson(text, message) {
  try { return JSON.parse(text); }
  catch (error) { throw new Error(message, { cause: error }); }
}

function readGhJson(args, message) {
  return parseJson(readGh(args), message);
}

function readApprovedScope(issueNumber, revision) {
  const issue = readGhJson(["api", `repos/${VERA_REPOSITORY}/issues/${issueNumber}`], "Could not read the approved issue scope");
  if (!issue || issue.number !== issueNumber || issue.repository_url !== `https://api.github.com/repos/${VERA_REPOSITORY}` ||
      issue.html_url !== `https://github.com/${VERA_REPOSITORY}/issues/${issueNumber}` || issue.pull_request ||
      typeof issue.title !== "string" || typeof issue.body !== "string" || issue.state?.toLowerCase() !== "open" ||
      issueRevision(issue.title, issue.body) !== revision) {
    throw new Error("Approved issue scope changed; no origin was registered");
  }
  return { title: issue.title, body: issue.body, revision };
}

function verifyActiveClaim(issueNumber, threadId, branch) {
  const result = spawnSync(process.execPath, [path.join(root, "scripts", "roadmap.mjs"), "inspect", String(issueNumber)], {
    cwd: root,
    encoding: "utf8",
    env: process.env,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error || result.signal || result.status !== 0) throw new Error("Could not verify the active roadmap claim");
  const snapshot = parseJson(result.stdout, "Could not verify the active roadmap claim");
  if (snapshot?.issue?.number !== issueNumber || snapshot.issue.state?.toLowerCase() !== "open" ||
      snapshot.project?.status !== "In progress" || snapshot.claim?.state !== "active" ||
      snapshot.claim?.task !== publicOwnerKey(threadId) || snapshot.claim?.branch !== branch) {
    throw new Error("Active roadmap claim does not match this runtime thread and branch");
  }
}

function parseFlags(argv, command, allowed) {
  const flags = new Map();
  for (let index = 1; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag.startsWith("--") || !allowed.has(flag.slice(2)) || flags.has(flag.slice(2))) {
      throw new Error(`Invalid ${command} arguments`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) throw new Error(`Missing value for ${flag}`);
    flags.set(flag.slice(2), value);
    index += 1;
  }
  for (const name of allowed) if (!flags.has(name)) throw new Error(`Missing --${name}`);
  return flags;
}

function positiveFlag(flags, name) {
  const value = flags.get(name);
  if (!/^[1-9]\d*$/.test(value || "")) throw new Error(`Invalid --${name}`);
  const number = Number(value);
  if (!isPositiveInteger(number)) throw new Error(`Invalid --${name}`);
  return number;
}

function verifyPullRequest(pr, record) {
  const pull = readGhJson(["api", `repos/${record.repository}/pulls/${pr}`], "Could not verify the pull request; no binding was written");
  if (!pull || pull.number !== pr || pull.state?.toLowerCase() !== "open" ||
      pull.head?.ref !== record.branch || pull.head?.repo?.full_name !== record.repository ||
      pull.base?.repo?.full_name !== record.repository) {
    throw new Error("Pull request must be open in the origin repository on the claimed branch");
  }
}

export async function main(argv = process.argv.slice(2), { directory = DEFAULT_DIRECTORY, env = process.env } = {}) {
  const [command] = argv;
  if (command === "owner-key" && argv.length === 1) {
    const key = publicOwnerKey(env.CODEX_THREAD_ID);
    console.log(key);
    return key;
  }
  if (command === "capture") {
    const flags = parseFlags(argv, command, new Set(["issue", "branch", "approval-comment", "approval-revision"]));
    const issue = positiveFlag(flags, "issue");
    const branch = flags.get("branch");
    assertText(branch, "branch", 255);
    const approvalCommentId = positiveFlag(flags, "approval-comment");
    const approvalRevision = flags.get("approval-revision");
    if (!REVISION_PATTERN.test(approvalRevision)) throw new Error("Invalid --approval-revision");
    const threadId = assertThreadId(env?.CODEX_THREAD_ID);
    const approval = verifyReviewFromGh(readGh, VERA_REPOSITORY, issue);
    if (approval.commentId !== approvalCommentId || approval.revision !== approvalRevision) {
      throw new Error("Current Producer review does not match the supplied approval; no origin was registered");
    }
    const authorizedScope = readApprovedScope(issue, approvalRevision);
    verifyActiveClaim(issue, threadId, branch);
    const record = captureOrigin({
      repository: VERA_REPOSITORY,
      issue,
      branch,
      approvalCommentId,
      approvalRevision,
      authorizedScope,
      env,
    });
    await saveOrigin(record, directory);
    console.log(record.launchId);
    return record.launchId;
  }
  if (command === "bind") {
    const flags = parseFlags(argv, command, new Set(["launch", "pr"]));
    const launchId = flags.get("launch");
    if (!LAUNCH_ID_PATTERN.test(launchId)) throw new Error("Invalid --launch");
    const pr = positiveFlag(flags, "pr");
    const record = loadOrigin(launchId, directory);
    if (!record) throw new Error("Launch origin is not registered");
    verifyPullRequest(pr, record);
    const bound = bindOrigin(record, pr, directory);
    console.log(bound.launchId);
    return bound.launchId;
  }
  throw new Error("Usage: ci-notification-origin.mjs <owner-key|capture|bind> [flags]");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : "CI notification origin failed");
    process.exitCode = 1;
  });
}
