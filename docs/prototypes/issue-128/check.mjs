import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const pilotPath = join(root, "s05-outbound-review-pilot.html");
const acceptedPath = join(root, "..", "issue-135", "S03 v3 authoring artifact - issue 135 export v2.dc.html");
const sharedCssPath = join(root, "..", "issue-127", "source-v2", "issue32-shared-system-v1.0.0.css");
const evidenceDir = join(root, "pilot-evidence");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const acceptedHash = "c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea";
const hash = value => createHash("sha256").update(value).digest("hex");
const assert = (condition, message) => { if (!condition) throw new Error(message); };

const pilot = readFileSync(pilotPath, "utf8");
const acceptedBytes = readFileSync(acceptedPath);
const accepted = acceptedBytes.toString("utf8");
const sharedCss = readFileSync(sharedCssPath, "utf8");
const grab = type => {
  const match = accepted.match(new RegExp(`<script type="${type}">\\s*([\\s\\S]*?)<\\/script>`));
  if (!match) throw new Error(`Missing accepted ${type}`);
  return match[1];
};
const acceptedTemplate = JSON.parse(grab("__bundler/template"));

assert(acceptedBytes.length === 3_943_452, `Accepted source size changed: ${acceptedBytes.length}`);
assert(hash(acceptedBytes) === acceptedHash, "Accepted #135 export hash changed");
assert(acceptedTemplate.includes(sharedCss.trim()), "Shared row stylesheet is not byte-identical inside accepted #135 source");
assert(pilot.includes("../issue-127/source-v2/issue32-shared-system-v1.0.0.css"), "Pilot does not import the frozen shared row stylesheet");
for (const marker of [
  'oc: { border: "#c9ab68", ink: "#725619", wash: "#fff8e7" }',
  'clip: { border: "#6b98b5", ink: "#244f69", wash: "#eef7fc" }',
  'graphic: { border: "#9879ad", ink: "#5f3f73", wash: "#f7f0fa" }',
  "start anchor, base before overlay, then source order",
  "No mutation callbacks",
]) assert(pilot.includes(marker), `Missing source-reuse marker: ${marker}`);

for (const marker of [
  "Narration edit + B-roll endpoint",
  "3 rows removed",
  "3-row passage moved",
  "Transparent Graphic merges 2 rows",
  "M2 cross-row duration change",
  "Missing local visual + audio",
  "Partial update failure",
  "Audio-only update · no picture changes",
  "Resolve stays unchanged — blocked",
]) assert(pilot.includes(marker), `Missing pilot behavior: ${marker}`);

assert(!pilot.includes("contenteditable"), "Read-only pilot contains authoring fields");
assert(!pilot.includes("Accept Resolve"), "Inbound #123 action leaked into outbound pilot");
assert(!pilot.includes("Keep current script"), "Inbound #123 action leaked into outbound pilot");
assert(!pilot.includes("runtime text"), "Pilot contains a runtime text-patch path");

if (!existsSync(chrome)) throw new Error(`Chrome not found at ${chrome}`);
mkdirSync(evidenceDir, { recursive: true });

const checks = [
  { name: "default", query: "", marker: "Compact default." },
  { name: "deletion-compare", query: "?compare=delete-three&focus=delete-three", marker: "In current Resolve · 00:01:12–00:01:40" },
  { name: "skipped-compare", query: "?compare=words-endpoint&selection=none", marker: "Unchanged — skipped" },
  { name: "move-stub", query: "?compare=move-passage&move=stub&focus=move-passage", marker: "Moved ↓ after" },
  { name: "move-full", query: "?compare=move-passage&move=full&focus=move-passage", marker: "both locations in full" },
  { name: "missing", query: "?state=missing&focus=graphic-merge", marker: "2 updates blocked by local files" },
  { name: "missing-cleared", query: "?state=missing&selection=none&focus=music-duration", marker: "0 selected · 3 skipped · 2 blocked" },
  { name: "partial", query: "?state=partial", marker: "Update incomplete. Timeline v3 remains current" },
  { name: "partial-audio-only", query: "?state=partial&selection=audio-only&focus=music-duration", marker: "1 verified" },
  { name: "audio-only", query: "?selection=audio-only&focus=music-duration", marker: "Audio-only update · no picture changes" },
];
const viewports = [[1280, 800], [1024, 768]];

async function capture(check, width, height) {
  const size = `${width}x${height}`;
  const image = join(evidenceDir, `${check.name}-${size}.png`);
  const profile = mkdtempSync(join(tmpdir(), `vera-issue-128-${check.name}-`));
  const url = `${pathToFileURL(pilotPath)}${check.query}`;
  let dom = "";
  let stderr = "";
  const child = spawn(chrome, [
    "--headless",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
    "--hide-scrollbars",
    "--metrics-recording-only",
    "--no-first-run",
    "--force-device-scale-factor=1",
    `--user-data-dir=${profile}`,
    `--window-size=${size}`,
    "--dump-dom",
    `--screenshot=${image}`,
    url,
  ], { detached: true });
  child.stdout.on("data", chunk => { dom += chunk; });
  child.stderr.on("data", chunk => { stderr += chunk; });

  await new Promise((resolve, reject) => {
    const started = Date.now();
    const poll = setInterval(() => {
      if (dom.includes("</html>") && existsSync(image)) finish();
      else if (Date.now() - started > 10_000) finish(new Error(`${check.name} ${size} timed out: ${stderr.slice(-1000)}`));
    }, 100);
    function finish(error) {
      clearInterval(poll);
      try { process.kill(-child.pid, "SIGTERM"); } catch {}
      error ? reject(error) : resolve();
    }
  });

  try {
    assert(dom.includes(check.marker), `${check.name} ${size} missing marker: ${check.marker}`);
    assert(dom.includes('data-horizontal-overflow="false"'), `${check.name} ${size} has horizontal overflow`);
    assert(dom.includes("window.__issue128Pilot"), `${check.name} ${size} did not retain the pilot self-check hook`);
  } finally {
    await new Promise(resolve => setTimeout(resolve, 100));
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
}

for (const check of checks) {
  for (const [width, height] of viewports) await capture(check, width, height);
}

console.log(`PASS accepted #135 source ${acceptedHash}`);
console.log("PASS shared stylesheet and copied row-type source markers");
console.log(`PASS ${checks.length} pilot states × ${viewports.length} viewports; ${checks.length * viewports.length} screenshots retained`);
