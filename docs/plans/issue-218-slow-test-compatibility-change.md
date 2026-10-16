# CN-218-A2 — two slow-test helper adaptations (approval requested)

Candidate `04d5abc272364fc37d448ff029eca346953c5abc` passed fresh fast
validation and separate Claude fix-delta review (GO). Final local full
validation completed exit 1 after 9,660.16 Python-test seconds: 1,081 passed,
15 failed, 55 setup errors, 1,151 collected. Generated-currentness, TypeScript
lint/types/tests and Python lint/types passed. This is failed acceptance, not
a performance timeout or passing evidence. No further full run is started.

## Why new approval is required

#218 says: "Any other frozen test/golden change stops for revised approval."
Repository AGENTS.md also says: "Do not modify `/contracts`, `/fixtures`, golden
files, or previously accepted acceptance tests without an explicit
contract-change or fixture-change note approved by the producer."
CN-166-P1 and CN-218-A1 do not authorize these two Python test-helper edits.
The roadmap coordination skill preserves required frozen-boundary approval;
it does not supply a waiver. Actual frozen files remain unchanged.

## Exact proposed exception

Approve only the exact patch retained at
`docs/verification/issue-218/CN-218-A2-proposed.patch`, affecting:

1. `tests/issue190_case.py`: in `make_proof_case`, immediately after reading
   the synthetic dependencies, for `scenario == "default"` only, set
   `graphicContentClass` to `legacy_unclassified` on resolutions whose
   `sourceSnapshot.system` is `graphic_asset`. The helper's default scenario
   explicitly reads the retained #173 legacy graphic fixtures at the two
   supported rates. This is trusted classification of those known synthetic
   records, not runtime inference from arbitrary media. No original fixture
   changes. Existing scenario variants and all assertions remain unchanged.
   The helper already recompiles and builds its own output identities, so the
   required classification remains in the complete dependency hash.
2. `tests/test_issue144_omission_bridge.py`: in `_canonical_hash`'s inline Node
   loader only, resolve `.js` to `.ts` for the exact five-module compiler graph:
   compiler-core, script-validator, ev24-lower-third, template-library and
   graphic-provenance-compiler. Both the parent and target must be listed.
   Remove the hook after import as before. Keep the actual canonical serializer,
   all assertions, timeouts, test collection and original input bytes unchanged.
   This mirrors the already-integrated #144 source CLI's bounded graph.

## Reproduction and retained evidence

`docs/verification/issue-218/CN-218-A2-reproduction.json` records direct
current/proposed checks on the actual compiler path and exact helper source.
The current #190 call exits 1 with `GRAPHIC_PROVENANCE_INCOMPLETE` because the
known legacy graphic lacks classification; adding only that declaration in a
scratch dependency copy produces ready compilation and media requirements.
The current #144 helper exits 1 with `ERR_MODULE_NOT_FOUND` for
`ev24-lower-third.js`; the exact proposed scratch helper returns the actual
canonical hash successfully. Frozen files are not edited for these checks.
The two failures have explicit deterministic diagnostics; broader speculative
diagnosis is unnecessary. The shared #190 helper is used by the failing
#190/#192 setup paths. Passing direct checks do not substitute for their full
regressions; no claim is made that every failure is resolved yet.

The raw scrubbed full log and atomic failed result are retained as
`full-04d5abc-failed.log.gz` and `full-04d5abc-failed-result.json` beside the
reproduction. The previous passing fast and Claude delta report are retained
separately. No test timeout, assertion, fixture/golden, contract, compiler
classification requirement or hash meaning is relaxed.

## Scope after approval

Apply only the retained two-file patch. Run the affected slow regressions
serially, fresh fast checks, a separate Claude review of this delta and any
fixes, then the required final local full gate under VERIFICATION_POLICY.md.
Any additional frozen change still stops for a new approved note. Keep the
queue and long-check checkpoint rules. No #8, native application, provider,
production data/storage, merge or deployment operation is authorized.

Approval response: `Approve CN-218-A2 at <note commit>`.
