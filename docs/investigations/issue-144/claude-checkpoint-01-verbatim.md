<!-- Independent reviewer output, retained verbatim. Findings are not acceptance or Producer authorization. -->

I'll attach the repo read-only, pull the pinned plan, review packet and evidence, then check them against the actual source before writing findings.

# Issue #144 checkpoint 1: adversarial plan review

I worked from the plan at `d055f90`, the packet at `b0f4e91`, baseline `9c8973d`, #131 at `817d0e5`/`ac0f5d9`, PR150 at `e020bd1`, and the published #141 and #149 evidence. I made no repo, issue or Resolve changes.

The plan should not start the omission slice or the native-build seam yet. Move/trim mapping and refusal logic can begin, but no positive move/trim fixture should be asserted until the topology question in finding 3 has an answer. Six blockers follow, then three medium and one low.

## Blocking findings

**1. The retained W1 detector cannot see partial-word residue. Blocks the omission gate.**
- **VERIFIED: how the detector works.** `analyze_audio.py`, present only at `e020bd1` and absent from baseline, mixes the program down to mono. For each of the 16 fixture words it takes the best normalized cross-correlation of the whole word template and calls the word present only if that score exceeds 0.8.
- **VERIFIED: the positive was easy.** In the word manifest (`media/manifest.json`), Charlie occupies frames [112.5, 122.36). The cut removed [100, 150), leaving 12.5 frames of margin before and 27.6 after, with about 1.5 s of silence on each side. It never came near a word edge.
- **VERIFIED: offline probe of that rule.** I applied the same rule to the published `a1_alpha.wav` with synthetic partial cuts. Keeping the first half of Charlie (about 200 ms, clearly audible) scored 0.775, so it counts as "absent". Keeping 60% of the tail scored 0.746, also "absent".
- **Failure:** a cut that leaves "Char-" audible is classified as a deletion, and the canonical text loses the word.
- **Correction:** build the gate on position-aware known-waveform alignment, as in #141 R2.
  - That evidence (report.md, "Actual rendered R2 waveform findings") caught the partial cut: its first 9590 samples remained correlated.
  - `docs/investigations/issue-141/program-pcm-check.py` is stdlib-only and observation-bound.
  - Treat any correlated or energetic segment inside the deleted phrase's support, plus a guard band, as a refusal. Require every retained word at its predicted lag.
  - Label W1 strictly as "whole-word, silence-margin, linked-AV fixture".

**2. The W1 positive uses a different topology and route proof from VERA narration. Blocks any "verified support" claim for narration; record it in the #148/#145 handoff.**
- **VERIFIED: W1's cut topology.** It cut a linked V1/A1 item whose audio is embedded in `base.mov`, in ripple style (source 150 placed at record 100).
- **VERIFIED: VERA's narration topology.** Narration is a separate audio-only item: `compileNarration` puts it on the narration track, and #34's `place_events` appends it with `mediaType: 2`. Nothing in `studio_spike.py` or `studio_assembly.py` calls `LinkClips`.
- **VERIFIED: the closest matching evidence is weaker.** An unlinked audio-only cut exists only in #141 R2 on 21.1.0/14. The report says geometry is supported but "program word omission/routing remains unproved". `final-findings.md` rates speech omission as "Ambiguous".
- **VERIFIED: the routes are fixture artifacts.** A1, A2 and A3 are identified by distinct vocabularies plus 1000/1500/2000 Hz pilot tones measured over the whole downmix. Real narration has neither.
- **Correction:** state the topology gap in the plan. Make route accounting a gate: every enabled audio item in the capture gets known-source attribution, and any unattributed audible energy in the deleted window refuses.

**3. The move/trim evidence does not match any topology #34 produces. A Producer decision is needed before positive mapping tests.**
- **VERIFIED: the evidence was a linked pair.** The moved item in `evidence/r1-move-success/edited/result.json` has `GetLinkedItems` and embedded audio. The #141 report says the move is "not proof of arbitrary independent visual movement".
- **VERIFIED: #34 never links.** It appends video and source audio as separate infos (`mediaType: 1` and `2`), with no `LinkClips`.
- **Failure, mute visual:** the edit is an independent single-item move, which the evidence explicitly does not cover.
- **Failure, `use_source` visual:** if the operator moves only the video, v1 cannot represent it, because the compiler gives video and source audio the same resolved range. If both are moved, that is still not the tested linked topology.
- **INFERENCE, needs a pristine capture:** whether Resolve auto-links separate `AppendToTimeline` entries. Check `GetLinkedItems` on a pristine #34 target.
- **Correction:**
  - Implement refusal when the video and audio deltas differ.
  - Ask the Producer to choose one: accept single-item (mute video) move/trim as in scope, with native proof in #145; or approve a linking change to the accepted #34 code.

