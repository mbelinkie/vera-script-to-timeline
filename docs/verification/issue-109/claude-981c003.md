# Re-review: #109 at `981c00322ce502a6b6dff36646c3383963a9ab8c`

## Decision: **CHANGES REQUIRED (narrow)**

All eight earlier findings (F1–F8) are correctly handled at this commit. No safety regression was introduced, and no frozen boundary drifted.

One new defect, N1, blocks the documented operator flow. It fails closed, so it cannot cause an unsafe mutation. But the runbook's own Finder steps are likely to trigger it, and its error message sends the operator back into the same loop. It is a small fix. Everything else below is non-blocking.

I reviewed only the supplied diff, sources and logs. I executed nothing.

## F1–F8 dispositions

| Finding | Verdict | Notes |
|---|---|---|
| F1 Target identity | Resolved | `create_project` and `create_timeline` capture unique IDs and assert immediately. `mutate` asserts before every stage after creation. `save_close_reopen` asserts before save, after save, and after reopen. Reopen requires the same project ID and `GetTimelineCount() == 1`. The runbook now forbids interaction until the result appears. Under an authorized run, the code can no longer save an existing current project. |
| F2 Bootstrap inventory | Resolved | Complete file and directory equality under `vera-delivery-v1/`. Symlinks and non-regular entries are refused. Undeclared files, `.so`, `.pyc` and empty `__pycache__` are refused. Inventory paths are bound by `resolve().is_relative_to(root)`. `pycache_prefix=None` and `dont_write_bytecode` are set before import. |
| F3 Cached runtime | Resolved | Any already-loaded `vera_timeline_agent*` module causes refusal. A same-interpreter relaunch test exists. |
| F4 Request binding | Resolved | Project name, timeline name and root are compared with the hash-verified attestation. `action` is a literal and authorization is a strict `bool`. Build still independently requires `externalScripting == "None"`. |
| F5 Hash and parse use the same bytes | Resolved | Attestation and `release.json` are each read once. Request bytes are pinned from bootstrap to runtime. |
| F6 Result survives storage failure | Resolved | The full result is printed before the `result-`/`hashes-` writes. |
| F7 Path normalization | Resolved | Both sides use `Path.resolve()`, matching the accepted `import_media`. |
| F8 Extra timelines and media | Resolved | Reopen requires one timeline. The whole media-pool tree is walked, including subfolders of Package Media. |

## Confirmed defects

### N1 — P2 (blocks the walkthrough, fail-closed): Finder `.DS_Store` breaks the installed inventory

**Where:** `integrations/resolve/VERA Delivery v1.py:41–65`, together with runbook steps 1–2.

**Problem:** `release_root.rglob("*")` includes dotfiles, so any `.DS_Store` makes `installed_files` differ from `declared_files`.

**Trigger:** the runbook tells the operator to:
- open the release folder in Finder,
- copy the entries in Finder, and
- use Finder again to put `request.json` into the installed `vera-delivery-v1/`.

Browsing a folder in Finder routinely writes a `.DS_Store`, either in the source release, which then gets copied, or in the installed directory.

**Impact:**
- Bootstrap refuses with "reinstall clean release".
- Reinstalling through Finder reproduces the refusal.
- Every attempt costs a Resolve restart.
- The promised reproducible handoff fails.

**Smallest fix:**
- In the inventory comparison, ignore regular, non-symlink files named exactly `.DS_Store`. That name cannot be imported as a Python module, so it does not reopen F2.
- Add a test with `.DS_Store` in both `vera-delivery-v1/` and `python/vera_timeline_agent/`.
- Add one runbook line: do not open the ready package folder in Finder before the build. The frozen verifier and the attestation inventory would also reject a `.DS_Store` there, which is correct, fail-closed and must not change.

## Non-blocking findings (recommended; P3)

### N2 — A missing track loses the whole discrepancy report

**Where:** `workflow_delivery.py` `verify`, the per-track loop.

