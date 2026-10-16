Checkpoint13c corrective review, following your no-blocker static13b review. User requires checkpoint reviews and immediate stop if Claude quota is exhausted. Read-only Read/Grep/Glob only, no commands/edits/native/cloud/paid actions/delegation.

An actual CLI/WI test after the13b packet did NOT pass: the negative picture-only trim was refused correctly, but its complete well-formed response failed the semantic occurrence validator before consumed.json or refused.json was written. The next explicit propose reused the pending response, so it never captured the restored/current positive edit. Full failing execution is checkpoint-13b-flow-failure.txt. No canonical/provider/rebuild/pointer change happened. Your previous review inspected assertions; it was not passing execution evidence.

Correction plan and implementation: in existing ProofSession._capture_files, catch ONLY ProofBuildError from the purpose-specific validate calls. Publish immutable terminal refused.json containing responseHash/reason, then re-raise the original refusal. Leave missing response/NeedsAction/process/source faults and all successful response validation unchanged. Pending selection already excludes consumed/refused attempts; the next explicit action therefore creates a NEW nonce/read instead of modifying/reusing rejected facts. Retain response/request/refusal bytes, no cleanup. No provider/native effect/baseline advancement is granted. Do not add a retry orchestrator or silently classify process faults as semantic refusals.

Read FULL current roundtrip_proof.py (13b did not reread the full unchanged host). Inspect this error-handling order and existing callers, source/current guards and immutable publication. New focused reservation regression isolates only native readiness with an explicit fake identity; it is not a native positive. It proves failed response retained/unconsumed, fresh next nonce/callback, one successful consumed receipt and old failure bytes unchanged. Actual full CLI/WI flow also asserts terminal refusal then attempts all three positive edits and generation/fresh target/replays; it is running, no pass claimed until log retained. The meaningful initial red is actual failed CLI flow, not just a synthetic direct helper.

Other post13b changes: demo now asserts refused.json/unconsumed capture; runbook clarifies #148 should target an approved complete programme close to60s, since3M48k samples/25fps cap=62.48s. No range/cap/coverage change, no silent truncation/padding/substitution. All frozen/protected boundaries remain unchanged. Other13b source is unchanged, static review accepted. Existing named real qualification gates remain closed.

Read full files:
- python/vera_timeline_agent/roundtrip_proof.py
- tests/test_issue144_capture_retry.py
- tests/issue144_wi_demo.py
- docs/investigations/issue-144/operator-runbook.md
- docs/investigations/issue-144/checkpoint-13b-flow-failure.txt
- docs/investigations/issue-144/checkpoint-13b-disposition.md

Report any actionable correctness/spec/effect/replay issue with severity/file/line, or explicitly none. Does this fix safely terminate rejected capture authority while requiring fresh reads? Is anything else required before freezing the source commit and running full validate? Static review is not native qualification or your test execution.
