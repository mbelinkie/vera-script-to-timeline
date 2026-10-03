# Issue 149 Workflow Integration discriminator plan

Task #149. This is a bounded native follow-up to Claude's discriminating tests.
It is preparation only until the root actor stages one reviewed configuration
and selects the existing menu entry. No native action is implied by this file.

## Scope and boundary

Use one new disposable project named `VERA Issue 149 WI Discriminators
20261003-kit-02` and output directory
`out/issue149-workflow-discriminators-20261003-kit-02`. Resolve must report
Studio `21.1.1.10` for a comparable run, and the producer attests
`externalScriptingSetting: "None"`. Use only synthetic fixture files copied
into that output directory. Do not open or mutate the retained #141 project,
`semi1b.mp4`, production files, contracts, fixtures, goldens, or dependencies.

The existing registered menu remains the entry point:
`Workspace → Workflow Integrations → VERA Issue 149 Workflow Reruns`. The
adapted launcher uses Resolve's injected `resolve` object and the same menu;
it never imports `scriptapp` or starts an external bridge. The launcher path
must be the real installed path under `.../DaVinci Resolve/Workflow
Integration Plugins/`; the older `.../Resolve/Workflow Integration Plugins/`
path is invalid. The configuration is disarmed atomically before the one
native action. A timeout or incomplete result is collected and diagnosed; it
is never replayed.

## Fixture shape

The W3 timelines each contain the exact `codex-rerun.md` geometry at 25 fps,
1920×1080, 48 kHz, start timecode `00:00:00:00`:

| Track | Media and range |
| --- | --- |
| V1 + linked A1 | `base.mov`, `[0,400)`, video source ID 1 plus A1 NATO words and 1000 Hz pilot |
| A2 mono | `a2_numbers.wav`, `[0,400)`, eight number words and 1500 Hz pilot |
| A3 mono | `a3_bed.wav`, `[0,400)`, bed and 2000 Hz pilot |

`CreateEmptyTimeline` supplies V1/A1. The build phase adds exactly two mono
audio tracks and appends the three placements with `endFrame = 399`.
`SetCurrentTimeline` and the resulting UID are recorded. Each W3 case has a
fresh timeline; a neutral control timeline may be rendered separately before
case 1, but case 1's target itself must never be rendered before its mute.

The W6 timelines use the same video/audio layout, with `swap.mov` (a byte
copy of `base.mov`) as the imported source. The replacement `relink_alt.mov`
must contain video plus one mono 48 kHz PCM stream. A replacement without an
audio stream is refused because it previously hung Resolve.

## W3 cases

Use `select-timeline` with `page: "edit"` before each target. The A2 item is
muted by `w3-mapping-mute` with `mappingTrackKey: "1"`; this is the source
channel key for the standalone mono A2 item. The action must retain the exact
original mapping, set only `track_mapping.1.mute`, and record the immediate
getter readback.

1. **D3-direct / never rendered.** Dispatch `w3-mapping-mute` with the fixed
   render settings in the same action. There is no baseline render of this
   target. Poll its one attributed job.
2. **D3-console.** Dispatch `w3-mapping-mute` without a render configuration.
   Leave the mapping untouched. The operator uses Workspace → Console to
   render once with the same settings and the documented
   `SetCurrentRenderMode(1)` method, then returns to the injected path for an
   `observe` snapshot. The Console action must not call the nonexistent
   `SetRenderMode`.
3. **D3-operator.** Dispatch `w3-mapping-mute` without a render. The operator
   opens and verifies the Fairlight page only, with no clip, mapping, M/S, or
   playhead changes. Then dispatch one Workflow Integration `render-stage` and
   poll its job. A two-second playback is an optional separate experiment and
   is not part of this page-only case.

For every case, retain the complete pre/post pair around the mapping action,
the operator observation pair where applicable, the render job and terminal
poll, full output SHA-256, decoded frame check, A2 1500 Hz pilot, and number
word list. Silence passes only when pilot ≤ `0.001` and `one` through `eight`
are absent while the A1 control words and video source identity remain valid.

After each case, dispatch `w3-mapping-restore` with the exact original mapping
returned by its mute result. Render once after restoration and compare the
restored PCM and mapping to the **original pre-mute snapshot**, not merely to
the immediate mute→restore pair. The immediate restore pair is still retained
to prove the setter call, but it cannot prove that unrelated state survived.
The independent comparison may allow only attributable render-queue entries
and explicitly documented page/playhead/settings/context changes; unexpected
snapshot differences remain failures or unknowns.

## W6 cases

Build a new timeline for each case and render a baseline before replacement so
the source-ID comparison is attributable. Before each swap, retain a
`w6-before-swap` guard and the original file hash, byte size, and `st_mtime_ns`.
The root actor owns the file operation in the new output directory:

```python
replacement = Path(".../media/relink_alt.mov")
target = Path(".../media/swap.mov")
temporary = target.with_name(".swap.mov.discriminator.tmp")
shutil.copyfile(replacement, temporary)
descriptor = os.open(temporary, os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
os.replace(temporary, target)
```

