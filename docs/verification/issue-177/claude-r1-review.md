# Verdict: **NO-GO**

The candidate is 1457e52 against baseline 7867fa4. Its frozen-boundary posture, fail-closed ordering, immutable publication and retry, and the fractional, sidecar and slate refusal ordering are sound. Four defects block closure:

- Two of them stop real v2 topology and source-audio packages from reaching the adapter at all.
- One is a readback regression from the accepted #109/#34 behavior.
- One is a named P7 topology obligation that neither layer enforces.

Every test that passes did so by bypassing the failing seam: direct private calls with `validate=False`, or hand-built runtime packages.

## Blocking findings

### B1 — The runtime refuses any real continuous-root return

- **Where:**
  - `python/vera_timeline_agent/workflow_v2.py:1037-1042` requires `return.recordFrame == rootEvent.recordRange.startFrame`.
  - `python/vera_timeline_agent/v2_package.py:767-773` instead allows `root_start <= frame <= root_end`.
- **Trigger:** any manifest with `composition.returns` non-empty. Under #56 and the plan's §3.2 rule ("one continuous event… a return reveals the existing advancing source; no restart event"), the return frame lies strictly inside the single root event.
  - `build_v2_package` and `verify_v2_package` accept such a manifest.
  - `attest_package_v2` then fails in its own `load_verified_package_v2` self-check (`workflow_v2_cli.py:104`), with "composition return does not bind to its root event".
- **Impact:**
  - AC2 "return-with-no-new-event" cannot be delivered or preflighted at all.
  - The two verifiers disagree on the same retained artifact.
- **Coverage hole:**
  - `test_accepted_root_child_overlay_return_otio_round_trip_without_source_audio` (`tests/test_v2_package.py:135-207`) calls private helpers with `validate=False`. It never runs `_validate_delivery_view`, `_media_artifacts`/`_validate_preparations`, build, attest or load.
  - Every runtime and handoff fixture has `returns: []`.
- **Smallest fix:**
  - Use one rule in both validators: `root_start < recordFrame < root_end`, with `emitsNewSourceEvent is False`.
  - Add a runtime test (extend `_make_package` with a child event and a return) asserting that load and fake-build succeed and that no extra root event is placed.
  - Run the package fixture through `_delivery_view(..., validate=True)`.

### B2 — Every aligned source-audio preparation receipt is refused

- **Where:** `python/vera_timeline_agent/v2_package.py:1197-1206`.
  - `actual_offset` and `actual_delivered_first` are `Fraction`s, but they are compared with `!=` against dicts.
  - `Fraction != dict` is always `True`.
- **Trigger:** any #174 receipt with `audio != None`. The refusal fires ("audio coordinates do not bind to P2") even for perfectly bound data.
- **Impact:**
  - No package containing a `source_audio` event can be built.
  - The stated readiness ("package preflight retains their metadata"; Quiet/Full −18/0 dB per AC3) is unreachable through the real builder.
- **Coverage hole:**
  - Both Quiet/Full package tests (`tests/test_v2_package.py:241-365`) call `_delivery_view`/`_source_audio_range` directly. They use contrived receipts and never reach `_validate_preparations`.
  - The runtime source-audio tests use a hand-built package (`tests/test_workflow_v2.py:141-186`) that the builder cannot produce.
  - There is no "No emits no source audio" test.
  - There is no source-audio overlap test; only same-track overlay overlap is tested.
- **Smallest fix:**
  - Compare `actual_offset != expected_offset` and `actual_delivered_first != expected_delivered_first`.
  - Add a fixture variant with an aligned audio receipt and an end-to-end build→verify→attest→preflight for Quiet and for Full.
  - Add a refusal test for a mute-policy event (refused by schema).
  - Add a cross-track source-audio overlap refusal. Per-track overlap is checked at `v2_package.py:719-735`, but `sourceAudioTrackIds` is plural, so overlap across tracks is not.

### B3 — Reopened readback silently ignores tracks that have no expected events, and does not compare marker fields

- **Where:** `python/vera_timeline_agent/workflow_v2.py:1278-1338`.
  - `verify` iterates only `by_track` (slots that have expected events).
  - It checks markers by frame and custom data only.
- **Trigger:** after save/reopen, any of these goes unreported:
  - a stray item on a declared-but-empty track (an empty child, overlay or source-audio track);
  - a stray item on an undeclared intermediate index within the expected count;
  - a marker whose name, note or color changed.
- **Impact:**
  - A false `"verified"` result.
  - This regresses the accepted #34 readback (`studio_spike.py:821-899`), which iterated every actual slot and compared marker fields. v2 overrides `verify` without calling `super()`.
