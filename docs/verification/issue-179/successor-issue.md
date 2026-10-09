## Outcome

Implement verified picture-boundary evidence and explicit audible-end anchors
from the Producer-accepted #179 design and CN-179. This is one bounded pure
Contracts and Compiler package. Tentative routing: model:sol / effort:high;
Size M; Priority P2; Acceptance Automated. Inbox only; no dispatch authority.

## Scope

Implement §§3–6 of `docs/plans/issue-179-cut-point-timing.md`: separate versioned
boundary evidence, strict per-row input selection/currentness, operation-specific
required observations, explicit before/after edges, compiler/media-needs shared
resolution, authoring command/projection edge consumers, schema/generated types
and issue-owned synthetic tests/goldens. Preserve accepted complete maps and
byte-identical legacy v1/v2 outputs. No new dependency required.

## Acceptance criteria

- [ ] Producer explicitly accepts the exact #179 design AND CN-179 before readiness; pin that review commit and approval.
- [ ] Valid sparse required marks resolve picture/needs independently of unrelated missing words; each missing required onset/end explicitly blocks with no fallback or invented acoustic evidence.
- [ ] Exact beta pause and final-word tail examples preserve authored before-next-word versus audible-end semantics, narration samples, rational quantization/deltas, parent continuity and same-token edge ordering.
- [ ] Identity, receipt/source/audio/currentness, duplicate/wrong UTF-16 token/quote, unsafe time and conflicting capability refusals match the design. Adjacent-word gap claims require adjacency in frozen tokens.
- [ ] New schema/type/currentness and byte-repeat goldens cover §§6.2's matrix; existing provider/v1/#144/#173 regressions and the full locked-toolchain `VITEST_MAX_WORKERS=1 npm run validate` pass without weakened gates.
- [ ] Retain exact source/tool/profile/input/output hashes and frozen-boundary evidence. Synthetic attestation tests do not qualify actual audio review or delivery.

## Dependencies

- Blocked by #179

## Dependency rationale

#179 supplies the sole proposed schema/semantic change authority. Its Closed AND
Done state after exact Producer design/change-note acceptance is necessary but
does not itself deliver this runtime behavior. No new execution dependency is
imposed on #148/#145, and no unrelated backend ticket blocks design review.

## Exclusions

No actual schema/compiler implementation until dispatched separately. No real
media preparation/review application, provider qualification/synthesis, private
source publication, UI, persistence/migration, native/Resolve operations,
retiming or #145 proof-version changes. #148 remains private preparation;
#145 remains v1/25-fps proof. Do not auto-promote or start any successor.

## Unresolved decisions and readiness

Producer must accept #179 and CN-179; if that review changes the selected design,
update this placeholder before promotion. Steward must pin authority, confirm
bounded Size M scope, exact routing/acceptance and dependency closure. Existing
authorized preparation callers own receipt byte verification; this pure package
does not qualify their real inputs.

## Duplicate audit

Open/closed title and semantic search on 2026-10-09 found no existing owner for
this bounded outcome. #173 supplies accepted full-map compiler behavior; #179
owns design; #89 owns secondary timing UI/reconciliation; #168 owns shared
recognizer/aligner port contracts; #148 owns private preparation. None owns this pure sparse
boundary implementation and explicit after-edge change.
