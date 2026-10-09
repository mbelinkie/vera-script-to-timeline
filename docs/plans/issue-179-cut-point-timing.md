# Issue #179 — verified picture boundaries without complete word maps

Status: proposed for Producer review. **Design only; no runtime change.**
Owner: `gpt-6.1-sol/high`, chat `01a121d8-d419-73b0-bbb9-76aab14917cc`,
branch `codex/issue-179-cut-point-design`. Acceptance: Producer.

## 1. Scope, authority and result

Allow a v2 picture-only build or media-needs request to resolve its requested
boundaries from independently verified observations. Unrelated words need no
timing. Missing required observations still block. The narration waveform,
spoken text, block order, row duration and playback remain unchanged.

Dependency: `Blocked by #173`, confirmed Closed and Done before claim.
The accepted #173 tested source is
`96fd70f573c3eaa1fc2b342de87ee9df00c64eaa` (tree
`a199b7ee8feb370f694c23f4d7b975d7264a1f8f`). Its accepted published evidence
baseline is `d2e241316cb032cdddc4bac5d7acd953b1af8519`. This new branch alone
fast-forwarded from main `96978919616df0148d9c4b06781aeb80acfa85e4` to that
baseline. #156 authority is the accepted plan at
`e32727f0c0e65dc5a8561e0f470ed28e59bd1809`, particularly §§3.2, 4, 7 and 9;
#56 at `9e2b8817ffe97fbc9d6fcf31099aca578c5022bb` §§3–7 supplies structural
order/returns. Product-spec §§6.2, 6.11, 6.13, 8.1–8.4 and 9.1 retain honest
precision, exact anchors, source bounds and canonical manifests. The change
note below names the deliberate extension to #56's before-word-only rule.

This slice touches only this proposal and issue-owned investigation evidence
under `docs/verification/issue-179/`. No production schemas, code, generated
types, fixtures, goldens or accepted tests change. No dependency is added:
installed Vitest, schema tooling and exact rational arithmetic suffice.
Excluded: source/media preparation, paid synthesis, alignment/provider
qualification, UI/HTML, persistence, Research/private source publication,
native/Resolve operations, proof-harness versions, execution or dispatch.

## 2. Accepted-runtime reproduction

[reproduction.test.ts](../verification/issue-179/reproduction.test.ts) invokes
the unmodified accepted compiler and media-needs resolver. It derives a new
synthetic specimen from the frozen #173 root/child/return input, removes its
overlay, and records its own complete and sparse inputs. It changes no frozen
file and contains no private wording or actual media. Artificial hashes,
asset identities and observations are test attestations, not acoustic review.

Text: `alpha beta gamma`. Row audio binding: 192000 samples / 48000 Hz = 4 s.
Child begins before `beta` (1 s); return is before `gamma` (2 s). The sparse
input omits only `alpha`, which is not requested by either boundary. Every
remaining ID, UTF-16 range, exact quote, revision, text/audio/timing identity
matches the complete input and frozen row. Both pin the same synthetic timing
source; a subset is a view, not a new timing source hash.

At 24 fps, complete input gives ready picture: continuous root `[0,96)`, child
`[24,48)`, unchanged narration `[0,96)`. Sparse input gives a blocked report
with `STALE_TIMING_MAP` and `STALE_ANCHOR`, suppresses picture and preserves
only narration. Media-needs refuses with `STALE_TIMING_MAP`.
[reproduction-result.json](../verification/issue-179/reproduction-result.json)
separates these observations from **proposed**, unimplemented outcomes.

The cause is `compiler-core-v2.ts:buildTimedRows`: length and positional identity
must equal every frozen token before any token times are retained. The Python
provider adapter also insists on complete coverage. The projection uses
`timing.tokens[wordIndex]`, and its preview estimator expects full arrays.
Simply permitting holes would both weaken coverage and risk binding the wrong
word. Preserve that existing map contract; add a separate evidence capability.

## 3. Selected input and trust boundary

Add optional `CompilerDependenciesV2.narrationBoundaryEvidence`, an array of
closed, explicitly versioned `NarrationBoundaryEvidenceV1` objects. Keep
`narrationTimingMaps` required (it may be empty as today) and its complete-map
semantics unchanged. For each active narration row, require exactly one input:
a complete map **or** boundary evidence. Reject duplicates, both kinds for the
same row, inactive/unknown row inputs and conflicting bindings for one asset.
No merging, precedence or per-word fallback between inputs.

