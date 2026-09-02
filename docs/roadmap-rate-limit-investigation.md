# Roadmap GitHub API rate-limit investigation

Issue #18 is an operations slice. This note records the bounded diagnosis and
the recovery procedure without retaining credentials, account identifiers, or
raw GitHub responses.

> **Issue #23 correction (2026-08-31):** the Issue #18 implementation below is
> historical evidence, not the current authority. GitHub's REST
> `/rate_limit` response proved capable of reporting a false-green GraphQL
> budget in this environment. The roadmap CLI now obtains GraphQL budget data
> only from a direct GraphQL `rateLimit` query.
>
> **Issue #30 extension (2026-09-01):** the progress dashboard and every other
> committed live roadmap reader now use the same lock, direct authority,
> reservation accounting, and bounded GraphQL transport. See
> `docs/roadmap-live-read-inventory.md`.

## Current GraphQL authority and preflight

`npm run roadmap -- rate-limit` runs a direct GraphQL query for `limit`,
`remaining`, `used`, `resetAt`, and `cost`. It does not read or fall back to
`resources.graphql` from REST `/rate_limit`. A direct probe during #23 returned
`limit: 5000`, `remaining: 3718`, `used: 1282`, `resetAt:
2026-08-31T22:32:49Z`, and `cost: 1`; after the next window reset, the command
reported the new direct window rather than carrying the earlier values.

Every networked roadmap command and progress-dashboard read first acquires the
shared host lock described below. `inspect`, `ready`, `claim`, and the other
issue commands then:

1. query direct GraphQL `rateLimit` and reserve enough points for the targeted
   issue/Project snapshot plus one possible dependency batch;
2. read the issue, routing labels, newest claim-comment page, matching Project
   item, Status, and Project field metadata in one GraphQL request;
3. batch declared dependency issue/status reads into targeted GraphQL requests
   of at most 100 aliases, guarding each additional batch;
4. page backward through claim comments only when the newest 100 comments have
   no claim marker, with a fresh direct preflight before each older page; and
5. immediately before a lifecycle mutation, query direct `rateLimit` again and
   reserve the mutation point.

The direct parser fails closed on GitHub's `RATE_LIMITED` /
`graphql_rate_limit` response. If the direct response headers expose the reset,
the error names its UTC timestamp and instructs the operator not to retry
before it. A REST-green payload is rejected because it has no direct GraphQL
`data.rateLimit` object. A direct `Retry-After` header also fails closed even
when primary GraphQL points remain, preserving the secondary-throttle guard.

## Current request accounting

The accounting table records primary GraphQL requests. Request count is not
necessarily point cost: the bounded dashboard page reserves two points for
its nested connections. Every read's returned `rateLimit` updates the budget
before another reserved request. Other bounded operations reserve one point.

| Operation | Actual transport | Planned GraphQL requests |
| --- | --- | ---: |
| Direct preflight/report | direct GraphQL query | 1 |
| Issue + matching Project V2 item/status/metadata | one targeted GraphQL query | 1 |
| Declared dependencies | one aliased GraphQL query per at most 100 dependencies | 1 per guarded batch |
| Older claim-comment page | direct GraphQL query | 1 per guarded page |
| Optional parent issue ID | one targeted GraphQL query | 1 |
| Dashboard Project V2 items | bounded direct GraphQL query, 100 items per page and 500 total | 1 per guarded page (2 points) |
| Comment + Project status + optional escalation label/close | one batched GraphQL lifecycle mutation | 1 |
| Issue creation | direct REST issue creation | 0 |
| Add a newly created issue to Project V2 | direct GraphQL mutation | 1 |
| Parent/sub-issue link (after parent lookup above) | direct GraphQL mutation | 1 |

The prior `gh issue view` call was itself GraphQL. The prior whole-board
`gh project item-list` path made an owner/field query and then one or more item
page queries. The prior `gh issue comment` path also hid an issue GraphQL read
before its comment mutation. The current explicit queries remove those hidden
requests, verify the Project ID before accepting an item, and batch lifecycle
writes without changing Ready, dependency, routing, claim, escalation, review,
or producer-acceptance rules.

## Shared serialization ownership and failure behavior

The shared gate in `scripts/roadmap-graphql-gate.mjs` owns a host-wide lock at
`$TMPDIR/vera-roadmap-github-graphql.lock`. The fixed path is shared by both
VERA roadmap repositories and is intentionally conservative across every
authenticated `gh` account on that host. The lock covers preflight, reads,
validation, and writes, so roadmap commands and dashboard reads cannot spend
the shared user quota concurrently.

