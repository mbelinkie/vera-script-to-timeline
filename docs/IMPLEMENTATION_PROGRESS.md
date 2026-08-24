# Implementation Progress

This document is the orchestration record for implementing
`Script-to-Timeline Product Spec - Fable Rev2.md`. It tracks slice ownership,
contract boundaries, verification, producer acceptance, decisions, and
follow-up work. A slice is complete only after its automated checks pass **and**
the producer runs its acceptance script successfully.

Last updated: 2026-08-24

## Current milestone

- **Phase:** 0 — Foundations and Resolve capability spike
- **Active slice:** 0.1 — Repository, contracts, and fixture scaffold
- **Overall state:** Agent complete; producer acceptance and remote CI remain pending
- **Source specification:** `docs/Script-to-Timeline Product Spec - Fable Rev2.md`

## Status legend

- `Queued` — bounded but not started
- `In progress` — assigned and actively being implemented
- `Agent complete` — implementation and automated checks reported complete;
  producer acceptance is still required
- `Accepted` — producer ran the acceptance script successfully
- `Blocked` — cannot proceed without a recorded decision or external condition

## Slice tracker

| Slice | Status | Owner | Depends on | Verification / notes |
| --- | --- | --- | --- | --- |
| 0.1 Repository, contracts, and fixture scaffold | Agent complete | Orchestrator + bounded implementation agents | — | Integrated through `5028ed8`; clean detached-worktree bootstrap and one-command validation pass. Producer acceptance and remote CI remain pending. |
| 0.2 Handcrafted manifest → OTIO package | Queued | Unassigned | 0.1 accepted | Contract consumer; `/contracts` and `/fixtures` freeze after 0.1 acceptance |
| 0.3 Resolve Free import trial | Queued | Producer + agent recorder | 0.2 accepted | Requires the actual Resolve Free installation and manual import evidence |
| 0.4 Resolve Studio scripting spike | Queued | Unassigned | 0.2 accepted | Requires supported desktop Studio and external scripting availability |

## Slice 0.1 orchestration plan

### In scope

1. TypeScript workspace and Python package scaffolds.
2. CI that runs lint and tests for both languages.
3. Draft JSON Schemas for `ScriptDocument v1`, `TimelineManifest v1`, and
   `BuildReport v1`, plus reproducibly generated TypeScript and Python types.
4. Deterministic fixture media: three clips, two stills, one audio bed, with
   recorded content hashes.
5. `DECISIONS.md`, `CAPABILITIES.md`, checked-in agent guardrails, and one
   documented validation command.

### Explicitly out of scope

- OTIO/FCPXML writing or Resolve automation (Slices 0.2–0.4).
- Script semantic validation and compilation (Phase 1).
- Web application, persistence, collaboration, or deployment.
- Real production media or credentials.

### Contract and fixture policy

Contracts and fixtures may be created during Slice 0.1. Once producer
acceptance passes, they are frozen between slices. Any later modification must
be accompanied by a contract-change or fixture-change note describing what
changes, why, compatibility impact, regenerated outputs, and acceptance impact.

### Acceptance script, restated

1. Start from a fresh clone with the documented tool prerequisites.
2. Run the single documented validation command.
3. Confirm TypeScript lint/tests pass.
4. Confirm Python lint/tests pass.
5. Confirm generated types are current with the three schemas.
6. Confirm every fixture descriptor validates and every media hash matches.
7. Confirm CI executes the same checks and is green.

## Agent work log

| Date | Agent/workstream | Assignment | State | Result |
| --- | --- | --- | --- | --- |
| 2026-08-24 | Orchestrator | Locate authoritative repository/spec; initialize assigned workspace from `origin/main`; establish progress record | Complete | Spec and slice ritual reviewed; workspace now tracks the product repository |
| 2026-08-24 | Tooling workstream | Monorepo, CI, developer commands, guardrails, decision/capability document scaffolds | Agent complete | Integrated as `178b668`; clean npm/uv installs and the pinned-toolchain `npm run validate` pass independently. Remote CI and producer acceptance remain pending. |
| 2026-08-24 | Contracts workstream | Three JSON Schemas, generated types, schema/type tests | Agent complete | Integrated as `3d9c3c4`; three Draft 2020-12 schemas, generated TypeScript/Python models, positive/negative tests, and byte-currentness checks. |
| 2026-08-24 | Fixtures workstream | Deterministic media kit, descriptors/hashes, validation tests | Agent complete | Integrated as `83b7b74`; exactly three clips, two stills, and one audio bed with strict inventory, SHA-256, FFprobe metadata, regeneration, and verifier tests. |
| 2026-08-24 | Integration/review workstream | Merge audit, fresh-clone simulation, acceptance script verification | Agent complete | Integrated as `5028ed8`; removed premature fixed track-name/count constraints, proved configurable delivery settings, tightened fixture verification, and passed a clean detached-worktree bootstrap. |

## Producer decisions and external checks

The following Phase 0 worksheet items must be recorded in `DECISIONS.md`
before their dependent slices close:

- Primary local-agent OS.
- Exact Resolve Free and Studio versions/installations to test.
- Timeline frame rate, resolution, and audio sample rate: **resolved by D-0004**
  as configurable settings with defaults of 23.976 fps, 1920×1080, and 48 kHz.
- Track naming convention: **resolved by D-0005**; use the specification's
  section 9.2 map as the adjustable default rather than a contract invariant.
- Slice 0.3 OTIO-versus-FCPXML fallback decision, based on recorded evidence.

## Risks / blockers

- The assigned workspace began as an empty Git repository; it has been
  initialized from the authoritative GitHub repository without modifying the
  separate desktop checkout.
- Slice 0.3 and the producer-observed portion of Slice 0.4 require interactive
  access to the team's actual Resolve installations. Those checks cannot be
  replaced by automated mocks.
- Contract workstreams must not independently invent incompatible event or
  block shapes; the spec's canonical model and Phase 0/1 boundaries govern.

## Slice 0.1 verification result

- Clean locked installs: `npm ci` and `uv sync --frozen` pass.
- Pinned Node 24.19.0 `npm run validate` passes:
  - 16 contract tests and 1 TypeScript tooling test.
  - Ruff and strict mypy.
  - 11 Python tests, including fixture and generated-model checks.
- Generated TypeScript/Python contract output is byte-current and its
  post-bootstrap currentness check passes offline.
- Required FFprobe verification passes for exactly three clips, two stills,
  and one audio bed; all recorded hashes and metadata match.
- The full sequence was reproduced in a clean detached worktree without
  lockfile changes.

## Acceptance history

No slice has yet received producer acceptance. Slice 0.1 is ready for the
producer checklist in `docs/plans/slice-0.1-integration-review.md`; remote
GitHub Actions must also be green before acceptance.
