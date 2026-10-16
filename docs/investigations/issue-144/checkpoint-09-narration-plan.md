# Checkpoint 9 plan: whole-row narration handoff

Resume from checkpoint 8 (`97c50a0`). This is the next bounded implementation
segment of #144, not a separate issue or full omission acceptance.

## Scope and boundary

Add one issue-owned Python function that connects an already validated revised
row to the unchanged accepted NarrationService and dependency projection. It
accepts a PreparedBuild baseline, a literal revised-document file and an
explicitly injected NarrationService. It has no default provider, CLI generation
action, cloud call or native action. This first segment accepts only the
`synthetic_injected` lane and an explicitly synthetic provider/profile.

The function is a building block for the later accepted-omission decision path.
It does not establish audible absence or authorize an arbitrary file rewrite as
a round-trip decision. The existing ProofSession remains visual-only until the
omission proposal/decision and composed canonical revision are integrated.

Before any generation, verify the baseline's literal inputs, implementation,
ready narration bytes and text/revision bindings. Validate the revised document
with the actual accepted script validator. Require the same project/draft, row
identity/order and narration inventory; one changed narration text with an
increased row version at most. Unchanged text requires unchanged row version.
Visual-only changes therefore preserve narration and call no provider.

Call `NarrationService.process_block` only for the changed complete row. Read
and verify its immutable cache asset/timing/audio, project it with the accepted
`narration_dependency_from_asset`, and replace only that row's dependency.
Refuse failed placeholder output, missing word marks, stale text/revision,
identical old recording bytes or missing provenance. Require synthetic labeling.
Return projected dependencies plus verified generated asset locations and
hash-bound provenance; do not write a ScriptDocument or impose a Python
canonical hash on it. Actual compiler serialization/compilation remains the
authority for the later composed decision and fresh build.

Implementation precision from the package check: the accepted projection's
cache-relative `v1/assets/...` audio locator is separate from the import package's
required `Media/` destination. Give the new dependency a stable
`Media/Narration/<assetId>.wav` delivery locator while retaining the verified
cache origin separately. Do not alter the accepted projection or old assets.
An optional explicit enclosing proof root accommodates archived revision build
directories sharing this isolated cache; both the prior build and cache must
stay within that owner directory. Guard existing cache lock links before use.

Recheck input/source/media and revised-file hashes after generation. Retry of
the same row revision uses the accepted immutable narration cache, creating no
second synthesis. A subsequent wording edit has a different complete request
identity. Historical bytes remain untouched. No splice, fragment reuse, old
mark subtraction or fixed preselected replacement WAV is permitted.

## Ownership and dependencies

New `python/vera_timeline_agent/roundtrip_narration.py`, new
`tests/test_issue144_row_narration.py`, issue-owned evidence/plan updates, and
`roundtrip_build.py` source hash inventory only. No changes to accepted narration,
compiler, Studio/jobs, contracts, fixtures, generated types, golden files,
accepted tests or lockfiles. No new dependency: reuse NarrationService,
NarrationCache, Normalizer, accepted projection, validator/compiler and stdlib.

Pin the handoff and accepted narration/validator source bytes in the proof
source inventory. This invalidates older code-bound test proof receipts rather
than attempting a migration; there is no accepted real #144 baseline yet.

## Checks and review

Test first with an injected provider whose complete revised text determines
both newly generated PCM and word marks. Use actual NarrationService/cache,
normalizer, dependency projection, script validator and compiler/package stages.
Add an unchanged following row with a visual: audio/text/revision/timing and
source handles remain identical; block-local geometry is unchanged while its
absolute start shifts by the preceding row's new duration. Verify changed-row
anchors follow new pacing rather than old duration arithmetic.

Checks: complete-row request and new bytes/marks; identical replay without a
second provider call; later edit generates again; visual-only edits call no
provider; failed generation, stale same-version wording and invalid revision
refuse; UTF-16 surrogate offsets; tampered cache or changed input refuses.
Then focused narration/compiler/build regressions, lint/typecheck, protected
boundary diff and git diff --check. Full validation is retained at the next
integrated checkpoint. Claude reviews this plan before code and the completed
segment before proceeding. Full material/results go on #144.

## Acceptance and remaining work

Acceptance is Automated; no deterministic producer retest is requested. This
segment proves the generation handoff, not audible omission, live capture or a
complete rebuilt native timeline. Complete omission evidence/composition, real
WI boundary, three-case integration and runbook remain. #145 owns authorized
real synthesis/preparation, selected-build observer qualification and real run.
Authoring lock/reshoot/pickup UI #153, music and production preservation #104
remain excluded.
