# Resolve Studio 21.2 compatibility investigation

Evidence reviewed November 14, 2026. [Investigation #564](https://github.com/mbelinkie/vera-script-to-timeline/issues/564)

## What passed and what blocks adoption

Resolve Studio **21.2.0.6** passed four-frame scripted rolls in both directions on linked video and audio, and a four-frame forward roll on two generated PNG stills. All three edits survived save, close and reopen with the original clip IDs, correct source and record geometry, and the expected cut and timeline end.

A temporary VERA candidate path built and structurally verified the same picture-only and picture-plus-narration timelines on both versions at 23.976 fps. Switching the running app back to 21.1.1 and using the older bundle's scripting library also worked. The unmodified CLI compiled, packaged and attested the picture fixture, then failed to connect to the running versioned 21.2 application folder before it could check the build identity.

These are distinct outcomes: the tested Resolve API roll passed; the test-only candidate build passed for one visual-only fixture; the currently shipped CLI still has an observed app-path routing blocker and a separate static 21.2 identity gate. No overall shipped 21.2 compatibility pass is asserted. The [API and release appendix](api-and-release-changes.md) contains the full documented method inventory and release summary.

## Scope and environment

This check compares the installed Studio versions for VERA’s native build/readback route and examines the offset API for an ordinary same-UID roll. #390 concerns Research snapshots; the roll history is in [#490](https://github.com/mbelinkie/vera-script-to-timeline/issues/490). Current [AGENTS.md](../../../AGENTS.md), the #520 save/close/reopen loop and [Resolve knowledge guide](../../RESOLVE_KNOWLEDGE_GUIDE.md) govern the live scope. No Producer projects or media, project migration, installation change or production allowlist update was part of this check. Live validation uses fresh synthetic targets, one Resolve job at a time, structural readback and stop-on-uncertain-write handling; render/audio comparisons and the retired Test Bench are outside scope.

The installed bundles report **21.1.1 build 21.1.10010** and **21.2.0 build 21.2.00006**. The Mac is Intel MacBookPro16,1. Blackmagic’s [21.1.1 ReadMe](https://www.blackmagicdesign.com/support/content/readme/dfbb6e4233c144d1b328c109c7ebc11e) and [21.2 ReadMe](https://www.blackmagicdesign.com/support/content/readme/630fd2cb208a46df9493de661a76628a) both list an Apple Silicon based computer. This is a host-support limitation shared with the working 21.1.1 baseline, not a 21.2-only regression or automatic no-go. The results below measure actual behavior on this Mac, not vendor-supported operation.

The later install updated the shared scripting SDK folder under `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting`; a complete separate 21.1.1 stub/README/changelog is no longer installed. Historical evidence in [#477](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-477-native-roll-feasibility.md) and [#489](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-489-resolve-nongui-static-audit.md) shows the old stub lacked the 21.1.2 position/offset setters. Both versions ship Python 3.14; this began in 21.1. Python 2 was removed, and the current README says pip, Tk and IDLE are unsupported in the bundled interpreter. Detailed documented additions and the limit on a full symbol-by-symbol removal diff are in the appendix.

## VERA route and focused host checks

The shipped `workflow_delivery.SUPPORTED_IDENTITIES` allowlist contains only `{("21.1.0", "14"), ("21.1.1", "10")}`. Separately, `build_timeline_once._external_resolve()` probes a fixed standard application path, `/Applications/DaVinci Resolve/DaVinci Resolve.app`, and the shared system SDK; the CLI has no selected-app-path option. The running 21.2 instance was in its versioned install folder. This path mismatch caused the unmodified invocation to fail before the allowlist was reached. The allowlist remains a static second blocker for 21.2, not an observed runtime refusal from that invocation.

Two existing feature guards in `workflow_v2.py` independently require 21.1.1 build 10. One applies to whole-timeline OTIO, which VERA uses for native image motion and row-spanning music. The other applies to native Cross Dissolve. The fixtures use none of these features. Adding 21.2 to the general identity list would still leave these routes blocked until they are qualified separately.

App selection and exact build admission are tracked in [#566](https://github.com/mbelinkie/vera-script-to-timeline/issues/566).

The temporary candidate copy changed only app selection and exact identity admission for 21.2 (`21.2.0`, build `6`), with the matching Fusion script and scripting module paths verified. It did not change other workflow guards or shipped files. A temporary `node_modules` symlink was required after the first candidate attempt lacked `ajv`; that was test-copy setup, not a Resolve failure. Candidate success is evidence for that exact test path, not current shipped support.

Focused automated checks ran at baseline commit `fb280574` from the dedicated worktree:

```sh
uv run --frozen pytest \
  tests/test_resolve_import_package.py tests/test_otio_package.py \
  tests/test_build_studio_stage.py tests/test_studio_assembly.py \
  tests/test_workflow_v2.py tests/test_studio_graphics_workflow.py \
  tests/test_readback_timeline_cli.py tests/test_issue507_studio_parent.py \
  tests/test_issue477_sdk_inventory.py tests/test_issue489_static_resolve_audit.py \
  tests/test_check_timeline_speed.py tests/test_issue520_long_fixture.py
```

Result: **321 passed in 29.56 seconds**, Python 3.12.14 / pytest 9.1.1, with no skips or failures. These synthetic, package and static checks cover VERA contracts, guards, SDK inventory and the #520 runner. They do not test Resolve.

## Evidence matrix

| Boundary | Evidence | Status and limit |
| --- | --- | --- |
| 21.2 scripting changes | Installed 21.2 SDK plus retained 21.1.1 findings | **Declared.** 21.1.2 added per-edge offsets/position, effects, photo, selective copy, frame and audio APIs; 21.2 added Extras, contact sheets, auto-color and color readback. Signatures are in the appendix; declarations alone do not prove behavior. |
| Direct native roll | Resolve Studio 21.2.0.6, synthetic linked AV source, save/close/reopen | **Pass** for four-frame rolls in both directions. The two setters leave an intermediate gap, and failure recovery remains unverified. |
| Still roll | Two generated one-frame PNGs on 21.2, each held for 48 frames | **Pass.** A positive four-frame roll preserved the IDs, changed the cut to frame 52 and left the timeline at 96 frames after reopen. |
| Shipped VERA CLI | Unmodified CLI with live versioned 21.2 app | **Connection failed** at the fixed standard app path after compile/package/attestation. No mutation; identity allowlist was not reached. |
| Candidate VERA build and old-version fallback | Same 240-frame picture fixture, exact app path on each version, exact 21.2 identity added in the temporary copy | **Pass on both** through build and structural readback. 21.1.1 still launches and builds after 21.2 runs. |
| Narration and picture together | Same 96-frame fixture with a WAV, primary picture and overlay picture | **Pass on both** through package, placement, save, reopen and structural verification. |
| Open old project in 21.2 | Disposable 21.1.1-built narration project | **Pass.** 21.2 loaded the project and read back the expected geometry and tracks. It was closed without saving. |
| WAV gain and fades | Direct 21.2 API on a 47-frame audio item from a stereo 48 kHz PCM WAV | **Pass.** Gain, fades, geometry and clip IDs persisted after reopen. |
| Direct Fusion graph persistence | Same Text+ composition on a video clip, with Text+ connected to MediaOut | **Shared failure.** Both reopened clips kept their IDs and geometry and reported zero compositions. |
| Pinned VERA Text+ template | Checked-in template preflight on 21.2 | **Blocked before import.** The bundle is 21.2.00006 and the local package receipt identifies 21.0.4. |
| Feature-specific gates | Native OTIO image motion and row-spanning music, native Cross Dissolve | **Blocked by current VERA code** on 21.2. These are separate from the general build allowlist. |

## Direct 21.2 roll result

The direct probe connected to Resolve Studio **21.2.0.6** in an isolated Disk library and used a synthetic 24 fps AV file. It appended two linked 48-frame clips to one video and one audio track. Before editing, left item A was record `[0,48)` / source `[0,48)`; right item B was record `[48,96)` / source `[60,108)`.

The public API sequence was `B.SetLeftOffset(64, False, True)` followed by `A.SetRightOffset(68, False, True)`. The first call advanced B’s record/source start to 52/64, shortened it to 44 frames and left a four-frame gap. The second extended A’s source out and record end to 52. The final boundary was shared at frame 52, B’s source out remained 108, and timeline end remained frame 96. This observed intermediate gap means the pair is non-atomic; no partial-failure injection or rollback behavior was tested.

After save/close/reopen, all four original video/audio UIDs and reciprocal links remained. The reopened geometry matched the post-roll capture. Marker data, project/timeline UIDs, zero start timecode, ZoomX/ZoomY 1.25, audio volume -12 dB, and disabled/locked video-track state also persisted. The native probe took 10.1 seconds. A second verifier compared each reopened item by UID to the post-roll geometry and confirmed the retained transform and audio values; it exited 0 without relaunching Resolve.

Blackmagic’s Nov. 12 Developer Support reply DEV-12324 says the offset setters and position methods first appeared in 21.1.2. The setters take absolute remaining handles. For a four-frame roll to the right the probe increased the right clip's left offset by four, then decreased the left clip's right offset by four. The vendor suggested that order and recommended checking clip identity after save/reopen. [Blackmagic reply on #490](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215)

A fresh linked AV project also passed the reverse direction on 21.2. The left clip shrank first with `A.SetRightOffset(76, False, True)`. The right clip extended left with `B.SetLeftOffset(56, False, True)`. The cut moved from 48 to 44, B’s source-in moved from 60 to 56, the timeline end stayed at 96, and both audio clips followed their video peers. All four IDs, ranges and reciprocal links survived reopen.

The same shrink-first sequence also passed on two generated PNG stills in a separate 21.2 project. Before the edit, their held occurrences were `[0,48)` and `[48,96)`. They exposed a right handle of 1,352,201 frames on the left item and a left handle of 86,313 frames on the right item. After the roll, the occurrences were `[0,52)` and `[52,96)`, with stable IDs after reopen. A setup assertion had initially assumed inclusive end frames. The corrected check used reported duration and confirmed the exclusive boundary for this fixture. The result covers these two held PNGs. The stricter historical requirement to hold the right clip's original source-in fixed is a different edit.

## VERA CLI attempts

The unmodified CLI ran against a genuine visual-only 240-frame synthetic fixture at `24000/1001`. Compiler, package and attestation stages passed in **7.08 seconds**. Attach then failed with `DaVinci Resolve Studio is not running or external scripting is unavailable.` The actual Resolve 21.2 instance was running from its versioned install folder, while VERA probed the standard app folder. No project was written. Because connection failed first, the 21.2 allowlist was not evaluated by this invocation.

The temporary candidate copy used the exact app path and 21.2 identity, and verified matching Fusion-script and module paths. After the temporary dependency setup noted above, preparation, media-needs, compile, package, attestation, connection, preflight, build, save/close/reopen and structural verification all passed. It built one visual event at `[0,240)` on a 1920×1080 timeline at `24000/1001`, or about 10.01 seconds. Resolve build/check took **9.39 seconds**; total time was **14.91 seconds**. This is a single warm, short run, not a speed claim. It is a candidate-only result and does not change the shipped allowlist or app discovery.

The same fixture passed the identical build and reopen checks on **21.1.1 build 10** after 21.2 exited. The temporary copy pointed to the older bundle and used its already admitted identity. Both reopened projects had one visual event with record and source ranges `[0,240)`, 1920×1080 geometry, and exact `24000/1001` timing. The older run took **22.17 seconds** for Resolve build/check and **31.49 seconds** total. Its first attempt stopped safely on the Media page because preflight requires a timeline page. Opening Edit permitted the fresh run. These single runs measure workflow completion and do not establish a version speed difference.

A second fixture added a generated mono PCM WAV with synthetic speech to a primary and an overlay picture event. The 48 kHz WAV contains 192,000 samples (4.000 seconds), while 96 frames at `24000/1001` span 4.004 seconds. This exercises VERA's distinction between the source audio end and the timeline frame boundary. VERA compiled and verified the package. On **21.1.1 build 10**, the candidate built and reopened the 96-frame timeline, with one narration item and two picture items all at `[0,96)`. Build plus check took **9.16 seconds**, including **1.95 seconds** for save/reopen, with **15.40 seconds** total.

**21.2.0 build 6** passed the same fixture. The independent reopened row maps agreed on timing, kind, track and source frame fields once the newly generated Resolve IDs were excluded. Audio was on track 1 and the pictures were on video tracks 1 and 5. Build plus check took **38.55 seconds**, including **4.65 seconds** for save/reopen, with **60.97 seconds** total. The older version took longer on the picture-only run, and the newer version took longer on this one. These runs did not control startup, cache or machine load enough to rank performance.

21.2 also opened the synthetic narration project previously built in 21.1.1. It read back the same 1920×1080, 96-frame layout at 23.976 fps and the same audio and picture placements. The agent closed that project without saving. This covers opening the old project in the new app. Opening a 21.2-saved project in 21.1.1 remains unverified.

## Direct WAV and Fusion checks

In a separate 21.2 project at 23.976 fps, the API appended a picture clip and a stereo 48 kHz PCM WAV, both 47 frames long. The saved and reopened WAV kept its `-12 dB` gain and four-frame fades at both ends. Source and record readbacks and both clip IDs persisted. The setup initially combined page selection with seeking on an empty timeline, then expected 48 frames from an append range that yielded 47. The final checks used the observed geometry of the inspected synthetic target.

In the same project, the Fusion API accepted a new composition and read back its Text+ input before save. On reopen, the same video clip reported zero compositions. The first probe had left Text+ disconnected. A fresh 21.2 project repeated the check with Text+ explicitly connected to MediaOut, and verified the connection and text before save. On reopen, the clip kept its ID and geometry and again reported zero compositions. The 21.2 logging script raised a key error after it recorded the reopened count and clip identity. The matching 21.1.1 probe corrected that reporting error and also read back zero compositions from the same clip after reopen. This is a shared failure of this direct API test. VERA's pinned Fusion templates use separate delivery steps.

The pinned VERA Text+ template check reached a read-only preflight. It stopped on the mismatch between the selected 21.2.00006 bundle and the machine's ManifestLite package receipt for 21.0.4. The preflight stopped before importing the SDK or changing a project, so the template's placement and persistence on 21.2 remain unverified.

The normal product command shape is:

```sh
uv run --frozen python -m vera_timeline_agent.build_timeline_cli \
  --script <script-document.json> \
  --inputs <prepared-input-directory> \
  --output <new-version-specific-output-directory>
```

The unmodified command currently cannot select the versioned Resolve app. The temporary copy supplied the selected app and the exact tested identity. After a shipped fix, repeat the same fixture with the unmodified command.

## Repeatable test process

1. Confirm the exact app bundle, API-reported edition and build, and selected disposable disk library. Launch one version at a time and use the scripting library from that app bundle. Confirm the other version can still launch independently.
2. Give both versions identical prepared synthetic inputs and fresh output directories. Start with a picture and PCM WAV at VERA’s default `24000/1001` timeline rate. Keep a picture-only sample for isolating media failures. Record any changes needed just to reach the existing product workflow.
3. Run the build command above. Compare reopened frame rate, raster, row placement, source clocks, markers and track structure. Compare clip IDs against each project's own pre-close capture. Independently built projects receive distinct IDs. Keep preparation time separate from the native build and verification time.
4. Use a separate 24 fps timeline for the roll. Start with two adjacent linked AV pairs and known handles, confirm adjacency using start plus duration, then apply the two offset calls. Enumerate actual audio and video track items since the append result can omit the audio peers. Compare record and source boundaries, total extent, links, IDs, markers and properties both immediately and after reopening. Give stills their own case since they expose different handle limits.
5. Test a WAV-only clip and a small Fusion graph on disposable timelines to isolate native behavior from compilation. Reopen and read back the audio placement, gain, fades, tool graph and input values. Repeat an established pinned template separately if the product change depends on it.
6. Stop on an uncertain write and inspect the target before repeating any operation. Use only synthetic projects for cross-version reopen checks. Before adopting 21.2 for VERA, require the shipped CLI to connect and pass the mixed fixture, and keep the 21.1.1 fallback usable.

## Prior baseline and remaining coverage

The original prepared inputs from #533 were unavailable locally. The new tests compared both versions using the same generated inputs.

Still to verify: pinned Text+ delivery after resolving the receipt mismatch, EV24, other still or placeholder types, changed/clamped roll handle limits, partial-failure recovery, rates beyond 24 and 23.976, VFR, Free-edition import, broader source-audio and project topologies, arbitrary transitions/effects, and VERA's manual-edit/readback/revision flows. The live checks read project structure and properties after reopen.

## Conclusion

The two build fixtures and the roll tests support proceeding with the targeted VERA routing fix. The shipped CLI still needs app selection and exact build admission. Native image motion, row-spanning music, Cross Dissolve and the pinned text template need separate checks. An automatic roll workflow needs a reliable way to detect and handle failure after the first setter.

All live writes used the disposable disk library and synthetic media. The original Local Database was reselected with its empty Untitled Project before shutdown. One 21.1.1 shutdown hung after Resolve acknowledged the quit request, so the agent stopped that empty app and its crash reporter after verifying the selected library and project. The final 21.2 shutdown succeeded, and both apps were confirmed closed.
