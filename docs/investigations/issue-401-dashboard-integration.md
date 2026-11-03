# #401 — existing dashboard integration

The approved `vera-queue-prototype.zip` baseline has SHA-256
`71a1b5c75520c09a1cb53d1b79a399bd58b663b097909067832a727870aaf5d6`.
The delivered compact progress/milestone/CI strip and grouped queue govern the
layout, as clarified in #401. Synthetic rows, receipts, buttons and clocks are
not production evidence. The implementation extends `renderDashboard` and the
existing Finder launcher; it adds no second dashboard or execution controller.

## Preserved local source

Before integration, read-only inspection found the existing dashboard responding
at `http://127.0.0.1:53842/`, served by `project-progress.mjs --serve` from
`feature/vera-master-roadmap-live-dashboard` at
`09da6b15ae7fb9144b1c66fe21304c414d49003a`. Its working directory had four
modified files: `Open VERA Progress.command`, `scripts/project-progress-lib.mjs`,
`scripts/project-progress-live.mjs`, and `scripts/project-progress.mjs`.
All four, their binary-capable patch, a hash manifest and the generated
`out/project-progress/index.html` were copied to a private local backup before
any integration edits. The original checkout was preserved. Implementation
started in an isolated `codex/401-verified-queue` worktree from freshly fetched
main `61d5c0eb874ef05f9eb9c1fd42339cf44782ae3c`.

## PR #395 disposition

| Path | Integration decision |
| --- | --- |
| `scripts/project-progress-lib.mjs` | Retain Queue Order, milestone, cross-project Size, native dependency and rate-budget handling. Explicitly exclude PR cards and retain strict issue validation. Replace the old queue markup with the approved layout. Union native dependencies with the canonical issue Dependencies section. |
| `scripts/project-progress-live.mjs` | Retain single-flight refresh, atomic replacement and last-good snapshots; bring forward the dirty checkout's startup fallback and waiting page. Enforce stale display and retry limits. |
| `scripts/project-progress.mjs` | Retain the existing static and `--serve` entry points and graceful startup fallback. |
| `Open VERA Progress.command` | Preserve the local background singleton launcher, with checkout identity checks before server reuse. |
| `scripts/project-progress.test.mjs` | Port useful queue ordering, Size and dependency regression coverage; update rendering assertions for the approved layout. |
| `package.json` | Run all focused progress tests, including the new adapter and renderer tests. |
| `scripts/chat-review-lib.mjs` and its tests | Omit the duplicate approval evaluator; import the merged #378 canonical verifier instead. |
| Setup documents | Superseded by this integration description and the launcher. No additional installation route is introduced. |

PR #395's original branch and PR are preserved. Skipped PR #375 is not merged
or used as an approval authority.

## Capability boundaries

| Visible action | Mechanism | Supported limits |
| --- | --- | --- |
| Open issue, PR, verified approval or Actions evidence | Read-only GitHub links and canonical #378 verifier | Approval is exact-revision and source freshness dependent. A label is insufficient. |
| Review in Chat | Interactive review prompt link | Opens a draft conversation; never records approval or starts execution. |
| Open an existing Codex chat | Merged #399 private mapping and independent installation identity | Local navigation only after Producer attestation; private identifiers are absent from saved HTML. It does not prove an agent is running. |
| Inspect CI | #361 durable state plus exact PR/head/base/run checks | Preview validation, ready delivery and post-merge smoke remain separate. No submit/resume control. |
| Launch Codex or run DeepSeek | Disabled | No authenticated dashboard execution backend or paid-job authorization. #396's unmerged controller is not imported. |
| Accept delivery | Separate issue acceptance | A merged PR or smoke result never substitutes for Producer acceptance. |

Rendering and local filters perform no network calls or mutations. Refresh
performs bounded GitHub reads, subject to rate limits; no model calls or spend.
Each source has its own fetched time and error state. A failed or expired
snapshot remains readable with stale workflow controls disabled. Remote hosting,
automatic chat wakeups and general shell access are outside #401.
