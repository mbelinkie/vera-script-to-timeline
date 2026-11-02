import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { validateEvent } from "./ci-notification-outbox.mjs";

export const PRODUCTION_INJECTION_ENABLED = false;

const REPOSITORY = "mbelinkie/vera-script-to-timeline";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const EVENT_FIELDS = [
  "version", "eventId", "repository", "issue", "pr", "launchId", "transaction", "queueTransaction", "runId",
  "runAttempt", "workflowId", "workflowHead", "candidate", "base", "mergeSha", "stateSha", "bindingSha", "phase",
  "conclusion", "assessment", "emittedAt", "expiresAt", "runUrl",
];
const STATE_FIELDS = ["persisted", "queue_intent", "queued", "ack_observed", "auto_woke", "reviewed", "accepted", "failed", "unknown"];
const AUTHORITY = Object.freeze({ edit: false, repair: false, spend: false, claim: false, resumeCI: false, merge: false, approve: false, accept: false, close: false });

function exactKeys(value, fields) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    Reflect.ownKeys(value).length === fields.length && fields.every((field) => Object.hasOwn(value, field));
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString();
}

function fixedContent(event) {
  return Object.freeze({
    type: "machine_status_only",
    eventId: event.eventId,
    repository: REPOSITORY,
    issue: event.issue,
    pr: event.pr,
    run: Object.freeze({
      id: event.runId,
      attempt: event.runAttempt,
      workflowId: event.workflowId,
      workflowHead: event.workflowHead,
      candidate: event.candidate,
      base: event.base,
      mergeSha: event.mergeSha,
      phase: event.phase,
      conclusion: event.conclusion,
      assessment: event.assessment,
      completionScope: event.assessment === "gates_completed" ? "validation_gates" : "workflow_completed",
      url: event.runUrl,
    }),
    emittedAt: event.emittedAt,
    expiresAt: event.expiresAt,
    authority: AUTHORITY,
  });
}

export function fixedEnvelope(event) {
  validateEvent(event);
  return fixedContent(event);
}

function sameEvent(left, right) {
  return EVENT_FIELDS.every((field) => left[field] === right[field]);
}

function callbackOutcome(error) {
  const code = String(error?.code ?? "").toLowerCase();
  if (["busy", "locked", "eagain"].includes(code)) return "busy";
  if (["writer_conflict", "conflict", "cas_conflict"].includes(code)) return "writer_conflict";
  if (["offline", "enetdown", "enetunreach", "ehostunreach", "enotfound", "econnreset", "etimedout"].includes(code)) return "offline";
  return "failed";
}

function result(outcome, warningCode, extra = {}) {
  return { status: "manual_disabled", outcome, warningCode, ...extra };
}

function matchesOrigin(origin, event) {
  return event.launchId !== null && event.bindingSha !== null && origin && typeof origin === "object" &&
    origin.repository === REPOSITORY && origin.issue === event.issue && origin.pr === event.pr &&
    origin.launchId === event.launchId && typeof origin.threadId === "string" && UUID.test(origin.threadId);
}

function newRecord(event, content, threadId, timestamp, state = null) {
  return {
    version: 1,
    event,
    content,
    threadId,
    states: {
      persisted: timestamp,
      queue_intent: null,
      queued: null,
      ack_observed: null,
      auto_woke: null,
      reviewed: null,
      accepted: null,
      failed: state === "expired" ? { at: timestamp, reason: "event_expired" } : null,
      unknown: state && state !== "expired" ? { at: timestamp, reason: state } : null,
    },
  };
}

