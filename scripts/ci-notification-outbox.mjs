import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import { setTimeout as delay } from "node:timers/promises";
import { TextDecoder } from "node:util";

export const REPOSITORY = "mbelinkie/vera-script-to-timeline";
export const OUTBOX_BRANCH = "vera-ci-notification-outbox";

const ROOT = "/repos/" + REPOSITORY;
const BOT_LOGIN = "github-actions[bot]";
const MAX_DOCUMENT_BYTES = 64 * 1024;
const MAX_ATTEMPTS = 3;
const BACKOFF_MS = [250, 1000];
const DAY_MS = 24 * 60 * 60 * 1000;
const RETENTION_MS = 7 * DAY_MS;
const SHA40 = /^[0-9a-f]{40}$/;
const SHA64 = /^[0-9a-f]{64}$/;
const TRANSACTION = /^[A-Za-z0-9._-]{1,64}$/;
const EVENT_KEYS = [
  "version", "eventId", "repository", "issue", "pr", "launchId", "transaction", "queueTransaction",
  "runId", "runAttempt", "workflowId", "workflowHead", "candidate", "base", "mergeSha", "stateSha",
  "bindingSha", "phase", "conclusion", "assessment", "emittedAt", "expiresAt", "runUrl",
];
const IDENTITY_KEYS = EVENT_KEYS.filter((key) => !["eventId", "emittedAt", "expiresAt"].includes(key));
const OUTCOME_VALUES = new Set(["none", "found", "posted", "ambiguous", "rejected"]);
const LEGACY_AUDIT_KEYS = [
  "version", "eventId", "status", "eventWriteAttempts", "commentAttempts", "manualRetryUsed",
  "nextAttemptAt", "lastOutcome",
];
const AUDIT_KEYS = [...LEGACY_AUDIT_KEYS, "commentHttpStatus", "commentIssue"];

function fail(message, code = "invalid") {
  const error = new Error(message);
  error.code = code;
  return error;
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}

function ownDataValue(object, key) {
  const descriptor = Object.getOwnPropertyDescriptor(object, key);
  if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) {
    throw fail("CI notification event fields must be enumerable data properties");
  }
  return descriptor.value;
}

function positiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function hasHex(value, pattern) {
  return typeof value === "string" && pattern.test(value);
}

function isoUtc(value, label) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) {
    throw fail("CI notification " + label + " must be a UTC ISO timestamp");
  }
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw fail("CI notification " + label + " must be a UTC ISO timestamp");
  const normalized = date.toISOString();
  if (normalized !== value && normalized !== value.replace(/Z$/, ".000Z")) {
    throw fail("CI notification " + label + " must be a valid UTC ISO timestamp");
  }
  return normalized;
}

function identityFor(event) {
  return Object.fromEntries(IDENTITY_KEYS.map((key) => [key, event[key]]));
}

function expectedEventId(event) {
  return createHash("sha256").update(JSON.stringify(identityFor(event))).digest("hex");
}

function validateAudit(audit, eventId, event) {
  const keys = isRecord(audit) ? Reflect.ownKeys(audit) : [];
  if (!isRecord(audit) || keys.length < LEGACY_AUDIT_KEYS.length ||
      keys.length > AUDIT_KEYS.length || LEGACY_AUDIT_KEYS.some((key) => !Object.hasOwn(audit, key)) ||
      keys.some((key) => !AUDIT_KEYS.includes(key))) {
    throw fail("CI notification audit had an invalid shape");
  }
  if (!Object.hasOwn(audit, "commentHttpStatus") || !Object.hasOwn(audit, "commentIssue")) audit = {
    ...audit,
    commentHttpStatus: audit.commentHttpStatus ?? null,
    commentIssue: audit.commentIssue ?? (audit.commentAttempts > 0 ? event?.pr ?? null : null),
  };
  if (audit.version !== 1 || audit.eventId !== eventId ||
      !["persisted", "posting", "commented", "pending", "failed"].includes(audit.status) ||
      !Number.isSafeInteger(audit.eventWriteAttempts) || audit.eventWriteAttempts < 0 ||
      audit.eventWriteAttempts > MAX_ATTEMPTS || !Number.isSafeInteger(audit.commentAttempts) ||
      audit.commentAttempts < 0 || audit.commentAttempts > 2 || typeof audit.manualRetryUsed !== "boolean" ||
      !OUTCOME_VALUES.has(audit.lastOutcome) ||
      !(audit.commentHttpStatus === null || Number.isSafeInteger(audit.commentHttpStatus) &&
        audit.commentHttpStatus >= 400 && audit.commentHttpStatus <= 599) ||
      !(audit.commentIssue === null || positiveInteger(audit.commentIssue)) ||
      (event && audit.commentIssue !== null && audit.commentIssue !== event.pr &&
        audit.commentIssue !== event.issue)) {
    throw fail("CI notification audit failed validation");
  }
  if (audit.nextAttemptAt !== null) {
    const normalized = isoUtc(audit.nextAttemptAt, "audit nextAttemptAt");
    if (normalized !== audit.nextAttemptAt) throw fail("CI notification audit timestamp was not canonical");
  }
  return audit;
}

