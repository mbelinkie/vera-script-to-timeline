# Issue 53 — provider-independent row take prototype

Status: implementation; Producer acceptance required. Baseline `333a064`.
Task `01a06803-59f3-7db3-9cfc-ce016e5fa575`, branch
`codex/issue-53-provider-neutral-takes`, exact Sol/high claim verified.

## Producer review revision — 2026-09-04

Continue this same claim for requested refinements. Preserve the prior report.
The new accurate, highlighted transcript is authorized private evaluation data:
blue means preferred primary, green means usable alternate, only highlighted
words count, and document instructions are not executed. Derive a separate
accurate-input experiment from the entire transcript with **all colors, take
labels, and clock lines removed**. Discovery cannot consume the highlight mask.
This is an in-sample logic diagnostic, not held-out validation or #51 selection.

Scope: robust approximate row edges; script-sentence pickups/restarts within a
row; exact word-span evaluation; retain useful partial alternates even where a
complete read exists (explicit Producer clarification); and spoken earlier-take
references as review-only editorial signals. Preserve the normal last-complete
suggestion and prior decisions; never execute transcript instructions or select
a keeper. Unknown speech times/handles remain unknown. No shared contracts,
accepted fixtures, old accepted tests, dependencies, or source media change.

Add fictional regression tests before these changes, then compare the previous
and revised algorithms to exact blue/green token spans privately. Test quoted/
scripted take language, ambiguous antecedents, negation, and read-only Producer
decision handling. Review the exact unresolved differences with the Producer.

Further Producer direction: expose useful partial alternates as a configurable
setting, treat supplied clocks as approximately one-second navigation hints,
and use retained word timing for proposed boundaries. The Producer explicitly
requested an FFmpeg half-resolution edit of the **blue reference selections**
for verification. This newly authorized private derivative is a reference
preview only, not #45 production conform or an algorithm-approved keeper edit.
Use immutable original source/audio, no treatment, no cloud, and exclusive new
outputs. Reference labels may choose this requested verification render, but
remain unavailable to candidate discovery. Do not silently add unsafe handles.

Producer playback rejected the tight reference edit: beginning/end words were
clipped at most cuts. Retain that failure, add about ten source frames per side,
and use original-audio waveform evidence to place cuts in nearby quiet intervals.
Transcript edges are search anchors, not final cuts. Add a slice-local tested
quiet-window/cut planner and retain per-edge measurements/reasons privately.
Preserve the first render and source; create another half-resolution reference
preview. A low-energy interval is evidence for review, not proof of absent
speech. Source limits/adjacent words/no quiet gap remain explicit exceptions.

## Scope and authority

Implement only #53 and the Producer's subsequent row guidance: use the seven
privately supplied script rows as recording units, search the completed
transcript backward, suggest the last complete usable row read, preserve
earlier complete reads, and propose partial assemblies only for review when
no complete read exists. An assembly is a list of suggested source ranges,
never a rendered splice, keeper approval, or conform. Sentence-level frozen
#37 beats remain unchanged; row-to-beat grouping is experimental metadata.

Read authority: product specification §6.14 / Slice 6.5, accepted #42 synthetic
feasibility evidence and revised acceptance split, accepted #37 export plan,
and historical IMPLEMENTATION_PROGRESS.md. Current issue and Producer row/
ten-frame guidance supersede older tentative granularity/handle defaults.

## Boundaries

New standalone experimental Python code, slice-owned fictional tests, and this
algorithm/handoff documentation only. No shared contract, generated type,
accepted fixture/test, golden, compiler, package dependency, or lockfile change.
No #45 production integration, #51 model choice, #52 treatment, registration,
proxy service, browser UI, keeper approval, conform, or source edits.

Reuse Run A's complete authorized recording and immutable retained transcripts
locally; no transcription, alignment-model invocation, download, metered cost,
or transmission. Private script rows, outputs, source locators/hashes, labels,
audio measurements, and detailed reports stay in Run A. Candidate discovery
receives only normalized recognized words/timing, source metadata, script rows,
and audio boundary evidence. Reference labels/times enter only a separate
post-discovery evaluator, after candidate results are frozen.

## Dependencies

- Blocked by #42 (closed / Done): accepted synthetic conditions and limitations.
- Blocked by #37 (closed / Done): frozen script/beat semantics.

No new library dependency: Python standard library plus installed FFmpeg for
read-only audio measurements/playback suffice. No dependency on #51 selection.

The Producer clarified that #53 judges parsing logic assuming the transcript
is accurate. Recognition/model adequacy stays with unresolved #51. Accurate
fictional and accepted synthetic cases establish logic behavior; retained noisy
variants diagnose robustness and boundary uncertainty without choosing a model.
The decision-complete algorithm and proposed future contract changes are in
`docs/issue-53-take-proposal.md`.

## Test-first verification

Freeze new fictional cases before implementation: complete repeats, row with
multiple sentences, restart, pickup, flub/ad-lib, uncovered/ambiguous rows,
missing/reversed/coarse timing, all-word accounting, reference independence,
last-complete selection, assembly-review fallback, immutable input, and source
limits/adjacent speech/short gaps with rational ten-frame handles. Consume at
least two normalized retained variants through the same algorithm. Keep ideal
synthetic failures separate from real recognition/timing and listening evidence.
Run focused tests, static checks, full repository validation, and frozen-boundary
audit. Compiler is untouched, so no new compiler golden is needed.

## Producer review

Open Run A / Issue 53's ordered report and playback list. Compare all discovered
groups and unresolved ranges to the independent reference; play every default
and earlier alternative; inspect proposed partial assemblies; listen at both
edges of every proposed ten-frame range and every exception. Expected: rows
remain whole where possible, last complete reads are suggested, incomplete
coverage and uncertain cuts stay visible. Reply
`Accepted provider-independent presenter take logic.` or identify the first
failed row/group/default/boundary/assembly. Leave #53 In review until accepted;
an inadequate result does not clear #45's design gate.
