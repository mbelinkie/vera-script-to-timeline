# Issue 141 second-opinion handoff: identity, assets, and freshness

Task ID: handoff_identity_v2  
Evidence scope: R1 identity/lineage/context/Copy-Paste metadata drift, R4 asset
bytes and occurrence removal, and R5 freshness/ABA. This is a read-only
handoff assembled from retained records; no Resolve action, staging, protected
media-byte read, external action, or test rerun was performed.

The links below are intentionally written as if this text lived at
docs/investigations/issue-141/second-opinion-handoff.md: output and out links
therefore begin with ../../../.

## Scope and evidence rule

All native observations are bounded to DaVinci Resolve Studio 21.1.0 build 14,
the synthetic project VERA Issue 141 Synthetic Probe 20260930-01a0f318
(project UID 97037b5a-aab6-48a9-b7e4-4c5697ae10a0), and generated media.
External Scripting None and synthetic-only scope are standing operator
attestations. The final native action was the reviewed duplicate; no later
native mutation is part of this handoff. The retained [final findings](final-findings.md)
and [chronological report](report.md) remain authoritative for evidence ordering
and the External acceptance gate.

The product constraint is stronger than a successful Resolve readback:
[Product Spec §7](<../../../docs/Script-to-Timeline Product Spec - Fable Rev2.md>)
requires stable entity IDs and immutable snapshots, while [§8.2](<../../../docs/Script-to-Timeline Product Spec - Fable Rev2.md>)
requires actual byte verification and treats paths as locators. [§6.13](<../../../docs/Script-to-Timeline Product Spec - Fable Rev2.md>)
requires stable marker identity and explicit handling when an anchor is
ambiguous. [§13](<../../../docs/Script-to-Timeline Product Spec - Fable Rev2.md>)
requires visible, blocking failures instead of silent substitution or deletion.
The [Issue 141 plan](../../../docs/plans/issue-141-resolve-observation.md) says
that two adjacent reads are a content fingerprint, never an atomic revision
token.

All 39 preparation/Resolve checks being complete means each named observation
was performed and reviewed; it does not resolve the explicit lineage, byte-
display, context-getter, freshness, or ABA unknowns below.

Classification used below:

- **Supported (bounded):** the named operation and exact observed delta were
  performed and independently reviewed.
- **Ambiguous:** the readback is real, but multiple causes or identities remain
  possible; it cannot authorize a semantic inference.
- **Harness/preparation failure:** a guard or setup assumption stopped the
  probe; it is not evidence of a Resolve capability failure.
- **Unrun:** proposed follow-up only. It must not be reported as existing
  evidence.

## R1 — identity, lineage, context, and Copy/Paste metadata

### R1.1 Native timeline duplication: new occurrence IDs are normal creation, not ancestry proof

**Classification:** Supported bounded Timeline.DuplicateTimeline; lineage remains
ambiguous.

**Exact operation, state, and delta.** For the first native duplicate, the
reopened cache setting was restored through the probe's one SetSettings call
with a settings dictionary, followed by an equal-adjacent baseline pair. The
action then called Timeline.DuplicateTimeline("VERA 141 R1 identity") once on
the selected source timeline, passed the returned timeline handle through
Project.SetCurrentTimeline, and called SaveProject once.
The duplicate returned timeline UID
aa2b8e36-83bd-4292-9e33-217c00ca192f. Its six occurrence UIDs were disjoint
from the six baseline occurrence UIDs; the five distinct source-media UIDs
were shared. Track names, ranges, enable values, marker signatures and marker
custom data matched the source readback.

The source timeline's post-duplicate readback also changed all six track
enabled getters true -> false. Exact pool Usage changes were Video 1/2/3
1 -> 2, repeated.wav Audio 1/2 2 -> 4, and bed.wav Audio 3 1 -> 2. Eight
audio property keys were omitted on each of three audio items. The journal
contains no setter for those fields. They are retained raw observations, not
evidence of a track/effect edit or reset. The cache restoration, duplicate,
and saved readbacks had equal adjacent passes. The later standalone cache
restoration record is a different action: it called Project.SetSetting once
for perfCacheClipsLocation with a key/value and returned true; its postflight
matched the saved pin.

