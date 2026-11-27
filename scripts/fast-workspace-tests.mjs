import { spawn } from "node:child_process";
import { availableParallelism, totalmem } from "node:os";
import { performance } from "node:perf_hooks";

import { fastWorkspaceConcurrency, fastWorkspaces, runWorkspaces, scheduleFastWorkspaces } from "./fast-workspace-tests-lib.mjs";

const root = process.cwd();
const selected = fastWorkspaces(root);
const { exclusive, parallel } = scheduleFastWorkspaces(selected);
const run = (workspace) => new Promise((resolve) => {
  const start = performance.now();
  console.log(`[fast-workspaces] starting ${workspace.name}`);
  const child = spawn("npm", ["run", "test:fast", "--workspace", workspace.path], {
    cwd: root,
    env: process.env,
    stdio: "inherit",
  });
  child.on("error", (error) => {
    console.error(`[fast-workspaces] ${workspace.name}: ${error}`);
    resolve(1);
  });
  child.on("close", (code) => {
    const seconds = (performance.now() - start) / 1000;
    console.log(`[fast-workspaces] ${workspace.name}: ${seconds.toFixed(3)}s`);
    resolve(code ?? 1);
  });
});

const options = {
  run,
  write: (line) => console.log(line),
};
const concurrency = fastWorkspaceConcurrency({
  platform: process.platform,
  cpus: availableParallelism(),
  memoryBytes: Math.min(totalmem(), process.constrainedMemory() || Infinity),
});
console.log(`[fast-workspaces] parallel workspace limit: ${concurrency}`);
const firstResult = await runWorkspaces(exclusive, { ...options, concurrency: 1 });
process.exitCode = firstResult || await runWorkspaces(parallel, { ...options, concurrency });
