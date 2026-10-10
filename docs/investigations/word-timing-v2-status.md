# Word-timing v2 — status (2026-10-10, end of day)

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

## Next

1. Finish the Qwen/Charsiu runs on the reconciled text, compute the remaining
   agreement curves, then freeze `word-timing-v2-frozen.json` (pipelines, the
   untuned decision, tau, model hashes) **before** scoring anything on B.
2. Run the frozen pipelines on B. Score timing against the blind set only.
3. When the Producer returns `answer-key/rec-b/rec-b-markers-corrected.csv`
   (the light words-and-stumbles pass), score WER, stumble recall, name
   spelling and gross errors on B.
4. Write `docs/investigations/word-timing-v2-results.md`, the listening-check
   label file, and recommend a local and a cloud pipeline (D-P007 softened).
5. Then: re-run the #53 take logic on the new transcripts. Consult Codex via
   its CLI for a second opinion.

## Decisions on record

- Local pipeline required; a clearly better cloud pipeline may be offered too.
- Transcription is take-agnostic; take logic belongs to #53/#45.
- B's answer key may use the script for name spelling only.
