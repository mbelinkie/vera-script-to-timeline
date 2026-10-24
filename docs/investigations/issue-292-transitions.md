# #292 — installed picture-transition capability proof

Status: paused at the Producer's request, 2026-10-24. Resume only when he
returns and requests continuation. This document does not clear the transition
capability hold on #125 or #61. PR #295 is a checkpoint, not completed evidence.

## Boundaries

This issue tests installed inventory/control discovery and precise declared
picture-transition execution together. It adds no production chooser or engine.
Only issue-owned disposable synthetic fixtures may be mutated. Existing
Producer projects, media and plugins are preserved.

The live issue's current product intent supersedes the old §8.5 default-policy
assumptions: new visual boundaries start as cuts, effects are explicitly added,
and installed effects must not be silently replaced or reduced to a fixed trio.

## Initial observations

- Baseline: `origin/main` at `cc9566672f4d9b97b484cf651b479a5e7044f94e`.
- Connector reports Resolve 21.1.1 installed and not running before probes.
- Connector metadata advertises `TimelineItem.AddTransition` with
  simple/fusion/ofx/audio categories. This is a lead, not runtime evidence.
- Installed official Scripting README (last updated 31 Aug 2026) has no
  `Transition` match. Runtime and alternative routes still need checking.
- Installed official Fusion Templates README documents transition macros,
  exposed controls, template paths and a restart to refresh templates.
- Current portable import-package verifier rejects OTIO transition items;
  existing cut-only acceptance is not transition acceptance.

## Real-runtime checkpoint

Runtime is DaVinci Resolve Studio **21.1.1 build 10**, macOS Intel. External
scripting initially was disabled. The Producer enabled **Local** scripting.
The connector and direct official Python module then connected successfully.
No global Resolve lease command was found; the issue comment records sole
operation after checking inactive peers and completed #145 work. This task has
stopped driving Resolve and is not reserving an active render slot while paused.

All mutations were in disposable `VERA292Probe20261024A`, using generated
640×360/24 fps red/blue picture and 48 kHz synthetic tone, under
`~/.local/share/vera/issue-292-transition-proof`. No Producer media was used.
The Producer separately authorized installing a transition. The new fixture is
`VERA292 Curve Dissolve.setting`, retained alongside this document and installed
in the user Fusion `Templates/Edit/Transitions` folder. Existing transitions
were preserved. No paid service, plugin purchase or third-party install occurred.

Observed results (not universal certification):

| Capability | Observed result |
|---|---|
| Direct native application | `AddTransition` works for Cross Dissolve, Edge Wipe and Push. Native Cross Dissolve rendered. |
| Native duration/alignment | With genuinely adjacent clips, 24 frames yielded left `[48,72)`, center `[60,84)`, right `[72,96)`. |
| Fixture range convention | On this build, AppendToTimeline source `24..96` produces 72 frames. Initial `24..95` attempts left a one-frame gap and gave misleading 2-frame results; those attempts are not positive evidence. |
| Fusion application | Bundled Slide Left, bundled Cross Dissolve and the newly installed custom transition all applied at `[60,84)`, with one accessible Fusion comp. The custom transition rendered. |
| Custom controls | Actual `GetInputList` metadata exposes Curve (`Linear/Easing/Custom`) and EaseIn/EaseOut enum IDs. `SetInput` followed by `GetInput` worked. This is a bounded representative, not exhaustive Inspector coverage. |
| Persistence | Initial native/custom 24-frame transitions retained names, spans, occurrence IDs, narration ranges, markers and custom values across save/close/load. |
| Subsequent update | Both were changed to 12 frames `[66,78)`; custom Curve=Easing, EaseIn=Quad, EaseOut=None. Rendered output changed consistently with the requests. Updated-state reopen is still outstanding. |
| Picture output | Initial renders contain red → mixed red/blue → blue frames. Updated custom output has the expected slower early blend for quadratic easing. Movies are 144 frames/6 seconds. |
| Narration | Video ranges `[0,72)` and `[72,144)`, audio `[0,144)`, marker at frame72 stayed unchanged. Decoded rendered audio is byte-identical for cut-only, native24, custom24, native12 and custom12. It is not byte-identical to the mono source after the project's normal output routing, so the cut-only comparison is the relevant control. |
| Zero handles | Raw API refused; no transition, clip/audio range or anchor movement. |
| Short handles | Two handles on each side silently shortened a requested24 to an actual2-frame transition. This is a failed precise request, not success. |
| Neighbor move | Incoming moved from72 to78 (six-frame gap); raw API created12 frames for requested24. Clips/audio/anchor stayed put. Preflight must refuse gaps and short handles. |
| Native control API | Transition GetProperties/GetProperty return `{}` / false for tested controls; SetProperties Direction/duration/Alignment returned false. This does not prove all possible import/private routes impossible. |
| Export/readback limits | Native OTIO export includes type, offsets and limited curve metadata. Fusion OTIO export omits the graph/controls. FCPXML and DRT exported, but their precise transition import/control routes have not been qualified. The production portable verifier remains unchanged and rejects OTIO transitions. |