export function validateEvent(event) {
  if (!isRecord(event) || Reflect.ownKeys(event).length !== EVENT_KEYS.length ||
      EVENT_KEYS.some((key) => !Object.hasOwn(event, key))) {
    throw fail("CI notification event had an invalid shape");
  }
  for (const key of EVENT_KEYS) ownDataValue(event, key);
  if (event.version !== 1 || event.repository !== REPOSITORY ||
      !(event.issue === null || positiveInteger(event.issue)) || !positiveInteger(event.pr) ||
      !(event.launchId === null || hasHex(event.launchId, SHA64)) ||
      typeof event.transaction !== "string" || !TRANSACTION.test(event.transaction) ||
      typeof event.queueTransaction !== "string" || !TRANSACTION.test(event.queueTransaction) ||
      !positiveInteger(event.runId) || !positiveInteger(event.runAttempt) || !positiveInteger(event.workflowId) ||
      !hasHex(event.workflowHead, SHA40) || !hasHex(event.candidate, SHA40) || !hasHex(event.base, SHA40) ||
      !(event.mergeSha === null || hasHex(event.mergeSha, SHA40)) || !hasHex(event.stateSha, SHA40) ||
      !(event.bindingSha === null || hasHex(event.bindingSha, SHA40)) ||
      !["preview", "candidate", "smoke"].includes(event.phase) ||
      !["success", "failure", "cancelled", "timed_out", "unknown"].includes(event.conclusion) ||
      !["gates_completed", "workflow_completed"].includes(event.assessment)) {
    throw fail("CI notification event failed schema validation");
  }
  if (typeof event.eventId !== "string" || !SHA64.test(event.eventId)) {
    throw fail("CI notification event id was invalid");
  }
  const emittedAt = isoUtc(event.emittedAt, "emittedAt");
  const expiresAt = isoUtc(event.expiresAt, "expiresAt");
  if (emittedAt !== event.emittedAt || expiresAt !== event.expiresAt ||
      Date.parse(expiresAt) - Date.parse(emittedAt) !== RETENTION_MS) {
    throw fail("CI notification event expiry must be exactly seven days after emission");
  }
  const expectedUrl = "https://github.com/" + REPOSITORY + "/actions/runs/" + event.runId +
    "/attempts/" + event.runAttempt;
  if (event.runUrl !== expectedUrl) throw fail("CI notification run URL did not match its run identity");
  if (event.eventId !== expectedEventId(event)) throw fail("CI notification event id did not match its identity");
  return event;
}

export function canonicalEvent(fields) {
  if (!isRecord(fields)) throw fail("CI notification event fields must be an object");
  if (Object.hasOwn(fields, "repository") && fields.repository !== REPOSITORY) {
    throw fail("CI notification repository did not match the configured repository");
  }
  const event = { version: 1, repository: REPOSITORY };
  for (const key of EVENT_KEYS) {
    if (["version", "eventId", "repository", "runUrl", "expiresAt"].includes(key)) continue;
    event[key] = ownDataValue(fields, key);
  }
  event.emittedAt = isoUtc(event.emittedAt, "emittedAt");
  const derivedExpiry = new Date(Date.parse(event.emittedAt) + RETENTION_MS).toISOString();
  if (Object.hasOwn(fields, "expiresAt")) {
    const suppliedExpiry = isoUtc(ownDataValue(fields, "expiresAt"), "expiresAt");
    if (suppliedExpiry !== derivedExpiry) throw fail("CI notification expiry must be exactly seven days after emission");
  }
  event.expiresAt = derivedExpiry;
  event.runUrl = "https://github.com/" + REPOSITORY + "/actions/runs/" + event.runId +
    "/attempts/" + event.runAttempt;
  if (Object.hasOwn(fields, "runUrl") && ownDataValue(fields, "runUrl") !== event.runUrl) {
    throw fail("CI notification run URL did not match its run identity");
  }
  event.eventId = expectedEventId(event);
  return validateEvent(event);
}