function validAudit(audit) {
  if (audit === null || audit === undefined) return { version: 1, entries: [] };
  if (!exactKeys(audit, ["version", "entries"]) || audit.version !== 1 || !Array.isArray(audit.entries) || audit.entries.length > 500) {
    throw new Error("audit_invalid");
  }
  for (const entry of audit.entries) {
    if (!exactKeys(entry, ["version", "event", "content", "threadId", "states"]) || entry.version !== 1 ||
        !exactKeys(entry.states, STATE_FIELDS) || !EVENT_FIELDS.every((field) => Object.hasOwn(entry.event ?? {}, field))) {
      throw new Error("audit_invalid");
    }
    validateEvent(entry.event);
    if (!exactKeys(entry.content, ["type", "eventId", "repository", "issue", "pr", "run", "emittedAt", "expiresAt", "authority"]) ||
        !exactKeys(entry.content.run, ["id", "attempt", "workflowId", "workflowHead", "candidate", "base", "mergeSha", "phase", "conclusion", "assessment", "completionScope", "url"]) ||
        !exactKeys(entry.content.authority, Object.keys(AUTHORITY)) || JSON.stringify(fixedContent(entry.event)) !== JSON.stringify(entry.content) ||
        (entry.threadId !== null && (typeof entry.threadId !== "string" || !UUID.test(entry.threadId))) ||
        !isTime(entry.states.persisted)) throw new Error("audit_invalid");
    const shapes = {
      queue_intent: ["at", "requestId"], queued: ["at", "requestId", "provenance"],
      ack_observed: ["at", "provenance", "turnId", "messageId"], auto_woke: ["at", "provenance", "evidenceId"],
      reviewed: ["at", "owner", "evidenceId"], accepted: ["at", "owner", "evidenceId"],
      failed: ["at", "reason"], unknown: ["at", "reason"],
    };
    for (const [name, fields] of Object.entries(shapes)) {
      const state = entry.states[name];
      if (state !== null && (!exactKeys(state, fields) || !isTime(state.at))) throw new Error("audit_invalid");
    }
  }
  return audit;
}

function threadUri(threadId) {
  return `codex://threads/${threadId}`;
}

export async function consumeEvent(event, { verify, findOrigin, loadAudit, saveAudit, now = Date.now } = {}) {
  let content;
  try {
    content = fixedEnvelope(event);
  } catch {
    return result("invalid_event", "CI_EVENT_INVALID");
  }
  if (typeof verify !== "function") return result("verification_unavailable", "CI_VERIFIER_REQUIRED");

  let verified;
  try {
    verified = await verify(event);
    validateEvent(verified);
    if (!sameEvent(event, verified)) return result("verification_failed", "CI_VERIFICATION_MISMATCH");
  } catch (error) {
    const reason = callbackOutcome(error) === "offline" ? "offline" : "verification_failed";
    return result(reason, reason === "offline" ? "CI_VERIFIER_OFFLINE" : "CI_VERIFICATION_REJECTED");
  }

  const clock = typeof now === "function" ? now() : now;
  const currentTime = clock instanceof Date ? clock.getTime() : clock;
  if (!Number.isSafeInteger(currentTime) || currentTime < 0) return result("clock_unavailable", "CI_CLOCK_INVALID");
  const timestamp = iso(currentTime);
  const expired = Date.parse(event.expiresAt) <= currentTime;
  let origin = null;
  let originVerified = false;
  let reason = expired ? "expired" : null;
  if (!expired) {
    if (typeof findOrigin !== "function") reason = "missing_mapping";
    else {
      try {
        origin = await findOrigin(verified);
        originVerified = matchesOrigin(origin, verified);
        if (!originVerified) reason = "missing_mapping";
      } catch (error) {
        reason = callbackOutcome(error);
      }
    }
  }
  if (typeof loadAudit !== "function" || typeof saveAudit !== "function") return result("audit_unavailable", "CI_AUDIT_REQUIRED");

  let audit;
  try {
    audit = validAudit(await loadAudit());
  } catch (error) {
    const failure = error?.message === "audit_invalid" ? "audit_invalid" : callbackOutcome(error);
    return result(failure, `CI_AUDIT_${failure.toUpperCase()}`);
  }

  const prior = audit.entries.find((entry) => entry.event.eventId === event.eventId);
  if (prior) {
    if (!sameEvent(prior.event, event)) return result("event_id_conflict", "CI_EVENT_ID_CONFLICT");
    return result(reason ?? "already_persisted", reason ? `CI_${reason.toUpperCase()}` : "CI_MAC_INJECTION_DISABLED",
      originVerified ? { navigation: threadUri(origin.threadId) } : {});
  }

  const record = newRecord(verified, content, matchesOrigin(origin, verified) ? origin.threadId : null, timestamp,
    reason === "expired" ? "expired" : reason);
  const next = { version: 1, entries: [...audit.entries, record] };
  try {
    const saved = await saveAudit(next, audit);
    if (saved === false || saved?.status === "writer_conflict") return result("writer_conflict", "CI_AUDIT_WRITER_CONFLICT");
    if (saved?.status === "busy") return result("busy", "CI_AUDIT_BUSY");
    if (saved?.status === "offline") return result("offline", "CI_AUDIT_OFFLINE");
  } catch (error) {
    const failure = callbackOutcome(error);
    return result(failure, `CI_AUDIT_${failure.toUpperCase()}`);
  }

  if (reason) return result(reason, `CI_${reason.toUpperCase()}`);
  return result("persisted", "CI_MAC_INJECTION_DISABLED", { navigation: threadUri(origin.threadId) });
}

