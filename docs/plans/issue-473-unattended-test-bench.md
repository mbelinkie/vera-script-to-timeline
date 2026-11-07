# #473 — One-start Resolve Test Bench: implementation and acceptance ledger

## State of this branch

**Draft implementation; NOT an accepted #312 M4 run.** This branch was created
from a freshly fetched `origin/main`, separate from #312, #472, the existing
PR #323, historical operation IDs, and retained evidence. All new native
operations use disposable project/timeline identities and an existing VERA
Delivery v2 signed request chain. There are no live Studio receipts from this
branch and no claim that the Test Bench has completed unattended acceptance.

The remaining hard blocker is a **genuine in-place 327 → 351 roll edit** that
preserves the two original picture timeline-item UIDs and every unrelated
media/audio UID. Resolve **21.1.2** added `SetLeftOffset` and `SetRightOffset`,
but a reported live Studio 21.1.2 test found `SetLeftOffset` moved a clip to
a large negative frame and changed its duration despite returning `True`.
Neither setter is empirically qualified for M4. A delete-and-reappend
approximation would change UIDs and is therefore **not a valid workaround**.
This is not permission to modify arbitrary Producer timelines or script the
Resolve console. The implementation intentionally returns
`blocked_unattended_native_roll_edit_not_proven` after any verified pristine
stage rather than fabricating an edit or claiming final completion.

References: [Resolve 21.1.2 TimelineItem API](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.2/resolve_api/TimelineItem)
and [live destructive offset report](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336).

The issue author explicitly permitted investigating Hammerspoon or another
helper. Such a fallback still needs a deliberately bounded, UID-pinned,
one-use operation with independent native before/after readback and empirical
proof that the exact two item identities are retained on the actual Studio
version. No untested GUI action is enabled in this branch.

## Implemented reusable building blocks

1. `resolve_test_bench_carrier.py`: source-and-request hash verification,
   global native-owner lock, selected disposable target preflight, durable
   intent-before-effect, preservation of previous installed request,
   atomic installation of the **exact** reviewed request, one detached worker
   using the supported `DaVinciResolveScript` API, and authenticated
   read-only status. UNKNOWN/partial/lost results cannot be dispatched again.
2. `vera_test_bench_native_worker.py`: clean, standalone Python process that
   launches only the repository-reviewed installed v2 bootstrap. It imports
   no host controller or untrusted scripting content. The v2 bootstrap
   independently authenticates installed source, request, authority,
   package, release, target, and one-use operation before any effect.
3. `resolve_test_bench_output.py`: automatic, bounded one-use output-host
   sequence. Issues narrowly scoped approval only using a real attributed
   Producer instruction and the existing `issue_operator_approval` contract.
   Prepares the next official host request, starts the one-use carrier,
   checks the original result and action identity, renders/polls/decodes via
   the existing host, and refuses to re-run uncertain PCM finalization.
4. `resolve_test_bench_m4_runner.py`: one-start disposable two-project setup
   through `resolve_test_queue_m4_provision` only **after** checking actual
   disk headroom and running the existing read-only public v2 package verifier;
   a pinned pristine host session,
   durable original M4 job enrollment with enqueue-crash reconciliation, the
   existing serialized M4 worker gate, the output chain driver, and an
   immutable original M4 receipt submitted to its **existing verifier**. A
   required exact #472 fix commit must be an ancestor of both the checked-out
   branch and fetched `origin/main`, without locally changed verifier source,
   and contain the source-range correction before any native work.
5. `resolve_test_bench_edit_probe.py`: automatic **read-only** post-pristine
   SDK inspection requiring an authenticated terminal session/capture and
   exact selected disposable target. Compares all eleven item UIDs, media
   UIDs, positions, durations, linked identities, six tracks and idle state
   with the genuine pristine geometry. Records current Resolve version and
   offset-method availability, but never invokes any edit setter. The probe
   receipt is immutable and tied to the exact original session/capture pins.
   The one-start controller runs it automatically and remains blocked until
   a separate sacrificial trial proves a safe same-UID editing route.

The controller never attempts to sign a Producer design decision. Consent
attribution is **not** a claim of cryptographic transcript authentication;
the trusted local caller must pass the actual instruction it received.

## One initial action — guarded launch contract

The trusted conductor prepares one private JSON config, based on the already
approved synthetic package and actual Producer instruction. The Producer
should not need to manufacture the config or administer each operation. The
runtime accepts only the following closed configuration shape:

