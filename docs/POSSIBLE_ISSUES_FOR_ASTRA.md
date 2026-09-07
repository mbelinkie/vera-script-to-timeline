# Possible Issues for Astra

This is a short, evidence-backed reconsideration register for unusually hard
engineering questions that may merit a later Astra review. It is **not** a
roadmap, authorization to start work, model-routing override, or a list of
features to build. Each entry remains only while its evidence shows a material
unresolved risk; a later accepted result should resolve, revise, or remove it.

## How to use this register

- Add an entry only after a completed issue's retained evidence exposes a
  bounded failure, unresolved safety gate, or cross-boundary design question.
- State the observed evidence, the precise question for Astra, and the
  condition that would retire the entry. Do not write “use Astra” as a remedy
  without a falsifiable question.
- Keep sensitive source media, transcripts, paths, credentials, and private
  evidence out of this public repository. Link only public/safe issue records.
- A future Producer-directed Astra pass may investigate an entry. It must still
  use its own bounded issue, routing, privacy, contract-change, and acceptance
  process.

## Current candidates

| Candidate | Why it is shaky now | Useful Astra question | Retirement condition | Evidence |
| --- | --- | --- | --- | --- |
| Local word timing with safe rejection | #51 found **no adequate selection**. On the frozen 80-word set, the best tested profiles missed the timing gates; calibration could not both reject false-confident boundaries and retain enough words. Apple Silicon remains unmeasured. | What recognition/alignment architecture and calibration method can provide editing-safe word boundaries without reference-text leakage or false confidence? Is the current two-stage boundary the right one? | A licensed, reproducible profile meets the approved recognition, timing, rejection, multilingual, and Apple Silicon evidence gates. | [#51](https://github.com/mbelinkie/vera-script-to-timeline/issues/51), follow-up [#63](https://github.com/mbelinkie/vera-script-to-timeline/issues/63) |
| Shared transcription/timing contract before production integration | #45 cannot safely turn the experiments into product adapters until both products agree on provenance, normalization, nullable/unaligned timing, rejection behavior, and conformance fixtures. A bad contract here would lock in unsafe edit semantics. | What is the smallest stable cross-product contract that keeps recognition, alignment, take logic, evidence identity, and provider replacement independently testable? | A Producer-accepted contract-design issue defines the ports, artifact identity, migration/compatibility boundary, and shared conformance cases; both adapters then pass it. | [#45](https://github.com/mbelinkie/vera-script-to-timeline/issues/45), [#51](https://github.com/mbelinkie/vera-script-to-timeline/issues/51), [#53](https://github.com/mbelinkie/vera-script-to-timeline/issues/53) |
| Ordered visual inpoints, cutaway hierarchy, and source trimming | The prototype exposed a deceptively deep semantic problem: sequential slots, indented cutaways, return-to-parent anchors, script-derived coverage, media-derived complete-clip cuts, and source trims must remain deterministic through edits. This crosses contracts, compiler behavior, and UI projection. | What invariant-based model handles reorder, deletion, narration edits, nested/returned cutaways, source-duration overflow, and uncertain media-timed transitions without silently changing editorial meaning? | The contract-design issue has an accepted state model, compatibility/migration plan, negative cases, and conformance fixtures before implementation begins. | [#56](https://github.com/mbelinkie/vera-script-to-timeline/issues/56), [#14](https://github.com/mbelinkie/vera-script-to-timeline/issues/14) |
| Browser authoring state/permission model | The original #14 proved too broad for one design slice and is now a six-slice program. The risk is not visual polish: it is accurately representing Phase 2 writing, Phase 3 roles/history/comments, local runtime states, and cross-product authorization without accidentally promising a capability. | Can the scenario, role, runtime, and authorization matrices be reduced to a coherent state model that preserves product-phase boundaries and yields implementable acceptance tests? | The #57 child program has an accepted traceability matrix with no unresolved role/runtime contradiction, and any remaining semantic gaps are separate bounded issues. | [#57](https://github.com/mbelinkie/vera-script-to-timeline/issues/57), [#14](https://github.com/mbelinkie/vera-script-to-timeline/issues/14), [#62](https://github.com/mbelinkie/vera-script-to-timeline/issues/62) |
| Production periodic webpage capture and recovery | The immutable local-revision spike and trust contract are useful, but production periodic recapture remains deliberately deferred. Scheduling, leases, retention, access revocation, side-effect containment, and recovery must work together without replacing a prior accepted revision. | What is the minimum production architecture that makes periodic capture safe, idempotent, observable, and recoverable while preserving immutable revisions and independent authorization? | A separately accepted production design and implementation prove periodic capture, lease/retry behavior, retention, authorization loss, and non-destructive recovery. | [#27](https://github.com/mbelinkie/vera-script-to-timeline/issues/27), [#28](https://github.com/mbelinkie/vera-script-to-timeline/issues/28), [#38](https://github.com/mbelinkie/vera-script-to-timeline/issues/38) |

## Explicit non-candidates today

- GitHub roadmap rate limiting is not listed: #18, #23, and #30 produced a
  shared budget gate, lock, preflight, and recovery evidence. Reopen it only
  if retained evidence shows that control failing under normal use.
- Fusion template design is not listed: its current limitation is deliberate
  human template design, not an unbounded engineering failure for a later model
  to solve.
