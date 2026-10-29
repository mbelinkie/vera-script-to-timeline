# CI queue service proof

The bounded live proof for [#359](https://github.com/mbelinkie/vera-script-to-timeline/issues/359)
passed on 2026-10-29. Implementation and service-boundary repairs were delivered
in PRs #360, #364 and #369. No new service or credential was needed.

## Protected serial delivery

| PR | Route | Exact candidate | Validation | Main smoke |
| --- | --- | --- | --- | --- |
| [#362](https://github.com/mbelinkie/vera-script-to-timeline/pull/362) | Docs only | [daa0062c](https://github.com/mbelinkie/vera-script-to-timeline/commit/daa0062c1720450cdbd6feb1dc0947998e863d34) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40942389967) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40942754330) |
| [#363](https://github.com/mbelinkie/vera-script-to-timeline/pull/363) | Full code gate | [ce8b5781](https://github.com/mbelinkie/vera-script-to-timeline/commit/ce8b5781d6ee8457666a22e381d7485ef43af2a3) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40943179606) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40950986881) |
| [#370](https://github.com/mbelinkie/vera-script-to-timeline/pull/370) | Repaired docs | [e695efd2](https://github.com/mbelinkie/vera-script-to-timeline/commit/e695efd20bfc3a3d55590c84883f78ff228e0796) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40953654589) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40954304129) |
| [#371](https://github.com/mbelinkie/vera-script-to-timeline/pull/371) | Waiting docs | [514947cb](https://github.com/mbelinkie/vera-script-to-timeline/commit/514947cb60a692b5726789ed8bef41e5efd00f8b) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40954709644) | [Passed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40955084722) |

The trusted completion job merged each exact passing candidate and dispatched
smoke automatically. Each following candidate was integrated with the newly
delivered main only after smoke passed. For the initial pair, completion ended
at 19:44:16 UTC, smoke started at 19:44:20 and its completion ended at 19:47:11;
the next candidate's classification started at 19:47:15. Docs used whitespace
validation without the full suite; the code candidate ran the full cloud gate.
Ordinary publication ran no additional full gate.

Main's classic protection and active ruleset required strict
`VERA queue validation`; classic protection included administrators and bound
the status to GitHub Actions (app 15368). Candidate status records identify
`github-actions[bot]` and link the exact validation run. Candidate jobs retained
read-only credentials; the separate completion job used trusted main code.

## Failure, replay and explicit recovery

PR #370's first candidate, `001bebba2c3b2c409cb6c9ef047fab3bad9726d6`,
contained one deliberate trailing-whitespace fault. Its
[validation failed](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40951892339/attempts/1),
the queue persisted a pause, and both #370 and waiting #371 remained unmerged.
One [actionable alert](https://github.com/mbelinkie/vera-script-to-timeline/issues/361#issuecomment-6508000874)
named the candidate and run. Replaying that run as
[attempt 2](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/40951892339/attempts/2)
was rejected as `identity_mismatch`; the same pause and alert were retained.

After removing the fault, an explicit
[fresh readiness command](https://github.com/mbelinkie/vera-script-to-timeline/issues/361#issuecomment-6508125965)
and [resume command](https://github.com/mbelinkie/vera-script-to-timeline/issues/361#issuecomment-6508126404)
validated only the repaired head. It merged and passed smoke before #371 was
integrated, validated, merged and smoked. Final durable state had four completed
deliveries, no active transaction, no waiting entries and no pause. Issue #359
remained open for owner-managed External acceptance throughout the proof.

## Boundaries learned

`GITHUB_TOKEN` cannot read classic administration-only protection metadata;
effective active branch rules provide the required strict/context evidence.
Bot-dispatched validation did not produce the expected `workflow_run` handoff
in this repository. A separate trusted final job now verifies completed gate
jobs directly and reconciles once. Neither path uses an AI polling loop.

This proof covers the demonstrated GitHub paths. Other failure modes, including
conflicts, main-smoke failure and interrupted side effects, retain focused test
coverage and the manual recovery procedures in [the queue guide](CI_QUEUE.md).
