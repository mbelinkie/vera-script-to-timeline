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

- `experiments/issue45/script_reconcile.py` + draft
  `script-reconciliation-v1.schema.json`: prompter parsing (restart points,
  pronunciation guides, keyterms) and script reconciliation as its own
  immutable record (`heard` = presenter-fidelity evidence, `text` = spelling
  to align). The aligner port takes it as an optional input and records
  `reconcileArtifactId`. Parity with the study: 6,032/6,032 units identical
  across 6 recognisers x 2 recordings.
- `adapters/elevenlabs_cloud.py`: ElevenLabs Scribe v2 via OpenRouter,
  consent-gated, key read from the environment and never stored.

## Exclusions

No `/contracts`, fixtures, goldens or generated-type changes (they wait for
schema approval). No production package (`python/vera_timeline_agent`)
changes. No take logic (#53 code is on its own unmerged branch; take
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
  - ElevenLabs cloud adapter → MFA adapter (B, ~3 cents): 557 tokens in 4 s,
    562/562 acoustic, conformance PASS. Matched by text against the study's
    ElevenLabs run: 557/562 units, onset/offset |diff| median and p95 0 ms.
    **Cloud output is not run-to-run deterministic**: the repeat call differed
    in 4 small spans ("acadefri con" vs "academic conf", an extra "um" and
    two "a"). Conformance therefore requires determinism only for local
    engines; each cloud call is its own immutable artifact (#168 already
    appends rather than rewrites).
- `profiles.py` (Script to Timeline: recogniser → reconcile → MFA with
  prompter pronunciation guides via the vendored guide G2P engine; Research:
  recogniser → MFA). End-to-end on recording A with Parakeet, scored by the
  study's scorer against the Producer's key: coverage 77.6%, onset 18/124 ms
  (median/p95), offset 34/145 ms on the independent 80 words — equal to the
  study pipeline (33 ms offset median); full key 88.8%, 10/54, 10/57 ms,
  identical to the study.
- `adapters/agreement.py` (Qwen3-ForcedAligner in its vendored container, on
  the identical segments MFA saw): on recording A's end-to-end alignment it
  marks 58/876 boundaries (6.6%) `needs_review`, and flags 16 of the 17
  displaced words (0.5–3 s off against the Producer's key). Container engines
  only see the home directory under Colima, so hand-off files live in
  `EngineConfig.work_dir` (`~/.cache/vera-engines`), not the system temp dir.
- `bench/` (Apple Silicon gate kit): `make_kit.sh` builds a 68 KB zip (code +
  public-domain LibriVox Gettysburg Address text + Intel reference); on any
  Mac `sh bench.sh` installs micromamba, MFA 3.4.3, the tools and Parakeet
  environments and pinned models inside the kit folder (all checksummed; no
  admin, no Homebrew), then times both profiles and compares word times to
  the reference. Clean-room run here (empty environment, system PATH only):
  setup 4.3 min; on the 2:41 clip Parakeet 16 s, MFA 94–107 s, all 331 units
  aligned, conformance PASS. Repeat run vs the reference: same transcript,
  323/331 and 329/331 units identical, max 10 ms (MFA run-to-run noise).
  The first clean-room run exposed an MFA failure mode: it rejects a corpus
  whose path string starts with its root dir, then reports every word
  "failed". The adapter now refuses when MFA aligns nothing, and conformance
  fails alignments with under 50% acoustic units.
