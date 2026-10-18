# 23.976 Studio qualification

Issue #178 starts from merged main `ba7f07f54ceda3fa8225b51427ca82e4a2137d3e`.
The installed #209 route is the native build/save-reopen/render boundary.

Status: physical qualification remains incomplete. Twelve actual native renders
and their decoded measurements pass; no complete #178 acceptance is claimed.

| Retained run | Physical result |
| --- | --- |
| `same-03` | Same-rate original reused; 72 frames, 3.003 s, exact numbered samples, Full 0 dB, zero click offset/drift. |
| `full-02` | 72 frames; Full 0 dB, zero click offset/drift. |
| `fractional-01` | 30000/1001 and 24 fps at nonzero inpoints; 312 frames, exact cadence, Full 0 dB, zero click offset/drift; muted interval peak 0. |
| `mixed-08` | 25/30 fps derivatives; 1032 frames, exact cadence, Full 0 dB, zero click offset/drift; muted interval peak 0. Research-descriptor variant remains separate. |
| `topology-01` | 641 frames; continuous root, child, return and independent overlay with real narration. Every visible numbered frame and the same-MOV PCM comparison pass. |
| `quiet-02` | 72 frames; measured −18.0000064 dB, zero click offset/drift. |
| `no-02` | 72 silent tested frames followed by a 72-frame Full reference; no source-audio event in the tested interval, decoded peak 0. |
| `endpoint-02` | 250-frame/10-second 25 fps picture becomes 240 target frames/10.01 seconds; exact cadence. Endpoint interval is muted, with an audible reference afterward. Enabled endpoint sound remains blocked by #249. |
| `mixed-09` | Research 25 fps plus local 30 fps; 1032 frames, exact cadence, Full 0 dB, zero click offset/drift; muted peak 0. |
| `quiet-mix-01` | 641 frames; prepared Quiet source sound under real narration, root/child/return/overlay geometry, every visible numbered frame and fixed same-MOV PCM comparison pass. Listening remains outstanding. |
| `defaults-04` | 168 frames; intentional default slate holds exactly 72 frames, explicit one-second override holds 24, followed by 72 verified reference frames. Every slate frame matches its admitted picture (maximum 8-bit pixel RMSE 2.375). |
| `recovery-01` | Host preparation with Resolve unavailable, retained uninvoked request, application relaunch, then all seven native stages and 72 measured same-rate frames pass. No consumed operation was replayed. |

Each passed run completed all seven installed native stages, save/reopen,
pre/post geometry, bound render job/output, and the fixed zero-lag/unity-gain
same-MOV PCM comparison. Measurement reports authenticate the completed session,
admission, preparation and actual MOV hash. Still/Presenter composition,
listening and native recovery remain outstanding. Sessions pin their consumed
production source; these historical results do not qualify later changed
native source automatically.

Actual preparation refusals/restart pass. Public package checks also refuse
wrong derived bytes (`package_file_hash_mismatch`), stale selected occurrences
(`MISSING_OCCURRENCE_BINDING`) and stale word anchors (`STALE_WORD_ANCHOR`).
An actual prepared three-source Quiet overlap refuses compilation with
`SOURCE_AUDIO_OVERLAP` and never reaches native construction.
`mismatch-01` constructs and saves/reopens in Resolve, then mechanically
disables its owned clips. Installed `capture_pre` refuses `disabled native
item`; no render is queued, no output exists, and the failed chain refuses
replay. The changed disposable target remains saved.

`quiet-01` completed native rendering but final comparison refused host clock
uncertainty; it is retained and not counted as a pass. Fully silent No/endpoint
fixtures correctly fail the existing non-vacuity gate. Replacement fixtures
place an audible reference after the silent tested interval, preserving that
gate. Every unsuccessful target and attempt remains retained.

Follow-up gaps are tracked in [#248](https://github.com/mbelinkie/vera-script-to-timeline/issues/248)
(bounded render retry) and [#249](https://github.com/mbelinkie/vera-script-to-timeline/issues/249)
(enabled source sound at fractional complete-clip endpoints), and
[#250](https://github.com/mbelinkie/vera-script-to-timeline/issues/250)
(current-compiler Presenter qualification admission). None was
dispatched. These gaps do not become qualification success by being ticketed.

The qualification uses issue-owned numbered-frame/flash/click media through
the public CFR preparer, the actual TypeScript compiler and verified v2
packages. Existing placeholder-byte package fixtures are unsuitable for
physical qualification. Original research and Sweden inputs remain untouched.

Required checks are same-rate reuse, combined 25/30 conversion, fractional
29.97/24 cadence with nonzero inpoints, continuous root/child/return and
independent overlay, default/override/complete-clip endpoints, No/Quiet/Full
sound, input refusals, and preparation/native/render recovery. Each positive
native case requires saved/reopened geometry, bound job/output, same-MOV PCM
comparison and picture/audio inspection.

Only `bounded_output_residual_consistency` may be claimed by the comparison.
Internal controls remain unverified; continuous state stability and causal
exclusivity remain unclaimed. Fixed comparison gates remain programme RMS
≤0.0004 and maximum sliding 960-sample RMS ≤0.006 per channel, at zero lag and
unity gain without fitting.

Focused and fast checks run locally; GitHub Actions runs the full regression
gate. Claude's read-only review completed; the path confinement, streamed
source hashing, matrix labels and native-output measurement binding findings
have been addressed. Focused profile/measurement checks and type checks pass.

The first retained mixed-rate construction in a verified 23.976 target stopped
as `partial`: native readback reported source start 0 and end 959 for the
expected 960-frame picture event. The scoped fix normalizes only EOF where the
independently verified source count, native count and exact timeline duration
agree. A second observed audio getter convention is accepted only in the
matrix profile when precise source-time edges match within one 48 kHz sample.
Old smoke/private profiles retain their prior audio counter guard. The host's
prediction read now uses its existing 48 MB PCM bound rather than the 8 MB JSON
bound. No comparison tolerance changed.

Still-image observations exposed a frozen 0% source clock and an arbitrary
held-frame counter (86/86). The matrix-only arbitrary-counter normalization requires a static
source, exact record geometry, one native source frame and source-time edges
of zero/one target frame within one audio sample. Ordinary video still refuses
zero speed or shifted source ranges. The failed `defaults-01` through
`defaults-03` targets remain retained; `defaults-04` is the fresh passing case.

The unavailable-application run also retained an interrupted mechanical
driver: its already issued request had no native start, effects or result.
After read-only inspection, that exact request was invoked for the first time.
This qualifies the uninvoked-request boundary; render failure/retry recovery
remains unavailable under #248 and is not implied by this result.

The scheduled continuation resumed on 2026-10-18. The retained private root
`qualification-output-preparation/issue178-20261016-01` contains prepared
cases, targets, runs and measurement reports. Fast validation passes, including
1133 non-slow Python tests; focused native/controller checks pass. Full CI
remains the regression gate before merging.
