# Orchestration Progress — 2026-08-25

This is the working orchestration log for the current execution run. The
authoritative long-lived slice states remain in `docs/IMPLEMENTATION_PROGRESS.md`,
and acceptance follows the producer's standing delegation in D-0008.

## Current gate

- **Phase 0 gate closed on 2026-08-25.** Slices 0.1 through 0.4 are accepted.
- The producer visually inspected the final Studio result and explicitly
  accepted Slice 0.4, including the documented V1/120-frame Text+ limitation.
- The Text+ limitation remains an open capability problem, recorded separately
  in `docs/resolve-text-plus-destination-track-limitation.md`.
- Slice 1.1 was explicitly accepted by the producer on 2026-08-25; its two
  canonical semantic inputs are now frozen.
- Active bounded slice: **1.2 — Voice adapter and block asset cache**.
- Under D-0008, automated-only slices may be accepted autonomously after all
  bounded checks, boundary audits, acceptance procedures, and independent
  review pass. Slice 1.2 still has a manual producer gate because its done
  condition requires listening to generated files and observing cache behavior.

## Slice 0.4 bounded execution record

### Scope

Run the documented supported-API producer workflow against the accepted Slice
0.2 package: focused checks, connected preflight, one uniquely named project
build, save/reopen, public-API verification, capability evidence, and producer
inspection/acceptance.

### Exclusions

- No UI automation, Resolve launch/quit, rendering, upload, or research data.
- No deletion, reuse, or overwrite of an existing Resolve project.
- No edits to frozen contracts, fixtures, generated types, accepted Slice 0.2
  data/tests, or golden files.
- No implementation work from Slice 1.1 or later until this gate closes.

### Touched contracts, fixtures, and dependencies

- Consumes the accepted `out/slice-0.2-package` and frozen manifest contract.
- Current staged code changes are confined to
  `python/vera_timeline_agent/studio_spike.py` and
  `tests/test_studio_spike.py`.
- No dependency or lockfile change is authorized.

### Automated checks

- 2026-08-25: focused Slice 0.4 pytest passed: **44 tests**.
- 2026-08-25: focused Ruff check passed.
- 2026-08-25: focused strict mypy check passed.
- 2026-08-25: clean detached verification worktree successfully completed
  locked `npm ci` and `uv sync --frozen` installs.
- 2026-08-25: pinned Node 24.19.0 `npm run validate` passed in that clean
  worktree: generated contracts current, TypeScript lint/typecheck, 16 contract
  tests, 1 tooling test, Ruff lint/format, strict mypy, and **85 Python tests**.
- 2026-08-25: `git diff --check` passed and the diff from accepted Slice 0.2
  commit `c4a093c` was empty across contracts, fixtures, generated contract
  outputs, accepted Slice 0.2 data/tests, and both lockfiles.

### Real Studio evidence

- Resolve process is running from the canonical default application path.
- The local scripting bridge and documentation are installed.
- Resolve is listening on its external-scripting port.
- Two fresh preflight attempts returned `stopped_safely` because the first
  Resolve process's internal script server failed to connect. Both reported no
  project mutation. After a producer restart, all preflights passed cleanly.
- Three uniquely named build attempts exposed and bounded Resolve 21's PNG
  duration behavior. They were retained and never overwritten or deleted.
- A separate retained probe timeline established the exact still-range matrix:
  mark 18/end 18 → 17 frames; mark 18/end 19 → 18 frames; mark 19/end 19 →
  18 frames; mark 19/end 20 → 19 frames.
- Final project `VERA Slice 0.4 Producer Acceptance 20260825-021704` saved,
  closed, reopened, and returned `verified` with no public-API-observable
  discrepancies. Its timeline is
  `VERA build 00000000-0000-4000-8000-000000000103`.
- The producer visually inspected the result and explicitly accepted Slice 0.4
  on 2026-08-25, including the documented V1/120-frame Text+ limitation.

## Subagent dispatch log

