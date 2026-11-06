# #336 phase 3 — Studio qualification attempt (blocked before output)

**Historical first attempt only.** The later fresh run5 succeeded after the
Resolve window was closed; read the superseding
[real Studio raster results](phase3-studio-results.md) and
[checked-in pixel witness record](studio-run5-pixels.json). The failures below
remain useful diagnostic history, **not the current phase-3 status**.

**2026-11-06; not a successful motion/geometry qualification.** An exclusive
disposable test was attempted on the connected Mac's installed **DaVinci
Resolve Studio 21.1.1.10**. Scripting eventually connected after the app had
finished startup. The command-side host was macOS, with local `ffprobe` and
`ffmpeg`; no Free-edition run was available.

## What was actually exercised

1. Resolve was initially not running. It was launched; an early `scriptapp`
   check returned no connection until the Resolve log reported its script
   server ready. A subsequent read-only call returned version `21.1.1.10`.
2. A public-only qualification harness was copied byte-for-byte from the
   reviewable GitHub transfer commit and checksum-checked. The harness
   generates synthetic **1000×1000, 1600×900, and 900×1600** PNG grids with
   distinct corner witnesses and an off-center `(0.75, 0.30)` marker. Its
   intended render project is 1280×720 / 24 fps. Its offline code is at
   `scripts/issue336_studio_qualify.py`, with contract/fixture checks in
   `tests/test_issue336_studio_qualify.py`.
3. A background launch returned before running the harness; no native
   project or output was created. To avoid untracked operations the harness
   was changed to run **one case per bounded command**, with persisted
   `starting`/`decoded`/`refused` state and no retry of uncertain cases.
4. The first bounded attempt refused because Resolve had auto-opened an
   existing `Untitled Project`. Read-only checks confirmed **zero timelines**;
   the subsequent guard also found no clips, subfolders, queued jobs, or
   active render. **Neither the existing project nor its assets were edited.**
5. Under that guard, `ProjectManager.CreateProject` returned `None` for the
   first fresh synthetic name. In the next new attempted target,
   `ProjectManager.CloseProject` returned `False` for the verified-empty
   startup project, before any fresh project could be created. We did not
   bypass this by importing into the existing project, deleting/renaming a
   project, changing scripting preferences, or replaying an uncertain job.

**Native evidence from this phase:** no synthetic timeline imported, no
render completed, no file decoded, **no frame 0 / quarter / half / last
samples**, no custom-focus mapping, no aspect-ratio/framing/matte/ease result,
and no save/close/reopen comparison. Exact new supported output envelope:
**none established**. Exact negative *product capability* envelope: **none
established**; the tested failure is a **project-creation/access blocker**, not
proof that native Dynamic Zoom cannot achieve a requested effect. The older
[#325 raster proof](../../investigations/issue-325-native-image-zoom.md)
remains the only positive runtime evidence.

## Unperformed matrix and bounded continuation

The harness defines eleven separate cases: square None (48 frames), square
linear motion (24/48/96/144 frames), wide and tall linear motion (48 frames),
square explicit fill (48 frames), and imported easing values 1/2/3 (48
frames). All would require actual decoded ProRes raster and exact frame count;
`SetProperty`/metadata readback is never evidence of eased pixels. The source
corner witnesses are necessary to reject a purported contain result if a
single source edge disappears at any sampled time. Full-size samples must
establish sign, inverse scale, aspect ratio, endpoint and black exposure
before any normalized-focus conversion can be promoted to production.

**Smallest safe unblock:** use Resolve's normal Project Manager UI to create
and open a genuinely new, empty disposable project named
`VERA336-SYN-run4`, without changing an existing project or preferences.
Then invoke the harness with a *new* `run4` output directory and
`--adopt-created-project`. It independently refuses if the active project
name, media, timelines, folders, queued renders, or edition differ. Once
one case completes with actual decoded frames, additional cases can be run
with `--case` and the *same* output directory, and `--finalize` performs
actual save/close/reopen verification. No pass may be recorded after any
uncertain/failed render. Do not reuse `run1`, `run2`, or `run3` targets.

`python/vera_timeline_agent/native_image_motion.py` deliberately retains
`production_qualification() -> None`; geometry, contain/background and
nonlinear easing remain fail-closed in the shipping path. #336 acceptance is
**open** and phase 4 must **not** construe this attempt as permission to
enable native effects. No preceding build, source, target or cache was
modified or deleted by the experiment.
