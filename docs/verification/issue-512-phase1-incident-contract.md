# #512 Phase 1 — Test Bench diagnostic contract and seventh-case source map

**Scope:** code and immutable-source audit only. No native case, Resolve SDK, GUI,
carrier, Mac worker, one-use authority, host journal, or existing signed receipt
was invoked, claimed, rewritten or replayed. Phase 2 will add the writer; Phase 3
the read-only inventory/report CLI; Phase 4 independently validates against the
original Mac private case before #499 may consider attempt 8.

## Frozen seventh incident, with explicit evidence limits

- Frozen code: `91e260291ed279a3789e1022afc2e0250c2d5b0a`, source graph
  `cfa1407c14572d1b5135bd1b5ac0b60d7523862054aa4514c30bbdfeaf71bee3`.
  This exact commit is available for offline `git show`/`git cat-file` verification.
- Case `vera499phase26h2426ee095c73443d`, Studio 21.1.1.10; two original
  distinct target-provision receipts and source-preflight attestation were
  observed on the Mac. Launch was claimed and ended `unknown-after-claim`.
- The **prior Mac read-only postmortem** independently authenticated and ingested
  pristine native **0 construct, 1 save_reopen, 2 capture_pre, 3 queue_render,
  4 start_render** (all `complete`). There was **no operation 5 poll_render
  request/result**, no pristine terminal signed M4 receipt, and no edited,
  revision, or rebuild M4 receipt: **M4 0/4; strict #312 not run**.
- This Linux container has the issue, retained `.pipeline/499` pointer,
  bootstrap and read-only scripts, and frozen Git commit, **but not** the Mac
  private seventh-case native files. Thus the five native authentication
  results are *reported findings from the retained Mac audit*, not hashes
  freshly verified here. Their result digests are deliberately **not invented**.
  See `issue-512-seventh-case-map.json`, whose `origin` records the copied
  pointer/bootstrap SHA-256. Phase 4 must independently re-read those native
  result files on the Mac without running their effects.

Reproduce the available portion without side effects, from the repo root:

```sh
git cat-file -t 91e260291ed279a3789e1022afc2e0250c2d5b0a
sha256sum .pipeline/499/phase26h-physical-start.json \
  .pipeline/499/phase26h-bootstrap-result.json
git show 91e260291ed279a3789e1022afc2e0250c2d5b0a:python/vera_timeline_agent/resolve_test_bench_conductor_launch.py \
  | grep -n -A7 'except BaseException'
```

Expected pointer SHA `af593351675d6c47e388a05abfae01d56fdd456a2139cff70295f329f51ee09e`,
bootstrap SHA `31bcfd02533cd932006825acb1c13b35a5b7a9636f2fd793da8aff4ac02eba16`.
The copied bootstrap says `submitted-not-verified`: never mistake it for a
native completion. The root cause is **unknown**, not a proven `poll_render`
bug; it was the first *absent evidence boundary*.

## Frozen-code audit of the five requested seams

| File | Actual immutable/UNKNOWN boundary | Diagnostic attachment in Phase 2 |
| --- | --- | --- |
| `resolve_test_bench_conductor_launch.py` | `start()` fsyncs `launch-intent.json` under separate Conductor lock, calls full loop, catches **`BaseException`**, writes only `unknown-after-claim` and discards exception/trace. | Capture safe error and boundary after durable claim; preserve original result state even if logging fails. No new start/dispatch. |
| `resolve_test_bench_campaign.py` | `start()` checks exact session, release, stage, target, clock and disk; `stage-intent.json` one-use before `output.drive`. `inspect()` is read-only. | Stage admitted/started/terminal diagnostics only; no retry after stage intent. |
| `resolve_test_bench_output.py` | `tick()` validates carrier result then writes host-ingest intent **before** `ingest_native_result`, writes `host-ingested.json` after. A spent ingest intent without receipt is UNKNOWN. `drive()` polls only within original cumulative deadline. | Event boundaries around source preparation, carrier result, host intent/ingest and `queue_render`/`start_render`/`poll_render`, distinguish completed host action vs M4. |
| `resolve_test_bench_carrier.py` | `_once` uses `O_EXCL | O_NOFOLLOW`, file+directory `fsync`; `start()` records native intent before spawning. `status()` verifies original signed result or returns `live`/`unknown`; never redrives. | Record immutable native dispatch and independently authenticated result; don't mirror installed mutable request or touch the shared owner lock for diagnostics. |
| `qualification_output_controller_v2.py` | `_publish` uses exclusive creation, file and directory `fsync`. `OutputAttemptJournal` pending/entry/head CAS rejects partial records. `ingest_native_result` authenticates exact context/sequence; `poll_render` is necessary for render lineage. | Diagnostics cite result SHA and original verifier output but do **not** replace signed result, reservation, MOV/PCM proof, or strict #312 verification. |

`origin/main` at phase start (`3852a5c7`) has `qualification_output_controller_v2.py`,
but **does not yet contain the four named Test Bench orchestrator/carrier files**.
They reside in #499's isolated adopted PR #474 branch. Phase 1 adds an
independently testable pure-contract module on #512; later integration is the
Conductor/#499 owner's task, never an edit to #499's shared worktree here.

## Closed v1 records: diagnostic, not authority