const isUuid = (value) => typeof value === "string" && UUID.test(value);
const isMessageId = (value) => isUuid(value) || (typeof value === "string" && /^msg_[0-9a-f]{32,128}$/.test(value));
const isTime = (value) => typeof value === "string" && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value;

/** Records trusted adapter evidence only; it does not authenticate caller-supplied JSON or enable effects. */
export function reduceDeliveryState(current, action, now = Date.now) {
  if (!current || !exactKeys(current, ["version", "event", "content", "threadId", "states"]) || current.version !== 1 ||
      !exactKeys(current.states, STATE_FIELDS)) throw new Error("invalid delivery state");
  validAudit({ version: 1, entries: [current] });
  const next = { ...current, states: { ...current.states } };
  const states = next.states;
  const value = typeof now === "function" ? now() : now;
  const milliseconds = value instanceof Date ? value.getTime() : value;
  if (!Number.isSafeInteger(milliseconds) || milliseconds < 0) throw new Error("invalid clock");
  const timestamp = iso(milliseconds);

  if (action?.type === "queue_intent" && exactKeys(action, ["type", "requestId"])) {
    if (!isUuid(action.requestId) || states.queue_intent || states.queued || states.failed || states.unknown) throw new Error("queue intent cannot be retried");
    states.queue_intent = { at: timestamp, requestId: action.requestId };
  } else if (action?.type === "enqueue_result" && exactKeys(action, ["type", "outcome", "receipt"])) {
    if (!states.queue_intent || states.queued || states.failed || states.unknown) throw new Error("queue result has no pending intent");
    if (action.outcome === "ambiguous") states.unknown = { at: timestamp, reason: "enqueue_ambiguous" };
    else if (action.outcome === "rejected") states.failed = { at: timestamp, reason: "enqueue_rejected" };
    else if (action.outcome === "queued") {
      const receipt = action.receipt;
      if (!exactKeys(receipt, ["eventId", "requestId", "status", "provenance", "observedAt"]) ||
          receipt.eventId !== next.event.eventId || receipt.requestId !== states.queue_intent.requestId || receipt.status !== "queued" ||
          receipt.provenance !== "supported_cli_receipt" || !isTime(receipt.observedAt) || Date.parse(receipt.observedAt) <= Date.parse(states.queue_intent.at)) {
        throw new Error("queue receipt does not match intent");
      }
      states.queued = { at: receipt.observedAt, requestId: receipt.requestId, provenance: receipt.provenance };
    } else throw new Error("invalid queue result");
  } else if (action?.type === "ack_observed" && exactKeys(action, ["type", "evidence"])) {
    const evidence = action.evidence;
    if (!states.queued || states.ack_observed || states.failed || states.unknown ||
        !exactKeys(evidence, ["eventId", "threadId", "requestId", "sourceMessageAuthor", "provenance", "turnId", "messageId", "observedAt"]) ||
        evidence.eventId !== next.event.eventId || evidence.threadId !== next.threadId || evidence.requestId !== states.queue_intent.requestId ||
        evidence.sourceMessageAuthor !== "assistant" || !["producer_ui_observation", "supported_thread_api"].includes(evidence.provenance) ||
        !isUuid(evidence.turnId) || !isMessageId(evidence.messageId) || !isTime(evidence.observedAt) ||
        Date.parse(evidence.observedAt) <= Date.parse(states.queued.at)) throw new Error("ACK evidence does not match delivery");
    states.ack_observed = { at: evidence.observedAt, provenance: evidence.provenance, turnId: evidence.turnId, messageId: evidence.messageId };
  } else if (action?.type === "auto_woke" && exactKeys(action, ["type", "evidence"])) {
    const evidence = action.evidence;
    if (!states.ack_observed || states.auto_woke || !exactKeys(evidence, ["eventId", "threadId", "provenance", "evidenceId", "beforeOpen", "idle", "unloaded", "observedAt"]) ||
        evidence.eventId !== next.event.eventId || evidence.threadId !== next.threadId || evidence.provenance !== "producer_ui_observation" ||
        !isUuid(evidence.evidenceId) || evidence.beforeOpen !== true || evidence.idle !== true || evidence.unloaded !== true ||
        evidence.evidenceId === states.ack_observed.messageId || !isTime(evidence.observedAt) ||
        Date.parse(evidence.observedAt) <= Date.parse(states.ack_observed.at)) throw new Error("separate before-open idle/unloaded evidence required");
    states.auto_woke = { at: evidence.observedAt, provenance: evidence.provenance, evidenceId: evidence.evidenceId };
  } else if (["reviewed", "accepted"].includes(action?.type) && exactKeys(action, ["type", "evidence"])) {
    const evidence = action.evidence;
    const ownerEvidence = (evidence?.provenance === "producer_ui_observation" && evidence.owner === "producer") ||
      (evidence?.provenance === "original_owner_review" && evidence.owner === "original-codex-owner");
    if (!exactKeys(evidence, ["eventId", "threadId", "provenance", "owner", "evidenceId", "observedAt"]) ||
        evidence.eventId !== next.event.eventId || evidence.threadId !== next.threadId || !ownerEvidence ||
        !isUuid(evidence.evidenceId) || !isTime(evidence.observedAt)) throw new Error("owner evidence required");
    if (action.type === "reviewed") {
      if (states.reviewed || Date.parse(evidence.observedAt) <= Date.parse(states.persisted)) throw new Error("review needs separate evidence after persistence");
      states.reviewed = { at: evidence.observedAt, owner: evidence.owner, evidenceId: evidence.evidenceId };
    } else {
      if (!states.reviewed || states.accepted || Date.parse(evidence.observedAt) <= Date.parse(states.reviewed.at) ||
          evidence.evidenceId === states.reviewed.evidenceId) throw new Error("acceptance needs separate owner evidence after review");
      states.accepted = { at: evidence.observedAt, owner: evidence.owner, evidenceId: evidence.evidenceId };
    }
  } else throw new Error("unsupported delivery action");
  return next;
}

