# #174 verification and External operator handoff

## Validation queue checkpoint — 2026-10-11

HOLD: producer queue is #109 → #174 → #191, superseding parallel scheduling.
#109 explicitly released #174 on 2026-10-11 after code revision
`8ef9f864acafbfa77ace5f3c699ef5cfb0e6ecb7`, full/fast/affected checks and
exact-revision Claude PASS. #174 now owns the slot; the HOLD instructions
below remain the historical queue checkpoint.
#174 remains idle until #109 explicitly releases this chat
`01a12bd6-3b7d-74a3-9ce0-b1990888cef6` on host `local`. Do not infer release
from process inventory, a quiet machine or elapsed time. While waiting, run no
tests, FFmpeg matrices, validation, Claude review, acceptance advancement or
helpers that run checks.

Saved checkpoint: uncommitted branch `codex/issue-174-verified-cfr`; initial
64-test matrix passed before final binding/fingerprint changes. Final focused
checks, retained artifact generation, fast/full validation, exact-commit Claude
antagonist review/fixes/re-review and External handoff remain pending. No owned
test/review subprocess was active when this hold was acknowledged.

After explicit release, complete the authorized agent checks and concrete
External handoff, leave human acceptance open, then release #191 via
`send_message_to_thread` to `01a12bbf-7390-7be0-bab1-e34a7387f292`, host `local`.
The bounded release is authorized by the producer queue instruction and must
name the exact revision, retained check/review results and confirm no owned
test/review subprocess remains. A real blocker or usage failure requires
retained evidence, safe draining of owned processes and release with the unmet
gate described. Never kill another chat's processes. No automatic merge,
acceptance bypass, native mutation or unrelated dispatch is authorized.

Coordinator update: preserve valid exact-revision evidence. Use affected tests
during fixes and the fast gate as appropriate; run the required full gate on
the final candidate and repeat expensive checks only when changed sources,
failures or unresolved concerns invalidate it. On the next required expensive
pytest run retain `--durations=25` (for example,
`PYTEST_ADDOPTS=--durations=25` on the full gate); do not run an extra suite
solely for timings or alter frozen tests for performance.

For future long commands, launch durable background execution and persist the
command, worktree, source revision, process identity, log and final exit-status
paths here. Verify startup once, then end the turn when no independent work
remains. The coordinator's active central heartbeat
`vera-serial-validation-30-minute-checks` resumes the current owner after
completion; create no separate monitor. One wake checks once and ends if still
running. Preserve already-running commands rather than restarting to detach;
use passive tool waits only when an existing command cannot survive the turn.
Claude review/fixes/re-review and explicit queue releases remain mandatory.

Current continuation: durable supervisor `/private/tmp/issue174_checks.py`
runs final focused tests (including `--durations=25`), new qualification,
sampling-route evidence, retained-artifact verification and fast validation
sequentially, halting on failure. Worktree is this checkout; candidate source
hashes, baseline, supervisor PID and exact commands are in
`out/issue174/checks-start.json`; active child/log is `checks-status.json`;
final exit code/results are `checks-exit.json`. A wake checks completion once.
After success, inspect results, then run required final full validation alone
with `PYTEST_ADDOPTS=--durations=25`; commit and obtain mandatory Claude review.
Do not release #191 until agent gates/handoff are complete or a genuine blocker
is retained and owned processes drained.

First durable run: final focused matrix passed 64 tests in 422.11s with
durations retained. Qualification then failed compiler `uri-reference`
validation on the real checkout path containing spaces. Preserved receipt/log
are in `out/issue174/checks-exit.json` and `qualification.log`. Fixed both new
and reused locators with `Path.as_uri()`; no frozen changes. Round 2 metadata
is in `out/issue174/r2/checks-start.json`, `checks-status.json` and
`checks-exit.json`. It runs affected URI/reuse checks, fresh qualification,
sampling/retained verification, fast gate and final full gate sequentially.
Full gate uses `VITEST_MAX_WORKERS=1` and `PYTEST_ADDOPTS=--durations=25`.
Retained qualification artifacts are under `out/issue174/r2/qualification`.

