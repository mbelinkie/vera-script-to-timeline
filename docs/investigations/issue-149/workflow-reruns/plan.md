# Issue 149 Phase 10 injected Workflow Integration harness

This directory is the issue-owned, stdlib-only source used by the producer's
new disposable Resolve project.  The harness is injected by Resolve's
Workflow Integration boundary.  It never imports `scriptapp`, starts an
external bridge, launches UI automation, changes files outside its output
directory, or selects an old project.

## Command and source contract

The root actor stages an immutable copy of `harness.py` and `launcher.py` in
Resolve's Workflow Integration Plugins directory, then selects exactly one
menu action for each configuration.  The staged configuration is
`vera-issue-149-workflow-reruns.json`; `launcher.py` reads it beside itself.
The configuration contains the absolute `probePath` and its `probeSha256`,
the exact action and unique `actionId`, and the absolute owned `outputDir`.
The launcher verifies the hash, writes the disarmed configuration atomically
before calling `harness.run`, and writes a progress record plus one result.
The root actor stages a new configuration and immutable source copy for every
next action.  Reusing an action ID or a disarmed configuration is refused.

Required common fields:

```json
{
  "schemaVersion": "issue-149-workflow-reruns-v1",
  "externalScriptingSetting": "None",
  "projectName": "VERA Issue 149 Workflow Reruns 20261002-kit-01",
  "action": "context",
  "phase": "context-01",
  "actionId": "context-01-<unique>",
  "probePath": "/absolute/staged/harness.py",
  "probeSha256": "<sha256>",
  "outputDir": "REPOSITORY/out/issue149-workflow-reruns-20261002-kit-01",
  "mediaDir": "<outputDir>/media"
}
```

`prepare` adds a `media` array of `{"name", "relative", "sha256"}`
objects.  Each relative path must resolve beneath `mediaDir`; the harness
hashes it before `ImportMedia` and checks the returned name and UID.  Later
configs carry an `owned` object with `projectUid`, `timelineUids`,
`itemUids`, and `mediaUids` returned by the previous result.  The root actor
updates those IDs after each additive duplicate; no historical IDs are
embedded in this source.

`actionId` is a safe filename component.  Evidence is written below
`<outputDir>/evidence/<actionId>/` as `journal.jsonl`, `pre.json`,
`post.json`, and `result.json`; the launcher also retains a progress JSONL
record beside the result.  All API calls are journaled with a request record
before dispatch and a return, missing, or error record afterwards.  Values
are stored in an envelope: `{"status":"ok","value":...}`,
`{"status":"missing"}`, or `{"status":"error","error":...}`.  A
successful `None` is therefore distinct from an absent getter and a getter
exception.  Native JSON values retain their native shape; non-JSON proxies
retain type and `repr`.

## Action contract

`context` reads only Resolve version and current project name.  It does not
walk a loaded project's timelines or pool.  `prepare` requires
`allowEmptyUntitled: true` and the exact untouched `Untitled Project` startup
state: zero timelines, no current timeline, no render jobs, no active render,
and an empty root media pool.  It creates the exact project name, applies
writable 25 fps / 1920x1080 / 48 kHz settings, imports only hash-pinned files
under `<outputDir>/media`, and returns the first owned `projectUid` and media
UIDs.  It never loads or deletes a project.

`timelinePlaybackFrameRate` is read-only and is never sent in the preparation
setter.  If a producer config includes it, preparation refuses before
`CreateProject`; if Resolve's observed playback rate still needs adjustment,
the result is retained for the root actor's manual checkpoint. Preparation
requires the post-setter `GetSettings` value to be numeric `25`; it does not
attempt a read-only setter. If preparation fails after creating the project,
the result retains the partial project UID for operator review. The root actor
decides whether to discard that run; this harness never retries `CreateProject`
or exposes a recovery mutation.

`save-checkpoint` is the sole operator checkpoint for an owned partial project.
The existing owned guard and complete pre/post capture apply; it calls
`ProjectManager.SaveProject()` exactly once and requires `True`.  It performs
no settings, import, delete, or recovery operation.

`import-media` is the bounded continuation for a project created by `prepare`
before its first import.  It requires the exact owned project UID, zero
timelines, no current timeline, no render jobs or active render, and an empty
root media pool.  It validates every configured media hash before one
`MediaPool.ImportMedia([absolute_path, ...])` call (the path-list form verified
by the native Issue 141 runner), checks each returned name and UID, and calls
`SaveProject()` exactly once with a `True` result.  It never
creates a project, writes settings, or performs recovery.  A partial pair is
retained on failure for the operator's manual checkpoint.

`build` consumes hash-pinned imported media and config-driven timeline specs.
It creates the two explicit A2/A3 mono audio tracks plus the requested video
track; the embedded A1 track's native subtype is retained as evidence.  It
sets `00:00:00:00` and appends source ranges with
`endFrame = endExclusive - 1`.  The actual getter end values remain in the
snapshots.  The result returns the newly observed timeline and item IDs for
the next staged configuration.

