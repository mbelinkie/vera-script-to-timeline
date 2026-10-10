# Codex second-opinion queue (held: Codex out of usage, 2026-10-10)

Run these through the Codex CLI when usage returns. Each item names the file
and the question. Do not send private transcripts or audio (#53 privacy rule:
no hosted LLM processing of private transcripts); send code, docs and
aggregate numbers only.

1. `docs/investigations/word-timing-v2-results.md` (when written): is the
   ranked recommendation supported by the numbers? Any metric or
   pre-registration violation (`scripts/word-timing-v2/SCORING-RULES.md`)?
2. `docs/plans/issue-168-recognizer-aligner-ports.md`: gaps against #168's
   acceptance list, D-P009, and Research #16's normalized-artefact rules.
3. `scripts/word-timing-v2/reconcile.py`: can name-spelling reconciliation
   ever rewrite a non-name word or invent a word?
4. Cleanup finding: is "agreed-core recall" (words two cloud recognisers both
   heard on raw audio) a fair proxy, given it is built from raw audio?
5. #53 re-run on recogniser transcripts (when done): is the comparison against
   the accepted Sample v2 takes fair?
