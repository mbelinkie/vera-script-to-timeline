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
| Explicit acceptance authority | Classify each slice as `Automated`, `External`, or `Producer`. Automated work closes on retained deterministic evidence; external work retains real application/service evidence; producer review is reserved for choices that truly require it. | [Repository instructions](../AGENTS.md), [coordination skill](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| Exact model and effort routing | Give each ready issue exactly one `model:*` and one `effort:*` label. Prefer the least powerful profile that safely fits; escalate only with concrete evidence and a preserved boundary. | [Routing rules](../.agents/skills/vera-roadmap-coordination/SKILL.md) |
| GraphQL budget gate and host-wide lock | Treat GitHub GraphQL as a shared finite budget. Serialize roadmap commands, preflight their planned query cost, read the direct GraphQL budget rather than trusting a REST summary, and fail closed with reset guidance. | [Rate-limit investigation](roadmap-rate-limit-investigation.md), [lock implementation](../scripts/roadmap-lock.mjs), [budget tests](../scripts/roadmap-rate-limit.test.mjs) |
| Read-only board dashboard | Generate project progress from the live board rather than maintaining a second status spreadsheet or markdown tracker. The dashboard is safe to refresh because it never mutates the Project. | `npm run progress`; [dashboard plan](plans/board-driven-progress-dashboard.md) |
| Frozen-boundary changes | Before changing a shared contract, fixture, golden, or accepted test, require a concise approved note: change, reason, compatibility, generated types, migration, and acceptance impact. | [Repository guardrail](../AGENTS.md), [#37 contract-change note](plans/issue-37-prompter-contract-change-note.md) |
| Retained, reproducible evidence | Make deterministic work prove itself with exact commands, versions, hashes, and repeated byte-identical outputs. Make real-world work retain a non-identifying result summary and the relevant authorization/policy record. | [#37 note](plans/issue-37-prompter-contract-change-note.md), [#49 real-media validation](https://github.com/mbelinkie/vera-script-to-timeline/issues/49) |
| Per-task token accounting | After an issue is closed, record the final cumulative token total from its claimed Codex task's local session record. Say that cached input is included; never substitute an account-wide number, an estimate, or the steward's own closure task. If the task record is missing or ambiguous, leave the metric absent. | [Roadmap coordination](../.agents/skills/vera-roadmap-coordination/SKILL.md), [#37 recorded example](https://github.com/mbelinkie/vera-script-to-timeline/issues/37#issuecomment-5540168417) |
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
   bounded scope, canonical dependencies, exact routing, and acceptance.
3. Implement a small roadmap CLI that inspects, promotes, claims, and reviews
   items. Put a shared lock and rate-limit preflight around all its networked
   operations before relying on automation.
4. Add a read-only progress view generated from the Project. Do not create a
   competing hand-maintained status document.
5. Set up a lessons channel and review this playbook at milestones. Promote only
   practices that have evidence, and label any remaining design as proposed.
