# Representative-script coverage audit

- Issue: [#24 — Audit a representative script against the Script-to-Timeline content model](https://github.com/mbelinkie/vera-script-to-timeline/issues/24)
- Status: Producer decisions recorded; complete artifact awaiting acceptance
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
| Pauses, pacing, emphasis, and delivery instructions inside speech | §§6.5, 8.3 | Voice settings and pronunciation/performance inputs are specified, but frozen v1 has only free-form `notes[]` | Show typed exact-range annotations distinct from narration. `Include in prompter` defaults on and emits a visibly non-spoken cue such as `[PAUSE]` or `[EMPHASIZE: second]`; the same typed data enters the performance sidecar/synthesis input. | Missing |
| Pronunciation guidance, including phonetic and plain-language forms | §§3, 6.5, 8.3 | Pronunciation dictionary/overrides are specified outside frozen v1 | Show a typed pronunciation annotation tied to exact text with readable alias/phoneme and preview. `Include in prompter` defaults on and emits a visibly non-spoken cue such as `[PRONUNCIATION: Lunara = loo-NAH-rah]`. | Missing |
| Questions, reminders, and drafting commentary | §§3, 6.3, 6.6 | `NoteDraftBlock`, `IdeaItem`, `StoredFragment`, or comment thread depending intent | Ask the author to classify as private note, Idea, Extra, comment, or production marker; position alone is insufficient. | Design decision required |
| Collaborative discussion, optionally directed to a specific user | §§5, 6.8 | Anchored comment thread with replies, stable-user mentions, resolve/reopen, attribution, and stale-anchor repair | Allow comments on text, typed cards, Ideas, Extras, or between blocks, with an optional `@user` mention. Comments never affect narration, timing, prompter, or build output. | Covered |

### 4.2 Visual, source, and evidence roles

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Generic picture/B-roll request | §§3, 6.2–6.4, 8.4, 13 | `VisualEvent` with `PlaceholderVisualSource` | Preserve request text on an anchored full-frame/overlay card. Its subtype remains `Unresolved visual` until classified; it is not a sibling media kind that overlaps Clip, Image, Capture, or Graphic. | Covered |
| Resolved local still or video | §§6.3, 8.2, 8.4 | `VisualEvent` with `LocalMediaVisualSource`; `MediaReference`/`LocalMediaImport` in later phases | Preview framing/audio/range and expose verified import/relink state; paths remain locators, never identity. | Covered |
| Logged research clip | §§6.11, 7, 8.1 | `VisualEvent`, `MediaReference`, and `ClipUsageRange` | Display title/excerpt and occurrence-specific use range while preserving research-owned evidence and immutable bounds. | Covered |
| Source URL with exact in/out or timestamp range | §§3, 6.11, 7, 8.1 | `MediaReference.requestedInOut`, `ClipUsageRange`, and transcript snapshot | Keep link, readable range, precision, and selected frames together; range never floats as an untyped note. | Covered |
| Transcript excerpt or quoted source speech | §§3, 6.11, 8.1 | Immutable transcript snapshot plus occurrence-readable excerpt | Display as evidence on the clip card/inspector; it does not become host narration or a citation by proximity. | Covered |
| Source-audio instruction, including mute/silent footage | §§3, 7, 8.1, 8.4 | `VisualEvent.audioPolicy` and later usage settings | Expose explicit `Mute`/`Use source` state on the Clip card; do not infer from link type or formatting. | Covered |
| Directly uploaded image | §§6.4, 8.2, 8.4 | Imported `MediaReference` plus immutable managed artifact and retained provenance | Import through an explicit copy/move/reference policy, verify/hash the bytes, and retain durable project-managed storage separately from the original locator. | Covered |
| Linked image URL | §§6.4, 8.2, 8.4 | URL-backed `MediaReference` resolved to an immutable local artifact | Automatically acquire the original full-resolution asset locally when added, then verify type/dimensions, hash, and provenance. The quiet acquisition must still expose failure, retry, and artifact status. | Covered |
| User-supplied screenshot | §§6.4, 8.4 | Uploaded image unless a live capture relationship is explicitly retained | Treat a manually uploaded screenshot as an Image, not as a recapturable webpage, because its source page and capture parameters are not authoritative. | Design decision required |
| VERA-created webpage or screen capture | §§6.4, 8.4 | Versioned Capture request plus immutable capture artifacts and provenance | Distinguish capture intent from Image: retain requested/final URL, region, viewport, adapter, time, warnings, revision history, and an explicit recapture policy. | Covered |
| Capture timing and version policy | §8.4 and §14 currently ship capture-on-add/manual recapture and defer scheduled monitoring | No accepted entity expresses `now`, `on build`, or `periodic` capture policy plus retention | Offer Capture now, Capture immediately before build/render, or Periodic capture. Freeze the exact resulting artifact into every build; keep bounded history without pruning pinned/checkpoint/build-referenced revisions. | Missing |
| Still/capture animation and focal subject | §8.4 supports explicit motion presets but defines only composition defaults, not custom zoom focus or semantic focus repair | Visual occurrence setting referencing a versioned motion-preset identity; no accepted focus-target/segment entity | Every Image or Capture exposes a motion setting. Built-ins are `None`, `Slow drift — top left`, `Slow drift — top center`, and `Slow zoom`; zoom focus may be center, a manually selected source-relative point such as a face, or a bound Spotlight region such as highlighted text. | Missing |
| YouTube watch-page presentation | §§6.4, 8.1–8.4 cover the source Clip, page Capture, artifact resolution, and motion separately | No accepted compound source/treatment binds a clip occurrence, watch-page capture, composite layout, and motion into one reproducible unit | From any compatible YouTube Clip, `Present on YouTube page` creates a nested composite: the chosen moving clip replaces the captured player area while the high-resolution page capture keeps the description and requested visible comments. A second optional `Refresh page now` action captures current public page state, including play count, as a new immutable page revision. | Missing |
| Critical-text spotlight on a page capture | §§6.4 and 8.4 expose capture region/crop and visual composition, but do not define an inverse-dimming matte or its recapture behavior | No accepted capture-treatment entity retains selected OCR words, source-pixel geometry, matte derivation, dimming parameters, timing, and repair evidence | Overlay selectable OCR word/line boxes on the immutable high-resolution capture. The author selects text; VERA unions and pads its source-pixel boxes into a previewed inverse matte that dims everything else. A recapture attempts evidence-based remapping and becomes `Spotlight stale` rather than moving silently when confidence is insufficient. | Missing |
| Citation, article, report, or evidence link not intended on screen | §§3, 6.3 | Planned `citation` row/card; no frozen-v1 citation block yet | Use a visibly typed Citation card, preserved in script/build report, with no timeline duration by default. | Covered |
| Production-only instruction or Resolve task | §§6.13, 7, 13 | Planned `ScriptVideoMarker` | Point-anchor to a word, event edge, or between blocks; no duration; unplaced if anchor is lost. | Covered |
| Music, sound file, or audio cue reference | §§6.3, 7 | Planned `MusicCueUse`/template revision; simpler production note before Phase 9 | Type as Music/SFX when it is timeline intent; type as Reference when it is only supporting material. Never treat an arbitrary file mention as approved media. | Covered |
| Right-column role inferred only from prose/position | §§3, 6.1–6.4 | Existing typed entities cover final roles, but no accepted classification workflow binds legacy text to them | Require a hierarchical role picker: timed Picture (`Unresolved visual`, `Clip`, `Image`, `Capture`, `YouTube page composite`, or `Graphic`), Audio cue, Citation, Editor note/timeline marker, Draft note, or Reference. `Clip` exposes `Mute`/`Use source audio`; `Graphic` is semantic script data rendered by a pinned template. | Design decision required |

### 4.3 Graphics and provenance

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Full-screen text or long-text graphic instruction | §§3, 6.3, 7 | Placeholder `VisualEvent` now; later `GraphicUse` with pinned template revision | Show editable semantic text and intended presentation, not a pasted screenshot as the only source of truth. | Covered |
| Map, chart, comparison, or other derived graphic | §§3, 6.3, 7 | `GraphicUse.semanticInputs` and immutable template revision | Author semantic inputs and preview the graphic while keeping it anchored like any visual. | Covered |
| Data/source provenance for a derived graphic | §§7, 8.4 and §4 principles 8–10 establish provenance, but no explicit graphic-evidence relationship is defined | No accepted canonical relationship from `GraphicUse` to source citations/data snapshot | Require source citations, data snapshot/version, derivation note, and template revision to survive together. | Missing |
| Infographic elements that change emphasis on narration cues | §§7 and Phase 9 define pinned Fusion templates, semantic inputs, timing policy, and occurrence settings, but no stable target manifest or intra-graphic cue schedule | No accepted entity identifies semantic rows/bars/cells/series or changes their template-defined visual state at exact compiled times | A template declares stable human-readable highlight targets and allowed semantic states. One Graphic occurrence may carry several narration-anchored cues—for example emphasize one table row, then two different bars—while the template revision maps states to actual Fusion controls/colors. | Missing |
| Multiple candidate visual treatments for the same words | §§6.2, 8.4 support one authored event/source at build time | No sequence/option/comparison-set entity in the canonical model | Preserve explicit intent: a Sequence plays all items consecutively; an Option set has zero or one selected candidate; a Comparison stack sends organized candidates to alternate Resolve tracks with a choose marker. Never infer intent or select the first item. | Missing |

### 4.4 Editorial alternatives, formatting, and asset durability

| Observed content family | Product-spec authority | Canonical representation | Planned authoring behavior | Status |
| --- | --- | --- | --- | --- |
| Mutually exclusive narration or visual alternatives | §§3, 6.6 preserve unused material, but do not express mutual exclusion | No `VariantGroup`/active-choice concept | Present a first-class variant group with exactly one active choice for Draft/build; keep other choices adjacent and lossless. | Missing |
| Proposed editorial cut | §§6.6, 6.8–6.9 and §4 principle 6 preserve history/Extras, while full suggestion mode is deferred | No accepted typed `Propose cut` review action | Strikethrough exists only as the visible, attributed pending-cut proposal. Accepting removes the text from active Draft while preserving it as section-linked parked material/history; rejecting restores ordinary text. A proposal never silently changes a build. | Missing |
| Highlight color, foreground color, bold, italic, and underline | §§6.1, 6.6 and §4 principle 1 preserve readable formatting but define no production semantics | Rich-text/editor presentation only; frozen v1 does not serialize arbitrary formatting | Preserve when useful for human review, but never infer OC/VO, readiness, selection, ownership, build eligibility, or timeline action from appearance. Generic decorative strikethrough is not offered because strikethrough is reserved for `Propose cut`. | Design decision required |
| “Add somewhere,” placement questions, and unresolved position | §§6.13, 13 and §4 principle 11 require honest incompleteness | Marker-only unplaced state exists; general unplaced content does not | Keep in an Unplaced queue with original order/proximity evidence; explicit reattachment or dismissal only. | Missing |
| Reference to a local path, folder, discussion thread, or unattached sound file | §§8.2, 13 and §4 principles 9 and 12 | `MediaReference`/`LocalMediaImport` only after an authorized verified import; otherwise placeholder/reference note | Show `Reference not durable`; require import, verified relink, or replacement before build use. Never publish or store a private absolute path as identity. | Covered |
| Saved asset with a durable verified identity | §§7, 8.2 and §4 principles 9–10 | `MediaReference`, `ResolvedArtifact`, `MaterializedMedia` | Display artifact identity/version and current locator state separately; missing locators do not erase intent. | Covered |

## 5. Explicit decision record

| ID | Proposed decision for Producer acceptance | Rationale | Follow-up owner |
| --- | --- | --- | --- |
| D24-01 | Table rows are never canonical edit, shot, paragraph, or anchor boundaries. | Only 85 of 547 rows pair both sides; narration and visual material are independently placed. | #13 incorporates the rule; later import/authoring work must prove it. |
| D24-02 | Right-column material uses a hierarchical taxonomy: timed Picture (`Unresolved visual`, `Clip`, `Image`, `Capture`, `Graphic`), Audio cue, Citation, Editor note/timeline marker, Draft note, or Reference. | `Visual` is a parent behavior, not a peer of Clip; the lane also contains evidence and non-build notes. | #13 proves the taxonomy; later authoring work implements it. |
| D24-03 | A timed Picture attaches to an exact text range or an explicit point designated as its start or end, and needs any consistent two of start, end, and duration. It may remain Unplaced while drafting, but Release blocks until an interval is derivable. | Proximity invents meaning; three-point editing permits start+end, start+duration, or duration+end without requiring all three. | A bounded model/design follow-up supplies general Unplaced and timing-validation behavior. |
| D24-04 | Mutually exclusive alternatives are first-class variant groups with exactly one active Draft/build choice. Removed-but-retained material is instead one section-linked parked `StoredFragment`, shown collapsed beneath its section and also in global Extras. | Optional parked material and alternate authored choices have different intent; the two views must not duplicate content identity. | Later authoring/contract design owns variant and section-linked Extras behavior. |
| D24-05 | Source collections carry explicit intent: Sequence (all consecutive), Option set (zero or one selected), or Comparison stack (organized alternate Resolve tracks plus a choose marker). No first-link selection is implicit. Release blocks on an unresolved Option set unless the Producer explicitly changes its resolution policy to `Choose in Resolve`. | Selection, succession, and editorial comparison have different deterministic timeline behavior. | Later candidate/group design owns schema and Resolve mapping. |
| D24-06 | Formatting never controls production semantics. Strikethrough exists only as the attributed visual state of an explicit `Propose cut` action; accept parks the cut content with history and reject restores it. | Decorative formatting and editorial decisions must not be conflated; pending proposals cannot silently change build content. | A bounded review-semantics follow-up is required because full suggestion mode is currently deferred. |
| D24-07 | Derived graphics retain semantic inputs, data/source citations, snapshot/version, derivation note, and pinned template revision together. | A screenshot or instruction alone cannot reproduce or audit a chart/map later. | A bounded graphic-provenance contract issue follows acceptance. |
| D24-08 | Paths, folders, and discussion references are locators/hints only. Build-eligible assets require a durable ID, verified bytes, and retained provenance. | The product already separates identity from locator and forbids silent substitution. | Existing Phase 5 asset workflow; #13 shows unresolved/relink presentation. |
| D24-09 | Citations and transcript evidence are not pictures unless the author explicitly promotes them to a timed Picture event. | A supporting source must not acquire screen time because of lane position. | #13 prototype distinguishes Citation and Picture cards. |
| D24-10 | Comments are first-class collaborative threads with optional stable-user mentions, replies, resolve/reopen, and stale-anchor repair; they have no timeline/build effect. | Discussion must not be overloaded into Draft notes or Resolve markers. | Existing Phase 3 contract; #13 proves the authoring distinction. |
| D24-11 | Image and Capture are distinct Picture subtypes. An Image is uploaded or linked; linked images are automatically acquired to verified local managed storage. A user-uploaded screenshot is an Image unless it explicitly retains a live Capture relationship. | Bytes alone do not establish recapture intent or provenance. | Phase 5 media design plus a bounded acquisition-taxonomy follow-up. |
| D24-12 | A Capture declares `Now`, `On build`, or `Periodic`. Each attempt creates an immutable revision; a build freezes the exact revision it used. Periodic history is bounded by configurable retention, but pinned, checkpoint-referenced, or build-referenced revisions are never pruned. | Freshness must be deliberate, reproducible, and storage-bounded. | Revives scheduled capture as an accepted bounded follow-up; retention count/age remains later design input. |
| D24-13 | Every Image and Capture occurrence has a versioned motion preset. Initial choices are `None`, `Slow drift — top left`, `Slow drift — top center`, and `Slow zoom` with `Center` as its default focus; later presets can be added without changing frozen builds. | Motion is per-use editorial intent, not a property inferred from source type. | Phase 5 design/contract follow-up. |
| D24-14 | Pronunciation and performance instructions are typed exact-range annotations with `Include in prompter` on by default. Included annotations render as unmistakably non-spoken bracketed cues in the prompter as well as its sidecar. | The person performing needs to see the direction; free-form notes are not deterministic enough. | Bounded prompter/annotation contract follow-up. |
| D24-15 | Public artifacts use only aggregate counts, generalized roles, and fictional examples; the source document and URL remain private evidence. | Issue #24 and the delegation explicitly require confidentiality. | Every reviewer and follow-up issue author. |
| D24-16 | `YouTube page composite` is a first-class compound Picture treatment available from any compatible YouTube Clip in one primary action. It binds the clip occurrence, immutable high-resolution watch-page capture with description/requested visible comments, player-area placement, pinned composite-template revision, audio policy, and versioned motion preset. Initial creation captures the page; `Refresh page now` optionally records current public page state such as play count as a new selected revision. Existing builds never change. | The Producer currently assembles this as two captures plus a nested edit; preserving the parts and derivation makes the convenient action reproducible instead of baking an unauditable screen recording. | Bounded compound-media authoring/contract and Resolve-materialization follow-up. |
| D24-17 | Capture and YouTube page composite occurrences may add one or more timed `Spotlight` treatments. VERA runs versioned OCR against the immutable high-resolution capture and exposes selectable word/line boxes. A Spotlight stores selected OCR word IDs/text/context, their capture-pixel and normalized geometry, optional DOM evidence, union/padding/rounding parameters, dim opacity/feather, its active interval (defaulting to the whole occurrence), and a versioned treatment identity. Confirmation generates a full-resolution immutable inverse-matte artifact. Recapture may propose a remap, but ambiguity creates `Spotlight stale` and requires keep-old-capture, accept-remap, or redraw; it never silently shifts. The deterministic composition order is source/composite → inverse matte → whole-picture motion. | OCR already supplies word-level pixel boxes, so text selection and matte generation are tractable. The harder parts are supervised target repair and a stable Resolve representation. The reliable baseline transfers a verified RGBA/alpha matte artifact into a generated nested sequence; emitting an editable native Resolve/Fusion mask from the same geometry is an adapter enhancement only after version-specific proof. | Bounded capture-treatment/OCR-matte and Resolve-materialization follow-up. |
| D24-18 | Infographic Fusion templates must publish stable semantic highlight targets—such as a table row, bar, cell, series, label, or map region—with human labels, target kind, supported states, and the Fusion control binding supplied by the pinned template revision. A Graphic occurrence may contain multiple ordered `Graphic highlight cue`s. Each cue selects one or more target IDs, a template-defined state such as `emphasis` or `muted`, an exact narration anchor/interval, and an optional template-supported transition. A start-only cue may explicitly last until the next cue or Graphic end; otherwise the ordinary two-of-three timing rule applies. Disjoint targets may overlap; contradictory active states on the same target block Release. Cue completion returns the target to its base state unless the next cue continues it. | Infographic emphasis is authored meaning, while the actual color and Fusion node/control implementation belong to the immutable template revision. Stable semantic targets prevent authoring from depending on brittle internal node names and allow several cues to compile deterministically. | Bounded graphic-highlight target/cue contract, Fusion template capability, compiler, and fallback follow-up. |
| D24-19 | Image, Capture, and YouTube page composite motion separates a versioned preset from its focus target. `Slow zoom` supports `Center`, a manually clicked source-relative point, or a bound region such as a confirmed Spotlight. Manual focus stores normalized source coordinates and a readable label; a Spotlight binding stores the treatment/revision identity and derives its centroid plus safe padding. `Zoom to spotlight` aligns the motion segment to the Spotlight interval by default. A Picture may have ordered motion segments when focus changes; contradictory overlapping transforms block Release. Authoring previews start/end frames and any clamping needed to avoid empty canvas. Updating source bytes or a capture revision makes manual focus `Needs review`; an accepted Spotlight remap repairs its bound focus, while a stale Spotlight keeps the motion stale. The build freezes source/capture revision, preset version, focus mode/evidence, resolved point/region, scale/translation keyframes, segment timing, and composition order. | A normalized manual point handles faces and other subjects without detection. Semantic binding lets a text highlight and zoom stay synchronized through supervised recapture repair instead of duplicating fragile coordinates. | Bounded motion-focus/segment contract, authoring preview, compiler, and Resolve/Free fallback follow-up. |

Producer acceptance of D24-01 through D24-19 makes them the investigation's
decision output. It does not amend `ScriptDocument v1` or authorize
implementation.

## 6. Follow-up record

No follow-up issue is created by this investigation before Producer acceptance.

| Proposed bounded follow-up | Trigger | Current owner | Relationship to frozen contracts |
| --- | --- | --- | --- |
| Variant groups, section-linked parked material, and candidate collection modes | Producer accepts D24-04 and D24-05 | Roadmap steward files bounded Inbox design/contract issue(s) after #24 acceptance | Must distinguish Variant, StoredFragment, Sequence, Option set, and Comparison stack identities and state exact Resolve/release behavior. |
| Typed right-lane roles, general Unplaced anchoring, and three-point timing | Producer accepts D24-02 and D24-03 | Roadmap steward files a bounded Inbox authoring-model issue after #24 acceptance | Must not overload `VisualEvent.status` or marker-only `unplaced`; must validate the two-of-three timing rule and disagreement when all three values exist. |
| Typed narration annotations for pronunciation/performance | Producer accepts D24-14 | Roadmap steward files a bounded Inbox contract/design issue after #24 acceptance | Must state visible prompter, sidecar, synthesis, validator, and migration effects while leaving ordinary direction blocks excluded. |
| Derived-graphic provenance relationship | Producer accepts D24-07 | Roadmap steward files an Inbox graphics-contract issue | Must preserve existing `GraphicUse` and template-version guarantees. |
| Image acquisition taxonomy, capture policies/retention, motion presets, and custom focus | Producer accepts D24-11 through D24-13 and D24-19 | Roadmap steward files bounded Phase 5 design/contract issues after #24 acceptance | Scheduled capture is explicitly revived from §14; exact retention count/age is still a design input. Define point/region focus, Spotlight binding, ordered segments, source-update review, framing/clamping, resolved transforms, and Studio/Free representations. Existing build snapshots keep immutable artifact and focus identities. |
| One-action YouTube watch-page composite | Producer accepts D24-16 | Roadmap steward files a bounded Inbox compound-media design/contract issue after #24 acceptance | Must reuse authoritative research/YouTube clip identity and Capture artifacts rather than duplicate acquisition; freeze clip revision, page-capture revision, layout/template, audio policy, motion preset, and rendered/nested artifact in the build snapshot. Public anonymous capture ships first; authenticated/personalized page capture remains separately authorized. |
| Capture Spotlight OCR matte and supervised remapping | Producer accepts D24-17 | Roadmap steward files a bounded Inbox capture-treatment design/contract issue after #24 acceptance | Define OCR word IDs/boxes/model version, capture hash, union/padding/rounding, normalized geometry, DOM/text evidence, matte artifact format/hash, accessibility, effect ordering, exact timing, stale/remap decisions, and build-snapshot fields. Baseline: verified RGBA/alpha matte in a generated nested sequence. Native editable Resolve/Fusion geometry follows only after adapter proof; manual completion is an explicit fallback, never the normal path. |
| Fusion infographic highlight targets and cue schedule | Producer accepts D24-18 | Roadmap steward files a bounded Inbox graphics-template/contract issue after #24 acceptance | Extend the package capability design with stable semantic targets, allowed states/control bindings, cue identity/timing/transition/reset behavior, overlap validation, Studio keyframe verification, and an honest Free fallback. A build pins the template revision, semantic inputs/data provenance, cue schedule, resolved state/control values, and rendered result. Actual visual values remain owned by the template and issue #21; #24 chooses none. |
| `Propose cut` review semantics | Producer accepts D24-06 | Roadmap steward files a bounded Inbox review-model issue after #24 acceptance | This is narrower than general track changes; it must state collaboration, history, Draft/Extras, prompter, and build effects. |
| Comments with optional directed mentions | Producer accepts D24-10 | Existing Phase 3 scope; no new issue required unless prototype review finds a gap | Must remain separate from Draft notes and Editor/Resolve markers. |
| Supervised legacy conversion review | Producer accepts D24-06 and the Unplaced behavior | Roadmap steward decides whether this belongs in the later authoring/import slice | Heuristic self-service import remains deferred; no parser is authorized here. |

## 7. Edit-boundary and anchor validation

The accepted design must pass these sample-grounded invariants:

1. A narration paragraph may span several legacy rows and several picture
   cuts without being split.
2. A single legacy row may contain only narration, only visual/reference
   material, both, or neither; none of those shapes implies duration.
3. A timed Picture is buildable only when any two of start, end, and duration
   derive one interval: start+end, start+duration, or duration+end. If all
   three are supplied they must agree; one anchor alone or duration alone is
   not enough. An overlay may overlap on-camera text but cannot satisfy
   voiceover coverage by itself.
4. A Citation, Reference, Draft note, or Editor note/timeline marker contributes
   no picture duration unless explicitly promoted to a timed Picture event.
5. A right-only item with no confident range remains Unplaced. Conversion may
   preserve its source order and neighboring block IDs as evidence, but must
   not silently bind it.
6. A Sequence schedules every member consecutively. An Option set schedules
   only its selected member; Release blocks if unresolved unless its Producer-
   set policy is `Choose in Resolve`. A Comparison stack intentionally places
   organized alternates and a choice marker rather than pretending one won.
7. A parked fragment appears under its source section and in global Extras by
   reference to one identity, and it never enters active Draft/build output.
8. Comments and included prompter annotations remain visibly different:
   comments never enter output, while included typed annotations render as
   non-spoken prompter cues and sidecar data.
9. Every Image/Capture build freezes verified bytes, source provenance, the
   selected motion-preset version, and—for Capture—the exact capture revision.
10. A YouTube page composite freezes its clip revision independently from its
   page-capture revision. Refreshing play count, description, or visible
   comments creates a new page revision and cannot rewrite an earlier build or
   silently change the selected video in/out.
11. A Spotlight is an inverse matte derived from confirmed OCR word/line boxes,
   not imported text formatting. The build pins the capture hash, OCR/profile
   version, selected text evidence, geometry/derivation parameters, and matte
   artifact hash. A capture revision change must retain an accepted remap or
   make the treatment stale; a build never guesses new geometry. Spotlight
   timing and whole-picture motion remain independently editable and are frozen
   in composition order.
12. Graphic highlight cues refer only to stable semantic target IDs declared by
   the pinned template, never Fusion node names. Several ordered cues may change
   one Graphic over time. The compiler resolves every cue anchor, blocks same-
   target state conflicts, returns completed cues to base state by policy, and
   freezes the resolved Fusion control schedule and template revision.
13. Slow-zoom focus is source-relative or bound to an accepted Spotlight—not a
   viewport pixel. Start/end preview must show the real crop, never expose empty
   canvas, and flag source/capture changes for review. Several ordered motion
   segments may follow several targets, but conflicting transforms cannot
   compile. The resolved focus and transforms are immutable build evidence.
14. Paragraph boundaries remain writing structure; frame timing remains
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
>   hierarchical right-lane roles, exact/unplaced/three-point timing, variants,
>   section-linked parked material, Sequences, Option sets, Comparison stacks,
>   uploaded/linked images, versioned capture policies and motion presets,
>   manual and Spotlight-bound slow-zoom focus with end-frame preview,
>   one-action YouTube watch-page composites, capture Spotlights with supervised
>   target repair, multi-cue Fusion infographic emphasis,
>   typed visible prompter cues, comments/mentions, `Propose cut`, derived-
>   graphic provenance, and unresolved local references without treating rows
>   as edit boundaries.

### 8.3 Add to section 7.4, Required high-fidelity evidence

> - Prove that timed Picture and its `Unresolved visual`, Clip, Image, Capture,
>   `YouTube page composite`, and Graphic subtypes remain distinguishable from
>   Audio cue, Citation, Editor note/timeline marker, Draft note, Reference, and
>   Comment by text/icon and accessible name, not color alone.
> - Prove hover, focus, and keyboard traversal between exact narration ranges
>   and attached cards; prove Unplaced items have no invented interval and the
>   two-of-three timing rule exposes incomplete or contradictory timing.
> - Prove Variants, Sequences, Option sets, and Comparison stacks have visibly
>   distinct build behavior; unresolved Option sets block Release unless their
>   Producer-set policy is `Choose in Resolve`.
> - Prove a section-linked parked fragment appears both collapsed under its
>   section and in global Extras without duplication or active-build inclusion.
> - Prove formatting remains nonsemantic and only an attributed `Propose cut`
>   action creates strikethrough; accept parks content and reject restores it.
> - Prove derived graphics show source/version provenance and unresolved local
>   references show import/relink/remediation without exposing absolute paths.
> - Prove upload and linked-image acquisition, Capture `Now`/`On build`/
>   `Periodic` policy, immutable revisions/retention state, and versioned motion
>   presets without performing real network or media actions.
> - Prove that `Present on YouTube page` turns a compatible Clip into a nested
>   composite in one primary action; description/comments remain visible,
>   `Refresh page now` produces a newly selected immutable page revision, slow
>   zoom applies to the whole composite, and prior builds remain unchanged.
> - Prove a Capture Spotlight exposes selectable OCR words/lines over a fictional
>   high-resolution capture, turns the confirmed source-pixel boxes into a
>   previewed inverse matte, dims everything outside it, and records an exact
>   interval. Show the generated matte/nested-sequence handoff, composition
>   before whole-picture motion, and a visibly stale target instead of silent
>   movement when a recapture changes layout.
> - Prove `Slow zoom` can focus on center, a manually clicked fictional face,
>   or a confirmed Spotlight region. Show `Zoom to spotlight` timing, end-frame
>   crop/clamping, ordered focus segments, source-update review, stale/accepted
>   Spotlight remapping, resolved transforms, and honest Studio/Free output.
> - Prove one pinned Fusion infographic exposes semantic targets rather than
>   internal node names and previews several narration-anchored highlight cues:
>   at minimum one table-row target and two sequential bar targets. Show base,
>   active, transition, reset, timing-conflict, template-update-available, Studio
>   keyframe, and declared Free-fallback states without selecting issue #21's
>   actual colors.
> - Prove typed pronunciation/performance annotations default to visible non-
>   spoken prompter cues, and Comments with optional mentions remain discussion
>   only.

### 8.4 Replace the generic fixture bullet in section 8.3

Replace `safe, fictional content and sanitization rules` with:

> - the issue #24 sanitized prototype brief as the required fictional content
>   authority; no private source title, URL, document identifier, names,
>   quotations, facts, or source-specific links may enter Claude or screenshots.

### 8.5 Add one issue #13 acceptance check

> Review the issue #24 additions and sanitized prototype brief. **Expected:**
> every accepted sample content family has a visible authoring treatment; rows
> are never edit boundaries; unresolved choices, capture freshness, timing, and
> review states remain explicit; and issue #21 still exclusively owns visual-
> token decisions.

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
3. Review D24-01 through D24-19 in §5.
   **Expected:** rows are rejected as edit boundaries; roles, timing, variants,
   parked material, candidate modes, comments, image/capture acquisition,
   motion and custom focus, YouTube page composites, capture Spotlights, multi-
   cue infographic emphasis, prompter cues, review semantics, graphics
   provenance, and asset durability each have an explicit decision.
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
