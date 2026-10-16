# Issue 141 — bounded program-audio output test plan

## Decision and boundary

A narrow native output test is conditionally viable, but it is not yet proven
safe to execute. The installed Resolve 21.1 scripting API documents
`GetAudioRenderFormats()` / `GetAudioRenderCodecs()` for the audio branch,
audio-only render settings, unique render-job IDs, and named render-preset
save/load. Current read-only discovery reports a
MOV/H.264 current selection, single-clip mode (`1`), an empty job queue, no
active render, WAV availability, and `lpcm` for WAV. Those facts establish
available API paths, not a successful render. Accepted #110 evidence from the
same Resolve build records that the `SetCurrentRenderFormatAndCodec()` WAV/PCM
selection failed before reaching render settings. The installed stubs document
`SetCurrentRenderFormatAndCodec()` as the current render format/codec selector,
while `RenderSettings.AudioFormat` is specifically documented for the
`ExportVideo == false` audio-only branch. The old failure therefore does not
prove this separate audio-only settings branch fails.

This proposal covers one test WAV rendered from the exact selected Issue 141
Matrix timeline, using only generated synthetic media. It excludes edits to
timeline content, Fairlight configuration, project save, import, upload, and
changes to any existing preset or render job. This draft is not run-ready;
focused checks, independent review, and a fresh hash-bound checkpoint must
precede a live action. Acceptance requires retained output evidence from Resolve.

## Why preset-based restoration is the only bounded API route

The installed `DaVinciResolveScript.pyi` has no `Project.GetRenderSettings()`
method. It documents `SaveAsNewRenderPreset(presetName) -> bool` as saving the
current render settings under a new name, and `LoadRenderPreset(presetName) ->
bool` as loading a preset. Use a unique, test-owned temporary preset as the
pre-change snapshot: require its name to be absent from
`GetRenderPresetList()`, save the current settings under that name, and confirm
the API returned true and the name is listed. Then call
`Resolve.ExportRenderPreset(temp_name, recovery_path)` to retain an exported copy
inside the test-owned output directory; require true, a regular non-symlink
file, and record its hash before changing anything. The stubs say export writes
a named render preset to a file. They also say `ImportRenderPreset(path)`
imports a render preset and selects it, which gives an API-documented recovery
path if the named snapshot is unexpectedly absent. At cleanup, load that exact
preset and require true; verify every available readback (current
format/codec, render mode, job-ID set, selected timeline, and no active
render), then delete only the uniquely named temporary preset and confirm it
is absent. Never update or delete a pre-existing preset.

Loading the snapshot is the documented restoration mechanism for fields with
no getter. Exporting and hashing it preserves a recovery copy; importing that
copy is documented to import and select it. The installed docs do not say the
export is a byte-for-byte snapshot, and no API reads back all settings, so
this is a concrete recovery mechanism rather than independent proof of
equality for hidden fields. If acceptance requires field-by-field independent
readback, the installed public API is insufficient and this experiment must
stop pending an operator-visible restoration method. If save, export, load,
or temporary-preset cleanup fails, retain the journal and recovery
file/preset, refuse completion, and do not retry or change other presets.

## Preconditions and stop rules

1. Require the operator's External Scripting `None` and synthetic-only
   attestation, Resolve Studio 21.1.0 build 14, the exact project ID
   `97037b5a-aab6-48a9-b7e4-4c5697ae10a0`, and selected Matrix timeline ID
   `29ae8331-b86e-4041-a548-960695cc7b24`. Require two equal adjacent fresh
   observations to match a newly reviewed immutable selected-Matrix pin.
   The discovery originally used the immutable post-reopen pin
   `capture-20260930T234711.275916Z.json` (SHA-256
   `3d08f757c8e188bbc5c1584158f5ea29c23f5bb7745bf01bd5de42c6d6436a46`),
   which is now historical: cache restoration and later availability setup
   require a fresh pin, not silently ignored differences.
   The native selected-Matrix checkpoint completed at01:52 UTC, retaining
   `matrix-checkpoint-20261001T015209.473668Z-matrix-observation.json`
   (SHA-256 `0220a23be312aea5906900dd094c8e21b363294bb11f9b0f1201ab23f40c4cbf`).
   Read its native pair schema directly: exact selectedTimelineUid plus
   equal timelinePasses and poolPasses, with both consistency fields equal.
   Do not manufacture a second capture format. Historical Matrix/Baseline/R1
   readbacks match the saved Matrix pin and the complete pool is unchanged.
   Recheck project, build, and selected timeline immediately before every
   mutating call.
