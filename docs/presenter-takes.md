# Finding the takes in a presenter recording

Issue #45. One command takes a presenter recording and its script and lists
every take: for each passage of the script, each attempt at it, where it
starts and ends, what was said, and how that differs from the script.

## The command

Run it from the repository root:

```sh
uv run --frozen python -m vera_timeline_agent.presenter_takes \
  "/path/to/recording.mp4" \
  --script "/path/to/prompter script.rtf" \
  --out "/path/to/a new folder"
```

When the sound was recorded separately, add `--audio "/path/to/sound.wav"`.
The separate file is lined up with the camera's own sound first, the offset
is printed, and the words are taken from the separate file. To line up only:

```sh
uv run --frozen python -m vera_timeline_agent.presenter_takes \
  "/path/to/recording.mov" --audio "/path/to/sound.wav" --sync-only
```

## The script

Three kinds of script file work:

- **A Word export of the script document** (`.docx`; in Google Docs, File,
  Download, Microsoft Word). The script is the document's first table. Each
  table row is a script row, and its first column is what the presenter says.
  **Bold is on camera; plain text is covered by footage.** If nothing in the
  table is bold, the report says the script does not give the camera state.
- **A prompter file** (RTF or plain text). Each paragraph is a script row.
  `(on)` and `(off)` mark what is on camera and what is covered by footage.
- `[guide]` pronunciations are understood in all of them.

**The row is the unit.** A take is matched against a whole script row. The
on-camera and voiceover marks inside a row are recorded word by word, but
they never split it: a change between presenter and footage is a change of
picture, not a cut in the presenter's take.

## What it suggests

Every row gets the best coverage the recording offers:

1. **One clip.** The last read of the whole row that reaches both ends and
   can be cut cleanly. Other whole reads are alternates. The clip covers just
   the row, so a countdown or stumble before it is left out.
