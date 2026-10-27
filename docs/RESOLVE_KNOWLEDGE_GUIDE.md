# Resolve knowledge guide

Reconciled 2026-10-27 for [#338](https://github.com/mbelinkie/vera-script-to-timeline/issues/338).
Source baseline: `068bee17402c90e4678351b2a390be6c9d4c7b47`.
This is a collection of bounded findings, not a new runtime certification.
The [source ledger](RESOLVE_KNOWLEDGE_SOURCES.md) records collection coverage.
Collection read tracked reports, implementation/tests and linked issue/PR
records; it reran no native experiment. Private raw evidence was not inspected.

## How to use and maintain this guide

AGENTS.md's backend knowledge-reuse rule is authoritative. Read only the
relevant topics at issue start; finding IDs support targeted retrieval with
search. Keep IDs stable, preserve historical conditions and link the original
evidence. A short result is enough. For example:

- **Reuse:** a new package-integrity fix can cite RK-01's established OTIO route
  and test changed-byte refusal locally; it needs no repeat format experiment.
- **Justified delta:** changing image focus conversion cites RK-43, names the
  unproved source-to-output geometry and checks a bounded grid output case.
- **Update:** RK-19 preserves #250's ordinary-package refusal and qualification
  admission, linking #145's later bounded admission instead of deleting the negative history. A new result
  adds its conditions/evidence there in the same PR. Ordinary backend work that
  changes no finding adds no entry. An uncovered question can be stated in the
  issue/PR until evidence answers it.

Each entry combines **conclusion/status**, **evidence and envelope**, and
**reuse/delta**. Evidence classes are **API** (declaration), **synthetic**
(unit/mock/replay), **native** (actual installed-app output), and **product**
(actual normal VERA path). These classes are not interchangeable. Unknown
metadata stays unknown. Unless an entry says otherwise, its reconciliation
date is the guide date; native claims apply only to the stated edition/build,
route and fixture. A historical successful run does not authorize a current
target or waive byte-integrity, identity, freshness or one-use checks.
Unlisted build, tool/profile or tested-code metadata is **unreported**, rather
than implicitly inherited from a neighboring entry or today's installation.

## Find an answer

| Question | Read first |
| --- | --- |
| Which Free import or Studio scripting route is established? | [Import/routes](#import-scripting-routes-and-graphics), RK-01–RK-03 |
| What do compiler/media tests establish before Resolve? | [Clocks/preparation](#source-clocks-and-precision), RK-06–RK-08 |
| What source/sample/word precision can be reused? | [Clocks/precision](#source-clocks-and-precision), RK-09–RK-15 |
| Which observed edits can become accepted revisions? | [Reverse limits](#rk-16--accepted-reverse-edits-produce-new-revisions-and-fresh-whole-row-builds), RK-16–RK-19 |
| Can I wait, retry, trust Complete or reuse verification work? | [Operations](#waiting-recovery-and-current-operations), RK-20–RK-24 |
| What performance was actually measured? What should #313 consume? | [Handoff](#current-312--313-handoff), RK-30; RK-23/RK-31 for earlier measurements |
| Do transitions, motion, spanning music or Fusion targets ship? | [Effects/integration](#effects-motion-and-editorial-integration-limits), RK-40–RK-45 and RK-04 |
| Does a design promise have a proof or an open gap? | [#318 crosswalk](#318-action-crosswalk) |
| Is an apparent repeated test needed? | [Reuse audit](#reuse-audit-apparent-repeats-and-the-actual-delta) |

## Import, scripting routes and graphics

### RK-01 — OTIO is the maintained Free interchange route

**Proved bounded / native manual import and later product-package acceptance.**
[Slice 0.3 worksheet](slice-0.3-resolve-free-trial.md) and
[capability matrix](../CAPABILITIES.md): Producer-reported **Resolve Free 21**,
72 frames at **24000/1001**, four 18-frame pictures, one narration item, one
marker and three hard cuts. OTIO linked all five items with no reported timing,
track, marker or cut discrepancy. FCPXML needed manual media redirection and lost
the marker; [D-P005](../DECISIONS.md) parks it as contingency code. The separately
detected 21.0.4 bundle is not the observed in-app Free patch/build, which is unknown.

The later [#15 real-media package import](https://github.com/mbelinkie/vera-script-to-timeline/issues/15#issuecomment-5465924777)
and [#2 acceptance](https://github.com/mbelinkie/vera-script-to-timeline/issues/2#issuecomment-5466013578)
add audible narration, visible slate and marker for a two-event/two-media package;
that Free version/build is unreported. [PR #246](https://github.com/mbelinkie/vera-script-to-timeline/pull/246)
delivers #2; package tests establish `ready_to_import`, not native fidelity.

**Reuse/delta:** carry forward this OTIO/layout knowledge. A new event type,
rate/media topology or edition/build needs its affected import/readback delta;
do not rediscover formats merely because an issue starts. These trials do not
prove effect transitions, arbitrary Fusion, Free scripting or #34 Free parity.
Free remains manual import/user-confirmed final placement; #10's baked graphics
fallback is open, and a placeholder is not a baked graphic.

### RK-02 — External API, injected integration and parent worker are separate routes

**Proved bounded / native and product.** [Slice 0.4](../CAPABILITIES.md) used
the public `DaVinciResolveScript.scriptapp` external bridge on Studio **21.0.4
API build 5**, macOS Intel: creation, population, save/close/reopen and observable
spike checks passed. [#34 report](verification/issue-34/studio-assembly-20260922-final.json)
then verified Studio **21.1.0 build 14**, **24 fps**, 72 frames, 1920×1080,
two events/media and one marker with zero discrepancies. Its
[Free comparison was explicitly skipped](verification/issue-34/producer-checklist.md).
The External Scripting preference value is unreported for those older external
runs; no lower supported-version floor follows.

[#6](https://github.com/mbelinkie/vera-script-to-timeline/issues/6#issuecomment-5628288680)
proved injection under External Scripting None but initially failed full startup
across Python 3.14/3.12 dependencies. [#107](https://github.com/mbelinkie/vera-script-to-timeline/issues/107#issuecomment-5608749819)
proved injected startup/attestation recheck only. [#109 / PR #194](https://github.com/mbelinkie/vera-script-to-timeline/pull/194)
then assembled/saved/reopened the bounded two-source/two-event/one-marker package
on Studio **21.1.1 build 10**, injected Python **3.14.7**, External Scripting
**None** confirmed by the operator. Its installed v1 script uses injected
`resolve`, never `scriptapp`. Python import success alone is not assembly proof.
v2 has both an installed injected/**None** lane (RK-08/RK-16/RK-24)
and a parent worker with an explicit **Local** connection (RK-20/RK-31).
Results do not transfer between them without assessing the route delta.
Product-spec external-API wording does not erase that distinction.

**Reuse/delta:** select the matching route and pinned installed source, then
follow the [v1 integration runbook](resolve-workflow-integration-v1.md) or
[v2 parent runbook](resolve-parent-delivery-v2.md). Recheck package inventory,
release bytes, current target, request and result for each build. Another
version/route/new event needs only its affected native delta. None is operator
evidence, not an API-readable preference or a Free automation guarantee.

### RK-03 — Text+ stock insertion and pinned-template append have different limits

**Unsupported stock selector; proved template workaround / native.**
The [destination-track report](resolve-text-plus-destination-track-limitation.md)
records Studio **21.0.4 build 5**, external API: stock insertion requested
Text+ at zero and obtained V1/120 frames. The documented call has no destination
track/duration argument or stock-title enumerator. Importing the pinned `.drb`
and appending its generator instead placed V4 at zero for exact 24/72-frame
tests, including save/close/reopen. The observed generator rule there was
`endFrame = requested duration + 1`; this is context-specific arithmetic.
Later full-build 21.1.0/14 duration mismatches are recorded in the
[#6 acceptance history](https://github.com/mbelinkie/vera-script-to-timeline/issues/6#issuecomment-5628288680),
not evidence for applying that rule universally.

**Reuse/delta:** use the shipped hash-pinned Text+ asset and manifest-selected
track, retaining provenance. For changed rate/build/generator/full-build context,
check exact occurrence extent and reopen; do not silently switch to stock
insertion or infer an arbitrary-title catalog. Existing stock-insertion limits
and the accepted template route coexist; one does not contradict the other.

### RK-04 — Pinned EV24 semantics and authored motion survive the qualified route

**Proved subset / native, Producer review and supplied output analysis.**
[#3 accepted native report](verification/issue-3/ev24-capability-20260922-030002.json)
on Studio **21.1.0 build 14**, external `scriptapp`, proves four pinned EV24
semantic cases on V4/zero at 64/120 frames with readback/save/reopen. The
[first graph-discovery failure](verification/issue-3/ev24-capability-20260922-030001.json)
is retained; it does not establish Fusion impossibility. #7's schema/compiler
goldens represent semantics but supply no native output evidence.

[#8 acceptance](verification/issue-8/ACCEPTANCE.md), tested product bytes
`75325e01015ff5b5285acbc980bf78e16a49ae1a`, then proves standard64,
overrides64, Otis64 and revised120 on Studio **21.1.1 build 10**, injected
Python **3.14.7**, operator-confirmed **None**. Native graph/use identity,
semantics, V4/extent and reopen passed; Producer accepted visuals. Supplied
1920×1080/**24 fps** H.264 exports preserve 48-frame entrance, 16-frame exit
and 56 added hold frames. Lossy output is near-equal, not pixel-identical;
uniform time-stretch is a failed negative control.

Initial 21.1.1 graph equality failed after reopen. The
[scoped persistence correction](verification/issue-8/graph-persistence-change-note.md)
normalizes four exact serialization shapes of this pinned graph; an intermediate
integer badge exception failed, and accepted float `0.0` is deliberately narrow.
This is a superseded detector interpretation, not permission to ignore graph drift.

**Reuse/delta:** carry forward only those cases and exact template/atlas/control
bindings. Changed graph/version/route needs affected identity/reopen/output checks.
Unused matrix variants are unused, not passed. Custom badges, arbitrary templates
and Free graphics remain unsupported/unproved. #11's After Effects reference
inspection had no authoritative source FPS; it is not Resolve motion evidence.
#12's pinned EV24 timing is specific to this authored template, not a general
animation rule. Semantic highlights use the separate RK-45 proof.

### RK-05 — Fairlight state readback is weaker than audible/rendered attachment

**Historical native subset; delivered integration unproved.**
[#110 report at `22d86fa783c141b59f8631ba3020338c3368aa3e`](https://github.com/mbelinkie/vera-script-to-timeline/blob/22d86fa783c141b59f8631ba3020338c3368aa3e/docs/verification/issue-110/capability-report.json)
is publicly reachable but absent from main and has no linked delivery PR.
Studio **21.1.0 build 14**, injected Python **3.14.7**, **None**, Edit page,
one-second stereo 48 kHz synthetic 440/880 Hz source: channel-1 mono mapping
read back; Voice Isolation and Dialogue Leveler setters read back/restored.
This is state evidence, not rendered exclusion of channel 2. Normalization and
48 kHz LPCM WAV render selection refused. No verified replacement WAV existed;
attachment was not proved. EQ/dynamics preset state remained operator-only.

[#108 comments](https://github.com/mbelinkie/vera-script-to-timeline/issues/108)
report later attachment/restoration, but its abbreviated `3989286` source/report
was not publicly recoverable during collection. Keep that result **unverified**
rather than combine it with #110 into an invented end-to-end proof. Later RK-17
also shows why mapping state cannot establish program silence.

**Reuse/delta:** use the historical setters only for their named build/route and
state claims. Audible processing, exact WAV selection, attachment/sync and reopen
require the specific missing output delta. Neither vendor API declarations nor
Closed issue state supplies it.

## Source clocks and precision

### RK-06 — Compiler/package proof is deterministic host evidence

**Proved host mechanisms / synthetic, no native claim by themselves.**
[#173 compiler](verification/issue-173/automated.md), code
`96fd70f573c3eaa1fc2b342de87ee9df00c64eaa`, and
[#177 / PR #201](https://github.com/mbelinkie/vera-script-to-timeline/pull/201)
implement v2 timed placements, media-needs, source/preparation bindings, package
inventory/topology and adapter verification. Exact rational projection and
byte-identical output tests establish those contracts; fake readbacks do not
prove physical media, placement or sound. #189/#190/#191/#192/#202/#214 add
bounded proof, omission, revision and comparison mechanisms. Their independent
native evidence comes from RK-08/RK-16/RK-21, not their CI results.

**Reuse/delta:** reuse unchanged schema/compiler/input/time-base results.
A changed consumed mapping or compiler needs focused projection/golden checks
and the affected integrated case. A new package still verifies its bytes,
inventory and provenance; neither package origin reuse nor `ready` status
authorizes a target. Existing v1 Free/package facts (RK-01) and v2 fake adapter
tests are different evidence envelopes.

### RK-07 — CFR preparation fixes a source clock before Resolve sees it

**Proved bounded preparation / actual tools and human VLC review.**
[#174 / PR #200](https://github.com/mbelinkie/vera-script-to-timeline/pull/200),
merge `7867fa4873429e799f748004896f7093d2ce625f`, retained
[qualification cases](verification/issue-174/qualification.json): 24 synthetic
cases with FFmpeg/FFprobe **8.1.2**, VLC **3.0.24**, target **24000/1001**;
decoded CFR sources 24000/1001,24,25,30000/1001,30. Qualified progressive 8-bit
SDR H.264/HEVC MP4/MOV/MKV, square pixels through 3840×2160, AAC/PCM mono/stereo
44.1/48 kHz. VFR, HDR/unknown color, interlace and ambiguous streams refuse.
`authoring-cfr/v1` derives H.264 High/yuv420p CRF18/medium/one thread and
PCM24/48 kHz. Source origin/PTS/time-base and half-open intervals are pinned;
source index is `I + floor(j × Fs / T)`. Measured sync residual ≤0.783 ms and
drift ≤0.042 ms concern these preparation cases, not Resolve playback.

**Reuse/delta:** verify source bytes/streams, offsets, rate, profile and tool
fingerprint before reusing a receipt. Change one of those and recheck that
mapping/CFR/PCM case. Same-rate reuse does not mean arbitrary-rate conversion.
#195's picture-only preparation policy remains open; excluded source sound
does not silently bypass #174's current paired-stream rules.

### RK-08 — Twelve physical qualification passes are a finite matrix

**Proved subset; full matrix incomplete / native installed qualification lane.**
[#178 report](verification/issue-178/STUDIO_QUALIFICATION.md),
[PR #247](https://github.com/mbelinkie/vera-script-to-timeline/pull/247),
Studio **21.1.1 build 10**, installed injected #209 lane, **24000/1001**:
twelve runs cover same-rate reuse, 24/29.97 nonzero inpoints, 25/30 conversion,
641-frame root/child/return/independent overlay, default/override slates and
No/Quiet/Full. Passed runs completed seven native stages, save/reopen,
pre/post geometry, bound job/MOV, cadence and fixed PCM comparison (RK-21).
The qualification profile/admission is distinct from ordinary delivery; these
runs do not qualify every normal-product profile or warning treatment.
Three-source Quiet overlap refused compilation; disabled-item readback refused
before rendering; wrong bytes/stale occurrence/word anchors refused.

EOF normalization applies only when independently verified source/native counts
and duration agree. Matrix-only still-counter handling requires a static source,
one native frame and precise zero/one-frame source times; ordinary video does
not gain a zero-speed exception. An unavailable-app recovery exercised a request
**not yet invoked**, not replay of a consumed operation. Silent test intervals
need an audible reference for comparison non-vacuity. Failed clock/partial
attempts remain failed, rather than absorbed into a later pass.

The [explicit Producer-requested closure](https://github.com/mbelinkie/vera-script-to-timeline/issues/178#issuecomment-6250336574)
did **not** accept the full physical matrix/listening. Later RK-14/RK-19/RK-22
address endpoint sound, Presenter and retry separately; they do not retroactively
complete every #178 case.

**Reuse/delta:** reuse the exact measured topology/rate/audio cases. Changed
source/tool/compiler/profile or a newly combined topology needs its affected
native check, with current target/job/bytes still verified. This is not all-media
or all-edition qualification.

### RK-09 — Provider timing admission is upstream of Resolve capability

**Proved host integration; acoustic limits remain conditional.**
[#293 / PR #296](https://github.com/mbelinkie/vera-script-to-timeline/pull/296)
at `354c79ec44327511a5d0a6aefe442c186d0bb6d1` exercised two live Inworld
TTS-2/configured Arthur rows: real service → normalized/cache assets → 102 token
projections → v2 compiler/media-needs. A fresh network-denied service reused the
verified assets with zero additional calls. It ran no Resolve operation.
The [revised #289 comparison](investigations/issue-289-sweden-provider-comparison.md)
supersedes its older recovery campaign; bounded human onset corrections and
repeat admission do not make every repeat boundary human verified. Native
provider ends remain structural metadata, not audible ends. Voice/model vendor
revision is unknown where the provider does not expose it.

**Reuse/delta:** reuse unchanged byte-bound admitted assets/configuration; a
new voice/performance must pass its own timing admission. RK-10–RK-12 address
normalization/acoustic boundaries; another Resolve import cannot repair them.
This guide grants no provider call, spending or private-text transmission authority.

### RK-10 — Sample correlation is useful but can legitimately refuse

**Conditional / synthetic and retained-input measurement.** [#297 / PR #299](https://github.com/mbelinkie/vera-script-to-timeline/pull/299)
added sample-domain alignment for same-rate mono normalization; differing-rate
sources retain the envelope route. A strong or zero-lag estimate alone does not
admit word boundaries: mismatch, ambiguity, local drift, inserted/deleted samples,
silence, negative/collapsed starts and missing audible support still refuse.
Resolve edition/version is inapplicable to this host measurement. The retained
48 kHz Inworld rows still refused this route; this was not a positive native
delivery result. RK-11 adds a separate qualified-clock route rather than
relaxing correlation thresholds.

**Reuse/delta:** carry forward measurement semantics for the same transform,
algorithm and byte-bound timing. A changed rate/filter/profile/tool needs its
affected alignment test and provenance check; do not synthesize again merely
because a retained asset failed measurement.

### RK-11 — Exact PCM replay and a qualified clock establish different facts

**Proved within limits / product plus transform-source evidence.**
[#300 report](investigations/issue-300-normalization.md), delivered by
[PR #301](https://github.com/mbelinkie/vera-script-to-timeline/pull/301) at
`129608010d11c9b05f129a0ec28209113504299a`, qualifies the default v2 graph on
FFmpeg **8.1.2**, mono **48 kHz**, no padding, with actual second-pass
`normalization_type=linear`. Reviewed filter semantics plus contiguous,
same-coordinate sample traces establish the clock. Exact replay separately
establishes that the bound raw/timing/profile/tool inputs reproduce the complete
cached PCM. Requested `linear=true` alone is insufficient because loudnorm can
fall back to dynamic mode. Version-3 measurement admits this route; older
measurement documents are historical, not current package admission.

**Reuse/delta:** use the same qualified graph/fingerprint and whole-PCM checks.
New FFmpeg semantics require source review and a clock trace, not a full Resolve
campaign. Other versions/modes/profiles keep the independent-correlation route;
44.1→48 kHz is not qualified by this same-rate result.

### RK-12 — Word onset, audible end and authored picture boundary are distinct

**Proved bounded resolution / product, with one explicit product decision.**
The [#300 placement audit](investigations/issue-300-normalization.md#retained-input-result)
found four word anchors plus a row-start placement, not the previously reported
five stale anchors. Qualified measurement resolved one missing end; another
still lacked acoustic support. The Producer approved moving that picture
boundary to the following onset in a new snapshot. No structural provider end,
frame edge or agreeing aligners became an audible end. Both narration rows
remained whole. The guarded Studio **21.1.1** build (build number unreported in
this report), at **24000/1001**, verified eleven events/media after save/reopen.

**Reuse/delta:** reuse admitted unchanged timing and the explicit revised
anchor. For a newly requested after-word edge, check that edge's acoustic
support or obtain an authored anchor choice; do not repair timings by nudging.
The earlier [#289 timing study](investigations/issue-289-timing-study.md) is
historical; its unfinished recovery protocol is superseded by the later scope,
not accepted acoustic evidence.

### RK-13 — Fractional source readback needs its actual clock

**Conditional / product.** The same [#300 report](investigations/issue-300-normalization.md)
qualifies the retained 24000/1001 narration/video mapping and authenticated
one-frame images. Precise source times, identity, rational rate and bound
sample/frame extent are checked together; observed integer getter rounding is
not permission for an arbitrary tolerance. Stills use their actual source rate;
scaling precedes anchor properties because scaling can reset them. Neutral
anchor offsets are zero. Fractional video-backed held frames with multiple
decoded source frames remain refused before adapter creation. Integer-rate
delivery retains exact getter checks.

**Reuse/delta:** preserve the exact derivation/frame map and precision rule.
A new conversion or held-frame class needs a source-clock/decoded-frame delta,
not rediscovery of OTIO import. See RK-30 for unmerged #312 corrections to a
different output verifier; that draft cannot broaden this accepted envelope.

### RK-14 — No/Quiet/Full and fractional complete-clip endpoints have measured limits

**Proved subset / native installed qualification lane and decoded sound.**
RK-08 measures Full 0 dB,
Quiet −18.0000064 dB, and No emitting no source-audio event with decoded peak
zero. It did not prove enabled fractional endpoint sound. Later
[#249 report](verification/issue-249-source-audio-endpoints.md) on Studio
**21.1.1 build 10**, installed qualification lane, independently qualifies Full
and Quiet for complete **25 fps** selections delivered at **24000/1001**:
3 seconds becomes 72 frames, original 144,000 samples plus 144 silent samples;
10 seconds becomes 240 frames, 480,000 plus 480 zeros. Picture cadence, PCM edges
within one sample, zero click drift and terminal silence passed all four cases.
Its qualification admission is not proof of every ordinary delivery profile.
The sparse ten-second Quiet fixture initially refused non-vacuity; the accepted
fixture adds a separate Full reference, not looser thresholds.

**Reuse/delta:** projection preserves selected PCM unchanged and adds only the
terminal frame remainder, less than half a frame, for a complete prepared
interval with exact native start and authored rounded duration. Other fractional
source ranges retain refusal. Recheck a changed source/interval/projection with
the same-MOV edge/gain/zero-tail delta. This is source sound, not a spanning bed,
ducking engine or exact arbitrary interior narration splice (RK-15).

### RK-15 — Fractional arguments do not preserve sample-exact interior source cuts

**Unsupported on two tested routes / native negative results.**
[#257 result](verification/issue-257/native-result.md),
[PR #258](https://github.com/mbelinkie/vera-script-to-timeline/pull/258), Studio
**21.1.1 build 10**, injected **None**, mono PCM24/**48 kHz**, **24000/1001**:
AppendToTimeline preserved fractional record placement after reopen but rounded
source edges. Required survivor end/start 232,320/241,440 samples became
232,232 (−88) / 242,242 (+802). Render settings returned true, but AddRenderJob
returned empty: no job, MOV or PCM result exists for this attempt.

[#259's distinct OTIO result](https://github.com/mbelinkie/vera-script-to-timeline/issues/259#issuecomment-6278008163),
[PR #266](https://github.com/mbelinkie/vera-script-to-timeline/pull/266), Studio
**21.1.1** (build unreported), injected **None**, OTIO **0.18.1** with 48 kHz
RationalTime: calibration `[101101,201201)` snapped to `[100100,200200)` samples.
Source **and** record edges snapped to 2,002-sample frames. The candidate's
next source/record starts became 240,240/242,242; same-job PCM failed the fixed
limits despite a silent gap. Representable OTIO sample coordinates are not
native precision evidence. Neither negative is contradicted by RK-16's whole-row
regeneration.

**Reuse/delta:** retain these exact route/build/source negatives; do not repeat
them without a changed assumption. A new route/build needs one source-edge
calibration, saved readback and bound output comparison. This proves neither
universal Resolve impossibility nor a valid workaround by changing samples,
enclosing frames or tolerances.

### RK-16 — Accepted reverse edits produce new revisions and fresh whole-row builds

**Proved bounded / integrated qualification observation → decision → rebuild.**
[#215 result](https://github.com/mbelinkie/vera-script-to-timeline/issues/215#issuecomment-6315494824),
[PR #269](https://github.com/mbelinkie/vera-script-to-timeline/pull/269),
`e7278878c79c13ec78f31e2d1541836becb21b3a`, Studio **21.1.1** (build unreported
in public acceptance), installed injected v2/**None**, generated VERA Polly
narration with #182 automatic timing at **24000/1001**:
A accepts a picture boundary and rebuilds a fresh 131-frame target with unchanged
narration; B's real linked/ripple trim moves 139→115 frames; C infers the supported
word omission, explicitly accepts it, then generates the **whole changed row**
with fresh timing (224,400 samples, 113 frames). Each own-source/observed-geometry
output comparison passed. D disabled-item refusal and explicit rejection changed
no canonical source or provider cache and started no new provider/job work.

[#260](https://github.com/mbelinkie/vera-script-to-timeline/issues/260#issuecomment-6277994466)
supplies the actual 139→115 native trim pair: authenticated render range 0..114,
230,230 samples in the shorter result, not a cropped substitute comparison.
Its earlier completed-render clock refusal remains uncertain (RK-24).
[#145 / PR #274](https://github.com/mbelinkie/vera-script-to-timeline/pull/274),
merge `fccdb0b9ef971b99ca1c5fd363e031a7d5206cc1`, then exercised the derived
real-script/visual path and retained A's cue through C's full-row regeneration;
Producer acceptance was “B looks good; C sounds good.” Original narration,
targets and script are preserved. [Current plan](plans/issue-145-generated-roundtrip.md)
supersedes earlier fixed-duration/manual-timing/splice assumptions.

**Reuse/delta:** reuse only bounded A/B/C/D inference and explicit revision
semantics, not arbitrary edits, original-recording splices or every rewrite.
#278's [removed-anchor resolution](https://github.com/mbelinkie/vera-script-to-timeline/pull/305)
is host-code evidence: resolve affected anchors before accepting the omission,
rather than guessing a surviving word. A new text change needs its own whole-row
audio/timing and accepted validator-passing revision. Consume/apply still needs
fresh current observation, one-use decision and fresh-target verification.

### RK-17 — Observation readback has context, identity and consistency limits

**Conditional / synthetic model plus native observation.** #131 models bounded
observations and reconciliation without calling Resolve. #141's native move/trim
work used Studio **21.1.0 build 14**; separate corrected #149 discriminators used
**21.1.1 build 10**, injected **None**. The
[#149 final summary](investigations/issue-149/workflow-reruns/final-summary.md),
published through [PR #151](https://github.com/mbelinkie/vera-script-to-timeline/pull/151),
keeps adverse outcomes rather than treating seven completed checks as seven
supported capabilities:

- Linked versus picture-only cuts had distinguishable rendered/subtitle results;
  phrase captions are not word-exact timing. Current-timeline Mute/Solo changed
  actual output and OTIO flags, but bus routing/sends stayed unknown.
- Mapping-mute true read back while PCM stayed baseline. The same-build
  Console/Workflow-Integration contradiction remains unexplained; version alone
  does not reconcile it.
- Scalar OTIO 0.375 retime aligned five clicks within one sample. Embedded linked
  A1 followed, separate-source linked A1 stayed at 100%. This is source/link
  topology, not a general retime curve or 29.97 proof.
- Track enable getters depended on which timeline was current. A relink returning
  true plus Online/path/date and same-layout replacement still rendered old
  source bytes. Four track locks guarded the tested Delete/disable operations;
  universal setter protection and atomic application remain unproved.

**Reuse/delta:** select/verify the intended timeline before active-only reads;
read actual output when an API flag purports to describe sound/bytes. Copied
custom stamps are not ancestry, and adjacent equal captures are content
fingerprints, not an atomic application revision token. Source topology,
visibility/mixer route or runtime changes need only that discriminator. An
unobservable/ambiguous fact remains blocked; it is not a deletion or safe default.

### RK-18 — Representation and a file-driven harness are weaker than a native round trip

**Proved host boundaries / synthetic with separately retained native inputs.**
[#131](https://github.com/mbelinkie/vera-script-to-timeline/issues/131), source
`817d0e5ab76219fdc3df95b196f84fbad0382f0a`, established representability/refusal
through stdlib experiments and real validator/compiler calls, with injected
Studio/OTIO adapters and **no Resolve call**. [#141's published plan](plans/issue-141-resolve-observation.md)
and corrected PR #151 provide actual Studio **21.1.0 build 14**, injected
Python **3.14.7**, operator-confirmed **None**, **25 fps/48 kHz** move/trim
observations. Its selected normal-speed linked +25-frame move/end trim is an
integer structural envelope, not sample-exact or arbitrary-curve evidence.

[#144 / PR #155](https://github.com/mbelinkie/vera-script-to-timeline/pull/155)
implements the [file-driven harness](plans/issue-144-roundtrip-harness.md):
compiler/package/job paths, explicit proposal/decision, canonical revision,
fresh rebuild and promotion with synthetic injected executors. It qualifies no
new WI/provider/native output. Whole-row regeneration replaces its early withdrawn
splice proposal; pre-prompter wording changes and later intact row shifts are
bounded separately from music or post-prompter recording-lock UI.

**Reuse/delta:** reuse the actual host workflow and the retained #141 edit bounds;
qualify only changed build/route/neighbor/source-handle/capture facts needed by
the real case. A manifest echo or consistent nonce/receipt is not independent
live capture. RK-16 supplies later actual integration; a fresh rebuild still
does not preserve every human refinement or prove native-object reuse (#327).

### RK-19 — Transparent Presenter proof is not continuous presenter reframing

**Proved qualification subset, later bounded product admission.**
[#250 report](verification/issue-250/PRESENTER_QUALIFICATION.md),
[PR #251](https://github.com/mbelinkie/vera-script-to-timeline/pull/251), Studio
**21.1.1 build 10**, installed injected lane, exact 320×720 RGBA still:
sampled decoded frames show root progression through transparency, independent
overlay above it/across its end, and the continuing root on return. Save/reopen,
geometry and same-MOV PCM passed. Its current-compiler qualification profile
initially admitted the exact `TEMPORARY_PRESENTER_STILL` warning; ordinary
packaging still refused it then.
Later [#145/PR #274](https://github.com/mbelinkie/vera-script-to-timeline/pull/274)
admits that same warning on the ordinary path only when canonical warning,
completion and recovery records agree. #250’s then-current ordinary-package
refusal is superseded for that bounded warning, not arbitrary errors/warnings.
The exact alpha-fixture sampled-frame measurements remain #250 evidence; the
later admission change alone does not rerun that fixture.

**Reuse/delta:** preserve source pixels, contain geometry, live root topology
and exact warning/record bindings. A changed alpha/composition seam needs the
affected decoded-frame and sound delta. Temporary still output proves neither
Wide/Tight transforms on continuous presenter footage nor general motion/focus;
#118/#119 retain those unresolved production capabilities.

## Waiting, recovery and current operations

### RK-20 — Resume waiting; never replay an uncertain mutation

**Proved bounded / product and independent native readback.**
[#302 / PR #306](https://github.com/mbelinkie/vera-script-to-timeline/pull/306)
completed the normal guarded build on Studio **21.1.1**, Intel Mac, with explicit
external scripting **Local**. Reservation-to-exit was **250.95 seconds**;
the same operation remained observable beyond 60 seconds, then verified eleven
events/media, zero discrepancies and save/close/reopen. Repeated parent start
returned the same terminal result without a second target. This was one short
package observation, not a benchmark. [Measured report](verification/issue-302-guarded-parent.md).

Follow [the parent runbook](resolve-parent-delivery-v2.md) for state meanings.
`live` can be waited on; `unknown` or infrastructure failure needs inspection.
`terminal` alone can contain a failed build; success requires matching final
evidence with `verified: true`. A legacy start-only request is consumed and has
no liveness proof. The parent resumes waiting, not partial Resolve mutations.
The earlier Media-page/empty-target preflight refusal and two legacy timed-out
attempts remain negative/incomplete evidence, not superseded successful runs.

**Reuse/delta:** reuse this parent for an unchanged guarded build exceeding a
caller window. A new execution route needs dispatch/liveness/identity tests;
render completion and process-restart recovery are separate questions. Fresh
attestation, one-use request, current target and host reservation checks still
run for each operation.

### RK-21 — Render completion, bounded output consistency and complete control proof differ

**Proved bounded output lane; complete controls unproved / native.**
[#204/#211 matrix](verification/issue-211/capability-matrix.md) enumerates 71
read-only gaps (5 supported, 23 ambiguous, 43 unsupported) on Studio
**21.1.1 build 10**/injected Python **3.14.7**. Empty job lists and codec
enumeration prove no render or full mixer state. #208's agreeing identity reads
are historical observation, not current write authority. #213 closed **not
planned**, without complete audio-control reader/change-detection proof.

The approved narrower [#209 smoke](verification/issue-209/STUDIO_SMOKE.md),
[PR #225](https://github.com/mbelinkie/vera-script-to-timeline/pull/225), on that
Studio/runtime used 111 frames at **24000/1001**, 1920×1080 ProRes422,
stereo 48 kHz/24-bit LPCM, 222,222 samples/channel. One bound MOV met fixed
zero-lag/unity-gain residual gates: programme RMS ≤0.0004, sliding 960-sample
RMS ≤0.006 per channel. Full-level input refused non-vacuity before render;
authored Quiet passed. This proves `bounded_output_residual_consistency`, not
internal control verification, continuous stability or causal exclusivity.

**Reuse/delta:** retain the comparison method and exact decoder/settings/source
assumptions; authenticate the actual job, MOV bytes, complete decode and prediction
for each output. A Complete job or setter readback alone cannot replace that
comparison. #325 even observed a Complete wrong-timeline output; corrected
selection/file/frame checks were necessary. New codec/settings/range needs its
output delta; #329 owns continuous section/saved-preset integration, still open.

### RK-22 — A canceled render can retry on a reverified target with fresh authority

**Proved bounded / native cancellation and qualification-controller retry.**
[#248 / PR #252](https://github.com/mbelinkie/vera-script-to-timeline/pull/252),
[retry report](verification/issue-248/RENDER_RETRY.md), Studio **21.1.1 build 10**:
the original render was stopped at 46%, preserving its partial MOV. A fresh
one-use retry reverified the same saved target/observable geometry and bound a
different job/output. The delivered 1,032-frame **24000/1001** MOV had stereo
48 kHz/24-bit PCM; exact same-MOV comparison passed with zero residual at the
unchanged gates. This is more than #35's synthetic stage-boundary cancellation.

**Reuse/delta:** same-target render retry is conditional on current inputs,
release/runtime, geometry and a known drained state, plus fresh finite authority
and separate job/output. Unknown state, changed target or already-consumed
mutation remains non-replayable (RK-20). Another failure class/controller change
needs its own narrow recovery case. No partial file becomes a completed artifact.

### RK-23 — Verification work can be reused within a call without trusting old operations

**Proved host optimization; native-chain context explicit.**
[#273 / PR #281](https://github.com/mbelinkie/vera-script-to-timeline/pull/281)
measured **synthetic** proof/currentness workload (16 MiB WAV, two session reopens):
9.49→5.64 seconds and 544→192 MiB hashed. No Resolve performance was measured.
[#254 / PR #330](https://github.com/mbelinkie/vera-script-to-timeline/pull/330)
then verified shared retry ancestors within one top-level synchronous check.
On the retained Studio **21.1.1 build 10** retry chain, a final-capture host check
fell 22.306→1.891 seconds, 7.423 GB→565 MB hashed; these are verifier timings,
not assembly or render speedups.

**Reuse/delta:** memoized success is scoped to one read-only operation, keyed by
path and expected digest, then discarded. New operations reread/reauthenticate
changed authority/results/source/release/runtime/artifacts; changed bytes refuse.
#312 excludes #273's seam and #313 excludes #254's seam. New performance work
must name its actual exclusive work and preserve currentness rather than use
these numbers as a general speedup forecast.

### RK-24 — All native stages can finish while host comparison still refuses

**Proved refusal/recovery boundaries / native history plus synthetic clock tests.**
[#261 result](https://github.com/mbelinkie/vera-script-to-timeline/issues/261#issuecomment-6272174344)
on Studio **21.1.1 build 10**, injected v2/**None**, source `187d19d`, completed
a fresh A observation/decision/revision/rebuild and same-job PCM comparison.
No clock step occurred inside finalization, so its bounded recheck was **not**
exercised live; unit tests replay it. Earlier completed/quarantined outputs and
expired unstarted reservations were not promoted or reset. The later #260
edited chain finished seven native stages but sustained wall-clock slew exhausted
the one recheck and left host finalization terminal/uncertain.

[#264 / PR #304](https://github.com/mbelinkie/vera-script-to-timeline/pull/304),
merge `6aa902131fd34e37430ac37ff458ce4b8011e8d3`, adds **synthetic-tested**
pre-write request-preparation handling for measured −30.9/−51.2 ms steps:
one complete recheck under #261's measured one-second bound and trusted
wall/monotonic high-water. Genuine expiry/rollback, repeated lag, source drift,
post-publication failures and sustained slew remain strict. It ran no Resolve
or OS clock modification.

**Reuse/delta:** a native Complete result does not establish final host acceptance.
Use the product's specific recheck/replan boundary; never loosen timestamps,
relaunch a consumed request or reset an uncertain slot to claim a pass. Changed
clock-handling code needs the affected synthetic measured-step test, with native
work only if the changed application behavior actually needs it.

### RK-31 — Turnaround observations are not a continuous long-program benchmark

**Measured limited performance / product.**
[#275 report](verification/issue-275-partial-benchmark.md),
[PR #309](https://github.com/mbelinkie/vera-script-to-timeline/pull/309), Intel Mac,
Studio **21.1.1** (build unreported), Inworld TTS-2/Arthur, **24000/1001**:
two narration rows/102 words, 1,143 frames (~47.7 s); one-row edit 1,149 frames.
Fresh, unchanged-cache and edited runs each verified eleven events/media after
save/reopen in **76.667 / 74.235 / 69.033 seconds** from parent reservation to
exit. One observation per case. Six existing preparations were reused; a separate
six-miss preparation run took 143.792 seconds. The report's ~5:15 cold stage sum
is approximate, not a measured continuous end-to-end wait. Initial tool/source
mapping, setup, optional render and a full program are excluded.

**Reuse/delta:** use this to motivate attribution, not predict ten-minute
performance. Changed machine/cache/provider/clip set or measured boundary needs
the affected timing observation. #312 is scoped to supply continuous clocks,
work counters,
representative density and paired forward improvements; none is accepted yet
at RK-30’s unmerged snapshot. #313 then measures reverse overhead against
resulting main.

## Current #312 / #313 handoff

### RK-30 — Shared performance fixture: provisional, not a speedup result

**Provisional / unmerged product-source report.** Snapshot of [PR #323](https://github.com/mbelinkie/vera-script-to-timeline/pull/323)
at [`c3682476ceef8bc1ccd4a7172f05691dbf24e47f`](https://github.com/mbelinkie/vera-script-to-timeline/blob/c3682476ceef8bc1ccd4a7172f05691dbf24e47f/docs/plans/issue-312-forward-overhead.md).
Its Studio rehearsal uses the existing guarded forward route and injected
output-proof route. Exact installed build must be read from its retained run
records; it is not independently established by the checkpoint narrative.
The report records these distinct stages:

- Full inputs prepared: 24 silent synthetic 1080/4K, 24000/1001 and 30000/1001
  sources, 30 measured public speech rows plus one alternate, 1,215 words and
  13,935 frames (581.205625 seconds). This is input preparation, not full native
  fixture acceptance. Speech is CC0 synthetic material with MFA onsets, not
  original provider word marks or a new human timing reference.
- A **three-row, 1,407-frame companion** covers all source classes and the
  supported held-picture boundary. The longer proof lane exceeded its existing
  limit; it must not be described as ten-minute reverse evidence. The selected
  first-row onsets quantize to 327/351, allowing the proposed +24-frame edit
  without invented timing or changed narration.
- Converted-video integer EOF readback caused an actual refusal. The draft
  output verifier now uses the derivation/byte/rate-bound precise clock check
  already used by delivery. This is a different verifier from RK-13, not a
  reason to dismiss the refusal or loosen all integer checks.
- The later pristine companion chain reports actual construction, save/reopen,
  capture, render completion and same-MOV `compared_consistent`. This is a
  checkpoint assertion backed by private retained artifacts; this collection
  did not inspect those raw artifacts. It is not accepted main evidence.
  At this revision the actual editor boundary move, edited output/inference,
  accepted revision and rebuilt target remain unfinished.

**Reuse/delta:** #312 owns its fixture/instrumentation and forward optimization;
#313 consumes the **actual merged** fixture and resulting main baseline. No
numeric optimization target, paired baseline/candidate campaign or measured
speedup is complete at this snapshot. Read-only inventory/planning can proceed.
Before **new native #313 experiments**, consume the merged reverse-relevant
guide and merged #312 fixture; compare revisions to decide which old reverse
observations remain comparable. This is a readiness recommendation, not a
change to canonical dependencies, permission to resume a held chat, or a
dependency of #312 on #338. #312 retains its active owner; #313/#336 remain held
under their current instructions. Update this entry when #312 lands.

## Effects, motion and editorial integration limits

### RK-40 — Named picture transitions work; a complete installed catalog does not follow

**Proved subset / native, investigation-only adapter.**
[#292 report](investigations/issue-292-transitions.md), delivered in
[PR #295](https://github.com/mbelinkie/vera-script-to-timeline/pull/295),
`bab9b6ad`, Studio **21.1.1 build 10**, external Local scripting, macOS Intel,
640×360/**24 fps** red/blue clips and 48 kHz tone: native Cross Dissolve,
Edge Wipe and Push applied; bundled Fusion Slide Left/Cross Dissolve and one
authored custom transition applied. Adjacent clips with verified handles gave
the requested 24-frame left/center/right spans. Delete/recreate produced exact
12-frame native/custom replacements; saved/reopened output and narration
matched their controls. Picture-only output kept the fixture's narration PCM
identical to the **cut-only render**, not to the differently routed mono source.

Direct native properties were empty/refused. A manually changed Edge Wipe
export exposed `angle`; a seeded native OTIO import requested 180°, re-exported
180°, persisted, and rendered a distinct split. This qualifies that seed/option,
not arbitrary native settings. Instantiated custom Fusion Curve/Ease enums
were set/read and visibly changed output. Fusion OTIO omitted its graph/controls;
FCPXML omitted the native angle. Neither is an arbitrary effect-preservation path.

**Reuse/delta:** reuse the exact qualified combinations, category and source
bindings. Native/Fusion Cross Dissolve share a name; name alone is insufficient
identity. Template files/registry are not the full Edit catalog, and no installed
third-party transition representative was qualified. A new effect/control needs
one exact application/readback/reopen/output delta. #88 owns production library
integration; the accepted scope is an expandable verified library, with exhaustive
discovery deferred. The portable package still rejects transitions (RK-42).

### RK-41 — A successful transition call can violate requested geometry

**Unsupported requests / native negative evidence.** On RK-40's fixture,
zero handles refused; two-frame handles silently shortened requested 24 to 2;
a six-frame gap yielded 12 rather than 24. An initial exclusive-end mistake
left a one-frame gap and misleading two-frame results. These are failed precise
requests, not support. [Retained observation](investigations/issue-292-transitions.md#real-runtime-checkpoint).

**Reuse/delta:** check actual adjacency, source handles and requested span before
writes, then read back actual geometry. The proved replacement is delete/recreate
in a disposable fixture; changing a neighbor of an existing transition or
preserving an unknown effect needs its own delta. Unknown/opaque settings must
be preserved through a proved route or the affected write refused; #327 owns
that remaining preservation proof. This does not blanket-block independently
bounded safe changes.

### RK-42 — Saved row intent and native probes are not normal product delivery

**Proved domain mechanisms; runtime unsupported/unproved.**
[#307 / PR #308](https://github.com/mbelinkie/vera-script-to-timeline/pull/308)
and [#310 / PR #315](https://github.com/mbelinkie/vera-script-to-timeline/pull/315)
prove contiguous row/run/section operations, Stash exclusion/restore, Undo and
provisional Sorting acceptance with unchanged-baseline guards. Their evidence
is TypeScript/consumer tests, independent of Resolve edition. They preserve or
flag saved audio/transition intent; they do not place audible spanning cues,
clone finishing or run a selected outbound plan. The
[compiler](../packages/contracts/src/compiler-core-v2.ts) refuses active
`rowAudioSpans` and non-cut row-transition intent; the
[portable verifier](../python/vera_timeline_agent/v2_package.py) rejects OTIO
transitions. RK-40 does not supersede those product refusals.

The [2026-10-26 #326 correction](https://github.com/mbelinkie/vera-script-to-timeline/issues/326)
supersedes #307/#310's starting-row-only broken-span rule: retain the consecutive
original prefix and stop at its first interrupted join. That revised domain
rule and audible result remain unproved. #326 owns that proof, #100 production
audio; #327 owns finishing preservation, #328 frozen selective execution/retry,
and #104/#157 production composition. #35's tested generic job stages (synthetic
executors) do not prove O09's item-level atomic plan or a native continuation.

**Reuse/delta:** reuse existing pure operations and their explicit refusals.
Check only the new audible/finishing/atomic-execution seam through the same saved
intent and actual product path. A mock receipt or independently hand-placed
timeline cannot fill that gap. [Sorting handoff](plans/issue-310-sorting-stash.md)
remains the API/limit reference; its older audio-rule text is historical where
the later #326 decision differs.

### RK-43 — Native image motion is real; exact focus and easing remain open

**Partial / native rendered evidence.** [#325 report](investigations/issue-325-native-image-zoom.md),
[PR #333](https://github.com/mbelinkie/vera-script-to-timeline/pull/333),
tested source revision `716f7773`, Studio **21.1.1 build 10**, external scripting and
native OTIO, 1280×720/**24 fps**, public square grid. Dynamic Zoom moves and
explicit None is static. OTIO reconstruction gave 24/48/96/144-frame extents;
Append requests instead became 120-frame stills, and Duration/SetSpeed refused.
Raw OTIO center/scale endpoints moved at 48/96 frames and persisted after
save/close/load, not a process restart. All 432 explicitly configured older
frames stayed identical after changing project scaling defaults; a use-project
control changed framing.

Imported ease 1/2/3 read back but rendered identically to linear for every frame.
Fit plus zoom cropped the square at endpoints; raw extreme centers persisted
but rendered black. Direct start/end/background properties refused. Opaque
key labels are not frame coordinates; normalized focus, safe arbitrary geometry,
reverse direction, contain/background composition, nonlinear easing, native
in-place trimming and Free import remain unqualified.

**Reuse/delta:** #336 should reuse this motion/None/duration/persistence evidence
and qualify only focus/output mapping and demonstrated composition/ease gaps
through the normal compiler/package path. Resolve defaults must become explicit
frozen occurrence values. A matte is only a candidate for the demonstrated
background gap, not accepted fallback output. #164 retains the product contract;
#319 capture integration. The later automatic-zoom decision supersedes older
static-default spec text without clearing these feasibility holds.

### RK-44 — Scene detection mutates its analysis timeline and has false positives

**Diagnostic-only / API plus native.** [#283 / PR #322](https://github.com/mbelinkie/vera-script-to-timeline/pull/322)
and [runtime report](investigations/issue-283-resolve-scene-cut-api.md), Studio
**21.1.1** (build unreported), duplicate isolated timeline: the 144-frame/24 fps
synthetic three-shot clip yielded starts 0,48,93,96. Both known cuts were found,
plus a false-positive three-frame segment. The original timeline fingerprint
was unchanged; VERA marker custom data round-tripped on the duplicate. API
status reports progress, not a cut list. This does not establish confidence
scores, reliable dissolves/flashes/montages or arbitrary source mapping.

The private motivating derivative yielded a cut four frames before the selected
out. Default warning 12 / automatic 3 means warning only. Its original manifest
bytes were unavailable, so historical content identity is unverified. Adjacent
direct source-range requests had non-uniform readback; an exact compensating
slide was not proved. The [Producer accepted these research limits](https://github.com/mbelinkie/vera-script-to-timeline/issues/283#issuecomment-6403626246),
not automatic correction. Broader representative accuracy was not established.

**Reuse/delta:** reuse duplicate/detect/enumerate as a bounded diagnostic lead.
#331 must first prove exact rendered source-window correction through the actual
compiler/package route, with retained synthetic bytes and unchanged neighbors,
before automatic writes. A closed research issue does not satisfy that positive
gate. Range/threshold changes only require proximity reevaluation once a valid
source/profile/frame-map cache exists; this research does not implement one.

### RK-45 — One semantic Fusion target contract is not a general graphics engine

**Proved subset / native, private rendered evidence summarized publicly.**
[#219 accepted record](https://github.com/mbelinkie/vera-script-to-timeline/issues/219#issuecomment-6200112909),
delivered through [PR #230](https://github.com/mbelinkie/vera-script-to-timeline/pull/230),
tested executable/manifest `5ae5e34fd3594071865974d25afc4975bf878972`, Studio
**21.1.1 build 10**, project-local import, 1920×1080/**24 fps**, 240 frames:
one unchanged Table template supported sequential/start-only-until-next/end,
disjoint overlap, reset and same-target continuation with exact sampled stepped
states. Two fresh-import sets in one project/session produced 36 matching decoded
RGB pairs; PNG file differences were ICC timestamps. Save/reopen/post-render
readbacks passed. These are not independent-machine or complete-animation proofs.
The [contract's provenance limits](investigations/issue-219/contract-proposal.md)
also retain that the exact pre-refactor first preparer binary was not preserved;
current-code readbacks independently checked both resulting instances.

**Reuse/delta:** reuse only its pinned target/state/control mapping, with
conservative data-reorder invalidation and authored-exit visibility. Proprietary
template/render/raw readback is unavailable for independent public inspection;
the public accepted report is the source here. Free is untested/manual-or-blocked.
#167 still owns cue compilation/runtime; #8/#9/#99/#166/#218 are not certified by
this probe. Changed graph/control/data mapping needs the affected target-boundary
and output delta; lower-third baking does not prove highlights on this template.

## #318 action crosswalk

The [original S03/S05 matrix](investigations/issue-318-capability-audit.md)
remains the control-level index and preserves its design holds. This crosswalk
locates Resolve-relevant evidence or its absence; it grants no blanket design
clearance. Later #325 and #326 conclusions qualify the older matrix's wording.

| Matrix actions | Guide / remaining gap |
| --- | --- |
| A04 source trim and word endpoints; B05 linked AV/reflow; B12 narration rewrite | RK-10–RK-13 plus RK-14/RK-16; bounded accepted edits do not qualify arbitrary rewrite or retime. |
| A05 source No/Quiet/Full | RK-14/RK-15; cross-row bed audio is a separate gap. |
| A06 and B10 spanning/audio-only cues | RK-42, open #326; new first-interruption policy supersedes starting-row-only behavior. |
| A07–A11 row/Sorting/Stash; B06 and B09 structural changes | RK-42: pure intent/consumer mechanisms; general native selective structural executor remains #328/#104. |
| A16 relink; A17 capture; A25/B02/B14 build/readiness | RK-01/RK-02/RK-06; verified bytes and edition guards are reusable, app acquisition/link/readiness composition remains #319/#70/#101/#157/#158. |
| A18 and B08 graphics/overlays | RK-45 and RK-04: pinned template subsets, not arbitrary graphics/finishing preservation. |
| A19 and B13 markers | RK-01/RK-06/RK-17 observe/emit bounded markers; no general selective marker executor. #328 remains open. |
| A20/B04 Wide/Tight; A24 presenter identity reaching native route | RK-19/RK-21 do not establish continuous presenter reframing; #118/#119 remain the owners. |
| A21 still motion | RK-43; #325 supplies partial evidence, #336 remains held with focus/framing/ease and product seam unfinished. |
| A22/A23 and B20 transition application/preservation | RK-40/RK-41/RK-42; qualified probe subsets versus cut-only portable path. #88 integration and #327 preservation remain open. |
| B01/B03/B11 reviewed selection, skips, conflicts | RK-16–RK-18 is not outbound selection. #328 must prove frozen selection and bounded conflict composition. |
| B07 replacement/Resolve-only items; B17 finishing | RK-41/RK-42/RK-45; arbitrary opaque effect/grade/Fusion preservation remains #327, not proved by fresh rebuild. |
| B15/B16 partial failure/same-attempt retry | RK-20 and RK-22 prove components; O09 item-level plan/baseline transaction remains #328/#104/#157. |
| B18/B19 render settings/ranges/waiting | RK-20–RK-22; #329 still owns continuous section range and saved-preset/override/output proof. Stage cancellation is not active-render cancellation. |

A01–A03, A12–A15 and display-only parts of A24 are authoring, service or UI
questions covered by the matrix, not missing native experiments. Their absence
from this guide is deliberate. Source acquisition, permissions, collaboration,
history and taste decisions retain their original owners.

## Reuse audit: apparent repeats and the actual delta

These are source-based comparisons, not a count of wasted runs or hours saved.

| Earlier evidence → later question | Classification and precise boundary |
| --- | --- |
| [#300](investigations/issue-300-normalization.md) verified an eleven-event build → [#302](verification/issue-302-guarded-parent.md) ran the same selected package beyond 60 seconds | **New execution-route/recovery proof.** #300 already settled that package's placement. #302 needed durable liveness, same-operation waiting, terminal evidence and no duplicate target on a parent-worker route. Repeating import-format discovery would add nothing; exercising the new waiting route was necessary. |
| [#292](investigations/issue-292-transitions.md) native/custom transition output → [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) preservation across neighboring updates | **Genuinely new capability.** Reuse exact effect/control/span facts. The unanswered delta is carrying finished and Resolve-only material through the outbound update with output intact; re-enumerating the installed catalog would not answer it. |
| [#297](https://github.com/mbelinkie/vera-script-to-timeline/pull/299) sample correlation → [#300](investigations/issue-300-normalization.md) qualified-clock admission | **Changed measurement assumption.** The retained rows legitimately refused correlation; exact replay alone was insufficient. Source semantics and same-coordinate traces supplied independent clock evidence. New provider generation or another Resolve import would not resolve that clock question. |
| [#325](investigations/issue-325-native-image-zoom.md) setters persisted ease/centers → [#336](https://github.com/mbelinkie/vera-script-to-timeline/issues/336) normal-product image motion | **New combined path plus unresolved visual behavior.** Reuse motion/None and reconstructed extents. Setter-only repetition would miss the already measured linear-equivalent ease and black extremes; the needed delta is safe focus/framing/ease output through compiled saved intent. |
| [#109's currentness rules](resolve-workflow-integration-v1.md) and [#302's reservations](resolve-parent-delivery-v2.md) → [#312/#313](https://github.com/mbelinkie/vera-script-to-timeline/issues/313) overhead reduction | **Necessary per-operation freshness versus avoidable rediscovery.** Package bytes and current target can change after a prior success, so current authorization/integrity/identity and consume-time observation must still run. Historical format facts can be reused. Measure duplicate work within one invocation; an earlier success cannot justify a cross-operation trust cache or skipping a fresh observation before accepting a decision. |