Latest queue amendment: preserve the live round-two run without restart or
extra polling. After #174's required checks/Claude/handoff complete (or a
genuine blocker is retained) and owned processes drain, send the explicit
release to coordinator chat `01a11bea-e437-71e2-87df-5409e80ee96b`, host `local`.
Next heavy owner is #193 (the necessary npm CI repair for #109 PR194), then
#191. This supersedes the earlier direct #174 → #191 release; do not message
#191 a release directly. #193 may prepare isolated clean-install/fast checks
meanwhile. No #174 scope change or extra full rerun is implied.

Producer authority update: the coordinator owns progression through the named
Sweden R16 sequence #109/#174/#191, then #177/#190/#192/#178/#145 in dependency
order. Objective Automated/External criteria may close on actual retained
evidence without human repetition; genuine subjective design/listening/quality
criteria remain explicit human gates. #174's visual/audible artifact judgment
is not waived. Required exact-revision Claude review, frozen checks, routing,
dependency gates and one heavy owner remain. Necessary reviewed PR push/merge
is authorized after required CI and exact diff/source checks; attach every PR.
Coordinator dispatches consumers only after prerequisites are Closed/Done and
integrated; #174 does not independently dispatch. Preserve live durable runs
and valid evidence; no additional full rerun follows merely from this authority
update. No destructive reset/deletion, original-media/research edit, upload,
sharing or production-project mutation is authorized. Any necessary native
work is limited to approved injected flows and uniquely named disposable
nonproduction targets through the installed #109 path. Subjective #145 final
review remains open. Release #191 after concrete #174 handoff while retaining
the genuine subjective External judgment if still pending.

Issue: https://github.com/mbelinkie/vera-script-to-timeline/issues/174.
Branch: `codex/issue-174-verified-cfr`. Implementation revision and required
Claude antagonist review are recorded in `acceptance.json` after the checks.
External visible/audible acceptance remains pending until an operator records
the result below. No native Studio qualification is claimed.

## Delivered boundary

`python/vera_timeline_agent/media_preparation.py` exposes `inspect_media`,
`PreparationAuthorization` and `prepare_media`. Supply a frozen occurrence
descriptor, the compiler's exact `requestedRange`, target rate, explicit stream
indices and an authorization pinning the installed tool/profile/policy hashes.
The result supplies the existing `PreparedMediaBindingV1`, verified picture,
optional PCM sidecar, immutable receipt and reuse disposition. Stage composition
is owned by #157 and does not run here.

Same-rate picture reuses the original package with its verified package map;
its receipt retains audio's position relative to picture P0. Derived picture
starts at the exact requested source origin and selects `I+floor(j*Fs/T)`.
The WAV is PCM24/48k without loudness, pitch or speed processing. The binding's
source-audio verification names the original sample rate expected by the
frozen compiler; the receipt records the 48k output sample boundaries.

Each requirement has a local lease, separate attempt directory, receipt
checksum and atomic verified publication. Incomplete attempts remain preserved;
a verified interrupted attempt is rechecked and reconciled. Conflicting bytes
refuse for audited repair. Source media is never modified or acquired.

## Retained measurements

`qualification.json` indexes synthetic sources, prepared pairs,
source maps, selected/decoded frame ordinals, audio endpoint/peak measurements,
independent repeat hashes and actual compiler binding probes. Per-case receipts
retain source/output probes, all adapter commands, exact FFmpeg/FFprobe build
and capabilities, binary/library/adapter hashes, platform, policy and profile.
`sampling-route.json` retains the installed-build comparison of the proposed
timestamp filter and the qualified exact-cadence route.

