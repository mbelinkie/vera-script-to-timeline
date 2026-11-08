# M4 — Guarded same-target reverse workflow (#466)

M4 is a **separate** finite state machine on the M1/M2/M3 private queue root.
It does **not** reinterpret an M2 build or any M3 independent campaign trial as
proof that an editor changed a timeline. M4 coordinates one output-host
`pristine → edited → revision → rebuild` sequence. The existing reviewed v2
output host, not the coordinator or an arbitrary script, creates and verifies
all native operations, owner locks, render/PCM records, approval decisions,
source currentness and signed one-use revised-build reservations.

M4 currently uses an explicit **human-required host handoff at each stage**.
The ordinary queue worker advances the *control state*, not the Resolve GUI.
This is deliberate: an automation-free editor change is not equivalent to an
authenticated `observe_edited` readback. The operator performs the specific
reviewed output-host flow, and M4 accepts no progress until the complete host
lineage is reauthenticated. Do not run an ad-hoc shell/GUI workaround, issue
new operation IDs to recover from UNKNOWN, or operate on Producer media.

## Prepare a brand-new synthetic session

Use only Mac-host-approved local files. First complete the existing output
preparation process (see `docs/qualification-output-v2.md` if present and
`python/vera_timeline_agent/workflow_v2_cli.py` for the exact installed
`output-prepare`, `output-authorize`, `output-next`, `output-ingest`,
`output-finalize`, `output-edited`, `output-proof`, `output-proof-step`, and
`output-revised` contracts). The initial `output-prepare` is **pre-native**:
prepare the session but do not yet launch any native request. Its context must
say phase `pristine` and bind the explicitly approved new synthetic target and
case ID. Never use the old #312 PR #323 project, original operation IDs, or
producer source files. Use the original media/voiceover fixture and native
source hashes; never fabricate a pristine or edited capture.

**Automatic Test Bench setup (no manual project creation):** The output host's
`construct` action requires a genuinely existing *empty* project/timeline
with real Resolve `GetUniqueId()` values. Use the dedicated, one-use native
provisioner rather than asking the Producer to create anything in the UI:

```sh
export TEST_RUN="$HOME/Library/Application Support/VERA/resolve-test-bench/provision/<new-test-run-id>"
uv run --frozen python -m vera_timeline_agent.resolve_test_queue_m4_provision \
  --root "$TEST_RUN" run
```

Replace `<new-test-run-id>` with one unique, unused private run directory.
`run` reserves two distinct `VERA Delivery <UUID> <12-hex>` names, uses the
supported Resolve project/timeline creation APIs, sets the 23.976 frame rate
**before** timeline creation, saves and reads back both actual independent
UID pairs, and leaves the initial target selected. Use
`resolve_test_queue_m4_provision.completed(Path(TEST_RUN))` to obtain the
read-only `{initial, fresh}` target records for the M4 plan and output-host
session; neither the CLI nor the agent may invent native UIDs.

The provisioner journals a one-use intention *before* each native effect.
`run` is idempotent after complete success, but an incomplete intent is UNKNOWN
and will **not** create or reuse that target on retry. Inspect the exact
private run record; do not blindly delete, retry or repair a partially created
project. No attempt can modify or save an existing Producer project. After
pristine/edit/revision is fully authenticated, the operator controller can
select the reserved fresh project using `select-fresh` (then check the M4
preflight); `select-initial` restores the first test target. Selection refuses
any currently selected Producer project, unknown work, active render, or
wrong UID. No ad-hoc Resolve GUI scripting is involved.

M4 performs a distinct **read-only, exact-UID selected-disposable preflight**
for every stage; it requires an empty timeline and no render jobs for pristine
and rebuild, and an exact selected project/timeline with no active or uncertain
native work for edited/revision. This does **not** weaken M2's separate
not-yet-created target preflight, change retained historical UNKNOWN state,
authorize editing Producer projects, or manufacture authority. An unresolved
operation on the selected target, a live native-owner lock, a foreign selected
project, or unexpected timeline content is a refusal.

An M4 plan is one JSON object, no executable command field:

```json
{
  "schema": "vera.resolve-test-reverse-plan/v1",
  "name": "m4-312-reverse",
  "caseId": "synthetic-312",
  "baselineSession": {
    "path": "/ABSOLUTE/PRIVATE/NEW/pristine/session.json",
    "sha256": "<SHA256 OF EXACT SESSION BYTES>"
  },
  "initialTarget": {
    "projectUid": "<NEW HOST TARGET UID>",
    "timelineUid": "<NEW HOST TIMELINE UID>",
    "projectName": "VERA Delivery <UUID> <12-lowercase-hex>",
    "timelineName": "VERA Delivery <SAME UUID> <SAME 12-hex>"
  },
  "freshTarget": {
    "projectUid": "<DIFFERENT NEW UID>",
    "timelineUid": "<DIFFERENT NEW UID>",
    "projectName": "VERA Delivery <DIFFERENT UUID> <DIFFERENT 12-hex>",
    "timelineName": "VERA Delivery <SAME DIFFERENT UUID> <SAME DIFFERENT 12-hex>"
  },
  "maxElapsedSeconds": 14400,
  "maxDiskBytes": 1073741824
}
```

