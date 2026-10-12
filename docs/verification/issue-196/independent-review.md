# Issue #196 independent review (execution phase)

2026-10-12. A fresh-context, read-only Claude reviewer subagent ran inside
owner session `85843512-9132-4b84-9c1e-86173c4de542`. It did not see the
owner's working reasoning, and it ran only the focused helper tests. It
reviewed the working-tree delta against `98b9a614` (committed as `712ee15`,
tree `642eca97`). It also checked the
prior preparation review findings against the code. This is less independent
than a separate coordinator-launched session. The coordinator may require one
before the final gate.

## Verdict: approve with fixes, no blocking findings

The reviewer found no path to a false acceptance:

- **Workflow:** no weakening.
  - `shell: bash` already uses `-eo pipefail`, so the step exit code comes
    from `npm run validate`.
  - `PYTEST_ADDOPTS` changes only reporting, and pytest is invoked once.
  - The new tests are additive.
  - `!cancelled()` steps can't mask failures.
  - Permissions and pins are unchanged.
- **Privacy:** acceptable. Only `manifest.json` is uploaded. Its free text is
  limited to skip reasons and collection-error tails of at most 300 characters,
  which still need checking on the first real artifact.
- **Parsers:** match the retained #193 log.
- **Prior findings:** every preparation-review finding is resolved in code.
  Spec 4 is partial: other branches are a stated limitation.

## Findings and disposition

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | should-fix | The one-page history read makes busy branches (`main` push runs, long PRs) unvalidatable. It fails closed with exit 2. | Fixed. Results are paged up to 10 × 100 runs, and anything beyond the cap is refused. Tests cover multi-page history and the cap. |
| 2 | note | Unrecognised Vitest summary words are dropped; pytest skip count is not cross-checked. | Fixed. Each Vitest summary needs `passed === total`, and the pytest skip count must equal its skipped outcomes. Tests added. |
| 3 | note | The report omits manifest provenance and digest. | Fixed. The report gives `manifest.source` (`local-file` or the artifact name) and `manifest.sha256`. |
| 4 | note | A profile is accepted with a single calibration run. | Fixed. A qualified profile needs at least two distinct calibration runs on the same tree. A draft can carry one. Tests added. |
| 5 | note | API and tool assumptions are unverified: `run.path` format, the `branch` filter for PR runs, job fields, `vitest list --json`, PR merge parentage. | These are retained as first-calibration-run checks. Each one fails closed if wrong. |

Delta checks after fixes:

| Check | Result |
| --- | --- |
| `eslint scripts/*.mjs` | Clean |
| Helper tests | 31/31 |
| `validate:fast` (18:26:09–18:28:11Z) | exit 0: Vitest 402+1, node:test 6+23+31, ruff/mypy clean, 317 non-slow pytest passed (`validate-fast-delta.*`) |
