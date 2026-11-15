# Resolve Studio 21.2 compatibility investigation

Investigation: [#564](https://github.com/mbelinkie/vera-script-to-timeline/issues/564). Evidence reviewed 2026-11-14. **Status: partial native pass; broader compatibility remains incomplete.**

## Results first

A direct public-API probe in Resolve Studio **21.2.0.6** completed a positive four-frame roll, then saved, closed and reopened the project. All four original linked A/V item UIDs, the shared edit boundary, source/record geometry and selected properties persisted. An independent readback verifier matched each reopened item by UID to its post-roll state.

A temporary VERA candidate path also built and structurally verified a visual-only 240-frame timeline inside Resolve. The unmodified shipped CLI compiled, packaged and attested the same fixture, then failed to connect to the running versioned 21.2 application folder. It did not mutate a project and did not reach the build-identity gate. The product path, WAV/narration, Fusion behavior and fallback/version comparison remain incomplete.

These are distinct outcomes: the tested Resolve API roll passed; the test-only candidate build passed for one visual-only fixture; the currently shipped CLI still has an observed app-path routing blocker and a separate static 21.2 identity gate. No overall shipped 21.2 compatibility pass is asserted. The [API and release appendix](api-and-release-changes.md) contains the full documented method inventory and release summary.

## Scope and environment

This check compares the installed Studio versions for VERA’s native build/readback route and examines the offset API for an ordinary same-UID roll. #390 concerns Research snapshots; the roll history is in [#490](https://github.com/mbelinkie/vera-script-to-timeline/issues/490). Current [AGENTS.md](../../../AGENTS.md), the #520 save/close/reopen loop and [Resolve knowledge guide](../../RESOLVE_KNOWLEDGE_GUIDE.md) govern the live scope. No Producer projects or media, project migration, installation change or production allowlist update was part of this check. Live validation uses fresh synthetic targets, one Resolve job at a time, structural readback and stop-on-uncertain-write handling; render/audio comparisons and the retired Test Bench are outside scope.

The installed bundles report **21.1.1 build 21.1.10010** and **21.2.0 build 21.2.00006**. The Mac is Intel MacBookPro16,1. Blackmagic’s [21.1.1 ReadMe](https://www.blackmagicdesign.com/support/content/readme/dfbb6e4233c144d1b328c109c7ebc11e) and [21.2 ReadMe](https://www.blackmagicdesign.com/support/content/readme/630fd2cb208a46df9493de661a76628a) both list an Apple Silicon based computer. This is a host-support limitation shared with the working 21.1.1 baseline, not a 21.2-only regression or automatic no-go. The results below measure actual behavior on this Mac, not vendor-supported operation.

The later install updated the shared scripting SDK folder under `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting`; a complete separate 21.1.1 stub/README/changelog is no longer installed. Historical evidence in [#477](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-477-native-roll-feasibility.md) and [#489](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-489-resolve-nongui-static-audit.md) shows the old stub lacked the 21.1.2 position/offset setters. Both versions ship Python 3.14; this began in 21.1. Python 2 was removed, and the current README says pip, Tk and IDLE are unsupported in the bundled interpreter. Detailed documented additions and the limit on a full symbol-by-symbol removal diff are in the appendix.

## VERA route and focused host checks

The shipped `workflow_delivery.SUPPORTED_IDENTITIES` allowlist contains only `{("21.1.0", "14"), ("21.1.1", "10")}`. Separately, `build_timeline_once._external_resolve()` probes a fixed standard application path, `/Applications/DaVinci Resolve/DaVinci Resolve.app`, and the shared system SDK; the CLI has no selected-app-path option. The running 21.2 instance was in its versioned install folder. This path mismatch caused the unmodified invocation to fail before the allowlist was reached. The allowlist remains a static second blocker for 21.2, not an observed runtime refusal from that invocation.

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
| Direct native roll | Resolve Studio 21.2.0.6, synthetic linked AV source, save/close/reopen | **Pass** for a positive four-frame roll, exact fixture and direct public-API route. This is not a VERA feature or proof of other roll directions/failure recovery. |
| Shipped VERA CLI | Unmodified CLI with live versioned 21.2 app | **Connection failed** at the fixed standard app path after compile/package/attestation. No mutation; identity allowlist was not reached. |
| Candidate VERA build | Temporary exact-path/identity candidate, visual-only 240-frame fixture | **Pass** through build and structural readback for this one fixture. Not shipped support, not a performance result. |
| Broader product cases | WAV/narration, Fusion, fallback and other project/media shapes | **Untested** on 21.2, as detailed below. |

## Direct 21.2 roll result

The direct probe connected to Resolve Studio **21.2.0.6** in an isolated Disk library and used a synthetic 24 fps AV file. It appended two linked 48-frame clips to one video and one audio track. Before editing, left item A was record `[0,48)` / source `[0,48)`; right item B was record `[48,96)` / source `[60,108)`.

The public API sequence was `B.SetLeftOffset(64, False, True)` followed by `A.SetRightOffset(68, False, True)`. The first call advanced B’s record/source start to 52/64, shortened it to 44 frames and left a four-frame gap. The second extended A’s source out and record end to 52. The final boundary was shared at frame 52, B’s source out remained 108, and timeline end remained frame 96. This observed intermediate gap means the pair is non-atomic; no partial-failure injection or rollback behavior was tested.

After save/close/reopen, all four original video/audio UIDs and reciprocal links remained. The reopened geometry matched the post-roll capture. Marker data, project/timeline UIDs, zero start timecode, ZoomX/ZoomY 1.25, audio volume -12 dB, and disabled/locked video-track state also persisted. The native probe took 10.1 seconds. A second verifier compared each reopened item by UID to the post-roll geometry and confirmed the retained transform and audio values; it exited 0 without relaunching Resolve.

Blackmagic’s Nov. 12 Developer Support reply DEV-12324 on #490 says the offset setters and position methods first appeared in 21.1.2, and offset arguments are absolute remaining handles, not deltas. Its positive-roll recipe is to shrink the right clip first with `R.SetLeftOffset(R.GetLeftOffset() + n)`, then extend the left clip with `L.SetRightOffset(L.GetRightOffset() - n)`. The measured call sequence followed that recipe. The vendor says the existing UIDs should persist and recommends save/reopen verification; this test supplies evidence for one positive 4-frame case. It does not establish all clip types, negative rolls or recovery from a partial write. #490 is closed/not planned; #564 authorizes this bounded capability check.

## VERA CLI attempts

The unmodified CLI ran against a genuine visual-only 240-frame synthetic fixture at `24000/1001`. Compiler, package and attestation stages passed in **7.08 seconds**. Attach then failed with `DaVinci Resolve Studio is not running or external scripting is unavailable.` The actual Resolve 21.2 instance was running from its versioned install folder, while VERA probed the standard app folder. No project was written. Because connection failed first, the 21.2 allowlist was not evaluated by this invocation.

The temporary candidate copy used the exact app path and 21.2 identity, and verified matching Fusion-script and module paths. After the temporary dependency setup noted above, preparation, media-needs, compile, package, attestation, connection, preflight, build, save/close/reopen and structural verification all passed. It built one visual event at `[0,240)` on a 1920×1080 timeline at `24000/1001`, or about 10.01 seconds. Resolve build/check took **9.39 seconds**; total time was **14.91 seconds**. This is a single warm, short run, not a speed claim. It is a candidate-only result and does not change the shipped allowlist or app discovery.

The normal product command shape is:

```sh
uv run --frozen python -m vera_timeline_agent.build_timeline_cli \
  --script <script-document.json> \
  --inputs <prepared-input-directory> \
  --output <new-version-specific-output-directory>
```

The unmodified command currently cannot select the versioned Resolve app. To test candidate behavior, the temporary copy supplied the selected app and exact identity; both are necessary to reach the native workflow. After any future shipped fix, compare it against this candidate result with a fresh target and the same fixture, then check save/close/reopen structure under #520’s short loop.

## Prior baseline and remaining coverage

Existing #533 evidence has a bounded 21.1.1 Studio build 10 pass for a **different** 10-frame picture-plus-narration fixture at `24000/1001`: 42.78 seconds total, 36.44 seconds in Resolve. This is useful prior evidence, but not a same-fixture 21.1.1 comparison against the new 240-frame visual case. A separate #520 short fixture is 24 fps and is not a default-rate substitute. The retained narration-plus-picture CLI fixture was unavailable, so WAV/narration product behavior remains untested on 21.2.

Also untested: the candidate’s Fusion/title operations; fallback on 21.1.1 after this comparison; negative-direction roll; changed/clamped handle limits; partial-failure recovery; other rates (25/29.97/30), VFR, source-audio topology, Free-edition import, arbitrary transitions/effects, manual-edit/readback/revision flows and broader project shapes. No render, audio comparison or listening check was made. The single short warm build result does not support a performance comparison.

## Conclusion

Resolve Studio 21.2.0.6 directly passed one same-UID positive roll and reopen check, and the isolated VERA candidate path passed one visual-only build and structural readback. The unmodified shipped CLI remains unable to discover/connect to the versioned app folder; its 21.2 identity admission is a separate static gate. These are actionable integration blockers, not evidence that the Resolve 21.2 engine failed. VERA does not yet have a shipped 21.2 compatibility pass. The next meaningful comparison is the same retained A/V/WAV fixture on both versions, plus the pending Fusion and 21.1.1 fallback checks, using the corrected app route and without changing production admission as part of this investigation.
