import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { classifyPullRequest, nulDelimitedPaths, RUNTIME_MARKDOWN_PATHS } from "./ci-docs-only.mjs";

function git(directory, ...args) {
  const result = spawnSync("git", ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", ...args], {
    cwd: directory,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function ciDiffFixture(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), "vera-ci-docs-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(path.join(root, "docs"));
  mkdirSync(path.join(root, "scripts"));
  writeFileSync(path.join(root, "README.md"), "base README\n");
  writeFileSync(path.join(root, "docs", "base.md"), "base documentation\n");
  writeFileSync(path.join(root, "scripts", "base.mjs"), "export const base = true;\n");
  git(root, "init", "-q");
  git(root, "config", "core.filemode", "true");
  const baseSha = commitGitFixture(root, "base");
  return { root, baseSha };
}

function commitGitFixture(root, message) {
  git(root, "add", "--all");
  git(root, "commit", "-q", "-m", message);
  return git(root, "rev-parse", "HEAD").trim();
}

test("runtime Markdown denylist covers every tracked Markdown path literal", () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const result = spawnSync(
    "git",
    ["grep", "-I", "-h", "-o", "-E", "docs/[[:alnum:]_./-]+[.]md", "HEAD", "--", "python", "integrations", "packages", "tests"],
    { cwd: root, encoding: "utf8" },
  );
  assert.equal(result.status, 0, result.stderr);
  const references = [...new Set(result.stdout.split(/\r?\n/).filter(Boolean))].sort();
  assert.deepEqual([...RUNTIME_MARKDOWN_PATHS].sort(), references);
});

test("allowlisted Markdown with unusual pathnames qualifies for docs-only validation", (t) => {
  const { root, baseSha } = ciDiffFixture(t);
  writeFileSync(path.join(root, "README.md"), "updated\n");
  for (const rootDocument of ["AGENTS.md", "CLAUDE.md", "DECISIONS.md", "CONTEXT.md"]) {
    writeFileSync(path.join(root, rootDocument), "allowed root documentation\n");
  }
  writeFileSync(path.join(root, "docs", "odd\nname.md"), "new note\n");
  const headSha = commitGitFixture(root, "docs only");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha, headSha, cwd: root }), "docs");
});

test("the classifier CLI publishes its route to the GitHub Actions output file", (t) => {
  const { root, baseSha } = ciDiffFixture(t);
  writeFileSync(path.join(root, "docs", "added.md"), "new documentation\n");
  const headSha = commitGitFixture(root, "add docs");
  const output = path.join(root, "github-output.txt");
  const script = path.join(path.dirname(fileURLToPath(import.meta.url)), "ci-docs-only.mjs");
  const result = spawnSync(process.execPath, [script], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      GITHUB_EVENT_NAME: "pull_request",
      GITHUB_OUTPUT: output,
      VERA_BASE_SHA: baseSha,
      VERA_HEAD_SHA: headSha,
    },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(readFileSync(output, "utf8"), "result=docs\n");
});

test("the pull request merge base excludes files changed only on the base branch", (t) => {
  const { root } = ciDiffFixture(t);
  git(root, "branch", "base-branch");
  git(root, "checkout", "-q", "-b", "pull-request");
  writeFileSync(path.join(root, "docs", "base.md"), "PR documentation\n");
  const headSha = commitGitFixture(root, "PR documentation");
  git(root, "checkout", "-q", "base-branch");
  writeFileSync(path.join(root, "scripts", "base-only.mjs"), "export {};\n");
  const baseSha = commitGitFixture(root, "base code change");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha, headSha, cwd: root }), "docs");
});

test("runtime-consumed Markdown changes use the full gate", (t) => {
  for (const filePath of RUNTIME_MARKDOWN_PATHS) {
    const { root, baseSha } = ciDiffFixture(t);
    const target = path.join(root, filePath);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, "updated runtime documentation\n");
    const headSha = commitGitFixture(root, `change ${filePath}`);
    assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha, headSha, cwd: root }), "full", filePath);
  }
});

