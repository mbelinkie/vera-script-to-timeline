# Independent fix-delta review — GO

Actual Claude Opus5.5 high effort, CLI2.1.299 (Claude Code), tools disabled; source 53cfffdede310ae1b552d4ac022b2c1150e082f4, accepted main deaa75c90b5486e500cb69266faa7bdf09697efc, session 7d7f36b9-5529-4d0b-bdec-57a0eae7a99a. Actual exit0/is_error=false/sourceStillCurrent=true. Raw result SHA256 3f6f60915bde4a348d45d141100372844b27df97c20a6c5e27949d45d0378dbb; full source/context/prompt/command/tool/PID receipts retained in out/issue192/claude-2 and review-input-2.json. Both processes drained naturally. This verdict covers the initial NO-GO fix delta and is not full acceptance.

## Verbatim reviewer result

# Verdict: **GO** for the fix delta

This review approves the fix delta only. It is not acceptance or closure. I read only the supplied source. I executed nothing and cannot confirm any runtime or fast result. The test bodies below are consistent with the reported results, but I have not reproduced them.

The original blocking finding B1 is resolved in #192-owned code. I found no new blocking defect in the delta or in the implementation it connects to.

---

## Original B1: resolved

**Session flow.**
- `ProofSessionV2.evidence` (`roundtrip_v2_proof.py:371-381`) does three things:
  - It publishes the complete record immutably to `authenticated-evidence/<identity>.json`. It does this only after the B1 view check, `roundtrip_inference_observations`, #191 `verify_selected_omission_v2` (status must be `verified`, `:360`) and a valid `_pure("infer")`.
  - It pins the record in `self.pins`, so every `_current()` call rechecks it.
  - It registers the record in `authenticated_evidence`.
- The single-case branch of `_observations_current` (`:231-240`) checks three things:
  - the case's identity is registered in this session;
  - the pinned bytes parse back to the same case;
  - `bindingJson` equals this session's `binding_pin` bytes.
- The case object is the identity, so `baseline`, `current.receiptJson`, `omission` and the binding are all covered. A hand-authored omission, a foreign binding or a forged receipt changes the identity and is refused.
- `compose`, `stage`, `proposal`, `_decide_once` and `accepted_revision` all go through this check before any pure step, authority call or ledger write.
- Mixed ownership is also refused. A case presented with a different owner fails, because that owner's registry lacks it. Bindings differ per evidence root.

**Test coverage.** The public test (`test_issue192_public_path.py:420-440`) checks four forgeries (binding, baseline, receipt, omission) against four operations (compose, stage, proposal, decide):
- each must refuse with "not authenticated";
- no `inference-decision.json` or `revision-decision.json` may be written;
- there must be zero adapter calls.

**Revised preflight.** `verify_revised_preflight_v2` (`roundtrip_v2_revised_build.py:184-248`) now:
- requires one `authenticatedCases` entry per case, in strict order;
- requires each case's evidence pin to parse and hash to that case;
- requires each binding pin's bytes to equal the case's `bindingJson`;
- requires the evidence and binding pins in `verifiedFiles` (via `required`, `:407-413`).

For C it also requires:
- all 14 #191 inputs, as a superset of mandatory keys;
- pins that exactly match `inputHashes`;
- the profile hash to equal `omission.profileHash`;
- a non-empty profile `sources` list, all present in the inventory.

The empty-C, missing-inventory and wrong-C-media negatives (`:687-709`) cover the vacuous case.

**Media-pin fix.** This change is acceptable.
- Omission pins use the existing descriptor-safe streaming `_file_hash` (`O_NOFOLLOW` walk, `nlink==1`, stat-unchanged), with an absolute-path check and three-way hash equality (`:238-247`).
- `profile.json` still goes through the bounded `pin_bytes_v2`.
- No shared reader limit was widened.
- Native `_guard` re-runs the whole verifier on every operation, which covers time-of-check/time-of-use changes.

**Residual, non-blocking.** The standalone verifier still cannot establish provenance alone. A file author could create a self-consistent evidence/case/inventory set elsewhere. Even re-running inference in the verifier would not prove it was authentic. That provenance check is the documented duty of the trusted `revised_proof_lineage` and `revised_native_lineage` ports (R3 handoff). This is what the original review asked for in the session layer. See hardening item 2.

---

## N1: resolved, with limits

- `_verify_exact_view` (`:795-823`) checks AV peer topology. It recomputes the expected linked set from authored `primary_visual`/`source_audio` kind, `blockId` and `payloadId`.
- For each audio item it requires exactly one route, gain equal to the package view (`gainDb or 0`), and a channel map matching the source's channel count.
- The Quiet pair fixture now models reciprocal links for Quiet under narration, with a deliberate unlinked-copy refusal.
- The gain/channel tests use a genuine audio-bearing capture.
- These tests qualify only the shared comparison guard, not a native audio save/reopen.
- The expected topology assumes #177 links every same-block, same-payload AV pair. If real delivery differs, the check fails closed and #178 must confirm.

## N2: resolved

`_require_accepted_rebuild` (`:663-668`) now requires `baseline.original != R16_INPUTS` for the synthetic shortcut. The synthetic lane forces originals to equal execution hashes, so R16 bytes cannot use the shortcut under either lane label. This is tested in `test_issue192_proof.py:311-315`.

