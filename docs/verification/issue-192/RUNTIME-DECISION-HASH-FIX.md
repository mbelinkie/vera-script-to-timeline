# #192 compiler result identities versus raw-file identities

Runtime5 tested6395c2a4e76fd8d9cdd5ab38c3fc952e4a6c462d and naturally
exited1 without signal:1 failed in110.29s. Verified immutable log SHA256:
1877bdf83b7369444aa33ef0e1f371f9a75e98762bf95674714f62e014157364.
Public capture, A/B inference, C renders/omission, actual narration synthesis,
cache replay (one provider call), finalizer and proposal completed before the
new test assertion compared priorDependenciesHash using compact Python JSON.
The remaining transport and #190 regression nodes were not reached.

Related owned comparison audit confirmed #191 priorDependenciesHash uses
compiler sha256CanonicalJson(prior), and #202 historyHash/result.decisionHash
use that same compiler serialization. Correct the new test's handoff/history
hashes and the new ProofSession accepted-result and revised-preflight guards
to use the existing _compiler_hash. Keep compact Python identities for raw
saved-file pins, inference decisions and session indexes: those are produced
by Python rather than the compiler core. Shared core/native APIs are unchanged.

New negative checks preserve refusal: compact decision-history input must
fail through the pure decision port before reserving a ledger, and a newly
written copied result with a compact decisionHash must fail revised preflight
even when its new raw file/pin is internally consistent. Prior records are
never rewritten; no assertion, hash guard or format is relaxed.

Focused Ruff, format and strict mypy pass for both changed production siblings
and the new public-path test. Initial formatting failure remains retained.
Runtime/focused receipts, log identities and final source pins are indexed in
runtime-decision-hash-fix.json; full immutable logs stay in out/issue192.

The two Python production changes alter the complete consumed proof source
graph. Rebuild all temporary packages/bindings/evidence and run the same
bounded34-item serial public-first runtime set. No public-path/full pass,
review, accepted #202 dependency, Ready claim or closure is asserted. No
global fast/full/Claude or actual native/provider/FFmpeg/original-media work.
