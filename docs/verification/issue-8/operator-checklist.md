# Issue #8 — External acceptance checklist (not yet runnable)

Status: native acceptance is **not established**. No #8 project, composition
or render has been created. Do not interpret a package verification pass as
Fusion placement. The `Transport` directory is internal media scaffolding;
never build it directly to accept graphics.

## Preconditions

Complete the reviewed-source fast/slow/full gates first. Establish a supported,
affirmatively identified Studio installation and retain actual EV24 runtime
qualification. The present 21.1.1 build 10 installation fails this candidate's
accepted installation/version checks. Do not edit a receipt, supply fabricated
`LocalFacts`, relax a version guard or enable external scripting to force a pass.
See [runtime assessment](runtime-assessment.md) for the accepted injected path
and the integration/qualification still needed to use it.

Only after that blocker is resolved, use the final reviewed candidate and its
retained native execution path. The commands below describe this candidate's
existing CLI; they do not authorize installation or a different adapter.

## Prepared matrix

Package paths are relative to this dedicated worktree's `out/issue8/packages`.
Each timeline is 1920×1080, 24 fps, starts at frame 0 and has one graphic on
V4. The stable graphic-use ID is
`70000000-0000-4000-8000-000000000001` in every build.

| Package | Build UUID suffix | Frames | Values |
| --- | --- | --- | --- |
| `standard-64` | `000000000001` | 64 | Finland, 2024; blank text overrides |
| `overrides-64` | `000000000002` | 64 | Finland, 2024; The Code / Nemo |
| `otis-64` | `000000000003` | 64 | Otis; Year omitted; blank text overrides |
| `standard-120` | `000000000004` | 120 | Finland, 2024; blank text overrides |
| `overrides-120` | `000000000005` | 120 | Finland, 2024; The Code / Nemo |
| `otis-120` | `000000000006` | 120 | Otis; Year omitted; blank text overrides |
| `revised-120` | `000000000007` | 120 | Finland, 2024; The Code — revised / Nemo |

Full build UUIDs have prefix `88000000-0000-4000-8000-`. The first six
packages are retained and verified. The seventh is a new actually compiled
one-field revision; its package preparation and slow verification are pending
the expensive-check slot. Fresh inputs are retained in
`out/issue8/revision-inputs`; all original six manifests/reports and registered
template files compare byte-identical to the earlier input set. Do not run or
accept an absent package artifact.

## Ordered accept/fail checks

1. Save a disposable nonproduction current project manually. Record its project
   name and timeline names/counts. No production project is in scope.
2. For each matrix package, run the graphics **preflight**, preserving a new
   result file outside the package. For example, from this worktree:

   ```sh
   rtk ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_graphics_cli preflight out/issue8/packages/standard-64 --result out/issue8/standard-64-native-preflight.json
   ```

   Require `preflight_passed`, actual connected edition/version/build and the
   expected fresh target names. Any refusal stops; retain it without edits.
3. After successful preflight and confirming the target is disposable, use the
   same command with `build` and a new `--result` filename. Require `status: verified`,
   `verified: true`, zero discrepancies, and one actual graphic observation.
   This candidate names the new project `VERA Studio build <full build UUID>`
   and timeline `VERA build <full build UUID>`. It never reuses an existing
   target. Retain any partial target on failure; do not delete or repair it.
4. In each saved/reopened target, open Edit and select the V4 graphic. Check
   start 0 and duration exactly 64 or 120 frames. In Fusion confirm the exact
   pinned EV24 composition, trusted values and built-in badge. Blank overrides
   must show authored auto-fill. Otis must use authored Otis behavior without
   a Year assignment. Explicit overrides must display The Code / Nemo.
5. Play and retain a render of each of the six original cases. Confirm the
   authored 48-frame entrance and 16-frame exit at both durations; the extra
   56 frames in the 120-frame case are hold, not stretched entrance/exit.
   Check actual badge pixels and text, including after reopen. Record exact
   render paths/hashes; no render is currently supplied by this task.
6. Compare `overrides-120` with the separately built `revised-120`: only the
   new timeline displays The Code — revised; both keep Nemo and the Finland
   built-in badge. Reopen the old project and confirm it still displays The
   Code. Confirm the original disposable project's timeline list/count is
   unchanged. Do not edit the old timeline to perform this check.
7. Retain the exact delivered revision, native result files/hashes, actual
   runtime/build, project/timeline names, post-reopen graphic observations and
   visual/render evidence. Reply:
   `Accepted #8: six visual/timing cases and one-field new-build isolation
   pass after reopen; result files <names/hashes>; existing timelines unchanged.`
   Or report the first failed step, exact target and result/artifact reference.

The issue remains open until the automated and actual External gates pass.
No badge override, Free baking, global installation, merge or deployment is
authorized by this checklist.
