import { cases, position } from "./assembly.mjs";

const $ = (id) => document.getElementById(id);
let parts = cases.partial;
let videos = [];
let audioElements = [];
let mediaNodes = [];
let buffers = {};
let config;
let context;
let analyser;
let nativeGain;
let worklet;
let sources = [];
let running = false;
let busy = false;
let baseTime = 0;
let baseClock = 0;
let currentIndex = -1;
let generation = 0;
let blockedIndex = -1;
let testGeneration = 0;
let report = {};
const duration = () => parts.at(-1).end;
const clock = () => context?.currentTime ?? 0;
const elapsed = () => Math.min(duration(), baseTime + (running ? clock() - baseClock : 0));
const status = (value) => { $("status").textContent = value; };
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const renderReport = () => { $("report").textContent = JSON.stringify(report, null, 2); };
const event = (type, detail = {}) => {
  (report.events ??= []).push({ type, wallMs: Math.round(performance.now()), assembly: +elapsed().toFixed(4), ...detail });
  renderReport();
};

function stopMedia() {
  for (const source of sources) { try { source.stop(); } catch { /* Already ended. */ } }
  sources = [];
  for (const video of videos) video.pause();
  for (const audio of audioElements) audio.pause();
}

function pause() {
  baseTime = elapsed();
  running = false;
  stopMedia();
  $("seek").value = baseTime;
}

function mediaReady(video, target) {
  return new Promise((resolve, reject) => {
    const finish = (error) => {
      clearTimeout(timer);
      video.removeEventListener("seeked", check);
      video.removeEventListener("loadeddata", check);
      video.removeEventListener("canplay", check);
      video.removeEventListener("error", fail);
      error ? reject(error) : resolve();
    };
    const check = () => {
      if (!video.seeking && video.readyState >= 2 && Math.abs(video.currentTime - target) < 0.08) finish();
    };
    const fail = () => finish(new Error("Media decode/load failed"));
    const timer = setTimeout(() => finish(new Error("Media preparation timed out")), 15000);
    video.addEventListener("seeked", check);
    video.addEventListener("loadeddata", check);
    video.addEventListener("canplay", check);
    video.addEventListener("error", fail);
    video.currentTime = target;
    check();
  });
}

function show(index) {
  videos.forEach((video, i) => video.classList.toggle("active", i === index));
  currentIndex = index;
}

function scheduleAudio(time) {
  // shortcut: decode the two whole short fixture WAVs; production long media needs bounded chunks.
  if ($("mode").value !== "scheduled") return;
  for (const part of parts) {
    if (part.end <= time) continue;
    const offset = Math.max(0, time - part.start);
    const source = context.createBufferSource();
    source.buffer = buffers[part.source];
    source.connect(analyser);
    source.start(baseClock + Math.max(0, part.start - time), part.in + offset, part.out - part.in - offset);
    sources.push(source);
  }
}

async function play() {
  if (busy || running || !videos.length) return;
  if (baseTime >= duration() - 0.001) baseTime = 0;
  const token = ++generation;
  busy = true;
  status("Preparing current segment…");
  try {
    await context.resume();
    const location = position(parts, baseTime);
    await mediaReady(videos[location.index], location.sourceTime);
    if (token !== generation) return;
    show(location.index);
    nativeGain.gain.value = $("mode").value === "native" ? 0.35 : 0;
    await videos[currentIndex].play();
    if (token !== generation) { videos[currentIndex].pause(); return; }
    baseClock = clock();
    running = true;
    scheduleAudio(baseTime);
    worklet.port.postMessage({ start: baseClock, end: baseClock + duration() - baseTime });
    event("play");
    status("Playing existing proxies — no render");
  } finally { busy = false; }
}

async function seek(time, resume = false) {
  ++generation;
  pause();
  baseTime = Math.max(0, Math.min(duration(), time));
  const location = position(parts, baseTime);
  const started = performance.now();
  await mediaReady(videos[location.index], Math.min(location.sourceTime, parts[location.index].out - 0.001));
  show(location.index);
  $("seek").value = baseTime;
  event("seek", { requested: time, source: parts[location.index].source, sourceTime: videos[location.index].currentTime,
    errorMs: +(1000 * (videos[location.index].currentTime - location.sourceTime)).toFixed(2),
    latencyMs: +(performance.now() - started).toFixed(2) });
  status("Paused — source frame prepared");
  if (resume) await play();
}

