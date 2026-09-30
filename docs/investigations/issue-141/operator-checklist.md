# Issue 141 — External operator checklist

## Historical preparation actions

The initial launch and guarded continuation below are historical. The first two
runs failed before import; baseline preparation then succeeded on the third run.
The retained project is `VERA Issue 141 Synthetic Probe 20260930-01a0f318`, with
baseline timeline `VERA 141 Baseline`. The operator confirmed for that run that
External Scripting stayed None and only the named synthetic project/generated
media were touched. No need to repeat preparation.

### Initial launch (historical)

The original Project Manager launch created the named project and initially
stopped at its settings check. Its journal and failure remain in
`evidence/attempt-1/`.

### Guarded continuation after the second failure (historical)

The staged continuation required Playback frame rate 25, set writable
timeline/storage settings, imported only generated synthetic inputs and created
the baseline. It ran successfully. The failed earlier attempts remain retained
with their hashes.

## Current next action — compare selected and inactive timeline readback

The native duplicate succeeded at 20:44:38 UTC. `VERA 141 R1 identity` is
selected and saved; no duplicate rerun is needed. Its six occurrence UIDs are
new and source-media UIDs are shared. The operator's standing confirmation is
External Scripting None and synthetic-only scope; do not repeat the mode question.

The inactive baseline's track-enabled readings changed and eight audio-property
keys are absent. A selection-only capture comparison is being prepared to test
whether those readings depend on the active timeline. Keep the existing timeline
contents unchanged. Wait for the staged action; no operator action is currently
required. Matrix preparation must preserve those uncertain readings as unknown
until this comparison resolves or explicitly bounds them.

## Historical successful cache restoration and duplication

At 20:17:34 UTC the operator reopened the named Synthetic Probe project. The
retained two-pass capture matches the original baseline except for
`perfCacheClipsLocation` at the project and timeline settings: both return
`CacheClip` instead of the baseline-owned cache location. Its resolved target is unknown. The
identity guard refused before duplication; no native journal or mutation exists.
See `evidence/native-reopen-cache-refusal/`. This is one bounded manual reopen
observation; it does not show that API `LoadProject` works. The operator confirmed
External Scripting None and synthetic-only scope for this run.

Exact-cache-only restoration is reviewed and staged, bound in
`installation-cache-restoration-native-duplicate.json`. It uses the same
one-dictionary writable setter as preparation. Only the precise two-field
`CacheClip` difference is accepted; any additional change refuses before
mutation. After restoring the pinned slice-owned cache setting, two fresh
complete raw passes must match the baseline before duplication.

Use only `VERA Issue 141 Synthetic Probe 20260930-01a0f318`, leave baseline
contents unchanged, keep External Scripting None, and launch
Workspace → Workflow Integrations → VERA Issue 141 Observation once.
Expected result: `VERA 141 R1 identity` becomes the current timeline and the
project is saved. Stop on refusal or no visible result; do not rerun or clean up.
Record the visible result and None/synthetic-only confirmation.

The cache restoration and duplicate-only action passed focused checks and
independent safety review, then ran successfully. Do not rerun it.
Earlier 18:12 and 19:42 refusals
remain retained; the former has no capture, and the latter stopped after Resolve
reported a different current project ID. Neither establishes behavior of an
unknown/default project.

The probe retains the observed bounds. Duration convention and overlay placement
need separate calibration before sample or visibility timing claims.

## Recording each later operation

### Batched operator sessions

These eight batches group the existing evidence checks; they are not eight
completed or already staged launches. The identity/duplication checkpoint has
one observed success. The labeled matrix timeline must be assembled
and its actual placement captured before the later grouped edits begin.

