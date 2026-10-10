# #45 prototype — shared recognizer/aligner ports (draft #168 contract)

## Status and authority

**Unclaimed prototype, local branch `claude/issue-45-word-timing`.** The
Producer authorised starting #45 on a branch off main on 2026-10-10 ("local
commits only; you review before anything merges"). #45 is not Ready: it is
blocked by #168, whose exact schemas (decision 1) await Producer approval.
No roadmap command, claim, board change, push or merge has been made.

Evidence for every pipeline choice: `docs/investigations/word-timing-v2-results.md`
and the #168 draft `docs/plans/issue-168-recognizer-aligner-ports.md`, both on
branch `claude/word-timing-v2`. Producer decisions 2–4 on #168 are approved
(per-stage AudioPrep, captions as a recogniser source, stored cloud consent).

## Scope (this package)

- `experiments/issue45/normalize.py`: display token → aligner units (the
  many-to-many map). Ports the study's rules without its `num2words`
  dependency; parity with the study verified on 4,605 tokens (0 mismatches).
- `experiments/issue45/artifacts.py`: builders for `recognition-artifact/v1`,
  `alignment-artifact/v1` and the agreement block; content-addressed ids;
  validation against the draft schemas in `experiments/issue45/schemas/`
  (copies of the #168 drafts).
- `experiments/issue45/ports.py`: `RecognizerPort`, `AlignerPort`,
  `PortRefusal` (+ `port-refusal/v1` record), `ProjectPolicy`.
- `experiments/issue45/fake.py`: deterministic fakes for product tests.
- `experiments/issue45/conformance.py`: the suite every engine must pass
  (schema validity, determinism, normalisation round trip, null bounds,
  monotonic times, unsupported-language and missing-consent refusals,
  reference-text never feeding production).
- `experiments/issue45/segmentation.py`: VAD region grouping and unit
  assignment (pure, ported).
- Adapters: `youtube_captions.py` (pure json3 parsing), `local_engines.py`
  (Parakeet recogniser and MFA aligner over vendored engine scripts in
  `adapters/engines/`, run in their own external runtimes; a missing runtime
  is a visible `runtime-missing` refusal; MFA runs are serialised by a lock).
- `experiments/issue45/smoke.py`: real-engine run + conformance on local audio.
- `tests/test_issue45_ports.py`: 25 tests, no external runtimes needed.

## Exclusions

No `/contracts`, fixtures, goldens or generated-type changes (they wait for
schema approval). No production package (`python/vera_timeline_agent`)
changes. No cloud adapter yet (ElevenLabs via the cloud profile), no script
reconciliation, no take logic (#53 code is on its own unmerged branch; take
rules v2 live on `claude/word-timing-v2`), no Qwen agreement runtime, no UI,
persistence, jobs or Research changes. No new dependencies: the repo already
pins `jsonschema`; engine runtimes are external and configured, not installed.

## Touched outside `experiments/`

`pyproject.toml`: a ruff per-file-ignore for the vendored engine scripts only
(they run in external runtimes and keep the study's measured behaviour).

## Checks

`uv run --frozen ruff check .`, `ruff format --check .`,
`uv run --frozen mypy python tests` (strict, 93 files),
`uv run --frozen pytest tests/test_issue45_ports.py` — all pass.

## Producer acceptance steps (when #168 is approved)

1. Approve or amend the three draft schemas (#168 decision 1).
2. Review this seam: ports, refusal codes, conformance list.
3. Decide the next package: cloud adapter + reconcile + agreement, then move
   schemas into `/contracts` with generated types, then take logic integration.

## Verification (2026-10-10, this Intel Mac)

- Lint/format/strict mypy pass. `tests/test_issue45_ports.py`: 25 passed.
- Full `pytest`: 97 failed / 297 passed. A pristine `origin/main` worktree on
  the same machine gives the identical 97 failures (272 passed): they are
  pre-existing Node-backed tests under the unsupported Node 26.5 (declared
  `>=24.19 <25`, see #106), not caused by this package.
- Real-engine smoke (`experiments.issue45.smoke`) on recording B:
  - Parakeet adapter → MFA adapter: 557 tokens (22 s), 559/559 units
    acoustic (109 s), conformance PASS; 520/559 units identical to the study's
    run of the same engines, the rest within 70 ms.
  - YouTube captions adapter → MFA adapter (raw B): 562/562 acoustic,
    conformance PASS; 540/562 identical to the study, the rest within 70 ms.
