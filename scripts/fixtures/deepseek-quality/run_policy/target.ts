export type Expected = {
  repository: string;
  workflow_head: string;
  not_before: string;
};

export type Run = {
  repository: string;
  workflow_head: string;
  started_at: string;
  run_id: number;
  url: string;
  conclusion: string;
};

export type RunPolicyInput = {
  expected: Expected;
  actual: Run;
  now: string;
};

export type Reason =
  | "invalid_payload"
  | "invalid_expected"
  | "invalid_actual"
  | "invalid_now"
  | "run_not_successful"
  | "repository_mismatch"
  | "workflow_head_mismatch"
  | "invalid_run_url"
  | "started_before_window"
  | "started_in_future"
  | "ok";

export type Decision = { ok: boolean; reason: Reason };

export const PAYLOAD_KEYS = ["expected", "actual", "now"] as const;
export const EXPECTED_KEYS = [
  "repository",
  "workflow_head",
  "not_before",
] as const;
export const RUN_KEYS = [
  "repository",
  "workflow_head",
  "started_at",
  "run_id",
  "url",
  "conclusion",
] as const;
export const REASON_CODES: readonly Reason[] = [
  "invalid_payload",
  "invalid_expected",
  "invalid_actual",
  "invalid_now",
  "run_not_successful",
  "repository_mismatch",
  "workflow_head_mismatch",
  "invalid_run_url",
  "started_before_window",
  "started_in_future",
  "ok",
];

function reject(reason: Reason): Decision {
  return { ok: false, reason };
}

// Intentionally incomplete baseline: it checks only the lower time bound.
function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function solve(payload: unknown): Decision {
  if (!isRecord(payload) || !isRecord(payload.expected) || !isRecord(payload.actual)) {
    return reject("invalid_payload");
  }
  const expected = payload.expected;
  const actual = payload.actual;
  if (typeof expected.not_before !== "string" || typeof actual.started_at !== "string") {
    return reject("invalid_actual");
  }
  if (actual.started_at < expected.not_before) {
    return reject("started_before_window");
  }
  return { ok: true, reason: "ok" };
}
