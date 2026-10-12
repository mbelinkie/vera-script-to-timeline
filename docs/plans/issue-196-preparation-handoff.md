# Issue #196 preparation handoff

Status: producer-authorized preparation only, 2026-10-12. Completing this
preparation is **not** completion of #196. Nothing here qualifies cloud
evidence, activates substitution, or changes the local-full rule in
[VERIFICATION_POLICY.md](../VERIFICATION_POLICY.md). Plan:
[cloud-validation-qualification.md](cloud-validation-qualification.md).

- Preparation owner: `claude:33ed0ca5-fcd6-4650-9bfd-63db45ef7a11`
  (`claude-opus-5-5`, high), recorded on #196 with
  `phase: producer-authorized-preparation-only`. The owner stays active until
  explicitly transferred or released.
- Branch `claude/issue-196-cloud-validation-prep`, starting at
  `353184b550bfcbb416face173e905e89afbac56e` (origin/main `5d59b2a` plus the
  plan and verification-policy documents). No #193 changes are included.
- #196 remains Blocked by #193 and #184. It wasn't promoted, claimed, pushed or
  dispatched.

## Scope and exclusions

Owned and changed:

| File | Purpose |
| --- | --- |
| `.github/workflows/validate.yml` | Preflight, JUnit reporting, evidence collection/upload, PR concurrency, exact acceptance command |
| `scripts/cloud-evidence-lib.mjs` | Pure parsing, control digests and the fail-closed evaluation |
| `scripts/cloud-evidence-collect.mjs` | Workflow-side manifest collector (records; never judges) |
| `scripts/cloud-evidence-validate.mjs` | Local CLI: read-only GitHub facts → verdict, or an unqualified draft profile |
| `scripts/cloud-evidence.test.mjs` | Focused tests with stubbed GitHub responses |
| this document | Scope, checks and remaining gates |

Excluded: product code, schemas, generated types, contracts, fixtures,
goldens, accepted tests, `package.json`, npm/uv lockfiles and new
dependencies. The helpers use only Node built-ins and follow the existing
`scripts/roadmap*.mjs` pattern (`node:test`, `gh` subprocess).

## What the workflow change does

- Runs `VITEST_MAX_WORKERS=1 npm run validate`, the policy acceptance command.
  The old step ran `npm run validate`. Test selection, serial Python
  execution, the 90-minute limit, lockfile verification, trusted events,
  `contents: read` and pinned actions are unchanged.
- **Preflight required media tools:** fails before the gate if `ffmpeg` or
  `ffprobe` is absent, so the frozen `tests/test_fixtures.py` FFprobe skip
  path cannot silently pass.
- Sets `PYTEST_ADDOPTS=--junitxml=…` for reporting only. The collector then
  runs plain `pytest --collect-only -q` without that variable, and the
  validator requires identical IDs (reporter parity).
- **Collect validation evidence** and **Upload validation evidence** run with
  `if: !cancelled()`, so evidence survives failures. A later successful step
  never changes an earlier failed step or the job's conclusion. Only
  `manifest.json` is uploaded, using artifact `vera-validation-evidence-attempt-N`.
  Raw JUnit (which can hold failure text), logs, the worktree and caches are not
  published. Artifact retention uses the repository default.
