# #209 source and ownership handoff

Coordinator desk preparation, 2026-10-15. This pins the intended implementation boundary; it does not mark #209 Ready, dispatch an owner, adopt code into main, or authorize media preparation, installation or native effects. The remaining input gap is stated below.

## Accepted source

#214 is independently Closed/Done under Automated acceptance, its exact claim is released, and its implementation chat has finished. PR216 delivered head is `e2f2d7fd508b7e21a0056779eb5b8640e78859f8`, based on accepted main `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`; the base is an actual ancestor. PR216 is unmerged at the retained receipt. Its pending remote CI is not a passing result or merge authority.

| Consumed artifact | SHA256 |
| --- | --- |
| `docs/verification/issue-214/INTERFACE.md` | `de87b21cd8ab7fa9c74bff1198b775dbb96aaee4967aa5b5c315b9d507c2800f` |
| `python/vera_timeline_agent/qualification_output_records_v2.py` | `ec54847a872b7fcdb6c4e434dd3e9dc2bc1d100d10a9d90d24367b96c8269e2a` |
| `python/vera_timeline_agent/qualification_output_v2.py` | `d1d137c91eb99d76dd8eecfa3297ef677d41f59a668644ee5d7a2bea364a9684` |

Consume #214's four public operations, pair comparison, closed records and statically supplied `OutputTrust` as documented at that exact head. Do not import test authenticators or private transition helpers as production authority. Preserve immutable CN-213-A1 r1 SHA256 `f7b7b1bfb5373d7a08bd5400aba7880b93b0864d8e9fcea3e78d916508c0983d` and the narrower output-consistency claim.

An eventual authorized #209 owner must claim first, then establish that this exact prerequisite source is present in its dedicated checkout before edits. If starting from the accepted base, a checked fast-forward of its own branch to the exact #214 head can supply the prerequisite without merging main. If the starting state has diverged, stop source adoption and retain the actual comparison; do not silently cherry-pick a subset or reuse qualification for a changed composition. This is an isolated source-adoption proposal, contingent on the remaining Ready gates and the Producer's retained CI-stage start instruction.

The independently checked local #214 evidence contains 1,247 Python, 464 contract TS, one tooling-smoke TS and 61 Node passes, zero skips, actual Claude implementation reviews02/03 GO, immutable exit0 and log SHA256 `d8b236e905c75be8af95d63b639227998f410f82bff07355a81290177122eea7`. All 7,007 before/after inventory entries match; subsequent changes are confined to retained evidence paths under the explicit unread-input audit. This is reused evidence, not a new root test run. It proves the pure package, not #209's native route.

## Minimal implementation ownership

All Python paths below are under `python/vera_timeline_agent/`.

| File | Responsibility |
| --- | --- |
| New `qualification_output_controller_v2.py` | Host-only verified-input adapter, static trust wiring and clock, baseline/revised preflight selection with revised port default-deny, immutable prediction publication, complete UID-chain persistence, exclusive reservation, fsync and terminal CAS. Own the actual currentness checks before effects; historical seal verification must not renew authority. |
| New `qualification_output_decode_v2.py` | Host-only pinned decoder of the same delivered MOV, exact profile/extent/channel/sample hashes and native-job/output binding. No independent WAV render, offset/gain fit or source selection. |
| New `qualification_output_native_v2.py` | Installed stdlib-only finite sibling entry point, audited target/authority/source checks, construction, observable geometry, exact settings/job/output lineage, save/reopen and read-only recovery. Reuse accepted low-level adapter behavior only where compatible; preserve ordinary #177 and old strict-reader refusals. Never import the host controller, predictor, decoder, compiler or providers into Resolve. |
| Existing `workflow_v2_launcher.py` | One statically named sibling request dispatch; preserve existing request grammars and their refusal behavior. No JSON-selected module or callback. |
| Existing `workflow_v2_cli.py` | Package the exact additional installed sibling and its stdlib import closure in the reviewed release. Keep host prediction/decoder modules out of the installed closure. Retain all legacy entry checks. |
| New `tests/test_issue209_controller.py`, `test_issue209_decode.py`, `test_issue209_native.py` | Owned sibling positive/refusal/recovery tests, actual compiler/package shape vectors and host/installed confinement. Existing accepted tests remain unchanged. |
| `docs/plans/issue-209-*`, `docs/verification/issue-209/` | Bounded plan, operator artifacts, exact evidence and handoff. |

