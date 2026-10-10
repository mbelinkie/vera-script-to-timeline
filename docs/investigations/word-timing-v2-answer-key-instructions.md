# Word-timing v2 — correcting the answer key in Audacity

This is step 3 of `docs/plans/word-timing-v2-test-plan.md`. You correct a
pre-filled file instead of marking from scratch. The pre-fill is the median of
three different aligners, so it does not favour any one of them.

Your files are in `~/.local/share/vera/word-timing-v2/answer-key/<rec>/`:

| File | What it is |
| --- | --- |
| `<rec>-48k.wav` | The original 48 kHz audio. |
| `<rec>-words.txt` | One label region per spoken word. **This is the file you correct.** |
| `<rec>-check.txt` | A second label track that marks only the places worth a close look. |

## One-time setup

1. Install Audacity (free): https://www.audacityteam.org/download/
2. Open `<rec>-48k.wav` with **File ▸ Open**.
3. Choose **File ▸ Import ▸ Labels…** and pick `<rec>-words.txt`.
4. Do the same for `<rec>-check.txt`. It appears as a second label track.
5. In the audio track's name menu (the ▾ beside the track name), choose
   **Multi-view**. You get the waveform and the spectrogram together. Word
   onsets are much easier to see in the spectrogram.

## The pass

**Work through the check track first.** For each flag:

1. Zoom in until about one second fills the screen (**Ctrl/Cmd + 1** zooms
   in).
2. Play the region. Click a label to select it; **Space** plays the selection.
3. Fix it:
   - **Wrong edge:** drag the small arrows at the left or right end of the word
     region in the words track.
   - **Wrong word:** click the text and retype it.
   - **A stumble the pre-fill missed** (the check track says
     `SPEECH WITH NO WORD`): select the span in the words track and press
     **Ctrl/Cmd + B** to add a region. Type its text with a tag:
     - `FRAG th` — a cut-off fragment ("th-" before "the")
     - `REP the` — a repeated word
     - `FILLER um` — um, uh, er and similar
   - **A word that was not actually said:** delete its region. Click it, then
     **Edit ▸ Labels ▸ Delete label** or Backspace.
4. Flags marked `MISSING` mean no aligner could place a word that your
   transcript says is there. Add its region if you hear it; ignore the flag
   if you don't.

**Then skim the rest** at normal zoom. You're listening for obviously wrong
regions, not 10 ms nudges.

You never need to edit the check track.

## Recording B: fix the words too

Recording B has no transcript of yours. Its pre-filled **words** come from a
speech recogniser (Speechmatics), so some will be wrong, and stumbles may be
missing or tidied up. On B, also:

- Listen for each line once at normal speed and fix misheard words.
- Add every stumble the recogniser dropped (`FRAG`, `REP`, `FILLER`). The
  `SPEECH WITH NO WORD` flags point at likely spots, but the recogniser may
  also have covered a stumble with a neighbouring word's region.
- Delete regions for words that were never said.
- A numeral appears as one region per spoken word, e.g. `nineteen[1998]`.
  Keep that form, or type plain spoken words.

## Boundary rules

- **A word starts at its first sound.** For a word that starts with a stop
  (p, b, t, d, k, g) after silence, that is the burst: the sharp vertical line
  in the spectrogram, not the silent closure before it.
- **A word ends at its last sound,** including a trailing "s"/"sh"/"f" hiss or
  the puff of breath after a final p/t/k.
- **Breaths are not part of words.** Leave breaths outside every region.
- **Between two connected words,** put the boundary where the sound changes
  from one word to the next. A shared boundary is fine: one region's end can
  equal the next one's start.
- If you genuinely cannot tell where a boundary is, leave the pre-fill and add
  `?` at the end of the word's text, e.g. `the?`. Those boundaries are
  reported separately.

## Saving

Audacity exports *every* label track into one file. So first close the check
track: click the **×** at the top left of that track. Then choose
**File ▸ Export ▸ Export Labels…** and save as `<rec>-words-corrected.txt` in
the same folder. Tell Claude when it's
saved. Claude checks that every time is in order, nothing overlaps, every
word is present and the tags are legal. It then freezes the file and records
its hash. If you need a break, export at any point and re-import later.

## Bias check (no extra work)

Before this study, you timed 80 words of recording A independently (#51).
Claude compares your corrected timings for those 80 words with your original
ones. The gap shows how far the pre-fill pulled your judgement, plus ordinary
human inconsistency. That number is reported next to every result. Don't look
up the old timings while correcting.
