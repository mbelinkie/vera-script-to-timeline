# Scenario spine, capabilities, and semantic inventory

Use the [manifest](README.md#2-required-and-forbidden-behavior-manifest) for
exact authorities, [content kit](content-kit.md) for aliases, and
[acceptance script](acceptance.md) for ordered actions. All cases are proposed
design representations. They neither execute nor authorize product behavior.

## 1. Tiered scenario spine

Each scenario has one primary job and a bounded set of deltas. Run each at
both viewports; use only the listed role/runtime variants. Do not multiply
every content type by every role, runtime, sync state, and viewport. Cross-cut
absence tests use S07/S11/S19; those tests still cover every invalid action
family listed in the capability table.

### Tier 1 — Pass 1 core writer journey

Start with the Phase 2 single writer, browser authoring, no local agent. This
is one user in a collaboration-ready model, not a claim that Phase 3 roles,
comments or multi-user services have shipped.

| Scenario | Job and fixed content | Bounded states / observable invariant | Phase ownership | Manifest |
| --- | --- | --- | --- | --- |
| S01 | Enter F01, open F02, return after reload | Authorized project chooser → script; empty E14 → populated document. Acknowledged text survives simulated reload; browser writing has no install prerequisite. | 2.1 | R01 |
| S02 | Write naturally in F04; section/direction/note/blank F02/F05/F32/F35 | Typing, undo/redo, OC→VO→OC inside one paragraph. No formatting-driven role change or new paragraph at a cut. | 2.2–2.3 | R01–R04, D24-01 |
| S03 | Attach two Pictures to exact ranges of F04 | Uncovered VO → placeholder/full-frame coverage; overlay-only stays uncovered. Range↔card keyboard/pointer link, incomplete/conflicting timing, honest precision. | 2.3–2.4; F three-point timing, 5.5 secondary | R02–R04, D24-01, D24-03 |
| S04 | Read/export spoken text with F05/F06/F28/F34 boundaries | OC/VO markers, optional section label, typed non-spoken cues, excluded direction/citation/marker; missing camera state blocks export; lost marker becomes unplaced. | 2.5–2.6; F typed annotations | R05–R06, D24-09, D24-14 |
| S05 | Understand Preview and local-work boundary using E02/E04/E05/E13 | Local changes → sync → Preview A; agent unavailable explanation; Free/Studio action terminology; browser closes/reopens to same durable job. Later Release ownership is visibly Phase 3. | 2.7–2.8; 3.5 source/release delta | R07–R10 |
| S06 | Switch to Research and return using E06 | New tab, source remains; one/many/none authorized links; unauthorized/stale/archived fallback. No product/project switch confusion or cross-product grant. | 2.1 shell; 3.1 membership; 4.1 Research access | R14–R15 |

### Tier 2 — Pass 2 role, review, and runtime boundaries

| Scenario | Job and fixed content | Bounded states / observable invariant | Phase ownership | Manifest |
| --- | --- | --- | --- | --- |
| S07 | Viewer reviews full F01 Draft, F30/F31, F33, E03/E04 | Read document/history/comments/results/status; editing, comment mutation, export/build submission/settings absent. Editor→Viewer revocation ends writes; no membership yields nonrevealing denial. | 3.1; read views of 3.3–3.7 | R01, R11, R15, D24-10 |
| S08 | Editor collaborates and discusses F03/F33/F34 | Presence, five sync states, per-user undo, reconnect conflict; comment reply/mention/resolve/reopen/stale reattach; no output effect; annotations remain separate. | 3.2–3.3; F annotations | R07, R11–R13, D24-10, D24-14 |
| S09 | Editor names E03; Producer approves/releases; later restores | Compare five identities; unapproved Release rejected with no build; successful approved Release remains fixed after editing; restore makes new live head preserving history. | 3.4–3.5 | R08, R11, R13 |
| S10 | Editor plans in F30 and parks/restores F31 | Ideas-only document valid; nesting/incorporation/backlink; atomic move vs explicit duplicate; one parked identity under section/global Extras; stale restoration requires review. | 3.6–3.7; F section-linked presentation | R12–R13, D24-04 |
| S11 | Producer/Editor inspect Free/Studio delivery and failures | E05 runtime rows; queued/waiting/failed/success; package ready ≠ imported verification; closed Resolve/edition mismatch; render/upload retry preserves verified artifacts. | 2.7–2.8; 3.5 role overlay | R09–R11, R15 |

### Tier 3 — Pass 2 content breadth without new implementation scope

These examples are required by A13/A24. Each identifies its later phase or
future contract boundary so #14 remains a design task.

| Scenario | Job and fixed content | Bounded states / observable invariant | Phase ownership | Manifest |
| --- | --- | --- | --- | --- |
| S12 | Editor searches and uses F19 twice; E06 access variations | Search/Topic filter, empty/error, insert exact range; refine one occurrence, reset, reject outside bounds; update/keep/compare; byte-verified media plan/remediation; revoked Research access hides restricted results. | 4.1–4.5; 3.1 auth | R04, R14, R18–R19, D24-09 |
| S13 | Classify/attach F06/F25/F26/F27/F28/F35 | Hierarchical roles, right-only known/unplaced, no invented anchor; start+end/start+duration/duration+end and contradictory all-three E12; Release blocked; attach, park, dismiss explicit. | 2.4, 2.6; F taxonomy/Unplaced/timing; 4/5/9 subtypes | R03, R06, D24-01–D24-03, D24-09 |
| S14 | Producer compares F07/F08/F09/F23 and reviews F24 | Sequence all; Option zero/one; Producer Choose in Resolve override; Comparison alternates; one active narration variant; pending/accepted/rejected cut and nonsemantic formatting. | 3/F variants/review; 4/F collections | D24-04–D24-06 |
| S15 | Editor resolves F14/F15/F16/F27 and configures F11/F13 | Image vs Capture; local import failure/effective-copy warning, linked acquisition; Now/On build selection; safe warning vs denial, protected revisions; Periodic conceptual-only under P27-01. Producer-only release acknowledgment delta. | 5.1–5.3 + F/A27 | R04, R19–R22, D24-08, D24-11–D24-13 |
| S16 | Editor uses F20 composite, F12 Spotlight, F14 focus; E07/E09/E10 | One-action composite, refresh/selection race, immutable clip/page; OCR/manual target, matte confirmation, stale/remap; center/point/Spotlight focus, start/end crop/clamp/segments/conflict; honest simulated output. | 5/F compound media, Spotlight, motion | R21, D24-13, D24-16–D24-19 |
| S17 | Editor inspects F17/F18/F21/F22 with E11 | Semantic inputs/citation/derivation/template; two sequential bars and one row cue; transition/reset/disjoint overlap/conflict/target missing; pinned update and declared Studio/Free fallback; missing music bytes. | 9.1–9.4 + F provenance/cues | R24, D24-07, D24-18 |
| S18 | Editor configures transition intent around F07 | Three independent defaults, Apply to everything then one override; handle error and explicit hard cut; anchors unchanged. Secondary timing only from verified simulated timing evidence. | 5.4–5.5 | R23 |
| S19 | Inspect semantic component/state breadth and suite conformance | Inventory below, symbolic tokens, modal and nonmodal focus, labels/search/Topics, role/runtime absence; both widths and reduced motion. No token values or component anatomy chosen. | Each family retains owning slice above | R15–R17, D24-15 |

### K24 required-view coverage crosswalk

This is the complete K24 §7 list, not a representative subset of its required
views. Each maps to a test even where several share one scene.

| K24 view | Dossier scenario |
| --- | --- |
| 1 Coverage overview | S02, S03, S13 |
| 2 Classify right-lane item | S13 |
| 3 Attach Unplaced item | S13 |
| 4 Choose collection behavior | S14 |
| 5 Choose narration variant | S14 |
| 6 Review proposed cut | S14 |
| 7 Inspect derived graphic provenance | S17 |
| 8 Cue infographic emphasis | S17 |
| 9 Resolve local reference | S15 |
| 10 Acquire image and configure capture | S15, S16 |
| 11 Review section-linked Extras | S10 |
| 12 Comment and prompter review | S04, S08 |
| 13 Present Clip on YouTube page | S16 |
| 14 Spotlight critical webpage text | S16 |

## 2. Role and capability matrix

Authorities: R08–R11, R14, R18–R22. For Phase 3, permission is the intersection
of role, authoring membership, independently verified Research access, and
runtime capability. A valid existing job may report waiting/needs-action;
that does not make a runtime-invalid execution control available. Contextual
explanations remain readable even when the action itself is absent.

| Action family | Viewer | Editor | Producer | Runtime / scope condition |
| --- | --- | --- | --- | --- |
| Read authorized Draft/Ideas/Extras/history/comments/results | Yes | Yes | Yes | Web; no workstation required. |
| Edit text/cards, ranges, promote/park/restore, per-user undo | Absent | Yes | Yes | Web, authorized active membership. |
| Add/reply/mention/resolve/reopen/reattach comments | Absent | Yes | Yes | Phase 3 only; Viewer may read existing threads. |
| Name/compare checkpoints; restore as new head | Read/compare only | Yes | Yes | Web; restore is a mutation, never destructive rewind. |
| Approve checkpoint; change members/settings/Research links/release destination | Absent | Absent | Yes | Product authorizes independently; no Research privilege implied. |
| Create Preview | Absent | Yes | Yes | Acknowledged source required; local execution needs agent. |
| Create Release | Absent | Absent | Yes | Approved checkpoint plus valid execution capability; rejection creates no build. |
| Prompter export | No new export action asserted | Yes | Yes | Phase 2 function carried into authorized writing role; missing camera state blocks. Viewer can read available results; no extra Viewer export permission inferred. |
| Read/search/insert/refine Research clip | Read only if separately authorized | Yes if separately authorized | Yes if separately authorized | Independent Research check on every read/artifact request; insert/refine are Script edits. |
| Configure Capture / Now / select ready revision / confirm selection / user pin | Absent | Yes | Yes | Local worker executes capture; Web authoring may express intent. |
| Request On build / acknowledge warning | Absent | Preview only | Preview or Release | Editor acknowledges preview; Producer explicitly accepts warning for release. |
| Configure/execute Periodic or prune | Absent | Absent | Absent | Production deferred; Producer authority is reserved only. Concept/history explanation is allowed. |
| Submit local media/voice/package work | Absent | Preview-authorized work | Authorized work | Agent required; never browser processing or hidden source-file access. |
| Execute Resolve timeline build/render/upload | Absent | Authorized Preview only | Authorized Preview/Release | Connected supported Studio; project delivery settings already authorized. Sharing never implicit. |
| Import/verify Free timeline in Resolve | No product execution control | Manual user step | Manual user step | Package preparation needs agent, not Resolve; app never claims automated import inspection. |

Detailed Propose cut and future model-action permission rules remain O07.
S14 uses Producer to prove content semantics without inventing Editor/Viewer
permissions. Phase 2's single implicit user is not a fourth role.

| Runtime condition | Available semantic experience | Invalid controls absent; valid waiting/result state |
| --- | --- | --- |
| Browser only; no local agent | Open/read/write authorized content, mark ranges, comments/history per phase, inspect status | No local execution, capture run, filesystem/voice processing, Resolve build/render/upload. Readable workstation-needed explanation and authorized setup guidance. |
| Previously paired agent disconnected/offline | Continue Web authoring; inspect durable queued job | Local execution absent while disconnected; existing job reports waiting and resumes at verified stage. |
| Agent connected, Free profile | Prepare Resolve timeline / Update import package for authorized build class | No external scripting/render/upload controls; ready_to_import plus manual checklist, then user confirmation. |
| Agent connected, supported Studio running with scripting | Build in Resolve / Update video; requested timeline/review/upload stages | Authorized role still required. Target busy = serialized waiting, never simultaneous application. |
| Studio selected but Resolve closed, scripting off, unsupported installation or license mismatch | Retain package and diagnostics, offer valid remediation/Free completion | Studio-only execution absent; job needs action. Browser identity never overrides detected facts. |
| Local media unavailable or verification failed | Intent/transcript/status retained, focused verified relink/re-export remediation | No ready claim or substituted asset. |
| Destination product unavailable/unauthorized/stale | Normal destination entry or nonrevealing access explanation | No leaked project listing, silent link, cross-grant or desktop cross-launch. |

Release remains absent for Editor even with Studio connected. Writer controls
remain available to authorized browser writers without an agent. Compare those
two orthogonal cases explicitly; do not collapse both to a generic “disabled.”

## 3. Semantic IA inventory

This is a map of meaning and access, not menu placement, page hierarchy,
layout, or a mandate that each row becomes a screen.

| Entity/surface | Information and relationships | Actions/state; scenario | Authority |
| --- | --- | --- | --- |
| Product/project context | Current product, authorized authoring project, separate linked Research context, member identity | Product vs project switch, nonrevealing entry; S01/S06 | R01, R14–R15 |
| Draft document and section navigation | Ordered sections/paragraphs; exact OC/VO and Picture anchors; typed evidence/notes | Edit, select, attach, inspect, validate; S02–S04/S13 | R02–R06 |
| Ideas | Nested planning items, open/incorporated, backlinks to promoted Draft IDs | Add sibling/child, reorder/indent/collapse/promote; S10 | R12 |
| Extras | Stored fragments, source section/revision/provenance, stale references | Move/restore/duplicate, one identity in both views; S10 | R12, D24-04 |
| Discussion/presence | Thread anchors, stable mentions, replies, resolve history; ephemeral presence separately | Read or role-valid mutation, stale repair; S07/S08 | R11–R13, D24-10 |
| History/checkpoints | Attributed operations, named immutable checkpoint, approved label | Compare, restore as new head, Producer approval; S09 | R08, R13 |
| Clip discovery/use | Authorized results, Topic/tag filter, excerpt, logged/use bounds, immutable media evidence | Search/clear/refine/reset/update/verify; S12 | R18–R19 |
| Picture/audio/evidence properties | Hierarchical role, exact placement, source audio, framing, provenance; future capture/template relationships | Role-valid inspectors and repair; S13–S18 | R04, R20–R24, D24-02–D24-19 |
| Validation/readiness | Active-Draft errors, stable issue-to-content link, nonblocking excluded content | Navigate to cause, repair, retry; S03/S05/S13–S19 | R02–R10, R17 |
| Build/delivery | Frozen source + dependencies, class, profile, media plan, stages, output/report/manual items | Preview/Release under rules, resume, inspect prior immutable result; S05/S09/S11 | R07–R10 |
| Membership/settings/account | Authorized context and runtime/project settings | Producer-only settings/link actions; no auth implementation; S06/S07/S11 | R11, R14–R15 |

Ideas, Extras, section headings, and Research Topics are not interchangeable
categories. Search grammar is shared; this dossier promises Research clip
search only, not a new global script-search index (A13 §4.2).

## 4. Component and state inventory

Component names describe semantic responsibilities only. Composition,
primitive anatomy, colors, placement, dimensions and token values remain O04.
Every listed state needs readable text, non-color distinction, accessible
name/state, and a relevant permitted action or explanation. Families inherit
A13 §§4.2–4.3; product semantics inherit the manifest rows below.

| Family | Required states / evidence | Remediation or interaction | Scenario / authority |
| --- | --- | --- | --- |
| Context, account, product/project selector | Current product/project; authorized results, empty, denied, unavailable | Open authorized destination/new tab; normal home fallback | S01/S06; R14–R17 |
| Writing field, range control, section/card inspector | Empty, populated, editable/read-only, selected, focus, error; hover/focus exact-range pairing | Edit/undo; select range; return between card and words | S02/S03/S07; R01–R04 |
| Primitive controls | Buttons/icon buttons/links; field/textarea/select/combobox; checkbox/radio/tabs/segmented/menu/tooltip | Name/role/value, pointer/keyboard, selected/expanded/focus, loading/valid-unavailable; role-invalid absent | S19; R17 |
| Modal/nonmodal feedback | Dialog/confirmation, popover, banner/inline notice/toast/help | Named modal, focus entry/containment/Escape policy/return; announcement without stolen focus | S19; R17 |
| Data/selection containers | List/table/card/metadata, inspector, pagination/virtualization, contextual/bulk actions, compact sort where relevant | Reading/selection order and overflow preserve content; authorized actions only, no new bulk permission | S12/S19; R17–R19 |
| Sync/presence | local changes, syncing, synced, offline, sync failed; connected/disconnected collaborator | Acknowledgment/wait/reconnect; per-user undo | S05/S08; R07, R13 |
| Narration audio | missing, queued, generating, ready, stale, locked, failed; replaced by host recording is a later-phase label only | Role/runtime-valid preview/regenerate one block; no shoot workflow | S05/S19; R04, R09 |
| Readiness/validation | excluded, ready, unresolved, generating, built, failed, needs classification, unplaced, incomplete timing, timing conflict | Open exact cause/classify/attach/repair; no invented defaults | S03/S13/S19; R02–R06, D24-03 |
| Comments/identity/receipts | Open/reply/mention, resolved/reopened, stale anchor, attribution, presence, new/unread | Explicit reattach, no text insertion; no invented notification policy | S08/S19; R11–R13, D24-10 |
| Search/Topics | Empty query, results/count, filter, clear, no results, loading, retryable error, access loss, overflow | Labeled search and Topic filter; retain distinct taxonomy | S12/S19; R17–R18 |
| Variants/candidates/cut review | Active/inactive, option selection required, Choose in Resolve, comparison, proposed cut, accepted/parked/rejected | Explicit selection, Producer policy, keep inactive content | S14; D24-04–D24-06 |
| Assets and capture | acquiring/verifying/ready/failed, Reference not durable, stale reference, capture due, review_required, denied, retention-protected | Authorized import/relink/replace/retry/use decision; conceptual Periodic explanation | S15; R19–R22, D24-08, D24-11–D24-13 |
| Spotlight/composite/motion | spotlight proposed/confirmed/stale, page refresh available, composite generating, motion focus needs review/clamped, motion-segment conflict | Keep prior/accept remap/redraw, preview start/end, resolve conflict | S16; D24-16–D24-19 |
| Graphic/music | ready/unresolved/render failure, graphic target missing, graphic cue conflict, template update available, invalid semantic input, missing audio | Pin/compare/migrate explicitly; repair target/timing; declared fallback | S17; R24, D24-07, D24-18 |
| Build and delivery | queued, stage progress, waiting/needs action, cancelled, retryable/terminal failure, skipped, success, ready_to_import/import_confirmed; upload failed with local MP4 ready | Resume/retry verified stage, manual checklist, non-release/source identity | S05/S11/S19; R07–R10 |

Numeric responsive tokens and the exact instantiation of generic controls
are not inputs here. In #14, record which primitive represents each semantic
action and attach the acceptance evidence; never add a product capability
merely to fill a component sheet.
