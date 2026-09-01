import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { acquireRoadmapLock } from "./roadmap-lock.mjs";

function temporaryLock() {
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-roadmap-lock-test-"));
  return { directory, lockPath: path.join(directory, "roadmap.lock") };
}

test("serializes roadmap commands before any GitHub request", (t) => {
  const { directory, lockPath } = temporaryLock();
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const release = acquireRoadmapLock({ lockPath });
  assert.throws(() => acquireRoadmapLock({ lockPath }), /Another VERA roadmap command is active.*no GitHub request was attempted/);
  release();
  assert.equal(existsSync(lockPath), false);
});

test("reclaims a sufficiently old lock whose owner process is gone", (t) => {
  const { directory, lockPath } = temporaryLock();
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  mkdirSync(lockPath);
  writeFileSync(
    path.join(lockPath, "owner.json"),
    `${JSON.stringify({ pid: 999_999_999, startedAt: "2026-08-31T20:00:00.000Z", task: "stale-task" })}\n`,
  );
  const release = acquireRoadmapLock({
    lockPath,
    now: Date.parse("2026-08-31T20:16:00.000Z"),
    pid: process.pid,
  });
  assert.equal(existsSync(lockPath), true);
  release();
  assert.equal(existsSync(lockPath), false);
});
