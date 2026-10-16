<!-- Completed independent reviewer output, retained verbatim. Not acceptance or Producer authorization. -->

# Issue #144 checkpoint 1 follow-up: review of the proposed corrections

The Producer's linked-case choice holds up: the tested move/trim topology can be reproduced by one link step after the build, with no change to #34. The omission gate works on W1 if it reconstructs the whole program rather than scoring per-word templates. The local WAV splice fits the existing compiler and package.

What's left is one Producer decision on the narration route, the render seam, the stale plan body, and some bounded implementation detail.

**What I read:**
- **Repository:** `7642a91`, `717e983`, `9bee62f`, `9c8973d` and #141's `probe.py`.
- **Public pages:** the #145, #146 and #148 bodies, through a fetch tool that returns summaries, not verbatim text.
- **Live #144 comments:** only the readiness comment you pasted; I did not reopen the browser.

I made no changes anywhere.

## Correction to my first review

My first review's finding 3 was wrong. #141's linked pair was not an embedded-audio clip.

- `probe.py:167-174` (`MATRIX_RECIPE`) appends `base.mov` as video only to V1 and the separate `repeated.wav` to A1, each as its own `AppendToTimeline` call.
- `probe.py:2582-2592` then calls `SetClipsLinked([V, A], True)` and reads back reciprocal `GetLinkedItems`.
- The retained move evidence confirms it: in `r1-move-success/edited/result.json`, V1 `base.mov` and A1 `repeated.wav` are linked to each other.

That is the same structure #34 produces (separate files, separate appends), plus one link call.

## 1. Topology (option 1): feasible without frozen changes, with binding rules

- **VERIFIED: video and source audio must be separate files, as in #141.**
  - The package writer refuses two sources with the same destination: "duplicate media destination" (`resolve_import_package/package.py:388-392`).
  - #34's `import_media` refuses duplicate paths (`studio_spike.py:569-590`).
  - The compiler gives them different source IDs: `visual-source:` versus `source-audio-source:` (`compiler-core.ts:705-735`).
- **VERIFIED: a proof-specific link step after `verify()` reproduces the tested structure.** That step is a `SetClipsLinked` call on the built video item and its source-audio item, and it leaves `studio_assembly.py` and `studio_spike.py` untouched.

**Bind in the sidecar (bounded implementation):**
- Exactly two items, reciprocal links, no other links.
- Identical record ranges, 100% speed.
- A journal with pre-link and post-link captures, where only link fields change.
- The baseline is the post-link capture.

**Disclose as differences from #141:**
- Track indices: VERA uses its source-audio role track, not A1.
- Durations are exact: #141 passed `end-1`, giving 199-frame clips.
- Neighbouring items differ.
- #141's linking ran through the Workflow Integration (WI) entry on 21.1.0/14.

**Required preflight:**
- **New, VERIFIED:** all source audio shares one track (`roles.sourceAudioTrackId`, `compiler-core.ts:730`), and `sortAndValidateEvents` throws on any overlap. A +25 move therefore needs ≥25 frames of clearance on the shared audio track as well as on the video layer.
- **Scope:** muted visuals have no partner to link. They stay outside the positive and must refuse.

**Rebuild and limits:**
- A rebuilt target comes out unlinked. Any later round trip must re-run and record the link step.
- This is a native mutation that belongs to #145. #144 implements it against fakes only.
- No contract change or further topology decision is needed. #145 must still prove move/trim behaviour on its chosen build.

## 2. Omission gate: sufficient for W1 only as full-program reconstruction

**The R2 numbers are measurements, not a classifier.** The "Actual rendered R2 waveform findings" section (`report.md`) reports:
- correlation ≈0.998 on retained supports and 0.081 in the removed window;
- the first 9590 samples of the partial cut still correlated;
- A2 residue present in the gap;
- a +1920-sample offset.

Calling the word "deleted" is a reading of those numbers. `program-pcm-check.py` explicitly disclaims making that call. Your qualification on this point is correct.

**VERIFIED: reconstruction test I ran offline on retained W1 data.** Inputs were the published `a1`/`a2`/`a3` sources and the actual post-render snapshot geometry (A1 [0,99)←[0,99) and [100,349)←[150,399); A2 and A3 [0,399)). I fitted one gain per route per channel:

| Measure | Value |
|---|---|
| Program RMS | 0.0897 |
| Residual RMS | 0.000218 |
| Largest 20 ms residual window | 0.0038 |
| Same, with half of Charlie's head injected at the cut | 0.222 |
| Fitted gains | embedded A1 1.000; WAV A2/A3 0.708 |
| Left vs right channel | identical |

So routes that can be attributed are explained, the ripple-shifted "delta" included, and a partial residue stands out about 58× above the clean floor. Silence is not required, as you said.

Gains depend on topology, so estimate them per route rather than assuming them.

**The gate is sufficient for the bounded W1 positive when all of these hold:**
1. **Structural:** the removed source interval fully contains the target support and touches no retained support. This is necessary but not sufficient, because structural readback is not proof of audio (accepted-149 decision 3).
2. **Binding:** a complete PCM render (`lpcm`) over the full timeline extent, bound to a snapshot fingerprint equal to the observation.
3. **Reconstruction:** every enabled occurrence is rebuilt from hash-bound local bytes, each channel separately, with a windowed residual below a floor calibrated per case.
4. **Target check:** sub-word windows of the target support show no match at any lag.

Two retained W1 cases must give fixed results:
- **Disabled A1:** a whole route is missing, which is not a phrase omission. It must refuse or go to review.
- **Picture-only:** Charlie is still present, so no deletion is proposed.

