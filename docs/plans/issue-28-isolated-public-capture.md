# Issue 28 — isolated public-page capture spike

## Scope and authority

Implement only #28 against producer-accepted #27 (artifact commit `9143518`,
merged in baseline `12c262c`). #27 is closed/Done; #28 was Ready with Sol/high
routing and no owner before this task claimed it. The product specification
§8.4, slice 5.3, and deferred monitoring decision remain authoritative.

Build a standalone, macOS-only, **offline fixture transport** driving real
headless Chromium. The browser receives synthetic anonymous public HTML through
interception; an OS sandbox denies all network access and restricts filesystem
access. There is no live transport, DNS lookup, attached browser, or profile
import. Network answers/peers in the fixture transport are explicitly synthetic;
receipts must never represent them as live connection evidence. Unsupported
platforms fail closed. This proves local acquisition/publication mechanics;
production egress, deployment isolation and authorization remain later work.

Use a fixed, hashed profile, one disposable browser/context per actual attempt,
GET/HEAD admission, guarded redirect/subresource fixtures, verified PNG output,
restricted complete receipts, and immutable local revision bundles. Explicit
new command keys recapture; duplicate delivery returns the original outcome.
Every successful recapture creates a revision; exact PNG bytes alone may reuse
an earlier artifact. Earlier receipts and artifacts never change.

## Exclusions and touched boundaries

- No production API, database, object store, scheduling, UI, shared contracts,
  generated types, compiler/build integration, selections/pins, OCR,
  notifications, authenticated capture, cookie import, or deletion workflow.
- No changes to `/contracts`, `/fixtures`, accepted tests or goldens. New
  authored, frozen synthetic fixtures live only in the standalone spike.
- New files under `spikes/public-capture/`, this plan, and a review guide only.
- #27 supplies the required trust, provenance, identity and revision semantics.
- Standalone pinned `playwright` dependency: actual browser contexts/rendering
  and request interception without changing application dependencies.
- Standalone pinned `pngjs` dependency: bounded PNG decoding and validation
  before publication. Neither dependency enters the production workspace.

## Implementation and verification

1. Write focused failing tests for public URL/address admission, immutable
   revisions, duplicate commands, byte reuse, and publication failures.
2. Implement fail-closed fixture transport and macOS browser sandbox, with
   fixed finite bounds and explicit warning/review classification.
3. Publish an entire verified bundle by same-filesystem atomic directory
   rename under an exclusive local writer lock. Keep incomplete staging out
   of committed history. Fault tests kill subprocesses at staging/commit
   boundaries and recover by the same command key. Retain failed attempts
   and staging for inspection; no automatic retry or deletion.
4. Exercise actual Chromium with frozen unchanged/changed pages, redirects,
   blocked resources and cookie probes. Verify denial before navigation for
   unsafe top-level URLs; synthetic peer/mixed DNS/redirect tests never contact
   private or real networks. Test OS sandbox denial independently.
5. Verify receipts, PNG decoding, exact-byte comparison, previous-file hashes,
   idempotency, concurrent writer exclusion, resource deadlines, corruption
   rejection and uncertain publication recovery. Run repository validation.
6. Commit/push the bounded result, retain exact commands/results and a producer
   checklist, and move #28 only to In review. No Done or next-task dispatch.

## Producer acceptance outline

Run the documented offline demo, inspect the first PNG and restricted receipt,
run unchanged and changed recaptures, and compare distinct attempt/revision IDs
and exact byte hashes. Run unsafe-URL and sandbox tests; confirm zero live
transport and no cookie/profile import. Inspect fault recovery and earlier
revision hash preservation. Report `Accepted` or the first failing numbered
step. Automated evidence does not substitute for producer acceptance.
