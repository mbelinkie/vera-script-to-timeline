import assert from "node:assert/strict";
import test from "node:test";
import { assessRun } from "./ci-queue-policy.ts";

const expected = {
  title: "Validate queued transaction 1",
  workflowId: 123,
  workflowHead: "abcdef123456",
  startedAt: 100_000,
  timeoutMs: 1_800_000,
};

function run(overrides = {}) {
  return {
    id: 321,
    display_title: expected.title,
    workflow_id: expected.workflowId,
    head_sha: expected.workflowHead,
    event: "workflow_dispatch",
    path: ".github/workflows/validate.yml",
    run_attempt: 1,
    status: "completed",
    conclusion: "success",
    html_url: "https://github.com/openai/vera/actions/runs/321",
    actor: { login: "github-actions[bot]" },
    ...overrides,
  };
}

const pause = (result, reason) => assert.deepEqual(result, { kind: "pause", reason });

test("accepts the exact completed successful default workflow run", () => {
  assert.deepEqual(assessRun(expected, [run()], 200_000), {
    kind: "passed",
    runId: 321,
    url: "https://github.com/openai/vera/actions/runs/321",
  });
});

test("ignores runs with a different display title", () => {
  assert.deepEqual(assessRun(expected, [run({ display_title: "other dispatch" })], 200_000), {
    kind: "wait",
  });
});

test("waits when the exact title has not appeared yet", () => {
  assert.deepEqual(assessRun(expected, [], 200_000), { kind: "wait" });
});

test("waits for a missing title at exactly 120 seconds", () => {
  assert.deepEqual(assessRun(expected, [], expected.startedAt + 120_000), { kind: "wait" });
});

test("pauses when the title is still missing after 120 seconds", () => {
  pause(assessRun(expected, [], expected.startedAt + 120_001), "missing");
});

test("pauses when more than one run has the exact title", () => {
  pause(assessRun(expected, [run(), run({ id: 322 })], 200_000), "ambiguous");
});

test("pauses for a non-finite current time", () => {
  pause(assessRun(expected, [run()], Number.NaN), "invalid_time");
});

test("pauses for a non-finite start time", () => {
  pause(assessRun({ ...expected, startedAt: Number.POSITIVE_INFINITY }, [run()], 200_000), "invalid_time");
});

test("pauses when the expected start time is in the future", () => {
  pause(assessRun({ ...expected, startedAt: 200_001 }, [run()], 200_000), "future_start");
});

test("pauses when a matching result is older than its timeout", () => {
  pause(assessRun(expected, [run()], expected.startedAt + expected.timeoutMs + 1), "timeout");
});

for (const [field, value] of [
  ["workflow_id", expected.workflowId + 1],
  ["head_sha", "different-sha"],
  ["event", "push"],
  ["path", ".github/workflows/other.yml"],
  ["run_attempt", 2],
  ["actor", { login: "someone-else" }],
]) {
  test(`pauses when ${field} does not match the expected workflow identity`, () => {
    pause(assessRun(expected, [run({ [field]: value })], 200_000), "identity_mismatch");
  });
}

for (const id of [0, -1, 1.5, Number.NaN, Number.MAX_SAFE_INTEGER + 1]) {
  test(`pauses when run id ${String(id)} is not a positive safe integer`, () => {
    pause(assessRun(expected, [run({ id })], 200_000), "invalid_run_reference");
  });
}

for (const url of [
  "http://github.com/openai/vera/actions/runs/321",
  "https://github.com.evil.example/openai/vera/actions/runs/321",
  "https://github.com@evil.example/openai/vera/actions/runs/321",
  "https://github.com",
  "not a URL",
]) {
  test(`pauses for untrusted run URL ${url}`, () => {
    pause(assessRun(expected, [run({ html_url: url })], 200_000), "invalid_run_reference");
  });
}

for (const status of ["queued", "in_progress", "waiting", "requested", "pending"]) {
  test(`waits while the exact run is ${status}`, () => {
    assert.deepEqual(assessRun(expected, [run({ status, conclusion: null })], 200_000), {
      kind: "wait",
      runId: 321,
      url: "https://github.com/openai/vera/actions/runs/321",
    });
  });
}

test("pauses when a completed run failed", () => {
  pause(assessRun(expected, [run({ conclusion: "failure" })], 200_000), "not_successful");
});

test("pauses when a completed run was cancelled", () => {
  pause(assessRun(expected, [run({ conclusion: "cancelled" })], 200_000), "not_successful");
});

test("pauses when a completed run timed out", () => {
  pause(assessRun(expected, [run({ conclusion: "timed_out" })], 200_000), "not_successful");
});

test("pauses when a completed run has no conclusion", () => {
  pause(assessRun(expected, [run({ conclusion: null })], 200_000), "not_successful");
});

test("pauses for an unrecognized run status", () => {
  pause(assessRun(expected, [run({ status: "dequeued" })], 200_000), "unknown_status");
});
