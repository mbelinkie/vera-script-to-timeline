#!/usr/bin/env node
// Read-only preflight for configured Codex launchers. This does not launch work.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { verifyReviewFromGh } from "./chat-review-github.mjs";

function readGh(args) {
  const result = spawnSync("gh", args, { encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  if (result.error || result.signal || result.status !== 0) {
    throw new Error("GitHub review preflight failed (no dispatch): " +
      (result.error?.message || result.signal || result.stderr || "GitHub unavailable"));
  }
  return result.stdout;
}

export function parseReviewUrl(raw) {
  const match = /^https:\/\/github\.com\/(mbelinkie)\/(vera-script-to-timeline|vera-research-video-clips)\/issues\/([1-9]\d*)\/?$/.exec(raw || "");
  if (!match) throw new Error("Pass one supported VERA issue URL");
  return { repo: match[1] + "/" + match[2], number: Number(match[3]) };
}

export function main(argv = process.argv.slice(2)) {
  if (argv.length !== 1) throw new Error("Usage: node scripts/chat-review-dispatch-gate.mjs https://github.com/mbelinkie/REPO/issues/N");
  const { repo, number } = parseReviewUrl(argv[0]);
  const record = verifyReviewFromGh(readGh, repo, number);
  console.log("Current Producer Chat review verified for " + repo + "#" + number +
    " (comment " + record.commentId + "); this check did not claim or launch work.");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(); } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
