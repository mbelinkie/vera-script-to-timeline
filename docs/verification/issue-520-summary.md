# Issue 520: timeline speed check and open questions

## Goal

Build a short timeline and an approximately 581-second timeline through the
shipped command. Save, close and reopen each Resolve project, check its
structure, and compare the time taken with the actual timeline duration.
Matthew then watches and listens to the short result once.

## Why preparation became complicated

- The retained examples and the original long fixture use 24000/1001 fps
  (23.976), VERA's default delivery rate. The current one-command build
  refuses unqualified fractional-rate native delivery. It supports an exact
  24 fps timeline, so the acceptance check is being prepared at 24 fps instead.
  This will not prove the default-rate path.
- The older samples were made for a different build route. The current command
  requires prepared media bindings and path maps; copying an old finished
  package alone does not provide those inputs.
- The long fixture's public speech and successful offline word alignment were
  retained, but its full set of 24 picture sources was not available locally.
  New synthetic 24 fps sources were generated. The alignment supplies measured
  onsets; it is not a human-verified word-timing reference.
- The short example contains measured narration evidence and existing video at
  23.976 fps. Its conversion must preserve the narration and identify freshly
  converted video as new media rather than relabeling the original files.
  Inspection found that its two measured narration records use audio-sample
  offsets and rational times, not frame-number fields.
- The long sample compiled, but package verification refused its report when
  several placements shared one prepared source and range. The compiler emits
  a report row per placement; the package checker requires one per preparation
  key. This product inconsistency is tracked in
  [#531](https://github.com/mbelinkie/vera-script-to-timeline/issues/531).
  Inventing different source identities to get around it would misrepresent
  the sample. The compiler maps requirements into report rows in
  `packages/contracts/src/compiler-core-v2.ts` (`makeReport`); the package
  checker indexes those rows by unique key in `python/vera_timeline_agent/v2_package.py`.

## Guidance from Opus

Opus 5.5 recommended measuring at 24 fps without bypassing the fractional-rate
guard, documenting the limitation, and checking that the short sample's
narration evidence remains valid. It also asked whether duration is checked
against Resolve itself. The structural verification compares Resolve's start
and end frames with the compiled timeline after reopen.

The suggestion to add a results receipt and repeated runs was not adopted as a
requirement: this issue asks for one simple check and excludes receipts.

## Workflow issues encountered

- Sample preparation expanded substantially beyond the expected small runner:
  it needed rate-compatible picture sources, measured narration, media
  preparation records and the current command's input mappings. The draft
  contains experimental preparation code and needs review for simplification.
  Preparation is outside the timed command, so a passing timing will not
  describe the elapsed time needed to create these inputs from scratch.
- Local backup-guard tests initially failed because macOS supplied a symlinked
  temporary directory. With the physical path and a 30-second test timeout,
  the four focused tests passed; the normal five-second timeout was too short
  on this Mac. The earlier cloud validation passed on its then-current draft.
- The first long preparation stopped because its process did not use the
  pinned Node version. Its generated files were retained and the next attempt
  used the pinned version. The first short conversion also exposed a mismatch
  between two hash formats; independent verification confirmed the source had
  not changed before the comparison was corrected.
- Progress paused under the repository stop rules and resumed on Matthew's
  instruction. No failure was treated as a successful timeline build.

## Status

The long input reached compilation, but its package was refused as described
in #531. The short input is still being prepared. Both native measurements,
final review and CI, and Matthew's watch-and-listen acceptance remain pending.
No native timing is claimed until the actual runs complete.
