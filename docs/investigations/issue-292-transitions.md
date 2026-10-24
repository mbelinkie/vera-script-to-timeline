# #292 — installed picture-transition capability proof

Status: bounded runtime proof completed, validation/delivery pending, 2026-10-24.
Precise native and custom application works on the tested routes. Full installed
inventory and exhaustive controls remain unsupported by the tested discovery
routes. **This result does not clear the current feature promise in #125/#61.**

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
operation after checking inactive peers and completed #145 work. On resumption,
Matthew authorized coordination with #275; its latest final explicitly stopped
the benchmark and helpers before #292 continued. The disposable project was
still current with no active render. All #292 renders finished before release.

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
| Subsequent update | Both were changed to 12 frames `[66,78)` by deleting/recreating only the disposable transition; custom Curve=Easing, EaseIn=Quad, EaseOut=None. Settings, anchors and audio survived save/close/load; re-rendered picture and audio are byte-identical to the pre-reopen12-frame renders. This is a bounded replacement proof, not a general in-place duration setter. |
| Picture output | Initial renders contain red → mixed red/blue → blue frames. Updated custom output has the expected slower early blend for quadratic easing. Movies are 144 frames/6 seconds. |
| Narration | Video ranges `[0,72)` and `[72,144)`, audio `[0,144)`, marker at frame72 stayed unchanged. Decoded rendered audio is byte-identical for cut-only, native24, custom24, native12 and custom12. It is not byte-identical to the mono source after the project's normal output routing, so the cut-only comparison is the relevant control. |
| Zero handles | Raw API refused; no transition, clip/audio range or anchor movement. |
| Short handles | Two handles on each side silently shortened a requested24 to an actual2-frame transition. This is a failed precise request, not success. |
| Neighbor move | Incoming moved from72 to78 (six-frame gap); raw API created12 frames for requested24. Clips/audio/anchor stayed put. Preflight must refuse gaps and short handles. |
| Native control API | Transition GetProperties/GetProperty return `{}` / false for tested controls; SetProperties Direction/duration/Alignment returned false. This does not prove all possible import/private routes impossible. |
| Independent manual edit | Producer changed Edge Wipe Angle to90. Subsequent OTIO export exposes parameter ID `angle`, value90, Int, default0, range−360..360. Direct GetProperties still `{}` and GetProperty('Angle') false. Native export includes non-default settings not present in the earlier default export; absence cannot mean exhaustive discovery or default safely. See `issue-292/manual-native-observation.json`. |
| Native option application through import | Changed the actual Edge Wipe OTIO parameter `angle` from90 to180; imported a fresh timeline and independently re-exported180 at `[60,84)`. Save/reopen preserved it. Rendered frame72 is vertically split for180 versus left/right for90; angle0 gives the opposite vertical split. The Inspector also displayed180. Both retained headless scenarios ran successfully. |
| Export/readback limits | Native OTIO export includes type, offsets and non-default angle metadata. Fusion OTIO export omits graph/controls. FCPXML omitted the manually set90° angle. DRT contains native effect blobs but was not decoded/modified. The production portable verifier remains unchanged and rejects OTIO transitions; native OTIO proof used Resolve's direct import API. |

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

The declarations, authored setting, `issue-292/probe.py` and `native_probe.py`
are the retained reproducible scenarios. Both ran successfully against the real
runtime. The custom scenario returned24 frames and all three requested controls;
the native scenario imported180° and read back180°. They require the named
disposable project and local synthetic fixture root, refuse other projects and
changed source bindings, and never scan the Producer's project library.

Generate the original fixtures in that root with FFmpeg's `color` source (red
and blue, six seconds,640×360,24fps, H.264/yuv420p) and a six-second440Hz,
48kHz PCM tone named narration.wav. Import those exact files into the disposable
project. The custom probe additionally uses its earlier instantiated custom
sample for actual enum metadata; it is not a standalone fresh-machine catalog.
The native probe uses the Producer-edited `producer-angle90.otio` seed retained
locally. It preserves unrecognized seed fields, changes only the measured angle
and imports a fresh timeline. It must not be generalized to arbitrary project
exports without validation. Local proof/update scripts, JSON observations and
synthetic movies remain in the issue-owned root; no private source is published.

## Capability verdict and integration handoff