Proposed wire definitions (all fields listed are required unless optional):

| Definition | Fields and exact meaning |
| --- | --- |
| `NarrationBoundaryEvidenceV1` | `schemaVersion="narration-boundary-evidence/v1"`; `blockId`, positive `blockRevision`, `textHash`, `tokenizationVersion="script-document/v2-frozen-tokens"`, `narrationAssetId`, `audioHash`, `timingHash`, nonempty `alignmentVersion`; required existing `NarrationAudioBindingV2 audio`; `tokens[]` (possibly empty); `verification`. There is no whole-row precision or claim of complete coverage. |
| `BoundaryTokenEvidenceV1` | `tokenId`, `startOffset`, `endOffset`, exact `quotedText`; optional `onset: RationalTime`, optional `audibleEnd: RationalTime`, at least one present. No derived end, ordinal-based token mapping or implicit onset. One entry per token, in frozen token order; gaps are permitted. |
| `BoundaryVerificationV1` | `method="reviewed_audio_boundaries/v1"`, `reviewId: EntityId`, positive `reviewRevision`, `reviewerReference: NonEmptyString`, `reviewArtifactLocator: ProjectRelativePath`, `reviewArtifactHash: ContentHash`. This references an immutable authorized review receipt binding this exact envelope's identities and observations. It is not a compiler-generated assertion of verification. |

Reuse existing `EntityId`, `ContentHash` (`sha256:` prefix), reduced
`NonNegativeRationalTime`, safe-integer and project-relative path definitions.
An empty token list can support only row endpoints/media-derived boundaries
that need no speech observation; it never satisfies a word boundary.

`timingHash` remains the hash of the independently verified timing **source**
bytes pinned by `audio.timingHash`. If observations are selected from a larger
receipt, its source hash stays fixed; never hash a subset and silently replace
the cache binding. If a new manual receipt is the timing source, only the
authorized preparation/review flow can bind its new hash to the unchanged audio.
The pure compiler cannot create or bless that binding. The review artifact
contains the exact row/audio/source identities, this selected observation list,
review identity and reviewer; its byte hash is verified by the assembling flow
before the frozen input is passed to the compiler. The receipt does not include
its own hash. The compiler's dependencies hash independently covers every
serialized observation and verification reference, including subset changes.

Real callers must load and verify the source/receipt bytes and normalized audio
hash using their existing audited product flow. An arbitrary JSON label or
hash is not acoustic proof. Pure compilation checks frozen attestation
consistency, not waveform truth, just as it consumes verified media bindings.
This design qualifies no new provider and implements no review application.
Candidates, estimates, sentence timing, unknown ends or unverified manual
timestamps cannot be promoted to this evidence input. Provider full maps
continue through `narration_v2_dependency_from_asset` without any weakening.

### 3.1 Validation and currentness

Validate the entire supplied envelope, including unused observations, before
resolving operations. For valid input, absence of unrelated observations is
allowed; an invalid supplied observation is never silently discarded.

1. Validate version/closed schema, exact document/project/live-head/content
   binding, row identity/revision/text hash and tokenization version. Reuse
   frozen-token validation, including surrogate safety; never retokenize or
   quote-search. Reject stale audio/cache asset/locator/duration/channel/sample
   binding and mismatched `audio.narrationAssetId`, `audioHash`, `timingHash`.
   Assemblers must compare to the current verified asset, not just two fields
   in attacker-supplied JSON. Pure self-consistency is necessary, not sufficient.
2. Check receipt reference/hash/current review revision and source identity in
   the assembling flow; reject missing, candidate, changed or unverifiable
   receipts before invoking either public compiler seam. Pure callers freeze
   those verified references; future runtime acceptance must test this boundary.
3. Resolve each entry by token ID, then compare exact UTF-16 start/end and
   quoted text with the frozen token and source slice. Reject unknown/repeated
   IDs, duplicated entries/ranges, wrong row, reordered entries, split
   surrogate, stale quote or wrong range. Repeated words remain distinct IDs.
