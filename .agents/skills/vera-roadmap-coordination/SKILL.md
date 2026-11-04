---
name: vera-roadmap-coordination
description: Board mechanics for VERA work on its GitHub Projects: dependencies, routing labels, claims, Ready and closing.
---

# VERA roadmap coordination

The GitHub Project in `.github/vera-roadmap.json` is the live roadmap. How work
is done is in `AGENTS.md`; this covers only the board.

- **Inspect:** `npm run roadmap -- inspect <issue>`.
- **Dependencies:** under `## Dependencies`, one `- Blocked by #123` (or
  `owner/repo#123`) line per prerequisite, or `None`. Parent/sub-issue links
  don't imply order.
- **Ready:** `npm run roadmap -- ready <issue>` once every dependency is
  closed. Ready issues need an `Acceptance criteria` list and exactly one
  `model:*` and one `effort:*` label.
- **Routing labels** pick the cheapest model that fits and tell Matthew
  roughly how long it will take. Luna low/medium: mechanical docs, fixtures,
  small tests, narrow fixes. Terra medium/high: bounded features, debugging,
  UI, adapters. Sol high/xhigh/max: architecture, contracts, migrations,
  privacy, concurrency, destructive change. If the labels are clearly wrong,
  fix them with `gh issue edit` and carry on; they never block a claim.
- **Claim:** `npm run roadmap -- claim <issue> --branch <branch>` (from Inbox,
  Backlog or Ready; refuses only open dependencies or an existing claim).
- **Close:** `Closes #<issue>` in the PR closes it on merge (the Project moves
  closed items to Done). For a real-application or Producer issue, use
  `npm run roadmap -- complete <issue> --accepted-by External|Producer
  --evidence <link>` (`review` instead of `complete` to leave it In review).
- Out-of-scope discoveries go to Inbox as new issues.
