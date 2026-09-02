# Repository-owned live roadmap read inventory

This is the checked-in inventory for GitHub issue #30. It covers every
committed executable entry point that reads the configured VERA GitHub Project
or its issues. All entries use `scripts/roadmap-graphql-gate.mjs`, which owns
the host-wide lock, direct GraphQL `rateLimit` authority, named request
accounting, and the only `gh` process boundary in production scripts.

| Entry point | Live reads | Bound | Shared-gate accounting |
| --- | --- | --- | --- |
| `npm run roadmap -- rate-limit` | Direct GraphQL `rateLimit` fields | One query | Direct authority/report; REST `/rate_limit` is never accepted as GraphQL evidence |
| `npm run roadmap` issue commands: `inspect`, `ready`, `claim`, `block`, `escalate`, `review`, `complete` | One issue plus its matching configured Project item/fields and newest 100 comments; declared dependency issues in bounded alias batches; older comment pages only while no claim marker is found | Issue Project items: 100; labels: 100; field values: 30; comments: 100 per backward page; dependencies: exactly those declared in `## Dependencies`, up to 100 per batch | `issueProjectSnapshot`, optional `dependencyBatch`, and guarded `issueCommentPage`; lifecycle mutations receive a separate reservation |
| `npm run roadmap -- create` | Configured Project metadata; optional parent issue ID | One configured Project; exactly one optional parent issue | `projectMetadata` and optional `parentIssueSnapshot`; issue creation remains an explicit REST mutation, followed by reserved GraphQL mutations |
| `npm run progress` | Configured Project V2 items, issue labels, and displayed single-select fields | 100 items per forward page, 500 items total (the prior limit), 100 labels and 100 field values per item; incomplete metadata connections fail closed | One `projectItemsPage` reservation (one request, two points) and direct preflight before every page |
| `npm run progress -- --open` | Same as `npm run progress` | Same | Same; browser opening occurs only after the read and HTML write finish |
| `Open VERA Progress.command` | Launches `npm run progress -- --open`; it performs no GitHub read itself | Same | Same shared dashboard path |

The gate permits one special REST read only for REST core budget evidence before
an explicit REST mutation. It rejects general REST reads, so issue or Project
data cannot silently use REST or REST-derived GraphQL quota evidence. It adds
no retries and retains no account, credential, or raw response metadata.

The factory holds the unchanged #23 lock throughout the operation, invalidates
the reader before release, and exposes no raw transport. A reservation checks
all outstanding work against fresh direct `rateLimit` evidence. Each target
read updates the remaining budget from its own direct response; any failure
invalidates outstanding reservations. Reads cannot use mutation reservations
or invoke mutation documents. The dashboard's 201 possible connection requests
(one item connection plus up to 100 label and 100 field-value connections)
budget two points under GitHub's documented connection-cost calculation;
HTTP-request counts alone are not GraphQL point costs. See
[GitHub's cost calculation](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api#predicting-the-point-value-of-a-query).

## Bypass check

Run:

```sh
npm run check:roadmap-readers
```

The check scans committed JavaScript/TypeScript/Python/shell sources, launchers,
package manifests, and YAML workflows. It fails if any production path
launches `gh` outside the gate, uses a direct GitHub GraphQL endpoint, or
reintroduces hidden `gh issue` / `gh project item-list` readers. The behavioral
suite also proves that an unreserved query, primary exhaustion, secondary
throttle, REST-shaped pseudo-authority, and lock contention all stop before the
protected target read.

Tests use isolated fake `gh` transports and lock paths; they do not consume
live quota or mutate issues. Documentation and skills instruct operators to
use the audited npm entry points and are not additional executable readers.
The shared gate itself is the sole reviewed transport allowlist entry; changing
it requires its behavioral tests as well as the inventory check.