2. Require `IsRenderingInProgress() == false`, an empty `GetRenderJobList()`,
   unchanged current format/codec and render mode across adjacent reads, and an
   output directory newly owned by this test under the Issue 141 output root.
   Refuse if any job exists; never call `DeleteAllRenderJobs()`.
3. Read the existing render-preset names twice. Choose one unique, clearly
   test-owned temporary name, journal and call `SaveAsNewRenderPreset`, then
   verify its successful return and appearance in the preset list. Do not
   mutate settings unless this snapshot step succeeds.
4. Keep the current MOV/H.264 `GetCurrentRenderFormatAndCodec()` and
   single-clip render mode unchanged. Do not gate the audio-only attempt on
   `SetCurrentRenderFormatAndCodec("wav", "lpcm")`: the installed docs do not
   say that video/current-format setter is required for the audio-only branch.
   Record the present format/mode before and after the test.
5. After the snapshot and exported recovery copy are verified, make one
   separately audited `SetRenderSettings()` request with the documented
   audio-only branch: `ExportVideo: false`, `ExportAudio: true`,
   `AudioFormat: "wav"`, `AudioCodec: "lpcm"`, `AudioSampleRate: 48000`,
   `AudioBitDepth: 16`, `SelectAllFrames: true`, an exact test-owned
   `TargetDir`, and one unique `CustomName`. Require a true return and recheck
   that the video/current format/codec and render mode remain at their captured
   values. If the setter fails, raises, or the recheck differs, do not queue a
   job; restore the saved preset and stop. No successful behavior is assumed
   from discovery alone.

## One-job render and evidence

Before queueing, retain the exact empty job-list response and hash-check the
synthetic input manifest. `AddRenderJob()` must return one non-empty job ID;
the next job-list read must contain exactly that one new ID and no other
change. Call `StartRendering([job_id])` with that ID only and require true.
Poll `GetRenderJobStatus(job_id)` until a terminal status; require `Complete`
for success, and retain evidence on error, cancellation, ambiguous status, or
timeout. Never use the no-argument or index-based start form, start pre-existing
jobs, or automatically retry.

The output path must resolve inside the test-owned output directory, must not
already exist before the job, and must be exactly the requested generated WAV.
Retain its byte length and SHA-256. Use `ffprobe` (or equivalent independent
container inspection) to verify WAV, Linear PCM, 48 kHz, bit depth, channel
count, and duration; parse samples with a deterministic PCM reader. Keep raw
output and analysis under the owned output directory, with a redacted report
and hashes for review.

For timing/routing evidence, calculate expected sample windows from the
captured Matrix item source/record ranges and the 25 fps / 48 kHz timeline
mapping (1,920 samples per frame), not from case labels or guessed positions.
Check the four synthetic “echo” nonzero source-support intervals
`[19210,36258)`, `[115210,132258)`, `[211210,228258)`, and
`[307210,324258)` against output waveform correlation/support at the mapped
positions. Separately inspect the crossing-bed region and R2 linked-cut,
partial, and residual-track regions only after those editorial cases have
actually been performed and separately captured, to show whether the signal
appears where expected and distinguishes the staged cases. Before interpreting
channel routing, record the actual Fairlight track enable/mute/solo, channel
mapping, sends, and program-output assignment from Resolve's Fairlight view;
an enabled source clip or source-range match alone does not establish its route
to the final program bus. Report unknown routes as unsupported. These checks
support conclusions only for the named synthetic samples/conditions, not for
the general Fairlight engine or presenter material.

After the created job is terminal, restore with `LoadRenderPreset(temp_name)`,
recheck available state, then call `DeleteRenderJob(job_id)` only for the
created job and `DeleteRenderPreset(temp_name)` only for the created snapshot.
If the job never reaches terminal state, do not stop or delete it; preserve the
active job and recovery preset for the operator. Verify the old job-ID set is
restored, the temporary preset is absent, no render is active, and the
original timeline remains selected. Do not save the project. Retain the
ordered request/return/failure journal, preflight and postflight reads, output
file/hash, render job status, preset-list evidence, and operator's Fairlight
routing evidence. A failed restoration or cleanup is a retained refusal, not
a reason to retry.

## Sources and evidence