No new dependency. No changes to #214 production modules, old strict readers, compiler, shared schemas/contracts, fixtures, goldens or accepted tests. A discovered need outside this list is a scope/ownership gap to reconcile before editing, not permission to widen the slice. #215 owns its new Python/TS consumer and revised verifier; #209's revised port remains a static refusal until that separate accepted implementation exists.

The new Python files enter the existing source graph. Fresh source-bound preparation, installed release and authority are mandatory; old #208 identities and consumed read-only authorizations are historical evidence only.

## Concrete incoming preparation gap

The read-only audit of the actual historical R16 manifest finds four 48-kHz source-audio event ranges with both original sample endpoints divisible by 2,002. The two actual narration WAVs read under Python3.12.14 as mono/48kHz/24-bit PCM, have their pinned whole-file hashes, and contain 400,400 and 1,283,282 samples: exactly 200 and 641 frames.

That does not establish a native-ready source-audio package. The inspected historical dependency file has six private preparation bindings and no #174 audio receipt; its media locators do not name preparation receipts. No actual sidecar `resampledFirstSample` q, decoded extent or signed/interleaved decode evidence was recovered from that input set. q must come from an authenticated actual receipt, never an assumed zero.

The accepted public `media_preparation.prepare_media` requires qualified tool/profile/policy identity, explicit read roots and a separate write root. It emits a new binding and immutable `receipt.json`, checksum and signed24/48k audio sidecar; `_prepare_audio` records the actual q, original and resampled endpoints, PCM hash, probe, decoded sample count and timing residuals. Merely renaming that public receipt as one of the old private-profile bindings would fail the independent binding check and is not a supported route.

The old `PreparedProofBuildV2` R16 path also requires execution document/dependency bytes to equal the frozen original inputs and accepts only its finite private profiles. Therefore a new public #174 binding cannot be silently inserted into that old R16 dependency file or passed through that old constructor. Preserve both original files byte-for-byte. Before Ready, establish the owning accepted route for the new lane's execution-input/preparation binding, or retain an exact prerequisite/Producer decision artifact. The approved new lane already distinguishes original and execution identity; that fact alone is not proof that an actual compatible prepared package exists.

Track naming has an inspected source mechanism: `AuditedResolveAdapterV2.configure_tracks` delegates to the accepted adapter's checked `SetTrackName`; its verification reads `GetTrackName` and compares the manifest name. This closes the desk question about which code owns the operation. Actual runtime readback remains an External #209 smoke criterion, not a claimed pass from this source inspection.

## Validation and actual acceptance

After Ready and authorized claim: focused sibling checks and fast gate, actual independent adversarial Claude review, fixes/affected checks/delta review, then the separately authorized disposable Studio smoke. Resolve actual failures within scope before final complete local validation on delivered source; retain `--durations=25`, exact locked tools, source/config/lock/input/environment/inventory/skips and immutable exits. Do not replace actual app evidence with tests or CI, and do not rerun unchanged full coverage without an invalidation.

The existing operator outline in `docs/verification/issue-213/parallel-preparation/issue209-operator-handoff-outline.md` supplies the ordered release/target/authority/precommit/reservation/render/decode/terminal/recovery checklist. Implementation must replace its blanks with exact reviewed artifacts before requesting the operator grant. No agent-issued CONFIRM, reused authority, installation, native connection, build, save, queue, start or render is authorized by this handoff. #178's physical matrix and #145's listening/creative acceptance remain open.

## Current Ready verdict

All canonical #209 dependencies are Closed/Done and the issue is unclaimed. Exact source and minimal ownership are now pinned here. The preparation-binding route above remains unresolved; #209 stays Inbox. No task was dispatched and no native or media-preparation command was run.
