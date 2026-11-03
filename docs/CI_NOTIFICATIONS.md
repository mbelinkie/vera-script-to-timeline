# CI reports to the original Codex chat

Issue #398 adds a manual-first report path. The trusted `Queue completion`
job reads the exact queue-state commit, transaction, run/attempt and gate jobs
before publishing fixed status data. An in-progress enclosing workflow is
reported as **gate assessment**, never as completed delivery. Candidate,
preview and smoke are separate events, including failure, cancellation,
timeout and unknown results. A run which never reaches its finalizer has no
verified event; its Actions page remains the manual fallback.

`vera-ci-notification-outbox` is a separate public branch. Events contain
GitHub identities and an opaque launch ID, never a local chat UUID or token.
Private origin records stay on the Mac. Missing mappings remain unmapped.
The downstream notification job has its own timeout and `continue-on-error`; it never changes
`vera-ci-queue-state/queue.json`, queue commands, required checks or closure.

The Mac consumer is **hard-disabled for production message injection and
resumption**. Reading a report or opening `codex://threads/<uuid>` only
navigates. No report, queue receipt or agent ACK grants permission to edit,
repair, spend, claim, resume CI, merge, approve, accept or close an issue.
The owner must independently review current run evidence and the acceptance
criteria under their existing authorization.

The two earlier disposable probes accepted messages but both warned that
resume failed. The Producer observed an exact first ACK and the second answer
already present when opening the chat. These observations do not establish
unattended wake of an unloaded chat. No further probe is authorized by those
results or by implementation launch. A fresh disposable test requires separate
specific Producer authorization identifying the exact target and paid-turn
boundary. Production activation also requires separate security/spending
authorization and independent wake evidence.

On November 2, the Producer separately authorized one further no-tools test
in the exact earlier disposable chat. The supported read-only chat API showed
`notLoaded` before sending. CLI 0.160.0 admitted one unique message, with an
exact target/message receipt, exit 0 and no warning (no resume option used).
Two subsequent read-only checks still showed `notLoaded` and only old turns;
no new ACK or unattended wake was observed before opening. The message was
not retried. This supports admission while unloaded, not automatic wake or
review. The private proof remains on the Mac, separate from public CI events.

The default installed CLI inspected on November 2, 2026 was `codex-cli
0.160.0`: `queue --thread --message` exists, while `--resume` was absent from
its help. Earlier evidence used a different bundled build. Inspect the exact
installed executable at runtime; do not start a competing app server, edit
private session databases, infer a thread from recent activity, or retry an
ambiguous enqueue. The [official integration overview](https://developers.openai.com/blog/codex-as-a-platform)
describes CLI, SDK and app-server interfaces; it does not prove this Mac's
unattended desktop wake behavior.

## Use at an authorized launch

At the authorized launch, use the pinned Node version and first run
`node scripts/ci-notification-origin.mjs owner-key`. Use its opaque output
for the normal roadmap claim's `--task` value; never publish the runtime UUID
as a claim task ID. The key is a one-way, repository-specific hash of the
actual runtime ID, not a guessed session association. Claim ownership still
uses the usual approval/dependency/profile checks. Then capture in that
claimed issue's checkout. Approval values come from the existing review gate;
the capture command rechecks that approval and this runtime's active claim.

```sh
node scripts/ci-notification-origin.mjs capture --issue N --branch codex/N-slug \
  --approval-comment COMMENT_ID --approval-revision REVISION
```

The command prints an opaque launch ID and stores the real runtime
`CODEX_THREAD_ID`, launch surface, approved scope and provenance in an owned
0700 directory with 0600 files. It does not alter #399's Producer-confirmed
navigation map; runtime capture and Producer-attested mapping are different
provenance. It does not install a universal launcher hook. Call capture at
the actual authorized launch boundary; legacy tasks remain unmapped.

After opening the draft PR, bind it once and publish only public correlation:

```sh
node scripts/ci-notification-origin.mjs bind --launch LAUNCH_ID --pr PR_NUMBER
node scripts/ci-notification-mac.mjs register --launch LAUNCH_ID
```

Both the local binding and public compare-and-swap reject replacement with
another launch. The public registration contains only the repository, issue,
PR, branch, opaque launch ID, registration time and approval references. The
consumer rechecks its immutable blob against the exact private registration.
No session name, recent activity, ChatGPT browser ID or PR author supplies a
local UUID.

## Read and review an event

Each bot report includes an event ID, the precise workflow-attempt
link, full SHAs and the immutable queue snapshot. With the Mac online:

```sh
node scripts/ci-notification-mac.mjs review --event EVENT_ID
node scripts/ci-notification-mac.mjs inspect-cli /absolute/path/to/codex
```

`review` uses the existing GitHub sign-in for outbound reads only. It checks
bot publication provenance, queue-history ancestry, the archived transaction,
exact run/attempt, all gate identities, duplicate runs and the public origin
binding before persisting a private audit. It prints the public report and,
when mapped, a private navigation-only link. Do not paste that private link
or the private audit into GitHub. Missing mapping, expiry, offline errors,
busy storage and writer conflicts are reported without claiming delivery.
The public Actions/PR links remain usable when local lookup fails.

Event persistence precedes report publication. Event writes reconcile exact
content before bounded retries (three attempts, 250 ms then 1 s backoff).
Comment publication claims a durable audit before posting. A definitive PR
comment rejection with HTTP 403 or 404 is reconciled, then the same fixed
report may use the independently registered roadmap issue with the existing
Issues-write permission. That fallback consumes the second and final POST;
no permission is added and an uncertain response never triggers fallback.
Audits retain only the bounded HTTP status and destination issue number,
not response text, headers or credentials. Old audit records remain readable.
An uncertain
outcome is reconciled by bot/event marker; normal replay never posts blindly.
An explicit `NotificationOutbox.manualRetry(eventId)` may reconcile and make
at most one further comment attempt after backoff, within the seven-day
expiry. There is no background scheduler or queue-message retry loop.
Expiry stops delivery/retry; it does not delete historical events or media.

The production delivery adapter exits at a hard false constant, before
calling Codex or reading flags. Even a future authorized invocation cannot
infer admission from a zero exit: until an actual receipt adapter is
qualified, its enqueue result remains unknown and cannot be retried.
The pure audit reducer accepts distinct trusted observer evidence for an
agent-authored exact-event ACK and a separate before-open idle/unloaded wake.
Caller-provided JSON is not independently authenticated evidence. No observer
or activation CLI is shipped. Manual owner review is possible without queue
admission or wake; review and acceptance each require separate evidence and
do not perform any GitHub lifecycle action.

A killed process may leave `.registry.lock`. Inspect that no registry writer
is active before removing only that lock; never delete origin/audit records
to work around a conflict. No automatic stale-lock takeover is implemented.
An interrupted atomic create can also leave its exact `.origin-<hex>.tmp`
hard-link twin. Reads recover only an owned 0600 twin with the same device
and inode; unrelated hard links and unsafe files remain rejected. Temporary
origin-lookup failures return without persisting a terminal delivery state.

## Validation boundary

The focused tests are included in `npm run test:ci-queue`, `validate:fast`
and main smoke. Tests exercise identity, failure, cancellation, timeout,
unknown/unfinished gates, replay, concurrency, ambiguous writes, expiry,
private-file safety, adversarial free text and the disabled adapter.
Local mocks do not prove real bot publication or unloaded wake behavior.
Exact-head cloud CI, post-merge bot publication/readback, the separately
authorized disposable proof and External acceptance remain outstanding on
the draft PR; neither green CI nor an ACK closes #398.
