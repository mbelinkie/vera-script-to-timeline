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

The script may be RTF or plain text. Passages are its `(on)` / `(off)`
blocks, or its paragraphs when it has no such markers. `[guide]`
pronunciations are understood.

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

- **`<- SUGGESTED`**: the last complete take of the passage.
- **`tight`**: the quiet gap next to the take is short, so the cut is fewer
  than ten frames clear of speech. The frames clear on each side are shown.
- **`CHECK BY EAR`**: the two timing engines disagreed about where that edge
  word is by more than 0.4 seconds, so the rougher recogniser time was used.
  The aligner is known to drag a word onto a sniff, laugh or stammer next to
  it; the recogniser is not.
- **`NO CLEAN CUT`**: no cut is offered, with the reason: there is no
  measured quiet next to the speech, or the edge word has no time.
- **`NO TAKE FOUND`**: nothing in the recording matches the passage.

## Rules it keeps

- Everything said is kept. Speech that matches no passage is off-script,
  never dropped.
- No match or time is invented. A word that cannot be placed has no time.
- If a separate audio file does not clearly match the camera sound, or the
  two drift apart, the command stops and says so.
- The take rules are the ones accepted in #53 (`experiments/issue53`, refined
  in `experiments/issue45/take_rules.py`). This command adds none.

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