function invoke(executable, args, runner) {
  try {
    const result = runner(executable, args, { encoding: "utf8", timeout: 5000, maxBuffer: 64 * 1024, shell: false, windowsHide: true });
    return result && !result.error && !result.signal && result.status === 0
      ? { ok: true, text: `${result.stdout ?? ""}\n${result.stderr ?? ""}` }
      : { ok: false, timeout: result?.error?.code === "ETIMEDOUT" };
  } catch {
    return { ok: false, timeout: false };
  }
}

function hasFlag(help, flag) {
  return new RegExp(`(?:^|[\\s,])${flag}(?=[\\s=,]|$)`, "m").test(help);
}

export function inspectCli(executable, runner = spawnSync) {
  if (typeof executable !== "string" || !executable || /[\r\n\0]/.test(executable) || typeof runner !== "function") throw new Error("Codex executable and runner required");
  const versionResult = invoke(executable, ["--version"], runner);
  const helpResult = invoke(executable, ["queue", "--help"], runner);
  const version = versionResult.ok ? /\bcodex(?:-cli)?\s+(\d+\.\d+\.\d+)\b/i.exec(versionResult.text)?.[1] ?? null : null;
  const help = helpResult.ok ? helpResult.text : "";
  return {
    available: Boolean(version && helpResult.ok),
    version,
    supportsThread: helpResult.ok && hasFlag(help, "--thread"),
    supportsMessage: helpResult.ok && hasFlag(help, "--message"),
    supportsQueue: helpResult.ok && hasFlag(help, "--thread") && hasFlag(help, "--message"),
    supportsResume: helpResult.ok ? hasFlag(help, "--resume") : null,
    warningCode: !versionResult.ok ? (versionResult.timeout ? "CODEX_VERSION_TIMEOUT" : "CODEX_VERSION_UNAVAILABLE") :
      !helpResult.ok ? (helpResult.timeout ? "CODEX_QUEUE_HELP_TIMEOUT" : "CODEX_QUEUE_HELP_UNAVAILABLE") :
        !version ? "CODEX_VERSION_UNRECOGNIZED" : null,
  };
}

