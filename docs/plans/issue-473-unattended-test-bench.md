# #473 — One-start Resolve Test Bench: implementation and acceptance ledger

## State of this branch

**Draft implementation; NOT an accepted #312 M4 run.** This branch was created
from a freshly fetched `origin/main`, separate from #312, #472, the existing
PR #323, historical operation IDs, and retained evidence. All new native
operations use disposable project/timeline identities and an existing VERA
Delivery v2 signed request chain. A full **real** pristine Studio 21.1.1.10
seven-operation chain with MOV/PCM comparison was later completed under
`issue-473-studio-05`. Its pinned first M4 stage was nevertheless correctly
marked **unknown** by the then-current incompatible native-frame-rate
representation guard. Neither the immutable M4 receipt nor original native
results are replayed, rewritten or backdated; unattended #312 acceptance is
**not** achieved. A fresh distinct campaign must re-prove the corrected gate.

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
   disk headroom, running the public v2 package verifier, verifying the exact
   six published #312 matrix preparation receipts, and reauthenticating the
   *three* original measured narration/cache artifacts. The Mac launch service
   must expose the independently verified **pinned Node 24.19.0**, **npm
   11.17.0** and **uv 0.12.5** binaries in `PATH` before even starting a costly
   source admission or native project.
   A fresh, private,
   write-once **complete package admission is performed before provisioning**:
   an interrupted or refused preflight cannot create any Resolve project and
   cannot be replayed on the same root. The later target-bound session repeats
   independent admission, with no shortcut around v2 source currentness;
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
  "narrationEvidenceRoot": "/absolute/approved/original-narration-campaign",
  "profile": "qualification-output-studio-matrix/v1",
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

- #472's source-range correction is merged and independently accepted on
  Resolve Studio 21.1.1.10. This branch has merged the corrected main and
  the official SDK self-replacing-module bootstrap fix from `39cf3114`.
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

- **135 focused contracts/controller/M4/native-carrier/edit-probe tests passed**
  after the render-source fixes. `ruff` and full
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
- **Real Mac native check (Nov 7, 19:27 Eastern):** verified direct connection
  through official Studio 21.1.1.10 SDK; independently validated the retained
  11-event public V2 synthetic package; created two *new* disposable projects
  under `~/.local/state/vera/issue-473-studio-01/run/provision` with original
  one-use journal receipts. The run then failed during output admission with
  `first smoke profile requires one actual picture/source-audio pair`: the
  closed config had incorrectly selected the two-event smoke profile instead
  of #312's 11-event **studio matrix**. A subsequent launch-service execution
  correctly refused to reuse the already-created incomplete session root with
  `new output session root required`. The launch job `vera-473-test01` was
  immediately removed; no `construct` or other #473 native-effect intent was
  dispatched. **Do not reuse** this run root, provisioned targets or session.
  The fixed profile and six published preparation-receipt checks are now
  required *before* creating any further disposable project.
- **Second distinct Mac-native campaign:** new root
  `~/.local/state/vera/issue-473-studio-02` passed the exact six published
  preparation-receipt checks and provisioned two new disposable Studio
  targets, but target-bound admission refused
  `measured narration requires its timing and measurement artifact paths`.
  Removed the `vera-473-test02` launch job before any native construct and
  retained all original one-use project/target records. The missing three
  **original** narration artifacts were located in the existing #312
  `rehearsal-speech-v1` campaign; the new closed `narrationEvidenceRoot`
  input and strict source-derived timing/measurement pins now route them to
  independent admission **before** any new project creation. Neither spent
  campaign is reused or represented as a successful M4 stage.
- **Third distinct Mac-native campaign:**
  `~/.local/state/vera/issue-473-studio-03`, using original exact published
  6 preparation/3 narration evidence bindings, **passed both** source-only
  and target-bound authenticated admission (sealed before any effects) and
  auto-provisioned two new disposable Studio targets. It then failed **before
  native construct** with `locked node unavailable`. The `launchctl submit`
  environment omitted Node from PATH, although the Mac has the pinned Node
  `v24.19.0` executable. Auto-restarted job correctly refused the already
  spent preflight root; removed `vera-473-test03`, no native operation was
  dispatched and no original evidence or target was reused. The next fresh
  launcher must set the pinned Node 24 directory first, and
  `_require_pinned_node` now prevents an incorrect launch-service PATH from
  creating any new Resolve project.
