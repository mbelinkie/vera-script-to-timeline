# Issue #196 cloud validation qualification

Status: Producer-authorized same-owner execution, 2026-10-12. This is not
qualification success, cloud substitution or activation. Local full
acceptance under [VERIFICATION_POLICY.md](../VERIFICATION_POLICY.md) remains
the rule until the Producer explicitly accepts a qualified scope. Plan:
[cloud-validation-qualification.md](cloud-validation-qualification.md).
The live checkpoint is
[docs/verification/issue-196/CHECKPOINT.md](../verification/issue-196/CHECKPOINT.md).

- Owner: the existing Claude Code session `85843512-9132-4b84-9c1e-86173c4de542`.
  It runs task `claude:33ed0ca5-fcd6-4650-9bfd-63db45ef7a11` with
  `claude-opus-5-5` at high effort, under the Producer's same-owner provider
  exception. This was not an ordinary `roadmap claim` model match, and the
  routing labels (`model:sol`, `effort:high`) were not changed.
- Branch: `claude/issue-196-cloud-validation-prep`. Merge commit `4f49b55`
  integrates accepted origin/main `98b9a614` (#193 / PR #197, with #184's
  `70e8435`), the preparation commit `d2720d9`, the plan (byte-identical to
  `7ff426f`) and the policy text (`5ab39b2` plus one trailing blank line).
- Not carried: `5ab39b2`'s one-paragraph policy pointers in `AGENTS.md`,
  `CLAUDE.md`, `README.md` and the coordination skill. The auto-mode
  classifier blocked edits to agent-instruction files in this session, so
  this owner did not apply them. They are pending for an authorized editor.

## Scope

| File | Purpose |
| --- | --- |
| `.github/workflows/validate.yml` | Media-tool preflight, reporting-only JUnit/durations/teed log, evidence collection/upload, PR concurrency, exact acceptance command |
| `scripts/cloud-evidence-lib.mjs` | Parsing, control digests, profile validation and the fail-closed evaluation |
| `scripts/cloud-evidence-collect.mjs` | Workflow-side manifest collector (records only, never judges) |
| `scripts/cloud-evidence-validate.mjs` | Local CLI: read-only GitHub facts → scoped verdict, or an unqualified calibration draft |
| `scripts/cloud-evidence.test.mjs` | Focused tests; GitHub responses are stubbed and the collector uses a temporary git repository |
| `package.json` | `test:cloud-evidence`, appended to `test:typescript` so the full gate runs the helper tests |
| this document, `docs/verification/issue-196/` | Qualification record, logs and checkpoint |

Excluded: product code, schemas, generated types, contracts, fixtures,
goldens, accepted tests, timeouts, test selection or sharding, lockfiles and
new dependencies. The helpers use only Node built-ins.

## Workflow changes

- The step runs `VITEST_MAX_WORKERS=1 npm run validate` unchanged. It now uses
  `shell: bash` with `set -o pipefail`, and its output is teed to
  `$RUNNER_TEMP/vera-evidence/validate.log`, so the gate's exit status stays
  authoritative. GitHub-hosted steps are not TTYs either way, so piping does
  not change tool output modes.
- `PYTEST_ADDOPTS=--junitxml=… --durations=25` is reporting-only. The
  collector re-runs plain `pytest --collect-only -q` without it, and the
  validator requires identical IDs.
- **Preflight required media tools** fails before the gate if `ffmpeg` or
  `ffprobe` is absent, so the frozen FFprobe skip path cannot silently pass.
- Collection and upload run with `if: !cancelled()`. Only `manifest.json` is
  uploaded (as `vera-validation-evidence-attempt-N`, `actions/upload-artifact`
  v7.0.1 pinned to `043fb46d…`). The raw JUnit, the teed log, the worktree,
  caches and the environment are never published.
- Concurrency: a newer push to the same PR cancels that PR's older run. Push
  runs are keyed by commit, so post-merge integration runs are never
  cancelled.
