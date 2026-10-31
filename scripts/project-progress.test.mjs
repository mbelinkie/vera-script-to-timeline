import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { startProgressServer } from "./project-progress-live.mjs";

import {
  buildProgressModel,
  buildSharedRoadmap,
  fetchNativeDependencies,
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
    repository: null, queueOrder: null, queueOrderInvalid: false,
    programMilestone: null, milestoneOrder: null, blockedBy: null,
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


test("live rendering adds a refresh button and connection status without changing static snapshots", () => {
  const model = buildProgressModel(parseProjectItems(projectData));
  const offline = renderDashboard(model);
  const online = renderDashboard(model, { live: true });
  assert.doesNotMatch(offline, /id="refresh-now"/);
  assert.match(online, /id="refresh-now"/);
  assert.match(online, /id="live-status"/);
  assert.match(online, /fetch\('\/status'/);
  assert.match(online, /fetch\('\/refresh'/);
});

test("local dashboard server refreshes on demand and retains the last good snapshot on errors", async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "vera-live-"));
  const outputPath = path.join(directory, "index.html");
  await writeFile(outputPath, '<html lang="en"><body>version 1</body></html>');
  let fakeTime = 1_800_000;
  let generated = 1;
  let shouldFail = false;
  const live = await startProgressServer({
    outputPath,
    refreshIntervalMs: 60_000,
    now: () => fakeTime,
    generate: async (destination) => {
      if (shouldFail) throw new Error("GitHub temporarily unavailable");
      generated += 1;
      await writeFile(destination, `<html lang="en"><body>version ${generated}</body></html>`);
    },
  });
  t.after(() => live.close());

  const first = await fetch(live.url);
  assert.match(await first.text(), /data-snapshot-version="1"/);
  const firstStatus = await (await fetch(`${live.url}status`)).json();
  assert.equal(firstStatus.version, 1);
  assert.equal(firstStatus.refreshing, false);

  const manual = await fetch(`${live.url}refresh`, {
    method: "POST", headers: { "X-VERA-Refresh": "1" },
  });
  assert.equal(manual.status, 200);
  assert.equal((await manual.json()).version, 2);
  assert.match(await (await fetch(live.url)).text(), /version 2/);

  fakeTime += 60_001;
  shouldFail = true;
  const failed = await fetch(`${live.url}refresh`, {
    method: "POST", headers: { "X-VERA-Refresh": "1" },
  });
  assert.equal(failed.status, 503);
  assert.match((await failed.json()).error, /GitHub temporarily unavailable/);
  assert.match(await (await fetch(live.url)).text(), /version 2/);

  shouldFail = false;
  fakeTime += 5 * 60_000 + 1;
  await fetch(`${live.url}status`); // A visible page checks; server finds an expired snapshot.
  await live.refresh(); // Share the in-flight auto-refresh to make the assertion deterministic.
  assert.equal((await (await fetch(`${live.url}status`)).json()).version, 3);
  assert.match(await (await fetch(live.url)).text(), /version 3/);
});

function programIssue(number, repo, queueOrder, programMilestone, extras = {}) {
  return {
    status: extras.status ?? "Ready",
    labels: ["type:implementation", "model:terra", "effort:high"],
    "Queue Order": queueOrder, "Program Milestone": programMilestone,
    "Milestone Order": extras.milestoneOrder ?? null,
    blockedBy: extras.blockedBy ?? null,
    size: extras.size ?? null,
    content: { type: "Issue", number, title: extras.title ?? `${repo} work ${number}`,
      url: `https://github.com/test/${repo}/issues/${number}` },
  };
}

function programModel(items, projectNumber, projectTitle) {
  return { ...buildProgressModel(parseProjectItems({ totalCount: items.length, items })),
    projectNumber, projectTitle };
}