4. All times are reduced safe rational seconds, nonnegative; onset < exact
   sample-derived row end, 0 < audible end <= row end. If both are present,
   onset < audible end. Observed onsets strictly increase in frozen token
   order, as in the accepted compiler. A supplied end for an earlier token
   beyond a later supplied onset cannot prove a between-word gap. For this
   picture-only input, contradictory/crossing supplied supports refuse rather
   than advertise complete word visibility. Audible ends strictly increase in
   frozen order; no earlier supplied end may exceed a later supplied onset
   (equality is allowed at a shared speech edge). End-only marks impose no
   fabricated onset. Never use the next **supplied**
   token as the next frozen word across a hole.
5. Build required observations from the actual document operations. Exact
   identity-valid input with a missing required mark yields an operation-local
   `BOUNDARY_EVIDENCE_REQUIRED`, naming token, requested edge and occurrence.
   Schema/identity errors refuse or block with existing specific diagnostics;
   missing evidence is not mislabeled as stale text. No interpolation,
   default ms/token, guessed silence, guessed final-word end or duration-based
   speech mark. Whole-row picture suppression and delivery refusal stay as
   accepted; other valid rows remain diagnosable. Known narration duration
   permits a blocked diagnostic manifest, never a deliverable picture build.

Changes to audio, text, frozen tokens, revision, timing source or review revoke
the binding. Boundary/sequence changes recompute requirements and invalidate
media needs, preparation keys and prior build identity; a late result cannot
bind to another snapshot. Prior artifacts remain immutable. Existing checks
against source descriptors, original bounds, preparation and audio mapping
remain mandatory; sparse speech evidence bypasses none of them.

## 4. Operation-specific evidence

All rows require their verified audio binding for row bounds. Times are local
to that audio; row record offset is added only at quantization. Full maps can
provide the same requested observations when honest evidence is present.

| Actual operation / claim | Minimum observations beyond audio binding | Missing evidence / consequence |
| --- | --- | --- |
| Row start, row end, final root endpoint, between-block endpoint | None: start is 0; end is `durationSamples/sampleRate`; adjacent block identities/order must be current | Unknown audio duration refuses. Neither endpoint is an audible first/last-word claim. |
| Existing `spoken_word` content/cutaway start, sibling/sequential cut, `ReturnSlot.inpoint` with `affinity=before` | Onset of the named frozen token only | Block that required boundary; no preceding-word timing requirement. |
| Explicit after-word content/return cut | Audible end of the named token only, independently reviewed | Missing audible end blocks; no next-word or row-end fallback. Its onset is additionally required only if another operation requests it or an inside-word claim needs it. |
| Independent overlay / supporting point before a word | Named onset | Resolve legal picture placement/point only. |
| Independent overlay / supporting point after a word | Named evidenced audible end | A next-word-derived end remains insufficient. |
| Overlay two-of-three start/end/duration | Only its actual authored anchor marks and positive exact duration where authored; event-edge dependencies must themselves resolve | Existing exact consistency, row bounds, cycle refusal and collapsed-frame checks apply. Duration arithmetic yields an event edge, never acoustic evidence. |
| Complete logged-clip endpoint | Resolved start plus exact current original logged source bounds/rate/inpoint | Picture endpoint can resolve with speech relation `derived_or_unknown`; no new spoken-word anchor. Preserve #56's B-roll target and complete-mode restrictions. |
| Label a media cut `at_word_start` | Named observed onset equals exact media time | Otherwise unknown unless another evidenced relation applies. |
| Label a media cut `inside_word` | Onset **and** audible end of the same token bracketing time | Derived ends or only one edge cannot establish inside support. |
| Label a media cut `between_words` | Audible end of frozen token i and onset of frozen token i+1, with end <= time < next onset and end < next onset | Check adjacency in the full frozen token list, not sparse entry order. Missing intervening word means unknown. This labels a gap between verified adjacent scripted supports; it does not certify all audio is silence. |
| Final-word audible end / tail cut | Independently evidenced final-token audible end | Row duration is not evidence of last speech. Keep trailing audio unless a separate audio-edit operation is authorized. |
| Word omission, subtitle/caption timing, spoken-text coverage proof, recorded take alignment, exact “no speech lost” proof | Fuller speech/segment/take evidence demanded by that consumer's own contract | Boundary-only input is insufficient; refuse explicitly. It never proves intervening words were spoken, omitted or aligned. |

