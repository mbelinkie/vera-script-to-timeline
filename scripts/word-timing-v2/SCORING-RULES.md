# Word-timing v2 scoring rules (pre-registered)

Written on 2026-10-10, after recording A's answer key was frozen
(`rec-a-markers-adjusted.csv`, sha256 `e022d11e…a69f`) and **before** any
system was scored against it. Changes after this point are listed at the end
with their reason.

## Answer-key words

- Every marker whose name is not a non-speech event is a **key word**. Events
  are sniff, sneeze, laugh, cough, breath or a `(parenthesised)` name; they
  count as silence.
- A tag (`FRAG`, `REP`, `FILLER`) is stripped for text matching. A tagged
  marker is a **stumble**, and its boundaries are scored like any other word.
- A numeral marker such as `nineteen[1998]` matches the text `nineteen`.
- `?` at the end of a name marks an unsure boundary. Those words are scored
  but also reported separately.

## Boundary classes

Each key word has two boundaries: onset (start) and offset (end). A boundary's
class depends on the silence between it and the neighbouring key word on that
side. The first and last words count as next to unlimited silence.

| Class | Silence on that side |
| --- | --- |
| `phrase_edge` | 700 ms or more |
| `pause_adjacent` | 150 ms or more, under 700 ms |
| `connected` | under 150 ms |

`phrase_edge` replaces the plan's `take_edge`. The transcription stage does not
know about takes. These are the long-pause boundaries where cuts usually fall.
The 700 ms threshold is the one the pre-fill already used for "possible take
edge".

## Matching a system's words to key words

A system output is a list of words, each with text, start and end. A system
word matches a key word when:

- the two normalised texts (`textnorm.normalise_token`) are identical;
- their midpoints are within 0.5 s of each other;
- order is kept and each word is used at most once (a greedy left-to-right
  pass, nearest midpoint first).

A key word with no match is **not covered**. Coverage is matched key words
divided by all key words. Errors are computed only over matched words.

For aligners run on the Producer transcript (T-O), the system's words are the
transcript entries with the times the aligner gave them.

## Metrics

Per system, per boundary side (onset, offset), per class, and overall:

- `n` (matched boundaries) and coverage;
- median, p90, p95 and max of |error|, using nearest-rank percentiles;
- signed bias: the mean of (system minus key). Positive means late;
- share with |error| > 120 ms, with its one-sided 95% Clopper–Pearson upper
  bound.

## Word accuracy and stumble recall (text sources)

- **WER:** edit distance between the system's normalised words (events
  dropped) and all key words in order, divided by the key word count.
- **Stumble recall:** a key stumble counts as recalled when the system has a
  word whose time span overlaps the stumble's span by at least 50% of the
  stumble's duration, and that word is not matched to a different key word.
  It is reported per tag and overall.

## Anchoring check

Take the 80 words timed independently in #51 (`frozen-reference-v2.json`). For
each one, find its corrected key word: the same text, with a midpoint within
0.5 s of the original midpoint. Report the median, p95 and max of
|corrected − original| for onsets and offsets.

## Tuning (step 4)

Settings are chosen by leave-one-segment-out cross-validation over A's VAD
segments. A "phrase" in the plan means one VAD segment, so there are 10 folds.
There are at most 5 tuned parameters per pipeline, and the report lists every
configuration tried.

## Changes after registration

- **2026-10-10: unanchored blind set on B (an addition; nothing scored yet).**
  A's check showed the Producer kept 70% of pre-filled onsets and 75% of
  offsets unchanged. So the corrected key favours the three systems the
  pre-fill came from (MFA, Qwen, Charsiu). Before seeing B's pre-fill, the
  Producer times 40 B words from scratch (`blind_set.py`, seed 70730,
  stratified 15/10/15 by the Speechmatics gaps). Those 40 are B's primary
  **unanchored** reference for comparing aligners with cloud systems. The
  corrected full key is still used for coverage, WER, stumble recall and
  per-class tables, with its anchoring disclosed. On A, the #51 80-word set
  plays the same unanchored role.
- **2026-10-10: script-informed candidates (T-CK, T-CR, A-MFA-G) and
  script-word accuracy** (plan section 5, "Script-informed pipelines"). They
  were added after A was scored script-free and before any script-informed run
  existed. The matching rules are unchanged. For script-informed outputs, a
  system word also matches a key word when both map to the same script
  spelling through `aliases-<rec>.json`, which is written before those runs
  are scored.
