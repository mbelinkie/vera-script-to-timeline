# Issue 193 verification

## Scope and repair

The only implementation change is `package-lock.json`: add the local npm
workspace link for `packages/word-timing` and record its existing name/version
metadata. No package versions, registry dependencies, manifests, contracts,
fixtures, tests, or Python files changed. The dependency-free workspace uses
the same lockfile link pattern as the other local packages.

The baseline failure is recorded in [issue #193](https://github.com/mbelinkie/vera-script-to-timeline/issues/193):
at `5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`, Node `v24.19.0` / npm
`11.17.0` clean `npm ci` failed before dependency download with `Missing:
@vera/word-timing@0.1.0 from lock file`. The issue also records that
`npm ci --workspaces=false` failed at baseline. That variant was not rerun
after repair; the acceptance criterion is ordinary clean `npm ci`, and no
post-repair result for `--workspaces=false` is claimed.

## Clean install and generated check

The acceptance install ran in disposable checkout
`/tmp/vera-issue193-disposable` at base
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`, with the repaired lockfile copied
in (SHA-256 below), using pinned Node `v24.19.0` and npm `11.17.0` on macOS:

- `rtk proxy npm ci` — exit `0`; raw output and checkout/runtime metadata are
  retained in [npm-ci-disposable.log](npm-ci-disposable.log) and
  [npm-ci-disposable.exit](npm-ci-disposable.exit). It installed 148 packages
  and audited 152.
- A second clean install in the implementation worktree also passed; its raw
  output and exit receipt are [npm-ci.log](npm-ci.log) and
  [npm-ci.exit](npm-ci.exit).
- `rtk npm run check:contracts-generated` — exit `0`; raw output retained in
  [generated-current.log](generated-current.log) and
  [generated-current.exit](generated-current.exit).

npm printed four high severity audit findings from the locked dependency tree;
the lockfile repair adds no registry dependency or package version. Advisory
work is outside this issue's scope.

## Fast gate and focused review

The focused gate completed once with exit `0` using
`rtk npm run validate:fast` (background runner PID `74714`) on branch
`codex/issue-193-workspace-lock`, base HEAD
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`, and repaired lockfile SHA-256
`e615667b1bcbea53bb34c4db11a6ca6a2745fae5edac6538ff87d3fdfe35d7b8`. Runtime:
macOS (`darwin`), Node `v24.19.0`, npm `11.17.0`, Python `3.12.14`, two pytest
workers. The exact output and exit receipt are retained in
[validate-fast.log](validate-fast.log) and [validate-fast.exit](validate-fast.exit).
Results: generated types current;
TypeScript lint and type checks passed; Vitest 402 contract + 1 tooling-smoke
tests passed; progress and roadmap Node tests passed (6 + 23); Ruff and format
checks passed; mypy passed for 111 files; 317 fast Python tests passed.

Claude Code `2.1.296` performed the requested read-only focused review of the
lockfile, manifests, evidence, and criteria. It found no lockfile blockers and
no implementation defects. It identified the final serial gate and evidence
provenance as pending. The review prompt, output, and exit receipt are retained as
[claude-review.prompt](claude-review.prompt),
[claude-review.log](claude-review.log), and
[claude-review.exit](claude-review.exit). A read-only review of the evidence
corrections found no blockers; its prompt, output, and exit receipt are
[claude-delta.prompt](claude-delta.prompt), [claude-delta.log](claude-delta.log),
and [claude-delta.exit](claude-delta.exit). Neither review made edits.
The final review found no blockers and one optional wording ambiguity, which
was removed; its prompt, output, and exit receipt are
[claude-final-delta.prompt](claude-final-delta.prompt),
[claude-final-delta.log](claude-final-delta.log), and
[claude-final-delta.exit](claude-final-delta.exit).

## Input hashes

| File | SHA-256 |
| --- | --- |
| `package.json` | `bee227c8878b8c15e5f5ef714813dfcb7a2ac628e764cdced384d7e7bf57d6bc` |
| `packages/word-timing/package.json` | `4547221dd55c4007dcc91c852e7d3e40b06b5f170ddaa349ea3c0e9cdb3721a7` |
| `package-lock.json` | `e615667b1bcbea53bb34c4db11a6ca6a2745fae5edac6538ff87d3fdfe35d7b8` |

The two manifests match their recorded hashes and were unchanged by the repair.
The repaired lockfile diff contains only the two expected workspace records.

## Final required gate

Pending one complete local run of
`PYTEST_ADDOPTS=--durations=25 VITEST_MAX_WORKERS=1 npm run validate` after
this reviewed candidate. Save the exact tested revision, command, toolchain,
process/log provenance, and exit receipt here. Keep the issue open until it
passes.
