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
  parseProgressTracker,
  parseRoadmap,
  renderDashboard,
  writeDashboard,
} from "./project-progress-lib.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

test("parses the current authoritative roadmap and progress tracker", async () => {
  const specification = await readFile(
    path.join(
      repositoryRoot,
      "docs",
      "Script-to-Timeline Product Spec - Fable Rev2.md",
    ),
    "utf8",
  );
  const progressDocument = await readFile(
    path.join(repositoryRoot, "docs", "IMPLEMENTATION_PROGRESS.md"),
    "utf8",
  );
  const phases = parseRoadmap(specification);
  const tracker = parseProgressTracker(progressDocument);

  assert.equal(phases.length, 11);
  assert.equal(
    phases.reduce((total, phase) => total + phase.slices.length, 0),
    59,
  );
  assert.equal(phases[0].slices[0].id, "0.1");
  assert.equal(phases.at(-1).slices.at(-1).id, "10.4");
  assert.equal(tracker.statuses.get("0.4"), "Agent complete");
  assert.equal(tracker.statuses.get("1.1"), "Paused");
});

test("calculates accepted and weighted progress without overstating acceptance", async () => {
  const model = await loadProgressModel(repositoryRoot);

  assert.equal(model.totalPhases, 11);
  assert.equal(model.acceptedPhases, 0);
  assert.equal(model.totalSlices, 59);
  assert.equal(model.acceptedSlices, 3);
  assert.equal(model.estimatedUnits, 4.4);
  assert.equal(model.statusCounts.Queued, 54);
  assert.equal(model.phases[0].acceptedPercent, 75);
  assert.equal(model.phases[0].estimatedPercent, 97.5);
  assert.equal(model.phases[1].acceptedPercent, 0);
  assert.ok(Math.abs(model.phases[1].estimatedPercent - 7.142_857) < 0.000_001);
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

  const model = await loadProgressModel(repositoryRoot);
  const firstRender = renderDashboard(model);
  const secondRender = renderDashboard(model);
  assert.equal(firstRender, secondRender);
  assert.match(firstRender, /VERA Project Progress/);
  assert.match(firstRender, /7\.5%/);
  assert.doesNotMatch(firstRender, /undefined/);

  const temporaryDirectory = await mkdtemp(
    path.join(os.tmpdir(), "vera-progress-"),
  );
  const outputPath = path.join(temporaryDirectory, "nested", "index.html");
  await writeDashboard(repositoryRoot, outputPath);
  assert.equal(await readFile(outputPath, "utf8"), firstRender);
});
