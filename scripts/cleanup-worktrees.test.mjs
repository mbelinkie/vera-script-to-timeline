import assert from "node:assert/strict";
import test from "node:test";

import { parseWorktrees } from "./cleanup-worktrees.mjs";

test("reads worktree paths and branches from porcelain output", () => {
  const porcelain = [
    "worktree /Users/m/VERA\nHEAD abc\nbranch refs/heads/main",
    "worktree /Users/m/VERA worktrees/codex 12-fix\nHEAD def\nbranch refs/heads/codex/12-fix",
    "worktree /tmp/detached\nHEAD 123\ndetached",
  ].join("\n\n");
  assert.deepEqual(parseWorktrees(`${porcelain}\n`), [
    { path: "/Users/m/VERA", branch: "main" },
    { path: "/Users/m/VERA worktrees/codex 12-fix", branch: "codex/12-fix" },
    { path: "/tmp/detached", branch: null },
  ]);
});
