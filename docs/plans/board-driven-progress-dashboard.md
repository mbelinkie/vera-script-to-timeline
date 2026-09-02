# Board-driven progress dashboard — bounded tooling plan

## Outcome

Make `Open VERA Progress.command` generate an accurate, read-only view of the
live GitHub Project configured in `.github/vera-roadmap.json`, including both
completed work and the remaining board scope.

## Scope

1. Treat every Project item with exactly one `type:*` label other than
   `type:goal` as one actionable work item.
2. Derive completion, remaining scope, lifecycle counts, workstream groupings,
   priority, size, acceptance authority, and model/effort routing solely from
   the live Project response.
3. Show goal issues as contextual rollups while excluding them from completion
   and remaining-scope denominators so they do not double-count their work.
4. Link displayed work to its GitHub issue and identify board items whose
   metadata is incomplete instead of silently inventing defaults.
5. Keep the existing Finder launcher and self-contained HTML output.

## Explicit exclusions

- No changes to roadmap item status, labels, fields, priority, hierarchy, or
  issue contents beyond the lifecycle updates for this bounded issue.
- No schedule forecast, task-level percent-complete inference, or synthetic
  product-spec slices that have not been added to the Project.
- No product, Resolve, compiler, editor, API, persistence, or deployment work.
- No changes to contracts, fixtures, golden files, generated types, accepted
  tests, or research-project data.

## Contracts and fixtures

- Issue #30 supersedes the original transport recorded by this accepted plan:
  the dashboard now maps bounded direct Project V2 GraphQL pages into the same
  parser shape through the shared roadmap budget gate. It establishes no
  product contract.
- Contracts, fixtures, golden files, generated types, and lockfiles remain
  unchanged.
- No dependency is added; the implementation uses Node.js standard-library
  APIs already used by the dashboard.

## Dependencies

None

## Automated checks

1. Parse actionable work and goal rollups from representative Project items.
2. Reject duplicate issues, unsupported statuses, missing or duplicate
   `type:*`, `model:*`, or `effort:*` labels, and non-Issue content.
3. Verify `Done`, remaining, lifecycle, workstream, and metadata-coverage
   totals without counting goals twice.
4. Verify deterministic escaped HTML, issue links, and terminal summary.
5. Run the focused progress tests and the repository TypeScript check.

## Acceptance criteria

- [ ] Double-clicking `Open VERA Progress.command` regenerates and opens a
  dashboard whose completion and remaining-scope totals match the live board.
- [ ] Goal items are visible but excluded from actionable-work totals.
- [ ] Every actionable board issue appears once with its exact live status,
  routing, workstream, priority, size, and acceptance authority when present.
- [ ] Missing optional board metadata is visibly identified rather than
  replaced with invented scope or progress.
- [ ] The dashboard remains read-only, and focused automated checks pass.

## Producer acceptance

1. Double-click `Open VERA Progress.command` in the repository root.
2. Compare the displayed `Done`, `Remaining`, and per-status counts with the
   GitHub Project's non-goal issues; expect exact agreement.
3. Confirm the two current goal issues are visible in a separate Goals section
   and do not change the actionable-work denominator.
4. Open at least one issue link and confirm its status, routing, workstream,
   priority, size, and acceptance fields match the Project.
5. Reply `Accepted` if all checks pass, or report the first mismatch and its
   issue number. The issue remains `In review` until that response.