**4. v1 constraints make the ±25-frame positives conditional or invalid. Blocks fixture definition and the #148 handoff.**
- **VERIFIED: boundaries are word starts only.** With `word_start_with_derived_end`, a token's end is the next word's start, rounded up to a frame, or the block end. With sentence precision, only sentence starts are available. A range must stay within one `blockId`.
- **VERIFIED: a move needs two exact boundaries.** Video `sourceRange` takes its start from the dependency's `sourceStartFrame` and its duration from the record duration. A +25 move with an unchanged source range therefore needs both the start and end boundaries to have exact +25-frame counterparts.
- **VERIFIED: vacated tokens break validation.** Every voiceover token must stay covered by a ready full-frame visual or an on-camera span, otherwise the validator raises `VOICEOVER_VISUAL_GAP`. The validator only passes with zero diagnostics.
- **VERIFIED: overlaps throw.** `sortAndValidateEvents` rejects same-track overlap. If a Resolve move overwrites the head of the next clip, v1 cannot represent it, because source start is fixed by the dependency.
- **VERIFIED: version bumps can break narration.** `compiler-core.ts:276` requires the dependency's `blockRevision` to equal the block's `version`. If "bump affected versions" means `NarrationBlock.version`, a move or trim forces new narration.
- **INFERENCE:** in natural speech, exact +25-frame pairs on both boundaries are rare.
- **Correction:**
  - Bump only `VisualEvent.version` and `anchorVersion`.
  - Make a #148 preflight a hard readiness gate, run with the actual compiler: ready full-frame video, word precision, 25/1, exact boundary counterparts in the same block, at least 25 frames of clearance to the next item, vacated tokens still covered, and enough block-end margin.
  - If nothing qualifies, stop for a Producer decision: a new natively proven delta, or a contract change to allow timing overrides (Phase 5). Do not substitute a refusal.

**5. The omission rebuild has no deterministic seam yet. Blocks #148/#145 executability.**
- **VERIFIED: compiler binding.** The dependency's text hash must equal `sha256(block.text)` (`compiler-core.ts:277`).
- **VERIFIED: synthesis.** Polly is the only provider. `NarrationService` synthesizes on any cache miss, which would be paid. The synthesis key (`models.py identity()`) excludes revision, so a cache-only path is possible: inject a provider with the same `prepare_input` and `adapter_version` whose `synthesize` raises.
- **VERIFIED: text surgery is undefined.** No rule says which whitespace and punctuation go with a deleted phrase (for example, "Bravo, Charlie, Delta"). Without one, the revised text hash will not match what #148 pre-synthesized.
- **VERIFIED: `liveContentHash` is unbound.** The compiler copies it into the manifest and report (`compiler-core.ts:445`), but nothing in the repo computes or validates it.
- **VERIFIED: no compiler CLI.** Only validator and prompter CLIs exist, so a compile CLI wrapper is needed.
- **VERIFIED: package bytes are not deterministic.** The package writer's `verifiedAt` defaults to now (`package.py:1196`). Under #35's `publish_immutable_output`, a re-executed stage raises "immutable stage receipt has different bytes".
- **VERIFIED: no true word ends.** Dependencies carry only derived ends, and #131 forbids relabeling them as deletion evidence.
- **Correction:**
  - Specify the deterministic deletion rule and share it with #148.
  - Run synthesis cache-only and refuse on a miss.
  - Define the `liveContentHash` derivation.
  - Pin `verifiedAt` from inputs, or reconcile before executing.
  - Make #148 supply independently verified word intervals and pre-synthesize the exact revised text, with the omission target declared in advance.

**6. A Workflow Integration (WI) entry cannot load the accepted #34/#35 code. Blocks the native-seam design.**
- **VERIFIED: WI is a narrow entry.** It is operator-launched, runs one staged action per launch, and loads a stdlib-only probe under CPython 3.14.7.
- **VERIFIED: the accepted code needs locked dependencies.** `studio_assembly` → `resolve_import_package` imports opentimelineio, and `studio_spike` imports `otio_package` (opentimelineio, referencing). The project requires Python ≥3.12,<3.13 and numpy is not locked.
- **VERIFIED: #34 assumes external scripting.** `_connected_studio_stop` requires it. The acceptance record (`studio-assembly-20260922-final.json`) shows 21.1.0/14, scripting enabled, 24 fps, 2 events, and the Free comparison skipped.
- **VERIFIED: entry path changes behavior.** #149 W3 showed the same setter behaving differently via WI and via Console.
- **Correction:** state the process split explicitly. Run verification and compile in the pinned 3.12 harness. Inject native calls through `run_studio_assembly(adapter_factory=…)` using either:
  - the accepted external-scripting adapter, which requires External Scripting Local; or
  - a new WI RPC adapter implementing the `StudioAssemblyAdapter` protocol, labeled unaccepted and journaled per call, with native acceptance deferred to #145.

  The orchestration is reusable; `PublicResolveAdapter` is not reusable under WI.

