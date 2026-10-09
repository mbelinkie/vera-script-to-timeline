import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readlinkSync, realpathSync, writeFileSync } from "node:fs";

const baseline = "03f1d333b85cceacd89be85a27723783c84ed310";
const directory = "docs/verification/issue-180";
const allowed = new Set([
  ".agents/skills/vera-roadmap-coordination/SKILL.md",
  ...["compiler-dependencies", "script-document", "timeline-manifest", "build-report"].map((name) => `contracts/${name}-v2.schema.json`),
  "packages/contracts/scripts/generate-contracts.mjs",
  ...["authoring-v2", "authoring-v2-validation", "authoring-v2-edits", "authoring-v2-placement", "authoring-v2-projection", "compiler-core-v2"].map((name) => `packages/contracts/src/${name}.ts`),
  "packages/contracts/src/generated/contracts-v2.ts",
  "python/vera_timeline_agent/generated/contracts/__init__.py",
  ...["compiler_dependencies", "script_document", "timeline_manifest", "build_report"].map((name) => `python/vera_timeline_agent/generated/contracts/${name}_v2_schema.py`),
]);
const git = (...args) => {
  const result = spawnSync("git", args, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
};
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const frozen = {};
for (const line of git("ls-tree", "-r", baseline).split("\n")) {
  const [metadata, path] = line.split("\t");
  if (allowed.has(path)) continue;
  const [mode, , object] = metadata.split(" ");
  const bytes = mode === "120000" ? Buffer.from(readlinkSync(path)) : readFileSync(path);
  const actual = createHash("sha1").update(`blob ${bytes.length}\0`).update(bytes).digest("hex");
  assert.equal(actual, object, `Frozen file changed: ${path}`);
  frozen[path] = sha(bytes);
}
assert.equal(readFileSync(".agents/skills/vera-roadmap-coordination/SKILL.md", "utf8").trim(), git("show", "24141d6977c5171439c1131187593dd0f0999816:.agents/skills/vera-roadmap-coordination/SKILL.md"));

// Undo precisely CN-179's additive schema surfaces, then compare all old semantics.
for (const name of ["compiler-dependencies", "script-document", "timeline-manifest", "build-report"]) {
  const path = `contracts/${name}-v2.schema.json`;
  const old = JSON.parse(git("show", `${baseline}:${path}`));
  const next = JSON.parse(readFileSync(path, "utf8"));
  const defs = next.$defs;
  if (name === "compiler-dependencies") {
    for (const definition of ["NarrationBoundaryEvidenceV1", "BoundaryTokenEvidenceV1", "BoundaryVerificationV1"]) delete defs[definition];
    delete next.properties.narrationBoundaryEvidence;
    delete defs.VisualSequenceResolutionV2.properties.boundaryEvidenceHash;
    defs.VisualSequenceResolutionV2.properties.alignmentPrecision.enum = defs.VisualSequenceResolutionV2.properties.alignmentPrecision.enum.filter((value) => value !== "verified_onset");
  } else if (name === "script-document") {
    delete defs.WordAudibleEndAnchor;
    for (const definition of ["BoundaryBefore", "PointAnchor"]) defs[definition].oneOf = defs[definition].oneOf.filter((value) => value.properties.kind.const !== "audible_word_end");
    defs.ReturnSlot.properties.inpoint.oneOf = defs.ReturnSlot.properties.inpoint.oneOf.filter((value) => value.$ref !== "#/$defs/WordAudibleEndAnchor");
  } else if (name === "timeline-manifest") {
    for (const definition of ["EventProvenanceV2", "BoundaryEvidenceV2"]) delete defs[definition].properties.boundaryEvidenceHash;
    defs.BoundaryEvidenceV2.properties.kind.enum = defs.BoundaryEvidenceV2.properties.kind.enum.filter((value) => !["row_start", "row_end"].includes(value));
    defs.BoundaryEvidenceV2.properties.precision.enum = defs.BoundaryEvidenceV2.properties.precision.enum.filter((value) => value !== "verified_onset");
    defs.BoundaryEvidenceV2.properties.wordRelation.enum = defs.BoundaryEvidenceV2.properties.wordRelation.enum.filter((value) => value !== "at_word_end");
  } else defs.DiagnosticCodeV2.enum = defs.DiagnosticCodeV2.enum.filter((value) => value !== "BOUNDARY_EVIDENCE_REQUIRED");
  assert.deepEqual(next, old, `Unapproved schema semantics: ${path}`);
}
const changed = git("diff", "--name-only", baseline).split("\n").filter(Boolean);
const own = (path) => path.startsWith(`${directory}/`) || path.startsWith("tests/data/authoring_v2/issue_180/") || ["docs/plans/issue-180-picture-boundary-evidence.md", "packages/contracts/src/narration-boundary-evidence-v2.ts", "packages/contracts/test/boundary-evidence-v2.test.ts", "tests/test_issue180_boundary_contracts.py"].includes(path);
assert.ok(changed.every((path) => allowed.has(path) || own(path)), "Change escaped CN-179 / issue-owned evidence");
const inputs = [...allowed, "packages/contracts/src/narration-boundary-evidence-v2.ts", "packages/contracts/test/boundary-evidence-v2.test.ts", "tests/test_issue180_boundary_contracts.py", "package.json", "package-lock.json", "pyproject.toml", "uv.lock"];
const result = { baseline, sourceCommit: git("rev-parse", "HEAD"), sourceTree: git("rev-parse", "HEAD^{tree}"), schemaSemanticAudit: "CN-179 additions only", frozenFileCount: Object.keys(frozen).length, frozenFilesUnchanged: true, allowedChangedPaths: changed };
writeFileSync(`${directory}/frozen-source-pins.json`, `${JSON.stringify(frozen, null, 2)}\n`);
writeFileSync(`${directory}/source-input-pins.json`, `${JSON.stringify(Object.fromEntries(inputs.map((path) => [path, sha(readFileSync(path))])), null, 2)}\n`);
writeFileSync(`${directory}/frozen-boundary-audit.json`, `${JSON.stringify(result, null, 2)}\n`);
const goldens = git("ls-files", "tests/data/authoring_v2/issue_180").split("\n").filter(Boolean);
assert.equal(goldens.length, 18);
writeFileSync(`${directory}/golden-pins.json`, `${JSON.stringify(Object.fromEntries(goldens.map((path) => [path, sha(readFileSync(path))])), null, 2)}\n`);
const command = (executable, args) => {
  const result = spawnSync(executable, args, { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
};
const uvPath = realpathSync(command("which", ["uv"]));
const profile = {
  model: "gpt-6.1-sol", effort: "high", task: "01a121fe-5af9-7e11-a9b6-cebf5627e71b",
  acceptance: "Automated", verification: "pure synthetic; no acoustic review or real delivery qualification",
  node: process.version, npm: command("npm", ["--version"]), uv: command("uv", ["--version"]),
  python: command("uv", ["run", "--frozen", "python", "--version"]),
  pytest: command("uv", ["run", "--frozen", "pytest", "--version"]),
  ruff: command("uv", ["run", "--frozen", "ruff", "--version"]),
  mypy: command("uv", ["run", "--frozen", "mypy", "--version"]),
  packages: Object.fromEntries(["vitest", "typescript", "eslint", "ajv", "json-schema-to-typescript"].map((name) => [name, JSON.parse(readFileSync(`node_modules/${name}/package.json`, "utf8")).version])),
  executableSHA256: { [realpathSync(process.execPath)]: sha(readFileSync(process.execPath)), [uvPath]: sha(readFileSync(uvPath)) },
  VITEST_MAX_WORKERS: "1",
  NODE_COMPILE_CACHE: process.env.NODE_COMPILE_CACHE ?? null,
};
writeFileSync(`${directory}/tool-profile.json`, `${JSON.stringify(profile, null, 2)}\n`);
const artifacts = ["audit.mjs", "run-full-validation.mjs", "cli-replay-probe.mjs", "automated.md", "runtime-gate-investigation.md", "frozen-source-pins.json", "source-input-pins.json", "golden-pins.json", "tool-profile.json", "frozen-boundary-audit.json", "attempt-1-status.json", "attempt-1-validate.log.gz", "attempt-2-status.json", "attempt-2-validate.log.gz", "cli-replay-uncached.json", "cli-replay-cached-1.json", "cli-replay-cached-2.json", "cli-replay-application-policy.json", "cli-replay-capacity-recovered.json", "python-validation-status.json", "python-validate.log.gz", "full-validation-status.json", "validate.log.gz"];
writeFileSync(`${directory}/artifact-pins.json`, `${JSON.stringify(Object.fromEntries(artifacts.filter((name) => existsSync(`${directory}/${name}`)).map((name) => [name, sha(readFileSync(`${directory}/${name}`))])), null, 2)}\n`);
console.log(JSON.stringify(result));
