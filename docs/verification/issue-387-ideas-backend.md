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

## Phase 5 — independent fast verification and whole-change review

The clean branch's fresh single-worker focused runs passed **102 tests, one optional PostgreSQL test skipped**: project-documents 39 passed/1 skipped (five files), service-host 17 passed (two files), build-submissions 15 passed, compiler-v2 31 passed. The optional independent two-client concurrency case then passed **1/1** on disposable PostgreSQL 16 (`vera387_phase5`), checking promotion/promotion and promotion/document-write races and paired committed revisions. These tests did not use any Producer media or native Resolve effects.

Seven reversible guard mutations were each detected by a **failing targeted test**: duplicate Idea ID acceptance; trimming exact source text on promotion; downgrading an Ideas write to view-only authorization; ignoring the expected Ideas revision; ignoring a replay request fingerprint; bypassing Ideas head digest checks; and contaminating a frozen build document with Ideas JSON. Each original file was restored byte-for-byte immediately after its mutant test; `git status` was clean afterward. The mutation runner and captured results are in the conductor's `.pipeline/387/` ticket folder, not in the product diff.

The required `VITEST_MAX_WORKERS=1 npm run validate:fast` was run **twice**. It did **not** produce a full green result, so CI remains required:

- First run: generated contracts, TypeScript lint and TypeScript typecheck passed. One of 67 host tests (`test/backup-guards.test.ts`) hit its pre-existing 5-second Vitest timeout; the other 66 passed. The exact failed case was rerun in isolation without edits and **passed in 2.47 seconds**.
- Second run: generated contracts, TypeScript lint and typecheck passed; the QA host's **8/8 test files**, project-builds, project-authorization, project-documents (**102 passed/1 optional skip**), and all other fast workspaces passed. Contracts had **1,245 passing tests** and exactly **two 5-second timeouts** in untouched `test/qualification-output-proposals-v2.test.ts` (#215), while the other 51 contract test files passed. Those exact two tests subsequently **passed in isolation** in 2.93 and 2.41 seconds. The relevant test file has identical SHA-256 to the branch's `b4ee4c67` base, and #387 changes neither the test nor its implementation. These are load-sensitive timeout observations, **not** a claim of an independently reproduced failure on `origin/main` or an all-green full fast gate.

Because both fast-gate attempts stopped at TypeScript tests, the Python fast stages were run separately. `npm run lint:python` passed Ruff lint/format, and `npm run typecheck:python` passed MyPy (**369 source files**). `npm run test:python:fast` completed with **2,987 passed, 43 skipped, 5 failed** in unrelated, unchanged tests: two narration CLI media-tool refusals (`tests/test_narration_cli.py`), a campaign generate/provider refusal (`tests/test_issue182_campaign.py`), a missing `ffmpeg` executable for cloud-scribe transcription and a child-process reaping expectation (`tests/test_word_timing_package.py`). All five also failed in a single-process isolated rerun; there is no installed `ffmpeg`/`ffprobe` in this Zodex container. These results are documented failures, **not** a claim the Python suite passed or a demonstrated execution of those tests on clean `origin/main`. None of these three test files or their functionality is in the #387 diff. Full CI on the intended toolchain is still mandatory.

Self-review covered the whole branch diff from `b4ee4c67` through the implementation's four phase commits: closed sidecar model and migration, authorized serializable transactional service and same-project key boundaries, dual-head CAS/source-preservation, HTTP authentication and closed envelopes, migration QA allowlist, frozen build boundaries, and negative/error/concurrency tests. No further implementation defect was found. The Zodex pipeline environment provides no Claude review CLI, so the required independent review remains a PR/CI handoff rather than a claimed completed Claude review. No `npm run validate` or native Resolve run was performed.

## Deliberate limitations and merge conditions

This backend-only sidecar does not implement a future multi-user Yjs shared head, user-facing Ideas UI (#77), native Resolve operations, or automatic narration. Promotion places an exact-copy **excluded** Draft note; a separate explicit Draft authoring action is required for spoken build output. The conductor must submit the committed branch through the project's ordinary PR, independent review and CI queue. The full CI check, rather than the load-sensitive local gate, is the acceptance evidence for merge.
