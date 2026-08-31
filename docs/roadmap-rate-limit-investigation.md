# Roadmap GitHub API rate-limit investigation

Issue #18 is an operations slice. This note records the bounded diagnosis and
the recovery procedure without retaining credentials, account identifiers, or
raw GitHub responses.

## Reconstructed request pattern

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

## Diagnosis and failure modes

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

## Recovery procedure

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
