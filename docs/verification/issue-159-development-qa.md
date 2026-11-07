# #159 — private development-QA PostgreSQL service recovery

**Status:** development QA only; not hosted-release, production backup, or
Producer acceptance. No Research database, media, external hosting, network
ingress, scheduled jobs, or billed resources. Phase 3 adds offline private
backup and fresh-database restore; phase 4 must prove the real HTTP application
can restart and read its restored roles, heads, revisions and audit records.

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

## Phase 4 verification and evidence to retain

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