**What #148 must supply for a new real narration case** (no paid calls, no transcripts):
- Original normalized narration WAVs and timing, already existing locally and hash-bound. If they are missing, that is a readiness blocker; any service consent belongs to #145.
- Independently measured supports (start and end) for the target phrase and its neighbours. These cannot be compiler-derived ends or ASR output.
- A phrase whose surrounding silence gaps each fit a whole frame boundary plus guard bands.
- Separate source-audio files.
- Timeline at 25/1, 100% speed, and no clip or track effects, fades or automation.

**What #145 must supply:**
- The chosen build and the link step.
- A razor cut on frame boundaries inside those silence gaps, with its ripple mode recorded.
- The complete render and the gate.
- A render of the rebuilt target.

## 3. Local WAV splice: compatible with the existing seam

The compiler only checks the text hash, block revision, one word mark per token, monotonic marks, offsets equal to token offsets, and marks before the audio end (`compiler-core.ts:276-277`, word-mark branch ~495-510).

**Pins needed, all bounded implementation:**
- **Frame-aligned cuts only:**
  - At 25/1, a frame is 1920 samples, exactly 40 ms, so the integer `timeMs` marks shift exactly.
  - Refuse fractional source frames or non-100% speed.
- **No renormalization:**
  - The normalized narration is PCM-24 mono at 48 kHz (`normalize.py:293-305`). Splice those bytes as they are.
  - Refuse a join point whose amplitude is above the silence threshold.
- **Separate splice provenance:**
  - `NarrationAudioAsset` is typed `temp_synthetic` and carries provider fields (`models.py:121-151`), so it doesn't fit a splice.
  - Emit a schema-valid `NarrationDependency` directly, with a deterministic `assetId`, a new `alignmentVersion` (for example `splice-derived/v1`), and a sidecar provenance record.
- **Sentence marks:** a fixed rule. Drop them, or remap them to the first retained token. Never point a mark into removed audio.
- **Text rule:** extend it with these refusals:
  - non-whitespace between the deleted span and its neighbours;
  - the first or last token of a block;
  - any anchor, host-span, annotation or beat endpoint inside the span;
  - deletion at the start of a sentence (capitalization would not be rewritten).

  Ranges that contain the span keep their endpoints and get a recomputed `quotedText`.

**Producer decision:** #145 requires a narration-route selection. Ask the Producer to approve "a splice of the hash-bound original narration" as the revised-narration route, and the deletion rule as wording policy.

## 4. Build seam: workable without an RPC layer; three gaps

The split works: pinned host Python 3.12 for the compiler, package and jobs, plus the accepted external-scripting Studio adapter, plus a stdlib-only file-staged WI observer. Three gaps remain.

1. **The plan body is stale (VERIFIED at `9bee62f`).**
   - The seam table still says "Local CLI / injected WI entry" (line 54).
   - The omission text still reads "consume retained W1 … on WI Studio21.1.1.10" (lines 74-75).
   - A header saying the disposition "governs" is not enough. Rewrite the plan body before coding.
2. **The render step has no seam.**
   - #34 has no render code, and #35's `rendering_mp4` stage has no adapter.
   - #141 saw queued settings differ from what was requested (1920×1080 and MarkOut 2449, against a request of 640×360 and 200).
   - Specify the render entry and read back job settings before `StartRendering`.
3. **Entry points and the build are unspecified.**
   - Name the entry used for the link step, and use one entry for both captures.
   - Disclose that External Scripting Local differs from the evidence lanes, which ran with it set to None.
   - `_still_end_frame_compensation` is 0 only on 21.1.0/14 (`studio_spike.py:695-707`). Placeholder and presenter events compile to stills, so this applies to nearly any real segment. #34's `verify()` will catch a mismatch rather than let it pass, but #145's build choice must account for it.

## 5. Remaining items: implementation detail versus Producer decisions

**Bounded implementation; can proceed now:**
- **Anchor preflight:**
  - Canonical affinity encoding.
  - Uniqueness at the resolved token index, refusing tokens that round to the same frame.
  - A rule for whether the block end counts as a boundary.
  - Clearance on the video layer and on the shared source-audio track.
  - Coverage checked by the validator.
- **Deletion and revision data:** the deletion rule and offsets, `liveContentHash` and `liveHeadSequence` derivation, version bumps, and the splice producer.
- **Recovery:**
  - A lost response or name collision leaves the job waiting, and only a read-only check of the existing project can resolve it.
  - That check maps sources by file path under the package root plus a hash recheck. It does not use the creation-time maps.
  - A partial target needs a new build ID and a new job; nothing is deleted.
  - UID ambiguity is referred to the operator.
- **Composition:** a ripple counts as a uniform shift only when every item past the cut moves by exactly the removed length. Any item spanning the cut refuses, and the sync-lock state is recorded.
- **Replay and promotion:**
  - The receipt key is the decision bytes plus the bound hashes.
  - The job idempotency key is the revision hash.
  - Promotion uses a lock, a check of the prior hash, an atomic replace and a directory fsync.

**Can proceed regardless of open decisions:** the refusal paths, immutability tests, the compiler-entry wrapper, the pinned package timestamp, the reconstruction gate tested against retained W1 and R2 data, and the job state machine against fakes.

**Must wait:**
- Positive move/trim assertions: until the link-step sidecar exists. They stay labeled as injected or retained evidence until #145 proves them natively.
- Any omission rebuild positive: until the Producer approves the narration route and #148 confirms the original assets exist locally.

**Producer or readiness decisions:**
1. Revised-narration route: the splice versus authorized synthesis in #145.
2. Who supplies the original narration assets, given #148 excludes any paid or cloud service call.
3. The #145 build and the External Scripting Local setting.
4. If the segment has no exact ±25-frame candidate: a new natively proven delta, or a contract change for timing overrides.
5. Acceptance of the wording rule.
