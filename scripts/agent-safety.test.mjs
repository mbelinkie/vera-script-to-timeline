import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

import { assessWorktree, classifyCommand } from "./agent-safety.mjs";

test("blocks destructive Git variants but preserves ordinary Git commands", () => {
  for (const [category, command] of [
    ["force push", "git push origin main --force-with-lease"],
    ["hard reset", "git reset --hard HEAD~1"],
    ["forced clean", "git clean -dfx"],
    ["destructive branch deletion", "git branch --delete --force old-work"],
    ["broad checkout", "git checkout -- ."],
    ["broad restore", "git restore --worktree --staged ."],
    ["broad recursive delete", 'rm -rf "$HOME"'],
  ]) {
    assert.equal(classifyCommand(command)?.category, category, command);
  }

  for (const command of [
    "git status --short",
    "git diff --check",
    "git log -1",
    "git push origin feature-branch",
    "git push -v origin feature-branch",
    "git checkout feature-branch",
    "git branch -d merged-branch",
    "git restore README.md",
    "rm -rf node_modules",
    "npm run validate",
  ]) {
    assert.equal(classifyCommand(command), null, command);
  }
});

test("blocks alternate force-push spellings", () => {
  for (const command of [
    "git push -f origin main",
    "git push -vf origin main",
    "git push origin main --force-if-includes",
    "git push origin +main",
  ]) {
    assert.equal(classifyCommand(command)?.category, "force push", command);
  }
});

test("blocks force pushes after supported Git global options", () => {
  for (const command of [
    "git -c core.quotepath=false push --force origin main",
    "git --no-pager push --force origin main",
  ]) {
    assert.equal(classifyCommand(command)?.category, "force push", command);
  }
});

test("blocks absolute and explicit broad recursive-delete targets", () => {
  for (const command of [
    "rm -rf /",
    "rm -rf /tmp/build",
    "rm -rf .",
    "rm -rf ../",
    "rm -rf ../*",
    "rm -rf '~/'",
    "rm -rf '$HOME'",
    "rm -rf '${HOME}/Downloads'",
  ]) {
    assert.equal(classifyCommand(command)?.category, "broad recursive delete", command);
  }
});

test("blocks combined force-delete branch flags", () => {
  assert.equal(classifyCommand("git branch -fd old-work")?.category, "destructive branch deletion");
  assert.equal(classifyCommand("git branch -d merged-branch"), null);
});

test("blocks recursive deletes that escape through normalized parent traversal", () => {
  for (const command of [
    "rm -rf ../../",
    "rm -rf child/../../",
    "rm -rf child/../../../tmp",
    "rm -rf ./../..",
    "rm -rf node_modules/..",
  ]) {
    assert.equal(classifyCommand(command)?.category, "broad recursive delete", command);
  }

  assert.equal(classifyCommand("rm -rf child/../output"), null);
});

test("blocks recursive deletion of the current worktree via PWD", () => {
  for (const command of ['rm -rf "$PWD"', 'rm -rf "${PWD}"']) {
    assert.equal(classifyCommand(command)?.category, "broad recursive delete", command);
  }
});

test("rejects a task outside its assigned linked worktree", () => {
  assert.deepEqual(
    assessWorktree({
      assignedWorktree: "/repo/worktrees/assigned",
      cwd: "/repo/worktrees/other/packages/app",
      gitRoot: "/repo/worktrees/other",
      gitDir: "/repo/.git/worktrees/other",
      commonGitDir: "/repo/.git",
    }),
    { ok: false, reason: "current Git worktree does not match the assigned worktree" },
  );
});

test("keeps the primary checkout available for bootstrap with advisory worktree scope", () => {
  assert.deepEqual(
    assessWorktree({
      assignedWorktree: "/repo",
      cwd: "/repo",
      gitRoot: "/repo",
      gitDir: "/repo/.git",
      commonGitDir: "/repo/.git",
    }),
    { ok: true, advisory: "primary checkout: linked-worktree scope is advisory" },
  );
});

test("Claude Code hook configuration runs the project-local guard on Bash", () => {
  const settings = JSON.parse(readFileSync(".claude/settings.json", "utf8"));
  const bashHook = settings.hooks?.PreToolUse?.find((entry) => entry.matcher === "Bash");
  assert.ok(bashHook);
  assert.match(bashHook.hooks?.[0]?.command ?? "", /\$\{CLAUDE_PROJECT_DIR\}\/scripts\/agent-safety\.mjs/u);
  assert.doesNotMatch(bashHook.hooks?.[0]?.command ?? "", /~\/\.claude/u);
  assert.equal(existsSync(".codex/hooks.json"), false);
});

test("hook classifies the command without executing it", () => {
  const cwd = process.cwd();
  const result = spawnSync(process.execPath, ["scripts/agent-safety.mjs", "hook"], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, VERA_ASSIGNED_WORKTREE: cwd },
    input: JSON.stringify({
      cwd,
      tool_name: "Bash",
      tool_input: { command: "git reset --hard && printf should-not-run" },
    }),
  });

  assert.equal(result.status, 2);
  assert.match(result.stderr, /BLOCKED.*hard reset/u);
  assert.doesNotMatch(result.stdout, /should-not-run/u);
});

test("hook leaves a read-only Git command in its assigned linked worktree alone", () => {
  const cwd = process.cwd();
  const result = spawnSync(process.execPath, ["scripts/agent-safety.mjs", "hook"], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, VERA_ASSIGNED_WORKTREE: cwd },
    input: JSON.stringify({
      cwd,
      tool_name: "Bash",
      tool_input: { command: "git status --short" },
    }),
  });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
});

test("primary checkout allows safe bootstrap commands without executing them", () => {
  const cwd = process.cwd();
  const commonGitDir = spawnSync("git", ["rev-parse", "--git-common-dir"], {
    cwd,
    encoding: "utf8",
  });
  assert.equal(commonGitDir.status, 0, commonGitDir.stderr);
  const primaryRoot = path.dirname(path.resolve(cwd, commonGitDir.stdout.trim()));
  const result = spawnSync(process.execPath, ["scripts/agent-safety.mjs", "hook"], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, VERA_ASSIGNED_WORKTREE: primaryRoot },
    input: JSON.stringify({
      cwd: primaryRoot,
      tool_name: "Bash",
      tool_input: { command: "git worktree add ../task-worktree origin/main" },
    }),
  });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
});
