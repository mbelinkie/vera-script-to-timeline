# #510 phase 3: exact-thread delivery and independent observations

**Code-only foundation, NOT a live sender or unattended wake.** This phase does
not call Codex, Zodex, ChatGPT, Mac, Resolve, the #499 runner or paid AI services.
All three production senders are **hard-disabled** regardless of environment
settings; no sender credentials, arbitrary transport callbacks or production
activation switches are accepted. The static simulation plan is fixture data,
never a platform transport. #511 owns real integration and observed wake.

## Trusted inputs and private storage

The module scripts/test-bench-exact-thread-delivery.mjs provides:

- createExactThreadDelivery: takes the phase-2 immutable signed event and a
  **fresh one-use independently signed** phase-1 resolution assertion.
  The registry's actual binding ID must match the signed event binding ID.
  Repo, issue, PR, operation, job, case, source/actor SHA, correlation,
  platform, owner and exact callback thread are checked on enqueue/dispatch.
  The registry gained resolveRegisteredOrigin, without changing the original
  resolveOrigin return shape. Correlation ID alone is never authority.
- capabilities: reports productionSendEnabled:false and
  independentlyObservedLiveWake:false for codex, zodex and chatgpt.
- enqueue: privately records the immutable target fingerprint and per-event
  delivery ID. No message is sent.
- dispatch: always rejects without an explicitly supplied **static**
  simulationPlans fixture. Historical/signed-read-only events cannot be
  dispatched even with simulation configured. The fixture defines per-attempt
  delivered (with exact recipient/message ID), offline, busy, rejected,
  ambiguous or crash outcomes; it cannot send network traffic.
- observe: independently **Ed25519**-signed platform observer must attest the same
  event, delivery, binding, correlation, owner, platform, exact thread and
  provider message ID. Observer keys are independent of sender/event/origin,
  tied to one platform. Short-lived nonce and evidence digest are mandatory.
- inspect, sweep, manualFallback: read opaque status, convert dangling
  in-flight/expired work into non-success states and preserve #398 manual owner
  handoff plus #421 optional scheduled-owner-check as clearly marked fallback.
- signDeliveryObservation: a low-level fixture/future trusted **observer-side**
  private-key primitive, NOT a way to attest untrusted AI/chat/queue text.
  The delivery verifier accepts **public keys only** and cannot forge its
  own ACK or wake attestations. Real observer private keys must stay in a
  separate trusted authority.

Delivery storage uses an owner-only 0700 directory and 0600 AES-256-GCM
authenticated file, exclusive no-steal writer lock, atomic replace, file and
directory fsync, event-to-delivery index and spent observer nonces. Private
owner/thread IDs are HMAC-fingerprinted before persistence and never returned
or printed. Corruption, symlinks, changed keys and unsafe modes fail closed.
There is no external anti-rollback anchor.

## States and faults

1. The separate phase-2 outbox stays at persisted. Enqueue records
   persisted -> queued only in the delivery lifecycle.
2. Dispatch durably claims in_flight BEFORE any simulated send response.
   A 2-minute in-flight claim lease protects a concurrent result commit;
   crash/restart with a dangling claim becomes unknown only *after* that
   bounded lease. Ambiguous enqueue and recipient mismatch become unknown
   with NO automatic replay.
3. Exact-recipient definitive simulated receipt produces delivered,
   not ACK or wake. Only explicit offline/busy **not-enqueued** results allow
   retry: maximum three attempts, 30s/60s/120s backoff. Exhaustion and
   definitive rejection become failed; expiry becomes expired or unknown.
4. Each subsequent transition needs independent signed evidence in order:
   delivered -> ack_observed -> auto_woke -> reviewed -> resumed.
   Evidence kinds: platform-delivery-ack, unloaded-thread-activation,
   thread-content-review and thread-agent-resumption. Duplicates,
   wrong-owner/thread/message, out-of-order, stale and unsigned observations
   fail closed. Signed fixture observations do NOT establish real wake.
5. Missing ACK never triggers a resend after delivered. Expiration of an
   unproved delivery becomes unknown. Terminal outcome UNKNOWN remains UNKNOWN;
   strict312Verdict always stays UNPROVED within this code-only scope.
6. Manual #398 handoff returns pinned report coordinates and outcome without
   private destination or injectable instructions. #421 is an optional
   scheduled owner reminder, not evidence of autonomous resumption.

## Checks and #511 boundary

Focused Node tests cover exact origin/binding, six immutable outcomes,
three hard-disabled platforms, positive lifecycle, signed ACK correlation,
malicious text, stale source, busy/offline bounded retry, ambiguous send,
crash-after-claim, lost ACK, expiration, corruption and manual fallback.
The fast gate includes these tests.

**UNPROVED for #511:** authenticated real platform-origin acquisition;
production sender/ACK transport; live #499/Test Bench native result ingestion;
strict four-stage M4 #312 acceptance; genuinely unloaded original-thread
wake, independently observed review and real agent resumption. A simulated
resumed state or VERIFIED terminal report cannot prove these.
