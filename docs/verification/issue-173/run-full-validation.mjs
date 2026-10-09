// Capture the single unattended acceptance gate and its completion independently
// of a Codex output buffer. Run only after committing the source under test.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream, closeSync, mkdirSync, openSync, renameSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const outputDirectory = resolve(root, "test-results/issue-173/full-validation");
mkdirSync(outputDirectory, { recursive: true });
const logPath = resolve(outputDirectory, "validate.log");
const statusPath = resolve(outputDirectory, "status.json");
const git = (...args) => {
  const result = spawnSync("git", args, { cwd: root, encoding: "utf8" });
  if (result.status !== 0) throw new Error(result.stderr || "Cannot resolve source pin");
  return result.stdout.trim();
};
if (git("status", "--porcelain", "--untracked-files=normal")) {
  throw new Error("Commit the complete source before starting the acceptance gate");
}
const sourceCommit = git("rev-parse", "HEAD");
const sourceTree = git("rev-parse", "HEAD^{tree}");
const branch = git("branch", "--show-current");
const startedAt = new Date().toISOString();
const startedMs = Date.now();
const environment = {
  ...process.env,
  PATH: "/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/Users/matthewbelinkie/.local/bin",
  VITEST_MAX_WORKERS: "1",
};
const base = { sourceCommit, sourceTree, branch, startedAt, logPath, statusPath, command: "VITEST_MAX_WORKERS=1 npm run validate", nodeVersion: process.version };
const save = (status) => {
  const temporary = `${statusPath}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(status, null, 2)}\n`);
  renameSync(temporary, statusPath);
};
const log = openSync(logPath, "w");
const child = spawn("npm", ["run", "validate"], { cwd: root, env: environment, stdio: ["ignore", log, log] });
save({ ...base, state: "running", launcherPid: process.pid, validationPid: child.pid, exitCode: null, elapsedSeconds: null, logSHA256: null });
console.log(JSON.stringify({ state: "running", sourceCommit, launcherPid: process.pid, validationPid: child.pid, logPath, statusPath }));
const result = await new Promise((finish) => {
  child.once("error", (error) => finish({ exitCode: null, signal: null, error: error.message }));
  child.once("close", (exitCode, signal) => finish({ exitCode, signal, error: null }));
});
closeSync(log);
const hash = createHash("sha256");
for await (const chunk of createReadStream(logPath)) hash.update(chunk);
const final = {
  ...base,
  state: result.exitCode === 0 ? "passed" : "failed",
  launcherPid: process.pid,
  validationPid: child.pid,
  ...result,
  finishedAt: new Date().toISOString(),
  elapsedSeconds: (Date.now() - startedMs) / 1000,
  logSHA256: hash.digest("hex"),
};
save(final);
console.log(JSON.stringify(final));
process.exitCode = result.exitCode === 0 ? 0 : 1;
