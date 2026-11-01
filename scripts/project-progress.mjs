#!/usr/bin/env node

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  terminalSummary,
  writeDashboard,
} from "./project-progress-lib.mjs";
import { startProgressServer } from "./project-progress-live.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputPath = path.join(repositoryRoot, "out", "project-progress", "index.html");
const allowedArguments = new Set(["--open", "--serve"]);
const unknownArguments = process.argv.slice(2).filter((argument) => !allowedArguments.has(argument));

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

if (unknownArguments.length > 0) {
  console.error(`Unknown argument(s): ${unknownArguments.join(", ")}`);
  console.error("Usage: npm run progress -- [--serve] [--open]");
  process.exitCode = 2;
} else {
  try {
    const serving = process.argv.includes("--serve");
    const refreshMinutes = Number(process.env.VERA_PROGRESS_REFRESH_MINUTES ?? 15);
    if (serving && (!Number.isInteger(refreshMinutes) || refreshMinutes < 1)) {
      throw new Error("VERA_PROGRESS_REFRESH_MINUTES must be a whole number of at least 1");
    }

    const generate = (destination) => writeDashboard(repositoryRoot, destination, { live: serving });
    const models = await generate(outputPath);
    if (serving) {
      const live = await startProgressServer({
        outputPath,
        generate,
        refreshIntervalMs: refreshMinutes * 60_000,
      });
      console.log(terminalSummary(models, live.url));
      console.log(`  Automatically checks GitHub every ${refreshMinutes} minute(s) while open.`);
      console.log("  Use Refresh now in the dashboard to check immediately.");
      console.log("  Keep this Terminal window open; press Ctrl+C to stop the server.");
      if (process.argv.includes("--open")) openBrowser(live.url);
    } else {
      console.log(terminalSummary(models, pathToFileURL(outputPath).href));
      if (process.argv.includes("--open")) openBrowser(outputPath);
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
