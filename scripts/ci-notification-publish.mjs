#!/usr/bin/env node
import { appendFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { GitHub } from "./ci-queue-github.mjs";
import { NotificationOutbox, renderReport } from "./ci-notification-outbox.mjs";
import { captureFinalization } from "./ci-notification-verify.mjs";

export function renderPublicationSummary({ event, result }) {
  const status = ["commented", "pending", "failed"].includes(result.status) ? result.status : "unknown";
  const http = Number.isInteger(result.commentHttpStatus) && result.commentHttpStatus >= 400 && result.commentHttpStatus <= 599 ? ` HTTP ${result.commentHttpStatus}.` : "";
  return `Report publication: ${status}.${http} Automatic Codex injection remains disabled.\n\n` + renderReport(event);
}

// Notification faults are deliberately outside the queue controller's state machine.
export async function publishCompletion(github, context, { summary = () => {} } = {}) {
  try {
    const captured = await captureFinalization(github, context, new NotificationOutbox(github));
    if (captured) summary(renderPublicationSummary(captured));
    return captured;
  } catch {
    summary("CI notification publication unavailable. Open this run's Queue completion and the PR's checks to review authoritative results. Automatic Codex delivery is disabled; queue controls and issue acceptance remain owner-managed.");
    return { status: "publication_unknown" };
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  // No exception or reporting failure may change reconciliation's exit status.
  try {
    const github = new GitHub({ repository: process.env.GITHUB_REPOSITORY, token: process.env.GITHUB_TOKEN });
    await publishCompletion(github, {
      job: process.env.GITHUB_JOB, actor: process.env.GITHUB_ACTOR,
      workflowRef: process.env.GITHUB_WORKFLOW_REF, ref: process.env.GITHUB_REF,
      runId: process.env.GITHUB_RUN_ID, runAttempt: process.env.GITHUB_RUN_ATTEMPT,
      stateSha: process.env.VERA_NOTIFICATION_STATE_SHA,
      mode: process.env.VERA_NOTIFICATION_MODE,
    }, { summary: (message) => {
      if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, message + "\n");
    } });
  } catch {
    console.warn("CI notification unavailable; use the PR checks and run report for manual review.");
  }
}
