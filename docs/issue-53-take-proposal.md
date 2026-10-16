# Issue 53 — row parsing algorithm and integration proposal

This is a local prototype for judging take logic **assuming accurate transcript
text**. #51 remains responsible for choosing adequate recognition and acoustic
timing. No provider is selected here. The bounded prototype and handoff are
Producer accepted on 2026-09-04; see `docs/issue-53-acceptance.md`. #45 still
requires its remaining dependencies and separate shared-contract approval.

The Producer's seven supplied rows are the recording units. A row can contain
several sentences and several frozen #37 beats. Row grouping does not rewrite
the script, beat IDs, or the accepted sentence-level export. Private row text
and binding evidence stay in Run A. No production schema is implemented.

## Producer review revision — 2026-09-04

The current experimental algorithm is `row-review-2`. The accurate full-text
run removes **all** highlights and approximate clock labels before discovery;
it evaluates the exact colored word spans only after freezing the result.
This is an in-sample refinement, not held-out validation. No new provider
transcription or acoustic alignment is performed, and #51 remains separate.

These refinements supersede the corresponding initial rules below:

- An opening/closing word substitution may still represent a complete read.
  For rows of at least seven words, two neighboring equal tokens can anchor
  such a boundary. The existing substitution/addition budgets still apply,
  with every difference marked approximate. This avoids dropping an otherwise
  complete read because of a changed name or word at its edge.
- For rows lacking a complete read, authored script sentences seed partial
  candidates before broad local alignment. At least 70% of the longer of
  expected/observed sentence tokens must be equal; repeated opening prefixes
  split restarts. These sentence seeds retain row identity and missing tokens.
  They do not turn each sentence into a new frozen beat or force the whole
  recording into sentence-sized takes. This experimental splitter uses `.?!`
  followed by whitespace; abbreviation-heavy scripts may need explicit units.
- A highlight may span several reads or cross a row boundary. The evaluator
  compares the **union of exact discovered word ranges**, rather than calling
  a whole timecode block or colored run a take. Non-highlighted words in the
  same block remain excluded from the reference choice.
- `options.include_partial_alternates` is a boolean, default **true**. The
  Producer explicitly requested useful partial alternatives alongside complete
  alternatives. Each names covered and missing row tokens. Set it false to hide
  that list, while retaining all candidates/evidence and leaving complete
  defaults and missing-row assembly fallback intact. The CLI override is
  `--partial-takes include` or `--partial-takes hide`.
- Assembly pieces retain substituted words with explicit transcript diffs and
  review reasons, instead of deleting those spoken words and leaving tiny
  isolated fragments. Deletions remain uncovered. Joins remain review-only.
- Off-script mentions of a `first`, `earlier`, `previous`, or `last` **take**
  create `editorial_signals`. The nearest preceding row/partial coverage is a
  tentative context; earlier reads covering at least 70% of that same span are
  linked as options. A first-take mention offers the earliest such read. These
  are untrusted speech observations, never executable instructions or evidence
  of speaker authority. Scripted matching wording is excluded; negation is
  flagged; quotations, jokes, unclear scope and antecedents need human review.
  The affected default is withheld as `producer_choice_required`, while
  `suggested_last_complete` and the ordinary assembly remain visible. No earlier
  candidate is automatically applied, and prior Producer decisions are intact.

`timing_links.py` optionally links the entire accurate transcript to retained
timed words after parsing. It transfers an endpoint only if that token has one
exact correspondence in **every optimal edit alignment**; deleted, substituted,
or ambiguous repeated words get no borrowed timestamp. It preserves supplied
precision/nulls and performs no interpolation or new acoustic alignment.
Producer clocks are navigation hints only and are never inputs to this pass.
Transferred acoustic times remain estimates pending listening, not verified cuts.