- **Fourth distinct Mac-native campaign:**
  `~/.local/state/vera/issue-473-studio-04` successfully used pinned Node
  24.19.0, performed its fresh sealed source-only and target-bound admission,
  and independently provisioned two new Studio targets. It then refused
  before constructing any native clip with `locked uv unavailable`: the
  launch-service PATH had the Node folder but omitted `~/.local/bin` (the
  installed verified `uv 0.12.5`). The original one-use directory and
  disposable targets remain retained, and `vera-473-test04` was removed.
  The controller now validates all three host runtime versions (Node, npm,
  uv) before provisioning, and the next fresh launch needs both the pinned
  Node and user-local uv directories in its PATH. The old run is not retried.
- **Fifth distinct Mac-native campaign (first real native effects):**
  `~/.local/state/vera/issue-473-studio-05`, on Studio 21.1.1.10, with
  verified Node 24.19.0 / npm 11.17.0 / uv 0.12.5 runtime, passed the sealed
  source preflight and target-bound admission, provisioned **two new** exact-UID
  disposable targets, enrolled a real M4 plan and authenticated **three
  complete, distinct, one-use native results** on the initial target:
  `construct` (sequence 0), `save_reopen` (1) and `capture_pre` (2), each with
  `host-ingested.json` status `complete`. The real native target key is
  `3dbdd327c8bfc4e6c7c842f288924bc4e28bd4a39d9b646404a01ffc174687bc`
  under the existing official private host/native vaults. The host then
  prepared the signed `queue_render` request (sequence 3) and entered its
  legitimate `reserved_by_render_intent` state. The carrier's generic
  `preflight_selected_disposable` rejected that **same target's own active
  output-host reservation** with `Resolve is owned by another VERA operation
  or is unresolved`. **No sequence-3 carrier intent or native effect was
  issued** (`native-03/` contains only its empty lock). No render was queued.
  An independent read-only inspection of `_active_output_host_chains(None)`
  confirmed this target's own chain as `reserved_by_render_intent`; the
  preflight currently unconditionally treats every active chain on the
  selected project as foreign, including its own valid render intent. This
  is a genuine integration safety incompatibility, not a reason to clear a
  lock or force execution. Removed launchctl job `vera-473-test05` and
  confirmed no Test Bench worker was still running. All original operation
  IDs, requests, results and complete/partial evidence remain preserved.
  **Next:** a separately reviewed, exact-request-and-job scoped, stage-aware
  read-only owner preflight that permits only its authenticated own render
  intent, while refusing foreign/uncertain owners and unknown/active render
  jobs. Do not monkeypatch, clear the owner, reuse this target or replay
  sequence 3. Real render/PCM and final M4 are not yet proven.
- **Original campaign 05 continuation, Nov 7:** Recovered via the **exact
  frozen commit** `3ea32582`, with the original sealed source graph hash
  `1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc`.
  A separate hash-pinned, read-only stage-aware owner guard was used solely
  through the original carrier's explicit preflight parameter; the actual
  native effects, source verifier and operator-approval envelope remained
  original and signed, not patched. `queue_render` (3), `start_render` (4),
  `poll_render` (5) and `capture_post` (6) each obtained **distinct, genuine,
  complete** Studio results and authenticated ingestion, with no replay of
  operations 0–2. The actual Resolve job was `Complete`, 100% (11,434 ms).
  An exact scope-and-consent bound post-render approval was necessary because
  the old `issue_operator_approval` mistakenly required the MOV to be absent
  even when the next fixed action was `poll_render` or `capture_post`; this is
  now corrected in the new code with four regression cases. The original
  controller then returned `terminal_native_verified` after source/geometry,
  render, decode and PCM comparison and submitted its original pristine M4
  receipt. The launch job was removed; the exhausted native action plan
  correctly refused the launch service's next invocation.
- **M4 independent refusal is immutable:** job
  `resolve-reverse-6d7e20fad0b64b418d6a94930526557d` marked the pristine
  stage `unknown` / `unverified_stage_do_not_replay`. Live authenticated
  `capture_post` geometry has `rate={"numerator":24000,"denominator":1001}`,
  `extentFrames=1407`, 11 real items and six tracks. The old M4 and reverse
  boundary validators erroneously required the **string** `"24000/1001"`,
  despite the canonical verified native rational-object encoding. The new
  code strictly accepts only the exact rational object, not arbitrary strings
  or approximations, with mutation checks for extra fields/wrong rates.
  **Never reclassify the spent M4 job as verified or resubmit its receipt**.
  New source admission and fresh M4 IDs are mandatory to prove acceptance.