export function renderReport(input) {
  const event = validateEvent(input);
  const issueLine = event.issue === null ? "" : "Issue: #" + event.issue + "\n";
  const eventUrl = "https://github.com/" + REPOSITORY + "/blob/" + OUTBOX_BRANCH +
    "/events/" + event.eventId + ".json";
  const stateUrl = "https://github.com/" + REPOSITORY + "/blob/" + event.stateSha + "/queue.json";
  const bindingLine = event.bindingSha === null ? "" :
    "Registration blob: \x60" + event.bindingSha + "\x60 ([open registration](" +
    "https://github.com/" + REPOSITORY + "/blob/" + OUTBOX_BRANCH +
    "/registrations/pr-" + event.pr + ".json)).\n";
  const mergeLine = event.mergeSha === null ? "" : "Merge: \x60" + event.mergeSha + "\x60\n";
  const assessmentLine = event.assessment === "gates_completed"
    ? "Assessment: gates_completed; enclosing workflow completion is not implied.\n"
    : "Assessment: workflow_completed.\n";
  return "<!-- vera-ci-event:" + event.eventId + " -->\n" +
    "## CI event requires manual review\n\n" +
    issueLine +
    "PR: #" + event.pr + "\n" +
    "Transaction: \x60" + event.transaction + "\x60; queue transaction: \x60" + event.queueTransaction + "\x60.\n" +
    "Phase: " + event.phase + "; conclusion: " + event.conclusion + ".\n" +
    assessmentLine +
    "Run: " + event.runId + ", attempt " + event.runAttempt + "; workflow: " + event.workflowId + ".\n" +
    "Candidate: \x60" + event.candidate + "\x60\n" +
    "Base: \x60" + event.base + "\x60\n" +
    mergeLine +
    bindingLine +
    "Event: \x60" + event.eventId + "\x60 ([open immutable event](" + eventUrl + "))\n" +
    "Queue state: \x60" + event.stateSha + "\x60 ([open queue snapshot](" + stateUrl + "))\n" +
    "[Open workflow attempt](" + event.runUrl + ")\n\n" +
    "Automatic Codex message injection/resumption is disabled. This event grants no approval or merge authority. " +
    "The original Codex owner must independently inspect the run and current queue state, then follow the issue's existing acceptance procedure. " +
    "This status data authorizes no editing, repair, spending, claim, queue control, merge, approval, acceptance or closure.";
}

function safeDocumentPath(path) {
  if (typeof path !== "string" ||
      !(/^(?:events\/[0-9a-f]{64}|audit\/[0-9a-f]{64}|registrations\/pr-[1-9][0-9]*)\.json$/.test(path))) {
    throw fail("CI notification document path was invalid");
  }
  return path;
}

function jsonText(data) {
  let content;
  try {
    content = JSON.stringify(data);
  } catch {
    throw fail("CI notification document must be JSON serializable");
  }
  if (typeof content !== "string" || Buffer.byteLength(content, "utf8") > MAX_DOCUMENT_BYTES) {
    throw fail("CI notification document exceeded 64 KiB or was not JSON serializable");
  }
  return content;
}

