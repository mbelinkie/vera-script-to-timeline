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
let warming = new Set();
let testGeneration = 0;
let report = {};
let monitorReady;
const mediaWaits = new Set();
const duration = () => parts.at(-1).end;
const audioOnly = () => $("audioOnly").checked;
const clock = () => context?.currentTime ?? 0;
const elapsed = () => Math.min(duration(), baseTime + (running ? Math.max(0, clock() - baseClock) : 0));
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
  busy = false;
  warming = new Set();
  for (const cancel of mediaWaits) cancel();
  stopMedia();
  $("seek").value = baseTime;
}

function mediaReady(video, target) {
  const token = generation;
  return new Promise((resolve, reject) => {
    let cancel;
    const finish = (error) => {
      clearTimeout(timer);
      video.removeEventListener("seeked", check);
      video.removeEventListener("loadeddata", check);
      video.removeEventListener("canplay", check);
      video.removeEventListener("error", fail);
      mediaWaits.delete(cancel);
      error ? reject(error) : resolve();
    };
    const check = () => {
      if (token !== generation) return finish();
      if (!video.seeking && video.readyState >= 2 && Math.abs(video.currentTime - target) < 0.08) finish();
    };
    const fail = () => finish(token === generation ? new Error("Media decode/load failed") : undefined);
    cancel = () => finish();
    mediaWaits.add(cancel);
    const timer = setTimeout(() => finish(token === generation ? new Error("Media preparation timed out") : undefined), 15000);
    video.addEventListener("seeked", check);
    video.addEventListener("loadeddata", check);
    video.addEventListener("canplay", check);
    video.addEventListener("error", fail);
    try { video.currentTime = target; check(); }
    catch (error) { finish(token === generation ? error : undefined); }
  });
}

function show(index) {
  videos.forEach((video, i) => video.classList.toggle("active", i === index));
  currentIndex = index;
}

