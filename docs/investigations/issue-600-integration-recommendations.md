# VERA #600 — "Hide black bars encoded in source media": integration design recommendations

**Scope.** I only read code; nothing was modified and Resolve was not opened. Worktree `vera-600-hide-baked-bars` at HEAD `00ba2a86` (draft PR #605).

**Sources read:** `AGENTS.md`, the spec slice in `docs/Script-to-Timeline Product Spec - Fable Rev2.md` (lines 1145–1169 and 2326), RK-49 in `docs/RESOLVE_KNOWLEDGE_GUIDE.md`, the draft files (`python/vera_timeline_agent/cropdetect.py`, `tests/test_cropdetect.py`, `tests/issue600_cropdetect_fixture.py`, `tests/test_issue600_cropdetect_fixture.py`, `scripts/issue600_native_prepare.py`, `scripts/issue600_native_proof.py`), and the code they connect to (compiler, contracts, package, adapter, media preparation).

**Issue text.** I had no shell, so I could not fetch issue #600 from GitHub. The product requirements below come from your brief and the spec paragraph at line 1165, which matches it.

**Labels.**
- **[V]** verified in code or recorded evidence
- **[A]** assumption or untested; needs a check
- **[P]** product choice for Matthew
- **⚠** unsafe assumption or impossibility

---

## 0. Recommendation in one paragraph

Follow the native image-motion pattern that already exists:

1. A frozen project setting.
2. The compiler emits only the per-event **intent**. When the setting is off, no field is emitted, so existing goldens stay byte-identical.
3. A **package-time detector** runs once on the exact delivered bytes and writes a hash-bound `encoded-bars.json`.
4. `_delivery_view` projects a pure, re-derivable decision (`apply` with zoom, or `skip` with reason) from that file.
5. The adapter applies `ZoomX`/`ZoomY` with Pan/Tilt 0 through the setter that was proven. It adds them to `expected_properties` so the existing reopen check verifies them.

For v1:
- **Video clips only.** Stills stay out of scope (§5).
- **Symmetric bars only**, so Pan/Tilt stay 0.
- **Source aspect must equal timeline aspect.** That is the only baseline proven so far.
- Every other case is skipped with a reason in the build output. The build never fails because of this feature.

---

## 1. Verified facts that shape the design

| # | Fact | Where |
|---|---|---|
| F1 | The compiler emits **no picture treatment for clips**. `mediaStillTreatment` returns `undefined` when `pictureKind === "clip"`, so a clip's `framingPolicy` never reaches the manifest. | `packages/contracts/src/compiler-core-v2.ts:1290` |
| F2 | ⚠ Research-clip occurrences **hard-code** `framingPolicy: "contain"`. Promoting a supporting picture *requires* a `framingPolicy`. So "`framingPolicy` is present" does **not** mean "the user chose framing". | `authoring-v2-research-snapshot.ts:164,182`; `authoring-v2-edits.ts:614` |
| F3 | Images with no `framingPolicy` resolve to `cover`. Every image gets the native Dynamic Zoom motion by default (D-0017). | `compiler-core-v2.ts:1293-1296`; `native_image_motion.py:32` |
| F4 | The manifest copies `authoringDefaults` verbatim, and the package checks equality with the dependencies. `settingsHash` is bound from the frozen submission through the dependencies to the document. | `v2_package.py:642-648, 703`; `build_submission_inputs.py:94-95` |
| F5 | The delivery view is **re-projected and compared for equality** during verification (`_delivery_view(..., validate=False)` must equal the stored view). Any decision stored in the view therefore has to come from a pure function of frozen inputs. | `v2_package.py:2770-2779` |
| F6 | Precedent: `_native_motion_for_event` binds the delivered hash, original hash, probe hashes, preparation binding, tool hash, `settingsHash` and ranges into `MotionBinding`, and refuses on anything stale. | `v2_package.py:2853-2972`; `native_image_motion.py:53-210` |
| F7 | Video clips are placed with `AppendToTimeline`. Today they get **no** properties: `expected_properties` is empty unless the item is source audio or a composed still. Anything added to `expected_properties` is read back after the set and again in `verify()` after reopen. | `workflow_v2.py:2454-2580` |
| F8 | The normal build sets only frame rate, resolution and sample rate. It **does not set** `timelineInputResMismatchBehavior`, so clips use Resolve's project default (only presenter code sets `scaleToFit`). | `studio_spike.py:1312-1320`; `presenter_source.py:205` |
| F9 | Preparation admits only progressive, 8-bit, **SAR 1:1**, SDR h264/hevc yuv420p with **no side data** (which excludes rotation matrices). `derived_cfr` keeps width, height, SAR and colour range, and requires `pts_origin == 0`. | `media_preparation.py:514-545, 1080-1101` |
| F10 | RK-49 #600: Studio 21.2.0.6 accepted `SetProperty("ZoomX"/"ZoomY")` on 320×180 clips in a 1920×1080 timeline. Readback held after reopen, still pixels matched, and the bar region got brighter. The check measured **fill only, not exact geometry**. Pan/Tilt stayed 0. | `RESOLVE_KNOWLEDGE_GUIDE.md:1276-1286`; `issue600_native_proof.py:343-346, 445-462` |
| F11 | The draft detector samples **3 windows of 0.5 s** (≈1.5 s total, whatever the used length). Settings: cropdetect `limit=24/255`, `round=2`, `reset=0`. It takes the union within a window, allows 2 px jitter, and requires symmetry on exactly one axis. Luma gate: `YAVG ≥ 18`. | `cropdetect.py:20-26, 339-377` |

### ⚠ Unsafe assumptions and impossibilities

- **U1 — The Resolve baseline is unproven for other aspect ratios.** 320×180 has the same aspect as 1920×1080, so fit, fill and crop give the *same* baseline. The proof therefore cannot show what `ZoomX` multiplies when the source aspect differs from the timeline. `crop_to_fill_transform` assumes a contain-fit baseline (`cropdetect.py:474`). For any other aspect this is **[A]** until proven: v1 must refuse it.
- **U2 — The default scaling mode is never checked.** F8: no code reads or asserts the project's input-scaling mode before relying on it.
- **U3 — Exact fill is not measured.** F10 checked that bars got brighter, not that the active edge lands on the frame edge. Over-zoom (cutting picture) would also pass that check.
- **U4 — The dark gate does almost nothing on TV-range media.** Limited-range black is Y=16, so `MIN_ACTIVE_MEAN_LUMA = 18` sits 2 code values above black. The `near_black` fixture (RGB 0x10 → Y≈30) is reported as `no_bars_detected`, not "too dark" (`test_issue600_cropdetect_fixture.py:58`). Dark-scene protection effectively rests on cropdetect's threshold of 24 alone.
- **U5 — The sample doesn't cover the used range.** Three 0.5 s windows cannot support "stable in the used range". Subtitles, logos or an aspect change between the windows would be zoomed away unnoticed.
- **U6 — Possible leftover bar sliver.** The union rect plus 2 px symmetry tolerance, with Pan forced to 0, can leave up to 2 source px of bar. At 320→1920 that is 12 output px.
- **U7 — Stills can't use temporal agreement.** A still has one frame, so "stable over time" is impossible. **[A]** FFmpeg cropdetect's `skip` option (believed to default to 2 initial frames in recent FFmpeg) would also yield **no** crop lines for a single frame; check with `ffmpeg -h filter=cropdetect` on the pinned tool.
- **U8 — Still motion composition is unproven.** No proof exists for combining a static zoom with native Dynamic Zoom. The image-motion lane is pinned to 21.1.1.10 and to the sizes {1000², 1600×900, 900×1600} (`native_image_motion.py:157,162`). Bar removal on moving stills is **impossible inside the current evidence**.
- **U9 — Spec tension.** The spec says "Do not stretch or silently crop sources" (`Product Spec:1147-1156`). Removing 2.39:1 bars crops about 26% of the picture width. Opt-in makes this allowed, but it must **not be silent** (§5, Q5).

---

## 2. (1) Setting, default and build freeze

- **Contract.** Add an optional `hideEncodedBars: boolean` to:
  - `contracts/authoring-project-settings-v1.schema.json`
  - `AuthoringDefaultsV2` in `contracts/compiler-dependencies-v2.schema.json`
  - the `timeline-manifest-v2` copy of `authoringDefaults`

  **Absent means off.** Write the field only when it is `true`. Older settings and their hashes stay unchanged, and so do all existing goldens (F4).
- **Freeze.** No new mechanism is needed. The submission already freezes `settingsJson` and `settingsDigest` (`project-builds/src/submission.ts:135`), and the package checks `manifest.authoringDefaults == dependencies.authoringDefaults`. Changing the setting later never rewrites an earlier build, as the spec requires at line 1153.
- **Regenerate** `packages/contracts/src/generated/contracts-v2.ts` and `python/vera_timeline_agent/generated/contracts/*_schema.py` with the repo's generator.

## 3. (2) Detector stage

**Where it runs:** at package time, inside `_build_v2_package`, between `_media_artifacts(...)` and `_delivery_view(...)` (`v2_package.py:3994-3995`).

- The compiler (TypeScript, no FFmpeg) can't run it.
- The adapter shouldn't run it, because the decision must be frozen before any Resolve write.
- It must not run inside `_delivery_view`, because verification re-projects that function (F5).

**What it analyzes:** the **delivered derivative**, meaning the hash-verified bytes behind `artifact.origin` that Resolve will actually decode. It never touches the original.
- Geometry is identical by construction (F9).
- Re-encoding at CRF 18 can add ringing near bar edges; the purity rule in §7 tolerates this.
- Never write to or next to the source. The draft already treats media as read-only (`test_issue600...:59`).

**Used range and clock:** use the delivery-view event's `sourceRange` (`startFrame`, `durationFrames`) in **delivered-rate frames**, with the rate from `sourceTimeMapping.deliveredRate` (`_event_source_rate`, `v2_package.py:2994-3005`).
- For `derived_cfr`, `pts_origin == 0` is guaranteed [V].
- For passthrough, the origin may be non-zero.
- Use input `-ss = S / rate` (FFmpeg treats it relative to `start_time` **[A]**) and print each frame's `pts_time`.
- **Refuse** if the first analyzed frame's pts differs from `S / rate` by more than half a frame, or if the analyzed frame count doesn't match. One exact check is cheaper and safer than mapping the clock twice.

**Coverage:** analyze the **whole** used range at a stride of `k = max(1, round(rate / 6))` (about 6 fps), with per-frame rectangles (`reset=1`, `skip=0`). Downscaling is not allowed, since edges are needed to the pixel.

**Binding:** each record in `Builds/<buildId>/encoded-bars.json` holds:
- `eventId`, `sourceId`, `deliveredHash`, `deliveredProbeHash`, and the delivered `sourceRange`
- `detectorVersion` and a `thresholdsHash` over all the constants in §7
- `toolHash` (the `MediaTools.fingerprint()` identity already used by preparation)
- `colorRange` from the prep receipt, and `timelineSize`
- per-frame statistics digests
- the result: `activeRect`, or `refusal` with a reason code

List the file in the attestation `files` map like the other build files, so `load_verified_package_v2` checks its hash.

**Caching (optional):** key on `(deliveredHash, sourceRange, detectorVersion, thresholdsHash, toolHash)` in the existing `_MediaCacheSession`.

## 4. (3) Contracts, hashes, generated types, goldens, package verification

- **Compiler intent.** When `authoringDefaults.hideEncodedBars === true`, emit an optional event field `encodedBars: { mode: "detect_and_fill" }` on `primary_visual`/`overlay_visual` events where all of these hold:
  - `pictureKind === "clip"`
  - the event is not presenter or placeholder content
  - framing is not explicit (§5)

  Emit `encodedBars: { mode: "keep", reason: "explicit_framing" }` for clips with explicit framing, so the report can explain the skip. Omit the field entirely when the setting is off: this is the same omission rule `transitions` uses (`contracts-v2.ts:1654`).
- **Goldens.** Existing goldens stay byte-identical when the setting is absent. Add new compiler goldens under `tests/data/authoring_v2/issue_600/compiler/`: off, on+eligible, on+explicit, on+image (no field in v1), on+graphic/capture (no field). If the compiler `sourceHash` changes all goldens anyway, update them in the same PR, as `AGENTS.md` step 3 requires.
- **Independent check.** In `_validate_manifest_semantics` (`v2_package.py:749`), recompute eligibility from the document and the frozen setting, the same way image motion is checked. A self-consistent manifest must not be able to add or drop `encodedBars`.
- **Delivery view.**
  - Pass the parsed, hash-verified `encoded-bars.json` into `_delivery_view` and `_validate_delivery_view` as a new pure argument.
  - Add a per-event `barRemoval` key **only when the event carries `encodedBars`**, holding `{decision: "apply", zoom, pan: 0, tilt: 0, detectionHash}` or `{decision: "skip", reason}`.
  - `zoom` is computed by a pure function from `activeRect`, source size and timeline size, so re-projection reproduces it exactly.
  - Keep `VIEW_SCHEMA_VERSION` unchanged if the key stays optional and is omitted when unused. Update any per-event key-set check.
- **Verification refuses** when:
  - the detection's `deliveredHash`, range or `toolHash` differs from the event and source
  - `thresholdsHash` or `detectorVersion` isn't the one built into the code
  - an `apply` decision fails the geometry rules in §7
- **Should verification re-run FFmpeg?** **No.** That would be expensive, and it is equivalent to trusting the attested file. The image-motion precedent also trusts code-side checks of frozen evidence.

## 5. (4) Native setters, readback, save/reopen, refusal

- **Where.** In `PublicResolveAdapter.place_event` (`workflow_v2.py:2454`), when `event.get("barRemoval", {}).get("decision") == "apply"`:
  1. Call `assert_current_target()`.
  2. Use **`SetProperty("ZoomX", z)` and `SetProperty("ZoomY", z)` one at a time.** That is the proven call (`issue600_native_proof.py:447-450`). `SetProperties` on clips for Zoom is unproven [A].
  3. Read back immediately.
  4. Put `{"ZoomX": z, "ZoomY": z, "Pan": 0.0, "Tilt": 0.0}` into `expected_properties` so `verify()` re-checks them after reopen (F7).
- **Precision.** Round the zoom **up** to 4 decimals, so a sub-pixel bar never survives rounding. The readback tolerance of 1e-6 has been observed [V].
- **Preflight before any timeline write** (U2), following the pattern of RK-49's app-selection refusal. Downgrade every `apply` to a skip with reason `route_unproven` unless all of these hold:
  - the app is `DaVinci Resolve Studio` 21.2.0.6 (the only version with this proof; 21.1.1 has a scripted 1.2 zoom surviving reopen in RK-50, but no bar-fill proof)
  - `timelineInputResMismatchBehavior` reads `scaleToFit` **[A: the default value and its exact string need one read on 21.2]**
  - the item's `Scaling` property reads "project default" or fit
  - the source aspect equals the timeline aspect within 0.5% (U1)
- **Partial skips.** Decide all of this before creating the timeline, so a run never ends half-applied.
- **Reporting.** Record per-event outcomes (`applied z`, `kept: reason`) in the build result and the row map. Applied zoom stays editable as an ordinary Inspector value.
- **⚠ Update and observe paths.** Check that the #104 update and observe code (`roundtrip_native.py`, `presenter_conform.py`) treat a user-changed `ZoomX` on a bar-filled clip as hand finishing, not drift. They must never re-apply the frozen zoom over a user's edit. A take or source swap must not inherit an old decision silently: v1 should keep the new item at zoom 1 and report it.
- **Draft scripts.** `scripts/issue600_native_*.py` are one-use proofs. Either don't merge them, or label them as evidence-only, so they don't become product paths.

## 6. (5) Explicit framing, stills, motion precedence, open product choices

**Precedence (highest wins):**
1. A user's later Resolve edit
2. Explicit occurrence framing
3. Presenter framing (`presenter_framing.py` owns its own ZoomX; exclude it)
4. Bar removal
5. The default fit

**What counts as "explicit" for clips today:** only `cover` or `native`. `contain` cannot mean explicit, because the system writes it automatically (F2). Treating `contain` as explicit would turn the feature off for every research clip. A true "keep bars on this clip" override needs a new optional per-payload field. That changes the authoring contract, so it is a product decision (Q2).

**Exclude from v1:** `capture` (dark-mode web pages have dark margins), `graphic` (black edges there are intentional), slates and placeholders.

**Stills.**
- **Moving stills** (the default for images): skip with reason `motion_route_unproven` (U8). Folding the bar zoom into the Dynamic Zoom endpoints would need a new native image-motion qualification.
- **Static stills** (`imageMotion: {mode: "none"}`): a static Zoom on a still has not been proven (RK-49 explicitly excludes stills). The detection would also have to rely on single-frame purity rules only (U7). Recommend phase 2, after a dedicated still proof.
- **Consequence ⚠:** "picture assets include stills" can't be delivered in v1 without a new proof. Say so plainly in the PR and to Matthew.

**Open product choices [P]** — batched for Matthew, each with a recommendation:

| Q | Question | Recommended answer |
|---|---|---|
| Q1 | Images with automatic zoom: hide bars too? | Not yet. Bars stay and the build says why. Revisit after a still proof. |
| Q2 | How does someone keep bars on one clip? | Add a per-clip "Keep black bars" toggle. Until then, only Cover/Native framing opts out. |
| Q3 | Maximum zoom? | Cap at 1.40×. This covers 2.39:1 and 4:3 inside 16:9. Vertical phone video in a 16:9 file (≈3.2×) keeps its bars. |
| Q4 | Subtitles or logos in the bar area? | Keep the bars. Never cut text. |
| Q5 | How visible are results? | Show one line per clip in the build summary: "bars hidden (1.33×)" or "bars kept: changing / too dark / …". |
| Q6 | Where is the switch? | Project settings, "Hide black bars in footage", off by default. |

## 7. (6) False detections and a conservative confidence rule

**Known ways cropdetect gets it wrong:**
- dark scenes with dark top and bottom (night sky, dark floor)
- a subject on a black background, which looks like pillarboxing
- fades to black and black frames
- burned-in subtitles or a logo inside a bar, which makes the result asymmetric or changing
- windowboxed or inset graphics
- the aspect ratio changing mid-clip
- full-range sources, where black is 0 rather than 16
- odd bar sizes trimmed by `round=2`
- unparseable or negative crop lines, which `_CROP_RE` silently drops (`cropdetect.py:26, 370`)

**Rule.** Accept only if **all** of R1–R8 pass; otherwise refuse with the first failing reason. All constants go into `thresholdsHash`. The starting values are **[A]** and must be calibrated on the slow fixtures in §8.

- **R1 Eligibility.** The event has `encodedBars.mode == detect_and_fill`. The source is video with SAR 1:1 (from the prep receipt).
- **R2 Coverage.** Analyze the whole used range at stride `k` (§3). Require at least 12 analyzed frames, and parsed crop lines equal to analyzed frames. Otherwise refuse with `insufficient_evidence`.
- **R3 Informative frames.** A frame is informative when the mean Y of its candidate active region is at least black + 24 (tv: 40, pc: 24). Require at least 80% of frames to be informative. Otherwise refuse with `too_dark`. This replaces the near-no-op gate of 18 (U4).
- **R4 Stability.** *Every* informative frame's rect stays within 2 px of the median rect on all four edges. A single intrusion refuses with `changing`. This covers subtitles, logos and aspect changes, and makes the result "stable in the used range" (U5).
- **R5 Bar purity.** This is the main defence against dark content. Over *all* analyzed frames, inside the bar region minus a 2 px guard band at the active edge:
  - max Y ≤ black + 8 (tv: 24, pc: 8)
  - per-frame Y standard deviation ≤ 1.5

  Encoded bars are flat. Dark real scenes have grain or noise. Failure refuses with `not_flat_black`.
- **R6 Geometry.**
  - Bars on exactly one axis.
  - Symmetric within max(2 px, 0.5% of that dimension).
  - Each bar at least max(4 px, 1% of that dimension).
  - The active rect covers at least 50% of each dimension (kept from the draft).
- **R7 Aspect sanity.** The active aspect is within 1.5% of a standard ratio: {2.39, 2.35, 2.20, 2.00, 1.85, 1.78, 1.66, 1.50, 1.33, 1.25}. The zoom is ≤ 1.40 (Q3). Otherwise refuse with `nonstandard_aspect` or `zoom_exceeds_limit`.
- **R8 Route.** The source aspect equals the timeline aspect (U1). Otherwise skip with `route_unproven`.

**Zoom.** Size the zoom so the **larger** bar on that axis is hidden with Pan = 0:
`zoom = D / (D − 2·max(b₁, b₂))`, then round up (U6).
This trades at most about 2 source px of picture for zero visible bar. That is the right direction for a feature whose purpose is hiding bars.

**Remaining limits:** no rule set can tell real bars apart from:
- an intentional flat digital-black matte that runs edge to edge on one axis
- archival footage that was already composited onto pure digital black

Those cases will be zoomed. The report line and the editable Inspector zoom are the mitigation.

## 8. (7) Focused tests

**Offline, fast (no FFmpeg):**
- `tests/test_cropdetect.py` and a new `test_encoded_bars_rule.py`: R2–R8 using synthetic per-frame statistics, including the TV vs PC black levels, jitter at exactly 2 and at 3 px, the 1.40 cap, the round-up zoom, and odd bar sizes.
- Contract and schema tests for the optional field.
- Compiler goldens: off (existing goldens unchanged), on+eligible, on+`cover`/`native` (keep), research `contain` (eligible), image, graphic and capture (no field).
- `test_v2_package.py`:
  - a tampered `encoded-bars.json`
  - mismatched hash, range, tool or threshold → refusal
  - delivery-view re-projection equality with `barRemoval`
  - an apply decision that breaks geometry → refusal
- Adapter with a fake Resolve:
  - the apply path uses `SetProperty` and adds the values to `expected_properties`
  - preflight downgrades on an unqualified version, scaling mode or aspect, *before* any write

**Slow, FFmpeg (`@pytest.mark.slow`):** extend `tests/issue600_cropdetect_fixture.py` with real H.264 at 1920×1080:
- positive: 2.39 letterbox and 4:3 pillarbox
- refusals: asymmetric bars, near-black with Y 17–22, a grainy dark scene with dark top and bottom, subtitles appearing in a bar mid-range, an aspect change inside the used range, a fade to black
- an aspect change *outside* the used range → accept
- 9:16 pillarbox → zoom cap
- a PC-range source, odd 21 px bars, and a passthrough source with non-zero `pts_origin` (clock check)
- a still PNG, which must be refused or skipped in v1

**Native (one #520 save/close/reopen loop, under 5 minutes, one Resolve job):** one normal-CLI build with the setting on, six clips:

| Case | Expectation |
|---|---|
| (a) letterbox 2.39 | applied |
| (b) pillarbox 4:3 | applied |
| (c) same media with `cover` framing | `ZoomX = 1` |
| (d) changing | skipped with reason, `ZoomX = 1` |
| (e) dark | skipped with reason, `ZoomX = 1` |
| (f) no bars | `ZoomX = 1` |

Check that `ZoomX/Y/Pan/Tilt` read back after reopen. On (a) and (b), also check the **geometry** in one exported still per clip: the first and last non-black row or column is within 1 px of the frame edge, which closes U3.

Also build the same project with the setting off and confirm the manifest and view bytes are identical.

Before trusting U2, add a one-line read of `timelineInputResMismatchBehavior` to that run.

**Suggested order:**
1. Detector rule and slow fixtures. This rewrites the current draft's sampling.
2. Setting, compiler intent and goldens.
3. Package freeze and verification.
4. Adapter apply and preflight.
5. The single native check, then a short RK-49 update.

Stills and non-matching aspect routes stay out until Matthew answers Q1 and Q3 and a separate proof exists.
