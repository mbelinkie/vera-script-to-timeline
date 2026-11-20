// The only external media surface in authoring. No Research URLs, tokens,
// transcript, project identity or private script content enter the iframe.
const YOUTUBE_ORIGIN = "https://www.youtube-nocookie.com";
const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/u;
const MAX_VIDEO_MS = 24 * 60 * 60 * 1000;

export function savedYoutubeRange(clip) {
  const id = clip?.video?.youtubeVideoId;
  const startMs = clip?.selection?.exportStartMs;
  const endMs = clip?.selection?.exportEndMs;
  if (typeof id !== "string" || !YOUTUBE_ID.test(id) ||
    !Number.isSafeInteger(startMs) || !Number.isSafeInteger(endMs) ||
    startMs < 0 || endMs <= startMs || endMs > MAX_VIDEO_MS) return null;
  return { id, startMs, endMs };
}

/** An iframe exists only between the writer's Play and a close/switch/teardown. */
export function mountFootagePlayer(root) {
  const doc = root.ownerDocument;
  const title = root.querySelector("[data-footage-preview-title]");
  const rangeText = root.querySelector("[data-footage-preview-range]");
  const playerMount = root.querySelector("[data-footage-player-mount]");
  const status = root.querySelector("[data-footage-player-status]");
  const play = root.querySelector("[data-footage-play]");
  const replay = root.querySelector("[data-footage-replay]");
  const close = root.querySelector("[data-footage-preview-close]");
  let range = null;
  let frame = null;
  let poll = null;
  let watchdog = null;
  let playing = false;
  let ended = false;
  let ready = false;

  const command = (func, args = []) => {
    if (!frame?.contentWindow) return;
    frame.contentWindow.postMessage(JSON.stringify({ event: "command", func, args }), YOUTUBE_ORIGIN);
  };
  const teardown = () => {
    window.removeEventListener("message", receive);
    window.clearInterval(poll);
    window.clearTimeout(watchdog);
    poll = null;
    watchdog = null;
    // Removing the frame, rather than just pausing it, stops playback when
    // the panel/preview closes or its Research project changes.
    frame?.remove();
    frame = null;
    playing = false;
    ended = false;
    ready = false;
  };
  const unavailable = (reason) => {
    teardown();
    status.textContent = reason;
    play.textContent = "Try playback again";
    replay.hidden = true;
  };
  const finished = () => {
    command("pauseVideo");
    playing = false;
    ended = true;
    play.textContent = "Replay saved range";
    status.textContent = "Saved range finished.";
  };
  const begin = () => {
    if (ready) return;
    ready = true;
    window.clearTimeout(watchdog);
    if (playing) {
      command("seekTo", [range.startMs / 1000, true]);
      command("playVideo");
      replay.hidden = false;
      status.textContent = "Playing saved range…";
    } else command("pauseVideo");
  };
  function receive(event) {
    if (!frame || event.origin !== YOUTUBE_ORIGIN || event.source !== frame.contentWindow) return;
    if (typeof event.data === "string" && event.data.length > 4096) return;
    let message;
    try { message = typeof event.data === "string" ? JSON.parse(event.data) : event.data; }
    catch { return; }
    if (!message || typeof message !== "object") return;
    if (message.event === "onError" || message.info?.errorCode !== undefined) {
      unavailable("YouTube can't play this clip here (removed or restricted). You can still place it.");
      return;
    }
    if (message.event === "onReady" ||
      (typeof message.info?.playerState === "number" && message.info.playerState >= 0)) begin();
    const currentTime = message.info?.currentTime;
    if (playing && Number.isFinite(currentTime) && currentTime >= range.endMs / 1000 - 0.03) {
      finished();
    }
  }
  const load = () => {
    if (!range) return;
    teardown();
    playing = true;
    play.textContent = "Pause";
    status.textContent = "Loading YouTube player…";
    // start/end are a coarse provider backstop. Exact milliseconds are sent
    // via seekTo and polled for the end; the external service owns precision.
    const url = new URL(`${YOUTUBE_ORIGIN}/embed/${range.id}`);
    url.searchParams.set("enablejsapi", "1");
    url.searchParams.set("playsinline", "1");
    url.searchParams.set("autoplay", "1"); // Only created by the Play gesture.
    url.searchParams.set("origin", window.location.origin);
    url.searchParams.set("start", String(Math.floor(range.startMs / 1000)));
    url.searchParams.set("end", String(Math.ceil(range.endMs / 1000)));
    const createdFrame = doc.createElement("iframe");
    frame = createdFrame;
    createdFrame.title = "YouTube saved-range preview";
    createdFrame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation");
    createdFrame.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture");
    createdFrame.referrerPolicy = "no-referrer";
    createdFrame.addEventListener("load", () => {
      // An old frame can finish loading after a fast clip switch. Its event
      // must never send commands to (or report an error for) the new player.
      if (frame !== createdFrame) return;
      createdFrame.contentWindow?.postMessage(JSON.stringify({ event: "listening" }), YOUTUBE_ORIGIN);
      command("addEventListener", ["onReady"]);
      command("addEventListener", ["onError"]);
      command("getCurrentTime");
    });
    createdFrame.addEventListener("error", () => {
      if (frame === createdFrame) unavailable("YouTube player could not load. You can still place this clip.");
    });
    window.addEventListener("message", receive);
    createdFrame.src = url.href;
    playerMount.append(createdFrame);
    poll = window.setInterval(() => { if (playing) command("getCurrentTime"); }, 250);
    watchdog = window.setTimeout(() => {
      if (!ready) unavailable("YouTube player did not respond. You can still place this clip.");
    }, 15_000);
  };
  play.addEventListener("click", () => {
    if (!range) return;
    if (!frame) { load(); return; }
    if (playing) {
      command("pauseVideo");
      playing = false;
      play.textContent = "Resume";
      status.textContent = "Paused.";
    } else {
      if (ended) command("seekTo", [range.startMs / 1000, true]);
      command("playVideo");
      playing = true;
      ended = false;
      replay.hidden = false;
      play.textContent = "Pause";
      status.textContent = "Playing saved range…";
    }
  });
  replay.addEventListener("click", () => {
    if (!frame || !range) return;
    command("seekTo", [range.startMs / 1000, true]);
    command("playVideo");
    playing = true;
    ended = false;
    play.textContent = "Pause";
    status.textContent = "Replaying saved range…";
  });
  close.addEventListener("click", () => hide());

  function hide() {
    teardown();
    range = null;
    root.hidden = true;
    playerMount.replaceChildren();
  }
  function show(clip) {
    hide();
    range = savedYoutubeRange(clip);
    title.textContent = `Preview: ${clip.video.title}`;
    root.hidden = false;
    rangeText.textContent = range ?
      `Saved range: ${(range.startMs / 1000).toFixed(3)}–${(range.endMs / 1000).toFixed(3)} s` :
      "No supported YouTube video and saved export range.";
    play.disabled = !range;
    play.textContent = "Play saved range";
    replay.hidden = true;
    status.textContent = range ? "Press Play to load the YouTube player." :
      "Playback unavailable for this source. You can still place it in your script.";
  }
  return { show, hide };
}