export function queueArguments(event, origin) {
  if (!matchesOrigin(origin, event)) throw new Error("registered thread mapping required");
  return ["queue", "--thread", origin.threadId, "--message", JSON.stringify(fixedEnvelope(event))];
}

export async function deliverRegisteredEvent(event, origin, {
  executable,
  runner = spawnSync,
  verify,
  findOrigin,
  loadAudit,
  saveAudit,
  now = Date.now,
} = {}) {
  if (!PRODUCTION_INJECTION_ENABLED) return result("manual_disabled", "CI_MAC_INJECTION_DISABLED");

  if (typeof verify !== "function" || typeof findOrigin !== "function") return result("verification_unavailable", "CI_VERIFIER_REQUIRED");
  let verified;
  let registeredOrigin;
  try {
    validateEvent(event);
    verified = await verify(event);
    validateEvent(verified);
    if (!sameEvent(event, verified)) return result("verification_failed", "CI_VERIFICATION_MISMATCH");
    const clock = typeof now === "function" ? now() : now;
    const currentTime = clock instanceof Date ? clock.getTime() : clock;
    if (!Number.isSafeInteger(currentTime) || currentTime < 0 || Date.parse(verified.expiresAt) <= currentTime) {
      return result("expired", "CI_EVENT_EXPIRED");
    }
    registeredOrigin = await findOrigin(verified);
    if (!matchesOrigin(registeredOrigin, verified) || registeredOrigin.threadId !== origin?.threadId) {
      return result("missing_mapping", "CI_ORIGIN_MISSING_MAPPING");
    }
  } catch (error) {
    const failure = callbackOutcome(error);
    return result(failure, `CI_VERIFICATION_${failure.toUpperCase()}`);
  }
  const args = queueArguments(verified, registeredOrigin);
  const capability = inspectCli(executable, runner);
  if (!capability.available || !capability.supportsQueue) return result("cli_unsupported", capability.warningCode ?? "CODEX_QUEUE_UNSUPPORTED");
  if (typeof loadAudit !== "function" || typeof saveAudit !== "function") return result("audit_unavailable", "CI_AUDIT_REQUIRED");

  let audit;
  try {
    audit = validAudit(await loadAudit());
  } catch (error) {
    const failure = callbackOutcome(error);
    return result(failure, `CI_AUDIT_${failure.toUpperCase()}`);
  }
  const index = audit.entries.findIndex((entry) => sameEvent(entry.event, event));
  if (index < 0 || audit.entries[index].threadId !== origin.threadId) return result("missing_mapping", "CI_ORIGIN_MISSING_MAPPING");
  const requestId = randomUUID();
  const intentRecord = reduceDeliveryState(audit.entries[index], { type: "queue_intent", requestId }, now);
  const intended = { version: 1, entries: [...audit.entries] };
  intended.entries[index] = intentRecord;
  try {
    const saved = await saveAudit(intended, audit);
    if (saved === false || ["writer_conflict", "busy", "offline"].includes(saved?.status)) {
      const failure = saved === false ? "writer_conflict" : saved.status;
      return result(failure, `CI_AUDIT_${failure.toUpperCase()}`);
    }
  } catch (error) {
    const failure = callbackOutcome(error);
    return result(failure, `CI_AUDIT_${failure.toUpperCase()}`);
  }

  // Exit status alone cannot authenticate admission, target or a new assistant turn.
  // A supported receipt/observer adapter must be qualified before activation.
  invoke(executable, args, runner);
  const nextRecord = reduceDeliveryState(intentRecord, { type: "enqueue_result", outcome: "ambiguous", receipt: null }, now);
  const nextAudit = { version: 1, entries: [...intended.entries] };
  nextAudit.entries[index] = nextRecord;
  try {
    const saved = await saveAudit(nextAudit, intended);
    if (saved === false || ["writer_conflict", "busy", "offline"].includes(saved?.status)) return result("unknown", "CI_QUEUE_RESULT_AUDIT_UNCONFIRMED");
  } catch {
    return result("unknown", "CI_QUEUE_RESULT_AUDIT_UNCONFIRMED");
  }
  return result("unknown", "CI_QUEUE_RESULT_AMBIGUOUS");
}
