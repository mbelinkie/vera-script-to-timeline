# #159 — private development-QA PostgreSQL service recovery

**Status:** real local development-QA HTTP/PostgreSQL/backup/restore smoke
**passed 2026-11-07 UTC** (evidence below). Not hosted-release, production
backup, or Producer acceptance; no Research data, media or paid hosting.

## Invariants and operator preparation

- Use **synthetic data only**. Stop the local QA HTTP host and all clients for
  the entire backup/restore window; the scripts refuse concurrently connected
  clients at their checks but cannot fence clients between separate CLI calls.
- The source database must be `vera_stt_qa_<unique>`; the destination must be
  a **different** `vera_stt_qa_restore_<unique>` database, provisioned by an
  administrator before invocation and **empty**. The tool **never creates,
  drops, truncates, cleans or overwrites a database**. A dedicated *non-root,
  non-superuser, NO CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS* role must own
  each database. Give it a strong private password, not a real user account.
- PostgreSQL (`psql`, `pg_dump`, `pg_restore`) must be installed locally.
  Configure each URL with `127.0.0.1`, the explicit database name, a dedicated
  owner username and password; omit query strings and libpq options. Connections
  use local TCP only and no TLS. The scripts suppress child diagnostics so
  credentials and SQL/data values are never printed on failure.
- Use one newly named **absolute directory outside the repo**, beneath a
  private local volume. The backup script creates it atomically with mode 0700
  and exclusive 0600 `qa.dump`/`manifest.json` files. No symlinks, preexisting
  directory, or permissive archive files are accepted. **Do not** add archives,
  credential files or data dumps to Git; encrypt and securely dispose of copies
  if using anything beyond disposable synthetic QA data.
- Pin `VERA_STT_SOURCE_SHA` to `git rev-parse HEAD` in the checkout executing
  the scripts; both operations require the same checked-out SHA as the backup
  manifest. If the source changes, make a new QA backup from that exact source
  revision. No hosted-release portability guarantee is inferred.

## Operator commands (run locally; no public binding)

First create a synthetic-only owner role and QA source and restore databases
via your separate privileged PostgreSQL provisioning console. Do **not** run
these scripts as a PostgreSQL administrator. Provisioning is deliberately out
of these scripts so that they cannot allocate or destroy databases.

```sh
export VERA_STT_MODE=development-qa
export VERA_STT_SOURCE_SHA="$(git rev-parse HEAD)"
install -d -m 700 "${HOME}/private-qa-backups"
export VERA_STT_QA_ARCHIVE_DIR="${HOME}/private-qa-backups/159-$(date -u +%Y%m%dT%H%M%SZ)"

# Populate these URLs privately; credentials are never CLI arguments.
# Source:  postgres://<owner>:<password>@127.0.0.1:5432/vera_stt_qa_<unique>
# Restore: postgres://<owner>:<password>@127.0.0.1:5432/vera_stt_qa_restore_<unique>
read -r -s -p 'Source DB URL: ' VERA_STT_QA_DATABASE_URL; echo
export VERA_STT_QA_DATABASE_URL

bash scripts/stt-qa-backup.sh

read -r -s -p 'Fresh restore DB URL: ' VERA_STT_QA_RESTORE_DATABASE_URL; echo
export VERA_STT_QA_RESTORE_DATABASE_URL

bash scripts/stt-qa-restore.sh
```

On backup, the private `manifest.json` contains the source name, source SHA,
archive byte count and SHA-256, both migration names/version/source-SQL
checksums, and per-table row counts and SHA-256 over deterministic sorted
row JSON. It contains **no raw document payloads, tokens or passwords**.
`qa.dump` is a PostgreSQL custom-format **schema + data** archive and *does*
contain synthetic QA project/document/identity information. Both files are
private and outside the source repository.