```json
{
  "schema": "vera.test-bench-one-start/v1",
  "root": "/absolute/private/new-run-root",
  "queueRoot": "/absolute/existing/M4-queue-root",
  "name": "test-bench-312",
  "caseId": "synthetic-312",
  "packageRoot": "/absolute/approved/verified-v2-package",
  "profile": "verified-v2-package/v1",
  "maxElapsedSeconds": 14400,
  "maxDiskBytes": 1073741824,
  "consentReference": "https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
  "consentInstruction": "Use the actual Producer instruction received; not a fabricated quote",
  "merged472Commit": "<actual 40-hex SHA of merged #472 verifier correction>"
}
```

The example contains **placeholders** and must not be submitted as-is. The
conductor should use a real absolute private root, actual existing package,
and the actual merged fix SHA. The approved launch command is:

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_bench_m4_runner start --config /absolute/private/config.json
```

Run inspection without any native effects:

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_bench_m4_runner inspect --config /absolute/private/config.json
```

`start` is **fail-stop** while #472 remains unmerged, or when source hashes,
native owner, real disk, target selection, consent, or any old operation are
unresolved. All limits are bounded, all identity pins are immutable, and the
same original M4 job must be reused after an interrupted enrollment.

## Remaining engineering before this issue is accepted

- Merge and integrate #472's authentic source-range correction; verify on
  current Mac Resolve Studio without changing #472-owned verifier/test files
  in this branch. The current source-range issue cannot be hidden as success.
- Build and empirically qualify one native **same-UID** timeline boundary-edit
  route, preferably product-supported. Do not call the 21.1.2 offset setters
  on the sole M4 target based only on method presence. First prove semantics
  on a *separate new sacrificial disposable* project under the native owner.
  A Hammerspoon helper must also be audited, disposable-only, one-use, and
  independently measured before it can be qualified as an alternative.
- After pristine, run that verified 327→351 edit on the *same* project and
  timeline, then automatically prepare and verify the edited output session
  and its original M4 stage receipt.
- Compute observed reverse inference through the existing proof controller;
  apply only decisions actually authorized by the Producer's explicit policy.
  An unresolved creative or semantic decision fails closed, never defaults
  to `accept`.
- Admit the genuinely revised package, perform its signed one-use fresh target
  reservation, select the independently created fresh timeline, and run the
  full rebuild/render/PCM/readback chain through the same native carrier.
- Submit all **four** authentic M4 stage receipts; run the final
  `verify_reverse_receipts` #312 acceptance and publish the existing private
  handoff. Only then may the conductor unblock #312 and proceed to #313.

## Regression / mutation expectations

Focused tests never open Resolve or substitute mock evidence as an accepted
result. Failure injection covers wrong target, wrong operation, altered
request, independently rejected native result, partial/UNKNOWN/lost result,
spawn failure after intent, replay refusal, symlinked run roots, clean-runtime
SDK launcher, no historical adoption, unowned/native-started operations,
unreviewed consent, #472 merge gate, queue enrollment recovery, one-use M4
receipt mutation, and no downstream edits when upstream proof is absent.

Commands:

```sh
uv run --frozen pytest -q tests/test_resolve_test_bench_carrier.py tests/test_resolve_test_bench_output.py tests/test_resolve_test_bench_m4_runner.py tests/test_resolve_test_bench_edit_probe.py
npm run validate:fast
```

Do not use full `npm run validate` locally. Do not modify #472 verifier tests,
clear historical M4 operations, mark #312 complete on fake data, or convert
this draft PR to ready merely because isolated tests pass.

## Local validation and independent review status (November 7, 2026)

- **46 isolated fake-host/SDK/controller/edit-probe tests passed.** `ruff` and full
  `mypy python tests` passed with no typing findings.
- `npm run validate:fast` was run after `npm ci`. It did **not pass**:
  `packages/contracts/test/qualification-output-proposals-v2.test.ts` had
  three timeouts under the normal four-worker gate (the other 50 contract
  test files passed). An isolated, one-worker rerun of this **unmodified**
  TypeScript test file also timed out (four cases, 26 passed). The branch
  changes only Python, Python tests and this document; no TypeScript code or
  tests were edited or their timeouts relaxed. Treat the gate as red until
  the upstream CI/environment failure is diagnosed.
- The required **one** `npm run review -- notes.md` adversarial review was
  attempted and could not run: Claude CLI reported its weekly usage limit
  (reset November 9 at 15:00 UTC). The draft PR remains pending independent
  code review; no review approval is claimed.
- No live Resolve Studio run was attempted. Issue #472 remained open when
  checked. Full native M4 success and #312 completion are **not verified**.
