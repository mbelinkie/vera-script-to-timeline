# #168 contract-change note: shared recognizer/aligner port contracts

## Status and authorization gate

**Approved by the Producer on 2026-10-10** (all four #168 decisions; decision
1 approved the exact schemas). Design and evidence: branch
`claude/word-timing-v2`, `docs/plans/issue-168-recognizer-aligner-ports.md`
and `docs/investigations/word-timing-v2-results.md`. This note authorizes
only the additions below. Prepared on the unpushed #45 prototype branch;
merging to main still needs review (Codex second opinion queued) and the
normal roadmap gates.

## What changes

Adds four schemas to `/contracts` (JSON Schema 2020-12, closed objects):

- `recognition-artifact-v1.schema.json`: RecognizerPort output; tokens with
  nullable integer source-ms anchors and anchor precision; recogniser kind
  (`asr-local`, `asr-cloud`, `caption`, `reference-text`); consent block where
  cloud processing requires a stored per-project policy id.
- `alignment-artifact-v1.schema.json`: AlignerPort output; one entry per
  aligner unit (`tokenIndex`, `sub`: the many-to-many normalisation map),
  nullable integer ms, `acoustic` / `interpolated` / `unaligned`; optional
  agreement block with `needs_review` verdicts at `tauMs`.
- `script-reconciliation-v1.schema.json` (Script to Timeline only): per unit
  `heard` (presenter fidelity) and `text` (spelling for timing), script index
  and applied spelling.
- `port-refusal-v1.schema.json`: explicit refusal codes; no silent fallback.

Registers them in `packages/contracts/scripts/generate-contracts.mjs` and
regenerates `packages/contracts/src/generated/contracts.ts` and four new
Python modules under `python/vera_timeline_agent/generated/contracts/`.

## What it breaks

Nothing existing: purely additive. No existing schema, fixture, golden or
accepted test changes. The aggregate generated TypeScript type gains four
required properties, so any code constructing the aggregate `VeraContractsV1`
object directly would need them (none does in this repository).

## Acceptance

`npm run check:contracts-generated` (current), `npm run check:typescript`,
`uv run --frozen mypy python tests` (strict), ruff, and the #45 conformance
tests (`tests/test_issue45_ports.py`) validating fakes and real-engine
artifacts against these exact files.
