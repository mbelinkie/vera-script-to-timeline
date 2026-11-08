import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// npm --workspaces runs these independent fast suites serially. Keep the
// selection dynamic, so adding a workspace cannot silently lose coverage.
export function fastWorkspaces(root) {
  const { workspaces } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  if (JSON.stringify(workspaces) !== JSON.stringify(["packages/*"])) {
    throw new Error("Fast test runner needs a selection audit for changed workspaces");
  }

  const paths = readdirSync(join(root, "packages"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  const selected = [];
  for (const name of paths) {
    const path = join("packages", name);
    let pkg;
    try {
      pkg = JSON.parse(readFileSync(join(root, path, "package.json"), "utf8"));
    } catch (error) {
      if (error?.code === "ENOENT") continue; // Not an npm workspace.
      throw error;
    }
    if (pkg.scripts?.test && !pkg.scripts["test:fast"]) {
      throw new Error(`Workspace ${path} has test but no test:fast`);
    }
    if (pkg.scripts?.["test:fast"]) selected.push({ name: pkg.name, path });
  }
  if (selected.length === 0) throw new Error("No fast workspace test scripts found");
  return selected;
}

// The development-QA backup guards invoke real subprocesses under 5-second
// assertions. Concurrent CPU-heavy suites make those guards time out on the
// reference Mac. Run this existing fast workspace before the parallel batch;
// do not omit or modify any tests or their timeouts.
export function scheduleFastWorkspaces(selected) {
  const exclusive = selected.filter(({ path }) => path === "packages/project-service-host");
  const parallel = selected.filter(({ path }) => path !== "packages/project-service-host");
  return { exclusive, parallel };
}

// Once a child fails, do not start new suites. Already-running suites finish,
// so no partial or stale test processes are left behind before the next phase.
export async function runWorkspaces(selected, { run, write, concurrency = 3 }) {
  if (!Number.isInteger(concurrency) || concurrency < 1) {
    throw new Error("concurrency must be a positive integer");
  }
  let cursor = 0;
  let exitCode = 0;
  const worker = async () => {
    while (cursor < selected.length && exitCode === 0) {
      const workspace = selected[cursor++];
      let result;
      try {
        result = await run(workspace);
      } catch (error) {
        write(`[fast-workspaces] ${workspace.name}: ${String(error)}`);
        result = 1;
      }
      if (!Number.isInteger(result) || result !== 0) {
        exitCode = Number.isInteger(result) && result > 0 ? result : 1;
      }
      write(`[fast-workspaces] ${workspace.name}: ${result === 0 ? "PASS" : "FAIL"}`);
    }
  };
  await Promise.all(Array.from({ length: Math.min(concurrency, selected.length) }, worker));
  return exitCode;
}
