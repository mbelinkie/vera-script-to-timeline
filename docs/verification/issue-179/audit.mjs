import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const output = fileURLToPath(new URL("./", import.meta.url));
const baseline = "d2e241316cb032cdddc4bac5d7acd953b1af8519";
const testedSource = "96fd70f573c3eaa1fc2b342de87ee9df00c64eaa";
const git = (...args) => {
  const result = spawnSync("git", args, { cwd: root, encoding: "utf8", maxBuffer: 20 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
};
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const allowed = (path) => path === "docs/plans/issue-179-cut-point-timing.md" || path.startsWith("docs/verification/issue-179/");
const originalPaths = git("ls-tree", "-r", "--name-only", baseline).trim().split("\n");
const changes = git("diff", "--name-only", baseline).trim().split("\n").filter(Boolean);
assert.ok(changes.every(allowed), `Out-of-scope tracked change: ${changes.filter((path) => !allowed(path))}`);
assert.ok(changes.every((path) => !originalPaths.includes(path)), "An accepted baseline file changed");
for (const path of originalPaths) assert.ok(existsSync(resolve(root, path)), `Missing accepted file ${path}`);
const status = git("status", "--porcelain", "-z").split("\0").filter(Boolean);
assert.ok(status.every((entry) => allowed(entry.slice(3))), "Untracked/staged change outside issue scope");
const inputs = [
  "docs/Script-to-Timeline Product Spec - Fable Rev2.md",
  "docs/plans/issue-156-authoring-realization.md",
  "docs/plans/issue-173-compiler-v2.md",
  "docs/verification/issue-173/automated.md",
  "docs/verification/issue-173/full-validation-result.json",
  "contracts/compiler-dependencies-v2.schema.json",
  "contracts/script-document-v2.schema.json",
  "contracts/timeline-manifest-v2.schema.json",
  "contracts/build-report-v2.schema.json",
  "packages/contracts/src/compiler-core-v2.ts",
  "packages/contracts/src/authoring-v2.ts",
  "packages/contracts/src/authoring-v2-projection.ts",
  "packages/contracts/src/authoring-v2-placement.ts",
  "packages/contracts/src/authoring-v2-validation.ts",
  "packages/contracts/src/authoring-v2-edits.ts",
  "packages/contracts/src/generated/contracts.ts",
  "packages/contracts/src/generated/contracts-v2.ts",
  "packages/contracts/scripts/generate-contracts.mjs",
  "packages/contracts/test/compiler-v2.test.ts",
  "python/vera_timeline_agent/narration/compiler_dependencies_v2.py",
  "tests/data/authoring_v2/issue_173/compiler/root-child-overlay-return.input.golden.json",
  "package.json", "package-lock.json", "pyproject.toml", "uv.lock",
];
const pins = Object.fromEntries(inputs.map((path) => {
  const bytes = readFileSync(resolve(root, path));
  assert.equal(bytes.toString(), git("show", `${baseline}:${path}`), `Baseline differs: ${path}`);
  return [path, { sha256: sha(bytes), gitBlob: git("rev-parse", `${baseline}:${path}`).trim() }];
}));
for (const path of inputs.filter((path) => /^(contracts|packages|python|tests)\//.test(path))) {
  assert.equal(git("rev-parse", `${testedSource}:${path}`), git("rev-parse", `${baseline}:${path}`), `Accepted runtime source differs: ${path}`);
}
const designPath = resolve(root, "docs/plans/issue-179-cut-point-timing.md");
assert.equal(git("rev-parse", "e32727f0c0e65dc5a8561e0f470ed28e59bd1809:docs/plans/issue-156-authoring-realization.md"), git("rev-parse", `${baseline}:docs/plans/issue-156-authoring-realization.md`));
const design = readFileSync(designPath, "utf8");
for (const match of design.matchAll(/\]\(([^)]+)\)/g)) {
  const target = match[1];
  if (/^https?:/.test(target)) continue;
  assert.ok(existsSync(resolve(dirname(designPath), target.split("#")[0])), `Missing reference ${target}`);
}
for (const required of ["CN-179", "verified_onset", "WordAudibleEndAnchor", "BOUNDARY_EVIDENCE_REQUIRED", "before < after", "v1/25-fps", "Blocked by #179", "## 8. Producer review"]) assert.ok(design.includes(required), `Missing design obligation ${required}`);
const result = JSON.parse(readFileSync(`${output}reproduction-result.json`, "utf8"));
assert.equal(result.observedAcceptedRuntime.complete.durationFrames, 96);
assert.equal(result.observedAcceptedRuntime.sparse.durationFrames, 96);
assert.equal(result.observedAcceptedRuntime.sparse.reportStatus, "blocked");
assert.deepEqual(result.proposalOnly.expectedPicture.childBeforeGamma, [24, 48]);
assert.deepEqual(result.proposalOnly.expectedPicture.childAfterBetaAudibleEnd, [24, 36]);
assert.ok(readFileSync(`${output}focused-tests.txt`, "utf8").includes("77 passed"));
assert.ok(readFileSync(`${output}generated-currentness.txt`, "utf8").includes("Generated contract types are current."));
const frozenCategories = ["contracts/", "fixtures/", "tests/", "packages/", "python/"];
writeFileSync(`${output}source-pins.json`, `${JSON.stringify({ baseline, testedSource, acceptedPlan: "e32727f0c0e65dc5a8561e0f470ed28e59bd1809", inputs: pins }, null, 2)}\n`);
writeFileSync(`${output}design-audit.json`, `${JSON.stringify({
  status: "passed", baseline, branch: git("branch", "--show-current").trim(),
  baselineTrackedFileCount: originalPaths.length,
  frozenCategoryFileCount: originalPaths.filter((path) => frozenCategories.some((prefix) => path.startsWith(prefix))).length,
  allBaselineFilesPresent: true, noBaselineFileChanges: changes.every((path) => !originalPaths.includes(path)),
  newArtifactsRestrictedToIssueScope: true, localDesignReferencesExist: true,
  acceptedRuntimeSourceBlobsMatch: true, exampleArithmeticAndReproductionConsistent: true,
  runtime: { node: process.version, vitest: JSON.parse(readFileSync(resolve(root, "node_modules/vitest/package.json"), "utf8")).version },
  validation: "Design evidence only; future runtime behavior is not implemented or accepted.",
}, null, 2)}\n`);
const artifacts = [
  "docs/plans/issue-179-cut-point-timing.md",
  ...["reproduction.test.ts", "complete.input.json", "sparse.input.json", "reproduction-result.json", "focused-tests.txt", "generated-currentness.txt", "source-pins.json", "design-audit.json", "audit.mjs", "successor-issue.md", "verification.md"].map((name) => `docs/verification/issue-179/${name}`),
];
writeFileSync(`${output}artifact-sha256.json`, `${JSON.stringify(Object.fromEntries(artifacts.map((path) => [path, sha(readFileSync(resolve(root, path)))])), null, 2)}\n`);
console.log("Design references, source pins, frozen boundaries and retained reproduction checks passed.");
