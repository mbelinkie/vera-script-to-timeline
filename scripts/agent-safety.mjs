import { readFileSync, realpathSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const BROAD_DELETE_TARGETS = new Set(["/", "/*", ".", "./", "./*", "..", "../", "../*", "~", "~/", "*", "$HOME", "${HOME}"]);
const BROAD_GIT_PATHS = new Set([".", "./", "./*", ":/", ":(top)", "*"]);

function shellWords(value) {
  return (value.match(/"[^"]*"|'[^']*'|[^\s]+/gu) ?? []).map((word) => {
    if ((word.startsWith('"') && word.endsWith('"')) || (word.startsWith("'") && word.endsWith("'"))) {
      return word.slice(1, -1);
    }
    return word;
  });
}

function gitTails(command, subcommand) {
  const optionWithValue = String.raw`(?:-C|--git-dir|--work-tree)(?:=|\s+)(?:"[^"]*"|'[^']*'|\S+)`;
  const pattern = new RegExp(String.raw`\bgit(?:\s+${optionWithValue})*\s+${subcommand}\b([^;&|\n]*)`, "giu");
  return [...command.matchAll(pattern)].map((match) => match[1]);
}

function hasOption(tail, longOption, shortOption) {
  return shellWords(tail).some((word) => word === longOption || word.startsWith(`${longOption}=`) || word === shortOption);
}

function hasShortFlag(tail, flag) {
  return shellWords(tail).some((word) => /^-[^-]+$/u.test(word) && word.slice(1).includes(flag));
}

function broadDeleteTarget(target) {
  const normalized = path.posix.normalize(target);
  return BROAD_DELETE_TARGETS.has(target) ||
    BROAD_DELETE_TARGETS.has(normalized) ||
    normalized === ".." ||
    normalized.startsWith("../") ||
    target.startsWith("/") ||
    target.startsWith("~/") ||
    target.startsWith("$HOME/") ||
    target.startsWith("${HOME}/");
}

export function classifyCommand(command) {
  for (const tail of gitTails(command, "push")) {
    const forcedRefspec = shellWords(tail).some((word) => word.startsWith("+") && word.length > 1);
    if (
      hasOption(tail, "--force", "-f") ||
      hasOption(tail, "--force-with-lease", "") ||
      hasOption(tail, "--force-if-includes", "") ||
      forcedRefspec
    ) {
      return { category: "force push", detail: "force-pushing can rewrite shared history" };
    }
  }

  for (const tail of gitTails(command, "reset")) {
    if (hasOption(tail, "--hard", "")) {
      return { category: "hard reset", detail: "a hard reset can discard worktree changes" };
    }
  }

  for (const tail of gitTails(command, "clean")) {
    if (hasOption(tail, "--force", "-f") || hasShortFlag(tail, "f")) {
      return { category: "forced clean", detail: "forced clean can delete untracked files" };
    }
  }

  for (const tail of gitTails(command, "branch")) {
    const forcedShortDelete = shellWords(tail).includes("-D");
    const forcedLongDelete = hasOption(tail, "--delete", "-d") && hasOption(tail, "--force", "-f");
    if (forcedShortDelete || forcedLongDelete) {
      return { category: "destructive branch deletion", detail: "forced branch deletion can remove an unmerged branch" };
    }
  }

  for (const subcommand of ["checkout", "restore"]) {
    for (const tail of gitTails(command, subcommand)) {
      if (shellWords(tail).some((word) => BROAD_GIT_PATHS.has(word))) {
        return { category: `broad ${subcommand}`, detail: `broad ${subcommand} can overwrite worktree changes` };
      }
    }
  }

  for (const match of command.matchAll(/\brm\b([^;&|\n]*)/giu)) {
    const words = shellWords(match[1]);
    const recursive = words.includes("--recursive") || hasShortFlag(match[1], "r") || hasShortFlag(match[1], "R");
    const targets = words.filter((word) => !word.startsWith("-"));
    if (recursive && targets.some(broadDeleteTarget)) {
      return { category: "broad recursive delete", detail: "recursive deletion of a broad path can destroy unrelated data" };
    }
  }

  return null;
}

function normalized(value) {
  return path.resolve(value);
}

export function assessWorktree({ assignedWorktree, cwd, gitRoot, gitDir, commonGitDir }) {
  if (normalized(gitRoot) !== normalized(assignedWorktree)) {
    return { ok: false, reason: "current Git worktree does not match the assigned worktree" };
  }
  const assigned = normalized(assignedWorktree);
  const current = normalized(cwd);
  if (current !== assigned && !current.startsWith(`${assigned}${path.sep}`)) {
    return { ok: false, reason: "current directory is outside the assigned worktree" };
  }
  if (normalized(gitDir) === normalized(commonGitDir)) {
    return { ok: false, reason: "assigned repository is not a dedicated linked worktree" };
  }
  return { ok: true };
}

function git(cwd, ...args) {
  const result = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8" });
  if (result.status !== 0) throw new Error("Git worktree check failed");
  return result.stdout;
}

function inspectWorktree(cwd, assignedWorktree) {
  const gitRoot = git(cwd, "rev-parse", "--show-toplevel").trim();
  const gitDir = git(cwd, "rev-parse", "--git-dir").trim();
  const commonGitDir = git(cwd, "rev-parse", "--git-common-dir").trim();
  return assessWorktree({
    assignedWorktree: realpathSync(assignedWorktree),
    cwd: realpathSync(cwd),
    gitRoot: realpathSync(gitRoot),
    gitDir: realpathSync(path.resolve(cwd, gitDir)),
    commonGitDir: realpathSync(path.resolve(cwd, commonGitDir)),
  });
}

function fail(message) {
  console.error(`BLOCKED by VERA repository safety guard: ${message}`);
  process.exitCode = 2;
}

function runHook() {
  let input;
  try {
    input = JSON.parse(readFileSync(0, "utf8"));
  } catch {
    fail("could not parse agent hook input");
    return;
  }

  const command = input?.tool_input?.command;
  const cwd = input?.cwd;
  const assignedWorktree = process.env.VERA_ASSIGNED_WORKTREE;
  if (typeof command !== "string" || typeof cwd !== "string" || !assignedWorktree) {
    fail("hook input is missing command, cwd, or assigned worktree");
    return;
  }

  const blocked = classifyCommand(command);
  if (blocked) {
    fail(`${blocked.category}: ${blocked.detail}. Stop and use the documented human-led recovery procedure.`);
    return;
  }

  try {
    const scope = inspectWorktree(cwd, assignedWorktree);
    if (!scope.ok) fail(`${scope.reason}. Start the task in its assigned linked worktree.`);
  } catch {
    fail("worktree preflight failed; start the task in its assigned linked worktree");
  }
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  if (process.argv[2] === "hook") runHook();
  else {
    console.error("Usage: node scripts/agent-safety.mjs hook");
    process.exitCode = 1;
  }
}
