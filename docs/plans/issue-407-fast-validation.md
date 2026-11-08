# #407 — Fast validation: measurements, coverage, and bounded optimization

## Purpose and measurement contract

The routine `npm run validate:fast` keeps the original **seven phases in order**, with fail-fast nonzero child status propagation and monotonic per-phase wall timing from `scripts/validate-fast.mjs`. It runs only the existing fast selectors, generated-contract freshness, linters, and typechecks. `npm run validate` is unchanged and remains **cloud-CI-only**, never a local Mac acceptance gate.

Benchmarks are on the **native Intel Mac** with the Zodex virtualization VM running, Node 24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14, `VITEST_MAX_WORKERS=1`, pinned frozen uv dependencies, and Python `-n 8 --dist=worksteal`. Set `TMPDIR="$(cd "$TMPDIR" && pwd -P)"` to resolve macOS's `/var/folders` → `/private/var/folders` symlink; otherwise the existing, correct backup-archive symlink guard refuses the test fixture. This fixes the test **environment**, not the safety guard or test timeout.

Baseline source was the unmodified `f0aa770e996135f16c37e90428688071deaab8d4` checkout. The optimized candidate consists of two local commits atop that source plus the final issue-specific test/stability correction, copied byte-for-byte into a **separate native Mac worktree**. The Linux-mounted Git worktree's `.git` pointer is invalid on macOS, so it must not serve as the Mac performance checkout. No competing native #473 driver was detected at test launch; neither the VM nor native Resolve ownership was stopped or altered.

## Before and after

| Fast phase | Original native Mac, seconds | Optimized native Mac, seconds |
| --- | ---: | ---: |
| Generated TS/Python contracts freshness | 2.925 | 2.939 PASS |
| TypeScript ESLint | 38.114 | 39.596 PASS |
| TypeScript typecheck | 17.232 | 17.343 PASS |
| TypeScript fast test suites | 188.299 | 133.203 PASS |
| Python Ruff checks | 0.855 | 0.848 PASS |
| Python mypy | 79.104 | 86.871 PASS |
| Python fast pytest | 128.612 PASS | 161.254 FAIL (2,831 passed, 1 failed) |
| **Total** | **455.142 PASS** | **442.059 FAIL** |

The biggest baseline cost was **188.299s** of **serial** TypeScript fast workspace tests. The original eight workspace `test:fast` commands and their exact exclusions/inclusions remain unchanged. New `scripts/fast-workspace-tests.mjs` runs the independent suites in a bounded three-worker pool while retaining dynamic workspace discovery, the no-unclassified-test-workspace guard, and fail-stop/drain behavior. The existing development-QA backup/restore workspace is deliberately **serialized ahead of the parallel batch**: its 5s guard tests use multiple real subprocesses and are sensitive to simultaneous CPU-heavy tests on the reference Mac. It still runs the same complete fast test script; no timeout was increased.

On the same Linux environment, the original serial TypeScript phase was **328.004s**. Early parallel checks ran in approximately **142.3s**, repeated in **146.88s**, with all eight workspace suites passing and the same **1,388 Vitest tests**. These are comparative Linux-only timings, **not** native Mac performance measurements.

A first Mac parallel attempt without isolation completed contracts **4.576s**, TS lint **38.262s**, TS types **17.171s**, but failed TS tests after **96.989s**: the one existing `project-service-host/test/backup-guards.test.ts` negative-path test exceeded its 5s timeout under contention. It was **not** a valid all-phase success or a basis for claiming <300s. In response, this issue added a narrow exclusive scheduling barrier and a regression test proving no workspace was lost or doubled. The rerun is the authoritative after result; the isolated workspace passed without increasing its timeout. However, the seventh phase failed in an unrelated, pre-existing Python concurrency test (evidence below).

## Selection and safety proofs