- Unchanged: the triggers, `contents: read`, the existing pinned actions, the
  90-minute limit, the lockfile check and test selection.

## Evidence authority

The manifest records only what the run consumed:

- the checkout commit and tree, and the PR head and base;
- the tracked files the gate modified (`git status`, NUL-delimited);
- control blob digests and input tree IDs;
- runtime and media tool fingerprints, and the runner image;
- pytest JUnit identities and outcomes;
- the Vitest listed IDs;
- runtime outcomes parsed from the gate's own output: Vitest run summaries,
  and node:test names and counts per `node --test` invocation.

`evaluateCloudEvidence` fails closed. It passes only when all of these hold:

- **The profile is valid.** Profile schema v2 must be structurally complete:
  - the exact command;
  - control SHAs including the workflow;
  - every runtime and media fingerprint;
  - at least one accepted runner image;
  - nonempty, unique pytest, Vitest and node:test inventories;
  - reasoned skip-allowlist entries;
  - recorded calibration runs.

  It must also be `qualified: true` with an approval that has `by`, an ISO
  `at` and a `reference`, and whose `profileDigest` equals the SHA-256 of the
  canonical profile content. Editing any qualified field after approval
  breaks that binding.
- **The run and job are confirmed by GitHub for that exact attempt:**
  - the run is the `Validate` workflow at `.github/workflows/validate.yml`,
    `completed` and `success`, with the expected event;
  - it is in the same repository (fork runs are unqualified) and linked to
    the expected PR;
  - it has exactly one `TypeScript and Python` job;
  - every required step concluded `success` and no other step failed;
  - the job carries the qualified runner label.
- **The tested tree is the delivered tree.**
  - For a PR, GitHub's commit object for the checked-out commit must be a
    merge whose second parent is the run head.
  - For a push, the checked-out commit must be the run head.
  - The tested tree must equal the delivered tree.
  - The gate must have modified no tracked file.
  - A base that moved after the event is reported (`pr-base-moved`).
  - The merge commit is named by the collector and corroborated by GitHub
    (`checkout-attested`).
- **Controls come from GitHub's own recursive tree.** Truncated listings are
  rejected. Any added, removed or changed control fails as `control-drift`,
  so a changed gate cannot self-certify.
- **History is clean.** Every attempt of every Validate run on the same tested
  source is checked: the same head SHA, or the same branch with an identical
  head tree (a recommit). Each non-success attempt needs a disposition (class,
  explanation and evidence). Accepted dispositions are returned in the report
  for the reviewer. Incomplete sibling runs and multi-page histories fail.
- **Outcomes are complete and passing:**
  - pytest: zero failures and errors, every skip allowlisted, counts that
    match its IDs, and reporter parity;
  - Vitest: summaries that sum to the listed count, with no failed, skipped
    or todo tests;
  - node:test: per-invocation names that match its counts, with no failed,
    cancelled, skipped or todo tests;
  - every required ID present.
- **Tool profile matches.** Runtime drift fails everything. Media-tool or
  runner-image drift suspends the `media-sensitive` scope only.

The CLI exits 0 only if the report covers the requested `--scope`. The
default is `full`, and a suspended media scope fails it; pass
`excluding-media-sensitive` to accept pure-logic scope only.
`--draft-profile` writes a draft only from a clean, complete calibration run
on its own tree. Drafts are always `qualified: false`, `approval: null`, with
an empty skip allowlist. Every caller identifier (repository, run, attempt,
PR, tree, manifest commit) is validated before any `gh` subprocess or API path
uses it.

### Limitation categories reported to reviewers

