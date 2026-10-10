# Word-timing v2 — status (2026-10-10, overnight update)

This is the resume point for any session picking up the study. The plan is
`docs/plans/word-timing-v2-test-plan.md`; the pre-registered scoring rules and
their change log are in `scripts/word-timing-v2/SCORING-RULES.md`. Private data
(audio, keys, per-word rows) is in `~/.local/share/vera/word-timing-v2/`, never
in git.

## Done

- **Step 1:** #51/#63 evidence was found. The 80-word independent set and the
  14-event ledger are in `~/.local/share/vera/issue-51-preflight/run-a/`.
- **Step 2:** every candidate ran on A and B. That covers 8 transcribers
  (Speechmatics, AssemblyAI, Deepgram, ElevenLabs via OpenRouter, Rev.ai,
  Chirp 2/3, Resolve 21.1.1) with and without script keyterms, and 4 aligners
  (MFA arpa/mfa, Qwen3-FA, Charsiu).
- **Step 3:**
  - A's key is corrected in Audition and frozen (`answer-key/rec-a/rec-a-markers-adjusted.csv`).
  - B's 40-word blind set is frozen (`answer-key/rec-b-blind/rec-b-blind-adjusted.csv`).
    Blind word 18, "enticing", is deliberately whispered.
- **Script-informed pipelines:** `prompter.py`, `reconcile.py`
  (`text` is used for timing, `heard` is fidelity evidence), and `guide_dict.py`
  with MFA `--extra-dict`.
- **Step 4 so far (A):**
  - The anchoring check found 70–75% of pre-filled boundaries kept, so the
    independent 80 words are the unanchored timing reference.
  - The best pipelines (recogniser → reconcile → MFA-G) score
    19–22 ms onset median and 30–33 ms offset median on the independent set,
    equal to MFA on the Producer transcript.
  - Coverage of 79–86% is the main weakness.
  - Cross-validated bias/snap tuning does not generalise, so the pipelines stay untuned.
  - First agreement curve: MFA-vs-Charsiu at tau 70–100 ms flags 5–10% of
    boundaries and cuts offsets over 120 ms from about 4.6% to under 2%. Onsets are not helped.

## Overnight (autonomous, no Producer input needed)

- **Research profile on A:** native timestamps from Chirp 2 (32/40 ms
  onset/offset median) and Resolve (27/35) are close to the MFA-refined ones.
  MFA mainly helps recognisers that start words late (ElevenLabs, AssemblyAI).
  MFA takes about 105–118 s per 244 s clip on this Intel Mac.
- **Agreement curves on A:** with Charsiu as the partner at tau 70, review is
  10–16% and accepted offsets over 120 ms fall to 0–2%. Qwen as partner is
  weaker (80 ms grid).
- **Frozen** at `28d94c7` (`scripts/word-timing-v2/word-timing-v2-frozen.json`):
  15 pipelines, untuned, tau 70, Charsiu primary (evaluation-only licence) and
  Qwen licence-safe.
- **Step 5 on B, blind set (n = 40), scored once:**
  - All 10 MFA pipelines (Script to Timeline and Research): onset median
    16–18 ms, p95 55–70, 0% over 120; offset median 17–19, p95 55–99, 2.5–5%
    over 120 (1–2 of 40 words).
  - Native timestamps: Chirp 3 23/39, Resolve 30/51, Chirp 2 20/46. Offsets
    run late (+16 to +28 ms). ElevenLabs and AssemblyAI start late
    (+58 to +86 ms).
  - Agreement filter at tau 70: 2–7% review. It removes no onset errors (there
    were none over 120) and leaves one offset error.
  - **Caveats:** n = 40. The blind words were drawn from Speechmatics' output,
    so blind coverage (100%) says nothing about missed words. Coverage, WER,
    stumbles and names on B come from the full key pass.

## Next

1. (done) Freeze; (done) B blind-set timing.
2. (done) Research no-script MFA on A and B.
3. When the Producer returns `answer-key/rec-b/rec-b-markers-corrected.csv`
   (the light words-and-stumbles pass), score WER, stumble recall, name
   spelling and gross errors on B.
4. Write `docs/investigations/word-timing-v2-results.md`, the listening-check
   label file, and recommend a local and a cloud pipeline (D-P007 softened).
5. Research profile: run recogniser → MFA **without** script reconciliation on A
   and B. Report the no-script accuracy, speed and cost per hour, and whether
   recogniser timestamps alone suffice for Research's volume use.
6. Then: re-run the #53 take logic on the new transcripts. Consult Codex via
   its CLI for a second opinion.

## B full key (2026-10-10)

- Frozen as `answer-key/rec-b/rec-b-markers-final.csv` (sha `b58b3e9a…`): the
  Producer's light pass, with the 40 blind timings restored and 2 `??` deleted.
  561 words, only 4 stumbles.
- WER is 0.9–2.3% for every recogniser. AssemblyAI is favoured, because the
  pre-fill words came from it. Reconciliation brings names to 32/32 for all.
  Resolve → reconcile → MFA reaches WER 2.0%, coverage 98.0%, and a gross
  rate of at most 0.7%: close to cloud on B (the A gap was larger).
- **Product framing (Producer):** three options: Resolve Studio, an option
  for free Resolve, and cloud. If Studio and a free option are close, prefer
  the one that works for everyone. Parakeet (free, local) is being scored.

## Open questions (parked)

- **Free-for-all VERA (Producer, 2026-10-10):** the Resolve route needs paid
  Resolve Studio. What is the best *free* option? First candidate: Parakeet
  TDT 0.6B v3 (plan T-P, still unscored: retained output for A, fresh run
  needed on B) → reconcile → MFA. Also consider an open Whisper-family
  recogniser. Answer this after the main report.
- **Headless Resolve:** works (`resolve_headless.py`, identical to the GUI run).
  Untested: a locked screen, SSH, or running as a launchd service.

## Decisions on record

- Local pipeline required; a clearly better cloud pipeline may be offered too.
- Transcription is take-agnostic; take logic belongs to #53/#45.
- B's answer key may use the script for name spelling only.
- One engine should serve both VERA apps. Research has no script, high volume
  and a looser accuracy need, so the stages are switchable per product.

## Autonomous run authorisations (Producer, 2026-10-10)

- After the study deliverables (cleanup test, results report, listening-check
  file, #53 re-run, Codex CLI consult), start #45 on a new branch off main.
  Commit locally only; the Producer reviews before any merge.
- May push `claude/word-timing-v2` to origin. No PR, no GitHub comments.
- Cloud spend up to $10 more; stop and ask beyond that.
- May test DeepFilterNet on one public YouTube talking-head clip (local only,
  never committed), with a consensus reference, clearly caveated.
