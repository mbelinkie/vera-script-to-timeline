import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  buildProgressModel,
  escapeHtml,
  parseProjectItems,
  requiredGraphqlReadBudget,
  renderDashboard,
  resolveProjectRepositoryPath,
  summarizeCodeFiles,
  terminalSummary,
  writeDashboard,
} from "./project-progress-lib.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const projectData = {
  totalCount: 5,
  items: [
    {
      status: "In progress",
      labels: ["model:terra", "effort:high", "type:goal"],
      priority: "P0", size: "L", workstream: "Contracts and Compiler", acceptance: "Producer",
      content: { type: "Issue", number: 1, title: "Goal: Phase 1", url: "https://example.test/1" },
    },
    {
      status: "Done",
      labels: ["model:terra", "effort:high", "type:implementation"],
      priority: "P0", size: "L", workstream: "Packaging", acceptance: "Producer",
      content: { type: "Issue", number: 2, title: "Package writer and verification", url: "https://example.test/2" },
    },
    {
      status: "Blocked",
      labels: ["model:terra", "effort:high", "type:investigation"],
      priority: "P1", size: "M", workstream: "Resolve Integration", acceptance: "Producer",
      content: { type: "Issue", number: 3, title: "Fusion capability spike", url: "https://example.test/3" },
    },
    {
      status: "In review",
      labels: ["model:sol", "effort:high", "type:implementation"],
      priority: "P1", size: "M", workstream: "Product and UX", acceptance: "Producer",
      content: { type: "Issue", number: 4, title: "Approve the authoring prototype", url: "https://example.test/4" },
    },
    {
      status: "Inbox",
      labels: ["model:luna", "effort:medium", "type:investigation"],
      content: { type: "Issue", number: 5, title: "Untriaged operational spike", url: "https://example.test/5" },
    },
  ],
};

test("parses the authoritative board without counting goals as work", () => {
  const parsed = parseProjectItems(projectData);
  assert.equal(parsed.goals.length, 1);
  assert.equal(parsed.workItems.length, 4);
  assert.deepEqual(parsed.workItems[0], {
    number: 2, title: "Package writer and verification", url: "https://example.test/2",
    status: "Done", type: "implementation", model: "terra", effort: "high",
    priority: "P0", size: "L", workstream: "Packaging", acceptance: "Producer",
  });
});

test("calculates exact done and remaining scope from actionable board issues", () => {
  const model = buildProgressModel(parseProjectItems(projectData));
  assert.equal(model.totalWork, 4);
  assert.equal(model.doneCount, 1);
  assert.equal(model.remainingCount, 3);
  assert.equal(model.completionPercent, 25);
  assert.equal(model.statusCounts.Done, 1);
  assert.equal(model.statusCounts.Blocked, 1);
  assert.equal(model.statusCounts["In review"], 1);
  assert.equal(model.statusCounts.Inbox, 1);
  assert.deepEqual(model.workstreams.map((group) => [group.name, group.items.length]), [
    ["Packaging", 1], ["Product and UX", 1], ["Resolve Integration", 1], ["Unassigned", 1],
  ]);
  assert.deepEqual(model.metadataGaps, { workstream: 1, priority: 1, size: 1, acceptance: 1 });
});

test("counts tracked source lines and separates production code", () => {
  assert.deepEqual(summarizeCodeFiles([
    { path: "apps/web/src/main.ts", contents: "one\n\nthree\n" },
    { path: "apps/web/src/main.test.ts", contents: "one\ntwo\n" },
    { path: "packages/contracts/src/generated/contracts.ts", contents: "one\ntwo\n" },
    { path: "scripts/tool.mjs", contents: "one\n" },
    { path: "README.md", contents: "not\ncode\n" },
  ]), { total: 8, production: 3 });
});

test("allows the actual research checkout path to override its portable default", () => {
  assert.equal(
    resolveProjectRepositoryPath("/dashboard", {
      repositoryPath: "../VERA Research Video Clips",
      repositoryPathEnv: "VERA_RESEARCH_REPOSITORY",
    }, { VERA_RESEARCH_REPOSITORY: "/projects/research" }),
    "/projects/research",
  );
  assert.equal(
    resolveProjectRepositoryPath("/dashboard", {
      repositoryPath: "../VERA Research Video Clips",
      repositoryPathEnv: "VERA_RESEARCH_REPOSITORY",
    }, {}),
    "/VERA Research Video Clips",
  );
});

test("budgets live Project reads from preflight item counts and the configured page cap", () => {
  const projects = [{ projectNumber: 1 }, { projectNumber: 2 }];
  assert.equal(requiredGraphqlReadBudget(projects, { 1: 115, 2: 197 }), 2_003);
  assert.equal(requiredGraphqlReadBudget(projects, { 1: 500, 2: 500 }), 5_003);
  assert.throws(
    () => requiredGraphqlReadBudget(projects, { 1: 115 }),
    /did not return a valid item count for project #2/,
  );
});

