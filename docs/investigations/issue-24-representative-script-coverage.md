# Representative-script coverage audit

- Issue: [#24 — Audit a representative script against the Script-to-Timeline content model](https://github.com/mbelinkie/vera-script-to-timeline/issues/24)
- Status: proposed for Producer acceptance
- Decision authority: Producer
- Evidence class: private source, sanitized findings
- Scope: content vocabulary, authoring presentation, and issue #13 handoff only

## Outcome in one sentence

The narration-first model is correct, but a faithful authoring experience needs
explicit typed right-column roles, anchors that do not depend on table rows,
first-class alternative and source-candidate selection, conservative formatting
review, and durable provenance/asset-resolution states before the sample can be
represented without loss or invented meaning.

Nothing in this investigation changes a frozen contract. Recommendations are
design decisions proposed for Producer acceptance; accepted missing work must
be filed later as separate bounded issues.

## 1. Evidence method and privacy boundary

The representative production script was inspected read-only through its
native Google Docs structure. The audit enumerated tabs, tables, rows, cell
occupancy, paragraphs, native links, and formatting runs, then classified
semantic families without retaining or quoting source text.

The source itself remains private. This artifact deliberately omits its title,
URL, document identifier, production names, factual claims, distinctive prose,
and source-specific links. All examples below are generalized; the companion
prototype brief is wholly fictional.

### 1.1 Reproducible structural signature

| Dimension | Sanitized count |
| --- | ---: |
| Native document tabs | 1 |
| Two-column tables | 43 |
| Total table rows | 547 |
| Rows with left-column content | 360 |
| Rows with right-column content | 268 |
| Rows with both columns populated | 85 |
| Left-only rows | 275 |
| Right-only rows | 183 |
| Fully empty separator rows | 4 |
| Native hyperlinks | 95 |

All 43 tables have exactly two columns. Only 85 of 547 rows contain content on
both sides. Therefore a row is evidence of the legacy document's visual
layout, not a reliable semantic pair, narration unit, shot, or edit boundary.

### 1.2 Load-bearing finding

Continuous narration and visual/reference material are asymmetrically placed.
The canonical authoring unit must remain an intact `NarrationBlock`; production
events attach through `TextAnchorRange` or an explicit point anchor. Import or
authoring code must never infer a visual duration, cut, or association merely
from a table row or the nearest nonempty left cell.

## 2. Status vocabulary

- **Covered** — the product specification and canonical model already express
  the meaning, including a named later-phase entity where the frozen Phase 1
  schema intentionally has not introduced that feature yet.
- **Design decision required** — the concept can be preserved using existing
  product surfaces, but presentation or supervised-conversion behavior needs
  explicit Producer approval.
- **Intentionally excluded** — the content is preserved for humans when useful
  but must not enter the active narration/build semantics.
- **Missing** — no current concept can preserve the accepted meaning without
  loss, ambiguity, or overloading; a separate accepted follow-up is required.

## 3. Structural coverage map

| Observed structure | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Document-level script identity | §§1, 2, 7 | `ScriptDocument { id, projectId, title, ... }` | One canonical document independent of editor markup or Google Docs tables. | Covered |
| Repeated two-column script tables | §§3, 6.1 | Presentation over typed blocks and cards; tables are not canonical entities | Render a readable two-column grid without spreadsheet chrome; never serialize table identity as edit meaning. | Covered |
| Section and topic breaks | §§3, 6.3, 7 | `SectionBlock` | Heading spans the document and may emit a chapter marker. | Covered |
| Left-side spoken paragraphs | §§2, 6.1–6.3, 7 | `NarrationBlock` with stable tokens | Preserve paragraph wording and flow even when camera or picture changes mid-paragraph. | Covered |
| Paired left/right material | §§6.1–6.2 | `NarrationBlock.visualEvents[]` and later typed cards | Right-side cards align approximately but attach to exact text anchors. | Covered |
| Right-only material with a known narration target | §§6.2, 6.3, 7 | `VisualBlock.event.range` or a point-anchored typed item | Show the item in the right lane with an explicit attachment chip; no synthetic left text or row split. | Covered |
| Right-only material whose target is ambiguous | §§6.2, 6.13, 13 | No general unplaced right-lane container in frozen v1; marker-only `unplaced` is planned | Preserve in an Unplaced queue with source order/proximity evidence and require deliberate attachment, classification, or dismissal. | Missing |
| Left-only narration across several picture changes | §§2, 3, 6.2 | One `NarrationBlock` plus multiple anchored `VisualEvent`s | Allow successive or overlapping cards inside one paragraph; hover/focus cross-highlights card and covered words. | Covered |
| Empty visual cells and blank separator rows | §§3, 4.3 | No canonical entity unless a semantic section/block exists | Treat as layout whitespace, not a placeholder, missing asset, pause, or cut. | Intentionally excluded |
| Long notes/drafts tail and unused research | §§3, 6.6, 7; §4 principle 6 | `NoteDraftBlock`; planned `IdeaItem` and `StoredFragment` surfaces | Classify into Ideas, Extras, or excluded note/draft; never compile by position alone. | Design decision required |
| Material moved out of the current draft | §§6.6, 7; §4 principle 6 | `StoredFragment` in Extras (planned Phase 3); v1 `NoteDraftBlock` for simple excluded text | Preserve readable content, provenance, formatting, and stale typed references; require explicit restore/promotion. | Covered |

## 4. Semantic coverage map

### 4.1 Spoken content and annotations

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Ordinary narration, jokes, quoted setup, and conclusions | §§2, 3, 6.1–6.3, 7 | `NarrationBlock.text` and stable `NarrationToken`s | Edit as normal prose; build and prompter use only active spoken text. | Covered |
| Inline on-camera and voiceover changes | §§2, 3, 6.2, 6.5, 7 | `HostVisibilitySpan { range, state }` | Non-color cue plus restrained styling; spans may start/end mid-paragraph and must cover every spoken token exactly once. | Covered |
| Parenthetical direction and performance notes | §§3, 6.3, 6.5 | `DirectionBlock`; `NarrationBlock.notes[]` for block-level notes | Render muted/non-spoken; allow explicit inclusion policy in performance-beat sidecars; never speak it by default. | Covered |
| Pauses, pacing, emphasis, and delivery instructions inside speech | §§6.5, 8.3 | Voice settings and pronunciation/performance inputs are specified, but frozen v1 has only free-form `notes[]` | Show typed inline annotations or inspector chips distinct from narration and preserve them in the prompter sidecar/synthesis input by policy. | Missing |
| Pronunciation guidance, including phonetic and plain-language forms | §§3, 6.5, 8.3 | Pronunciation dictionary/overrides are specified outside frozen v1 | Show a pronunciation annotation tied to exact text with readable alias/phoneme and preview; never make the note spoken prose. | Missing |
| Questions, reminders, and drafting commentary | §§3, 6.3, 6.6 | `NoteDraftBlock`, `IdeaItem`, `StoredFragment`, or comment thread depending intent | Ask the author to classify as private note, Idea, Extra, comment, or production marker; position alone is insufficient. | Design decision required |

### 4.2 Visual, source, and evidence roles

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Generic clip/B-roll/still request | §§3, 6.2–6.4, 8.4, 13 | `VisualEvent` with `PlaceholderVisualSource` | Preserve request text on an anchored full-frame/overlay card; unresolved status remains visible and may compile to a labeled slate by policy. | Covered |
| Resolved local still or video | §§6.3, 8.2, 8.4 | `VisualEvent` with `LocalMediaVisualSource`; `MediaReference`/`LocalMediaImport` in later phases | Preview framing/audio/range and expose verified import/relink state; paths remain locators, never identity. | Covered |
| Logged research clip | §§6.11, 7, 8.1 | `VisualEvent`, `MediaReference`, and `ClipUsageRange` | Display title/excerpt and occurrence-specific use range while preserving research-owned evidence and immutable bounds. | Covered |
| Source URL with exact in/out or timestamp range | §§3, 6.11, 7, 8.1 | `MediaReference.requestedInOut`, `ClipUsageRange`, and transcript snapshot | Keep link, readable range, precision, and selected frames together; range never floats as an untyped note. | Covered |
| Transcript excerpt or quoted source speech | §§3, 6.11, 8.1 | Immutable transcript snapshot plus occurrence-readable excerpt | Display as evidence on the clip card/inspector; it does not become host narration or a citation by proximity. | Covered |
| Source-audio instruction, including mute/silent footage | §§3, 7, 8.1, 8.4 | `VisualEvent.audioPolicy` and later usage settings | Expose explicit `Mute`/`Use source` state on the visual card; do not infer from link type or formatting. | Covered |
| Direct image or webpage/screen reference | §§6.4, 8.4 | Planned `MediaReference` with URL/capture provenance | Preserve as a reference in authoring; build uses only an authorized immutable artifact or explicit placeholder. | Covered |
| Citation, article, report, or evidence link not intended on screen | §§3, 6.3 | Planned `citation` row/card; no frozen-v1 citation block yet | Use a visibly typed Citation card, preserved in script/build report, with no timeline duration by default. | Covered |
| Production-only instruction or Resolve task | §§6.13, 7, 13 | Planned `ScriptVideoMarker` | Point-anchor to a word, event edge, or between blocks; no duration; unplaced if anchor is lost. | Covered |
| Music, sound file, or audio cue reference | §§6.3, 7 | Planned `MusicCueUse`/template revision; simpler production note before Phase 9 | Type as Music/SFX when it is timeline intent; type as Reference when it is only supporting material. Never treat an arbitrary file mention as approved media. | Covered |
| Right-column role inferred only from prose/position | §§3, 6.1–6.4 | Existing typed entities cover final roles, but no accepted classification workflow binds legacy text to them | Require an explicit role picker: Visual, Citation, Source clip/audio, Graphic, Production marker, Draft note, or Reference. | Design decision required |

### 4.3 Graphics and provenance

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Full-screen text or long-text graphic instruction | §§3, 6.3, 7 | Placeholder `VisualEvent` now; later `GraphicUse` with pinned template revision | Show editable semantic text and intended presentation, not a pasted screenshot as the only source of truth. | Covered |
| Map, chart, comparison, or other derived graphic | §§3, 6.3, 7 | `GraphicUse.semanticInputs` and immutable template revision | Author semantic inputs and preview the graphic while keeping it anchored like any visual. | Covered |
| Data/source provenance for a derived graphic | §§7, 8.4 and §4 principles 8–10 establish provenance, but no explicit graphic-evidence relationship is defined | No accepted canonical relationship from `GraphicUse` to source citations/data snapshot | Require source citations, data snapshot/version, derivation note, and template revision to survive together. | Missing |
| Multiple candidate visual treatments for the same words | §§6.2, 8.4 support one authored event/source at build time | No candidate-set/selection entity in the canonical model | Preserve all candidates under one request, identify one selected candidate, and never compile the first or nearest candidate implicitly. | Missing |

### 4.4 Editorial alternatives, formatting, and asset durability

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Mutually exclusive narration or visual alternatives | §§3, 6.6 preserve unused material, but do not express mutual exclusion | No `VariantGroup`/active-choice concept | Present a first-class variant group with exactly one active choice for Draft/build; keep other choices adjacent and lossless. | Missing |
| Superseded or struck material | §§6.6, 6.9 and §4 principle 6 preserve history/Extras | `StoredFragment`/history after explicit classification; strikethrough itself is not canonical meaning | On supervised conversion, flag as `possible superseded`; require confirmation before moving to Extras or exclusion. | Design decision required |
| Highlight color, foreground color, bold, italic, and underline | §§6.1, 6.6 and §4 principle 1 preserve readable formatting but define no production semantics | Rich-text/editor presentation only; frozen v1 does not serialize arbitrary formatting | Preserve when useful for human review, but never infer OC/VO, readiness, selection, ownership, build eligibility, or timeline action from appearance. | Design decision required |
| “Add somewhere,” placement questions, and unresolved position | §§6.13, 13 and §4 principle 11 require honest incompleteness | Marker-only unplaced state exists; general unplaced content does not | Keep in an Unplaced queue with original order/proximity evidence; explicit reattachment or dismissal only. | Missing |
| Reference to a local path, folder, discussion thread, or unattached sound file | §§8.2, 13 and §4 principles 9 and 12 | `MediaReference`/`LocalMediaImport` only after an authorized verified import; otherwise placeholder/reference note | Show `Reference not durable`; require import, verified relink, or replacement before build use. Never publish or store a private absolute path as identity. | Covered |
| Saved asset with a durable verified identity | §§7, 8.2 and §4 principles 9–10 | `MediaReference`, `ResolvedArtifact`, `MaterializedMedia` | Display artifact identity/version and current locator state separately; missing locators do not erase intent. | Covered |

## 5. Explicit decision record

| ID | Proposed decision for Producer acceptance | Rationale | Follow-up owner |
| --- | --- | --- | --- |
| D24-01 | Table rows are never canonical edit, shot, paragraph, or anchor boundaries. | Only 85 of 547 rows pair both sides; narration and visual material are independently placed. | #13 incorporates the rule; later import/authoring work must prove it. |
| D24-02 | Right-column material must carry an explicit role: Visual, Citation, Source clip/audio, Graphic, Production marker, Draft note, or Reference. | The same legacy lane contains build events, evidence, instructions, and non-build notes. | Producer accepts taxonomy; later authoring design implements it. |
| D24-03 | A right-only item attaches by exact text range or explicit point-between-blocks anchor. Ambiguous items remain Unplaced; proximity is evidence, not authority. | Silent nearest-row attachment would invent timing and meaning. | Producer accepts behavior; a bounded model/design follow-up supplies the missing general unplaced state. |
| D24-04 | Mutually exclusive alternatives become a first-class variant group with exactly one active Draft/build choice; other choices remain losslessly adjacent. | Extras preserves material but does not state exclusivity or active choice. | After acceptance, roadmap steward files a contract/design issue; no change in #24. |
| D24-05 | Multiple candidate links/ranges remain one request with explicit candidates and one nullable selected candidate. No implicit first-link selection. | Candidate preservation and build determinism require separate proposal and choice identities. | After acceptance, roadmap steward files a bounded candidate-selection issue. |
| D24-06 | Formatting is never imported as production semantics. Strikethrough triggers a `possible superseded` review; highlights/colors remain human emphasis until classified. | Source formatting is inconsistent and cannot safely determine visibility, readiness, or build scope. | #13 prototype shows conversion-review states; later import design owns mapping UI. |
| D24-07 | Derived graphics must retain semantic inputs, data/source citations, snapshot/version, derivation note, and pinned template revision together. | A screenshot or instruction alone cannot reproduce or audit a chart/map later. | After acceptance, roadmap steward files a bounded graphic-provenance contract issue. |
| D24-08 | Paths, folders, and discussion references are locators/hints only. Build-eligible assets require a durable ID, verified bytes, and retained provenance. | The product already separates identity from locator and forbids silent substitution. | Existing Phase 5 asset workflow; #13 shows unresolved/relink presentation. |
| D24-09 | Citations and transcript evidence are not visuals unless the author explicitly promotes them to a visual event. | A supporting source link must not acquire screen time merely because it is in the right lane. | #13 prototype distinguishes Citation and Visual cards. |
| D24-10 | Public artifacts use only aggregate counts, generalized roles, and fictional examples; the source document and URL remain private evidence. | Issue #24 and the delegation explicitly require confidentiality. | Every reviewer and follow-up issue author. |

Producer acceptance of D24-01 through D24-10 makes them the investigation's
decision output. It does not amend `ScriptDocument v1` or authorize
implementation.

## 6. Follow-up record

No follow-up issue is created by this investigation before Producer acceptance.

| Proposed bounded follow-up | Trigger | Current owner | Relationship to frozen contracts |
| --- | --- | --- | --- |
| Variant groups and candidate-source selection design | Producer accepts D24-04 and D24-05 | Roadmap steward files an Inbox design/contract issue | Must propose exact schema/version and migration impact before any contract edit. |
| Typed right-lane roles and general Unplaced anchoring | Producer accepts D24-02 and D24-03 | Roadmap steward files an Inbox authoring-model issue | Must not overload `VisualEvent.status` or marker-only `unplaced`. |
| Typed narration annotations for pronunciation/performance | Producer accepts the Missing findings in §4.1 | Roadmap steward files an Inbox contract/design issue | Must state prompter, synthesis, validator, and migration effects. |
| Derived-graphic provenance relationship | Producer accepts D24-07 | Roadmap steward files an Inbox graphics-contract issue | Must preserve existing `GraphicUse` and template-version guarantees. |
| Supervised legacy conversion review | Producer accepts D24-06 and the Unplaced behavior | Roadmap steward decides whether this belongs in the later authoring/import slice | Heuristic self-service import remains deferred; no parser is authorized here. |

## 7. Edit-boundary and anchor validation

The accepted design must pass these sample-grounded invariants:

1. A narration paragraph may span several legacy rows and several picture
   cuts without being split.
2. A single legacy row may contain only narration, only visual/reference
   material, both, or neither; none of those shapes implies duration.
3. A full-frame visual covers an exact narration token range; an overlay may
   overlap on-camera text but cannot satisfy voiceover coverage by itself.
4. A Citation, Reference, Draft note, or Production marker contributes no
   picture duration unless explicitly promoted to a Visual event.
5. A right-only item with no confident range remains Unplaced. Conversion may
   preserve its source order and neighboring block IDs as evidence, but must
   not silently bind it.
6. Multiple candidates and alternatives do not create overlapping build
   events until one candidate/variant is selected.
7. Paragraph boundaries remain writing structure; frame timing remains
   compiled output or an explicit timing override.

## 8. Exact bounded impact on issue #13

Issue #13's artifact-structure recommendation, suite design-language contract,
authorization boundaries, Desktop/Web treatment, and issue #21 token boundary
do not change. Its Claude brief needs only the following bounded additions.

### 8.1 Add to section 8.2, Required source artifacts

> - The Producer-accepted issue #24 representative-script coverage audit and
>   `docs/prototypes/issue-24-sanitized-prototype-input-brief.md`. Use the
>   private source only as retained evidence; Claude receives the sanitized
>   brief, never the source document or URL.

### 8.2 Add to section 7.3, Script to Timeline artifact structure

> - **Content-language coverage** — a focused scenario proving continuous
>   narration across multiple visual cuts, left-only/right-only asymmetry,
>   typed right-lane roles, exact and unplaced anchors, variants, multiple
>   source candidates, formatting-review signals, derived-graphic provenance,
>   and unresolved local references without treating rows as edit boundaries.

### 8.3 Add to section 7.4, Required high-fidelity evidence

> - Prove that Citation, Visual, Source clip/audio, Graphic, Production marker,
>   Draft note, and Reference cards remain distinguishable by text/icon and
>   accessible name, not color alone.
> - Prove hover, focus, and keyboard traversal between exact narration ranges
>   and attached cards; prove Unplaced items have no invented range or
>   duration.
> - Prove only the selected variant and selected source candidate participate
>   in active Draft/build previews; all alternatives remain readable.
> - Prove formatting cues enter an explicit review state and never silently
>   assign OC/VO, build scope, status, or ownership.
> - Prove derived graphics show source/version provenance and unresolved local
>   references show import/relink/remediation without exposing absolute paths.

### 8.4 Replace the generic fixture bullet in section 8.3

Replace `safe, fictional content and sanitization rules` with:

> - the issue #24 sanitized prototype brief as the required fictional content
>   authority; no private source title, URL, document identifier, names,
>   quotations, facts, or source-specific links may enter Claude or screenshots.

### 8.5 Add one issue #13 acceptance check

> Review the issue #24 additions and sanitized prototype brief. **Expected:**
> every accepted sample content family has a visible authoring treatment; rows
> are never edit boundaries; unresolved choices remain explicit; and issue #21
> still exclusively owns visual-token decisions.

These edits are the entire #13 handoff. They do not reopen its artifact
structure decision, add a dependency on issue #21, authorize high-fidelity UI,
or alter any contract.

## 9. Producer acceptance checklist

1. Open this coverage audit and review §1.1.
   **Expected:** the structural counts are complete and contain no private
   title, URL, quotation, name, or source-specific link.
2. Review §§3–4 row by row.
   **Expected:** every observed structural and semantic family has a product-
   spec mapping, canonical-model mapping, planned authoring behavior, and one
   of the four allowed statuses.
3. Review D24-01 through D24-10 in §5.
   **Expected:** rows are rejected as edit boundaries; typed roles, anchoring,
   variants, candidates, formatting, graphics provenance, and asset durability
   each have an explicit decision.
4. Review §6.
   **Expected:** genuine Missing work has a bounded owner/trigger, but no
   follow-up issue or contract change has been created prematurely.
5. Review §7 against the structural signature.
   **Expected:** left-only, right-only, paired, and blank rows all preserve
   content without inventing duration or attachment.
6. Open `docs/prototypes/issue-24-sanitized-prototype-input-brief.md` and run
   its coverage checklist.
   **Expected:** every accepted content family is represented with fictional
   content only, and the required interactions/states are testable.
7. Review §8.
   **Expected:** the issue #13 delta is exact and bounded, preserves its prior
   architecture, and neither blocks on nor overrides issue #21.
8. Record one precise response on issue #24:
   - acceptance: `Accept issue #24 coverage map, decisions, sanitized prototype brief, and bounded issue #13 handoff.`
   - failure: `Issue #24 acceptance failed at checklist step <number>: <observed mismatch>.`

Leave issue #24 `In review` until the Producer records the acceptance response.
Never infer acceptance from silence or mark the issue `Done` from an agent
self-report.
