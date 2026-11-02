import test from "node:test";
import assert from "node:assert/strict";
import { issueRevision } from "./chat-review-current.mjs";
import { verifyReviewFromGh } from "./chat-review-github.mjs";

const repo = "mbelinkie/vera-script-to-timeline";
const number = 378;

function issue(comments = 1) {
  return {
    number,
    title: "GitHub boundary test",
    body: "Bound the read-only review check.",
    state: "open",
    labels: [{ name: "chat-reviewed" }],
    comments,
    repository_url: "https://api.github.com/repos/" + repo,
    html_url: "https://github.com/" + repo + "/issues/" + number,
  };
}

function approval(currentIssue, id = 1) {
  return {
    id,
    user: { login: "mbelinkie" },
    created_at: "2026-11-02T02:59:16Z",
    updated_at: "2026-11-02T02:59:16Z",
    performed_via_github_app: null,
    body: "<!-- VERA_CHAT_REVIEW_V1 " + JSON.stringify({
      revision: issueRevision(currentIssue.title, currentIssue.body),
      producer: "mbelinkie",
      promptVersion: "1",
      reviewedAt: "2026-11-02T02:59:16.691Z",
    }) + " -->",
  };
}

function ordinary(id) {
  return { id, user: { login: "reviewer" }, body: "Ordinary discussion." };
}

function pages(comments) {
  const result = [];
  for (let start = 0; start < comments.length; start += 100) {
    result.push(comments.slice(start, start + 100));
  }
  return result.length ? result : [[]];
}

function fakeGh({ issues, histories, failIssueAt = -1, failHistoryAt = -1, calls = [] }) {
  let issueReads = 0;
  let historyReads = 0;
  return args => {
    calls.push(args);
    assert.equal(args[0], "api");
    if (args.includes("--paginate")) {
      const index = historyReads++;
      assert.deepEqual(args.slice(0, 3), ["api", "--paginate", "--slurp"]);
      assert.equal(args[3], "repos/" + repo + "/issues/" + number + "/comments?per_page=100");
      if (index === failHistoryAt) throw new Error("GitHub comment API failed");
      const value = histories[Math.min(index, histories.length - 1)];
      if (value instanceof Error) throw value;
      return typeof value === "string" ? value : JSON.stringify(value);
    }
    assert.deepEqual(args, ["api", "repos/" + repo + "/issues/" + number]);
    const index = issueReads++;
    if (index === failIssueAt) throw new Error("GitHub issue API failed");
    const value = issues[Math.min(index, issues.length - 1)];
    if (value instanceof Error) throw value;
    return typeof value === "string" ? value : JSON.stringify(value);
  };
}

test("reads all pages and confirms the same history before accepting", () => {
  const current = issue(101);
  const history = [approval(current), ...Array.from({ length: 100 }, (_, index) => ordinary(index + 2))];
  const calls = [];
  const result = verifyReviewFromGh(fakeGh({
    issues: [current, current], histories: [pages(history), pages(history)], calls,
  }), repo, number);

  assert.equal(result.approved, true);
  assert.equal(result.commentId, 1);
  assert.deepEqual(calls.map(args => args.includes("--paginate") ? "comments" : "issue"),
    ["issue", "comments", "issue", "comments"]);
});

test("rejects missing, extra, short, duplicate, and out-of-order pages", async t => {
  const two = issue(2);
  const approved = approval(two);
  const cases = [
    ["missing page envelope", [ [] ], /pagination/i],
    ["extra page", [pages([approved, ordinary(2)]).concat([[]])], /pagination/i],
    ["short non-final page", [[ [approved], [ordinary(2)] ]], /pagination/i],
    ["duplicate comments", [pages([approved, { ...ordinary(2), id: 1 }])], /out of order/i],
    ["out-of-order comments", [pages([ordinary(2), approved])], /out of order/i],
    ["comment count mismatch", [pages([approved])], /pagination/i],
  ];
  for (const [name, histories, expected] of cases) {
    await t.test(name, () => {
      assert.throws(() => verifyReviewFromGh(fakeGh({
        issues: [two, two], histories: [histories[0], histories[0]],
      }), repo, number), expected);
    });
  }

  const many = issue(101);
  const incomplete = [approval(many), ...Array.from({ length: 100 }, (_, index) => ordinary(index + 2))];
  await t.test("missing page", () => assert.throws(() => verifyReviewFromGh(fakeGh({
    issues: [many, many], histories: [pages(incomplete).slice(0, 1)],
  }), repo, number), /pagination/i));
});