Future contract review must additionally include the user preference, partial
coverage lists, review-only editorial signals (text span, tentative target,
candidate options, negation/ambiguity, review state), and timing-link provenance.
It must not confuse these with authenticated Producer decisions or modify
`TakeAssignment` in response to recorded speech.

## Boundary correction after Producer playback

The Producer reported clipped opening/closing words at most cuts in the first
reference video. That playback failure overrides any implication that unique
text-to-timestamp linkage is enough to cut speech. **Transcript timestamps are
search anchors, never final edit boundaries. Open and close cuts in quiet audio.**

The isolated `boundaries.py` prototype now measures decoded original audio in
10ms windows, retaining all channels. A quiet interval needs every channel's
RMS at or below -40 dBFS, peaks below -28 dBFS, and at least 120ms duration.
This rejects isolated zero crossings and protects against a transient or speech
in the other channel. These are declared experimental measurement thresholds;
quiet speech/breaths and noisy recordings still require Producer judgment.
The measurement does not denoise, level, or change the source audio.

For each selected word span, target ten frames before/after the transcript's
outer estimates, then search up to 0.8 seconds farther outward for a frame
boundary at least 20ms inside a measured quiet interval. Check the entire
extension against adjacent recognized speech, not just the chosen point. Never
cross another read to reach a more distant silence. All results retain the
selected quiet interval, actual padding, review reasons, and `safe: false`.

When requested padding cannot fit, the default policy reports an exception.
The explicitly enabled `allow_reduced_padding` preview policy may use the
largest smaller padding that still lands in quiet without crossing neighboring
speech, leaving at least two frames outside the transcript estimate. It must
report `reduced_padding_to_fit_quiet_gap` and actual frame counts. Source limits
or no usable quiet interval stay unresolved; never silently fall back to a tight
word-edge cut. Padded review-only geometry is distinct from waveform-supported
geometry, and neither is certified by energy alone. The earlier `_handles`
transcript geometry is only a starting proposal, not an executable final cut.

Producer acceptance must listen around each new edge and verify complete words,
natural breathing room, and absence of the adjacent take. Future #45 boundary
contracts need quiet-evidence provenance, measured interval, requested/actual
padding, explicit reduced-padding policy, and playback review status. No shared
contract is changed here.

## Experimental seam

`experiments/issue53/takes.py` exposes a pure `discover(packet)` function.
`take-experiment/1` contains:

| Field | Meaning |
| --- | --- |
| `source` | Local alias, full duration in seconds, rational `fps: [numerator, denominator]` |
| `rows[]` | Stable experimental ID, exact row text, existing beat IDs when available |
| `words[]` | Recognized text, source-relative `start`/`end` or null, timing precision, provenance, optional confidence/cue interval |
| `provenance` | Immutable transcript/version and adapter identity; private locators/hashes remain local |
| `audio_activity[]` | Source-relative activity intervals and the measurement method; evidence, never speech truth |
| `decisions` | Opaque existing Producer decisions copied intact and never overwritten |

The adapter preserves absent times as null, retains recognized wording, and
does not interpolate word edges. Word timing may be `acoustic`, `derived`,
`cue`, or `missing`; multi-token provider items retain a shared interval.
Source clocks must already be normalized by the adapter. Array order is
transcript order; nonmonotonic known starts block default suggestions rather
than silently reordering words. Invalid/out-of-bounds/overlapping timing stays
visible. Provider confidence is retained separately and does not score acting.

Unknown top-level/word fields are rejected. Discovery has no reference argument,
does no I/O, and reads no provider-specific fields. Case/highlight labels and
Producer reference times are available only to the separate evaluator after
the discovery report is frozen. New engines change the adapter, not discovery.

For normalized input, from the repository root:

```sh
rtk uv run --frozen python -m experiments.issue53.cli \
  --input /private/local/normalized.json --output /private/local/new-report.json
```

These are placeholders, not Run A locators. The destination parent must exist
outside Git. The CLI uses exclusive creation with mode 0600; it neither replaces
inputs nor overwrites prior evidence. It prints no transcript, source path, or
hash. Run A's exact adapter and immutable inputs are retained privately.

