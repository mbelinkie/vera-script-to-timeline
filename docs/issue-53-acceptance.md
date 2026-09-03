# Issue 53 — implementation and Producer review

The provider-neutral row parser is implemented locally. **Producer acceptance
is pending.** #53 evaluates logic assuming accurate transcript text; #51 stays
unresolved and owns recognition/timing model adequacy. No provider, keeper,
speech-safe boundary, or production contract is approved by this handoff.

Branch: `codex/issue-53-provider-neutral-takes`; baseline `333a064`.
Task: `01a06803-59f3-7db3-9cfc-ce016e5fa575`, exact Sol/high claim.
The [algorithm and contract proposal](issue-53-take-proposal.md) records all
rules, thresholds, compatibility consequences, and remaining judgments.

## What changed

- `experiments/issue53/takes.py`: normalized seam, backward whole-row discovery,
  source-ordered complete/partial/modified/unmatched reads, last-complete
  suggestions and earlier alternatives, review-only partial assemblies,
  separate timing/handle uncertainty, and independent reference evaluation.
- `experiments/issue53/cli.py`: exclusive private JSON output outside Git.
- `tests/test_issue53_takes.py`: 24 new fictional assertions, including
  multi-sentence rows, repeats/restarts, ad-lib substring protection, ambiguous
  mappings, missing/noisy timing, Producer decisions, coverage, and boundaries.
- New plan, proposal, and this handoff. No shared contract, generated type,
  accepted fixture/test/golden, compiler, dependency, or lockfile changed.

The judgment calls needing review are the 1.4-second pause split, limited
approximate completeness, attachment of adjacent unmatched words, and greedy
partial assembly. Long intentional pauses and strongly altered openings can
remain partials. An assembly lists exact source-token pieces and every join's
review status; it is not rendered or selected as a keeper.

## Retained verification — 2026-09-03

Node 24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14, Ruff 0.16.4,
mypy 2.3.1, installed FFmpeg/FFplay 8.1.2.

```sh
rtk uv run --frozen pytest tests/test_issue53_takes.py -q
rtk uv run --frozen mypy experiments tests/test_issue53_takes.py
rtk proxy env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/matthewbelinkie/.local/bin:/usr/local/bin:/usr/bin:/bin npm run validate
rtk git diff --check
```

Focused tests: **24 passed**. Focused strict typing: **5 source files passed**.
Full gate: **199 Python, 141 contract, 1 tooling, 6 progress, and 23 roadmap
tests passed**, generated contracts current, Ruff/formatting and strict typing
passed. Raw final log: ignored local `out/issue-53-checks/validate-final.txt`.
An earlier full attempt stopped at two new formatting/lint findings; those
were corrected before the retained successful full gate.

Read-only accepted #42 corpus checks used ideal words and retained noisy words
through the same discovery function. The ad-lib stays approximate, the omitted
beat stays uncovered, every word is retained, and restart subdivisions remain
explicit review cases. Accepted corpus content and detailed results remain
local; none is copied into this branch.

Run A execution consumed two already-retained normalized variants, including
missing acoustic timing. It invoked no recognizer or alignment model. OS policy
denied network access and writes outside the new private evidence directory.
Read-only energy measurement supplied additional boundary evidence without
treating the audio. Every input word is accounted for, input hashes stayed
unchanged, and both discovery reports were frozen before reference evaluation.
All highlighted and supplied timing/count-only reference cases are represented;
unknown cases and possible split/merge links remain separate from recognition
errors. No listening result is invented.

The standalone CLI replay equals the final private discovery JSON. The playback
manifest validates all ranges against full source duration. It plays original
source ranges without creating media. Private inputs, reports, locators, hashes,
and per-case results remain outside Git; the workspace review link is ignored.

## Producer acceptance checklist

1. In this task's workspace open `out/issue-53-review/REPORT.md` (Run A / Issue
   53 / Review 03). Review the seven row groups and the algorithm proposal.
   Expected: several sentences can form one row; text-parsing judgments are
   separated from #51's model/timing limitations.
2. Open `out/issue-53-review/playback.command`. Enter the report's playback
   numbers for each last-complete suggestion and earlier alternative. Enter
   `full` or `range START END` to inspect missed/unmatched source material.
   Expected: separate repeated reads remain source-ordered; the last eligible
   complete row is suggested; later partials do not displace it.
3. Inspect each review-only assembly, uncovered row/token, ambiguous group, and
   reference case. Play the listed pieces in row order. Expected: missing
   complete reads yield visible partial proposals, and every join or unknown
   case remains flagged rather than becoming an approved take.
4. For boundary proposals, listen at both edges and inspect every exception.
   Expected: approximately ten source frames outside speech only when feasible;
   unavailable handles use broad context, never a silent cut through speech or
   an adjacent take. All actual boundary confirmations are yours to record in
   `PLAYBACK-OBSERVATIONS.md` alongside the report.
5. Reply **`Accepted provider-independent presenter take logic.`** or name the
   first failed row, candidate, default, assembly, boundary, or rule. This accepts
   the bounded logic/proposal only; #51 and #45's other gates stay separate.

Leave #53 **In review** until explicit Producer acceptance. An inadequate logic
result does not clear #45's design gate. No other roadmap issue is dispatched.