2. **Several clips, only when nobody read the whole row.** The row may be
   joined at sentence ends and where the picture changes. For each stretch
   the last read is used, and stretches from the same read stay one clip.
   A join is marked *hidden* when footage is on screen on at least one side
   of it, *JUMP CUT ON CAMERA* when both sides are on camera, and *CHECK*
   when the script does not say. A read in hand is never left where the join
   would show if it carries on.

   Some editors are happy with jump cuts. Add `--allow-jump-cuts` (the
   project's **Allow Jump Cuts** box, off by default) and the same clips are
   suggested at the same cut points, but an on-camera join is no longer
   flagged in the report or on the timeline. `takes.json` records the
   setting as `allowJumpCuts`, and each join still records what it is.

   Allowing jump cuts opens one more choice, `--jump-cut-choice`:
   `long-takes` (the default) works exactly as above: a whole read stays
   whole and jump cuts are still avoided where a read carries on.
   `last-take` always uses the latest read of every stretch, so a
   one-sentence pickup recorded after a whole read replaces that sentence,
   however much that chops the row up. Whichever is chosen, nothing is
   thrown away: each clip
   lists its alternates (other reads of the whole clip) and `otherReads`
   (other reads of part of it, "Also read" in the report), so the producer
   can overrule the suggestion when takes are chosen (#46).
3. Only a stretch that nobody read through is reported as a gap, and only
   the words nobody said are reported as NOT COVERED.

`takes.json` also holds `suggestedEdit`: the clips in script order, each with
its row, cut times, the voiceover ranges inside it (where a slate or footage
covers the presenter), its join, and its wording differences.

**Small wording changes are allowed.** A read covers a row (or a stretch)
when it says at least three quarters of the words as written and is missing
at most one word at either end. Whatever differs is listed under "Differs"
(said X for Y, added, left out) and saved in `takes.json`, so the timeline
can carry a marker for it. It is not treated as missing script.

A read that the take rules split at one or two unmatched words ("kinda" for
"kind of") is put back together when the pause is short and the second part
carries on where the first stopped.

The command prints the time taken. A four-minute recording takes about four
minutes on the 2019 Intel Mac; nearly all of it is the aligner.

## What it writes

- `report.txt`: the readable report. Each passage, its takes in the order
  they were recorded, each take's cut points, what was said, differences from
  the script, and the suggested take (the last complete one). Then everything
  said that matches no passage, under OFF-SCRIPT.
- `takes.json`: the same content for the take-approval work (#46, #47).
  `"approved"` is always `false`: a suggestion is not an approval.
- `work/`: the engine's own files (the 16 kHz sound, recognition,
  reconciliation and alignment records).

## Approving a performance (issue #46)

The analysis above **only suggests** reads. It never approves one, even when
`suggested` is nonempty. A human makes decisions using a separate local CLI.
Use the **original video** (not the derived 16 kHz sound) each time: decisions
are pinned to its SHA-256, rational source-video frame rate, duration, passage
wording and original source-frame cut. A file can move or be renamed after the
first approval if its content hash is unchanged. Run from the repository root:

```sh
# Review eligible complete, clean whole-row reads and their frame keys.
uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli choices \
  --takes "/path/to/a new folder/takes.json"

# Examples: use keys actually printed by choices for your own recording.
uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli choose \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4" \
  --row row-1 --state take --take 60:120 --alternate 150:210 \
  --start-frame 70 --end-frame 110

uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli choose \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4" --row row-2 --state temp-voice

uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli choose \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4" --row row-3 --state needs-pickup

uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli choose \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4" --row row-4 --state no-spoken-line

# Undo the most recent change for that passage (keeps the audit history).
uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli undo \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4" --row row-4

# Print the ordered report AND write its JSON/text versions beside takes.json.
uv run --frozen python -m vera_timeline_agent.presenter_approvals_cli list \
  --takes "/path/to/a new folder/takes.json" \
  --video "/path/to/recording.mp4"
```

The frame keys, row IDs and trims in this example are **fictional**; copy a
real eligible key from `choices`, not these numbers. `choices` does not require
the video and never approves a suggestion. `choose`, `undo` and `list` require
the video. A chosen `take` can have repeated `--alternate` values for distinct
whole-row reads; the argument can be a printed frame key or an ephemeral take
ID shown by `choices`. That ID is *not* stored as the lasting identity.

**Trim rules:** `--start-frame` and `--end-frame` use integer frames of the
original camera recording, not time in a separate audio track. An omitted end
retains the original end (and vice versa). Trims can only tighten an existing
clean cut, cannot leave the video or include more than the proposed quiet
handles, and must leave both measured speech edges **strictly inside** the
new range. If either speech edge is approximate or unmeasured, manual trim is
refused. Invalid requests leave the previous approval intact. An identical
repeat of `choose` is a byte-for-byte no-op, including revision and history;
`undo` adds a new timestamped before/after entry rather than erasing history.

The files beside `takes.json` are:

- **`approvals.json`** (`presenter-approvals/1`): human-only decisions and an
  append-only UTC history of revisions, stored separately from analysis. Even
  temporary-voice, pickup and no-spoken-line decisions pin the script wording
  and complete row order so a later inserted passage cannot inherit a choice.
  Older state-only non-take decisions remain readable but require an explicit
  reapproval before being trusted by `list`.
- **`approved-performance.json`** (`approved-performance/1`): versioned,
  script-ordered preview for future #47 consumption, regenerated by `list`.
- **`approved-performance.txt`**: human-readable version of the same ordered
  preview, including unresolved passages and possible abrupt joins.

The JSON preview has this shape (illustrative values, abbreviated rows):

```json
{
  "schemaVersion": "approved-performance/1",
  "approvalRevision": 3,
  "source": {
    "sha256": "sha256:<64 lowercase hex characters>",
    "file": "recording.mp4",
    "fps": [30, 1],
    "durationS": "12"
  },
  "rows": [
    {
      "rowId": "row-1",
      "rowNumber": 1,
      "script": "First line",
      "state": "take",
      "active": {
        "file": "recording.mp4",
        "startFrame": 70,
        "endFrame": 110,
        "startS": "7/3",
        "endS": "11/3",
        "said": "First line"
      },
      "alternates": []
    },
    {
      "rowId": "row-2",
      "rowNumber": 2,
      "script": "Second line",
      "state": "needs_another_look",
      "previousState": "take",
      "reason": "active: approved read missing, shifted, changed words or ambiguous",
      "savedApproval": {
        "originalFile": "recording.mp4",
        "originalCut": {"startFrame": 150, "endFrame": 200},
        "effectiveCut": {"startFrame": 155, "endFrame": 195},
        "said": "Second line"
      }
    }
  ],
  "possibleAbruptJoins": [],
  "orphanedDecisions": []
}
```

`rows` always contains **every current script passage, in script order**.
Each row has `rowId`, `rowNumber`, `script`, and `state`: `take`, `undecided`,
`temp_voice`, `needs_pickup`, `no_spoken_line`, or `needs_another_look`.
Only verified `take` rows expose build-ready `active` and `alternates`
source ranges. `startS`/`endS` are exact rational-second strings (e.g. `7/3`),
not rounded decimal timestamps; source-video frames are authoritative.
Other states have no usable cut. A stale row includes `previousState`,
`reason`, and for saved takes `savedApproval` **for review only**. A decision
whose row disappeared is still shown under `orphanedDecisions`, never
silently attached to a different row. Changes to the script or source, missing
or shifted reads, changed speech timing, invalid saved trims or ambiguous
matches mark affected takes `needs_another_look`. An alternate becoming stale
also blocks the whole approval until reviewed. Non-take decisions whose
saved script wording or row order changes are likewise marked for review.

`possibleAbruptJoins` lists adjacent verified takes when the measured clear
space on either side of the cut is under ten source-video frames. This is a
**check-by-ear warning**, not a claim that a jump cut sounds bad. Unapproved
passages between takes prevent a join check across that gap. Rerunning the
analysis may change `takes.json`, but does not touch `approvals.json`; rerun
`list` to refresh both preview files. The preview never auto-chooses a
suggested take or builds a Resolve timeline.

## What the report's flags mean

- **`<- SUGGESTED`**: the suggested coverage for the passage (see above).
- **`(alternate)`**: another take that also covers the whole passage.
- **`tight`**: the quiet gap next to the take is short, so the cut is fewer
  than ten frames clear of speech. The frames clear on each side are shown.
- **`CHECK BY EAR`**: the two timing engines disagreed about where that edge
  word is by more than 0.4 seconds, so the rougher recogniser time was used.
  The aligner is known to drag a word onto a sniff, laugh or stammer next to
  it; the recogniser is not.
- **`NO CLEAN CUT`**: no cut is offered, with the reason: the presenter runs
  straight on (usually the camera state changes mid-read), there is no
  measured quiet next to the speech, or the edge word has no time. The speech
  times are still given.
- **`NOT COVERED`**: nothing in the recording matches the passage, or the
  listed words of it.

## Rules it keeps

- Everything said is kept. Speech that matches no passage is off-script,
  never dropped.
- No match or time is invented. A word that cannot be placed has no time.
  Speech counts as an attempt at a passage only when more of its words match
  the script than differ from it; otherwise it is off-script.
- If a separate audio file does not clearly match the camera sound, or the
  two drift apart, the command stops and says so.
- The take rules are the ones accepted in #53 (`experiments/issue53`, refined
  in `experiments/issue45/take_rules.py`). This command adds none, apart from
  the two guards above (the timing cross-check and the match guard).

## Engine settings

The engines are the ones chosen in #51 and packaged in #183. They run in
their own environments, named by environment variables (see
`packages/word-timing/src/vera_word_timing/adapters/local_engines.py`). On
the Producer's Mac:

```sh
export VERA_TOOLS_PYTHON="$HOME/.local/share/vera/word-timing-v2/venv/bin/python"
export VERA_PARAKEET_PYTHON="$HOME/.local/share/vera/issue-51-preflight/run-a/autosubs/parakeet-env/bin/python"
export VERA_PARAKEET_MODEL_GLOB="$HOME/.local/share/vera/issue-51-preflight/run-a/autosubs/app-caches/models/models--istupakov--parakeet-tdt-0.6b-v3-onnx/snapshots/8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"
export VERA_MFA_COMMAND="micromamba run -n mfa python"
export MAMBA_ROOT_PREFIX="$HOME/.local/share/micromamba"
export VERA_MFA_HOME="$HOME/.local/share/vera/word-timing-v2"
```

`ffmpeg` and `ffprobe` must be on the path. A missing engine stops the
command with the reason; nothing falls back to another engine.