| Batch | Checks answered together | Manual intervention |
|---|---|---|
| 1. Reopen and native identity | R1 reopen/duplicate; R5 reopened markers/ranges/settings | Reopen and one native duplicate are observed; no rerun. |
| 2. Calibrate and prepare the matrix | Active-timeline getter context; actual duration/overlay placement; before-state for separate labeled cases | Launch the reviewed context comparison and audited matrix preparation when staged; inspect named bounds/frames. Agent verifies every case before editing. |
| 3. Local identity edits | R1 trim, move, razor and copy on separate case occurrences | Perform the four labeled edits together, then one observation capture. |
| 4. Speech edit cases | R2 linked/unlinked/picture-only/partial cuts, residual track, offset, retime and boundary precision | Edit separate labeled speech cases, then capture them together; record routing/listening evidence as required. |
| 5. Picture and structure | R3 opaque/transparent/effect/disabled cases, Graphic merge, exact boundary and crossing bed | Edit/view the labeled cases together, then one capture. Viewer samples and unknown effects remain explicit. |
| 6. Shared audio/media state | R2 mute/solo/output routes; R4 unlink/relink/wrong bytes/remove; R3 offline | Use separately staged transitions with before/after captures. Global mix and shared-source changes cannot be proved from one final state. |
| 7. Repeat and freshness | R1 repeated results; R5 marker/clip edits, reopen and inconsistent capture | Perform the bounded repeat/marker/move/race checkpoints; retain each changed state. |
| 8. Evidence review and acceptance | Final R1–R5 classifications and External scope confirmation | Review the retained report and confirm the required operator attestations. |

The unchanged baseline remains the reference. A batch has one retained before
state and one retained after state only when its individual edits affect
separate, identified cases. Do not run future batches before their staged steps
are supplied. Recovery refusals can require additional launches; batch count is
not a time estimate.

Use only the named new project. Agent sets the observation `stage` label before
each launch. Capture **before** the batch, perform exactly its named edits on
separate cases, then capture **after** with the same Workflow Integration. Record exact
timecodes/source bounds, settings, viewer/listening observations and capture
filenames in `operator-record.md`. Do not perform the next edit until the
previous batch capture is retained. Keep `VERA 141 Baseline` unchanged; the
labeled matrix and any state-transition duplicate begin `VERA 141 `.

The successful native `DuplicateTimeline` call tested timeline
duplication itself; appending equivalent clips would not establish that behavior.
Copy/paste remains a separate R1 editorial probe. Every operation is audited by
its named action, before/after captures and operator record; no general UI
automation is used.

## R1 — identity and editorial survival

The following edits are planned case-local operations. The matrix layout will
supply absolute timeline coordinates after its placement is captured. Trim,
move, razor and copy use separate case occurrences, sharing one before/after
batch capture; these are not sequential changes to the same linked clip.

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R1-reopen | One manual reopen capture is retained; cache restoration subsequently matched the original raw baseline. | IDs, ranges, markers/custom-data and other properties match the raw baseline; API `LoadProject` remains untested. |
| R1-duplicate | One successful `DuplicateTimeline` created `VERA 141 R1 identity`; both timelines and saved state are captured. | Six new occurrence UIDs, five shared media UIDs and matching copied markers/ranges. Copied authoring data alone never proves a unique occurrence binding. Inactive baseline track/audio-property readings require context comparison. |
| R1-trim | Trim the linked trim-case occurrence's right edge by 25 frames without ripple, using its actual captured end. | End/duration changes with observed UID/custom-data survival or loss. |
| R1-move | Move the separate linked move-case occurrence 25 frames later without ripple. | Record position changes separately from source identity; no sort-order binding. |
| R1-razor | Blade the separate linked razor-case occurrence at local frame 100; do not remove either piece. | Both children, UIDs, source ranges, link groups and inherited marker data; never assume either child retains the logical parent's identity. |
| R1-copy | Copy/paste the separate linked copy-case occurrence at its staged nonoverlapping record location. | Original versus copy UIDs and marker data; copied signatures/metadata may be ambiguous. |
| R1-repeat | Save/close/reopen R1 timeline's project and capture again; repeat duplicate operation on a second named duplicate. | A bounded repeat either matches the rule or pinpoints which IDs/data vary. |

