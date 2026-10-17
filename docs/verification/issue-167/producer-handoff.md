# #167 — Producer handoff

Reviewed design revision: `824923d14271a5dd341b0df7c6cc1f5c47014dfb`.
Baseline: `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`.
Dedicated branch: `codex/issue-167-semantic-cue-design`.

The [design](../../design/issue-167-semantic-highlight-cues.md) separates
occurrence cue intent from content/provenance, resolves timing once, and
aggregates every active target before producing the shared Table control.
Global strictly-later next-start groups and strict whole-dataset invalidation
are proposed product choices. Equal states union; contradictory base/emphasis
claims block. Existing v1 only supplies word onsets, so audible-end requests
block rather than borrowing the next word's onset. Free remains unfinished
manual work, and production qualification is separate.

1. Open design §§3–5 at the revision above. Check the sequential, grouped
   next-start, overlap, continuation/conflict and precision-failure examples.
   Accept or revise global-next semantics, equal-state union and strict timing.
   Expected: one deterministic result per example with no guessed narration.
2. Open design §§2, 6–7 and [runtime handoff](runtime-handoff.md). Accept or revise
   whole-dataset invalidation and explicit repair, the limited Table profile and
   blocked/manual outcomes. Expected: #220 stays Inbox/unclaimed, canonically
   blocked by #8/#167/#218/#99; #8 remains unaccepted and no runtime is enabled.
3. Open [CN-167-P1](../../plans/issue-167-proposed-contract-change.md). Accept or
   revise its proposed v1 Table/anchor/evidence/report/default changes. v2 is
   explicitly deferred. Design acceptance does not approve frozen changes.

Record `Accept issue #167 design at 824923d14271a5dd341b0df7c6cc1f5c47014dfb`
or `Revise issue #167 step <n>: <change>`.
Separately authorize frozen implementation only with
`Approve CN-167-P1 at 824923d14271a5dd341b0df7c6cc1f5c47014dfb`.

Evidence: [Claude review/dispositions](review-dispositions.md),
[final GO](claude-final-delta-review.md), [initial checks](candidate-checks.json)
and [final checks](final-checks.json). No executable/check input, shared schema,
generated output, fixture/golden or accepted test changed. Documentation-only
verification applies; no application suite or Resolve operation was performed.
Later evidence-only commits preserve the reviewed design/note bytes exactly.
Keep #167 In review until explicit acceptance; no self-closure, merge or dispatch.
