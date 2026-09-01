import { mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

export const DEFAULT_ROADMAP_LOCK_PATH = path.join(os.tmpdir(), "vera-roadmap-github-graphql.lock");

function ownerPath(lockPath) {
  return path.join(lockPath, "owner.json");
}

function readOwner(lockPath) {
  try {
    return JSON.parse(readFileSync(ownerPath(lockPath), "utf8"));
  } catch {
    return null;
  }
}

function processIsAlive(pid) {
  if (!Number.isInteger(pid) || pid < 1) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error?.code === "EPERM";
  }
}

function staleLock(lockPath, owner, now, staleAfterMs) {
  if (owner && processIsAlive(owner.pid)) return false;
  const startedAt = Date.parse(owner?.startedAt);
  if (!Number.isNaN(startedAt)) return now - startedAt >= staleAfterMs;
  try {
    return now - statSync(lockPath).mtimeMs >= staleAfterMs;
  } catch {
    return false;
  }
}

export function acquireRoadmapLock({
  lockPath = process.env.VERA_ROADMAP_LOCK_PATH || DEFAULT_ROADMAP_LOCK_PATH,
  now = Date.now(),
  pid = process.pid,
  staleAfterMs = 15 * 60 * 1000,
} = {}) {
  const startedAt = new Date(now).toISOString();
  const owner = {
    pid,
    startedAt,
    task: process.env.CODEX_THREAD_ID || null,
  };

  const create = () => {
    mkdirSync(lockPath, { mode: 0o700 });
    writeFileSync(ownerPath(lockPath), `${JSON.stringify(owner)}\n`, { encoding: "utf8", mode: 0o600 });
  };

  try {
    create();
  } catch (error) {
    if (error?.code !== "EEXIST") throw error;
    const current = readOwner(lockPath);
    if (!staleLock(lockPath, current, now, staleAfterMs)) {
      const identity = current?.task ? `task ${current.task}` : current?.pid ? `process ${current.pid}` : "another process";
      throw new Error(`Another VERA roadmap command is active (${identity}). Wait for it to finish, then retry; no GitHub request was attempted.`, {
        cause: error,
      });
    }
    rmSync(lockPath, { recursive: true, force: true });
    create();
  }

  let released = false;
  return () => {
    if (released) return;
    released = true;
    const current = readOwner(lockPath);
    if (current?.pid === pid && current?.startedAt === startedAt) {
      rmSync(lockPath, { recursive: true, force: true });
    }
  };
}
