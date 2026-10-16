# Verdict: **NO-GO**

**Basis:** source-reading review of the delta from 1457e52 to 3021546 against accepted 7867fa4. Tools were disabled, so I executed nothing. Retained evidence is taken as reported.

**R1 blockers B1–B4 are fixed, and the two layers now agree:**
- **B1 (returns):** both validators use the strict interior rule (`root_start < frame < root_end`). The package layer now also counts root-track placeholder events, which matches the compiler's `rootEvent` lookup at `compiler-core-v2.ts:1416`.
- **B2 (audio comparison):** the Fraction-to-Fraction comparisons are correct.
- **B3 (readback):** readback now covers every actual track slot and every marker field.
- **B4 (topology):** roles are disjoint and index-ordered, and OTIO stacks tracks by kind and index.

**Additional fixes are sound:**
- **Canonicalizer parity:** I checked separators, empty containers, control-character and lone-surrogate escaping, integral-float normalization and ASCII key ordering against `compiler-core.ts:146-166`. The executed TypeScript parity test is real evidence, not a copied implementation.
- **Strict JSON:** both parsers refuse BOM, duplicate keys, NaN and overflow.
- **Document closure:** the textHash and settingsHash checks match `compiler-core-v2.ts:1370-1377` exactly. The compiler version and event provenance checks match the compiler's emission.
- **Child primary_visual and generated slates:** child `primary_visual` matches `:723`. The generated-slate branch matches `:412` and `:1438`.

One blocking defect remains. It sits in the same hunk the fix edited, and it is the same class as R1's B2: accepted compiler output is refused.

## Blocking finding

### D1 — Every ready report that contains a `verified_reuse` binding is refused

- **Where:**
  - `python/vera_timeline_agent/v2_package.py:1026-1035` requires `item.get("status") == "prepared"`.
  - The accepted compiler, at `packages/contracts/src/compiler-core-v2.ts:1324`, emits `status: binding.mode === "verified_reuse" ? "reused" : "prepared"`.
- **Trigger:** any same-rate source that the compiler binds in `verified_reuse` mode, for example a 24000/1001 source on a 24000/1001 timeline. The report is fully ready, but the build raises "build report preparation result differs for requirement …" before publication.
- **Impact:**
  - Same-rate verified reuse can never be packaged, even though the package layer explicitly supports this mode elsewhere:
    - `:1194-1198` checks reuse identity;
    - `:1230-1231` checks the reuse mapping origin;
    - `:1350-1354` handles the reuse audio first-sample time.
  - This breaks plan §5.4 ("compatible same-rate video uses `verified_reuse`") and the first P8 case ("Same-rate 24000/1001").
- **Why tests missed it:** every fixture binding is `derived_cfr`. `tests/issue177_package_fixture.py:460` calls `binding["derivation"].update(...)`, which presumes a derivation exists. So reuse is never exercised.
- **Smallest fix:**
  - Require `"reused" if binding["mode"] == "verified_reuse" else "prepared"`.
  - Add one fixture scenario that converts a binding to `verified_reuse`:
    - remove `derivation`;
    - set `deliveredHash`/`probeHash` equal to the original's;
    - set `sourceOrigin` to the logged origin;
    - set `sourceRate` equal to the target rate;
    - set `decodedFrameCount` to `decodedPackageFrameCount`;
    - set `videoTimeBase` to `packageVideoTimeBase`;
    - set the report status to `"reused"`.
  - Run that scenario through public build → verify → attest → preflight.
  - Add the reverse negative case: a `derived_cfr` binding labelled `"reused"` must be refused.

This changes source, so the policy requires fresh focused and fast runs, a delta review, and then the full gate.

## Non-blocking observations

1. **Coverage gap for return and source-audio packages:** builder-produced packages of these two shapes are never attested or preflighted.
   - `test_public_builder_handoff_preserves_root_child_overlay_return` calls the private `_validate_composition`, not `attest_package_v2` + `run_workflow_delivery_v2(preflight)`.
   - The Quiet/Full tests stop at `verify_v2_package`.
   - R1's B1 failure surfaced exactly at attest's self-check. Attesting and preflighting those packages is cheap and would close the gap.
2. **The child fixture is not compiler-shaped:**
   - `_make_child_visual_ready` gives the child the root's binding hash and mapping, and adds no `occurrenceResolution` for payload `…020`.
   - A real compiler would emit `MISSING_OCCURRENCE_BINDING`.
   - The package layer accepts it because it does not check payload-to-occurrence coverage.
   - So this proves the child role is accepted, not that real child bindings are.
3. **Slate rendering errors escape the package error type:**
   - `render_placeholder_slate` raises raw `ValueError`/`TypeError` for timeline dimensions outside 16–16384 px or above 67M pixels. The schema permits those dimensions.
   - From `_media_artifacts` (`:1459`) the error escapes the build before the `try` block, so it is not a `V2PackageError`.
   - Slates are also re-rendered 4–5 times per build. At 4K that is a noticeable cost.
4. **Track-list ordering is stricter than the compiler:** `v2_package.py:648-649` also requires `childTrackIds`/`overlayTrackIds` to be listed in index order. The compiler (`:391`) does not require this, so the package refuses some valid configurations. This is fail-closed; either document it or drop it.
5. **Stale comment:** `workflow_v2.py:964-967` says no rendered card is bound, which is no longer true. The refusal is still correct.

## Uncertainties (not counted as blocking)

- **U1 — authority of the liveContentHash formula.** The parity test proves canonicalizer equality only. Its document's hash was produced by the fixture's own recomputation, so it is circular about the formula. The formula matches accepted `issue-189-v2-omission.ts:403-405`. Please confirm whether the unmodified accepted #173 golden inputs (and `applyVisualSequenceEditV2`) satisfy it. If they don't, real documents from other producers will be refused, which fails closed.
- **U2 — temporary presenter stills cannot be packaged.**
  - The compiler always attaches a `TEMPORARY_PRESENTER_STILL` warning, a `REPLACE_TEMPORARY_PRESENTER` recovery action and a `manual_completion` disposition.
  - The unchanged readiness and disposition gates (`:548-558`, `:1001`) refuse all three.
  - The fixture's `manifest["authoringDefaults"] = …` overwrite (`:683`) would also hide the compiler's effective-presenter substitution (`compiler-core-v2.ts:1409-1411`).
  - Please confirm whether excluding this from the #177 "still/default composition" criterion is intended.
- **U3 — reproducibility of slate bytes.** These depend on the zlib build behind the locked CPython 3.12.14. Builder and verifier must share it; the Resolve runtime only rehashes, so it is unaffected.

## Evidence

- FAST-R3 on f5e5ac6 is accurately recorded: exit 0, no skips.
- Later commits are reported as evidence-only. I did not independently diff them.
- No full qualifying pass exists, and none is claimed.
- Because D1 requires a source change, the FAST-R3 evidence cannot be reused for the final gate.
