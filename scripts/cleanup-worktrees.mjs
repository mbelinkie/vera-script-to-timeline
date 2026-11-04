// Remove local worktrees (and their branches) whose pushed work is already
// merged into origin/main. Worktrees with uncommitted changes, and branches
// that were never pushed (a task that has only just started), are kept.
//   npm run cleanup            remove merged worktrees
//   npm run cleanup -- --dry   only list what would be removed
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function parseWorktrees(porcelain) {
  return porcelain
    .split("\n\n")
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const entry = {};
      for (const line of block.split("\n")) {
        const [key, ...rest] = line.split(" ");
        entry[key] = rest.length ? rest.join(" ") : true;
      }
      return { path: entry.worktree, branch: typeof entry.branch === "string" ? entry.branch.replace(/^refs\/heads\//, "") : null };
    });
}

function git(args, cwd) {
  return execFileSync("git", args, { cwd, encoding: "utf8" }).trim();
}

function succeeds(args, cwd) {
  try {
    execFileSync("git", args, { cwd, stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function main() {
  const dry = process.argv.includes("--dry");
  const root = git(["rev-parse", "--show-toplevel"]);
  git(["fetch", "--quiet", "--prune", "origin"], root);
  const [primary, ...others] = parseWorktrees(git(["worktree", "list", "--porcelain"], root));
  let removed = 0;
  for (const tree of others) {
    if (!tree.branch || tree.branch === "main") continue;
    if (!succeeds(["config", `branch.${tree.branch}.remote`], root)) continue;
    if (!succeeds(["merge-base", "--is-ancestor", tree.branch, "origin/main"], root)) continue;
    if (git(["status", "--porcelain"], tree.path) !== "") {
      console.log(`kept (uncommitted changes): ${tree.path}`);
      continue;
    }
    console.log(`${dry ? "would remove" : "removed"}: ${tree.path} (${tree.branch})`);
    if (!dry) {
      git(["worktree", "remove", tree.path], primary.path);
      git(["branch", "-D", tree.branch], primary.path);
    }
    removed += 1;
  }
  git(["worktree", "prune"], root);
  console.log(`${removed} merged worktree(s) ${dry ? "found" : "removed"}.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
