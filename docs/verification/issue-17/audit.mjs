// Documentation-only audit; accepted package bytes are never loaded or executed.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../../..");
const pins = JSON.parse(readFileSync(resolve(here, "source-pins.json"), "utf8"));
const guidePath = resolve(root, "docs/external-template-pipeline.md");
const guide = readFileSync(guidePath, "utf8");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const git = (...args) => execFileSync("git", args, { cwd: root });

function checkPin(pin) {
  const bytes = git("show", `${pin.commit}:${pin.path}`);
  assert.equal(sha(bytes), pin.sha256, `Accepted artifact changed: ${pin.path}`);
  return bytes.toString("utf8");
}

function checkLinks(text, path) {
  let count = 0;
  for (const match of text.matchAll(/\[[^\]\n]+\]\((<[^>]+>|[^)\s]+)\)/g)) {
    const target = match[1].replace(/^<|>$/g, "");
    if (/^https:\/\//.test(target)) continue;
    const [file, fragment] = target.split("#");
    const destination = file ? resolve(dirname(path), decodeURIComponent(file)) : path;
    assert.ok(destination.startsWith(`${root}/`), `Non-repository link: ${target}`);
    assert.ok(existsSync(destination), `Missing link: ${target}`);
    if (fragment) {
      const headings = readFileSync(destination, "utf8").match(/^#+ .+$/gm) ?? [];
      const slugs = headings.map((line) => line.replace(/^#+ /, "").toLowerCase()
        .replace(/[^\p{L}\p{N}_\s-]/gu, "").replace(/ /g, "-"));
      assert.ok(slugs.includes(fragment), `Missing heading: ${target}`);
    }
    count += 1;
  }
  return count;
}

const sources = pins.sources.map((pin) => ({ ...pin, text: checkPin(pin) }));
function source(issue, suffix) {
  return sources.find((pin) => pin.issue === issue && pin.path.endsWith(suffix)).text;
}
const trace = [
  ["S12 semantic mapping", source(12, "ev24-lower-third.ts"), ["EV24_COUNTRY_IDS", "ControlHub", "SongTitle", "Singer", "BadgeOverride", 'values.country === "otis"']],
  ["S12 package/timing/rights", source(12, "ev24-lower-third.ts"), ["entranceFrames: 48", "exitFrames: 16", "minimumFrames: 64", "redistributionAllowed: false", "MACHINE_PATH_FORBIDDEN", "SemiBold ExtraCondensed", "UltraCondensed"]],
  ["S12 accepted tests", source(12, "ev24-registration-acceptance.md"), ["12 tests", "byte-identical", "48/16/64"]],
  ["S20 manifest/service", source(20, "template-library.ts"), ["external-template-package/v1", "computePackageDigest", "maximumFiles = 1_000", "512 * 1024 * 1024", "FILE_HASH_MISMATCH", "FONT_EMBEDDING_DENIED"]],
  ["S20 copy/use", source(20, "template-library.ts"), ["createProjectWithTemplates", "selectionSnapshotHash", "IDEMPOTENCY_KEY_REUSED", "resolveTemplateUse", "copiedFrom", "redistributionAllowed === true"]],
  ["S20 accepted tests", source(20, "template-library-copy-acceptance.md"), ["15 passing tests", "in-memory", "persistence-agnostic"]],
];
for (const [name, text, anchors] of trace) {
  for (const anchor of anchors) assert.ok(text.includes(anchor), `${name}: missing ${anchor}`);
}

const sections = ["Receive the package and intake brief", "Repository layout and immutable package record",
  "Register, discover and copy", "Semantic controls and responsive behavior", "Layered verification",
  "Troubleshooting and change control", "Reusable Producer acceptance handoff", "Documentation verification and remaining work"];
for (const section of sections) assert.ok(guide.includes(`## ${section}`), `Missing criterion section: ${section}`);
for (const phrase of ["S12", "S20", "In-memory", "planned", "rights", "safe areas", "Save/reopen", "ACCEPT #<issue>", "FAIL #<issue>", "syntax only", "redistributionAllowed to false", "No new Resolve test"])
  assert.ok(guide.toLowerCase().includes(phrase.toLowerCase()), `Missing boundary: ${phrase}`);
assert.doesNotMatch(guide, /\/Users\/|\/Volumes\/|\/private\/|file:\/\//, "Sensitive machine locator in public guide");
for (const match of guide.matchAll(/git show ([a-f0-9]{40}):([^\s]+)/g))
  assert.ok(pins.sources.some((pin) => pin.commit === match[1] && pin.path === match[2]), "Unpinned Git artifact command");

// Negative checks demonstrate that bad links, anchors and source pins fail.
assert.throws(() => checkLinks("[missing](issue-17-deliberately-absent.md)", guidePath));
assert.throws(() => checkLinks("[missing](#issue-17-deliberately-absent)", guidePath));
assert.throws(() => checkPin({ ...pins.sources[0], sha256: "0".repeat(64) }));

const docs = [guidePath, resolve(root, "docs/plans/issue-17-external-template-pipeline.md"), resolve(here, "verification.md")];
const linkCount = docs.reduce((total, path) => total + checkLinks(readFileSync(path, "utf8"), path), 0);
const changed = new Set([
  ...git("diff", "--name-only", pins.startingCommit).toString().trim().split("\n"),
  ...git("ls-files", "--others", "--exclude-standard").toString().trim().split("\n"),
].filter(Boolean));
for (const path of changed) assert.ok(path === "docs/external-template-pipeline.md" ||
  path === "docs/plans/issue-17-external-template-pipeline.md" || path.startsWith("docs/verification/issue-17/"), `Outside documentation slice: ${path}`);
git("diff", "--check", pins.startingCommit);
console.log(JSON.stringify({ status: "PASS", startingCommit: pins.startingCommit,
  acceptedArtifacts: sources.length, traceGroups: trace.length, internalLinks: linkCount,
  negativeChecks: 3, criterionSections: sections.length,
  artifacts: docs.map((path) => ({ path: relative(root, path), sha256: sha(readFileSync(path)) })),
  changedPaths: [...changed].sort(), runtimeAcceptance: "Not performed or implied" }, null, 2));
