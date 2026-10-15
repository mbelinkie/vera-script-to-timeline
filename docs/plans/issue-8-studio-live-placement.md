# Issue #8 — Studio live placement and integration gate

## Baseline and claim

Task `01a13277-8209-79b1-a9bc-9b42c5cc27c2`, model `gpt-6.1-sol/high`,
branch `codex/8-curated-fusion-studio`, clean starting commit
`4e31565f88e71e0c1d1cd1be5e52c34df2819347`.
The 2026-10-12 live inspection confirmed Ready, Size M, External acceptance,
dependencies #7/#34 Closed and Done, and no prior owner. The normal claim
command succeeded as the first GitHub mutation.

## Confirmed prerequisite gap

The starting tree has #34's production Studio adapter, but has no
`fusion_graphic`, `curated_fusion_graphic`, or EV24 implementation in
`contracts`, `packages/contracts/src`, or `python/vera_timeline_agent`.
The search was repeated with `--no-ignore-vcs`.
Accepted #7 commit `7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab` is not an
ancestor of this baseline; their merge base is
`0ae139a6124e2419d3ce32da70cc61b0e00b5fbe`.

Accepted sources are #12 `59838d6a8bf7fa536af3382788a947f5701a7d2c`,
#3 `cc39f29`, and #7 `7cb942e`. Their acceptance is recorded on the
corresponding GitHub issues. #34's preservation is `2586dde`, published by
PR #152. #17's guide and exact source pins were read from accepted commit
`b818c196ddb0ab3cee78f401ca158c3089e8b7c8` without merging its branch.

## Proposed separately approved integration note

Producer approved this integration note in this task on 2026-10-12 with
`Approved`. Before implementation, integrate the already accepted
#12 registration/package, #3 capability seam, and #7 contract/compiler changes
onto this baseline, retaining all unrelated later main changes. Do not replace
whole modern files with older branch versions or import unaccepted work.

This adds the previously approved v1 curated source/event variants, resolved
graphics dependency and report fields to four v1 schemas: ScriptDocument,
CompilerDependencies, TimelineManifest and BuildReport. It requires updating
their derived TypeScript and Python generated output using the locked
generator. Current main does not contain these accepted additions, so this
would change frozen surfaces relative to the assigned baseline. There is no
new semantic design, migration, timing rule or badge capability in this note.
The approved #7 compatibility effect remains: exhaustive old consumers must
handle or visibly reject the added variants; non-graphics output must stay
byte-identical. Preserve modern v2 schemas and consumers, all existing
fixtures/goldens/accepted tests, and locks. Add the accepted dependency tests
and data without editing their accepted contents. Any integration conflict
requiring a new product decision or accepted-test change stops for direction.

Acceptance of this integration requires the exact accepted dependency
inventories, byte-identical #7 goldens, current generated output, old-output
regressions and the current verification-policy gate. Earlier dependency
passes are provenance, not qualifying evidence for this new combined tree.

Requested approval: `APPROVE #8 INTEGRATION — I approve integrating the
accepted #12/#3/#7 source changes onto 4e31565 under this note, including the
accepted v1 schema additions and regeneration, while preserving later main
changes and existing frozen fixtures, goldens and tests.`

## Bounded implementation after approval

This task owns only the package/Studio seam, issue-owned new tests and
acceptance artifacts, plus the expressly approved prerequisite integration.
Package the exact setting, atlas and provenance; map the compiled typed
snapshot to trusted controls; place exact occurrences on the configured V4
track; retain graphic-use identity; verify after save/reopen. Reject nonempty
badgeOverrideAsset before creating its occurrence. Use existing authored
auto-fill and the 48-frame entrance, 16-frame exit, elastic hold and 64-frame
minimum. No dependencies are added: existing hashing, schema, package and
Resolve APIs provide the necessary operations.

Custom badge materialization/Loader overrides remain #9/#85. Browser UI,
template redesign/conversion, HTML/OGraf, uploaded graphs, Free baking,
timing UI, existing-timeline rewrite and production-project mutation are
excluded. No additional frozen surface change is authorized by implementation.

## Checks and External acceptance

Follow docs/VERIFICATION_POLICY.md: focused/fast checks, adversarial review of
identity/hash and Resolve seams, fixes/delta checks, then qualifying final full
evidence. Check the expensive-check coordinator and competing jobs first.
Cover missing/renamed/duplicate/type-incompatible controls, missing/altered
assets, custom-badge rejection, exact range/track/use identity, persistence,
generated currentness, frozen boundaries and git diff --check.