`w1-subtitle-request` opens and verifies the Edit page, accepts exactly one
configured W1 source per invocation, duplicates it exactly once, saves once
before starting the subtitle job, and calls `CreateSubtitlesFromAudio()` once
on that duplicate.  It does not poll or retry; the actor stages one request
per source after the prior request has settled.  `w1-subtitle-poll` only reads
the configured duplicates' project status getter and subtitle track items
until a bounded deadline.  The status getter
(`GetCreateSubtitlesFromAudioStatus`) is retained separately from the first
observed subtitle item; the latter alone never claims completion.

`select-timeline` performs one owned `SetCurrentTimeline` and verifies the
current UID.  When configured with `page: "edit"`, it opens and verifies the
Edit page before selecting the timeline for a controlled W3 phase.

`w2-export` reads the current operator-selected timeline and exports OTIO
once.  The operator owns Edit-page M/S controls.  `w3-mapping-mute` applies
the target's exact getter mapping with only the configured track's `mute`
field changed, stages one owned render, and retains the original raw mapping
for `w3-mapping-restore`.  Restore passes the original raw value back to the
setter and compares complete pre/post snapshots, allowing only the explicitly
journaled target mapping difference (the harness derives that item path).
Any expected queue/export difference must be listed explicitly in
`allowedRestoreDifferencePaths`; settings and queue changes are never
silently ignored.

`w4-speed` applies the configured `SetSpeed` options to one owned item,
exports OTIO, and optionally stages one owned render.  Linked items and all
getter speed values are retained in both snapshots.  `w5-context-read`
explicitly captures the active getter on the current timeline, selects the
configured inactive timeline to read the same getter, and restores the
original selection; it labels the two contexts instead of comparing missing
context values to global `False`.

`w6-before-swap` and `w6-after-swap` are read-only guards around a same-layout
file swap performed by the root actor.  When an explicit render config is
provided, `w6-after-swap` may stage one guarded pre-relink render; it does not
relink the clip.  `w6-relink-render` verifies the externally supplied
replacement hash, calls `RelinkClips`, and stages one owned render.  The root
actor owns the restore guard; the harness never copies or deletes media and
never accepts an audio-less replacement.

`w7-lock-setter` locks every track and records the expected false result from
`SetClipEnabled(False)`, leaving the locks for the root actor's exact
`Edit → Delete Selected` menu attempt.  `w7-unlock` unlocks every track after
the caller-controlled menu action.  No harness action invokes menu APIs or
deletes clips.

### W7 root-owned named-menu sequence

The root actor may use the issue-owned
`hammerspoon-lock-test.lua` helper.  It exposes only four one-shot methods:
`focusTimeline` (`Workspace → Active Panel Selection → Timeline`), `deselectAll`
(`Edit → Deselect All`), `selectNearest` (`Trim → Select Nearest → Clip/Gap`),
and `deleteSelected` (`Edit → Delete Selected`).  Every method requires
Hammerspoon Accessibility, the Resolve bundle, the exact project title, an
activated and still-frontmost Resolve window, and an enabled exact menu item.
Each call returns one JSON receipt and never retries.  `deleteSelected` also
requires a root-supplied attestation containing `lockedStateId`, the expected
owned UID list, and the locked-proof path and SHA-256; the root actor verifies
that proof before invoking the menu.

Before locking, the root actor opens/verifies the Edit page, sets and reads
back the target playhead, focuses the Timeline panel, deselects, selects the
nearest clip, and retains two adjacent native `GetSelectedClips()` list reads
plus complete snapshot equality.  Only then does it dispatch `w7-lock-setter`.
After the one `deleteSelected` call, it dispatches `w7-unlock` and retains the
full post-state, requiring unchanged item count and UIDs.  `SetSelectedClips`
is unavailable; menu selection and native readback are therefore required.

Render staging is one-way: configure settings once, add one attributable job,
verify the returned job ID in the owned queue, and call `StartRendering` once.
`render-poll` only reads status with a bounded deadline and never calls
`StartRendering`.  `Complete`, `Cancelled`, `Canceled`, `Background Render
Cancelled`, and `Remote Render Cancelled` (including Resolve's canceled
spellings) are terminal; `Failed` and `Error` are terminal adverse outcomes.
A partial exception retains the journal and whatever pre/post capture was
available; no automatic retry is performed.

Every mutating or context-selection action returns two complete snapshots of
the named new project.  Each snapshot includes all project timelines and
pool items, current timeline and selected clips, page, settings, render
queue, source mappings, speeds, links, properties, and subtitle track items.
Track getters documented as active-timeline-only are captured only for the
active timeline and explicitly marked as context-only elsewhere.

## Scope and acceptance

The harness owns only these four files.  It does not change contracts,
fixtures, dependencies, old Issue 141 sources, or roadmap state.  Automated
acceptance is the stdlib `harness-check.py`; native acceptance is the root
actor's retained Workflow Integration evidence for W1–W7 and the producer's
review of the result table.  The root actor must retain the exact staged
source hash, launcher/progress records, action journals, snapshots, exports,
render status, and the external W6 restore evidence.