The owner file stores only process ID, start time, and the Codex task ID when
available. It contains no token or account identifier. A second command fails
before any GitHub request and tells the operator to wait. Normal and handled
error exits release the lock. A dead owner is reclaimed after 15 minutes; a
live owner is never reclaimed based on age alone. A crash can therefore impose
at most that local cooldown, while an ambiguous fresh or live lock fails closed.
`VERA_ROADMAP_LOCK_PATH` exists only to isolate automated tests.

## Historical Issue #18 request pattern

The roadmap CLI uses `gh` through one synchronous wrapper in
`scripts/roadmap.mjs`. Every command first reads the issue and the entire
configured Project (two REST requests). Dependency validation adds one issue
read and one Project listing per uncached dependency roadmap. Mutating commands
then write one or more operations:

| Command | Reads before mutation | Planned writes | Budget gate |
| --- | --- | --- | ---: |
| `ready` | issue, Project, dependencies | status | 1 |
| `claim` | issue, Project, dependencies | comment, status | 2 |
| `block` | issue, Project | comment, status | 2 |
| `escalate` | issue, Project | label, comment, status | 3 |
| `review` | issue, Project | comment, status | 2 |
| `complete` | issue, Project | comment, status, close | 3 |

`project item-list --limit 500` asks `gh` to retrieve up to 500 Project items;
the command is therefore a potentially paginated REST read even though it is
one CLI invocation. The request inventory records that pagination boundary,
but the current wrapper does not retain per-page counts or response headers.
`create` performs issue creation, Project add, and status edit (3 planned
writes), with an optional sub-issue GraphQL mutation outside this bounded
budget. A dependency on another configured roadmap adds another issue read and
Project listing. The implementation has no retry loop; `spawnSync` returns the
first `gh` failure to the caller.

The live `gh api rate_limit --include` probe on 2026-08-31 reported REST core,
GraphQL, and search resource objects. Only those numeric fields are retained by
the parser. OAuth scopes, request IDs, dates, and all other headers are
discarded. The probe is intentionally exposed as a read-only command:

```sh
npm run roadmap -- rate-limit
```

## Historical Issue #18 diagnosis and failure modes

The predictable local risk is request multiplication: full Project listings
and dependency reads are repeated for each command, and a mutation consists of
several sequential writes. A low REST core budget can therefore leave a board
partially changed if checked only after the first write. The new gate probes the
budget after validation and immediately before the first write. It fails closed
when the REST core remaining count is below the command's planned writes; no
comment, label, status, or close call is attempted.

This is not evidence of a GraphQL exhaustion event. The report distinguishes
and, when present, retains only the numeric delay from `Retry-After`:

- REST core exhaustion: REST `rate_limit` data or an API rate-limit error;
- GraphQL exhaustion: a GraphQL/query-cost error or depleted GraphQL resource;
- secondary rate limiting: “secondary rate limit”, abuse-detection, or
  `Retry-After` evidence, which is not predicted by the primary counter; and
- client/tooling failure: authentication, network, `gh` installation, JSON, or
  other errors without rate-limit evidence.

No blind retry is added. A `Retry-After` response makes the mutation gate fail
closed even when the primary counters look healthy. A secondary-limit response
must be deferred until the indicated delay and then revalidated; a
client/tooling failure must be fixed or escalated before resuming.

## Historical Issue #18 recovery procedure

1. Stop mutating roadmap commands. Run `npm run roadmap -- rate-limit` and save
   only its redacted three-line report and timestamp.
2. Defer `claim`, `ready`, `block`, `escalate`, `review`, `complete`, and
   `create` until REST core has reset or the operator has confirmed enough
   budget. Do not manually repeat comments or status transitions.
3. If a command failed after a write, inspect the issue and Project once with
   `npm run roadmap -- inspect <issue>`. Treat the visible latest claim marker
   and current status as authoritative before taking any next action.
4. Resume with the original command only after the preflight passes. The gate
   runs after validation and before writes, so a refusal is non-mutating. A
   secondary-limit response requires waiting for `Retry-After` and rerunning
   the read-only inspection/rate report first.

The producer must decide whether any already-written comment or status is
acceptable; this tooling does not delete or rewrite history.
