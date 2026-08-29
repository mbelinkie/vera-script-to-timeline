# Project progress dashboard — bounded tooling plan

## Scope

Add a lightweight, read-only project progress view that:

1. derives the eleven phases and all numbered slices from section 11 of the
   authoritative product specification;
2. overlays live status and exact model/effort routing from the GitHub Project
   configured in `.github/vera-roadmap.json`;
3. reports both strict producer-accepted completion and a clearly labeled
   weighted estimate for work that is in progress or awaiting acceptance;
4. writes one self-contained HTML dashboard under ignored `out/` output and
   prints a compact terminal summary; and
5. is available through one documented npm command.

## Explicit exclusions

- No product feature, editor, API, persistence, collaboration, deployment, or
  Resolve behavior.
- No automated claim that a slice or phase is accepted; the producer remains
  authoritative.
- No inferred task-level progress inside a slice and no schedule/date
  forecast.
- No edits to the product roadmap, current slice statuses, decisions, or
  capability evidence.
- No background server, telemetry, mutation, or generated file checked into
  source control. The command performs a read-only GitHub CLI query.

## Contracts, fixtures, and dependencies

- `/contracts`, generated contract types, `/fixtures`, accepted test data, and
  golden files remain byte-for-byte unchanged.
- The tool reads the existing specification headings and the configured GitHub
  Project's issue status and routing labels; it does not establish a new
  product contract.
- No dependency is added. The implementation uses the pinned Node.js runtime
  and standard library only, so neither lockfile should change.

## Estimate policy

The dashboard will show accepted completion separately from the playful
estimate. Estimated slice-equivalent weights are deliberately simple and
visible in the dashboard:

- `Accepted`: 100%
- `Agent complete`: 90%
- `In progress`: 50%
- `Paused`: 50%
- `Blocked`: 25%
- `Queued`: 0%

These weights are a visualization convention, not an acceptance claim or a
forecast. Phase completion is the average of its slices. A phase is accepted
only when every slice in that phase is producer-accepted.

## Automated checks

1. Parse exactly the current eleven phases and sixty slices from the
   authoritative section 11 roadmap.
2. Parse live Project statuses and exact model/effort labels, fail closed on
   missing or duplicate routing, and default slices without issues to `Queued`.
3. Verify strict and estimated totals, per-phase aggregation, HTML escaping,
   and deterministic output.
4. Include the focused tests in the top-level `npm run validate` ratchet.
5. Confirm frozen contracts, fixtures, generated types, accepted test data,
   and lockfiles have no diff.

## Producer acceptance

1. Run `npm run progress` at the repository root.
2. Open the printed `out/project-progress/index.html` path, or run
   `npm run progress -- --open` on macOS.
3. Confirm the view reports 11 phases and 60 slices, with accepted and active
   counts matching the GitHub Project at the time the command runs.
4. Toggle between the weighted estimate and accepted-only view and expand at
   least one phase.
5. Confirm the percentages feel useful as a fun project indicator while the
   producer-acceptance distinction remains unmistakable.

Producer acceptance, not this implementation report, closes this bounded
tooling addition.
