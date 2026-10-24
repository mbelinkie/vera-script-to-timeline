import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const exportPath = join(root, "S03 v3 authoring artifact - issue 140 connector lanes.dc.html");
const baselinePath = join(root, "..", "issue-135", "S03 v3 authoring artifact - issue 135 export v2.dc.html");
const expectedExportHash = "08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d";
const expectedBaselineHash = "c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea";
const hash = value => createHash("sha256").update(value).digest("hex");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const bytes = readFileSync(exportPath);
const html = bytes.toString("utf8");

assert(bytes.length === 3_505_885, `Unexpected export size: ${bytes.length}`);
assert(hash(bytes) === expectedExportHash, "Export hash does not match the reviewed artifact");
assert(hash(readFileSync(baselinePath)) === expectedBaselineHash, "Accepted #135 baseline changed");
assert((html.match(/data:image\/png;base64,/g) || []).length === 7, "Expected seven embedded thumbnail images");
assert((html.match(/\{ id: "r[0-9]+"/g) || []).length === 22, "Expected the complete 22-row seed");
assert(!html.includes("assets/"), "Export still references a neighbouring assets folder");
assert(!html.includes("data-omelette-injected"), "Export contains Claude preview-only injection");

for (const marker of [
  "const gutterW = cmp ? 42 : 50",
  "const laneHi = laneEdge - 9, laneLo = 17",
  "Math.max(2, Math.min(8, Math.floor((laneHi - laneLo) / (laneN - 1))))",
  "const trackX = laneN > 1 ? laneHi - rank[v.id] * laneStep",
  "const stemTop = pb === null ? 3 : Math.max(3, pb + 2 - p.top)",
  "const stemH = Math.max(0, off - stemTop)",
]) assert(html.includes(marker), `Missing reviewed connector marker: ${marker}`);

for (const marker of [
  "✓ Saved in this browser",
  "Add audio",
  "Audio picker for",
  "Audio file needed on this computer",
  "Image file needed on this computer",
  "Use this file anyway",
  "Files needed on this computer",
  "No out-word",
  "Holds through the ",
  "Keeper’s Notebook Piano",
  "EXAMPLE",
]) assert(html.includes(marker), `Missing retained S03 marker: ${marker}`);

console.log(`PASS issue #140 export ${expectedExportHash}`);
console.log("PASS dedicated nested-lane routing and fixed responsive gutters retained");
console.log("PASS accepted #135 baseline remains byte-identical");