Before restoring, the script validates private path ownership/modes, archive
size and SHA-256, migration digests against *this checkout*, and archive TOC
readability; it refuses nonloopback/malformed URLs, wrong database prefixes,
privileged/unexpected users, existing user relations/functions/extensions or
additional schemas, and other active sessions. It then restores with
`pg_restore --single-transaction --exit-on-error --no-owner --no-acl` to the
already-created empty database; no `--clean`, `--create` or DROP. An SQL error
rolls back the restore transaction. Finally, it recomputes **all migration
receipts and row inventories** and refuses mismatches. Never treat a restore
failure (or incomplete archive directory) as accepted data recovery; use a
newly provisioned empty destination for each retry, rather than reusing a
possibly partially populated target.

## Phase 4 verification requirements (exercised below)

Phase 3's fake-tool guard suite and scratch-Postgres roundtrip exercise the
utilities, not user-visible API acceptance. The application proof must include:

1. Host started with `VERA_STT_MODE=development-qa`, clean/source-pinned
   checkout and private SHA-256 token identity file, listening on
   `127.0.0.1:<port>` **only**. Unknown token or caller-supplied identity
   headers cannot bypass the authorization service.
2. Synthetic project and document created via HTTP; compare project ID,
   revision, content digest, idempotent replay/stale conflict and immutable
   revision history. Verify Editor/Viewer privileges and Producer-only settings
   and revoke Editor, including an already-open write session.
3. Terminate process, relaunch against the **same populated source** and verify
   exact state survived, then re-run auth-before-documents checksum migrations
   without modification. Record counts, digests and migration receipts.
4. With host stopped, take a new private backup, restore to a separately
   provisioned empty target, start a host against that target (alone), and
   repeat all state/auth/revocation/audit readbacks. Prove archive tamper and
   preexisting destination refusal; do not paste archive bytes or credentials
   into evidence.

Record UTC, git SHA, PostgreSQL/CLI versions, source/restore database **names**,
manifest SHA-256, migrated names/digests, table counts/hashes, test commands,
and actual HTTP status/result evidence **without tokens, payloads, credentials
or user information**. If real end-to-end evidence isn't available, label it
*unverified* and do not claim #159 accepted. Hosted release, production
retention, encrypted off-machine storage, scheduling, managed secret rotation,
TLS/ingress and recovery SLOs remain separate decisions; no new shared
contract, fixture, or Research/Resolve change is authorized here.

## Opt-in actual-application smoke workflow

`npm run smoke:qa -w @vera/project-service-host` starts **real, separate HTTP
host processes** and exercises the actual PostgreSQL-backed API and existing
private backup/restore scripts. It never uses the injectable HTTP unit-test
server or PGlite. The runner requires a clean source-SHA-pinned checkout, an
explicitly named mode, a localhost port, private identity credentials, and
**two newly provisioned empty** distinct QA databases owned by the same
nonprivileged role. It never creates, drops, truncates or overwrites databases.
The local test harness alone calls the internal membership service: **no
public administrator endpoint** is introduced.

In addition to the operator variables above, privately generate three
independent 32-byte random lowercase hex tokens. The private mode-0600
`VERA_STT_QA_IDENTITY_FILE` must contain their SHA-256 digests mapped to
`synthetic-producer`, `synthetic-editor` and `synthetic-viewer` with the
issuer `urn:vera:stt:development-qa`. Export the raw tokens **only** into
the local process environment as
`VERA_STT_QA_SMOKE_PRODUCER_TOKEN`,
`VERA_STT_QA_SMOKE_EDITOR_TOKEN`,
`VERA_STT_QA_SMOKE_VIEWER_TOKEN`, and run:

~~~sh
export VERA_STT_QA_SMOKE=synthetic-disposable
npm run smoke:qa -w @vera/project-service-host
~~~

The runner writes a sanitized mode-0600 `smoke-evidence.json` alongside the
private archive only on full success. It refuses a reused source/restore DB;
to re-execute, provision fresh empty databases and a new private archive
directory. Do not commit tokens, private identity file, connection strings,
raw logs, dumps, project payloads or that private evidence file.

## Retained phase-4 real HTTP/PostgreSQL acceptance evidence