- **Attempt 06** was refused by its own safety preflight during disposable
  creation because campaign 05's legitimate render reservation was still
  active. No #06 native effects were dispatched; its launch job was removed.
- Full four-stage M4 and #312 acceptance remain **unverified**. Same-target
  identity-preserving 327→351 edit and revised fresh rebuild are still pending.

## Conductor adoption: phase 1 read-only native-state reconciliation (2026-11-07)

This is an evidence snapshot of the **existing** campaign, not a new acceptance
attempt. Original draft PR #474 was adopted at exact source commit
`920adcac979a575672cf4fae5d5fad2de7adb7f8`, without replay, reset, new
Resolve targets, or changes to the original Codex branch. On the Mac, the
frozen original native host checkout at
`~/.local/state/vera/issue-473-studio-05/pinned-code` independently returned
`3ea32582a6761ead588762ba2df2f95bf80bd8e9` from `git rev-parse HEAD`.
The originally recorded sealed source graph is
`1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc`.

The original queue ID remains
`resolve-reverse-6d7e20fad0b64b418d6a94930526557d`. Its real M4
`report.json` (read directly on the Mac) reports the first two independently
verified receipts and no receipt for the third or fourth stage yet:

| Stage | M4 state at 2026-11-07 22:44 EST | Original receipt SHA-256 |
| --- | --- | --- |
| pristine | `verified` | `60bab65ad24bd2d0942fb70bd1f09b4c3c912ff8b9f1fe6855a6b3265281c748` |
| edited | `verified` | `bf6ce57b471b09d766a1edaabad8aa07cedc322190f1deca2007fc2018d4d468` |
| revision | `awaiting_operator` | none; one-use operation `5dd1a010-fdcb-4dc2-a82f-c0740411465e` |
| rebuild | `pending` | none; one-use operation `3371430a-fccb-4662-93ac-eced922d0d81` |

The original source-pinned proof session is
`run/revision/session.json`, SHA-256
`c49f1278acdcab2fd6c4d809d6ba93ea6a71d50f16e62cb4ea2316f37026f319`.
Its signed `revision-ledger.json` has `outcome=accept`, history containing only
proposal `sha256:0d87abdf59bc941797eec2b0080cf0b17711a70bc471fedc7eaeb22e4b3f8afd`,
and its signed `decision-receipt.json` identifies the original approved
proposal decision. `run/revision/comparison.md` shows the picture-only slate
boundary 327→351, unchanged total 1407 programme frames, unchanged mapping,
no new audio; the source-pinned `accept-proposal` step finished and emitted
`original_picture_only_revision_accepted`. This is **not** yet the independent
M4 revision verification.

**Initial active-owner audit:** the preexisting launchd job
`vera-473-revision-continue05` remained running (launchd parent PID 45805)
and progressed without intervention from `accept-proposal` to `submit`. At
the initial read-only inspection, M4 remained
`verified, verified, awaiting_operator, pending`; no
`receipt-revision.json` had been observed and the `submit` step was still
in flight. No competing worker, re-submission or one-use native operation may
be started. Protect the entire campaign directory, `run/revision/`, the
original queue directory/SQLite DB/owner lock, `pinned-code/`, all source pins,
original disposable project UIDs and previous native operation IDs, and the
historically damaged #312 target and its results.

**Next read-only reconciliation:** wait for that *same* launchd owner to become
terminal; inspect its stdout/stderr, receipt bytes and SHA-256, original
proof-session pin and M4 `report.json`. Advance to separate rebuild phase
only upon independently established stage states
`verified, verified, verified, pending` with the original signed revision
receipt. If the owner ends after the one-use decision or receipt intent but
before M4 verification, fail closed; never replay or relaunch the consumed
step. Full #473 still has the documented menu-driven GUI roll versus
non-GUI acceptance gap, so stage verification alone cannot close #473 or
unblock #312.

Linux worktree verification for this **documentation-only** reconciliation:
`git diff --check` passed. `npm run validate:fast` was attempted using
Node 24.19.0/npm 11.17.0 and exited 1 at `@vera/public-page-capture` lint
with 45 `@typescript-eslint` unresolved-type errors. This worktree had no
`node_modules` directory before the attempt. No source code or test was changed
in this phase, and no assertion is made that the lint failure is new or
identical to `origin/main` without a separate baseline comparison.