The same exact boundary resolver must serve media-needs and compilation. UI
projection may consume verified boundary observations for timing/ordinal order
by ID, but cannot turn them into a full preview word map. Keep the existing
`media_cut_estimate/v1` full-provider path and honest fallback display behavior;
neither can supply a compiler boundary. Structural word highlights remain
editorial token coverage, not a claim that every highlighted word was timed.

For the new input, relation precedence is exact onset, exact audible end,
inside a supplied support, then a verified adjacent gap, otherwise unknown.
At a coincident end/onset, onset takes precedence; retain the exact token/edge
chosen. Do not classify the leading/trailing tail as silence from row endpoints.
These new-input rules never alter accepted full-map media-relation bytes.

## 5. Authored edges, pauses and row tails

Keep every existing `WordInpointAnchor` (`affinity=before`) exactly as accepted:
it means the named word's onset. “End through beta” expressed by today's
before-gamma return includes the pause after beta. It must never be silently
rewritten to beta's audible end.

Propose an explicit `WordAudibleEndAnchor` with the same block/token/quote/
revision fields but `affinity=after`. Add `BoundaryBefore` variant
`{kind:"audible_word_end", anchor:WordAudibleEndAnchor}`. Widen
`ReturnSlot.inpoint` to `WordInpointAnchor | WordAudibleEndAnchor | null`.
Add the equivalent `PointAnchor` variant for overlay endpoints. Existing
supporting word points already permit after affinity; use their honest
audible-end resolver, including end-only observations without forcing onset.
Null return remains an unrenderable authoring state.

This deliberately extends #56's before-word-only invariant. Authoring order is
the pair `(frozen token index, edge)` with before < after. A child can begin
before beta and return after beta; they are distinct edges on the same word.
Duplicate edges remain illegal. Later boundaries must increase both editorial
order and resolved rational time, then remain positive after frame rounding.
The after edge is token index + 1 for text coverage; it does not shift words or
claim the pause is spoken. Shared boundary transactions remain atomic, return
reveals the advancing parent, and final root still reaches fixed row end.
Ending a final child after the final word can reveal its parent in the tail;
the return must precede row end. Ending a final root early still requires an
explicit following content slot; this adds no freeform range authority.

The synthetic receipt places beta onset at 1 s, beta audible end at 3/2 s,
gamma onset at 2 s, gamma audible end at 11/4 s, row end at 4 s:

| Authored request | Picture at 24 fps | Pause/tail outcome |
| --- | --- | --- |
| Child before beta; return before gamma | Child `[24,48)` | Child owns the 1.5–2 s pause; parent reveals at gamma onset. Sparse beta/gamma onsets suffice; alpha timing is irrelevant. |
| Child before beta; return after beta | Child `[24,36)` | Parent reveals at beta audible end, so parent owns the pause. Needs beta onset and beta audible end; no gamma onset unless otherwise requested. |
| Return before gamma but gamma onset absent | Block | Beta end is not a replacement; no inferred 0.5 s pause. |
| Return after beta but beta end absent | Block | Gamma onset is not a replacement, even if a provider supplies it. |
| Child before gamma; return after final gamma | Child `[48,66)` | Parent remains visible `[66,96)` through the audio tail. Requires gamma onset/end; narration stays `[0,96)`. |
| Final root with no authored successor | Root continues to frame 96 | Neither final-word end nor missing word observations truncate the row. |

Use accepted quantization: `ceil(t * rate.numerator / rate.denominator)` with
checked rational arithmetic, one shared boundary frame and explicit delta.
At 25 fps beta end is frame 38 (1.52 s), gamma onset 50, final audible end 69,
row end 100. At 24000/1001 they are 36, 48, 66 and 96; the exact times still
remain 1.5, 2, 2.75 and 4 seconds. Quantized picture may extend less than one
frame past an observed end; retain the delta, never describe it as a changed
acoustic end. Narration retains exact original sample endpoints and content.
Sparse observations cannot establish that the pause contains no other sound.

## 6. Proposed contract-change note CN-179

**Approval required separately and explicitly together with this design.**
Why: the accepted complete-map check conflates picture boundary requirements
with complete speech alignment. Explicit after-word semantics avoid silently
moving cuts across pauses. This proposal is additive to v2 readers upgraded
for this capability; it changes neither v1 nor old full-map semantics.

