# Checkpoint 12e review — explicit omission choice and rederivation

Read-only review complete, bounded to `roundtrip_omission.py`'s new `choice`/`decision_receipt`/`revision_artifacts`/`decide`/`retained_decision` logic and the `__init__`'s new `baseline_hash` parameter, cross-checked against `roundtrip_proof.py`'s dispatch and the new decision test file. I traced the highest-risk paths by hand rather than trusting the summary, reusing confidence already established for the unchanged pieces (visual UID gate, `_capture_files`, `evidence_files`, the audio verifier) across this session's prior checkpoints.

## Consistently-rehashed report/receipt cannot grant acceptance — confirmed by trace

I specifically hand-traced the `kind="source"` case in `test_consistently_rehashed_omission_report_is_not_decision_authority`: it tampers `report["evidence"]["inputs"]["profile.json"]` to a fake hash *and* recomputes the outer digest/filename consistently from the tampered bytes — a genuinely self-consistent forgery, not a sloppy one. `retained_report()` still catches it: `proposal_report()` rebuilds `evidence["inputs"]` from `self.evidence_files(...)`'s own fresh `files.hashes` (the actual re-read file hashes, not anything taken from the stored report), and `retained_report`'s `raw == _receipt_bytes(expected)` requires full byte equality against that independently recomputed value. A forged report can only pass if it's *actually* correct, not merely internally consistent. Same logic applies to the `classification`/`text`/`revision` variants — each one is a field `proposal_report()` recomputes from scratch rather than copying forward.

## Retained replay after a future promotion — confirmed read-only, not a new authorization path

The new `baseline_hash` constructor parameter sets `self.retained = baseline_hash is not None`, which only skips the *current-pointer-must-match* check (`__init__`'s `_fact(self.retained or _file_hash(session.pointer) == self.pointer_hash, ...)`) — it does not skip `session._baseline(self.baseline_hash)`, which unconditionally re-verifies the specified baseline's artifact hash, snapshot ID, source hashes, and native identity regardless of whether it's the current or a historical one. `_baseline`'s own `_ready(build)` call only performs read-only verification (`build.run()` with no adapter), so no native action occurs on replay. This is the same shape as the already-proven visual `_retained_decision` pattern (`self._baseline(receipt["baselineHash"])`), not a new mechanism — confirmed by direct comparison, not assumed.

## Fresh capture at decision time is genuinely fresh, not reused from proposal

`decide()`'s `self.capture("decide-omission", _digest(raw), pristine=False)` uses a different `purpose` string than `propose()`'s `"propose-omission"` call, so `_capture_files`'s request-basis hash differs and this is a distinct reservation/nonce, not a replay of the proposal-time capture. The subsequent `_fact(self.proposal_inputs(a, b) == report["bindings"], "edited omission observation changed before decision")` requires this fresh capture to exactly match what was proposed — the "fresh equal complete edited captures must exactly match the proposed raw facts" property, confirmed by reading the actual comparison, not just the error message.

## Retained decision replay triggers no recapture/generation, confirmed by what it does and doesn't call

`retained_decision` → `retained_report` → `proposal_report` reads `a, b` from the already-stored `inputs["observationA"/"observationB"]` dict, never calling `self.capture(...)` again — so replay re-validates stored, hash-verified data and re-invokes the deterministic TS transformer (`revise-omission`, pure and already proven idempotent in checkpoint 11/12c), but never issues a new capture request or touches `self.session.omission_evidence`/`native_provider`. The only live capture in the whole decision flow happens once, on the first (non-retained) `decide()` call.

## Accept/reject gating — confirmed precise

`decision_receipt`'s `_fact(not accepted or report["classification"] == "supported", "unsupported omission cannot be accepted")` is checked before any capture or artifact write, confirmed by `test_unqualified_omission_report_cannot_be_accepted` asserting zero provider calls and no `decisions/` directory created. `revision_artifacts` returns `{}` for `status == "rejected"`, so `decide()`'s artifact-writing loop is a no-op on reject — no revision directory, no `compiler-dependencies.json`, no `materialization-plan.json`, confirmed directly in the test (`assert not revision_root.exists()` for reject).

## No weakened visual identity gate, no unneeded machinery

`OmissionProof` never touches `_occurrence_identity`; it uses its own `audio()` validator through the shared `_capture_files` reservation helper, exactly as established in checkpoint 12d and unchanged here. No second job store, lock, or decisions format was introduced — `decide-omission` reuses the same `decisions/<key>/` directory convention, the same `proof.lock`, and the same `publish_immutable_output` guard as the visual path.

## Verdict

No blocker found before wiring the real `NarrationService`/cache handoff, finalization/compiler step, or native rebuild/CAS segment. This stage correctly stops at `prepared_revision` — no replacement dependency, no materialization plan, no provider call, no native build, no pointer change, confirmed directly by the test asserting those artifacts don't exist on accept. This does not close #144 and does not substitute for the three original named positives, real #145 qualification, composition, or the WI/runbook work still ahead.

Static advisory review only — not test execution or native/final acceptance.
