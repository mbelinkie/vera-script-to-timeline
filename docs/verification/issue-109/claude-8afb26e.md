# Antagonist review: #109 at `8afb26e`

## Decision: **Changes required**

All fixes below are small. None of them touches frozen contracts or the accepted #34 source; each can live in the #109-owned modules.

The core design holds up:
- **Attestation:** the injected runtime rechecks a hash-pinned attestation before preflight, before creation and before every mutating stage.
- **Startup:** Python `-S` startup avoids the verifier and native-bridge imports.
- **Version gate:** it is exact.
- **Target creation:** it is gated by both a collision check and explicit authorization.
- **Failures:** every post-creation failure retains the named partial target.

I found one moderate target-identity gap, two bootstrap-integrity gaps, and several low-severity issues.

---

## Confirmed defects

### F1 — P2: Save, close and reopen do not verify which project they act on

**Where:**
- `python/vera_timeline_agent/workflow_delivery.py:~181–214` (`mutate` and the stage sequence)
- The inherited `studio_spike.py:767–778` (`save_close_reopen`)

**Problem:**
- `ProjectManager.SaveProject()` takes no arguments and saves whichever project is current.
- `CloseProject(self.project)` and `LoadProject(name)` key on a held object and on a name in the current folder.
- Nothing asserts that the current project is still the one `create_project` just created.

**Trigger:** while hashing, import or append is running, the operator or the UI switches to another project, either by reopening the disposable project or by changing the project-manager folder.

**Impact:**
- `SaveProject` persists the other, existing project. That is a write to an existing target under an authorized run.
- The following mutations (bins, timeline, markers) act on a project object that is no longer current, which is undefined in the API.
- Reopen confirms identity by name only. A folder change makes `LoadProject` fail, which is safe, but the result still records no proof of identity.

**Is the operator step adequate?** The runbook tells the operator to save the disposable project before launch, but it never says "do not interact with Resolve until the result is written." So the code can still mutate an existing project during an authorized run. Whether the UI is actually interactive while a Workflow Integration script runs is a native question (Q1); the guard should exist either way.

