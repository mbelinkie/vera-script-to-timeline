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

The parent, injected launcher, output entry point and #328 bridge share a host
ownership lock. The detached parent worker inherits that lock. The queue and
external parent perform a host-only check of retained parent, output-render and
bridge reservations as well: a released OS lock
does not clear an unresolved native operation. Known terminal native results
and authenticated expired unstarted requests are distinguished from unresolved
render work; records are never deleted to make a new job eligible. Old installed
bundles must be regenerated from the current runtime before use; a pre-M2 bundle
does not gain the new guard merely because the queue was upgraded.
Other entry points retain their existing lane-specific authorization and recovery
checks and refuse a live or unresolved guarded parent. Standalone non-output
writes also refuse retained render reservations, using the same journal validator
as the host controller. The output lane can continue its own approved chain.
The installed guard uses only stdlib; it does not load the host output controller
inside Resolve.

### Paused historical output queues

An old `queue_render` result with an uncertain `Project.AddRenderJob` effect is
**not** a completed render and cannot be retried or rewritten. When its original
Producer has explicitly paused that work, an operator may use the separate
`python -m vera_timeline_agent.resolve_native_owner --observe-paused-queue
<exact-original-result.json>` command with local Resolve scripting to observe
the **original** project and timeline by unique ID. The observation fails closed
if any render is active/unknown, any job has a nonterminal status, the old
output still has a matching queued job, or the native request/result/history
cannot be authenticated. **The operator must already have the exact original
project and timeline selected**; the observer never calls `LoadProject` or
switches the UI, and never queues, starts, removes or saves a render.

The immutable private observation records the old result digest, complete host
journal digest, original project/timeline identity, observed job statuses and
time. It is MAC-authenticated using that output chain's private host receipt
key and expires after twelve hours. A fresh observation gets a new
digest-qualified file; old evidence is never deleted or reclassified. Only an
exact unchanged historical tail and a current authenticated observation can
make an *independent new disposable target* eligible under the owner protocol.
The old result remains UNKNOWN; an expired observation, any changed retained
chain or mismatched observation restores the refusal. This is isolation of
quiescent **queued-only** work, not native completion proof or permission to
resume the old job. Human changes to the Resolve UI outside VERA are not
controlled by the queue; no one should start an old render while testing.

The installed Resolve launcher uses a self-contained stdlib owner guard and
small journal/observation checks. It must **not** import the full host output
verifier, which is absent from some installed runtime inventories. The host
queue and guarded parent retain their stronger full historic verification
before a new dispatch. When old retained sources live on external storage,
macOS background privacy permissions must allow the scheduled worker to read
them. A LaunchAgent's `Operation not permitted` is a **blocked prerequisite**,
not a reason to waive historic authentication or fabricate success.

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
`blocked_native` means the case did not qualify for verified completion; `unknown` means the
native outcome cannot be established. v1 success remains
`completed_simulated` with `nativeVerified: false`.

Cancellation before dispatch ends the job. After intent it requests attention
while the native operation continues to reconcile. Finite deadline, elapsed and
disk budgets similarly never imply a live native operation has stopped. A
live/uncertain over-budget job records that condition; authenticated completion
after the budget is `timed_out`, with any actual native verification retained
privately in the parent evidence; the queue does not mark the case verified.
Completion time comes from that authenticated parent, so later observation or
sleep does not turn on-time completion into a timeout. Finished evidence must
still fit its disk budget; unrelated free-space changes after completion do not
downgrade it. These are observation/refusal limits, not an OS kill or a promise to
recover disk space. Partial projects, existing media and raw evidence are kept.

Reports contain synthetic fixture/target identifiers, hashes, journal, one-use
attempt and parent identities, native verification and explicit limitations.
Private request locators and target/media paths stay in private plan/SQLite/raw
evidence. Hashes detect changed bytes; they are not a trust boundary against
someone controlling the same operating-system account. No render/PCM proof or
performance claim follows from this build case.

## Acceptance

Native acceptance is pending. The last host-only ownership
preflight refused with `output_operation_unresolved`: retained native effect
records lack authenticated completion. No #447 Resolve operation was started,
and no retained reservation was cleared or retried. The independent offline
package passes the compiler/package verifier (one 25-frame video event at
25 fps, one media item, no markers); that is host evidence only.

On November 5, 2026, live verification was stopped at the Producer's direction
while the retained-evidence drive is disconnected. Resume only after the drive
is available and existing operations can be authenticated without retry or override.

The future-scheduled LaunchAgent native case, actual save/reopen/readback,
and later worker-restart reconciliation must pass before #447 is delivered.
