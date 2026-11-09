# Issue #388 — Extras backend verification

## Acceptance and implementation

- Phase 3.7B backend only. The existing Stash bundles/outline are the *single* canonical persistence backing store for Extras; schema-v2 `extras` remains `[]`. There is no UI, migration or second synchronized store.
- `extras-operations.ts` rejects unsupported commands and unknown or hostile JSON shapes, delegates park/restore/place to canonical row edits, and persists only validated round-trippable documents. Move and restore preserve row identity, supporting items, footage and frozen origin context; ambiguous destinations and external crossings refuse safely.
- `extras-duplicate.ts` clones saved ordinary rows or closed branches atomically into an exact Draft gap, allocates fresh owned IDs, remaps typed internal references, preserves external Research/media identifiers and saved originals, and refuses uncertain supporting anchors, group boundaries, audio and media ownership.
- `ProjectDocumentService.applyExtrasOperation` and authenticated `POST /v1/projects/:id/document/extras-operations` use existing `edit_document` grants, optional write sessions, strict body/command parsing, request fingerprints, immutable revision receipts, head-row locks, CAS, idempotency, digest checks and transactional comment reconciliation.
- Compiler and media requirements use `activeDraft` only. Deliberately, an immutable build snapshot stores the **entire** exact validated document, including saved Stash; compiled events/requirements omit parked material. Tests cover typed footage and citations, restored Draft output and snapshot integrity.

## Focused verification

- Phase 1: Stash core regressions and Extras adapter; typed move/restore and refusal.
- Phase 2: Extras duplicate and typed-ID/refusal regressions.
- Phase 3: PGlite service and HTTP authentication, tenancy, replay, stale writes, comment atomicity.
- Phase 4: compiler requirements/output, frozen-build submission/agent reads, host route, scratch PostgreSQL races and revoked-session replay.
- Phase 5 combined focused run: `npm exec --workspace packages/contracts -- vitest run test/compiler-v2.test.ts test/stash-edits-v2.test.ts test/stash-outline-v2.test.ts --maxWorkers=1`; project-documents extras-duplicate/extras-operations/service/api; project-builds submission; project-service-host serve/http. All commands exited 0. Details in `.pipeline/388/phase5-focused.log` (conductor ticket folder).

## Restrictions and known limitations

No live Resolve or UI validation, no Producer media, no external/paid integrations, no schema-v2 nonempty `extras`, no product-facing partial selection. The user-facing Extras UI stays in #78. The conductor, not this worktree, owns push/PR/CI/merge. Real PostgreSQL test database is disposable only.

## Final phase gate, adversarial mutation results and review

### Fast gate and unrelated timeout

VITEST_MAX_WORKERS=1 npm run validate:fast on this branch: generated contracts PASS (4.527s), repo TypeScript lint PASS (90.154s), TypeScript typecheck PASS (43.332s), broad workspace TypeScript tests FAIL (332.782s). The **sole reported failure** was a 5000ms timeout in packages/contracts/test/qualification-output-proposals-v2.test.ts, test "keeps video native sources outside the audio PCM source mappings". The file's Git blob is exactly 374126dab54f357c260599d83e0567b4560b7a30 at both current HEAD and fetched origin/main. No #388 change touches this test. The *entire file* passed when rerun independently (30/30, 26.16s). The observed failure was isolated to concurrent workspace load; this is not a claim that the entire gate passed or that a baseline origin/main full suite ran. The full fast gate stopped before Python; previous phase-3 logs also record environment-dependent Python/FFmpeg failures. Logs: .pipeline/388/phase5-validate-fast.log and phase5-postgate-focused-pg.log.

Post-gate document service and duplicate rerun 21/21 PASS, including strengthened Viewer-without-session, Editor-with-invalid-session and exact attachment/reference refusal assertions. Scratch PostgreSQL 16 integration on disposable vera388_phase5 4/4 PASS, including independent competing head CAS and revoked session replay. Final lint and TypeScript typecheck passed for all four touched packages. Final combined focused rerun after all mutation restorations: contracts 86/86 PASS, project-documents 35/35 PASS, project-builds 15/15 PASS, project-service-host 9/9 PASS (total 145/145). Logs: .pipeline/388/phase5-final-focused.log.

### Reversible adversarial guard mutations

Each probe temporarily altered one source guard in the named worktree, ran its targeted negative test, and restored original bytes in a finally clause. Runtime source diff against HEAD was verified empty after probes. **8/8 negative mutants were caught** by focused failing assertions:

| Guard | Reversible fault introduced | Observation |
| --- | --- | --- |
| Role auth | Downgrade Extras write permission to view | Caught after no-session Viewer regression |
| Write session | Ignore supplied lease ID | Caught invalid-session Editor edit |
| Head CAS | Bypass expected-revision compare and pass current revision | Caught stale accepted write |
| Idempotency | Ignore mismatched replay fingerprint | Caught reused-key receipt |
| Owned IDs | Disable allocator collision check | Caught duplicate ID diagnostic |
| Attachments | Disable exact one-slot mirror preflight | Caught refusal diagnostic |
| References | Disable selected-row opaque-reference guard | Caught review-required diagnostic |
| Draft compilation | Include saved Stash rows in timed-row traversal | Caught parked-row compiler regression |

The first auth probe initially survived because the Viewer case also supplied an Editor-owned session, independently denying access. Added a Viewer request *without* a lease, then repeated all eight mutations with all eight detected. Details: .pipeline/388/mutate-guards.py, phase5-mutation-summary.log and mutation-*.log.

### Self-review and review attempt

Reviewed the combined 15-file diff against scope: permissions/tenant isolation, strict commands, immutable document transaction and comment reconciliation, CAS/replay namespace, clone owned IDs and external references, PostgreSQL races, compiler/build exclusion and frozen full-document bytes. One test-isolation gap was found and fixed. No outstanding implementation blocker identified in self-review.

Attempted npm run review -- notes.md **exactly once**; it returned "You've hit your weekly limit - resets 3pm (UTC)". No independent Claude reviewer result obtained. Restored the original tracked notes.md from HEAD. CI, PR and merge remain conductor-owned. No Resolve native actions, private Producer media, deployment or paid integration occurred.
