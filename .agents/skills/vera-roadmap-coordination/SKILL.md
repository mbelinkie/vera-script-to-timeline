---
name: vera-roadmap-coordination
description: Coordinate VERA Script-to-Timeline work through its GitHub Project, including exact model routing, claims, escalation, review, producer acceptance, dependencies, and steward maintenance.
---

# VERA Script-to-Timeline roadmap coordination

Use the GitHub Project configured in `.github/vera-roadmap.json` as the sole live roadmap and ownership authority. The product specification, decisions, accepted plans, and historical implementation record retain durable product and acceptance truth.

## Required flow

1. Inspect the issue with `npm run roadmap -- inspect <issue>`.
2. Record prerequisites under `## Dependencies` as one `- Blocked by #123` or `- Blocked by owner/repo#123` entry per issue, or `None`. Parent/sub-issue hierarchy does not imply ordering. Use `npm run roadmap -- ready <issue>`; it moves the issue to `Ready` only after every dependency is closed and `Done` on its own VERA roadmap.
3. Begin only when Status is `Ready`, dependencies are resolved, acceptance criteria are complete, and exactly one supported `model:*` plus one `effort:*` label exists. The claim command revalidates dependency state to catch manual board moves and races.
4. Claim with the exact running profile, task identity, and dedicated branch: `npm run roadmap -- claim <issue> --model <exact-model> --effort <effort> --task <task> --branch <branch>`.
5. Keep work inside issue scope. File discoveries in Inbox and do not start them.
6. Move implementation to `In review` with actual evidence. The Project's
   `Acceptance` field determines the closing authority: `Automated` closes on
   retained passing automated evidence, `External` closes on retained evidence
   from the required real application/service, and `Producer` remains in review
   until the producer explicitly accepts. Manual listening, visual inspection,
   and Resolve testing are External or Producer evidence according to that
   field; they are not automatically producer approvals.
7. Close only with the named acceptance authority and retained evidence.

## Producer acceptance handoff

Apply this section only when the Project `Acceptance` field is `Producer`.
Do not make a bare request for approval: supply a concise, step-by-step
checklist that the producer can execute without reconstructing the agent's
work. It must name the exact artifact, command, or application view to open;
the ordered actions; the expected result for each action; any manual judgment
that remains; and the precise response that records acceptance or reports a
failure. Include only checks relevant to the issue's acceptance criteria and
leave the issue `In review` until explicit producer acceptance.

For `Automated`, record exact commands, versions, results, and artifact hashes
as acceptance evidence; do not ask the producer to repeat deterministic checks.
For `External`, provide a concise operator checklist for the real application
or service and retain that result; ask the producer only if a product or
creative decision remains.

For design-first work, create and accept the bounded design issue before implementation. Keep implementation in `Backlog` or `Blocked` with `Blocked by` the design issue; only its accepted `Done` state unlocks `Ready`.

## Routing

- Luna low/medium: mechanical docs, formatting, deterministic fixture updates, small tests, renames, generated output, narrow low-risk corrections.
- Terra medium/high: bounded multi-file features, standard debugging, UI, established adapters, ordinary integration tests.
- Sol high/xhigh/max: architecture, contracts, migrations, auth/privacy, concurrency/idempotency, recovery, destructive change, cross-boundary ambiguity, and critical release decisions.

Exact matching is mandatory. If work exceeds its profile, stop, mark Blocked with `needs:model-escalation`, preserve confirmed evidence, release the claim, and recommend a new profile. The steward approves label changes before work resumes.

## Steward boundary

Scheduled or autonomous steward passes may refine scope, verify routing/readiness, maintain parents/dependencies, and detect stale or conflicting claims. They do not reprioritize goals, implement code, close implementation issues, or dispatch tasks. A direct user invocation of the personal `$vera-roadmap-dispatch` skill is the sole dispatch exception: it may start exactly one validated Ready issue and must not alter scheduled steward behavior or auto-chain. Stay quiet when no meaningful board change is needed.
