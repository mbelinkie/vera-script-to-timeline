# Calibration round 1: complete passing runs, refused as a qualification baseline

Head `ea5db6c20f83c5e95b97477cf5ec9cc4b8493827`, tested tree
`7c5ea7bcf3508ca93b5fd673cc547d9a527ebb71`, attempt 1 of each run:

| | Run A | Run B |
| --- | --- | --- |
| Event | push | pull_request #198 |
| Run | [38291149935](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38291149935) | [38291234081](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38291234081) |
| GitHub conclusion | success | success |
| Checked-out commit | `ea5db6c` (head) | `992485c8` (merge: parents `98b9a614`, `ea5db6c`) |
| Tested tree | `7c5ea7bc` | `7c5ea7bc` |
| Queue | 3 s | 3 s |
| Job total | 39:55 | 29:59 |
| `npm run validate` step | 38:42 | 28:51 |
| pytest (JUnit) | 499 passed, 0 skipped; collect-only parity 499 | same |
| Vitest | 402 + 1 passed; `vitest list` 403 | same |
| node:test | 6 + 23 + 31 passed, 0 skipped | same |
| Tracked files modified | none | none |
| Collection | complete | complete |

Both runs used the same tools:

- Node v24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14;
- ubuntu 24.04 on x64, runner label `ubuntu-24.04`, image `20261004.327.1`;
- FFmpeg/FFprobe 6.1.1-3ubuntu5, package `7:6.1.1-3ubuntu5`;
- binary SHA-256 `ed16af62…` (ffmpeg) and `272f6ebc…` (ffprobe), capability
  digest `41778d36…`.

The 24 control digests and the input trees are identical across the runs.

Retained here:

- `round1-manifest-A.json` and `round1-manifest-B.json`: the manifests
  exactly as downloaded from the run artifacts;
- `round1-run-*.json`: GitHub run and job step metadata;
- `draft-run-A.log` and `draft-run-A.exit` (exit 1): the refused draft.

## Why round 1 cannot qualify

`--draft-profile` refused the run (`malformed-profile: inventory.vitest must be
a nonempty list of unique IDs`). Vitest abbreviates `it.each` values in
display names, so `vitest list` reported 403 tests under only 396 distinct
names. The duplicated names include "refuses invalid selected IDs
[ Array(1) ]" in `issue-144-text-revision.test.ts` and a path-argument case in
`prompter-export-cli.test.ts`. The fail-closed check was correct. Counting
alone cannot identify those tests.

The fix numbers repeated names in declaration order (` #2`, …), at collection
time. That edits evidence helpers, which are qualified controls. So round 1's
controls cannot match any profile that includes the fix, and two fresh runs
on the fixed tree are required (round 2).

## Local hypothetical simulation (not an approval)

A local script applied the same numbering to the round-1 manifests. It built
a profile from run A plus run B and gave it a placeholder approval
(`by: HYPOTHETICAL-LOCAL-SIMULATION`). It then evaluated both runs. The
results:

- Both runs passed with no failures and no suspended scope.
- Limitations reported: `history-scope` and `outcome-by-step-only`, plus
  `checkout-attested` for B.

The real-data assumptions all held: `run.path` is exact; the job has labels,
`runner_name` and `run_attempt`; the branch-filtered history works; `vitest list
--json` works; the PR merge parentage is as expected. This simulation is not
an approval, it is not retained as a profile, and it qualifies nothing.
