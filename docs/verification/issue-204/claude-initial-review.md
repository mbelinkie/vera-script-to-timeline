# Verdict: **NO-GO** for candidate `560a44ed`

The candidate has the right overall shape:

- The ordinary #177 path is untouched.
- Every native call is a hard-coded `Get*` name behind a prefix check.
- Records are closed and reject duplicate keys and nonfinite numbers.
- Release, source and approval hashes are checked again between getter groups.
- Every result says `qualified` and `futureEffectsAuthorized` are false.

Two concrete defects block it. Both have small fixes. One is a truth defect in the gap table. The other is that the bootstrap's pre-import authority code has never been run by any test.

I could not run anything; tools were disabled. The fast evidence below is your supplied receipt, not my own rerun.

---

## Blocking findings

### B1 — The gap table can report clip controls as `supported` when the item inventory is incomplete

- **Where:** `python/vera_timeline_agent/native_qualification_v2.py:825-835`, `:601`, `:625-672`.
- **What happens:** If `GetItemListInTrack` raises, returns a non-list, or would push the total past 500 items, that track's inventory row is marked `unsupported` and the loop moves on (`continue`). Its items never reach `items`.
  - `_gaps` then builds `audio_items` only from tracks that were read. It marks `clip.enabled`, `clip.gainDb`, `clip.pan` and `clip.channelMap` as `supported` when `len(sources) == len(audio_items)`.
  - Nothing requires every `track:audio:N.GetItemListInTrack` row to be `supported`.
  - The run still finishes with `status: capability_gaps_observed`.
- **Trigger:** Audio track 1 has one readable item. Audio track 2's inventory getter fails, or exceeds the bound. Video items count toward that 500-item bound too. Result: clip-level controls are reported `supported` while part of the audio inventory was never read.
- **Why it blocks:** The issue says missing fields must never become "inferred complete control inventories".
- **Bounded fix:** Before any `clip.*` row can be `supported`, require:
  - `timeline:audio.GetTrackCount` is `supported`, and
  - every `track:audio:*.GetItemListInTrack` row is `supported`.

  Add those inventory rows to the gap's `sources`. Otherwise mark it `ambiguous`.
- **Same pattern, apply the same fix:** `render.candidates.GetRenderResolutions` can be `supported` from some formats when another format's codec read failed (`:904-905`). That gap should also require complete parent enumeration.
- **Add a test for each.**

### B2 — The bootstrap's qualification branch has no test coverage

- **Where:** `integrations/resolve/VERA Delivery v2.py:91-152`. This code:
  - checks the request's closed keys,
  - checks paths are absolute with no symlinks,
  - checks the authority hash and that the authority's binding equals the request's,
  - checks the approval hash and that evidence does not overlap protected inputs,
  - writes the pre-import `bootstrap-started-*.json`.
- **Gap:** The only bootstrap tests (`tests/test_issue204_native_preflight.py:315-336`) fail at the release-inventory and loaded-runtime checks (`:61-90`). Those happen before line 91. They also check only stdout, not that a refusal record was kept.
  - So the first time lines 91-152 ever run would be the real installed operator run.
  - The issue explicitly requires recording provenance before import, and testing authority, drift and undeclared-file refusals.
- **Bounded fix:** Add subprocess launcher tests using an installed `request.json`:
  1. **Clean path, no `resolve`:** expect exactly one `bootstrap-started-*` file whose hashes, pins and target match exactly, then a `stopped_safely` result.
  2. **Authority bytes changed:** expect `bootstrap-refusal-*` to exist, and no `started-*` or `result-*`.
  3. **Authority binding differs from the request's.**
  4. **Approval drift.**
  5. **Evidence directory inside the plugin root or the repository.**
  6. **Request with an extra key or a wrong action.**

  Assert the refusal file is kept in every negative case.
- **Should, same pass:** Add a `main([...])` test of `capability-authorize` and `capability-request`, the commands the operator will actually run (`workflow_v2_cli.py:212-263`). Cover a missing confirmation flag, which should exit 2 and write no file.

---

## Nonblocking limitations (fix before the operator run where noted)

1. **One unexpected format identifier stops all remaining observation** (`native_qualification_v2.py:892-899`). The regex `[a-z0-9]{1,16}` and the limit of 32 formats are enforced with `_require` inside the main `try`.
   - One odd identifier ends the run before codecs, audio formats, `GetCurrentRenderFormatAndCodec` and the render queue are read.
   - I believe, but have not verified, that Resolve's MXF variants use underscored identifiers. If so, a real run stops at a boundary the code created, not one the API imposes.
   - **Recommended before the run:** record unexpected identifiers as `ambiguous` and continue.

2. **Gaps are computed from every row even when the run stopped** (`:931`). Rows read after the last successful `guard()` still feed `supported` classifications. Reads go through the original target handles, so this is weaker than wrong-target evidence. Still, record the last guarded row index and mark later rows as unverified context.