| Code | Meaning |
| --- | --- |
| `outcome-by-step-only` | Lint, type checks and generated-currentness are proven by the GitHub step conclusion. Test runners have per-test or per-summary outcomes. |
| `checkout-attested` | GitHub's run API does not expose the PR merge SHA. The collector names it; GitHub corroborates its tree and its head parent. |
| `pr-base-moved` | The merge commit's base differs from the event's base SHA. Tree equality with the delivered tree still decides. |
| `history-scope` | Identical content on a *different* branch is not searched. |
| `prior-failure-dispositioned` | Each accepted disposition is listed for reviewer audit. |
| `inventory-added` | Tests beyond the qualified inventory passed but were not part of qualification. |
| `media-tool-drift`, `runner-image-changed` | Media-sensitive scope is suspended. |

Also known, by design:

- A job timeout or cancellation skips collection (`!cancelled()`). The run is
  rejected regardless, and GitHub's step timing remains readable.
- Vitest IDs come from `vitest list`; runtime proof is the summary counts
  matching that list.
- Output-shape assumptions are confirmed only by the first real run, and an
  unmet one fails as `incomplete-collection`, never as a pass. They are:
  `vitest list --json`, the Vitest 4 summary line, Node 24 spec output, pytest
  node-ID↔JUnit parity, and the run-list `branch` filter.

## Review findings and disposition

These come from the independent preparation review
(`docs/investigations/claude-frontier-2026-10-12/issue-196-preparation-review.md`
in the primary checkout).

| Finding | Disposition | Regression test |
| --- | --- | --- |
| Spec 1 / Standards 2: empty or malformed inventory, incomplete calibration | `profileProblems` rejects empty or duplicate inventories, missing controls, command, fingerprints and calibration. Drafts come only from a clean calibration. | "rejects malformed profiles…", "CLI drafts only…" |
| Spec 2 / Standards 1: alternate gate configurations | Per-directory basename matching covers ruff, mypy, pytest, tox, setup.cfg, conftest, tsconfig, eslint, vite/vitest, `.npmrc`, `uv.toml`, `.gitattributes` and pyproject. The three tracked nested `ruff.toml` files (`output/`, `docs/investigations/issue-141`, `issue-149`) are real ruff controls. | "treats every gate configuration…", "a changed or added control…" |
| Spec 3 / Standards 4: source-scan skips, root Node tests | Source scanning removed. Runtime Vitest summaries and node:test results (including all root `scripts/*.test.mjs`) are parsed from the unchanged gate's output, so conditional markers are judged by actual outcome. | "reads runtime outcomes…", "rejects runtime Vitest and node:test skips…" |
| Spec 4: history keyed by head SHA, not tree | Adds same-branch runs whose head tree is identical, and states the remaining `history-scope` limit. | "gathers every earlier attempt on the same tested source…" |
| Spec 5: weak approval/disposition | Approval needs `by`/`at`/`reference` and a matching `profileDigest`. All accepted dispositions are returned and flagged. | "an unqualified, unbound or edited profile…", "…accepted dispositions stay visible" |
| Spec 6: post-gate cleanliness | Collector records tracked modifications; the validator fails `tracked-state-changed`. | "rejects a gate that changed tracked files…", collector test |
| Standards 3: media-suspended CLI success | `--scope` is required to be `full` by default; suspended media fails it. | "CLI success is scoped…" |
| Standards 5: identifiers reach API paths | Strict validation runs before any subprocess or request, and the tests assert that no request is made. | "CLI rejects malformed arguments…", "…or malformed identifiers" |
| Standards 6: PR provenance | Base parent compared; `checkout-attested` stated. | "requires the PR merge commit…" |
| Standards 7: quoted paths | `git ls-tree -z` / `git status -z` parsing. | "reads NUL-delimited tree…", collector test with `naïve dir/ruff.toml` |
| Standards 8: timeout/cancellation | Documented. The run is rejected either way, and `always()` was not adopted. | n/a |
| Standards 9: collector seam | `collectEvidence` takes an injectable command runner. It is tested against a real temporary git repository. | two collector tests |

## Check-to-platform matrix (proposed; activation decides)

