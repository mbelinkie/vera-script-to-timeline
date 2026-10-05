# Issue144 audio supplier contract and #145 render bridge blocker

The implemented reader is `roundtrip_audio.verify_omission_evidence`; `OmissionProof`
derives the controlled audio observations from complete native observations.
This contract describes the current synthetic lane. It does not qualify an
external supplier, real word supports, mixer reader or renderer. Real execution
remains hard closed. Example supplier: `tests/issue144_omission_fixture.py`;
executed WI example: `tests/issue144_wi_fixture.py`.

## Supplier request and files

The explicitly injected `omission_evidence` callback receives purpose
`issue144-synthetic-audio-evidence`, destination, baselineAudio, currentAudio,
expectedSources and sources. Return an absolute evidence directory inside the
independently owned proof root. The host retains tracked input bytes and hashes.
No symlink parents, symlink files or hardlinks are allowed. Reader limits are
32MiB per file and 8MiB per JSON object. Paths in the files below are relative
independent local paths inside that evidence directory.

Required names: `profile.json`, `baseline.json`, `observation-a.json`,
`observation-b.json`, `calibration.json`, `render.json`, and every referenced
source/output WAV. The fixture uses `source-*.wav`, `reference.wav` and
`program.wav`; those WAV names are examples, not fixed names. JSON field sets
are exact: missing and extra fields refuse. SHA256 values use the `sha256:`
prefix. Write observations with the host's canonical receipt encoding. The render
observationHash hashes literal observation-a.json bytes; canonical encoding
makes them match the host-derived observation binding. Baseline/current observations must equal the actual
host-derived baselineAudio/currentAudio; a supplier cannot invent neutral facts.
The audio profile/render baselineHash is the canonical baselineAudio hash, not
the authoritative script baseline-pointer hash. profileHash binds literal
profile.json bytes; observationHash binds the relevant controlled-audio observation.
Preparation profile, source and calibration bytes remain immutable through
proposal. The complete programme starts at frame0 at actual25/1fps and has at
most1562 complete frames (1920samples/frame, at most3million samples).

## Exact field inventory

| File/object | Exact fields and required meaning |
| --- | --- |
| profile.json | schemaVersion=`issue-144-audio-profile/v1`, evidenceLevel=`synthetic_injected`, supportProvenance=`fixture_generator`, baselineHash, extentFrames, sources |
| sources entry | id, rowId, path, sha256, supports; identity matches the host-selected compiled source |
| supports entry | tokenId, startSample, endSample; ordered complete nonempty word support inside the source, with independently supplied ends |
| baseline.json / observation-a.json / observation-b.json | schemaVersion=`issue-144-audio-observation/v1`, target, extentFrames, programControls, routes |
| target | projectUid, timelineUid; exact selected native target |
| programControls | gainDb, effects, limiter; qualified neutral values0, [], false |
| routes entry | id, sourceId, controls, segments; complete actual audible inventory |
| controls | enabled, mute, solo, gainDb, pan, effects, sends, destination; enabled, unmuted, nonsolo, zero gain/pan, empty effects/sends, stereo-program destination |
| segments entry | uid, recordStart, recordEnd, sourceStart, sourceEnd, speed, enabled, online; complete ordered nonoverlapping geometry with speed100, enabled and online |
| calibration.json / render.json | schemaVersion=`issue-144-audio-render/v1`, target, baselineHash, observationHash, profileHash, jobId, queuedJobId, polledJobId, status, settings, output |
| settings | startFrame, endFrame, frameRate, sampleRate, channels, codec, sampleWidth; complete0→extent, `25/1`,48000,2,`pcm`, width2 or3 |
| output | path, sha256; exact complete rendered WAV bytes |

Source profile permits1–8 distinct sources. Each has mono48k PCM16/24 WAV,
at least960 and at most3million samples, frame-aligned duration, unique encoded
AND decoded bytes, and at most64 complete supports. The selected primary has
at least3 supports so an interior omission retains neighbors. Actual narration
build input separately requires mono48k PCM24; supporting PCM16 does not widen
that requirement. Each route has1–65 ordered segments. No aliases, defaults,
partial programme renders, undocumented routes, guessed word ends or transcript
substitutions establish the required evidence.

Each render receipt must have equal jobId/queuedJobId/polledJobId and
status=`complete`; pristine calibration and edited render use distinct jobs.
Both channels contain exactly extentFrames×1920 samples. Calibration reconstructs
the complete pristine baseline and qualifies finite fixed per-channel gains
in[0.25,1.5]. Both pristine calibration and full edited reconstruction must have
whole-programme residual RMS≤0.0004 AND maximum sliding20ms (960sample) residual
RMS≤0.006 on each channel. These are RMS limits, not peak sample limits.
Residue below these limits remains a disclosed
measurement limit; success does not prove mathematically zero residual sound.
Source supports and control facts remain independently required even with a
passing reconstruction. Edited-route allowances come from actual compiler
preview; unrelated geometry/control changes refuse.

## Current WI boundary and required #145 bridge

The executable synthetic demo performs an actual WI render queue/inspection
against a fake renderer, and retains `wi-effects/.../intent.json`, `effect.json`
and `complete.json`. However, the audio verifier's supplier render receipts use
fixture job IDs and are not tied to those WI records. Synthetic pristine
calibration bypasses WI entirely. Executed WI queue records are therefore not
the host audio verdict's authority. The current trusted supplier contract checks
internal consistency; it does not attest to a live render job.

This is an explicit #145 readiness blocker. Its reviewed qualification bridge
must derive each supplier receipt from the same owned WI action:

- intent.json binds requestHash, codeHash, literal request and the actual before
  observation. effect.json binds the single queued job, target, settings and
  outputPath. complete.json binds intentHash, identical completed job, outputHash
  and sampleCount. Queue, poll and supplier job IDs must match that one job.
- Match exact projectUid/timelineUid, full-programme settings, output path and
  independently read output bytes/hash to the audio receipt. A different file
  with equal bytes is insufficient to identify the same rendered output.
- Derive controlledAudio from that action's actual raw before observation and
  a qualified complete mixer/control inventory for the same target/time. The
  raw WI observation hash and derived controlled-audio observationHash have
  different schemas; explicitly retain the mapping and both hashes.
- Qualify this path for pristine calibration, edited full programme and fresh
  rebuilt full programme. Calibration cannot be borrowed from another target,
  job or profile, and the rebuilt render must contain the replacement recording.

No supplier flag, hand-written job IDs or synthetic evidence relabeling resolves
this blocker. #145 must independently qualify real supports, routes/controls,
source/time geometry, render stability and provider provenance alongside the
bridge. #144 acceptance is limited to the implemented synthetic harness and
its refusal/safety checks.
