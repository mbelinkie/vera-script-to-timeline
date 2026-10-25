# S03/S05 capability audit — #318

Audit date: 2026-10-25. Source baseline: `6f5d73f4e96af6b7709c853c2af15c78bc5183aa`
(`origin/main`, freshly fetched at launch). Final integration baseline: `044011a1447713a0656ec382fc99e0ea0f64cf45`, including merged #310/PR #315; re-fetched before final push. This report audits current retained
authoring and outbound-review promises; it does not resume design or certify
the finished application. [Issue #318](https://github.com/mbelinkie/vera-script-to-timeline/issues/318)
owns this finite audit. #33 and #147 are historical inputs, not current
capability certificates.

## Evidence rules

- **W — working:** executable implementation supports the stated bounded claim.
- **M — mechanism proved, integration unfinished:** domain tests or external
  runtime evidence prove the specified mechanism; the consuming app seam is open.
- **U — unproved:** evidence does not establish the promised operation. An
  unimplemented ordinary app feature is not evidence of impossibility.
- **X — unsupported in the tested route:** a measured refusal or omission;
  other routes remain possible.
- **D — Producer-deferred:** a recorded product decision, not an engineering
  assumption or a failed test disguised as acceptance.

Each row must name its scope, evidence, limit and existing or missing owner.
HTML is a source of promises, not runtime proof. A schema is not an operation;
an inbound observation is not outbound placement; a successful disposable
probe is not production compiler/package integration.

## Initial established boundaries

The [#292 runtime report](issue-292-transitions.md) qualifies named native and
Fusion transition subsets on Studio 21.1.1 build 10, macOS Intel. It proves
specific duration/alignment/control/save-reopen/output behavior, including
picture-only preservation of the fixture's narration. It does not qualify all
installed transitions or all controls. The production portable verifier still
rejects OTIO transitions. #88 owns production library integration. Universal
installed discovery is explicitly deferred beyond V1; a verified expandable
library is the adopted scope.

The [2026-10-25 Producer decision](https://github.com/mbelinkie/vera-script-to-timeline/issues/164#issuecomment-6399451899)
requires automatic zoom on every image, customizable in settings, with native
Resolve capabilities first and immutable prior builds preserved. [PR #317](https://github.com/mbelinkie/vera-script-to-timeline/pull/317)
is pending at this snapshot. API declarations for Dynamic Zoom are leads, not
proof of framing, retiming, persistence or edition support. #164 remains the
motion/focus owner; #319 owns the existing missing public-capture-to-timeline
integration. Neither is delivered by this audit.

## Source register and coverage limits

All relative repository links below refer to the pinned baseline unless an
explicit other commit is given. Later issue comments supply decisions, not
retroactive acceptance of an earlier artifact.

| ID | Exact retained authority | Status and limit |
| --- | --- | --- |
| S1 | [#135 handoff](../prototypes/issue-135/handoff.md), `S03 v3 authoring artifact - issue 135 export v2.dc.html`, SHA-256 `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea` | Producer-accepted ordinary-authoring baseline; 22 rows. Browser-local simulation, no service/Resolve integration. |
| S2 | [#140 handoff](../prototypes/issue-140/handoff.md), [connector-lane source](../prototypes/issue-140/S03%20v3%20authoring%20artifact%20-%20issue%20140%20connector%20lanes.dc.html), SHA-256 `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d` | Accepted connector correction; preserve S1/S2, do not reconstruct them. |
| S3 | [shared #137 r6 source](../prototypes/issue-137/Shared%20S03%20Review%20Foundation%20-%20issue%20137%20r6.dc.html), SHA-256 `fe9d0bb63405faa1fba57938e1dbffe8a420b12241b9e6c569b180412895626b`; matching [export r6](../prototypes/issue-137/Shared%20S03%20Review%20Foundation%20-%20issue%20137%20export%20r6.html), SHA-256 `25d82916e9f0427e1423aa502d6a2cd6ebd4fdc3f67588d7f327892c86b831ce` | Advanced working source, not complete acceptance. #125 explicitly starts here rather than reverting to the early #128 pilot. |
| S4 | [#125 current issue](https://github.com/mbelinkie/vera-script-to-timeline/issues/125); [Sorting revision brief at `e2bc379`](https://github.com/mbelinkie/vera-script-to-timeline/blob/e2bc3796289c1c8ea7829db8bd7de3003a016f4f/docs/prototypes/issue-125/sorting-revision-brief.md) and its long-row fixture/unsent prompt, retained in [PR #311](https://github.com/mbelinkie/vera-script-to-timeline/pull/311) | Latest written decisions after r10. Neither Line nor Strip selected; revision request unsent. Actual r10 HTML/export was not retained with this packet; no export was requested. Coverage of that unavailable artifact is incomplete. Audit uses exact retained r6 + written later decisions, not invented r10 controls. |
| S5 | [#58 accepted S05 record](https://github.com/mbelinkie/vera-script-to-timeline/issues/58), accepted 2026-09-13; [#128 successor scope](https://github.com/mbelinkie/vera-script-to-timeline/issues/128) | Historical S05 HTML/evidence paths named in #58 are absent from this main tree. Use its explicit accepted control/lifecycle list. Pilot `987e732` is checkpoint evidence, not accepted complete S05. No later complete accepted successor was located. |
| S6 | [paired literal content specification](../prototypes/issue-128/paired-123-s05-scenario-content-spec.md) and [corpus recommendation](../prototypes/issue-128/paired-123-s05-scenario-corpus-recommendation.md), checkpoint `db16cec`; hashes `f355a8e9ee08326c09a78c929b848ea4c9681e2a86889bc1eac4b5c80016a6c0` / `aa97fddbe25cb0870032c408c26d5634562bab7ed25030eb4c0070841d639344` | [#136](https://github.com/mbelinkie/vera-script-to-timeline/issues/136) is Closed with explicit Producer acceptance; its local handoff's older “not accepted” heading is historical. 17 shared C cases, 10 outbound O cases and CR-O define S05 coverage. Inbound-only I cases are used only for preservation/conflict promises made by S05. |
| S7 | [Product Spec](../Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md) §§6.1–6.14, 8.3–8.5, 9.1–9.6; [#125](https://github.com/mbelinkie/vera-script-to-timeline/issues/125)/[#128](https://github.com/mbelinkie/vera-script-to-timeline/issues/128) later decisions | Later explicit decisions win: new boundaries cut; verified expandable transition library; automatic image zoom. Old static-image/default-transition text on the pinned main is not current direction. #317 records the zoom update. |

#137 has no accepted final #125 derivation input yet. #138/#139 retain their
owners and consuming roles; stale historical blocker comments do not turn a
new feature green. Nothing here restarts those chats, sends a Design prompt,
or reopens #147's historical audit programme.

## Evidence register

| ID | Implementation or accepted proof | What it establishes and does not establish |
| --- | --- | --- |
| E1 | [authoring operations](../../packages/contracts/src/authoring-v2-edits.ts), [validation](../../packages/contracts/src/authoring-v2-validation.ts), [projection](../../packages/contracts/src/authoring-v2-projection.ts), [tests](../../packages/contracts/test/authoring-v2.test.ts) (#172) | Executable pure v2 sequence/anchor operations with optimistic versions and explicit diagnostics. No live collaboration, permission service or durable browser save. |
| E2 | [row operations](../../packages/contracts/src/authoring-v2-rows.ts), [row tests](../../packages/contracts/test/row-edits-v2.test.ts), [actual consumer tests](../../packages/contracts/test/row-edit-consumers-v2.test.ts) (#307, PR #308) | Single/contiguous run/section move, exact gaps, ordered Stash serialization/restore, local Undo, active-Draft exclusion. Comments are opaque preserved payloads. No audible spanning-audio or transition adapter. |
| E2b | [#310 handoff](../plans/issue-310-sorting-stash.md), [Sorting core](../../packages/contracts/src/authoring-v2-sorting.ts), [saved-Stash edits](../../packages/contracts/src/authoring-v2-stash.ts), [tests](../../packages/contracts/test/stash-edits-v2.test.ts), [merged PR #315](https://github.com/mbelinkie/vera-script-to-timeline/pull/315) | Provisional trial accept/discard/return, changed-baseline refusal, saved resume/marks/Undo and edited Stash consumer exclusion. Caller installs returned acceptance as one transaction; no storage service/collaboration. Limits 1,000 successful edits plus Undos/2,000 actions and 5,000,000 JS characters. |
| E3 | [v2 compiler](../../packages/contracts/src/compiler-core-v2.ts), [compiler tests](../../packages/contracts/test/compiler-v2.test.ts), [prompter exporter](../../packages/contracts/src/prompter-export.ts) (#173/#37) | Deterministic timed supported placements/coverage/diagnostics and spoken-only export; not every source-acquisition or motion intent. Active row-audio intent and non-cut row-transition intent explicitly refuse. |
| E4 | [#131](https://github.com/mbelinkie/vera-script-to-timeline/issues/131), [#141 accepted correction PR #151](https://github.com/mbelinkie/vera-script-to-timeline/pull/151), [#149 runtime discriminator summary](issue-149/workflow-reruns/final-summary.md) | #131 is synthetic/injected representation evidence, no Resolve call. #141 native move/trim used Studio 21.1.0 build 14; separate #149 discriminators used 21.1.1 build 10, not a blanket rerun. Bounded observation/refusal evidence is not finishing preservation or outbound creation. Mapping-mute readback did not prove rendered silence; lock tests did not prove all setters protected. |
| E5 | [#145 plan](../plans/issue-145-generated-roundtrip.md), [accepted merged PR #274](https://github.com/mbelinkie/vera-script-to-timeline/pull/274), [v2 revision core](../../packages/contracts/src/issue-192-v2-revision-core.ts) and [tests](../../packages/contracts/test/issue-202-v2-revision-core.test.ts) | Accepted A visual boundary, B supported linked AV trim/reflow, C verified phrase omission + whole-row fresh speech/timing/rebuild, D unsafe refusal/rejection. Actual Studio/23.976 route; accessible public acceptance summary does not pin the Resolve build, so do not inherit another proof’s version. No new provider calls here. Not a generic row split/merge, arbitrary narration remap, or complete selective-update executor. |
| E6 | [#292 transition report](issue-292-transitions.md) and [bounded helper](../../scripts/issue292_transition_probe.py) | Studio 21.1.1 build 10/macOS Intel: named native/Fusion placement, measured controls, reopen/render/audio results. Seed-based Edge Wipe import and custom enums are exact qualified subsets. No universal catalog or production portable transition adapter. |
| E7 | [v2 package plan](../plans/issue-177-v2-package-studio.md), [package](../../python/vera_timeline_agent/v2_package.py), [native qualification](../../python/vera_timeline_agent/native_qualification_v2.py), [output controller](../../python/vera_timeline_agent/qualification_output_controller_v2.py) | Package/hash/route guards plus accepted subsequent Studio qualification. Qualification and disposable-target authority are not a general app permission, all-edition guarantee or arbitrary timeline clone. |
| E8 | [durable jobs](../../python/vera_timeline_agent/build_jobs.py), [tests](../../tests/test_build_jobs.py) (#35); [#157 real composition](https://github.com/mbelinkie/vera-script-to-timeline/issues/157) remains open | Executable idempotency, leases, interruption/uncertainty, stage retry/cancel and retained artifacts. Test executors do not prove the actual end-to-end app composition or O09 item plan. |
| E9 | [capture service/tests](../../packages/public-page-capture), [graphic provenance compiler](../../packages/contracts/src/graphic-provenance-compiler.ts), [#219 semantic target proof](https://github.com/mbelinkie/vera-script-to-timeline/issues/219) | Component-specific capture authorization/immutability, provenance and one template target. No general capture→script→package→Resolve seam, all graphics, arbitrary OCR focus or source service. |
| E10 | S1/S2 executable display controls and retained interaction evidence | Establishes browser-local presentation only: size, divider, thumbnails, hover/focus, panels and navigation. No duration, saved server state, media transfer or runtime output inferred. |

No tests or runtime probes were re-run for this documentation audit. The
matrix cites accepted delivered tests/evidence and source inspection; it does
not label the existence of a test file as a fresh passing run.

## S03 action-to-evidence matrix

“Owner” below means issue scope, not a new assignment. Pure mechanisms apply
independently of Resolve edition; external claims use the explicit E4–E7
envelope. U means the stated promise has no qualifying evidence; it is not a finding of impossibility. The explicit hold map below distinguishes missing mechanism proofs from existing implementation work. No blanket design clearance follows for unproved controls.

| ID / source control or scenario | User-visible promise and consequential states | Disposition, exact evidence and limits | Owner / missing proof |
| --- | --- | --- | --- |
| A01 · S1/S2 narration, row/section title, + Row/+ Section, delete | Edit continuous text; add/delete row or heading; Undo/Redo; preserve IDs and supported attachments | M E1/E2/E3 for typed sequences and row transactions; E10 local prototype editing. Finished text editor, row split/merge identity and persistent user history are not delivered. | #65/#75; S05 split/merge limited in B09 below |
| A02 · S2 On Camera/VO range | Every spoken token has one camera state; semibold OC plus explicit state; full-frame visual can make VO; transparent overlay preserves OC | M E1/E3 validate typed coverage and explicit placement. Invalid gaps/contradictions/zero lengths refuse; UI integration unfinished. | #66/#67 |
| A03 · S2 range drag/keys/right-click, card↔word hover/focus | Select actual phrase, move endpoint/visual order, inspect linked content without changing wording; no silent anchor repair | M E1/E3; W E10 only for display correspondence. Ambiguous/removed tokens need explicit decision; #278 proves its accepted omission path, not every rewrite. | #67/#89; #172/#278 delivered subsets |
| A04 · S2 source trim/player/word seek, cut-on-word/media-outpoint | Exact selected source range, preview, Set/Clear out, timing precision; short/missing/ambiguous ranges show remedy | M E3/E5 for supported range/word-boundary and linked trim; E10 player is a simulation. Arbitrary playback service and secondary frame UI unfinished. | #83/#89; #180/#249/#260 delivered limits |
| A05 · S1/S2 source sound No/Quiet/Full and narration conflict | Keep primary clip sound or remove narration explicitly; no accidental double foreground; link picture/audio range | M [#178 measured No/Quiet/Full](../verification/issue-178/STUDIO_QUALIFICATION.md) (`no-02` decoded peak0, `quiet-02` −18.0000064dB) and [#249](../verification/issue-249-source-audio-endpoints.md) exact Full/Quiet endpoint output, Studio21.1.1 build10; #178 report retains incomplete broader cases. No removes the source-audio event, not a mute flag. #141 mapping-mute readback did not prove silence. All mixes/fades/ducking not qualified. | #67/#83/#100; #195 picture-only preparation remains separate |
| A06 · S1 Add audio/library/local audio; M1 word end, M2 duration tail | One cue across rows; source trim/fade/mix intent; duration-only end; local file missing; atomic move/add/remove | U actual audible spanning route; X E3 active `rowAudioSpans` refuses. E2 preserves/transforms bounded intent only, not sound. M2's ~3.9s prototype estimate is not timing evidence. | #100; proposed [#326](https://github.com/mbelinkie/vera-script-to-timeline/issues/326) independent cross-row proof |
| A07 · S4 row/run/section move, exact insertion gap, cancel/keyboard | Preserve order/identities; contiguous selection stops at section boundary; run can move across sections; reject stale/invalid destination | M E2; no frontend drag/drop/collaborative merge. New adjacent boundaries cut; separated old pair kept for review. | #307 delivered; #125/#65 app integration |
| A08 · S4 earlier noncontiguous group language in #125 | Original scope says contiguous/noncontiguous; latest Sorting brief explicitly describes contiguous section-bounded selection | U unresolved breadth, not a proven impossibility. E2 explicitly refuses noncontiguous IDs; #310 does not extend it. Do not label the later contiguous trial as proof of noncontiguous moves or silently add that older interaction to r10. | #125 must reconcile its control inventory before construction; a separate noncontiguous proof is needed only if retained as an active promise |
| A09 · S4 outline summary/expansion/thumbnails/omission, return to detail | Long-copy summary preserves mixed OC/VO, endpoint visuals including X→Y→X, missing endpoints and overlay distinction; click expands real S03 read-only | M typed content + E10 presentation mechanics; exact r10 reuse/compact fit is unverified without its retained export. Neither density selected. Orange omission is not an authored cut. | #125; fixture and exact renderer comparison, no runtime campaign |
| A10 · S4 Show Stash, bundle preview, restore, Undo | Saved rows excluded from Draft consumers; ordered bundle restored at explicit gap; preview does not restore; full content retained | M E2 actual serialization/compiler/prompter/media-needs tests. Cross-boundary opaque references/audio refuse when unsupported. Broader Ideas/Extras not implied. | #307 delivered; #78 broader workflow |
| A11 · S4 trial Accept/Discard/Return, net Moved marks, normal Edit Stash | Canonical script AND saved Stash unchanged until accept; read-only during trial; resume with baseline guard; normal saved-content edits survive restore | M E2b delivered on final main via PR #315; original launch baseline lacked it. Canonical acceptance is caller-installed once; repeated/stale acceptance refuses. Local serialize/resume has explicit action/size limits and no multi-client merge/storage service. #125 still owns renderer and interaction integration. | #310 delivered; #125 retains other holds |
| A12 · #125 text/card/block/between-block comments | Reply/mention/resolve/reopen, attribution, empty/error/long threads; edits/moves/deletion make ambiguous anchor stale with explicit reattach; no narration leakage | U service and anchor lifecycle. E2 only preserves opaque comment data. Capture membership tests do not prove authoring roles/comments. | #74/#72/#73; [#324](https://github.com/mbelinkie/vera-script-to-timeline/issues/324) bounded pre-design comment proof |
| A13 · S7 authoring roles, revoked access, preview/release | Producer/Editor/Viewer controls; next-request revocation; approved checkpoint for release; Research access rechecked separately | U authoring service. Existing capture revocation tests prove capture scope only; no cross-project inherited permission. A disabled prototype button is not authorization. | #72/#76; #72/#76 must supply their own service evidence; [#324](https://github.com/mbelinkie/vera-script-to-timeline/issues/324) does not clear roles |
| A14 · S2 Saved, history, checkpoints, offline/sync failed | Immediate typing, honest local/sync states; build freezes acknowledged revision; restore creates new head | W E10 says “Saved in this browser” only. U durable authoring sync/history; E1 optimistic versions are not Yjs/live session convergence. | #64/#73/#75/#76; no new generic storage research issue |
| A15 · S2 Check readiness, row state and audio state | Count and focus affected rows; excluded/ready/unresolved/stale/generating/failed/built; speech missing/locked/replaced; retry only affected material | M E3 diagnostics and narration cache/timing components; U integrated app state. Preview placeholders honest; Release must not claim unresolved media complete. | #64/#67/#70/#157/#158 |
| A16 · S2 Locate file / mismatch Use anyway / Choose another | Preserve title/range/provenance when bytes missing locally; relink exact artifact or explicitly record replacement, not silently certify mismatch | M verified file/materialization/hash primitives; U app relink flow. Name/size match or “Use anyway” cannot waive hash/authorization for an immutable prior build. | #81/#82/#85/#87/#67 |
| A17 · S1/S2 +Visual/URL/local/Research entry | Insert reference or placeholder; acquire authorized immutable bytes; pending/denied/offline/stale revision never silently changes selected source | M E9 capture component; U E3/E9 seam. Public web capture is not all websites/cookie access. Local import, direct image, Research remain distinct. | #67/#80–#85/#87; #319 capture integration; no duplicate capture proof |
| A18 · S1 Graphic overlay/full frame, semantic cue | Pin template/version/provenance and explicit target; overlays/foreground have different coverage; missing template/source/focus stays visible | M E9 for provenance and one #219 target; U complete library/template/cue delivery. #169 source→matte materialization unfinished; no arbitrary template approval. | #9/#10/#99/#169/#220; S03 entry only, not whole S17 audit |
| A19 · S2 marker/citation/direction/scratch/Ideas/Extras | Nonspoken material excluded; zero-duration markers; promote/move/duplicate distinct identity; exact export options | M E1/E3/E2 for supported notes, marker/prompter/exclusion. U full Ideas tree/promotion/checkpoint service. Stash does not implement Ideas/Extras. | #68/#69/#77/#78 |
| A20 · S1/S2 Wide/Tight and cutaway returns | Apply pinned framing to continuous presenter source, exact return, unchanged B-roll/dialogue; prior builds immutable | U runtime Wide/Tight delivery. Temporary presenter still and metadata do not prove transform/source continuity. | Existing #118 contract/#119 external proof-and-delivery; no duplicate owner |
| A21 · S1 still/capture motion, S7 automatic image zoom/settings/None | Contain vs explicit crop, normalized focus/start/end, retime on shorter/longer event, preserve frozen transforms | U runtime, E3 still duration is not motion. Dynamic Zoom API declarations prove neither custom framing nor persistence. Native first; custom fallback only after measured gap. | #164 contract; [#325](https://github.com/mbelinkie/vera-script-to-timeline/issues/325) native proof independent of #61; #319 consumes qualified route |
| A22 · #125 Add transition/inspect/bulk-copy | New boundaries cut; explicit qualified type/duration/alignment/settings; disclosed bulk impact; handles fit without narration shift | M E6 for exact qualified subset; X E3 active non-cut row intent and portable package reject. #307 keeps original-pair intent; no adapter magically follows. | #88 production integration; reuse #292, no repeat campaign |
| A23 · #125 unknown/opaque transition, moved/deleted neighbor | Preserve only through proved route or refuse; stale/ambiguous/unobservable/short-handle/gap does not silently substitute | M/X E6 negative cases and E2 review intent. Raw API silently shortens some requests; preflight must refuse. U arbitrary opaque-effect preservation. | #88; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) preservation affects writes; unsupported control stays unavailable |
| A24 · S2 settings: presenter thumbnail/name, text size, thumbnail size incl 0, divider/reset | Display preferences don't alter content/anchors/timing; configured presenter identity remains explicit | W E10 display-only simulation; U durable preference/account binding. Configured identity must reach actual presenter route separately; no framing proof inferred. | #64/#65; #119 for actual framing |
| A25 · S1/S7 prompter, preview/build/update/inbound entry | Spoken-only export, honest OC/VO/missing states; preview vs release, immutable builds; update returns to ordinary S03 | M E3 export/components; U integrated launch/auth/freeze/readiness. Inbound entry opens its owner flow; audit does not clear #138. | #68/#70/#76/#157; S05 matrix below |

## S05 action-to-evidence matrix

S6 is the exact scenario source for C/O identifiers. All multi-edit rows and
linked structural/audio operations are one selectable update, never a count of
decorations. “Skip” leaves a difference outstanding and never edits the script.

| ID / source scenario or control | User-visible promise and consequential states | Disposition, exact evidence and limits | Owner / missing proof |
| --- | --- | --- | --- |
| B01 · S5/S6 SCRIPT↔RESOLVE; C01–C17, CR-O | Show newer script/older Resolve with real neighbors; inspect/scroll/remount without changing selection; truthful selected/skipped/blocked counts; Select safe/Clear; zero disables | W E10-style harness presentation only; U reusable complete outbound selection model. Inbound decision algebra E4/E5 is not the outbound executor. | #128 design/#103 app; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) bounded frozen-selection mechanism |
| B02 · O01 first creation / current | No diff before first link; Create timeline immediate; up-to-date no fictitious update | M E7 creates verified disposable new timeline from package; U app link and current-state service. Existing timeline never overwritten. | #70/#101/#157 |
| B03 · O02 skip carry-over; O03 newer script | Skips remain outstanding in v4; stale source forces refresh without silently altering reviewed selection | M E1/E5 input-hash freshness; U selective carry-over/baseline atomicity. Newer script and changed Resolve are distinct freshness checks. | #102/#104; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) |
| B04 · C01 framing; C14 VO Undefined→OC/ambiguous presenter | Exact Wide/Tight or visibility choice, no invented presenter evidence | U external framing as A20. E4 ambiguous observation blocks; unsupported presenter does not become a safe default selection. | #118/#119/#128 |
| B05 · C02 word deletion + Footage endpoint; C03a earlier Footage end/OC return; C03b later Graphic start; C04 visual-only row added | Fresh narration for accepted text change, dependent timing reflow; missing picture/program audio blocks only required use | M E5 precise accepted A/B/C subset; M E3/E7 supported source audio/duration. C03b/C04 exact S05 placement is U, not established by linked trim. Offline is not deletion evidence. No universal omission/remap or arbitrary AV retime. | #192/#215 delivered subset; #102/#104 integration |
| B06 · C05 atomic three-row deletion; C06 run move; C07 intra-row cut point | Same identities/context at origin and destination, one update; preserve surviving content and order | M E1/E2 pure contiguous row domain and E4 identity observations; U complete outbound structural execution/preservation. | #104; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327)/[#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328); do not infer noncontiguous move support |
| B07 · C08 same-anchor replacement; C09 opaque cutaway/return | Replace exact occurrence; keep underlying/dormant material and return strip; preserve Resolve-only items | M E1/E3 support declared topology, E4 bounded observation; U finished/opaque preservation under outbound rebuild. | #104; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) |
| B08 · C10 transparent graphic; C11 remove overlay with OC sibling; C13 clips trade rows | Correct layer/coverage, independent sibling preserved, source/asset/template identity pinned | M E3/E9 for supported declared placements/provenance; U all template/unknown finishing transfer. Full-frame is not transparent overlay. | #99/#104/#220; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) for finishing |
| B09 · C12 merge two rows; O06 split row | Atomic row identity/anchor/audio impacts; bridging Graphic offline blocks required placement, not unrelated safe work | U general production split/merge executor. E4 structural/identity observations and E1 sequence edits are not complete merge/split delivery. | #102/#104; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) must include one structural atomic unit/refusal; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) preservation |
| B10 · C15a/b/c spanning cue add/remove/move; C16 audio-only duration | One document-wide audio change; source trim/fade/mix/extent exact, duration-only end; Audio offline blocks when needed; zero safe disables | U audible route; X E3 active rowAudioSpans refuses. E2 move intent/alert is not an audio placement. | #100; [#326](https://github.com/mbelinkie/vera-script-to-timeline/issues/326); [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) atomic selection |
| B11 · C17 compatible two-sided changes and bounded/unbounded conflict | Block only facts/ranges invalidating outbound execution; independently safe work can coexist with reviewed/deferred inbound differences | M E4/E5 bounded mapping/freshness; U complete outbound fact-level classification and partial-plan composition. Whole-row blanket conflict is not the adopted rule. | #102/#104; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327)/[#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328); inbound remains #138 |
| B12 · O04 narration rewrite/unique or ambiguous remap; O05 new narrated row | Whole changed row audio, honest stale/locked/recording-needed; explicit placeholder can unblock supported preview; no silent gap compression | M E3/E5 fresh whole-row regeneration/removed-anchor decisions. Arbitrary rewrite/recorded pickup/remap remains limited; placeholder preview is not approved performance. | #153/#157/#95/#104; no new provider campaign |
| B13 · O07 marker remove/rename/move | Zero-duration marker, accurate section context and one semantic change, no invented visual duration | M E3 marker emission, E4 limited readback; U general selective marker executor. | #69/#101/#104; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) |
| B14 · O08 ready/closed/unreachable/unsupported/missing link/Free/unbounded | Gate actual installed capability; Free prepares package/manual import, Studio verified automation; broken link never means delete | M E7 guards and E8 waiting states; U finished companion/app readiness. Studio evidence does not qualify Free scripting; Free final placement is user-confirmed. | #70/#158/#36; no UI automation fallback |
| B15 · O09 frozen submission | Document-order execution stops first failure; verified/attempted-not-verified/unattempted/blocked remain distinct; original v3 stays current | M E8 stage mechanics; U item-level frozen selection/executor and final-baseline transaction. Never claim whole plan success after a partial run. | #104/#157; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) |
| B16 · O09 Retry | Same frozen v4 attempt, same target and last verified artifact; no duplicated C09 or silently recomputed selection; advance only all selected verified | M E8 idempotency/retry and E7 guarded target components; U composed O09 semantics. | #104/#157; [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) |
| B17 · O09 post-success preservation, Resolve-only dormant alternatives/live readout | Verify same identities/bounds in new timeline only after success; preserve current target and unknown settings or refuse affected write | U arbitrary finishing preservation. E4 observes a subset; E5 fresh rebuild isn't copying arbitrary effects/grades/Fusion/settings. | #104 already names gap; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) independent runtime proof |
| B18 · O10 Format/Resolution/Quality/Destination/Filename, Last used/Saved preset | Validate real supported preset and exact output; complete or continuous section range, no fictitious noncontiguous render | M bounded qualification render/output/retry E7; U full app preset/range/control combination. Saving settings is separate from rendering them. | #71 integration; [#329](https://github.com/mbelinkie/vera-script-to-timeline/issues/329) independent native range/preset proof |
| B19 · O10 preparing/duplicate/apply/verify/render/verify, waiting/resume | Durable stages, no repeat completed timeline work; render-only retry; cancel retains verified timeline; partial artifact never completed | M E8 and [#248 retry](../verification/issue-248/RENDER_RETRY.md) on Studio 21.1.1 build 10; #302 proves guarded build/reopen beyond call window, not render. U general product composition; stage-boundary cancellation is not active-render cancellation. Resolve closing/sleep/license mismatch needs resumable needs-action. | #71/#157/#158; [#329](https://github.com/mbelinkie/vera-script-to-timeline/issues/329) reuses #248, no new job engine |
| B20 · #128 qualified transition update and explicit bulk impact | Preview/selection/frozen plan agree on effect/settings/handles/picture-only intent; preserve unknown only if proved | M/X E6/E3 exact same A22/A23 limits; U production selected-transition adapter and preservation. Free transition import is not certified. | #88/#104; [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327)/[#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) only relevant general mechanisms, no duplicate #292 |

## Design-impact brief

Safe to carry forward now: accepted renderer/connector grammar, exact
display-only controls, tested v2 anchor/coverage semantics, contiguous
row/section/Stash/Undo mechanisms, qualified cut/source-audio/round-trip
subsets, and the **measured** expandable transition-library controls. Design
may represent their actual supported/refused states while application wiring
remains unfinished. A full frontend is not required for those mechanisms.

The provisional Sorting and normal saved-Stash mechanisms are now proved by
merged #310 within E2b limits; exact renderer/UI integration remains #125.
Pause comment anchor-state promises until their bounded transform proof;
for audible spanning cues, exact image motion, complete frozen selective
execution and Resolve-only finishing preservation until the specific evidence
below. Existing #119 owns Wide/Tight proof. #71 owns render integration and
[#329](https://github.com/mbelinkie/vera-script-to-timeline/issues/329) its missing range/preset proof; a qualification render does not prove every O10 setting.
Generic app persistence/collaboration/build composition remain explicitly U
with their existing implementation owners; this audit does not launch a
platform-wide proof campaign or clear those controls by analogy.

Measured limits requiring product-visible treatment are concrete: short
handles/gaps refuse rather than silently shorten a transition; unknown
effects/settings are unavailable or refuse affected writes; missing media never means deletion; partial attempts must keep
v3 current; stale/ambiguous anchors require review. Universal installed
transition discovery is Producer-deferred in #88. Other unknowns are **not**
Producer-approved feature cuts. The product default (zoom on every image) is settled; native suitability is [#325](https://github.com/mbelinkie/vera-script-to-timeline/issues/325)’s question. Numeric motion taste remains a distinct decision. Free manual import/confirmation is the specified route, not measured S05 acceptance in this audit; #36 retains both-edition acceptance.

Three seams must not be collapsed: E2 saved row intent → E3 runtime refusal;
E6 successful direct probe → still-missing #88 production package adapter;
E9 immutable raster → still-missing #319 authoring/compiler/package/readback.
Closing this audit clears none of those seams. #125/#128 consume the report
without becoming backend investigation projects or losing their owners.

## Finite proof handoff

Open **and closed** issue inventory was searched (all 234 returned issues at
launch), then targeted searches covered motion/Dynamic Zoom, comments/anchors,
spanning audio, finishing/preservation and noncontiguous moves. Reuse delivered #310,
#292, #119, #319, #157 and the other owners above. The missing *pre-design*
experiments below are narrower than downstream production issues whose
dependencies currently consume the design. They must not depend on #125,
#128, #61, #62 or their consuming UI implementation. No proof is dispatched.

| Issue | Concrete question and smallest experiment | Positive / negative exit and consumer |
| --- | --- | --- |
| [#324](https://github.com/mbelinkie/vera-script-to-timeline/issues/324) | Can actual authoring comment anchors survive one text edit + whole-row move and save/load, become stale on ambiguous deletion, reattach explicitly, use an injected actor and never enter export/compiler output? Use two public synthetic rows and actual reusable operations, not opaque payload copying. | Focused pure anchor/serialization/exclusion tests with explicit stale/repeated refusal and limits. Roles, live collaboration and durable service stay U with #72/#73/#74; no service proof inferred. A12 comment anchors only. |
| [#325](https://github.com/mbelinkie/vera-script-to-timeline/issues/325) | Can native Resolve Dynamic Zoom express default image zoom and explicit None/settings at two durations, survive shorter/longer occurrence and save/reopen, with requested framing and output? Disposable generated still only; record Studio/Free route separately. | Exact duration/endpoints/ease, off-center focus/start/end and explicit crop-vs-contain or demonstrated native gap; refuse unknown framing. #164 consumes evidence; no custom engine without negative native result. A21. |
| [#326](https://github.com/mbelinkie/vera-script-to-timeline/issues/326) | Can one declared cue across two rows retain source/trim/fade/mix/extent through neighboring duration change, move and reopen, including the approved broken-span rule? Generated tone plus two synthetic rows, actual package/native route and decoded output. | Correct audible extent/settings without narration movement; unsupported crossing/overlap/stash explicitly refuses. #100 production integration; A06/B10. |
| [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) | Can one unchanged finished row and one Resolve-only item survive a neighboring duration change/reorder into a new timeline with identity/bounds, one native effect/grade, one Fusion/custom setting and a #292-qualified boundary transition? Compare original/reopened output; negative unknown setting/transition must refuse affected write. | Qualify exact preserved subset or identify lost/opaque field and refusal boundary, not “all finishing.” #104 integration; A23/B07–B11/B17. |
| [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328) | Can selected/skipped/blocked atomic changes freeze, stop first failure, retry same target/plan without duplicate verified work, and commit baseline only after all selected verify? Minimal real reusable selection/execution core over three changes, one structural/audio unit, injected failure, saved/reloaded attempt and changed-source guard, followed by a minimal cut-only actual native partial-target/retry smoke through the same executor. | Domain tests establish the algebra; actual same-target native failure/retry readback proves no duplicate verified work. Neither proves arbitrary finishing preservation. #104/#157 integrate; B01/B03/B09/B15/B16. |
| [#329](https://github.com/mbelinkie/vera-script-to-timeline/issues/329) | Can the native route render an exact continuous section range using saved/last-used preset plus explicit format/resolution/quality/path/name? Two named synthetic sections, whole timeline and one continuous range; reuse #248 cancel/retry evidence and test only missing range/settings behavior. | Actual settings/readback/output and unsupported combinations, collision and stale preset refusal. #71 integrates; B18/B19. No Drive call. |

Noncontiguous row selection is an older #125 promise, while S4 now expressly
selects contiguous rows. Reconcile retained scope in #125’s inventory first;
do not create a proof ticket for a possibly superseded promise or silently
claim #307 delivers it.

One authorized Opus/high CLI critique completed on 2026-10-25 with read-only tools, restricted MCP/hooks and six compact risk excerpts. Eight findings were triaged once; the PR records dispositions. No review loop or runtime qualification occurred. Local-link and whitespace checks pass; final-head cloud Validate and merge remain delivery gates.


## Exact hold map and issue ownership

| Mechanism/affected controls | Hold / remaining ownership |
| --- | --- |
| Sorting trial/edit saved Stash A11 | #310 Closed/Done at final baseline; E2b domain mechanism clears this specific proof hold only. #125 owns UI. |
| Comment stale/reattach A12 | [#324](https://github.com/mbelinkie/vera-script-to-timeline/issues/324) only; permissions/live session/durable sync A13/A14 remain unproved with #72/#73/#74/#64, not cleared by this experiment. |
| Image motion A21 | [#325](https://github.com/mbelinkie/vera-script-to-timeline/issues/325); #164 consumes technical result, retains contract/taste scope. |
| Audible spanning A06/B10 | [#326](https://github.com/mbelinkie/vera-script-to-timeline/issues/326) extracted from #100; #100 consumes result, owns production music. |
| Finishing/opaque transitions A23/B07–B11/B17/B20 | [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) extracted from #104; #88 still owns qualified transition production adapter. Unsupported effects remain refuse-only until individually proved. |
| O09 actual frozen retry B01/B03/B09/B15/B16 | [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328); ordinary selection/counting alone is not a reason for a runtime campaign, actual partial-target continuation is. #104/#157 integrate. |
| Render range/preset B18/B19 | [#329](https://github.com/mbelinkie/vera-script-to-timeline/issues/329); reuse #248 retry, #71 owns production render/delivery. |
| Wide/Tight A20/B04 | Existing #119 proof-and-delivery, not a duplicate issue. |
| Other U portions in A01–A05/A13–A19/A24/A25/B02/B05/B06/B08/B12–B14 | Existing implementation owners in each row must produce their specified executable/service/adapter evidence. No new generic proof campaign; neither automatic clearance nor permanent design freeze is inferred. Narrow design to already proved mechanisms or retain the affected promise on hold under the capability gate. |

The six new experiments are independent proof slices, not second owners for
production #74/#164/#100/#104/#71. The matching proof requests in #100/#104
are replaced by links to the extracted evidence owners, preserving their
implementation acceptance. Proof failure/partial support must return exact
limits and a fallback or Producer decision; it cannot silently clear a promise.


All six proof issues are Inbox, Sol/high, P1/M. #324 is Contracts and
Compiler/Automated; #325–#329 are Resolve Integration/External. None has an
owner or dispatch. Canonical pre-design dependencies are added only to their
affected #125/#128 consumers. #100/#104 retain implementation and consume the
extracted #326/#327 proof results, so there is one evidence owner per question.
