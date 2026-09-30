# Issue 141 — External operator checklist

## First action requested now

Historical initial launch, completed with a retained settings-check failure
before media import. **Use the guarded continuation below now.** R1–R5 still
wait for successful baseline preparation. No External acceptance exists yet.

1. Start the currently installed Resolve Studio at its Project Manager, keeping
   existing projects closed. Confirm Preferences > System > General >
   **External scripting using: None**. Leave it None. If the integration menu
   cannot be used from this state, stop and report that limitation; do not open
   another project, change scripting mode, reboot or use UI automation.
2. Select **Workspace > Workflow Integrations > VERA Issue 141 Observation**
   once. Expected: a newly created project named
   **VERA Issue 141 Synthetic Probe 20260930-01a0f318**, timeline
   **VERA 141 Baseline**, 25 fps, 48 kHz, eight seconds. Only generated synthetic
   inputs are imported. V1/A1 contain linked base picture/repeated speech;
   A2's residual-speech occurrence, V2's cutaway and V3's transparent overlay
   are disabled. A3's synthetic bed crosses the marker at 00:00:04:00.
3. Record the actual result, whether External Scripting stayed None, and
   whether only the named new project and generated media were touched. Reply
   **`141 preparation ran; None confirmed; synthetic project only`**, or give
   the first error/variation. This is preparation evidence, not acceptance.
   If the launcher reports a failure, stop; retain its journal and partial
   project. Do not rerun preparation or delete anything.

The launcher writes timestamped results beside its installed configuration and
full raw captures under the configured slice-owned output directory. The agent
will inspect those files directly; no reconstruction or screenshot is needed
for the API readback. The installed configuration switches to read-only
`observe` after successful preparation; repeated launches then capture without
editing Resolve. Missing getters may yield `incomplete-refused`; that result
must be retained, not described as a passing capability test.

## Guarded continuation after the second failure

1. Keep **VERA Issue 141 Synthetic Probe 20260930-01a0f318** open, with no
   imported media or timelines. Confirm External Scripting remains **None**.
   Do not create another project or import anything manually.
2. Open **Project Settings** using the gear at the bottom right. Under
   **Master Settings > Timeline Format**, set **Playback frame rate** to
   **25**, then **Save**. The scripting API exposes this property as read-only,
   so the agent cannot set it. If it is unavailable or disabled, stop and
   report that exact result; do not substitute another setting.
3. Launch **Workspace > Workflow Integrations > VERA Issue 141 Observation**
   once more. The staged action continues only the exact recorded empty
   project. It retains current settings and verifies 25 fps playback before
   applying writable timeline/storage settings individually with readbacks,
   then imports the synthetic media and creates **VERA 141 Baseline**.
   Expected: eight seconds at 25 fps / 48 kHz with the tracks/marker above.
4. Reply **`141 continuation ran; playback 25; None confirmed; synthetic project only`**, or
   give the visible result/error. If it still looks unchanged, the agent will
   read its new timestamped result directly. Do not repeatedly launch on a
   failure, delete the project, open an existing project or change scripting.

Both the initial `25.0` versus `"25"` failure and the read-only setting refusal
remain retained with their hashes. This action does not accept R1–R5; it only
prepares their baseline.

## Recording each later operation

Use only the named new project. Agent sets the observation `stage` label before
each launch. Capture **before** the operation, perform exactly the named edit,
then capture **after** with the same Workflow Integration. Record exact
timecodes/source bounds, settings, viewer/listening observations and capture
filenames in `operator-record.md`. Do not perform the next edit until the
previous capture is retained. Keep `VERA 141 Baseline` unchanged; make each
probe on an explicitly named duplicate beginning `VERA 141 `.

UI duplication and copy/paste are actual editorial probes. Appending equivalent
clips through the API would not establish their behavior. An operator edit is
audited by the named operation, before/after captures and operator record; no
agent general UI automation is used.

## R1 — identity and editorial survival

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R1-reopen | Capture baseline; save; close only this new project in Project Manager; reopen it; capture again. | Compare project/timeline/item/media UIDs, custom-data and ranges. Report actual changes; stable is not assumed. |
| R1-duplicate | Duplicate baseline as `VERA 141 R1 identity`; capture both. | Identical source/track/range signatures now exist in two timelines. Preserve all UIDs and copied custom-data. Copied authoring data alone never proves a unique occurrence binding. |
| R1-trim | On R1 timeline, trim the right edge of linked V1/A1 from 00:00:08:00 to 00:00:07:00 without ripple. | End/duration changes with observed UID/custom-data survival or loss. |
| R1-move | Move those linked items from frame 0 to frame 25 (00:00:01:00) without ripple. | Record position changes separately from source identity; no sort-order binding. |
| R1-razor | Blade V1/A1 at record 00:00:04:00; do not remove either piece. | Both children, UIDs, source ranges, link groups and inherited marker data; never assume either child retains the logical parent's identity. |
| R1-copy | Copy/paste one linked piece at a nonoverlapping record location. | Original versus copy UIDs and marker data; copied signatures/metadata may be ambiguous. |
| R1-repeat | Save/close/reopen R1 timeline's project and capture again; repeat duplicate operation on a second named duplicate. | A bounded repeat either matches the rule or pinpoints which IDs/data vary. |