Discovery is **not proved complete**. The bundled Templates.drfx contains67
transition settings; the user-authorized custom fixture adds one loose setting.
The existing third-party sample DRFX has titles and zero transition settings.
An installed 3D LUT Creator OFX filter is visible in Fusion registry metadata;
it is not evidence of a third-party transition. No installed third-party picture
transition representative has been qualified.

`Fusion.GetRegList(0)` returned1454 registry entries. It did not include exact
names Cross Dissolve, Slide Left or VERA292; generic DFTDissolve and DFTWipe
operators are not the Edit Effects Library catalog. The real Effects Library
showed native Dissolve/Iris categories and native controls absent from scripting
properties. Its item names were not exposed through the tested accessibility
tree. Native and Fusion Cross Dissolve share a display name and both apply;
name alone is therefore insufficient identity. Source-path/hash and native
build/category/name are bounded matching hints, not official universal IDs.

Web leads were checked against runtime, including the contributor's firsthand
[Resolve21.1 native-transition test](https://github.com/samuelgursky/davinci-resolve-mcp/blob/main/docs/reference/resolve211-native-transitions.md)
and the official [Fusion scripting guide](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf).
Other builds and third-party documentation are not acceptance for this build.

## Retained work and resume point

`scripts/issue292_transition_probe.py` is a small bounded preflight/apply/readback
helper. Its inventory is explicitly scoped to `292-representatives`, never the
full installed catalog. Simulated tests cover unavailable/incomplete inventory,
missing/changed/duplicate identities, unsupported controls, gaps, short handles
and preserving an existing sentinel on preflight refusal. Post-write mismatch
reports uncertainty and does not claim rollback. Seven focused tests passed
after correcting the helper to use the actual dictionary AddTransition API.

The custom declaration, authored setting and `issue-292/probe.py` are retained
as the reproducible live scenario. **The retained live scenario has not yet
been run.** The earlier runtime proof used the local `live-proof.py` and
`live-update.py`; local JSON observations and five synthetic movies remain in
the issue-owned root. No validate:fast, final Claude review, full CI gate, merge
or acceptance has been completed for this checkpoint.

Next, with the Producer back:

1. Coordinate runtime access again. No timer or automatic restart is authorized.
2. In `VERA292Probe20261024A`, open `292-type-Edge Wipe` and have the Producer
   change the transition's **Angle** to90. Earlier GUI automation attempts did
   not successfully change that field; typing90 moved the playhead instead.
   Do not label `native-manual-angle90.otio` a successful manual-edit sample.
3. Independently observe the manual native edit, compare direct API/OTIO/DRT
   readback and preserve unknown settings. Complete the updated save/reopen and
   targeted rerender check, plus run the retained headless declaration scenario.
4. Finish installed-library comparison, supported/unsupported/ambiguous matrix,
   concrete native-control/import limits, safe identity/cache constraints and
   #88/#61/#125 handoff. Universal installed discovery/control access is still
   unproved; the existing design promise stays blocked.
5. Focused checks, validate:fast, one final restricted Claude review and actual
   PR Validate; push and stop if CI is pending. Merge/close only if the
   investigation's requirements are actually satisfied. No successor dispatch.
