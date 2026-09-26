import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const exportPath = join(root, "S03 v3 authoring artifact - issue 135 export v2.dc.html");
const v2Path = join(root, "..", "issue-127", "source-v2", "Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html");
const expectedExportHash = "c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea";
const expectedV2Hash = "632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535";

const bytes = readFileSync(exportPath);
const html = bytes.toString("utf8");
const hash = value => createHash("sha256").update(value).digest("hex");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

assert(bytes.length === 3_943_452, `Unexpected export size: ${bytes.length}`);
assert(hash(bytes) === expectedExportHash, "Export hash does not match the reviewed artifact");
assert(hash(readFileSync(v2Path)) === expectedV2Hash, "Accepted S03 v2 source changed");
assert((html.match(/data:image\/png;base64,/g) || []).length === 7, "Expected seven embedded thumbnail images");
assert(!html.includes("assets/"), "Export still references a neighbouring assets folder");
assert(!html.includes("data-omelette-injected"), "Export contains Claude preview-only injection");
assert((html.match(/\{ id: \\"r[0-9]+\\"/g) || []).length === 22, "Expected the complete 22-row seed");

for (const marker of [
  "<div id=\"__bundler_thumbnail\">",
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
]) assert(html.includes(marker), `Missing reviewed marker: ${marker}`);

console.log(`PASS issue #135 export ${expectedExportHash}`);
console.log("PASS seven thumbnails embedded; no assets/ dependency");
console.log("PASS accepted S03 v2 remains byte-identical");