async function bufferAt(time, index) {
  const token = ++generation;
  pause();
  baseTime = time;
  busy = true;
  status("Buffering — assembly clock paused");
  event("buffer-start", { index });
  try {
    if (blockedIndex === index) { await wait(600); blockedIndex = -1; }
    const location = position(parts, time);
    await mediaReady(videos[index], location.sourceTime);
    event("buffer-end", { index });
  } finally { busy = false; }
  if (token === generation) await play();
}

function frame() {
  requestAnimationFrame(frame);
  if (!videos.length) return;
  const time = elapsed();
  const location = position(parts, time);
  $("live").textContent = `${time.toFixed(3)} / ${duration().toFixed(3)}s · source ${parts[location.index].source.toUpperCase()} ${location.sourceTime.toFixed(3)}s · ${parts[location.index].framing}`;
  if (!running) return;
  $("seek").value = time;
  if (time >= duration()) { pause(); status("Ended"); event("ended"); return; }
  if (location.index !== currentIndex) {
    if (blockedIndex === location.index || videos[location.index].readyState < 2) {
      void bufferAt(parts[location.index].start, location.index).catch(fail);
      return;
    }
    const previous = currentIndex;
    videos[previous].pause();
    show(location.index);
    void videos[currentIndex].play().catch(fail);
    event("join", { from: previous, to: currentIndex,
      boundaryLateMs: +((time - parts[currentIndex].start) * 1000).toFixed(2) });
  }
  const video = videos[currentIndex];
  const drift = video.currentTime - location.sourceTime;
  report.maxVideoClockErrorMs = Math.max(report.maxVideoClockErrorMs ?? 0, Math.abs(drift * 1000));
  if (Math.abs(drift) > 0.12 && !video.seeking) {
    event("drift-correction", { driftMs: +(drift * 1000).toFixed(2) });
    video.currentTime = location.sourceTime;
  }
  if ((report.samples ??= []).length < 1500 && Math.round(time * 10) !== report.lastSample) {
    report.lastSample = Math.round(time * 10);
    report.samples.push({ time: +time.toFixed(4), videoClockErrorMs: +(drift * 1000).toFixed(2), readyState: video.readyState });
    renderReport();
  }
}

function fail(error) { ++generation; pause(); busy = false; status(`Error: ${error.message}`); event("error", { message: error.message }); }

async function prepareAudioMonitor() {
  const code = `class Meter extends AudioWorkletProcessor {
    constructor(){super();this.blocks=0;this.silent=0;this.longest=0;this.run=0;this.start=Infinity;this.end=0;this.port.onmessage=({data})=>{if(data==='reset'){this.blocks=0;this.silent=0;this.longest=0;this.run=0;}else{this.start=data.start;this.end=data.end;}};}
    process(inputs,outputs){let power=0;const ch=inputs[0]?.[0];if(ch){for(let i=0;i<ch.length;i++)power+=ch[i]*ch[i];}
      for(let c=0;c<outputs[0].length;c++)outputs[0][c].set(inputs[0]?.[c]??ch??new Float32Array(128));
      if(ch&&currentTime>=this.start&&currentTime<this.end){this.blocks++;if(Math.sqrt(power/ch.length)<0.001){this.silent++;this.run+=ch.length;this.longest=Math.max(this.longest,this.run);}else this.run=0;}
      if(this.blocks%40===0)this.port.postMessage({blocks:this.blocks,silentBlocks:this.silent,longestSilenceMs:this.longest/sampleRate*1000});return true;}}
    registerProcessor('meter',Meter);`;
  const url = URL.createObjectURL(new Blob([code], { type: "text/javascript" }));
  try { await context.audioWorklet.addModule(url); } finally { URL.revokeObjectURL(url); }
  worklet = new AudioWorkletNode(context, "meter");
  analyser.connect(worklet);
  const gain = context.createGain(); gain.gain.value = 0.35;
  worklet.connect(gain).connect(context.destination);
  worklet.port.onmessage = ({ data }) => { report.audioOutput = data; renderReport(); };
}

