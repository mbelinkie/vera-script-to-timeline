# Script-to-Timeline semantic input dossier

Issue [#26](https://github.com/mbelinkie/vera-script-to-timeline/issues/26)
• Prepared for Producer review • Baseline `163ecfa`

This dossier supplies the semantic input for #14. It is documentation, not a
prototype, a new contract, an implementation plan for later phases, or evidence
that an application behavior already works. Producer acceptance is pending.

Read [the manifest](#2-required-and-forbidden-behavior-manifest), then the
[scenario spine](scenario-spine.md), [fictional content kit](content-kit.md),
and [acceptance script](acceptance.md). The short
[Pass 1 / Pass 2 packets](claude-packets.md) are for a later authorized Claude
task. The packets inherit this entire dossier; they cannot narrow its rules.

## 1. Pinned authorities and precedence

| Key | Exact source | Authority and use |
| --- | --- | --- |
| S | [Product specification at baseline 163ecfa][S] | Rev2 behavior and phase/slice ownership; especially §§4, 6, 7, 8.1–8.2, 8.4–8.5, 9, 10, 11, 13, 14. |
| A13 | [Suite design contract at accepted a23459d][A13] | Artifact structure, shared language, capabilities, switching, and later design evidence. [Producer acceptance][accept13]. |
| A24 | [Coverage audit at accepted e72aa24][A24] | D24-01 through D24-19, invariant §7, exact #13 handoff §8. [Producer acceptance][accept24]. |
| K24 | [Fictional prototype brief at accepted e72aa24][K24] | Sole story-content source, required interactions §6, views §7, coverage checklist §8. No private source is an input. |
| A27 | [Capture contract at accepted 9143518][A27] | Accepted capture trust/selection boundaries and P27-01 production Periodic deferral. [Producer acceptance][accept27]. |
| I26 | [Issue #26][I26] | Live scope and acceptance authority; manifest, scenarios, kit, inventory, tests, decisions, packets. |
| I14 | [Issue #14][I14] | Downstream consumer; Phase 2/3 browser design, intact OC→VO→OC paragraph, Viewer and runtime boundaries. No work performed here. |
| I21 | [Issue #21][I21] | Still open when this dossier was prepared. Producer-approved tokens and wiring handoff remain prerequisites for high-fidelity work. |

Full pins: `163ecfa672fabeaaaae30fe3befa97f17aefe127`,
`a23459dcf1c19600b98ec30c3e4b45f271085b07`,
`e72aa2436fa49d6b256b7cf811d5c1dea39120c3`,
`9143518602fa369c4bb41a00c64bcc99e2b8dd0e`.
The accepted documents retain historical “proposed” headings; their linked
Producer acceptance records establish their accepted versions. Issue bodies
are live scope references, not immutable behavioral pins.

Precedence follows A13 §1: product behavior first, accepted A24 content
language, suite interaction grammar, accepted I21 tokens, then a product's
approved visual artifact. A27 §1 explicitly reconciles capture policy with
A24: `Periodic` remains conceptual; production execution is deferred. No
source here changes frozen `ScriptDocument v1`. A conflict not resolved by
these authorities goes to the Producer before Claude proceeds.

S §6.1 and A13 contain existing visual guidance. This dossier retains their
source authority without transcribing visual literals or choosing hierarchy,
layout, anatomy, placements, or compact composition. Any conflict between
that guidance and future token reconciliation must be recorded for Producer
resolution, never silently settled here.

### Phase envelope

- **Pass 1, Tier 1:** single-writer Phase 2 authoring and its build boundary.
- **Pass 2, Tier 2:** Phase 3 roles, review, collaboration, Ideas/Extras,
  checkpoints, and suite/runtime cases. They are representations, not Phase 2
  promises.
- **Pass 2, Tier 3:** required A24 breadth from Phases 4, 5, 9 and accepted
  future model decisions. These are focused content/state examples, not a
  commitment to implement those phases in #14.
- **Explicitly outside the scenario set:** shoot ingest/conform (6–7),
  subtitle-copy authoring (8), Regeneration Review (10), and S §14 deferred
  workflows except A24's narrow conceptual cases. Their exclusion does not
  cancel their specification. No synthetic host-recording workflow, subtitle
  editor, timeline reconciler, NLE, authentication flow implementation, or
  production capture scheduler is smuggled into a state example.

## 2. Required and forbidden behavior manifest

Each row is a retained requirement. Its exact section/decision, owning phase,
scenario, and decision owner are explicit. `P` = Producer owns semantic
acceptance; `C→P` = Claude may propose presentation in #14, Producer accepts;
`T→P` = #21 token owner proposes, Producer accepts. These design owners confer
no product permission. Scenario IDs link through [the spine](scenario-spine.md).
`F` in a phase means accepted future design requiring its own bounded
contract/implementation work; no delivery date or schema is inferred.

| ID | Required behavior; forbidden shortcut | Exact authority | Phase / slice | Scenarios | Owner |
| --- | --- | --- | --- | --- | --- |
| R01 | Open an authorized project/script, edit headings/prose, undo/redo, reload acknowledged content; never require desktop installation for browser reading/writing. | S §§6.1, 10; §11 slices 2.1–2.2; I14 AC1 | 2 / 2.1–2.2 | S01, S02, S07 | P |
| R02 | Preserve one readable narration paragraph through OC→VO→OC; each spoken token has one state; each VO interval has full-frame coverage or explicit placeholder. An overlay alone cannot cover VO. Never infer state from weight/color or rows. | S §§6.1–6.2; §11 2.3–2.4 | 1 model; 2 / 2.2–2.4 | S02, S03 | P |
| R03 | Exact semantic range/card links work in both directions; show honest word/cue versus verified frame timing. No shot rows, primary inline cut syntax, or primary miniature timeline. | S §§6.2, 7; §11 2.4, 5.5; A13 §7.4 | 2 / 2.4; 5 / 5.5 secondary | S03, S13 | P |
| R04 | Typing/Insert and typed inspectors retain timing, source audio, fit, provenance, readiness; phase-valid choices only. No silent crop/stretch/retime or invented asset. | S §§6.4, 8.4, 13; §11 2.2, 2.4 | 2 / 2.2, 2.4; later media | S02, S03, S12, S15 | P |
| R05 | Prompter contains active spoken wording/order, initial and changed OC/VO markers, optional non-spoken section labels, frozen revision/sidecar; missing camera state blocks export. | S §6.5; §11 2.5 | 2 / 2.5 | S04 | P |
| R06 | Citation preserves evidence without screen duration; marker is point-only and becomes unplaced on lost anchor. No marker task-management workflow. | S §§6.3, 6.13, 13–14; §11 2.6 | 2 / 2.6 | S04, S13 | P |
| R07 | Save states distinguish local changes/syncing/synced/offline/sync failed; Preview waits or identifies acknowledged source. No claim unsynced text entered a build. | S §§6.8, 6.10, 13; §11 2.7, 3.2, 3.5 | 2 / 2.7; 3 / 3.2, 3.5 | S05, S08 | P |
| R08 | Preview freezes acknowledged live revision; Release requires Producer plus approved checkpoint; later edits/retries never alter frozen input. Keep all five version layers distinct. | S §§6.7, 6.9–6.10, 7, 10.1; §11 3.4–3.5 | 3 / 3.1, 3.4–3.5 | S05, S09 | P |
| R09 | Browser/local-agent/Resolve capability facts are explicit; typed server/runtime capabilities control validity, never user agent. Free prepares verified package, manual import confirmation; Studio needs supported running installation/scripting and serialized target. No browser Resolve or Free UI automation. | S §§9.1, 9.3–9.6, 10, 13; A13 §§3.3, 7.4 | 2 / 2.7; 3 / 3.5 | S05, S11 | P |
| R10 | Durable staged jobs survive browser closure; unrequested stages are skipped; retry last verified stage. Preserve timeline after render failure and MP4 after upload failure. Sharing is an explicit separate choice. Updates create new timelines before Phase 10. | S §§9.3–9.6, 13–14; §11 2.7–2.8 | 2 / 2.7–2.8 | S05, S11 | P |
| R11 | Viewer reads document/history/comments/results and changes nothing; Editor edits/comments/checkpoints/Preview; Producer adds settings/membership/links/approval/Release. Revocation takes effect on next request and ends write sessions promptly. No Reviewer role or formal review-state workflow. | S §§6.7–6.10, 14; §11 3.1–3.5 | 3 / 3.1–3.5 | S07, S08, S09 | P |
| R12 | Draft/Ideas/Extras share one atomic live head/checkpoint; only Draft is build eligible. Ideas are an outliner distinct from section navigation/Topics; promotion retains backlink, moves retain identity, duplicates create new identity. Ordinary delete is not automatic parking. | S §4 principle 6; §§6.6, 6.8–6.9, 7; §11 3.6–3.7 | 3 / 3.2, 3.4, 3.6–3.7 | S08, S10 | P |
| R13 | Presence is ephemeral; per-user undo preserves others' work; reconnect merges accepted work and surfaces semantic conflicts. History is attributed; checkpoint restore creates new head, never rewinds history. | S §§6.8–6.9; §11 3.2, 3.4 | 3 / 3.2, 3.4 | S08, S09 | P |
| R14 | Suite products open reciprocally in new tabs; only source-product ID, opaque project hint and bounded intent may transfer. Destination rechecks session, membership, linked Research access. No automatic linking, project leakage, text, secrets, locators, or permission claims. | A13 §§5.1–5.4 | 2 shell / 2.1; 3 / 3.1; 4 / 4.1 | S06, S12 | P |
| R15 | One suite project, separate product artifacts and contract-only reference; runtime variants stay within products. Shared grammar never copies Research IA, shares data/auth/deployment, or invents Desktop authoring app. | A13 §§3–6, 7.1–7.3 | Cross-product design | S06, S07, S11, S19 | P; C→P presentation |
| R16 | Only symbolic token-family references pending accepted #21; shared changes are versioned and separately accepted/adopted. No literals, aliases, consolidation or wiring here. | A13 §§4.2, 6, 7.2, 8.1; I21 | Cross-product design | S19 | T→P |
| R17 | Both 1280×800 and 1024×768, real reflow, pointer/keyboard, names/roles/focus/announcements, non-color cues, dialogs and reduced motion. Invalid role/capability controls absent from DOM, not decorative disabled actions. | A13 §§3.3, 4.2–4.3, 7.4; K24 §§6.9, 7 | Every represented phase | S01–S19 | C→P |
| R18 | Authorized Research search by tag/note/title/transcript, stable clip/version/excerpt, separate occurrence ranges; inward-only refinement and reset; update available offers keep/update/compare. Never change another use or Research evidence. | S §§6.11, 8.1; §11 4.1, 4.4–4.5 | 4 / 4.1, 4.4–4.5 | S12 | P |
| R19 | Preparation reports reused/materialized/exported/relinked/unresolved and estimated disk; availability requires byte verification. Research packages never moved; verified clone/copy or explicit reference. Local move explicit with effective-copy warning on removal failure. | S §§6.4, 8.2, 13; §11 4.2–4.3, 5.1 | 4 / 4.2–4.3; 5 / 5.1 | S12, S15 | P |
| R20 | Capture uses public anonymous, bounded trusted worker; denied targets/failed integrity create no revision; safe warning may create review-required. Keep intent, explain/remediate, never borrow browser cookies. | S §§8.4, 10, 13; A27 §§2.5, 3.2, 4.3, 7.4 | 5 / 5.3 + F | S15 | P |
| R21 | Now candidate is unselected unless explicit conditional capture-and-use succeeds; On build selects only for frozen build; Preview acknowledgment vs Producer release-use decision. Retained reference/evidence/hold protection survives unpin; no policy means retain all. Stored bytes reproducible, remote page not guaranteed. | A27 §§2.5–2.6, 3.2, 7.3, 9–10 | 5 / 5.3 + F | S15, S16 | P |
| R22 | Periodic vocabulary/history can be conceptual examples; no executable schedule, frequency, notification or pruning controls. Producer-only reserved authority and retention dry-run require future work. | A27 §§1, 3.2, 9.3, 11 P27-01; S §14 | 5 / F, production deferred | S15 | P |
| R23 | Transitions have three independent defaults, explicit boundary override, ordered resolution, picture-only default and handle validation; no shift of narration to fit. | S §8.5; §11 5.4 | 5 / 5.4 | S18 | P |
| R24 | Graphics/music use immutable template revisions and occurrence settings; updates explicit; missing bytes/invalid package block Release or declared tested fallback, never latest substitution or invented rights clearance. | S §7 templates; §13; §14; §11 9.1–9.4 | 9 / 9.1–9.4 | S17 | P |

All A24 decisions are retained individually below, not collapsed into a
single “content coverage” promise. K24 supplies the detailed interaction
semantics referenced by each row.

| ID | Required behavior; forbidden shortcut | Exact authority | Phase / slice | Scenarios | Owner |
| --- | --- | --- | --- | --- | --- |
| D24-01 | Rows/asymmetry/blank space carry no edit or duration meaning; intact paragraphs may span multiple cuts. | A24 §5 D24-01; K24 §6.1 | 2 / 2.2–2.4 | S02, S03, S13 | P |
| D24-02 | Hierarchical Picture subtypes and Audio/Citation/Editor note/Draft note/Reference remain distinct; preview classification effects. Composite added by D24-16; Comment remains discussion. | A24 §5 D24-02; K24 §6.2 | 2 / 2.4, 2.6 + 4/5/9/F | S13 | P |
| D24-03 | Any consistent two of start/end/duration; all three must agree. Unplaced items keep evidence and no invented interval; Release blocks until resolved. | A24 §5 D24-03; §7.3–7.5; K24 §6.1 | 2 / 2.4 + F timing | S03, S13 | P |
| D24-04 | Exactly one active narration variant; parked fragment has one identity under section and global Extras, inactive in builds. | A24 §5 D24-04; K24 §§5, 6.3 | 3 / 3.7 + F variants | S10, S14 | P |
| D24-05 | Sequence = all consecutive; Option = zero/one chosen; unresolved Release blocks unless Producer sets Choose in Resolve; Comparison = intentional alternates plus marker. Never first-link auto-selection. | A24 §5 D24-05; K24 §6.3 | 4 / F collections | S14 | P |
| D24-06 | Formatting is nonsemantic; only attributed Propose cut creates strikethrough; pending retains active words, accept parks, reject restores. No general track changes. | A24 §5 D24-06; K24 §6.4 | 3 / F bounded review | S14 | P |
| D24-07 | Graphic input, citation, snapshot, derivation note and template remain traceable together. No screenshot-only data model. | A24 §5 D24-07; K24 §6.5 | 9 / 9.3 + F provenance | S17 | P |
| D24-08 | Locator is not identity; unresolved local reference needs verified import/relink/replace, no paths or silent substitute. | A24 §5 D24-08; K24 §6.5 | 5 / 5.1 | S15 | P |
| D24-09 | Citation/transcript evidence never becomes Picture by proximity. | A24 §5 D24-09; K24 §6.2 | 2 / 2.6; 4 / 4.1 | S04, S12, S13 | P |
| D24-10 | Optional stable-user mentions, replies, resolve/reopen and explicit stale reattach; no narration/duration/prompter/build effect. | A24 §5 D24-10; K24 §6.7 | 3 / 3.3 | S07, S08 | P |
| D24-11 | Upload/linked Image acquire verified managed bytes; linked acquisition automatic; screenshot is Image unless explicit Capture relation retained. | A24 §5 D24-11; K24 §6.6 | 5 / 5.1–5.3 | S15 | P |
| D24-12 | Now/On build/Periodic vocabulary and immutable protected history; apply R21–R22 reconciliation, no numeric retention default or deletion. | A24 §5 D24-12; K24 §6.6; A27 §11 | 5 / 5.3 + F | S15 | P |
| D24-13 | Per-occurrence versioned None/drift/Slow zoom presets; Center default for Slow zoom. No animation inferred for an Image. | A24 §5 D24-13; K24 §6.6 | 5 / F motion | S15, S16 | P |
| D24-14 | Typed pronunciation/pause/pacing/emphasis exact-range annotations default to non-spoken visible prompter cues plus sidecar. Ordinary Direction remains excluded. | A24 §5 D24-14; K24 §6.7 | 2 / 2.5 + F annotations | S04, S08 | P |
| D24-15 | Only fictional content and safe provenance; never private source text/URL/identity or local paths in Claude, documents or screenshots. | A24 §5 D24-15; K24 §2 | Every phase | S01–S19 | P |
| D24-16 | One-action YouTube page composite; separate Clip/page revisions, description/comments, captured count, pinned template and whole-composite motion. Refresh conditionally selects new page revision, never mutates clip/build. | A24 §5 D24-16; K24 §6.8; A27 §7.3 | 5 / F compound media | S16 | P |
| D24-17 | Select OCR words/lines or manual region; confirmed full-resolution inverse matte and exact interval; supervised stale/remap. Source/composite → matte → motion; verified matte/nested sequence baseline, native mask only later proven enhancement. | A24 §5 D24-17; K24 §6.6 | 5 / F Spotlight | S16 | P |
| D24-18 | Pinned template declares human-readable targets, states/bindings; multiple exact cues, explicit start-only end policy, transitions/base reset; disjoint overlap allowed, same-target contradiction blocks Release. Studio keyframes/declared Free fallback are simulated evidence only. | A24 §5 D24-18; K24 §6.5 | 9 / F highlight cues | S17 | P |
| D24-19 | Preset separate from Center/manual source-relative/Spotlight focus; synchronized Zoom to spotlight, actual start/end crop/clamp, ordered segments; conflicting transforms block, updated source prompts review, accepted remap repairs bound focus. Build freezes evidence/transforms. | A24 §5 D24-19; K24 §6.6 | 5 / F focus/segments | S16 | P |

## 3. Open decisions and handoff gates

Resolved semantic decisions above are not reopened as “options.” This register
lists only decisions that remain with their owners. A blocked design gate does
not prevent review and acceptance of this dossier.

| ID | When / owner | Decision still needed | Constraint or safe interim representation |
| --- | --- | --- | --- |
| O01 | Before Claude high-fidelity / Producer | Accept #26 as #14 semantic input, including scenario envelope and exclusions. | This review; no artifact work in #26. |
| O02 | Before Claude high-fidelity / #21 owner → Producer | Approve token reconciliation and bounded wiring handoff; pin accepted version/evidence. | Only symbolic families: `TOKEN.color`, `TOKEN.type`, `TOKEN.spacing`, `TOKEN.radius`, `TOKEN.shadow`, `TOKEN.focus`, `TOKEN.control`, `TOKEN.dialog`, `TOKEN.responsive`. These are dossier placeholders, not new token names. |
| O03 | Before Claude / Producer | Confirm runtime presentation names and bounded #14 pass plan; pin approved Research visual reference and suite contract adoption version required by A13 §8. | Working semantic labels: Web authoring, local agent connected/disconnected, Resolve Free/Studio. No separate Desktop authoring app. This dossier does not revisit the Research artifact. |
| O04 | Claude may propose in #14 / C→P | Visual hierarchy, layout, density, component anatomy, navigation placement, responsive composition, expression of source-owned semantic controls. | Follow pinned authorities and accepted #21; no decision supplied here. |
| O05 | Claude may propose in #14 / C→P | Discoverable keyboard range/card navigation, selection and geometry editing, dialog focus and dismissal details. | Must pass acceptance.md; no undocumented shortcut or pointer-only required action. |
| O06 | Producer acceptance of #14 | Readability, visual fidelity, actual reflow/overflow, accessibility, runtime clarity, complete coverage and justified product exceptions. | Require actual evidence at both viewports; #26 has no visual evidence. |
| O07 | Later contract/implementation owner → Producer | A24 missing model/wire shapes, precise candidate Preview policy, detailed review-action permissions, motion/OCR algorithms and template bindings. | Show accepted meaning and deterministic semantic examples; do not invent wire schemas or extend permissions. In S14 the Producer demonstrates Propose cut/accept/reject; no unapproved permission rule is asserted. Preview must expose unresolved options; their exact output policy remains an explicit pending decision. |
| O08 | Future periodic revival owner → Producer | Trigger evidence, schedule/retention/recovery values, notifications and audited deletion. | A27 P27-01 defers production; conceptual history only, no numeric defaults or executable scheduling. |
| O09 | Later suite integration owner → Producer | Exact safe navigation envelope and authorized destination URL. | A13 §5.2 defines permitted categories; static destination outcomes in #14, no production URL protocol here. |

If #14 cannot represent a required state without settling O07–O09, record the
specific row as blocked for Producer decision; never hide the row or invent
implementation. This dossier's proposed test branch selection (for example,
waiting for sync) exercises a permitted outcome without choosing the final UI.

## 4. Producer handoff and evidence

Follow [acceptance.md §1](acceptance.md#1-producer-review-of-this-dossier).
The acceptance request is for semantic input only. The future UI regression
script has **not** been executed; all screen, DOM, keyboard, reflow, and Resolve
examples remain planned or simulated until their owning task supplies proof.
Automated scope/source/reference checks and the repository validation result
are recorded with the committed review evidence on #26. The issue remains
In review until explicit Producer acceptance; this task never marks it Done.

[S]: https://github.com/mbelinkie/vera-script-to-timeline/blob/163ecfa672fabeaaaae30fe3befa97f17aefe127/docs/Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md
[A13]: https://github.com/mbelinkie/vera-script-to-timeline/blob/a23459dcf1c19600b98ec30c3e4b45f271085b07/docs/vera-suite-design-contract-and-claude-brief.md
[A24]: https://github.com/mbelinkie/vera-script-to-timeline/blob/e72aa2436fa49d6b256b7cf811d5c1dea39120c3/docs/investigations/issue-24-representative-script-coverage.md
[K24]: https://github.com/mbelinkie/vera-script-to-timeline/blob/e72aa2436fa49d6b256b7cf811d5c1dea39120c3/docs/prototypes/issue-24-sanitized-prototype-input-brief.md
[A27]: https://github.com/mbelinkie/vera-script-to-timeline/blob/9143518602fa369c4bb41a00c64bcc99e2b8dd0e/docs/investigations/issue-27-webpage-capture-contract.md
[accept13]: https://github.com/mbelinkie/vera-script-to-timeline/issues/13#issuecomment-5500907936
[accept24]: https://github.com/mbelinkie/vera-script-to-timeline/issues/24#issuecomment-5500767669
[accept27]: https://github.com/mbelinkie/vera-script-to-timeline/issues/27#issuecomment-5502823349
[I26]: https://github.com/mbelinkie/vera-script-to-timeline/issues/26
[I14]: https://github.com/mbelinkie/vera-script-to-timeline/issues/14
[I21]: https://github.com/mbelinkie/vera-script-to-timeline/issues/21
