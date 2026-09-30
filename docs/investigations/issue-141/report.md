# Issue 141 — observation investigation, preparation checkpoint

September 30, 2026. **In progress; baseline preparation succeeded on the third run.**
The injected application readback is retained. R1–R5 editorial results and
External acceptance remain pending; the initial adjacent-read consistency is
bounded evidence only.

## Successful baseline preparation

At 17:39:43 UTC (13:39:43 EDT), the operator reported “It worked!” The retained
injected run identifies DaVinci Resolve Studio 21.1.0 build 14 / CPython 3.14.7,
project `VERA Issue 141 Synthetic Probe 20260930-01a0f318`
(`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`) and baseline timeline
`88f7923d-55a7-471f-b09b-cf10f9fae8ad`. Preparation setters/imports/linking/markers
and save returned success. The capture has two identical adjacent passes, no
getter failures, six distinct timeline occurrence IDs, matching hashes for all
reachable sources, 25 fps timeline/playback, 48 kHz sample rate, and storage
locations under the probe output. The operator subsequently confirmed: “Yes, None
stayed set; synthetic project only.” This confirms External Scripting remained None
and only the named synthetic project/generated media were touched for this run.

The readback differs from requested bounds: base, speech and bed each report
`GetDuration=199`, start 0, end 199 (requested duration 200); cutaway reports
49, start 50, end 99 (requested 50); overlay reports 125, start 75, end 200
(requested 50). These are raw reported values; no endpoint convention is assumed
and the baseline is not corrected. This establishes preparation and adjacent-read
consistency only. No R1–R5 editorial outcome has been observed.

## Native repeat preflight refusal

At 18:12:39 UTC on September 30, the native-repeat launcher stopped with
`RuntimeError: Current project is not the prepared baseline-only state`. Its
full preflight comparison differed from the prepared baseline. The cause is
unknown (metadata change or edit); this does not establish unsupported Resolve
behavior. The harness stopped before mutation and produced no native journal.
The preflight current-observe readback was not retained, leaving an evidence-
retention gap: the exact before-state comparison cannot now be reconstructed.
The sanitized launcher result and matching raw/published SHA-256 are retained in
`evidence/native-preflight-refusal/`.

The staged next action is read-only observation at stage
`baseline-state-discrepancy-read-only`; it makes no Resolve mutation. The next
operator launch should retain that preflight readback to establish the current
state before deciding what action is supported.

## First operator run and correction

At 16:56:37 UTC (12:56:37 EDT), the operator launched the integration and
reported no visible result. Actual injected evidence confirms **DaVinci Resolve
Studio 21.1.0 build 14**, **CPython 3.14.7**, and creation of project
`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`, named
`VERA Issue 141 Synthetic Probe 20260930-01a0f318`.

The journal records only CreateProject and SetSettings, with true setter
return. The readback has `timelineFrameRate: 25.0` (number), while the request
used `"25"` (string). The agent's guard wrongly compared their string forms
and stopped before any import or timeline creation. This is a probe bug,
not evidence that Resolve rejected 25 fps. Replaying the actual readback
reproduced the failure. The numeric guard now compares exact decimal values
and still rejects missing/incorrect/nonfinite settings.

Full originals remain immutable locally; `evidence/attempt-1/` publishes
private-path-redacted versions plus raw/published hashes. Operator launch and
symptom are confirmed; None and synthetic-only/untouched-existing-state
attestations remain pending and are not inferred from config or the audit.

The readback also showed inherited 24 fps playback and storage locations
outside the disposable directory. The first correction requested 25 fps
playback and slice-owned media/cache/gallery paths. That continuation ran at
17:20:18 UTC (13:20:18 EDT) and failed with `SetSettings refused operation`,
again before import. `evidence/attempt-2/` retains the request, failure and
launcher result with raw/published hashes. The operator again reported no
visible result; scripting/synthetic-only attestations remain pending.

## Read-only playback setting and current correction