| Production surface to change in the successor | Exact proposal / compatibility effect |
| --- | --- |
| `contracts/compiler-dependencies-v2.schema.json` | Optional `narrationBoundaryEvidence` and the three definitions in §3; semantic XOR per active row. Existing maps/`TokenTimingV2`/audio fields retain meaning. Add optional `VisualSequenceResolutionV2.boundaryEvidenceHash` (`ContentHash`) for new-input rows and `alignmentPrecision=verified_onset` for onset-only resolution; preserve existing enum meanings. |
| `contracts/script-document-v2.schema.json` | New `WordAudibleEndAnchor`, `BoundaryBefore.audible_word_end`, return-anchor union and point-anchor variant (§5). Preserve every before-only anchor as onset; no eager migration or affinity rewriting. |
| `contracts/timeline-manifest-v2.schema.json` | Optional event provenance `boundaryEvidenceHash`; optional `BoundaryEvidenceV2.boundaryEvidenceHash`; add `kind=row_start|row_end` and `precision=verified_onset`. Use existing word_end/audible_word kinds, exact inputTime/frame/delta, related token identity. New-input outputs retain the canonical hash of the complete selected evidence envelope; `timingMapHash` remains the pinned timing source hash, not an invented complete map. Extend wordRelation with `at_word_end` for evidenced ends; do not label an end as a proved gap. |
| `contracts/build-report-v2.schema.json` | Add blocking `BOUNDARY_EVIDENCE_REQUIRED` diagnostic with existing details/recovery evidence (`refresh_timing`, `manual_review`), exact entity/JSON path and requested token/edge in message. Preserve stale identity/hash and collapsed-boundary codes. No readiness bypass. |

Hash the selected evidence envelope using existing canonical JSON hashing;
freeze it in new-input event, boundary and sequence provenance. Include the
audio/receipt identities in that envelope. Emission of these optional additions
is confined to new-input rows. Full-map documents compiled by the successor
retain the accepted canonical manifest/report bytes, not only semantic parity.
Their existing media-cut classifications, preview estimates and unavailable
recorded-provider behavior stay unchanged. New after-edge authoring is explicit
opt-in and requires its new supported contract; no old output changes implicitly.

Onset-only new-input resolution uses new precision `verified_onset`: it
establishes an exact named onset, but no audible end or gap. An independently
reviewed audible-end edge uses
`audible_word`; media gap uses `between_words`; unsupported speech relation
uses `unknown`. Precision is operation-specific, never copied across a whole
sparse row. Row start/end use `unknown` speech precision. `alignmentPrecision`
is not a declaration that recorded presenter alignment is available.
`word_end` output must carry the exact observed end/delta and named token;
existing `word_start` output keeps its exact onset. Every new-input requested
boundary, including returns and row endpoints, retains boundary evidence;
new row endpoint evidence uses `kind=row_start|row_end`, not word_end.

### 6.1 Callers, generation and exports

| Current file / public seam | Successor work required |
| --- | --- |
| `packages/contracts/src/compiler-core-v2.ts`: `compileTimelineV2`, `buildTimedRows`, `resolvePlan`, `wordRelationAt`, `supportingPointFrame`, source/conflict/duration checks | Accept exactly one row capability; validate by token ID; keep audio spine independent; collect operation-specific requirements; resolve before/after/end-only evidence honestly; share needs/compile resolver; retain output provenance and blocked accounting. |
| Same file: `MediaRequirementsInputV2`, `resolveMediaRequirementsV2` | Add optional `boundaryEvidence` alongside existing `timing` (which remains required and may be empty). Schema/preflight and cross-kind conflict rules match compile. No fabricated full maps. |
| `packages/contracts/src/authoring-v2.ts`, `authoring-v2-projection.ts` | Add optional boundary-evidence projection input; ID lookup for new input and after-edge ordering/coverage. Preserve full-map preview estimator and its fallback; never feed sparse observations to positional complete-map helpers. |
| `authoring-v2-validation.ts`, `authoring-v2-edits.ts`, `authoring-v2-placement.ts` | Validate new edge identity/order, preserve atomic edits and null-return rules; resolve new point/key and keyed end observations; explicitly reject unsupported commands rather than coerce to before. Recheck all command variants and anchor consumers. |
| `python/vera_timeline_agent/narration/compiler_dependencies_v2.py:narration_v2_dependency_from_asset` | Preserve complete provider mapping, errors and output bytes; do not repurpose it for sparse manual marks. Generated new evidence types are available to later assemblers; no new paid/provider/manual-review adapter is hidden here. |
| `packages/contracts/scripts/generate-contracts.mjs`; generated `contracts-v2.ts`; Python `compiler_dependencies_v2_schema.py`, `script_document_v2_schema.py`, `timeline_manifest_v2_schema.py`, `build_report_v2_schema.py`, `__init__.py` | Run existing generation, never hand-edit types. Export named evidence/anchor definitions through existing `@vera/contracts/v2` generation bundle (extend its definition selection if needed); keep explicit `authoring-v2`/`compiler-core-v2` seams. Check root generator's full currentness and byte-identical v1 outputs. No new package export or dependency required. |
| New-input assemblers/preparation callers (future P5/P6) | Verify receipt/source/audio bytes in authorized flows; select capability per row; pass same frozen snapshot to both seams; refuse unsupported capability. Not implemented or qualified by #179. |
| Full-map preview, captions, omissions, take alignment, v1 Studio/OTIO/proof callers | Retain their existing capabilities/requirements. Never pass boundary-only input as full-map data; no casts, synthetic completion, retiming or proof-version change. |

