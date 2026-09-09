# Issue 41 — Spotlight OCR evidence and supervised remap backend

## Scope

Implement the accepted #40 evidence boundary behind a local TypeScript service:
canonicalize the #105-pinned Apple Vision frozen response envelope, persist
append-only in-process records for tests/adapters, require explicit
Editor/Producer confirmation, assess exact-context remaps, and project only
confirmed geometry into #29.

## Exclusions

No OCR account or remote provider, page capture, browser/UI work, automatic
confirmation or target movement, motion/compositing, Resolve/Fusion work,
scheduler, deployment, deletion, or edits to existing contracts/fixtures.

## Contracts and dependencies

- #29 supplies the unchanged alpha8 matte core. Its receipt bytes are retained
  separately in the immutable wrapper record.
- #39 supplies immutable capture/raster identity concepts. This service accepts
  an exact revision/raster reference and never resolves a latest capture.
- #40 authorizes the one additive `spotlight-evidence/v1` shared root and fixes
  confirmation/remap semantics.
- #105 pins the only executable profile: Apple Vision revision 3, accurate,
  `en-US`, language correction off. Frozen retained local outputs are used for
  all provider integration tests; no test invokes a provider or URL.

## Verification

- The shared contract rejects unknown record fields and unapproved variants.
- Five retained fictional Vision outputs produce repeatable element/evidence
  identities.
- Tests prove proposal-only evidence cannot derive, services cannot confirm,
  manual geometry derives, unique remaps remain proposed until accepted, and
  missing/ambiguous/contradictory/manual cases remain stale.
- Focused package tests/lint/typecheck and repository validation must pass.

## Producer acceptance path

Run the fictional proposal test, inspect its alpha plane (selected pixels are
zero alpha and surrounding pixels retain the dim alpha), inspect the wrapper
digest and profile/provenance fields, then run unique and ambiguous remap
fixtures plus manual fallback. Ambiguous output must have no confirmation or
matte until a redraw is explicitly confirmed.