## N3: resolved

`request_fresh_delivery` (`:686-690`) requires a revised-native boundary for any `PreparedRevisedProofBuildV2`. It refuses before any adapter call (`public_path:737-741`).

## N4: resolved

Each session gets a per-session `uuid4` capture namespace (`:92`, `:247-251`). The second-session test on the shared boundary (`test_issue192_proof.py:85-92`) exercises the former collision.

## Actual-D1 gap: closed for automated scope

The test prepares 200 frames while the injected provider returns 187. It then checks:
- **Refusal point.** The real #191 `finalize_replacement_row_v2` refuses, through the unchanged `finalizeReplacementV2` "blocked/…" check. This happens before `row-handoff.json` or `replacement-preview.json` is published (`roundtrip_v2_narration.py:417-428`).
- **Probe evidence untouched.** The probe's `generation-inputs.json` hash is unchanged, checked twice.
- **Clean restage.** The restage uses a fresh session root and a fresh generation root. Replay goes through the existing intent/cache path. `old_intent` requires a verified synthesis cache, and `provider.calls == 1` is asserted after every step, including the final rebuild.
- **Placement.** Final placement comes from the compiled manifest (`1082 + D1 − 200`, D1 = 187). Production code contains no D1 constant and no six-frame subtraction.
- **No relaxation.** The delta touches no core, #191 or finalizer code.
- **Restage caveat.** The restage duration `durationSamples // FRAME` is test-only orchestration, valid because the fixture is frame-exact and asserted equal to compiled D1. A real run must take D1 from the compiler/finalizer, not floor division. This should be noted for #145.

---

## Non-blocking hardening

1. **`roundtrip_v2_proof.py:814`.** `wave.open(item["sourcePath"])` reopens a pathname, which goes against #190's stated rule against reopening WAVs by path. It raises `wave.Error` rather than `ProofNativeError`.
   - It cannot cause a false acceptance. Capture's `_derive_audio` (`roundtrip_v2_native.py:923-927`) already bound `channelMap` to the hashed bytes, so this line can only add refusals.
   - Fix: drop it in favour of the capture-time binding, or read through `_operator_bytes` with a hash check.
2. **`verify_revised_preflight_v2:189-201`.** Two cheap additions:
   - Require each case binding's `attestationHash`, `proofPackageHash` and `sourceHashes` to equal `baselineNative`/`baselineProof`.
   - Have `FakeAuthority` model a provenance ledger for `revised_proof_lineage`.
3. **`request_fresh_delivery:686`.** Also compare `fresh.revised_preflight_hash == package["preflightRawHash"]`. Today this is implied only by the unique per-request attestation path.
4. **Test precision.**
   - The `links` attack (`test_issue192_proof.py:246-255`) and the N4 refusal use `ProofNativeError` without a `match=`, so any refusal would pass.
   - The binding-equality branch at `:237-240` is shadowed by the identity check and not independently exercised.

---

## Remaining acceptance limitations

- **Full local gate pending.** `VITEST_MAX_WORKERS=1 npm run validate` on the exact final tree is still required.
  - The delta touches WAV/PCM-reading and render-adjacent paths. I would treat it as media-sensitive and ineligible for cloud substitution.
  - Reusing fast3 (2b396dc) and runtime12/runtime11 for 53cfffd requires the owner to prove the later documentation commits are not read by any lint, format, generation or test inputs.
  - I have not verified any reported pass.
- **Synthetic delivery only.** A successful fresh delivery and save/reopen is shown only through the integer synthetic transport double. The genuine revised path truthfully stops at #177's fractional-rate/source-audio refusal before adapter creation.
- **Fake ports.** All authority, Resolve, probe, provider and cache ports are injected fakes. Nothing qualifies real Resolve, acoustic selection, provider execution, listening, or the Producer gates in #178/#145.
- **Unchanged guards.** The original R16 document-and-dependencies guard, the #190 initial route and the frozen contracts, fixtures and goldens are unchanged by this delta.
- **Workflow gates.** Merge, In-review status and Automated closure still require the retained full-gate evidence. Exit success is not acceptance.

## Owner disposition

B1, N1-N4 and actual-D1 gap are resolved under this actual independent verdict. The accepted #190 WAV rule requires a follow-up in owned _verify_exact_view: securely read/hash the exact opened PCM bytes rather than reopening by pathname. Affected source-bound runtime/fast evidence must be refreshed and this narrow production delta re-reviewed before final full validation.

Other nonblocking recommendations do not reveal false acceptance under this bounded trusted-port design. Complete case provenance is authenticated in the owner session; independently constructed revised records additionally require the documented trusted revised_proof_lineage/revised_native_lineage ports and cannot self-certify. The unique per-request attestation/execution-input identity already binds the revised native route; raw-preflight equality is implied. Existing broad refusal tests supplement exact-specific forgery/audio tests; no requirement to expand accepted shared provenance contracts or ports here. These are retained reviewer recommendations, not qualification of fakes.

For #145: a real restage must obtain D1 from actual compiler/finalizer output. The test-only durationSamples//FRAME shortcut assumes and asserts frame-exact synthetic PCM; it is not a real orchestration rule. Real Resolve/acoustic/provider and #178/#145 gates remain open.
