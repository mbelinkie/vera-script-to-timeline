// The only external media surface in authoring. No Research URLs, tokens,
// transcript, project identity or private script content enter the iframe.
const YOUTUBE_ORIGIN = "https://www.youtube-nocookie.com";
const WIDGET_ID = 1;
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
  let handshake = null;
  let watchdog = null;
  let playing = false;
  let ended = false;
  let ready = false;

  const send = (message) => {
    frame?.contentWindow?.postMessage(JSON.stringify({
      ...message, id: WIDGET_ID, channel: "widget",
    }), YOUTUBE_ORIGIN);
  };
  const command = (func, args = []) => send({ event: "command", func, args });
  const teardown = () => {
    window.removeEventListener("message", receive);
    window.clearInterval(handshake);
    window.clearTimeout(watchdog);
    handshake = null;
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
    play.disabled = false;
    play.textContent = "Try playback again";
    replay.hidden = true;
  };
  const playRange = () => {
    // Reload the bounds on replay. YouTube's seekTo drops a queued end time.
    command("loadVideoById", [{
      videoId: range.id, startSeconds: range.startMs / 1000, endSeconds: range.endMs / 1000,
    }]);
    playing = true;
    ended = false;
    play.textContent = "Pause";
    status.textContent = "Starting saved range…";
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
    if (message.event === "onAutoplayBlocked") {
      unavailable("The browser blocked YouTube playback. You can still place this clip.");
      return;
    }
    if (message.event === "onReady" && !ready) {
      ready = true;
      window.clearInterval(handshake);
      window.clearTimeout(watchdog);
      command("addEventListener", ["onError"]);
      command("addEventListener", ["onAutoplayBlocked"]);
      play.disabled = false;
      playRange();
    }
    if (!ready || message.event !== "infoDelivery" || !playing) return;
    if (message.info?.playerState === 1) {
      replay.hidden = false;
      status.textContent = "Playing saved range…";
    } else if (message.info?.playerState === 0) {
      playing = false;
      ended = true;
      play.textContent = "Replay saved range";
      status.textContent = "Saved range finished.";
    }
  }
  const load = () => {
    if (!range) return;
    teardown();
    play.disabled = true;
    status.textContent = "Loading YouTube player…";
    const url = new URL(`${YOUTUBE_ORIGIN}/embed/${range.id}`);
    url.searchParams.set("enablejsapi", "1");
    url.searchParams.set("playsinline", "1");
    url.searchParams.set("origin", window.location.origin);
    url.searchParams.set("widgetid", String(WIDGET_ID));
    const createdFrame = doc.createElement("iframe");
    frame = createdFrame;
    createdFrame.title = "YouTube saved-range preview";
    createdFrame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation");
    createdFrame.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture");
    // YouTube requires an HTTP Referer for embedded playback (error 153 without
    // one). Send only this app's origin, never a project path, query or launch
    // fragment. The host's other responses stay on the no-referrer policy.
    createdFrame.referrerPolicy = "strict-origin-when-cross-origin";
    createdFrame.addEventListener("error", () => {
      if (frame === createdFrame) unavailable("YouTube player could not load. You can still place this clip.");
    });
    window.addEventListener("message", receive);
    createdFrame.src = url.href;
    playerMount.append(createdFrame);
    // Like YouTube's wrapper, retry until the widget has initialized. An
    // iframe load event does not tell us when its message listener is ready.
    handshake = window.setInterval(() => send({ event: "listening" }), 250);
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
    } else if (ended) {
      playRange();
    } else {
      command("playVideo");
      playing = true;
      play.textContent = "Pause";
      status.textContent = "Starting saved range…";
    }
  });
  replay.addEventListener("click", () => {
    if (ready) playRange();
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
