# VERA #159 development-QA service and recovery review
- Goal: real loopback-only synthetic development-QA PostgreSQL service; never hosted release or production migration.
- Change: Node HTTP host reuses accepted auth/docs APIs, checksum migrations, shared PostgreSQL pool and private hashed bearer identities.
- Change: source-pinned private backup, fresh-only verified restore and separate-process HTTP/Postgres acceptance runner.
- Actual proof: phase 4 retained 13/13 localhost HTTP/PostgreSQL 16.15 restart, CAS, revocation, backup and restore scenarios.
- Phase 5 gate: generated checks plus all TypeScript ESLint/typecheck green, host 67/67 green; unrelated unchanged Contracts qualification test had 5 parallel timeouts.
- Mutation audit: 8/8 inverted secret/mode/role/migration/authorization/CAS/archive/restore guards produced targeted test failures; files restored.
- Self-review found and fixed the main-repository credential path gap for detached worktrees; added a focused regression.
- Review focus: auth/revocation and idempotency/CAS remain serialized; SQL inventories/rollback never overwrite existing destinations.
- External review attempted exactly once; Claude CLI weekly quota blocked. Hosted TLS, production identities, external backups and real-data acceptance unverified/out of scope.
