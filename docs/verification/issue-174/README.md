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

Continuation 2026-10-12: all round-two stages exited 0. Final full gate passed
563 Python tests in 3061.49s plus lint/types/generated/TypeScript; fast passed
323, affected URI checks 8. Qualification 15 cases verified 63 hashes,
maximum sync residual 0.062642ms/drift 0.067744ms. Tested source hashes match
committed candidate `a640e3f99dd6a68c6565a4404e6abc1b9ccda7d6`; frozen diff clean.
Claude read-only antagonist review is running durably via
`/private/tmp/issue174_claude_review.py`: supervisor PID45754, prompt/command/
revision in `out/issue174/claude-r1/start.json`, child in `process.json`, raw
`result.json`, stderr `stderr.log`, final exit/status/hash `exit.json`.
Check once on wake. Fix substantive findings and rerun affected evidence and
review; reuse valid gates only when no invalidating source change occurred.
After review, finalize criterion/human playback handoff and release coordinator
for #193 then #191. Visual/audible human judgment remains pending.

Next continuation: Claude r1 completed exit0/is_error=false with verdict FAIL,
not PASS. Raw result and finding dispositions are retained as
`claude-r1-result.json` and `claude-r1-disposition.md`. Substantive code/evidence
fixes invalidate prior final-candidate gates. Round-three durable supervisor
`/private/tmp/issue174_checks.py` now runs revised issue tests, fresh installed-
build qualification, independent retained-media verification, fast and full
gates sequentially, halting on failure. Exact source hashes/process/commands
are in `out/issue174/r3/checks-start.json`, active stage/log in
`checks-status.json`, terminal exit in `checks-exit.json`. Keep prior logs and
artifacts; never restart a live command or infer release. On terminal success,
inspect evidence once, commit revised sources, obtain exact-revision Claude
re-review and finalize the subjective handoff/release to coordinator.

Round-three result: 82 revised focused tests passed in 569.58s and all 24
installed-tool qualification cases passed. Independent verifier failed on
`target-reuse-aac` because its rawvideo decode allowed FFmpeg's implicit FPS
conversion. Corrected to `-fps_mode passthrough`; exact retained source now
independently decodes original ordinals 0–329. Production/test/qualifier source
and artifacts did not change, so those passing results remain valid. Raw
failure is in `out/issue174/r3/verify-retained.log` and `checks-exit.json`.
Round four runs only independent verification against the same round-three
artifacts, then fast/final full gates. Metadata/log/exit paths are
`out/issue174/r4/checks-start.json`, `checks-status.json`, `checks-exit.json`.
The new full gate is required because substantive post-Claude production
changes invalidated round two; this is not a repeated passing final gate.

Round four stopped on the second independent-decoder default: WAV output was
implicitly PCM16. Explicit `-c:a pcm_s24le` preserves source precision. The
corrected verifier completed exit0 (exec session55446), checking 24 cases and
98 hashes, generated-clock residual ≤0.782597ms and drift ≤0.041667ms.
Exact output/command are retained in `verifier-final.json`; failures remain in
round-three/four logs. No production/fixture/test/qualifier/artifact changed.
Round five runs only remaining fast/full gates; metadata/status/final exit
are `out/issue174/r5/checks-start.json`, `checks-status.json`, `checks-exit.json`.
Do not regenerate the passing 24-case qualification or revised 82-test matrix.
Commit after passing final gates, then obtain mandatory exact-revision Claude
re-review and concrete human quality handoff before coordinator release.

Recovery checkpoint: round-five fast gate passed 323 tests in 55.46s. Its full
gate disappeared at approximately 20% with no terminal summary/exit receipt;
supervisor91998/full93024 and matching subtree are absent, and the prior
`/private/tmp` supervisor script is missing. No diagnostic explains the cause.
Failure/log/source hashes are preserved in `interrupted-full-gate.json`;
do not call it passing. Source hashes remain unchanged, so retain the 82 tests,
24 cases, 98 hashes and fast pass. Round six recovers only full validation,
using launchd job `com.vera.issue174.full-r6` independent of the desktop session.
Supervisor source is retained in `out/issue174/r6/run_full_gate.py` (not tmp).
Command/worktree/hash revision/label are in `checks-start.json`, supervisor
PID in `supervisor-process.json`, child/stage in `checks-status.json`, actual
log in `validate-full.log`, final exit/hash in `checks-exit.json`, diagnostics
in `checks-supervisor.log` / `checks-supervisor.stderr` in that same directory.
Explicit command environment: `VITEST_MAX_WORKERS=1`,
`PYTEST_ADDOPTS=--durations=25`. Verify once per central wake; no polling loop.
After terminal pass, check hashes/commit and obtain exact-revision Claude
re-review. Remove only this completed launchd job after its subtree drains.
#174 retains slot until reviewed handoff/coordinator release for #193 then #191.

