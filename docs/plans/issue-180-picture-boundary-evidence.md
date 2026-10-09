# Issue #180 — verified picture boundaries and explicit audible ends

Owner: `gpt-6.1-sol/high`, chat `01a121fe-5af9-7e11-a9b6-cebf5627e71b`,
branch `codex/issue-180-picture-boundary-evidence`. Acceptance: Automated.
Dependency: `Blocked by #179`, confirmed Closed and Done before claim.

Authority: Producer accepted the #179 design AND CN-179 at
`03f1d333b85cceacd89be85a27723783c84ed310`; closure evidence is
https://github.com/mbelinkie/vera-script-to-timeline/issues/179#issuecomment-6087100716.
This branch fast-forwarded to that commit and integrated standing-policy commit
`24141d6977c5171439c1131187593dd0f0999816` as `e0aef5e`.

## Bounded scope and frozen boundary

Implement only accepted design §§3–6: separate versioned evidence, per-row XOR,
whole-envelope validation, required exact edges, explicit after anchors, shared
compiler/media-needs planning, authoring validation/edit/projection consumers.
CN-179 authorizes additive changes to the four named v2 schemas, generation
selection, TypeScript/Python generated surfaces, and new issue-owned synthetic
fixtures/goldens under `tests/data/authoring_v2/issue_180/`. Existing fixtures,
goldens, accepted tests, v1 schemas/types, and Python provider adapter stay frozen.
Before anchors retain onset semantics; after anchors require evidenced ends.
Older closed-schema clients must upgrade before reading new capability.

No dependency added: installed schema tooling, Vitest and BigInt arithmetic
suffice. No UI, persistence/migration, real-media preparation/review, synthesis,
provider qualification, private-source publication, native/Resolve operation,
retiming, #145 proof amendment, #148 ownership or successor dispatch.

## Checks and automated acceptance

Test-first sparse onsets, end-only/empty evidence, beta pause and final gamma
tail, same-token edge ordering, exact quantization/deltas/narration samples,
shared needs ranges, receipt assembly self-check, identity/currentness/schema/
UTF-16/quote/time/conflict refusals, frozen adjacency media relations, overlays,
supporting points and edge-preserving command variants. Add deterministic byte
goldens at 25 and 24000/1001 fps without replacing any accepted file.

Run existing provider/v1/#144/#173 regressions, generated-currentness and full
locked-toolchain `VITEST_MAX_WORKERS=1 npm run validate`, plus frozen inventory
audit and `git diff --check`. Retain exact tested/delivered revision, commands,
results and source/tool/profile/input/output hashes. Synthetic receipts prove
attestation consistency only; no acoustic or actual delivery qualification.
Record review, then self-close only after every criterion and required gate
passes; re-inspect Closed and Done. No Producer reapproval is required.

## Forecast

Initial inspection: 3–5 hours remaining active work, medium confidence.
Main uncertainty: cross-consumer compatibility, provisional until sparse-input
and authoring-edge tests pass. Reassess at that checkpoint and full validation.
External/approval waiting is outside active-work estimates.

Validation checkpoint: implementation/review and focused tests are complete.
The first full gate failed only on six existing #144 CLI 5-second timeouts;
all 82 new TS cases passed. Retry the unchanged gate. Remaining active work
is about 15–25 minutes for evidence/closure; full validation waiting may take
50–70 minutes based on #173's retained 52-minute run. Medium confidence until
the unchanged timeout-sensitive tests pass. No scope or routing change.

Second gate checkpoint: twelve existing CLI cases exceeded unchanged deadlines;
all 82 new cases passed again. Focused cache and application-policy probes did
not reliably resolve the timing failure, and full-gate settings remain unchanged.
The runtime investigation is retained in the issue's verification directory.
Python lint/types pass; its 394-case suite continues independently. Full
Automated acceptance is blocked on a passing unchanged gate with sufficient
host capacity. Keep the implementation claim and Sol/high route; this is not
a model escalation. External waiting duration is now uncertain.

Blocked handoff: a third complete invocation with recorded Node compilation
cache failed twelve existing CLI deadlines again (390/402 contract tests passed;
all 82 new cases passed). The separate Python run was intentionally stopped
with SIGTERM to consolidate into that authoritative gate; it is not a passing
full suite. Final focused new/authoring/schema/compiler evidence and all failed
gate logs are retained. No further source change or deadline relaxation is
authorized by this slice. #180 stays Open/Blocked with its active claim pending
stable capacity and one complete passing gate; no Automated acceptance or
closure, producer reapproval, model escalation or successor dispatch.
