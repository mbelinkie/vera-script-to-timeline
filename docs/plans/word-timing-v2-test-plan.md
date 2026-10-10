# Word-timing v2 — measurement plan for Claude Code

**Status:** plan agreed with the Producer on 2026-10-09. It follows #51 and #63.

**Executor:** Claude Code running locally on the Producer's Mac, in this
repository.

**Goal:** this is a *measurement study*, not a pass/fail test. Find the most
accurate word-timing approach available, local or cloud. Measure exactly where
and how it fails, so VERA can be designed around its weaknesses. There are no
hard rejection gates. The 40 ms median / 120 ms p95 / 5% figures from #51 are
reported only as reference lines.

The one discipline kept from earlier rounds: settings are tuned on recording A
and then measured once on recording B. Without that, every number would be
flattering.

---

## 1. Why another attempt

#51 and #63 tested only one family of aligners: wav2vec2 and XLSR CTC, and
WhisperX. Their raw medians were 38–50 ms and their p95 values 139–231 ms.

FA-Bench (arXiv 2609.32396, September 2026) scores aligners against
human-labelled word boundaries. Word-tier mean absolute error (MAE), clean
audio, reference text given to the aligner:

| System | TIMIT MAE | Buckeye MAE | Within 50 ms (F1@50, TIMIT / Buckeye) |
| --- | ---: | ---: | ---: |
| TorchAudio CTC (≈ what #51/#63 tested) | 39.8 ms | 42.4 ms | .47 / .53 |
| WhisperX | 37.2 ms | 41.7 ms | .43 / .49 |
| Qwen3-ForcedAligner | 32.2 ms | 33.8 ms | .82 / .84 |
| Charsiu | 28.1 ms | 28.1 ms | .86 / .87 |
| **Montreal Forced Aligner (MFA) 3.4** | **21.8 ms** | **21.3 ms** | **.92 / .93** |
| Olign (commercial API, beta) | 18.2 ms | 22.5 ms | .91 / .91 |

Other findings from the same paper:

- ASR text fed into MFA still scored about 22 ms MAE, so a perfect transcript
  is not required.
- Native ASR timestamps were much worse. Parakeet scored about 80 ms. Most
  commercial APIs scored 48–98 ms. The exceptions were Google Chirp 2
  (27–33 ms) and ElevenLabs Scribe v2 (32–35 ms). ElevenLabs' F1@20 is far
  lower than Google's (.17 against .44), so its low MAE hides imprecise
  boundaries. Most commercial APIs start words late. *(Corrected 2026-10-09
  from the paper's Table 1, Track 2.)*
- Utterance edges were the hardest boundaries. Take edges are exactly that
  kind of boundary.

**Caveats.** The benchmark was written by Olewave, which sells Olign. It
reports MAE and F1 only. Its corpora are not presenter footage. Its code is
licensed noncommercial, so **do not copy any FA-Bench code**.

#63 also tuned its rule on a 43-word synthetic corpus whose medians were twice
as bad as the real footage. Its "true" timings may come from text-to-speech
markers, which give word starts only, so the ends would have been derived.
That corpus is not used here. Record where its timings actually came from if
it is easy to find.

---

## 2. Producer decisions (resolved)

| Topic | Decision |
| --- | --- |
| Pass/fail gates | **None.** Measure and compare. Report the #51 thresholds as reference lines only. |
| 120 ms reporting | Report the share of boundaries above 120 ms, with a one-sided 95% upper bound, instead of "zero allowed." |
| Missed stumbles | Measured as recall, not a pass/fail condition. VERA will be designed around whatever is missed. |
| Cloud services | Any service may receive the two test recordings. The Producer supplies API keys. Expected cost is a few dollars. |
| Licences | MFA's CC BY 4.0 model licence is accepted, with attribution. Qwen3-FA is Apache-2.0. Charsiu is MIT code with an unstated model licence, so it is evaluation-only for now. MMS-FA and CrisperWhisper remain excluded, as in #51. |
| Answer key | **Correct a pre-filled file, never mark from scratch** (section 5). Reuse any timings the Producer already supplied for #51 and #63. |
| Recordings | **A** = `semi1b` (244 s, 444 transcript words, unprocessed 48 kHz), used for tuning. **B** (fixed 2026-10-09) = a different, more halting presenter: `presenter sample 2/IMG_E2549 sample.mp4`, cut losslessly from the synced external WAV (`united by music 1 3-26-esv2-90p-bg-10p.wav`, sample 5021747 = 104.620 s, 226.6 s long). B's audio has Adobe Enhance Speech v2 at 90% applied; the Producer accepts this because audio processing may become a standard VERA step. Report it as a difference between A and B. Used only for the final measurement. |

---

## 3. Setup on the Mac

**The hardware does not limit the choice.** The current test machine is a 2019
Intel Mac that will be replaced. VERA's target is Apple Silicon. Accuracy does
not depend on the machine, so pick the most accurate approach regardless of
what is awkward to run on Intel. Speed measured on Intel is informational only.

Getting the tools running on the Intel Mac:

- **MFA:** install natively from conda-forge in its own environment. If no
  `osx-64` build resolves, use MFA's official Docker image.
- **Torch-based tools** (Qwen3-FA, Charsiu): PyTorch has not shipped Intel-Mac
  wheels since 2.2, so run these in a pinned Linux x86_64 Docker image.

If a tool cannot run on Intel at all, say so and keep it in the plan for an
Apple Silicon run. Do not drop it.
- **Cloud keys:** keep them in `.env`, which is already gitignored. Never log
  them.
- **Private evidence:** audio, transcripts, per-word rows and keys stay in a
  private folder outside git. The repo receives aggregate tables only.
- **Provenance:** record for every run the package versions, model ids and
  revisions, model-file hashes, settings, wall time and peak memory.
- **Dependencies:** give each new dependency a one-line justification in the
  report.

---

## 4. Step 1 — Find what already exists

Search the #51 and #63 private evidence packets (likely under `~/.codex/` or a
Codex worktree's ignored output folder) and the `test files/presenter sample`
folder. Look for:

- the Producer's word timings, either the whole sequence or the frozen 80-word
  set;
- the 14-event disfluency ledger;
- retained Parakeet output;
- the Producer transcript (`accurate transcript from producer.rtf`).

Report exactly what was found: how many words are timed, the format, and
whether both onset and offset are present. If a full-sequence timing file
exists, it becomes the starting point for recording A's answer key in step 3.
**If nothing is found, ask the Producer where it is** before going further.

---

## 5. Step 2 — Run every candidate on both recordings

Running candidates is fine on B. Looking at B's answer key is not, until
step 5.

### Text sources (what words were said)

| Id | Source | Notes |
| --- | --- | --- |
| T-P | Parakeet TDT 0.6B v3 | Retained output for A; run it fresh on B. |
| T-C | Cloud ASR, with verbatim or filler options on where offered | ElevenLabs Scribe v2; AssemblyAI (best current model, `disfluencies` on); Deepgram Nova-3 (`filler_words` on); Google Chirp 2 and Chirp 3 (V2 API, `enable_word_time_offsets`); Speechmatics `enhanced` (fillers kept by default); Rev.ai (`verbatim`, the only provider that advertises keeping false starts). Check each option in the provider's current docs. |
| T-O | Producer transcript | **Diagnostic only.** It measures the aligner's ceiling and is never a shippable option. |

### Aligners (where each word starts and ends)

| Id | Aligner |
| --- | --- |
| A-MFA | MFA 3.x, both the `english_us_arpa` 3.0.0 and the `english_mfa` acoustic models. Unknown words get pronunciations from MFA's G2P model. |
| A-QWEN | `Qwen/Qwen3-ForcedAligner-0.6B` via `qwen-asr`. |
| A-CHAR | Charsiu `charsiu/en_w2v2_fc_10ms`. |
| A-CLOUD | Each cloud service's own word timestamps, taken from the same calls. |
| A-ELFA | ElevenLabs Forced Alignment API: audio plus transcript, the cloud counterpart of A-MFA. Run it on T-O, and on the best T-C source. |
| A-RESOLVE | DaVinci Resolve 21.1.1 Studio transcription (`MediaPoolItem.TranscribeAudio` / `GetTranscription`), which gives word start/end timecodes. It is both a text source and an aligner. Resolution is one frame of the project rate, so it is run at 120 fps (8.3 ms). Added 2026-10-09 because VERA targets Resolve. Adobe Premiere was considered and dropped (the Producer is leaving Premiere). |
| A-OLIGN | Optional, if the Producer gets beta access. Treat it as a lead, since it is the benchmark author's product. |
| A-BASE | The best #51 profile (XLSR CTC), as a control. |

### Shared rules

- **Text normalisation:** expand numerals to words, strip punctuation, and keep
  the original display token beside each word.
- **Segmentation:** use an independent VAD pass over the whole recording, with
  300 ms padding and segments of 30 s or less. Parakeet's segment anchors are
  not used.
- **Missed speech:** any speech region of 150 ms or more with no aligned word
  is reported as `unrecognised_speech`.
- **No reference leakage:** the script and the Producer transcript never go
  into a recogniser, and recogniser text is never "repaired" toward them.

---

## 6. Step 3 — Build the answer keys by correction, not from scratch

The Producer adjusts pre-filled timings in **Audacity**, which is free.

Why Audacity and not DaVinci markers:

- Resolve markers snap to video frames. At 29.97 fps that is 33 ms per frame,
  about ±17 ms of rounding, which is too coarse to tell a 20 ms system from a
  40 ms one.
- Resolve markers are single points, so start and end would need separate
  markers.
- Audacity label regions are sample-accurate, have a draggable start and end,
  and import and export as plain text.

### Pre-fill

The pre-fill is the **per-boundary median of the three structurally different
aligners** (A-MFA, A-QWEN, A-CHAR), each run on the *Producer transcript*.
Using a median rather than any single system avoids favouring one competitor.
If a full-sequence Producer timing file already exists for A, start from that
instead.

Claude Code writes one Audacity label file per recording:

- **`<rec>-words.txt`:** one region per word, as `start<TAB>end<TAB>word`, in
  seconds.
- **`<rec>-check.txt`:** a second label track that flags only the words worth
  attention. These are words where the three aligners disagree by more than
  40 ms, take edges, unknown words, and speech regions with no word (where a
  stumble may need adding).

### Producer instructions

Claude Code writes these out step by step. In outline:

1. Open the native 48 kHz audio. Choose Import ▸ Labels for both files.
2. Use spectrogram or multi-view, and zoom in at the flagged words.
3. Drag edges that are wrong. Fix misspelled words. Add a region for any
   stumble or fragment the pre-fill missed, tagged `FRAG`, `REP` or `FILLER`.
4. Skim the rest.
5. Choose Export Labels.

The boundary rules fit on one page:

- A word starts at its first sound. For a word-initial stop after silence,
  that is the burst.
- A word ends at its last sound, including fricative or aspiration tails.
- Breaths are not part of words.

Recording B has no Producer transcript unless the Producer supplies one. Its
pre-fill uses the best cloud transcript's words, and the Producer fixes words
as well as timings.

### Bias checks

- **Anchoring:** if only the independent 80-word set exists, compare the
  Producer's *corrected* timings for those 80 words against their *original*
  independent timings. The gap measures how far the pre-fill pulled the
  Producer, plus ordinary human inconsistency. Report it next to every system
  number.
- **Human floor:** if a full file already exists, have the Producer re-time 40
  random boundaries from scratch instead. Report the median and p95 gap.

Claude Code validates every exported file: times in order, no overlaps, every
word present, legal tags. Then it freezes the file and records its hash.

---

## 7. Step 4 — Measure and tune on recording A

### Classes and metrics

Every boundary is classed as one of:

- `take_edge`: the first or last word of a take;
- `pause_adjacent`: 150 ms or more of silence on that side;
- `connected`: everything else.

For every text-source × aligner pair, report onset and offset **separately**,
by class:

- median, p90, p95 and max error;
- signed bias;
- share above 120 ms, with a one-sided 95% upper bound;
- coverage.

### Small, cross-validated improvements

Tune these on A with leave-one-phrase-out cross-validation. Keep the total
number of tuned parameters to 5 or fewer, and report how many configurations
were tried.

- **Bias correction:** one constant onset shift and one constant offset shift
  per system.
- **Silence snap:** pause-adjacent boundaries move to the nearest energy
  threshold crossing within ±60 ms.
- **Agreement filter:** accept a boundary when MFA and a neural aligner agree
  within τ, and mark it "needs review" otherwise. Report the **trade-off
  curve**: share of boundaries marked needs review against the error of
  accepted boundaries, for τ = 10…100 ms. This is the main design input.

### Also report

- **Word accuracy:** WER and **stumble recall** for each text source.
- **Speed:** wall time and peak memory for 4 minutes of audio, labelled with
  the machine they were measured on. Intel figures are informational; Apple
  Silicon figures are wanted when a machine is available. Speed never removes
  a candidate from the accuracy ranking.

Then freeze the chosen settings in `word-timing-v2-frozen.json`, with model
hashes. Do this *before* opening B's answer key.

---

## 8. Step 5 — Measure once on recording B

Run the frozen settings on B and report the same tables. No retuning on B. If
the numbers fall well short of A's, report that rather than adjusting.

---

## 9. Deliverables

1. **`docs/investigations/word-timing-v2-results.md`**, aggregate only:
   - an accuracy profile for every approach;
   - a ranked recommendation;
   - the trade-off curve;
   - the anchoring and human-floor numbers;
   - a **"weaknesses to design around"** list. Examples: misses fragments, late
     on plosive onsets, connected boundaries in fast speech need review N% of
     the time, cloud required for stumble recall.
2. A private evidence packet: per-word rows, label files, run logs and hashes.
3. A short listening check. Claude Code picks 20 accepted cut points and 10
   needs-review points at random and exports them as an Audacity label file.
   The Producer auditions them.

---

## Sources

- FA-Bench paper (vendor-authored): https://arxiv.org/abs/2609.32396
- FA-Bench repository (noncommercial; do not copy): https://github.com/olewave/fa-bench
- MFA `english_us_arpa` 3.0.0 model (CC BY 4.0): https://mfa-models.readthedocs.io/en/latest/acoustic/English/English%20(US)%20ARPA%20acoustic%20model%20v3_0_0.html
- Qwen3-ForcedAligner-0.6B (Apache-2.0): https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B
- Charsiu (MIT code): https://github.com/lingjzhu/charsiu
- VERA #51: https://github.com/mbelinkie/vera-script-to-timeline/issues/51
- VERA #63 handoff: `docs/investigations/issue-63-llm-evaluation-handoff.md` on branch `codex/issue-63-ctc-disagreement`
