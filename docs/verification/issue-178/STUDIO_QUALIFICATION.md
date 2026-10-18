# 23.976 Studio qualification

Issue #178 starts from merged main `ba7f07f54ceda3fa8225b51427ca82e4a2137d3e`.
The installed #209 route is the native build/save-reopen/render boundary.

Status: preparation and focused checks pass; physical qualification remains
incomplete. No #178 matrix acceptance claimed.

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
expected 960-frame picture event. No render success is claimed. Preserve this
target and diagnose the Resolve source-end convention before creating a fresh
attempt. Other required positives, topology/composition, listening and native
recovery remain outstanding. Preparation refusal/restart checks have passed
against actual issue-owned media.

At the Producer's request, continuation is scheduled for 2026-10-17 at
03:20 America/New_York. The retained private handoff contains the exact failed
attempt and prepared case paths. The final result will replace this status
with measured outcomes and remaining limitations.