- **Smallest fix:**
  - For each kind, iterate indices `1..GetTrackCount(kind)` and compare against `by_track.get(slot, [])`.
  - Compare the `GetMarkers()[frame]` name, note, color and duration with the view marker (color via `_MARKER_COLORS`).
  - Add one fake test with a stray item on an empty track, and one with a changed marker note.

### B4 — Root/child/overlay layering and role disjointness are not validated

- **Where:**
  - `python/vera_timeline_agent/v2_package.py:497-534` and `workflow_v2.py:989-1000` check only that each role's track kind is video.
  - `_build_otio` (`v2_package.py:1883-1985`) stacks OTIO tracks in list order, not by index.
- **Trigger:** any of the following passes package, OTIO and native readback:
  - an overlay or child track whose index is at or below the root's;
  - the root ID also appearing in `childTrackIds`/`overlayTrackIds`;
  - tracks listed out of index order.
- **Impact:**
  - The native output can hide overlays or children under the root while reporting `verified`.
  - The OTIO stacking can disagree with native index order.
  - The plan's §7 assigns this check to P7 ("validates new lower-root/upper-child topology"), and plan §3.2 says preflight "rejects collisions/inadequate topology".
- **Smallest fix:**
  - In both validators, require root, children and overlays to be pairwise disjoint, with `root.index < min(child indices)` and `max(child) < min(overlay)`.
  - Emit OTIO video tracks in ascending index.
  - Add one refusal test with swapped root and overlay indices.

## Actual uncertainties (not counted as blocking)

1. **Child-track visual event kind.** `v2_package.py:565-569` refuses any `primary_visual` that is off the root track. If the compiler emits B-roll cutaways as `primary_visual` with `trackRole: "child"`, every cutaway package is refused. Confirm against `compiler-core-v2.ts` and the accepted golden; the accepted fixture only shows placeholder/overlay children.
2. **Slate placeholders.** `v2_package.py:590-602` and `:1289-1294` require `placeholder` events to carry a `still` treatment with a reference.
   - If intentional or undefined placeholders compile to `placeholder` events with a `slate` treatment, the builder refuses them.
   - In that case, the claim that "package preflight retains [slate] metadata" is true only for the hand-built `primary_visual` slate in `tests/test_workflow_v2.py:666-702`.
3. **Document content closure.** Only the self-declared `liveContentHash`, IDs and head sequence are compared (`v2_package.py:371-408`); document bytes and `textHash`/`settingsHash` are never recomputed. A first build accepts a document with altered content that keeps the same declared hash. If the canonical content-hash definition is reproducible in Python, this should become an AC1 refusal.
4. **44.1 kHz readiness is narrower than the tests suggest.**
   - `_source_audio_range` (`v2_package.py:1444-1447`) requires WAV-local offsets to land on exact timeline frames.
   - Real compiler ceil'd 44.1 kHz ranges will generally not, so they refuse. That is honest fail-closed behavior.
   - The 44.1 kHz test, however, uses a contrived aligned range. Document this as a known limitation pending #178.
5. **Parser differential.** `v2_package._load_json` is permissive: duplicate keys resolve last-wins and a BOM is accepted. `workflow_v2._strict_object` is strict, so the runtime fails closed at attest/load. Using the strict hook in both would remove the raw-versus-canonical ambiguity.
6. **Trust model.** The runtime and the `request` CLI trust the attestation file without rerunning `verify_v2_package`; runtime fixtures with a placeholder `timeline.otio` load successfully. This matches the accepted #109 model; I am noting it, not objecting to it.
7. **Cost.** `mutate` re-hashes the whole package before every event and marker (`workflow_v2.py:1532-1566`). This is correct, but potentially very slow for large media inside Resolve; #178 should measure it.
8. **Smaller fail-closed gaps.**
   - `_otio_track_kind` refuses `subtitle` tracks that the schema allows.
   - There is no test for 30000/1001 or other unsupported fractional rates, or for a view/manifest rate mismatch, at the runtime layer.

## Evidence and other notes

- **Evidence is reported accurately.**
  - FAST-R2: exit 0 with no skips (429 contract Vitest tests and 422 Python fast tests).
  - The R1 timeout disposition is reasonable and retained.
  - Focused counts (15 package, 15 Studio, 21 handoff) match the shown tests.
  - No full qualifying pass exists, and none is claimed.
  - The fixes above change source and tests, so fresh focused and fast runs, a delta review and the full gate are all required.
- **Not demanded as blocking:** absent real Studio qualification. Fractional rates, source audio, slate and cover/native framing correctly refuse before adapter creation and are deferred to #178.
- **Minor cleanups:**
  - the unused `value` parameter of `_receipt_identity` (`v2_package.py:2317`);
  - `del visual_source_ids` (`:813`);
  - the duplicated `packageStart` parse (`:1027-1035`);
  - before closure, update the README "not acceptance evidence yet" status.