Standing policy received/read 2026-10-12: canonical
`/Users/matthewbelinkie/Desktop/ONGOING/VERA Script to Timeline/docs/VERIFICATION_POLICY.md`,
producer-approved policy commit `5ab39b221a3c58fae64be017c277655ee2d9ca28`
(local primary branch; no assertion it is on main). Preferred future order is
focused/fast → required adversarial Claude review → fixes/delta coverage →
complete final local full gate. Preserve the currently running gate; a no-change
review may reuse its passing result after proving input/profile equivalence.
Record tested versus delivered differences, exact completed command/results,
source/tests/config/locks/generated/fixtures/goldens/runtime input identities,
media and language toolchains/OS/workers/relevant environment and log provenance.
Do not treat Markdown/evidence files as automatically exempt: if checks consume
them, obtain fresh affected coverage; uncertain impact requires a new full gate.
Failed/aborted/missing coverage is never green. CI does not substitute for local
acceptance. Keep #174's adversarial Claude requirement and genuine visual/audio
human gate. The notification authorizes no new work, cherry-pick, queue release,
dispatch, merge or acceptance bypass. Apply it at next already-authorized handoff.

Round-six receipt diagnosis: actual log completed all 581 Python tests in
9646.27s with durations and all preceding checks. The legacy launchctl submit
job was non-on-demand and relaunched after completion; every later invocation
failed at the exclusive existing-log open before starting validation. Those
errors replaced the original exit receipt. All original files remain retained;
only owned job `com.vera.issue174.full-r6` was retired after its validation
subtree drained. The original npm exit value is not recoverable from current
records; no exit0 is fabricated. Keep completed coverage as observed evidence,
not a qualifying complete local full pass. Next: exact revised-commit Claude
delta review, then only the remaining final full evidence with a one-shot
runner and immutable first terminal receipt. Preserve focused82/qualification24/
verifier98/fast323 results. No blind repeats or unrelated performance work.

Current continuation: revised candidate commit
`01309fc60be899702a830fec43ff068ca74adf51`. Required adversarial Claude delta
review runs in one-shot job `com.vera.issue174.claude-r2`, KeepAlive=false;
startup verified OnDemand=true, supervisor67743/child67746. Workspace-retained
runner/plist/prompt/revision are under `out/issue174/claude-r2`; `start.json`
pins commit/command/prompt hash, `process.json` pins child, `result.json` and
`stderr.log` retain output, `command-exit.txt` and `exit.json` retain first
terminal exit without overwrite. A claim file prevents accidental duplicate
execution. Check once per coordinator wake; if still running end immediately.
After result inspection, fix/re-review substantive findings; then obtain the
remaining required full command exit evidence with the same one-shot pattern.
No subjective acceptance, merge or coordinator slot release occurred yet.

Producer steering: “I really don't want to launch another 2 hour check.”
Do not launch another full suite. Preserve the completed 581-test log and all
passing focused/qualification/fast evidence. Finish the already-running Claude
delta review, then retain the exact lost terminal-receipt provenance gap in
the handoff and use only bounded checks to resolve what can actually be proved.
This supersedes the preceding instruction to recover full evidence by another
suite run; it does not authorize fabricating an exit code or subjective result.

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

## Bounded retry after the Producer pause

The Producer's “try again” resumes this existing task. The coordinator granted
the local validation slot after #109's explicit drained release. No new blanket
full suite is authorized. The pending durability fix and published-corruption
refusal remain unverified until fresh affected checks and Claude delta review
pass. The previous 581-test log has no recoverable original exit receipt and is
not a qualifying full pass. Integrate accepted main's #193 install repair and
#196 policy before the retry; retain actual media-tool qualification and the
unperformed human playback judgment separately.
