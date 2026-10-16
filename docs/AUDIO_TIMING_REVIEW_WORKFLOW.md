# Audio timing review through Adobe Audition

Standing Producer instruction, adopted 2026-10-11. Read this before asking the
Producer for manual audio timing, including a `BOUNDARY_EVIDENCE_REQUIRED`
blocker. Prepare machine transcription and timing first, then a prefilled
Audition marker file for the Producer to review and edit. Never request timing
from scratch. This supersedes older Audacity handoff instructions for future
manual timing requests, without changing historical evidence or study results.

## Prepare the candidate

1. Identify the original audio by immutable source identity and byte hash,
   the script revision, and the exact boundaries needing review. Reuse valid
   retained machine results; otherwise use the accepted shared
   `vera-word-timing` route and its locked toolchain. Inspect the relevant
   checkout's CLI and engine configuration rather than inventing new commands.
   The supplied example uses recognition → script reconciliation → alignment
   → agreement. Keep recognition faithful to speech: record additions,
   omissions and variants separately; the written script remains authoritative
   and is not automatically rewritten to match recognition.
2. Preserve the original audio. An engine-only resampled copy may be used with
   a verified mapping to original source time; review uses the original, not
   trimmed, cleaned or noise-reduced audio. Serialize MFA jobs sharing its
   temporary workspace. Inspect runtime refusals; missing tooling or ambiguous
   alignment is a visible blocker, not permission for silent engine fallback.
3. Write one range marker per spoken word, with script-friendly display names
   where correspondence is established. Keep extra spoken words and flag
   `NOT IN SCRIPT`; retain a private correspondence record for canonical token
   identities, repeated words and numeral expansions. Display text and ordinal
   position alone are not token identity.
4. Put the requested edge and reason in `Description` first; also flag alignment
   disagreements, likely cut points, unknown words and uncertain mappings.
   Name the review scope explicitly: required boundaries plus relevant flagged
   uncertainty, not an automatic whole-recording timing exercise. An empty
   description or agreement between engines does not mean human verification.
5. Hash the prefilled marker file and retain the machine provenance and private
   correspondence record before handing it over.

Use the established Audition interchange format, even though the extension is
`.csv`: UTF-8 with BOM, tab-separated columns and CRLF line endings.

```text
Name<TAB>Start<TAB>Duration<TAB>Time Format<TAB>Type<TAB>Description
```

`<TAB>` above denotes an actual tab. `Start` and `Duration` use `m:ss.mmm`;
`Time Format` is `decimal` and `Type` is `Cue`. Use an existing verified
exporter when available; the private source guide's `make-audition-markers.py`
is a working reference, not authorization to publish private input files.

## Producer handoff

Supply the exact original audio, marker file, requested words/edges and output
location privately, with this checklist adapted to the current request:

1. Open the original audio in Adobe Audition.
2. Choose **File → Import → Markers from File…** and select the prefilled CSV.
   Expected: word-range markers appear over the original audio.
3. Open **Window → Markers**, show the Description column and use Decimal
   time display. Find the explicitly requested edge first.
4. Listen, scrub and use spectral view (**Shift + D**) as useful. Correct that
   edge by dragging it or entering Start/End values. A word begins at its
   first audible sound (a stop burst after silence where applicable) and ends
   at its last audible sound; breaths are outside the word.
5. Review the other relevant flagged markers. Append `?` to any word whose
   boundary cannot be determined. State which required edges were checked,
   including those left unchanged; an unchanged prefill alone proves no review.
6. Select all markers in the panel (**Cmd + A**) and choose **Export Selected
   Markers to CSV**. Save a new `<row>-markers-reviewed.csv`, preserving the
   prefilled file.
7. Return the reviewed file and identify any unresolved edges. The agent will
   validate the export and report the changes; uncertain required edges remain
   blocked rather than being guessed.

## Validate and bind reviewed evidence

- Check the expected columns and decimal time format, finite nonnegative
  starts, positive durations, increasing/non-overlapping ranges and bounds
  inside the original audio. Unexpected overlaps or ordering require
  clarification, not silent clamping or deletion.
- Verify marker inventory and correspondence against the prefill and private
  token mapping. Each requested token must map unambiguously to the expected
  spoken occurrence. Resolve missing/duplicate markers, placeholder `??`
  entries and any `?` on a requested edge before consuming it. Repeated words
  are legitimate; never identify the requested token by word spelling alone.
- Report every start/end delta and rename. Freeze the reviewed export by hash;
  leave it untouched. Corrections require a new export and review revision.
- Use the accepted boundary-evidence contract and approved preparation flow,
  not a new schema invented for this handoff. For the #179/CN-179 contract,
  canonical token IDs, offsets and quoted text come from the frozen script;
  observations use reduced rational seconds in original audio time. Populate
  only explicitly reviewed observations; include an audible end only when
  required and reviewed. Preserve contract-required token ordering/shape.
- Bind the review receipt to the script/row, unchanged audio and source
  identities, selected observations, reviewer, review ID/revision and reviewed
  CSV hash. Receipt locators are project-relative. The authorized preparation
  flow verifies source bytes; the pure compiler cannot establish that binding.
- Rerun the applicable compiler and media-needs checks on that exact revision.
  Report whether the requested blocker is resolved, without claiming complete
  word mapping, take approval or whole-recording verification.

## Privacy and authority

Keep audio, transcripts, per-word rows, marker files and receipts in the
project's approved private preparation area outside version control. Public
evidence contains only safe aggregates/hashes, never private text or paths.
This workflow does not authorize cloud transmission, paid calls, source
mutation or publication. Reuse the accepted local route; additional provider
access requires its separately recorded privacy/retention/cost authorization.

Machine times remain candidates. The Producer's exported and validated review
establishes evidence only for the explicitly reviewed boundaries. It does not
change the issue's acceptance authority or authorize closing unrelated gates.