The kept-time case applies `os.utime(target, ns=(original_atime_ns,
original_mtime_ns))` after `os.replace`. The changed-time case applies the
same operation with a demonstrably greater `mtime_ns` (for example, the
original value plus one second) and retains the before/after stat records.
The actual actor should use a safe open/close sequence and retain the file
operation journal; the snippet is a procedure description, not a dispatch.

4. **D6-kept.** Replace atomically and restore the original modified time.
   Dispatch `w6-after-swap` as a read-only replacement-hash guard, then
   `w6-relink-render`. The required result is `RelinkClips` returning true,
   a completed render, and decoded source ID 1 (old bytes). Restore original
   bytes and time, relink, render, and save once.
5. **D6-changed.** Use a new W6 timeline. Replace atomically, then set a new
   modified time. Dispatch the same guard and relink/render sequence. The
   required result is decoded source ID 2 from the replacement. Restore the
   original bytes/time, relink, render source ID 1, and save once.

The harness rejects audio-less or non-mono replacements, verifies the expected
hash before every W6 action, and never copies, deletes, or relinks a path
outside the owned media directory. Online status and Date Modified are
reported as observed API fields; neither is treated as byte identity.

If Resolve is currently showing an earlier disposable #149 project, the
creation config may use `creationGuard: {"mode": "known-disposable",
`"projectName": "VERA 149 Discriminators 20261002-b"` (or the retained
`VERA Issue 149 Workflow Reruns 20261002-kit-01`), the exact project UID, and
`"allowedProjectNames": ["<same exact name>"]`. The harness reads only that
project’s name, UID, render queue and `IsRenderingInProgress`; for every queue
row it calls the documented `Project.GetRenderJobStatus(JobId)` getter and
retains the returned state in the guard result and journal. It permits
already-terminal queued jobs and refuses active/unknown jobs. The allowlist
must identify a known synthetic #149 project and must never name the retained
#141 project or a production project. It performs no cleanup, save, timeline
read, or mutation on the prior project before `CreateProject`.

## Evidence and classification

Every mutating or render-stage action must retain an exclusive dispatch
receipt, the disarmed configuration hash, `journal.jsonl`, `pre.json`,
`post.json`, result JSON, render job ID, terminal poll, and output hash. Local
analysis uses `analyze.py` and `analysis-check.py` from this directory plus
the retained fixture analyzer. A native setter return is never a media result.

Each case is classified `reproduced`, `adverse`, `unknown`, or `harness
failure` using the #141 new-result template. A missing injected object,
unattributed output, incomplete pair, unsafe file state, or probe failure is a
harness/observation issue until diagnosed; it is not a Resolve capability
claim. Only if both W6 required source-ID outcomes match may the report adopt
the bounded design input: detect replacement by content hash, force reload
with changed modified time, call `RelinkClips`, and verify through a render.
Issue #149 remains open for producer review.

## D3-console command and guard

After the Workflow Integration `w3-mapping-mute` result is terminal and the
mapping readback is retained, write one config at
`out/issue149-workflow-discriminators-20261003-kit-02/params/d3-console-render.json`
with `schemaVersion: "issue-149-console-render-v1"`,
`action: "console-render"`, `phase: "d3-console-render-<unique>"`, a unique
`actionId`, the exact project/timeline/project UID, the owned output path, and
the fixed `render.settings`. It must also include
`consoleSourceSha256` for `console-render.py` and `harnessSourceSha256` for
`harness.py`; the helper verifies both before creating progress evidence or
disarming the config. Record its config SHA before the operator uses
this single Console command:

```python
exec(compile(open("REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", encoding="utf-8").read(), "REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", "exec"), dict(globals(), __file__="REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", CONSOLE_CONFIG_PATH="REPOSITORY/out/issue149-workflow-discriminators-20261003-kit-02/params/d3-console-render.json"))
```

The helper consumes Resolve's injected `resolve`, verifies the exact project,
current timeline, owned IDs and `externalScriptingSetting: "None"`, captures
`pre.json`, calls `SetCurrentRenderMode(1)` plus the fixed format/settings,
adds and starts exactly one returned render job, polls that same job, and
captures `post.json`. It never calls `SetSourceAudioChannelMapping` and never
replays a timeout. Before any native render call it exclusively creates the
action progress/evidence directory and atomically replaces the config with a
`__disarmed__` copy. An existing result, progress file, evidence directory,
wrong project/timeline, wrong hash, or missing injected object stops before
native mutation. The helper source is `console-render.py`; retain its SHA-256
with the config and command receipt.

## Producer checkpoint exception and remaining closeout

The producer requested a stop after the first direct muted render. Its original mapping and complete captured state were restored and saved, but the planned direct post-restoration render was not run. On resume, the fresh Console case was already muted/staged before that extra output check could be scheduled. Preserve the active Console test. After the operator cases are complete and restored, perform the unique direct post-restore output check if continuing the full plan; do not replay the direct mute or call snapshot restoration program-output verification.

## Final closeout completed

The historical direct restored-output exception above is closed by job `de6df76f-a57b-4642-aafd-75fa30955a2d`, independently analyzed with 399 source-ID-1 frames, expected pilots and all eight number words. All five outcomes, each restored output, and the final equal-pair save are retained in [final-summary.md](results/final-summary.md) and [final-checkpoint-review.md](results/final-checkpoint-review.md). Native actions are stopped and configs disarmed. #149 remains open for producer review.
