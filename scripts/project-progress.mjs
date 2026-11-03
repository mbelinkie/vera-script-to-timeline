#!/usr/bin/env node

import { execFileSync, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { progressSourceIdentity, startProgressServer } from "./project-progress-live.mjs";
import { issueRevision } from "./chat-review-current.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const preview = process.env.VERA_PROGRESS_PREVIEW === "1";
const outputPath = path.join(repositoryRoot, "out", "project-progress", preview ? "producer-preview.html" : "index.html");
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
    if (serving && (!Number.isInteger(refreshMinutes) || refreshMinutes < 1 || refreshMinutes >= 16)) {
      throw new Error("VERA_PROGRESS_REFRESH_MINUTES must be a whole number from 1 through 15");
    }

    const generate = async (destination) => {
      if (!serving) return await writeDashboard(repositoryRoot, destination, { live: false });
      const actions = new Map();
      const tokens = new Map();
      const snapshotAt = Date.now();
      const registerAction = (item, action) => {
        if (typeof item?.title !== "string" || typeof item.body !== "string" || !action?.kind) return null;
        const record = { issueUrl: item.url, kind: action.kind, revision: issueRevision(item.title, item.body),
          pr: action.pr, eventId: action.eventId, approvalUrl: action.approvalUrl,
          checklistDigest: action.checklistDigest, snapshotAt };
        const key = JSON.stringify(record);
        if (tokens.has(key)) return tokens.get(key);
        const token = randomBytes(24).toString("hex");
        tokens.set(key, token);
        actions.set(token, record);
        return token;
      };
      const models = await writeDashboard(repositoryRoot, destination, { live: true, registerAction, preview });
      return { models, actions };
    };
    if (serving) {
      const { createProgressExecutor } = await import("./project-progress-executor.mjs");
      let initialUpdatedAt = null;
      try {
        initialUpdatedAt = (await stat(outputPath)).mtimeMs;
      } catch (fileError) {
        if (fileError?.code !== "ENOENT") throw fileError;
      }
      const live = await startProgressServer({
        outputPath,
        sourceId: currentSourceId(),
        generate,
        resolveLocalSession,
        actionExecutor: createProgressExecutor(repositoryRoot),
        refreshIntervalMs: refreshMinutes * 60_000,
        initialUpdatedAt,
        initialRefresh: true,
      });
      console.log(`VERA progress\n  Dashboard: ${live.url}`);
      console.log(initialUpdatedAt === null
        ? "  No saved snapshot yet; showing a status page until the first refresh completes."
        : `  Showing the saved snapshot from ${new Date(initialUpdatedAt).toLocaleString()} until refresh completes.`);
      console.log(`  Checks GitHub every ${refreshMinutes} minute(s) while open, subject to API limits.`);
      console.log("  Use Refresh now to check sooner when permitted.");
      console.log("  Keep the server running for automatic updates.");
      if (process.argv.includes("--open")) openBrowser(live.url);
    } else {
      const models = await generate(outputPath);
      console.log(terminalSummary(models, pathToFileURL(outputPath).href));
      if (process.argv.includes("--open")) openBrowser(outputPath);
    }
  } catch {
    console.error("VERA progress dashboard could not be generated or refreshed.");
    process.exitCode = 1;
  }
}
