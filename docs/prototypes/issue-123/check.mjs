import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const html = join(root, "timeline-to-script-reconciliation.html");
const evidence = join(root, "evidence");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const states = {
  entry: "Managed Resolve timeline changed",
  review: "Review timeline and script changes",
  conflict: "Protected editorial state",
  result: "Reconciliation plan recorded",
  "no-change": "Managed timeline matches Build 18",
  unavailable: "Local agent unavailable",
  focus: "Keyboard route and focus order",
  "non-color": "Review timeline and script changes",
  overflow: "Long content stays readable",
  error: "Timeline observation failed",
};
const viewports = [[1280, 800], [1024, 768]];

if (!existsSync(chrome)) throw new Error(`Chrome not found at ${chrome}`);
mkdirSync(evidence, { recursive: true });

function pngSize(path) {
  const png = readFileSync(path);
  if (png.toString("ascii", 1, 4) !== "PNG") throw new Error(`${path} is not a PNG`);
  return [png.readUInt32BE(16), png.readUInt32BE(20)];
}

async function capture(state, marker, width, height) {
  const size = `${width}x${height}`;
  const image = join(evidence, `${state}-${size}.png`);
  const profile = mkdtempSync(join(tmpdir(), `vera-issue-123-${state}-`));
  const url = `${pathToFileURL(html)}?state=${encodeURIComponent(state)}`;
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
      else if (Date.now() - started > 7000) finish(new Error(`${state} ${size} render timed out: ${stderr}`));
    }, 100);
    function finish(error) {
      clearInterval(poll);
      try { process.kill(-child.pid, "SIGTERM"); } catch {}
      error ? reject(error) : resolve();
    }
  });

  try {
    if (!dom.includes(marker)) throw new Error(`${state} ${size} did not render its marker`);
    if (!dom.includes('data-horizontal-overflow="false"')) {
      throw new Error(`${state} ${size} has horizontal document overflow`);
    }
    const [actualWidth, actualHeight] = pngSize(image);
    if (actualWidth !== width || actualHeight !== height) {
      throw new Error(`${image} is ${actualWidth}x${actualHeight}, expected ${size}`);
    }
  } finally {
    await new Promise(resolve => setTimeout(resolve, 150));
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

const jobs = Object.entries(states).flatMap(([state, marker]) =>
  viewports.map(([width, height]) => [state, marker, width, height])
);
for (const args of jobs) {
  await capture(...args);
}
console.log(`Issue 123 prototype: ${Object.keys(states).length} states × ${viewports.length} viewports passed; ${jobs.length} screenshots retained.`);
