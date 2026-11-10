# #499 helper completion — document phase 1 / Conductor phase 20 reconciliation

Date: 2026-11-10. This is **repository/plan reconciliation only**. No Resolve,
native owner, GUI menu, project, target, render, one-use intent, or receipt was
operated during this phase.

## Frozen instructions and sole continuation

- Read the complete 25,572-byte `.pipeline/499/issue-499-vera-helper-completion.md`
  *before inspecting or changing anything*. Its independently computed SHA-256
  equals `816b5dd17611d5b8198a453ce6fe687d12c201f2438a2d6d88ed6a8e5617be18`.
- `.pipeline/499/plan.json` contains **31** phases, `current=20`. The first
  19 phase entries compare equal to their archived counterparts in
  `plan-before-vera-helper-12-phase-replacement.json`; entries 20–31 correspond
  in order to the document's twelve helper phases. The old plan remains an
  archive, not another eligible pending plan. The previous progress entry
  records the authenticated phase-20 Conductor nudge; daemon in-memory state
  cannot be independently inspected in this Linux Zodex environment.
- Original adopted PR **#474** remains **open, draft, unmerged**, on
  `chat/473-unattended-test-bench`. The remote PR head is
  `6002418666d7d338f0821ac01eb500e2f6fea6c9`, exactly the
  `adoption.json.expectedSha`. The retained local work branch is
  `zodex/499-adopt-pr474`; `adoption.json.startingSha`
  `daec386bdccd243402dc3d358dbd19b783d1a318` is an ancestor.
  `git worktree list --porcelain` shows the exact worktree **locked** with
  reason `vera adopted PR`. It was **not** replaced, reset, rebased, pushed
  or merged. Local branch is seven commits ahead of the remote PR head;
  Conductor retains the checkpoint/push/merge lease.
- The required tracking-only helper issue was absent in repository issue
  searches. Created **#505** as a sub-issue of #499 expressly forbidding
  concurrent implementation, a new PR or a competing native Test Bench actor.

## Recovered files, source and actor pins

- Recovery began with `progress.md`, `git status`, `git diff --stat`, and
  `git log -5`. The only pending tracked change was the bounded System Events
  activation fix in `resolve_test_bench_ui_readiness.py`. The existing
  simulated activation mock required updating to handle the added `open -g`
  subprocess call. Focused verification passed; committed both files as
  `5473b58a0affabdad80fa68a9aef22416e51cd17` (`wip: recovered`).
- There are **no untracked runner/test files** in the adopted worktree:
  `git ls-files --others --exclude-standard` was empty. Existing M4 runner
  and its tests are tracked. The working checkout is now clean. Build products
  and old private Mac-case evidence remain outside the checkout.
- Current **candidate** proof-source graph computed by
  `resolve_test_bench_full_loop._source_hash()` is
  `b492a93e50273c4baeab6e2d93e87aea7db43d16b157227f3fa172f9663226d8`.
  The old one-command Roll actor pin is
  `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`.
  These are diagnostic comparisons **only**, not a new approved freeze, a
  Swift-helper identity or authority for any historical operation. The plan
  explicitly notes that helper Swift source/binary pins are not yet included;
  they will be implemented in phases 21–24.

## Consumed, expired, or uncertain native cases: replay never allowed

Historical evidence remains immutable. This census is not a claim that any
native worker is now running or stopped; last observed status is preserved.

| Existing case/authority | Last recorded observation | Eligibility |
|---|---|---|
| Original #473 campaign and later source-sealed pristine 1/4 | Expired or bound to earlier source graph | No replay or reseal |
| One-use direct Roll calibration (v1/v2) | Separate diagnostic executed; target/source and effect spent | No production M4 reuse |
| `issue-499-phase18-internal-stage-20261109` | Earlier launcher/authority failed or expired | No relaunch |
| Phase-20 recovery `9795a20bde634bbd` | `launchctl` ran, repeated launcher entry, failed before M4 intent; bounded authority expired | No relaunch |
| Phase-20 recovery `59682d75ada24d68` | Prior compiler/launcher failure after one-start intent | No relaunch |
| Phase-20 recovery `803b807cf8904422` | Last recorded live pristine runner, then terminal result not established here | UNKNOWN; preserve |
| Phase-20 recovery `e4b55f10847a47ae` | Authentic pristine 1/4; one-use loop UNKNOWN after System Events readiness failure | Spent; no replay |
| Phase-20 recovery `7723b67e4ef347fd` | Authentic pristine 1/4; one-use F1 intent consumed, edited verification failed on old package-root comparison | Spent; no replay |
| Phase-20 recovery `a6ef98888dd44d8c` | Last progress recorded a live pristine runner and 0/4 signed; no terminal proof here | UNKNOWN; preserve |
| Fifth config-only/other pre-effect diagnostic roots | No authenticated full M4 accepted on current graph | Old-bound/uncertain; no reuse |

Evidence: `.pipeline/499/progress.md`, `phase5-acceptance-ledger.md`,
`phase20-retry-brief.md`, `phase19-source-refreeze-reapproval.json`, and the
existing `docs/verification/issue-499-phase20-*.md` files. Native M4 **4/4**
and strict #312 success **have not been shown** by those records. The new
helper track must start with its own qualified code/build and fresh authority.

## Revised attempt policy and eventual merge requirements

The **three-attempt ceiling is obsolete**. Follow section 2 of the verified
helper document instead: recorded diagnosis, targeted correction, focused
test/rehearsal, brand-new case/UIDs/source/actor-bound attribution, and previous
owner/evidence reconciliation **between** attempts. There is **no automated
retry loop**, and no case can have its spent intent reopened. Older
`overnight-100-attempts-authorization.md` is a retained historical request,
not an active trial quota or authority bypass.

`origin/main...HEAD` had 18 main-only and 106 branch-only commits at the
local checked refs; the original PR is not current with main. The PR's
GitHub metadata reports `mergeable=true`, which does **not** prove required
checks or branch rulesets. A read-only public branch-protection API probe
returned HTTP 401 (`Requires authentication`); the available connected PR
metadata does not expose rulesets, so **specific protection requirements are
unverified**. Repository policy requires main integration, required CI and
source-matched verification. Resolve main changes/conflicts in Conductor phase
27 (document phase 8) **before the release freeze**, not by rewriting source
in phase 20. Conductor phase 31 must recheck current delivery-head CI,
protections, reviews, ancestry and frozen source equivalence before merge.

## Checks and verdict

- Full helper document hash: **PASS**.
- Historical 1–19 equality / current phase 20 / 31 phases: **PASS**.
- Original PR remote SHA, adopted starting-commit ancestry, branch and worktree
  lease: **PASS** by read-only checks; direct daemon memory not accessible.
- Worktree recovery: initial 7 test failures from changed subprocess mocking;
  repaired; `uv run --frozen pytest -q tests/test_resolve_test_bench_ui_readiness.py`
  **128 passed**; Ruff check, Ruff format check, `python3 -m py_compile`,
  `git diff --check` **PASS**.
- Clean checkout, tracked runner/tests and no competing helper issue: **PASS**.
- Full `validate:fast`: **not run** in this maintenance-only phase; later
  source-changing phases have explicitly scheduled gates.
- Native tests: **not run and not claimed**. All old-case effect identities
  remain ineligible.

**Result:** Phase-1 repository and plan reconciliation satisfies the bounded
acceptance criteria. Advance only to document phase 2 / Conductor phase 21
for simulated actor/protocol contracts. No historical case is authorized by
this result; all prior UNKNOWN or consumed authorities remain spent.
