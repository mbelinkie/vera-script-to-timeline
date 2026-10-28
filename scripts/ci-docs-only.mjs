import { execFileSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { TextDecoder } from "node:util";

const COMMIT_SHA = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const ALLOWED_ROOT_MARKDOWN = new Set(["README.md", "AGENTS.md", "CLAUDE.md", "DECISIONS.md", "CONTEXT.md"]);
export const RUNTIME_MARKDOWN_PATHS = Object.freeze([
  "docs/investigations/issue-300-normalization.md",
  "docs/plans/issue-178-native-qualification-change-note.md",
  "docs/plans/issue-207-target-identity-handoff.md",
  "docs/plans/issue-37-prompter-export.md",
  "docs/resolve-workflow-integration-v1.md",
  "docs/slice-0.3-resolve-free-trial.md",
]);
const runtimeMarkdownPaths = new Set(RUNTIME_MARKDOWN_PATHS);
const decoder = new TextDecoder("utf-8", { fatal: true });

function gitBuffer(cwd, args) {
  return execFileSync("git", args, { cwd, maxBuffer: 16 * 1024 * 1024 });
}

function gitText(cwd, args) {
  return execFileSync("git", args, { cwd, encoding: "utf8" }).trim();
}

export function nulDelimitedPaths(output) {
  if (output.length === 0) return [];
  let text;
  try {
    text = decoder.decode(output);
  } catch {
    return null;
  }
  if (!text.endsWith("\0")) throw new Error("Git returned an incomplete NUL-delimited path list");
  const paths = text.slice(0, -1).split("\0");
  if (paths.some((filePath) => filePath.length === 0)) throw new Error("Git returned an empty path");
  return paths;
}

function treeEntry(cwd, treeSha, filePath) {
  const output = gitBuffer(cwd, ["--literal-pathspecs", "ls-tree", "-z", "--full-tree", treeSha, "--", filePath]);
  if (output.length === 0) return null;
  const records = nulDelimitedPaths(output);
  if (!records || records.length !== 1) return null;
  const record = records[0];
  const tab = record.indexOf("\t");
  if (tab < 0 || record.slice(tab + 1) !== filePath) return null;
  const [mode, type] = record.slice(0, tab).split(" ");
  return { mode, type };
}

function isAllowedMarkdown(filePath) {
  return ALLOWED_ROOT_MARKDOWN.has(filePath) || /^docs\/[\s\S]+\.md$/.test(filePath);
}

export function classifyPullRequest({ eventName, baseSha, headSha, cwd = process.cwd() }) {
  if (eventName !== "pull_request") return "full";
  if (!COMMIT_SHA.test(baseSha ?? "") || !COMMIT_SHA.test(headSha ?? "")) {
    throw new Error("Pull request base and head must be commit SHAs");
  }

  const mergeBase = gitText(cwd, ["merge-base", baseSha, headSha]);
  if (!COMMIT_SHA.test(mergeBase)) throw new Error("Git returned an invalid merge base");
  const changedPaths = nulDelimitedPaths(
    gitBuffer(cwd, ["diff", "--no-renames", "--name-only", "-z", "--no-ext-diff", "--no-textconv", mergeBase, headSha]),
  );
  if (
    !changedPaths ||
    changedPaths.length === 0 ||
    changedPaths.some((filePath) => !isAllowedMarkdown(filePath) || runtimeMarkdownPaths.has(filePath))
  ) {
    return "full";
  }

  for (const filePath of changedPaths) {
    const mergeBaseEntry = treeEntry(cwd, mergeBase, filePath);
    const baseEntry = treeEntry(cwd, baseSha, filePath);
    const headEntry = treeEntry(cwd, headSha, filePath);
    const entries = [mergeBaseEntry, baseEntry, headEntry].filter(Boolean);
    if (entries.length === 0 || entries.some(({ mode, type }) => mode !== "100644" || type !== "blob")) return "full";
  }

  return "docs";
}

function main() {
  const result = classifyPullRequest({
    eventName: process.env.GITHUB_EVENT_NAME,
    baseSha: process.env.VERA_BASE_SHA,
    headSha: process.env.VERA_HEAD_SHA,
  });
  if (!process.env.GITHUB_OUTPUT) throw new Error("GITHUB_OUTPUT is required");
  appendFileSync(process.env.GITHUB_OUTPUT, `result=${result}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
