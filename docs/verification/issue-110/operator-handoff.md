# Issue 110 — Resolve Fairlight operator handoff

Project: `VERA Issue 110 Fairlight Probe 20260910-000458`  
Resolve: `DaVinci Resolve Studio 21.1.0 build 14`  
Injected Python: `CPython 3.14.7`

## Capability boundary

- channelMapping: `supported-api` — the media-pool readback changed from one stereo track using channels 1 and 2 to one mono track using only channel 1.
- voiceIsolation: `supported-api` — enabled/amount changed, read back, and restored to disabled/zero.
- dialogueLeveler: `supported-api` — enable, mode, loud/soft treatment, background reduction, and output gain changed, read back, and restored.
- normalization: `unavailable` — `Timeline.NormalizeAudioLevel` returned false for the documented mode/target call; no normalization was claimed.
- eqDynamicsPreset: `operator-only` — no exact preset was authorized, and the public API exposes no current-preset or EQ/dynamics state getter and safe restoration call.
- pcmWavRender: `unavailable` — Resolve exposed WAV/`lpcm`, but `SetCurrentRenderFormatAndCodec("wav", "lpcm")` returned false. No rendered WAV existed to attach.

## External verification

1. Confirm Resolve Preferences > System > General > **External scripting using** remains **None**.
2. Open `VERA Issue 110 Fairlight Probe 20260910-000458` and its `VERA Issue 110 Fairlight Probe` timeline on the Fairlight page.
3. Confirm the synthetic media maps channel 1 to one mono track and excludes channel 2, matching `channelMapping.readback` in `capability-report.json`.
4. Confirm the original synthetic item is present and enabled on `Original clean probe`, Voice Isolation and Dialogue Leveler match their `restored` states, and no replacement item remains on `Rendered replacement probe`.
5. Confirm the report classifies normalization and PCM-WAV rendering as `unavailable` and EQ/dynamics/preset application as `operator-only`; do not infer those capabilities from method availability.
6. Confirm no existing project or presenter file was opened, copied, hashed, transmitted, rendered, or altered.

## Handoff to #108

#108 may automate only channel mapping, Voice Isolation, and Dialogue Leveler on Resolve Studio 21.1.0 build 14, with the same mutation/readback/restoration evidence. It must leave EQ/dynamics/preset work to a Fairlight operator, refuse the unavailable normalization and PCM-WAV paths, retain clean presenter audio, and collect final enabled-state and UI verification evidence before any A/B comparison. This handoff does not choose or apply a presenter treatment.
