# #382 — Backend local-agent and QA host verification

**Scope:** Phase 4/5, synthetic-only transport integration (2026-11-08). This
record does **not** certify a real Resolve build, package acceptance, or a
Producer-approved Studio effect. No Research/Producer media, paid providers,
uploads, native writes, or browser UI were used.

## Private boundaries

The #159 development-QA host remains a single `127.0.0.1` listener with exact
Host, request-size, bearer-identity, path and startup checks. Routes added:

| Route | Identity | Result |
| --- | --- | --- |
| `POST /v1/projects/:id/agent-pairing-offers` | current Producer | single-use TTL offer |
| `POST /v1/agent-pairing/consume` | one-use offer secret | independently hashed agent credential |
| `GET /v1/projects/:id/agent-readiness` | current project member | advisory readiness |
| `DELETE /v1/projects/:id/agents/:agentId` | current Producer | revoke credential |
| `POST /v1/projects/:id/builds` | Editor/Producer Preview, Producer Release | 202 durable frozen submission, **not** native completion |
| `GET /v1/projects/:id/builds/:jobId` | viewer/current member | redacted authoritative event history |
| `POST /v1/projects/:id/builds/:jobId/cancel` | current submitter-class authority | cancel or waiting reconciliation |
| `GET /v1/agent/projects/:id/queue` | current scoped agent credential | unassigned job IDs only, no effect permission |
| `POST /v1/agent/projects/:id/jobs/:jobId/claim` | scoped agent plus current submitter role | versioned 60-second transport lease |
| `GET /v1/agent/projects/:id/jobs/:jobId/leases/:epoch/frozen` | active scoped epoch, current head/settings | exact server-stored frozen JSON and selected source pins |
| `POST /v1/agent/projects/:id/jobs/:jobId/leases/:epoch/progress` | active scoped epoch | append-only, *untrusted* stage/progress event |

The unmounted independent evidence inspector has **no HTTP endpoint**: agent
reports can never self-promote to `verified_package` or `verified_native`.
The currently unavailable accepted-source authority means nonempty selected
source claims remain blocked until a trusted adapter exists. The local Python
bridge uses only explicitly injected versioned #157 StagePorts, is
**Free-only**, and runs at most one local stage per manual call. A Studio
manifest requires separate native permission and is reported `needs_action`;
there is no automatic native retry. Local ambiguous results stay in SQLite
`waiting` and server `waiting_reconcile`, not `ABSENT` or `VERIFIED`. A
reconnect must prove the original active server lease/epoch and digest, never
silently claim a second effect after uncertainty.

## Additive database and recovery inventory

Start from #379 authorization and #380 documents, then apply
`stt_project_builds_001` and
`stt_project_builds_002_preflight_refusals` on the same QA connection.
Database allowlist now contains **19 tables**: original 11 plus pairing
offers, agents, immutable submissions, selected pins, dispatches, append-only
events, immutable evidence and preflight refusals. SHA-256 receipt allowlist
contains exactly four records; backup/recovery checks account for the
owned `stt_build_events_id_seq` and immutable build trigger function.
No old migration SQL is modified; no DROP/overwrite is authorized.

## Synthetic verification

Commands from the isolated #382 worktree (UTC 2026-11-08):

* `uv run --frozen pytest -q tests/test_issue382_build_agent.py tests/test_build_composition.py tests/test_build_jobs.py` — **28 passed**, fake stage effects only; no native calls.
* `uv run --frozen ruff check python/vera_timeline_agent/build_agent_service.py tests/test_issue382_build_agent.py` — **passed**.
* `uv run --frozen ruff format --check python/vera_timeline_agent/build_agent_service.py tests/test_issue382_build_agent.py` — **passed**.
* `uv run --frozen mypy python/vera_timeline_agent/build_agent_service.py tests/test_issue382_build_agent.py` — **passed, 2 files**.
* `npm run lint -w @vera/project-service-host` and `npm run typecheck -w @vera/project-service-host` — **passed**.
* `npm run test -w @vera/project-service-host` — **67 passed, 1 skipped** (the separately configured PostgreSQL integration test requires a test URL). The 4 backup-guard fixtures pass, including the exact owned-sequence allowlist; bad sequence names still fail closed.
* `npm run test -w @vera/project-builds` — **36 passed**, including authenticated project-scoped queue polling, foreign-project refusal, and revoked agent credential refusal.

