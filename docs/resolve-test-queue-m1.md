# Resolve test queue: M1 offline-only

This is the independent, non-native implementation slice of issue #376.
It is unrelated to the GitHub CI/PR merge queue (#361) and does not launch or
validate DaVinci Resolve. No output of this service counts as verified native
work, a save/reopen check, or performance evidence.

From a repo checkout bootstrapped with `uv sync --frozen`:

    uv run --frozen python -m vera_timeline_agent.resolve_test_queue enqueue --plan fixtures/resolve-test-queue-m1.json
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue list
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue worker once
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue status resolve-test-<ID>
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue report resolve-test-<ID> --format markdown

Use `--at 2026-11-05T23:00:00-05:00` after `--plan` to schedule a future job.
The CLI uses a user-private default queue root under
`~/Library/Application Support/VERA/resolve-test-queue`. Override it with
`--root /absolute/private/test/directory` **before** the subcommand.
The enqueue response is a unique durable ID; status, report and cancel accept it.
All jobs retain immutable `plan.json`, `status.json`, `report.json`, `report.md`
and the SQLite journal/trials. `status.json` includes the job state, schedule and
deadline, attempt and worker-run identity, cancellation flag and plan digest.
`report.json` adds the frozen plan's synthetic fixture/target/category identity,
`planIntegrity` (`verified` or `unavailable_or_changed`), the append-only
journal, per-trial rows and explicit `nativeVerified: false` and
`verifiedStatistics: null` markers. No model call or terminal remains necessary
after enqueue, and a later process can rebuild the derived report files from
SQLite.

A checked-in sample produced by `fixtures/resolve-test-queue-m1.json` is in
[`docs/verification/issue-376/`](verification/issue-376/README.md). It is mock
output only, never native or performance evidence.

## Plan contract

Plans are versioned data (`vera.resolve-test-plan/v1`), not shell strings.
M1 accepts only `targetPolicy: synthetic_only`, `synthetic-*` fixture IDs,
`disposable-*` target IDs, at most 32 cases, at most 64 trials, a finite
elapsed-time budget and a finite disk budget. The only adapters are
`mock.pass`, `mock.fail` and `mock.block`; there is no dynamic import, command
adapter, media action or native request path. Every successful mock job ends in
`completed_simulated`, never `completed_verified`.

## Job outcomes

Terminal states are `completed_simulated`, `failed_simulated`,
`blocked_simulated`, `canceled`, `expired`, `timed_out` and `unknown`.
`expired` means the absolute deadline passed before or during execution;
`timed_out` means the job's own elapsed budget was exhausted. `unknown` records
interruption, a missing/changed/unreadable frozen plan, or an unexpected worker
failure, and is never replayed automatically. `blocked_simulated` covers a
declared mock block or the disk budget/free-space guard. A `queued` job is
waiting for its scheduled time; a `running` job with `cancelRequested: true`
has not yet reached its cooperative cancellation boundary.

The plan digest detects accidental or third-party changes to `plan.json`; it is
not a cryptographic trust anchor against the same operating-system user.
Published reports contain only synthetic identifiers, fixed reasons and
timestamps, never the queue root, plan path, home directory or media paths.

## Worker and interruption behaviour

`worker once` claims at most one due job under a per-root `flock`. If a worker
dies mid-job, the next worker records that job as `unknown` with reason
`interrupted_worker_no_replay` and never redispatches it. Cancellation of a
running mock job is cooperative at the next mock boundary; if the worker
crashes first, the job becomes `unknown` rather than a false `canceled`.
Derived report files are written atomically from SQLite, so the database remains
authoritative if publication is interrupted.

## Opt-in macOS user LaunchAgent

On the local logged-in Mac only, explicitly opt in with:

    uv run --frozen python -m vera_timeline_agent.resolve_test_queue install-launchd

This creates an exact user LaunchAgent invoking a single worker pass every
60 seconds and starts it through the user's `launchctl` domain. It refuses to
overwrite a differing or symlinked plist. Re-running installation starts a
matching but unloaded service, or leaves an already loaded service alone.
launchd cannot execute while the Mac
is asleep or off, or while its user domain is not active. Jobs due during
sleep start after the next wake/service tick if they have not expired; the
report keeps the true scheduled and started times and never claims on-time
execution. The LaunchAgent does not wake or resume any AI/chat session; a later
session reads the result by job ID. A GUI-only Resolve action is still
unsupported; native work is not enabled.

To stop the LaunchAgent, as the same local user:

    launchctl bootout gui/$(id -u)/org.vera.resolve-test-queue.m1

To enable it again while the plist still exists:

    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.vera.resolve-test-queue.m1.plist

To remove it, separately delete only the exact installed
`~/Library/LaunchAgents/org.vera.resolve-test-queue.m1.plist` after `bootout`.

## Native work (not this slice)

A real native adapter is M2 work: it must reserve existing VERA operator
ownership; use the #302 guarded-parent operation identity/status; enforce #276
authorization as applicable; verify genuine evidence through the product;
preserve unknown/cancelled live targets; and never treat a mock result, process
exit or missing receipt as verified native success. M2/M3 require their own
guarded prerequisites and real installed-Resolve acceptance, so this M1 module
must not be represented as native support.
