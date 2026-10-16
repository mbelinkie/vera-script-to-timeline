# Issue 177 second usage checkpoint

User explicitly resumed this same chat, then the five-hour window reached
90% used / 10% remaining. Weekly14% used /86% remaining. Paused again under
the standing user threshold. Do not resume without explicit human direction.
Same active claim/branch/worktree; root goal and resume heartbeat remain paused.

The complete v2 package APIs, independent OTIO/tree/receipt verification,
atomic publication and retry are now saved. Package focused command:
`rtk proxy ctx-wire run uv run --frozen pytest tests/test_v2_package.py -q --durations=25`
completed exit0,5passed in3.25s. Original log retained at
`/private/tmp/issue177-v2-package-focused.log` and copied beside this checkpoint.
Ruff passed before final type-only edits; current full type/lint rerun is due.

Parent handoff3-file mypy passed after helper return annotation repair.
Parent handoff formatting/lint passed. Package6mypy failures were reported
to worker for correction; verify final owned code before claiming type green.

Final short combined command (session9396):
`rtk proxy ctx-wire run uv run --frozen pytest tests/test_workflow_v2.py tests/test_issue177_handoff.py -q --durations=25`
completed exit1,27passed1failed in7.75s. All17parent handoff tests now pass,
including independent package attestation/readback and media drift refusal.
Studio10pass1fail: `test_native_source_audio_is_refused_before_adapter_creation`
fails with KeyError `sourceAudioNativeQualified` at testline393. The result
is stopped_safely and the forbidden adapter is not invoked, but the result
does not reach the expected qualification field. Investigate the earlier
loader refusal/message and fixture consistency; do not mask the missing field.
No passing Studio rerun is claimed.

The final short run was accidentally launched in the same tool call as the
threshold read, before the parent inspected90%used. It was allowed to finish;
no further implementation or test began. Future cost phases must follow a
separate inspected usage read. No owned command remains live.

Both workers stopped and released their test slots. Slate/cover/native picture
metadata preflight support is now separated from native capability; native
unqualified treatment/audio/fractional builds refuse. Still treatment on video
sources is corrected. These changes need complete source/review verification.

Remaining: fix final Studio failure; rerun all focused checks/types/lint;
expand missing meaningful topology/audio/gain and attack coverage; frozen/
generated currentness; fast gate; adversarial Claude review/fixes/delta review;
qualifying final full evidence under VERIFICATION_POLICY. No PR/commit/merge/
closure has occurred. Keep all v1 frozen boundaries unchanged. No real media,
Resolve, private data, upload or successor operation occurred.