Evidence: [native duplicate review](evidence/native-duplicate-success/summary.json),
[reopen cache refusal](evidence/native-reopen-cache-refusal/summary.json), and
[cache restoration](evidence/cache-restoration-success/summary.json).

**Inference boundary and VERA requirement.** Disjoint IDs establish fresh
occurrence instances. Shared source IDs and matching signatures establish
copied shape/source association in this case. Neither proves that a duplicate
is the semantic descendant of a particular source occurrence, because copied
metadata and identical signatures are reproducible. A VERA identity decision
must retain the operation journal, source/occurrence IDs, source bytes or
verified artifact hashes, ranges, markers, and selected context separately;
it must refuse or request review when lineage is inferred only from name,
order, marker/custom-data equality, or signature equality.

**Known failures and limits.** The first close/reopen attempt stopped after
SaveProject/CloseProject because the current project ID changed; the guard did
not call LoadProject or duplicate an unexpected project. A duplicate-only
launch then refused because the exact project was not current. The manual
reopen readback differed only in project/timeline perfCacheClipsLocation
(CacheClip versus the owned path) and refused before duplication. A later
reopen had eight adjacent Usage changes and refused: timelines[0] tracks[0]
and [1] changed 2 -> 6; timeline[4] tracks[0], [1], [2], [3], [4], and [5]
changed 27 -> 28, 20 -> 21, 20 -> 21, 48 -> 50, 48 -> 50, and 21 -> 22.
Its stable follow-up showed eight Resolution leaves
changing 0x0 -> 1920x1080: two producer transcription proxy items, each with
one pool-item and one timeline-mapping leaf across two pool passes. None of
these refusals proves unsupported Resolve reopen or duplication, and the cache
path's resolved target was not inferred. Cache restoration ended
restored-to-saved-pin after one true setter and an exact postflight pair.

### R1.2 Razor, trim, and move: observed identity preservation is operation-specific

**Classification:** Supported bounded editorial observations; no general
lineage rule.

**Exact operations and deltas.** The approved native menu sequence selected the
reciprocal V1/A1 pair and called one Split Clips at frame 1600. The left
occurrence IDs remained and new right IDs were created; record ranges became
1500–1600 and 1600–1699, source ranges 0–100 and 100–199, reciprocal links and
markers were retained, and the expected source Usage +1 was the only other
modeled delta. One Trim -> Resize -> End to Playhead at frame 674 changed
each target's GetEnd 699 -> 674, GetDuration 199 -> 174, source end
199 -> 174, source end time 7.96 -> 6.96 seconds, and right offset 1 -> 26;
IDs, starts, source starts, links, markers and other state stayed equal. The
move driver sent 25 nudge-right menu actions, each followed by a complete
readback. Only target GetStart/GetEnd fields advanced one frame per action
(1000 -> 1025 and 1199 -> 1224); source bounds, IDs, markers, links and all
other content stayed fixed. Restoration changed only recorded secondary-track
locks and playhead; it did not save or undo the edit.

