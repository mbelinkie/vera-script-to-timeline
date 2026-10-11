# Issue 183: shared word-timing package — evidence

Package: `packages/word-timing` (`vera_word_timing`, console script `vera-word-timing`).
It implements the Producer-approved #168 ports and contracts and promotes the #45
prototype (`docs/plans/issue-45-ports-prototype.md`).

## Acceptance evidence

| Criterion | Evidence |
| --- | --- |
| Installs in the locked toolchain; lint, strict mypy and the contract check pass | uv workspace member; `uv run --frozen` lint and mypy are clean; contract-drift test |
| Conformance passes for the fakes, and opt-in for real adapters | `tests/test_word_timing_package.py`; real-engine smoke below |
| The CLI round-trips with schema-valid JSON and explicit refusals | `tests/test_word_timing_cli.py`; real-engine smoke below (every output is checked against its contract before it is written) |
| No product changes; take logic stays in #45 | The diff touches only the package, contracts and generated types, tests, and `experiments/issue45` |

Codex review history:

- **First review:** 14 findings (3 blockers, 11 should-fix), addressed in `f6bc9b0`.
- **Re-review:** 6 partly fixed and 4 new issues, addressed in `bf258aa`. One design
  addition: German capitalises nouns, so there a capital needs dictionary absence
  to count as a name.
- **Second re-review:** 8 fixed and 2 partly fixed, verdict "merge after fixes".
  The last two (truncated WAV refusal, caption offsets outside their cue) are
  fixed in the final commit.

Real-data checks after these fixes:

- English reconciliation on recordings A and B is unchanged (0/997 units differ).
- Caption tokens are identical on all 8 study caption files.
- Real Qwen agreement on A is identical.
- Resolve now leaves 0 invalid words. Before, 4 words overlapped a neighbour; the
  5 edges involved now fall back to MFA's own times as `unresolved`.

## Real-engine smoke (2026-10-11, Intel reference Mac)

The smoke drove the installed CLI only (`uv run --frozen vera-word-timing ...`).
It used the study recordings, which stay private; only aggregates are recorded here.

English (recording A, 8 min): Parakeet → reconcile → MFA `english_us_arpa` with
pronunciation guides → Qwen agreement → resolve.

- **Parity with the #45 prototype:**
  - 438/438 words acoustic, the same as the prototype.
  - 438 of 438 words match.
  - 436 have identical times.
  - Median start and end difference is 0 ms, and no word differs by more than 50 ms.
- **Agreement:** 58/876 boundaries need review (6.6%), the same as the prototype.
- **Resolve:**
  - 818 agreed
  - 40 anchor tie-break
  - 11 outer edge
  - 3 quiet-gap inner
  - 4 unresolved
- **Wall time:**
  - recognise 31 s
  - reconcile 2 s
  - align 146 s
  - agree 469 s
  - resolve 2 s

European (study YouTube talks, about 5 minutes each): Canary-1B v2 with forced
language → MFA, then Qwen agreement.

| Language | Recognise | Align (MFA model) | vs study MFA run (matched words) | Agreement |
| --- | --- | --- | --- | --- |
| de | 626 tokens | 629/629 acoustic (`german_mfa`) | 620 matched; median Δ 0 ms; 2 ends >50 ms | 129/1258 need review (10.3%) |
| fr | 608 tokens | 611/611 acoustic (`french_mfa`) | 599 matched; median Δ 0 ms; 1 end >50 ms | 65/1222 need review (5.3%) |
| sv | 611 tokens | 612/612 acoustic (`swedish_mfa`) | 609 matched; median Δ 0 ms; 1 start >50 ms | **Refused (exit 3):** Qwen has no Swedish |
| it | 406 tokens | **Refused (exit 3):** no Italian MFA model | — | — |

Notes on the table:
- **Unmatched words** are mostly numerals. The package keeps digits for
  non-English languages (`2015`), where the study spelled them out.
- **The refusals are intended.** Swedish and Italian return explicit
  `port-refusal/v1` records, never a silent fallback. They still need an agreement
  partner or keys (Swedish) and an aligner (Italian).
