# #192 additive revised-native draft handoff r3

**Unexecuted candidate.** No test/type/lint/fast/full/review/media/native/provider
job was launched. #202 retains the coordinator's heavy slot. This handoff is a
reviewable source/API delta, not accepted validation or installed capability.

## Authority and baseline

Direct Producer resume clears the previous usage hold for this same owner;
account change alone would not. Own actual usage read46%/51%, then59%/53% used,
below97%, accountdf07e429-f81e-41d4-8124-a6bba181ddb6. No credit/reset purchase.
CN-192-R1 approved note SHA92a28cd3fba89f176d4f633d640f35ef11a2f6564b40f9f6aebabd3c6cb218c8.
#190 owner delegation SHA27028207695429908492f98ed06ad46a1ab4bd437230f3fa90f7c2323ade7411
explicitly delegates only the additive public revised-native entrypoint, common
initialization and revised lineage guard in this #192 checkout.

Accepted #190 merge baseline `bd6048b02604954df037bf0b2dd01906e986d19d`, tree
`372ab23daa550780ce7bb9eba1d159706efd4472`, is source-identical to reviewede17.
Rebase completed cleanly: all six commits in range-diff are `=`; former8e335c8
becamee4a0408ac73d984a877253f83474a61cb0b1eed4 before this amendment.
#202 fix77b82 remains provisional; imported rebase commitc442595. Its core hash
stillf6669b700fd676a451a2402c0390cb9fdfc726409c393df91ca9e7d0120069cf.
No locally edited core/test, changed compiler/package/shared boundary or initial
R16 preparation source. #202 actual Closed/Done is still required before claim.

## Additive public API

```python
NativeProofBoundaryV2.from_revised_proof(
    resolve,
    *,
    attestation_path: Path,
    attestation_hash: str,
    proof_package_path: Path,
    proof_package_hash: str,
    revised_preflight_path: Path,
    revised_preflight_hash: str,
    evidence_root: Path,
    authenticate: ReceiptVerifier,
    authority: bytes,
    code_hashes: JsonObject,
    read_controls: ControlReader | None = None,
    adapter_factory: Callable[[Any], Any] | None = None,
) -> NativeProofBoundaryV2

verify_revised_preflight_v2(
    preflight: JsonObject, *, authenticate: ReceiptVerifier, authority: bytes,
) -> None
```

The ordinary constructor keeps its initial closed shapes and exact versions and
refuses revised records. Its tail moves to common binding initialization; native
locks, intent/effect/completion/recovery, capture, render and public #177 delivery
semantics are retained. A separately constructed revised boundary exposes those
same public methods; callers never invoke private effect helpers.

New closed proof envelope: `issue-192-v2-revised-proof-package/v1`, exact keys
`schemaVersion evidenceLevel preflightHash preflightPath preflightRawHash
requestHash package verification attestationPath attestationHash`. `preflightHash`
is the owning record canonical identity; path/rawHash bind actual opened bytes.
The initial `issue-189-v2-proof-package/v1` envelope is unchanged.

Revised preflight remains `issue-192-v2-revised-preflight/v1`. Exact keys:
`schemaVersion status evidenceLevel lane requestHash originalInputs executionInputs
sourceHashes verifiedFiles manifestHash reportHash needs packageVerification
unchecked revisionBinding`. Its `revisionBinding` is closed:
`lane request originalFiles baselineInputs baselineProof baselineNative stagedInputs
evidence candidate result decision`. File references use exact `{path, sha256}`;
stagedInputs is null without C, otherwise exact document/dependencies pins.

Revised native binding is `issue-192-v2-revised-native-binding/v1`. It retains
the initial binding fields, adding `revisedPreflightPath`,
`revisedPreflightRawHash`, `revisionBinding`. Every inherited authority callback
therefore receives the revised lineage. Each operation guard rechecks all raw
preflight/envelope/package/source/file inputs, verifies the closed revised
lineage, and invokes trusted `revised_native_lineage` freshness before effects,
reads or render polls. This callback must verify any external current sequence
or decision registry; unchanged on-disk bytes cannot establish that freshness.

The public revised parser consumes evidence/candidate/result/decision records:
actual proposal identity and before document/dependency identities; isolated
case hashes, complete raw/derived/receipt input pins and C omission inputs; original
document AND dependency raw identities; baseline public package/native binding;
actual execution equal to the accepted result; staged C document AND dependencies
equal to the #191 handoff; fresh media/receipt/probe/PCM pins. Trusted
`revised_proof_lineage` receives all consumed records and explicit context and
must authenticate isolated A/B/C and decision/receipt provenance. Parsing/matching
hashes are insufficient. Required pins cannot be omitted from verifiedFiles.
Fresh package input/output bytes must match actual proposal/preflight and public
attestation/load result. Baseline/prior targets and assets remain retained.

## Invalidation and pending verification

The native source changed from #190 raw98ec3c098f1ab16a6b3351758de9fe8d5d3c7d5154de46c406ec9b28a534b1e4
to844d99dc99f52cf4457546e38dd1df1f1d8b77a17cb6248f87fc3a6d93e219c8.
This invalidates precomputed source graphs, proof packages/attestations, native
bindings and affected test receipts from older trees. Rebuild/rebind through the
public ports on the delivered combined tree; do not update old receipt hashes.
Old frozen owner evidence remains valid only for its own unchanged tree.

New combined public-path tests select the new entrypoint and assert initial
constructor refusal, wrong raw pin refusal before binding, and trusted external
decision-registry drift before deliver/capture/recovery with zero new effects.
Previously written original/source/decision/timing/media/package/omission and
uncertain-provider negatives remain. Actual B1/B3 service/cache/core/package path
must pass; transport doubles cannot supply final criteria evidence.

Required after coordinator grant: actual locked tools/input receipts; affected
focused TS/Python checks, unchanged initial #190 regressions; lint/types/generated
and fast; independent adversarial #190 boundary and #192 integration review;
fix/delta review; complete qualifying exact combined-tree final evidence. Then
actual accepted dependency reinspection, genuine Ready/claim and Automated gates.

Public #177 fractional/source-audio/treatment creation refusals remain before
adapter construction. Temporary On Camera compiler diagnostics retain the actual
public package refusal; the new intentional static holds are sanitized fake inputs
only. #178 actual installed/native and #145 provider/acoustic/Producer/visual/
listening gates remain. No initial guard, shared contract, fixture/golden or
accepted acceptance test change; no qualification flag/bootstrap/discovery.
