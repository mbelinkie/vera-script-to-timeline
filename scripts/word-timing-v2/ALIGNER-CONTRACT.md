# Word-timing v2 aligner contract

Every aligner wrapper in this folder takes the same input and writes the same
output, so the scoring code never needs to know which aligner produced a file.
See `docs/plans/word-timing-v2-test-plan.md` for the study.

## Command line

```
<wrapper> --segments SEGMENTS.json --audio-dir DIR --out RESULT.json [--variant NAME]
```

- `--segments`: input file (below). Its `audio` path is relative to `--audio-dir`.
- `--variant`: aligner-specific setting, such as an MFA acoustic model name.
- The wrapper must not read anything else: no transcript, script or answer key.

## Input: `SEGMENTS.json`

```json
{
  "audio": "rec-a-16k.wav",
  "offsetSec": 0.0,
  "segments": [
    {"id": "s000", "start": 8.4, "end": 14.2,
     "words": [{"i": 0, "text": "kai", "display": "Kai"}]}
  ]
}
```

- `start`/`end`: seconds in the audio file. Segments are at most 30 s and
  already carry the 300 ms VAD padding.
- `words[].i`: global word index; `text`: normalised (lower case, numerals
  spelled out, no punctuation; apostrophes and hyphens kept inside words);
  `display`: original token.
- A numeral expands to several spoken words, e.g. `1998` becomes `nineteen`,
  `ninety`, `eight`. Each spoken word is its own entry. All entries keep the
  token's `i`, add `"sub": 0, 1, 2…`, and repeat the same `display`. Entries
  without `sub` are single-word tokens.
- `offsetSec`: added to every output time so results are on the recording's
  clock. It is non-zero only for excerpts such as the smoke test.

Each wrapper loads the audio file and aligns each segment's words inside that
segment's span only.

## Output: `RESULT.json`

```json
{
  "aligner": "A-MFA",
  "variant": "english_us_arpa",
  "words": [{"i": 0, "start": 8.955, "end": 9.421, "status": "aligned"}],
  "provenance": {
    "packages": {"montreal-forced-aligner": "3.4.3"},
    "models": [{"id": "...", "revision": "...", "sha256": "..."}],
    "settings": {},
    "platform": "linux/amd64 docker | darwin x86_64 native",
    "wallSeconds": 0.0,
    "peakRssBytes": 0
  }
}
```

- There is exactly one row per input word entry, in input order, echoing `i`
  and `sub` when present. Times are in
  seconds, absolute (`offsetSec` already added), and rounded to 1 ms.
- `status` is `aligned`, or `failed` with `start` and `end` set to null.
  Failed words are never interpolated.
- Times inside the aligner keep their native resolution. Report that
  resolution in `settings.frameMs`.

## Private data

Audio, transcripts, results and logs live in `~/.local/share/vera/word-timing-v2/`
and never in git. Model caches live in `~/.local/share/vera/word-timing-v2/cache/`.
