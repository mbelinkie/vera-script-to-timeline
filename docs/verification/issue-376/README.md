# #376 M1 sample job and report

These files are a real output of the M1 offline queue, generated on
2026-11-04 from the checked-in `fixtures/resolve-test-queue-m1.json` plan by a
single `worker once` pass. They are inspectable without DaVinci Resolve because
every case uses the hard-coded `mock.pass` adapter.

- `sample-status.json` — the stable `status.json` a later process can read.
- `sample-report.json` — machine-readable report with the immutable plan
  identity, journal, trial rows and explicit unverified markers.
- `sample-report.md` — the short human summary.

The job ended `completed_simulated`. `nativeVerified` is `false` and
`verifiedStatistics` is `null`: this is not Resolve evidence, not a
save/reopen proof, and not a performance result. Do not cite it as any of
those.

To regenerate an equivalent private sample in a disposable directory:

    uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
        --root /absolute/private/test/directory enqueue \
        --plan fixtures/resolve-test-queue-m1.json
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
        --root /absolute/private/test/directory worker once
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
        --root /absolute/private/test/directory list

The job ID and timestamps differ per run; the fixed reasons, classifications
and unverified markers do not. SQLite in the queue root remains authoritative
if the derived report files are removed; the next status/report request
rebuilds them.