**UTC:** 2026-11-07T03:34:16.905Z. **Mode:** `development-qa` only.
**Exact clean source revision:**
`2c7c191819ab2528d3d856c207f480b06d973a36`.
**Runtimes:** Node v24.19.0; PostgreSQL
16.15 (Ubuntu 16.15-0ubuntu0.24.04.1); loopback `127.0.0.1`.
**Dedicated synthetic DBs:** source
`vera_stt_qa_p4_1794022189_r1_r2`, fresh destination
`vera_stt_qa_restore_p4_1794022189_r1_r2`.

Command: `npm run smoke:qa -w @vera/project-service-host` — **exit 0**,
`STT development-QA real HTTP/PostgreSQL/recovery smoke passed (13 scenarios)`.
All thirteen independently checked scenarios passed:

1. `loopback-auth` — unknown bearer 401, forged user/role headers cannot
   grant access (403).
2. `create-replay` — HTTP create 201, exact request replay 200 with the
   duplicate flag and unchanged digest.
3. `document-cas-replay` — Producer then Editor document PUT advanced server
   revision 0 → 1 → 2, idempotent retry unchanged, stale CAS 409 with
   current revision 2.
4. `viewer-read-refusal` — Viewer GET 200 and document/settings PUT 403.
5. `editor-write-producer-refusal` — Editor could PUT the document with a real
   write session but settings PUT and project-title PATCH returned 403.
6. `producer-settings-title` — Producer settings revision 1 → 2 and project
   title version 1 → 2 via real HTTP.
7. `editor-revocation` — internal role revocation denied Editor GET, replay
   of a previously successful PUT and new PUT (all 403); previously opened
   session denied independently by auth service.
8. `source-restart` — independently restarted the HTTP host against the same
   populated PostgreSQL DB; exact typed document, settings, roles, audit,
   version and revoked-session readbacks retained.
9. `populated-migration` — startup reran checksum-verified auth migration
   before documents migration on existing populated v1 tables with no altered
   receipts or rows. This is *repeatability*, not a legacy upgrade claim.
10. `tampered-archive-refusal` — a byte changed in a disposable private
    archive copy caused restore refusal; target remained empty.
11. `fresh-restore` — source host stopped; pg_dump custom-format archive
    passed hash/inventory verification and restored transactionally to a
    separately provisioned empty QA database.
12. `existing-restore-refusal` — reusing populated restored target refused;
    no overwrite or truncation.
13. `restored-restart` — new host process against restored PostgreSQL
    reproduced Producer/Viewer readbacks, Editor and revoked-session refusals,
    immutable revision history, membership/audit/settings and migration
    receipts. Source SQL snapshot remained unchanged.

**Recovered state:** document head revision **2** with **3 immutable**
revision rows (0, 1, 2), settings head revision **2** with 2 settings
revisions, project title version **2**, **4** membership audit rows, **1**
revoked write session. Source and restored private inventory row counts:

| Table | Rows |
| --- | ---: |
| `vera_schema_migrations` | 2 |
| `vera_identity_actors` | 3 |
| `vera_project_members` | 3 |
| `vera_project_write_sessions` | 1 |
| `vera_project_membership_audit` | 4 |
| `stt_projects` | 1 |
| `stt_document_heads` | 1 |
| `stt_document_revisions` | 3 |
| `stt_project_settings` | 1 |
| `stt_settings_revisions` | 2 |
| `stt_project_title_mutations` | 1 |

**Migration checksum receipts (version 1):**
`vera_project_identity_membership_001` SHA-256
`dc6523dd55b28dc70034abefafb2d3d1e2ae93b82632af4bb2bb3cdf2739aef8`;
`stt_project_documents_001` SHA-256
`70aa02588f58e59473842dfc6bd15519bc60d347c211d1b242c94f0bc8a0c1dc`.

**Private archive** 67,292 bytes, SHA-256
`bd89e099205a98c755dc9c34d10d5ca2d3e8081784433cef21e165fa5f9bbd7d`.
**Manifest SHA-256**
`bbc7faa595e772c2e869bc20b0895d72e1394d2a424ab33511e55e6f5edb648a`.
**Stable source/restarted/restored SQL snapshot SHA-256**
`2418f496822be17e2cdd9e4f46116545bd4266a9f71d3749bb0784de79d307ed`.
No raw tokens, identities, SQL row contents, JSON project bodies, database
connection strings, private archives or manifest were committed.

