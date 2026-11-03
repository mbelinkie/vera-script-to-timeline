import assert from "node:assert/strict";

const { solve } = await import("./target.ts");

const input = (changes = {}) => {
  const expected = {
    repository: "sample/project",
    workflow_head: "a".repeat(40),
    not_before: "2030-01-02T03:04:05Z",
  };
  const actual = {
    repository: "sample/project",
    workflow_head: "a".repeat(40),
    started_at: "2030-01-02T03:05:00Z",
    run_id: 731,
    url: "https://github.com/sample/project/actions/runs/731",
    conclusion: "success",
  };
  Object.assign(expected, changes.expected);
  Object.assign(actual, changes.actual);
  return { expected, actual, now: "2030-01-02T03:10:00Z" };
};

assert.deepEqual(solve(input()), { ok: true, reason: "ok" });
assert.deepEqual(solve(input({ actual: { workflow_head: "b".repeat(40) } })), {
  ok: false,
  reason: "workflow_head_mismatch",
});
assert.deepEqual(
  solve(input({ actual: { started_at: "2030-01-02T03:00:00Z" } })),
  { ok: false, reason: "started_before_window" },
);