test("renders a globally ordered cross-repository execution queue and milestone percentages", () => {
  const research = programModel([
    programIssue(1, "vera-research", 10, "01 Research", { status: "Done", blockedBy: [] }),
    programIssue(2, "vera-research", 20, "01 Research", {
      blockedBy: ["https://github.com/test/vera-research/issues/1"],
    }),
  ], 1, "VERA Research Roadmap");
  const implementation = programModel([
    programIssue(1, "script-to-timeline", 30, "02 Implementation", {
      blockedBy: ["https://github.com/test/vera-research/issues/2"],
    }),
  ], 2, "VERA Script-to-Timeline Roadmap");
  const roadmap = buildSharedRoadmap([research, implementation]);
  assert.deepEqual(roadmap.queue.map((item) => item.queueOrder), [10, 20, 30]);
  assert.deepEqual(roadmap.milestones.map((m) => [m.name, m.done, m.total]),
    [["01 Research", 1, 2], ["02 Implementation", 0, 1]]);
  assert.deepEqual(roadmap.warnings, []);
  assert.equal(roadmap.unverifiedCount, 0);
  const html = renderDashboard([research, implementation]);
  assert.match(html, /Master execution queue/);
  assert.match(html, /Program milestones/);
  assert.match(html, /All queued issue dependencies are ordered correctly/);
  assert.ok(html.indexOf('class="order">10') < html.indexOf('class="order">20'));
  assert.ok(html.indexOf('class="order">20') < html.indexOf('class="order">30'));
  assert.match(html, /<option value="vera-research">vera-research<\/option>/);
  assert.match(html, /<b>1 of 3<\/b> work items done across both boards/);
});