**Scope limit:** this proves a real **local development-QA** application and
recovery, **not** an internet-hosted release, real user data migration,
managed identity/TLS/ingress, production retention, disaster-recovery SLO,
external expense authorization or Producer sign-off.

## Phase 5 final-code repeat and independent safety audit

**UTC:** 2026-11-07T04:44:01.506Z. **Mode:** local synthetic
`development-qa` only. **Exact hardened service source revision:**
`3d8eea70336f79433248de9e95c7552de8e710c9` (before this
verification-document-only commit). **Runtime:** Node v24.19.0,
PostgreSQL 16.15; loopback `127.0.0.1`. Fresh owner-scoped synthetic
source `vera_stt_qa_p5_1794025970`, fresh restoration target
`vera_stt_qa_restore_p5_1794025970`.

`npm run smoke:qa -w @vera/project-service-host` exited 0:
**13/13 real-process HTTP/PostgreSQL/restart/backup/restore scenarios passed**
(in exactly the named cases above), including Editor revocation, stale CAS,
idempotent replay, unchanged source restart, private backup, tamper refusal,
empty fresh transactional restore, repeated restore refusal and identical
post-restore HTTP/SQL readback. Head revision **2**, immutable document
revisions **3**, settings revision **2**, membership audit records **4**,
revoked write sessions **1**, checksum migration receipts **2**. Source and
restored SQL snapshot SHA-256
`f2e86e723dfd08021fcb61d307a5e9e94e77e7faa75b1816034953da5108928e`.
Private custom archive **66,622 bytes**, SHA-256
`621cbb28d11d7c3cae4d8b5302dd50a9d4eca9ef7dc5f577cf09fc0fd021391c`;
manifest SHA-256
`857a9cc14826a0229650e80f13a4ab3f7bf50b23123a29eb0f96b72a7a647579`.
Migration checksums remained the exact two values listed above.
All bearer tokens, identity JSON, private archive and raw SQL/document
contents remain outside the checkout and are not committed.

Phase-5 adversarial review additionally patched a credential-file boundary:
when the active worktree is separate, startup now refuses files in **either**
the worktree or the Git common/main repository, including symlink resolution.
The new regression passed in the host suite (**67/67** in the root fast run).
Eight separately inverted safety guards (deployment mode, identity-file
permissions, elevated database role, migration digest, viewer authorization,
document CAS, archive SHA-256, and populated restore target) each caused
its targeted negative test to fail; all modifications were restored.

The root `npm run validate:fast` passed generated-currentness, every TypeScript
workspace lint and typecheck and all host tests; it did **not** exit green:
five unchanged `packages/contracts/test/qualification-output-proposals-v2.test.ts`
tests timed out with four parallel workers (Contracts: **1147/1152 passed**),
matching the earlier phases' contention-sensitive failures. Consequently
root progress/roadmap/CI scripts and Python stages were not reached in that
invocation; do not call the aggregate gate green. An isolated rerun of the
unchanged Contracts test file with one worker and its default timeouts
**passed 30/30 tests**. An additional fresh, disposable unprivileged
PostgreSQL database run of
`npm run test -w @vera/project-service-host -- test/postgres.integration.test.ts`
**passed 1/1**, covering populated auth/doc migration repeat. Separately
`npm run lint:python` passed Ruff check and 967-file format verification;
`npm run typecheck:python` passed mypy on 339 source files.
The separately launched 8-worker `npm run test:python:fast` ran through
approximately 97% of its 2,596 scheduled items with four failure markers,
then stalled in a synthetic Resolve subprocess/bootstrap test. It was
interrupted by the operator after failing to complete; **no final pytest
summary or passing Python-test claim is available**. There were no Python
source changes in this ticket, and this incomplete run is not considered a
passing root gate. Do not infer failure causes without a completed traceback.
`npm run review -- notes.md`
was attempted exactly once but the Claude CLI reported its weekly quota had
been exhausted; an independent source/diff self-review and mutation audit
were completed instead. This remains **development QA**, never hosted-release
or Producer acceptance.
