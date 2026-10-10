# Word-timing v2 — correcting the answer key in Adobe Audition

This is step 3 of `docs/plans/word-timing-v2-test-plan.md`. You correct a
pre-filled marker list instead of marking from scratch. The pre-fill is the
median of three different aligners, so it does not favour any one of them.

Your files are in `~/.local/share/vera/word-timing-v2/answer-key/<rec>/`:

| File | What it is |
| --- | --- |
| `<rec>-48k.wav` | The original 48 kHz audio. |
| `<rec>-markers.csv` | **The file you correct.** One range marker per spoken word, plus `??` markers where a stumble may be missing. |
| `<rec>-words.txt`, `<rec>-check.txt` | The same pre-fill as Audacity label files. Use them only if you go back to Audacity 3.7.9. |

## Setup

1. Open `<rec>-48k.wav` in Audition.
2. **File ▸ Import ▸ Markers from File…** and pick `<rec>-markers.csv`.
3. Open the Markers panel (**Window ▸ Markers**). Make it wide enough to see
   the **Description** column.
4. Optional: **Shift + D** toggles the spectral display. Word onsets are much
   easier to see there.
5. Keep the time display on **Decimal**. The export only works in that
   format.

## What the markers mean

- **Word markers** are named with the word. Their Description says why one is
  worth a look:
  - `start disagree 85ms` or `end disagree 60ms`: the aligners disagreed by
    that much. **Over about 150 ms: always check. 40–80 ms: mostly skim**,
    because one aligner works on a coarse 80 ms grid.
  - `possible take edge`: the word sits next to a long pause. Take edges are
    exactly where VERA cuts, so these matter most.
  - `1 aligner(s) failed`: one aligner could not place the word.
  - An empty Description means all three aligners agreed within 40 ms.
- **`??` markers** sit on speech that no word covers. For each one, do one of
  these:
  - rename it to a tagged word, adjusting its edges: `FRAG th` (cut-off
    fragment), `REP the` (repeated word) or `FILLER um` (um, uh, er);
  - rename it to a real word the pre-fill missed;
  - delete it if it's a breath, a noise or nothing.

  The file won't validate while any `??` is left.

## Stumble tags

Every word that was actually said is a plain word: just get its timing right.
That includes words in takes that fall apart, and a first "Kai" before a
restart. You do **not** need to mark takes or decide which attempts failed.

Tags are only for stumbles the pre-fill is **missing**. Add a marker and put
the tag and a space before the text:

| Tag | Meaning | Example |
| --- | --- | --- |
| `FRAG` | A word cut off partway. | `FRAG simul` |
| `REP` | An extra repeat of a word that the pre-fill skipped. | `REP the` in "the the" |
| `FILLER` | Um, uh, er and similar. | `FILLER um` |

## The pass

1. Sort the Markers panel by Description, or just work in time order, and
   deal with every flagged word and every `??` marker.
2. For each one, play and scrub it. Then:
   - **Wrong edge:** drag the marker's start or end handle in the timeline, or
     type a new Start or End in the Markers panel.
   - **Wrong word:** rename the marker (double-click its name).
   - **A stumble nobody marked:** select the span and press **M** to add a
     range marker, then name it with a tag (`FRAG`, `REP` or `FILLER`).
   - **A word that was not said:** delete its marker.
3. Then skim the unflagged words at normal zoom. You're listening for
   obviously wrong markers, not 10 ms nudges.

You never need to edit the Description column.

## Recording B: a lighter pass

B's precise timing comes from the 40-word blind set, so the full B pass is
mainly about **words and stumbles**:

- Fix misheard words, add missed stumbles (`FRAG`, `REP`, `FILLER`), delete
  breath `??` markers and words that were never said.
- Markers whose Description says `BLIND-TIMED (leave as is)` already carry
  your blind-set timings. Don't touch their edges. Fixing their *word* is fine
  if needed.
- Fix timing **only when it's grossly wrong**: a marker on the wrong sound, or
  clearly more than about 150 ms off (start with the `disagree 150ms+` flags).
  Leave smaller nudges alone.

## Recording B: fix the words too

Recording B has no transcript of yours. Its pre-filled **words** come from a
speech recogniser (AssemblyAI), so some will be wrong, and stumbles may be
missing or tidied up. On B, also:

- Listen for each line once at normal speed and fix misheard words.
- Add every stumble the recogniser dropped (`FRAG`, `REP`, `FILLER`). The `??`
  markers point at likely spots, but the recogniser may also have covered a
  stumble with a neighbouring word's marker.
- Delete markers for words that were never said.
- A numeral appears as one marker per spoken word, e.g. `nineteen[1998]`.
  Keep that form, or type plain spoken words.

## Boundary rules

- **A word starts at its first sound.** For a word that starts with a stop
  (p, b, t, d, k, g) after silence, that is the burst: the sharp vertical line
  in the spectrogram, not the silent closure before it.
- **A word ends at its last sound,** including a trailing "s"/"sh"/"f" hiss or
  the puff of breath after a final p/t/k.
- **Breaths are not part of words.** Leave breaths outside every marker.
- **Between two connected words,** put the boundary where the sound changes
  from one word to the next. A shared boundary is fine: one marker's end can
  equal the next one's start. Markers must not overlap.
- If you genuinely cannot tell where a boundary is, leave it and add `?` to
  the end of the word's name, e.g. `the?`. Those boundaries are reported
  separately.

## Saving

In the Markers panel, select all markers (**Cmd + A** with the panel focused).
Then use **Export Selected Markers to CSV**, as in the test, and save it as
`<rec>-markers-corrected.csv` in the same folder. Tell Claude when it's saved.
Claude checks that every marker is in order, nothing overlaps, no `??` is left,
the tags are legal, and that every word edit is listed. It then freezes the
file and records its hash. You can save partway through and carry on later:
re-import your saved file instead of the original.

## Bias check (no extra work)

Before this study, you timed 80 words of recording A independently (#51).
Claude compares your corrected timings for those 80 words with your original
ones. The gap shows how far the pre-fill pulled your judgement, plus ordinary
human inconsistency. That number is reported next to every result. Don't look
up the old timings while correcting.