The `<...>` strings are placeholders **only**, never a valid plan or evidence.
Generate new unrelated target identities on the Mac. The initial output-host
session must authenticate the pristine target in the plan, and no sequence-0
native result may already exist. The fresh target is reserved immediately and
may never alias the pristine target or an M2/M3 reservation. Case, target,
plan, host session and cryptographic references are frozen on enqueue.

`runAt` and `deadlineAt` are optional timezone-aware ISO-8601 UTC times, with
the same scheduling semantics as M1. M4 has its own maximum of four hours for
the operation window; this is **not** a #312 timed benchmark. Check the separate
four-hour **cumulative measurement** ledger in #312 before any new benchmark.
The Producer's below-40-GiB override is respected: there is no arbitrary
40-GiB threshold, but the actual bounded free-space requirement still applies.
Mount the external drive before preparing or submitting evidence if relevant.

## Queue and stage handoff

Use the existing private queue root in the same Mac user account:

```sh
export QUEUE="$HOME/Library/Application Support/VERA/resolve-test-queue"
uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
  --root "$QUEUE" enqueue --plan "$PRIVATE_M4_PLAN"
# Save the printed resolve-reverse-... ID and let the installed queue worker tick.
uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
  --root "$QUEUE" status "$M4_JOB_ID"
uv run --frozen python -m vera_timeline_agent.resolve_test_queue \
  --root "$QUEUE" report "$M4_JOB_ID"
```

The normal queue worker also advances M4; `resolve_test_queue_m4 worker-once`
is an optional single diagnostic tick, protected by the same worker lock.
Only **one** stage at a time becomes `awaiting_operator`. The stage's durable
`operation_id` and timestamp are recorded in SQLite before any host effect.
While an M4 stage has unresolved native intent, normal M2/M3 native dispatch
is fenced; mock jobs can still run. A stale, failed, partial or unknown result
does not clear a historical operation or authorize a new request.

Read the stage `operation_id` in the private `report.json` and perform only
the corresponding reviewed output-host operations:

1. **pristine:** Use the existing output host's reviewed build/terminal path
   on the newly authorized disposable target. Complete genuine save/reopen,
   pre/post native capture, signed render, decode and terminal PCM comparison.
2. **edited:** Use `output-edited` on the **same** project/timeline UID. Change
   only the adjoining held-picture boundary **327 → 351** (+24 frames),
   preserving all other item/media/audio identities, original program end,
   11 events, six tracks, 1407 frames at **24000/1001**. If no supported
   Resolve API can make the edit, pause for a human editor action; then run
   `observe_edited` and the reviewed host native readback/PCM sequence. Do not
   insert a manufactured geometry snapshot.
3. **revision:** Use the reviewed output proof's real inference, explicit
   inference acceptance and explicit accepted script revision. No provider
   spend without a separate approved budget. Do not treat a proposed revision
   or rejected inference as acceptance.
4. **rebuild:** Use `output-revised` with the already accepted proof, signed
   *one-use* revised-build reservation, the independently authorized fresh
   target and a newly admitted package. Complete genuine save/reopen/readback,
   final authenticated native capture, render, decode and PCM comparison.

After the host has settled, write the **canonical** sorted-key compact JSON,
newline-terminated, to the one exact private queue receipt path:
`$QUEUE/$M4_JOB_ID/receipt-<stage>.json`. Use the per-stage `operationId` from
the private M4 report, never copy it into a second job:

```json
{
  "schema": "vera.resolve-test-reverse-receipt/v1",
  "stage": "pristine",
  "operationId": "<ENROLLED STAGE OPERATION ID>",
  "session": {"path": "/PRIVATE/HOST/session.json", "sha256": "<SHA256>"},
  "capture": {"path": "/PRIVATE/HOST/final-result.json", "sha256": "<SHA256>"}
}
```

`edited` and `rebuild` use the same receipt shape with their own session and
capture refs. `revision` uses `proof` (path and SHA-256 to the actual output
proof session) instead of `session` and `capture`. All stage files must be
regular, non-symlinked, single-linked, private and no larger than 16 KiB.
The host itself verifies larger/related immutable evidence, source and effect
chains. A wrong operation ID or invalid receipt is not correctable by replay.

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_queue_m4 \
  --root "$QUEUE" submit "$M4_JOB_ID"
```

`submit` pins the exact receipt bytes to SQLite *before* verification. A crash
while checking them can be reconciled by the original job's `status` or
`resolve_test_queue_m4 reconcile`, which rereads only those pinned bytes and
does not issue a native request. `cancel` before any stage intent is safe;
cancel after intent becomes UNKNOWN and requires manual host inspection.
The work is not green until **all four stages** are individually verified and
the final imported strict #312 verifier reauthenticates both native captures,
the exact +24 geometry, inference/accepted revision, new signed build
reservation, and independently decoded PCM.

## Evidence and #312 continuation

If and only if the terminal state is `completed_verified`, the queue writes
`$QUEUE/$M4_JOB_ID/handoff-private.json` (mode 0600). This preserves the
actual stage receipt paths/hashes and all host artifact references without
publishing private media locations to GitHub. Attach sanitized hashes and the
host's bounded acceptance summary to the pipeline handoff. Continue the
**existing #312 phase 2/5** worktree/PR #323; do not restart #312, replay its
native requests, or count unrelated raw job timestamps as timed benchmarks.
#313 follows only after #312 is proven and accepted. A Linux-only unit test or
M4 stage marked `awaiting_operator` is not native success.
