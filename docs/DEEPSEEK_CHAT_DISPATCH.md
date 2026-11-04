# Chat → GitHub → Mac dispatch

> **Superseded (issue #429).** New DeepSeek work uses the label-triggered GitHub
> Actions job in [`.github/deepseek/README.md`](../.github/deepseek/README.md). This
> receiver path remains only for its existing records.

The outbound Mac receiver reuses the existing private bounded controller,
credential helper, native Seatbelt confinement, cross-campaign lock and single
lifetime USD10 ledger. The legacy self-hosted Actions runner stays offline.
Defaults remain disabled; readiness, labels and dashboard navigation start no job.

## Hosted validation

The `issue_comment` workflow runs trusted default-branch code on `ubuntu-latest`
with read-only contents/issues permissions. It validates the exact
`/deepseek dispatch` comment, actor, open issue, classification, opt-in labels,
handoff and canonical current Chat review. It allocates no receipt and never
invokes a Mac adapter or provider. No private material enters Actions.

The Mac receiver uses outbound public GitHub reads, with no incoming listener or
GitHub write token. Required labels are `chat-reviewed`, `deepseek-eligible`,
`deepseek-ready`, `deepseek-dispatch`, and exactly one `type:implementation` or
`type:bug`. Pending review/escalation, design/non-coding classifications,
`deepseek-excluded`, another execution owner and `execution:codex/design/human`
veto dispatch. #416 itself is Codex-owned and cannot be a worker target.

## Versioned immutable task contract

Both receiver and adapter read the same immutable owner-only task file (0400)
inside an owner-only directory (0700):
`~/.local/share/vera/deepseek/tasks/issue-N.json`.

Legacy `schema: 1` / `VERA_DEEPSEEK_RECEIVER_V1` receiver requests remain mock
only. Missing legacy mode means mock; an unknown mode refuses. New requests use
`schema: 2`, `transport_contract: "VERA_DEEPSEEK_RECEIVER_V2"` and an explicit
`execution_mode: "mock"` or `"live"`. Missing/unknown V2 modes refuse.
A mock request always requires `live_enabled: false` and its bounded approved
`mock_replacement`; it never reaches credentials, provider calls or reservations.

Common fields bind repository, issue, exact `dispatch_comment_id`, current main
`base_sha`, installed `adapter_sha256`, one `editable_file` and hash, explicit
`edit_scope`, `frozen_files` hashes, 1–3 absolute trusted `checks` vectors, clean
public `source_repo`, `task_instructions`, `max_rounds`, `max_output_tokens`,
`task_cap_usd`, `operator_approved` and `public_synthetic_only`.

Live V2 additionally requires `live_contract: "VERA_DEEPSEEK_LIVE_V2"`,
`live_enabled: true`, one attempt (`max_rounds: 1`), `max_input_units: 20000`,
`reasoning_effort: "high"`, exact `model`, approved peak `verified_rates`, a
current `pricing_verified_on`, unique `attempt_id` and `campaign`, and exact
`ledger_sha256` / `reconciliation_sha256` bindings. Task and single-task campaign
caps are USD0.25; the unchanged shared lifetime cap is USD10. Live manifests
cannot carry mock replacements or continuation-only contracts. `live_gate_files`
binds every public gate dependency to the approved source bytes.

The manifest SHA covers the exact immutable bytes, including files, checks,
limits, model, pricing and accounting references. A task/mode/build change
requires renewed exact approval. No flag or label supplies spending authority.

## Independent live task approval

`scripts/deepseek-live-gate.mjs` is a read-only gate. Its identity and returned
metadata are specified in [the adapter contract](DEEPSEEK_LIVE_ADAPTER_CONTRACT.md).
The target issue must contain exactly one `VERA_DEEPSEEK_LIVE_V2` metadata marker
matching `liveApprovalMetadata(identity)`, plus authentic current canonical
Producer Chat review of the full issue. The exact owner `/deepseek dispatch`
event must be unedited and have no GitHub App mediation. Mock or continuation
approval does not satisfy live approval. #416's implementation approval does not
approve any paid task.

Prepare the dispatch event before finalizing its manifest and issue metadata,
then obtain independent approval of that exact revision. This avoids guessing a
future event ID. Keep polling disabled throughout preparation. The event alone
cannot execute until current task review, local enable and all gates pass.

## Read-only host preflight before publication

After installing the reviewed adapter, while all dispatch/live flags are off:

```sh
node scripts/deepseek-receiver.mjs --preflight <approved-adapter-sha256>
```

Run this **before posting** any new dispatch event. It reads the receiver and
receipt storage, cursor, installed adapter, controller state/ledger access,
accounting and native isolation readiness. It checks owner-only real files and
directories, the reviewed build and disabled flags. The private adapter's
`--host-preflight` mode neither imports credentials nor calls a network/provider.
It cannot create receipts, advance cursors, reset state, change permissions or
initialize a ledger. Known refusals provide safe corrective instructions;
repair the named condition separately and rerun. Preserve every old artifact.
The read-only cursor is valid because its private parent permits atomic replacement.
A live host refusal or transient public approval-read failure preserves the cursor
for an explicit repair/rerun before any adapter call. Legacy mock dispatch retains
its original adapter compatibility and does not require the new preflight hook.

For live V2 tasks, the receiver repeats preflight immediately before invocation, allowing only
the explicitly enabled one-shot flags at that boundary. The private controller
also repeats its host readiness checks before entering live processing.

## One-shot execution and accounting

Initialize the cursor with one explicit poll before posting the new event. Its
first run saves the newest comment identity and deliberately replays nothing.
No daemon, timer or standing poller is installed. After separate exact paid-task
approval, run one poll with temporary `VERA_DEEPSEEK_DISPATCH_ENABLED=true` and
`VERA_DEEPSEEK_LIVE_ENABLED=true`, plus the exact approved
`VERA_DEEPSEEK_LIVE_ISSUE` and `VERA_DEEPSEEK_LIVE_COMMENT_ID`. This limits the
poll to one selected live event. A different pending live event stops the poll
without consuming it; process pending live events in comment order. A poll with
live mode disabled also preserves such an event. Keep persistent defaults off afterward.

The receiver repeats issue, event, canonical review, current main, manifest and
adapter checks before its sole adapter invocation. Live mode delegates to the
existing #415 single-attempt controller. Under the same exclusive lock, it
rechecks source/build/frozen checks, model/pricing, independent approval, ledger
and reconciliation after provider preflight and immediately before reservation.
A passing baseline makes no provider call. Otherwise the controller atomically
allocates the per-issue receipt, durably reserves at peak pricing, and only then
may invoke the approved model once. The controller owns its rich live receipt;
the transport never overwrites it with a process-exit summary.

Every historical actual charge and pending/uncertain reservation counts against
the same USD10 lifetime ceiling. #411's original uncertain receipt, manifest,
history and full held reservation remain immutable. Charge evidence cannot
manufacture a returned response, verified usage or a successful candidate.
[Manual recovery](DEEPSEEK_RECOVERY.md) remains an explicit separate new-trial
route; it cannot replay an old receipt or revive the discontinued campaign.

Timeouts/interruption retain reservations and safe failure category/stage;
there is no automatic retry. Verified charges remain charged even if parsing or
checks later fail. Missing/changed approval, build, manifest, source, accounting,
budget or isolation refuses. Public reads cannot form an atomic transaction
with a local process launch; repeated gates narrow that race.

## Candidate and acceptance boundaries

Only the disposable candidate is writable during frozen checks. Private
controller, ledger, credentials, home/media, arbitrary network and Mach-service
access are denied by native candidate confinement. Model output is a bounded
JSON replacement for the one approved file, never tools or commands. The worker
cannot write GitHub, start CI, merge, close issues or invoke Resolve.

`worker-returned` proves process exit only. Codex independently checks the exact
diff, frozen file hashes, checks and private accounting before integrating an
isolated unmerged candidate. Safe summaries may be published; private sources,
responses, credentials, receipts and account data stay local.

Offline fake-provider tests cover both modes, approval drift, exact bindings,
preflight refusals, caps/reservation ordering, duplicates and uncertainty. They
do not prove a real GitHub-to-provider round trip. #416 closure additionally
requires protected merged/green implementation and the separately authorized
[single-task pilot](investigations/issue-416-live-pilot-proposal.md).