**Phase 1 terminal reconciliation, 2026-11-07 22:49 EST:** Without any new
worker, native operation or replay from this Conductor phase, the *original*
launchd owner completed `submit` and emitted `original_M4_revision_verified`,
followed by `original_revision_step_completed submit`. Independent direct
inspection of the original M4 `report.json` confirmed the exact stage sequence
`[verified, verified, verified, pending]`. The revision receipt SHA-256 is
`a484161a433dd2e3792641c80dfbed5ad63356828a442788f2ae8ab9a1717ef5`,
equal to independently run `shasum -a 256` of the original 304-byte
`receipt-revision.json`. That receipt has original revision operation ID
`5dd1a010-fdcb-4dc2-a82f-c0740411465e` and exact source-pinned proof
`run/revision/session.json` with SHA-256
`c49f1278acdcab2fd6c4d809d6ba93ea6a71d50f16e62cb4ea2316f37026f319`.
M4 `status.json` is `queued`, `humanRequired=false`, `readyFor312Phase2=false`
because the fourth rebuild receipt has not yet been produced. **Phase 1 is
verified; only the separate phase 2 can now pursue the provisioned distinct
fresh rebuild target.**

The retired `vera-473-revision-continue05` launchd entry remained registered
after success (`launchctl list` showed PID `-`, last exit `1`). Subsequent
auto-restarted `inspect` attempts fail closed before any stage operation with
`#473 original revision refused: original edited M4 not verified or revision
already attempted`. This is a residual service-cleanup consideration for the
next phase, not permission to reset or replay revision. Confirm there is no
active native owner before fresh rebuild and preserve original source hashes,
queue and one-use receipts. This phase did not modify any Mac service.
### Adopted Conductor phase 2: original M4 rebuild fail-stop (2026-11-08)

**Disposition:** bounded fail-stop, **not** original M4 acceptance. Preserve the existing draft PR #474, the original pinned native host, the retained Mac campaign at `~/.local/state/vera/issue-473-studio-05`, the original #312 target, the distinct provisioned rebuild target, and every signed native operation. Do not replay or overwrite the consumed one-use intent.

- Independently verified original M4 stages `pristine`, `edited`, and `revision` remain `verified`. The original `rebuild` stage (operation `3371430a-fccb-4662-93ac-eced922d0d81`) remains `awaiting_operator` with **no** `receipt-rebuild.json`. `readyFor312Phase2=false`. The original M4 deadline was `2026-11-08T05:56:15.366999Z` and expired before a fourth receipt was produced.
- The independently verified accepted revision public package, signed session, and preflight were prepared on a distinct target (project UID `6726f2ee-3172-4813-b887-02614bebc1c1`, timeline UID `999ba98a-4670-4f26-99a5-0a4f86bb05af`). Session SHA-256 `25fd3ef4bc8f41b7806b395b5cd8c7c5a583654ab3903fb38f45baaaa3dbff96`; accepted package build ID `2ae6c5ae-03f4-4f28-8012-04ea7ded20d5`.
- The sole original signed native drive successfully completed and authenticated/ingested `construct` (sequence 0), `save_reopen` (sequence 1), and `capture_pre` (sequence 2). A signed `operator-plan-03.json`, `operator-approval-03.json`, and issuance receipt exist for `queue_render`, but **no native sequence-3 intent or result** was emitted. No rebuild render, terminal MOV/PCM comparison, or fourth M4 receipt was verified.
- The frozen pinned Mac carrier still invokes `(preflight or preflight_selected_disposable)(target, ...)` in `resolve_test_bench_carrier.py`; `queue_render` hit `selected_disposable_not_idle` / `selected project has unresolved output operation`. The adopted worktree contains the render-aware `preflight_owned_render` path, but substituting it into this source-pinned, already-started native campaign is not allowed. Further auto-restart attempts reported `HostClockRegression: host clock rollback/uncertainty` and the one-use guard's `native rebuilt host operation already started; no replay`; none replayed the original native operation. The auto-restarting phase-owned launchd service `vera-473-rebuild-drive2` was removed and confirmed absent at `2026-11-08T07:59Z`; no phase driver remained active.
- The original three verified M4 receipts and original signed/native results are retained. **Do not submit an expired receipt, reset deadlines, delete the native journal, recreate the project, launch another phase-2 driver, or unblock #312.** A new campaign or remediation requires separately reviewed authorization, with updated compatible source-pinned host and fresh target/IDs. Phase 3 can investigate and test the reusable render-aware guard without adopting or replaying these consumed operations.

