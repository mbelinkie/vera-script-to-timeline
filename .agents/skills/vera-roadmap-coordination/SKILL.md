---
name: vera-roadmap-coordination
description: Coordinate VERA Script-to-Timeline work through its GitHub Project, including exact model routing, claims, escalation, review, producer acceptance, dependencies, and steward maintenance.
---

# VERA Script-to-Timeline roadmap coordination

Use the GitHub Project configured in `.github/vera-roadmap.json` as the sole live roadmap and ownership authority. The product specification, decisions, accepted plans, and historical implementation record retain durable product and acceptance truth.

## Required flow

1. Inspect the issue with `npm run roadmap -- inspect <issue>`.
2. Begin only when Status is `Ready`, dependencies are resolved, acceptance criteria are complete, and exactly one supported `model:*` plus one `effort:*` label exists.
3. Claim with the exact running profile, task identity, and dedicated branch: `npm run roadmap -- claim <issue> --model <exact-model> --effort <effort> --task <task> --branch <branch>`.
4. Keep work inside issue scope. File discoveries in Inbox and do not start them.
5. Move implementation to `In review` with actual evidence. Manual listening, visual inspection, Resolve testing, and producer judgment remain there until accepted.
6. Close only with named acceptance authority and retained evidence.

## Routing

- Luna low/medium: mechanical docs, formatting, deterministic fixture updates, small tests, renames, generated output, narrow low-risk corrections.
- Terra medium/high: bounded multi-file features, standard debugging, UI, established adapters, ordinary integration tests.
- Sol high/xhigh/max: architecture, contracts, migrations, auth/privacy, concurrency/idempotency, recovery, destructive change, cross-boundary ambiguity, and critical release decisions.

Exact matching is mandatory. If work exceeds its profile, stop, mark Blocked with `needs:model-escalation`, preserve confirmed evidence, release the claim, and recommend a new profile. The steward approves label changes before work resumes.

## Steward boundary

Stewards may refine scope, verify routing/readiness, maintain parents/dependencies, and detect stale or conflicting claims. They do not reprioritize goals, implement code, close implementation issues, or dispatch tasks. Stay quiet when no meaningful board change is needed.