test("rejects an unavailable or out-of-bound comment count", () => {
  const missing = { ...issue(), comments: undefined };
  const tooMany = issue(2001);
  assert.throws(() => verifyReviewFromGh(fakeGh({ issues: [missing], histories: [[]] }), repo, number), /count/i);
  assert.throws(() => verifyReviewFromGh(fakeGh({ issues: [tooMany], histories: [[]] }), repo, number), /count/i);
});

test("fails closed on API errors and malformed JSON at every read boundary", async t => {
  const current = issue();
  const validHistory = pages([approval(current)]);
  const cases = [
    ["initial issue API error", { issues: [new Error("GitHub issue API failed")] }, /API failed/],
    ["comment API error", { issues: [current], histories: [new Error("GitHub comment API failed")] }, /API failed/],
    ["initial issue parse error", { issues: ["not JSON"] }, /JSON/],
    ["comment parse error", { issues: [current], histories: ["not JSON"] }, /JSON/],
    ["second issue parse error", { issues: [current, "not JSON"], histories: [validHistory] }, /JSON/],
    ["confirmation comment API error", { issues: [current, current], histories: [validHistory, new Error("GitHub comment API failed")] }, /API failed/],
    ["confirmation comment parse error", { issues: [current, current], histories: [validHistory, "not JSON"] }, /JSON/],
  ];
  for (const [name, options, expected] of cases) {
    await t.test(name, () => assert.throws(
      () => verifyReviewFromGh(fakeGh(options), repo, number), expected,
    ));
  }
});

test("validates identity on both issue reads", () => {
  const current = issue();
  const wrongBefore = { ...current, repository_url: "https://api.github.com/repos/other/repo" };
  const wrongAfter = { ...current, number: number + 1 };
  const history = pages([approval(current)]);
  assert.throws(() => verifyReviewFromGh(fakeGh({
    issues: [wrongBefore, current], histories: [history],
  }), repo, number), /identity/i);
  assert.throws(() => verifyReviewFromGh(fakeGh({
    issues: [current, wrongAfter], histories: [history],
  }), repo, number), /identity/i);
});

test("detects title, body, label, and count changes between issue reads", async t => {
  const current = issue();
  const history = pages([approval(current)]);
  const changes = [
    ["title", { ...current, title: "Changed" }],
    ["body", { ...current, body: "Changed" }],
    ["labels", { ...current, labels: [] }],
    ["comment count", { ...current, comments: 2 }],
  ];
  for (const [name, changed] of changes) {
    await t.test(name, () => assert.throws(() => verifyReviewFromGh(fakeGh({
      issues: [current, changed], histories: [history],
    }), repo, number), /changed during verification|pagination/i));
  }
});

test("rejects edits or deletions to comment history even when the count is unchanged", async t => {
  const current = issue(2);
  const original = [approval(current), ordinary(2)];
  const edit = [approval(current, 1), { ...ordinary(2), body: "Edited while verifying." }];
  const replacement = [approval(current), { ...ordinary(2), id: 3 }];
  const updatedApproval = [{ ...approval(current), updated_at: "2026-11-02T03:00:00Z" }, ordinary(2)];
  const appMediatedApproval = [{ ...approval(current), performed_via_github_app: { id: 1, slug: "github-actions" } }, ordinary(2)];
  for (const [name, confirmed] of [
    ["edit", edit], ["delete and replace", replacement],
    ["approval timestamp change", updatedApproval], ["approval App metadata change", appMediatedApproval],
  ]) {
    await t.test(name, () => assert.throws(() => verifyReviewFromGh(fakeGh({
      issues: [current, current], histories: [pages(original), pages(confirmed)],
    }), repo, number), /comments changed/i));
  }
});

test("compares the roadmap snapshot title, body, and labels", async t => {
  const current = issue();
  const history = pages([approval(current)]);
  const goodSnapshot = { title: current.title, body: current.body, labels: ["chat-reviewed"] };
  assert.equal(verifyReviewFromGh(fakeGh({
    issues: [current, current], histories: [history],
  }), repo, number, goodSnapshot).approved, true);

  for (const snapshot of [
    { ...goodSnapshot, title: "stale" },
    { ...goodSnapshot, body: "stale" },
    { ...goodSnapshot, labels: [] },
  ]) {
    await t.test(JSON.stringify(snapshot), () => assert.throws(() => verifyReviewFromGh(fakeGh({
      issues: [current, current], histories: [history],
    }), repo, number, snapshot), /snapshot/i));
  }
});
