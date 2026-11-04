# Resolve test queue: M1 offline-only

This is the independent, non-native implementation slice of issue #376.
It does not launch or validate DaVinci Resolve. No output of this service
counts as verified native work, a save/reopen check, or performance evidence.

From a repo checkout bootstrapped with `uv sync --frozen`:

    uv run --frozen python -m vera_timeline_agent.resolve_test_queue enqueue --plan fixtures/resolve-test-queue-m1.json
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue list
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue worker once
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue status resolve-test-<ID>
    uv run --frozen python -m vera_timeline_agent.resolve_test_queue report resolve-test-<ID> --format markdown

Use --at 2026-11-05T23:00:00-05:00 after --plan to schedule a future job.
CLI uses a user-private default queue root under Library/Application Support/VERA.
Override it with --root /absolute/private/test/directory BEFORE the subcommand.
The enqueue response is a unique durable ID; status, report and cancel accept it.
All jobs retain immutable plan.json, status.json, report.json, report.md and
SQLite journal/trials. No model call or terminal remains necessary after enqueue.

On the local logged-in Mac only, explicitly opt in with:

    uv run --frozen python -m vera_timeline_agent.resolve_test_queue install-launchd

This creates an exact user LaunchAgent invoking a single worker pass every
60 seconds and starts it through the user's launchctl domain. launchd cannot
execute while the Mac is asleep/off or while its user domain is not active.
Jobs due during sleep start after the next wake/service tick, if not expired.
A GUI-only Resolve action is still unsupported; native work is not enabled.

To stop the LaunchAgent, as the same local user:

    launchctl bootout gui/$(id -u)/org.vera.resolve-test-queue.m1

To remove it, separately delete only the exact installed
~/Library/LaunchAgents/org.vera.resolve-test-queue.m1.plist after bootout.

A real native adapter is M2 work: it must reserve existing VERA operator
ownership; use #302 guarded-parent operation identity/status; enforce #276
authorization as applicable; verify genuine evidence via the product;
preserve unknown/cancelled live targets; and never treat a mock result,
PID exit or missing receipt as verified native success.

A separate-process CLI smoke on 2026-11-04 produced this example summary
(two synthetic pass trials; timestamps and job ID vary on each enqueue):

```json
{
  "state": "completed_simulated",
  "reason": "all_mock_cases_completed",
  "nativeVerified": false,
  "cancelRequested": false
}
```

This change has not installed the LaunchAgent or qualified logout/reboot
behavior. The opt-in service definition is tested offline. It needs a stable
checkout and Python environment; moving or deleting either breaks its command.
Elapsed limits count time across sleep; absolute deadlines still apply after wake.
Interrupted running jobs become `unknown` on the next worker pass and are never
replayed. SQLite is authoritative; derived reports are regenerated on query.
