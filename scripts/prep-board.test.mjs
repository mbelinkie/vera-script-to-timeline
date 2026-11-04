import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { URL } from "node:url";

import { chatPrompt, compareRows, deepseekState, prsByIssue, rowsFromProject } from "./prep-board.mjs";
import { buildPrompt, estimateCost, readAgentResult } from "../.github/deepseek/job.mjs";

const issue = (repo, number, extra = {}) => ({
  content: { type: "Issue", number, title: `Issue ${number}`, url: `https://github.com/mbelinkie/${repo}/issues/${number}` },
  status: "Inbox",
  labels: [],
  ...extra,
});

test("DeepSeek labels map to board stages", () => {
  assert.equal(deepseekState([]), "none");
  assert.equal(deepseekState(["deepseek"]), "queued");
  assert.equal(deepseekState(["deepseek-pro", "deepseek-done"]), "queued");
  assert.equal(deepseekState(["deepseek-running", "deepseek-done"]), "running");
  assert.equal(deepseekState(["deepseek-done"]), "ready");
  assert.equal(deepseekState(["deepseek-failed"]), "failed");
});

test("rows follow Queue Order, skip Done and foreign issues, and attach DeepSeek PRs", () => {
  const prs = prsByIssue("vera-script-to-timeline", [
    { number: 5, url: "pr5", headRefName: "deepseek/issue-7-100" },
    { number: 6, url: "pr6", headRefName: "deepseek/issue-7-200" },
    { number: 9, url: "pr9", headRefName: "claude/7-other" },
  ]);
  const rows = rowsFromProject({ items: [
    issue("vera-script-to-timeline", 7, { "queue Order": 30, labels: ["deepseek-done"] }),
    issue("vera-script-to-timeline", 8, { queueOrder: 10 }),
    issue("vera-script-to-timeline", 9),
    issue("vera-script-to-timeline", 1, { status: "Done", queueOrder: 1 }),
    issue("someone-else", 2),
    { content: { type: "PullRequest", url: "x" } },
  ] }, prs);
  assert.deepEqual(rows.map((r) => r.number), [8, 7, 9]);
  assert.equal(rows[1].stage, "ready");
  assert.equal(rows[1].pr.url, "pr6");
  assert.equal(rows[0].stage, "groom");
});

test("priority breaks ties when Queue Order is missing", () => {
  const a = { queueOrder: null, priority: "P2", repo: "a", number: 1 };
  const b = { queueOrder: null, priority: "P0", repo: "a", number: 2 };
  assert.ok(compareRows(b, a) < 0);
});

test("the Chat prompt is filled for the right repo and launch tool", () => {
  const template = readFileSync(new URL("../.github/deepseek/chat-prompt.md", import.meta.url), "utf8");
  const text = chatPrompt(template, { url: "https://github.com/mbelinkie/vera-research-video-clips/issues/51", repo: "vera-research-video-clips", number: 51 });
  assert.match(text, /vera_launch_deepseek with repo="research", issue=51/);
  assert.match(text, /https:\/\/github\.com\/mbelinkie\/vera-research-video-clips\b/);
  assert.doesNotMatch(text, /\{\{/);
});

test("job prompt marks the groomed brief and drops status notes", () => {
  const text = buildPrompt({ number: 4, title: "T", body: "B" }, [
    { body: "<!-- vera-deepseek-brief -->\nDo X", user: { login: "m" }, created_at: "t" },
    { body: "<!-- vera-deepseek-status -->\nstarted", user: { login: "bot" }, created_at: "t" },
  ]);
  assert.match(text, /GROOMED BRIEF \(authoritative\)/);
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

test("agent results are read safely, including missing output", () => {
  assert.equal(readAgentResult("", "DEEPSEEK_API_KEY secret is missing").ok, false);
  const ok = readAgentResult(JSON.stringify({ subtype: "success", is_error: false, result: "## Summary", num_turns: 3, modelUsage: {} }));
  assert.equal(ok.ok, true);
  assert.equal(ok.summary, "## Summary");
  const capped = readAgentResult(JSON.stringify({ subtype: "error_max_turns", is_error: true, num_turns: 200 }));
  assert.match(capped.reason, /error_max_turns/);
});