- Fast Python collection, before and after: **2,832 exact node IDs selected** from 3,493 discovered (661 deselected). The original Linux snapshot, original native Mac baseline, and native Mac after selection are byte-identical. The `-m "(not slow) or fast"` expression, `-n 8 --dist=worksteal`, native-owner isolation and subprocess safety were not changed.
- All eight existing npm fast workspaces, their `test:fast` commands and exclusions remain present. Full npm `test:typescript` additionally runs the new timing and runner regression tests; the fast command runs them too.
- Reversibly corrupted the phase-timer short-circuit, the workspace completeness guard, and the scheduler's fail-stop condition one at a time. Each causes focused regression assertions to fail. Restoring each source file makes the focused suites pass again. The scheduler regression was hardened so a broken guard fails promptly instead of waiting forever on an unresolved Promise.
- `scripts/validate-fast-lib.mjs` preserves all seven script names/order and stops at the first error, including missing executable and invalid child statuses. Generated-contract `--check` still regenerates and compares both languages; no timestamp shortcut was added.
- Linux Python worker diagnostic retained selection: `-n 8` took **116.26s** and `-n 4` **148.53s**. Linux-specific missing media executables and subprocess differences produced unrelated failures under both settings, so neither Linux Python result is a passing Mac acceptance claim; `-n 8` was kept.

## Reproduction and evidence

From the optimized checkout with pinned npm/uv dependencies:

```sh
node --test scripts/validate-fast.test.mjs scripts/fast-workspace-tests.test.mjs
npm run check:contracts-generated
uv run --frozen pytest -m "(not slow) or fast" --collect-only -q
VITEST_MAX_WORKERS=1 npm run validate:fast
git diff --check
```

The conductor's ignored `.pipeline/407/` ticket folder retains the original native Mac `mac-quiet-fast.log`, `mac-quiet-baseline-env.txt`, `mac-quiet-nodeids.txt`; the failed first attempt under `mac-after-first-attempt-*`; the final `mac-after-fast.log`, `mac-after-env.txt`, `mac-after-nodeids.txt`; and four negative mutation/recovery `phase3-mutation-*.log` / `phase3-restored-*.log` pairs.

## Python seventh-phase failure: independently reproduced on original code

The after-run completed **six phases PASS** and then **2,831 passed / 1 failed** in pytest after 160.10s of pytest execution (161.254s phase wall). The sole failing node ID was `tests/test_local_media_import.py::test_concurrent_same_id_publishes_once`. Both attempts to create `.vera-local-import.lock` under a project-scoped directory can race: `os.open(..., dir_fd=project)` at `python/vera_timeline_agent/local_media_import.py:597` sometimes raises `FileNotFoundError`, later surfaced as `ImportModelError("source_unavailable")`. No Python source, selection, native ownership or import data-integrity guards changed in #407.

To establish that this is **not caused by the TS workspace scheduler**, the same **single focused test** was run three times on the original unmodified native Mac checkout and three times on the optimized checkout, with identical canonical TMPDIR and pinned uv. Results: **original 2 failures / 3 trials; optimized 1 failure / 3 trials**. Logs are in `phase3-import-race-original-{1,2,3}.log`, `phase3-import-race-optimized-{1,2,3}.log`, and `phase3-import-race-summary.txt`. The original source had also passed the test during its complete seven-phase 455.142s baseline: this is an **intermittent pre-existing failure**, not a deterministic regression or authorization to weaken the check. It needs a separately scoped data-integrity/race repair.

The optimized native Mac gate therefore **cannot be described as an all-green pass** or as achieving 300s. Its observed **442.059s** includes the failing seventh phase. Relative to the original passing 455.142s, the measured TS test phase improved by **55.096s**, but Python tests took **32.642s longer**, and mypy took **7.767s longer**. These two nonidentical outcomes are evidence of a high, variable runtime floor, not a claimed repeatable end-to-end success.

## Acceptance and next bounded action

First repair/reproduce the original Python import-lock concurrency race as its own narrowly scoped ticket, preserving its lock, ownership, and source-verification guarantees; then rerun the **same seven-phase** native-Mac fast gate without changing selections. After that all-green baseline, profile the slowest Python pytest tests and mypy cold-cache cost on a comparable idle Mac and optimize the largest measured avoidable component, retaining exact node IDs, data-integrity guards and the fast/full boundary. Neither increasing the failing test's deadline nor moving its coverage into the cloud-only suite would be an acceptable shortcut.

The independent `npm run review -- ../../.pipeline/407/review-notes.md` was attempted once, but the Claude CLI hit its weekly quota without returning review findings. A complete self-review, focused regression tests, four negative mutations and restoration checks were performed. The cloud-only full `npm run validate` remains untouched and the required `TypeScript and Python` CI check must still pass before merging.
