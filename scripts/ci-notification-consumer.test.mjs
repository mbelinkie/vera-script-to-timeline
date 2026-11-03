import assert from "node:assert/strict";
import test from "node:test";
import { canonicalEvent } from "./ci-notification-outbox.mjs";
import {
  consumeEvent,
  fixedEnvelope,
  inspectCli,
  PRODUCTION_INJECTION_ENABLED,
  queueArguments,
  reduceDeliveryState,
} from "./ci-notification-consumer.mjs";

const repository = "mbelinkie/vera-script-to-timeline";
const sha = (letter) => letter.repeat(40);
const sha64 = (letter) => letter.repeat(64);
const threadId = "01234567-89ab-4cde-8fab-0123456789ab";
const requestId = "11234567-89ab-4cde-8fab-0123456789ab";
const nowMs = Date.parse("2026-11-02T17:30:00.000Z");
const iso = (time) => new Date(time).toISOString();

function event(fields = {}) {
  return canonicalEvent({
    issue: 398, pr: 410, launchId: sha64("b"), transaction: "dispatch-transaction", queueTransaction: "queue-transaction",
    runId: 900, runAttempt: 2, workflowId: 7, workflowHead: sha("c"), candidate: sha("d"), base: sha("e"), mergeSha: null,
    stateSha: sha("f"), bindingSha: sha("1"), phase: "candidate", conclusion: "success", assessment: "gates_completed",
    emittedAt: iso(nowMs - 10_000), ...fields,
  });
}

function origin(value) {
  return { repository, issue: value.issue, pr: value.pr, launchId: value.launchId, threadId };
}

function harness(overrides = {}) {
  const calls = [];
  const writes = [];
  return {
    calls,
    writes,
    dependencies: {
      verify: async (candidate) => { calls.push("verify"); return JSON.parse(JSON.stringify(candidate)); },
      findOrigin: async (candidate) => { calls.push("origin"); return origin(candidate); },
      loadAudit: async () => { calls.push("load"); return null; },
      saveAudit: async (audit) => { calls.push("save"); writes.push(audit); },
      now: () => nowMs,
      ...overrides,
    },
  };
}

async function persistedRecord(value = event()) {
  const h = harness();
  await consumeEvent(value, h.dependencies);
  return { record: h.writes[0].entries[0], harness: h };
}

test("fixedEnvelope only reports allowlisted machine status and distinguishes gates from workflow completion", () => {
  const report = fixedEnvelope(event());
  assert.equal(report.type, "machine_status_only");
  assert.equal(report.run.completionScope, "validation_gates");
  assert.ok(Object.values(report.authority).every((permission) => permission === false));
  assert.equal("launchId" in report, false);
  assert.equal("transaction" in report, false);
  assert.doesNotMatch(JSON.stringify(report), new RegExp(threadId));
  const args = queueArguments(event(), origin(event()));
  assert.deepEqual(args.slice(0, 4), ["queue", "--thread", threadId, "--message"]);
  assert.equal(JSON.parse(args[4]).type, "machine_status_only");
  assert.equal(args.includes("--resume"), false);
  assert.equal(fixedEnvelope(event({ assessment: "workflow_completed" })).run.completionScope, "workflow_completed");
  assert.throws(() => fixedEnvelope({ ...event(), extra: "raw PR text" }));
});

test("consumer verifies before persistence and stays disabled even when caller supplies enable or queue flags", async () => {
  assert.equal(PRODUCTION_INJECTION_ENABLED, false);
  const h = harness();
  let queueCalls = 0;
  const result = await consumeEvent(event(), {
    ...h.dependencies,
    enabled: true,
    production: true,
    enqueue: () => { queueCalls += 1; },
    resume: () => { queueCalls += 1; },
  });
  assert.equal(result.status, "manual_disabled");
  assert.equal(result.outcome, "persisted");
  assert.equal(result.navigation, `codex://threads/${threadId}`);
  assert.deepEqual(h.calls, ["verify", "origin", "load", "save"]);
  assert.equal(queueCalls, 0);
  assert.equal(h.writes[0].entries[0].states.queued, null);
  assert.doesNotMatch(JSON.stringify(h.writes[0].entries[0].content), new RegExp(threadId));
});

