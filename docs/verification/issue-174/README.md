# #174 verification and External operator handoff

Current reviewed candidate: `bd1fb70f926802b491be3e75c20c5bc56d3a53fe` on
`codex/issue-174-verified-cfr`, integrated with accepted main `289cfea`.
Executable inputs match the r7 tested revision `6365acbe`; exact source/config/
lock hashes, commands, toolchain, logs and immutable exit receipts are retained
in [bounded-retry.json](bounded-retry.json). Scope and exclusions remain in
[the plan](../../plans/issue-174-verified-cfr.md).

## Current result and remaining gates

The bounded retry exited 0 for all six stages: fresh pinned npm ci; 33 serial
recovery tests (686.35s); 24 installed-tool qualification cases; independent
verification of 98 artifact hashes and actual decoded media; public qualified
ledger/exact reuse; and the fast gate (355 Python tests in 121.21s plus
TypeScript, lint, types and generated-currentness). Measured maximum sync
residual is 0.782596ms and drift is 0.041667ms. Both are within the 1ms gate.
The public runtime accepted tool hash
`sha256:b8add4fd429a93b2bd7b1191a433b993eaf16a70a418e7f5e94ee0844630c320`.

Claude r2 found that media bytes were synced after the completion marker.
The fix syncs all attempt files and the directory before creating that marker;
new picture-only and paired-audio tests verify ordering. Corrupt published media
now produces the required published_conflict refusal while preserving bytes.
Claude r3 returned technical **PASS, with no blocking code findings**, for that
exact delta. The actual result, exit and hash are retained as
`claude-r3-result.json` and `claude-r3-exit.json`. Runtime qualification inputs
match the reviewed tree, and the public-positive source is retained byte for
byte; see `review-equivalence.json`. The three other issue-owned media test
modules still need serial checks on the current adapter. This technical PASS
does not supply missing full evidence or human judgment.

The old full log records 581 passed in 9646.27s, but a restarted wrapper
replaced its original exit receipt. It is not a qualifying full pass. The
subsequent source change also prevents using it as current full evidence.
The Producer prohibited another blanket local full suite. No new full suite
was launched. Accepted #196 cloud qualification does not certify Mac media
processing or human judgment; no own accepted exact-tree cloud evidence exists.
The required full-gate criterion remains explicitly unresolved.

The source/tools are qualified only by the retained measured cases, not every
possible cross-product of codec/container/rate/channel combinations. Other
builds fail closed. This repository-local adapter's ledger is not a packaged
runtime resource; later composition/packaging is out of scope. No original or
private media, Research data, native Studio or production project was modified.
No #174 dependency or frozen-boundary change was introduced.

## Operator checklist

Use this exact checkout:
`/Users/matthewbelinkie/.codex/worktrees/488c/VERA Script to Timeline`.
The deterministic verifier already passed; the operator supplies only the
remaining visible/audible judgment, not a repeat of automated checks.

1. Open `out/issue174/r7/qualification/sync-grid/operator-pair.mkv` in VLC,
   or run from this checkout:

   ```sh
   ffplay -autoexit -sync audio -vf scale=640:640:flags=neighbor out/issue174/r7/qualification/sync-grid/operator-pair.mkv
   ```

   Watch/listen at the beginning, 40.04s and 80.08s. Flashes and clicks should
   coincide. Judge visible judder, damaged frames/colour/quality and audible
   artifacts beyond the intentional click markers. A failure remains a
   qualification failure even when measurements pass.
2. Compare the source and video paths named in each `case.json` for the four
   silent converted controls: `24-convert`, `25-convert`, `2997-convert` and
   `30-convert`, under `out/issue174/r7/qualification`. Moving bars should follow
   the accepted measured sampling rule; binary frame identities stay readable.
3. Play the eight AAC/PCM mono/stereo 44.1/48k `operator-pair.mkv` files under
   that directory, plus `aac-48000-1-mov`, `aac-48000-1-mkv`,
   `target-reuse-aac` and `target-reuse-pcm_s24le`. Check the trim boundary and
   middle/end markers for added delay, drift or unacceptable audio artifacts.
4. Record: **“#174 visual/audible qualification accepted for bd1fb70 and the
   qualificationRecordHash in acceptance.json, reviewed in PLAYER VERSION.”**
   For failure, identify case, playback time, artifact and player/version.
   This records the subjective gate only; full evidence and Claude approval
   must also be resolved before closure or merge.

## Continuation and scheduling

The latest direct Producer instruction is “resume”. Claude r3 has completed;
do not repeat it or the unchanged r7 pipeline. The coordinator owns expensive-
work scheduling. The remaining three media modules are a bounded affected
check, requiring a clear slot; no blanket full-suite stage is authorized.
Retain a precise blocker if the compulsory full criterion cannot be satisfied
within that limit. Release after owned processes drain; do not dispatch another
issue.
Root goal remains paused unless the Producer separately resumes it.

Historical execution/queue checkpoints are retained in prior Git revisions.
Current acceptance status is in [acceptance.json](acceptance.json) and the
[criterion table](criteria.md); previous whole-gate logs are historical coverage,
not current acceptance evidence.
