import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { URL } from "node:url";

import { buildProgressModel, parseProjectItems } from "./project-progress-lib.mjs";
import { buildBoard, chatPrompt, compareRows, deepseekState, nextPrepped, notReadyReasons, prsByIssue } from "./prep-board.mjs";
import { buildPrompt, estimateCost, ineligibleReason, readAgentResult } from "../.github/deepseek/job.mjs";

const TL = "vera-script-to-timeline";
const RS = "vera-research-video-clips";
const url = (repo, number) => `https://github.com/mbelinkie/${repo}/issues/${number}`;
const issue = (repo, number, { type = "implementation", status = "Inbox", queue = null, labels = [], milestone = null } = {}) => ({
  content: { type: "Issue", number, title: `Issue ${number}`, url: url(repo, number) },
  status,
  labels: [`type:${type}`, ...labels],
  ...(queue === null ? {} : { "queue Order": queue }),
  ...(milestone ? { "program Milestone": milestone } : {}),
});
const model = (title, items) => ({ ...buildProgressModel(parseProjectItems({ items })), projectTitle: title, codeStats: { production: 1000, total: 2000 } });

function fixture() {
  const timeline = model("VERA Script-to-Timeline Roadmap", [
    issue(TL, 1, { status: "Done", queue: 1, milestone: "M1" }),
    issue(TL, 2, { queue: 2, milestone: "M1" }),
    issue(TL, 3, { queue: 3, milestone: "M1" }),
    issue(TL, 4, { type: "design", queue: 4, milestone: "M2" }),
    issue(TL, 5, { status: "In progress", queue: 5 }),
    issue(TL, 6, { queue: 6, labels: ["deepseek-done"] }),
    issue(TL, 7, { queue: 7, labels: ["deepseek-running"] }),
    issue(TL, 8),
    issue(TL, 9, { queue: 9, labels: ["deepseek-excluded"] }),
  ]);
  const research = model("VERA Research Roadmap", [issue(RS, 50, { type: "bug", queue: 10, milestone: "M2" })]);
  const verified = [2, 3, 4, 5, 6, 7, 9].map((n) => url(TL, n)).concat(url(RS, 50));
  const deps = {
    // Like fetchNativeDependencies: every verified issue has a list, even an empty one.
    dependencies: {
      ...Object.fromEntries(verified.map((key) => [key, []])),
      [url(TL, 2)]: [{ url: url(TL, 1), state: "CLOSED" }],
      [url(TL, 3)]: [{ url: url(TL, 2), state: "OPEN" }],
    },
    verified,
  };
  const pulls = { [TL]: [{ number: 66, url: "pr66", headRefName: "deepseek/issue-6-100" }], [RS]: [] };
  return buildBoard([timeline, research], deps, pulls, "Groom {{ISSUE_URL}} in {{REPO}} as {{SHORT_REPO}} #{{NUMBER}}");
}

