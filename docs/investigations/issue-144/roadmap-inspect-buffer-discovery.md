# Out-of-scope roadmap tooling discovery

Filed https://github.com/mbelinkie/vera-script-to-timeline/issues/154 as Inbox / S / Automated. No implementation or dispatch.

## Outcome

Keep the VERA roadmap CLI usable when retained issue-review comments make the
GitHub response exceed the child-process stdout buffer. This is an Inbox tooling
follow-up discovered during #144; no implementation or dispatch is authorized.
Tentative routing: model:luna / effort:medium; Size S; Acceptance Automated.

## Evidence

On #144 at d5aea3a, pinned Node24.19.0 `npm run roadmap -- inspect 144` exits1
and prints a truncated GraphQL response instead of the inspection. Reproducing
`ISSUE_PROJECT_QUERY` through the current `spawnSync("gh", args)` options yielded
`status:null`, `signal:SIGTERM`, `errorCode:ENOBUFS`, `stdoutBytes:1114112`,
`stderrBytes:0`. `scripts/roadmap.mjs:runGhResult` does not set `maxBuffer`, while
the query requests100 complete comment bodies. Full source/review retention on
#144 legitimately makes this response large. A smaller read-only GraphQL query
confirmed the issue remains Open / In progress / Automated.

## Scope

- Bound the GitHub response transport or page size so large review histories
  remain inspectable, with an explicit size/failure policy rather than an
  unlimited buffer.
- Preserve complete claim-history discovery, dependency/status checks, rate
  budget/locks and command semantics.
- Report process-size errors clearly without dumping a megabyte of partial JSON.
- Add issue-owned tests for a response larger than the old default and explicit
  overflow handling. Do not edit accepted fixtures or live claims as a test.

## Acceptance criteria

- [ ] A representative large-history issue is inspected successfully with the
  correct issue, claim, labels, project status and acceptance authority.
- [ ] Synthetic transport tests cover >1MiB successful response and the retained
  bounded-overflow failure; invalid JSON never becomes partial state.
- [ ] Claim pagination, dependencies, rate-limit/lock and existing roadmap tests
  still pass. No status/claim/dependency mutation is used for read-only validation.
- [ ] Relevant checks and git diff --check pass, with exact evidence retained.

## Dependencies

None

## Exclusions

No #144 harness change, dispatch, reprioritization, claim release, broader
GitHub client rewrite, new dependency or frozen-boundary change.

## Duplicate audit

Searched all148 open/closed issue bodies plus fresh repository issue searches
for ENOBUFS, stdout buffer and large comments. Hits were #144 and unrelated
browser-design tickets; no existing owner covers this transport-size failure.
