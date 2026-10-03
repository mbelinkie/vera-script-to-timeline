# Slice 1.7 — Durable build-job core (#35)

## Scope and boundary

Implement a local Python/SQLite `VideoBuildJob` core for the section 9.6 Free and
Studio stage graphs. A submitted job binds a project, immutable snapshot ID,
mode, optional render/delivery choices, and caller idempotency key. Stage
adapters receive only that job/project identity, a stable stage key, and a
job-owned output path. They must reconcile the stage key before executing and
must make external effects idempotent under it. The core verifies and records
one immutable local receipt per completed stage, retains every attempt and
progress event, and fences publication with an expiring lease epoch.

This slice provides the backend API, SQLite persistence adapter, status CLI,
and a local fake-stage CLI for a retained interruption demonstration. Compiler,
package, Resolve, render, and delivery adapters are **not** connected here;
those existing implementations and future services can use this seam after
their own idempotent reconciliation is established.

## Exclusions and contracts

No browser UI, deployment, production database/cloud credentials, Drive,
notifications, scheduler, real Resolve projects, research data, or in-place
reconciliation. No shared job/RPC schema is introduced, so no frozen contract,
fixture, generated type, or accepted golden changes. The new Python job
types and SQLite tables are internal to this slice. A later shared API requires
the producer-approved contract-change note described in #35.

No dependency is added: SQLite, file hashing, atomic fake-output publication,
and the CLI use Python's standard library. Tests create slice-owned temporary
databases and outputs only.

## Recovery rules

- A completed stage's recorded local receipt is rehashed before subsequent
  work. Missing or changed bytes fail the job without changing the completed
  stage's status.
- A worker always reconciles the stable job/stage key before attempting work.
  A stage adapter may run only after an authoritative absence; an uncertain
  result moves the job to `waiting` for a later reconciliation.
- One lease is active per job. Expiry permits a new epoch and retains the old
  attempt; a late epoch cannot publish, report progress, or change status.
- Cancellation sets a request while a stage runs. The stage may finish and
  publish its verified result; cancellation takes effect before the next
  stage. An idle job cancels immediately. Completed artifacts remain complete.
- Free stops at `ready_to_import` and advances to `import_confirmed` only on
  an explicit confirmation. Studio finishes after its requested stages;
  unrequested stages are reported as `skipped`.

## Test-first checks and acceptance

Add tests for duplicate keys and conflicting requests, both stage graphs,
lease expiry and late completion, process interruption, response loss,
waiting/resume, cancellation boundaries, tampered outputs, and concurrent
workers. Run the focused tests and full `npm run validate`, retain their
results, and move #35 only to `In review` under its Automated acceptance field.

For the producer's optional retained demonstration, use the documented
fake-stage CLI with a temporary project directory: start a job, stop its worker
during a deliberately delayed stage, restart the same job, then inspect
`status` for the same job ID, the unchanged completed artifact IDs, and the
expired/new attempt records. No real project or service is touched.
