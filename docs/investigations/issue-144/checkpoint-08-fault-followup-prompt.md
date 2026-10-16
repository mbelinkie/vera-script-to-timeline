# Checkpoint 8 follow-up: process faults and the real-observer gate

Read-only bounded correction review. No edits, execution, comments or native
actions. Your full checkpoint 8 response is retained. Both findings are acted
on; confirm the corrections before we move to the audio segment.

`roundtrip_proof.py` now has `ProofProcessFault(ProofBuildError)`. An abnormal
semantic-child exit raises this class. `main` catches it, OSError and
TimeoutExpired separately, returning status `fault`/exit 70. NeedsAction remains
`needs_action`/2; evaluated refusal remains `refused`/2. The new parametrized
`test_cli_process_fault_cannot_masquerade_as_semantic_refusal` exercises the actual
semantic subprocess boundary through the CLI with injected timeout/exit-70
faults. Both were red before correction (returned refused/2).

The plan/disposition explicitly name a #145 readiness gate: the real WI capture
and initial identity inspector require independent review and retained current
build qualification proving live Resolve getters supply actual facts. Local
manifest/package facts may serve as expected comparisons, never fill in an
unobserved native result. The file nonce/hash protocol does not authenticate a
response as live Resolve readback and claims no cryptographic provenance.

Please inspect the changed CLI exception paths and new tests, and confirm the
observer constraint is the correct minimal boundary. Do not reopen the settled
whole-row policy or widen this visual segment into native/provider execution.
No additional synthesis framework is planned: the next segment uses accepted
NarrationService with an injected test provider.
