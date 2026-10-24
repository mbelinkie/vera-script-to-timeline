# Fish/Polly timing study and retained-take recovery (#289)

Status: in progress. No recovery or provider ranking is established.

## Frozen protocol (before acoustic scoring)

Run local recovery first on the retained failed take, without synthesis. Preserve
the source audio, native response, failed assets and prior cache. Use a new output
identity; never call acoustic starts provider marks. Public model acquisition is
separate from network-denied private inference. Private inputs and per-word output
stay outside Git; only safe aliases and aggregates belong here.

Require 100% exact authored-token coverage, strictly increasing starts, positive
acoustic support within unchanged audio, and unambiguous occurrence mapping.
Omissions, additions, repeats with ambiguous correspondence, nonfinite or collapsed
intervals, out-of-bounds results and missing acoustic support refuse admission.
Recognizer and aligner scores are not calibrated confidence probabilities.

Use MFA as the recovery candidate and a structurally independent local aligner as
an error detector. Predeclare a 70 ms agreement threshold (the shared package's
existing threshold); disagreement abstains, rather than silently choosing an edge.
Agreement alone is not acoustic truth. Independently check acoustic boundaries,
including every formerly tied word, every disagreement and a systematic sample of
the remaining words. Report the checked denominator and unresolved cases. Require
checked onset p95 <= 150 ms (the existing narration evaluation gate), max <= 200 ms,
and zero admitted boundaries outside declared uncertainty. Any required boundary
without independent checked evidence remains refused. Report median/p95/max,
false-confident count, abstentions, coverage, wall time and reference limitations.
Do not call an unreviewed machine prefill human verified.

Public comparison: three original synthetic English texts, 10–20, 40–60 and
90–120 words; three independent generations per provider and text (18 takes).
Include contractions, repeats, punctuation, numerals and real Fish chunking.
Freeze texts and settings before calls. No retry-until-valid selection. Keep native,
normalized and recovered outcomes separate, and distinguish Fish audio ends from
Polly text byte offsets. Words in one take are correlated; this is exploratory,
not an estimate of production failure rates.

Polly total authorization is $1 for public text only. Preflight current official
audio-plus-marks pricing; reserve the conservative entire call cost before each
request, including uncertain failures. Parent serializes calls. Fish has a hard
$0 cap with no paid fallback. No private provider calls, Resolve or #275 benchmark
execution is part of this issue.

## Initial code-path audit

Both providers supply native starts to the shared synthesis/cache, normalization,
measurement and compiler paths. Production synthesis does not run MFA for either.
The shared `MfaAligner` refuses `reference-text` artifacts by design; the old
`scripts/word-timing/mfa_reference.py` is explicitly evaluation-only. Recovery
must use a supported explicit admission path with acoustic provenance, rather
than relabeling that evaluation bypass as production success.

## Results

Pending local engine feasibility, recovery integration and paired provider calls.
The default provider remains unchanged. #275 remains blocked until a tested
recovery handoff is delivered; a public surrogate alone cannot clear its private take.