function scheduleAudio(time) {
  // shortcut: decode both whole fixture WAVs; production long media needs bounded chunks.
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

function mediaPlayError(token, error) {
  if (token === generation && error?.name !== "AbortError") fail(error);
}

async function play() {
  if (busy || running || !buffers.a || !buffers.b) return;
  if (baseTime >= duration() - 0.001) baseTime = 0;
  const token = ++generation;
  busy = true;
  status("Preparing current segment…");
  try {
    await context.resume();
    if (token !== generation) return;
    const location = position(parts, baseTime);
    if (!audioOnly()) await mediaReady(videos[location.index], location.sourceTime);
    if (token !== generation) return;
    show(location.index);
    nativeGain.gain.value = $("mode").value === "native" ? 0.35 : 0;
    if (!audioOnly()) {
      const video = videos[location.index];
      try { await video.play(); }
      catch (error) { if (token !== generation || error?.name === "AbortError") return; throw error; }
      if (token !== generation) { video.pause(); return; }
    }
    baseClock = clock() + (audioOnly() ? 0.05 : 0);
    running = true;
    scheduleAudio(baseTime);
    worklet.port.postMessage({ start: baseClock, end: baseClock + duration() - baseTime });
    event("play");
    status(audioOnly() ? "Playing assembled audio — no render" : "Playing existing proxies — no render");
  } catch (error) {
    if (token === generation) throw error;
  } finally { if (token === generation) busy = false; }
}

async function seek(time, resume = false) {
  const token = ++generation;
  pause();
  busy = true;
  baseTime = Math.max(0, Math.min(duration(), time));
  warming = new Set();
  const location = position(parts, baseTime);
  const started = performance.now();
  try {
    if (!audioOnly()) await mediaReady(videos[location.index], Math.min(location.sourceTime, parts[location.index].out - 0.001));
    if (token !== generation) return;
    show(location.index);
    if (!audioOnly()) await Promise.all(videos.map((video, index) => index > location.index
      ? mediaReady(video, Math.max(0, parts[index].in - 1)) : Promise.resolve()));
    if (token !== generation) return;
    $("seek").value = baseTime;
    event("seek", { requested: time, source: parts[location.index].source, sourceTime: audioOnly() ? location.sourceTime : videos[location.index].currentTime,
      errorMs: audioOnly() ? null : +(1000 * (videos[location.index].currentTime - location.sourceTime)).toFixed(2),
      latencyMs: +(performance.now() - started).toFixed(2) });
    status(audioOnly() ? "Paused — audio position prepared" : "Paused — source frame prepared");
  } catch (error) {
    if (token === generation) throw error;
  } finally { if (token === generation) busy = false; }
  if (resume && token === generation) await play();
}

async function bufferAt(time, index) {
  const token = ++generation;
  pause();
  baseTime = time;
  busy = true;
  status("Buffering — assembly clock paused");
  event("buffer-start", { index });
  try {
    if (blockedIndex === index) {
      await wait(600);
      if (token !== generation) return;
      blockedIndex = -1;
    }
    const location = position(parts, time);
    await mediaReady(videos[index], location.sourceTime);
    if (token !== generation) return;
    event("buffer-end", { index });
  } catch (error) {
    if (token === generation) throw error;
  } finally { if (token === generation) busy = false; }
  if (token === generation) await play();
}

function frame() {
  requestAnimationFrame(frame);
  if (!buffers.a || !buffers.b) return;
  const time = elapsed();
  const location = position(parts, time);
  $("live").textContent = `${time.toFixed(3)} / ${duration().toFixed(3)}s · source ${parts[location.index].source.toUpperCase()} ${location.sourceTime.toFixed(3)}s · ${parts[location.index].framing}`;
  if (!running) return;
  $("seek").value = time;
  if (time >= duration()) { pause(); status("Ended"); event("ended"); return; }
  if (audioOnly()) {
    if (location.index !== currentIndex) {
      const previous = currentIndex; currentIndex = location.index;
      event("audio-segment", { from: previous, to: currentIndex });
    }
    return;
  }
  const next = location.index + 1;
  if ($("mode").value === "scheduled" && next < parts.length && !warming.has(next)
    && time >= parts[next].start - 1 && next !== blockedIndex) {
    warming.add(next);
    const token = generation;
    const video = videos[next];
    void video.play().then(() => {
      if (token !== generation || !running) { video.pause(); return; }
      const target = parts[next].in + elapsed() - parts[next].start;
      if (Math.abs(video.currentTime - target) > 0.025) video.currentTime = Math.max(0, target);
      event("decoder-warm", { index: next });
    }).catch((error) => mediaPlayError(token, error));
  }
  if (location.index !== currentIndex) {
    if (blockedIndex === location.index || videos[location.index].readyState < 2) {
      void bufferAt(parts[location.index].start, location.index).catch(fail);
      return;
    }
    const previous = currentIndex;
    videos[previous].pause();
    show(location.index);
    const token = generation;
    const nextVideo = videos[currentIndex];
    void nextVideo.play().then(() => {
      if (token !== generation || !running || videos[currentIndex] !== nextVideo) nextVideo.pause();
    }).catch((error) => mediaPlayError(token, error));
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
  await context.audioWorklet.addModule("/meter.mjs");
  worklet = new AudioWorkletNode(context, "meter");
  analyser.connect(worklet);
  const gain = context.createGain(); gain.gain.value = 0.35;
  worklet.connect(gain).connect(context.destination);
  worklet.port.onmessage = ({ data }) => { report.audioOutput = data; renderReport(); };
}

async function load() {
  const token = ++generation;
  testGeneration++;
  pause();
  busy = true;
  status("Loading existing proxies/audio…");
  try {
    config ??= await (await fetch("/config.json")).json();
    if (token !== generation) return;
    if (!context) {
      context = new AudioContext(); analyser = context.createGain(); nativeGain = context.createGain();
      nativeGain.connect(analyser);
      monitorReady = prepareAudioMonitor();
    }
    await monitorReady;
    if (token !== generation) return;
    parts = cases[$("sequence").value];
    if (audioOnly()) $("mode").value = "scheduled";
    $("mode").disabled = audioOnly();
    for (const node of mediaNodes) node.disconnect();
    mediaNodes = []; audioElements = [];
    $("stage").replaceChildren();
    videos = audioOnly() ? [] : parts.map((part) => {
      const video = document.createElement("video");
      video.playsInline = true; video.preload = "auto"; video.src = `/media/${part.source}`;
      video.style.transform = part.framing === "tight" ? "scale(1.5)" : "none";
      video.style.filter = part.source === "b" && $("gray").checked ? "grayscale(1)" : "none";
      $("stage").append(video);
      video.addEventListener("waiting", () => {
        if (token === generation && running && !busy && videos[currentIndex] === video) {
          event("media-waiting");
          void bufferAt(elapsed(), currentIndex).catch(fail);
        }
      });
      const node = context.createMediaElementSource(video); node.connect(nativeGain); mediaNodes.push(node);
      if (config.audio[part.source]) {
        // Silent proxy: control mode uses an independently clocked audio element.
        const audio = new Audio(`/audio/${part.source}`);
        audioElements.push(audio);
        const node = context.createMediaElementSource(audio); node.connect(nativeGain); mediaNodes.push(node);
        video.addEventListener("play", () => {
          if ($("mode").value === "native") {
            audio.currentTime = video.currentTime;
            void audio.play().then(() => {
              if (token !== generation || video.paused || $("mode").value !== "native") audio.pause();
            }).catch((error) => mediaPlayError(token, error));
          }
        });
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
    if (!audioOnly()) await Promise.all(videos.map((video, index) => mediaReady(video, Math.max(0, parts[index].in - (index ? 1 : 0)))));
    if (token !== generation) return;
    if (!buffers.a || !buffers.b) {
      buffers = Object.fromEntries(await Promise.all(["a", "b"].map(async (source) => {
        const url = config.audio[source] ? `/audio/${source}` : `/media/${source}`;
        const data = await (await fetch(url)).arrayBuffer();
        return [source, await context.decodeAudioData(data)];
      })));
    }
    if (token !== generation) return;
    for (const part of parts) {
      if (part.out > buffers[part.source].duration || (!audioOnly() && part.out > videos[parts.indexOf(part)].duration)) throw new Error("Fixture shorter than edit list");
    }
    baseTime = 0; currentIndex = -1; show(0); blockedIndex = -1; warming = new Set();
    report = { browser: navigator.userAgent, case: $("sequence").value, mode: $("mode").value,
      visibility: document.visibilityState,
      duration: duration(), parts, audioOnly: audioOnly(), videoElements: videos.length,
      decodedAudioBytes: Object.values(buffers).reduce((n, b) => n + b.length * b.numberOfChannels * 4, 0), events: [], samples: [] };
    $("seek").max = duration(); $("seek").value = 0;
    for (const id of ["play", "pause", "run", "stall", "seek", "before", "after"]) $(id).disabled = false;
    $("stage").style.display = audioOnly() ? "none" : "block";
    status(audioOnly() ? "Ready — existing audio decoded; no video needed" : "Ready — all segment start frames preloaded"); renderReport();
  } catch (error) {
    if (token === generation) throw error;
  } finally { if (token === generation) busy = false; }
}

async function run() {
  const token = ++testGeneration;
  $("run").disabled = true; $("cancel").disabled = false;
  for (const id of ["load", "sequence", "mode", "audioOnly", "play", "seek", "before", "after"]) $(id).disabled = true;
  delete report.complete;
  delete report.videoQuality;
  delete report.heapBytes;
  try {
    await seek(0);
    if (token !== testGeneration) return;
    report.events = []; report.samples = []; report.maxVideoClockErrorMs = 0;
    report.presentedFrames = []; worklet.port.postMessage("reset");
    await play();
    if (token !== testGeneration) return;
    while ((running || busy) && token === testGeneration) await wait(50);
    if (token !== testGeneration) return;
    if (baseTime < duration() - 0.001) {
      event("measured-pass-interrupted"); status("Measurement interrupted — not a complete playback pass"); return;
    }
    // A resumed window measures only its last stretch; never qualify that as a continuous pass.
    if (report.events.some(({ type }) => type === "buffer-start")) {
      event("measured-pass-interrupted", { reason: "buffering restarted the audio window" });
      status("Playback buffered — not a continuous measurement pass"); return;
    }
    for (let attempt = 0; attempt < 20 && !report.audioOutput?.windowComplete; attempt++) await wait(50);
    if (token !== testGeneration) return;
    const expectedFrames = Math.round(duration() * context.sampleRate);
    if (!report.audioOutput?.windowComplete || report.audioOutput.expectedFrames !== expectedFrames
      || report.audioOutput.observedFrames !== expectedFrames) {
      event("measured-pass-interrupted", { reason: "audio window incomplete", expectedFrames });
      status("Audio measurement incomplete — not a qualified pass"); return;
    }
    event("measured-pass-complete");
    const qualities = videos.map((video) => video.getVideoPlaybackQuality());
    report.videoQuality = qualities.map(({ totalVideoFrames, droppedVideoFrames, corruptedVideoFrames }) => ({ totalVideoFrames, droppedVideoFrames, corruptedVideoFrames }));
    report.heapBytes = performance.memory?.usedJSHeapSize ?? null;
    report.complete = true; renderReport(); status("Measured pass complete — report retained below");
  } finally {
    $("run").disabled = false; $("cancel").disabled = true;
    for (const id of ["load", "sequence", "mode", "audioOnly", "play", "seek", "before", "after"]) $(id).disabled = false;
    $("mode").disabled = audioOnly();
  }
}

$("load").onclick = () => load().catch(fail);
$("play").onclick = () => play().catch(fail);
$("pause").onclick = () => { ++generation; pause(); status("Paused"); event("pause"); };
$("seek").onchange = () => seek(+$("seek").value, running).catch(fail);
$("before").onclick = () => seek(parts[0].end - 0.1).catch(fail);
$("after").onclick = () => seek(parts[0].end + 0.1).catch(fail);
$("run").onclick = () => run().catch(fail);
$("cancel").onclick = () => { testGeneration++; ++generation; pause(); status("Measurement cancelled — paused"); event("measurement-cancelled"); };
$("stall").onclick = () => { blockedIndex = Math.min(currentIndex + 1, parts.length - 1); event("unready-test-armed", { blockedIndex }); };
$("sequence").onchange = $("mode").onchange = () => load().catch(fail);
$("gray").onchange = () => videos.forEach((v, i) => { v.style.filter = parts[i].source === "b" && $("gray").checked ? "grayscale(1)" : "none"; });
$("audioOnly").onchange = () => { $("mode").value = "scheduled"; load().catch(fail); };
document.addEventListener("visibilitychange", () => event("visibility", { state: document.visibilityState }));
requestAnimationFrame(frame);
