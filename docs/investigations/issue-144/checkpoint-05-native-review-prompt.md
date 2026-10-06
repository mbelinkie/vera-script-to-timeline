# Claude checkpoint 5 — completed injected Studio assembly seam

Continue independent review of VERA #144. Repository reads only; do not edit,
run tests, connect to Resolve, read private media/credentials, invoke providers,
publish, add agents/tools/plugins or change claims. This is a completed segment
review, not Producer/native acceptance. Prior reviews and dispositions are
retained in this directory. The Producer requested regular plan and finished
segment checks and authorized direct CLI exchange.

Read:

- `python/vera_timeline_agent/roundtrip_native.py` (new completed segment)
- `python/vera_timeline_agent/roundtrip_build.py` (parser and replay integration)
- `tests/test_issue144_native_build.py` (six issue-owned fake native checks)
- `tests/test_issue144_prepared_build.py` (20 prepared-input checks)
- `docs/investigations/issue-144/checkpoint-04-disposition.md`
- Current complete `docs/plans/issue-144-roundtrip-harness.md`
- Unchanged #34 studio_assembly, #35 build_jobs and package APIs as needed.

This runs actual compiler/package/job/Studio assembly logic with an explicitly
injected fake native adapter and a fresh read-only inspector. No default live
adapter is allowed. Intent is exclusively reserved/fsynced before any effect;
only one owner may enter assembly. Result and first UID map are immutable;
lost/unverified result never retries creation. Completed replay rechecks native
UIDs, all mapped events, settings/tracks/markers, package-relative media bytes,
enabled state and normal speed. No baseline promotion or real native claim.
Inspector mapping is a future WI seam, not an already implemented real observer.
Core evidence stays local_prepared; injected native receipts synthetic_injected.

Focused first run: 48 passed (five native +20 prepared+23 accepted regressions).
New exclusive-reservation test makes six native checks. Whole-tree Ruff/mypy
checked; full validate run retained separately. Accepted compiler/validator,
Studio/job sources, frozen contracts/types/fixtures/goldens/locks unchanged.

Inspect concrete failure/recovery paths:

1. Two workers/expired leases, intent reservation and crash between intent,
   assembly, result, UID map and stage receipt. Any path to duplicate effects?
2. Missing, changed or foreign result/intent/UID mapping and completed replay.
   Can an unverified native target cause complete status or baseline eligibility?
3. Compare the inspector contract with what the accepted real boundary can
   actually observe. Identify any impossible or overclaimed mapping now, before
   WI implementation. Synthetic injected checks cannot establish real support.
4. Reconcile/execute behavior on #35 durable stages and exact compiler/package
   bytes. Does custom completed-stage reconciliation preserve integrity or trust
   a corrupted SQLite path/receipt too far?
5. Parser correction: integer safe range, finite floats and failure envelopes.
   Request no bespoke tokenizer or accepted-source modification.

Next planned audio gate remains scoped to hash-bound retained W1 source/fixture
support declarations: structural no-overlap/full-neighbor-preservation primary,
full per-channel render reconstruction consistency secondary. No known-good
hash short-circuit to a verdict. Numeric limits cannot prove arbitrary quiet
residue; tiny/quiet probes stay an explicit non-generalization check. Producer
route/wording remains pending before omission-rebuild positive. No changes to
#148/#145 dependencies or paid-service authorization.

Return actionable findings with severity, concrete location, failure example
and smallest bounded fix. Distinguish implementation bugs from unimplemented
WI/semantic seams. State whether this segment may be used as the injected
native-boundary foundation for the remaining harness, and what must wait.