test("mixed changes and renames with a non-Markdown endpoint take the full gate", (t) => {
  const mixed = ciDiffFixture(t);
  writeFileSync(path.join(mixed.root, "docs", "change.md"), "updated\n");
  writeFileSync(path.join(mixed.root, "scripts", "new.mjs"), "export {};\n");
  const mixedHead = commitGitFixture(mixed.root, "mixed change");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: mixed.baseSha, headSha: mixedHead, cwd: mixed.root }), "full");

  const codeToDocs = ciDiffFixture(t);
  git(codeToDocs.root, "mv", "scripts/base.mjs", "docs/moved.md");
  const codeToDocsHead = commitGitFixture(codeToDocs.root, "rename code into docs");
  assert.equal(
    classifyPullRequest({ eventName: "pull_request", baseSha: codeToDocs.baseSha, headSha: codeToDocsHead, cwd: codeToDocs.root }),
    "full",
  );

  const docsToCode = ciDiffFixture(t);
  git(docsToCode.root, "mv", "docs/base.md", "scripts/moved.md");
  const docsToCodeHead = commitGitFixture(docsToCode.root, "rename docs into code");
  assert.equal(
    classifyPullRequest({ eventName: "pull_request", baseSha: docsToCode.baseSha, headSha: docsToCodeHead, cwd: docsToCode.root }),
    "full",
  );

  const docsRename = ciDiffFixture(t);
  git(docsRename.root, "mv", "docs/base.md", "docs/renamed.md");
  const docsRenameHead = commitGitFixture(docsRename.root, "rename documentation");
  assert.equal(
    classifyPullRequest({ eventName: "pull_request", baseSha: docsRename.baseSha, headSha: docsRenameHead, cwd: docsRename.root }),
    "docs",
  );
});

test("mode changes, symlinks, non-Markdown paths and empty diffs fail closed to full", (t) => {
  const executable = ciDiffFixture(t);
  chmodSync(path.join(executable.root, "docs", "base.md"), 0o755);
  const executableHead = commitGitFixture(executable.root, "executable Markdown mode");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: executable.baseSha, headSha: executableHead, cwd: executable.root }), "full");

  const symlink = ciDiffFixture(t);
  symlinkSync("../README.md", path.join(symlink.root, "docs", "linked.md"));
  const symlinkHead = commitGitFixture(symlink.root, "Markdown symlink");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: symlink.baseSha, headSha: symlinkHead, cwd: symlink.root }), "full");

  const nonMarkdown = ciDiffFixture(t);
  writeFileSync(path.join(nonMarkdown.root, "docs", "notes.txt"), "not Markdown\n");
  const nonMarkdownHead = commitGitFixture(nonMarkdown.root, "non-Markdown path");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: nonMarkdown.baseSha, headSha: nonMarkdownHead, cwd: nonMarkdown.root }), "full");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: nonMarkdown.baseSha, headSha: nonMarkdown.baseSha, cwd: nonMarkdown.root }), "full");
  assert.equal(classifyPullRequest({ eventName: "workflow_dispatch" }), "full");
  assert.throws(() => classifyPullRequest({ eventName: "pull_request", baseSha: "unknown", headSha: nonMarkdownHead, cwd: nonMarkdown.root }));

  const unlistedRoot = ciDiffFixture(t);
  writeFileSync(path.join(unlistedRoot.root, "CHANGELOG.md"), "not an allowed root document\n");
  const unlistedRootHead = commitGitFixture(unlistedRoot.root, "unlisted root Markdown");
  assert.equal(classifyPullRequest({ eventName: "pull_request", baseSha: unlistedRoot.baseSha, headSha: unlistedRootHead, cwd: unlistedRoot.root }), "full");
});

test("invalid UTF-8 Git path output is recognized as unclassifiable", () => {
  assert.equal(nulDelimitedPaths(Buffer.from([0xff, 0])), null);
  assert.deepEqual(nulDelimitedPaths(Buffer.from("docs/notes.md\0")), ["docs/notes.md"]);
});