| Gate | Cloud qualified run (ubuntu-24.04) | Remains local / External / Producer |
| --- | --- | --- |
| Generated-currentness, TypeScript/Python lint and type checks | Eligible substitute | — |
| Vitest, root node:test, pure-logic pytest (contracts, validators, compiler, take rules, build jobs, recovery with fakes) | Eligible substitute | — |
| Compiler byte-identical goldens (existing assertions on unchanged goldens) | Eligible substitute | Golden/fixture changes still need their approved change note |
| Synthetic-media and subprocess tests (`slow`-marked FFmpeg/FFprobe integrations) | Regression evidence under the qualified Ubuntu media fingerprint; scope suspended on drift | Changes to media-processing code: affected slow tests serially on the Mac's installed tools |
| Dependency or lockfile changes | Clean `npm ci` / `uv sync --frozen` on Ubuntu | Local Mac pinned `npm ci` / `uv sync --frozen` (macOS-native optional packages such as `fsevents`) |
| Control-file changes (workflow, tool configs, evidence helpers, manifests) | Not eligible: `control-drift` | Local full gate, plus requalification of the profile |
| #174 installed Mac media-tool qualification | Not certified | External, local Mac |
| Real Resolve runtime / native operations (tests use fake SDK modules) | Not certified | External, local |
| Private media, transcripts, provider calls | Never in CI | External, local, under existing privacy gates |
| Listening, visual quality, design | Not applicable | Producer |

## Checks completed in execution

| Check | Result |
| --- | --- |
| `node --test scripts/cloud-evidence.test.mjs` (Node v24.19.0) | 31/31 pass |
| Mutation sanity (7 safeguards disabled one at a time in job-temp copies) | Each fails ≥1 test |
| Parser on the retained #193 log and real Node 24 piped output | Vitest 402 + 1, node:test 6 + 23, and 31 parsed exactly |
| Pinned `npm ci` / `uv sync --frozen` on the integrated tree | exit 0 / 0; lockfiles unchanged (`docs/verification/issue-196/`) |
| `npm run validate:fast` | Attempt 1 exit 1 (ESLint on the new scripts, fixed); attempt 2 exit 0: Vitest 402+1, node:test 6+23+31, ruff/mypy clean, 317 non-slow pytest passed |

## Local reference reuse (#193)

`docs/verification/issue-193/validate-final.*` covers candidate `98847b97`:
a full local gate, exit 0, Node 24.19.0, npm 11.17.0, uv 0.12.5, Python
3.12.14, Intel macOS. Results: pytest 499 passed in 54:03, Vitest 402 + 1,
node:test 6 + 23, no skips. That candidate differs from `98b9a614` only in
`docs/verification/issue-193/*` evidence files, which no gate reads. It is
therefore the inventory and timing reference for every product test. It is
not evidence for this branch's workflow, helpers or `package.json` change,
and it is Mac-platform evidence, not Ubuntu.

## Remaining gates

1. Required independent review of the delta against `98b9a614`, then fixes
   and delta checks.
2. Commit, push the branch and open a PR. This is authorized by the
   coordinator's instruction but blocked in this session by the auto-mode
   classifier.
3. Calibration run 1 on the PR. Draft the profile with
   `node scripts/cloud-evidence-validate.mjs --draft-profile <file> --repo mbelinkie/vera-script-to-timeline --run <id> --attempt <n>`.
   Compare its inventory with the #193 reference (pytest 499 + any added,
   Vitest 403, node:test 29 + 31).
4. Calibration run 2 on the same source and profile. Evaluate both runs, and
   record every attempt and its disposition.
5. Write the go/no-go page and the durable evidence archive in
   `docs/verification/issue-196/`.
6. Producer activation decision. Only after approval: set `qualified`,
   `approval` and `profileDigest`, then update the policy, AGENTS/CLAUDE, the
   dispatch guidance and the playbook together.
