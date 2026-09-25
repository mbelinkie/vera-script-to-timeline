import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const htmlPath = join(root, "s03-successor-pilot.dc.html");
const sourcePath = join(root, "source-v2", "Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html");
const evidence = join(root, "successor-evidence");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sourceHash = "632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535";
const html = readFileSync(htmlPath, "utf8");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(existsSync(chrome), `Chrome not found at ${chrome}`);
assert(createHash("sha256").update(readFileSync(sourcePath)).digest("hex") === sourceHash, "Accepted v2 source changed");
assert(html.includes('data-bundled-from="source-v2/support.js"'), "Successor is missing its bundled runtime");
assert(html.includes('data-bundled-from="source-v2/issue32-shared-system-v1.0.0.css"'), "Successor is missing its bundled shared CSS");
assert((html.match(/data:image\/png;base64,/g) || []).length >= 7, "Successor is missing bundled thumbnail assets");
assert(!html.includes('./source-v2/'), "Successor still depends on a local source-v2 path");

for (const marker of [
  "Issue 127 bounded successor pilot",
  "SUCCESSOR_PILOT",
  'music: { id: "M1", part: "start"',
  'music: { id: "M1", part: "middle"',
  'music: { id: "M1", part: "end"',
  'music: { id: "M2", part: "single"',
  "singleton ordinals stay visible but quiet",
  "Transparent Graphics are independent layers",
  "│",
  "Quiet sound",
  "No sound",
  "Source trim",
  "Fade out",
  'whiteSpace: (broll && (abs === seg.start || abs === seg.end))',
]) assert(html.includes(marker), `Missing successor marker: ${marker}`);

for (const forbidden of [
  "Added in Resolve", "Current Resolve", ">Accept<", ">Reject<", ">Defer<",
  "Transparent overlay", "Opaque cutaway", "Opaque moving imagery",
  "Ranged request ·", "Standalone footage ·", "⟦6", "6⟧"
]) {
  assert(!html.includes(forbidden), `Ordinary authoring contains reconciliation language: ${forbidden}`);
}

mkdirSync(evidence, { recursive: true });

class CDP {
  constructor(url) {
    this.next = 1;
    this.pending = new Map();
    this.ws = new WebSocket(url);
  }
  async open() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", event => {
      const msg = JSON.parse(event.data);
      if (!msg.id || !this.pending.has(msg.id)) return;
      const { resolve, reject } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    });
  }
  send(method, params = {}) {
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  close() { this.ws.close(); }
}

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitFor(test, timeout = 12000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const value = await test();
    if (value) return value;
    await delay(80);
  }
  throw new Error("Timed out waiting for rendered successor");
}