test("fails closed on incomplete or ambiguous board data", () => {
  assert.throws(() => parseProjectItems({ ...projectData, totalCount: 6 }), /received 5 of 6 items/);
  for (const [field, replacement, pattern] of [
    ["status", "Paused", /unsupported project status: Paused/],
    ["labels", ["model:terra", "effort:high"], /exactly one type label/],
    ["labels", ["model:terra", "model:sol", "effort:high", "type:goal"], /exactly one model label/],
    ["content", { type: "DraftIssue", title: "Draft" }, /must be a GitHub Issue/],
  ]) {
    const items = clone(projectData.items);
    items[0][field] = replacement;
    assert.throws(() => parseProjectItems({ totalCount: 5, items }), pattern);
  }
  const items = clone(projectData.items);
  items[1].content.number = 1;
  assert.throws(() => parseProjectItems({ totalCount: 5, items }), /Duplicate project issue #1/);
});

test("counts completed historical draft records as Done work but rejects active drafts", () => {
  const historical = {
    title: "Historical — BUG-DOGFOOD-003 — Batch removal and caption retry",
    status: "Done",
    content: { type: "DraftIssue", title: "Historical — BUG-DOGFOOD-003 — Batch removal and caption retry" },
  };
  const parsed = parseProjectItems({
    totalCount: projectData.totalCount + 1,
    items: [...projectData.items, historical],
  });

  assert.equal(parsed.goals.length, 1);
  assert.equal(parsed.workItems.length, 5);
  assert.equal(parsed.workItems.filter((item) => item.status === "Done").length, 2);
  assert.equal(parsed.workItems.at(-1).type, "historical");
  const model = buildProgressModel(parsed);
  assert.deepEqual(
    [model.totalWork, model.doneCount, model.remainingCount, model.completionPercent],
    [5, 2, 3, 40],
  );
  const html = renderDashboard(model);
  assert.match(html, /data-issue="historical-/);
  assert.match(html, /Historical — BUG-DOGFOOD-003 — Batch removal and caption retry/);
  assert.doesNotMatch(html, /#historical-/);
  assert.doesNotMatch(html, /href=""/);
  assert.throws(
    () => parseProjectItems({ totalCount: 1, items: [{ ...historical, status: "Inbox" }] }),
    /must be a GitHub Issue/,
  );
});

test("sorts numbered issues before historical records and titles historical records consistently", () => {
  const historicalZ = {
    title: "Historical — Zeta work",
    status: "Done",
    workstream: "Packaging",
    content: { type: "DraftIssue", title: "Historical — Zeta work" },
  };
  const historicalA = {
    title: "Historical — Alpha work",
    status: "Done",
    workstream: "Packaging",
    content: { type: "DraftIssue", title: "Historical — Alpha work" },
  };
  const parsed = parseProjectItems({
    totalCount: 3,
    items: [historicalZ, projectData.items[1], historicalA],
  });
  const model = buildProgressModel(parsed);
  assert.deepEqual(model.workstreams[0].items.map((item) => item.number), [
    2, "historical-2", "historical-0",
  ]);
});

test("renders every work item, collapsed workstreams with progress tracks, and goal rollups", () => {
  assert.equal(escapeHtml('<script data-name="test">&</script>'), "&lt;script data-name=&quot;test&quot;&gt;&amp;&lt;/script&gt;");
  const data = clone(projectData);
  data.items[4].content.title = "Investigate <unsafe> & missing metadata";
  const model = buildProgressModel(parseProjectItems(data));
  const firstRender = renderDashboard(model);
  assert.equal(firstRender, renderDashboard(model));
  assert.match(firstRender, /<h1 id="page-title">VERA progress<\/h1>/);
  assert.match(firstRender, /<b>1 of 4<\/b> work items done</);
  assert.doesNotMatch(firstRender, /Updated/);
  assert.match(firstRender, /Lines of code unavailable/);
  assert.match(firstRender, /Goal rollups/);
  assert.match(firstRender, /Investigate &lt;unsafe&gt; &amp; missing metadata/);
  assert.match(firstRender, /href="https:\/\/example\.test\/2"/);
  for (let issue = 1; issue <= 5; issue += 1) {
    assert.equal(firstRender.match(new RegExp(`data-issue="${issue}"`, "g"))?.length, 1);
  }
  // Workstreams start collapsed, each with its own mini progress track and count.
  assert.doesNotMatch(firstRender, /<details[^>]*\sopen/);
  assert.match(firstRender, /<span class="ws-name">Packaging<\/span>\s*<div class="track" role="img" aria-label="Packaging: 1 Done">[\s\S]*?<span class="ws-count">1 of 1<\/span>/);
  assert.match(firstRender, /<span class="ws-name">Unassigned<\/span>\s*<div class="track" role="img" aria-label="Unassigned: 1 Inbox">/);
  // Workstreams with work left come before finished ones.
  assert.ok(firstRender.indexOf('ws-name">Unassigned') < firstRender.indexOf('ws-name">Packaging'));
  assert.match(firstRender, /<p class="pct"[^>]*>25%<\/p>/);
  assert.match(firstRender, /Metadata missing: 1 without a workstream, 1 without a priority, 1 without a size, 1 without an acceptance owner\./);
  assert.match(firstRender, /class="missing">No priority</);
  assert.match(firstRender, /Expand all/);
  assert.doesNotMatch(firstRender, /weighted estimate|eleven-phase|60 slices/i);
});

test("shows when the dashboard was generated", () => {
  const model = buildProgressModel(parseProjectItems(projectData));
  assert.match(renderDashboard(model, { generatedAt: new Date(2026, 9, 16, 13, 40) }), /Updated Fri, Oct 16, 1:40\sPM/);
});

test("writes the dashboard and reports an exact terminal summary", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const outputPath = path.join(directory, "nested", "index.html");
  const models = await writeDashboard(repositoryRoot, outputPath, {
    projectData,
    codeStats: { total: 100, production: 60 },
  });
  assert.match(await readFile(outputPath, "utf8"), />25%</);
  assert.match(terminalSummary(models, "file:///tmp/progress.html"), /Code: 100 total lines · 60 production[\s\S]*VERA Script-to-Timeline Roadmap: 1 of 4 work items Done \(25\.0%\)[\s\S]*3 remaining[\s\S]*1 Blocked[\s\S]*Dashboard: file:\/\/\/tmp\/progress\.html/);
});

test("writes both configured VERA boards into one dashboard", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const outputPath = path.join(directory, "index.html");
  const models = await writeDashboard(repositoryRoot, outputPath, {
    projectDataByNumber: { 1: projectData, 2: projectData },
    codeStatsByNumber: {
      1: { total: 100, production: 60 },
      2: { total: 200, production: 120 },
    },
  });
  const html = await readFile(outputPath, "utf8");

  assert.equal(models.length, 2);
  assert.match(html, /data-project="1"[\s\S]*VERA Research Roadmap/);
  assert.match(html, /data-project="2"[\s\S]*VERA Script-to-Timeline Roadmap/);
  assert.match(html, /<b>2 of 8<\/b> work items done across both boards/);
  assert.match(html, /data-project="1"[\s\S]*<b>100<\/b> lines of code, <b>60<\/b> production[\s\S]*data-project="2"[\s\S]*<b>200<\/b> lines of code, <b>120<\/b> production/);
  assert.match(html, /<h3 id="project-1-ws">Research<\/h3>[\s\S]*<h3 id="project-2-ws">Script-to-Timeline<\/h3>/);
  assert.equal(html.match(/Goal rollups/g)?.length, 2);
  assert.match(html, /Updated /);
  assert.match(terminalSummary(models, "file:///tmp/progress.html"), /VERA Research Roadmap[\s\S]*VERA Script-to-Timeline Roadmap/);
});

test("keeps board progress available when the optional Research checkout is missing", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const outputPath = path.join(directory, "index.html");
  const originalResearchPath = process.env.VERA_RESEARCH_REPOSITORY;
  process.env.VERA_RESEARCH_REPOSITORY = path.join(directory, "missing-research-checkout");
  try {
    const models = await writeDashboard(repositoryRoot, outputPath, {
      projectDataByNumber: { 1: projectData, 2: projectData },
      codeStatsByNumber: { 2: { total: 200, production: 120 } },
    });
    const html = await readFile(outputPath, "utf8");
    assert.equal(models[0].codeStats, null);
    assert.match(html, /Lines of code unavailable/);
    assert.match(html, /Set VERA_RESEARCH_REPOSITORY to the local checkout/);
    assert.doesNotMatch(html, new RegExp(directory.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.match(
      terminalSummary(models, "file:///tmp/progress.html"),
      /Code: unavailable \(Set VERA_RESEARCH_REPOSITORY/,
    );
  } finally {
    if (originalResearchPath === undefined) delete process.env.VERA_RESEARCH_REPOSITORY;
    else process.env.VERA_RESEARCH_REPOSITORY = originalResearchPath;
  }
});

test("fails clearly when the live GitHub Project is unavailable", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const originalPath = process.env.PATH;
  process.env.PATH = "";
  try {
    await assert.rejects(() => writeDashboard(repositoryRoot, path.join(directory, "index.html")), /GitHub GraphQL budget could not be checked/);
  } finally {
    process.env.PATH = originalPath;
  }
});
