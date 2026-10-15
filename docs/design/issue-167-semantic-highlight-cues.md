# #167 — semantic highlight targets and cues

Design proposal, 2026-10-15. Acceptance pending. No implementation, template
registration, production profile qualification or frozen contract approval is
implied. [CN-167-P1](../plans/issue-167-proposed-contract-change.md) is a separate,
unapproved proposal.

## 1. Decision

Store cue intent on a graphic **occurrence**, separately from immutable graphic
content/provenance. Each cue selects stable targets from one exact manifest and
requests a named state for an exact interval. Resolve all cues together, then
produce one aggregate control schedule. Finishing one cue cannot clear another
cue's active target.

For start-only intent, the author must choose `until_next_or_end` or
`until_graphic_end`. “Next” means the first strictly later start time among
**all cues on this occurrence**, regardless of target; simultaneous starts form
one group. This is a proposed product decision, not something #219 proved in
ambiguous cases. No last-writer-wins, inferred narration time, automatic target
repair or interpolated transition is allowed.

## 2. Authority and exact boundaries

Main baseline is `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`. Read-only accepted
sources below are separate from main; no branch was integrated.

| Source | Exact revision and authority | Used here |
| --- | --- | --- |
| Product spec §§6.2, 7, 8.2 and Phase 9 | [baseline spec](https://github.com/mbelinkie/vera-script-to-timeline/blob/22f65c4f2b4ff61e7b08f530cdda3d92fea11d08/docs/Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md) | Stable narration anchors; immutable template/use/build pins; bytes versus locators |
| #24 D24-03/18 | `e72aa2436fa49d6b256b7cf811d5c1dea39120c3`; [acceptance](https://github.com/mbelinkie/vera-script-to-timeline/issues/24#issuecomment-5500767669), [decision table](https://github.com/mbelinkie/vera-script-to-timeline/blob/e72aa2436fa49d6b256b7cf811d5c1dea39120c3/docs/investigations/issue-24-representative-script-coverage.md) | Two-of-three; exact cue anchors; reset/continuation; disjoint overlap; contradictions block Release |
| #7 | `7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab`; [approved boundary](https://github.com/mbelinkie/vera-script-to-timeline/blob/7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab/docs/plans/issue-7-fusion-graphics-contract-change.md) | Existing `VisualEvent.id`, trusted `resolvedGraphics`, template tuple, semantic hash and editor-neutral manifest intent |
| #20 | `951c658bf06fc9b06caeab88c9d43809c41cef94`; [accepted service](https://github.com/mbelinkie/vera-script-to-timeline/blob/951c658bf06fc9b06caeab88c9d43809c41cef94/packages/contracts/src/template-library.ts) | Project-local immutable template revisions, copying/authorization; caller-defined use hash remains distinct |
| #166 design | `0c50a30a4e78fd771b51ee6732e78641ceb3da7b`; [design](https://github.com/mbelinkie/vera-script-to-timeline/blob/0c50a30a4e78fd771b51ee6732e78641ceb3da7b/docs/design/issue-166-derived-graphic-provenance.md), [CN-166-P1](https://github.com/mbelinkie/vera-script-to-timeline/blob/0c50a30a4e78fd771b51ee6732e78641ceb3da7b/docs/plans/issue-166-proposed-contract-change.md) | Accepted provenance relationship and later separately approved note; #218 implementation remains unstarted. That format currently allows lower-third semantics only |
| #219 | delivered `460371f398974882289f57de30ddd6b3db590e70`; receipt read at `570288f18d028dfae317d1e0ace5005f5d0cd5bb`: [proposal](https://github.com/mbelinkie/vera-script-to-timeline/blob/570288f18d028dfae317d1e0ace5005f5d0cd5bb/docs/investigations/issue-219/contract-proposal.md), [manifest](https://github.com/mbelinkie/vera-script-to-timeline/blob/570288f18d028dfae317d1e0ace5005f5d0cd5bb/docs/investigations/issue-219/target-manifest.json), [acceptance](https://github.com/mbelinkie/vera-script-to-timeline/blob/570288f18d028dfae317d1e0ace5005f5d0cd5bb/docs/investigations/issue-219/producer-acceptance.md) | Exact two-target Table evidence; historical manifest status text does not override the later receipt |
| #8 provisional only | `75325e01015ff5b5285acbc980bf78e16a49ae1a`; [plan](https://github.com/mbelinkie/vera-script-to-timeline/blob/75325e01015ff5b5285acbc980bf78e16a49ae1a/docs/plans/issue-8-studio-live-placement.md) | Candidate package/placement/use/readback seam. Open/In review; no acceptance, interface freeze or successful native result inferred |

Accepted #7/#20 are absent from starting main. Main v2 has
`GraphicRevisionSource {kind:"graphic_revision",graphicId,revisionId}` and
media-based graphics, not a live Fusion cue event. Do not rebuild a lookalike
or treat a source reference as implemented semantic content. #166's provenance
hash `P` binds content/data/template, never cue timing. Reuse #218; extend its
typed Table applicability only after separately approved CN-167-P1.

### Exact positive profile

Template byte SHA-256 `869bffd705ac949a58bcb25d6bc80de5027219792336f0d599be81162447440a`;
target-manifest byte SHA-256 `dc21391f032d35cadab909e590302bc7ed8a46567703da93b4f82846d7948424`;
dataset byte SHA-256 `1aec6e192c64748a6102507e45c59bb5d193bb8ae5e43e3e5e2469672d220d64`;
static declaration subset SHA-256 `4884b85a9e3d93af3be86fb836b63ed98cf0664e128e6e21e5f0453141fd343c`.
These are four different byte domains. Neither setting hash nor declaration
subset hash is a package digest. The package/revision registration is future
work; do not fabricate those pins from a display name.

Only Studio 21.1.1 build 10, 1920×1080, 24/1 fps, 240 occurrence frames,
the exact synthetic dataset and `target-a`/`target-b`, `base`/`emphasis`, discrete
native text animation are positively evidenced. Sampled sequential, overlap,
reset, continuation, until-end, save/reopen and repeated imports in one project/
session passed. No full-frame sweep, continuous playback, fresh-application
repeat, arbitrary data/rate/duration, Free or continuous transition proof exists.
That evidence permits designing this profile; production integration remains
unqualified until the runtime owner passes its gates. New schedules below are
semantic expectations, not claims of additional native proof.

## 3. Relationship and fields

`occurrence → cue set → exact content/template/target manifest pins → targets`
and `cue intent + frozen narration evidence → resolved semantic schedule`.
The trusted package owns `target ID → state → control mapping`; authoring never
supplies a node, expression, path or raw control value.

All proposed objects are closed. IDs use the receiving contract's existing
opaque/UUID rules; versions are positive safe integers; frames are nonnegative
safe integers. `Hash` is `sha256:` plus 64 lowercase hex characters. Bare probe
digests above acquire only this prefix at a typed boundary, without rehashing.

| Record / proposed fields | Meaning and validation |
| --- | --- |
| `GraphicCueSet {schemaVersion:"graphic-cues/v1",id,version,occurrence,contentPin,targetManifestHash,cues}` | One set per occurrence, unique set/cue IDs within document. Nonempty cues; deleting all cues removes the optional set. No reuse of cue ID as use ID |
| `occurrence` | Discriminated `{kind:"visual_event",eventId}` for v1; `{kind:"overlay_event",overlayEventId,payloadId}` or `{kind:"primary_slot",sequenceId,slotId,payloadId}` for v2. Must resolve exactly once to a graphic in the same project/document. A return-to-parent is part of its original occurrence, not a fresh cue owner |
| `contentPin {template,semanticSnapshotHash,provenance}` | `template` is exact #166 tuple `templateKey/projectRevisionId/packageDigest/entryAssetHash`. `provenance` is the existing manual/derived binding; derived pointer resolves through #218. v2 additionally pins `graphicId/revisionId` equal to its source reference. No cue set may attach to legacy-unclassified content |
| `targetManifestHash` | Exact retained UTF-8 manifest **file bytes**, including its newline/formatting. Resolves through authorized trusted dependencies to the unmodified #219 manifest and an independently verified package binding. Not canonicalized into a different hash |
| `GraphicHighlightCue {id,version,targetIds,state,timing,transition?}` | Nonempty unique target ID set, sorted lexically when frozen; one state applies to all selected targets. IDs must exist, and each must support the state. Authored cue array order is retained, never sorted to repair intent |
| `timing` | `TimedPlacement`-equivalent `{kind:"timed",start?,end?,durationMs?}` with consistent two-of-three, or `{kind:"start_only",start,endPolicy:"until_next_or_end"|"until_graphic_end"}`. `start/end` reuse current `PointAnchor` shapes; first profile admits only current word-onset or evidenced audible-word-end anchors on the owning narration block. Event-edge, between-block, self/cyclic or cross-block references are refused in this first profile |
| `transition` | Omitted or explicit `null` means discrete state replacement. A non-null `{id,version}` names a separately qualified template transition; none is allowed by the accepted Table manifest. Unknown/non-null requests block; they are never silently stripped |
| Trusted `ResolvedGraphicTargetBinding {projectId,template,targetManifestHash,manifestArtifactId,semanticSnapshotHash,datasetSha256,profileId,profileEvidenceHash}` | Resolver/package-owned immutable relationship, unique by template/content/manifest tuple; rejects duplicate/unused records. Retains exact manifest bytes and attests semantic `tableData` bytes equal manifest dataset. Evidence receipt is independently verified, not authority granted by the author supplying an ID |
| Manifest target entries | Preserve #219 `id,label,kind,bodyPosition,states,base`; identity is scoped by exact manifest/template/data pins. Position and label are bindings. Do not manufacture stable IDs from text or position |
| `ResolvedGraphicCueSchedule {schemaVersion:"graphic-cue-schedule/v1",cueSetHash,occurrence,contentPin,targetManifestHash,frameRate,recordRange,cues,segments}` | Compiler result, not authored frames. `recordRange` is `{startFrame,endFrame}`; v1 boundary converts to existing start+duration shape when embedded. Each resolved cue retains ID/version, exact rational endpoints, endpoint evidence/deltas, local and record half-open ranges, targets/state and resolved end policy. `segments` covers the whole occurrence with complete semantic target states |
| `cueSetHash`, `cueScheduleHash` | `H(normalized cue set)` and `H(full resolved schedule)` respectively; no self-hash. Use #7 `canonicalJson/sha256CanonicalJson` (recursive key sort, array order preserved, two spaces, LF, UTF-8). Normalize target sets and omitted transition to null **before** authoring snapshot freeze, retaining edit history; never silently normalize an already hashed record |
| Execution plan / receipt | Package-owned plan addresses schedule hash, exact manifest bytes and verified binding; aggregates local writes. Runtime receipt adds actual timeline/comp origins, translated writes/readback, actual edition/build and save/reopen evidence, outcome and diagnostics. It does not redefine the semantic schedule hash |

#7 `semanticSnapshotHash = H({values,badgeAsset})` stays unchanged for every
accepted lower-third value, including nulls. Table is a **new typed branch**:
`values:{tableData:string}, badgeAsset:null`; exact UTF-8 `tableData` bytes must
match the dataset hash. CN-167-P1 proposes extending the accepted hash domain
to that branch, never relabeling a dataset byte hash as `S`. #166 `P` retains
its full snapshot hash material and remains independent of cue timing. Table
provenance uses that same relationship with the approved new typed branch;
no generic JSON semantic escape hatch is introduced. #20 caller-supplied
`resolvedSnapshotHash` and selection/copy hashes keep their accepted meanings.

Changing only timing changes cue hashes/build, not `S` or `P`. Changing data,
template, labels, targets, positions or manifest invalidates the old cue set
binding even if `S` or visible values happen to match. Changing the source
evidence with identical displayed data changes `P` and requires explicit cue-set
rebind/review; no silent reuse under a new content pin. Locators/audit timestamps
are outside content identity. Hashes do not grant access or publisher trust.

## 4. Exact timing and state algorithm

1. Freeze the document, occurrence range, template/content/manifest and timing
   evidence. Validate identities, authorization and profile before creating an
   execution plan. Every cue on the occurrence succeeds or the entire schedule
   refuses; there is no partial valid subset for ordinary Preview or Release.
2. Resolve anchors to exact reduced rational seconds using the existing
   narration map, frozen block/token/version/text and audio/timing hashes. Word
   onset uses actual evidenced onset; audible end requires its actual support.
   Sentence/estimated/unknown, next-word-derived audible ends, stale/missing
   evidence or unverifiable audio bindings block. Durations derive time only;
   they never create a token anchor. Do not retime narration to make a cue fit.
3. Two-of-three: start+end derives duration; start+duration derives end;
   end+duration derives start. `durationMs` is a positive safe integer divided
   by 1000 exactly. If all three exist, compare exact rational equality before
   quantization. Fewer than two, duration alone, nonpositive/reversed/outside
   the graphic or owning narration block, arithmetic overflow or unknown fields
   refuse. No clipping, padding or tolerances that turn disagreement into success.
4. Resolve every start independently, including end+duration starts. Authored
   array must be nondecreasing in exact resolved start time. Equal starts are
   legal in retained array order; duplicate cue IDs are not. Inserting/reordering
   a cue is an explicit edit creating a new version/hash, never compiler repair.
5. For `until_next_or_end`, find the minimum **strictly greater exact start**
   anywhere later in this occurrence's cue array; use it, or Graphic end when
   none exists. It includes timed/start-only cues, base cues and disjoint targets.
   Same-time cues share the next later boundary; no same-time zero interval is
   invented. `until_graphic_end` ignores all other cue starts. This rule requires
   no recursive end resolution. A later start quantizing to the same frame
   causes a collapsed-interval refusal, not a skip to another cue.
6. Quantize resolved endpoints once with existing ceil rational-to-frame policy:
   `F(t)=ceil(t * fpsNumerator/fpsDenominator)` in the owning block's local
   time, then add its compiled record-frame start. Do not ceil the duration
   independently or round a second time. Keep exact endpoints, timing evidence
   IDs/hashes and signed rational delta `F(t)/fps - t` per edge. Derived Graphic
   end is its compiled exclusive end and cites occurrence-boundary evidence;
   do not invent an audible-word endpoint there. Quantized `s >= e` refuses.
7. Let occurrence record start be `G`, length `N`; local range is
   `[s-G,e-G)` within `[0,N)`. Timeline absolute frame is
   `timeline.startFrame + recordFrame`; comp frame is `observedCompStart +
   localFrame` only after actual placement verifies 1:1 rate/duration mapping.
   Never assume timeline or comp frame zero. Trimming, speed change, split,
   interrupted primary appearance or incompatible mapping refuses this profile.
8. Sweep sorted distinct boundaries `{0,N, all starts/ends}`. At each boundary
   remove ending cues and add starting cues **atomically**, then examine the
   complete active set for each target. No active cue means base. One distinct
   requested state means that state. More than one distinct state means conflict
   (including explicit base versus emphasis): refuse before state writes, naming
   all conflicting cues and interval. Equal-state overlaps/touches are unioned;
   continuation is automatic while at least one such cue remains active. There
   is no priority from cue order, target order or latest start.
9. Emit maximal nonempty half-open segments with a complete target-state vector;
   merge adjacent equal vectors. Keep resolved cue identity/evidence separately
   even if aggregation removes a boundary. On completion restore only targets
   with no remaining active claim. At local `N` lifetime ends: no write at `N`
   inside this clip and no state carried to another occurrence. A new occurrence
   initializes at base independently. State does not force visibility through
   the template's authored entrance/exit.
10. Table mapping: emphasis target-a→position 1, target-b→2; base→absence.
    Serialize the full emphasis set once per changed boundary, numeric ascending:
    `[]→""`, `[A]→"1"`, `[B]→"2"`, `[A,B]→"1,2"`. At frame 0 initialize
    directly to the aggregate effective there, even when empty; never a separate
    transient base write. Trusted package maps to `EV24Table/Controls` Background
    `HighlightRows` Text/TextEditControl, with native `BezierSpline`
    `ControlsHighlightRows` Text output and pinned `DiagnosticOver` Merge output.
    Runtime must verify exact graph/control/type before assigning controls.
    #219 showed timed `SetInput` alone overwrites a constant; the qualified native
    modifier is required. Do not animate one target independently or inject an
    expression. No nonzero transition duration, easing or interpolation exists.

Graph/type mismatches found only after import can leave audited disposable
setup, but must yield zero semantic-control/state writes. Preflight validation
errors cause zero application writes. A runtime write/readback failure stops
the new target as failed, retains partial evidence, and never reports placement
verified; recovery uses the product's audited fresh-build path, not blind retries.

## 5. Synthetic examples and expected results

All examples use fictional #219 data, exact same profile/pins, A=`target-a`,
B=`target-b`. Exact dataset is `ITEM\tVALUE\nAlpha\t18\nBeta\t27\nGamma\t9`
with real tabs/LFs and **no final newline**. Gamma has no addressable target.
Assume verified synthetic onset anchors at 2, 3, 4, 5 seconds resolve to local
48,72,96,120. These are supplied example evidence, never inferred narration.
`[s,e)` below is resolved output shorthand, not permitted authored frame input.

| Case / authored intent shorthand | Expected schedule, all other frames base |
| --- | --- |
| Sequential A emphasis `[48,72)`, B emphasis `[72,96)` | `0:""; 48:"1"; 72:"2"; 96:""` |
| A start 48 until-next/end; B start 72 until-Graphic-end | `0:""; 48:"1"; 72:"2"`; B state through 239, no write 240 |
| A start 48 until-next/end; disjoint B timed `[72,96)`; A timed `[120,144)` | A's first cue ends 72, **not 120**. `0:""; 48:"1"; 72:"2"; 96:""; 120:"1"; 144:""` |
| Simultaneous A/B start 48 until-next/end; A base `[96,120)` | Both start-only cues end 96. `0:""; 48:"1,2"; 96:""`; no zero-length cue from equal starts |
| Last A starts 120 until-next/end | Ends 240; same end as explicit until-Graphic-end. An absent end policy instead blocks |
| Disjoint overlap A `[48,96)`, B `[72,120)` | `0:""; 48:"1"; 72:"1,2"; 96:"2"; 120:""` |
| Touching A emphasis `[48,72)`, A emphasis `[72,96)` | `0:""; 48:"1"; 96:""`; no reset/flash/write at 72 |
| Equal overlapping A emphasis `[48,96)`, A emphasis `[72,120)` | `0:""; 48:"1"; 120:""`; first completion does not clear second |
| A emphasis `[48,96)`, A base `[72,120)` | Block conflict on `[72,96)`; zero state writes. “Base” is an explicit claim, not a priority clear |
| A emphasis `[48,72)`, A base `[72,96)` | Legal; `0:""; 48:"1"; 72:""`; half-open touch has no conflict |
| One cue targets `[A,B]`, emphasis `[48,72)` | One aggregate write `"1,2"` at 48, empty at 72 |
| A emphasis `[48,72)`, next A emphasis `[73,96)` | Base for frame 72; this is a gap, not continuation |
| Start=2s + durationMs=1000; or end=3s + durationMs=1000 | Both derive `[48,72)`; start=2s/end=3s/durationMs=999 refuses even if rounded endpoints could agree |
| Start 2s, end 2.001s | `ceil(48)=48`, `ceil(48.024)=49`: one frame; no hidden minimum cue length. Two endpoints 2.001s/2.002s both ceil to 49: refuse collapse |
| Anchor points at “Alpha” but only sentence-level timing exists | Block precision; retain intent and request valid timing evidence. No distribution across words, nearest mark or manual narration shift |
| Anchor asks for audible end but only next-word onset exists | Block missing audible support; onset evidence cannot masquerade as audible end |

For an occurrence at record `G=1000`, timeline start 86400 and observed comp
start 7, local `[48,72)` maps to record `[1048,1072)`, timeline absolute
`[87448,87472)`, comp `[55,79)`. Native start/mapping must be measured; these
numbers do not assert an actual placement. Native lifetime at local 239 may
still be B emphasis while the authored exit is black, as #219 sampled. Preserve
entrance/exit rather than stretching them to expose an otherwise hidden cue.

## 6. Success, refusal and recovery

Diagnostics identify document/occurrence/cue IDs, code, severity, expected and
observed safe hashes/profile fields, conflicting local/record interval and
specific repair. Sort by occurrence ID, cue ID, code, interval; omit nonexistent
values rather than guess. Source paths/bytes/native dumps remain private.
Retain frozen intent, timing evidence/deltas, source/content/manifest pins,
semantic schedule and hashes, profile evidence, planned delivery and actual
adapter receipt. Planned support and verified execution are separate statuses.

| Condition | Visible outcome / diagnostic | Recovery |
| --- | --- | --- |
| All identity/timing/state checks pass, exact profile and runtime gates satisfied | `planned_supported`; after actual write/readback/save-reopen, `verified` | Retain separate compiler and runtime receipts; identical frozen input yields identical schedule bytes |
| Runtime gates still open (including #8/#167/#218 or note approval) | `blocked`, `GRAPHIC_CUE_INTEGRATION_UNQUALIFIED` | Finish required owners/approvals and exact integration tests; this design alone never enables delivery |
| Unknown/empty/duplicate target IDs, unsupported state, missing manifest/mapping or duplicate binding | `blocked`, `GRAPHIC_CUE_TARGET_INVALID` or `GRAPHIC_CUE_BINDING_MISSING` | Explicitly repair cue/registered manifest, new revision; no nearest target/state substitution |
| Dataset edit, reorder, add/remove row or label change; target label/position/state edit | `blocked`, `GRAPHIC_CUE_BINDING_STALE` | New reviewed dataset-specific manifest; author reviews every target mapping and cue, explicitly selects new content/set version. Existing builds unchanged |
| Template/entry/package/manifest/dataset/semantic hash mismatch | `blocked`, `GRAPHIC_CUE_HASH_MISMATCH` | Restore exact authorized bytes or explicitly migrate. Byte hashes and semantic hashes are checked in their own domains |
| Source/provenance mismatch/lost evidence/cross-project binding | `blocked`, existing #166 provenance diagnostic plus cue binding context | #218 repair/relink exact evidence or new content revision; never downgrade derived to manual to bypass it |
| Incomplete/inconsistent/reversed/outside/collapsed interval, unsorted starts, missing start-only policy or overflow | `blocked`, `GRAPHIC_CUE_TIMING_INVALID` | Repair intent and preview new resolved interval; never clamp, reorder or extend occurrence |
| Missing/stale/uncertain timing or unsupported anchor kind | `blocked`, `GRAPHIC_CUE_TIMING_UNQUALIFIED` | Refresh machine evidence or explicitly repair anchor; manual timing review must follow accepted audio workflow if later needed |
| Same-target different active states | `blocked`, `GRAPHIC_CUE_STATE_CONFLICT` | Change interval/target/state explicitly; no winner chosen |
| Wrong edition/build, rate, dimensions, duration, dataset, speed/trim/appearance mapping or profile | `unqualified` and Release blocked, `GRAPHIC_CUE_PROFILE_UNQUALIFIED` | Restore exact qualified profile or separately accept narrowly scoped evidence for the requested profile; matching names do not qualify it |
| Free requested | `manual_required`, no automated cue delivery; Release blocked, `GRAPHIC_CUE_MANUAL_REQUIRED` | Retain cue sheet and an explicit manual-completion item linked to occurrence/schedule; later manual completion needs its own accepted evidence. No automatic bake/live substitute or resolved status |
| Non-null transition, muted/custom state, unsupported target kind | `unqualified` and Release blocked, `GRAPHIC_CUE_CAPABILITY_UNQUALIFIED` | Select supported intent or separately approve/prove a bounded extension; do not silently drop the request |
| Live graph/control/type differs after audited import/setup | `blocked`, `GRAPHIC_CUE_NATIVE_BINDING_MISMATCH`; zero semantic writes | Retain refused target/setup and evidence; restore exact package/profile or new approved qualification |
| Native assignment/readback/save-reopen fails after writes | `failed`, `GRAPHIC_CUE_NATIVE_VERIFICATION_FAILED`; no verified placement | Retain partial-stage receipt; explicit audited fresh-target recovery. Existing timelines remain untouched |
| Older reader cannot preserve cue set/schedule/evidence | `blocked`, `GRAPHIC_CUE_CONSUMER_UNSUPPORTED` | Upgrade reader or explicitly remove cues in a new authored revision; no silent field stripping |

Manual outcome is unfinished work, not an alternative successful runtime.
A forced diagnostic preview may display the blocked cue sheet/placeholder
with its diagnostics; it must not present a static or partly animated graphic
as an accepted cue result. A stale mapping invalidates **all** targets for this
manifest, including a target whose row happened to stay in place.

## 7. Compatibility, integration and ownership

| Boundary | Proposed seam / retained constraint |
| --- | --- |
| v1 accepted #7 source/authoring | Add typed `ev24-table` source branch, optional document-level `graphicCueSets`; retain `VisualEvent.id`, range/layer and existing lower-third fields unchanged. No Table minimum/entrance timing borrowed from the lower-third: this profile is exactly 240 frames |
| v2 authoring | Keep `GraphicRevisionSource` unchanged; optional document-level cue sets bind actual overlay/primary owner IDs and selected graphic revision. No cues in citation/supporting text; no duration inferred from citation. Initially live execution is **unsupported** by current media-only compiler |
| Trusted compiler dependencies | Optional `graphicTargetBindings` default empty; require exact binding for every cue set, refuse unused/duplicates. Reuse #7 template resolution and #218 content/provenance resolution with approved Table type; no paths/nodes from author input |
| Manifest v1 | Optional `FusionGraphicEvent.graphicCueScheduleHash`; addressed semantic schedule inventory retained in package; no raw Fusion node/control IDs in editor-neutral event. Existing event/source identities unchanged |
| Manifest/dependencies v2 | Do not invent a live Fusion variant in this note. A future media realization must bind immutable rendered asset hash to selected content **and cueScheduleHash**, requiring a separately qualified materializer; otherwise refuse cue-bearing media. Cue authoring does not imply implementation |
| Report | Per-occurrence schedule pointer, planned/verified/unqualified/manual/blocked/failed outcome and exact diagnostics/evidence; v2 diagnostic enum needs additions, v1 open pattern does not. Existing planned #7 materialization values keep their meanings |
| Target package / adapter | Exact retained manifest+package bytes, schedule and binding; deterministic aggregate local plan; actual origins/native graph/control verification and readback receipt. Adapt to accepted #8 seam after it closes; reconcile any difference explicitly before Ready |
| Provenance | #218 realizes CN-166-P1 once; CN-167-P1 adds Table applicability, leaving `P/S` relationships, storage authorization, source evidence and replay/refresh/migrate semantics intact |

Absence of cue fields means legacy/no cues, with identical accepted compiler
bytes. Present-but-empty sets, unknown owner, missing classification or dropped
cue metadata cannot mean legacy. New closed-schema readers/types must precede
writers; old readers visibly reject. Do not strip cues on downgrade or rewrite
stored revisions. Every explicit target/content/template migration retains
old/new pins and an author decision receipt, then recompiles/qualifies; there
is no automatic label/position remap. Revisions and checkpoints retain old pins.
CN-167-P1 enumerates generated types, frozen-test and acceptance consequences.

Runtime owner and duplicate-audit evidence are retained in
[the handoff](../verification/issue-167/runtime-handoff.md). Its canonical
dependencies must include #8 **and** #167 **and** #218, plus any actual required
registration/qualification owner; no parent link substitutes. #9/#99 retain UI/
registration, #8 placement, #218 provenance, #10 truthful Free fallback. No
other issue is dispatched here. New profile qualification is a bounded runtime
gate, not a new open-ended research program or broader capability claim.

Runtime acceptance must add owned synthetic timing/negative/golden tests for
every row in §§5–6, exact byte repeat and no-cue legacy bytes, missing/unused/
wrong-project pins, equal-time and frame-collapse cases, source refresh with
same visible data, target migration, one aggregate control stream and zero writes
on preflight refusal. Exact accepted-source integration, all approved frozen
notes and current generated types precede runtime. Actual Studio acceptance
must verify the requested schedule, measured origins, graph/types/aggregate
writes, authored visibility and save/reopen at the exact profile. Broader rate/
dataset/version/Free/transition or fresh-launch guarantees need their own
explicitly accepted proof; none is inherited from #219's sampled evidence.

## 8. Producer acceptance

1. Open this exact design at the delivered commit, §§3–5. Decide whether global
   next-start groups, explicit end policies, strict timing precision, equal-state
   union and base-versus-emphasis conflict match the intended editing behavior.
   Expected: all examples have one outcome with no guessed timing or base flash.
2. Read §§2, 6–7 and the runtime handoff. Accept or revise the strict dataset-wide
   invalidation, explicit repair, Table-only evidence limits and unfinished Free
   manual outcome. Expected: no design approval qualifies runtime or waives #8.
3. Read CN-167-P1. Accept or revise its proposed interfaces/defaults and separate
   Table extension to #166. This accepts a proposal for handoff only; frozen
   changes require a distinct `Approve CN-167-P1 at <commit>` response.

Record `Accept issue #167 design at <commit>` or `Revise issue #167 step <n>:
<change>`. Keep the issue In review until that exact acceptance is retained.
