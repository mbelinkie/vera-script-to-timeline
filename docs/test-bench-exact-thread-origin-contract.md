# Test Bench exact-thread origin binding — #510 phase 1

**Status:** code-only security foundation; does not deliver terminal results, wake a
chat, authorize a Resolve effect, or prove unattended resumption. #511 remains
responsible for separately gated live integration after #499.

## Trust boundary

The destination is the **real initiating platform, private owner ID, and private
thread ID** established by an authenticated platform integration. A model reply,
notification, GitHub issue, PR comment, runner output, terminal-result document,
correlation ID, or user-supplied thread string is **not** a trusted origin.

The eventual producer-side platform adapter must authenticate the originating
session against platform-owned identity, verify the authorized operation and
repo context, and **only then** sign a `register` assertion. The authority's
HMAC key must remain in private configuration, separate from Test Bench worker
data. No adapter that proves the actual Codex/ChatGPT/Zodex platform identity is
implemented here; therefore no claim that real-thread registration works in
production is made by this phase.

The code-only registry is implemented in
`scripts/test-bench-origin-registry.mjs`. It has no thread sender, HTTP
endpoints, Mac/Resolve hooks, or production activation. It provides:

- `signOriginAssertion(unsigned, signingKey)`: low-level HMAC-SHA256 signing,
  callable **only by the trusted adapter** after it authenticates the real
  platform identity; not an untrusted message signing service.
- `createOriginRegistry({ filePath, signingKey, encryptionKey,
  trustedIssuers, now? })`: a private, single-writer local registry. Both keys
  are distinct 32+-byte secret Buffers supplied out of band, never checked in.
  `trustedIssuers` is an issuer-to-platform map such as
  `{ 'verified-codex-bridge': 'codex' }`, so a signer cannot claim a different
  platform through the registry.
- `registry.registerOrigin(signedRegistration)`: validates proof, duration,
  expiry, route, scope, uniqueness, and one-use nonce, and durably saves the
  destination. Returns only `{bindingId, correlationId}` with no private IDs.
- `registry.resolveOrigin(signedResolution)`: requires a fresh independently
  authorized `resolve` assertion that **exactly matches** the registered
  owner/thread and full operation/source/actor binding. Returns private binding
  details **only to the trusted future delivery adapter**. Do not log these.

Both assertion purposes use the following signed payload (the final `signature`
is lowercase hex HMAC-SHA256 over domain-separated canonical JSON of all other
fields):

```json
{
  "version": 1,
  "purpose": "register",
  "issuer": "verified-platform-bridge",
  "nonce": "c9ab931a-0ee2-4492-ac2a-0847284d10c2",
  "issuedAt": 1794412800000,
  "expiresAt": 1794412860000,
  "binding": {
    "platform": "codex",
    "ownerId": "PRIVATE_PLATFORM_OWNER_ID",
    "threadId": "PRIVATE_PLATFORM_THREAD_ID",
    "repository": "mbelinkie/vera-script-to-timeline",
    "issueNumber": 510,
    "pullNumber": null,
    "jobId": "trusted-job-id",
    "caseId": "trusted-case-id",
    "operationId": "trusted-operation-id",
    "sourceSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "actorSha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "authorizationScope": "test-bench.terminal-result-delivery",
    "authorizationExpiresAt": 1794499200000,
    "callbackRoute": {
      "kind": "exact-thread",
      "platform": "codex",
      "ownerId": "PRIVATE_PLATFORM_OWNER_ID",
      "threadId": "PRIVATE_PLATFORM_THREAD_ID"
    },
    "correlationId": "f4da07a3-e71a-45b1-856d-ed07655b9be8"
  },
  "signature": "64-lowercase-hex-characters-produced-by-trusted-signer"
}
```

For a resolve assertion, set `purpose` to `resolve`, obtain a **new** one-use
nonce and signed short-lived timestamp, and preserve the binding byte-for-byte
in canonical field semantics. A correlation ID alone does not confer authority.

## Invariants and privacy

1. Only an allowlisted issuer with the correct HMAC key can register/resolve;
   signatures cover scope, target, callback, source/actor hashes and timestamps.
2. Only a fixed `exact-thread` callback route is accepted. It must equal the
   verified platform, owner and thread. Arbitrary callback URLs are rejected.
3. Scope is exactly `test-bench.terminal-result-delivery`, with an explicit
   expiration; it cannot authorize native effects or user-role injection.
4. Registration is once per correlation ID **and** once per
   `(repository, issue, job, case, operation)` identity. Duplicate registration,
   changed thread, foreign owner, changed source or actor cannot rebind a case.
5. Both register and resolve assertions require a fresh nonce; spent nonces
   survive restart in the encrypted registry. Expired assertions and bindings
   fail closed. Time checks require a bounded assertion lifetime.
6. Destination identifiers and signed assertions never appear in public
   return values or plaintext on disk. The local registry uses AES-256-GCM,
   a private `0700` directory and `0600` file, authenticated integrity,
   atomic replacement and a fail-closed exclusive writer lock. The process
   must secure its own private secrets and must not log resolved bindings.
7. Corrupt/unsafe/symlinked storage and concurrent writes fail closed; there
   is no automatic stale-lock deletion or reinitialization of corrupt state.

## Later phases and remaining proof

Phase 2 can use the opaque correlation ID to associate an immutable outbox
event, **not** to infer a callback destination. Phase 3 must build a trusted
platform adapter that can issue a fresh signed `resolve` request, securely
receive the private destination and enforce independent exact-thread ACKs; all
production senders remain hard-disabled until separately authorized. The
manual #398 handoff and optional #421 original-owner reminder are fallback,
not evidence of automatic wake. Phase 4 will produce the #511 interface and
fixture proofs.

This registry intentionally does not touch #499 worker, actor, operation IDs,
signed live receipts or Resolve projects. No auto-wake claim is made by #510.
