# Issue #184: fast routine validation

## Scope and boundaries

Add `validate:fast` for implementation iterations: generated-contract currentness,
all TypeScript checks, Python lint/types, and every Python test without `slow`.
Keep `validate` and `test:python` unchanged, including serial execution, strict
markers/configuration, all accepted assertions, and frozen CLI deadlines.
Classify media/process-heavy tests using explicit pytest metadata and retain
per-test measurements from the full gate. No product, contract, fixture, golden,
CI-provider, or acceptance-test assertion changes.

Touched callers/configuration: root npm scripts, pytest configuration and dev
lockfile, test marker metadata, README, AGENTS.md, and CLAUDE.md. No exports or
generated types change. Markers select routine coverage only; full acceptance
continues to discover every test.

## Dependencies

None.

Dependency justification: pinned `pytest-xdist` runs independent non-slow tests
in two worker processes using pytest's existing per-test temporary directories.
Two workers bound host load; language/check phases remain sequential.

## Automated acceptance sequence

1. Retain baseline Python collection and compare exact node IDs after marking.
2. Before any heavy run, check `pgrep -fl "npm run validate|pytest"` and wait for
   other validation/test processes to finish. Never run the full gate alongside
   other heavy work. Ignore read-only agent command lines merely quoting these
   commands; inspect actual executable/arguments when needed.
3. Run the unchanged `VITEST_MAX_WORKERS=1 npm run validate` with reporting-only
   `PYTEST_ADDOPTS="--durations=0 --junitxml=<evidence path>"`. Retain its timing,
   exit status, test counts, and per-test durations. No selection overrides.
4. Run `VITEST_MAX_WORKERS=1 npm run validate:fast` three consecutive times with
   no other heavy test run. Each must pass in under 600 seconds. Review all
   non-slow tests for isolated writable files, ports, and caches.
5. Verify the full npm scripts/strict pytest options and accepted test bodies
   match baseline. Record versions, evidence hashes, commands and timings below.
6. Commit locally and move #184 to review with commands, timings and commit.

Acceptance is Automated per Producer dispatch and issue scope; no manual
Producer repeat is needed. CI, acceptance and agent handoffs use the full gate.

## Slow classification rationale

Markers are explicit module metadata for uniform integration suites and
individual decorators in mixed suites. Existing assertions remain untouched.

| Group | Marked tests | Why slow |
| --- | --- | --- |
| OTIO and Free trial | Package-building OTIO cases; Free trial module | Builds/verifies/copies actual media and repeatedly probes frame counts. Pure manifest and existing-directory refusal stay fast. |
| Resolve import and Studio | Successful/tampered/CLI Resolve package cases; Studio spike cases building or requesting the `package` fixture; Studio assembly cases building acceptance packages | Media materialization/probing dominates even when the Resolve API itself is injected. Pure adapter and early-refusal cases stay fast. |
| Narration | Successful normalizer renders; service cases processing audio; two CLI synthesis/failure-placeholder cases | Real FFmpeg loudness passes, FFprobe, and cache publication/replay. SSML, provider fakes, cache unit tests, profiles, preflight, and validation stay fast. |
| Prepared builds and proof sessions | Prepared-build cases calling `_inputs`; proof-session and driver tests; native-build and recovery modules; capture-retry cases | Actual Node compiler/validator child processes, package checks, repeated durable stage/replay checks. Strict JSON and SDK-import tests stay fast. |
| Row narration and composition | Row-narration cases except SDK import; composition, generation-recovery, omission bridge/decisions/generation/preparation, and WI-flow modules | Whole-row audio normalization, compiler subprocesses, real retained media builds/probes, recovery and CLI replays. |
| Retained audio and fixtures | Retained-audio module; FFprobe metadata and standalone full fixture verification | Decodes retained real render media and probes checked-in fixtures. Schema, inventory, hash and missing-tool behavior stay fast. |
| Process recovery | Build-job process-kill/restart case | Actual child process lifecycle and lease wait; in-process job tests stay fast. |

