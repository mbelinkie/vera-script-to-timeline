# #167 — runtime ownership audit and handoff

Read-only audit on 2026-10-15, before any handoff issue creation. Searches covered
open **and closed** GitHub issues with `semantic highlight`, `highlight target`,
`graphic cue`, `cue integration`. Results included #167/#219/#24/#147 and
#218/#166/#127/#144, plus unrelated prototype/workstream hits #61/#45/#116/#33.
No existing owner covers production cue compilation plus Studio execution.

| Existing owner | Live state / bounded scope | Gap |
| --- | --- | --- |
| #167 | In progress, Producer; contract design only | No runtime scope retained here |
| #8 | Open/In review, External; basic EV24 lower-third placement, exact range/use/value save/reopen | Unaccepted; excludes semantic cue compiler/aggregate schedules |
| #218 | Open/Inbox; approved provenance core realization, dependencies #166/#7/#20 | Not started; excludes cues, UI and Resolve. Reuse, do not reimplement |
| #219 | Closed/Done; accepted exact synthetic Table probe | Probe is not production compiler/runtime/registered package |
| #9 | Blocked; authoring picker/form; #7/#8/#67/#85 prerequisites | Owns UI, not runtime integration |
| #99 | Inbox, Producer; approved starter package registration/availability | Owns future Table package/revision/profile registration needed by this design; exact Table inclusion must be confirmed during refinement |

The runtime handoff must canonically depend on #8 **and** #167 **and** #218.
It also consumes a registered Table package/profile, so #99 is an explicit
dependency rather than an assumed private-file registration. #24/#7/#20/#166/
#219 are covered transitively. If the steward later splits exact Table
registration/qualification from #99, replace that blocker only with the actual
bounded owner, retaining canonical dependencies before Ready. No implied waiver
or registration implementation in #167.

## Bounded missing owner

Retain one Inbox issue for implementation of the accepted cue contract against
the exact #219 profile, using #218 content/provenance and #8 placement. Include
typed Table applicability only after CN-167-P1 approval, deterministic cue
resolution/aggregation, package/report evidence and exact Studio verification.
Exclude UI, general registration, new templates/profiles/Free baking, native
experiments and v2 media realization. Tentative route Sol/high, Size M, P2,
Contracts and Compiler; Acceptance External with required separate Producer
contract approval. Refine/split if actual integration cannot fit that bound.

No issue is promoted, claimed or dispatched by this handoff. Runtime stays
blocked until canonical prerequisites are Closed/Done, frozen notes approved,
exact integration baseline reconciled, registered profile available and actual
qualification evidence accepted. #8 has not been accepted or waived.

Created [#220](https://github.com/mbelinkie/vera-script-to-timeline/issues/220)
once through normal `roadmap create`; readback confirmed Open/Inbox, unclaimed,
and all four canonical dependencies unresolved. Exact retained creation body:
[runtime-inbox-body.md](runtime-inbox-body.md). The normal CLI cannot set custom
fields at creation, so a single guarded metadata update reused the repository's
roadmap lock and direct GraphQL budget parser/planner (4992 points remaining,
five planned operations), setting External/P2/M/Contracts and Compiler. No
Ready promotion or claim. Subsequent normal CLI readback verifies those fields.