## R2 — word boundaries and complete audio

Each independent edit starts in its own labeled matrix section with captured
before-state; table frame offsets are local until the actual layout is staged.
Shared mute/solo and routing transitions retain separate captures. Speech is four copies of the
same isolated synthetic “echo”; reference half-open nonzero PCM sample ranges
at 48 kHz: `[19210,36258)`, `[115210,132258)`, `[211210,228258)`,
`[307210,324258)`. These are actual source waveform ranges, not derived end
times or proof of program omission. A 25 fps frame is 1,920 samples. Audio
subframe units/precision must be verified against the source before conversion.

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R2-linked-cut | In the linked-cut case, blade linked V1/A1 at local frames 60 and 70; remove only that 10-frame interval without ripple. | Second word's full source support lies inside `[115200,134400)`. Capture source/record intervals and links. Do not claim deletion until routing and program omission are complete. |
| R2-unlinked-cut | In the separate unlinked case, unlink V1/A1, make/remove the same interval only on A1. | Audio cut differs from picture. Neither link status nor picture establishes speech removal. |
| R2-picture-only | In the separate picture-only case, unlink and make/remove the interval only on V1; leave A1 intact. | Second word remains audible; never classify this as word deletion. |
| R2-partial | In the separate partial case, cut A1 at local frame 65 and remove only local frames 65–70. | A residual part of the second word remains before source sample 124800. Preserve the word; report partial removal. |
| R2-residual-track | In a separate residual case, make the linked cut and enable A2's full repeated-speech occurrence. | Second word remains on A2 despite A1's cut. Retain all tracks, source mappings and observed bus/output assignment. |
| R2-disable-mute | Record A2 enabled, then disabled; separately record track mute and any solo state. | Compare public enable/property/mapping values with Fairlight UI and audible program. A disabled item, muted track, silent channel and deleted occurrence are distinct. |
| R2-offset | In the separate offset case, unlink A1 and shift it one frame (1,920 samples) later without changing source bounds. | Record/source time mapping changes; no assumed synchronization. |
| R2-retime | In the separate retime case with expansion space, set linked clip speed to 50%, record actual pitch/ripple options, then capture. | Read speed and source map; unknown time warps/effects block exact word inference. Do not assume a constant map from one duration. |
| R2-derived-end | Compare raw integer/subframe/source-time readbacks to the four exact support ends above. | Quantify precision/units. A rounded or inferred end cannot prove a complete sample omission. |

For every R2 result record all audible tracks, channel mapping, buses/sends,
mute/solo, effects and program-output assignment in the Fairlight view. Unknown
routes stay explicitly unsupported. #110's unavailable PCM-WAV rendering on
21.1.0 build 14 is a limit, not permission to assume rendered audio exists.
Any needed program render must first be staged as a bounded audited operation
and verified from actual output. Do not invent sample-exact program proof from
listening, method names or source ranges alone.

## R3 — visibility and structural boundaries