test("only implementation/bug issues with finished dependencies are groomable", () => {
  const board = fixture();
  const byNumber = Object.fromEntries(board.rows.map((row) => [row.number, row]));
  assert.equal(byNumber[1], undefined, "Done issues are hidden");
  assert.equal(byNumber[2].stage, "groom");
  assert.equal(byNumber[2].canGroom, true);
  assert.match(byNumber[2].chatPrompt, /as timeline #2/);
  assert.equal(byNumber[50].stage, "groom", "bugs qualify, across repos");
  assert.equal(byNumber[3].stage, "blocked");
  assert.deepEqual(byNumber[3].reasons, ["Waiting on Timeline #2"]);
  assert.match(byNumber[4].reasons.join(), /type:design isn't DeepSeek work/);
  assert.match(byNumber[5].reasons.join(), /Already in progress/);
  assert.match(byNumber[8].reasons.join(), /Not in Queue Order/);
  assert.match(byNumber[9].reasons.join(), /Excluded/);
  for (const n of [3, 4, 5, 8, 9]) assert.equal(byNumber[n].canGroom, false);
  assert.equal(byNumber[6].stage, "ready");
  assert.equal(byNumber[6].pr.url, "pr66");
  assert.equal(byNumber[7].stage, "running");
});

test("summary reports progress, code lines and the next milestone", () => {
  const { summary } = fixture();
  assert.equal(summary.total, 10);
  assert.equal(summary.done, 1);
  assert.equal(summary.percent, 10);
  assert.equal(summary.productionLines, 2000);
  assert.deepEqual(summary.nextMilestone, { name: "M1", done: 1, total: 3, left: 2 });
});

test("the next prepped ticket is the first ready, unstarted one", () => {
  const board = fixture();
  assert.equal(board.nextPrepped.number, 6);
  const rows = board.rows.map((row) => (row.number === 6 ? { ...row, status: "In progress" } : row));
  assert.equal(nextPrepped(rows), null);
});

test("DeepSeek labels map to states", () => {
  assert.equal(deepseekState([]), "none");
  assert.equal(deepseekState(["deepseek-pro", "deepseek-done"]), "queued");
  assert.equal(deepseekState(["deepseek-running", "deepseek-done"]), "running");
  assert.equal(deepseekState(["deepseek-done"]), "ready");
  assert.equal(deepseekState(["deepseek-failed"]), "failed");
});

test("readiness reasons and ordering helpers", () => {
  assert.deepEqual(notReadyReasons({ status: "Ready", type: "bug", queueOrder: 1, dependenciesVerified: true, dependencies: [] }), []);
  assert.match(notReadyReasons({ status: "Ready", type: "bug", queueOrder: 1, dependenciesVerified: false }).join(), /not verified/);
  assert.ok(compareRows({ queueOrder: null, priority: "P0", repo: "a", number: 2 }, { queueOrder: null, priority: "P2", repo: "a", number: 1 }) < 0);
  const prs = prsByIssue(TL, [{ number: 1, url: "a", headRefName: "deepseek/issue-7-1" }, { number: 2, url: "b", headRefName: "deepseek/issue-7-9" }]);
  assert.equal(prs.get(`${TL}#7`).url, "b");
});

test("the Chat prompt is filled for the right repo, writes code and refuses non-code work", () => {
  const template = readFileSync(new URL("../.github/deepseek/chat-prompt.md", import.meta.url), "utf8");
  const text = chatPrompt(template, { url: url(RS, 51), repo: RS, number: 51 });
  assert.match(text, /vera_launch_deepseek with repo="research", issue=51/);
  assert.match(text, /Draft code/);
  assert.match(text, /design, taste, research or investigation work/);
  assert.doesNotMatch(text, /\{\{/);
});

test("the job refuses non-code tickets", () => {
  assert.equal(ineligibleReason(["type:implementation"]), "");
  assert.equal(ineligibleReason(["type:bug", "model:sol"]), "");
  assert.match(ineligibleReason(["type:design"]), /type:design/);
  assert.match(ineligibleReason([]), /none/);
  assert.match(ineligibleReason(["type:bug", "deepseek-excluded"]), /excluded/);
});

test("job prompt marks the groomed brief, explains draft code and drops status notes", () => {
  const text = buildPrompt({ number: 4, title: "T", body: "B" }, [
    { body: "<!-- vera-deepseek-brief -->\nDo X", user: { login: "m" }, created_at: "t" },
    { body: "<!-- vera-deepseek-status -->\nstarted", user: { login: "bot" }, created_at: "t" },
  ]);
  assert.match(text, /GROOMED BRIEF \(authoritative\)/);
  assert.match(text, /Draft code in the brief/);
  assert.doesNotMatch(text, /started/);
});

test("cost estimate uses DeepSeek peak rates per model", () => {
  const { usd, tokens } = estimateCost({
    "deepseek-flash[1m]": { inputTokens: 1_000_000, cacheReadInputTokens: 1_000_000, outputTokens: 1_000_000 },
    "deepseek-v4-pro[1m]": { inputTokens: 1_000_000 },
  });
  assert.equal(tokens, 4_000_000);
  assert.equal(Number(usd.toFixed(3)), Number((0.3 + 0.006 + 1.2 + 1.32).toFixed(3)));
});

test("agent results are read safely, including bad keys and caps", () => {
  assert.equal(readAgentResult("", "DEEPSEEK_API_KEY secret is missing").ok, false);
  const ok = readAgentResult(JSON.stringify({ subtype: "success", is_error: false, result: "## Summary", num_turns: 3, modelUsage: {} }));
  assert.equal(ok.ok, true);
  assert.equal(ok.summary, "## Summary");
  assert.match(readAgentResult(JSON.stringify({ subtype: "error_max_turns", is_error: true, num_turns: 200 })).reason, /error_max_turns/);
  assert.match(readAgentResult(JSON.stringify({ subtype: "success", is_error: true, api_error_status: 401 })).reason, /rejected the API key/);
});