| Workstream | Boundary | State | Result |
| --- | --- | --- | --- |
| Slice 0.4 independent staged-diff review | Read-only; no Resolve connection or mutation | Dispatch failed | Local Codex CLI provider authentication timed out and then returned HTTP 401; no repository or Resolve side effect occurred. |
| Slice 1.1 preserved-worktree audit | Read-only; producer pause enforced | Dispatch failed | Same local subagent authentication failure; preserved worktree unchanged. |
| Phase 1 roadmap/dependency audit | Read-only | Dispatch failed | Same local subagent authentication failure; no file change. |
| Slice 1.1 implementation reviews | Read-only final-state audits | Complete | Successive reviews found and prompted fixes for exact affinity boundaries, canonical fixture-shape ratchets, complete CLI references/output, DraftBlock schema-noise collapse, and active-draft-wide ID scope. Final review of `4fe34ab` against accepted `9dfacb4` reported no findings. |
| Slice 1.2 provider comparison | Read-only current official-document research | Complete | Compared AWS Polly, Google Cloud TTS, Azure Speech, and ElevenLabs across timing, pronunciation, price, data handling, API burden, limits, identity, and credentials. Recommended AWS Polly Neural with explicit content-policy and managed-voice-version caveats. |
| Slice 1.2 contract/cache audit | Read-only repository/spec design | Complete | Defined a Python provider boundary, two-level synthesis/normalization cache, internal narration-asset records, deterministic CLI evidence, failure semantics, dependency boundary, and tests without changing frozen shared contracts. |
| Slice 1.2 FFmpeg normalization | Read-only capability and command probe | Complete | Confirmed FFmpeg/FFprobe 8.1.2, two-pass loudnorm and required PCM/WAV capabilities; repeated full-filter runs matched under the same fingerprint. Recommended mono 48 kHz PCM-24, -16 LUFS, -1.5 dBTP, LRA 7, exact sample preservation, and no timing concealment. |

Local CLI authentication later recovered. Slice 1.1 received successive
read-only reviews, and the final rebased review completed with no findings.

## Slice 1.1 bounded execution record

### Scope and exclusions

- Added a pure TypeScript structural/semantic validator and file CLI, two
  canonical script inputs, positive/negative tests, and a producer acceptance
  procedure.
- Enforces the approved D-0006 token, anchor, ownership, coverage, qualifying
  visual, excluded-narration, and uniqueness decisions without repair or
  inferred defaults.
- Excludes voice synthesis, compilation, package generation, Resolve work,
  editor/persistence work, media probing, and any contract or fixture change.
- Reuses already pinned Ajv dependencies; no dependency or lockfile changed.

### Automated checks and review

- Focused lint, strict TypeScript typecheck, and **59** contract/validator tests
  pass; exact canonical pass output and the producer-required broken-copy
  failure are regression-tested.
- Clean detached locked installs passed. With pinned Node 24.19.0, the combined
  accepted Slice 0.4 + Slice 1.1 tree passed generated-type currentness,
  TypeScript checks, 1 tooling test, Ruff, strict mypy, and **85 Python tests**.
- Frozen contracts, fixtures, generated types, accepted Slice 0.2 data/tests,
  and both lockfiles have no diff; `git diff --check` passes.
- Final independent read-only review reported no findings.

### Producer gate — passed

The producer explicitly accepted the semantic decisions, canonical inputs, and
Slice 1.1 on 2026-08-25 after the documented evidence passed. The canonical
inputs are frozen for later compiler goldens.

## Producer acceptance checklist for Slice 0.4

1. **Passed.** Connected preflight reports Studio identity, supported scripting, no
   discrepancies, and no mutation.
2. **Passed.** One unique project name is authorized and does not collide.
3. **Passed.** The build creates bins, adjustable tracks, three trimmed videos, one still,
   one narration placement, one requested Text+ title, and marker custom data.
4. **Passed.** The project saves, closes, reopens, and the CLI reports no observable
   discrepancies.
5. **Passed.** Producer visually inspected the resulting project/timeline and recorded the
   public-API gaps, especially the Fusion title's stock identity and track.
6. **Passed.** `CAPABILITIES.md`, `DECISIONS.md` if needed, and
   `docs/IMPLEMENTATION_PROGRESS.md` record the actual version-stamped result.
7. **Passed.** Producer explicitly accepted Slice 0.4 on 2026-08-25, including
   the Text+ limitation; the Phase 0 gate is closed.

## Decision queue

- Slice 0.4 requires no further acceptance decision. Its Text+ limitation is
  an open capability investigation, not a reopened Phase 0 gate.
- Slice 1.1 is accepted; no decision remains open.
- The orchestrator will select Slice 1.2's initial cloud voice provider from a
  current evidence-based comparison and record the rationale rather than stop
  for an ordinary design choice. Provider credentials or account authorization,
  if unavailable, remain an external gate.
- Slice 1.2's final acceptance remains manual because the producer must hear
  each normalized block file and observe all-reused and exactly-one-regenerated
  command results.
- D-0009 through D-0011 close the ordinary Slice 1.2 implementation choices.
  The still-manual live gate is the producer's AWS data-policy attestation,
  authorization of the first billable command, listening judgment, and cache
  observation. Implementation proceeds without those live side effects.
