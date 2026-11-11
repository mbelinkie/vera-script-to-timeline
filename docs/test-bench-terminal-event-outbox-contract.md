# Test Bench terminal-result event/outbox — #510 phase 2

**Scope:** code-only, signed fixture/simulation input; **no live #499 worker,
native Resolve effect, chat sender, or thread wake**. #511 remains responsible
for independent real M4 4/4 acceptance and actual unattended origin-thread wake.

## Trust and entry points

`scripts/test-bench-terminal-outbox.mjs` exports:

- `signTerminalAttestation(unsigned, key)`: a low-level, HMAC-SHA256,
  domain-separated signing primitive for **trusted verifier adapters only**.
  An AI message, native job log, or terminal report is not a signing authority.
  Tests use private synthetic keys; no production verifier/writer is wired.
- `createTerminalOutbox({filePath, receiptKeys, eventKey, encryptionKey,
  now?})`: separate private local store and immutable authenticated event
  builder. All keys are distinct 32+-byte private Buffers supplied out of
  band. `receiptKeys` is a map of trusted issuer names to
  `{provenance:'simulation'|'signed-read-only', key: Buffer}`.
- `.ingestSimulation(signedAttestation)` accepts only a verifiable signed
  simulation, never an unsigned native report.
- `.ingestSignedFixture({fixturePath, sha256})` opens a previously retained
  historical signed attestation **read only**, refuses symlinks, requires an
  exact pinned byte digest, strict canonical JSON, the correct issuer and
  an unexpired HMAC. Stage digest references are not dereferenced or modified.
- `.inspect(eventId)` returns an immutable signed event and a separate durable
  audit copy, or `null` for an unknown ID. There are no methods to send,
  acknowledge, resume, mutate a native case, or confer CI/issue authority.

## Signed input contract

The issuer attests a complete `terminal` record only after independently
authenticating its source; one must not sign mere queue exit or an unverified
status file. Signature covers the version, issuer, provenance, timestamps,
and *all* terminal fields in sorted-key canonical JSON. Assertions expire in
at most five minutes; historical **evidence** may be old, but the authorized
read-only verifier must produce a fresh attestation over it.

```json
{
  "version": 1,
  "issuer": "historical-read-only-verifier",
  "provenance": "signed-read-only",
  "issuedAt": 1794412800000,
  "expiresAt": 1794412860000,
  "terminal": {
    "repository": "mbelinkie/vera-script-to-timeline",
    "issueNumber": 510,
    "pullNumber": null,
    "jobId": "job-1",
    "caseId": "case-1",
    "attemptId": "attempt-1",
    "operationId": "operation-1",
    "sourceSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "actorSha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "correlationId": "a17d6edb-c200-442d-8bdd-f0d4573ab789",
    "bindingId": "a17d6edb-c200-442d-8bdd-f0d4573ab780",
    "outcome": "UNKNOWN",
    "reasonCode": "unknown_after_claim",
    "stageReceipts": [
      { "stage": "pristine", "sha256": "1111111111111111111111111111111111111111111111111111111111111111" }
    ],
    "report": {
      "artifactId": "reports/attempt-1.json",
      "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    },
    "strict312": null
  },
  "signature": "64-hex-HMAC-generated-by-trusted-verifier"
}
```

`outcome` is exactly one of `VERIFIED`, `FAILED`, `BLOCKED`, `UNKNOWN`,
`CANCELED`, `EXPIRED`; **UNKNOWN is never changed into PASS**. Receipt digests
use the actual M4 stage names (`pristine`, `edited`, `revision`, `rebuild`),
sorted with no duplicates. Report identifiers are non-executable relative
artifact pointers; their SHA-256 pins evidence bytes. Callback URLs and
owner/thread IDs are deliberately absent. `strict312` is *only* `null`:
signed terminal status does not, by itself, certify #312 strict native
acceptance, even for `VERIFIED`.

## Event identity, persistence, audit, and recovery

1. A deterministic `eventId` hashes the domain-separated immutable event
   content, including the authenticated receipt digest and source/actor,
   operation, opaque correlation/binding, stage receipts, report, outcome,
   attempt and provenance. The event has a separate event-key HMAC signature.
2. Case-attempt uniqueness is keyed by `(repository, issueNumber, jobId,
   caseId, attemptId)`; a byte-identical signed replay returns `duplicate:true`
   without altering the event or audit, while a different receipt or outcome
   for the same attempt fails closed. This prevents replay of older UNKNOWN
   attempts as a new VERIFIED event; new attempts require a new attempt ID.
3. One AES-256-GCM authenticated file atomically holds immutable events,
   attempt index, and logically separate audit: `persisted`, time, one
   append-only persistence entry. A private 0700 directory, 0600 file,
   exclusive single-writer lock, atomic replace, file and directory fsync
   provide crash/restart durability. Corruption, changed keys, missing
   indices, mode violations and held locks fail closed rather than resetting.
4. **Nothing is delivered by phase 2.** `persisted` is not `queued`,
   `delivered`, `ack_observed`, `auto_woke`, `reviewed`, or `resumed`. Phase 3
   must add bounded delivery and independently observed ACK audit transitions,
   with senders disabled by default and #398's manual path retained.
5. Correlation/binding IDs are *opaque locators*, **not** authorizations.
   The phase-3 trusted adapter must obtain a fresh phase-1 platform `resolve`
   attestation, match *all* event context fields against the resolved private
   origin, and fail closed on mismatch or expiry before any possible send.
   The event cannot infer owner, thread, or callback route by itself.

The original #398 CI notification code was removed when the legacy CI queue
was retired. This standalone store reuses its authenticated immutable-event,
independent outbox, deduplication, status, manual-first and audit contract
without restoring the deleted CI machinery or touching #361/#499.

**Unproved:** authentication of a production Test Bench verifier, integration
with a live native worker, strict four-stage #312 acceptance, actual exact
platform owner/thread registration, ACK, and an unloaded/idle-chat wake. No
fixture or simulated `VERIFIED` status can establish these.