Small pure-Python PNG and synthetic PCM evidence tests remain fast even though
they handle media bytes: they do not launch renderers or probe packages.
Non-slow tests use per-test `tmp_path` for writable media, SQLite stores and
narration caches. No non-slow test binds a port; monkeypatch state stays in its
worker process. Checked-in fixtures/goldens and publication evidence are read
only. Python workers run after TypeScript exits, so the two languages cannot
race over resources. See pytest-xdist's
[fixed worker count](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)
and [worker behavior](https://pytest-xdist.readthedocs.io/en/stable/how-to.html).

## Measured evidence

Measured on 2026-10-11 on the reference Intel i9-9880H Mac, macOS 15.1.
Versions: Node v24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14,
pytest 9.1.1, pytest-xdist 3.8.0. The measurement runner waited for #180's
validation/pytest processes to exit, polling every three minutes, and checked
again before each run. It ran these four commands sequentially:

| Command | Wall time | Python result | TypeScript/tooling result |
| --- | --- | --- | --- |
| `VITEST_MAX_WORKERS=1 npm run validate` | 3030.992 s (50:31) | 419 passed; 0 skipped; serial | 274 passed |
| `VITEST_MAX_WORKERS=1 npm run validate:fast` (1) | 99.791 s (1:40) | 237 passed; 0 skipped; 2 workers | 274 passed |
| Same fast command (2) | 97.877 s (1:38) | 237 passed; 0 skipped; 2 workers | 274 passed |
| Same fast command (3) | 103.491 s (1:43) | 237 passed; 0 skipped; 2 workers | 274 passed |

Every run also used reporting-only
`PYTEST_ADDOPTS="--durations=0 --junitxml=/tmp/vera184-validation/<run>.xml"`,
where `<run>` is `full`, `fast-1`, `fast-2`, or `fast-3`. No test selection,
timeout, or strictness override was applied to the full gate. Python wall times
were 2979.59 s for the full run and 49.94 / 48.00 / 52.75 s for the fast runs.
The routine target keeps each existing lint, type, currentness, and TypeScript
test command; shell `&&` propagates any failed phase, and pytest returns failure
for a failed non-slow test. Parallelism is confined to Python's final test phase.

The full run's accumulated per-test setup/call/teardown time was 2892.458 s for
the 182 slow cases and 81.600 s for the 237 non-slow cases. Group costs:

| Slow group | Cases | Accumulated seconds |
| --- | --- | --- |
| OTIO and Free trial | 28 | 5.298 |
| Resolve import and Studio | 40 | 8.551 |
| Narration | 12 | 7.860 |
| Prepared builds and proof sessions | 45 | 400.854 |
| Row narration and composition | 53 | 2459.978 |
| Retained audio and fixtures | 3 | 8.742 |
| Process recovery | 1 | 1.175 |

Classification includes short cases in media/process integration groups so
routine runs do not mix renderer/prober and package/CLI replay workloads with
unit tests. The longest case, the actual WI CLI composition/generation/replay,
took 294.054 s. Pure synthetic PCM evidence remains routine coverage (70.278 s
accumulated serially), as do pure adapter, cache, SSML and strict JSON checks.

TypeScript lint/types, Python strict mypy, and Ruff lint/format pass. Collection
matches baseline `f4cc90652c02a40283270ee6ecb32d18983eb3d9` exactly: 419 Python
node IDs. The full JUnit set matches baseline; all three fast JUnit sets match
the same non-slow collection exactly, with no failures, errors, or skips.
An AST comparison strips only slow metadata/pytest imports and confirms all
41 existing Python test modules' bodies and other decorators match baseline.
All 19 existing npm commands match baseline exactly. Contracts, fixtures,
goldens, product code, generated types, npm lockfile, and CI are unchanged.

Retained evidence under `docs/investigations/issue-184/`:

- `full-output.txt` retains the passing full command and `--durations=0` report;
  `fast-{1,2,3}-output.txt` retain the three consecutive passing parallel runs.
- `runs.json` retains commands, start times, wall times, exit codes, counts and
  SHA-256 hashes of all four command logs. SHA-256:
  `9990afe5b734cdbd1d71b3634e82dfad074a388a4140aeca8c160f920c54a0f1`.
- `python-durations.tsv` retains all 419 full-run node IDs with per-test
  setup/call/teardown time and slow classification. SHA-256:
  `abfa2bdb81c515402681fa9ea373c83ba64de19911b00746be248c426fbf3594`.
- `coverage-audit.json` retains baseline identity, exact collection/set checks,
  unchanged-command checks, normalized test AST hashes, and module timing sums.
  SHA-256: `405c438419cf453b5c85467c41e77bdf41c1e007cbb47afd5a69a948ff81652f`.

All four acceptance criteria are evidenced. Workflow steps are documented in
AGENTS.md, CLAUDE.md and README.md. The full gate remains the acceptance and
handoff command; routine results alone never replace it. No manual Producer
check or unresolved implementation decision remains. The implementation task
will leave #184 In review for the requested handoff, without closing it.
