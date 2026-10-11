// Isolate the existing two-process CLI replay and retain its unchanged bytes/timing.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const cached = process.argv[2] === "cached";
const environment = { ...process.env };
delete environment.NODE_COMPILE_CACHE;
delete environment.NODE_DISABLE_COMPILE_CACHE;
if (cached) environment.NODE_COMPILE_CACHE = resolve("test-results/issue-180/node-compile-cache");
const args = ["packages/contracts/src/issue-144-compile-cli.ts", "tests/data/slice_1_1/minimal.script-document.json", "tests/data/slice_1_3/minimal.compiler-dependencies.json"];
const invoke = () => {
  const start = performance.now();
  const result = spawnSync(process.execPath, args, { env: environment, encoding: "utf8" });
  const elapsedMs = performance.now() - start;
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).ok, true);
  return { stdout: result.stdout, elapsedMs };
};
const prime = cached ? invoke() : null;
const first = invoke(); const second = invoke();
assert.equal(first.stdout, second.stdout);
if (prime) assert.equal(prime.stdout, first.stdout);
const result = {
  mode: cached ? "cached" : "uncached", nodeVersion: process.version,
  elapsedMs: [first.elapsedMs, second.elapsedMs], replayElapsedMs: first.elapsedMs + second.elapsedMs,
  primeElapsedMs: prime?.elapsedMs ?? null,
  stdoutSHA256: createHash("sha256").update(first.stdout).digest("hex"),
  byteIdentical: true, withinExisting5000msGate: first.elapsedMs + second.elapsedMs < 5000,
};
mkdirSync("test-results/issue-180", { recursive: true });
writeFileSync(`test-results/issue-180/cli-replay-${result.mode}.json`, `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result));
process.exitCode = result.withinExisting5000msGate ? 0 : 1;
