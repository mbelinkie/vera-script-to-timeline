# Word-timing v2 — results and recommendation

Status: **draft for Producer review** (2026-10-10). Plan:
`docs/plans/word-timing-v2-test-plan.md`. Pre-registered scoring rules:
`scripts/word-timing-v2/SCORING-RULES.md`. Frozen settings:
`scripts/word-timing-v2/word-timing-v2-frozen.json` (commit `28d94c7`, before
any recording-B scoring). Private audio, transcripts and per-word rows stay in
`~/.local/share/vera/word-timing-v2/`; this report holds aggregates only.

## Recommendation

| Product use | Recommended pipeline | Why |
|---|---|---|
| **Script to Timeline, default** (paid is fine: presenter recordings are rare) | ElevenLabs Scribe v2 → script reconcile → MFA (english_us_arpa + pronunciation guides) → agreement flags | Best words on the halting presenter (WER 2.8%, names 23/23), fewest displaced words (8), best take recovery in the #53 re-run (12/15 spans, 6/7 picks). Timing equal to every other MFA pipeline. |
| **Script to Timeline, free local option** | Parakeet TDT 0.6B v3 → script reconcile → MFA → agreement flags | Free, local, ~17 s per 4 min on this Intel Mac. Same timing as the best pipelines; weaker words on a halting presenter (WER 7.4%, names 11/23; take picks 3/7). |
| Script to Timeline, Resolve Studio option | Resolve 21 transcription → reconcile → MFA | Works headless. Quality ≈ Parakeet (WER 8.1%, picks 3/7) but slower (~2.5 min per 4 min) and needs a paid Studio licence. **Recommend Parakeet over it** for the "works for everyone" local option. |
| **Research, default** (must be free) | YouTube captions → MFA | Free. Captions → MFA timing equals the best pipelines on both keyed recordings. |
| Research, no captions | Parakeet → MFA | Free, fast, multilingual model family (25 European languages). |
| Retire | whisper.cpp large-v3-turbo (Research's current engine) | Drops whole repeated takes on a halting presenter (WER 33.9% on A), slower than real time on this Mac, unusable native word times. |

"Agreement flags" = a second aligner (Qwen3-ForcedAligner, Apache-2.0) checks
every MFA boundary; disagreements over 70 ms are marked *needs review*. This is
the safety net for the main failure mode below.

## Recordings and answer keys

- **A**: halting presenter, many restarts and stumbles, 244 s, raw recorder
  audio. Key corrected in Audition (457 words, 15 tagged stumbles).
- **B**: fluent presenter, 227 s, Adobe-enhanced audio (raw also tested). Key:
  light Producer pass (561 words, 4 stumbles) plus a 40-word blind timing set.
- **Anchoring:** the Producer kept 70–75% of pre-filled boundaries in A's key,
  so full-key timing is biased toward the pre-fill. Timing claims therefore use
  **unanchored** references: A's independent 80-word set (from #51) and B's
  blind 40. The full keys are used for words, names, stumbles and coverage.
- **Human floor:** two human passes on the same words agree to a 13 ms onset
  median (p95 127) and 30 ms offset median (p95 305). Pipelines at ~20/30 ms
  are at human repeatability.

## Words: accuracy, names, stumbles (full keys)

`T-CR` = after script reconciliation (names spelled from the prompter).

| Recogniser | A WER (raw → reconciled) | A names | A stumbles | B WER (reconciled) | B names |
|---|---|---|---|---|---|
| ElevenLabs Scribe v2 | 3.5% → **2.8%** | **23/23** | 67% | 1.2% | 32/32 |
| AssemblyAI universal | 4.6% → 3.1% | 22/23 | 67% | **0.9%**¹ | 32/32 |
| Google Chirp 2 + keyterms | 3.7% → 3.3% | 23/23 | 60% | 1.6% | 32/32 |
| Speechmatics enhanced | 5.9% → 4.2% | 19/23 | 40% | 1.6% | 32/32 |
| Parakeet TDT 0.6B v3 (local) | 8.1% → 7.4% | 11/23 | 60% | 1.6% | 32/32 |
| Resolve 21 Studio (local) | 9.8% → 8.1% | 15/23 | 67% | 2.0% | 32/32 |
| YouTube auto-captions | 8.8% | 5/23 | 53% | 2.9% (raw) | 25/32 |
| whisper.cpp large-v3-turbo (local) | 33.9% → 32.8% | 4/23 | — ² | 6.4% | 25/32 |
| Deepgram nova-3 / Rev.ai | 9.6% / 9.6% | 3/23 | 40% / 33% | 2.1% / 1.6% (raw) | 30/32 |
| Google Chirp 3 | 15.3% | 4/23 | 80% | 2.0% (raw) | 30/32 |

¹ B's pre-fill words came from AssemblyAI, so its B figure is favoured.
² whisper's stumble "recall" is inflated by misplaced words; its dominant
error is deleting repeated takes (one 45-word stretch of repeats became one
word).

On a fluent presenter (B) every recogniser is within 1–3% WER. The halting
presenter (A) is what separates them.

## Timing (unanchored references)

Onset/offset absolute error in ms: median / p95 / share over 120 ms.

| Pipeline | A independent 80: onset | A: offset | A coverage | B blind 40: onset | B: offset |
|---|---|---|---|---|---|
| Producer transcript → MFA (ceiling) | 22 / 111 / 2.7% | 33 / 181 / 9.3% | 98.7% | — | — |
| ElevenLabs → reconcile → MFA-G | 19 / 111 / 3.1% | 32 / 116 / 4.6% | 85.5% | 18 / 57 / 0% | 19 / 55 / 2.5% |
| Speechmatics → reconcile → MFA-G | 22 / 111 / 3.3% | 30 / 79 / 1.7% | 78.9% | 16 / 62 / 0% | 19 / 99 / 5.0% |
| Parakeet → reconcile → MFA-G | 18 / 124 / 5.1% | 33 / 145 / 5.1% | 77.6% | 16 / 70 / 0% | 19 / 141 / 5.3% |
| Resolve → reconcile → MFA-G | 19 / 118 / 5.0% | 33 / 187 / 8.3% | 78.9% | 16 / 57 / 0% | 17 / 55 / 2.5% |
| YouTube captions → MFA | 20 / 118 / 5.0% | 27 / 116 / 5.0% | 78.9% | 16 / 57 / 0% | 21 / 89 / 2.6% |

Every MFA pipeline lands at the same timing quality; **the recogniser decides
words and coverage, MFA decides timing**. n is small (A 76–80 words, B 38–40),
so differences of a few ms are noise.

### The main failure: displaced words (A)

The scorer's 0.5 s matching window hides gross MFA errors as lost coverage.
Counting key words whose same-text MFA word sits 0.5–3 s away:

| Pipeline (A) | Displaced words | All early? | Flagged by agreement (Qwen / Charsiu, τ 70 ms) |
|---|---|---|---|
| ElevenLabs | 8 | yes | 8 / 8 |
| AssemblyAI | 17 | yes | 16 / 17 |
| Parakeet | 17 | 16 of 17 | — |
| Speechmatics | 24 | yes | 24 / 24 |
| Resolve | 26 | yes | 25 / 26 |
| YouTube captions | 28 | yes | — |

B has **zero** in every pipeline. They cluster where the transcript lacks a
false start that is in the audio (MFA stretches the remaining words back over
it) and on short phrase-initial words after a breath ("it", "but", "yes" moved
1.4–2.5 s early). They land exactly on take starts. **The agreement filter
catches essentially all of them (73/75 with licence-safe Qwen)**, so they
surface as *needs review* rather than bad cuts.

### Agreement trade-off

MFA vs Charsiu at τ 70 ms flags 10–16% of boundaries on A and 2–7% on B;
accepted offsets over 120 ms fall from ~4.6% to 0–2% on A. Qwen (80 ms
grid) is the weaker but licence-safe partner. Charsiu's model licence is
unstated: evaluation only.

## Take logic (#53) on machine transcripts (A)

The accepted #53 logic (`discover()` unchanged) on each pipeline's transcript;
scored against the Producer's 15 highlighted spans (±250 ms) and 7 blue picks.
Validation: an exact Sample v2 replica scores 15/15 and 7/7.

| Transcript | Spans recovered | Blue picks matched |
|---|---|---|
| Producer text (Sample v2) | 15/15 | 7/7 |
| ElevenLabs | 12/15 | **6/7** |
| Speechmatics | 10/15 | 6/7 |
| AssemblyAI / Chirp 2 | 11/15 | 5/7 |
| Resolve / Parakeet | 10/15 | 3/7 |
| whisper | 6/15 | 1/7 |

Most misses are displaced first words (above): the take starts 1.3–2.5 s early.
Finding for #45: #53's "pauses over 1.4 s split reads" rule splits genuine
reads when given exact word times (7/7 → 2/7 picks with the key's own times).

### Recording B playback and take rules v2

`b_playback.py` runs the same logic on B (rows = the 9 prompter paragraphs,
since B has no on/off markers) with the recommended pipeline and renders the
default take per row, cut in measured silence.

Producer playback: "almost perfect except row 3". Row 3's good read
(0:55–1:07) was split into four clips because (1) the paragraph's first
sentence was delivered separately, so no single read covered the row, and
(2) the presenter moved "okay" earlier than written, which broke #53's
sentence-by-sentence matching.

**Take rules v2** (`take_rules_v2.py`, a post-processing layer; `discover()`
unchanged), following the Producer's rule *"if the presenter moves on and
doesn't read the part again, the part is probably a keeper"*:

- partial pieces that run on (gap ≤ 1.4 s, no repeated content) merge into
  one delivery; a run covering the whole row is a complete read;
- moved words are reported as differences, never restored to script order;
- every selected take carries a **"differs from script"** flag listing moved,
  substituted, added and skipped words (spoken numerals count as matching);
- earlier full reads are offered as **usable alternates**, newest first;
  the last delivery stays the default; abandoned restarts are not offered.

Results: B row 3 becomes 2 pieces, the second 0:54.6–1:07.3 as the Producer
expected; 10/10 cuts land in quiet. On A, Sample v2 still scores 15/15 spans
and 7/7 picks, and offered alternates match 6 of the Producer's 8 green
alternates (1 extra). All of it is rule-based; no language model is involved.

## Research profile (no script)

- **Native recogniser timestamps** (no MFA), A independent: Chirp 2 32/40 ms,
  Resolve 27/35 ms onset/offset median — usable. ElevenLabs and AssemblyAI
  start words late (51–74 ms median); Parakeet's are unusable (70–81 ms,
  25–31% over 120 ms) — Parakeet requires MFA.
- **YouTube auto-captions** (A and B uploaded unlisted; 0-sample offset vs
  the originals): caption WER 8.8% (A) and 2.9% (B); per-word *start* times
  only, median 64 ms (A) to 108 ms (B) late, 18–42% over 120 ms. Good enough
  for "jump to roughly here" (Research #46). **Captions → MFA** is
  editing-grade: 20/27 ms (A, independent 80) and 16/21 ms (B, blind 40)
  onset/offset median, equal to the best pipelines (Research #47).
- **Speed on this Intel Mac** (relative only; Apple Silicon is the target):
  Parakeet ~17 s per 4 min; MFA ~105–118 s per 4 min; Resolve ~36 s start-up +
  ~118 s per 4 min; whisper.cpp ~474 s per 4 min. A Research hour would take
  roughly 30 min of MFA on this machine; Apple Silicon numbers still needed.
- **Noisy YouTube** (no key, proxy measure): see cleanup.

## Audio cleanup (DeepFilterNet) before transcription

**Verdict: transcribe and align on the original audio. Use DeepFilterNet only
for the edit.** Cleanup before recognition is never clearly better and is
sometimes much worse; before alignment it is roughly neutral.

Every recogniser was re-run on three versions of each recording (raw
recorder audio, Adobe Enhance, DeepFilterNet `-a 30`), then through the same
frozen pipeline (`score_cleanup.py`). Same-text runs re-align the original
transcript on the cleaned audio, so only the audio changes.

| Recogniser (A, halting) | WER raw / Adobe / DFN | Displaced words raw / Adobe / DFN |
|---|---|---|
| ElevenLabs | 2.8% / 4.6% / 5.5% | 8 / 9 / 18 |
| AssemblyAI | 3.1% / 3.5% / 4.4% (names 22 → 13 of 23) | 17 / 17 / 18 |
| Speechmatics | 4.2% / 3.9% / 3.7% | 24 / 17 / 20 |
| Chirp 2 + keyterms | 3.3% / 3.5% / 3.5% | 10 / 5 / 27 |
| Resolve | 8.1% / 6.3% / **36.8%** | 26 / 34 / 68 |
| Parakeet | 7.4% / 6.6% / 7.9% | 17 / 16 / 26 |

- **Recognition:** DeepFilterNet hurt most recognisers on the halting
  presenter. Resolve dropped a third of the words (292 vs 417, full-length
  transcript, so not a truncation). On the fluent presenter (B) every
  recogniser stayed within 0.9–2.5% WER under all three versions. On a noisy
  YouTube street clip (no key; proxy = words two cloud recognisers agreed on)
  Parakeet's recall fell 80.7% → 72.2%.
- **Alignment (same text):** medians move by no more than ±5 ms (A offsets
  slightly earlier and closer, onsets slightly later). B's offset tails get
  worse on DeepFilterNet audio (p95 141–191 ms vs 55–99 ms on the Adobe
  original). YouTube-caption text aligned on raw vs DeepFilterNet audio:
  identical scores on A, ±2 ms on B.
- **Adobe Enhance** is mixed (±2 points WER depending on recogniser), so it
  is not a requirement either.
- The #168 draft binds AudioPrep per stage, so a product can keep cleaned
  audio for the edit while recognition and alignment read the original.

## European languages (Research; recognition only)

Public TEDx talks with same-language human captions as the reference (may be
lightly edited, so WER is pessimistic for both systems); the same 4-minute
window (1:00–5:00) per talk; `eu_wer.py`.

| Language | Parakeet v3 (auto language) | whisper large-v3-turbo (language forced) |
|---|---|---|
| Italian | 2.9% | 1.5% |
| Swedish | 13.5% | 10.0% |
| French | 24.6% | 6.1% |
| German | 54.6% | 15.5% |

- **Parakeet v3 cannot be told the language** and sometimes decodes stretches
  as English (German: "sure if it's this is what john the rhymes wanted" for
  *"bin mir nicht sicher ob es das ist was Shonda Rhimes wollte"*). Fine for
  English and some languages, unreliable for others.
- **whisper with a forced language is much better here**, but slower (~4.5–6
  min per 4-min window on this Intel Mac) and it collapses repeated takes
  (A: 33.9% WER), which matters for presenter footage, less for Research.
- YouTube auto-captions could not serve as a baseline: on videos with human
  captions, the same-language "auto" track is derived from them (0% "WER").
- Next candidate: NVIDIA Canary-1B v2 (same 25 languages, language can be
  forced). Word timing in these languages also needs MFA language models
  (available for German, French, Swedish; not Italian or Finnish). No
  Finnish talk with Finnish captions was found yet.
- Engineering finding: a single unbroken speech region longer than 30 s
  (German talk) breaks segment grouping; segments must be split.

## Narration (AWS Polly) word ends

VERA narration uses Polly neural voices, whose speech marks give word
*starts* only; ends are derived from the next word's start
(`word_start_with_derived_end`). Test (`polly_test.py`, B script as 9
blocks, Joanna and Matthew, ~12 cents): MFA aligns all 333 words and its
onsets agree with Polly's marks (|median| 7 ms Matthew; Joanna a constant
30 ms offset).

| Situation | Derived end vs measured end |
|---|---|
| Word running into the next | 7–32 ms (fine) |
| Word before a pause | late by the whole pause: median 229–522 ms, max 870 ms |
| Block-final word (= file end) | ~125 ms late (silence only; never clips speech) |

A plain silence detector finds pre-pause ends within ~35 ms of MFA on clean
synthetic audio. Proposed on #180 as `measured_audio_boundaries/v1` (−40 dBFS
for ≥ 100 ms, +30 ms tail, bounded by the next onset; narration only), with
an MFA cross-check in the conformance suite.

## Implementation status (#168 / #45)

- Draft #168 schemas (`docs/plans/issue-168/schemas/`): recognition,
  alignment, script reconciliation, refusal. Producer decisions 2–4
  approved; decision 1 (exact schemas) open.
- #45 prototype (local branch `claude/issue-45-word-timing`): every stage of
  the recommended pipelines behind the shared ports, plus a conformance
  suite. Reconciliation parity with this study: 6,032/6,032 units. The
  free local Script to Timeline profile end-to-end on A reproduces this
  study's scores (coverage 77.6%, onset 18/124 ms, offset 34/145 ms on the
  independent 80); the agreement stage flags 16 of 17 displaced words.
- Cloud recognisers are not run-to-run deterministic (a repeat ElevenLabs
  call differed in 4 spans): each cloud call is its own immutable artifact.

## Weaknesses to design around

1. **Displaced words around stumbles and breaths** (above). Mitigation: the
   agreement flag; prefer a recogniser that transcribes false starts verbatim.
2. **Missed words**: coverage 77–86% on A against 98–99% on B; part of A's
   loss is displacement, part real omissions of fragments.
3. **Restarts**: whisper collapses them (disqualifying); others keep most.
4. **Whispered speech**: B's deliberately whispered word "enticing" is the
   blind set's hardest item.
5. **Late native starts** (ElevenLabs, AssemblyAI, YouTube captions): always
   refine with MFA when cutting.

## Limits

Two English presenters, one Intel Mac, small blind sets (40/80 words),
in-sample take evaluation (one Producer example). Apple Silicon and Windows
runs, multilingual (European) fixtures, and a second halting presenter are
the next evidence gates (Research #16).

## Cost

Presenter recordings are rare, so cloud cost is negligible for Script to
Timeline; list prices for these services are on the order of tens of cents to
about a dollar per audio hour (verify before enabling). Research stays free:
captions and Parakeet + MFA are local.
