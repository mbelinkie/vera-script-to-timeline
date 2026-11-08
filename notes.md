Issue #386 backend-only attributed history, immutable checkpoints, approval and restore-as-new-head.
Changes add migration 003, authorized service methods, semantic fact comparison and strict HTTP routes.
The restore path appends a revision and provenance, then performs head CAS in one SERIALIZABLE transaction.
Focused PGlite tests cover roles, revoked sessions, tampered bytes, replay, tenant scoping and rollback.
Disposable PostgreSQL tests exercise restore/edit and restore/restore races across independent connections.
Run the repository fast gate with VITEST_MAX_WORKERS=1; full validation is out of scope.
Review cross-operation mutation-key races, history-provenance integrity and backward compatibility with 001+002 fixtures.
Review authorization before replay, response bounds, malformed query/body rejection and old document/build paths.
The release-build approved-checkpoint gate remains outside #386 and is not established here.