function decodeBase64Document(file) {
  if (file?.encoding !== "base64" || typeof file.content !== "string") {
    throw fail("CI notification document had an invalid encoding");
  }
  const encoded = file.content.replace(/\s/g, "");
  if (encoded.length > Math.ceil((MAX_DOCUMENT_BYTES * 4) / 3) + 4 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw fail("CI notification document contained invalid base64 or exceeded 64 KiB");
  }
  const bytes = Buffer.from(encoded, "base64");
  if (bytes.length > MAX_DOCUMENT_BYTES || bytes.toString("base64") !== encoded) {
    throw fail("CI notification document contained invalid base64 or exceeded 64 KiB");
  }
  let content;
  try {
    content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw fail("CI notification document was not valid UTF-8");
  }
  let data;
  try {
    data = JSON.parse(content);
  } catch {
    throw fail("CI notification document was not valid JSON");
  }
  if (typeof file.sha !== "string" || !SHA40.test(file.sha)) {
    throw fail("CI notification document blob id was invalid");
  }
  return { data, sha: file.sha, content };
}

function isRetryable(error) {
  return !Number.isInteger(error?.status) || error.status === 408 || error.status === 409 ||
    error.status === 422 || error.status === 429 || error.status >= 500;
}

function boundedHttpStatus(error) {
  return Number.isSafeInteger(error?.status) && error.status >= 400 && error.status <= 599 ? error.status : null;
}

async function backoff(attempt) {
  const duration = BACKOFF_MS[attempt - 1];
  if (duration) await delay(duration);
}

function nextAttemptAt(now, attempts) {
  const duration = BACKOFF_MS[Math.min(Math.max(attempts - 1, 0), BACKOFF_MS.length - 1)];
  const timestamp = now();
  if (!Number.isFinite(timestamp)) throw fail("CI notification clock returned an invalid time");
  return new Date(timestamp + duration).toISOString();
}

function commentMarker(eventId) {
  return "<!-- vera-ci-event:" + eventId + " -->";
}

function auditDocument(eventId, {
  status = "persisted",
  eventWriteAttempts = 0,
  commentAttempts = 0,
  manualRetryUsed = false,
  nextAttempt = null,
  lastOutcome = "none",
  commentHttpStatus = null,
  commentIssue = null,
} = {}) {
  return validateAudit({
    version: 1,
    eventId,
    status,
    eventWriteAttempts,
    commentAttempts,
    manualRetryUsed,
    nextAttemptAt: nextAttempt,
    lastOutcome,
    commentHttpStatus,
    commentIssue,
  }, eventId);
}

export class NotificationOutbox {
  constructor(github, { now = Date.now } = {}) {
    if (!github || github.repository !== REPOSITORY || typeof github.api !== "function") {
      throw fail("Notification outbox requires the configured authenticated GitHub client");
    }
    if (typeof now !== "function") throw fail("Notification outbox clock must be a function");
    this.github = github;
    this.now = now;
  }

  api(method, suffix, body) {
    return this.github.api(method, ROOT + suffix, body);
  }

