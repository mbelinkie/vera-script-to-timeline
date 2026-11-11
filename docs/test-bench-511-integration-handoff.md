# #510 → #511: exact-origin Test Bench result delivery integration handoff

**Status: foundation only.** This contract is a code-only, local, private,
fail-closed implementation. The independent #511 live integration **MUST NOT**
start until #499's relevant gate has completed. It must not replay or modify
#499's source-frozen actors, operations, native cases or projects. #510 never
invoked Resolve or a production thread sender. A local `resumed` simulation is
**not** proof of a real idle-thread wake.

## Source/API contract (JavaScript ES modules)

| Boundary | Path / exports | Authenticating input | Durable output |
| --- | --- | --- | --- |
| Origin | `scripts/test-bench-origin-registry.mjs`: `signOriginAssertion`, `createOriginRegistry({filePath, signingKey, encryptionKey, trustedIssuers, now?})` → `registerOrigin`, `resolveOrigin`, `resolveRegisteredOrigin` | Signed `register` / one-use `resolve` from authenticated platform authority; exact verified owner, platform, thread, scope, operation, source/actor SHA and callback | Private AES-GCM registry; registration returns **opaque** `{bindingId,correlationId}`; resolution returns binding ID and private route only to trusted caller |
| Terminal | `scripts/test-bench-terminal-outbox.mjs`: `signTerminalAttestation`, `createTerminalOutbox({filePath,receiptKeys,eventKey,encryptionKey,now?})` → `ingestSimulation`, `ingestSignedFixture({fixturePath,sha256})`, `inspect(eventId)`, `verifyTerminalEvent(event,eventKey)` | Independent trusted verifier with allowlisted issuer, provenance, signed six-state terminal attestation; historical fixture read-only and byte-digest pinned | One signed, immutable event **per case attempt**; separately durable outbox audit stays `persisted` |
| Delivery | `scripts/test-bench-exact-thread-delivery.mjs`: `createSupportedPlatformSenderAdapters`, `signDeliveryObservation`, `createExactThreadDelivery({filePath,outbox,registry,eventKey,encryptionKey,observerKeys,now?,simulationPlans?})` → `capabilities`, `enqueue({eventId,resolveAssertion})`, `dispatch({eventId,resolveAssertion})`, `observe(signedObservation)`, `inspect(eventId)`, `sweep(eventId)`, `manualFallback(eventId)` | Signed event + fresh one-use exact registered destination; observer issuer/platform key separate from source signer and sender, exact provider message ID and origin correlation | Private AES-GCM lifecycle with history. Only **static test simulations** can dispatch; all codex/zodex/chatgpt production senders **hard-disabled**, including when environment flags are set. |

Required secrets: origin, receipt, event and encryption signing keys are
distinct private 32+-byte Buffers; never check in real keys or grant an
untrusted model/chat/test result signing authority. The registry now enforces
distinct **per-issuer** signing keys when multiple platform issuers are
configured; legacy root-key configuration is restricted to one issuer.
Delivery observer verification instead uses issuer-specific **Ed25519 public
keys only** (`observerKeys[issuer] = {platform, publicKey}`), with private
keys held exclusively by independent observer authorities and used via
`signDeliveryObservation` on the signing side. Every store must have its own
private 0700 directory/0600 file and its own single-writer owner, distinct
from #499's live case writer.

## Exact acceptance / evidence boundary

1. **Real origin registration**: the initiating provider/owner/exact thread and
   callback must come from an authenticated platform API. `bindingId` and
   `correlationId` are locators, not proof or bearer authority. Register only
   the actual authorized case/attempt, actor/source hashes and expiry. Do not
   infer origin from issue comments, prompt text, a terminal report, CI text,
   the browser URL or a client-supplied thread ID.
2. **Native Test Bench adapter**: read verified immutable terminal records and
   stage receipts via the #499/#473 supported interface *after* #499 gate.
   Independently verify signed native evidence, report SHA, operation/actor/
   source/case identities and strict native outcome before signing a short-lived
   attestation. Never generate it merely from queue exit, navigation or a GUI
   command. `UNKNOWN` after claim stays UNKNOWN; retries require a new,
   authorized attempt, never replaying native effects.
3. **Terminal persistence**: `ingestSignedFixture` is **only** for preexisting
   retained, pinned read-only test/historical records, not an activation path.
   A #511 native adapter needs separately reviewed trusted ingestion. The
   `strict312Verdict` remains `UNPROVED` for every #510 event, including
   `VERIFIED`: strict four-stage #312 acceptance needs its own native evaluator.