Independent visibility edits use separate labeled matrix cases. Inspect the
actual staged frame coordinates; the table's frame numbers are case-local.
The crossing-bed before/after transition still requires its two captures.

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R3-opaque | In the opaque case, enable V2 cutaway; leave V3 disabled. Inspect local frames 49, 50, 99, 100 after placement calibration. | Viewer shows actual opaque cutaway and return, if supported; retain enable/properties/source values. Track height alone is insufficient. |
| R3-transparent | In a separate transparent case, enable V3 overlay. Inspect calibrated overlap and base-return samples. | RGBA overlay is translucent; underlying program remains visible. Record actual compositing mode/opacity. |
| R3-effect | In a separate effect case, add one identified Inspector/OpenFX effect to the synthetic overlay; record exact name, version and settings. | Raw effect-related getters plus actual viewer result. Unknown effect behavior is opaque/manual, never flattened or called safely observable. |
| R3-disabled | In separate disabled cases, disable cutaway and overlay respectively, retaining their before/after states in the batch capture. | Disabled but present remains an occurrence. |
| R3-offline | Use the later bounded R4 unlink operation for synthetic picture only; leave its occurrence present. | Offline status differs from disabled/deleted and from available lower-track video. Do not infer visibility from layout. |
| R3-merge-graphic | In the separate Graphic case, blade V1/A1 at local frame 100 and retain both halves beneath enabled V3. Treat the two recorded halves as the proposed row-regrouping example. | Keep source audio edit and Graphic separate. No ScriptDocument row is mutated; this is observation evidence only. |
| R3-boundary | At the boundary case's exact local-frame-100 marker, blade all linked base A/V; first leave A3 uncut, then capture; subsequently blade A3 at the marker and capture. | First case has a crossing bed. All crossing media must be established before a structural interpretation; an arbitrary razor is never a section boundary by itself. |

Viewer/limited render evidence can establish only named samples/conditions. It
does not expose a general effects graph or prove every pixel/frame's visibility.

## R4 — asset identity, availability and disappearance

These operations wait for baseline identity readback and individually staged,
audited Workflow Integration commands. Do not rename or overwrite files in
Finder or use an external script as a substitute.

1. Capture `VERA 141 R4 media`; unlink only its synthetic `base.mov` media-pool
   item through the documented API. Capture the still-present occurrence and
   actual online-status/source readback. Original source bytes stay retained.
2. Relink that exact media-pool item to the generated `relink/base.mov` copy,
   whose bytes match the baseline hash. Retain request, API return, source/media
   identity, availability and hash readback. Locator changes do not change bytes.
3. Stage an audited replacement **at the same slice-owned locator** using the
   generated wrong-byte candidate; retain immutable originals and before/after
   hashes, then capture Resolve's readback after its explicit refresh/reopen.
   Equal filename/path does not authorize claiming unchanged asset identity.
4. Compare an explicitly removed synthetic timeline occurrence with the
   offline-but-present case on a separate duplicate. Retain media-pool and all
   occurrence readback; disappearance from one track does not imply asset or
   logical-item deletion. Restore only through a separately journaled action.

The verified and wrong-byte candidates both use filename `base.mov`. Baseline
manifest hashes remain the comparison authority; do not rewrite them to bless
the replacement. No existing or presenter original is accessed.

## R5 — repeats, markers and freshness

1. Launch read-only observation twice without editing; compare capture values
   and content fingerprints. Record any getter that changes on a quiet project.
2. Save/close/reopen only this project and repeat. One manual reopen readback is
   retained; its IDs/markers match, but the cache setting differs and blocked the
   native duplicate guard. After exact restoration, compare marker custom-data,
   identities and all source/range/settings evidence, not just item counts.
3. On `VERA 141 R5 freshness`, change the section marker's note using Resolve's
   marker editor; capture again. Then move one synthetic clip one frame and
   capture. Both edits must appear in raw evidence and change the fingerprint.
4. Perform one bounded operator edit during capture, if the capture duration
   permits it; retain both passes. A differing/incomplete read must report
   refusal. If a race cannot be reproduced, report it untested. Equal adjacent
   reads never rule out an edit-and-undo between passes or supply an atomic
   application revision token.

## External acceptance after the full matrix

Verify every R1–R5 operation has an actual readback or a retained reproducible
failure, a bounded interpretation, and a repeat. Confirm None remained None,
only this new project/generated media were used, and no existing project or
original source was touched. Review the final constraints report for truthful
unsupported/ambiguous results. Record **`Issue #141 External evidence confirmed`**
with the named project, report/capture identities and any discrepancy. That
statement cannot be supplied by the agent or inferred from automated tests.