## Medium findings

**7. Recovery after a lost response has no authoritative check. Blocks the durable stage adapters.**
- **VERIFIED: `verify()` cannot check an existing project.** It depends on state set during creation (`expected_project_name`, `media_id_by_source`, `_track_id_map`).
- **VERIFIED: identity is by name only.** Projects are checked by name, in the current folder only, with no UID binding.
- **VERIFIED: #35 assumes certainty.** Its `reconcile` contract requires an authoritative absence check. `BuildRequest.snapshot_id` binds no input bytes, and job IDs are random.
- **Correction:**
  - Add a read-only "verify existing project" path and capture project and timeline UIDs.
  - Map the `StudioAssemblyResult` statuses to #35 outcomes. A name collision after a lost response means "uncertain", not "failed".
  - Derive build, manifest and report IDs from the revision and dependency hashes, so retries converge on the one project name, which is the only native idempotency guard.
  - Recheck input hashes at every stage.

**8. Ripple consequences and multi-edit composition are undefined.**
- **VERIFIED: the W1 cut was a ripple.**
- **INFERENCE: Resolve ripple-on-other-tracks behavior depends on sync locks.**
- **Failure:** a narration ripple shifts every downstream visual by −N frames. Each shifted visual is then refused as an unsupported move, or the target move is read as +25−N.
- **Correction:**
  - Attribute an exact uniform shift to the omission.
  - Evaluate move/trim in ripple-corrected coordinates, against baseline dependencies.
  - Forbid anchors that touch deleted tokens.
  - Define the composition order across accepted proposals.
  - Verify the rebuild against the new compile, not against observed frames.

**9. Freshness, promotion and evidence binding have gaps.**
- **Promotion:** the baseline pointer needs a lock plus compare-and-swap on the prior baseline hash (#131 migration step 5).
- **Proposal binding:** bind the compiler, package and harness code hashes plus the build lane.
- **Replay:** replaying a decision after promotion should return its recorded receipt rather than a stale-decision error.
- **Render binding:** the render's pre-snapshot fingerprint must equal the observation fingerprint, and the render must cover the full timeline extent. W1 passes this (timeline End 399, MarkOut 398, so 399 frames), but it has to be checked, not assumed.
- **VERIFIED: some hashes are attested only.** The W1 check record was sanitized at publication: original `79b53…`, published `57d1de…`. Bind the published hash and treat the original as attested.
- **VERIFIED: W1 cannot be re-measured from baseline.** Baseline `workflow-reruns/analyze.py` references the missing `../evidence/scripts`.

## Low finding (handoff)

**10. Build lanes need to be pinned for #145.**
- **VERIFIED:** #34's still-image end compensation is 0 only on 21.1.0/14 and 1 everywhere else, which is unverified on 21.1.1.10.
- **VERIFIED:** the W runs used External Scripting None.
- **VERIFIED:** the W harness passed `endFrame = end − 1` (`harness.py:1088`) and got 99-frame clips. The W1 configured ranges are therefore off by one, so use snapshots, never configured ranges.
- **Correction:** #145 should choose one build and re-prove #34 assembly, move, trim and the omission gate on it, at 25/1.
- Cite the Oct 3 report envelope as governing over the older `final-findings.md` line "Narrow #144/#145 automation to the named synthetic move/trim only".

## Independently verified

- `studio_assembly.py` matches the plan's SHA256 and source commit `2586dde`.
- `build_jobs.py` matches the plan's SHA256.
- The publication verifier passed: 5,670 records, 5,530 sanitized, 0 native actions.
- The three W1 MOV hashes match, and each probes to 399 frames, 25 fps, 766,080 stereo samples at 48 kHz.

## Not inspected

- The #144 comments and plan comment: GitHub API access isn't attached and the page fetch returned only the body. I reviewed the plan at `d055f90` instead.
- #35 source commit `4354c63`: a short SHA can't be fetched.
- The #145, #146 and #148 issue texts.

The 6–12 hour forecast looks low given findings 1, 4, 5 and 6.
