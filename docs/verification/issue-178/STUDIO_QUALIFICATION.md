# 23.976 Studio qualification

Issue #178 starts from merged main `ba7f07f54ceda3fa8225b51427ca82e4a2137d3e`.
The installed #209 route is the native build/save-reopen/render boundary.

Status: physical qualification remains incomplete. Four actual native renders
and their decoded measurements pass; no complete #178 acceptance is claimed.

| Retained run | Physical result |
| --- | --- |
| `same-03` | Same-rate original reused; 72 frames, 3.003 s, exact numbered samples, Full 0 dB, zero click offset/drift. |
| `full-02` | 72 frames; Full 0 dB, zero click offset/drift. |
| `fractional-01` | 30000/1001 and 24 fps at nonzero inpoints; 312 frames, exact cadence, Full 0 dB, zero click offset/drift; muted interval peak 0. |
| `mixed-08` | 25/30 fps derivatives; 1032 frames, exact cadence, Full 0 dB, zero click offset/drift; muted interval peak 0. Research-descriptor variant remains separate. |

Each passed run completed all seven installed native stages, save/reopen,
pre/post geometry, bound render job/output, and the fixed zero-lag/unity-gain
same-MOV PCM comparison. Measurement reports authenticate the completed session,
admission, preparation and actual MOV hash. Root/child/return/overlay, still
composition, listening and recovery are not implied by these flat cases.

Actual preparation refusals/restart pass. Public package checks also refuse
wrong derived bytes (`package_file_hash_mismatch`), stale selected occurrences
(`MISSING_OCCURRENCE_BINDING`) and stale word anchors (`STALE_WORD_ANCHOR`).

`quiet-01` completed native rendering but final comparison refused host clock
uncertainty; it is retained and not counted as a pass. Fully silent No/endpoint
fixtures correctly fail the existing non-vacuity gate. Replacement fixtures
place an audible reference after the silent tested interval, preserving that
gate. Every unsuccessful target and attempt remains retained.

Follow-up gaps are tracked in [#248](https://github.com/mbelinkie/vera-script-to-timeline/issues/248)
(bounded render retry) and [#249](https://github.com/mbelinkie/vera-script-to-timeline/issues/249)
(enabled source sound at fractional complete-clip endpoints). Neither was
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

The scheduled continuation resumed on 2026-10-18. The retained private root
`qualification-output-preparation/issue178-20261016-01` contains prepared
cases, targets, runs and measurement reports. Fast validation passes, including
1129 non-slow Python tests; focused native/controller checks pass. Full CI
remains the regression gate before merging.
