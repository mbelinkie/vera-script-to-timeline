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