Pure command handoff: widen `VisualDestinationV2.boundary`, insert-sequential/
cutaway `boundary` and set-playout `nextBoundary` to the before/after union.
Add optional `VisualSequenceEditCommandV2.move_word_boundary.affinity`;
omission preserves the current owner's edge (legacy before stays before),
explicit `before|after` selects that edge. Rebuild the exact quote/version at
the chosen token without changing token IDs. Convert/flatten/delete/swap/
move/promote operations preserve edges and compare `(index,edge)`; they may
not coerce after to before. `wordIndexV2` continues returning token index;
validation/edit ordering and coverage use the separate edge offset. This
extends existing operations only; no new UI or edit command is introduced.

Old closed-schema consumers will reject new optional fields/anchor variants:
they must upgrade explicitly before use. Do not remove unknown fields or route
new evidence into v1 to make it load. Existing documents need no migration.
Previously accepted v2/v1 artifacts stay immutable, and unsupported clients
refuse new capability honestly. Currentness applies across all generated
surfaces, even if only v2 roots change. #144 caller/source pins and #145
v1/25-fps proof remain frozen; #179 is not v2/23.976 execution qualification.

### 6.2 Fixtures and focused success/refusal acceptance

No existing fixture, golden or accepted test may be rewritten. Implementation
adds its own synthetic data under `tests/data/authoring_v2/<successor>/` and
new tests; approved CN-179 authorizes only the new definitions/semantics above.
If accepted bytes must change, stop for a distinct Producer-approved note.

Required successor tests:

1. Sparse required onsets with holes before/between/after them succeed for
   picture/needs; absent unrelated timing never changes placements. End-only
   observation resolves an explicit after cut; row-end-only picture requires
   no tokens. Exact needs/compile ranges and hashes agree. Deterministic
   byte-repeat new manifest/report goldens at 24000/1001 and 25 fps.
2. Before-next-word versus audible-end pause/tail cases in §5; same-token
   before→after is legal, duplicate edges/reversed order are not. Quantization
   deltas are exact; equal/collapsed frames block, including subframe supports.
3. Omit each required onset/end separately: `BOUNDARY_EVIDENCE_REQUIRED`, no
   row picture, no row-end/other-edge fallback; needs refuses. Unknown final
   word end stays unknown; candidate/sentence/estimated evidence refuses.
4. Wrong/missing row, revision, text hash, asset/audio/timing identity, receipt
   binding/revision/hash or malformed locator; dual inputs/duplicate rows,
   stale/inactive rows and conflicting reused audio bindings refuse. Add an
   assembling-flow byte/hash/review-status self-check without provider calls.
5. Wrong/duplicate/reordered token IDs, wrong ranges/quotes, repeated words,
   punctuation/apostrophes, combining characters and surrogate pairs; no
   ordinal or normalization/quote fallback. Invalid unused supplied entries
   also refuse; missing unrelated entries remain valid.
6. Negative/unsafe/non-reduced times, zero denominators, onset at/beyond audio
   end, end beyond row, collapsed/crossed observed supports, overflow and
   invalid sample binding refuse without weakening schema gates.
