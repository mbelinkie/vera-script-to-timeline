import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { URL } from "node:url";

import { FAST_PHASES, runFastPhases } from "./validate-fast-lib.mjs";

const expectedScripts = [
  "check:contracts-generated",
  "lint:typescript",
  "typecheck:typescript",
  "test:typescript:fast",
  "lint:python",
  "typecheck:python",
  "test:python:fast",
];

test("runs exactly the seven original npm scripts once, in order", () => {
  const called = [];
  const lines = [];
  let clock = 0;
  const report = runFastPhases({
    now: () => clock,
    run: (script) => {
      called.push(script);
      clock += 1000;
      return 0;
    },
    write: (line) => lines.push(line),
  });

  assert.deepEqual(FAST_PHASES.map(([, script]) => script), expectedScripts);
  assert.deepEqual(FAST_PHASES.map(([name]) => name), [
    "contracts", "ts-lint", "ts-types", "ts-tests", "py-lint", "py-types", "py-tests",
  ]);
  assert.deepEqual(called, expectedScripts);
  assert.equal(report.phases.length, 7);
  assert.equal(report.totalSeconds, 7);
  assert.equal(report.exitCode, 0);
  assert.deepEqual(report.phases.map(({ seconds }) => seconds), Array(7).fill(1));
  assert.match(lines[0], /contracts: 1\.000s PASS/);
  assert.equal(lines.at(-1), "[validate:fast] total: 7.000s; exit=0");
});

test("stops at the failing phase, preserving the child exit status and total", () => {
  const called = [];
  const lines = [];
  let clock = 0;
  const report = runFastPhases({
    now: () => clock,
    run: (script) => {
      called.push(script);
      clock += 500;
      return called.length === 3 ? 42 : 0;
    },
    write: (line) => lines.push(line),
  });

  assert.deepEqual(called, expectedScripts.slice(0, 3));
  assert.deepEqual(report.phases.map(({ exitCode }) => exitCode), [0, 0, 42]);
  assert.equal(report.exitCode, 42);
  assert.equal(report.totalSeconds, 1.5);
  assert.match(lines[2], /ts-types: 0\.500s FAIL \(exit=42\)/);
  assert.equal(lines.at(-1), "[validate:fast] total: 1.500s; exit=42");
});

test("a missing child command fails closed before the next phase", () => {
  const called = [];
  const lines = [];
  let clock = 0;
  const report = runFastPhases({
    now: () => clock,
    run: (script) => {
      called.push(script);
      clock += 125;
      throw Object.assign(new Error("spawn npm ENOENT"), { code: "ENOENT" });
    },
    write: (line) => lines.push(line),
  });

  assert.deepEqual(called, [expectedScripts[0]]);
  assert.equal(report.exitCode, 1);
  assert.equal(report.totalSeconds, 0.125);
  assert.match(lines[0], /could not run: Error: spawn npm ENOENT/);
  assert.match(lines[1], /contracts: 0\.125s FAIL \(exit=1\)/);
  assert.equal(lines.at(-1), "[validate:fast] total: 0.125s; exit=1");
});

test("an unavailable child status cannot accidentally count as a pass", () => {
  const called = [];
  const report = runFastPhases({
    now: () => 0,
    run: (script) => {
      called.push(script);
      return null;
    },
    write: () => {},
  });

  assert.deepEqual(called, [expectedScripts[0]]);
  assert.equal(report.exitCode, 1);
});

test("package scripts include timer tests in both fast and full TS, without altering full validate", () => {
  const { scripts } = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.equal(scripts["validate:fast"], "node scripts/validate-fast.mjs");
  assert.equal(scripts.validate, "npm run check:contracts-generated && npm run check:typescript && npm run check:python");
  assert.equal(scripts["test:python:fast"], 'uv run --frozen pytest -m "(not slow) or fast" -n 8 --dist=worksteal');
  for (const name of ["test:typescript", "test:typescript:fast"]) {
    assert.match(scripts[name], /&& node --test scripts\/validate-fast\.test\.mjs$/);
  }
  for (const script of expectedScripts) assert.equal(typeof scripts[script], "string");
});
