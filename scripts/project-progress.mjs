#!/usr/bin/env node

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  terminalSummary,
  writeDashboard,
} from "./project-progress-lib.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputPath = path.join(repositoryRoot, "out", "project-progress", "index.html");
const allowedArguments = new Set(["--open"]);
const unknownArguments = process.argv.slice(2).filter((argument) => !allowedArguments.has(argument));

if (unknownArguments.length > 0) {
  console.error(`Unknown argument(s): ${unknownArguments.join(", ")}`);
  console.error("Usage: npm run progress -- [--open]");
  process.exitCode = 2;
} else {
  try {
    const model = await writeDashboard(repositoryRoot, outputPath);
    console.log(terminalSummary(model, pathToFileURL(outputPath).href));

    if (process.argv.includes("--open")) {
      const command =
        process.platform === "darwin"
          ? ["open", [outputPath]]
          : process.platform === "win32"
            ? ["cmd", ["/c", "start", "", outputPath]]
            : ["xdg-open", [outputPath]];
      const child = spawn(command[0], command[1], {
        detached: true,
        stdio: "ignore",
      });
      child.unref();
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
