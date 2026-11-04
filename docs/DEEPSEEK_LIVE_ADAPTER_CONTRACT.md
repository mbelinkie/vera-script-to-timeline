# Live receiver / private adapter contract

This public-safe contract describes the boundary; it contains no private source,
credential, response, receipt, account data or installed private path inventory.

## Read-only adapter host preflight

The reviewed executable receives `--host-preflight` with HOME, system PATH
and `VERA_DEEPSEEK_ADAPTER_SHA256`. Research also supplies `VERA_REPOSITORY`.
It performs no state write, event consumption,
credential import or network request. Success returns exactly:

```json
{"contract":"VERA_DEEPSEEK_HOST_PREFLIGHT_V1","ready":true,"adapterSha256":"<approved SHA-256>","defaultMode":"disabled","isolation":"seatbelt","accounting":"shared-lifetime-ledger"}
```

Refusal returns exactly the same contract name, `ready: false` and one safe
`reason`: `STATE_PERMISSIONS`, `STATE_ACCESS`, `ADAPTER_BUILD`, `ACCOUNTING`, or
`ISOLATION`. Public code maps only those codes to fixed actionable messages.
Arbitrary child text and private error details are never exposed. The public
caller also checks runner bytes before/after and receiver/receipt storage.

## Approval identity and event

For Timeline, `liveApprovalMetadata(identity)` accepts exactly `issue`, `commentId`,
`manifestSha`, `sourceSha`, `adapterSha`, `reconciliationSha`, `attemptId`,
`campaign`, `model`, `maxOutputTokens`. Research requires the additional
`repository` key in both identity and returned metadata. Hashes are full
SHA-256, except the 40-character source commit. Timeline issue #411 and the
discontinued shared campaign are prohibited. Bounds are one attempt, 20,000 input units, 512–24,000 output
tokens, high effort, USD0.25 task/campaign and USD10 shared lifetime.

The issue's sole `VERA_DEEPSEEK_LIVE_V2` marker contains the generated metadata:
the exact identity bindings, `executionMode: "live"`,
`transportContract: "VERA_DEEPSEEK_RECEIVER_V2"`, fixed limits and only the chosen
model's verified peak rates. Canonical current Producer review binds the entire
issue title/body. The owner event is exactly `/deepseek dispatch`, with equal
creation/update timestamps and no App mediation. The gate repeats issue,
comment-history and main reads. Its result adds `approved: true`, issue/event,
`reviewCommentId` and canonical `revision`. The private controller validates
every result field and repeats the gate after provider preflight.

## Receiver invocation

Script-to-Timeline retains its existing state locations and approval shape.
Research requires an explicit repository identity in the approval record and
uses separate cursor, manifest, receipt and candidate directories. Research
source files and checks come from the approved Research commit. The private
adapter runs the live approval gate from the separate reviewed Timeline commit
pinned in the adapter and bound by the manifest. Both repositories use the
same ledger and lock. Historical rows without a repository remain Timeline
records. Attempt IDs and campaign IDs remain unique across repositories.

The receiver invokes the same reviewed executable once with issue and comment
as two arguments. The environment contains HOME/system PATH, repository,
issue/event, manifest/source/adapter hashes, exact task USD0.25 and lifetime
USD10 caps, the expected receipt location, explicit execution mode and, only
for approved live mode, `VERA_DEEPSEEK_LIVE_ENABLED=true`. It contains no
inherited GitHub/provider credential or arbitrary caller configuration.

Mock mode uses the existing transport receipt guard and cannot enter provider
code or write reservations. Live mode uses the existing bounded continuation
implementation with a distinct live approval contract. It acquires the same
cross-campaign lock, independently verifies the approved manifest/source/build,
frozen files/checks, current review/event, model/pricing, historical spend,
reconciliation and all pending commitments. No second executor or ledger exists.

The controller allocates the same atomic per-issue receipt only after final
gates and persists its conservative reservation before the one provider call.
An existing mock, live or continuation receipt vetoes any second attempt.
Uncertain invocation holds the full reservation and cannot automatically retry;
verified usage never becomes uncharged when checks fail. #411 remains unchanged.

The candidate receives neither controller state nor credentials. Frozen checks
run in native deny-default confinement; only the disposable candidate is
writable, and the private home/accounting/network remain inaccessible. Results
stay isolated and unmerged for host-owned independent assessment.

## Verification limits

Public hosted tests exercise this contract using synthetic state and fake
GitHub/adapter results. Private tests use temporary homes, fake providers and
native confinement. Public review inputs contain this contract and synthetic
tests, never private controller source or live evidence. A real paid pilot
still needs its own exact reviewed task and explicit spending approval.
