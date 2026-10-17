# #166 — derived graphic provenance contract design

Status: proposed; Producer acceptance required. Design only.

## Bounded work and gates

The deliverable is [the design](../design/issue-166-derived-graphic-provenance.md),
with its field/applicability table, accepted-source mapping, synthetic examples,
failure/recovery matrix and implementation handoff. A separate
[proposed change note](issue-166-proposed-contract-change.md) describes future
wire changes for explicit Producer approval. This plan does not apply them.

No runtime, persistence, template, renderer, UI, registration, cue timing,
provider call or Resolve operation is part of this issue. No shared schema,
generated type, fixture, golden, accepted test or dependency changes. The
verification-policy edit records the Producer's 2026-10-15 review/wait rules
and preserves the existing qualified cloud policy.

Starting HEAD and origin/main were both
`22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`; clean dedicated worktree, branch
`codex/issue-166-derived-graphic-provenance`. Live inspection found Ready,
model:sol/effort:high, Acceptance Producer, complete criteria, no claim and
#24/#7/#20 all Closed/Done. The normal budget/locking CLI successfully claimed
#166 for task `01a13fa4-891a-7320-8b03-4005ee0bcb37` with gpt-6.1-sol/high.

## Verification

Use the accepted verification policy's documentation-only gate: verify exact
accepted source revisions and interface names, local/pinned reference targets,
example relationships and hash rules, frozen-boundary confinement, and
`git diff --check`. Retain a separate adversarial Claude CLI review of the
candidate revision/diff using only public/synthetic read-only inputs. Fix and
delta-review findings before final checks. Stop for a revision-specific Producer
waiver if Claude provides no usable review. No full application suite is
required because no executable/check input changes. Do not claim runtime proof.

Retain evidence and finding dispositions under `docs/verification/issue-166/`.
Keep #166 In review until explicit acceptance of the exact design and proposed
compatibility decisions, using the design's short numbered checklist.

## Dependency and ownership justification

#24 supplies D24-07; #7 supplies accepted compiler/use/hash semantics; #20
supplies project revision and package-copy semantics. No software dependencies
are added. The design names existing #64/#8/#9/#99/#167 owners and identifies
any genuinely missing implementation seam only after an open/closed issue
search. An Inbox placeholder is retained scope, never dispatch authority.