3. **Issuer "provenance" is self-declared** (`:326-339`). `issuer.toolSha256` is compared with a pin recomputed from the same binding, so any hand-written JSON passes. Under the approved #109 local operator model this is acceptable, and the handoff discloses it honestly.
   - The plan's claim that the consumer "rechecks … tool/source identity" (plan `:67-68`) overstates this.
   - The authority has no freshness or replay limit; the tests run the same request twice.
   - Authority independence rests entirely on the operator procedure.

4. **Path overlap checks compare paths as text** (`:91-101`, `:273-280`, bootstrap `:129-133`). Two aliases on macOS slip past them:
   - Default APFS is case-insensitive, so `…/vera script to timeline/out` names the same directory as the repository but passes `is_relative_to`.
   - `/System/Volumes/Data/...` reaches the same directories through firmlinks, which are not symlinks.
   - Consequence: private evidence could be written into the repository checkout. Outputs never overwrite, so the damage is bounded.
   - **Fix:** compare ancestry by `(st_dev, st_ino)`.

5. **No hardlink checks.** Integrity still holds: every input is hash-pinned, and outputs are created with exclusive `os.link`. This differs from the repository's existing #144 convention of refusing hardlinked sources. No tests cover hardlinks or alias paths.

6. **Some failures lose evidence.**
   - The qualification dispatch (`workflow_v2_launcher.py:43-50`) skips the ordinary path's console print of the result (`:118-119`).
   - If the result exceeds the 2 MiB size bound (`:932-935`), every observation is discarded.
   - `bootstrap-started-*` is never made read-only, unlike the refusal record (`:214`).
   - The bootstrap overlap check omits `releaseRoot`. The controller catches this, but only after the bootstrap has already written.

7. **Channel maps may always come out `ambiguous`** (`:873-877`). The check requires `track_mapping` to be a list. I recall, without having verified it, that Resolve's documented Audio Mapping format makes it an object keyed by track number. If so, every real channel map is marked ambiguous. That is conservative, and the raw value is kept.

8. **Smaller items:**
   - Approval `recordedAt` is never validated (`:251-270`).
   - A getter that exists but raises is labelled `unsupported` rather than `ambiguous` (`:522-526`).
   - `RUNTIME_FILES` is duplicated in `native_qualification_v2.py:28-38` and `workflow_v2_cli.py:25-30`. If they drift apart, it fails closed.

---

## Test coverage

**Meaningfully covered:**

- missing authority, and a request binding that differs from the authority's
- unsupported action and extra field
- source and release drift before any native call
- exact request-hash drift
- request preparation without an authority, and each separate confirmation flag
- symlinked request path and duplicate JSON keys
- wrong target UID, wrong version, and timeline UID drift during the run
- missing getter, and a non-boolean value kept raw
- immutable repeated evidence
- undeclared installed file and an already-loaded runtime (at the release-inventory level)

**Missing:**

- the bootstrap qualification branch (B2), and incomplete inventory (B1)
- approval drift or wrong approval content
- evidence overlapping any protected input
- input drift during the run, after it starts (`guard()` → `_request`)
- type confusion in inputs (`true` or `204.0` for the issue number, `1` for a confirmation, `NaN`)
- wrong product name
- hardlink, case and firmlink aliases
- that a refusal record is actually kept on disk
- the CLI wiring

**Trap weakness** (`tests:35-46`, `:257-279`): a forbidden call raises `AssertionError`, which the controller's broad `except Exception` swallows. The trap never records the attempt in `calls`. The happy-path test would still catch a mutation, because its status would change. But the stopped-path tests would pass even if a mutation were attempted.
- **Fix:** record every forbidden attempt before raising, and assert that list is empty.

**Frozen boundary:** Judging by the supplied diff, changes stay inside the owned files. `workflow_v2.py`, `roundtrip_v2_native.py` and `roundtrip_v2_records.py` are unchanged, and there are no contract, fixture, golden or lock edits. The supplied fast receipt shows 494 passed and exit 0 at `560a44e`. That receipt is necessary but not sufficient.

---

## Held boundaries and required external gates

- **Operator UID provenance (held).** Resolve's UI does not show project or timeline UIDs.
  - A trusted source must already exist, for example a retained, audited #177 build result that records a VERA-created nonproduction project's actual UIDs. I cannot confirm any such record exists.
  - Using the UIDs that a mismatched preflight's `stopped_safely` report observed would be circular trust.
  - That, or any "identify the current target" step, needs an explicit coordinator or Producer decision. Do not prepare an authority until this is settled.
- **Private approval receipt.** Confirm the receipt at the handoff path exactly matches the six-key closed schema and the compressed `APPROVED_SCOPE` string. Otherwise the authorize step refuses.
- **After the B1/B2 fixes:**
  - delta review
  - fresh fast evidence
  - a complete local `VITEST_MAX_WORKERS=1 npm run validate`, per the verification policy
- **The real installed run:**
  - Resolve Studio 21.1.1 build 10, with External Scripting set to None, per the operator handoff
  - the operator personally issues the authority
  - evidence that the target was left unchanged
- **Scope:** #204 cannot close #178, and it authorizes no `qualify_build`, rendering or native effects.
