# Guarded native test queue (M2)

Implementation for #447 extends [the M1 queue](resolve-test-queue-m1.md) with an
explicit `vera.resolve-test-plan/v2` plan. v1 remains mock-only. v2 permits
exactly one `native.v2.guarded_build` case, one trial, and a
`new_disposable_native` target. It requires an independently verified synthetic
v2 package and an existing, explicitly authorized normal guarded request.

## Prepare and schedule

Prepare an importable offline synthetic v2 package through the existing compiler
and package verifier. Fake unit-test media bytes are not importable evidence.
Use [the normal v2 workflow](resolve-parent-delivery-v2.md) to attest the package,
create the current release, and prepare a fresh request with `--action build`,
`--authorize-new-nonproduction`, and `--external-scripting-local`. This queue does
not grant that authority or convert a qualification-output approval into it.

With locally assigned private paths, prepare a plan without touching Resolve:

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_queue prepare-native \
  --request "$REQUEST" --output "$PLAN" --at "$RUN_AT" \
  --max-elapsed-seconds 900 --max-disk-bytes 67108864
uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
  --root "$QUEUE" enqueue --plan "$PLAN"
uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
  --root "$QUEUE" install-launchd
```

`RUN_AT` is an ISO-8601 time with a timezone. Keep the returned job ID. The
existing opt-in LaunchAgent runs one worker pass every 60 seconds. It refuses to
overwrite a differing installation. The submitting process may exit; later
processes use `--root "$QUEUE" status "$JOB"` or `report "$JOB"` to retrieve the
durable result. `status` and `report` only reconcile an existing native attempt;
they never launch it. The checkout and its virtual environment must remain
available while the installed worker points to them.

The Mac must be awake and logged in, with supported Studio already reachable
through its existing Local scripting preference. The queue does not open a GUI,
change preferences, wake the Mac or drive dialogs. After sleep, scheduling keeps
the true scheduled/started times; an expired unstarted job never dispatches.

The private plan pins request bytes and installed slot, release and attestation
digests, the exact fresh target, and digests/counts for the package view,
events, settings, markers and media. Current package and runtime bytes are
rechecked before dispatch and reconciliation. Plans cannot supply commands,
interpreters, dynamic imports, private data uploads or automatic retries.

## Recovery and reports

The queue records dispatch intent and immutable request identity before calling
the existing guarded parent. Every subsequent worker only reconciles that same
operation. Live or uncertain work is never replayed, including after cancellation
or a deadline. Private request paths and raw application evidence stay local;
published queue reports contain only sanitized identities and outcomes.

An exclusive intent file also binds the request to its queue job/attempt, so a
second queue root cannot adopt another job's native result. The actual parent
invocation is pinned on reconciliation. Missing or changed intent, input,
invocation, result or result hash leaves the attempt unknown and retains all
artifacts. A later worker may authenticate that same operation; it never starts
a replacement.

`completed_verified` requires the existing parent's authenticated native result:
the expected v2 build, matching target and request context, supported native
rate, save/close/reopen, full declared readback and zero discrepancies.
`failed_native` requires an authenticated mutation/readback failure.
`blocked_native` means no verified build was performed; `unknown` means the
native outcome cannot be established. v1 success remains
`completed_simulated` with `nativeVerified: false`.

Cancellation before dispatch ends the job. After intent it requests attention
while the native operation continues to reconcile. Finite deadline, elapsed and
disk budgets similarly never imply a live native operation has stopped. A
live/uncertain over-budget job records that condition; authenticated completion
after the budget is `timed_out`, with any actual native verification retained
separately. These are observation/refusal limits, not an OS kill or a promise to
recover disk space. Partial projects, existing media and raw evidence are kept.

Reports contain synthetic fixture/target identifiers, hashes, journal, one-use
attempt and parent identities, native verification and explicit limitations.
Private request locators and target/media paths stay in private plan/SQLite/raw
evidence. Hashes detect changed bytes; they are not a trust boundary against
someone controlling the same operating-system account. No render/PCM proof or
performance claim follows from this build case.

## Acceptance

Native acceptance is pending. This document will record the supported route,
commands and the actual unattended acceptance result before delivery.