Pure functions `redact`, `exception_details`, `timestamp`, `validate_record`
and `canonical_bytes` live in `resolve_test_bench_diagnostics.py`. They perform
no I/O and **cannot dispatch, verify, approve or replay native operations**.
Each `vera.test-bench-diagnostic/v1` record has exactly these fields:

- `recordIndex`, `previousRecordSha256`: zero-based append position and prior
  canonical record hash, with `null` prior hash only for the first record.
- `kind=stage|exception`, `event` (closed boundary categories: claim,
  admission, preparation, native dispatch, carrier result, verification,
  ingestion, render queue/start/poll/capture, MOV/PCM, inference, M4 receipt,
  strict 312, handoff, origin-thread ACK or exception), `boundary`, `status`.
- `proofLayer=none|process_exit|os_effect|authenticated_native_result|signed_m4_receipt|origin_thread_ack`
  and `proofSha256` (hash when not `none`); even a populated diagnostic is not
  an authenticated proof without the original, independently verified item.
  M4/ACK layers are only syntactically permitted on their own event types.
- `clock={utc,monotonicNs,pid}`; monotonic time is valid for intervals only
  within the same boot/process clock scope; UTC must not be used to infer
  causal order across wall-clock jumps.
- `identity={caseId,jobId,operationId,phase,stage,action,nativeSequence}`;
  all IDs are bounded opaque values, never arbitrary file paths or authority.
- `pins={frozenSourceSha256,actorSha256,targetSha256,authorizationSha256}`;
  absent digests are `null`, never guessed.
- `lastVerified={nativeSequence,action,resultSha256}` or `null`, and
  `nextPending={nativeSequence,action}` or `null`, to preserve what was truly
  observed (e.g. 4 start_render, 5 poll_render missing).
- `evidence`: at most 12 references per record with `role`, `sha256`,
  `sizeBytes` and optional `locatorSha256`; **no literal absolute paths**, raw
  credentials, duplicated MOV/PCM or unrelated home-directory inventory.
- `exception` is only present as a detail object on `kind=exception` (otherwise
  `null`). It contains class name, redacted message max 512 characters, at
  most 16 `file/function/line` frames. File names are basename-only for
  whitelisted Test Bench/output modules; everything else is `redacted.py`.
  Never include frame locals, function source, environment, command line or
  raw traceback strings. **All exception records force `status=unknown` and
  `proofLayer=none`.**

The validator rejects extra/missing fields, malformed hashes and IDs,
unauthenticated proof tier claims, unsafe frame paths and noncanonical record
sizes (max **8192 bytes including the final newline**). Redaction masks URLs,
credentials, email addresses, absolute paths, long tokens and control bytes;
it is deliberately conservative and still requires private storage because
free-form errors can include unforeseen sensitive data. Logs must be scrubbed
before any transport, not merely when displayed.

## Phase 2 writer contract (design; not implemented in Phase 1)

1. Open an owner-only, already-admitted case diagnostic root (`0700`, owner UID,
   no symlinks), distinct from immutable signed/native journal paths. Never
   create it inside old seventh-case root: old evidence is sealed. Do not
   follow any input-supplied absolute output path. Use a single case-bound
   writer lock; reject foreign process/case identifiers and partial records.
2. For new runs only, publish each **fully validated canonical record** as
   `records/record-000000.json` etc with `open(O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600)`,
   full write, file `fsync`, close, parent-directory `fsync`. Verify prior
   SHA and ordinal under lock; never truncate/overwrite or skip an ambiguous
   partial file. The writer is write-once per event, **not** a reopening JSON
   array. `recordIndex` is distinct from native operation sequence.
3. Quota proposal: 8192 records per case (64 MiB maximum structured payload),
   separately bounded 256 MiB total sanitized text logs with 16 MiB per segment,
   and a 1 MiB reserved emergency-error budget. Reuse the existing native
   minimum-free-space reservation, plus a dedicated 256 MiB diagnostic floor.
   Never copy MOV/PCM into incident folders: retain their size, SHA-256 and
   safe locator hashes/inventory refs. The future inventory can be generous
   with external artifact references without storing huge media twice.
4. If fsync, log publish, quota, disk, lock or schema validation fails, **stop
   subsequent native effects**, retain already claimed intent and set or keep
   externally authoritative `UNKNOWN`. On a spent claim, failures to write
   the diagnostic must **not** erase `launch-result.json`, authorize retry,
   or falsely mark the signed M4 receipt. Reserve space where feasible, but
   cannot promise an error record when physically out of disk.
5. Preserve UNKNOWN/FAILED evidence and raw original authenticated source
   until explicitly reviewed retention authorization. No automatic expiry or
   deletion of spent native cases. Success logs may be bounded/rotated by
   explicit generation only; diagnostic record files are immutable.

**No-replay boundary:** `unknown-after-claim` after seventh launch intent,
native operations 0–4 and missing 5 mean *read-only diagnosis only*. A new
freshly authorized attempt 8 may begin **only after** #512 is integrated into
the #499 owner's original PR and separately gated. #510/#511 exact-thread
delivery/ACK remain independent; neither a process exit, OS action, host
receipt nor diagnostic record substitutes for a signed M4 result or thread ACK.
