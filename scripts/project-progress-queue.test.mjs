import assert from "node:assert/strict";
import test from "node:test";
import { Script } from "node:vm";

import { queueClientScript, queueStyles, renderWorkflowQueue } from "./project-progress-queue.mjs";

const privateId = "123e4567-e89b-42d3-a456-426614174000";
const firstItem = {
  number: 41, title: `First <issue> ${privateId} /Users/matthew/Private`,
  url: "https://github.com/example/project/issues/41", status: "Ready", priority: "P0", size: "M",
  workstream: "Operations", type: "implementation", acceptance: "External", labels: ["model:sol"], dependencies: [],
};
const secondItem = {
  number: 42, title: "Second issue", url: "https://github.com/example/project/issues/42", status: "In progress",
  priority: "P1", size: "S", workstream: "Operations", type: "investigation", acceptance: "Automated", labels: [], dependencies: [],
};

const generatedAt = new Date("2026-11-03T17:00:00.000Z");
const freshSnapshot = "2026-11-03T16:58:00.000Z";
const fullHead = "0123456789abcdef0123456789abcdef01234567";
const fullBase = "fedcba9876543210fedcba9876543210fedcba98";

function ciQueue(overrides = {}) {
  return {
    state: "Validating",
    slot: { pr: 9, phase: "validating", head: fullHead, base: fullBase },
    active: { pr: 9, phase: "validating", head: fullHead, base: fullBase, ready: true, verified: true },
    waiting: [11, 12, 13, 14].map((pr) => ({ pr, phase: "Waiting", head: fullHead, base: fullBase })),
    ready: 2,
    delivered: 1,
    lastDelivered: { pr: 8, runId: 123, head: fullHead, base: fullBase },
    snapshotAt: freshSnapshot,
    url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/361",
    ...overrides,
  };
}

function renderCi(queue, at = generatedAt) {
  return renderWorkflowQueue([], { generatedAt: at, workflow: { snapshotAt: "2026-11-03T16:58:00.000Z", ciQueue: queue } });
}