The synthetic controls use O=3000, P0=2 seconds and H=7 seconds. Audio cases
request ten seconds at I=3010. The shared-grid case lasts 80.12 seconds and
flashes/clicks at source frames 0/1001/2002: output frames 0/960/1920, at
0/40.04/80.08 seconds. The final picture interval ends at frame 1921; PCM
stops at the exact real endpoint without invented tail audio.

AAC peak comparisons use decoded source audio and the samples actually retained
by trimming. A full-source peak before the requested start is not present in
the output. The 48k tests also compare the complete retained decoded waveform;
44.1k tests measure the resampled waveform. Signed start/middle/end residuals
and their spread are retained separately from natural source/target frame
quantization. The shared-grid PCM control aligns flash and click clocks exactly.

## Commands and required gates

Run from this checkout with the repository's pinned Node 24.19.0/npm 11.17.0
and frozen Python environment. Shell commands use `ctx-wire run rtk`.

```sh
ctx-wire run rtk uv run --frozen pytest tests/test_issue174_media_preparation.py tests/test_issue174_real_media.py tests/test_issue174_recovery.py tests/test_issue174_source_refusals.py -q
ctx-wire run rtk npm run validate:fast
ctx-wire run rtk pgrep -fl 'npm run validate|pytest'
ctx-wire run rtk env VITEST_MAX_WORKERS=1 npm run validate
```

Run full validation alone. Retained command/results and frozen-boundary audit
are in `acceptance.json`; a fast gate is not full acceptance. The baseline
`npm ci` failure is tracked separately as #193. Validation uses an exact
lockfile install in disposable staging with only the recorded workspace
manifests, then compares every installed locked package version. Root package
and lockfile bytes remain unchanged. The first temporary unlocked install was
preserved and replaced after its version comparison failed.

To generate a new independent synthetic evidence directory, use a path that
does not exist; do not overwrite accepted artifacts:

```sh
ctx-wire run rtk uv run --frozen python docs/verification/issue-174/qualify.py --output /private/tmp/issue174-new-qualification
```

## Operator checklist

1. Verify the retained artifacts from this checkout:

   ```sh
   ctx-wire run rtk uv run --frozen python docs/verification/issue-174/verify_retained.py out/issue174/r2/qualification
   ```

   Expected: all hashes, exact selection/count/endpoints and independent repeat
   hashes pass; maximum sync residual and drift are each at most 1 ms. Review
   the per-case `case.json` and receipt if a measurement needs inspection.

2. Open `out/issue174/r2/qualification/sync-grid/operator-pair.mkv` in installed VLC, or play the
   stream-copy synthetic viewing pair with the installed FFplay:

   ```sh
   ffplay -autoexit -sync audio -vf scale=640:640:flags=neighbor out/issue174/r2/qualification/sync-grid/operator-pair.mkv
   ```

   Watch/listen at the beginning, 40.04 seconds and 80.08 seconds. The white
   flashes and clicks should coincide. Judge visible judder, lost/flawed frames,
   colour/quality damage and audible clicks/distortion beyond the intentional
   marker impulses. Any unacceptable artifact is a qualification failure even
   when deterministic measurements pass.

3. Review the four converted silent picture controls (`24-convert`,
   `25-convert`, `2997-convert`, `30-convert`) using the `video` path in each
   `case.json`. Compare their source and prepared moving bars. Then play the
   eight AAC/PCM mono/stereo 44.1/48k `operator-pair.mkv` files, checking the
   trim boundary and middle/end markers. Binary identity blocks remain readable;
   motion follows the measured sampling policy and audio has no added delay
   or drift. Record player/version and each failed case/time if needed.

4. Record: **“#174 External qualification accepted for implementation COMMIT
   and qualification SHA256, reviewed in PLAYER VERSION; no unacceptable
   visible judder/quality or audible artifacts.”** Replace the placeholders
   with the revision and `qualification.json` hash in `acceptance.json`.
   For failure, name the case, playback time, observed artifact and player.
   Required Claude review and passing repository gates must also be retained
   before closure or merge. Keep #174 open while any gate is missing.
