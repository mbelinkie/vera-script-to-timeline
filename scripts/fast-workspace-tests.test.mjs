import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { URL, fileURLToPath } from "node:url";

import { fastWorkspaces, runWorkspaces, scheduleFastWorkspaces } from "./fast-workspace-tests-lib.mjs";

test("selects exactly the existing fast workspace scripts and keeps all their original commands", () => {
  const root = fileURLToPath(new URL("..", import.meta.url));
  const selected = fastWorkspaces(root);
  const expected = [
    "contracts", "project-authorization", "project-builds", "project-documents",
    "project-service-host", "public-page-capture", "spotlight-evidence",
    "spotlight-matte", "tooling-smoke",
  ];
  assert.deepEqual(selected.map(({ path }) => path), expected.map((name) => `packages/${name}`));
  for (const { path } of selected) {
    const { scripts } = JSON.parse(readFileSync(join(root, path, "package.json"), "utf8"));
    assert.equal(typeof scripts["test:fast"], "string");
    assert.ok(scripts["test:fast"].length > 0);
  }
});

test("new test workspace without an explicit fast script fails closed", () => {
  const root = mkdtempSync(join(tmpdir(), "vera-fast-workspaces-"));
  try {
    mkdirSync(join(root, "packages", "new"), { recursive: true });
    writeFileSync(join(root, "package.json"), JSON.stringify({ workspaces: ["packages/*"] }));
    writeFileSync(join(root, "packages", "new", "package.json"), JSON.stringify({
      name: "new", scripts: { test: "node --test" },
    }));
    assert.throws(() => fastWorkspaces(root), /has test but no test:fast/);
    writeFileSync(join(root, "package.json"), JSON.stringify({ workspaces: ["other/*"] }));
    assert.throws(() => fastWorkspaces(root), /selection audit/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("time-sensitive backup guard suite runs alone without dropping or duplicating fast workspaces", () => {
  const root = fileURLToPath(new URL("..", import.meta.url));
  const selected = fastWorkspaces(root);
  const { exclusive, parallel } = scheduleFastWorkspaces(selected);
  assert.deepEqual(exclusive.map(({ path }) => path), ["packages/project-service-host"]);
  assert.deepEqual([...exclusive, ...parallel].map(({ path }) => path).sort(),
    selected.map(({ path }) => path).sort());
});

test("bounded parallel runner executes each workspace once, including the final suite", async () => {
  const selected = Array.from({ length: 8 }, (_, index) => ({ name: `suite-${index}` }));
  const started = [];
  const pending = [];
  const outcome = runWorkspaces(selected, {
    concurrency: 3,
    run: (item) => {
      started.push(item.name);
      return new Promise((resolve) => pending.push(resolve));
    },
    write: () => {},
  });
  assert.deepEqual(started, ["suite-0", "suite-1", "suite-2"]);
  for (let index = 0; index < selected.length; index += 1) {
    pending[index](0);
    await Promise.resolve();
    assert.equal(started.length, Math.min(index + 4, selected.length));
  }
  assert.equal(await outcome, 0);
  assert.deepEqual(started, selected.map(({ name }) => name));
});

test("failure stops scheduling new suites and propagates nonzero after in-flight children finish", async () => {
  const called = [];
  const pending = [];
  const outcome = runWorkspaces(["a", "b", "c", "d"], {
    concurrency: 2,
    run: (name) => {
      called.push(name);
      // Unexpected follow-on suites must settle rather than hanging the test.
      if (name === "c" || name === "d") return Promise.resolve(0);
      return new Promise((resolve) => pending.push(resolve));
    },
    write: () => {},
  });
  assert.deepEqual(called, ["a", "b"]);
  pending[0](3);
  await Promise.resolve();
  pending[1](0);
  assert.equal(await outcome, 3);
  assert.deepEqual(called, ["a", "b"]);
});

test("unexpected runner exception and invalid status both fail closed", async () => {
  const messages = [];
  assert.equal(await runWorkspaces(["a", "b"], {
    run: () => { throw new Error("missing npm"); },
    write: (message) => messages.push(message),
  }), 1);
  assert.match(messages[0], /missing npm/);
  assert.equal(await runWorkspaces(["a"], {
    run: () => null,
    write: () => {},
  }), 1);
});
