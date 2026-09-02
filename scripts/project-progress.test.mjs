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
  renderDashboard,
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

test("renders every issue once with escaped links and board metadata", () => {
  assert.equal(escapeHtml('<script data-name="test">&</script>'), "&lt;script data-name=&quot;test&quot;&gt;&amp;&lt;/script&gt;");
  const data = clone(projectData);
  data.items[4].content.title = "Investigate <unsafe> & missing metadata";
  const model = buildProgressModel(parseProjectItems(data));
  const firstRender = renderDashboard(model);
  assert.equal(firstRender, renderDashboard(model));
  assert.match(firstRender, /VERA Board Progress/);
  assert.match(firstRender, /3 remaining/);
  assert.match(firstRender, /Goals are shown separately/);
  assert.match(firstRender, /href="https:\/\/example\.test\/2"/);
  assert.match(firstRender, /Investigate &lt;unsafe&gt; &amp; missing metadata/);
  assert.match(firstRender, /Metadata missing/);
  for (let issue = 1; issue <= 5; issue += 1) {
    assert.equal(firstRender.match(new RegExp(`data-issue="${issue}"`, "g"))?.length, 1);
  }
  assert.doesNotMatch(firstRender, /weighted estimate|eleven-phase|60 slices/i);
});

test("writes the dashboard and reports an exact terminal summary", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const outputPath = path.join(directory, "nested", "index.html");
  const model = await writeDashboard(repositoryRoot, outputPath, { projectData });
  assert.match(await readFile(outputPath, "utf8"), /25\.0%/);
  assert.match(terminalSummary(model, "file:///tmp/progress.html"), /1 of 4 board work items Done \(25\.0%\)[\s\S]*3 remaining[\s\S]*1 Blocked[\s\S]*Dashboard: file:\/\/\/tmp\/progress\.html/);
});

test("fails clearly when the live GitHub Project is unavailable", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-progress-"));
  const originalPath = process.env.PATH;
  process.env.PATH = "";
  try {
    await assert.rejects(() => writeDashboard(repositoryRoot, path.join(directory, "index.html")), /GitHub Project is unavailable/);
  } finally {
    process.env.PATH = originalPath;
  }
});