- Installed Resolve 21.1 scripting README, `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md`, SHA-256 `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`. The documented settings snapshot behavior is in “Looking up Project and Clip properties”; the render APIs are listed in the Project API section.
- Installed Resolve 21.1 type stubs, `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi`, SHA-256 `00078fa1256851b9807621a4eea5e670f4266b0e7003763cba4a62655543f0ec`. `RenderSettings` keys are around lines 829–875; render preset, queue, format and job-ID method signatures are around lines 1762–1844.
- Installed scripting API changelog, `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md`, SHA-256 `b12c961176d79a5fc87757a21dc7ce2e147f13fb4dab927ed9154943c7de1491`; it records the audio render APIs.
- Current Issue 141 read-only discovery: installed result `vera-issue-141-observation-result-20261001T000558.604188Z.json` reports WAV in both `GetRenderFormats()` and `GetAudioRenderFormats()`, `GetAudioRenderCodecs("wav") == {"Linear PCM": "lpcm"}`, current MOV/H.264, mode `1`, an empty queue, `IsRenderingInProgress() == false`, and equal adjacent pre/post reads. Staging metadata and the pinned input are retained in `installation-output-discovery.json` and `evidence/after-reopen-read-only/capture-20260930T234711.275916Z.json`. None is output-render evidence.
- Accepted #110 commit `22d86fa783c141b59f8631ba3020338c3368aa3e`, `docs/verification/issue-110/capability-report.json` (`pcmWavRender.status: unavailable`, explanation: `SetCurrentRenderFormatAndCodec()` selection failed before render settings), and `docs/verification/issue-110/external-acceptance.md`. This is a historical limit for that selection path on Studio 21.1.0 build 14, not evidence that the documented audio-only `SetRenderSettings()` branch works or fails.
- Generated source evidence: `docs/investigations/issue-141/operator-checklist.md` R2 section records exact speech-support intervals and cautions on sample/frame precision and output routing; `inputs/manifest.json` pins the synthetic 48 kHz files and sample conventions.

No Resolve calls were made while preparing this plan. No production source,
contract, fixture, or accepted test was changed.

## MOV/H.264 plus PCM calibration candidate

The exported native recovery XML from the first guarded output attempt is
retained at
`out/issue-141-observation-20260930-01a0f318/audio-output-20261001T015945.287072Z/VERA141_AUDIO_OUTPUT_20261001T015945.287072Z.drp/VERA141_AUDIO_OUTPUT_20261001T015945.287072Z.xml`
(SHA-256
`1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595`). It
records `RecordFormatType=mov`, `RecordFormatSubType=avc1`, audio enabled,
`RecordAudioBitDepth=24`, and `aud_codec=lpcm`. The accepted Issue 141 getter
discovery separately maps H.264 to the literal `H264`, WAV's Linear PCM to
`lpcm`, and QuickTime to extension `mov`. This is evidence for one candidate
configuration, not proof that the exported file will contain PCM. The XML has
no explicit ExportVideo/ExportAudio boolean and does not record an audio sample
rate.

The focused candidate is `av-output.py`; `av-output-check.py` exercises it only
with fakes. Root supplies the fresh immutable selected-Matrix checkpoint path
and hash and exact sample-rate attestation (`sampleRateHz=48000`). The module
uses the existing hash-pinned `r4-range-repair.py` full-state reader and its
complete four-timeline context, generated-manifest, timeline/pool capture, and
source-hash checks. It saves one new uniquely named preset and verifies its
exported XML contains the observed MOV/avc1/lpcm/24-bit fields before settings
change. Its one render request keeps MOV/H.264, uses `ExportVideo=True`,
`ExportAudio=True`, `AudioCodec=lpcm`, 48 kHz, 24-bit, 640x360, 25 fps, and
MarkIn0/MarkOut200 (201 frames); it omits `AudioFormat`, whose installed stub
explicitly scopes that key to `ExportVideo=False`.

The module requires the single queued job to report the exact video/audio
flags, MOV/H.264, `lpcm`, 48 kHz, 24-bit, requested dimensions/rate/range and
owned destination before starting only its returned ID. After a bounded
terminal success it uses `ffprobe` to require a MOV container, H.264 video,
201 frames at25 fps, and 48 kHz 24-bit PCM audio, then requires full content and
source equality before loading the exact snapshot. Only after those checks does
it remove its own terminal job and preset; it retains the exported XML and makes
no hidden-render-settings equality claim. Unknown job metadata, output metadata,
state drift, failures, or timeout stop with recovery evidence preserved and no
automatic cleanup/retry. No real render has been run, so compatibility remains
unproven; in particular `SetRenderSettings` can return True while leaving the
current format getter unknown, as the prior audio-only attempt showed.

The candidate was registered and staged after the verified R1 move restoration. Its direct-output checkpoint is a byte-identical copy of that restored pair (`35f7132f331a8ecf0f1685dd1167c636add1aea3118bfbf2f2e7896ae348c1c3`), with retained provenance. Focused fake checks, dispatcher validation and Ruff passed. One fixed-menu launch is authorized by the existing autonomous synthetic-only investigation scope; no render outcome is claimed before its retained result.

