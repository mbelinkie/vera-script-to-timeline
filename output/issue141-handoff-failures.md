# Issue 141 — handoff of observed harness failures

Task ID: `handoff_failures_v2`

This is a replication handoff for the Resolve observation run from 2026-09-30
through 2026-10-02. It records refusal points, partial mutations, wrapper and
launcher defects, and the evidence needed before a bounded observation can be
called successful. It is deliberately narrower than a product defect report:
a guard that stopped before a native call is evidence about the guard, input
shape, page, state, or retained evidence. It is not evidence that Resolve or
the script-to-timeline path lacks the guarded capability.

The authoritative chronological narrative is [report.md](report.md). Issue-local
evidence links below are relative to the eventual
`docs/investigations/issue-141/second-opinion-handoff.md` location. Repository
artifacts under `out/` therefore use `../../../out/...`. No protected source
media bytes were read for this handoff, and no native action or test was
rerun.

Each occurrence below gives: UTC time, retained path, exact trigger or output,
the mutation boundary, the current diagnosis, later recovery, the success gate,
and a new experiment that remains unrun. “Product absence” means that the
occurrence cannot be used to claim that Resolve, its API, or the VERA authoring
workflow is unavailable.

## R3 evidence that bounds the interpretation

### Calibration and sampled picture cases

The calibration at 2026-09-30 22:44 UTC is retained in
[evidence/picture-calibration-success/](evidence/picture-calibration-success/).
On Edit, `ExportCurrentFrameAsStill` returned true at four requested frames
after restoring the initial timecode. The base slate is visible at local
frames 0 and 198; local frames 199 and 200 are identical all-black samples.
This is a bounded base-video endpoint observation. It does not define an audio
endpoint, still-export synchronization, arbitrary effect behavior, or a
general “last visible frame” rule.

The picture case at 23:17 UTC is retained in
[evidence/picture-cases-success/](evidence/picture-cases-success/). It recorded
21 captures, eight setters, and 14 still exports, with exact final-matrix
equality. The synthetic opaque `cutaway.mov` samples were local frames
49/50/98/99/100, with disabled sample 50. The transparent `overlay.png`
samples were local frames 74/75/198/199/200, with disabled sample 75.
The observed cutaway is present at 50 and 98 while the base is present at 49,
99, and 100. The overlay is present at 75, 198, and 199; local 200 is black.
Inspector Opacity 25 reduced the green overlay, then the target was restored
to 100 and disabled.

The picture cases establish only those named synthetic samples and setter
round-trips. They do not establish general visibility, arbitrary OpenFX or
Fusion behavior, exact sample synchronization, clip lineage, audibility, or
product absence.

**Success gate.** A later R3 picture experiment must bind each requested frame
to the exact occurrence, playhead readback, export result, and restored
full-state pair; it must say which effect and enable/lock context was tested.

**Unrun experiments.** No broad effect matrix, arbitrary track-order
visibility test, exact rendered-sample synchronization test, lineage test, or
picture-to-audio audibility test was run.

### Offline guard and later recovery

