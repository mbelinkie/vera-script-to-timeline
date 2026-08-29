# Claude Code coordination guide

Read `AGENTS.md` and `.agents/skills/vera-roadmap-coordination/SKILL.md` before coordinating or implementing work. The GitHub Project configured in `.github/vera-roadmap.json` is authoritative for live scope, status, dependencies, ownership, priority, and model routing. Product specifications, decisions, plans, contracts, and historical acceptance records remain authoritative for their durable subjects.

Implement only one Ready issue in one dedicated `claude/<issue>-<slug>` branch/worktree. Claim only an exact model-class and effort match. File out-of-scope discoveries in Inbox without starting them. If the assigned profile is insufficient, stop before scope expansion, record evidence, request escalation, release the claim, and wait for steward relabeling.

Record prerequisites under `## Dependencies` as one `- Blocked by #123` or `- Blocked by owner/repo#123` line per issue, or `None`. Parent/sub-issue hierarchy does not imply execution order. Promote work only through `npm run roadmap -- ready <issue>`; both that command and `claim` require every dependency to be closed and `Done` on its own VERA roadmap. For design-first work, keep implementation in Backlog or Blocked until the accepted design issue is Done.

Merged or agent-complete code remains `In review` until every required automated, listening, visual, Resolve, and producer-acceptance gate passes. Never infer acceptance from an implementation report.
