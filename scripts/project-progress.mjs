#!/usr/bin/env node

import { execFileSync, spawn } from "node:child_process";
import { stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { progressSourceIdentity, startProgressServer } from "./project-progress-live.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputPath = path.join(repositoryRoot, "out", "project-progress", "index.html");
const allowedArguments = new Set(["--identity", "--open", "--serve"]);
const unknownArguments = process.argv.slice(2).filter((argument) => !allowedArguments.has(argument));

function currentSourceId() {
  const head = execFileSync("git", ["rev-parse", "--verify", "HEAD"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  return progressSourceIdentity(repositoryRoot, head);
}

function openBrowser(destination) {
  const command = process.platform === "darwin"
    ? ["open", [destination]]
    : process.platform === "win32"
      ? ["cmd", ["/c", "start", "", destination]]
      : ["xdg-open", [destination]];
  const child = spawn(command[0], command[1], {
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

if (process.argv.includes("--identity")) {
  if (process.argv.length !== 3 || unknownArguments.length > 0) {
    console.error("Usage: node scripts/project-progress.mjs --identity");
    process.exitCode = 2;
  } else {
    try {
      process.stdout.write(`${currentSourceId()}\n`);
    } catch {
      console.error("VERA checkout identity is unavailable.");
      process.exitCode = 1;
    }
  }
} else if (unknownArguments.length > 0) {
  console.error(`Unknown argument(s): ${unknownArguments.join(", ")}`);
  console.error("Usage: npm run progress -- [--serve] [--open]");
  process.exitCode = 2;
} else {
  try {
    const { terminalSummary, writeDashboard } = await import("./project-progress-lib.mjs");
    const { resolveLocalSession } = await import("./project-progress-workflow.mjs");
    const serving = process.argv.includes("--serve");
    const refreshMinutes = Number(process.env.VERA_PROGRESS_REFRESH_MINUTES ?? 15);
    if (serving && (!Number.isInteger(refreshMinutes) || refreshMinutes < 1)) {
      throw new Error("VERA_PROGRESS_REFRESH_MINUTES must be a whole number of at least 1");
    }

    const generate = (destination) => writeDashboard(repositoryRoot, destination, { live: serving });
    let models = null;
    let startupError = null;
    let initialUpdatedAt;

    try {
      models = await generate(outputPath);
    } catch (cause) {
      // A live dashboard must remain accessible even if the GitHub API budget
      // is exhausted or a Project read fails. Static generation remains strict.
      if (!serving) throw cause;
      startupError = cause;
      try {
        initialUpdatedAt = (await stat(outputPath)).mtimeMs;
      } catch (fileError) {
        if (fileError?.code !== "ENOENT") throw fileError;
        initialUpdatedAt = null; // No saved dashboard to show yet.
      }
    }

    if (serving) {
      const live = await startProgressServer({
        outputPath,
        sourceId: currentSourceId(),
        generate,
        resolveLocalSession,
        refreshIntervalMs: refreshMinutes * 60_000,
        initialError: startupError,
        initialUpdatedAt,
      });
      if (models) {
        console.log(terminalSummary(models, live.url));
      } else {
        console.log(`VERA progress\n  Dashboard: ${live.url}`);
        console.warn(`  ${live.snapshot().error ?? "GitHub refresh is unavailable."}`);
        console.log(initialUpdatedAt === null
          ? "  No saved snapshot yet; showing a status page."
          : `  Showing saved snapshot from ${new Date(initialUpdatedAt).toLocaleString()}.`);
      }
      console.log(`  Checks GitHub every ${refreshMinutes} minute(s) while open, subject to API limits.`);
      console.log("  Use Refresh now to check sooner when permitted.");
      console.log("  Keep the server running for automatic updates.");
      if (process.argv.includes("--open")) openBrowser(live.url);
    } else {
      console.log(terminalSummary(models, pathToFileURL(outputPath).href));
      if (process.argv.includes("--open")) openBrowser(outputPath);
    }
  } catch {
    console.error("VERA progress dashboard could not be generated or refreshed.");
    process.exitCode = 1;
  }
}
