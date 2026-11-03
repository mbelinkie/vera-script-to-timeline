# Manual DeepSeek recovery

Issue #415 adds recovery support to the existing private bounded controller.
The outbound receiver supports a distinct, separately approved live V2 task
contract; see [dispatch](DEEPSEEK_CHAT_DISPATCH.md). This recovery contract grants no spending,
dispatch activation or retry authority.

## Preserve the original attempt

An uncertain request keeps its original receipt, manifest, ledger entry and
full reservation. Provider charge evidence can establish that a charge occurred;
it cannot establish a returned response, request ID, usage, candidate or successful
check. A separate immutable reconciliation record documents that distinction and
binds the retained artifacts. It does not rewrite historical accounting or
release held funds.

## A separately authorized new trial

The manual continuation path accepts one new task with its own current Producer
Chat review, exact owner event, immutable manifest and single-use receipt. It
never reopens #411 or the discontinued four-call calibration campaign. A new
task retains the ordinary USD0.25 task ceiling, a USD0.25 single-task campaign
ceiling, and the shared USD10 lifetime ceiling.

Before a provider path, the controller must check the current task, actor and
review; exact source, adapter and manifest; frozen files and checks; approved
model and peak pricing; the shared ledger and lock; all historical costs and
pending reservations. Every unresolved attempt must have matching retained
evidence. Its full reservation still counts. Missing, stale or altered evidence,
duplicate identity, inconsistent accounting or insufficient budget refuses.

The read-only `scripts/deepseek-continuation-gate.mjs` accepts one JSON identity
argument and returns a verified identity; it never invokes the controller.
The identity supplies `issue`, `commentId`, `manifestSha`, `sourceSha`,
`adapterSha`, `reconciliationSha`, `attemptId`, `campaign`, `model` and
`maxOutputTokens`. The approved issue must contain exactly one
`VERA_DEEPSEEK_CONTINUATION_V1` marker whose metadata matches
`continuationApprovalMetadata(identity)`. Its explicit `/deepseek continue`
owner comment must be unedited. Prepare that event first, then bind its ID
into the immutable manifest and finalize the issue before independent Chat
review. This avoids predicting a future event ID; the event alone grants no
execution until the exact current review and all other gates pass.
The source must still be current `main`. The existing eligibility/type/owner
vetoes and canonical review verifier apply unchanged.
The manual gate limits a new task to 100 comments and reuses the canonical
verifier's two history reads, keeping each full gate within ten public reads.
The controller runs it twice, without caching approval across provider preflight.

The private controller's explicit `--continuation` mode requires independent
operator enable and exact manifest/source bindings. It shares the ordinary
per-issue receipt namespace, so a previous mock, dispatch or continuation
receipt prevents another attempt. It hard-codes one call; there is no repair
loop, resume switch or timeout retry. A baseline already passing makes no call.
Receipt allocation follows the final approval/accounting checks. Earlier
refusals retain local diagnostic evidence without reserving funds or consuming
a receipt; preserved candidate workspaces still prevent blind restarts.

The immutable `VERA_DEEPSEEK_RECONCILIATION_V1` record binds the original
ledger history, historical billing evidence and each uncertain row to retained
receipt, manifest and charge-evidence hashes. It records charge evidence,
response retention, usage verification and request-ID retention separately.
The reviewed #411 record says charge observed, response/usage/request ID not
retained, and `reservation_action: retain_full`. Its statement of charge is
informational: budget calculations still use the full held reservation.
New continuation receipts can also be reconciled as invocation not started,
outcome unknown, or response retained with unverifiable usage. A retained
response gets its own hash binding and request-ID evidence. None of these
records releases a reservation or reuses the failed task.

## Diagnostics

Future failures retain an allowlisted error category, named execution stage,
whether invocation started, and whether a response was durably retained.
Exception messages, credentials, headers, payloads and private paths are never
part of the safe diagnostic. An interrupted or uncertain provider attempt
remains non-retryable, even if a charge was later observed.

Safe stages are `authorization`, `request_preparation`, `provider_preflight`,
`provider_invocation`, `response_retention`, `response_parse`, `accounting`,
`frozen_checks` and `unknown`. Safe error classes are `host_interrupted`,
`transport_timeout`, `provider_http`, `transport_error`, `invalid_data`,
`io_failure` and `internal_error`. Unknown exception types never supply their
own name or text. The receipt also records invocation and response-retention
booleans; charge status remains separate. Malformed code or failed checks
after verified usage cannot turn a known charge into a refund or new allowance.

## Verification

Public approval-gate tests use fake GitHub reads. Private controller tests use
temporary ledgers, retained evidence and fake providers. Installed compatibility
is checked without provider access. A future real request needs its own explicit
authorization; a passing offline test does not supply it.