The new route tests exercise scoped user/machine identity separation, no
external Host/forwarded authorization, lease epoch, malformed body refusal,
no fabricated native progress, and safe error redaction. Local Python tests
prove fake StagePort receipts survive service recreation, uncertain stages
are retained without re-execution, altered frozen data rejects, and Studio
does not execute native effects. These are **synthetic** assertions; no
real-provider or application-native result is inferred.

## External evidence and limitations

**Real Resolve save/close/reopen readback: UNVERIFIED.** The Linux phase-4
worker cannot access the Mac's Resolve GUI or its native owner, and #382 does
not authorize a new one-use Studio mutation. Independent native readback
remains a separate acceptance authority.

## Real PostgreSQL/loopback recovery verification (synthetic-only)

`npm run smoke:qa -w @vera/project-service-host` — **PASS, 15/15 scenarios**,
`2026-11-08T16:49:58.695Z`; actual PostgreSQL `16.15` and separate CLI host
processes on `127.0.0.1`. Source commit pinned at
`496b1a207caa16f040a7e3f1d34dc4e72c0c7ec9`. The operator provisioned
two **new empty databases** under the same dedicated nonprivileged QA owner:
source `vera_stt_qa_p382_1794156574` and fresh destination
`vera_stt_qa_restore_p382_1794156574`. 0600 identity mapping and bearer
tokens were kept outside the repository and omitted from this report.

The checks completed in sequence: loopback auth refusal, exact creation
replay, document CAS and role checks, producer settings, editor revocation,
new build freeze/replay/conflict/Viewer refusal, one-use pairing, agent
credential and epoch checks, untrusted running-to-`waiting_reconcile`
progress, populated source process restart, four checksum migrations,
private custom-format database backup, intentionally corrupted archive
rejection, fresh target restore, refusal to restore into a populated
destination, and exact authenticated readback after restored host restart.
The original source and restored DB were compared for full state equality;
both retained a single frozen build and its four append-only events.

**Recovery inventory:** 19 allowlisted tables, 4 checksum-verified migrations.
Build rows: 1 pairing offer, 1 agent, 1 frozen submission, 1 dispatch,
4 events, 0 selected source pins, 0 independently classified evidence,
0 preflight refusals. No app/native effect was executed; all four events
remained untrusted observations. Archive length **135,377 bytes**.
SHA-256 manifest:
`e9ef0259f31f9486acdf5a567db2c18514be5aea3a3a5eeebd9ce23d0128f09f`;
SHA-256 archive:
`f2f25988f7dead1b99ca62653db7fa7fa9a3d2049ade01fd090a29e3c5af38fd`.
The actual archive and credentials are private and **not committed**.

The first real QA run had rejected backup because the newly allowed event
sequence guard was accidentally inverted. No archive/restore was claimed
on that run. Phase-4 fix `496b1a20` corrected the exact-name predicate,
and a fake `pg_class` fixture now includes the owned sequence. The second
run used fresh databases and passed all checks; the guard was not bypassed.

## Whole-repository fast-gate limitation

`VITEST_MAX_WORKERS=1 npm run validate:fast` was run on the Linux Zodex
worktree after the source commits: **exit 1**, total **345.644 s**. The
single Python xdist phase reported **2,813 passed, 43 skipped and 19 failed**;
the failing tests belong to narration CLI, word timing/consent, issue #182
campaign portability, and issue #208 target/authority capabilities. **No
test in `tests/test_issue382_build_agent.py` failed.** The target-scoped
Python run above passed **28/28**, host run passed **67/67** runnable unit
tests, build-service run passed **36/36**, and the real PostgreSQL recovery
smoke passed **15/15**. We did not alter unrelated tests, broaden the allowed
native capabilities, or mark this whole-repo gate green. Phase 5 must retain
this explicit gate failure in final review and decide appropriate escalation.

**No production deployment:** This listener is local QA only, no TLS or remote
host, no automated Studio driver, and no accepted source integration. The
subsequent phase 5 owns whole-diff/mutation review and the above
whole-repository gate disposition.