**Smallest fix** (in the #109 subclass and `mutate`, no change to `studio_spike.py`):
1. After `create_project`, capture `self.project.GetUniqueId()`.
2. In `mutate`, for every stage after creation, and immediately before `SaveProject`, require that `manager.GetCurrentProject().GetUniqueId()` equals the captured ID. Otherwise raise, which retains the partial target.
3. After `LoadProject`, require the same unique ID and exactly one timeline (`GetTimelineCount() == 1`).
4. Add the instruction "don't touch Resolve until `result-*.json` appears" to runbook step 4.

### F2 — P2: Bootstrap integrity covers only `*.py` and `*.pyc` files

**Where:** `integrations/resolve/VERA Delivery v1.py:41–48`

**Problem:**
- The installed-inventory check compares only `rglob("*.py")` and rejects only `*.pyc`.
- CPython's `FileFinder` tries extension modules (`.cpython-314-darwin.so`, `.abi3.so`) before `.py` files in the same directory.
- Setting `sys.dont_write_bytecode` stops writes but not reads. If Resolve's interpreter has `sys.pycache_prefix` or `PYTHONPYCACHEPREFIX` set, cached bytecode is read from outside the checked tree.

**Trigger:** a `workflow_delivery.cpython-314-darwin.so` file sits in `vera-delivery-v1/python/vera_timeline_agent/`, or a prefix cache matches the source mtime and size.

**Impact:**
- Unverified code runs while the release check passes.
- The runbook's claim that the launcher "refuses extra Python source and bytecode caches" is not true.
- Exploiting it needs write access to the plugin root, but the promised guarantee is broken.

**Smallest fix:**
1. Require that the complete file set under `release_root`, excluding `request.json` and `release.json`, plus the script, equals the declared inventory.
2. Reject any directory not implied by that inventory, including `__pycache__`.
3. Set `sys.pycache_prefix = None` before the import.
4. Add tests for an extra `.so` file and for an extra non-`.py` file.

### F3 — P2: Cached runtime modules survive an on-disk update

**Where:** `VERA Delivery v1.py:49–58`

**Problem:** if `vera_timeline_agent.*` modules are already in `sys.modules` from the same runtime path, the check passes. The import then returns the cached modules from the first launch, while the hash check has only verified the new bytes on disk.

**Trigger:** within one Resolve session, the operator launches, then installs an updated release and request, then launches again.

**Impact:** the report stamps the new `releaseSha256`, but the code that ran was the old release. That is false version evidence.

**Is the operator step adequate?** The runbook requires a restart after every update and between preflight and build. That is adequate for the audited flow if it is followed, but the code cannot detect a missed restart.

**Smallest fix:** before the import, remove every `vera_timeline_agent` entry from `sys.modules` (all of them are pure Python). Alternatively, refuse to run if any are present. Add a test that runs the launcher twice in one interpreter with the release swapped between runs.

### F4 — P3: The request's target is not checked against the attestation

**Where:** `workflow_launcher.py:33–48`

**Problem:**
- `requestedProjectName` and `requestedTimelineName` are copied into the evidence but never compared with the attestation's names.
- `request["action"]` and the authorization booleans are not schema-checked either. A string `"true"` fails safely only by accident.

**Impact:** a hand-edited request can record authorization for target X while target Y is created. That breaks the "authorize that named target" audit trail.

**Fix:** after `load_verified_package`, require equal project and timeline names, `packageDir` equal to the package root, and boolean types for the authorization fields. Add a test.

### F5 — P3: Hash-then-reparse race on the attestation and `release.json`

**Where:**
- `workflow_package.py:97–100`
- `VERA Delivery v1.py:23–28`

**Problem:** the file is hashed, then read and parsed in a second open. The parsed content is not bound to the hash.

**Fix:** read the bytes once, hash those bytes, and parse those same bytes.

### F6 — P3: A failure after the run leaves only a generic Console report

**Where:** `workflow_launcher.py:50–53`

**Problem:** if writing `result-` or `hashes-` fails after a target was created, the bootstrap fallback reports only `workflow_launcher_failed`. It has no partial-target or discrepancy fields. Only the `started-` record names the target.

**Fix:** print the result JSON to the Console before attempting the write.

### F7 — P3: Media path comparison is a raw string match

**Where:** `workflow_delivery.py:~83–92`

**Problem:** the subclass compares `GetClipProperty("File Path")` to `str(path)` directly. The accepted `import_media` normalizes with `Path(...).resolve()` instead. Any path normalization difference between the two produces a false discrepancy.

**Impact:** fail-safe (the build is marked unverified, never falsely verified), but it is noise in the result.

**Fix:** normalize both sides the same way the base adapter does.

### F8 — P3: Readback does not check for extra objects outside the expected locations

**Problem:** readback never looks for:
- extra timelines in the new project (F1's `GetTimelineCount` check covers this), or
- media placed in bins other than the final `Package Media` bin.

**Fix:** walk the whole media pool tree, and assert that no clips exist outside the expected bin apart from the timeline item.

---

## Test gaps

- **Drift recheck timing:** only drift after `create_project` is tested. Add drift after `import_media`, `place_events` and the first `add_marker` to prove the recheck happens before every stage.
- **F1:** a current-project switch before `SaveProject`, and a unique-ID mismatch after reopen.
- **F2 and F3:** an extra `.so` file, `pycache_prefix`, and a relaunch in the same interpreter after an update.
- **F4:** a request whose names, action or booleans don't match the attestation.
- **Installed path end to end:** no test runs the shipped launcher through a passing preflight with a valid attestation and a fake injected `resolve`. Every launcher test stops at a missing attestation.
- **Release subset import:** the `-S` import test runs from the repository tree. Add one that imports only the six shipped release files.
- **Version boundaries:** test adjacent builds such as 21.1.1/9, 21.1.1/11 and 21.1.0/15.

## Questions only real Resolve evidence can answer

| | Question |
|---|---|
| Q1 | Can the UI switch projects or folders while a Workflow Integration script runs? This sets F1's practical severity. |
| Q2 | Does `CreateProject` implicitly save or discard unsaved changes in the current project? The runbook's save-first step makes either outcome harmless if followed. |
| Q3 | Does each launch get a fresh interpreter? This sets F3's practical severity. |
| Q4 | Is `__file__` defined, and is the system plugin root the location actually executed? |
| Q5 | On 21.1.1/10, is still/placeholder end-frame compensation 0? A wrong value fails safe as duration discrepancies. Also, is `GetSourceEndFrame` inclusive, in source-rate frames? |
| Q6 | Do `GetMarkers` keys and the `File Path` form match the manifest frames and resolved paths? |
| Q7 | How long does a full rehash before each marker stall Resolve with real media sizes? This is operational risk, not a correctness defect. |

## Remaining native acceptance limits

- External Scripting None is an operator statement only; nothing in the code can observe it.
- 21.1.1/10 is still an uncalibrated candidate.
- The only native evidence so far is the ResolvePython 3.14.4 import test. No installation, launch, save/reopen or Producer check of existing timelines has occurred, and mocks and import tests do not substitute for any of them.
- After fixes, the Producer walkthrough still needs:
  - the None screenshot,
  - the installed `release.json` SHA,
  - a `verified` result and its hashes,
  - manual inspection of the reopened target, and
  - confirmation that the disposable project is unchanged.

Fix F1–F3, which are blocking for the native run, and preferably F4. Rerun the affected focused tests, then request re-review before the native walkthrough.