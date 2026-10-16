Review the completed checkpoint 9 whole-row narration handoff for #144.
Read roundtrip_narration.py, tests/test_issue144_row_narration.py, the updated
checkpoint-09-narration-plan.md and roundtrip_build.py CODE_PATHS diff. Review
against the accepted NarrationService/cache/projection/normalizer and producer
row-audio policy. Eleven new tests pass; Ruff and strict mypy pass. Wider
regressions are running separately; do not treat this static review as tests.

The accepted standalone script-validator CLI exists and is used BEFORE synthesis
because old narration dependencies are stale against revised wording. There is
no Python validator reimplementation. Package testing exposed the accepted cache
locator vs required Media/ delivery destination; the issue-owned handoff maps
only the new dependency locator and keeps the actual cache origin/provenance.

Check whole-text generation/mark/cache identity and replay, untouched-row
preservation, stale/input/cache refusal, provider/lane gating and source binding.
The injected provider derives PCM and marks from complete text, with UTF-16
offsets; it is synthetic tones, not speech absence evidence. The main test goes
through actual compiler, package and durable core stages, stopping at absent
native adapter. The test revised documents are input-only, not canonical accepted
omission decisions. Final canonical serialization/fresh build IDs and wiring
into ProofSession are still later integration work. Same-request repeat returns
identical handoff; a subsequent row revision generates again. `proof_root`
explicitly encloses archived builds and the shared isolated cache.

Find concrete correctness/safety/scope issues and minimal fixes with exact
locations. Do not reopen settled whole-row replacement, propose splicing, or
claim this segment completes omission/native round-trip acceptance. Read-only:
no edits, commands, native/provider/cloud calls or permissions changes.