- `actions/upload-artifact` is pinned to
  `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1). The SHA was resolved
  read-only from `refs/tags/v7.0.1`, a lightweight tag on the commit. I
  preferred v7.0.1 over v7.0.2 (5 days old, download-retry changes only).
- Concurrency: a newer pull-request push cancels that PR's older, obsolete
  run. Push runs are keyed by commit SHA, so post-merge integration runs on
  `main` are never cancelled or replaced. Cancelled runs remain non-passing.

## Evidence authority model

The manifest records only what the run consumed: checkout commit/tree, PR
head/base, control blob digests, input tree IDs, Node/npm/uv/Python/OS/arch,
the FFmpeg/FFprobe version, binary SHA-256 and a capability digest, the runner
image, pytest JUnit identities/outcomes/skip reasons/timing, Vitest list IDs
and skip markers in test sources. It never decides that the run passed.

`evaluateCloudEvidence` passes only when all of these hold:

- **Run and job facts come from GitHub:** the exact
  `/actions/runs/{id}/attempts/{n}` run and that attempt's jobs.
  - The run must be the `Validate` workflow at `.github/workflows/validate.yml`,
    with status `completed`, conclusion `success` and the expected event.
  - It must belong to the same repository (fork runs are unqualified) and be
    linked to the expected PR.
  - It must have exactly one `TypeScript and Python` job for that attempt,
    every required step must have concluded `success` (not `skipped`), and the
    job must carry the qualified runner label.
- **The tested tree is corroborated by GitHub's commit object:**
  - For a PR, the checked-out merge commit's second parent must equal the
    run's head SHA.
  - For a push, the checked-out commit must equal the run's head.
  - The tested tree must equal the delivered tree on the integration
    baseline. Any difference fails and falls back to the policy's
    evidence-reuse analysis.
- **Controls come from GitHub's recursive tree listing, not the manifest:**
  - These files are controls: the workflow, `.nvmrc`, `.python-version`, root
    and package manifests, lockfiles, the eslint config, tsconfig files, any
    vitest config, `conftest.py`, the contract generator and the evidence
    helpers.
  - Any difference from the qualified profile fails as `control-drift`. A
    changed gate therefore cannot self-certify. A truncated listing also fails.
- **Every attempt of every Validate run on the same head SHA is checked**
  (both events):
  - Each non-success attempt needs a retained disposition: class
    `infrastructure`, `operator-cancelled` or `diagnosed-flake`, plus an
    explanation and evidence. Flake dispositions are flagged for the reviewer.
  - Incomplete sibling runs fail.
  - A history spanning more than one page is refused.
- **Inventory and outcomes:**
  - pytest must show zero failures and errors.
  - Every skip must be on the profile allowlist, which is empty by default;
    any Vitest skip, todo or focus marker also fails.
  - Every required ID must be present.
  - The manifest must report complete collection and successful
    self-recorded steps.
- **Tool profile:**
  - Runtime drift fails everything.
  - Media-tool or runner-image drift suspends only the `media-sensitive`
    scope.
- **The profile must be `qualified: true` with an approval record.**
  `--draft-profile` writes `qualified: false`, `approval: null` and an empty
  skip allowlist. Only qualification review can change those values.

The validator supplies GitHub responses only as data. It issues `gh api` GET
reads and downloads the artifact into a fresh temporary directory, which it
parses as JSON only.

### Stated limitation categories

| Code | Meaning |
| --- | --- |
| `outcome-by-step-only` (always) | Lint, type checks, generated-currentness, Vitest and `node:test` results are proven by GitHub's step conclusion, not per-test reports. Adding reporters would change commands, so it's deferred. |
| `inventory-added` | IDs beyond the qualified inventory passed but were not part of qualification. |
| `media-tool-drift`, `runner-image-changed` | Media-sensitive substitution is suspended; pure-logic scope is unaffected. |
| `flake-disposition` | A reviewer must confirm the prior failure under the flake policy. |

Known non-coverage, by design: a removed or renamed required test fails as
`incomplete-coverage` until the profile is requalified. Vitest skip detection
is a source scan, not a runtime report. Duplicate push and PR runs are not
suppressed. Instead the caller names the authoritative event (`--event
pull_request --pr N` when a PR exists), and the sibling history covers both
events. Suppressing duplicates would need a PR lookup with added permissions,
which was deliberately not done.

## Judgment calls for qualification review

1. The collector exits 0 whenever it writes a manifest, even an incomplete one.
   This keeps an evidence bug from turning ordinary CI red, while the
   validator still fails closed on `incomplete-collection`.
2. A runner-image change with identical tool fingerprints suspends media scope
   rather than everything. `acceptedRunnerImages` records approved exceptions.
3. Whether to wire `scripts/cloud-evidence.test.mjs` into `npm run validate`.
   That needs a `package.json` change, which is outside this preparation's
   ownership. Today the tests run only by direct `node --test`. ESLint already
   covers `scripts/*.mjs` through `lint:typescript`.

## Checks completed (preparation only)

All checks ran locally on this branch's committed sources with the pinned Node
`v24.19.0` (`~/.local/share/vera/toolchains/node-v24.19.0-darwin-x64`):

| Check | Result |
| --- | --- |
| `node --check` on all four new scripts | pass |
| `node --test scripts/cloud-evidence.test.mjs` | 22/22 pass |
| Mutation sanity (copies in job temp): disable the prior-failure check, control-drift failure, PR merge-parent check or skip rejection | Each mutation fails ≥1 test |
| `ruby -ryaml` parse of `validate.yml` | Valid; `contents: read`; 4 SHA-pinned actions; step names match `REQUIRED_STEPS` |
| Workflow consistency test | Required steps, exact command, artifact name, permissions and 40-hex pins present |
| Diff/frozen audit vs `353184b` | Only the workflow and new `scripts/cloud-evidence*` plus this document; no contracts, fixtures, tests, packages, Python or lockfile/manifest paths |

Visible pending checks (not run, and not substituted):

- `npm run lint:typescript` (ESLint over the new `scripts/*.mjs`), fast and
  full validation. These need `npm ci`/`uv sync`, which this phase prohibits.
  Run them in the claimed implementation after #193.
- actionlint. It is not installed, and it was deliberately not installed.
- A real CI execution of the collector: `vitest list --json=<file>` output
  shape under Vitest 4.1.11, pytest node-ID to JUnit-ID parity on the real
  suite, FFmpeg capability commands, `ImageOS`/`ImageVersion`, artifact upload.
  The first qualification run is the first real exercise.

## Remaining gates (in order)

1. #174 → #193 heavy queue completes; #193 and #184 are Closed and Done and
   integrated on the chosen baseline. Then run
   `npm run roadmap -- ready 196` and claim with the routed profile
   (`model:sol`, `effort:high`). This preparation owner is either the claim
   holder or is released.
2. Rebase or merge this branch onto that baseline. Then run `npm ci`,
   `uv sync --frozen`, `npm run lint:typescript`, the helper tests, and the
   fast/full gates under the coordinator queue. Decide judgment call 3.
3. Push or open a PR only with authorization. Select one reviewed calibration
   commit. Compare collected IDs against retained local full evidence or one
   coordinated local reference run.
4. Run the two full qualification runs on the same source/profile. For the
   first, run `node scripts/cloud-evidence-validate.mjs --draft-profile
   <file> --repo mbelinkie/vera-script-to-timeline --run <id> --attempt <n>`.
   Review that draft (controls, tools, inventory, skips), then evaluate both
   runs, retaining every attempt and its disposition.
5. Write the check-to-platform matrix and local exceptions: Resolve,
   private media, the Mac/#174 tool fingerprint, design/listening. Archive the
   small durable evidence record and write the go/no-go report.
6. Producer activation decision. Only after approval, set `qualified: true`
   with the approval record, then update the verification policy,
   AGENTS/CLAUDE, dispatch prompts and the playbook together.

Until step 6, local full acceptance remains the rule. No result from this
preparation is a cloud substitution, a full regression pass or an activation.