test("flags reversed, missing, and duplicate queue positions instead of auto-fixing them", () => {
  const model = programModel([
    programIssue(5, "research", 40, "M1", { blockedBy: [] }),
    programIssue(6, "application", 20, "M2", {
      blockedBy: ["https://github.com/test/research/issues/5", "https://github.com/test/absent/issues/9"],
    }),
    programIssue(7, "application", 20, "M2", { blockedBy: [] }),
  ], 1, "VERA Shared");
  const roadmap = buildSharedRoadmap(model);
  assert.equal(roadmap.queue[0].queueOrder, 20);
  assert.match(roadmap.warnings.join(" "), /Queue #20 is assigned to both/);
  assert.match(roadmap.warnings.join(" "), /depends on test\/research#5 at #40/);
  assert.match(roadmap.warnings.join(" "), /which has no queue position/);
  assert.match(renderDashboard(model), /Out of order/);
});

test("does not report a clean dependency audit when GitHub relationships were not fetched", () => {
  const model = programModel([programIssue(10, "research", 10, "Research")], 1, "VERA Research");
  const roadmap = buildSharedRoadmap(model);
  assert.equal(roadmap.unverifiedCount, 1);
  assert.match(renderDashboard(model), /Do not assume the order is valid/);
  assert.doesNotMatch(renderDashboard(model), /All queued issue dependencies are ordered correctly/);
});

test("allows identical issue numbers in distinct repositories and de-duplicates shared-project items", () => {
  const first = programIssue(42, "research", 10, "Research", { blockedBy: [] });
  const second = programIssue(42, "implementation", 20, "Build", { blockedBy: [] });
  const combined = programModel([first, second], 2, "VERA Master");
  assert.equal(combined.totalWork, 2);
  const research = programModel([first], 1, "Research");
  const roadmap = buildSharedRoadmap([research, combined]);
  assert.equal(roadmap.queue.length, 2);
  assert.equal(roadmap.duplicateCount, 1);
});

test("reads native GitHub issue blockedBy data across repositories and reports GraphQL failures", async () => {
  const model = programModel([
    programIssue(3, "research", 10, "Research"),
    programIssue(4, "implementation", 20, "Implementation"),
  ], 2, "Master");
  const queryCalls = [];
  const data = await fetchNativeDependencies("/tmp", [model], {
    queryGraphql: async (query) => {
      queryCalls.push(query);
      return { data: { i0: { issue: { blockedBy: { totalCount: 0, pageInfo: { hasNextPage: false }, nodes: [] } } },
        i1: { issue: { blockedBy: { totalCount: 1, pageInfo: { hasNextPage: false }, nodes: [
          { url: "https://github.com/test/research/issues/3", state: "OPEN" },
        ] } } } } };
    },
  });
  assert.equal(queryCalls.length, 1);
  assert.match(queryCalls[0], /blockedBy\(first:50\)/);
  assert.equal(data.verified.length, 2);
  assert.equal(buildSharedRoadmap([model], data).unverifiedCount, 0);
  assert.equal(buildSharedRoadmap([model], data).warnings.length, 0);
  const failure = await fetchNativeDependencies("/tmp", [model], {
    queryGraphql: async () => { throw new Error("Permissions denied"); },
  });
  assert.equal(failure.verified.length, 0);
  assert.equal(buildSharedRoadmap([model], failure).unverifiedCount, 2);
  assert.match(failure.errors.join(" "), /Permissions denied/);
});

test("renders missing setup guidance and escapes untrusted milestone names", () => {
  const empty = buildProgressModel(parseProjectItems(projectData));
  assert.match(renderDashboard(empty), /No queue entries yet/);
  const malicious = programModel([programIssue(11, "research", 50, '<img src=x onerror=alert(1)>', { blockedBy: [] })], 1, "Research");
  const html = renderDashboard(malicious);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img src=x onerror=alert\(1\)>/);
});


test("shows issue Size in the master queue with a functional size filter and unassigned fallback", () => {
  const model = programModel([
    programIssue(10, "research", 10, "Discovery", { size: "S", blockedBy: [] }),
    programIssue(11, "research", 20, "Discovery", { size: "XXL", blockedBy: [] }),
    programIssue(12, "implementation", 30, "Build", { size: "Large", blockedBy: [] }),
    programIssue(13, "implementation", 40, "Build", { blockedBy: [] }),
  ], 2, "VERA Master");
  const html = renderDashboard(model);
  assert.match(html, /<th scope="col">Size<\/th>/);
  assert.match(html, /data-queue-size="s"[^>]*>[\s\S]*?S · Small/);
  assert.match(html, /data-queue-size="xxl"[^>]*>[\s\S]*?XXL · Huge/);
  assert.match(html, /data-queue-size="l"[^>]*>[\s\S]*?L · Large/);
  assert.match(html, /data-queue-size="unsized"[^>]*>[\s\S]*?Unassigned/);
  assert.match(html, /<label for="queue-size">Size<\/label>/);
  assert.match(html, /<option value="xxl">XXL · Huge<\/option>/);
  assert.match(html, /queueSize\.addEventListener\('change', filterQueue\)/);
  assert.match(html, /row\.dataset\.queueSize === queueSize\.value/);
  assert.match(html, /Size is a relative scope estimate/);
});

test("preserves sizes when an issue is tracked by both GitHub Projects", () => {
  const research = programModel([
    programIssue(14, "research", null, "Discovery", { size: "XL", blockedBy: [] }),
  ], 1, "Research");
  const master = programModel([
    programIssue(14, "research", 10, "Discovery", { blockedBy: [] }),
  ], 2, "Master");
  const roadmap = buildSharedRoadmap([research, master]);
  assert.equal(roadmap.queue.length, 1);
  assert.equal(roadmap.queue[0].size, "XL");
  assert.match(renderDashboard([research, master]), /XL · Extra large/);

  const conflict = programModel([
    programIssue(14, "research", 10, "Discovery", { size: "S", blockedBy: [] }),
  ], 2, "Master");
  assert.match(buildSharedRoadmap([research, conflict]).warnings.join(" "), /Conflicting Size/);
});

test("escapes custom GitHub Size values as untrusted text", () => {
  const model = programModel([
    programIssue(15, "research", 10, "Discovery", { size: '<script>alert("x")</script>', blockedBy: [] }),
  ], 1, "Research");
  const html = renderDashboard(model);
  assert.match(html, /&lt;script&gt;alert\(&quot;x&quot;\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>alert\("x"\)<\/script>/);
});
