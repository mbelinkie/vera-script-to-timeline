export type Expected = {
  title: string;
  workflowId: number;
  workflowHead: string;
  startedAt: number;
  timeoutMs: number;
};

export type Run = {
  id: number;
  display_title: string;
  workflow_id: number;
  head_sha: string;
  event: string;
  path: string;
  run_attempt: number;
  status: string;
  conclusion: string | null;
  html_url: string;
  actor: { login: string };
};

export type RunAssessment =
  | { kind: "wait"; runId?: number; url?: string }
  | { kind: "passed"; runId: number; url: string }
  | { kind: "pause"; reason: string };

export function assessRun(expected: Expected, runs: Run[], now: number): RunAssessment {
  if (!Number.isFinite(now) || !Number.isFinite(expected.startedAt) || !Number.isFinite(expected.timeoutMs) || expected.timeoutMs <= 0) {
    return { kind: "pause", reason: "invalid_time" };
  }
  if (expected.startedAt > now) return { kind: "pause", reason: "future_start" };
  const elapsed = now - expected.startedAt;
  if (elapsed > expected.timeoutMs) return { kind: "pause", reason: "timeout" };
  const matches = runs.filter((run) => run.display_title === expected.title);
  if (matches.length === 0) return elapsed <= 120000 ? { kind: "wait" } : { kind: "pause", reason: "missing" };
  if (matches.length !== 1) return { kind: "pause", reason: "ambiguous" };
  const run = matches[0];
  if (run.workflow_id !== expected.workflowId || run.head_sha !== expected.workflowHead ||
      run.event !== "workflow_dispatch" || run.path !== ".github/workflows/validate.yml" ||
      run.run_attempt !== 1 || run.actor?.login !== "github-actions[bot]") {
    return { kind: "pause", reason: "identity_mismatch" };
  }
  if (!Number.isSafeInteger(run.id) || run.id <= 0) return { kind: "pause", reason: "invalid_run_reference" };
  let url: URL;
  try { url = new URL(run.html_url); } catch { return { kind: "pause", reason: "invalid_run_reference" }; }
  if (url.origin !== "https://github.com" || url.username || url.password ||
      !/^\/[^/]+\/[^/]+\/actions\/runs\/[0-9]+$/.test(url.pathname) || url.pathname.split("/").at(-1) !== String(run.id) || url.search || url.hash) {
    return { kind: "pause", reason: "invalid_run_reference" };
  }
  if (run.status === "completed") {
    return run.conclusion === "success" ? { kind: "passed", runId: run.id, url: run.html_url } : { kind: "pause", reason: "not_successful" };
  }
  if (["queued", "in_progress", "waiting", "requested", "pending"].includes(run.status)) {
    return { kind: "wait", runId: run.id, url: run.html_url };
  }
  return { kind: "pause", reason: "unknown_status" };
}