Evidence: [razor comparison](evidence/r1-razor-success/independent-comparison.json),
[trim evidence](evidence/r1-trim-success/), [move evidence](evidence/r1-move-success/),
and the dated [editorial report](report.md#approved-r1-linked-pair-move--2026-10-01-0607-0618-utc).

**GetEnd versus source geometry.** The matrix preparation used requested
AppendToTimeline endFrame = duration - 1 for the 200-frame generated clips.
That request convention and the later raw getter convention are separate
facts. The retained endpoint calibration applies only to named 100%-speed
integer cases: for those cases, the observed record GetEnd behaves as the
exclusive edge of the tested frame range. The synthetic getters can still
report record GetEnd = 199/duration = 199 while source getters report source
frames 0–199 and 7.96 seconds for the 200-frame input; source-bound getter
semantics remain recorded exactly as returned, not normalized. A 50% retime
also changed source end 199 -> 99 while record end/duration stayed 199. VERA
must store record start/end, source start/end, time values, offsets, speed and
subframe values as separate facts. It must not turn a GetEnd value into a
sample-exact word boundary or general endpoint convention. See the retained
[endpoint calibration review](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json)
and [R1 report details](report.md#source-pcm-ranges-and-clip-getter-boundary-arithmetic).

**Limits.** These are one synthetic split, one trim, and one 25-frame move.
They do not prove arbitrary movement, semantic section boundaries, sample-
exact audio edits, rendered output, or ancestry of either split half. A copied
marker can exist on both halves, so marker equality is not a unique binding.

### R1.3 Genuine Copy/Paste: copied metadata and four Out changes are retained as drift

**Classification:** Supported bounded Copy/Paste; metadata/meaning ambiguous;
the strict guard correctly stopped on an unexplained modeled delta.

**Exact operation, state, and delta.** From the verified Edit state, the native
menu sequence selected the pinned V1/A1 pair, called Copy once, moved the
playhead to frame 2250, then called Paste once. It returned new V1/A1
occurrence IDs 7dc4a98b-33cb-4feb-9727-b2bca434138e and
a9175c87-6bc0-4c07-a167-3b7c9de70fba. Both had record bounds 2250–2449,
source bounds 0–199, reciprocal links, and inherited marker/custom data;
source Usage +1 was observed. The original occurrences remained.

The complete-pair guard then stopped on exactly four Matrix pool leaves. In
both pool passes, these paths changed from 00:00:08:00 to empty:
poolPasses[0]/items[7]/evidence/GetClipProperty/value/Out,
poolPasses[0]/timelineMappings[2]/poolItemProperties/value/Out,
poolPasses[1]/items[7]/evidence/GetClipProperty/value/Out, and
poolPasses[1]/timelineMappings[2]/poolItemProperties/value/Out. The stopped
review found no other timeline/pool/byte delta. No undo, cleanup, save,
render, retry, or automatic context restoration followed. The copied clips
and the four Out changes remain retained evidence.

Evidence: [Copy/Paste delta review](../../../out/issue-141-observation-20260930-01a0f318/r1-copy-paste-delta-review.json),
[stopped Copy/Paste evidence index](evidence/r1-copy-paste-stopped/evidence-index.json),
[copy restoration review](evidence/r1-copy-paste-stopped/r1-copy-restore-review.json),
and [report entry](report.md#genuine-r1-copypaste-retained-with-pool-out-drift--2026-10-01-0720-0725-utc).

**Inference boundary and VERA requirement.** New reciprocal IDs and an actual
Copy/Paste journal support a copied-occurrence classification. Inherited
markers/custom data do not prove ancestry or unique semantic binding. The
four Out changes have unknown render-range significance; VERA must preserve
them as an explicit unresolved delta and block automatic apply where their
meaning matters. It must not normalize them away or call the output
correct/incorrect without an output check.

**Known failures.** The first Copy/Paste launch refused its Edit/known-format/
empty-queue preflight while Resolve was on Deliver; no copy occurred. An
earlier selection reader expected a dictionary although the installed API
returned a list, and a local snapshot path check was corrected before the
native paste. These are harness/preparation issues, not capability findings.

### R1.4 Selected context and final duplicate: projection is a comparison aid, not state evidence

**Classification:** Supported bounded context dependence and final duplicate;
context-sensitive getters remain unknown for semantic interpretation.

**Exact observations.** Selecting R1 changed 60 raw fields relative to the
Matrix-selected pair: 12 track-enabled values and 48 presences of exactly
these eight audio properties: AudioDialogueLevelerBackgroundReduction,
AudioDialogueLevelerEnabled, AudioDialogueLevelerLiftSoftDialogue,
AudioDialogueLevelerMode, AudioDialogueLevelerOutputGain,
AudioDialogueLevelerReduceLoudDialogue, AudioVoiceIsolationAmount, and
AudioVoiceIsolationEnabled. IDs, geometry, markers, links, source metadata,
settings, Usage, and all other structural fields were equal. The local
repair projects out both track enabled/locked getters, Usage, and the eight
named audio properties from its cross-context signature, keeps every raw field,
and still rejects changed IDs, source bounds, record bounds, clip enablement,
markers, or an unlisted audio property. The
initial native duplicate stopped before mutation on the context mismatch. One
Project.SetCurrentTimeline restoration received the Matrix timeline handle,
returned true, and produced an exact stable six-timeline/pool pair.

The final native sequence called Timeline.DuplicateTimeline exactly once from
the selected R1 source and restored Matrix selection by passing the Matrix
timeline handle through Project.SetCurrentTimeline. It created
VERA 141 R1 identity repeat (timeline UID
1835476c-8bc1-48fc-bb78-99906490480a) with six new occurrence IDs disjoint
from every original occurrence. Source/signature multisets matched; original
six non-Usage fields and original pool non-Usage fields were preserved. The
review measured Usage changes on five original pool media items, 142 timeline
Usage paths across four timelines, and exactly one new duplicate pool proxy plus
one new timeline mapping. All Usage paths ended in Usage; no unknown unrelated
delta was found. The final Matrix context equaled its checkpoint. No save,
render, cleanup, or further native action followed.

Recovery status: selection restoration is PASS with exactly one native
Project.SetCurrentTimeline call receiving the Matrix timeline handle, exact
pair/context equality, and no save, render, clip, lock, or playhead mutation.
The final seven-timeline review is
PASS_WITH_EXPLICIT_LINEAGE_LIMIT; its terminal action is the one duplicate.

Evidence: [selected-context review](../../../output/r1-selected-context-independent-review.json),
[native restoration review](../../../output/r1-selection-restoration-native-independent-review.json),
[final seven-timeline review](../../../output/r1-final-seven-independent-review.json),
and [final reopen review](../../../output/r1-reopen-final-independent-review.json).

**Required interpretation.** The projection is only a context-normalized
comparison over a retained raw capture. The helper's structural signature pops
both track GetIsTrackEnabled/GetIsTrackLocked fields, Usage, and the eight
named audio properties; the independent comparison still reports the actual
cross-context delta as 12 enabled values, 0 locked values, and 48 audio-key
presence differences. It does not prove the underlying track enabled/locked
state, audio effects state, mute state, or speech state; missing context keys
and getter failures remain unknown. VERA must bind every control/effect
observation to the same selected timeline and a fresh complete pair, retaining
raw fields and errors. It may project only these exact reviewed context fields,
never arbitrary missing or failed getters.

**Known failures.** The first restoration launch stopped before integration
menu selection because the main window was unavailable; the later read-only
window check supplied availability and one guarded restoration succeeded. The
prior refusal remains terminal evidence. The final duplicate review did not
rerun the old shared six-timeline collector, reopen, save, or render.
## R4 — asset availability, bytes, and occurrence removal

### R4.1 Preparation/refusal history is not asset behavior

**Classification:** Harness/preparation failures, retained to prevent false
capability conclusions.

The initial complete media-pool inventory refused before ImportMedia. The
documented FilePath-dictionary ImportMedia shape refused; the separate path-
list form accepted ImportMedia, CreateEmptyTimeline, Project.SetCurrentTimeline, and
AppendToTimeline, then its post-append proxy/equality guard refused on an extra
or unreadable track item. A read-only follow-up verified exactly one online
base.mov occurrence with source/record bounds 0–199 and generated source bytes
matching the approved hash. Later MediaPool.UnlinkClips returned true, but the first
complete offline inventory refused because the guard did not allow Resolve's
OFFLINE - locator prefix. A start-timecode repair also shifted the R4 timeline
from 90000 to 0 and the occurrence to negative record coordinates before
refusing on unreviewed drift. None proves import, unlink, relink, offline
handling, or deletion unavailable.

Evidence: [pool refusal](evidence/r4-pool-inventory-refusal/summary.json),
[dictionary import refusal](evidence/r4-dictionary-import-refusal/summary.json),
[path-list partial](evidence/r4-path-list-import-partial/summary.json),
[post-append read-only state](evidence/r4-post-append-read-only/summary.json),
[offline refusal and prefix diagnosis](evidence/r4-offline-prefix-read-only/), and
[R4 report history](report.md#r4-initial-media-pool-inventory-refusal-october-1).

VERA should preserve the exact refusal and partial state, then require a fresh
complete read of source UID, locator, bytes, occurrence UID, ranges and pool
mapping before any transition. It must never infer asset deletion from a
failed inventory or an unreadable proxy handle.

### R4.2 Offline-present versus same-byte relink

**Classification:** Supported bounded offline/relink; occurrence and source
remain present through the offline transition.

**Exact operation, state, and delta.** In the valid in-range re-prepared R4
arrangement, one MediaPool.UnlinkClips operation received the media-pool item
handle whose journaled source UID was 81d81dc0-4c37-478b-8079-03debba5e780.
The occurrence UID
65a7bcd1-f211-4dee-9726-8c7e0b89cc84 remained in the timeline with the same
source/record ranges and source identity. Online reads became Offline, the
locator acquired Resolve's OFFLINE - prefix, and offline source-byte evidence
was marked not accessed. Exported local frames 0 and 50 showed Media Offline.
One MediaPool.RelinkClips call received the media-pool item handle and the
verified original base.mov path, then returned true; complete postflight pairs
matched the original online timeline/pool state, including IDs, ranges and
source hashes, and the original playhead was restored.

Evidence: [offline/relink summary](evidence/offline-cycle-continuation-success/summary.json),
[relink recovery review](evidence/r4-recovery-success/summary.json), and
[R4 report entries](report.md#2026-10-01-0121-utc--r4-unlink-offline-prefix-refusal).

This proves offline-present is distinct from occurrence removal for the tested
source. It does not prove arbitrary-source relink, arbitrary effects, general
visibility, program output, or byte access while offline. The earlier offline
picture arrangement with timeline start/end 90000 was rejected as out of range;
its failed preparation must not be used as output evidence.

### R4.3 Same locator and Online status do not prove bytes or displayed replacement

**Classification:** Supported bounded wrong-byte mismatch; displayed replacement
is ambiguous.

**Exact operation, state, and delta.** The generated relink candidate at the
same locator was replaced with wrong bytes
771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b instead of
expected c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942.
A single MediaPool.RelinkClips refresh received the media-pool item handle and
the same-locator candidate path, then returned true. Source UID, occurrence
UID, locator, Online status, ranges and all other captured metadata stayed the
same; only explicit source-byte evidence changed to mismatch. The sampled frame-0
PNG after refresh was byte-identical to the earlier original slate, so this
run did not establish that wrong replacement bytes were displayed. The
original bytes were restored and refreshed once; complete state and the
original frame-0 sample then matched exactly.

Evidence: [wrong-byte summary](evidence/r4-wrong-bytes-success/summary.json),
[R4 report entry](report.md#2026-10-01-0426-0428-utc--wrong-bytes-survive-unchanged-identitystatus-readbacks),
and [retained source readbacks](../../../out/issue-141-observation-20260930-01a0f318/r4-readonly-20261001T003141.604326Z.json).

VERA must verify bytes independently of locator, UID, path and Online status;
a mismatch is stale/ambiguous asset evidence requiring review or refusal. It
must not infer displayed replacement from metadata or one cached frame.
Protected producer media was not read or hashed in these generated-media
checks.

### R4.4 Occurrence removal is distinct from asset deletion and identity restoration

**Classification:** Supported bounded non-ripple occurrence removal; asset
deletion and restoration are not established.

**Exact operation, state, and delta.** With a stable pinned R4 pair, one
Timeline.DeleteClips call received the timeline-item handle whose journaled UID
was af55478a-0ba3-458a-a6e1-e47b2544111d, with False for ripple, and returned
true. The exact occurrence disappeared; the source pool item remained online
with UID 81d81dc0-4c37-478b-8079-03debba5e780, unchanged generated-byte hash,
and Usage 1 -> 0. All other pool fields and timeline state were equal in
adjacent postflight reads. No MediaPool.DeleteClips, append, save, render,
rollback, or retry occurred.

One later AppendToTimeline of the same source at absolute record frame 0
returned a different occurrence UID 65a7bcd1-f211-4dee-9726-8c7e0b89cc84.
Its read-only follow-up verified source/record ranges 0–199 and Usage 0 -> 1,
but this is a new occurrence, not the removed identity restored. A page guard
refused the immediate append postflight; the later read-only capture is the
authority for the new-ID facts.

Evidence: [independent removal comparison](evidence/r4-removal-success/independent-comparison.json),
[removal result](evidence/r4-removal-success/result-extract.json),
[new occurrence readback](evidence/r4-post-append-read-only/summary.json), and
[R4 report entries](report.md#2026-10-01-0313-utc--occurrence-removed-source-retained).

VERA must represent timeline occurrence removal, source-pool retention, and
new occurrence preparation as separate events. A removed UID cannot be
recovered by matching source bytes, path, marker, or range; restoration of
semantic identity requires an explicit retained mapping or human decision.
## R5 — freshness, stable reads, and ABA

### R5.1 What the capture checks prove

**Classification:** Supported bounded drift detection; freshness/atomicity
remains unproven.

The separate quiet repeat took two adjacent reads in each launcher invocation.
After excluding only expected capturedAt/stage envelope fields, raw
observation payloads and content fingerprints matched exactly; there were no
getter failures or capture failures. This proves a repeatable quiet read for
that state, not close/reopen behavior or an application revision token.

The controlled metadata test called UpdateMarkerCustomData once between
observations, returned true, and changed only the named Matrix marker custom
data. The comparator returned inconsistent-refused; a second setter restored
the original marker and complete state. The real capture-loop test then
changed the same marker during capture, observed exactly that interpass delta,
returned inconsistent-refused, and verified full timeline/pool restoration
(observerRestored=true and fullTimelineAndPoolStateRestored=true).

Evidence: [quiet repeat](evidence/quiet-repeat/summary.json),
[controlled marker change](evidence/r5-controlled-metadata/summary.json),
[real capture-loop refusal](evidence/r5-capture-loop-success/summary.json),
and [R5 report entries](report.md#2026-10-01-0354-utc--controlled-metadata-comparison-refuses-a-change).

### R5.2 Marker note and one-frame move

**Classification:** Marker-note edit and linked one-frame move are supported
bounded observations; unrelated state and freshness remain ambiguous.

The producer's marker editor change altered only Matrix marker 0 Notes to
Issue 141 R5 marker-note observation; IDs, ranges, sources and other marker
fields stayed equal in both full passes. A fixed Trim -> Nudge -> One Frame
Right menu action then produced a byte-identical readback and the checker
refused its expected delta; no retry, undo, or save followed. A later producer-
confirmed move, independently compared from retained JSON without replay,
showed linked video UID 3f2de461-d510-46f8-939f-0c794d48e38b and audio UID
22561398-bce0-4c22-b55f-a73d3ad5e4cf moving record start/end 0/199 -> 1/200
in both stable fresh passes. Source bounds, IDs, links, enabled state and the
calibration marker identity/note were preserved.

The fresh comparison also retained an unrelated cache-path change, selected-
timeline change, authorized producer timeline/pool additions, and omission of
the eight context-sensitive audio property keys. Its applicationRevisionToken
is null. It explicitly does not claim atomicity, ABA exclusion, all unrelated
state unchanged, or independent proof of the menu mechanism.

Evidence: [marker/move summary](evidence/r5-manual-marker-move/summary.json),
[confirmed marker note](../../../out/issue-141-observation-20260930-01a0f318/r5-manual-note-confirmed.json),
[fresh independent comparison](../../../out/issue-141-observation-20260930-01a0f318/r5-independent-fresh-comparison-20261001T181642Z.json),
and [R5 report entries](report.md#r5-manual-marker-note-and-no-effect-menu-diagnostic--1307-1313-utc).

**Known failures and limits.** The first manual-move readback timed out with
no new injected result. A later capture saw the requested 0/199 -> 1/200
geometry but refused on changing Usage and cache locators and lacked pool
passes. The stable later comparison is therefore a bounded move result, not
an all-fields-equal result. Equal adjacent reads cannot exclude a change that
occurs and is undone between reads (ABA), a simultaneous UI edit, or a change
between capture and apply.

## Successful VERA inference criteria

The following are the minimum conditions for using these observations in VERA
reconciliation or apply logic:

1. **Identity and lineage:** retain occurrence UID, source UID, source artifact
   hash, record/source geometry, links, markers, custom data, and operation
   journal as separate fields. Treat newly allocated IDs as normal creation.
   Infer ancestry only from an explicit operation-bound mapping plus verified
   source/occurrence evidence; copied signatures, names, order, markers, and
   shared source IDs are insufficient.
2. **Context:** capture selected timeline UID, page, queue/idle state, playhead,
   selection, complete timeline/pool pairs, and getter errors/missing fields.
   Compare control/effect properties in the same selected context. A reviewed
   context projection here excludes the explicitly reviewed track enabled/locked
   getters, Usage and eight named R1 audio properties for structural comparison;
   same-context control preservation is checked separately. It cannot turn
   projected fields, ignored errors or absent keys into known state.
3. **Geometry:** preserve record and source getter geometry independently,
   including integer and subframe values, time values, offsets, speed and
   endpoint convention. The tested GetEnd calibration is not a universal
   sample or word-boundary rule.
4. **Assets:** verify actual bytes before accepting a locator, UID, path, or
   Online status. Distinguish an offline-but-present occurrence from an absent
   occurrence, and distinguish occurrence removal from source-pool deletion.
   Mismatched bytes or unknown display behavior must block automatic
   replacement or deletion.
5. **Freshness:** require stable, complete adjacent reads and refuse any
   observed drift, incomplete inventory, getter failure, context change, or
   unexplained delta. These checks provide no atomic revision or ABA proof;
   apply authorization needs an application revision token, transaction/lock,
   or an explicit human review at the actual apply boundary.
6. **Failure policy:** preserve raw evidence and partial states. Do not label a
   guard refusal as unsupported Resolve behavior, and do not normalize away
   unknown Out, cache, Usage, Resolution, or context-property differences.

## Proposed unrun counterexamples and follow-up tests

These are proposals only; none was run for this handoff.

| Area | Unrun counterexample | Success criterion for a future VERA inference |
|---|---|---|
| R1 lineage | Duplicate or Copy/Paste two occurrences with identical markers/custom data and then mutate only one occurrence's marker, source range, or destination. | The mapping stays bound to the journaled source/destination IDs; copied metadata alone never selects the sibling. |
| R1 context | Capture the same timeline selected before and after a deliberate track/effect change, then capture it inactive. | Same-context reads expose the real change; inactive getter differences are tagged context-dependent and never interpreted as control state. |
| R1 geometry | Exercise 100%, 50%, fractional and non-frame-aligned ranges with frame stills/PCM and source/record getters. | VERA stores source and record bounds separately and adopts only explicitly calibrated endpoint conventions. |
| R1 Copy/Paste drift | Reopen or render the retained four-Out Copy/Paste case, then copy a case with a materially different source. | The four Out leaves receive a verified interpretation or remain a blocking unknown; no silent normalization. |
| R4 bytes | Relink a deliberately visually distinct wrong-byte file at the same locator, invalidate/reopen the cache, and sample output plus source hash. | Byte hash, displayed sample, source UID and occurrence mapping are compared independently; stale display cannot authorize replacement. |
| R4 availability | Compare source-present offline, missing/offline locator, same-byte relink, wrong-byte relink, and an occurrence removed while the source remains. | Offline state, byte mismatch, occurrence absence, and source-pool retention become distinct classifications with exact IDs and hashes. |
| R4 deletion | In a newly authorized disposable fixture, remove one occurrence, all occurrences, and (if explicitly approved) the pool item with ripple false/true. | Timeline occurrence removal never masquerades as asset deletion; source and occurrence IDs are tracked through each explicit destructive operation. |
| R5 ABA | Arrange A -> B -> A between two reads, including a marker or Usage change. | A monotonic revision/transaction token or lock detects ABA; equal content fingerprints alone fail closed. |
| R5 UI race | Edit/select/relink concurrently with capture and again between capture and apply. | The apply boundary is atomic or explicitly reviewed; stable preflight is not treated as a lease. |

No current record establishes a global Resolve API absence, general lineage
algorithm, arbitrary-source relink guarantee, atomic revision primitive, or
complete collector coverage. Those questions stay unclaimed until one of the
follow-ups produces the required evidence.
