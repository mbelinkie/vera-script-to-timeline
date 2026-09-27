import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const issue128 = join(root, "..", "issue-128");
const issue135 = join(root, "..", "issue-135");
const recommendationPath = join(issue128, "paired-123-s05-scenario-corpus-recommendation.md");
const contentPath = join(issue128, "paired-123-s05-scenario-content-spec.md");
const acceptedSourcePath = join(issue135, "S03 v3 authoring artifact - issue 135 export v2.dc.html");

const recommendation = readFileSync(recommendationPath, "utf8");
const content = readFileSync(contentPath, "utf8");
const acceptedSource = readFileSync(acceptedSourcePath, "utf8");
const acceptedHandoff = readFileSync(join(issue135, "handoff.md"), "utf8");
const hash = value => createHash("sha256").update(value).digest("hex");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const squash = value => value.replace(/\s+/g, " ");
const assertIncludes = (text, values, label) => {
  const haystack = squash(text);
  for (const value of values) assert(haystack.includes(squash(value)), `${label} is missing: ${value}`);
};
const assertExactSet = (actual, expected, label) => {
  assert(actual.length === new Set(actual).size, `${label} contains a duplicate`);
  assert(actual.length === expected.length, `${label}: expected ${expected.length}, found ${actual.length}`);
  assert(expected.every(value => actual.includes(value)), `${label} does not match the expected IDs`);
};

assert(
  hash(recommendation) === "aa97fddbe25cb0870032c408c26d5634562bab7ed25030eb4c0070841d639344",
  "Corpus recommendation changed",
);
assert(
  hash(content) === "f355a8e9ee08326c09a78c929b848ea4c9681e2a86889bc1eac4b5c80016a6c0",
  "Scenario content specification changed",
);
assert(
  hash(acceptedSource) === "c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea",
  "Accepted #135 source changed",
);
assert(
  acceptedHandoff.includes("Issue #135 S03 v3 artifact accepted"),
  "Accepted #135 handoff no longer records Producer acceptance",
);

const sharedScenarios = Array.from({ length: 17 }, (_, index) => `C${String(index + 1).padStart(2, "0")}`);
const inboundScenarios = Array.from({ length: 8 }, (_, index) => `I${String(index + 1).padStart(2, "0")}`);
const outboundScenarios = Array.from({ length: 10 }, (_, index) => `O${String(index + 1).padStart(2, "0")}`);
const scenarioHeadings = [...content.matchAll(/^### ([CIO]\d{2}) ·/gm)].map(match => match[1]);
assertExactSet(scenarioHeadings, [...sharedScenarios, ...inboundScenarios, ...outboundScenarios], "Scenario corpus");

const expectedCases = [
  "C01", "C02", "C03a", "C03b", "C04", "C05", "C06", "C07", "C08", "C09", "C10",
  "C11", "C12", "C13", "C14", "C15a", "C15b", "C15c", "C16", "C17a", "C17b",
  ...inboundScenarios,
  "O01a", "O01b", "O02", "O03", "O04a", "O04b", "O05", "O06", "O07a", "O07b", "O07c",
  "O08", "O09", "O10",
];
const matrix = content.slice(
  content.indexOf("## Allocation and controlled-state matrix"),
  content.indexOf("## Shared scenario content"),
);
const matrixCases = [...matrix.matchAll(/^\| ([CIO]\d{2}[a-c]?) \|/gm)].map(match => match[1]);
assertExactSet(matrixCases, expectedCases, "Allocation matrix");

const rowHeadings = [...content.matchAll(/^#### r(\d+)\b/gm)].map(match => Number(match[1]));
assertExactSet(rowHeadings, Array.from({ length: 22 }, (_, index) => index + 1), "Harbor Lights row bank");
assert((acceptedSource.match(/\{ id: \\"r[0-9]+\\"/g) || []).length === 22, "Accepted #135 source no longer has 22 rows");

let narratedRows = 0;
for (let number = 1; number <= 22; number += 1) {
  const start = acceptedSource.indexOf(`{ id: \\"r${number}\\"`);
  const end = number < 22 ? acceptedSource.indexOf(`{ id: \\"r${number + 1}\\"`, start + 1) : acceptedSource.length;
  assert(start >= 0 && end > start, `Cannot locate accepted #135 row r${number}`);
  const words = acceptedSource.slice(start, end).match(/words: \\"([\s\S]*?)\\",\\n/);
  if (!words?.[1]) continue;
  narratedRows += 1;
  assert(content.includes(words[1]), `Row r${number} narration is not word-for-word from accepted #135`);
}
assert(narratedRows === 18, `Expected 18 narrated accepted rows, found ${narratedRows}`);

const acceptedMedia = [
  "harbour-mouth-wide_0812.mov",
  "horizon-steady_0805.mov",
  "sensor-housing-cu_0812.mov",
  "channel-light-dusk_0809.mov",
  "gull-liftoff_0731.mov",
  "fogged-lens_0805.mov",
  "Harbor Tide Bed",
  "Harbor Lights Theme",
];
assertIncludes(acceptedSource, acceptedMedia, "Accepted #135 source");
assertIncludes(content, acceptedMedia, "Scenario content specification");

assertIncludes(content, [
  "#123: `SCRIPT = older`; `RESOLVE = newer`.",
  "S05: `RESOLVE v3 = older`; `SCRIPT = newer`.",
  "name the common ancestor, current",
  "script and current Resolve states",
  "This composition is not a 36th scenario.",
  "At r21's canonical row-bank position after r20, both states omit r21",
  "The fixture must never render r21 twice.",
  "ends on `around the opening,`, and Footage 2 starts on `which changes`",
  "Footage 1 ending on `the probe responds.` and Footage 2 starting on `A ferry wake`",
  "Results follow document order and stop at the first failure",
  "same frozen C09/C05/C01 plan",
], "Scenario content specification");

assertIncludes(content, [
  "The ID is plain text in a gap in the neutral-gray harness's top border.",
  "The gray frame sits outside the measured product shell and is not its scroll container",
  "the product itself remains exactly `1280 × 800` or `1024 × 768`",
  "Accepted dashed card outline; no word underline",
  "Dashed underline beneath its words",
  "Accepted filled treatment; no word underline",
  "Solid underline beneath its words",
  "Dotted remains reserved for music-bed inspection and boundary editing.",
  "A Graphic may never show dashed and solid word underlines simultaneously.",
], "Harness and Graphic grammar");

assertIncludes(recommendation, [
  "accepted #135 two-track connector routing",
  "#128-style nested connector lanes",
  "`1280×800` and `1024×768`",
  "intersection with cards, thumbnails, labels or readable text",
  "traceability of every relationship",
  "document width lost to gutters",
  "horizontal overflow",
  "pointer and keyboard focus correspondence",
  "The Producer selects the winner before Issue B completes.",
  "Resolve-driven row splitting remains excluded from #123.",
  "Resolve-driven section-marker editing remains excluded from #123.",
  "M2 changes duration only; its accepted 3.0s fade remains unchanged.",
  "Display `Footage`, not `Logged Clip`",
], "Corpus recommendation");

console.log("PASS planning documents match checkpoint hashes");
console.log("PASS accepted #135 source hash, Producer provenance, 22 rows and 18 narrated rows");
console.log("PASS exact corpus: 17 shared + 8 inbound-only + 10 outbound-only = 35 scenarios");
console.log(`PASS allocation matrix: ${matrixCases.length} named cases and controlled-state rows`);
console.log("PASS direction, harness, Graphic grammar, C07/O05 corrections and C12 comparison gates");