test("verification must return the canonical event before local state is read", async () => {
  for (const verify of [async () => true, async (value) => event({ stateSha: sha("9"), emittedAt: value.emittedAt })]) {
    let localCalls = 0;
    const result = await consumeEvent(event(), {
      verify,
      findOrigin: async () => { localCalls += 1; return null; },
      loadAudit: async () => { localCalls += 1; return null; },
      saveAudit: async () => { localCalls += 1; },
    });
    assert.equal(result.outcome, "verification_failed");
    assert.equal(localCalls, 0);
  }
  const offline = await consumeEvent(event(), { verify: async () => { const error = new Error(); error.code = "offline"; throw error; } });
  assert.equal(offline.outcome, "offline");
});

test("expiry and missing origin are recorded without inventing a thread target", async () => {
  const missing = harness({ findOrigin: async () => null });
  const missingResult = await consumeEvent(event(), missing.dependencies);
  assert.equal(missingResult.outcome, "missing_mapping");
  assert.equal("navigation" in missingResult, false);
  assert.equal(missing.writes[0].entries[0].states.unknown.reason, "missing_mapping");

  const value = event();
  const expired = harness({ now: () => Date.parse(value.expiresAt) + 1 });
  const expiredResult = await consumeEvent(value, expired.dependencies);
  assert.equal(expiredResult.outcome, "expired");
  assert.deepEqual(expired.calls, ["verify", "load", "save"]);
  assert.equal(expired.writes[0].entries[0].states.failed.reason, "event_expired");
});

test("temporary origin lookup failure is not persisted, so a later lookup can bind the private target", async () => {
  const value = event();
  let attempts = 0;
  const h = harness({ findOrigin: async (candidate) => {
    attempts += 1;
    if (attempts === 1) { const error = new Error(); error.code = "offline"; throw error; }
    return origin(candidate);
  } });

  const unavailable = await consumeEvent(value, h.dependencies);
  assert.equal(unavailable.outcome, "offline");
  assert.equal(h.writes.length, 0);
  assert.deepEqual(h.calls, ["verify"]);

  const recovered = await consumeEvent(value, h.dependencies);
  assert.equal(recovered.outcome, "persisted");
  assert.equal(recovered.navigation, `codex://threads/${threadId}`);
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].entries[0].threadId, threadId);
});

test("busy reads and writer conflicts remain visible without claiming persistence", async () => {
  const busy = harness({ loadAudit: async () => { const error = new Error(); error.code = "busy"; throw error; } });
  assert.equal((await consumeEvent(event(), busy.dependencies)).outcome, "busy");
  const conflict = harness({ saveAudit: async () => { const error = new Error(); error.code = "writer_conflict"; throw error; } });
  assert.equal((await consumeEvent(event(), conflict.dependencies)).outcome, "writer_conflict");
});

test("ambiguous enqueue is terminal; only a matching receipt admits queued and assistant ACK states", async () => {
  const { record } = await persistedRecord();
  const intent = reduceDeliveryState(record, { type: "queue_intent", requestId }, () => nowMs + 1000);
  const unknown = reduceDeliveryState(intent, { type: "enqueue_result", outcome: "ambiguous", receipt: null }, () => nowMs + 2000);
  assert.equal(unknown.states.unknown.reason, "enqueue_ambiguous");
  assert.throws(() => reduceDeliveryState(unknown, { type: "queue_intent", requestId }), /retried/);
  assert.throws(() => reduceDeliveryState(intent, { type: "enqueue_result", outcome: "queued", receipt: null }), /receipt/);

  const queued = reduceDeliveryState(intent, { type: "enqueue_result", outcome: "queued", receipt: {
    eventId: record.event.eventId, requestId, status: "queued", provenance: "supported_cli_receipt", observedAt: iso(nowMs + 2000),
  } }, () => nowMs + 3000);
  const evidence = {
    eventId: record.event.eventId, threadId, requestId, sourceMessageAuthor: "assistant", provenance: "supported_thread_api",
    turnId: "21234567-89ab-4cde-8fab-0123456789ab", messageId: "31234567-89ab-4cde-8fab-0123456789ab", observedAt: iso(nowMs + 4000),
  };
  assert.throws(() => reduceDeliveryState(queued, { type: "ack_observed", evidence: { ...evidence, sourceMessageAuthor: "user" } }), /ACK/);
  assert.equal(reduceDeliveryState(queued, { type: "ack_observed", evidence }).states.ack_observed.messageId, evidence.messageId);
  const apiMessageId = "msg_" + "a".repeat(48);
  assert.equal(reduceDeliveryState(queued, { type: "ack_observed", evidence: { ...evidence, messageId: apiMessageId } }).states.ack_observed.messageId, apiMessageId);
});