The full chronological Mac evidence, owners, receipt hashes, run log paths, and prior test/gate results are in `.pipeline/473/progress.md`. Local `npm run validate:fast` reproduced the pre-existing `@vera/public-page-capture` lint failure (45 type-resolution errors); the phase's focused rebuild-stage unit tests, Ruff and strict mypy passed. This phase is **closed out as an exact protected fail-stop**, not as a native acceptance pass.

### Adopted Conductor phase 3: native-only compatibility and reusable safety

**Non-GUI acceptance verdict: BLOCKED, not waived.** The genuinely verified
327→351 same-target edit in `issue-473-studio-05` used the now-retired Edit-page
menu/keyboard workaround. Resolve Studio 21.1.1.10 lacks a documented
in-place timeline-item boundary setter. The later 21.1.2
`TimelineItem.SetLeftOffset` and `SetRightOffset` change available *source
handles*, not a dual-item roll edit; a reported Studio 21.1.2 result was
destructive despite returning true. A file-import route creates another
timeline with different native UIDs. None is a qualified API route for M4.
References: the [published 21.1.2 API](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.2/resolve_api/TimelineItem)
and [empirical offset failure](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336).
This is a technical compatibility finding, not an excuse to bypass the
requirement. The historical `scripts/issue-473-native-roll-once.py` now
**refuses all GUI edit and selection calls** while retaining read-only
inspection and immutable forensic checks.

The new `resolve_test_bench_non_gui_edit.py` keeps a capability probe
read-only and returns explicit `blocked_no_qualified_non_gui_roll` even
for hypothetical 21.1.2/22 SDK method presence. Before enabling any real
new stage, an *independent* signed one-use sacrificial Studio trial must
prove, after save/reopen, the exact original two timeline-item UIDs, same
media/audio UIDs, complete six-track geometry and 327→351 programme while
invoking only an **official supported native editor API** or reviewed
equivalent. No arbitrary script/GUI commands, edited-M4 assertion or
source-pinned old-campaign replay are authorized.

**Reusable controller, code-reviewed boundary:**

- `resolve_test_bench_campaign.py` exposes `start` and
  read-only `inspect` for a **new**, explicitly authorized
  stage. Exact closed config pins the original V2 session SHA, installed
  release manifest SHA, case/phase/target UIDs, real Producer instruction,
  cumulative UTC Unix deadline and free-space reserve. The original
  `_verify_output_release` / `load_output_session` validators
  independently enforce source and release currentness.
- The stage intent is durable before the first action. A later call
  **cannot repeat** a stage after an UNKNOWN, crash after spawn or crash
  during signed terminal commit; `inspect` only reports
  original host/capture evidence. It never fabricates an M4 receipt.
- The #312 one-start M4 runner calls this stage controller for **new**
  pristine stages and derives the strictest deadline from the original
  M4 `runAt + maxElapsedSeconds` and `deadlineAt`.
  The lower-level native carrier rechecks deadlines before intent and
  immediately before spawn, even when source verification is slow; an
  expired already-spent intent is **not retried**. Disk reserve is rechecked
  before dispatch.
- The controller's case-specific checks are bound to the authenticated
  V2 host; mock tests demonstrate a later `synthetic-313` session
  can use the **same interface** without GUI, but do not authorize or
  claim a real #313 benchmark. #313 requires merged #312 source and its own
  exact fixture, deadlines, approval and independent native evidence.

The existing expired phase-2 Mac campaign remains completely untouched:
three original M4 receipts verified, rebuild awaiting_operator without
fourth receipt, and no final #312 evidence. The **source-pinned frozen
native host is NOT changed by this branch**. No new Mac native operation
was performed or claimed in phase 3. Fake SDK tests are only software
fault injection; a real Mac smoke and supported same-UID native edit
remain necessary before phase 4 or any #312/#313 acceptance.

**Phase-3 local verification:** 85 affected focused Python tests pass, including
the fake-host #313 reuse and crash/deadline cases; affected Ruff and strict
mypy pass, and full-tree mypy reported no issues in 375 files after the test
import correction. Local `npm run validate:fast` was attempted twice with
the pinned Node/npm installation: its second pass completed TypeScript checks
and full-tree Ruff, but stopped at four mypy test import declarations
(subsequently corrected; focused tests were rerun). No green *entire*
`validate:fast` completion or CI/Mac Studio smoke is claimed here. Two
semantics-preserving existing source formatter changes were needed in
`qualification_output_controller_v2.py` and
`resolve_test_bench_render_preflight.py`; the original frozen Mac
runtime and in-flight receipts were **not** modified. For any future new
source-pinned campaign, a fresh installed release and authorization are
mandatory.
