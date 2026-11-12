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

## Producer decision on 2026-11-12

Use 24 fps for both cases. The results table shows preparation and build plus
check separately. Preparation creates the fixture inputs and prepared media.
The short case uses the retained measured narration. The long case creates
the narration rows from public audio and a retained offline alignment. Build
plus check uses the shipped command total through save, close, reopen and
structural verification. Compare only that total with the verified timeline
duration. The default 23.976 fps command remains outside this check.

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
- A later short-sample attempt converted all six picture sources and compiled,
  but package verification rejected the saved document because its
  `liveContentHash` did not match its content. The cause has not yet been
  established. The converted files were retained. This was the second
  preparation failure in the resumed attempt, triggering the repository stop
  rule before any Resolve run.
- Progress paused under the repository stop rules and resumed on Matthew's
  instruction. No failure was treated as a successful timeline build.

## 24 fps Resolve speed check, 2026-11-12

| Sample | Timeline duration (s) | Preparation (s) | Build plus check (s) | Result |
| --- | ---: | ---: | ---: | --- |
| Short retained sample | 47.792 | ~2,588 | 59.09 | **FAIL** — structural check failed after reopen and elapsed time exceeded timeline duration |
| 30-row public fixture | 581.250 | 743.09 | 85.85 | **FAIL** — command refused before native creation or structural check |

Studio 21.1.1 build 10 on the Intel Mac, using Local scripting after the restart. This check does not cover VERA's default 23.976 fps. Preparation is outside the speed gate. The short run reused measured narration and converted six pictures. Its preparation time is estimated from the run start and the final media-map write because the timing log was lost. Long preparation includes the measured generation of the two slates. Build plus check is the command's elapsed total from input selection through completion or refusal.

- Short: save/close/reopen succeeded. Read-only inspection confirmed 1,147 timeline frames and all 11 event placements and stamps. Source-end verification rejected the observed video, narration and one-frame still ranges. The disposable project remains available for diagnosis.
- Long: package build and attestation passed, including shared bindings after #531. Read-only preflight confirmed that two intentional slate treatments lack a native mapping. Resolve created no long project. The elapsed time to refusal is not a passing speed measurement.

The benchmark remains open. The short result is a retained diagnostic target,
and Producer watch-and-listen acceptance is pending a verified result.

[Results posted on #520](https://github.com/mbelinkie/vera-script-to-timeline/issues/520#issuecomment-6834652634)
