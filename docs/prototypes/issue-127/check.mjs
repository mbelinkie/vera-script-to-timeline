import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const htmlPath = join(root, "pilot.html");
const evidence = join(root, "evidence");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const html = readFileSync(htmlPath, "utf8");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const required = [
  "Controlled authoring range pilot",
  'value="minimal"',
  'value="numbered"',
  'data-number-policy="row"',
  'data-non-oc-cards="2"',
  'data-non-oc-cards="3"',
  "nonOnCameraCardCount >= 2",
  "white-space: nowrap",
  "Quiet sound",
  "No sound",
  "Full sound",
  "Opaque cutaway",
  "Transparent overlay",
  "Need to Find",
  "Graphic intent",
  "Music 6",
  "Source trim",
  "Fade out",
  "stable ID R5",
  "stable ID R7",
];
for (const marker of required) assert(html.includes(marker), `Missing pilot marker: ${marker}`);

const product = html.slice(html.indexOf('<main class="app"'), html.indexOf("</main>") + 7);
for (const forbidden of ["Added in Resolve", "Current Resolve", ">Accept<", ">Reject<", ">Defer<"]) {
  assert(!product.includes(forbidden), `Ordinary-authoring frame contains reconciliation language: ${forbidden}`);
}

for (const range of ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]) {
  const uses = html.match(new RegExp(`data-range="${range}"`, "g"))?.length ?? 0;
  assert(uses >= 2, `${range} is not linked from at least two inspectable surfaces`);
}
assert((html.match(/class="endpoint"/g)?.length ?? 0) >= 12, "Endpoint groups are missing");
assert((html.match(/<details>/g)?.length ?? 0) >= 5, "Source bookkeeping is not consistently on demand");
assert(existsSync(chrome), `Chrome not found at ${chrome}`);

mkdirSync(evidence, { recursive: true });

const states = {
  "minimal-default": "?mode=minimal",
  "numbered-default": "?mode=numbered",
  "minimal-compact": "?mode=minimal&thumbs=0&text=small&found=true&graphic=true",
  "numbered-compact": "?mode=numbered&thumbs=0&text=small&found=true&graphic=true",
};
const viewports = [[1280, 800], [1024, 768]];

function pngSize(path) {
  const png = readFileSync(path);
  assert(png.toString("ascii", 1, 4) === "PNG", `${path} is not a PNG`);
  return [png.readUInt32BE(16), png.readUInt32BE(20)];
}

async function capture(name, query, width, height) {
  const size = `${width}x${height}`;
  const image = join(evidence, `${name}-${size}.png`);
  const profile = mkdtempSync(join(tmpdir(), `vera-issue-127-${name}-`));
  const url = `${pathToFileURL(htmlPath)}${query}`;
  let dom = "";
  let stderr = "";

  const child = spawn(chrome, [
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-sync",
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
      else if (Date.now() - started > 30000) finish(new Error(`${name} ${size} render timed out: ${stderr}`));
    }, 100);
    function finish(error) {
      clearInterval(poll);
      try { process.kill(-child.pid, "SIGTERM"); } catch {}
      error ? reject(error) : resolve();
    }
  });

  try {
    assert(dom.includes("Controlled authoring range pilot"), `${name} ${size} did not render the pilot`);
    assert(dom.includes('data-horizontal-overflow="false"'), `${name} ${size} has horizontal overflow`);
    assert(dom.includes('data-card-fit="true"'), `${name} ${size} has a card or visual-column fit failure`);
    assert(dom.includes(`data-labels="${name.startsWith("numbered") ? "numbered" : "minimal"}"`), `${name} did not apply its range-label mode`);
    const hiddenNumberCount = (dom.match(/data-show-number="false"/g)?.length ?? 0)
      - (html.match(/data-show-number="false"/g)?.length ?? 0);
    const quietNumberCount = (dom.match(/data-number-emphasis="quiet"/g)?.length ?? 0)
      - (html.match(/data-number-emphasis="quiet"/g)?.length ?? 0);
    if (name.startsWith("minimal")) assert(hiddenNumberCount === 2, `${name} should hide the single-card row's two linked ordinals, found ${hiddenNumberCount}`);
    else assert(hiddenNumberCount === 0, `${name} should show every visual ordinal`);
    assert(quietNumberCount === 2, `${name} should mark only the singleton range and card ordinal as quiet, found ${quietNumberCount}`);
    const [actualWidth, actualHeight] = pngSize(image);
    assert(actualWidth === width && actualHeight === height, `${image} is ${actualWidth}x${actualHeight}, expected ${size}`);
  } finally {
    await new Promise(resolve => setTimeout(resolve, 150));
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

for (const [name, query] of Object.entries(states)) {
  for (const [width, height] of viewports) await capture(name, query, width, height);
}

console.log(`Issue 127 pilot: ${Object.keys(states).length} states × ${viewports.length} viewports passed; ${Object.keys(states).length * viewports.length} screenshots retained.`);