4. **Explicit production authorization**: do not switch simulation adapters
   into production senders. #511 must implement separate platform-specific
   capability discovery, explicit Producer permission for paid AI/user-role
   turns, authenticated exact-thread transport and source/owner checks at send
   time. Without that permission and capability, use #398 **manual** owner
   handoff or optional #421 **scheduled owner check**, marked as fallbacks.
5. **Delivery/observation lifecycle**: `persisted -> queued -> in_flight ->
   delivered -> ack_observed -> auto_woke -> reviewed -> resumed`. A queued
   request is not delivered; a delivered response is not an ACK or a wake.
   Commit `in_flight` before send; ambiguous enqueue, crash or lost ACK MUST
   fail closed (`unknown`, no automatic replay). Only definitive **not
   enqueued** offline/busy can retry, at most 3 attempts with 30/60/120 s
   backoff; expiry and failures retain distinct states. An in-flight claim is
   not swept to UNKNOWN before its two-minute lease expires; a different
   process must not overwrite an active result claim. Each subsequent
   transition requires a fresh independent **Ed25519** signed observer attesting exact
   event/delivery/binding/correlation, owner, thread, provider message ID,
   observed evidence digest, nonce and stage kind.
6. **Unattended proof**: run a real source-frozen #499-approved native case,
   independently capture terminal/failure evidence, and verify a genuinely
   idle/unloaded originating thread receives the result, becomes active,
   *reviews* the report and *resumes* without a human checking or polling.
   Keep signed raw receipts, platform ACKs, observer/owner identity and time
   evidence. A simulated `auto_woke` or successful API enqueue never proves
   this. Test failed and UNKNOWN paths independently, without fake PASS.

## #511 test fixtures (signed, read-only, deliberately artificial)

`scripts/fixtures/test-bench-510/manifest.json` pins the byte-level SHA-256 of
three canonical, HMAC-signed `signed-read-only` JSON fixtures:
`verified.signed.json`, `failed.signed.json`, `unknown.signed.json`.
The corresponding immutable terminal outcomes are **VERIFIED**, **FAILED**,
**UNKNOWN**. These **are not native Test Bench receipts**; stage hashes,
source/actor identities and reports are synthetic. In particular VERIFIED
means only the synthetic receipt said VERIFIED, not strict #312 PASS.

The fixture-only verifier key is `Buffer.alloc(32, 73)`, **public and completely
insecure for production**. The test freezes its clock to 2026-11-11
16:00:00 UTC, since assertions expire after five minutes. Never use these
attestations in a real-time #511 integration: a real trusted verifier must
independently authenticate and freshly attest real immutable native evidence.
- Local lock files are intentionally **never stolen** when a process dies
  inside a critical section; the service fails closed instead. #511 must
  provide a separately verified single-writer owner/recovery protocol and
  retain the no-replay guarantee before unattended live activation. An
  independent `inspect` can temporarily encounter an active writer lock;
  production readers need bounded retry or a read-only snapshot API.

Reproduce locally, without changing any native case:

```sh
node --test scripts/test-bench-origin-registry.test.mjs scripts/test-bench-terminal-outbox.test.mjs scripts/test-bench-exact-thread-delivery.test.mjs scripts/test-bench-511-fixture-contract.test.mjs scripts/validate-fast.test.mjs
npm run validate:fast
```

`#511` should use these examples only as interface/negative regression
fixtures, then add actual signed native fixture ingestion and platform/observer
contract tests. Do not treat the HMAC fixture test, `resumed` synthetic event,
queue exit or false notification text as unattended proof.

## Known limits / closure boundaries

- No production platform-origin attestor, sender, real ACK observer, native
  Test Bench hookup, external anti-rollback anchor or idle-thread wake is built
  or verified here. No actual #499 case is touched by #510.
- Historical fixture byte pinning prevents post-hoc edits but the short-lived
  signer must independently attest real historical evidence. A forged receipt
  signed by the test-only key is not native proof.
- CI/PR creation, remote review, mandatory checks and merging are **owned by
  Conductor after the final `handoff.json`**. A local gate or a generated PR
  body is not remote green CI or an actual merged PR. #510 must not close
  #473, unblock adopted #312, or progress #313; #511 and #499 are distinct
  required prerequisites.