async function load() {
  ++generation; pause(); testGeneration++;
  busy = true;
  status("Loading existing proxies/audio…");
  try {
    config ??= await (await fetch("/config.json")).json();
    if (!context) {
      context = new AudioContext(); analyser = context.createGain(); nativeGain = context.createGain();
      nativeGain.connect(analyser);
      await prepareAudioMonitor();
    }
    parts = cases[$("sequence").value];
    for (const node of mediaNodes) node.disconnect();
    mediaNodes = []; audioElements = [];
    $("stage").replaceChildren();
    videos = parts.map((part) => {
      const video = document.createElement("video");
      video.playsInline = true; video.preload = "auto"; video.src = `/media/${part.source}`;
      video.style.transform = part.framing === "tight" ? "scale(1.5)" : "none";
      $("stage").append(video);
      const node = context.createMediaElementSource(video); node.connect(nativeGain); mediaNodes.push(node);
      if (config.audio[part.source]) {
        // Silent proxy: control mode uses an independently clocked audio element.
        const audio = new Audio(`/audio/${part.source}`);
        audioElements.push(audio);
        const node = context.createMediaElementSource(audio); node.connect(nativeGain); mediaNodes.push(node);
        video.addEventListener("play", () => { audio.currentTime = video.currentTime; void audio.play().catch(fail); });
        video.addEventListener("pause", () => audio.pause());
        video.addEventListener("seeked", () => { audio.currentTime = video.currentTime; });
      }
      const observe = (now, metadata) => {
        if (running && currentIndex === parts.indexOf(part)) {
          const target = part.in + elapsed() - part.start;
          (report.presentedFrames ??= []).push({ index: currentIndex, assembly: +elapsed().toFixed(4),
            mediaTime: +metadata.mediaTime.toFixed(4), target: +target.toFixed(4),
            errorMs: +((metadata.mediaTime - target) * 1000).toFixed(2),
            displayTimeMs: +metadata.expectedDisplayTime.toFixed(2) });
        }
        if (video.isConnected) video.requestVideoFrameCallback(observe);
      };
      video.requestVideoFrameCallback(observe);
      return video;
    });
    await Promise.all(videos.map((video, index) => mediaReady(video, parts[index].in)));
    if (!buffers.a || !buffers.b) {
      buffers = Object.fromEntries(await Promise.all(["a", "b"].map(async (source) => {
        const url = config.audio[source] ? `/audio/${source}` : `/media/${source}`;
        const data = await (await fetch(url)).arrayBuffer();
        return [source, await context.decodeAudioData(data)];
      })));
    }
    for (const part of parts) {
      if (part.out > buffers[part.source].duration || part.out > videos[parts.indexOf(part)].duration) throw new Error("Fixture shorter than edit list");
    }
    baseTime = 0; currentIndex = -1; show(0); blockedIndex = -1;
    report = { browser: navigator.userAgent, case: $("sequence").value, mode: $("mode").value,
      duration: duration(), parts, videoElements: videos.length,
      decodedAudioBytes: Object.values(buffers).reduce((n, b) => n + b.length * b.numberOfChannels * 4, 0), events: [], samples: [] };
    $("seek").max = duration(); $("seek").value = 0;
    for (const id of ["play", "pause", "run", "stall", "seek", "before", "after"]) $(id).disabled = false;
    status("Ready — all segment start frames preloaded"); renderReport();
  } finally { busy = false; }
}

async function run() {
  const token = ++testGeneration;
  $("run").disabled = true; $("cancel").disabled = false;
  try {
    await seek(0);
    report.events = []; report.samples = []; report.maxVideoClockErrorMs = 0;
    report.presentedFrames = []; worklet.port.postMessage("reset");
    await play();
    while (running && token === testGeneration) await wait(50);
    if (token !== testGeneration) return;
    event("measured-pass-complete");
    const qualities = videos.map((video) => video.getVideoPlaybackQuality());
    report.videoQuality = qualities.map(({ totalVideoFrames, droppedVideoFrames, corruptedVideoFrames }) => ({ totalVideoFrames, droppedVideoFrames, corruptedVideoFrames }));
    report.heapBytes = performance.memory?.usedJSHeapSize ?? null;
    report.complete = true; renderReport(); status("Measured pass complete — report retained below");
  } finally { $("run").disabled = false; $("cancel").disabled = true; }
}

$("load").onclick = () => load().catch(fail);
$("play").onclick = () => play().catch(fail);
$("pause").onclick = () => { ++generation; pause(); status("Paused"); event("pause"); };
$("seek").onchange = () => seek(+$("seek").value, running).catch(fail);
$("before").onclick = () => seek(parts[0].end - 0.1).catch(fail);
$("after").onclick = () => seek(parts[0].end + 0.1).catch(fail);
$("run").onclick = () => run().catch(fail);
$("cancel").onclick = () => { testGeneration++; ++generation; pause(); event("measurement-cancelled"); };
$("stall").onclick = () => { blockedIndex = Math.min(currentIndex + 1, parts.length - 1); event("unready-test-armed", { blockedIndex }); };
$("sequence").onchange = $("mode").onchange = () => load().catch(fail);
requestAnimationFrame(frame);
