# Issue #387 — Ideas backend verification

## Scope and isolation boundary

- Ideas are saved as a versioned `stt-idea-outline/v1` sidecar with independently immutable revisions; no populated Ideas are written to `script-document/v2.ideaOutline` or passed to the compiler.
- `GET/PUT /v1/projects/{projectId}/ideas` and `POST /v1/projects/{projectId}/ideas/promotions` reuse the trusted suite identity adapter and `ProjectDocumentService` authorization, session, optimistic revision and idempotency checks. The API admits only closed request envelopes and rejects unsupported methods, query strings, and malformed bodies.
- Promotion atomically advances the Ideas and document heads. It copies the exact source Idea text into an **excluded** `note_draft` row and preserves the Idea and backlink. Neither an Ideas-only write nor `state: "incorporated"` makes source text narratable. A later explicit, valid active Draft edit is required for narration.
- The QA host installs checksum-pinned Ideas migration `stt_project_ideas_004` (version 4) after project history and before builds. The three Ideas tables are on the closed QA allowlist. Unexpected tables or missing/tampered receipts still fail startup.
- `ProjectBuildSubmissionService` continues to freeze only the current v2 document and settings, without reading Ideas storage. Previous frozen submissions remain immutable after subsequent Ideas edits and promotion; the local agent and Resolve interfaces have not changed.

## Evidence through Phase 4

| Check | Outcome |
| --- | --- |
| `npm run test --workspace @vera/project-documents -- test/api.test.ts` | 9 passed, including trusted GET/PUT/promotion, replay, stale heads, denied Viewer/cross-project/revoked member, unknown fields and malformed/anonymous requests |
| `npm run test --workspace @vera/project-service-host -- test/migrate.test.ts test/serve.test.ts` | 17 passed, including exact migration sequence/checksums, QA table preflight and existing host serving |
| `npm run test --workspace @vera/contracts -- test/compiler-v2.test.ts` | 31 passed, including refusal of a populated v2 Ideas field and byte-for-byte unchanged compiler artifacts/media requirements after adding an excluded promoted Draft note |
| `npm run test --workspace @vera/project-builds -- test/submission.test.ts -t 'never freezes unpromoted Ideas'` | 1 passed; persisted positive control for Ideas text, identical frozen bytes and agent document before promotion, then excluded Draft-only persistence and unchanged prior jobs |
| `npm run test --workspace @vera/project-builds -- test/submission.test.ts` | 15 passed, including all existing build and agent-snapshot regressions |
| Typecheck and lint, `@vera/project-documents`, `@vera/project-service-host`, `@vera/project-builds`, `@vera/contracts` | All eight workspace commands passed (`tsc --project tsconfig.json`; `eslint src test --max-warnings=0`) |

An initial full build-submission run passed the 14 existing tests but found an assertion in the new regression that searched for literal newline characters inside JSON-escaped text. The assertion was fixed to compare `JSON.stringify(source)` and to check leakage by stable sentinel prefix. The isolated regression and subsequent complete 15-test rerun both passed.

## Related earlier-phase evidence

- Phase 1: Ideas-model and migration suites (12 passed); additive migration checksum and immutable-history tests.
- Phase 2: authorized Ideas service and transactional CAS/replay/revocation/cross-project checks (29 focused tests passed, recorded in the pipeline progress log).
- Phase 3: atomic promotion suite (30 focused tests passed with one optional PostgreSQL test skipped in that run); a separate disposable PostgreSQL two-client race passed. The phase's mutated stale-Ideas-CAS guard caused its targeted test to fail and was restored.

## Deliberate limitations / remaining Phase 5

This backend-only sidecar does not implement a future multi-user Yjs shared head, user-facing Ideas UI (#77), native Resolve operations, or automatic narration. Phase 5 owns the complete `VITEST_MAX_WORKERS=1 npm run validate:fast` gate, wider reversible security/data-integrity mutations, independent whole-diff review and final PR handoff; those checks are **not** claimed here.