The first offline-picture setup was correctly refused. R4 initially reported
`GetStartTimecode=01:00:00:00`, `GetStartFrame=90000`, and
`GetEndFrame=90000`, while the occurrence was record 0..199. The planned
frame 0/frame 50 action was stopped before a playhead setter or export. The
diagnostic is recorded at
[report.md#2026-10-01-04:00–04:01-utc--offline-picture-guard-refusal](report.md#2026-10-01-04:00–04:01-utc--offline-picture-guard-refusal).
This was a preparation-range defect. It does not imply that offline picture
output is absent.

The later valid cycle is retained in
[evidence/offline-cycle-continuation-success/](evidence/offline-cycle-continuation-success/).
Online and offline samples at frames 0 and 50 were exported; the offline
samples were Media Offline, and same-byte relink restored the exact prior
state. The success gate is a fresh in-range occurrence with explicit
online/offline/relink pairs and no stale timecode assumption. The unrun
experiment is a second, independently reviewed offline visual case with
different source bytes and an explicit cache-refresh check.

### Graphic enable refusal and repair

At 2026-10-01 19:44 UTC the Graphic preparation attempted
`SetClipEnabled(True)` for locked, disabled V3 Graphic
`ea448c37-4821-419d-8fbf-112790cc0499`. The exact native output was
`SetClipEnabled did not return true` (the setter returned false). The
before/after pair is byte-identical; no split, lock, playhead, save, retry, or
cleanup followed. Retain
`graphic-preparation-refusal-analysis.json` and
`r3-graphic-native-executor-result.json` beside the
[report.md#graphic-enable-refusal-before-split--october-1-1944-utc](report.md#graphic-enable-refusal-before-split--october-1-1944-utc)
entry.

The diagnosis is ordering: the first preparation tried to enable the target
before unlocking its locked track. It was unknown whether the false return
would also occur on an unlocked target. This does not imply missing
`SetClipEnabled` support or missing Graphic support.

The repaired order—unlock the exact target, enable it, perform the bounded
operation, and restore its original lock—succeeded. The linked V1/A1 split at
Matrix 8600 produced ranges 8500..8600/source 0..100 and
8600..8699/source 100..199; V3 remained enabled and distinct. Independent
review `graphic-full-pair-independent-review.json` passes the structural
criterion while retaining the restore-wrapper caveat.

**Success gate.** Any repeat must retain original lock, target UID, setter
return, split ranges, final lock, and complete postflight equality. It may
claim the named structural split only.

**Unrun experiment.** A general visibility or arbitrary-effect experiment under
the repaired lock ordering was not run.

### Authored section boundary

The first boundary-base preparation at about 20:21 UTC refused before mutation
with `Exact enabled R3-boundary A3 crossing bed changed`. The exact prior
source schema exposed `Clip Name` for `bed.wav`, but the guard required
`source.GetName`. The retained refusal is described at
[report.md#boundary-preparation-refused-captured-schema-mismatch-diagnosed--october-1](report.md#boundary-preparation-refused-captured-schema-mismatch-diagnosed--october-1)
and bound by the native result
`20261001T202103.928483Z`. No final pair was created for that attempt. The
executor also carried a stale R2 after-pair reference in its narrative; that
reference is not evidence of a boundary postflight. This is a captured-schema
and evidence-index defect, not a boundary or Razor capability failure.

After the predicate repair, the authored marker was placed at absolute frame
9100 (local frame 100), named `141 R3 exact section boundary`, duration 1,
Blue, with note `Synthetic authored boundary at local frame 100` and custom
data `{"issue":141,"section":"R3-boundary","boundaryLocalFrame":100}`.
Base V1/A1 was split at 9100, and separate enabled A3 `bed.wav` was split
9000..9100 and 9100..9199. Disabled V3 `overlay.png` and disabled A2
`repeated.wav` still cross 9100 and were unchanged; the enabled A3 crossing
became two pieces. The independent boundary review
`../../../out/issue-141-observation-20260930-01a0f318/boundary-complete-independent-review.json`
passes the structural criterion.

**Success gate.** Preserve the authored marker and its custom data, report
enabled and disabled crossing items separately, and compare both base and A3
full pairs. The result may establish the meaning of the authored section
marker and the named structural split.

**Unrun experiment.** A blade without an authored marker has not been shown to
carry section meaning. No “all crossings gone,” general visibility, audibility,
or lineage test was run.

## Failure inventory

## 1. Setup, settings, reopen, and cache

### 2026-09-30 16:56 UTC — rate representation stopped preparation

**Path.** [evidence/attempt-1/](evidence/attempt-1/), with the source history
and failure hashes retained in the issue-owned output directory.

**Trigger/output.** The first launcher created the project and applied settings,
then read `timelineFrameRate: 25.0` as a number while the request used the
string `"25"`. The guard compared string forms and stopped before import,
timeline creation, or media setup. The operator saw no visible result.

**Partial mutation.** `CreateProject` and `SetSettings` had run; the new
project existed with an otherwise empty preparation state. No import or
timeline mutation occurred. The readback also exposed inherited 24 fps
playback and storage locations outside the disposable slice.

**Diagnosis and product-absence interpretation.** This is a numeric/string
probe bug. It does not imply rejection of 25 fps, inability to create a
project, or product absence. The operator’s External Scripting and
synthetic-only attestations were not inferred from configuration.

**Later recovery.** The corrected guard compares exact finite numeric values and
the later successful baseline preparation created the named synthetic project,
timeline, media, markers, and links.

**Success gate.** Retain the requested type, actual readback type/value, and
an empty-project invariant before import. Refuse only on a real numeric
mismatch.

**Unrun experiment.** No independent test of a non-string rate request against
a newly created blank project was run after this correction.

### 2026-09-30 17:20 UTC — read-only playback setting in a batch

**Path.** [evidence/attempt-2/](evidence/attempt-2/).

**Trigger/output.** The correction attempted to write
`timelinePlaybackFrameRate`; the installed stub marks it read-only and
`SetSettings refused operation` was returned.

**Partial mutation.** The operation stopped before import. README guidance says
batch settings may be partially applied in unspecified order on failure, so the
state of any other requested writable settings was not safely known. No
timeline or media was created by this attempt.

**Diagnosis and product-absence interpretation.** This is a second probe
boundary error. It does not imply that writable settings, media import, or
timeline creation are unavailable.

**Later recovery.** The operator set playback to 25 manually; the corrected
launcher stopped writing the read-only key, applied writable keys individually,
retained each readback, and later reached the successful baseline.

**Success gate.** Capture all settings before the batch, never include the
read-only key, set writable keys one at a time, and retain post-readback even
when a setter refuses.

**Unrun experiment.** A clean-project test of the documented partial-batch
ordering and each writable storage setter remains unrun.

### 2026-09-30 18:12 UTC — native repeat baseline preflight

**Path.** [evidence/native-preflight-refusal/](evidence/native-preflight-refusal/).

**Trigger/output.** The native repeat launcher raised
`RuntimeError: Current project is not the prepared baseline-only state`.

**Partial mutation.** None: the refusal preceded native mutation and produced
no native journal. The exact current before-state comparison was not retained.

**Diagnosis and product-absence interpretation.** Cause is unknown: metadata
change and edit are both possible. This does not imply a Resolve mismatch,
unsupported repeat, or failure of the prepared timeline.

**Later recovery.** A quiet read-only repeat at 18:22 retained two equal
adjacent reads matching the baseline. The later run used explicit project and
cache guards, then native duplication succeeded.

**Success gate.** Persist the complete failed preflight (raw current pair,
expected pair, normalized diff, and project identity) before raising. A
repeat may proceed only from two equal complete baseline passes.

**Unrun experiment.** The missing 18:12 current state cannot be reconstructed;
no replay of that exact state is possible.

### Historical #110 compatibility carryover

**Path.** The inherited evidence referenced by the preparation report, not a
new #141 native occurrence.

**Trigger/output.** Normalization and PCM-WAV render selection failed in the
older #110 workflow; preset/EQ/dynamics remained operator-only.

**Partial mutation.** No #141 state was mutated by that historical result.

**Diagnosis and product-absence interpretation.** Treat this as inherited
compatibility context, not fresh #141 evidence. It does not imply that the
#141 synthetic authoring path is absent.

**Later recovery.** #141 reached a native synthetic baseline and later completed
a bounded generated render through a separately verified queue.

**Success gate.** Keep historical compatibility labels separate from #141
failures and require current-build evidence for any product conclusion.

**Unrun experiment.** The inherited operator-only controls were not re-tested
in #141 and remain outside this handoff.

### 2026-09-30 19:42 UTC — close returned a different project

**Path.** [evidence/native-close-refusal/](evidence/native-close-refusal/).

**Trigger/output.** `SaveProject` and `CloseProject` returned true, but the
current project after close was UID
`fedceab7-8706-4b83-9ffe-fb77c65f0dbe`, not approved UID
`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`. The launcher stopped before
`LoadProject` or `DuplicateTimeline`.

**Partial mutation.** The approved project was saved and closed. The
unexpected current project was neither inspected nor mutated; no duplicate
was attempted.

**Diagnosis and product-absence interpretation.** The cause and contents of the
unexpected project are unknown. This does not imply failed close/load support,
an empty/default project, or missing DuplicateTimeline capability.

**Later recovery.** The operator manually reopened the exact synthetic project;
a later cache-only mismatch was isolated and then restored before native
duplication.

**Success gate.** Retain current project UID and name after every close/load,
inspect only the approved project, and refuse before any duplicate call on
mismatch.

**Unrun experiment.** The unexpected project was never inspected, by design;
no automatic project switch or replay is authorized.

### 2026-09-30 20:11 UTC — duplicate-only named-project guard

**Path.** [evidence/native-duplicate-project-refusal/](evidence/native-duplicate-project-refusal/).

**Trigger/output.** The duplicate-only launch returned
`Select only the named issue-141 project; no automatic switch`; current
project identity was absent or did not match.

**Partial mutation.** No capture, selection, or native mutation occurred.

**Diagnosis and product-absence interpretation.** This is a project-selection
guard refusal. It does not imply a Resolve project API or duplication failure.

**Later recovery.** Manual exact-project reopen plus read-only identity checks led
to cache restoration and successful duplication.

**Success gate.** Keep the refused identity in the retained result, then require
two complete exact-project reads before any action.

**Unrun experiment.** Automatic project switching was intentionally not tested.

### 2026-09-30 20:17 UTC — cache readback mismatch on reopened project

**Path.** [evidence/native-reopen-cache-refusal/](evidence/native-reopen-cache-refusal/).

**Trigger/output.** Project identity matched, but
`perfCacheClipsLocation` read back as `CacheClip` at project and timeline
settings instead of the pinned owned cache path. IDs, ranges, markers, item
properties, and media hashes otherwise matched.

**Partial mutation.** None after the manual reopen; no duplication or native
journal was produced.

**Diagnosis and product-absence interpretation.** The resolved target of
`CacheClip` was unknown. This is an environment/readback mismatch, not
evidence that reopening, cache settings, or duplication are unsupported.

**Later recovery.** The guarded cache-restoration action set the project setting
once, returned true, and produced a postflight exactly equal to the saved
baseline; native duplicate then succeeded. See
[evidence/cache-restoration-success/](evidence/cache-restoration-success/).

**Success gate.** Pin the cache path and its observed readback form across
project and all timelines; restore only after a fresh full pair and verify the
same pair after restoration.

**Unrun experiment.** The meaning or persistence of the literal `CacheClip`
target after a fresh application restart was not tested.

### 2026-09-30 21:49 UTC — source-list shape assumption

**Path.** [evidence/matrix-source-read-refusal/](evidence/matrix-source-read-refusal/).

**Trigger/output.** The matrix action refused
`Media pool items are unreadable; refusing` because it required exactly five
root-folder entries.

**Partial mutation.** None. Two complete before/after passes were equal and the
journal contains no API mutation.

**Diagnosis and product-absence interpretation.** The raw list type, value, and
count were not retained, so the precise mismatch is unknown. This is a probe
assumption, not unavailable media-pool or timeline capability.

**Later recovery.** The corrected continuation reused already observed source
handles, completed all 114 placements, and saved the matrix.

**Success gate.** Retain the raw source-list type/value/count and bind every
source handle to UID, locator, and owned-byte policy before creation.

**Unrun experiment.** The original five-entry source-list value cannot be
recovered; no replay of the discarded read is available.

### 2026-09-30 21:56 UTC — marker numeric/string-key bug

**Path.** [evidence/matrix-marker-refusal/](evidence/matrix-marker-refusal/).

**Trigger/output.** After timeline creation and the first occurrence/marker,
the marker guard rejected a numeric/string key mismatch.

**Partial mutation.** The matrix timeline, first occurrence, and marker existed;
the remainder of the matrix was not completed in that invocation. The partial
state was retained and no cleanup or blind retry occurred.

**Diagnosis and product-absence interpretation.** The failure was an
implementation key-type assumption. It does not imply marker creation,
timeline creation, or placement capability is absent.

**Later recovery.** The corrected key handling preserved the first marker and
completed the remaining 113 placements.

**Success gate.** Normalize marker keys only after retaining their raw type and
verify the first marker plus all later markers in a fresh pair.

**Unrun experiment.** No separate marker-key regression was run against an
unrelated existing timeline; only the corrected synthetic path was exercised.

### 2026-09-30 22:11 UTC — audio-format guard rejected stereo A1

**Path.** [evidence/matrix-track-refusal/](evidence/matrix-track-refusal/).

**Trigger/output.** After 114 placements completed, the final guard raised
`Final matrix audio tracks are not all mono`. Actual tracks were A1 stereo,
A2 mono, and A3 mono.

**Partial mutation.** All 114 items, source bindings, markers, links, and enable
states were present. The guard stopped before `SaveProject`.

**Diagnosis and product-absence interpretation.** The guard assumed every audio
track would be mono; the existing default A1 was stereo. This does not imply
audio placement or track-format support is unavailable.

**Later recovery.** The corrected observed matrix layout was accepted and a
save-only action succeeded with one `SaveProject` call.

**Success gate.** Pin the expected per-track format (stereo/mono/mono), rather
than an all-mono predicate, and require exact 114-item post-save equality.

**Unrun experiment.** No generic mono-conversion or all-mono authoring test was
run.

## 2. Media-pool, R4, range, and recovery-state failures

### 2026-10-01 00:18 UTC — initial R4 pool inventory

**Path.** [evidence/r4-pool-inventory-refusal/](evidence/r4-pool-inventory-refusal/).

**Trigger/output.** Initial complete inventory refused with
`Media-pool item identity/properties are unreadable`.

**Partial mutation.** None; no `ImportMedia`, transition, or mutation journal
was produced.

**Diagnosis and product-absence interpretation.** The failure is limited to
the first identity/property read. It does not imply import, unlink, relink,
offline, replacement, removal, or R4 support is absent.

**Later recovery.** Later read-only checks enumerated the unchanged original pool;
the path-list import branch was run separately.

**Success gate.** Persist the failed item identity/property payload and require
a complete, readable inventory before any R4 transition.

**Unrun experiment.** The exact unreadable first shape was not reconstructed;
the later successful inventory used a new read.

### 2026-10-01 00:27 UTC — dictionary-shaped ImportMedia request

**Path.** [evidence/r4-dictionary-import-refusal/](evidence/r4-dictionary-import-refusal/).

**Trigger/output.** `ImportMedia` refused the approved `FilePath`/hash
dictionary item shape.

**Partial mutation.** None. Follow-up read-only checks retained equal pools with
eight pre-existing entries and no mutation.

**Diagnosis and product-absence interpretation.** This applies only to that
argument shape. It does not imply path-list import, relink, unlink, or other
R4 operations are unavailable.

**Later recovery.** A path-list import succeeded and produced an imported item.

**Success gate.** Test each accepted argument shape independently and retain the
exact request and return before changing the next phase.

**Unrun experiment.** No second dictionary-shape variant was tried after the
refusal.

### 2026-10-01 00:31 UTC — path-list import and append partial state

**Path.** [evidence/r4-path-list-import-partial/](evidence/r4-path-list-import-partial/).

**Trigger/output.** Path-list `ImportMedia` returned an item; the action
created `VERA 141 R4 availability`, selected it, and appended to V1. The
post-append proxy/equality guard then refused
`R4 contains an extra or unreadable track item`.

**Partial mutation.** Media UID
`81d81dc0-4c37-478b-8079-03debba5e780`, timeline UID
`64de8a4c-86bd-4f19-9d20-47b8940f610b`, and occurrence UID
`af55478a-0ba3-458a-a6e1-e47b2544111d` existed. The occurrence was enabled
on V1 with bounds 0..199. No `SaveProject` occurred.

**Diagnosis and product-absence interpretation.** The extra/unreadable postflight
guard failed after successful import and append. This does not imply either
native operation failed or that the new item cannot be read.

**Later recovery.** A read-only follow-up retained a single enabled base
occurrence, ten pool entries, and matching source bytes. Later unlink/relink,
removal, and new-ID in-range preparation were run as separate checkpoints.

**Success gate.** Bind the expected extra media item and occurrence UIDs before
append; permit exactly those deltas and require a complete post-append pair.

**Unrun experiment.** No retry of the original append or save was made; the
partial state was deliberately preserved.

### 2026-10-01 01:21 UTC — unlink succeeded, offline-prefix guard refused

**Path.** [evidence/r4-unlink-offline-prefix-refusal/](evidence/r4-unlink-offline-prefix-refusal/)
and [evidence/r4-offline-prefix-read-only/](evidence/r4-offline-prefix-read-only/).

**Trigger/output.** `UnlinkClips` returned true. The occurrence remained
present with `Online Status: Offline` and locator
`OFFLINE - <approved relink/base.mov>`. The full pool inventory then refused
`Media-pool item identity/properties are unreadable` because the guard did
not accept the literal `OFFLINE -` prefix.

**Partial mutation.** The imported occurrence remained on R4 with the intended
offline status. Only one complete pool read was retained; no relink or save
followed.

**Diagnosis and product-absence interpretation.** This is prefix handling and
incomplete-read evidence. It does not imply unlink failure, disappearance,
deletion, or unavailable offline support.

**Later recovery.** The read-only comparison isolated the two intended offline
properties. A relink-only action returned true and restored the exact online
pair.

**Success gate.** Treat offline locator decoration as a display field; retain
the underlying locator/status separately and require two complete pool passes
before relink.

**Unrun experiment.** No cache/display-refresh test for an offline item was run
before relink.

### 2026-10-01 02:54 UTC — start-timecode repair shifted occurrence negative

**Path.** [evidence/r4-range-repair-refusal/](evidence/r4-range-repair-refusal/).

**Trigger/output.** `SetCurrentTimeline` selected R4 and
`SetStartTimecode(00:00:00:00)` returned true. R4 timeline start/end changed
90000→0 and timecode 01:00:00:00→00:00:00:00, but the occurrence shifted from
record 0..199 to -90000..-89801. The postcondition refused the range.

**Partial mutation.** The same occurrence and source IDs remained; source range
and duration stayed intact, while seven timeline/occurrence and six mapped
pool-proxy leaves changed. No save/render/source mutation occurred. The
unsaved invalid state was retained without rollback.

**Diagnosis and product-absence interpretation.** The setter preserves absolute
record coordinates relative to the timeline start. The invalid occurrence was
not moved into range. This is a preparation arithmetic assumption, not an
offline-output or Resolve setter failure.

**Later recovery.** The occurrence was removed with exact before/after evidence;
a new append created a new occurrence UID at record 0..199 on the zero-start
timeline. The old identity was not reused.

**Success gate.** Derive record coordinates after changing start timecode,
require an in-range new occurrence, and keep removal and re-preparation pairs
separate.

**Unrun experiment.** No fractional or nonzero-start in-range offline visual
case was run.

### 2026-10-01 03:26–03:28 UTC — append succeeded, page guard refused

**Path.** The native result is
`vera-issue-141-observation-result-20261001T032648.191508Z.json`; the
read-only recovery is [evidence/r4-reprepare-read-only/](evidence/r4-reprepare-read-only/).

**Trigger/output.** `AppendToTimeline` returned new occurrence UID
`65a7bcd1-f211-4dee-9726-8c7e0b89cc84`, source 0..199, V1, record frame 0.
The postflight required Deliver while Resolve was on Edit and refused.

**Partial mutation.** The new occurrence and timeline end 0→199 existed;
source Usage changed 0→1 and R4 proxy duration/end fields updated. No retry,
rollback, save, render, or cleanup occurred.

**Diagnosis and product-absence interpretation.** This is a page-precondition
failure after a successful append. It does not imply append, source access, or
in-range preparation is unavailable.

**Later recovery.** A read-only Edit capture verified the new UID, source/record
0..199, idle queue, and exact anticipated deltas.

**Success gate.** Require the observed Edit page or make page a read-only
diagnostic, and compare the actual new UID and all expected deltas.

**Unrun experiment.** No append retry or save from this partial state was made.


### 2026-10-01 00:02:29 UTC — output discovery preflight mismatch

**Path.** [evidence/program-output-discovery-preflight-refusal/](evidence/program-output-discovery-preflight-refusal/).

**Trigger/output.** The read-only output-discovery launcher raised
`RuntimeError: Live preflight differs from saved Matrix pin` before any
capability getter. The persisted two passes themselves were equal to the
stable 23:47 pin; the mismatch was in the comparison representation.

**Partial mutation.** None. The journal contains only output-discovery start
and preflight readback; `GetRenderFormats`, codec, mode, job-list, and
rendering-status getters were never reached.

**Diagnosis and product-absence interpretation.** The probe compared native
Python marker keys/tuples with JSON-loaded keys/lists. This is a
canonicalization defect. It does not imply output-capability getters,
rendering, or audio output is absent.

**Later recovery.** Canonical JSON normalization was added; the 00:05:58
read-only continuation reached all eight getters and returned current
MOV/H264, mode 1, an empty queue, and idle rendering. No mutation was added.

**Success gate.** Canonicalize every persisted/live comparison while retaining
the raw representation, and record `capabilityGettersReached=false` on this
class of refusal.

**Unrun experiment.** No getter or render job was run from the refused
preflight; only the corrected read-only enumeration was accepted.

### 2026-10-01 01:59 UTC — preset export directory/file shape

**Path.** [evidence/audio-preset-export-refusal/](evidence/audio-preset-export-refusal/).

**Trigger/output.** `SaveAsNewRenderPreset` and
`Resolve.ExportRenderPreset` each returned true, but Resolve created a
directory containing a named XML while the probe expected a file at the export
path. The probe refused `Could not retain owned render-preset recovery copy`.

**Partial mutation.** The owned preset and XML existed; no render settings,
queue, job, or render mutation followed.

**Diagnosis and product-absence interpretation.** This is a representation
gap in the probe. It does not imply preset export or audio capability is
absent.

**Later recovery.** The XML was retained and reused without replaying export.
Its recorded raw hash is
`1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595`.

**Success gate.** Accept the documented directory/XML representation, bind the
actual XML path and hash, and retain the owned preset name.

**Unrun experiment.** A fresh export to an already existing directory was not
run.

### 2026-10-01 02:12 UTC — audio-only settings made current format unknown

**Path.** [evidence/audio-settings-restoration-refusal/](evidence/audio-settings-restoration-refusal/).

**Trigger/output.** Audio-only `SetRenderSettings` returned true, then
`GetCurrentRenderFormatAndCodec` returned
`{"format":"unknown","codec":""}`. The guard refused before
`AddRenderJob`/ `StartRendering`. `LoadRenderPreset` also returned true
but left the getter unknown.

**Partial mutation.** Render settings changed enough to produce the unknown
readback; no job, render, save, or cleanup occurred. The owned preset/XML were
retained.

**Diagnosis and product-absence interpretation.** The getter behavior and
hidden preset fields were not exposed. This does not imply audio rendering,
preset load, or job creation is unavailable.

**Later recovery.** The exact XML import was attempted on Deliver and returned
false; explicit `SetRenderSettings({"ExportVideo": true})` returned true
but still left unknown. `SetCurrentRenderFormatAndCodec("mov","H264")` later
restored the visible format, with hidden-setting equality still unknown.

**Success gate.** Capture format, codec, mode, page, queue, and all exposed
settings before and after every one-field action; do not authorize a job on
unknown format.

**Unrun experiment.** No actual audio-only job was queued from the unknown
state, and no documented getter for the hidden ExportVideo state was found.

### 2026-10-01 02:30 UTC — recovery assumed Edit instead of Deliver

**Path.** [evidence/audio-recovery-page-preflight-refusal/](evidence/audio-recovery-page-preflight-refusal/).

**Trigger/output.** Import recovery refused the Edit-page precondition before
calling `ImportRenderPreset`. Read-only state showed page Deliver, unknown
format, mode 1, idle empty queue.

**Partial mutation.** None after the prior settings change; no import request
was dispatched.

**Diagnosis and product-absence interpretation.** Wrong page assumption in the
recovery guard. It does not imply import or Deliver-page recovery failure.

**Later recovery.** The corrected Deliver action was run once with full content,
pool, source, and render guards.

**Success gate.** Pin current page and require the page observed in the
preceding read-only capture; retain a no-import journal on refusal.

**Unrun experiment.** No page-switch automation was attempted.

### 2026-10-01 02:38 UTC — exact XML import returned false

**Path.** [evidence/audio-render-import-refusal/](evidence/audio-render-import-refusal/).

**Trigger/output.** Deliver-page recovery called
`ImportRenderPreset` once on the exact owned XML; return was false.

**Partial mutation.** Complete timeline/pool/source pairs remained equal; preset
list, mode, empty queue, idle state, and unknown format were unchanged. No
retry, setter, queue, render, save, or cleanup followed.

**Diagnosis and product-absence interpretation.** The reason for this exact
import refusal is unknown. It does not imply import of an absent preset, audio
rendering, or queueing is unavailable.

**Later recovery.** Visible format was restored using the documented explicit
MOV/H264 selector, then the original render snapshot was restored and cleaned
after later output work.

**Success gate.** Record XML path/hash, preset-list delta, page, format/mode,
and import return; separate “visible format restored” from “all hidden fields
restored.”

**Unrun experiment.** An import of an absent preset or a cleanly exported
fresh XML was not tested.

### 2026-10-01 02:46 UTC — one-field video toggle did not recover format

**Path.** [evidence/audio-video-toggle-unresolved/](evidence/audio-video-toggle-unresolved/).

**Trigger/output.** `SetRenderSettings({"ExportVideo": true})` returned true,
but the format/codec getter remained unknown/empty.

**Partial mutation.** Complete content/pool/source pairs were unchanged; no
queue, render, save, cleanup, or retry followed.

**Diagnosis and product-absence interpretation.** The field did not restore the
visible format in this state. It does not imply SetRenderSettings, video
rendering, or audio rendering is unavailable.

**Later recovery.** A separate `SetCurrentRenderFormatAndCodec("mov","H264")`
call returned true and restored the visible format.

**Success gate.** Verify each setting through its own getter, and do not treat a
true setter return as restoration.

**Unrun experiment.** No clean baseline was used to isolate whether the
unknown state came from audio-only settings, preset loading, or page context.

### 2026-10-01 06:20 and 06:32 UTC — AV settings/readback drift

**Path.** [evidence/av-preset-precondition-refusal/](evidence/av-preset-precondition-refusal/)
and [evidence/av-settings-pool-out-refusal/](evidence/av-settings-pool-out-refusal/).

**Trigger/output.** The 06:20 snapshot guard saw
`RecordAudioBitDepth=16` while the pin expected 24. At 06:32
`SetRenderSettings` returned true, then four Matrix proxy/mapping pool
`Out` leaves changed from empty to `00:00:08:00\), so the guard refused.

**Partial mutation.** The first attempt did not dispatch a setter. The second
changed exactly those four pool-display leaves; no `AddRenderJob` or
`StartRendering` was issued.

**Diagnosis and product-absence interpretation.** The bit-depth mismatch and
Out-display drift are state/pin and readback effects. They do not imply render
or audio capability is absent.

**Later recovery.** A fresh after-settings checkpoint independently verified
the four Out leaves, queued a job with actual dimensions/range, and later
completed one owned render.

**Success gate.** Derive settings and range from the current full pair, verify
actual queued metadata before start, and retain the four-leaf drift as an
explicit expected delta.

**Unrun experiment.** No second setter replay from the stale 16-bit or
pre-drift snapshot was run.

### 2026-10-01 07:07 UTC — R1 copy page/format/queue guard

**Path.** [evidence/r1-copy-paste-stopped/](evidence/r1-copy-paste-stopped/).

**Trigger/output.** The copy launch refused
`Exact Edit/known format/empty queue required`; read-only context was Deliver
with MOV/H264 and an idle empty queue.

**Partial mutation.** No selection, copy, paste, or native mutation occurred.

**Diagnosis and product-absence interpretation.** The action assumed Edit. This
does not imply copy/paste capability is absent.

**Later recovery.** With renewed bounded approval, a genuine copy/paste ran on
the correct context. Its expected new clips were retained, but a later
four-leaf pool-Out drift stopped the continuation.

**Success gate.** Pin page, format, queue, selected UIDs, and complete before
pair; require exact new occurrence IDs and expected pool deltas afterward.

**Unrun experiment.** No retry of this refused invocation was made.

### 2026-10-01 07:20–07:25 UTC — genuine Copy/Paste stopped on pool-Out drift

**Path.** The continuation records are in
[evidence/r1-copy-paste-stopped/](evidence/r1-copy-paste-stopped/) and the
full pair is in the issue-owned `out/` directory.

**Trigger/output.** Copy/Paste created new clips, but the postflight saw the
same four Matrix proxy/mapping `Out` leaves change. The action stopped before
accepting the final state.

**Partial mutation.** New copied timeline occurrences and expected Usage
increments existed; no save or cleanup was used to hide the drift.

**Diagnosis and product-absence interpretation.** The drift is a
context/readback delta. It does not imply that Copy/Paste or occurrence
creation failed.

**Later recovery.** The original stopped copies and metadata remained
protected; later R1 razor, trim, move, and final duplicate were verified with
their own context guards.

**Success gate.** Compare copy-specific expected deltas separately from known
pool Out-display fields, and retain copied UIDs, reciprocal links, markers, and
source identities.

**Unrun experiment.** A second copy/paste from the same stopped state was not
run.

## 3. Editorial, launcher, and bridge failures

### Initial selection reader/API-shape failure

**Time/path.** The first R3/R1 selection reader expected a dictionary, while the
API returned a list; the retained helper sources and editorial refusal bundle
are in [evidence/editorial-helper-sources/](evidence/editorial-helper-sources/)
and the report’s approved editorial calibration section.

**Trigger/output.** The reader failed its shape expectation. The later Select
All action selected locked items, and the safety guard stopped rather than
editing them.

**Partial mutation.** Selection state may have changed during calibration, but
the guarded action dispatched no edit and retained no accepted final edit pair.

**Diagnosis and product-absence interpretation.** The reader and selection
scope were harness assumptions. This does not imply selection, lock handling,
or editorial commands are unavailable.

**Later recovery.** Explicit V1/A1 Auto Select and deselection produced exact
target lists; named R1 razor, trim, move, and copy/paste actions then completed
bounded cases.

**Success gate.** Normalize the actual list shape, pin selected UIDs and lock
state, and retain a complete readback after each menu action.

**Unrun experiment.** No broad Select All behavior on mixed locked tracks was
accepted as a product result.

### 2026-10-01 05:48 UTC — R1 trim window/title guard

**Path.** [evidence/r1-trim-launch-refusal/](evidence/r1-trim-launch-refusal/).

**Trigger/output.** The Hammerspoon project-title/window guard refused before
the Trim menu was dispatched.

**Partial mutation.** None: no menu, selection, timeline, or save mutation.

**Diagnosis and product-absence interpretation.** Window identity/readiness was
unknown at that launch. This does not imply Trim or linked-pair editing is
unavailable.

**Later recovery.** A fresh focus check and exact selection enabled the bounded
25-frame linked-pair trim, with independent full comparison.

**Success gate.** Retain title, frontmost window, enabled menu, target UIDs,
and empty/expected selection before dispatch.

**Unrun experiment.** No automatic window activation or retry was performed.

### 2026-10-01 06:20/06:32 and 07:07 — downstream editorial launch preconditions

The AV and R1-copy occurrences are recorded above because they share the page,
format, queue, and pool-Display-Out boundary. Each stopped before the unsafe
operation or retained its exact bounded partial result. None establishes
product absence.

**Success gate.** Use current page and current queue as observed inputs, not
pinned expectations copied from a prior checkpoint. **Unrun:** no generic
cross-page editorial macro was tested.

### 2026-10-01 11:25–11:34 UTC — R2 selection returned empty lists

**Path.** The R2 continuation records are summarized in
[report.md#independent-r2-selection-attempts--october-1-1125–1134-utc](report.md#independent-r2-selection-attempts--october-1-1125–1134-utc).

**Trigger/output.** Focus and Auto Select attempts still returned empty
selected-item lists. No target could be authorized.

**Partial mutation.** Focus/Auto Select menu calls occurred, but no blade,
delete, or other edit was dispatched.

**Diagnosis and product-absence interpretation.** Selection/readback context
was not established. This does not imply R2 editing or selection is absent.

**Later recovery.** Explicit V1/A1 scope and named UIDs were used for later
R2 cuts and deletion.

**Success gate.** Require exact selected UIDs, scope, and complete before pair
before any R2 edit.

**Unrun experiment.** No generic Auto Select inference was accepted across
tracks.

### 2026-10-01 11:xx UTC — R2 float guard

**Path.** R2 derived-end/selection continuation records.

**Trigger/output.** The guard rejected `7.96` versus
`7.959999999999999`.

**Partial mutation.** No blade or repeat was dispatched.

**Diagnosis and product-absence interpretation.** Decimal formatting/equality
was too strict. This does not imply a retime or endpoint capability failure.

**Later recovery.** A bounded comparison used normalized numeric tolerance and
completed the named R2 cases.

**Success gate.** Preserve raw values but compare documented numeric values
with explicit tolerance and endpoint convention.

**Unrun experiment.** No fractional retime endpoint case was run.

### 2026-10-01 13:07–13:13 UTC — R5 no-effect menu nudge

**Path.** [evidence/r5-manual-marker-move/](evidence/r5-manual-marker-move/).

**Trigger/output.** After the operator’s marker-note change, the reviewed
Playback/nudge command returned without changing the target pair. The guard
refused the expected one-frame delta; the readback was byte-identical.

**Partial mutation.** Marker notes changed as requested; the nudge produced no
observed movement. No retry, undo, save, or unrelated mutation occurred.

**Diagnosis and product-absence interpretation.** This is a no-effect menu
observation. It does not imply Playback, nudge, or timeline move is absent.

**Later recovery.** The producer later reported a manual move. A subsequent
read-only comparison found the requested 1..200 geometry but retained Usage
and missing-pool-pass instability, so the full R5 pair remained unverified.

**Success gate.** Require a stable full pair with exact target geometry and
unrelated-field comparison after the single menu action.

**Unrun experiment.** No second automated nudge was issued; no atomic revision
or ABA test was run.

### 2026-10-01 13:25–16:20 UTC — producer move/bridge readiness stalls

**Path.** [evidence/bridge-readiness-stall/](evidence/bridge-readiness-stall/),
plus the retained independent action and
`r5-manual-move-report.json`.

**Trigger/output.** The producer’s read-only launch timed out after 10 seconds.
No injected result appeared. Later bridge calls returned Usage-only
adjacent-read refusals, an unknown current render format, and
`<no main window>`/exact-window refusals.

**Partial mutation.** No nudge, save, reopen, edit, or render was replayed.
The producer’s “moved” report was not promoted to native evidence.

**Diagnosis and product-absence interpretation.** Window/process readiness and
capture freshness were unresolved. This does not imply a Resolve API or
timeline-edit failure.

**Later recovery.** Read-only comparisons eventually established the
requested geometry, but the complete R5 acceptance still required stable pool
passes and Usage handling. The bridge was restarted without replaying the
edit.

**Success gate.** Retain process state, window title, bridge result, exact
before/after pairs, and operator reports as separate evidence classes.

**Unrun experiment.** No automated retry of the timed-out manual move was run;
the exact producer action cannot be reconstructed.

### 2026-10-01 16:55 UTC — transcript serializer failed before getters

**Path.** The producer transcript dispatch record and
`../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-dispatch-review.json`.

**Trigger/output.** The first launch failed before transcript or geometry
getters with `AttributeError: NoneType has no attribute __name__`.

**Partial mutation.** No transcription read, source-file read/hash/export,
timeline edit, save, or render occurred; configuration was restored.

**Diagnosis and product-absence interpretation.** Serializer/dispatch failure.
It does not imply transcript getters or source-word mapping are unavailable.

**Later recovery.** Serializer repair enabled a read-only test: source
transcription was returned, while the two existing timeline media-pool
proxies returned None. That bounds those objects only; it is not a universal
transcription absence claim.

**Success gate.** Validate serializer output and module pins offline before
dispatch; retain source, nested, and timeline proxy results separately.

**Unrun experiment.** No complete all-clips transcription coverage check was
run; Inbox #146 remains the required future coverage gate.

### 2026-10-01 18:56 UTC — stale editorial dispatcher pin

**Path.**
`../../../out/issue-141-observation-20260930-01a0f318/r2-picture-native-executor-result.json`
and [report.md#r2-picture-only-harness-refusal--october-1-1856-utc](report.md#r2-picture-only-harness-refusal--october-1-1856-utc).

**Trigger/output.** The R2 picture preparation completed two matching full
state reads, then the executor found that `probe.py` retained the old
`editorial-readback.py` hash. It exited 1 before getters.

**Partial mutation.** Auto Select none/V1 and deselection menus had dispatched;
no split, delete, retry, or restoration occurred, and final protected state
after those menus was not accepted.

**Diagnosis and product-absence interpretation.** Stale dispatcher-owned module
pin. This does not imply R2 picture editing is unavailable.

**Later recovery.** The pin was corrected and exact prepared-state readback
succeeded; the named picture-only case then ran once.


A separate root read-only invocation at 19:20 UTC used an unapproved
`r2-picture` readback label and refused before getters. Its raw launcher
failure is retained with the corrected approved `r2-picture-context` readback;
no split, deletion, or restoration occurred. This is the same label-contract
class, not a second Resolve failure.

**Success gate.** Validate dispatcher AST/module hashes before any menu action
and require a fresh exact pair after preparation.

**Unrun experiment.** No replay of the stale-pinned preparation is allowed.

### R5 manual launcher timeout and unknown-window continuation

The 10-second timeout and later `Project changed; stop: <no main window>`
refusals are launcher/window failures recorded above. They stopped before
injected dispatch and therefore provide no native edit result.

**Success gate.** A read-only readiness check must prove exact project title,
frontmost window, enabled menu, and `triggered=false` before one approved
continuation. **Unrun:** no automatic retry or window-switch policy was
tested.

## 4. Render, output, residual, and restoration failures

### Residual first-cut review was invoked too early

**Time/path.** 2026-10-01, first residual cut; evidence is in the issue-owned
residual continuation records and
`../../../out/issue-141-observation-20260930-01a0f318/residual-resume-native-executor-original-wording.json`.

**Trigger/output.** The genuine first split at record frame 4560 was retained,
but the driver called the full-state review before the relative approved-output
pin existed. It refused `A relative approved-output evidence pin is required`.

**Partial mutation.** First cut and selection occurred; no second cut,
deletion, final readback, save, or render occurred.

**Diagnosis and product-absence interpretation.** Harness sequencing/evidence
pin failure. It does not imply Razor, linked cutting, deletion, or rendering is
unavailable.

**Later recovery.** The continuation resumed from the retained first split,
performed the second cut at 4570, later deleted the exact middle interval, and
restored context without replaying either cut.

**Success gate.** Validate all relative evidence pins before the first native
mutation; retain phase-indexed records and exact UIDs.

**Unrun experiment.** No replay of the first cut or preparation is allowed.

### Residual second-position/selection labels

**Trigger/output.** A continuation reached the second-position checkpoint but
stopped because a deselection label was outside the approved readback list.
Later the right-tail selection did not match the intended deletion target.

**Partial mutation.** Position setter and menu preparation ran; no incorrect
deletion was made. The exact middle interval was deleted only in the corrected
continuation using explicit handles.

**Diagnosis and product-absence interpretation.** Selection label/index and
executor narrative defects. They do not imply deletion or R2 editing is absent.

**Later recovery.** The corrected driver treated observed UI selection as
diagnostic and used the explicit derived interval UIDs as deletion authority;
independent final review passed.

**Success gate.** Require exact target UID/source/range/link guards and make a
wrong UI selection refuse before `DeleteClips`.

**Unrun experiment.** No deletion using an unverified UI tail selection was
run.

### 2026-10-01 11:53 UTC — stale render range/dimensions

**Path.** [evidence/av-owned-unstarted-job-recovery/](evidence/av-owned-unstarted-job-recovery/)
and the queue records in `out/`.

**Trigger/output.** `AddRenderJob` created owned job
`9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd`, but actual metadata was 1920x1080
and MarkOut 2449 while the guard expected 640x360 and 200. It refused before
`StartRendering`.

**Partial mutation.** One unstarted job existed; recovery preset/XML and edited
timeline remained. No render started.

**Diagnosis and product-absence interpretation.** Queue guard used stale
dimensions/range. This does not imply AddRenderJob or rendering is unavailable.

**Later recovery.** The owned job was removed with exact full before/after
equality; a fresh queue derived MarkOut 9199 and later rendered once.

**Success gate.** Derive dimensions and MarkOut from the current complete state,
then compare actual job metadata before allowing one start.

**Unrun experiment.** No start of the stale 640x360/200 job was attempted.

### 2026-10-01 — full-Matrix queue dispatcher route missing

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/dispatch-registration-check.py`
and the AV continuation records.

**Trigger/output.** The first registered continuation lacked its runtime
dispatch route and silently returned observation-only results. No native render
start occurred.

**Partial mutation.** Earlier attempts reached preset export/settings and
refused before `AddRenderJob`; the route-missing invocations added no native
mutation.

**Diagnosis and product-absence interpretation.** Dispatcher registration
defect. It does not imply queue or rendering absence.

**Later recovery.** The route was added and a registration regression covered
all owned aliases. The actual owned job was then started exactly once.

**Success gate.** Validate route presence and action/route consistency before
registration; reject non-observe actions with no route.

**Unrun experiment.** No silent observation-only invocation may be promoted to
native evidence.

### 2026-10-02 — render poll menu unavailable and caller wait expired

**Path.** `cli-av-owned-render-resume-result.json` and retained render
continuation records under `out/`.

**Trigger/output.** The first poll could not find the approved Observation
menu while rendering and stopped. A resume-only call later observed Complete
100% without a second start. A separate queue caller’s wait expired, but its
same-job result was recovered without replay.

**Partial mutation.** One owned job had already started; no second
`StartRendering` was issued. Output and final restored pair were retained.

**Diagnosis and product-absence interpretation.** Menu/window availability and
caller wait behavior. This does not imply an incomplete render or missing
render API.

**Later recovery.** Same-job continuation observed completion; the generated
MOV was retained and independently analyzed.

**Success gate.** Bind job UID, one-start count, terminal status, output hash,
and restored pair; resume only with `resumeExistingJob=true`.

**Unrun experiment.** No second start or duplicate output was attempted.

### 2026-10-02 — first PCM analyzer failed upstream

**Path.** `pcm-real-render-analysis.json` lineage and the retained analyzer
worker record.

**Trigger/output.** The first PCM analyzer ended on upstream HTTP 502/503 before
extraction/comparison.

**Partial mutation.** No Resolve call, render, source read, or output rewrite
occurred; no analyzer artifact was produced by that worker.

**Diagnosis and product-absence interpretation.** External analyzer transport
failure. It does not imply render, PCM extraction, or speech analysis is absent.

**Later recovery.** An offline replacement used the retained generated MOV and
produced the reviewed six-case waveform result; the render was not repeated.

**Success gate.** Bind the analyzer input/output hashes and distinguish
transport failure from parser or waveform verdict.

**Unrun experiment.** No second online analyzer call was issued.

### Outer render restoration registration and worker failure

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/cli-outer-native-once-result.json`
and the outer-recovery review.

**Trigger/output.** Registration was rejected because the helper counted
original journal reads without actually reading format/mode after loading the
preset; its fake client lacked those getters. The first correction worker then
failed upstream 502 without editing or calling Resolve.

**Partial mutation.** None from the rejected registration or failed worker.

**Diagnosis and product-absence interpretation.** Review/fake-client coverage and
transport defects. They do not imply preset loading, restoration, or rendering
is unavailable.

**Later recovery.** The helper was corrected to read format/mode twice and
refuse wrong values before deletion. A later native restoration loaded and
deleted the owned preset with MOV/H264/mode 1 and exact final pair equality.

**Success gate.** Read actual post-load settings twice, compare final settings
before deletion, and bind preset ownership and final pair.

**Unrun experiment.** Hidden render fields remain unobservable; no claim of
complete hidden-setting equality is allowed.

### 2026-10-02 — held-mute restoration first refused on render page

**Path.** `mute-render-existing-job-completion-summary.json`,
`mute-pcm-comparison-result.json`, and
`audio-mapping-restore-summary.json`.

**Trigger/output.** The post-render restoration readback refused its
Edit/empty-queue guard while Resolve remained on the render page.

**Partial mutation.** The held A2 source-mapping mute had already rendered; no
additional render or restore setter was issued on the refusal.

**Diagnosis and product-absence interpretation.** Page/queue guard state. It
does not imply mute restoration or mapping setters are unavailable.

**Later recovery.** One approved Edit-page action preceded one A2 restore; the
fresh complete pair exactly matched the original. The held-mute output PCM was
byte-identical to baseline, so the mapping flag did not prove program silence.

**Success gate.** Restore only after Edit/idle/empty-queue readiness and compare
the complete pair; treat mapping mute and audible program output as separate
claims.

**Unrun experiment.** No generalized bus/routing or live-monitor audibility
test was run.

### 2026-10-02 — Fairlight Solo observation menu disabled

**Path.** Fairlight operator/queue/render records under `out/`.

**Trigger/output.** Operator reported A2 Solo on, but output/bus labels were not
visible. The same-job follow-up could not dispatch because the observation menu
was unavailable/disabled while rendering.

**Partial mutation.** Queue setup issued zero starts; the separately authorized
render issued exactly one start. No second start or Solo-state setter was
issued.

**Diagnosis and product-absence interpretation.** Routing labels and collector
visibility were unknown; menu availability was transient. This does not imply
Solo, routing, or render capability is absent.

**Later recovery.** The existing job completed; offline comparison found zero
A1/A3 control output and retained A2 waveform under the operator-reported Solo
state. Solo-off was later restored with exact full-state equality.

**Success gate.** Bind operator state, job UID, one-start count, generated PCM,
and exact restored pair. State only the named output controls tested.

**Unrun experiment.** Complete Fairlight bus routing and collector-backed Solo
getter coverage remain unrun.

## 5. Final reopen, duplicate, and restoration failures

### 2026-10-02 12:13–12:22 UTC — transient Usage refusal after reopen

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/r1-reopen-final-independent-review.json`.

**Trigger/output.** Save/close/load each returned success. The first post-load
capture refused eight Usage differences between adjacent reads; stable pool
reads remained available. A later pair was stable, with only eight
Resolution 0x0→1920x1080 reads on producer-timeline proxies.

**Partial mutation.** No replay, edit, duplicate, or save followed the first
refusal.

**Diagnosis and product-absence interpretation.** Transient Usage/Resolution
readback. This does not imply reopen or project persistence failure.

**Later recovery.** The stable pair was accepted for the final duplicate preflight;
the remaining selection-signature guard exposed a separate context issue.

**Success gate.** Retain every transient pair and require a later stable pair
with an explicit explanation of all deltas.

**Unrun experiment.** No atomic snapshot, revision-token, or ABA-exclusion
experiment was run.

### 2026-10-02 12:22 UTC — second duplicate stopped on selected-context fields

**Path.** `r1-repeat-duplicate-20261002T122220.047704Z` and
`../../../out/issue-141-observation-20260930-01a0f318/r1-selected-context-local-repair.json`.

**Trigger/output.** Before `DuplicateTimeline`, the guard reported
`selected R1 source signature changed; no duplicate attempted`. Switching
between R1 and Matrix changed active/inactive track enabled/locked getters and
eight audio dialogue/voice property-presence fields.

**Partial mutation.** No duplicate, save, or cleanup occurred.

**Diagnosis and product-absence interpretation.** The structural comparator
included context-sensitive inactive getters. This does not imply duplicate
capability or source identity changed.

**Later recovery.** The repair excluded only those known context-sensitive
fields while retaining all identity, source, range, record, marker, link,
enablement, and unlisted-property guards. Independent restoration then selected
Matrix and the final duplicate created six new occurrence IDs.

**Success gate.** Capture source/structure in the same selected timeline
context, document excluded context fields, and independently review the
projection before native duplicate.

**Unrun experiment.** No cross-context universal getter equality experiment was
run; inactive getters remain unknown for control/effect claims.

### 2026-10-02 12:54 UTC — selection-restoration launch had no main window

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/independent-action-20261002T125424.498570Z/launch.json`
and `r1-restoration-menu-refusal-independent-review.json`.

**Trigger/output.** The fixed macro passed its first project-window guard, then
refused `Project changed; stop: <no main window>` before selecting the
integration menu.

**Partial mutation.** No injected result, selection setter, duplicate, or save
followed.

**Diagnosis and product-absence interpretation.** Window availability changed
between checks. This does not imply SetCurrentTimeline or duplicate support is
absent.

**Later recovery.** Read-only readiness found the exact title and enabled menu;
one bounded continuation then executed exactly one SetCurrentTimeline(Matrix)
and restored complete pair/context equality.

**Success gate.** Require one fresh readiness check, one bounded invocation, and
a complete post-selection pair before any duplicate.

**Unrun experiment.** No automatic retry after a missing-window refusal was run.

## Automated validation caveat

The first independent full validation exited in the contracts Vitest lifecycle
without an available assertion. The isolated pinned-contracts rerun then passed
all 141 tests without code or test repair, and the subsequent full pinned
validation passed all 175 Python tests. An intermediate Ruff run stopped on one
overlong error-message line; splitting the same literal fixed that lint issue,
and the full validation rerun passed. These are validation-harness events, not
Resolve or product failures. Retain the first exit as unexplained evidence;
never summarize it as a failing product test.

## Evidence-retention gaps and replication rules

The following gaps materially affect how a future engineer should reproduce or
interpret the run:

1. **Retain failed preflight state before raising.** The 18:12 baseline
   refusal retained the result and hashes but not the raw current before-state.
   The 19:42 unexpected project was identified but not inspected. Future
   preflight failures need project UID/name, page/window, two full pairs, and
   normalized diff before the guard raises.
2. **Retain source-list shape.** The 21:49 matrix refusal omitted the raw
   list type/value/count. A message saying “unreadable” is insufficient to
   distinguish API shape from unreadable content.
3. **Record mutation phase and partial state.** The R4 path-list append,
   start-timecode repair, render job creation, and residual cuts all prove why
   “refused” must carry a phase-indexed journal and a read-only continuation
   plan. Never replay a phase whose successful result is already retained.
4. **Do not trust wrapper narratives over native phase records.** The boundary
   base wrapper timed out at 30 seconds while PID 38693 remained alive; the
   process was monitored to terminal, but the wrapper exit code is unavailable.
   The A3 executor narrative used preparation deselection as final context; the
   corrected raw final pair is authoritative.
5. **Keep output/analyzer failures separate.** The first PCM analyzer failed
   upstream 502/503 before extraction. A later offline analyzer produced the
   result. The failed worker is not a missing render artifact or a negative
   waveform verdict.
6. **Bind paths and hashes without exposing private paths.** Published evidence
   must use issue-local relative links and preserve raw/public hash bindings.
   Protected real-media locator/hash access remains false in the retained
   reviews.
7. **Separate observed absence from unobserved fields.** Unknown page,
   format, routing, Fairlight bus, inactive getter, or timeline proxy values
   must remain unknown. A getter that returns no data for one context is not a
   product-absence finding.
8. **Use one phase, one owner, one recovery.** Native actors must be
   single-dispatch, action-specific, and resume from retained state. A wait
   timeout or missing menu must not trigger a second start, duplicate, cut,
   save, or cleanup.

## What a successful follow-up must prove

A follow-up can close a named handoff item only when it has:

- an exact UTC timestamp and action/configuration hash;
- a complete preflight pair with page, project, selected timeline, queue,
  locks, source IDs, occurrence IDs, and relevant settings;
- a phase-indexed native journal showing the exact setter/operation and return;
- an explicit partial-state record if any later guard refuses;
- a complete postflight pair with only the allowlisted expected deltas;
- independent review of the raw pair and wrapper/native binding;
- a recovery pair that proves the owned state was restored where required; and
- a plain-language claim limited to the tested synthetic case.

No listed harness failure establishes Resolve/product absence or a failure of the
core script-to-timeline authoring workflow. The successful baseline, saved
114-item Matrix, bounded R3 samples, R4 relink/offline cycle, authored boundary,
generated render, and final duplicate all demonstrate that the investigation
reached native operations when their preconditions and evidence contracts were
correct. Their limits remain explicit: no general effect visibility, lineage,
complete mixer routing, universal audibility, fractional endpoint semantics,
atomic revision token, or protected-media access is claimed.