  async #getRef() {
    try {
      const ref = await this.api("GET", "/git/ref/heads/" + OUTBOX_BRANCH);
      if (typeof ref?.object?.sha !== "string" || !SHA40.test(ref.object.sha)) {
        throw fail("CI notification outbox reference was invalid");
      }
      return ref.object.sha;
    } catch (error) {
      if (error?.status === 404) return null;
      throw error;
    }
  }

  async ensureBranch() {
    const existing = await this.#getRef();
    if (existing) return { sha: existing, created: false };

    const marker = await this.api("POST", "/git/blobs", {
      content: '{"version":1,"kind":"vera-ci-notification-outbox"}',
      encoding: "utf-8",
    });
    if (typeof marker?.sha !== "string" || !SHA40.test(marker.sha)) {
      throw fail("Could not create the CI notification outbox marker");
    }
    const tree = await this.api("POST", "/git/trees", {
      tree: [{ path: "outbox.json", mode: "100644", type: "blob", sha: marker.sha }],
    });
    if (typeof tree?.sha !== "string" || !SHA40.test(tree.sha)) {
      throw fail("Could not initialize the empty CI notification outbox tree");
    }
    const commit = await this.api("POST", "/git/commits", {
      message: "Initialize CI notification outbox",
      tree: tree.sha,
      parents: [],
    });
    if (typeof commit?.sha !== "string" || !SHA40.test(commit.sha)) {
      throw fail("Could not initialize the CI notification outbox commit");
    }
    try {
      await this.api("POST", "/git/refs", { ref: "refs/heads/" + OUTBOX_BRANCH, sha: commit.sha });
      return { sha: commit.sha, created: true };
    } catch (error) {
      const raced = await this.#getRef();
      if (raced) return { sha: raced, created: false };
      throw error;
    }
  }

  #contentsPath(path) {
    return "/contents/" + safeDocumentPath(path) + "?ref=" + OUTBOX_BRANCH;
  }

  async #readFile(path) {
    safeDocumentPath(path);
    try {
      return decodeBase64Document(await this.api("GET", this.#contentsPath(path)));
    } catch (error) {
      if (error?.status === 404) return null;
      throw error;
    }
  }

  async readDocument(path) {
    const file = await this.#readFile(path);
    return file ? { data: file.data, sha: file.sha } : null;
  }

  async writeDocument(path, data, options = {}) {
    safeDocumentPath(path);
    await this.ensureBranch();
    const content = jsonText(data);
    const immutable = path.startsWith("events/");
    const hasExpectedSha = Object.hasOwn(options, "expectedSha");
    const expectedSha = options.expectedSha;
    if (hasExpectedSha && expectedSha !== null && (typeof expectedSha !== "string" || !SHA40.test(expectedSha))) {
      throw fail("Expected CI notification document blob id was invalid");
    }
    if (!immutable && path.startsWith("registrations/") && !hasExpectedSha) {
      throw fail("Updating a CI notification registration requires its expected blob id");
    }

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      const existing = await this.#readFile(path);
      if (existing?.content === content) return { sha: existing.sha, stored: false, attempts: attempt - 1 };
      if (immutable && existing) throw fail("Immutable CI notification event path contained different content", "conflict");
      if (hasExpectedSha && (existing?.sha ?? null) !== expectedSha) {
        throw fail("CI notification document changed before compare-and-swap", "conflict");
      }
      if (attempt === 1 && !hasExpectedSha && path.startsWith("audit/") && existing) {
        throw fail("Updating a CI notification audit requires its expected blob id");
      }

      const body = {
        message: "Update CI notification " + (path.startsWith("events/") ? "event" :
          path.startsWith("audit/") ? "audit" : "registration"),
        content: Buffer.from(content, "utf8").toString("base64"),
        branch: OUTBOX_BRANCH,
      };
      if (existing) body.sha = existing.sha;
      try {
        const result = await this.api("PUT", this.#contentsPath(path), body);
        const blobSha = result?.content?.sha;
        if (typeof blobSha === "string" && SHA40.test(blobSha)) return { sha: blobSha, stored: true, attempts: attempt };
        const reconciled = await this.#readFile(path);
        if (reconciled?.content === content) return { sha: reconciled.sha, stored: true, attempts: attempt };
        if (reconciled && immutable) throw fail("Immutable CI notification event path contained different content", "conflict");
        throw fail("CI notification document write could not be confirmed", "pending");
      } catch (error) {
        if (error?.code === "conflict") throw error;
        let reconciled;
        try {
          reconciled = await this.#readFile(path);
        } catch {
          throw fail("CI notification document write outcome could not be reconciled", "pending");
        }
        if (reconciled?.content === content) {
          return {
            sha: reconciled.sha,
            stored: !(hasExpectedSha && [409, 422].includes(error.status)),
            attempts: attempt,
          };
        }
        if (reconciled && immutable) throw fail("Immutable CI notification event path contained different content", "conflict");
        if (hasExpectedSha && (reconciled?.sha ?? null) !== expectedSha) {
          throw fail("CI notification document changed during compare-and-swap", "conflict");
        }
        if (!isRetryable(error) || attempt === MAX_ATTEMPTS) throw error;
        await backoff(attempt);
      }
    }
    throw fail("CI notification document retries were exhausted", "pending");
  }

  async #findBotComment(pr, marker) {
    for (let page = 1; page <= 100; page += 1) {
      const comments = await this.api(
        "GET",
        "/issues/" + pr + "/comments?per_page=100&page=" + page,
      );
      if (!Array.isArray(comments)) throw fail("GitHub returned an invalid CI notification comment page");
      const found = comments.find((comment) =>
        comment?.user?.login === BOT_LOGIN && typeof comment.body === "string" && comment.body.includes(marker),
      );
      if (found) return found;
      if (comments.length < 100) return null;
    }
    throw fail("CI notification comment listing exceeded its 100-page limit");
  }

  async #saveAudit(event, previous, next) {
    validateAudit(next, event.eventId, event);
    return this.writeDocument("audit/" + event.eventId + ".json", next, {
      expectedSha: previous?.sha ?? null,
    });
  }

  async #updateAudit(event, previous, next) {
    try {
      const saved = await this.#saveAudit(event, previous, next);
      return { data: next, sha: saved.sha, stored: saved.stored };
    } catch (error) {
      if (error?.code !== "conflict") throw error;
      const latest = await this.#loadAudit(event.eventId, event);
      if (!latest) throw error;
      return { ...latest, stored: false };
    }
  }

  async #loadAudit(eventId, event) {
    const file = await this.#readFile("audit/" + eventId + ".json");
    if (!file) return null;
    return { data: validateAudit(file.data, eventId, event), sha: file.sha };
  }

  #result(event, audit, persisted = true) {
    const status = audit.status === "commented" ? "commented" :
      audit.status === "failed" ? "failed" : "pending";
    return {
      eventId: event.eventId,
      persisted,
      status,
      attempts: {
        eventWrite: audit.eventWriteAttempts,
        commentPost: audit.commentAttempts,
      },
      commentHttpStatus: audit.commentHttpStatus,
      commentIssue: audit.commentIssue,
      reportUrl: audit.status === "commented" && audit.commentIssue !== null
        ? "https://github.com/" + REPOSITORY + "/issues/" + audit.commentIssue
        : null,
      nextAttemptAt: audit.nextAttemptAt,
      manualRetryAvailable: persisted && audit.commentAttempts <= 1 && !audit.manualRetryUsed &&
        audit.status !== "commented" && audit.status !== "posting" && audit.lastOutcome !== "rejected" &&
        Date.parse(event.expiresAt) > this.now(),
      manualReport: status === "commented" ? null : renderReport(event),
    };
  }

  async #fallbackComment(event, previous, primaryStatus, marker, manual = false, enforceBackoff = false) {
    const issue = event.issue;
    let existing;
    try {
      existing = await this.#findBotComment(issue, marker);
    } catch {
      const pending = auditDocument(event.eventId, {
        ...previous.data,
        status: "pending",
        commentHttpStatus: primaryStatus,
        commentIssue: issue,
        nextAttempt: nextAttemptAt(this.now, previous.data.commentAttempts),
        lastOutcome: "ambiguous",
      });
      return (await this.#updateAudit(event, previous, pending)).data;
    }
    if (existing) {
      const reconciled = auditDocument(event.eventId, {
        ...previous.data,
        status: "commented",
        commentHttpStatus: primaryStatus,
        commentIssue: issue,
        nextAttempt: null,
        lastOutcome: "found",
      });
      return (await this.#updateAudit(event, previous, reconciled)).data;
    }
    if (enforceBackoff && previous.data.nextAttemptAt &&
        Date.parse(previous.data.nextAttemptAt) > this.now()) return previous.data;
    if (previous.data.commentAttempts >= 2) return previous.data;

    const claimData = auditDocument(event.eventId, {
      ...previous.data,
      status: "posting",
      commentAttempts: previous.data.commentAttempts + 1,
      manualRetryUsed: previous.data.manualRetryUsed || manual,
      commentHttpStatus: primaryStatus,
      commentIssue: issue,
      nextAttempt: nextAttemptAt(this.now, previous.data.commentAttempts + 1),
      lastOutcome: "none",
    });
    const claim = await this.#updateAudit(event, previous, claimData);
    if (!claim.stored) return claim.data;
    return this.#publishComment(event, claim, issue, marker);
  }

  async #resumeFallback(event, pending, primaryStatus, marker, manual, enforceBackoff = false) {
    let existing;
    try {
      existing = await this.#findBotComment(event.pr, marker);
    } catch {
      return pending.data;
    }
    if (existing) {
      const reconciled = auditDocument(event.eventId, {
        ...pending.data,
        status: "commented",
        commentHttpStatus: primaryStatus,
        commentIssue: event.pr,
        nextAttempt: null,
        lastOutcome: "found",
      });
      return (await this.#updateAudit(event, pending, reconciled)).data;
    }
    return this.#fallbackComment(event, pending, primaryStatus, marker, manual, enforceBackoff);
  }

  async #publishComment(event, claim, issue, marker, manual = false) {
    try {
      await this.api("POST", "/issues/" + issue + "/comments", { body: renderReport(event) });
      const posted = auditDocument(event.eventId, {
        ...claim.data,
        status: "commented",
        commentHttpStatus: issue === event.pr ? null : claim.data.commentHttpStatus,
        commentIssue: issue,
        nextAttempt: null,
        lastOutcome: "posted",
      });
      return (await this.#updateAudit(event, claim, posted)).data;
    } catch (error) {
      const rejectedStatus = boundedHttpStatus(error);
      if (issue === event.pr && [403, 404].includes(rejectedStatus) &&
          event.issue !== null && event.issue !== event.pr && claim.data.commentAttempts < 2) {
        const pendingData = auditDocument(event.eventId, {
          ...claim.data,
          status: "pending",
          commentHttpStatus: rejectedStatus,
          commentIssue: event.issue,
          nextAttempt: nextAttemptAt(this.now, claim.data.commentAttempts),
          lastOutcome: "ambiguous",
        });
        const pending = await this.#updateAudit(event, claim, pendingData);
        if (!pending.stored) return pending.data;
        return this.#resumeFallback(event, pending, rejectedStatus, marker, manual);
      }

      let existing = null;
      let listingSucceeded = true;
      try {
        existing = await this.#findBotComment(issue, marker);
      } catch {
        listingSucceeded = false;
      }
      const httpStatus = issue === event.pr
        ? rejectedStatus
        : claim.data.commentHttpStatus ?? rejectedStatus;
      if (existing) {
        const reconciled = auditDocument(event.eventId, {
          ...claim.data,
          status: "commented",
          commentHttpStatus: httpStatus,
          commentIssue: issue,
          nextAttempt: null,
          lastOutcome: "found",
        });
        return (await this.#updateAudit(event, claim, reconciled)).data;
      }
      const ambiguous = !listingSucceeded || isRetryable(error);
      const finalAudit = auditDocument(event.eventId, {
        ...claim.data,
        status: ambiguous ? "pending" : "failed",
        commentHttpStatus: httpStatus,
        commentIssue: issue,
        nextAttempt: ambiguous ? nextAttemptAt(this.now, claim.data.commentAttempts) : null,
        lastOutcome: ambiguous ? "ambiguous" : "rejected",
      });
      return (await this.#updateAudit(event, claim, finalAudit)).data;
    }
  }

  async #postComment(event, auditFile, manual = false) {
    const marker = commentMarker(event.eventId);
    const issue = auditFile.data.commentIssue ?? event.pr;
    if (manual && auditFile.data.status === "posting") {
      const targets = issue === event.pr ? [issue] : [issue, event.pr];
      for (const target of targets) {
        let existing;
        try {
          existing = await this.#findBotComment(target, marker);
        } catch {
          continue;
        }
        if (!existing) continue;
        const reconciled = auditDocument(event.eventId, {
          ...auditFile.data,
          status: "commented",
          commentHttpStatus: target === event.pr ? null : auditFile.data.commentHttpStatus,
          commentIssue: target,
          nextAttempt: null,
          lastOutcome: "found",
        });
        return (await this.#updateAudit(event, auditFile, reconciled)).data;
      }
      return auditFile.data;
    }
    if (manual && event.issue !== null && event.issue !== event.pr && issue === event.issue &&
        auditFile.data.commentAttempts === 1 && [403, 404].includes(auditFile.data.commentHttpStatus)) {
      return this.#resumeFallback(
        event,
        auditFile,
        auditFile.data.commentHttpStatus,
        marker,
        true,
        true,
      );
    }
    let existing;
    try {
      existing = await this.#findBotComment(issue, marker);
    } catch {
      const pending = auditDocument(event.eventId, {
        ...auditFile.data,
        status: "pending",
        nextAttempt: nextAttemptAt(this.now, Math.max(auditFile.data.commentAttempts, 1)),
      });
      return (await this.#updateAudit(event, auditFile, pending)).data;
    }
    if (existing) {
      const reconciled = auditDocument(event.eventId, {
        ...auditFile.data,
        status: "commented",
        commentHttpStatus: issue === event.pr ? null : auditFile.data.commentHttpStatus,
        commentIssue: issue,
        nextAttempt: null,
        lastOutcome: "found",
      });
      return (await this.#updateAudit(event, auditFile, reconciled)).data;
    }

    if ((!manual && auditFile.data.commentAttempts > 0) ||
        (manual && (auditFile.data.manualRetryUsed || auditFile.data.commentAttempts > 1 ||
          ["rejected", "ambiguous"].includes(auditFile.data.lastOutcome)))) {
      return auditFile.data;
    }
    if (manual && auditFile.data.nextAttemptAt && Date.parse(auditFile.data.nextAttemptAt) > this.now()) {
      return auditFile.data;
    }

    const inFlight = auditDocument(event.eventId, {
      ...auditFile.data,
      status: "posting",
      commentAttempts: auditFile.data.commentAttempts + 1,
      manualRetryUsed: auditFile.data.manualRetryUsed || manual,
      commentHttpStatus: issue === event.pr ? null : auditFile.data.commentHttpStatus,
      commentIssue: issue,
      nextAttempt: nextAttemptAt(this.now, auditFile.data.commentAttempts + 1),
      lastOutcome: "none",
    });
    const claim = await this.#updateAudit(event, auditFile, inFlight);
    if (!claim.stored) return claim.data;
    return this.#publishComment(event, claim, issue, marker, manual);
  }

  async publish(input) {
    const event = validateEvent(input);
    const now = this.now();
    if (!Number.isFinite(now)) throw fail("CI notification clock returned an invalid time");
    if (Date.parse(event.expiresAt) <= now) throw fail("Expired CI notification events cannot be published");
    await this.ensureBranch();
    const write = await this.writeDocument("events/" + event.eventId + ".json", event, { expectedSha: null });
    let auditFile = await this.#loadAudit(event.eventId, event);
    if (auditFile) {
      if (auditFile.data.eventWriteAttempts < write.attempts) {
        const updated = auditDocument(event.eventId, {
          ...auditFile.data,
          eventWriteAttempts: write.attempts,
        });
        auditFile = await this.#updateAudit(event, auditFile, updated);
      }
    } else {
      const initial = auditDocument(event.eventId, {
        status: "persisted",
        eventWriteAttempts: write.attempts,
      });
      auditFile = await this.#updateAudit(event, null, initial);
    }
    const audit = await this.#postComment(event, auditFile, false);
    return this.#result(event, audit);
  }

  async manualRetry(eventId) {
    if (typeof eventId !== "string" || !SHA64.test(eventId)) throw fail("CI notification event id was invalid");
    const stored = await this.read(eventId);
    if (!stored) throw fail("CI notification event was not found");
    if (Date.parse(stored.event.expiresAt) <= this.now()) throw fail("Expired CI notification events cannot be retried");
    const auditFile = await this.#loadAudit(eventId, stored.event);
    if (!auditFile) throw fail("CI notification audit was not found");
    const audit = await this.#postComment(stored.event, auditFile, true);
    return this.#result(stored.event, audit);
  }

  async read(eventId) {
    if (typeof eventId !== "string" || !SHA64.test(eventId)) throw fail("CI notification event id was invalid");
    const file = await this.#readFile("events/" + eventId + ".json");
    if (!file) return null;
    const event = validateEvent(file.data);
    if (event.eventId !== eventId || JSON.stringify(event) !== file.content) {
      throw fail("CI notification event content was not canonical");
    }
    const history = await this.api(
      "GET",
      "/commits?path=events/" + eventId + ".json&sha=" + OUTBOX_BRANCH + "&per_page=1",
    );
    const latest = Array.isArray(history) ? history[0] : null;
    if (!latest || typeof latest.sha !== "string" || !SHA40.test(latest.sha) ||
        latest.author?.login !== BOT_LOGIN) {
      throw fail("CI notification event commit did not have authenticated bot provenance");
    }
    return {
      event,
      blobSha: file.sha,
      provenance: { commitSha: latest.sha, author: BOT_LOGIN },
    };
  }
}