Use disposable issue-owned Resolve projects/new timelines after establishing
a safe application baseline. Retain the actual edition/build, source and asset
hashes, semantic readback and start/duration/track before and after reopen.
Render standard auto-fill, explicit text overrides and Otis at both 64 and
120 frames. A changed value must appear only in a newly generated timeline.
Provide the exact project/timeline and artifacts in a short ordered operator
accept/fail checklist for the remaining visual judgment. External acceptance
cannot be replaced by mocks or CI; remain In review until it is retained.

## Forecast

After the first substantive source check, active implementation time cannot
be estimated reliably because accepted dependency integration is missing from
the required baseline. Reassess after that integration is approved and its
focused checks pass. Coding, heavy-check queue time, actual Resolve execution
and Producer visual-response waits will be reported separately. No tests or
Resolve operations have run in this task.

## Implementation checkpoint — 2026-10-14

The approved prerequisite integration is present. The accepted template-library
service (#20, required by #12) and registration/capability imports are preserved
in commits `9bb4f9b` and `be6831d`; the remaining #3/#7 integration is staged.
Generated output is current. The original 36 TypeScript and 12 Python focused
dependency tests pass, including the unchanged #7 goldens.

The Studio-only package preserves original canonical compiler files. Its
separately named internal Transport directory uses the existing verified-media
writer for atlas-backed seed stills. Verification derives that transport view
again from the original manifest and checks equality; it is not a replacement
compiler result, a Free graphic fallback or successful Fusion evidence.
The native adapter must additionally import the exact setting, preserve
package/provenance and composition-scoped atlas mapping, verify trusted
controls and retain stable use/graph identity after save/reopen.

The actual touched implementation boundaries are the new studio_graphics
module/CLI, new compiler-input and Python tests, and narrow integration
adaptations in current exhaustive consumers. The media reconciliation source
and its input-construction helper explicitly reject Fusion instead of reading
nonexistent media fields. No existing assertion or fixture changes.
The older graphics error class is converted to native strip-only-compatible
TypeScript. A shared immutable EV24 hash module avoids pulling file-backed
registration into the pure compiler, and both existing CLI source-inventory
receipts include it. These are compatibility repairs within the approved
integration, with unchanged accepted compiler bytes and no new schema choice.

20 new focused Python tests pass, including six real compiler/registry package
cases at 64/120 frames and negative asset/control/snapshot/transport cases.
The first fast gate found 26 native CLI failures from the older parameter
property syntax; retain that failed log, then rerun the affected CLI tests and
the fast gate after the compatibility fix. It is not accepted full evidence.
Read-only independent review and the final qualifying gate remain pending.

The installed app is now Studio 21.1.1 build 10. The accepted EV24 profile
remains Studio 21.1.0 build 14; no compatibility declaration has been relaxed.
The launch tool timed out after 60 seconds, then still reported not running.
The retained nonmutating preflight stopped before API import/project mutation:
installer receipt says 21.0.4, expected scripting README is absent, and the
bundle cannot pass the existing accepted installation check. Evidence:
out/issue8/resolve-preflight.json. No native placement/render is claimed.

Initial post-integration estimate was 3–6 active hours, medium confidence.
At this checkpoint, remaining coding/review and automated validation is about
1–3 active hours, medium confidence; the next reassessment follows independent
review and fast validation. Runtime qualification/installation resolution and
the Producer's visual response are separate, currently unbounded waits.

## Continuation decision — current Studio integration

Read-only independent implementation delta review returned GO. A seventh
acceptance case now changes exactly one field in a fresh build; the original
six compiler artifacts remain byte-identical. A second narrow review returned
GO for that matrix and the concrete operator checklist. Production source is
unchanged between those reviews. Final automated acceptance remains pending
the shared slot, currently held by #214's actual final local validation.

Accepted #109 source8ef9f864 was inspected for its injected21.1.1/10 delivery
boundary, not integrated. It does not qualify EV24 or load this candidate's
Python3.12 verifier dependencies in injectedPython3.14. Adopting it is a
distinct bounded native-integration/qualification decision outside the exact
#12/#3/#7 prerequisite note above, not permission to weaken guards or install
globally. The current runtime evidence, remaining decision and operator
boundaries are in ../verification/issue-8/runtime-assessment.md; exact ordered
External checks are in ../verification/issue-8/operator-checklist.md. Neither
document asserts that a native run happened.
