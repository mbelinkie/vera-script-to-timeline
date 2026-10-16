# #208 — audited read-only target identity implementation

Owner: `01a13aaf-1142-7ef1-b8bb-f0396cb5d0ec`, Sol/high,
`codex/issue-208-target-identity`, worktree 3754. External acceptance.
Exact first mutation was the eligible roadmap claim; canonical dependencies
#207/#109/#177/#190 were Closed/Done. Accepted main is `017e7cf`.
The source prerequisite is committed as `72aac8a`; exact input pins and public
exclusive-seam grant are retained in
`../verification/issue-208/source-adoption.json`.

Implement only accepted CN-207-ID1 (raw SHA256
`e02da9eacd54fb90b7ca4ba63f1c3f72f37b997e426828ad8237d0bd1adc6006`):
closed name-bound operator authority/request; pre-import provenance and one-use
reservation; two complete agreeing finite current-target getter reads; immutable
unqualified result/hash lineage; separate operator acknowledgement and
receipt-backed capability authority/request v2 with freshness and consumption.

Owned paths: new `target_identity_v2.py`, CLI/launcher/bootstrap action and
inventory seams, only receipt-backed capability dispatch/guards in
`native_qualification_v2.py`, new #208 tests/plan/runbook/evidence. Preserve all
adopted #204 tests and existing observations, v1 record shapes, ordinary #177
guards and accepted #190/#192 native/core sources. No shared contracts,
generated types, fixtures, goldens or accepted tests change.
Dependency justification: standard library plus existing release flow;
no additional dependencies or lock changes.

Test-first meaningful malformed-record/scalar/path/refusal cases where practical,
then call-order/drift/currentness, expiry/rollback, concurrent reservation,
crash/publication, consumption, bootstrap and receipt-backed capability tests.
Mutation traps record attempts before raising; assert zero forbidden attempts.
Run focused new tests and relevant unchanged #204/#177/bootstrap/release
regressions (connected inventory and dispatch guards), necessary complete fast
gate, adversarial Claude Opus 5.5/high tools-empty review of exact connected
source/pins, fixes and affected checks/delta review. Preserve failed evidence.

Installation, authority issuance/confirmation on the operator's behalf and all
real Resolve operations remain held. Prepare a reviewed versioned release,
inventory/source/request hashes and short exact operator checklist. Operator
personally supplies visible names and confirmations, installs through #109,
invokes the injected flow once, independently confirms returned receipt/UIDs,
and transitions to #204 within 30 minutes. Actual installed identity and
capability evidence plus runtime fix/delta review precede final full validation.
No full gate, cloud substitution, self-closure, successor, provider, upload,
research media, selection/save/create/render/queue or fallback scripting now.

Initial active-work forecast: 4–7 hours, moderate confidence; separate operator
and runtime wait. Primary uncertainty is safe filesystem/receipt/freshness
integration across bootstrap and #204. Size S appears optimistic; coordinator
notified of practical capture and capability-integration checkpoints without
changing issue routing or scope.
