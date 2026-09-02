# Shared roadmap read gate — bounded implementation plan

## Outcome

Route every committed repository-owned live read of the configured VERA
GitHub Project or its issues through one shared direct-GraphQL budget gate.
The roadmap CLI keeps its lifecycle behavior, and the progress dashboard keeps
its read-only board-derived output.

## Scope

1. Extract the #23 host-wide lock, direct GraphQL `rateLimit` preflight, request
   accounting, and GraphQL transport into one reusable boundary.
2. Keep every `npm run roadmap` issue, dependency, claim-history, Project
   metadata, and lifecycle read behind that boundary.
3. Replace the dashboard's hidden `gh project item-list` path with bounded,
   explicit Project V2 item pages behind the same boundary.
4. Replace the roadmap `create --parent` REST parent-ID lookup with one
   accounted, targeted GraphQL issue read.
5. Check in an inventory and an automated bypass guard covering the committed
   executable source paths.

## Explicit exclusions

- No product, compiler, editor, Resolve, API, persistence, deployment, or
  scheduler behavior.
- No GitHub account, credential, quota threshold, retry loop, cache, or
  lifecycle/routing/dependency/claim/acceptance policy change.
- No contract, fixture, golden-file, generated-type, accepted-test, or lockfile
  change.
- No dashboard scope, denominator, presentation, launcher, or mutation.

## Contracts, fixtures, and dependencies

- Product contracts, fixtures, golden files, and generated types remain
  byte-for-byte unchanged.
- No package dependency is added; the implementation uses Node.js standard
  library APIs and the existing `gh` executable.
- Canonical prerequisites are issue #23 and issue #25. Both are closed and
  `Done`; no new dependency is introduced.

## Automated checks

1. Prove an accounted read cannot execute without a direct GraphQL preflight.
2. Prove host-lock contention refuses before any GitHub request.
3. Prove exhausted primary budget, secondary throttling, and REST-derived
   pseudo-authority refuse before the target read.
4. Prove bounded multi-page Project data maps to the dashboard's existing
   parser model without changing totals or metadata.
5. Scan committed executable sources and fail when a live GitHub reader bypasses
   the shared gate or reintroduces `gh issue` / `gh project item-list`.
6. Run focused roadmap/progress tests and full `npm run validate`.

## Implementation walkthrough and retained evidence

The CLI and dashboard now enter the same lock-owning factory. Named
reservations must precede every query; direct read responses update the budget,
and failed reads invalidate outstanding work. The original host lock and its
cooldown policy are unchanged. No cache, automatic retry, account switching,
credential handling, or quota threshold was introduced.

The dashboard keeps its existing parser, model, rendering, terminal summary,
and launcher. A new adapter maps bounded Project V2 pages to that parser's
existing shape; parity tests compare the entire model and byte-identical HTML
and terminal output. The 500-item cap is unchanged. Nested metadata is checked
for completeness, and pagination must make forward progress. One dashboard
page reserves two GraphQL points, confirmed by a live response reporting
`cost: 2`. Dependency sets above 100 entries use additional guarded batches,
preserving every declared dependency without an unbounded alias query.

The optional parent ID is now read through an accounted GraphQL query before
issue creation. Creation still writes Inbox, and all lifecycle status,
claim, routing, escalation, close, and producer-acceptance behavior is retained.
The only remaining REST read is REST core quota evidence before the existing
REST issue-creation mutation; it cannot serve as GraphQL authority.

Validation completed:

- Full `rtk npm exec --yes --package=node@24.19.0 -- npm run validate` passed
  with the pinned Node 24.19.0 runtime: 92 workspace tests, 6 existing dashboard
  tests, 47 roadmap tests, and 173 Python tests. Generated-type checks, both
  language linters, and both language typechecks passed.
- `rtk npm run check:roadmap-readers` passed, reporting no ungated live reader
  across 56 committed production-source, launcher, manifest, and workflow files.
- The exact refusal-test command below passed all 6 selected tests. No fake
  transport attempted a target read after refusal; both actual CLI entry points
  are covered for shared-lock contention, primary exhaustion, and secondary
  throttling.
- Live `rtk npm run roadmap -- inspect 23` returned #23 as CLOSED/Done with
  valid/resolved dependencies and its retained claim record.
- Live `rtk npm run progress` and
  `rtk env VERA_PROGRESS_NO_OPEN=1 /bin/zsh './Open VERA Progress.command'`
  generated the same read-only dashboard path. The observed board snapshot had
  28 work items, 11 Done, 17 remaining, and 2 separate goals. Board totals may
  change independently after that snapshot.
- `rtk git diff --check` passed. Contracts, fixtures, golden files, generated
  types, existing accepted tests, product code, and lockfiles have no diff.

Finder double-click/browser appearance and comparison against the producer's
live Project view remain manual acceptance, not agent-certified completion.

## Producer acceptance

Use this issue's dedicated checkout on branch
`codex/issue-30-shared-roadmap-read-gate`; run commands at its repository root.

1. Run `rtk npm run check:roadmap-readers`; expect a passing check reporting
   no ungated live roadmap reader. The complete inventory is
   `docs/roadmap-live-read-inventory.md`.
2. Run `rtk npm run roadmap -- inspect 23`; expect issue #23, state `CLOSED`,
   Project status `Done`, valid/resolved dependencies, and its retained claim
   record. This command must not alter the issue or Project.
3. Run `rtk npm run progress -- --open` or double-click
   `Open VERA Progress.command`; confirm the self-contained dashboard opens,
   stays read-only, and its Done/Remaining/per-status totals match the live
   [Project](https://github.com/users/mbelinkie/projects/2). Goals must remain
   separate from the work-item denominator. Open one issue link and compare
   its routing and displayed metadata with the Project. This visual comparison
   and Finder launch are the remaining producer judgments.
4. Run `rtk node --test --test-name-pattern='refuse|refuses' scripts/roadmap-read-gate.test.mjs scripts/roadmap-entrypoints.test.mjs`;
   expect passing exhausted/secondary-throttle tests for both entry points.
   They assert only the direct probe executes, no target read occurs, and the
   error includes reset or Retry-After guidance. They use fake GitHub responses,
   not real exhaustion or real mutations.
5. Run `rtk npm run validate`; expect all checks to pass. Reply `Accepted #30`
   only if the command checks and live visual comparison pass; otherwise report
   the first failing step, command/error or issue-number mismatch. The issue
   stays `In review` until explicit producer acceptance.
