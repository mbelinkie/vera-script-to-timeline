# Issue 29 plan — deterministic confirmed-text Spotlight matte

## Objective

Implement the narrow, pure derivation core for GitHub issue #29.  Given an
immutable capture identity, its raster bounds, and already-confirmed OCR boxes
or an already-confirmed manual region, it produces a deterministic inverse
alpha plane and a canonical provenance receipt.  It performs no capture,
selection, OCR, persistence, remapping, or composition work.

## Scope and boundary

1. Add one private TypeScript workspace package containing the pure derivation
   function and its focused tests.
2. Require the selected evidence's capture hash to exactly equal the supplied
   capture hash before deriving anything.
3. Support either confirmed OCR word/line rectangles or one confirmed manual
   rectangle.  OCR rectangles are order-independent: the derived mask is the
   union of their padded capture-pixel rectangles.
4. Produce an `alpha8` inverse-alpha plane: a selected pixel has alpha `0`
   (transparent, leaving the source bright) and every other pixel has the
   requested dim alpha.  The byte plane is deliberately not an artifact-file
   encoding or a Resolve/Fusion representation.
5. Produce canonical JSON that records the capture hash, source kind, accepted
   geometry, clamped derivation parameters, dimensions, and SHA-256 of the
   alpha bytes.
6. Reject invalid/stale evidence and invalid geometry with named diagnostics;
   no result object exposes a matte or receipt on failure.

## Explicit decisions

- Capture-pixel geometry is half-open (`x`, `y`, `width`, `height`) and must be
  finite safe integers, positive in extent, and wholly inside the exact capture
  dimensions.  Out-of-bounds geometry is rejected rather than silently moved.
- `paddingPx` and `dimAlpha` are bounded derivation controls and are clamped
  to `0..64` pixels and `1..255` respectively.  Capture dimensions are capped
  at 16,777,216 pixels before allocation.  This satisfies the bounded-input
  rule without disguising invalid evidence geometry.
- The dimmed preview interpretation is a black overlay using the returned
  alpha plane.  Thus, on a synthetic white capture, a selected pixel remains
  255 while an outside pixel is `255 - dimAlpha`.  Rendering, feathering,
  file encoding, and application integration remain excluded.
- Canonical receipt fields and sorted accepted OCR geometry make the output
  stable even when a caller supplies the same confirmed OCR boxes in a
  different order.  The caller owns durable artifact storage and higher-level
  treatment identity.

## Exclusions

- OCR execution/provider/model choice, author selection UI, DOM evidence,
  stale-remap decisions, capture or recapture, storage, network access,
  database/API/shared-schema changes, timing, motion, Fusion/Resolve, and
  deletion.
- No change to frozen `/contracts`, `/fixtures`, generated types, or accepted
  golden files.  The new unit test contains synthetic expected byte arrays as
  the issue-required focused golden evidence; it does not alter a frozen
  fixture.

## Inputs and dependency justification

- #27 is closed and `Done`; it supplies the only prerequisite: an exact,
  immutable `CaptureRevision` and revision-bound `SelectionEvidence`.  This
  module models only the values it needs and does not amend that accepted
  contract.
- No new runtime dependency is needed; Node's built-in SHA-256 supports the
  deterministic receipt.

## Automated checks

1. Focused Vitest coverage proves byte-identical alpha/receipt output across
   repeated runs and equivalent OCR-box ordering.
2. Synthetic OCR and manual cases verify selected pixels remain transparent
   and outside pixels carry the requested dim alpha; their white-background
   composite values are asserted as 255 and 64 respectively.
3. Validation coverage verifies malformed/out-of-bounds geometry, stale hash,
   and hash mismatch fail without exposing output artifacts.
4. Run the package test, lint, typecheck, and the repository validation gate.

## Producer acceptance checklist

Automated evidence will be supplied with the commit.  For the remaining
Producer review:

1. Run `rtk npm run test --workspace @vera/spotlight-matte`.
   **Expected:** the confirmed-text and manual-geometry tests pass, including
   exact alpha bytes and receipt bytes.
2. Open `packages/spotlight-matte/test/spotlight-matte.test.ts` and review the
   synthetic white-capture assertions.
   **Expected:** selected pixels composite to 255 and surrounding pixels to 64
   with `dimAlpha: 191`; the manual fallback has the same behavior.
3. Review the stale/hash-mismatch test in that file.
   **Expected:** it returns a named failure and no matte or receipt.
4. Review the receipt assertions.
   **Expected:** it pins the exact capture hash, source kind, dimensions,
   parameters, and alpha-byte digest.
5. Reply `Accepted` or identify the first incorrect output.  Keep #29 in
   `In review` until that response.
