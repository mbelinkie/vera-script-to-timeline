# Live proxy assembly experiment — #91 / #125

Opt-in local diagnostic player. This is not the presenter editor, take matching,
approval persistence, production preview service or Resolve conform. It does
not block the rest of #125. The Producer authorized only this experiment as a
narrow exception to the deferred presenter workflow.

## Run

Use two existing authorized browser-safe proxy files and, for silent #44
proxies, their existing verified, zero-aligned WAV derivatives. Never substitute
unverified embedded audio for an absent verified audio handoff. No media is
included in this source package or uploaded by the player.

```sh
node docs/prototypes/issue-91-live-proxy/server.mjs \
  --a /absolute/proxy-a.mp4 --b /absolute/proxy-b.mp4 \
  --audio-a /absolute/aligned-a.wav --audio-b /absolute/aligned-b.wav
```

Open the printed loopback URL in Chrome. The fixed edit lists require A to be
at least 10 seconds and B at least 5 seconds. Audio-only is the default and creates no video elements. Load the inputs,
choose a sequence, then Run measured playback. Video mode is an exploratory
control with known continuity failures. Play/Pause, the assembly
position slider, and join seek buttons exercise actual controls. The simulated
unready-segment button tests the explicit buffering path; it is not evidence
of real network starvation. The server reads only the explicitly supplied files
and fixed player modules; there are no uploads, directory browsing or writes.

## Mechanism and checks

- Partial assembly: A1–4s → B2–4s → A4–7s (8 s). Distant same-source ranges:
  A1–3s → A8–10s → A3–5s (6 s). Continuous-tone duplicate-source control:
  A1–3s → B3–5s → A5–7s (6 s).
- In optional video mode, each segment has a preloaded native video element at its source in-point.
  The common Web Audio clock supplies the assembly position. Video follows it;
  the next segment is prepared before the join.
- Scheduled mode decodes the existing audio into AudioBuffers and schedules
  selected ranges on that same clock. It creates no new encoded audio/video.
  The control mode uses independent native media elements for audio.
- A worklet measures decoded output silence for the synthetic continuous-tone
  fixtures. This measures the browser audio graph, not physical speaker output
  or human performance quality. Silence metrics are meaningful only for a
  fixture known to have uninterrupted tone in the selected ranges.
- Video-frame callbacks retain presented source times, join lateness, seek
  completion and drift corrections. Media-element currentTime is also logged;
  neither field alone proves sample/frame-perfect playback.
- Wide/Tight uses CSS scaling for this preview experiment. It does not certify
  framing geometry, image quality or the separate Resolve profile route.

Run the focused source tests:

```sh
node --test docs/prototypes/issue-91-live-proxy/*.test.mjs
```

## Limits

The experiment decodes both whole audio files. The tested ten-minute mono
48 kHz fixtures consume 230,630,400 decoded bytes (about 220 MiB), excluding
native browser overhead. Audio-only mounts zero video elements; video mode
mounts one per segment. Production long-media playback needs bounded decoding/caching and
limited decoder counts; this implementation must not be transplanted as a full
long-script engine. The fixed edit list does not establish word alignment,
join handles, arbitrary codec support, mobile/Safari performance, network
reconnect, source permissions or production asset readiness. The diagnostic
report and transient selection are not saved project state.

## Conditions and design consequence

Tested locally on macOS in Chrome 156 with two separate, byte-identical copies
of the accepted #44 numbered-frame / 440 Hz tone fixture and their verified,
zero-aligned WAV handoffs. The Producer explicitly authorized this duplicate
control. No media, private paths or presenter transcript are committed.

The video branch did **not** qualify as seamless: even a foreground control
with one-second decoder warming encountered repeated buffering and substantial
clock drift (about 740 ms maximum in that run). Those earlier video-mode silence totals used the superseded meter and are not
used as quantitative audio evidence. A run that buffers is now explicitly
unqualified as a continuous measurement pass. CSS Wide/Tight
and grayscale switching were diagnostic treatments, not certification of
production picture quality or framing/conform behavior.

The real authorized 4K presenter sample was submitted through the normal
`ReviewIngestAdapter` workflow. Source inspection refused it with
`unsupported_profile: decoded SDR metadata missing or changes`, before a
reviewable proxy was produced. The source was only read; no guard was bypassed,
no replacement transcode or upload was attempted. This is a supported-profile
limit, not evidence that the real file completed the proxy workflow.

Corrected audio-only results are retained in
[audio-measurements.json](audio-measurements.json). Earlier zero-silence reports
used a meter that skipped missing input channels and are superseded. The new
focused test proves disconnected input is counted as silence and checks final
window completion. Each measured pass requires the full expected frame count;
buffering, cancellation, manual seek or an incomplete audio window cannot
qualify as a continuous pass.

| Corrected Chrome case | Expected / observed audio frames | Silent blocks | Longest detected silence |
| --- | --- | --- | --- |
| Continuous A → B → A, 6 s | 288,000 / 288,000 | 0 | 0 ms |
| Partial A → B → A, 8 s | 384,000 / 384,000 | 0 | 0 ms |
| Distant A ranges, 6 s | 288,000 / 288,000 | 0 | 0 ms |

All three completed with zero video elements and no composite encoding. The
threshold is RMS < 0.001 per measured render block; this excludes detected
silent blocks, not every possible click, discontinuity or audible editorial
problem. Source-time discontinuities in the partial/distant cases are intended;
the continuous duplicate-source case provides the uninterrupted-tone control.
This measures browser-graph output, not a physical speaker recording or a
human judgment of presenter performance. The join seek buttons map assembly
1.9/2.1 s to A source 2.9/8.1 s in the distant case. Play/Pause held the shared
position; keyboard Home/ArrowRight/Tab sought to assembly 0.01 / source 1.01 s.
These are observed controls and deterministic audio offsets, not a measured
speaker latency or word-boundary accuracy guarantee.

Design boundary: the Producer accepts audio-only preview. A bounded shared-clock
audio result can support that preview direction without rendering a composite;
it cannot establish seamless picture, word-to-source alignment, take matching,
approval persistence, long-media memory scaling or Resolve assembly. Keep #125
progressing and retain those production responsibilities with existing owners.
