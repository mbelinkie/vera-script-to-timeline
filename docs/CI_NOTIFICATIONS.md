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
The notification step is isolated with `continue-on-error`; it never changes
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

The default installed CLI inspected on November 2, 2026 was `codex-cli
0.160.0`: `queue --thread --message` exists, while `--resume` was absent from
its help. Earlier evidence used a different bundled build. Inspect the exact
installed executable at runtime; do not start a competing app server, edit
private session databases, infer a thread from recent activity, or retry an
ambiguous enqueue. The [official integration overview](https://developers.openai.com/blog/codex-as-a-platform)
describes CLI, SDK and app-server interfaces; it does not prove this Mac's
unattended desktop wake behavior.

Implementation and external checks remain in progress on the draft PR.