**Problem:** the loop calls `GetItemListInTrack(kind, index)` for every manifest track, without the base adapter's `index <= GetTrackCount(kind)` guard. If Resolve returns `None` for a missing track, `sorted(None)` raises.

**Impact:**
- The result becomes `mutation_failed` carrying the exception text.
- The base discrepancies (track count, names, ranges) are lost.
- This is fail-safe, because the build is never marked verified, but it degrades the discrepancy report the issue promises.

**Fix:** use `... or []`, or skip tracks whose index exceeds `GetTrackCount(kind)`.

### N3 — Reusing a build request can create a same-named duplicate

**Problem:** `check_project_name_available` and `CreateProject` both work in the project manager's current folder. If a build request is rerun after a restart while a different folder is current, a second project with the same name is created there.

**Impact:**
- It does not overwrite an existing target.
- The evidence trail becomes ambiguous: two projects carry one name.
- The runbook forbids reruns, which is adequate for the audited flow.

**Optional hardening:** refuse a build when `evidenceDir` already contains a `started-*` record with the same `requestSha256`.

### N4 — A collision race is reported as a partial target

**Problem:** `mutation_started = True` is set before `create_project` runs.

**Trigger:** a name collision raised inside `create_project`, in the tiny window after the preflight check.

**Impact:** the result says `mutation_failed` with `partialTargetRetained: True`, although nothing was created. The report overclaims but the behaviour is safe.

## Test gaps

- **No full build through the real adapter.** No test runs the real `workflow_delivery.PublicResolveAdapter` build sequence (`create_project` through `verify`) against a fake injected Resolve. Build tests use `RecordingAdapter`, so how the subclass and base adapter work together in a build (manager set by `probe`, ID capture in `create_*`, timeline-current assertion after `create_timeline`) is only unit-tested. Adding one launcher-level build test like the existing preflight one would close this.
- `.DS_Store` tolerance (N1).
- `verify` with a missing track or a `None` item list (N2).
- CLI `request` refusals: build without both flags, and evidence or output inside the package.

## Questions only real Resolve evidence can answer

The earlier native questions Q1–Q7 still stand. In addition, these points would block acceptance even though each fails safe:

- **R1:** Does `CreateEmptyTimeline` make the new timeline current? If not, `assert_current_target` fails at `configure_tracks` on every build. The contingency is a `SetCurrentTimeline` call on the new project, which would need a code change and a fresh review.
- **R2:** Is `Timeline.GetUniqueId()` stable across close and reopen? If not, every build fails after reopen.
- **R3:** Are `Folder.GetUniqueId`, `Timeline.GetMediaPoolItem` and `TimelineItem.GetSourceEndFrame` present and behaving as assumed on 21.1.1/10?
- **R4:** Does Resolve write any file into the package directory during import (caches, sidecars)? If it does, the per-stage package rehash fails every stage after import.
- **R5:** For audio events, is `GetSourceEndFrame` measured in the manifest's timeline-frame units?

## Remaining native acceptance limits

These are unchanged and are not a code-gate failure:

- External Scripting None is an operator statement only; the code cannot observe it.
- 21.1.1/10 is still an uncalibrated candidate. Still-image compensation of 0 is unproven there, though a wrong value would surface as duration discrepancies.
- The only native evidence is the ResolvePython 3.14.4 `-S` import, which is import evidence, not a launch.
- No installation, launch, save/reopen, readback or Producer check of existing timelines has happened. Mocks and the 561 passing tests do not substitute for any of them.
- The walkthrough still needs:
  - the None screenshot,
  - the installed `release.json` SHA, which will change from `dcb8aaed…` once N1 is fixed,
  - a `verified` result and its hashes,
  - manual inspection of the reopened target, and
  - confirmation that the disposable project is unchanged.

Fix N1 (and preferably N2), rerun the focused tests and the gate, and get a re-review of the new commit before the native walkthrough.