function renderAction(itemChanges, recordChanges = {}) {
  const snapshotAt = "2026-11-03T16:58:00.000Z";
  const item = { ...firstItem, url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/41", snapshotAt, ...itemChanges };
  const sources = Object.fromEntries(["project", "workflow", "chat", "codex", "pr", "review", "ci", "session"].map((name) => [name, { snapshotAt }]));
  return renderWorkflowQueue([{
    projectNumber: 1, projectTitle: "VERA Operations Roadmap", snapshotAt, totalWork: 1, doneCount: 0,
    statusCounts: { [item.status]: 1 }, workItems: [item], goals: [],
  }], {
    generatedAt,
    roadmap: { queue: [{ ...item, queueOrder: 1, dependenciesVerified: true, dependencies: [] }], milestones: [] },
    workflow: {
      snapshotAt,
      issues: { [item.url]: { snapshotAt, sources, ...recordChanges } },
      ciQueue: { state: "idle", snapshotAt, ready: 0, delivered: 0 },
    },
  });
}

function primaryAction(html) {
  return html.match(/<a class="wf-primary-action"[^>]*>[\s\S]*?<\/a>/)?.[0] ?? "";
}

function fixture() {
  return renderWorkflowQueue([{
    projectNumber: 1,
    projectTitle: "VERA Operations Roadmap",
    projectUrl: "https://github.com/users/example/projects/1",
    snapshotAt: "2026-11-02T16:59:00.000Z",
    totalWork: 2,
    doneCount: 0,
    statusCounts: { Done: 0, Ready: 1, "In progress": 1 },
    workItems: [firstItem, secondItem],
    goals: [],
  }], {
    generatedAt: new Date("2026-11-02T17:00:00.000Z"),
    localLinks: true,
    roadmap: {
      queue: [
        { ...secondItem, queueOrder: 13, dependenciesVerified: true, dependencies: [] },
        { ...firstItem, queueOrder: 4, dependenciesVerified: true, dependencies: [] },
      ],
      milestones: [{
        name: "First program milestone",
        order: 1,
        done: 0,
        total: 2,
        percent: 0,
        items: [firstItem, secondItem],
      }],
      warnings: ["Roadmap warning"],
      dependencyErrors: ["Dependency source needs refresh"],
      unverifiedCount: 1,
      unqueuedCount: 0,
    },
    workflow: {
      snapshotAt: "2026-11-02T16:59:00.000Z",
      lastError: "Workflow refresh <failed>",
      issues: {},
      ciQueue: {
        state: "Validating",
        slot: { pr: 9, phase: "validating", head: "head-9", base: "main" },
        active: { pr: 9, phase: "validating", head: "head-9", base: "main", ready: true, verified: true },
        waiting: [11, 12, 13, 14].map((pr) => ({ pr, phase: "Waiting", head: `head-${pr}`, base: "main" })),
        ready: 2,
        delivered: 1,
        lastDelivered: { pr: 8, runId: 123, head: "head-8", base: "main" },
        snapshotAt: "2026-11-02T16:58:00.000Z",
        url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/361",
        lastError: "Controller <timeout>",
      },
    },
  });
}

test("renders the compact top strip and all next-actor groups in order", () => {
  const html = fixture();
  const headings = ["launch", "you", "working", "stuck", "done"].map((key) => html.indexOf(`data-queue-group="${key}"`));
  assert.ok(headings.every((index) => index >= 0));
  assert.deepEqual(headings, [...headings].sort((left, right) => left - right));
  assert.match(html, /Overall progress/);
  assert.match(html, /Next milestone/);
  assert.match(html, /First program milestone/);
  assert.match(html, /CI queue/);
  assert.match(html, /0 of 2 work items done/);
});

test("uses roadmap Queue Order across projects and includes ranked order for flat mode", () => {
  const html = fixture();
  assert.match(html, /data-row-index="0" data-queue-order="4"/);
  assert.match(html, /data-row-index="1" data-queue-order="13"/);
  assert.match(queueClientScript, /sort\(\(left, right\) => Number\(left\.dataset\.rowIndex\)/);
  assert.match(html, /data-queue-mode="flat"/);
});

test("renders five visible status chips, accessible expanders, and preserved issue filters", () => {
  const html = fixture();
  for (const name of ["Chat", "DeepSeek", "Codex", "Review", "CI"]) assert.match(html, new RegExp(`<span>${name}</span>`));
  assert.equal((html.match(/class="wf-chip /g) || []).length, 10);
  assert.match(html, /aria-controls="wf-detail-0"/);
  assert.match(html, /data-filter-search/);
  assert.match(html, /data-filter-project/);
  assert.match(html, /data-filter-status/);
  assert.match(html, /data-filter-size/);
  assert.match(html, /data-filter-dependency/);
  assert.match(html, /data-actor-filter="chat"/);
  assert.match(html, /data-actor-filter="codex"/);
  assert.match(html, /data-actor-filter="approval"/);
  assert.match(html, /data-actor-filter="deepseek"/);
  assert.match(html, /data-actor-filter="blocked"/);
  assert.match(html, /data-actor-filter="all"/);
  assert.match(html, /Repository: example\/project · Type: implementation · Route: sol \/ unconfigured · Acceptance: External/);
});

test("keeps CI source errors visible and does not show an optimistic queue status", () => {
  const html = fixture();
  assert.match(html, /Workflow refresh &lt;failed&gt;/);
  assert.match(html, /Controller &lt;timeout&gt;/);
  assert.match(html, /Controller snapshot:/);
  assert.match(html, /class="wf-ci-state"[^>]*>Unknown<\/span>/);
  assert.match(html, /Queue state is unknown; only the last known controller snapshot is shown\./);
  assert.doesNotMatch(html, /PR #9 · validating|Ready to send: 2|Verified deliveries: 1|PR #8 · run #123/);
  assert.match(html, /Queue control issue #361/);
  assert.match(html, /data-group-count/);
});

test("keeps the current CI queue compact, with full SHAs inside collapsed evidence", () => {
  const html = renderCi(ciQueue({ snapshotAt: "2026-11-03T16:45:00.000Z" }));
  assert.match(html, /data-workflow-status="Validating"[^>]*>Validating<\/span>/);
  assert.match(html, /<summary><span data-workflow-status="ciQueue.waiting"[^>]*>Waiting \(4\)<\/span><\/summary>/);
  for (const pr of [11, 12, 13, 14]) assert.match(html, new RegExp(`PR #${pr}`));
  assert.match(html, /Queue control issue #361/);
  assert.match(html, /head 0123456 · base fedcba9/);
  assert.match(html, /<summary>Full head\/base evidence<\/summary>/);
  const visibleHtml = html.replace(/<details class="wf-ci-sha">[\s\S]*?<\/details>/g, "");
  assert.doesNotMatch(visibleHtml, new RegExp(fullHead));
  assert.doesNotMatch(visibleHtml, new RegExp(fullBase));
  assert.match(html, new RegExp(fullHead));
  assert.match(html, new RegExp(fullBase));
});

test("shows only the known CI source when its timestamp is invalid, expired, future, or failed", () => {
  const cases = [
    ciQueue({ lastError: "Controller refresh failed" }),
    ciQueue({ source: { snapshotAt: freshSnapshot, lastError: "Per-source refresh failed" } }),
    ciQueue({ snapshotAt: "invalid timestamp" }),
    ciQueue({ snapshotAt: "2026-11-03T16:43:59.999Z" }),
    ciQueue({ snapshotAt: "2026-11-03T17:00:00.001Z" }),
  ];
  for (const queue of cases) {
    const html = renderCi(queue);
    assert.match(html, /class="wf-ci-state"[^>]*>Unknown<\/span>/);
    assert.match(html, /Controller snapshot:/);
    assert.match(html, /Queue control issue #361/);
    assert.doesNotMatch(html, /PR #9 · validating|PR #11|Ready to send|Verified deliveries/);
  }
  assert.doesNotMatch(renderCi(ciQueue({ lastError: "Controller refresh failed" })), /data-stale="true"/);
});

test("prioritizes safe interactive review, PR, CI, and verified approval links with Issue as fallback", () => {
  const pending = renderAction({
    labels: ["type:investigation", "chat-review-pending"],
    body: "## Research question\nThis bounded research question needs a current workflow review before anyone starts implementation.",
  }, { chat: { state: "pending", reason: "Producer Chat review is pending." } });
  assert.match(primaryAction(pending), /Open Chat review prompt/);
  assert.match(primaryAction(pending), /data-requires-fresh/);
  assert.match(primaryAction(pending), /href="https:\/\/chatgpt\.com\/"/);
  assert.match(pending, /Copy this draft into ChatGPT and send it when ready\./);
  assert.match(pending, /Review the exact current issue/);
  assert.doesNotMatch(pending, /chatgpt\.com\/\?q=/);

  const pr = "https://github.com/mbelinkie/vera-script-to-timeline/pull/77";
  const needsReview = renderAction({ status: "Ready" }, {
    chat: { state: "approved", url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/41#issuecomment-123" },
    pr: { number: 77, url: pr },
    review: { state: "unknown" },
  });
  assert.match(primaryAction(needsReview), new RegExp(`href="${pr.replaceAll("/", "\\/")}"`));
  assert.match(primaryAction(needsReview), />PR<\/a>/);

  const run = "https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/123";
  const ci = renderAction({ status: "In review" }, {
    chat: { state: "approved", url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/41#issuecomment-123" },
    pr: { number: 77, url: pr },
    review: { state: "approved" },
    ci: { state: "validating", url: run },
  });
  assert.match(primaryAction(ci), new RegExp(`href="${run.replaceAll("/", "\\/")}"`));
  assert.match(primaryAction(ci), />CI run<\/a>/);

  const approval = renderAction({ status: "Ready" }, {
    chat: { state: "approved", url: "https://github.com/mbelinkie/vera-script-to-timeline/issues/41#issuecomment-123" },
  });
  assert.match(primaryAction(approval), /Verified Chat review/);

  const fallback = renderAction({ status: "Inbox" }, { chat: { state: "unknown" } });
  assert.match(primaryAction(fallback), /href="https:\/\/github\.com\/mbelinkie\/vera-script-to-timeline\/issues\/41"/);
  assert.match(primaryAction(fallback), />Issue<\/a>/);
});

test("expires generated workflow markup at the earliest relevant source timestamp", () => {
  const workflow = {
    snapshotAt: "2026-11-03T16:57:00.000Z",
    ciQueue: { snapshotAt: "2026-11-03T16:55:00.000Z" },
  };
  const project = { projectNumber: 1, projectTitle: "VERA Operations", snapshotAt: "2026-11-03T16:59:00.000Z", workItems: [], goals: [] };
  const html = renderWorkflowQueue([project], { generatedAt, workflow });
  assert.match(html, /data-workflow-expires-at="1793725980000"/);
  assert.doesNotMatch(html, /data-stale="true"/);

  const invalid = renderWorkflowQueue([project], { generatedAt, workflow: { ...workflow, snapshotAt: "invalid" } });
  assert.match(invalid, /data-stale="true"/);
  assert.match(invalid, /Last-known groups:/);
  assert.match(queueClientScript, /Date\.now\(\)/);
  assert.match(queueClientScript, /Math\.min\(Math\.max\(next - now \+ 1, 1\), 60_000\)/);
  assert.match(queueClientScript, /a\[data-requires-fresh\]/);
  assert.match(queueClientScript, /Unknown · Refresh sources before acting\./);
  assert.match(queueStyles, /\.workflow-queue\[data-stale="true"\] \.wf-stale-notice/);
  assert.match(queueStyles, /html\[data-snapshot-stale="true"\] \.workflow-queue \.wf-stale-notice/);
});

test("keeps generated markup free of local identifiers and paths", () => {
  const html = fixture();
  assert.doesNotMatch(html, new RegExp(privateId));
  assert.doesNotMatch(html, /\/Users\/matthew/);
  assert.doesNotMatch(html, /codex:\/\//i);
  assert.doesNotMatch(html, /Synthetic demo|S-\d{3}/);
  assert.match(html, /\[local identifier hidden\]/);
  assert.match(html, /\[local path hidden\]/);
});

test("counts shared issue URLs once and historical records only in progress", () => {
  const shared = { ...secondItem, title: "Shared issue", size: "M", status: "Ready" };
  const historical = { number: "historical-draft-1", title: "Historical — earlier work", url: "", status: "Done", type: "historical" };
  const html = renderWorkflowQueue([
    { projectNumber: 1, projectTitle: "VERA Master", totalWork: 2, doneCount: 1, workItems: [shared, historical], goals: [] },
    { projectNumber: 2, projectTitle: "VERA Research", totalWork: 2, doneCount: 1, workItems: [{ ...shared, size: "S" }, historical], goals: [] },
  ], {
    generatedAt: new Date("2026-11-02T17:00:00.000Z"),
    roadmap: { queue: [{ ...shared, projectTitle: "VERA Master", queueOrder: 8, dependenciesVerified: true, dependencies: [] }], milestones: [] },
    workflow: { issues: {}, ciQueue: { state: "Unknown", snapshotAt: "2026-11-02T16:59:00.000Z" } },
  });

  assert.equal((html.match(/class="wf-row /g) || []).length, 1);
  assert.match(html, /2 of 3 work items done/);
  assert.match(html, /data-queue-order="8"[^>]*data-project="1"[^>]*data-status="Ready"[^>]*data-size="M"/);
  assert.doesNotMatch(html, /historical-/i);
});

test("renders a live session endpoint only from fresh verified evidence", () => {
  const generatedAt = new Date("2026-11-02T17:00:00.000Z");
  const snapshotAt = "2026-11-02T16:59:00.000Z";
  const project = {
    projectNumber: 1,
    projectTitle: "VERA Operations Roadmap",
    snapshotAt,
    totalWork: 1,
    doneCount: 0,
    statusCounts: { Ready: 1 },
    workItems: [{ ...firstItem, snapshotAt, title: "Approved issue", status: "Ready" }],
    goals: [],
  };
  const issue = project.workItems[0];
  const roadmap = { queue: [{ ...issue, queueOrder: 4, dependenciesVerified: true, dependencies: [] }], milestones: [] };
  const workflow = {
    snapshotAt,
    issues: {
      [issue.url]: {
        sources: {
          project: { snapshotAt },
          workflow: { snapshotAt },
          ci: { snapshotAt },
        },
        chat: { state: "approved", url: `${issue.url}#issuecomment-123` },
        session: { status: "verified-local", reason: "Verified local mapping.", hasBrowser: true },
      },
    },
    ciQueue: { state: "Unknown", snapshotAt },
  };
  const live = renderWorkflowQueue([project], { generatedAt, live: true, roadmap, workflow });
  assert.match(live, /href="\/local-session\?issue=https%3A%2F%2Fgithub.com%2Fexample%2Fproject%2Fissues%2F41"[^>]*data-requires-fresh/);
  assert.match(live, /&amp;surface=browser/);
  assert.match(live, /Open existing Codex chat/);
  assert.match(live, /Open separate web conversation/);

  const failedRefresh = renderWorkflowQueue([project], { generatedAt, live: true, roadmap, workflow: { ...workflow, lastError: "Refresh failed" } });
  assert.doesNotMatch(failedRefresh, /\/local-session/);
  assert.match(failedRefresh, /Refresh failed/);
  const staticHtml = renderWorkflowQueue([project], { generatedAt, roadmap, workflow });
  assert.doesNotMatch(staticHtml, /\/local-session/);
});

test("browser controls stay local and the layout has a narrow-screen rule", () => {
  assert.doesNotMatch(queueClientScript, /\bfetch\s*\(|XMLHttpRequest|WebSocket|localStorage|sessionStorage/i);
  assert.doesNotThrow(() => new Script(queueClientScript));
  assert.match(queueClientScript, /data-expand-row/);
  assert.match(queueClientScript, /data-actor-filter/);
  assert.match(queueStyles, /@media \(max-width:640px\)/);
  assert.match(queueStyles, /grid-template-columns:minmax\(0,1fr\)/);
});
