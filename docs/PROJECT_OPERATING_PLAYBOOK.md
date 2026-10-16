# Project operating playbook

This is a short, reusable record of operating practices that have proved useful
in VERA. It is intentionally separate from product requirements and the live
roadmap: it describes *how to run a project safely*, not what VERA must build.

Use it when bootstrapping another project. Copy the pattern, then adapt its
names, commands, roles, and risk boundaries to that project's context.

## How this stays useful

- Add an entry only after it has been used successfully or has retained,
  reviewable evidence. Link the source issue, plan, test, or command.
- Mark an idea `Proposed`, rather than presenting it as established practice,
  until it has that evidence.
- Keep public notes free of private inputs, credentials, local paths, and
  production content.
- The roadmap steward reviews this file after meaningful milestones; the
  **VERA Engineering Lessons** task turns one-off lessons into plain-language
  explanations, while this file retains the repeatable operating pattern.

## Reusable practices

| Practice | What to carry to another project | Evidence and starting point |
| --- | --- | --- |
| Live GitHub Project as the operational source of truth | Put active scope, status, priority, dependencies, owner, routing, and acceptance authority in one Project. Keep specifications, contracts, and historical acceptance records authoritative only for their durable subjects. | [Roadmap configuration](../.github/vera-roadmap.json), [coordination skill](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| Small, testable issue contracts | Require every actionable issue to state outcome, bounded scope, acceptance criteria, exclusions, canonical `Dependencies`, one model label, and one effort label. A parent relationship explains roll-up; it never silently creates execution order. | [Issue template](../.github/ISSUE_TEMPLATE/work-item.yml), [roadmap coordination](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| Ready-and-claim gate | Promote only after a command rechecks criteria and dependencies. Let the implementation task claim itself with its real task ID and branch, preventing duplicate ownership. Use one issue, one task, and one worktree. | `npm run roadmap -- ready <issue>` and `npm run roadmap -- claim <issue> ...`; [roadmap tests](../scripts/roadmap.test.mjs) |
| Project-local agent command guard | Use a repository-owned Claude Code Bash `PreToolUse` hook to block recognized destructive Git variants and broad recursive-delete targets, while leaving ordinary Git commands and pushes available. Treat it as a narrow classifier, not a sandbox: it does not cover disabled or untrusted hooks, non-Bash tools, commands it cannot parse, or direct human shell use. | [Project hook](../.claude/settings.json), [classifier and tests](../scripts/agent-safety.mjs), [Claude Code hook reference](https://code.claude.com/docs/en/hooks) |
| Explicit acceptance authority | Classify each slice as `Automated`, `External`, or `Producer`. Automated work closes on a merged PR with green CI. External work records one real-application result. Producer review is only for taste and product judgment, never for technical approvals. | [Repository instructions](../AGENTS.md), [coordination skill](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| Exact model and effort routing | Give each ready issue exactly one `model:*` and one `effort:*` label. Prefer the least powerful profile that safely fits; escalate only with concrete evidence and a preserved boundary. | [Routing rules](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| GraphQL budget gate and host-wide lock | Treat GitHub GraphQL as a shared finite budget. Serialize roadmap commands, preflight their planned query cost, read the direct GraphQL budget rather than trusting a REST summary, and fail closed with reset guidance. | [Rate-limit investigation](roadmap-rate-limit-investigation.md), [lock implementation](../scripts/roadmap-lock.mjs), [budget tests](../scripts/roadmap-rate-limit.test.mjs) |
| Read-only board dashboard | Generate project progress from the live board rather than maintaining a second status spreadsheet or markdown tracker. The dashboard is safe to refresh because it never mutates the Project. | `npm run progress`; [dashboard plan](plans/board-driven-progress-dashboard.md) |
| Agent-owned technical changes | Let agents change contracts, fixtures, goldens and tests when the work needs it. Regenerate types and explain what changed, why, and what it affects in the PR description. A non-developer owner should not be asked to approve schemas. | [D-0016](../DECISIONS.md), [Repository instructions](../AGENTS.md) |
| Lightweight evidence | Use the PR as the evidence: diff, a short note on what changed and how it was tested, and the CI result. Deterministic output still has golden tests. Real-world work gets one result comment. Earlier receipt and hash-bundle practice cost more than it caught. | [Verification policy](VERIFICATION_POLICY.md), [D-0016](../DECISIONS.md) |
| Cloud CI as the full gate | Run fast checks locally and let free hosted CI (GitHub Actions on a public repo) run the full suite on every push. A green PR check is the regression gate; merge then, and fix later failures forward in new issues. Never tie up a slow owner machine with full runs. Mark slow end-to-end tests and keep new tests small so per-issue cost does not grow with the project. | [Verification policy](VERIFICATION_POLICY.md), [#184 fast-validation plan](plans/issue-184-fast-validation.md), [D-0016](../DECISIONS.md) |
| Optional per-task token accounting | Optionally record the final cumulative token total from a closed issue's claimed task. Say that cached input is included; never substitute an account-wide number or an estimate. Never let it block closure. | [Roadmap coordination](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| Astra reconsideration register | After hard work closes, capture only evidence-backed unresolved engineering risks in a short register: observed failure, precise later-review question, and retirement condition. It is a decision aid, not a shadow roadmap or automatic routing rule. | [Possible Issues for Astra](POSSIBLE_ISSUES_FOR_ASTRA.md) |
| Safe handling of real media and other sensitive inputs | Keep public issues free of private source material. Require a per-run authorization, explicit local/cloud route, retention/deletion behavior, and cost limit before sending sensitive inputs to an external service. Default to local-only when no such authorization exists. | [#42 capability boundary](https://github.com/mbelinkie/vera-script-to-timeline/issues/42), [#49 validation boundary](https://github.com/mbelinkie/vera-script-to-timeline/issues/49) |

## Recovery and backup posture

VERA has proven safeguards around immutable revisions, checkpoint/build
snapshots, and non-destructive restore. Those are useful recovery patterns:
never silently overwrite a prior accepted input, and make restoration create a
new history entry rather than erase history.

An automated repository or production-data backup system is **not yet an
implemented VERA practice**. Do not describe it as one when copying this
playbook. Add it here only after its backup location, encryption/access model,
restore test, retention policy, and ownership have been explicitly designed
and tested.

Sources: [product specification](Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md), [web capture recovery boundary](investigations/issue-27-webpage-capture-contract.md).

## Fast bootstrap for another project

1. Create a GitHub Project with Status, Priority, Size, Workstream, and
   Acceptance fields. Decide which artifact is authoritative for live work and
   which documents remain durable authority.
2. Add a short project instruction file plus an issue template that enforces
   bounded scope, canonical dependencies, routing, and acceptance. State
   plainly which decisions the owner wants to make (product, taste, money)
   and that agents make all technical ones.
3. Implement a small roadmap CLI that inspects, promotes, claims, and reviews
   items. Put a shared lock and rate-limit preflight around all its networked
   operations before relying on automation.
4. Add a read-only progress view generated from the Project. Do not create a
   competing hand-maintained status document.
5. Set up a lessons channel and review this playbook at milestones. Promote only
   practices that have evidence, and label any remaining design as proposed.