## Deterministic take rules

1. Normalize Unicode NFKC/case and apostrophes, then tokenize words. Preserve
   original text/provenance alongside tokens. Punctuation/case equality is
   lexical equality only. Numbers, names, synonyms, and semantic paraphrases
   are not silently rewritten.
2. Search the completed transcript backward for each row's opening and closing
   words. Bound a candidate window to 1.3 times the expected token count.
   A repeated opening prefix beyond its count in the row signals a restart;
   a repeated phrase actually written inside the row is allowed.
3. Use deterministic unit-cost edit alignment. A complete proposal covers
   every expected token without deletions, starts/ends on equal tokens, allows
   at most floor(15% of row length) substitutions and floor(10%) additions.
   Every changed word is still an explicit diff; approximate is never exact.
   These are reviewable experimental thresholds, not a performance score.
4. A recognized pause over 1.4 seconds divides the search. This is a conservative
   take-boundary heuristic: an intentional long pause can yield partials instead
   of a whole-row suggestion. Missing timing cannot prove continuity. Playback
   must resolve these cases; the threshold is explicitly submitted for review.
5. Resolve overlapping complete proposals by most equal words, then fewest
   edits, then latest start. Equal-quality same-span row matches remain
   ambiguous and get no default. Keep unmatched words available for later passes.
6. Recover partials/pickups with local lexical alignment (+3 equality, -3
   substitution/gap); require at least min(3, row length) equal tokens and
   equality over at least half the observed span. This local score discovers
   text correspondences only. Unmatched spans remain candidates of their own.
7. Attach otherwise unmatched adjacent material when it lies within 0.6 seconds
   of one candidate, or is at least 0.05 seconds closer to one of two neighbors.
   Recompute the diff/completeness after attachment. This prevents a clean row
   substring inside an ad-lib from falsely appearing as an exact take. Equally
   plausible boundaries remain separate for review.
8. Return candidates in transcript/source order. A usable *suggestion* is an
   unambiguous complete row without invalid, reversed, or overlapping known
   timing. Missing timing keeps the suggestion but withholds a handled cut.
   Search those candidates backward: the last is the suggested default; every
   earlier eligible complete read is an alternative in source order. No acting
   quality, approval, or active production assignment is inferred. An existing
   Producer decision suppresses application of the default and remains intact.
9. Only when no unambiguous complete row exists, propose a partial assembly.
   Traverse candidates backward, take still-uncovered equal row tokens, split
   discontinuous pieces, and order the pieces by script position. Each piece
   names candidate, source token span, timing/context, handles, and uncovered
   tokens. Every join is `review_needed`. No splice is rendered and no partial
   assembly becomes a default. This greedy coverage proposal does not optimize
   performance, continuity, or number of cuts.

## Boundaries and reporting

All ranges are half open and source-relative. For acoustic outer estimates,
propose `floor(start × fps) - 10` through `ceil(end × fps) + 10`. Rounding moves
outward, providing ten to less than eleven source frames per side. Do not clamp
an out-of-source proposal, shrink handles into a short gap, or cross adjacent
recognized speech. Shared/coarse/derived/missing timing, unlocated speech, or
audio activity in a handle withholds that handle. Retain the candidate and broad
source playback context with the exact reason.

Energy measurement checks the complete retained source but cannot distinguish
speech from breath/noise or prove silence. Every boundary remains
`review_needed`, `safe: false`, until Producer playback; a playable proposal
is not a safe-pass claim. Low-quality timing from #51 cannot establish a logic
failure or pass here. Synthetic logic assertions and real listening evidence
are separate.

Reports retain row groups, every candidate and normalized token, differences,
defaults/alternatives, assemblies, evidence components, timing uncertainty,
uncovered/ambiguous rows, and a continuous partition of the entire source into
candidate-review and unassigned-audio-review intervals. The latter includes
intro, pauses, tail, off-script speech, and material missing from recognition;
none is silently called silence or discarded.