async function capture(name, query, width, height, interactive = false) {
  const image = join(evidence, `${name}-${width}x${height}.png`);
  const profile = mkdtempSync(join(tmpdir(), `vera-issue-127-successor-${name}-`));
  const url = `${pathToFileURL(htmlPath)}${query}`;
  let stderr = "";
  let debuggerUrl = "";
  const child = spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-sync",
    "--no-first-run",
    "--remote-debugging-port=0",
    "--remote-allow-origins=*",
    "--force-device-scale-factor=1",
    `--user-data-dir=${profile}`,
    `--window-size=${width},${height}`,
    url,
  ], { detached: true });
  child.stderr.on("data", chunk => {
    stderr += chunk;
    const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (match) debuggerUrl = match[1];
  });

  let cdp;
  try {
    await waitFor(() => debuggerUrl);
    const endpoint = new URL(debuggerUrl);
    const pages = await waitFor(async () => {
      try {
        const list = await fetch(`http://${endpoint.host}/json/list`).then(r => r.json());
        return list.filter(p => p.type === "page" && p.url.includes("s03-successor-pilot.dc.html"));
      } catch { return null; }
    });
    cdp = new CDP(pages[0].webSocketDebuggerUrl);
    await cdp.open();
    await cdp.send("Runtime.enable");
    await cdp.send("Page.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });

    const evaluate = async expression => {
      const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Runtime evaluation failed");
      return result.result.value;
    };

    await waitFor(async () => evaluate(`Boolean(window.__dcFirstUpdate && document.body.innerText.includes("Issue 127 bounded successor pilot") && document.querySelectorAll("[data-slot]").length >= 8)`));
    await delay(700);

    const metrics = await evaluate(`(() => {
      const cards = [...document.querySelectorAll("[data-slot]")];
      const cardOrdinal = (id, n) => [...document.querySelectorAll("[data-slot='" + id + "'] button")].find(b => b.getAttribute("aria-label") === "Go to timed visual " + n + " in the narration");
      const quiet = cardOrdinal("pilot-capture", 1);
      const standard = cardOrdinal("pilot-lower-third", 1);
      const caps = [...document.querySelectorAll("[data-cap]")];
      const rowText = id => document.querySelector("[data-rowid='" + id + "']").innerText;
      const proseText = id => document.querySelector("[data-prose='" + id + "']").innerText;
      return {
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
        pageWidth: document.documentElement.scrollWidth,
        viewportWidth: innerWidth,
        widest: [...document.querySelectorAll("body *")].map(el => ({ tag: el.tagName, text: (el.textContent || "").trim().slice(0, 40), right: Math.round(el.getBoundingClientRect().right), width: Math.round(el.scrollWidth) })).sort((a,b) => b.right - a.right).slice(0,5),
        cardsFit: cards.every(card => card.scrollWidth <= card.clientWidth + 1),
        cardWidths: cards.map(card => ({ id: card.dataset.slot, scroll: card.scrollWidth, client: card.clientWidth })).filter(x => x.scroll > x.client + 1),
        ids: cards.map(card => card.dataset.slot),
        visibleOrdinals: [
          ["pilot-capture",1],
          ["pilot-lower-third",1],["pilot-cutaway",2],
          ["pilot-footage-a",1],["pilot-quote",2],["pilot-footage-b",3],
          ["pilot-request",1],["pilot-contained-footage",1]
        ].every(([id,n]) => Boolean(cardOrdinal(id,n))),
        quietOpacity: quiet ? getComputedStyle(quiet).opacity : null,
        quietWidth: quiet ? Math.round(quiet.getBoundingClientRect().width) : null,
        standardOpacity: standard ? getComputedStyle(standard).opacity : null,
        standardWidth: standard ? Math.round(standard.getBoundingClientRect().width) : null,
        endpointGroups: caps.length,
        endpointsNoWrap: caps.every(cap => getComputedStyle(cap.parentElement).whiteSpace === "nowrap"),
        overlayOpen: document.querySelector("#cap-pilot-quote")?.textContent,
        overlayClose: [...document.querySelectorAll("[data-overlay-cap='close']")].find(x => /Graphic 2 ends/.test(x.getAttribute("aria-label") || ""))?.textContent,
        graphicMargins: ["pilot-lower-third","pilot-quote"].map(id => getComputedStyle(document.querySelector("[data-slot='" + id + "']")).marginLeft),
        m1Segments: document.querySelectorAll("[data-music-range='M1']").length,
        m2Segments: document.querySelectorAll("[data-music-range='M2']").length,
        musicPollutedProse: ["p1","p2","p3","p5"].some(id => /M[12]|⟦6|6⟧/.test(proseText(id))),
        firstHostStates: ["p1","p4","p5"].map(id => ({ id, plain: /ON CAMERA/.test(rowText(id)), resumes: /ON CAMERA RESUMES/.test(rowText(id)) })),
        cutawayReturn: /ON CAMERA RESUMES/.test(rowText("p2")),
        rowCount: document.querySelectorAll("[data-rowid]").length,
        controls: [...document.querySelectorAll("input[type=range]")].map(x => x.getAttribute("aria-label")),
      };
    })()`);

    assert(!metrics.horizontalOverflow, `${name} ${width}x${height} has horizontal overflow: ${JSON.stringify(metrics)}`);
    assert(metrics.cardsFit, `${name} ${width}x${height} has a card-fit failure: ${JSON.stringify(metrics.cardWidths)}`);
    assert(metrics.visibleOrdinals, `${name} is missing a stable visible ordinal`);
    assert(metrics.quietOpacity === "0.66" && metrics.quietWidth < metrics.standardWidth, `${name} singleton ordinal is not quieter`);
    assert(metrics.standardOpacity === "1" && metrics.standardWidth >= 16, `${name} multi-visual ordinal lacks standard emphasis`);
    assert(metrics.endpointGroups >= 16 && metrics.endpointsNoWrap, `${name} has an orphanable range endpoint`);
    assert(metrics.overlayOpen === "◇│2" && metrics.overlayClose === "2│", `${name} does not use straight Graphic range ticks`);
    assert(metrics.graphicMargins.every(x => x === "0px"), `${name} indents an independent Graphic layer`);
    assert(metrics.m1Segments === 3 && metrics.m2Segments === 1, `${name} does not keep the two music cases independent`);
    assert(!metrics.musicPollutedProse, `${name} inserts music identity into narration text`);
    assert(metrics.firstHostStates.every(x => x.plain && !x.resumes), `${name} mislabels a first presenter-visible interval as a resume`);
    assert(metrics.cutawayReturn, `${name} lost the genuine On Camera return after the opaque cutaway`);
    assert(metrics.rowCount === 5, `${name} merged or added authoring rows`);

    if (interactive) {
      const result = await evaluate(`(async () => {
        const wait = () => new Promise(r => setTimeout(r, 100));
        const captureCard = document.querySelector("[data-slot='pilot-capture']");
        captureCard.focus();
        await wait();
        const focusVisible = document.activeElement === captureCard && getComputedStyle(captureCard).outlineStyle !== "none";
        captureCard.click();
        await wait();
        const detailsOpened = captureCard.getAttribute("aria-expanded") === "true" && captureCard.innerText.includes("Captured source");
        const cap = document.getElementById("cap-pilot-capture");
        cap.focus();
        await wait();
        const keyboardRange = document.activeElement === cap && /visual 1 starts/.test(cap.getAttribute("aria-label") || "");
        const quote = document.querySelector("[data-slot='pilot-quote']");
        quote.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
        await wait();
        const pointerRange = quote.getAttribute("aria-label").includes("visual 2");
        const quoteOpen = document.getElementById("cap-pilot-quote").getAttribute("aria-label");
        const quoteClose = [...document.querySelectorAll("[data-overlay-cap='close']")].find(x => /Graphic 2 ends/.test(x.getAttribute("aria-label") || "")).getAttribute("aria-label");
        const crossClipGraphic = /starts on “tide”/.test(quoteOpen) && /ends on “clear”/.test(quoteClose);
        const rail = document.querySelector("[data-music-range='M1']");
        rail.focus();
        rail.click();
        await wait();
        const m1Panel = document.querySelector("[data-music-panel='M1']");
        const m1Opened = Boolean(m1Panel);
        const m1AnchorsVisible = /publishes/.test(rail.getAttribute("aria-label") || "") && Boolean(m1Panel && m1Panel.innerText.includes("falls"));
        rail.click();
        await wait();
        rail.blur();
        const rail2 = document.querySelector("[data-music-range='M2']");
        rail2.focus();
        rail2.click();
        await wait();
        const m2Panel = document.querySelector("[data-music-panel='M2']");
        const m2Opened = Boolean(m2Panel);
        const m2AnchorsVisible = /a short/.test(rail2.getAttribute("aria-label") || "") && Boolean(m2Panel && m2Panel.innerText.includes("sting fades"));
        const controls = [...document.querySelectorAll("[data-music-panel='M2'] input[type=range]")].map(x => x.getAttribute("aria-label"));
        const requestOpen = document.getElementById("cap-pilot-request").getAttribute("aria-label");
        const requestClose = [...document.querySelectorAll("[data-cap]")].find(x => /Row 4, visual 1 ends/.test(x.getAttribute("aria-label") || "")).getAttribute("aria-label");
        document.querySelector("[data-slot='pilot-request']").click();
        await wait();
        [...document.querySelectorAll("button")].find(x => x.textContent.includes("Use found footage in this range")).click();
        await wait();
        const replaced = document.querySelector("[data-slot='pilot-request']");
        const replacementStable = replaced.innerText.includes("FOOTAGE")
          && Boolean([...replaced.querySelectorAll("button")].find(x => x.getAttribute("aria-label") === "Go to timed visual 1 in the narration"))
          && document.getElementById("cap-pilot-request").getAttribute("aria-label") === requestOpen
          && [...document.querySelectorAll("[data-cap]")].find(x => /Row 4, visual 1 ends/.test(x.getAttribute("aria-label") || "")).getAttribute("aria-label") === requestClose;
        return { focusVisible, detailsOpened, keyboardRange, pointerRange, crossClipGraphic, m1Opened, m1AnchorsVisible, m2Opened, m2AnchorsVisible, controls, replacementStable };
      })()`);
      assert(result.focusVisible, "Focused visual card does not show a visible outline");
      assert(result.detailsOpened, "Pointer activation did not reveal source details");
      assert(result.keyboardRange, "Keyboard focus did not reach the numbered range endpoint");
      assert(result.pointerRange, "Pointer inspection did not retain the quote range identity");
      assert(result.crossClipGraphic, "The Graphic does not retain its exact cross-clip endpoints");
      assert(result.m1Opened && result.m1AnchorsVisible, "Keyboard focus did not reveal M1 and its exact anchors");
      assert(result.m2Opened && result.m2AnchorsVisible, "Keyboard focus did not reveal M2 and its exact anchors");
      assert(result.controls.includes("Music source trim in seconds") && result.controls.includes("Music fade out in seconds"), "Music trim/fade controls are missing");
      assert(result.replacementStable, "Replacing the ranged request changed its ordinal or exact anchors");
      await evaluate(`(() => {
        const close = [...document.querySelectorAll("button")].find(x => x.getAttribute("aria-label") === "Close music details");
        if (close) close.click();
        const undo = [...document.querySelectorAll("button")].find(x => /^↶ Undo/.test(x.textContent.trim()));
        if (undo) undo.click();
        let scroller = document.querySelector("[data-rowid]");
        while (scroller && getComputedStyle(scroller).overflowY !== "auto") scroller = scroller.parentElement;
        if (scroller) scroller.scrollTop = 0;
        return true;
      })()`);
      await delay(3400);
    }

    const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    writeFileSync(image, Buffer.from(shot.data, "base64"));
    const png = readFileSync(image);
    assert(png.readUInt32BE(16) === width && png.readUInt32BE(20) === height, `${image} has the wrong dimensions`);
    if (interactive) {
      await evaluate(`document.querySelector("[data-slot='pilot-footage-a']").scrollIntoView({ block: "center" }); true`);
      await delay(250);
      const lower = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      writeFileSync(join(evidence, `${name}-lower-${width}x${height}.png`), Buffer.from(lower.data, "base64"));
    }
  } finally {
    if (cdp) cdp.close();
    try { process.kill(-child.pid, "SIGTERM"); } catch {}
    await delay(120);
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 150 });
  }
}

const states = [
  ["default", "?", 1280, 800, true],
  ["compact", "?viewport=compact", 1024, 768, false],
  ["small-zero", "?text=small&thumbs=0", 1280, 800, false],
  ["compact-small-zero", "?viewport=compact&text=small&thumbs=0&music=open", 1024, 768, false],
];

for (const state of states) await capture(...state);
console.log(`Issue 127 successor: ${states.length} states passed; source hash, row-local numbering, clip/Graphic ranges, host states, focus, and M1/M2 controls verified.`);
