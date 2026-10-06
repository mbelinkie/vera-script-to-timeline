# Checkpoint 11 proposed plan: canonical row omission revision

Checkpoint10's verifier completed plan/segment/confirmation reviews. Its 42-case
expanded run and two new boolean checks pass; full 292-case validation is running.
No checkpoint11 implementation begins until that source is verified and saved.
The producer's whole-row recording rule and three original named positive cases
remain unchanged. No actual native/provider work is authorized by this segment.

## Bounded scope and interface

Implement one issue-owned pure TypeScript transformation for a previously
explicitly accepted contiguous interior omission in one active narration row.
Input is the validator-passing current ScriptDocument, row ID and exact removed
token IDs, plus its expected canonical input hash. Output is a new complete
validator-passing ScriptDocument/canonical bytes and a whole-row regeneration
requirement. This function does not authenticate acceptance or prove audible
absence. The later file workflow must rederive supported audio evidence, bind
its exact baseline/script/observation/render/report bytes, obtain explicit
accept/reject and recheck freshness before invoking it. No arbitrary operator
'removedTokens' file is treated as authorized evidence. The trusted pure function
is a transformation building block, never a standalone public acceptance CLI.

Keep this segment separate from changed-UID capture mapping, composed visual
proposal evaluation, decision-file/replay, service invocation/materialization,
new build IDs and baseline promotion. Those remain integration work after its
finished-code review. In particular, do not silently substitute original geometry
for edited audio to trick the visual verifier into accepting a mixed edit.

New `packages/contracts/src/issue-144-text-revision.ts` and issue-owned tests.
Use the accepted `validateScriptDocument`, `canonicalJson`,
`sha256CanonicalJson`; do not implement another serializer, token parser or
validator. Existing compiler/service/Studio/jobs, contracts/generated types,
accepted tests/fixtures/goldens and lockfiles remain unchanged. No dependency.
Add the new module's bytes to CODE_PATHS only after checkpoint10 is saved.

## Exact text and row invariants

Use the main plan's already reviewed ASCII-whitespace join rule: ordered,
unique, nonempty contiguous selected IDs, at most 64 tokens, retained neighbors
on both sides. Preserve all surviving token IDs/values/order. Replace the span
from previous retained token.endOffset through next retained token.startOffset
with exactly one ASCII space. Boundary gaps must contain only ASCII space, tab,
CR or LF; punctuation/other whitespace in these joining gaps refuses. Shift
later token offsets by the actual JavaScript UTF-16 length delta, never code-point
or UTF-8 byte count. No grammar/capitalization rewrite or spoken reordering.

The plan also says sentence boundaries refuse. Plain W1 words have no ambiguity;
for safety, refuse terminal sentence punctuation at the prior retained boundary
or anywhere in the removed interval rather than joining sentences implicitly.
Review this conservative interpretation explicitly; do not broaden punctuation
support. Tests include punctuation-in-gap, selected sentence terminator and
non-ASCII separators. Other punctuation inside an explicitly removed token is
removed with that token; nothing outside the selected/joining span is rewritten.

Clone before changes. Bump only the changed narration's version by one. Do not
alter row identities/order/metadata/state/timing policy or another narration
row's text/tokens/version. Original document stays intact. A new revision
increments liveHeadSequence exactly once with safe-integer guard, clears local
liveStateVector, and uses the real canonical serializer to calculate
liveContentHash excluding itself. Identical inputs return identical bytes.

## Anchors and revision validation

Inspect every actual TextAnchorRange in visual events, host visibility spans,
annotations and performance beats, including standalone VisualBlock.event.
A removed endpoint refuses; do not guess its replacement. Surviving endpoint
IDs and affinities stay intact. Resolve affinity-selected surviving token spans
using the same before/after semantics as the validator. Recompute quotedText
from new UTF-16 offsets. When selected content changes, increment anchorVersion
and owning entity version once; untouched ranges/entities remain identical.
Do not mutate arbitrary notes/text by recursive key names or rewrite historical
recordings/approved prompter snapshots. If cross-narration ownership would alter
another row, refuse that unsupported cross-row profile rather than violating the
row-box rule. Standalone VisualBlock wrapper version changes only if its owned
event changes; verify this convention against the current contract/validator.

Run the actual validator after the complete candidate is assembled. Refuse
invalid empty/overlapping beats, coverage or other canonical constraints before
returning any revised artifact. Do not compile against stale narration
text/version/audio; the accepted standalone validator is the correct first gate.
Emit the complete revised row text/version/text hash as the regeneration request,
explicitly invalidating its old recording. Do not output a supposedly usable new
audio dependency, subtract old-cut timing, or claim rewritten text is new VO.

Integration follow-up: the current row narration handoff intentionally rejects
all non-narration block edits, including a standalone visual entity reanchored to
the changed row. Before supporting that composed case, validate a bounded
accepted-decision handoff that permits only the actual canonical visual changes;
never loosen generation's input guard to arbitrary non-narration changes.
Original current positive fixtures keep visuals inside their narration rows.

## Test-first checks and evidence

Issue-owned tests use copies/constructed samples, actual accepted validator and
canonical serializer. Positive Alpha Bravo Charlie Delta Echo omission, multiple
interior tokens, differing ASCII separators, UTF-16 astral values before/after
the cut, enclosing anchor updated quotes/version, untouched anchors/entities,
annotations/beats/standalone event, following narration byte equality,
deterministic replay and stale input hash. Refuse duplicate/reordered/unknown/
first/last/noncontiguous IDs, excluded rows, removed endpoints for each entity
kind, sentence/other punctuation boundaries, invalid coverage and revision
integer overflow. Confirm no original mutation or stale dependency compilation.
Existing full compiler/golden tests remain byte-identical regression evidence.

Claude reviews this plan before code and the finished pure transformer before
workflow integration. Retain prompts/full reviews/results on #144. Full source
checks and exact validation counts are retained per checkpoint. If Claude hits
usage limits, save the current checkpoint and stop all #144 work until available;
never change model/session/account, use browser as a quota bypass or skip review.

## Remaining acceptance

This is automated transformation evidence, not #144 closure or a live positive.
Composed explicit decisions, verified generation/fresh IDs/materialization,
guarded WI/capture/render/link entry, three-edit integrated proof, refusal/replay
and operator runbook remain. #145 independently qualifies and executes real
standalone route/support/current-build/observer/renderer; #148 prepares inputs.
Producer auth UI/reshoot/pickups remain #153; music and human Resolve refinement
preservation remain excluded. No producer retest is requested for this building
block.