test("wake and owner acceptance need separate evidence", async () => {
  const { record } = await persistedRecord();
  const intent = reduceDeliveryState(record, { type: "queue_intent", requestId }, () => nowMs + 1000);
  const queued = reduceDeliveryState(intent, { type: "enqueue_result", outcome: "queued", receipt: {
    eventId: record.event.eventId, requestId, status: "queued", provenance: "supported_cli_receipt", observedAt: iso(nowMs + 2000),
  } });
  const acknowledged = reduceDeliveryState(queued, { type: "ack_observed", evidence: {
    eventId: record.event.eventId, threadId, requestId, sourceMessageAuthor: "assistant", provenance: "producer_ui_observation",
    turnId: "41234567-89ab-4cde-8fab-0123456789ab", messageId: "51234567-89ab-4cde-8fab-0123456789ab", observedAt: iso(nowMs + 3000),
  } });
  const wakeEvidence = { eventId: record.event.eventId, threadId, provenance: "producer_ui_observation",
    evidenceId: "61234567-89ab-4cde-8fab-0123456789ab", beforeOpen: true, idle: true, unloaded: true, observedAt: iso(nowMs + 4000) };
  assert.throws(() => reduceDeliveryState(acknowledged, { type: "auto_woke", evidence: { ...wakeEvidence, idle: false } }), /evidence/);
  const woken = reduceDeliveryState(acknowledged, { type: "auto_woke", evidence: wakeEvidence });
  const review = (evidenceId, observedAt) => ({ eventId: record.event.eventId, threadId,
    provenance: "producer_ui_observation", owner: "producer", evidenceId, observedAt: iso(observedAt) });
  const reviewed = reduceDeliveryState(woken, { type: "reviewed", evidence: review("71234567-89ab-4cde-8fab-0123456789ab", nowMs + 5000) });
  assert.throws(() => reduceDeliveryState(reviewed, { type: "accepted", evidence: review("71234567-89ab-4cde-8fab-0123456789ab", nowMs + 6000) }), /separate/);
  assert.ok(reduceDeliveryState(reviewed, { type: "accepted", evidence: review("81234567-89ab-4cde-8fab-0123456789ab", nowMs + 6000) }).states.accepted);
});

test("CLI check runs only bounded version/help queries and reports resume separately", () => {
  const calls = [];
  const info = inspectCli("/installed/codex", (executable, args, options) => {
    calls.push({ args, options });
    return args[0] === "--version"
      ? { status: 0, stdout: "codex-cli 0.160.0\n" }
      : { status: 0, stdout: "queue --thread THREAD --message MESSAGE\n" };
  });
  assert.equal(info.available, true);
  assert.equal(info.supportsQueue, true);
  assert.equal(info.supportsResume, false);
  assert.deepEqual(calls.map((call) => call.args), [["--version"], ["queue", "--help"]]);
  assert.ok(calls.every((call) => call.options.shell === false && call.options.timeout === 5000));
});

test("original owner can record manual review without queueing or waking a model", async () => {
  const { record } = await persistedRecord();
  const reviewed = reduceDeliveryState(record, { type: "reviewed", evidence: {
    eventId: record.event.eventId, threadId, provenance: "original_owner_review", owner: "original-codex-owner",
    evidenceId: "71234567-89ab-4cde-8fab-0123456789ab", observedAt: iso(nowMs + 1000),
  } });
  assert.ok(reviewed.states.reviewed);
  assert.equal(reviewed.states.queued, null);
  assert.equal(reviewed.states.auto_woke, null);
  assert.equal(reviewed.states.accepted, null);
});
