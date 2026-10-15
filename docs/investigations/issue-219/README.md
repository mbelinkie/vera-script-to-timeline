# #219 — Table semantic-target feasibility evidence

Actual Studio 21.1.1 build 10 supports the pinned Table's two synthetic row targets
through a native Text-output animation modifier. This is a proposed per-template
contract, not production implementation or acceptance of #167.

Read [contract-proposal.md](contract-proposal.md) and the exact
[target-manifest.json](target-manifest.json). Public evidence contains no asset
bytes, raw readback or render images. The local private entry point is the
worktree's ignored `out/issue-219/PRIVATE-INDEX.md`; preserve that directory with
this worktree for Producer review. Do not upload it.

Final automated verification and adversarial review passed. The full gate tested
clean commit `5ae5e34fd3594071865974d25afc4975bf878972`; exact counts/tool versions,
log digest and source inventory digest are in [final-validation.json](final-validation.json).
Initial and delta Claude reviews returned GO with no blockers; limitations and
dispositions are in [review-disposition.md](review-disposition.md). Remaining
acceptance is the numbered Producer checklist below, including restoration choice.

## Reproducible checks

From the repository root, using its locked tools:
`rtk` and `ctx-wire` are workstation output wrappers; the commands they wrap
are the reproducible checks and need no repository dependency change.

```sh
rtk proxy ctx-wire run uv run --frozen python -m unittest discover -s docs/investigations/issue-219 -p test_probe.py
rtk proxy ctx-wire run uv run --frozen ruff check docs/investigations/issue-219
rtk proxy ctx-wire run uv run --frozen ruff format --check docs/investigations/issue-219
rtk proxy ctx-wire run git diff --check
```

Render analysis uses the app's bundled Python/Pillow returned by
`load_workspace_dependencies`, without adding a project dependency:
`<bundled-python> docs/investigations/issue-219/analyze_renders.py`.
It verifies the exact 72-file set, frame-pair pixel equality, ICC-only creation
timestamp differences and row-band state/black-endpoint assertions. It writes
only the private analysis receipt. The private index records the actual command.

## Native probe reproduction

Do not run live operations without Producer permission, a fresh issue-owned
disposable project and exclusive Resolve/host capacity. Never reuse a production
project or rerun an ambiguous mutation. Do not install globally.

1. The private setup scripts record the exact source pointer, generated seed,
   observed endpoint corrections and imported whole-setting hash. Preserve the
   failed setup attempts; the confirmed setup records actual 0/240/240 placement
   and composition frames 0–239 before any control write.
2. Import `probe.py` through Python `importlib.util.spec_from_file_location`,
   setting `VERA219_TEMPLATE` to the private selected source pointer. Use the
   private receipt's exact project UID and fixed Studio profile. Python
   optimization flags are refused because this isolated probe uses assertions.
3. `prepare(resolve, project_uid, "run-a", case)` creates one fresh timeline for
   each fixed case `sequential`, `start-only`, `overlap`, `continuation`; repeat
   with `run-b`. Existing names/receipts refuse retries. `verify` records
   `before-reopen`; `reopen` then `verify(..., "after-reopen")` checks persistence.
4. `queue_case` creates per-frame private job intents/IDs, with one short call
   per case/run. `start_render` starts only the exact 72-job inventory after a
   separate actual capacity release. `render_status` observes that batch once
   per scheduled wake without restart. `verify(..., "after-render")` checks all
   four cases in each run after completion.
5. Run analysis and retained focused checks. Native graph enumeration alone is
   never evidence of rendered capability. The probe rejects graph/control/type,
   source/data/manifest mismatches and conflicting/unknown target schedules.

Live graph/control inspection runs after disposable import/output setup and
before control/state writes. A mismatch leaves a refused scratch timeline;
the pure flag tests are not injected live graph-mismatch tests. Run A used the
earlier batch preparer, Run B the single-case preparer, with identical `CASES`
and writes. Both are separate imports in one project/session and one render batch.
Run A's pre-refactor code hash is missing; current readbacks and pixel comparison
verify its retained output rather than claiming identical preparer binaries.

No source template was rebuilt, installed or edited. Import adds only the
accepted MediaOut connection and native keyframing modifier to each local
instance. The supplied font is workstation-only, not bundled. The Probe's render
batch left the disposable project's selected render format PNG/RGB8 despite
queue-time restoration; initial selection was MOV/H264, mode 1. This is retained
as an issue-project setting difference. No global setting was changed by the
agent; Producer set External Scripting Local. After #8 explicitly released
exclusive Resolve access, restoration was attempted, but the bridge reported
Resolve closed and no mutation ran. An initial completion message/commit was
incorrect and is superseded here. PNG/RGB8 remains the last observed selection
in the disposable project; restoring MOV/H264 is an open operator step. Do not
relaunch or switch projects solely to hide this difference. Global settings and
rendered proof are unaffected.

## Producer acceptance checklist

1. Open the contract proposal and exact target manifest. Confirm the selected
   Table hash, supplied asset authorship/rights and locally licensed **ITC
   Franklin Gothic LT Pro / SemiBold ExtraCondensed**. This approves this local
   probe/contract use only; future distribution/registration is separate.
2. Confirm `target-a`/`target-b` mean the frozen Alpha/Beta rows at positions
   1/2, independently of display labels. Any data edit/reorder/rename invalidates
   the mapping; no automatic identity repair is implied. Confirm only base and
   emphasis, aggregate writes, stepped timing and this exact Studio profile.
3. Open `PRIVATE-INDEX.md`, then its Run A frame links. At sequential 47/48,
   71/72 and 95/96 expect base→Alpha→Beta→base. At overlap 72 both rows are red;
   at 96 only Beta; at 120 neither. At continuation 71 and 72 Alpha remains red.
4. Check start-only 48/71/72 and end samples: Alpha lasts until the next cue at
   72, then Beta until Graphic end. At 239 the authored exit is black even though
   readback remains Beta. Confirm the proposed visibility/state distinction.
   Review the private analysis report: all 36 Run A/Run B decoded RGB pairs
   match, and reopen/post-render readbacks agree. This is sampled-frame proof.
5. Account for the still-open disposable-project render-format restoration:
   last observed PNG/RGB8 mode 1, initial MOV/H264 mode 1. The attempted restore
   never ran because Resolve was closed. In a later exclusive window, open only
   the private index's exact issue-owned project and restore/read back MOV/H264
   mode 1, or explicitly accept this retained disposable-project difference.
   Never switch or alter another task's project. Record which choice you make.
6. Confirm Free is untested/unavailable with explicit manual/blocked treatment;
   no production compiler/runtime, general dataset identity, other template,
   duration/frame rate or edition is qualified. Then reply:
   `ACCEPT #219 — I accept the pinned Table synthetic target contract and its
   sampled Studio evidence, including fixed position bindings, conservative
   invalidation, stepped states, authored-exit visibility and stated limits;
   render-format restoration is <completed / accepted as retained difference>.`
   Or: `FAIL #219 — step <number>: <mismatch or required decision>.`

The issue remains In review until explicit Producer judgment is retained.
Passing this probe does not accept #167's compiler/runtime or broader templates.
