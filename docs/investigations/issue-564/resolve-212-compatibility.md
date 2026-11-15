# Resolve Studio 21.2 compatibility investigation

Investigation: [#564](https://github.com/mbelinkie/vera-script-to-timeline/issues/564).
Started 2026-11-14 at the Producer's request. This report is in progress.

## Purpose and scope

Determine whether the installed Studio 21.2 can support VERA's existing native
workflows alongside Studio 21.1.1, and whether new scripting can perform the
roll edits previously investigated in #477, #489 and #490. Timeline issue #390
concerns Research snapshots rather than Resolve roll editing.

All test execution is assigned to `gpt-6-luna` helpers at maximum reasoning.
One helper alone controls Resolve. Research, static inspection and focused
automated tests run independently of that native session.

## Test process

1. Inventory the actual hardware, macOS, both app builds, native library and SDK
   routing. Establish what is installed, what the vendor supports, and what can
   actually run as separate facts.
2. Compare first-party release documentation and installed scripting references.
   Identify additions, removals and changed signatures before invoking methods.
3. Map VERA's native boundaries to existing Resolve knowledge findings. Reuse
   established results and test the changed runtime rather than rebuilding the
   retired Test Bench.
4. Run focused host tests for packaging, native adapters, observation, recovery,
   effects and structural verification. Record these as synthetic evidence.
5. When target isolation is safe, use a fresh synthetic project through the
   existing VERA build route, then save, close, reopen and verify structure.
   Check exact application identity before any writes. Run one native job at a
   time, and stop on uncertain writes.
6. Test roll edits with source handles, linked audio/video and unchanged native
   identities; verify both changed and unchanged geometry after reopen. API
   presence alone is insufficient.
7. Repeat the identical fixture on the other version where possible and verify
   the old installation remains usable. Keep unsupported, failed, untested and
   previously limited cases distinct.

Producer media, existing project contents, project-library migration, installers
and global SDK/preferences are outside the effects authorized by this check.
The complete local suite is excluded; GitHub Actions owns that gate. Current
AGENTS.md and #520's short structural loop govern live checks; retired Test Bench
gates, one-use run machinery and render/audio-comparison campaigns are excluded.

## Results

Pending helper findings. No compatibility pass is asserted by this draft.