| Route / family | Identity and inventory | Real control discovery | Outbound | Inbound / persistence | Verdict on this build |
|---|---|---|---|---|---|
| Direct Resolve, native | Known exact category/name works; occurrence UID persists. No complete installed transition enumerator observed. Native type13 in OTIO is build-specific evidence, not a universal stable identifier. | Direct properties empty for tested transitions. | Name/duration/alignment proved; native settings through direct setter refused. | Name/span/UID proved. | Supported bounded placement; unsupported complete discovery/direct native settings on tested route. |
| Resolve OTIO, native Edge Wipe | Export names/type metadata identify instantiated occurrence; not an installed catalog. | Non-default angle ID/type/range/current/default appear after manual edit. Default export omitted angle entirely, so absent field is unknown. | Angle180,24frames,center proved in fresh import. | Manual90 and imported180 readback, reopen and output proved. | Supported for the measured native option; exhaustive metadata and other native settings remain ambiguous. |
| Fusion, bundled/custom templates |67 bundled settings plus1 authored installed fixture can be listed by documented paths/archive entries; exact application checked for Slide Left, Cross Dissolve and VERA292. Registry is not their catalog. | Instantiated graph inputs expose real IDs/types/enums/ranges/default-like attributes/current values and visibility. Numeric “default” on FuID was0, not a usable enum identity. | Custom Curve/Ease settings plus duration/alignment rendered. | Graph values persist; OTIO loses graph. | Supported representative controls; exhaustive arbitrary macro/Inspector equivalence unproved. |
| Already-installed third-party transition / OFX transition | Installed third-party OFX representative is a color filter, not transition. Existing sample DRFX contains no transitions. | Not tested on a representative transition. | Not tested. | Not tested. | Untested; absence of representative is not pass or universal impossibility. Authored custom fixture is not third-party certification. |
| Full installed chooser + all settings | File inventory covers templates, not all native/OFX/preset/runtime availability. Known registry omissions contradict treating it as full catalog. | No proven exhaustive conditional/read-only/default/units model across all families. | Cannot promise arbitrary chosen installed effect. | Unknown fields cannot safely be synthesized. | Not deliverable from the tested discovery routes; current broad product promise remains blocked. |

**#88's smallest seam:** use boundary IDs/markers and exact adjacent source
ranges, validate handles before writes, call native AddTransition for qualified
name/category/duration/alignment, access an instantiated Fusion graph for
qualified controls, and use Resolve OTIO metadata/import only for specifically
qualified native controls. Read actual name/type/span/control values afterwards;
then save/reopen and inspect output when qualifying a new effect. Treat a failed
or mismatched post-write result as uncertain, preserving the target for recovery.
Import into a fresh timeline, not over the existing one. The cut-only portable
verifier must gain an explicit future transition path in #88; do not weaken its
current rejection or pass this probe off as production delivery.

**#61/#125 allowed claims:** occurrence duration/alignment on qualified effects;
measured Fusion enum controls; measured Edge Wipe angle through an explicitly
qualified native route. The proposed full installed searchable chooser and
automatic exhaustive settings panels are **not cleared**. Do not silently
replace them with a three-effect menu. A future broader discovery route must be
proved, or Matthew must explicitly select a narrower/deferred product scope.
New cuts, explicit effect addition, project chooser order and keep-existing /
explicit-replace removal remain the product requirements; this investigation
does not redesign them or restart design owners.

## Unavailable, ambiguous and changed states

- Disconnected companion/offline or unqualified build/edition: observation is
  unavailable, not an empty catalog. Retain prior intent/existing occurrences;
  refuse writes and offer the named manual step. Free and other builds are
  untested. Do not infer Studio methods work on Free.
- Missing template/plugin, changed hash/version, duplicate category/name or
  unknown control: refuse new application/update. Preserve existing embedded
  instances and opaque settings; never substitute Cut or another effect.
  AddTransition accepts category/name only, so even distinct source paths cannot
  disambiguate a duplicate dispatch name safely. Tests simulate inventory loss
  instead of uninstalling anything. Localization/duplicate runtime resolution
  across locales has not been tested.
- Refresh on a new connection/session and explicit library refresh; check the
  exact source/build fingerprint again before applying. The custom fixture was
  found/applied without app restart on this session. Installed docs recommend
  restart for template refresh; no install/uninstall/restart matrix was run.
  Do not claim a persistent cache is authoritative or reset existing uses on a
  refresh discrepancy.
- Conditional controls: re-read Fusion metadata after a controlling value
  changes. The tested enums exist in actual metadata, but all possible controls,
  units, expressions, spline/image inputs, read-only behavior and arbitrary
  third-party custom UI are not qualified. Display unknown/unsupported values
  explicitly; do not round-trip them as guessed defaults.

This is a negative/narrowed feasibility verdict for universal discovery, not a
claim that every route or future Resolve build is impossible. The successful
OTIO native route is specifically why one empty getter cannot establish that.