## R2 — word boundaries and complete audio

Each test starts on its own baseline duplicate. Speech is four copies of the
same isolated synthetic “echo”; reference half-open nonzero PCM sample ranges
at 48 kHz: `[19210,36258)`, `[115210,132258)`, `[211210,228258)`,
`[307210,324258)`. These are actual source waveform ranges, not derived end
times or proof of program omission. A 25 fps frame is 1,920 samples. Audio
subframe units/precision must be verified against the source before conversion.

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R2-linked-cut | On `VERA 141 R2 linked`, blade linked V1/A1 at frames 60 and 70; remove only that 10-frame interval without ripple. | Second word's full support lies inside `[115200,134400)`. Capture source/record intervals and links. Do not claim deletion until routing and program omission are complete. |
| R2-unlinked-cut | On a fresh duplicate, unlink V1/A1, make/remove the same interval only on A1. | Audio cut differs from picture. Neither link status nor picture establishes speech removal. |
| R2-picture-only | On another duplicate, unlink and make/remove the interval only on V1; leave A1 intact. | Second word remains audible; never classify this as word deletion. |
| R2-partial | On another duplicate, cut A1 at frame 65 and remove only frames 65–70. | A residual part of the second word remains before sample 124800. Preserve the word; report partial removal. |
| R2-residual-track | On R2 linked, enable A2's full repeated-speech occurrence. | Second word returns on A2 despite A1's cut. Retain all tracks, source mappings and observed bus/output assignment. |
| R2-disable-mute | Record A2 enabled, then disabled; separately record track mute and any solo state. | Compare public enable/property/mapping values with Fairlight UI and audible program. A disabled item, muted track, silent channel and deleted occurrence are distinct. |
| R2-offset | On a fresh duplicate, unlink A1 and shift it one frame (1,920 samples) later without changing source bounds. | Record/source time mapping changes; no assumed synchronization. |
| R2-retime | On a fresh duplicate, set linked clip speed to 50%, record actual pitch/ripple options, then capture. | Read speed and source map; unknown time warps/effects block exact word inference. Do not assume a constant map from one duration. |
| R2-derived-end | Compare raw integer/subframe/source-time readbacks to the four exact support ends above. | Quantify precision/units. A rounded or inferred end cannot prove a complete sample omission. |

For every R2 result record all audible tracks, channel mapping, buses/sends,
mute/solo, effects and program-output assignment in the Fairlight view. Unknown
routes stay explicitly unsupported. #110's unavailable PCM-WAV rendering on
21.1.0 build 14 is a limit, not permission to assume rendered audio exists.
Any needed program render must first be staged as a bounded audited operation
and verified from actual output. Do not invent sample-exact program proof from
listening, method names or source ranges alone.

## R3 — visibility and structural boundaries

| Stage | Ordered action | Required evidence / expected discriminant |
|---|---|---|
| R3-opaque | On `VERA 141 R3 visibility`, enable V2 cutaway; leave V3 disabled. Inspect frame 49, 50, 99, 100. | Viewer shows actual opaque cutaway and return, if supported; retain enable/properties/source values. Track height alone is insufficient. |
| R3-transparent | Enable V3 overlay. Inspect overlap frames 75–99 and base-return frames 100–124. | RGBA overlay is translucent; underlying program remains visible. Record actual compositing mode/opacity. |
| R3-effect | Add one identified Inspector/OpenFX effect to the synthetic overlay; record exact name, version and settings. | Raw effect-related getters plus actual viewer result. Unknown effect behavior is opaque/manual, never flattened or called safely observable. |
| R3-disabled | Disable cutaway and overlay individually, capturing each state. | Disabled but present remains an occurrence. |
| R3-offline | Use the later bounded R4 unlink operation for synthetic picture only; leave its occurrence present. | Offline status differs from disabled/deleted and from available lower-track video. Do not infer visibility from layout. |
| R3-merge-graphic | On a fresh named duplicate, blade V1/A1 at frame 100 and retain both halves beneath enabled V3. Treat the two recorded halves as the proposed row-regrouping example. | Keep source audio edit and Graphic separate. No ScriptDocument row is mutated; this is observation evidence only. |
| R3-boundary | At exact marker frame 100, blade all linked base A/V on a fresh duplicate; first leave A3 uncut, then capture; subsequently blade A3 at 100 and capture. | First case has a crossing bed. All crossing media must be established before a structural interpretation; an arbitrary razor is never a section boundary by itself. |

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
2. Save/close/reopen only this project and repeat. Compare marker custom-data,
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