Post-discovery evaluation accounts for every frozen highlighted case and every
complete/partial/count-only Producer timing case. Full-transcript edit counts
describe recognition separately. Temporal overlaps and reference-token links
identify matches to inspect, possible false splits/merges, extras, misses, and
unknown cases. Coarse boundaries, multi-take labels, and repeated text make
those **review leads**, not certified error counts. Missing outer edges remain
unscored. No reference result repairs or rewrites discovery.

## Exact proposed production contract changes for #45

This is a proposal requiring a separate Producer-approved contract-change note.
No shared schema, generated type, or accepted fixture changes in #53.

| Proposed entity/change | Required fields and behavior |
| --- | --- |
| `RecordingRow` (or equivalent immutable recording-unit grouping) | ID, frozen document/prompter revision, ordered existing beat IDs/token ranges, exact expected text/hash. Several beats may share one take; no sentence/beat regeneration. Reject gaps, overlap, text mismatch, or stale binding before production alignment. |
| `ShootTranscript` + word record | Immutable ID/version, source identity/duration/rational frame rate, source-relative nullable start/end, explicit precision/missing reason, recognized text, raw word/cue identity, adapter/profile provenance, optional confidence. Engine output is behind the adapter. |
| `TakeCandidate` + group | Recording-row ID plus existing beat mappings, source-ordered recognized-token range, immutable transcript/alignment versions, lexical kind/diff, multiple row hypotheses, separate completeness and timing evidence, null-or-proposed speech/handled ranges, warnings, review state. No single opaque score. |
| `TakeDefaultSuggestion` | Group ID, last eligible complete candidate ID or null, all earlier complete alternatives, algorithm version/reasons; separate from `TakeAssignment`. Reprocessing never changes existing decisions. |
| `PartialAssemblyProposal` | Row ID, ordered candidate/source subranges, covered/uncovered row-token ranges, per-join review reasons, review-only state. This is not a keeper, splice assignment, or conform input. |
| `TakeAssignment` integration | Preserve actor/version/lock and approved choices. Any future multi-beat source take must map each beat into that same candidate without duplicate picture/audio; row-level suggestions cannot silently alter the accepted one-active-take-per-beat rule. |

Why: a sentence-only candidate model cannot represent the Producer's whole-row
reads or truthfully express missing edges and partial assemblies. What breaks:
consumers assuming one row equals one beat, all times are numeric and verified,
or a default is an approval must be updated. Regeneration: add corresponding
JSON Schema definitions and regenerate TypeScript/Python contracts in the
future approved slice; none exists or is regenerated here. Existing frozen
schemas/fixtures remain byte-identical. Migration must preserve immutable
transcripts and assignments and reject stale row bindings.

Acceptance additions for that contract: cross-beat row binding, unknown timing,
complete/partial/modified reads, ambiguous rows, last-complete/alternative
preservation, prior-decision protection, review-only assembly joins, source
accounting, and producer-confirmed handled edges. #45 must also pass its other
dependencies, including #51; acceptance of this logic never chooses a model.

## Remaining judgment calls

Review the long-pause, approximate-completeness, adjacent-word, and assembly
policies above. They are transparent heuristics, not general semantic or acting
understanding. Equal-quality overlapping rows with different spans, very short
pickups, heavily altered openings/endings, long within-row pauses, and missing
recognition can leave unresolved coverage. Speaker identity, phonetic matching,
and performance continuity are outside this experiment. The row-to-existing-beat
binding and final schemas remain #45's approved integration work.

The local acceptance packet is available through the ignored workspace locator
`out/issue-53-review/REPORT.md`; `playback.command` alongside it plays original
source ranges without creating media. It includes both retained normalized
variants and separate reference evaluation. This locator contains private
material and must never be committed or uploaded.
