import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  buildProgressModel,
  escapeHtml,
  loadProgressModel,
  parseProjectItems,
  parseRoadmap,
  renderDashboard,
  writeDashboard,
} from "./project-progress-lib.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

const projectData = {
  items: [
    {
      status: "Done",
      labels: ["model:terra", "effort:high", "type:implementation"],
      content: { number: 101, title: "Slice 0.1 — Repository scaffold", url: "https://example.test/101" },
    },
    {
      status: "In progress",
      labels: ["model:terra", "effort:high", "type:implementation"],
      content: { number: 114, title: "Slice 1.4 — Package writer", url: "https://example.test/114" },
    },
  ],
};

test("parses the authoritative roadmap and GitHub Project items", async () => {
  const specification = await readFile(
    path.join(
      repositoryRoot,
      "docs",
      "Script-to-Timeline Product Spec - Fable Rev2.md",
    ),
    "utf8",
  );
  const phases = parseRoadmap(specification);
  const tracker = parseProjectItems(projectData);

  assert.equal(phases.length, 11);
  assert.equal(
    phases.reduce((total, phase) => total + phase.slices.length, 0),
    60,
  );
  assert.equal(phases[0].slices[0].id, "0.1");
  assert.equal(phases.at(-1).slices.at(-1).id, "10.4");
  assert.match(phases[8].promise, /^edit viewer-facing English subtitle copy/);
  assert.match(phases[10].gate, /sole edited prior timeline intact\.$/);
  assert.equal(tracker.statuses.get("0.1"), "Accepted");
  assert.equal(tracker.statuses.get("1.4"), "In progress");
  assert.deepEqual(tracker.routes.get("1.4"), {
    model: "terra",
    effort: "high",
    issueNumber: 114,
    url: "https://example.test/114",
    projectStatus: "In progress",
  });
});

test("calculates accepted and weighted progress without overstating acceptance", () => {
  const phases = [
    {
      id: 0,
      name: "Foundation",
      promise: "test the boundary",
      gate: "the boundary works",
      slices: [
        { id: "0.1", name: "Accepted work" },
        { id: "0.2", name: "Agent-complete work" },
        { id: "0.3", name: "Active work" },
      ],
    },
    {
      id: 1,
      name: "Future",
      promise: "build the future",
      gate: "the future works",
      slices: [
        { id: "1.1", name: "Paused work" },
        { id: "1.2", name: "Blocked work" },
        { id: "1.3", name: "Queued work" },
      ],
    },
  ];
  const model = buildProgressModel(phases, {
    lastUpdated: "today",
    statuses: new Map([
      ["0.1", "Accepted"],
      ["0.2", "Agent complete"],
      ["0.3", "In progress"],
      ["1.1", "Paused"],
      ["1.2", "Blocked"],
    ]),
  });

  assert.equal(model.totalPhases, 2);
  assert.equal(model.acceptedPhases, 0);
  assert.equal(model.totalSlices, 6);
  assert.equal(model.acceptedSlices, 1);
  assert.equal(model.estimatedUnits, 3.15);
  assert.equal(model.statusCounts.Queued, 1);
  assert.ok(Math.abs(model.phases[0].acceptedPercent - 33.333_333) < 0.000_001);
  assert.equal(model.phases[0].estimatedPercent, 80);
  assert.equal(model.phases[1].acceptedPercent, 0);
  assert.equal(model.phases[1].estimatedPercent, 25);
});

test("rejects tracker rows that do not exist in the roadmap", () => {
  const phases = [
    {
      id: 0,
      name: "Foundation",
      promise: "test the boundary",
      gate: "the boundary works",
      slices: [{ id: "0.1", name: "First" }],
    },
  ];
  const tracker = {
    lastUpdated: "today",
    statuses: new Map([
      ["0.1", "Accepted"],
      ["9.9", "In progress"],
    ]),
  };

  assert.throws(
    () => buildProgressModel(phases, tracker),
    /Tracked slices missing from the roadmap: 9\.9/,
  );
});

test("renders escaped, deterministic HTML and writes the dashboard", async () => {
  assert.equal(
    escapeHtml('<script data-name="test">&</script>'),
    "&lt;script data-name=&quot;test&quot;&gt;&amp;&lt;/script&gt;",
  );

  const model = await loadProgressModel(repositoryRoot, { projectData });
  const firstRender = renderDashboard(model);
  const secondRender = renderDashboard(model);
  assert.equal(firstRender, secondRender);
  assert.match(firstRender, /VERA Project Progress/);
  assert.ok(firstRender.includes(`${model.estimatedPercent.toFixed(1)}%`));
  assert.doesNotMatch(firstRender, /undefined/);

  const temporaryDirectory = await mkdtemp(
    path.join(os.tmpdir(), "vera-progress-"),
  );
  const outputPath = path.join(temporaryDirectory, "nested", "index.html");
  const originalGhPath = process.env.PATH;
  process.env.PATH = "";
  await assert.rejects(() => writeDashboard(repositoryRoot, outputPath), /GitHub Project is unavailable/);
  process.env.PATH = originalGhPath;
  const htmlPath = path.join(temporaryDirectory, "fixture", "index.html");
  const html = renderDashboard(model);
  await (await import("node:fs/promises")).mkdir(path.dirname(htmlPath), { recursive: true });
  await (await import("node:fs/promises")).writeFile(htmlPath, html, "utf8");
  assert.equal(await readFile(htmlPath, "utf8"), firstRender);
});
