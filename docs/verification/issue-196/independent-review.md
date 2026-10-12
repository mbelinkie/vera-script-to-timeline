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

## Delta review: duplicate-ID numbering (after calibration round 1)

A fresh-context read-only reviewer subagent ran inside session
`da5a3fbd-c7c1-45af-bb5a-d3d5e12bf4b5`. It reviewed `git diff ea5db6c --
scripts/` against the round-1 manifests and confirmed the duplicate count
(403 IDs, 396 distinct).

**Verdict: approve, no blocking findings.**

- **Numbering is order-independent.** It depends only on how many times each
  exact name appears, and Vitest IDs include the file path.
- **A removed case is detected** (`incomplete-coverage`).
- **A numbering collision fails closed** (uniqueness checks).

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | informational | For abbreviated `it.each` names the identity is positional. A removed case is detected; swapping one abbreviated value for another is not. | Documented as `parameterized-identity` in the qualification record. |
| 2 | low | No validator-level test for a removed numbered case or a collision; a fixture count was confusing. | Added both tests and fixed the fixture. The helper suite now passes 32/32. |

## Final-revision review (revision `289a080`, calibration tree `5eb5c6e8`)

A fresh-context read-only reviewer subagent ran inside CLI session
`9908bbc3-704d-42c5-896b-3da72b64dd71`. It ran no tests while the local full
gate was running. It independently re-verified, using read-only `gh api` and
`jq`:

- the run conclusions and attempts;
- that commit `d9c63a84` and merge `cc0aa6fc` both have tree `5eb5c6e8`;
- that the branch has exactly 4 Validate runs, all successful;
- the manifest digests;
- that the draft matches both manifests (24 controls, tools, inventories
  499/403/61);
- the recomputed profile digest `1d6b3c41…`;
- that the delivered tree differs only under `docs/`;
- that the `upload-artifact` pin is v7.0.1;
- that the artifacts contain no private content.

It found no false-acceptance path in the evaluator.

**Verdict: GO with fixes.** No code or workflow change is needed, so the
qualified controls stay unchanged.

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | should-fix | The profile file and validator are an unprotected trust anchor. A branch could regenerate its own profile and run its own validator. | Activation rules in GO-NO-GO: run the validator and profile from accepted `main`; require the approved digest; require an artifact-sourced manifest; any candidate diff to the anchor, controls or profile is ineligible. |
| 2 | should-fix | Cited evidence logs were gitignored (`*.log`). | Force-tracked after a secret scan, following #193's precedent. `validate-final.log` will be added after completion. |
| 3 | should-fix | The runner image will roll over and suspend media scope; per-image approval would mean recurring Producer asks. | The durable scope is `excluding-media-sensitive`. Full scope is available only on the qualified image. Requalification is an optional owner submission, never a routine Producer request. |
| 4 | blocking for activation | AGENTS and CLAUDE still state the local-full rule; the guidance must change together with the policy. | Attempted only after a GO verdict. A classifier denial is reported as an activation blocker, never bypassed. |
| 5 | note | Record the approval verbatim. | The GO-NO-GO receipt section quotes it, with its condition and binding. |
| 6 | note | Scope choice is asserted by the caller. | Scope rule 4: a media-path diff is never eligible, and the reviewer confirms. |
| 7 | note | Stale text (retired session, 31/31, duplicated checkpoint steps). | Fixed. |
| 8 | note | Evaluating the post-merge `main` run is a free activation check. | Recorded in GO-NO-GO. |

## Receipt-delta review (`67946eb..4280f66`, docs/evidence only)

**Verdict: approve with fixes, no blocking findings.**

- No overclaim about activation.
- The receipt is verbatim, and the profile matches the draft plus approval
  only (both digests `1d6b3c41…`, `profileProblems` empty).
- The gate numbers match the retained files.
- Privacy is consistent with precedent.

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | medium | Qualified eval logs lacked the command and profile header. | Regenerated with a header (command, `--profile …/profile-qualified.json`, profile SHA-256 `b6cc9a83…`); both still exit 0. |
| 2 | low | "No tracked files modified" was not backed by a retained file. | Reworded: an owner-run post-gate `git status` was empty, and its output is not retained. |
| 3 | low | A glob also matched the qualified logs. | The hypothetical logs are now named explicitly. |
| 4 | low | Stale profile heading. | Points to `profile-qualified.json`. |
| 5 | low | The `5ab39b2` pointers were not self-contained. | Quoted inline in the activation blocker. |
| 6 | info | The private-consent statement can't be verified by the owner. | Attributed to the coordinator. |
