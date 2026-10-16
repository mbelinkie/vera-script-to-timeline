# Verdict: **GO**

**Basis:** I reviewed the source of the R3 fix delta (302154617 → 9d43f61) and how it integrates with the unchanged package, runtime and accepted compiler code. Tools were disabled, so I executed nothing. All test and fast-gate results below are as reported in the retained evidence. I did not repeat the whole-code review.

## D1 is fixed and the fix is genuinely tested

- **Fix:** `python/vera_timeline_agent/v2_package.py:1028-1032` now expects `"reused"` when the mode is `verified_reuse` and `"prepared"` otherwise. This matches accepted `compiler-core-v2.ts:1324` exactly. The same check runs again in `_verify_package`, so build, verify and attest all agree.
- **Positive case (`verified-reuse`, from the `reuse-nonzero-inpoint` golden).** The fixture builds data that the accepted compiler's `validPreparedBinding` (`:1066-1076`) would accept:
  - Delivered bytes are the original bytes, so `deliveredHash == contentHash`.
  - The delivered probe is a copy of the source probe, so `verification.probeHash == sourceSnapshot.probeHash`.
  - `derivation` is removed and `commands` is `[]`.
  - Decoded frame count, rate and time base are taken from the source frame map.
  - The source ID is re-derived exactly as the compiler's `deliveredSourceId` derives it.
  - The test asserts both `mode == "verified_reuse"` and status `"reused"` in the *published* package. It then attests and passes read-only preflight.
- **Reverse case:** `test_derived_preparation_cannot_claim_reuse_status` is a genuine negative test.
  - The report itself carries no hash that could fail first.
  - The default golden must be `derived_cfr`. Otherwise the fixture's `derivation.update` or the `pytest.raises` would fail.
  - So the refusal can only come from the new status rule.
- **Reuse geometry:** `_preparation_geometry` computes the package-relative origin `(I−O)/Fs − preHandle`. This matches plan §5.2 and the compiler's `exactLogicalTimeAtFrame`. It also fixes the old fixture's misuse of `sourceOrigin` as `packageStart`, which was only correct when the logged origin was zero.

## Other delta items check out

- **Role-list relaxation (`v2_package.py:654-670`).** The remaining checks are:
  - root < min(child)
  - root < min(overlay)
  - max(child) < min(overlay)
  
  These are equivalent to the compiler's check at `:391`. OTIO ordering (`_otio_track_order`), the runtime `_validate_composition` check and native `configure_tracks` all key on index, not list position. The new test would have failed under the old sorted-list rule.
- **Slate normalization.** `_render_slate` is used at both render sites (`:1464` and `:1950`). An out-of-range dimension now raises `V2PackageError` before staging, and raises it with the partial-retention message inside staging. The trust guard is unchanged.
- **Child fixture.** It now has its own:
  - occurrence, with owner `primary_slot`, `sequenceId`, `slotId` and source-in 0;
  - `derived_cfr` binding and preparation receipt;
  - delivered source ID;
  - event ID, using the compiler formula at `:654`;
  - provenance and report requirement.
  
  `deliveredRangeForOriginalRange` for this child yields `{0,24}`, which is consistent with `sourceOrigin = logged + a`.
- **Public coverage.** One parametrized test runs build → verify → attest (with the runtime self-check) → preflight for reuse, root-child-return, Quiet and Full. This closes R2 observation 1.
- **Comment fix:** `workflow_v2.py:965-966` is accurate, and the refusal behaviour is unchanged.
- **Scope:** every file in the boundary list is issue-owned and newly added. Contracts, compiler, preparer, renderer and #109 helpers are untouched.

## Evidence equivalence

- **Fast-test count.** 458 (FAST-R3) + 7 new tests (4 parametrized + 3 single) = 465. This matches the fresh Python run on 25c8ad7 with no skips. That confirms the repaired, formatted source has its own passing coverage.
- **Formatting repair.** It touched only the owned helper, and the AST is equal before and after, so the focused-R3 result on 84a6612 carries over behaviourally.
- **TypeScript and generator stages.** The FAST-R4 results on 7179408 remain valid, because nothing they read changed.
- **Labelling.** The combined evidence is labelled correctly: FAST-R4 is still a failure, and no full pass is claimed.

## Non-blocking observations

1. **Evidence record gaps.** Ruff scanned 447 files in FAST-R3 but 449 in the R4 remainder, and the R3 delta adds no Python files. Before claiming equivalence for the final full gate, identify those two files and confirm they are tracked. Also add the toolchain block (Node/npm/uv/Python) to `fast-r4-remainder-summary.json`.
2. **Package-layer layering refusal is untested after the rewrite.** The rewritten package-layer check (`:654-670`) has no negative test; only the runtime `_validate_composition` refusals exist. Attest's runtime self-check backstops it. A single swapped-index `_validate_manifest_semantics` test would close this.
3. **Reuse-specific compiler invariants are not re-checked by the package.** The package does not re-assert, for reuse:
   - `verification.probeHash == originalSource.probeHash`
   - `sourceRate == targetRate`
   - `decodedFrameCount == decodedPackageFrameCount`
   - `videoTimeBase == packageVideoTimeBase`
   - empty `commands`
   
   The compiler enforces all of these, and byte identity is enforced here. Adding them would be cheap hardening, but it is not required for D1.
4. **Child fixture still has stale records.** Its `visualSequenceResolutions` entry still references the former placeholder event ID, with a null source range, mapping and requirement key. The package does not read these records, but the fixture is only partly compiler-shaped. The package also still does not enforce payload-to-occurrence coverage (R2 observation 2), which is unchanged and fail-open only for hand-built inputs.

## Required next steps (unchanged)

1. Run a complete local `VITEST_MAX_WORKERS=1 npm run validate` on the final reviewed source.
2. Record its equivalence evidence and the frozen-boundary and generated-currentness audits.
3. Only then proceed to Automated acceptance.

#178 retains the real Studio, fractional-rate, audio and slate qualification.