7. Media relation at/onset, evidenced end, inside support, verified adjacent
   gap and nonadjacent sparse entries. Missing speech relation remains unknown
   for legal media picture cuts. No inferred silence or nonadjacent adjacency.
8. Boundary-only data cannot satisfy caption/omission/full-speech/take proof.
   Existing complete-provider, authoring, v1 compiler/validator/prompter/OTIO,
   #144 and all #173 goldens pass byte-identically. Source shortage, track/
   overlapping source-audio and unavailable recorded-mode refusals persist.
9. Run generated-currentness, lint/typecheck, both language/schema regressions
   and the full locked-toolchain `VITEST_MAX_WORKERS=1 npm run validate`.
   Retain frozen inventory/source/tool/profile hashes. No weakened gates.

This design's own checks are the accepted-runtime reproduction and exact
example arithmetic, source/reference consistency and frozen-boundary audit,
generated-currentness, focused accepted compiler/authoring/schema regressions,
and `git diff --check`. A full repository gate is required for the implementation,
not this docs-only proposal; retain #173's passing full-gate evidence without
claiming it tested the new behavior.

## 7. One bounded implementation successor and sequence

Successor: [#180 — Implement verified picture-boundary evidence and explicit
audible-end anchors](https://github.com/mbelinkie/vera-script-to-timeline/issues/180).
One pure Contracts and Compiler slice, tentative `model:sol /
effort:high`, Size M, Acceptance Automated under this Producer-accepted design
and CN-179. Canonical dependency: `Blocked by #179`. Scope is §§3–6's schemas,
generation, compiler/media-needs and authoring edge consumers plus issue-owned
tests/goldens. No real-media preparation/review app, providers, UI, migration,
native or proof changes. Real inputs remain the responsibility of existing
authorized preparation owners; synthetic attestations cannot qualify them.

Keep the successor an Inbox placeholder, with this accepted design as the
promotion prerequisite. Readiness and boundedness need steward revalidation;
do not dispatch, implement or auto-promote it here. Its full gate is a separate
runtime acceptance. No second successor is proposed by this issue.

For the Producer's “179, 148, 145, then design” sequence: **#179 is this design**.
Its implementation successor must land before consumers can use the new
runtime input. #148 private preparation and #145 proof keep separate owners
and existing execution limits; no new formal dependency or retiming is added
to either by this document. They may do independent work meanwhile. #145
remains its accepted v1/25-fps proof; it is not silently changed to v2/23.976.
Other backend tickets do not all block this design decision.

## 8. Producer review of this exact design and CN-179

The published review commit/hash manifest identifies the precise bytes. No
acoustic listening or Resolve test is requested for synthetic design evidence.

1. Open this file §§2–4 and `reproduction-result.json`. Expected: the accepted
   runtime rejects sparse input; the proposal permits missing unrelated words
   while demanding the requested edges. Confirm separate versioned evidence,
   strict receipt/currentness checks and unchanged complete-map semantics.
2. Review §5's two beta examples. Expected: before-gamma return at 2 s keeps
   the pause under the child; after-beta return at 1.5 s shows the parent
   during the pause. Confirm this explicit choice is intended, and absent
   required edges block rather than switch the choice.
3. Review final gamma at 2.75 s versus row end 4 s, §4's adjacent-word rule
   and §6. Expected: after-word picture changes do not trim narration, missing
   words never prove silence/omission/captions/take alignment, and upgraded
   consumers explicitly adopt the new after edge. Confirm CN-179's exact
   schema/caller/type/fixture/compatibility boundaries.
4. Review §7. Expected: one unstarted implementation successor before runtime
   consumption; no new #148/#145 dependency or execution-version change.
   Record on #179: `Accept issue #179 design and CN-179 at <review commit>.`
   Or: `Issue #179 review failed at step <n>: <required correction>.`

Leave #179 In review until that exact design/change-note acceptance. Approval
of design alone delivers no compiler behavior and does not close #148/#145.

## 9. Forecast

After the first substantive investigation, forecast was 45–75 minutes of
remaining active work with medium confidence. Main uncertainty was consumer
compatibility and explicit pause/end-boundary semantics. Separate evidence and
explicit after edges resolve the design proposal; Producer choice remains a
separate approval wait. Validation/publication checkpoints and actual results
are retained in `docs/verification/issue-179/verification.md`; elapsed review
waiting is not part of the active-work forecast.
