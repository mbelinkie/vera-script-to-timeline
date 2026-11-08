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
* `npm run test -w @vera/project-service-host` — **67 passed, 1 skipped** (real PostgreSQL integration requires explicit isolated test URL). Four earlier failing fake backup inventory tests were corrected to sort fixture migration names exactly as the production inventory; all 4 then passed without weakening refusal guards.

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

**Real PostgreSQL HTTP/backup/restore:** Record the phase-4 local result and
fresh SHA/DB inventory after an actual disposable QA run; fixture-only
guards must not be represented as full database recovery. The opt-in #159
real smoke must be invoked only with two empty, distinct owner-scoped
`vera_stt_qa_*` databases, private outside-repo 0600 identity file, trusted
source SHA, and private backup root, with no other client connections.

**No production deployment:** This listener is local QA only, no TLS or remote
host, no automated Studio driver, and no accepted source integration. The
subsequent phase 5 owns final fast-gate, mutation and whole-diff review.
