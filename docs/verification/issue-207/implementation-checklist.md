# #208 — required implementation evidence for CN-207-ID1

Design checklist only. No tests or app checks in this file have been executed
by #207. [The note](../../plans/issue-207-target-identity-handoff.md) selects the
exact scope; #208 remains undispatched with External acceptance.

## Meaningful negative cases

Use source-tagged fake getters and call-order assertions to prove refusal at
the intended seam, not an earlier unrelated binding error. Never label them
actual injected evidence. Include successful synthetic round-trip validation
only to exercise the closed records; it does not qualify Studio.

| Attack or failure | Required evidence |
| --- | --- |
| Missing/wrong operator confirmation; `readOnly:1`; duplicate/unknown JSON keys; scalar root; NaN/infinity; overflowing float; boolean version integer | Refusal before imports/getters, no authority synthesized by request preparation. |
| Wrong project name, absent project, wrong timeline name, absent timeline | Project mismatch prevents timeline access; timeline mismatch prevents its UID read. No search or selecting setter. |
| Missing/blank/wrong-type UID; same-name target replacement between reads; either name/UID changes | No consumable target. Both UIDs are opaque strings; do not assert global uniqueness across project/timeline namespaces. |
| Unsupported product/build, no injection, prior loaded VERA modules | No usable receipt and no fallback connection/import. |
| Source/note/approval/authority/request drift before import, between reads, after reads and before output; installed/host pin mismatch | Correctly source-tagged refusal. Started provenance precedes imports. Identity is not copied from expectation. |
| Extra/missing/duplicate release entries, changed launcher bytes, undeclared installed code | Refusal before loading installed modules. Exact complete inventory, including new identity module. |
| Handcrafted matching authority/request placing output inside repository, prepared release, installed plugin or approval/authority/request; reverse containment; symlink/hardlink/case/firmlink alias | Reach path checks with otherwise valid binding. No file created in any protected input root, including bootstrap refusal. |
| Changed file descriptor/extent, swapped ancestry during read/write, output collision | Bounded safe refusal; no overwrite/delete. If safe retention unavailable, Console states that fact. |
| Future/reversed/expired timestamps, clock rollback during operation, age exceeds 30 minutes before consumption/preflight | Refusal; no expiration extension or implicit revival. Required completed-receipt request/restart transition within the window remains eligible after separate confirmation and UID recheck. |
| Two concurrent launches, repeated request, crash after reservation, uncertain output, replayed/copied receipt missing original lineage | One reservation wins before getters; no retry/resume of old invocation. New capture needs fresh authority/root/UUID. |
| Failed/synthetic/preflight result passed as identity; changed hash/read pair/UID/result status; mismatched operator acknowledgement | Receipt-backed authority issuance refuses; a successful hash calculation alone is insufficient trust. |
| Two simultaneous receipt consumers or crash after consumption reservation | At most one capability authority; consumption is irreversible within the audited attempt. New identity capture required on uncertain issuance. |
| Capability request/v2 with changed receipt/confirmation/source/release/expiry, correct names but wrong live UIDs | Refuse before general capability reads; retain all #204 existing guards. Legacy v1 must not claim receipt-backed route. |
| Every success/failure branch | Exact finite allowlist; zero setter/save/import/export/render/queue/provider attempts. No accepted-test, fixture, golden or ordinary-build guard change. |

Independent adversarial review must inspect trust provenance, early imports,
safe refusal paths, clock/replay/consumption races and target ambiguity. Review
fix deltas and rerun their checks. New source invalidates #204's prepared release
and earlier source validation equivalence; no automatic GO inheritance.

## Actual operator/Studio evidence, after separate grants

1. Record Closed/Done #207 acceptance with note hash, coordinator's exact #208
   integration baseline/shared-seam grant, reviewed delivered revision, focused/
   fast results and required independent review. Prepare fresh complete release,
   inventory and private paths before requesting installation/runtime authority.
2. Operator personally supplies exact visible current target names and confirms
   saved/disposable/nonproduction/read-only/None. Retain the operator-only host
   authority, issuer/tool/version, request and approval hashes. No agent supplies
   these confirmations. The known #109 names are only an optional candidate.
3. Through #109's manual quit/archive/copy/restart flow, retain actual installed
   source/inventory/request hashes. Preserve v1 and other plugins. Launch the
   named Workflow Integration once; no concurrent UI interaction or fallback.
4. Retain actual pre-import bootstrap reservation/provenance, injected runtime,
   Studio 21.1.1/build 10, two adjacent complete actual reads and immutable
   result/hash lineage. Expected `identity_observed`, with all qualification/
   verification/effects flags false. A failure retains the precise boundary;
   menu visibility or fake tests cannot establish success.
5. Operator confirms the observed names/UID pair describes the personally
   selected target and acknowledges the exact result hash. Retain separate
   receipt-consumption reservation and new capability authority/request/v2.
   Use the required request/restart transition and re-open the same saved target
   within expiry; retain fresh confirmation and actual UID recheck in #204.
6. Retain #204's actual getter-only preflight/result and gaps, or exact safe
   refusal. Identity success alone is not #204 acceptance. Preserve its current
   consumer owner and separate authority. No control/render effect follows.
7. Operator confirms unchanged visible target/timeline/settings and no
   production target involved; retain actual native call/effect observations
   available through this finite flow. Do not claim a full content fingerprint
   from identity getters or relabel attestation as independent API proof.
8. Fix actual runtime findings, delta-review and affected checks, then final
   complete qualifying evidence on final delivered source under VERIFICATION_POLICY.
   Record exact source/input/tool/environment/command/exit correspondence and
   frozen-boundary checks. Give #204 the exact integrated revision, release,
   receipt hash/UIDs, consumption ancestry and held gates. No automatic successor.

An unavailable UID getter is a real engineering refusal, not a Producer task
to discover invisible UIDs. It can document a failed boundary, but cannot yield
a usable receipt, unblock successful #204 execution or fabricate External success.