The installed `DaVinciResolveScript.pyi:424–425` explicitly marks
`timelinePlaybackFrameRate` read-only. Writing it was the agent's second
probe bug. `README.md:237–244` documents batch settings as partially applied
in unspecified order on failure. Thus the second attempt does not prove that
other settings remained unchanged; their current values need a fresh readback.
The setter form itself is documented and is not the problem.

The corrected continuation never writes the playback property. Before any
further setting mutation it retains current settings and requires the operator
to have set Playback frame rate to 25 in the named project's settings. It then
applies each writable setting separately and retains its readback even on
refusal. Final verification includes 25 fps playback, 25 fps timeline, 48 kHz
audio and the slice-owned storage paths before any media import. Writable
storage setter support remains untested; a refusal must remain explicit.

The continuation is bound to the second failed journal/failure hashes and
project ID. It requires the current project to have zero timelines, no root
media and no subfolders. It does not create another project, delete/replay
items, overwrite prior evidence or supply a generic retry system. Any mismatch
stops before further Resolve mutation. The launcher becomes read-only observe
only after successful preparation.

`installation-resume.json` recorded the latest staged launcher/source/config
hashes at that checkpoint; the staged correction subsequently ran successfully
in Resolve, as documented under Successful baseline preparation. The
settings-boundary regression
failed on the read-only write before the fix and passes after it; inherited
24 fps playback stops with an operator instruction before any setter/import.
These are harness results, not newly established Resolve capabilities. The
actual-readback regression, incorrect/missing/nonfinite-rate refusals and
empty-project recovery guards pass under CPython 3.14.7 `-S`.

## Evidence retained

- #131 baseline `817d0e5ab76219fdc3df95b196f84fbad0382f0a` and accepted #110
  immutable reference `22d86fa783c141b59f8631ba3020338c3368aa3e` were inspected.
  No unrelated implementation was merged to obtain #110's evidence.
- #110's operator observed Studio 21.1.0 build 14 / injected CPython 3.14.7,
  External Scripting None, synthetic-only scope, channel-1 mono mapping, Voice
  Isolation and Dialogue Leveler changed/read back/restored. Normalization and
  PCM-WAV render selection failed; preset/EQ/dynamics remained operator-only.
  These are historical compatibility bounds, not new #141 probe results.
- The initial status query reported **not running**, installation version 21.1.
  Actual injected identity from the later operator run supersedes that query
  for the named run. Preferences still require operator confirmation.
- Generated inputs and exact manifest are retained under `inputs/`. Eleven
  files, 25 fps / video time base 1/12800, 48 kHz PCM, four byte-identical
  synthetic “echo” kernels, a crossing tone bed, a 50%-alpha overlay, and
  same-byte/wrong-byte relink candidates. Original manifest SHA-256:
  `10eafc271a38be2db2cc34a808e5d0346755009a366d3566a562d8b28442aef3`.
  These are generated test inputs, never captured program output.
- Separate stdlib-only Workflow Integration launcher matches #110's injected
  object pattern. It refuses changed input hashes, project collisions,
  non-None attestation, unknown project ID and unexpected locators. Preparation
  journals calls/returns and item before/after getters; observation has no
  Resolve mutations. Failures retain the partial project rather than cleaning up.
- Fingerprints cover two adjacent read-only passes. Changed/failed/incomplete
  capture is refused. There is no application revision token, no atomicity
  guarantee, and no proof against changes occurring and being undone between
  reads. Do not use this content hash as apply authorization.

## R1–R5 status and downstream limits

| Required evidence | Current status | Constraint until an actual result |
|---|---|---|
| R1 reopen/trim/move/razor/copy/timeline duplicate; identical signatures | **Untested; operator run pending** | No occurrence lineage or binding by filename, order, signature or copied custom-data. |
| R2 complete program audio, repeated word/sample/derived ends, residual/mute/retime | **Untested; operator run pending** | Word deletion stays unavailable. Source support alone never proves omission from every route. |
| R3 compositing/effects/offline/Graphic/structural boundary/crossing bed | **Untested; operator run pending** | Track order is not visibility. Preserve opaque effects and crossing media; no automatic structural adoption. |
| R4 verified relink/offline/present versus removed/wrong bytes at same locator | **Untested; operator run pending** | Availability, bytes, locator, occurrence and logical identity stay distinct. Missing/offline cannot mean deletion. |
| R5 quiet/reopen/new-edit/marker repeats and inconsistent capture | **Editorial repeat tests pending**; initial baseline capture has equal adjacent reads with no getter errors | Fingerprint is evidence only; no atomic source revision or durable review/apply concurrency claim. |

