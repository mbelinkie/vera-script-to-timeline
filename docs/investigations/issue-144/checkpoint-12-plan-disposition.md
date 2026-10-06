# Checkpoint12 plan disposition

Claude completed4 read-only turns, zero denials. No blocker beyond the precisely
identified two-part primary-source change already called out in the plan.
Implement both together: allow auxiliary sources to share rowId while retaining
unique source IDs/raw hashes/full decoded PCM and exact route/source inventory;
make primary_source_id a required trusted-caller parameter from the actual
compiled narration event, select by it and explicitly cross-check its rowId.
Never read a primary selector out of operator profile JSON or retain the old
one-source-per-row heuristic. Add an auxiliary same-row source with3+ supports
that would also satisfy the old heuristic, to show the trusted primary controls
selection; wrong-primary/row and raw/decoded aliases must refuse.

Existing44 audio tests remain regression gates. Separate strict split capture
shape preserves old visual exact UID gate. Retained replay must re-invoke both
audio verifier and actual text transformer on frozen inputs, compare freshly
rederived receipts field-for-field and verify cached returned audio/timing/
provenance before build. Reuse existing locks/jobs/CAS/promotion recovery.
Default actions wait; no real/current-build/observer/renderer qualification is
implied by synthetic closed-route evidence. Composed decisions and stdlib WI
remain explicit later #144 work, not silently dropped positives.

Begin test-first issue-owned primary/profile bridge then omission workflow.
Finish with full review and required checks before moving to composition/WI.
The user-directed quota guard remains active. No checkpoint12 code exists at
this reviewed plan boundary; all previous source/checks are saved.