The initial AV attempt stopped after successful snapshot save/export because its actual XML records16-bit PCM, contradicting the historical24-bit precondition. Full pairs remain byte-identical to the move-restoration checkpoint; no render setter/queue/start was dispatched. The reviewed `av-output-continue` action binds the exact refused attempt, current state plus its one owned preset, XML16-bit recovery copy and complete checkpoint. It skips the successful save/export and performs only the remaining first-time24-bit render request. No hidden-state equality is claimed. Native refusals stop without retry or cleanup; focused continuation checks pass.

At06:32 UTC the pinned-snapshot continuation applied SetRenderSettings once (True), then stopped on four pool-readback leaves: Matrix timeline proxy `de8efefa-310d-451c-863c-d6b847e8b82e` Out and its mapping Out changed from empty to00:00:08:00 in each pass. All timeline fields, other pool fields and source evidence remain equal. No AddRenderJob or StartRendering was dispatched. Settings and the recovery preset remain retained, the launcher is disarmed, and one producer decision about a bounded queue-from-settings continuation is pending under the instruction to stop on unexpected drift. The private applied-settings record is hash-bound under output; the proposed continuation must not repeat snapshot save/export or SetRenderSettings, must validate the exact four-leaf pool delta and fresh complete state, and must verify actual queued job metadata before any render.

The reviewed queue-from-settings candidate is complete and registered, but is not staged in the private launcher. Root independently passed its fake suite, the exact raw four-leaf delta guard, dispatcher checks, Ruff and diff hygiene. It skips all already-dispatched snapshot/settings operations, uses the prior owned empty output path, and requires complete current state plus exact queued metadata before starting only one owned job. After a verified terminal output, the retained recovery preset can leave either exact pre-settings or exact post-settings pool Out state; the result names which, preserves all content, and makes no hidden-render-state equality claim. Source/hash/replay/drift checks stay mandatory. Producer decision remains pending; the launcher is synchronized but disarmed to observe.

The later actual Copy/Paste invalidates that candidate's live-state pin: new
occurrences and source Usage are present, and Matrix Out cleared again. The
review is now explicitly `stale-checkpoint-not-stageable`. A future approved
continuation must retain the settings-attempt provenance while binding a fresh
complete post-editorial checkpoint; it must verify actual queue metadata before
starting any owned job. Never broaden the old equality guard or replay settings
to make the stale pin fit. Hidden render fields and synchronization remain
unknown until native job/output evidence exists.


## Fresh-checkpoint queue continuation — 2026-10-01 11:50 UTC

The standing autonomous independent-test authorization now covers a newly reviewed checkpoint; the old queue-from-settings action remains stale and unchanged. New av-output-queue-from-fresh-checkpoint retains exact original exported preset and applied-settings attempt provenance, skips SaveAsNewRenderPreset/ExportRenderPreset/SetRenderSettings, and binds the current complete post-R2-cut pair at `editorial-case-20261001T114857.294317Z/after.json`, SHA256 `1be6a4fe8f6f98e31b9cac544e7251c74e24f7e07aaa0668985d2ae753e66e48`. Only the fresh action may accept an owned nested checkpoint; old action still requires its historical checkpoint. Full current state/source equality is mandatory before/after queue/start and restoration, including current Out values, retained copied clips and real R2 edit. One first-time owned job must expose exact flags, MOV/H264, PCM24/48k, dimensions/rate0..200 and destination before it starts. A metadata failure preserves the unstarted owned job; a render/restore failure retains evidence/recovery and stops the probe. No hidden settings equality or routing claim. Main harness, focused AV fake success/refusals and Ruff pass; prior destination is still empty. Review retained at `av-fresh-checkpoint-review.json`.


## Owned unstarted job recovery — 2026-10-01

The reviewed `av-output-drop-unstarted-owned-job` action binds the 11:53 retained result and journal hashes, exact sole unstarted job `9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd`, absent owned output, idle renderer and complete current post-R2 checkpoint. It calls DeleteRenderJob only for this ID, once; full before/after timeline/pool and visible render state must match. Preset/XML, timeline edits and all Out values stay preserved. This recovery is covered by the standing autonomous synthetic-only testing authorization. No settings replay, render, save, or retry. AV fake guards/main harness/wrapper/Ruff passed. The timeout fake exposed a negative remaining-sleep race; reused the already-present audio helper clamp, then timeout fake passed.