For #131/#139, safe design discussion can continue to describe these explicit
refusals, source preservation and manual review. **No observation-dependent
design claim is newly cleared by this checkpoint.** It does not reopen #131's
accepted artifacts or establish production feasibility.

Future #101 must retain raw observations, exact source hashes and unknown states;
#102 cannot manufacture identity, speech deletion or visibility from incomplete
facts; #103 must surface ambiguity and stale/inconsistent review; #104 must
preserve sources and block unsafe apply. Contract and review decisions remain
separate gates. #137/#128/#138/#139 retain their current scopes/statuses and
dependencies on #141/#142. Neither dependency is removed here.

## Automated check record

- The pending `native-repeat` batch passed its fake lifecycle/refusal checks and
  independent safety review. It binds the original raw baseline hash, requires
  the unchanged single-timeline baseline, journals save/close/load/duplicate
  operations and checks project identity before mutations. No live batch result
  is claimed. Its launcher returns to observation after a consistent result.
- Independent verification checked all 26 published baseline artifact hashes
  and found no private-path leak. Its first full validation exited in the
  contracts Vitest lifecycle without an available assertion. An isolated
  pinned contracts rerun passed all 141 tests with no code/test repair; the
  original failure remains unexplained rather than being called fixed.
  The subsequent full pinned validation passed, including all 175 Python tests.
  `installation-native-repeat.json` binds the installed source/config for the
  pending operator batch; staging made no Resolve call.
- `python3 -S docs/investigations/issue-141/check.py <generated-media-dir>`:
  passed; refusal/error-retention and exact media hash/time-base/sample checks.
- `npm exec --yes --package=node@24.19.0 -- npm run validate`: passed;
  generated types current, TypeScript lint/typecheck, 141 contract tests,
  1 smoke, 6 progress and 23 roadmap tests; Python lint/format/strict mypy and
  175 tests. Python application test runtime 3.12.14 / pytest 9.1.1.
  The latest correction passed the full command again. An intermediate run
  stopped on one overlong error-message line; splitting the same literal
  corrected lint, and the full rerun passed.
- Locked install only: `npm ci --ignore-scripts`, no dependency/lock changes.
  It reproduced the three advisories already owned by #142; no fix attempted.
- Initial checkpoint frozen-boundary audit: passed; all 21 changed
  paths belong to this investigation and its plan. No frozen contracts,
  fixtures, goldens, accepted tests/design artifacts or locks changed.
  `git diff --check` and `git diff --cached --check`: passed.
- Harness/media checks ran in CPython 3.14.7 with `-S`, matching #110's
  accepted injected runtime. The installed launcher and probe source have
  retained hash bindings in `installation.json`; the successful-run None
confirmation is recorded in the operator report and interpretation summary.

Use repository shell wrappers for those commands. The injected code imports
only Python stdlib; synthetic preparation reuses the existing slate writer and
installed macOS say/FFmpeg/FFprobe. Automated checks validate the harness and
inputs, never R1–R5 application behavior.

## Next required evidence

Follow **Current next action — native repeat batch** in `operator-checklist.md`.
The batch has not run; record its actual outcome before further editorial edits.

Preserve the actual baseline bounds in the retained capture and use them in
editorial probes; do not silently correct them. Duration convention and overlay
placement require separate bounded calibration before making sample- or
visibility-timing claims. Proceed with identity/reopen testing and the remaining
operation matrix one operation at a time, replacing untested
entries with actual bounded supported/unsupported/ambiguous interpretations.
Only complete truthful evidence permits In review. External confirmation is
required for acceptance; this checkpoint does not close the issue.
