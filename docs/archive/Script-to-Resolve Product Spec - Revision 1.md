# Script-to-Resolve Authoring Platform

Product and technical specification — working draft

Working title: Assembly. Status: discovery / scope. Prepared 13 August 2026;
updated 24 August 2026.

## 1. Executive summary

Build a collaborative web-based authoring system that feels as familiar as the
current two-column Google Docs workflow, but stores enough structured
information to compile a written script into a rough-cut DaVinci Resolve
project. Multiple authorized editors can work in the same script, see presence
and synchronized-save state, discuss anchored passages, and preserve an
attributed linear history without turning Resolve into a shared mutable
document. A script can begin as a per-script nested outline of research topics,
questions, and ideas before any draft prose exists. As writing develops, the
writer can promote those ideas into the active draft and move promising but
currently unused script material into a separate **Extras** area instead of
deleting it. The output should include generated voiceover, research clips,
B-roll, stills, approved music cues, and versioned graphic standards placed at
intentional points on a timeline. The document must also state whether the host
is on camera or speaking in voiceover at every point, and every off-camera span
must identify what the audience sees. The authored script remains readable by a
human; the machine-readable behavior lives beneath visible blocks and cards
rather than in fragile formatting conventions. A later recorded-performance
phase can ingest long prompter line shoots, align repeated takes to stable
script ranges, collect explicit keeper approvals, and compile a new timeline
that replaces temporary narration while reflowing text-anchored visuals to the
real performance.

The product should be a compiler, not a replacement nonlinear editor. The authoring project is the source of truth. A DaVinci Resolve project or timeline is a generated, inspectable deliverable that an editor can refine. Rebuilding should be deterministic, incremental where practical, and must never erase manual editorial work without an explicit reconciliation step.

The product distinguishes the synchronized collaborative live head, immutable
named document checkpoints, immutable standard/asset/rights revisions,
immutable compiler build snapshots, and generated Resolve timeline or import
package versions. Editors may create clearly labeled preview builds from a
fully synchronized working revision. A Producer may create a release build only
from an approved named checkpoint. Continued writing, restored content,
approval changes, and newer standards never rewrite a prior checkpoint, build,
or generated timeline.

A use of a logged clip in the script is also distinct from the logged source
record. The writer may trim that occurrence inward, revise the English subtitle
copy shown to viewers, and attach production markers without changing the
research clip, its source-language transcript, or any other use of it. When the
script and an already generated Resolve timeline both change, **Regeneration
Review** presents a highlighted, row-based comparison and lets the user adjust
which proposed script updates will be applied before a new timeline version is
created.

Recommended first release: author narration plus structured visual cues,
synthesize replaceable temporary narration at the narration-block level, resolve
already-logged research clips from the existing clip project, and use still-image
placeholders for unresolved visuals. Include live multi-editor authoring,
anchored comments, linear checkpoint history, and pinned workspace/project
graphic and music standards with explicitly permitted occurrence overrides.
Support two Resolve delivery modes from the
same frozen build and canonical timeline manifest: a Free-compatible verified
OTIO/FCPXML import package with one explicit manual import step, and a Studio
automation mode that creates and verifies the timeline through the supported
external scripting API. Studio mode may continue through automated review render
and optional Google Drive upload. Defer automatic visual search/generation and a
broad Fusion template library until both delivery contracts are proven.

### 1.1 Suite phases

1. The research tool logs transcript-backed source clips and prepares reusable
   editing artifacts.
2. This authoring platform compiles a structured script into a temp-narrated
   Resolve rough cut and exports the frozen prompter script used for a shoot.
3. The recorded-performance phase ingests the resulting long line-shoot media,
   presents matched takes beside the script, records keeper approvals, and
   creates a new recorded conform with B-roll retimed from verified word
   alignment. Its discovery outline is maintained in
   [Recorded-Performance-Conform Product Spec.md](./Recorded-Performance-Conform%20Product%20Spec.md).

Part 3 shares this product's document, artifact, build, and Resolve contracts,
but is intentionally a separate phase of work rather than an implied feature of
the narration-led MVP.

### 1.2 Resolve edition support

Both desktop editions are supported product targets:

- **Resolve Free — Prepare Resolve timeline:** compile the complete authoring
  revision, materialize verified media, and produce a self-contained import
  package containing the canonical manifest, OTIO plus FCPXML fallback, build
  report, and clear manual import instructions. Free mode never pretends it can
  use Studio-only external scripting. Resolve-specific features that interchange
  cannot express use an edition-compatible baked asset, a labeled placeholder,
  or an explicit manual-completion item recorded in the report.
- **Resolve Studio — Build in Resolve:** produce the same verified interchange
  package, then use a supported standard desktop Studio installation and the
  external Python/Lua API to create projects/bins/timelines, place media and
  Fusion templates, attach metadata, verify the result, and optionally render
  and deliver a review file in the background.

The authoring compiler, source resolution, immutable artifacts, narration,
timing, and build identity are shared. Edition mode changes only delivery and
post-delivery verification. A Free build and Studio build from the same frozen
revision must agree on every representable event rather than using separate
editorial interpretations.

## 2. Product promise

A writer can collect and hierarchically organize research ideas before drafting,
author a normal-looking two-column script, park unused passages without throwing
them away, and assign or request media beside each active passage. Authorized
Editors can work concurrently while Reviewers discuss and approve immutable
checkpoints and Producers control release builds. A workspace can publish
approved reusable graphic and music standards, a project can pin and override
only permitted fields, and each placed occurrence remains traceable to the exact
standard revision it used. A Resolve Free user can choose **Prepare Resolve
timeline** and receive a verified import package plus instructions for one manual
timeline import. A Resolve Studio user can choose **Build in Resolve** to create
and verify the timeline automatically;
**Update video** recompiles a later revision through the same selected delivery
mode. Studio automation can optionally render and upload a shareable review MP4
after timeline verification. The narration remains the writer's primary surface:
camera-state and visual events can begin or end inside a paragraph without
forcing the writer to split that paragraph into edit-sized rows.

Within that readable script, the writer can refine an individual use of a
logged clip, edit the English subtitle copy viewers will see for non-English
speech, and leave point-anchored Resolve production notes. Updating an existing
Studio edit opens a highlighted Regeneration Review with proposed row selections
and two-sided changes before a new timeline version is applied.

## 3. What the example script teaches us

The “OEV25 Finland” document is a useful real-world specimen. It is not simply a narration column and a link column. It mixes polished script, performance directions, section breaks, quoted clips, source URLs, time ranges, silent footage, still-image requests, named graphics, research citations, saved assets, alternates, and a long notes/drafts tail. The interface must support that messiness without forcing the writer to think like a database administrator.

- The left column usually holds narration, on-camera direction, jokes, pauses, pronunciations, and section structure.
- The right column may hold a clip, still, graphic, citation, URL, transcript excerpt, time range, instruction such as “clip with no audio,” or merely an unresolved idea.
- Some rows are left-only, right-only, or intentionally blank on one side.
- **One narration paragraph may continue across several picture cuts. Paragraph boundaries express writing structure, not edit boundaries.**
- **Host visibility is a continuous state independent of paragraph and row boundaries: on camera (OC) or off camera/voiceover (VO).**
- **When the host is off camera, visual coverage is required. The script must identify the clip, still, graphic, screen capture, or explicit unresolved placeholder visible for the entire VO span.**
- A clip reference may include a title, YouTube URL, in/out points, translated or quoted dialogue, desired audio policy, and commentary about the moment.
- Draft notes and abandoned material coexist with the active script. Build eligibility therefore cannot be inferred from document position alone.
- Early research often begins as topics, questions, and fragments with parent/child relationships rather than finished prose. That planning structure should remain useful before and during drafting without becoming accidental narration.
- Material removed from the current draft is not necessarily rejected. Writers need a deliberate holding area that preserves the full script fragment and makes restoration easy without relying on undo or revision-history archaeology.
- The script is optimized for humans collaborating on meaning. Machine semantics should appear progressively through cards, status, and an inspector—not through visible JSON, tags, or syntax.

## 4. Product principles

1. Human-readable first. A printed or exported script should still make sense without the application.
1. **Narration-first authoring. Paragraphs follow the flow of spoken language; camera changes and visual cuts attach to text ranges rather than dictating paragraph or row breaks.**
1. Structure beneath the surface. Every build-relevant row and asset has a stable ID and typed data even when it renders as ordinary text.
1. Collaboration does not trade away provenance. Concurrent edits converge into
   one attributed live history; comments, approvals, restores, and builds keep
   stable actor and revision evidence.
1. Version terms are not interchangeable. The live head, named checkpoints,
   standards/assets/rights revisions, build snapshots, and Resolve timeline or
   package versions have separate identities and lifecycles.
1. Active scope is explicit. The idea outline and Extras travel with the script but never enter narration, validation, prompter exports, duration estimates, voice generation, or video builds until the writer explicitly promotes or restores their content into the active draft.
1. The script is canonical; Resolve is compiled output. Editorial refinements can be preserved, but the Resolve timeline is not the only copy of authoring intent.
1. Source evidence and edit usage are separate. A logged clip, its source/English transcript tracks, a script-specific refined range, and editable subtitle copy remain independently identifiable and reversible.
1. Regeneration is reviewable. Script changes and recognized Resolve changes are compared against the last applied build; proposed row updates are visible and adjustable before any edited timeline is changed.
1. References before files. Reuse clip IDs, transcript versions, and asset identities. Do not duplicate downloads or silently create disconnected media.
1. Standards are inherited, not copied invisibly. Reusable team/project graphic
   and music standards use immutable revisions, explicit field-level override
   rules, fixed project bindings, and pinned occurrence snapshots. A newer
   revision is offered for comparison and never applied silently.
1. Immutable builds. Each build snapshots the synchronized script revision or
   approved checkpoint, media versions, voice model, graphic/music standard and
   implementation versions, rights evidence, resolved overrides, settings, and
   tool versions.
1. Honest incompleteness. Missing assets create visible placeholders or blocking issues; they do not disappear or receive invented substitutions.
1. Local media authority. Filesystem access, YouTube acquisition, FFmpeg, voice rendering, and Resolve automation run through a trusted local agent unless the user opts into a hosted provider.
1. Edition-aware delivery without split semantics. Resolve Free and Studio
   builds share one canonical manifest and prepared-media graph. Capability
   differences are explicit delivery results, not silent omissions or separate
   timing logic.
1. Replaceable providers. Voice, image generation, stock search, media acquisition, and Resolve integration stay behind narrow adapters.

## 5. Scope

### 5.1 MVP

- Sign in through the shared suite identity, enter a workspace, and create/open
  an explicitly authorized authoring project with timeline settings, a script,
  linked research projects, and a local output workspace. Authoring membership
  never substitutes for authorization to a linked research project.
- Support Workspace Owner, Workspace Administrator, Project Producer, Editor,
  Reviewer, and read-only Viewer capabilities as defined in section 6.11.
- Let multiple Editors work in Draft, Ideas, Extras, and typed cards at the same
  time with presence, per-user undo/redo, autosave/sync state, offline reconnect,
  and convergent conflict-safe editing.
- Add text/card-anchored comment threads with replies, stable-member mentions,
  notifications, and resolve/reopen behavior. Preserve ambiguous anchors as
  visibly stale rather than silently attaching them to nearby content.
- Keep attributed linear document history; create, name, compare, review,
  approve, and restore immutable checkpoints without erasing later history.
- Allow Editors and Producers to create preview builds from a fully synchronized
  working revision. Allow only a Producer to create a release build, and only
  from an approved named checkpoint.
- Select or detect a supported Resolve delivery profile: Free-compatible
  interchange or Studio automation. Show the exact edition/version capabilities
  before the first build and allow a project default plus per-build override.
- Create a script with no active draft yet and capture topics, questions, research leads, and writing tasks in a per-script outline with multi-level nesting, drag/reorder, indent/outdent, and open/incorporated state.
- Promote an outline item into the active draft at a chosen location while retaining its planning identity and marking/linking it as incorporated rather than silently deleting it.
- Move selected prose, complete rows, or structured script fragments from the active draft into a per-script **Extras** area; preserve rich text, typed cards, citations, and references, exclude the material from every build surface, and allow it to be restored at a chosen draft location.
- Edit a two-column document with section rows, narration rows, production-only rows, and media/graphic cards.
- **Mark narration ranges as on camera or voiceover without splitting the underlying paragraph; render on-camera words in a restrained semibold weight and voiceover words in normal weight.**
- **Attach multiple visual events to exact word ranges within one narration paragraph and reveal the relationship in both directions: hovering/selecting a visual highlights its covered words, and selecting words reveals covering visuals.**
- **Require complete visual coverage for VO spans, allowing an explicit unresolved placeholder while a shot is still undecided.**
- Accept common visual inputs as typed cards, including a logged research clip,
  a webpage URL, a direct image URL, and a local image or video file. Local
  files are imported directly and never need to pass through webpage/image
  capture. Resolve each source into a verified immutable media artifact before
  timeline placement.
- When adding a local image or video, let the writer explicitly copy, use a
  filesystem-supported copy-on-write clone, move, or reference the file in
  place. Default to clone with verified copy fallback. A move is never implicit:
  stage and hash-verify the project copy before removing the original, and
  retain the original plus an actionable warning if removal fails.
- Configure optional transition defaults independently for presenter→B-roll, B-roll→presenter, and B-roll→B-roll boundaries, with per-event overrides and an `Apply to everything` shortcut.
- **Export a narration-only plain-text prompter script with (OC) and (VO) inserted at every host-visibility transition.**
- Import a legacy two-column Google Doc into a review queue using heuristics; require confirmation of inferred row types and links.
- Insert clips already logged by the Research Video Transcript & Clip Extraction Tool and display their transcript text as the readable representation.
- Refine each use of a logged clip to a narrower script-specific in/out range
  without modifying the logged range, reusable research package, transcript, or
  another occurrence of the same clip. Preview the range, snap to honest spoken
  boundaries by default, allow frame-level adjustment, and reset reversibly.
- For foreign-, mixed-, or unknown-language speech, show editable English
  subtitle copy as the clip's primary readable script text with an explicit
  source-language/subtitles label. Preserve the immutable original transcript
  and baseline English translation separately; compile the approved copy into
  a required, versioned branded subtitle treatment for the edit.
- Insert a point video marker at a word, clip boundary, or position between
  blocks and attach an editable production note. Compile it into a native
  timeline marker where supported without affecting runtime or rendered video.
- Before each build, resolve every research clip to an exact verified compatible
  package; reuse reachable packages, offer verified relink for relocated media,
  and request durable re-export for missing or incompatible packages.
- Materialize research media into a persistent authoring-project media folder by
  copy or filesystem-supported copy-on-write clone by default. Never move or
  mutate the canonical research package.
- Accept direct media files and manually entered URL/time-range references, while clearly distinguishing resolved from unresolved assets.
- Generate computer voiceover for narration blocks with pronunciation and performance controls.
- Generate and cache replaceable temporary speech clips per narration block when a draft build is requested; unchanged blocks reuse verified audio.
- Place video clips, approved music cues, other audio, stills, and explicit
  placeholders onto predictable Resolve tracks.
- Discover workspace and project standard libraries. Pin project bindings and
  placed occurrences to exact immutable standard revisions, expose inherited
  and overridden values, enforce field-level override policy, and require an
  explicit comparison/migration before adopting a newer revision.
- Instantiate a small starter set of versioned graphic standards—lower third,
  quote, full-screen text, image-with-caption, and simple two-series chart—whose
  reusable configuration is distinct from its immutable Fusion/template
  implementation package and its placed occurrence.
- Place approved reusable music cues that pin an exact audio asset and rights
  snapshot plus cue range, loop, fades, gain/loudness, ducking intent,
  attribution, duration policy, and permitted occurrence overrides.
- Compile a new canonical rough-cut timeline manifest and build report; rerun
  safely against changed script blocks and deliver it through either supported
  edition mode.
- In Resolve Free mode, produce and verify a self-contained OTIO package plus
  FCPXML fallback and manual import instructions. Preserve unsupported
  Resolve-specific operations as baked assets, labeled placeholders, or explicit
  manual-completion items; never omit them silently.
- In Resolve Studio mode, build and verify a new rough-cut Resolve timeline
  automatically and rerun safely against changed script blocks.
- In Studio mode, optionally render a review-quality MP4 after timeline
  verification and upload the finalized file to a user-selected Google Drive
  folder. Free users may render normally inside Resolve after manual import;
  automated Resolve-side rendering is not promised in Free mode.
- Run applicable preparation, interchange, Studio assembly, render, and upload
  stages as a durable background job that survives a closed browser tab, reports
  progress, and supports safe retry. Free package preparation is a complete
  result without Studio-only stages.

### 5.2 Not MVP

- A complete browser-based nonlinear editor, color suite, audio mixer, compositing environment, or final delivery system.
- Fully autonomous research, fact checking, rights clearance, or editorial judgment.
- Arbitrary natural-language interpretation of every legacy production note without human confirmation.
- A large Fusion design system; template design and QA is a parallel workstream with its own acceptance process.
- Suggestion/track-changes mode, document branches and merges, mobile authoring,
  full Google Docs authoring/comment parity, or perfect bidirectional Google
  Docs synchronization. Live coediting, presence, anchored comments, and linear
  checkpoint history are in MVP.
- Automatic modification of a manually refined Resolve timeline without a diff, branch, or explicit overwrite choice.
- UI automation, mouse/keyboard scripting, or undocumented project-file editing
  to make Resolve Free imitate Studio's external API. Free support uses documented
  interchange and an explicit manual import.
- Automated Resolve-side render/upload in Free mode; Free users retain normal
  manual Resolve rendering, while Studio automation owns the MVP background
  render/delivery path.
- Arbitrary automatic merging of every possible Resolve edit. The later
  Regeneration Review supports recognized managed items, protected additions,
  explicit row selection, and conflicts; edits that cannot be mapped safely
  remain preserved for manual review.

## 6. Authoring experience

### 6.1 Main document

The default view should look intentionally close to Google Docs: a white page,
Arial typography, familiar text controls, page-like margins, section
navigation, per-user undo/redo, collaborator presence, and unobtrusive but
explicit sync/checkpoint status. The central content is a two-column grid with
no spreadsheet chrome. Rows expand naturally and can contain ordinary
paragraphs or structured cards. The left column is visually primary. On-camera
text uses a subtle semibold treatment (target CSS font-weight 600; bold only as
a fallback), while voiceover text stays normal weight. A small state control,
accessible label, and inspector value accompany the styling so camera state is
never communicated by weight alone.

| Left: spoken / performed                                    | Right: shown / heard / built                           |
| ----------------------------------------------------------- | ------------------------------------------------------ |
| Narration with inline OC/VO spans; OC words appear semibold | One or more visual cards anchored to exact word ranges |
| Stage direction or performance note                         | B-roll, still image, screen capture, or source link    |
| Section heading or beat                                     | Graphic template plus structured data                  |
| Blank                                                       | Production-only cue, music, transition, or clip        |
| Scratch / excluded draft                                    | Optional reference notes and unused alternatives       |

### 6.2 Idea outline and Extras

Each script has three explicit content surfaces: **Ideas**, **Draft**, and **Extras**. The Draft remains the primary page and the only build-eligible surface. Ideas and Extras are available from a collapsible side panel or focused full view so early research can lead naturally into writing without crowding the two-column document.

**Ideas is an outliner, not the document's section-navigation outline.** Every item can contain text and child items, and supports add-child/add-sibling, drag/reorder, indent/outdent, collapse/expand, and open/incorporated state. A script may exist with only Ideas populated. Promoting an item creates or inserts a chosen draft block, preserves a backlink to the originating idea, and marks the idea incorporated; the writer can reopen it or link it to a different block later. Incorporation state is informative and never controls build eligibility by itself.

**Extras is a loss-averse holding area for authored material that is not in the current draft.** `Move to Extras` is a first-class action for selected text, rows, or structured fragments. It preserves readable content, formatting, typed cards, citations, media references, provenance, and the source revision/location where practical. Moving a whole block preserves its stable identity. Restoring inserts the material at a writer-selected Draft location; duplicating it into the Draft creates new identities so the stored alternate remains available. References or text anchors that are no longer valid return visibly stale and require review rather than being silently discarded or rebound.

Ideas and Extras participate atomically in the same collaborative live head and
checkpoint as the Draft. Their counts and unresolved/stale state are visible,
but they do not create host-visibility or visual-coverage errors. They are
excluded from prompter/print exports by default, with an explicit appendix
option for human-readable exports only. Ordinary delete still exists with
per-user undo and checkpoint/history recovery; the application does not
silently convert every deletion into an Extra.

### 6.3 Progressive controls

- Typing stays immediate. A blank right cell behaves like text until the writer types @, pastes a URL, drags an asset, or chooses Insert.
- Insert opens clip search, local image/video import, stock/generated image
  request, approved graphic standard, approved music cue, placeholder, video
  marker, and citation choices. Dragging or choosing a local file opens the
  effective import action—`Clone/copy into project`, `Move into project`, or
  `Reference in place`—unless a visible
  project default already applies; the writer can override it before import.
- Selecting a structured card opens a right-hand inspector with timing, audio, crop, fit, handles, template inputs, provenance, and build status.
- Standard-backed cards show the pinned revision, project binding, inherited and
  overridden fields, locked-field explanations, and available-update comparison.
- **Hovering or selecting a right-column visual highlights the narration range it covers. Selecting narration can create a visual event or adjust an existing event's semantic start/end anchors.**
- Every row has an unobtrusive build-state indicator: excluded, ready, unresolved, generating, stale, failed, or built.
- A Preview timing mode estimates duration from generated or recorded narration and displays row-level time spans without turning the document into a timeline.
- A Resolve view shows the last build, track map, warnings, changed blocks, and
  the exact timeline/project destination. After a Studio timeline has diverged,
  it opens the highlighted Regeneration Review rather than applying an update
  immediately.
- The primary action first distinguishes **Preview** from **Release**, then
  reflects the selected delivery profile. Editors and Producers can preview the
  fully synchronized live head. Only Producers can release an approved named
  checkpoint. Resolve Free shows **Prepare Resolve timeline** and then **Update
  import package**. Resolve Studio shows **Build in Resolve** and then **Update
  video**; its menu exposes `Timeline only`, `Timeline + review MP4`, and
  `Timeline + review MP4 + Drive upload`.
  Edition, version, destination, unsupported-feature fallbacks, and sharing
  policy are visible before submission. Switching profiles creates a new build
  target from the frozen revision rather than mutating an earlier result.
- Build preparation summarizes how many media requirements will be reused,
  materialized, exported, relinked, or left unresolved, plus estimated new disk
  usage. It proceeds without interruption when policy resolves every item and
  opens a focused remediation view only for missing, incompatible, invalid, or
  authorization-blocked media.
- Reuse policy and project-media policy are separate controls. The recommended
  defaults are `Reuse verified; export missing/incompatible` and
  `Make project self-contained by copy/clone`. Advanced alternatives may
  reference verified media in place, forbid new exports, or explicitly
  re-export all clips.
- Each narration block shows its temporary-audio state—missing, queued, generating, ready, stale, locked, failed, or replaced by host recording—and can preview or regenerate only that block.

### 6.4 Narration-first visual anchoring

**Recommended model: keep each narration paragraph intact and add independent, range-anchored event lanes. A host-visibility lane records OC/VO spans. A visual lane records clips, stills, graphics, and placeholders. Both lanes use stable text anchors—block ID plus start/end token IDs or resilient relative positions—rather than new table rows.**

**A visual card in the right column shows a compact coverage label and aligns approximately with the relevant text. Hovering the card highlights its covered words on the left; hovering highlighted words emphasizes the corresponding card. Multiple cards can cover successive or overlapping ranges inside one paragraph. Full-frame visuals normally create a VO span over the same range; overlays can coexist with OC when the host remains visible.**

**Authoring anchors express meaning before exact audio timing exists. After generated or recorded narration is available, the compiler resolves text anchors to milliseconds/frames using provider speech marks or word alignment. Timing precision is visible. A secondary timing mode lets the editor fine-tune frame boundaries without changing the paragraph or its semantic anchors.**

#### Coverage rule

**Every spoken token belongs to exactly one host-visibility state. Every VO interval must be covered by at least one full-frame visual instruction or an explicit unresolved-visual placeholder. Gaps, contradictory overlaps, and visual events with no duration are build validation errors, not silent defaults.**

#### Alternative interaction models

- **Inline cut markers between words offer maximum immediacy and export cleanly, but they clutter the prose and make revisions fragile. They are best as an optional visibility mode, not the primary interface.**
- **One row per shot is simple to compile, but it makes editorial cuts control the writing structure and breaks continuous paragraphs. Reject this as the default.**
- **A miniature timeline under every paragraph is precise, but visually heavy during drafting. Use it only in the secondary timing/refinement mode.**
- **Sentence-level visual cards are easier to implement but cannot express mid-sentence cuts cleanly. They may be a prototype constraint, not the final data model.**

### 6.5 Row and block types

| Type                 | Readable rendering                                         | Build behavior                                                        |
| -------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------- |
| section              | Heading spanning the document                              | Chapter marker; optional timeline marker                              |
| narration            | Continuous paragraph; OC ranges semibold, VO ranges normal | Generates/references narration audio; carries host-visibility spans   |
| direction            | Parenthetical or muted text                                | Non-spoken; may create marker or actor note                           |
| clip                 | Title plus transcript excerpt                              | Resolves a stable clip reference and places chosen source/audio range |
| subtitle copy        | English viewer-facing text plus source-language badge      | Compiles reviewed branded captions without changing source evidence   |
| video marker         | Margin marker with expandable production note              | Emits a point timeline marker; contributes no duration                |
| visual               | Thumbnail, name, or request text                           | Places still/video or creates an explicit placeholder                 |
| graphic              | Standard name plus human-readable semantic values          | Resolves a pinned graphic standard/package and permitted overrides    |
| music/sfx            | Approved cue name, rights state, and instruction           | Resolves pinned audio/rights plus cue and mix-intent overrides        |
| citation             | Linked source                                              | Preserved in script/build report; no timeline item by default         |
| note/draft           | Ordinary scratch text                                      | Excluded unless promoted                                              |
| host-visibility span | OC or VO state over a narration range                      | Emits prompter markers and validates host visibility                  |
| visual event         | Right-column card linked to highlighted words              | Places a clip/still/graphic over the compiled time range              |

### 6.6 Prompter export

**The prompter export contains only spoken host narration, in document order. It excludes direction blocks, citations, visual notes, asset transcripts, graphics data, and excluded drafts. It always begins with a state marker and adds a new marker only when host visibility changes.**

**Default formatting places (OC) or (VO) on its own line immediately before the first affected word, even when the transition occurs inside an authoring paragraph. Paragraph wording and order remain unchanged. Section headings may be included as non-spoken navigation labels through an export option.**

**(OC)**

**We’re doing Finland for the third time in a row? Why in the Helsinki would we do that?**

**(VO)**

**All the clues are hidden in last season’s videos, if you have way too much time on your hands.**

**The export records the source document revision and is deterministic: the same revision and settings produce the same text file. Validation blocks export if any spoken range has no camera state.**

### 6.7 Refining a logged clip in the script

A logged clip keeps the original transcript selection and logged/export bounds
owned by the research project. Each `VisualEvent` that uses it receives an
independent `ClipUsageRange` owned by the script. The writer can shorten that
occurrence without changing the logged clip, canonical artifact, or another
occurrence of the same clip.

- A clip card exposes **Refine clip** and summarizes `Using 00:08 of 00:21`.
- Refinement opens a compact player with waveform/transcript context and
  draggable in/out handles. The default interaction snaps to verified word
  boundaries when available, falls back honestly to cue boundaries, and offers
  frame-level adjustment as an explicit precision mode.
- The use range may move inward anywhere inside the logged playable range but
  may not extend beyond it. Access to additional source handles is a separate
  research re-export/update operation, not a hidden expansion of the log.
- Preview loops only the proposed use range. **Reset to logged range** restores
  the full occurrence reversibly.
- The card and readable script representation immediately show only the
  transcript/subtitle content that overlaps the refined range. The build stores
  the exact chosen frames plus the timing precision and transcript evidence used
  to derive them.
- Refinement changes only the beginning and end in the first implementation.
  Removing words from the middle creates multiple occurrences or jump cuts and
  is deferred to an explicit multi-range feature.

If the selected research package does not contain the required refined range or
transition handles, normal artifact resolution requests a compatible immutable
export. It never mutates or stretches an existing package.

### 6.8 Editable English subtitle copy for non-English clips

For every clip occurrence containing foreign-, mixed-, or unknown-language
speech, the main scripting view shows the English words the audience will read,
not the source-language transcript. The card must make that representation
unambiguous, for example `Spanish · English subtitles`, and provide the source
transcript and baseline translation in its inspector for comparison.

The first English subtitle copy is derived from the exact immutable English
translation supplied by the research clip snapshot. It then becomes a
script-owned, occurrence-specific `SubtitleCopyTrack`:

- Editing subtitle copy changes only the viewer-facing English subtitles for
  this use of the clip in this script. It does not edit the media, research
  record, source-language transcript, baseline English translation, or another
  script occurrence.
- Each subtitle segment remains time-linked to immutable source evidence.
  Refining the clip removes segments outside the use range and clamps/rebases
  the remaining compiled events without rewriting their source timing.
- After a text edit, the system reflows lines over the existing speech-aligned
  timing and warns when reading speed, line length, line count, or safe-area
  constraints are exceeded. Material timing changes require an explicit timing
  edit rather than being inferred from rewritten prose.
- Machine-generated copy begins in `needs_review`. Approval or a human edit
  records the reviewer and revision. Low-confidence language/timing, mixed
  speech, and detected source-burned captions remain visible review states.
- Mixed-language clips apply this behavior at the timed segment level. English
  passages can remain ordinary quoted dialogue while non-English passages use
  subtitle copy; unknown language follows the safer subtitle-required path.

Every authoring project selects a versioned subtitle brand preset containing at
least font, weight, size, text/fill color, outline or background treatment,
screen position, margins/safe area, maximum lines, and optional speaker
treatment. The compiler emits semantic timed caption events plus the exact
preset version. Studio places and verifies the tested Resolve representation.
Free delivery must use a tested native, title-based, or baked representation
that preserves required visible English subtitles; a manual-completion item
alone is not an acceptable fallback for required non-English dialogue.

### 6.9 Script video markers

The writer can insert a point marker anywhere the compiled video has a semantic
position: on a specific word, at the start/end of a clip, or between two script
blocks. The marker has a stable ID and an editable production note intended for
work that will be completed in Resolve.

- The script margin shows a marker icon at its anchor; selecting it opens the
  note without adding visible syntax to the narration.
- The first nonempty note line becomes the Resolve marker name and the complete
  note becomes its description. Script-originated markers use a consistent
  project color and identity metadata where the delivery adapter supports it.
- Markers move with their semantic text/block anchor when preceding duration or
  document order changes. They never affect runtime and do not appear in a
  rendered video.
- If the anchored content is removed or its mapping becomes ambiguous, the
  marker becomes `unplaced` and requires reattachment or dismissal; it is never
  silently deleted or attached to nearby unrelated content.
- Regeneration updates or removes the matching script-owned timeline marker by
  stable identity instead of duplicating it. Editor-created Resolve markers are
  Resolve-owned and remain protected.

Point markers and notes are the initial scope. Marker duration, assignee,
status, keywords, annotations, and general task management can follow without
changing the point-anchor contract.

### 6.10 Regeneration Review mode

Studio **Update video** begins with a three-way comparison between the last
applied immutable build, the current script revision, and the current managed
Resolve timeline. The application opens a highlighted script view rather than
immediately rewriting the timeline. Each build-eligible row is one selectable
regeneration unit; expanding it reveals property-level changes and preserved
Resolve work.

| Row state                 | Script display                          | Default regeneration selection                 |
| ------------------------- | --------------------------------------- | ---------------------------------------------- |
| Script changed only       | Green highlight plus `Script changed`   | Selected                                       |
| Resolve changed only      | Purple highlight plus `Resolve changed` | Not selected                                   |
| Both changed, compatible  | Split highlight plus `Both changed`     | Selected; compatible Resolve work is preserved |
| Both changed, conflicting | Red outline plus `Conflict`             | Selected proposal, but blocked until reviewed  |
| Unchanged                 | No highlight                            | Hidden by default                              |

Labels and icons accompany color so state is accessible. Filters include
`Changed only`, `Conflicts`, `Script changes`, and `Resolve changes`, with
section-level selection and **Select all safe updates**. Rows changed on the
script side are proposed automatically, but the user may adjust every
non-blocked selection before applying it.

Selecting a row means: rebuild the script-owned contents of that row from the
current script while carrying forward compatible, recognized Resolve work.
Deselecting means: leave the current Resolve row untouched for this update and
record it as out of sync. It does not silently accept the Resolve representation
back into the script.

The expanded comparison shows the prior generated version, current script,
current Resolve observation, timing changes, protected work, and the exact
proposed result. A conflict offers only explicit outcomes:

- **Use script version**;
- **Keep Resolve version for now** and retain an out-of-sync row;
- **Adopt Resolve change into script** for a deliberately bounded reversible
  mapping such as a clean in/out refinement or subtitle-copy edit; or
- **Review manually in Resolve**.

Adoption never interprets arbitrary tracks, effects, or ripple edits as script
structure. Regeneration Review distinguishes script-equivalent editorial
changes—trim, replace, delete, move, duration, subtitle copy/timing, and
script-owned marker edits—from finishing work such as grades, effects, graphics,
mix changes, or protected-track additions. The latter appears as a summary such
as `3 Resolve additions preserved` rather than overwhelming the prose diff.

Before application, the review calculates dependency effects. A duration change
must state how much later material moves, which anchored Resolve additions move
with it, and which unanchored items require review. The default result is a new
versioned timeline; the sole edited timeline is never overwritten. Completion
reports regenerated rows, preserved Resolve work, deliberately out-of-sync
rows, and deferred conflicts.

### 6.11 Workspaces, membership, and roles

The suite identity supplies stable users and workspaces, but each authoring
project has an explicit membership list. A linked research project remains a
separate authorization boundary: membership in either project never grants
access to the other, and every clip read or build-time artifact request rechecks
the current research-project permission.

| Role                    | Initial authority                                                                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Workspace Owner         | Own/transfer the workspace and exercise Administrator authority                                                                                                                                  |
| Workspace Administrator | Manage workspace members and publish/deprecate workspace standards; no implicit access to private authoring projects                                                                             |
| Project Producer        | Manage authoring-project members/settings/links, publish project standards, approve checkpoints, create preview/release builds, choose release destinations, and apply Regeneration Review plans |
| Editor                  | Edit all three document surfaces and typed cards, comment, create/request review of checkpoints, draft standards, and create preview builds                                                      |
| Reviewer                | Read, comment, reply, mention, and approve or request changes on checkpoints; no direct script editing                                                                                           |
| Viewer                  | Read the document, history, comments, standards, and build results                                                                                                                               |

Workspace Owner/Administrator powers are governance powers rather than a hidden
content bypass; a private authoring project still requires project membership.
Every mutation records the stable actor. Role removal takes effect on the next
request and terminates write-capable collaboration sessions promptly. Unsynced
local text from a revoked Editor is preserved as a private recovery export but
is never committed after authority is lost.

### 6.12 Live collaboration and comments

Draft, Ideas, Extras, and their stable typed nodes form one collaborative
document transaction boundary. Multiple Editors may change different or
overlapping content concurrently without a whole-document lock.
ProseMirror/Tiptap with a CRDT such as Yjs is a strong candidate, but the
product contract is convergent operation-based editing, not a dependency on one
library.

- Presence shows active collaborators, connection state, and cursor or selected
  block/card when available. Presence is ephemeral and never changes document
  or build identity.
- Autosave distinguishes `local changes`, `syncing`, `synced`, `offline`, and
  `sync failed`. A preview cannot claim unsynchronized local changes; the action
  must wait for acknowledgment or state exactly which synchronized revision it
  will freeze.
- Undo/redo is per user and per editing session. It reverses that user's tracked
  operations rather than rewinding another collaborator's accepted work.
- Offline Editor operations merge when authorization and connectivity return.
  Semantic build validation may expose a temporarily invalid merged state, but
  the system never resolves it by deleting one participant's accepted text.
- Moving a typed subtree between Draft and Extras or promoting an Idea is one
  atomic collaborative transaction, preserving IDs where the operation is a
  move and creating new IDs where it is an explicit duplicate.

A comment thread anchors to a text range, block/card, Idea, Extra, or point
between blocks. It supports replies, stable-user mentions, resolve/reopen, and
an attributed edit history. Text anchors use collaborative relative positions
plus stable semantic IDs and quoted text as repair evidence. When deletion or
concurrent rewriting makes placement ambiguous, the thread becomes `stale` and
offers explicit reattachment; it never jumps silently. Mentions resolve only to
current eligible workspace/project members and create deduplicated, body-safe
notifications. Comments are authoring discussion and do not enter narration,
duration, prompter output, or the compiled timeline unless a separate typed
production marker is deliberately created.

Suggestion/track-changes mode, document branching, and arbitrary rich review
workflows are deferred. They must not be simulated through hidden duplicate
documents or by treating comments as script content.

### 6.13 Document history, checkpoints, and approvals

The product uses five separate version layers:

1. **Collaborative live head:** the current converged document state, identified
   by its acknowledged operation/state-vector evidence and materialized content
   hash.
2. **Document checkpoint:** an immutable named materialization of one live state
   for comparison, review, approval, restore, or release-build input.
3. **Dependency revision:** an immutable graphic package, standard, media asset,
   music-rights, voice, or other external dependency revision.
4. **Build snapshot:** the exact checkpoint or synchronized live revision plus
   every resolved dependency/settings version used by one compiler job.
5. **Delivery version:** the generated Resolve import package or Studio timeline
   produced from a build snapshot.

Accepted collaborative operations retain stable actor, client transaction,
server ordering, and timestamp evidence. The history UI groups that evidence
into readable attributed revisions and lets a user compare prose, structure,
Idea/Extra movement, typed-card properties, anchors, standards, and overrides.
It does not present unrelated standard or build versions as document revisions.

Editors and Producers can create a named checkpoint and request review.
Reviewers and Producers can approve it or request changes. Initial checkpoint
states are `draft`, `in_review`, `approved`, `changes_requested`, `superseded`,
and `approval_revoked`; state transitions are append-only review events. One
Reviewer or Producer approval is sufficient initially. New edits advance the
live head but never rewrite a checkpoint or its review evidence. Approval
revocation prevents future release builds from that checkpoint without
invalidating a completed build.

Restore creates a new live-head transaction whose content comes from the chosen
checkpoint. It preserves the checkpoint, all intervening history, comments, and
completed builds; it is never a destructive rewind or an implicit branch.

### 6.14 Preview and release builds

An Editor or Producer may create a **preview build** from the latest fully
synchronized live revision. The UI labels it as non-release, records the exact
acknowledged revision it froze, and shows immediately when the live head moves
ahead. Only a Producer may create a **release build**, and only from a currently
approved named checkpoint. A release here means an approved rough-cut compiler
input, not final legal, audio, color, or delivery approval.

Both actions produce immutable build snapshots and use the same Free/Studio
delivery adapters. Collaboration continues while a job runs, but later edits,
comments, approvals, restores, project-default changes, and standard revisions
cannot alter its input or retry. Media preparation may run concurrently, while
Studio application to the same Resolve project/timeline target is serialized
through an expiring target claim. Producers select release destinations and
apply Regeneration Review decisions; Editors may inspect or prepare preview
reviews without gaining authority to rewrite a release target.

Simultaneous script authoring never makes a Resolve timeline a collaboratively
edited source document. Resolve remains generated/editorial output governed by
the existing new-timeline default, protected-work rules, explicit three-way
review, target verification, and no-silent-overwrite policy.

## 7. Canonical content model

Do not compile directly from HTML, Google Docs table markup, or free-form prose.
The editor should persist one collaborative document tree whose nodes have
stable IDs and typed properties, plus an append-only attributed operation
history and immutable materialized checkpoints. ProseMirror/Tiptap with a CRDT
such as Yjs is a strong prototype candidate because custom block nodes,
relative positions, concurrent editing, and Google-Docs-like interactions are
established patterns, but the choice should be validated with a two-column
selection/clipboard/concurrency spike before commitment. Resource metadata,
comments, approvals, standards, and builds still use explicit optimistic
versions and idempotent commands; CRDT operations are not a substitute for
authorization or lifecycle rules.

Illustrative row shape:

**AuthoringWorkspace { id, name, ownerUserId, version }**

**WorkspaceMember { workspaceId, userId, role: owner | administrator | member, version }**

**AuthoringProject { id, workspaceId, title, linkedResearchProjectIds[], settings, version }**

**ProjectMember { projectId, userId, role: producer | editor | reviewer | viewer, version }**

**ScriptDocument { id, projectId, title, activeDraft, ideaOutline, extras, liveHeadSequence, liveStateVector, liveContentHash }**

**DocumentOperation { id, documentId, actorUserId, clientTransactionId, serverSequence, operationHash, acceptedAt }**

**DocumentCheckpoint { id, documentId, name, sourceSequence, stateVector, canonicalSnapshotHash, createdBy, createdAt }**

**CheckpointReviewEvent { id, checkpointId, actorUserId, action: request_review | approve | request_changes | supersede | revoke_approval, note, createdAt }**

**CommentThread { id, documentId, anchor, state: open | resolved | stale, createdBy, version }**

**CommentEntry { id, threadId, authorUserId, body, mentionedUserIds[], version, createdAt, editedAt }**

**IdeaItem { id, parentId, orderKey, text, state: open | incorporated, linkedDraftBlockIds[], collapsed, version }**

**StoredFragment { id, orderKey, contentTree, sourceBlockIds[], sourceRevision, sourceLocation, state: stored | stale, version }**

**NarrationBlock { id, orderKey, text, hostVisibilitySpans[], visualEvents[], timingPolicy, state, notes, version }**

**TextAnchorRange { blockId, startTokenId, endTokenId, startAffinity, endAffinity, quotedText, anchorVersion }**

**HostVisibilitySpan { id, range, state: on_camera | voiceover, source, version }**

**VisualEvent { id, range, source, presentationMode, framingPolicy, motionPreset, audioPolicy, layer, transitionIn, transitionOut, timingOverrides, status }**

**CompiledEventTiming { eventId, startMs, endMs, startFrame, endFrame, timingPrecision, alignmentVersion }**

**ClipUsageRange { id, visualEventId, loggedStartMs, loggedEndMs, useStartMs, useEndMs, startAnchor, endAnchor, timingPrecision, version }**

**SubtitleCopyTrack { id, visualEventId, sourceLanguage, baselineEnglishTrackId, baselineEnglishTrackVersion, segments[], reviewState, reviewerId, brandPresetId, brandPresetVersion, version }**

**SubtitleCopySegment { id, sourceSegmentIds[], sourceStartMs, sourceEndMs, englishText, timingOverride, version }**

**SubtitleBrandPreset { id, version, font, weight, size, fill, outlineOrBackground, position, margins, safeArea, maxLines, speakerTreatment }**

**ScriptVideoMarker { id, anchor, note, color, state: placed | unplaced, version }**

**StandardItem { id, workspaceId, scope: workspace | project, projectId?, kind: graphic | music_cue, name, currentRevisionId, version }**

**StandardRevision { id, standardId, revisionNumber, payload, overrideRules[], dependencyVersions[], previewArtifactId?, createdBy, createdAt }**

**StandardLifecycleEvent { id, standardRevisionId, actorUserId, action: publish_draft | approve | deprecate | archive, createdAt }**

**OverrideRule { fieldPath, allowedScopes: none | project | occurrence | project_and_occurrence }**

**ProjectStandardBinding { id, projectId, standardId, pinnedRevisionId, projectOverrides, resolvedHash, defaultUseCategories[], version }**

**GraphicTemplatePackage { id, version, fusionArtifactId, semanticSchema, dependencies, freeFallback, referenceRenderIds[], contentHash }**

**GraphicStandardPayload { templatePackageId, templatePackageVersion, semanticInputDefaults, styleDefaults, durationPolicy, layoutSupport, freeFallback }**

**GraphicUse { id, visualEventId, standardId, standardRevisionId, projectBindingVersion, semanticInputs, occurrenceOverrides, resolvedSnapshotHash }**

**MusicRightsSnapshot { id, audioAssetId, version, licenseSource, permittedUse, territories, expiresAt?, attribution, evidenceArtifactId?, status }**

**MusicCueStandardPayload { audioAssetId, audioAssetVersion, rightsSnapshotId, cueInMs, cueOutMs, loopPolicy, fadeInMs, fadeOutMs, gainOrLoudnessTarget, duckingPolicy, durationPolicy, attribution }**

**MusicCueUse { id, anchor, standardId, standardRevisionId, projectBindingVersion, occurrenceOverrides, resolvedSnapshotHash }**

MediaReference { id, kind, sourceSystem, sourceId, sourceUrl, versionSnapshot, transcriptSnapshot, requestedInOut, exportHandles, captureProfile, artifactId, provenance, status }

ArtifactRequirement { id, mediaReferenceId, clipSnapshot, requiredBounds, requiredHandles, conversionRequirements, languageArtifactPolicy, reusePolicy }

ResolvedArtifact { requirementId, artifactId, packageManifestHash, contentHashes, compatibility, availability, verifiedAt, sourceLocatorId }

MaterializedMedia { id, projectId, requirementId, artifactId, mode: clone | copy | move | reference, projectRelativeLocator, contentHashes, verifiedAt }

LocalMediaImport { id, projectId, mediaReferenceId, sourceLocator, sourceFingerprint, requestedMode: clone | copy | move | reference, completedMode, projectRelativeLocator, contentHashes, originalRemovalStatus, verifiedAt }

TransitionPolicy { presenterToBroll, brollToPresenter, brollToBroll }

TransitionSpec { kind, durationFrames, easing, templateId, templateVersion, audioBehavior }

GraphicInstance { id, graphicUseId, resolvedTemplatePackageId, resolvedTemplatePackageVersion, data, resolvedStyle, durationPolicy, validationState }

BuildSnapshot { id, class: preview | release, liveHeadSequence?, checkpointId?, checkpointApprovalEvidence?, canonicalDocumentHash, activeDraftBlockVersions, assetVersions, voiceSettings, resolvedStandardUses, rightsSnapshots, templatePackageVersions, timelineSettings, target, createdBy, status, manifestHash }

ResolveDeliveryProfile { mode: free_interchange | studio_automation, resolveVersion, resolveEdition, installationKind, capabilitySnapshot, interchangeFormats, studioApiAvailable }

ResolveImportPackage { id, buildId, manifestHash, otioArtifact, fcpxmlArtifact, mediaRoot, importInstructionsArtifact, manualCompletionItems[], verifiedAt }

ResolveSyncBaseline { id, timelineId, appliedBuildId, managedItemMap, observedTimelineFingerprint, createdAt }

RegenerationReview { id, baselineId, scriptRevision, resolveObservationId, rowChanges[], selectedRowIds[], decisions[], status }

RegenerationRowChange { rowId, scriptDelta, resolveDelta, compatibility, protectedWork[], dependencyImpact, proposedAction }

The collaborative document transaction and live-head identity cover Draft,
Ideas, and Extras together, but the compiler receives only `activeDraft`.
Moving a block between Draft and Extras is a reversible document operation, not
destructive deletion. A checkpoint materializes all three surfaces; a build
snapshot records the exact synchronized live head or approved checkpoint plus
the active block versions it compiled so later outline or Extra edits do not
rewrite the build or falsely imply that generated media is stale.

Implementation packages, reusable standards, project bindings, and placed uses
have separate IDs. Resolve each standard use in the order permitted occurrence
override → permitted project override → pinned standard revision. Validate every
field against the standard revision's override rules, then freeze the complete
resolved value and dependency revisions in the build. Updating a binding changes
future insertions only; migrating existing uses is an explicit document
operation that can be reviewed and reversed.

The baseline translation, editable subtitle copy, and compiled subtitle events
are separate versioned records. Likewise, absolute Resolve timecode is compiled
output: clip uses and script markers retain semantic anchors so they can move
with script content and participate in three-way regeneration review.

## 8. Integration with the research clip project

The existing project should remain authoritative for research clips, transcripts, source-video identity, transcript provenance, selected bounds, export bounds, notes/tags, and rendered clip packages. The authoring platform consumes those records through an API; it should not scrape the spreadsheet or duplicate YouTube/transcript logic.

1. The writer searches project clips by project, tags, note, source title, or transcript text.
1. Dropping a result onto selected narration creates a VisualEvent whose assetReference points to the stable project clip ID. It snapshots the readable transcript plus selected version/bounds while its TextAnchorRange states exactly which words the clip covers.
1. The new occurrence begins with the complete logged range. Any later in/out
   refinement is stored as a script-owned use range inside that immutable logged
   range; it never patches the research record or another occurrence.
1. A foreign/mixed/unknown-language occurrence derives editable English
   subtitle copy from the snapshotted English track while retaining the exact
   original and baseline-English identities for reference and rebuilds.
1. At build time, the authoring client asks the research artifact resolver for an
   exact package matching the clip snapshot, required bounds/handles,
   language-policy files, and conversion requirements.
1. If a compatible artifact is reachable, the resolver verifies its manifest and
   required hashes before the build reuses it. A catalog status of `complete`
   alone is not a cache hit.
1. If the expected locator is missing, the local agent searches only configured
   artifact roots or asks the user to locate the package. A located candidate is
   accepted only after its manifest, clip snapshot, and hashes verify.
1. If no verified compatible artifact is reachable, the authoring build requests
   a new immutable export through the existing durable export boundary and
   waits, fails clearly, or builds with a placeholder according to policy.
1. Script-specific choices—mute source audio, use only part of the exported range, crop, layer, speed, or placement duration—remain usage overrides and do not mutate the research clip.
1. If the research record changes, the script shows “update available” and offers keep snapshot, update reference, or compare. It never silently retargets the edit.

**Recommended ownership boundary:**

- Research project owns source acquisition, transcripts, clip logging, rights/provenance notes, clip export, and reusable clip artifacts.
- Authoring project owns narrative order, usage of a clip in a particular video, voiceover, graphics, visual requests, timeline placement, and build history.
- Resolve bridge owns deterministic translation from one build snapshot into a local Resolve project/timeline and the reconciliation report.

### 8.1 Build-time media resolution and materialization

Artifact identity and file placement are separate concerns. The immutable
research artifact/package ID, manifest, and content hashes identify reusable
media. Local paths, object keys, temporary download grants, and project-local
copies are locators. The build must verify actual bytes; it must not infer
availability from a remembered path or a completed export record.

When either Free or Studio delivery action freezes a revision, create an
`ArtifactRequirement` for every research clip and produce a media-preparation
plan before timeline compilation:

| Resolution state                                       | Default action                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------- |
| Exact, compatible, reachable, and hash-verified        | Reuse and materialize into the authoring project                       |
| Reachable but incompatible or lacking required handles | Request a new immutable export                                         |
| Completed record with a missing locator                | Search configured roots, then offer verified `Locate`                  |
| User-located package                                   | Accept only after manifest/snapshot/hash verification                  |
| Still missing                                          | Request durable re-export from the frozen clip snapshot                |
| Source unavailable or unauthorized                     | Block or use an explicit labeled placeholder according to build policy |

Keep two settings independent:

- **Reuse policy:** `Reuse verified; export missing/incompatible` (default),
  `Re-export all`, or `Reuse only; do not start exports`.
- **Project media policy:** `Make project self-contained by copy/clone` (default),
  `Reference verified media in place`, or `Ask for each source`.

Research packages and writer-owned local files have different move authority.
The authoring product may never move a canonical research package. For a local
image or video explicitly supplied by the writer, the project default or import
dialog may choose `Clone/copy into project`, `Move into project`, `Reference in
place`, or `Ask each time`. The recommended default is copy-on-write clone with
verified copy fallback. `Move` requires a separate explicit choice and uses a
copy-to-private-staging, media/hash verification, and atomic-promotion sequence
before attempting to remove the original. Cross-volume moves use the same
copy-verify-promote-delete protocol rather than trusting a rename. If original
removal fails, retain both verified files, record the effective result as a copy,
and show the cleanup warning; never discard the only verified bytes.

The default authoring workspace keeps reusable media outside individual build
directories so later builds can reuse it without multiplying copies:

```text
Authoring Project/
  Media/
    Research Clips/
      <clip-id>/<artifact-id>/
        <verified package files>
    Local Images/
      <asset-id>/<original-filename>
    Local Clips/
      <asset-id>/<original-filename>
  Builds/
    <build-id>/
      timeline-manifest.json
      build-report.json
```

Prefer a filesystem-supported copy-on-write clone when it preserves independent
consumer bytes; otherwise copy. Referencing in place is an advanced, less
portable option. Do not move the research package. A writer-owned local source
may be moved only through the explicit verified import path above. Do not use
ordinary hard links when later mutation could alter canonical bytes. Record the
materialized artifact ID, import/materialization mode, project-relative locator,
hashes, and verification time in the build snapshot.

`Re-export all` creates new immutable research artifact versions using the
frozen requirements; it never overwrites prior packages or silently changes an
earlier build. If a project-local copy is deleted later, the next build attempts
verified rematerialization from the canonical package, then verified relink,
then durable re-export. If reacquisition is impossible, preserve the clip
reference and transcript and expose missing media rather than substituting
unrelated footage.

## 9. Voiceover subsystem

- Temporary speech is an editing aid, not the intended final performance. The system must make that status obvious in the script, build report, Resolve metadata, and review export.
- Generate audio per narration block (the default row-level unit), not as one monolithic file. Stable block IDs enable partial regeneration and precise timeline replacement. Long blocks may be internally chunked for provider limits, but finalize as one logical block asset with continuous timing metadata.
- The first Free preparation or Studio build action creates speech only for
  missing or stale narration blocks. Reuse a verified block asset when its text,
  voice profile, pronunciation dictionary, synthesis settings, provider/model
  version, and normalization profile hashes are unchanged.
- **Preserve word/speech-mark timing when the provider supplies it; otherwise run alignment or expose honest sentence/cue precision. Range anchors must not be presented as frame-exact until compiled timing is verified.**
- Store plain text separately from provider-specific synthesis input. Support pronunciation dictionary entries, phoneme/alias overrides, emphasis, pacing, pause, and named voice/profile.
- Record provider, model, voice version, settings, input hash, output hash, duration, sample rate, and generation time.
- Allow locked audio: once a human recording or approved synthetic take is attached, a normal rebuild must not regenerate it.
- A recorded host take can replace a temporary block asset while preserving the block ID and editorial intent. Because the real performance may have a different duration, replacement triggers a timing-impact preview and a new compiled timeline rather than silently stretching or overwriting the edit.
- Create audible and visible placeholders when synthesis fails. Never compress the remaining timeline and hide a missing line.
- Normalize loudness and sample format through the media worker, but treat final mixing as editorial work in Resolve.
- **Generate the plain-text prompter artifact from host-visibility spans independently of whether the timeline uses synthetic or recorded narration.**

### 9.1 Speech provider boundary

Define a narrow `SpeechSynthesisProvider` contract that accepts normalized block text, voice/profile settings, pronunciations, and requested timing output, then returns audio plus timing/provenance metadata. Compare at least one cloud provider and one local/offline provider before choosing a default. The build model must not encode vendor-specific voices, SSML, identifiers, or billing assumptions.

### 9.2 Narration artifact identity

`NarrationAudioAsset { id, blockId, blockRevision, kind: temp_synthetic | host_recording, textHash, synthesisProfileHash, provider, model, voiceVersion, audioHash, durationMs, timingPrecision, timingArtifact, normalizationProfile, status }`

Temporary audio should be stored as an immutable artifact. Regeneration creates a new version and never mutates the asset used by a previous build snapshot.

## 10. Visual assets and B-roll

- A visual request begins as intent: description, purpose, desired duration, aspect/crop policy, source preference, and rights note.
- It can resolve to a research clip, uploaded file, generated image, licensed stock item, URL-backed reference, screen capture, or placeholder slate.
- Generated images must preserve prompt, model, seed/settings when available, generation policy, and content hash. The writer explicitly selects the accepted candidate.
- URLs are references, not durable media. A local build must resolve them into authorized, checksum-tracked artifacts before final placement.
- Stills receive a default motion preset only when the author chooses one; the compiler should not invent pans and zooms globally.
- Every asset card exposes fit/fill, crop focus, in/out, speed, source-audio policy, attribution, and rights status where relevant.
- **Each visual event exposes its covered narration text, semantic start/end anchors, compiled timing, timing precision, presentation mode (full frame, overlay, picture-in-picture, background), and coverage validation state.**

### 10.1 Common visual-source presets

These are common typed inputs, not an exclusive list:

| Input                | Resolution behavior                                                                                                                                                                                        | Default composition behavior                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Logged research clip | Resolve the stable project clip/version; reuse its verified export when available or request the existing durable export pipeline to download, trim with handles, convert, and finalize it                 | Full-frame B-roll using the chosen source-audio policy; no invented retiming                                    |
| Webpage URL          | Capture through a versioned webpage-capture adapter using a recorded viewport, device scale, final URL, capture time, and capture profile; persist the resulting image as an immutable artifact            | Full-frame capture with a slow top-left-anchored drift over the visual event's duration                         |
| Direct image URL     | Download the original full-resolution asset once when added, verify media type and dimensions, hash it, and preserve source/provenance metadata; do not schedule recurring acquisition                     | Scale to the largest size that keeps the entire image visible; preserve aspect ratio; no animation by default   |
| Local image file     | Import directly through the selected clone/copy, move, or reference policy; decode, hash, and verify the finalized project artifact without invoking a capture provider                                    | Scale to the largest size that keeps the entire image visible; preserve aspect ratio; no animation by default   |
| Local video file     | Import directly through the selected clone/copy, move, or reference policy; inspect streams/duration, hash, and verify the finalized project artifact without invoking webpage or remote-media acquisition | Use the selected in/out, audio, framing, speed, and placement policy; never transcode merely to complete import |

For image aspect ratios that do not match the timeline, “fill without cutting anything off” means **contain**, not crop: the complete image is visible, with letterbox/pillarbox space filled by a project background preset. Stretching and silent cropping are prohibited. The writer can explicitly choose crop-to-fill or a motion preset as an override.

The webpage default is a still capture plus a motion transform, not live web content embedded in Resolve. The card should preview the selected viewport or region before build. Public pages can be captured by a local headless-browser worker; no browser extension is required. Authenticated, paywalled, or session-dependent pages are deferred to an explicitly authorized attached-browser flow or a user-supplied screenshot. The MVP must not copy browser cookies into a background worker silently.

Web capture must record the requested URL, final URL after redirects, page title, capture timestamp, viewport, device scale, capture-adapter/version, artifact hash, and any load warnings. Dynamic pages, consent overlays, failed fonts/images, blocked automation, and pages that change between revisions must be visible failure or review states rather than hidden differences. A hosted capture service must reject private/local-network targets and apply normal SSRF protections.

Source preservation is type-specific. A direct image URL is acquired once when
added, and a local image/video is imported once; neither receives a recurring
capture schedule. A webpage may use `Off`, `Capture when added`, or `Capture when
added + monitor daily/weekly`. Monitoring creates immutable candidate revisions
only when the rendered result changes materially, preserves every version used
by a build, and shows `Newer capture available` without silently changing the
card's selected revision. Manual recapture remains available for any remote
source, but only webpages are monitored automatically.

### 10.2 Transition policy

Transitions are properties of visual boundaries, not narration paragraphs. A project/video may set three independent defaults:

- `presenterToBroll`: the presenter is visible before the boundary and a full-frame B-roll source begins.
- `brollToPresenter`: a full-frame B-roll source ends and the presenter becomes visible.
- `brollToBroll`: one full-frame B-roll source changes to another.

Each slot may be `cut` or a versioned transition specification with type, duration, easing, and optional Fusion/template identity. `Apply to everything` copies one selection into all three slots as a convenience; the slots remain independently editable afterward. A visual event can override either adjacent boundary without changing project defaults.

The compiler classifies each boundary from the OC/VO state plus the neighboring events, resolves the effective transition in this order—boundary override, event/type preset, project default, hard cut—and writes the result into the immutable build snapshot. Transitions affect picture only by default; audio crossfades or source-audio behavior require an explicit audio setting.

Transition duration must fit the available handles and adjacent event durations. When it does not, validation should ask the writer to shorten the transition, extend the event/handles, or use a cut; the compiler must not silently move narration anchors or steal time from another visual.

## 11. Reusable standard-item system

Workspace and project libraries hold reusable approved standards for repeated
production choices. Four identities remain separate:

1. An immutable implementation asset, such as a Fusion package or audio file.
2. A reusable standard with immutable configured revisions.
3. A project binding that pins one revision and applies permitted project
   overrides/default-use categories.
4. A placed occurrence that pins the binding/revision and stores semantic
   inputs plus permitted occurrence overrides.

Workspace Owners/Administrators publish and deprecate workspace standards.
Project Producers publish project standards and project bindings. Editors may
prepare drafts but cannot make them approved defaults. Standard revisions use
`draft`, `approved`, `deprecated`, and `archived` lifecycle states recorded by
append-only lifecycle events. Publication creates a new immutable payload
revision; later lifecycle events never edit the configured values used by an
existing project, occurrence, checkpoint, or build.

Each configurable semantic field declares whether it is `locked`,
`project_overridable`, `occurrence_overridable`, or
`project_and_occurrence_overridable`. A project cannot loosen a workspace lock,
and an occurrence cannot override a project-locked effective value. The
inspector distinguishes inherited, overridden, invalid, and reset-to-standard
states. Resolve effective values in this order: permitted occurrence override,
permitted project override, then pinned standard revision. Missing required
values or prohibited override paths fail validation rather than falling back
silently.

Project bindings and placed occurrences remain pinned when a newer approved
revision appears. The UI shows `Update available`, compares the effective old
and proposed values/dependencies, and requires an explicit binding update or
selected occurrence migration. Updating a binding affects future insertions;
existing occurrences change only through an explicit migration recorded as a
normal reversible document revision. `Save as project standard` creates a new
draft standard instead of mutating the source standard.

### 11.1 Graphic implementation packages and standards

Template design is a separate creative/engineering workstream, but the authoring
contract should be defined early. Each graphic implementation is a versioned
package with a stable ID, Resolve/Fusion artifact, preview, semantic input
schema, default duration, safe-area/aspect support, fonts, dependencies, and
validation fixture. It must also declare its Resolve Free delivery behavior:
`interchange_native`, `baked_media`, or `manual_placeholder`. The build report
must identify the chosen fallback and never claim that an interchange package
contains a live Fusion composition when it does not.

| Package contract field | Example                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| Semantic inputs        | name, job_title, quote, value_a, value_b, source_label                |
| Data types             | short text, long text, number, percent, date, image, color, series    |
| Constraints            | max characters, min/max values, required fields, line limits          |
| Timing                 | fixed, stretchable, intro/hold/outro, minimum duration                |
| Layout support         | 16:9 initially; explicit 9:16/1:1 variants later                      |
| Versioning             | new immutable version when animation, schema, font, or layout changes |
| Verification           | reference render, edge-case fixture, missing-font/dependency check    |
| Resolve Free fallback  | interchange-native title, baked media, or explicit manual placeholder |

A graphic standard pins one package version and configures reusable style,
timing, layout, Free fallback, and semantic-input defaults. Variable production
content such as a person's name, quote, image, source label, or chart series is
an instance input governed by the semantic schema, not an unrestricted style
override. A placed graphic stores the exact standard revision, package version,
project-binding version, instance data, permitted overrides, and resolved hash.

The UI renders semantic inputs as a small form and shows the result in readable
prose inside the script. For example, a lower third card can read “Erika Vikman
— Singer” while storing the standard/package identities, fields, duration, and
style variant. Avoid exposing raw Fusion node names to writers.

### 11.2 Approved music cue standards

A reusable music standard represents an exact approved cue, not merely a mood
label or a mutable search result. It pins:

- an immutable audio asset identity/version and verified content hash;
- an immutable rights snapshot with license source, permitted use, territory,
  optional expiry, attribution, and evidence status;
- cue in/out, loop policy, fade-in/out, gain or loudness target, narration
  ducking intent, and fixed/stretch/fill duration policy; and
- field-level project and occurrence override permissions.

A music occurrence anchors to a script range, block, section, or explicit
timeline region and stores its standard revision, project-binding version,
permitted use overrides, and fully resolved snapshot hash. An override changes
only that occurrence; it never edits the approved cue, audio asset, rights
record, or another occurrence. Updating or replacing the standard follows the
same pinned comparison/migration policy as graphics.

Release validation blocks a cue whose audio bytes are missing or unverifiable,
whose rights are expired/unverified for the declared use, or whose required
attribution cannot be represented. A preview may proceed only when project
policy permits it and must carry a prominent non-release rights warning in the
script and build report. The compiler implements tested gain/fade/ducking
behavior where the delivery mode supports it and otherwise uses an explicit
baked or manual-completion result; it never omits music or mix intent silently.

## 12. DaVinci Resolve output architecture

### 12.1 Shared compiler with two delivery adapters

Compile every build first into one editor-neutral canonical timeline manifest.
Resolve all source media, narration timing, visual events, transitions, graphics
requirements, frame calculations, and provenance before choosing an edition
adapter. Generate OTIO as the primary interchange artifact and FCPXML as a
verified compatibility fallback for both modes.

This architecture prevents the product from depending entirely on undocumented
project-file internals while acknowledging that interchange formats do not fully
express Fusion templates, custom metadata, and all Resolve-specific settings.
The canonical manifest remains the authoritative expected timeline for both
editions.

#### Resolve Free adapter

The Free adapter requires no Resolve scripting API. It writes a versioned,
self-contained `Resolve Import Package` containing:

- canonical timeline manifest and human-readable build report;
- `.otio` plus `.fcpxml` fallback;
- verified project-relative media and narration files;
- baked graphic/transition assets when a template supplies a Free-compatible
  renderer;
- labeled placeholder events and an exact manual-completion checklist for
  unsupported Resolve-specific behavior; and
- edition/version-specific import instructions using `File > Import > Timeline`.

The application verifies package structure, paths, hashes, frame rate, duration,
and interchange parseability before declaring it ready. Because it cannot query
Resolve Free externally through a supported API, final in-application placement
verification is a user-confirmed post-import step. The app must describe that
boundary honestly and keep the import package useful even when Resolve is not
installed on the authoring machine.

#### Resolve Studio adapter

Studio mode begins with the exact same verified import package, then uses
Resolve's Python/Lua scripting API for project creation, bins, exact track setup,
media import, timeline item placement, markers, Fusion title/generator insertion,
timeline verification, and optional rendering. The installed Resolve scripting
documentation confirms those API capabilities. The adapter must require a
supported standard desktop Studio installation with external scripting enabled;
it must not silently fall back to UI automation or assume the Mac App Store build
exposes external control.

#### Capability matrix

| Capability                                   | Resolve Free mode                                                         | Resolve Studio mode                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Authoring, media preparation, voice, timing  | Full                                                                      | Full                                                                        |
| Canonical manifest and OTIO/FCPXML           | Full                                                                      | Full                                                                        |
| Timeline creation in Resolve                 | One manual import                                                         | Automated through supported API                                             |
| Resolve-specific bins/metadata/custom data   | Best-effort interchange plus manual checklist                             | Automated and verified                                                      |
| Fusion/template behavior                     | Native interchange, baked asset, or placeholder                           | Live versioned Fusion insertion when tested                                 |
| Approved music cue and mix intent            | Native interchange when tested; otherwise baked/manual result is reported | Versioned audio placement and tested gain/fade/ducking automation, verified |
| Required non-English subtitle copy           | Tested native/title/baked visible representation                          | Versioned branded timeline representation, verified                         |
| Script video markers                         | Native interchange when tested; otherwise report                          | Native stable-ID marker placement and verification                          |
| Resolve-side timeline verification           | User-confirmed after import                                               | Automated against canonical manifest                                        |
| Resolve-side review render and Drive handoff | Manual render/upload                                                      | Optional durable automation                                                 |
| Update behavior                              | Generate/import a new immutable timeline                                  | Three-way review, selective plan, then a new verified timeline by default   |

### 12.2 Predictable track map

| Track | Default purpose                                                                 |
| ----- | ------------------------------------------------------------------------------- |
| V1    | Primary picture or presenter/A-roll placeholder                                 |
| V2    | Research clips and featured source footage                                      |
| V3    | B-roll and still images                                                         |
| V4    | Fusion graphics, titles, and overlays                                           |
| V5    | Debug slates or unresolved placeholders; disabled for clean review when desired |
| A1–A2 | Generated or recorded narration                                                 |
| A3–A4 | Source clip audio                                                               |
| A5    | Approved music cues and sound effects                                           |
| S1    | Required English subtitle copy for non-English/mixed/unknown speech             |

### 12.3 Build sequence

1. Authorize the requested build class, then freeze an immutable build snapshot
   from either the acknowledged collaborative live head (`preview`) or an
   approved named checkpoint (`release`). Validate row order, timeline rate,
   asset identities, graphic/music data, rights evidence, and voice settings.
1. Resolve every graphic/music use through its pinned implementation asset,
   standard revision, project binding, and permitted occurrence overrides.
   Validate field policy and freeze the complete effective values; never consult
   a newer current revision during this build or retry.
1. Build the media-preparation plan. Resolve exact research artifact candidates,
   verify manifests/hashes and compatibility, classify missing or invalid
   locators, and freeze the effective reuse/project-media policies.
1. Resolve or generate changed narration, clip packages, stills, and graphics
   dependencies. Reuse or re-export according to the plan, then copy/clone or
   reference verified packages into the authoring workspace. Record hashes,
   materialization locators, and actionable failures.
1. **Calculate durations. Narration is the default timing spine. Resolve text anchors to verified speech timing, compile OC/VO spans and visual-event ranges into integer frames, then apply explicit timing overrides and transitions. Report anchor/alignment precision rather than implying exactness.**
1. Resolve each logged clip occurrence's script-specific use range against the
   immutable logged range and verified media. Compile approved English subtitle
   copy for foreign/mixed/unknown speech into timed events using the frozen
   subtitle brand preset, and validate reading speed, line layout, safe area,
   and complete coverage of the refined range.
1. Resolve every visual source into a verified immutable artifact. Logged clips use the research export boundary; webpage URLs use the capture adapter and motion preset; image URLs/files use full-resolution acquisition plus the chosen framing policy.
1. Classify visual boundaries and compile effective presenter→B-roll, B-roll→presenter, and B-roll→B-roll transition specifications, validating available duration and handles.
1. Emit a canonical timeline manifest using integer frames at the project rate,
   including every placed/unplaced script video marker, plus a human-readable
   build report.
1. Generate and parse-verify OTIO and FCPXML against the canonical manifest,
   materialize project-relative media, and finalize the immutable Resolve Import
   Package. Classify every non-representable item as baked, placeholder, or
   manual completion rather than dropping it.
1. For Resolve Free, stop at `ready_to_import`, show exact import instructions,
   and let the user confirm the imported timeline/build ID without implying that
   Resolve placement was automatically inspected.
1. For Resolve Studio, create or select the target project, import the verified
   package into deterministic bins, create a new timeline named from the build
   ID/revision, place or enhance timeline items, insert supported Fusion
   templates, and add row/build IDs as marker custom data where supported.
1. In Studio mode, save the Resolve project, verify item counts/durations/track
   names against the manifest, and report discrepancies. Optionally export a
   DRT backup; retain the OTIO/FCPXML package for recovery and portability.

### 12.4 Rebuild safety

Initial builds should always create a new timeline. Resolve Free updates produce
a new immutable import package and are imported as a new timeline by default.
Studio records a `ResolveSyncBaseline` only after the generated timeline has
been verified against the canonical manifest. Every managed clip occurrence,
subtitle event, script marker, narration block, and graphic keeps a stable
identity across builds where its authoring identity survives.

Studio incremental rebuilds may update a generated timeline only through
Regeneration Review. The bridge compares the last applied baseline with both
the current script and current Resolve timeline, then classifies untouched
managed items, recognized manual edits, protected additions, compatible
two-sided changes, and conflicts. A user-created item is Resolve-owned by
default. A generated item is script-owned for its managed editorial properties,
but compatible finishing work attached to it is preserved where the adapter can
prove the mapping.

Arbitrary ripple edits, replacements, transition changes across a modified cut,
and effects whose attachment cannot be established are conflicts rather than
guessed merges. If a script anchor is deleted, attached Resolve-owned work moves
to an orphaned/disabled review area or remains on the preserved prior timeline;
it is never silently deleted. Never rebuild over the sole edited timeline in
either edition.

### 12.5 Regeneration review and selective update

The Review view defined in section 6.10 is the required entry point for Studio
updates after Resolve has diverged. It operates at script-row granularity for
selection and property granularity for conflict explanation.

Rows changed in the script are selected automatically. An authorized Producer
can deselect them, select additional rows, use section selection, or choose
**Select all safe updates**. A selected row regenerates only its managed
contents and preserves compatible Resolve-owned work. An unselected changed row
stays untouched and is recorded as out of sync so a later review compares it
against the same applied baseline instead of pretending synchronization
succeeded.

Resolve-only structural changes are visible but not automatically imported into
the script. The initial bounded **Adopt Resolve change into script** actions are
clean per-occurrence in/out refinements and English subtitle-copy edits; both
create ordinary reversible script revisions. Everything else offers keep-for-now,
use-script, or manual-review decisions.

Applying the plan requires current Producer authority, creates a new timeline
version by default, verifies every selected managed result against the plan,
writes a new immutable sync baseline, and retains the prior timeline and review
record. A partial failure leaves the prior timeline authoritative and the
review retryable; it must not report rows as applied merely because some API
calls succeeded.

### 12.6 Review render and delivery

After Studio timeline assembly passes manifest verification, the build may
continue through two optional stages:

1. Render a review preset to a staging path, normally H.264/AAC MP4 with project-standard resolution and frame rate.
1. Inspect the output with FFprobe and validate duration, streams, nonzero size, and expected build/revision metadata.
1. Atomically promote the verified MP4 into the project's completed-artifact directory.
1. If Drive delivery was requested, upload that immutable artifact through a `ReviewDeliveryProvider`, initially Google Drive, using a resumable upload where supported.
1. Verify the remote file identity/size, record its Drive file ID and URL, then mark delivery complete. Sharing permissions are an explicit separate choice; uploading must not silently make the file public.

The local MP4 remains a successful artifact if Drive upload fails. The upload
stage can be retried without rebuilding or rerendering. A new script revision
produces a new review artifact; it does not overwrite an earlier shared review
unless the user explicitly selects a version-replacement policy. Resolve Free
users can render and upload manually after import; automated Resolve-side render
and delivery are capability-labeled Studio features unless a separate
edition-independent review renderer is deliberately added later.

### 12.7 Background build experience

Submitting either delivery action freezes the authorized source—an acknowledged
live revision for preview or an approved checkpoint for release—and creates a
durable `VideoBuildJob`. The browser may close without canceling it.
Both modes report `queued → generating speech → resolving media → compiling →
writing interchange → verifying import package`. Free then reports
`ready_to_import → import_confirmed` when the user confirms the result. Studio
continues through `building Resolve timeline → verifying timeline → rendering
MP4 → verifying MP4 → uploading → complete`, while unrequested stages are
labeled as skipped rather than hidden.

Jobs use idempotency keys, attempts, progress, cancellation boundaries, and
worker leases. Retry resumes from the last verified immutable artifact whenever
possible. Free import-package creation requires the local agent for filesystem
media preparation but does not require Resolve to be installed or open. Studio
automation requires a running supported Resolve installation; sleep, shutdown,
closed Resolve, disabled scripting, or license mismatch moves the job into a
resumable waiting/needs-action state rather than losing it. Completion
notification can begin as in-app status and later add email/desktop adapters.

### 12.8 Collaborative build behavior

Build submission first resolves the requested source into one immutable input:

- A preview build references the latest server-acknowledged collaborative live
  head sequence/state vector and canonical content hash. An Editor or Producer
  may submit it. Unsynchronized local edits must finish syncing or be visibly
  excluded from the frozen input.
- A release build references one approved named checkpoint plus its current
  approval evidence. Only a Producer may submit it. Approval is rechecked at
  submission; later revocation blocks new release builds but does not alter a
  previously accepted job.

The build resolves every standard occurrence to pinned implementation/standard/
binding revisions, permitted overrides, media or music-rights evidence, and a
complete effective snapshot before durable work begins. No stage or retry asks
for `latest`. Other collaborators may continue editing, commenting, approving,
or publishing standards while the job runs; the build UI shows its frozen
revision/checkpoint and whether the live head has advanced.

Preparation jobs may share immutable cached dependencies, but two Studio jobs
must not concurrently mutate the same Resolve project/timeline target. Use an
expiring target claim with visible owner/job identity and safe recovery. The
default output remains a new timeline/version. Applying a Regeneration Review
plan requires Producer authority, revalidates its baseline/target identity, and
never interprets live coauthoring as permission to overwrite Resolve work.

## 13. System architecture

- Web client: collaborative structured document editor, presence/sync state,
  comments, history/checkpoint review, standard library and override inspectors,
  clip/asset search, preview timing, and build/status UI.
- Shared identity boundary: stable suite users/workspaces, explicit authoring
  project memberships/roles, and independently authorized links to research
  projects.
- Collaboration service: authenticated operation-based document sessions,
  ephemeral presence, per-user undo origins, durable attributed updates,
  reconnect, snapshots, and materialization into the canonical typed tree.
- Authoring API: projects/memberships, comments/mentions, checkpoints/reviews,
  media references, workspace/project standard registries, project bindings,
  build snapshots, optimistic versions for non-document resources, idempotent
  commands, and permissions.
- Local agent: filesystem, FFmpeg/FFprobe, voice provider credentials where
  local, verified clone/copy/move/reference imports, downloads, configured-root
  artifact lookup, manifest/hash verification, project-media materialization,
  OTIO/FCPXML package writing/verification, Resolve edition/version discovery,
  Studio automation when available, and local artifact cache.
- Resolve delivery adapters: a Free-compatible interchange-package adapter that
  never calls Studio APIs, and a Studio adapter that consumes the same package
  through supported external scripting and verifies the live timeline.
- Resolve reconciliation adapter: Studio-only observation of the last applied
  managed timeline, stable-ID mapping, three-way change classification,
  protected-work reporting, selective regeneration planning, application, and
  verification. It must not infer success for properties the installed API
  cannot inspect reliably.
- Build orchestrator: persisted dependency graph and jobs for voice, clip
  export, image generation, music/rights validation, media normalization,
  standard resolution, manifest compilation, target claims, and Resolve
  assembly.
- Research clip adapter: versioned API client to the existing shared catalog and export worker.
- Provider adapters: voice synthesis, image generation, stock/media search,
  review delivery/Google Drive, notifications, and future music/SFX discovery;
  a discovery result does not become an approved music standard automatically.
- Webpage capture adapter: public-page rendering/capture, viewport/region selection, provenance, and immutable screenshot finalization; authenticated capture remains a separate explicit capability.
- Standard registry: workspace/project standard metadata, immutable revisions,
  field-level override rules, project bindings, previews, approvals, and update
  comparisons in the control plane; Resolve/Fusion packages and music/audio/
  rights evidence in versioned object storage or a controlled local library.

## 14. Persistence and identity

- Use UUIDs for workspaces, projects, memberships, documents, checkpoints,
  comments, rows, blocks, standards/bindings/uses, media references, graphic and
  music instances, assets, builds, and delivery versions.
- Store collaborative authoring intent as durable attributed operations plus
  materialized typed snapshots in a transactional service; store comments,
  reviews, standards, project bindings, and build records transactionally, and
  store large artifact bytes in object storage or a verified local cache.
- Preserve an append-only actor/client-transaction/server-order history for
  accepted document operations. Compaction may optimize reconstruction but may
  not destroy checkpoint replay, attribution, or audit evidence.
- Persist immutable named checkpoints and append-only review events separately
  from the collaborative live head. Restore always creates a new live-head
  operation instead of moving or deleting the historical head.
- Use immutable artifact versions and content hashes. A path is a locator, not identity.
- Represent long work as durable, observable, retryable jobs with idempotency keys, attempts, progress, cancellation boundaries, and leases where distributed.
- Snapshot every external dependency in a build: research clip/version,
  exported artifact hash, voice/provider settings, graphic implementation and
  standard revisions, project-binding and resolved occurrence overrides,
  music asset and rights revisions, generated image version, and Resolve/timeline
  settings.
- Snapshot the selected Resolve delivery mode, detected/declared edition and
  version, capability matrix, interchange schema/adapter versions, every
  fallback/manual-completion decision, and—only for Studio—the scripting/API
  version used for live assembly.
- Persist each artifact requirement, resolution result, and project-local
  materialization separately. A missing locator can be repaired without
  changing the research clip reference or pretending the old artifact never
  completed.
- Persist each local import's requested and completed mode, original and
  project-local locators, source fingerprint, verified hashes, and original-file
  removal outcome. Treat the original path as provenance/locator rather than
  artifact identity, and never report `move` complete until the project artifact
  verifies and original removal has an explicit outcome.
- Reuse policy, project-media policy, resolved compatibility decision, artifact
  ID/manifest hash, and content hashes are frozen in the build snapshot. A later
  `Re-export all` action produces new artifact dependencies and a new build.
- Keep a build dependency graph so changing one narration paragraph regenerates only its voice asset and downstream timing, while unchanged assets are reused.
- Persist logged ranges separately from occurrence-specific clip-use ranges.
  Preserve baseline source/English transcript identities separately from
  editable subtitle-copy revisions and compiled branded caption events.
- Persist script marker anchors/notes independently from their compiled
  timeline frames, and keep script-owned marker IDs distinct from editor-created
  Resolve markers.
- Persist each applied Resolve sync baseline, managed-item identity map,
  observed timeline fingerprint, two-sided row/property deltas, selection,
  dependency impact, conflict decision, application result, and new baseline.
  A deselected row remains explicitly out of sync.
- Persist `VideoBuildJob`, `ReviewRenderArtifact`, and `DeliveryAttempt` separately. A successful timeline or MP4 remains successful when a later upload attempt fails.
- Persist workspace/project standards as stable identities with immutable
  revisions and optimistic current pointers. Persist project bindings and
  placed occurrences separately so a default update never retargets existing
  script content or completed builds.
- Persist `preview` versus `release`, live-head/checkpoint source identity,
  approval evidence, submitting actor, and resolved dependency hashes on every
  build. A later edit, approval revocation, rights change, or deprecation is new
  state rather than a mutation of the accepted snapshot.
- Persist expiring Resolve target claims separately from build state. Claim
  recovery must never imply that a partially applied timeline passed
  verification.

## 15. Failure and placeholder policy

| Condition                                                                          | Default behavior                                                                                                                   |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Editor is offline or has unacknowledged local changes when preview is requested    | Wait for synchronization or freeze the latest acknowledged revision and identify excluded local changes explicitly                 |
| Concurrent edits produce a semantically invalid coverage/anchor state              | Preserve accepted content, show the validation conflict, and block compilation until an Editor repairs it                          |
| Comment or typed anchor becomes ambiguous after concurrent deletion/rewrite        | Mark it stale and require explicit reattachment; never bind to nearby content silently                                             |
| Editor loses project authority with unsynchronized local text                      | Reject further synchronization, terminate write access, and preserve a private exportable recovery copy                            |
| Release build references an unapproved, superseded, or approval-revoked checkpoint | Reject submission without creating a build; completed builds from previously valid approvals remain immutable                      |
| Standard override targets a locked or unauthorized field                           | Reject the override, retain the last valid effective value, and identify the governing standard revision/rule                      |
| New standard revision exists                                                       | Show an update comparison; keep project bindings, occurrences, checkpoints, and builds pinned until explicit migration             |
| Graphic standard package/dependency is missing or invalid                          | Reject release or use only its declared tested baked/placeholder fallback; never substitute an unrelated/latest package            |
| Music bytes or rights evidence is missing, expired, or invalid                     | Block release; allow a policy-approved preview only with a prominent non-release rights warning and immutable diagnostic evidence  |
| Two Studio jobs target the same Resolve project/timeline                           | Serialize through an expiring target claim; never apply concurrently or infer success after claim loss                             |
| Completed clip record but package locator is missing                               | Search configured roots, offer verified `Locate`, then request immutable re-export or apply the explicit placeholder/block policy  |
| Located package fails manifest/snapshot/hash verification                          | Reject it as invalid; retain the clip reference and offer another location or durable re-export                                    |
| Reachable clip package lacks required handles or compatibility                     | Request a new immutable export; never stretch, silently substitute, or mutate the prior package                                    |
| Project-local media copy was deleted                                               | Rematerialize from a verified canonical package, then relink or re-export if necessary                                             |
| YouTube/source acquisition unavailable                                             | Keep the clip reference and transcript; show remediation; never substitute unrelated footage                                       |
| Voice generation fails                                                             | Place duration-preserving tone/slate or block build; retain text and error                                                         |
| Graphic data invalid                                                               | Show field-level validation; optionally place template-named slate                                                                 |
| Image unresolved                                                                   | Place request text on a slate with stable row ID                                                                                   |
| Local file cannot be decoded or inspected                                          | Reject the import without modifying the source; retain the card/import intent and actionable diagnostics                           |
| Local clone is unsupported                                                         | Fall back to a verified full copy and record `completedMode = copy`                                                                |
| Local move verifies the project artifact but cannot remove the original            | Keep both files, complete as a verified copy with a cleanup warning, and offer `Remove original` retry                             |
| Referenced local file moved, changed, or deleted                                   | Preserve the card and expected hash; offer verified relink, clone/copy into the project, replacement, or a labeled placeholder     |
| Webpage capture is blocked, incomplete, or materially different                    | Keep the URL/card and capture diagnostics; require review, retry with a revised capture profile, or use a supplied screenshot      |
| Image aspect ratio differs from timeline                                           | Use contain plus the selected project background; never crop or stretch unless explicitly overridden                               |
| Transition lacks sufficient duration or media handles                              | Block that transition with corrective choices; allow an explicit hard cut without moving narration anchors                         |
| Refined clip use falls outside the logged playable range                           | Reject the range, retain the prior valid use, and offer reset or an explicit research clip update/re-export                        |
| Subtitle copy is missing, unreviewed, or exceeds layout/reading constraints        | Keep source and baseline translation visible; block or explicitly slate the required subtitle event according to project policy    |
| Script marker loses its text/block anchor                                          | Mark it `unplaced`, omit it from compilation with a visible warning, and require reattachment or dismissal                         |
| Resolve timeline or baseline identity cannot be verified                           | Disable in-place reconciliation; preserve the timeline and offer a fresh generated timeline plus diagnostic report                 |
| Both script and Resolve changed the same managed property                          | Show a blocking row/property conflict and require an explicit use-script, keep-for-now, adopt-supported-change, or manual decision |
| Resolve-owned work loses its script anchor during a selected regeneration          | Preserve it in an orphaned/disabled review area or on the prior timeline; never delete it silently                                 |
| Resolve unavailable                                                                | Finish the Free-compatible import package; leave Studio assembly retryable                                                         |
| Resolve Free selected                                                              | Finalize a verified import package and stop at `ready_to_import`; never attempt external scripting                                 |
| Studio automation selected but Free, App Store, or unsupported Resolve is detected | Preserve the verified import package, block Studio-only stages, and offer Free-mode completion or installation remediation         |
| OTIO cannot represent a requested Fusion/Resolve operation                         | Use the declared baked/placeholder/manual fallback and list it in the report; never omit it silently                               |
| Imported Free timeline differs from the package                                    | Preserve the package and accept a user-reported discrepancy; do not claim automated live-timeline verification                     |
| Studio Resolve output differs from manifest                                        | Fail verification and retain both manifest and generated timeline for diagnosis                                                    |
| Review render fails                                                                | Retain the verified timeline and earlier artifacts; retry render without regenerating unchanged dependencies                       |
| Studio Drive upload fails or authentication expires                                | Keep the verified local MP4, expose reauthentication/retry, and never rebuild merely to retry delivery                             |
| Workstation sleeps, restarts, or Resolve is closed                                 | Persist state and resume from the last verified stage when the local agent and required application return                         |

## 16. Milestones

### Milestone 0 — Resolve capability spike

- Compile one deterministic fixture into a canonical manifest, self-contained
  media directory, OTIO, FCPXML, import instructions, and a report identifying
  every native, baked, placeholder, and manual-completion item.
- On a supported Resolve Free installation, manually import the OTIO package,
  inspect exact item count, durations, tracks, media links, and supported
  transitions/markers, then repeat with FCPXML fallback. Record the actual
  representational gaps and edition/version limits.
- On a supported standard desktop Resolve Studio installation, detect
  version/edition and external-scripting availability, consume the same package
  through the supported API, place three trimmed clips at exact record frames,
  add narration, insert one tested Fusion title, attach marker custom data,
  save/reopen, and verify against the same canonical manifest.
- Prove that selecting Free never invokes the scripting API and that selecting
  Studio against Free, Mac App Store, disabled-scripting, or unsupported
  installations stops safely after the verified import package.
- Decide the minimum supported Free and Studio versions and publish the tested
  capability matrix rather than inferring parity from marketing names.

Gate: one deterministic fixture produces a correct, reopenable manually imported
timeline in Resolve Free and a correct externally automated timeline in Resolve
Studio. Both originate from the same manifest and media package; neither path
uses UI automation, and every edition-specific difference is visible.

### Milestone 1 — Collaborative structured authoring and version history

- Two-column editor with section, narration, direction, clip, visual, graphic, citation, and excluded-draft blocks.
- Per-script Ideas outliner with nested items, reordering/indentation, open/incorporated state, and explicit promotion into a chosen Draft location.
- Per-script Extras surface with lossless move, restore, and duplicate-to-Draft operations for text, rows, and structured fragments.
- Shared workspace identity, explicit authoring-project membership, and the
  Owner/Administrator/Producer/Editor/Reviewer/Viewer authorization matrix.
- Live concurrent editing across Draft, Ideas, Extras, and typed cards with
  stable IDs, per-user undo/redo, copy/paste, selection across rows, presence,
  explicit sync state, offline reconnect, and printable/exportable human view.
- Anchored comment threads, replies, stable mentions, notifications,
  resolve/reopen, and stale-anchor repair.
- Attributed linear history, immutable named checkpoints, semantic comparison,
  review/approval events, and restore-as-new-head.
- **Continuous paragraphs with range-anchored OC/VO spans, multiple visual cards per paragraph, bidirectional hover highlighting, complete VO coverage validation, and deterministic prompter export.**
- Point video markers with stable semantic anchors, editable production notes,
  visible placed/unplaced state, and no effect on narration or runtime.
- Legacy Google Doc table import for the example document, with an inference-review screen.

Gate: two Editors concurrently change a new script, including a nested
Ideas-only outline, one promoted item, one Draft/Extras move, and one continuous
narration paragraph with multiple picture cuts/camera-state changes. One Editor
disconnects and reconnects without accepted work loss; a Reviewer discusses and
approves a named checkpoint; restoring it creates a new head while all later
history remains available. Ideas, Extras, comments, and presence never enter
prompter or build input.

### Milestone 2 — Narration-led rough cut

- One voice adapter, explicit temporary-audio labeling, pronunciation overrides, per-block generation/caching, waveform/duration/timing metadata, preview/regeneration controls, and audio normalization.
- Uploaded media/stills, placeholder slates, deterministic track map, canonical timeline manifest, and new-timeline builds.
- Immutable preview builds from an acknowledged collaborative live head and
  Producer-only release builds from an approved checkpoint, each showing when
  the live head has advanced.
- Compile script markers into native timeline markers where the tested delivery
  path supports them, with a visible fallback/report otherwise; repeated builds
  do not duplicate stable script-owned markers.
- Durable Free **Prepare/Update import package** and Studio **Build/Update in
  Resolve** jobs that can continue after the browser closes and reuse unchanged
  narration/media artifacts.

Gate: a five-minute script with mixed narration, stills, and local clips
produces a verified Free-compatible import package that becomes a correctly
timed rough cut after one manual import, and the same manifest produces an
automatically assembled and verified Studio timeline. Continued coauthoring
does not change either accepted build; an Editor may preview the synchronized
head, while only a Producer can release the approved checkpoint.

### Milestone 2B — Review render and Drive delivery

- Keep Free mode complete at a verified, manually renderable imported timeline;
  do not make automated Resolve rendering a hidden requirement for Free support.
- A versioned review-render preset, staging/finalization, FFprobe verification, and immutable MP4 artifact records.
- Optional Google Drive destination selection, resumable upload, explicit sharing policy, remote verification, and delivery retry independent of render.
- Background progress, restart recovery, and completion/failure notification.

Gate: in Studio mode, one action creates a verified shareable MP4; with Drive
enabled, the same frozen revision appears once in the chosen folder with a
recorded link. Closing the browser does not cancel the job, and an upload failure
can be retried without rerendering. In Free mode, the verified import package
remains a successful terminal result and carries clear manual render/upload
instructions.

### Milestone 3 — Research clip integration

- Search and insert stable clip records from the existing project.
- Resolve exact compatibility and current byte availability rather than trusting
  completed catalog state alone.
- Reuse matching verified artifacts, recover relocated packages through verified
  relink, or request durable immutable exports; propagate status and errors.
- Add a media-preparation summary plus independent reuse and project-media
  policies, defaulting to reuse verified media and copy/clone it into a
  self-contained authoring-project media folder.
- Preserve missing clip/transcript references when reacquisition fails and apply
  the project's explicit block-versus-placeholder policy.
- Snapshot transcript/version/bounds and show update comparisons.
- Give each script occurrence an inward-only, reversible refined in/out range
  with transcript/waveform preview, honest boundary snapping, optional
  frame-level adjustment, and independent use ranges for repeated occurrences.
- For foreign/mixed/unknown clips, derive occurrence-specific editable English
  subtitle copy from the immutable baseline translation, show only that English
  copy in the main script with a clear language/subtitle label, and compile it
  through a versioned branded subtitle preset without changing research
  transcript evidence.

Gate: a selected research clip appears as transcript text in the script and as
the correct script-refined media—with handles and chosen audio policy—in both
the Free import package and Studio timeline. A foreign-language occurrence
shows editable English subtitle copy in the script and required branded English
subtitles in both delivery results while its source and baseline English tracks
remain unchanged. A reachable verified package is reused without rendering; a
relocated package can
be verified and relinked; a missing or incompatible package creates one
idempotent re-export; and the resulting bytes are copied/cloned into the
authoring project without moving the canonical research package.

### Milestone 3B — Visual acquisition and transitions

- Typed cards and immutable artifact resolution for logged clips, public
  webpage captures, direct image URLs, and local image/video files.
- Direct local-file import with explicit verified clone/copy, move, or
  reference-in-place behavior and project-relative `Media/Local Images` and
  `Media/Local Clips` destinations.
- Webpage viewport/region preview, capture-on-add, optional daily/weekly webpage
  monitoring, immutable capture history, manual recapture, and the default
  top-left drift motion preset. Images and videos are never scheduled for
  recurring capture.
- Full-resolution image acquisition with contain/no-crop composition and no animation by default.
- Independent project defaults and per-boundary overrides for presenter→B-roll, B-roll→presenter, and B-roll→B-roll transitions.

Gate: one continuous narration passage resolves a logged clip, public webpage,
direct image URL, local image, and local video; keeps the full image visible;
imports local files without capture; verifies clone/copy and move semantics;
applies the webpage drift for exactly its covered range; and produces the
independently selected transition at each boundary without shifting narration
timing. A scheduled webpage change creates a reviewable immutable revision
without retargeting an existing build, while image/video sources are not polled.

### Milestone 4 — Reusable graphic and music standards

- Workspace/project standard registries, immutable revision publication,
  lifecycle/role enforcement, project bindings/defaults, field-level override
  rules, update comparison, and explicit occurrence migration.
- Graphic package/schema/preview/version registry and installer, kept distinct
  from configured standards and placed occurrences.
- Starter graphic standards with edge-case fixtures, Studio Fusion
  implementations, reference renders, structured inputs, and explicit Free
  fallbacks.
- One approved reusable music-cue standard with immutable audio and rights versions,
  cue/loop/fade/gain/ducking/duration defaults, permitted overrides, rights
  validation, and delivery-mode fallback reporting.

Gate: lower-third, quote, full-screen text, image-caption, and chart instances
render correctly from authored data in Studio and remain traceable through
standard, package, binding, and occurrence versions. Each also imports into Free
through a tested native/baked fallback or exact labeled placeholder. The music
cue resolves to the approved asset/rights snapshot and declared mix intent. A
new standard revision changes no binding, occurrence, checkpoint, or build until
an authorized explicit migration; locked overrides fail visibly.

### Milestone 5 — Assisted visuals and safe rebuild

- Generated-image and stock-search adapters, candidate review, rights/provenance fields, and caching.
- Stable applied-build baselines and Studio-side observation of managed items,
  recognized editorial changes, and protected Resolve additions.
- Highlighted **Regeneration Review** over the script with Script changed,
  Resolve changed, Both changed, Conflict, and Unchanged row states; accessible
  filters; automatically proposed but adjustable row selection; dependency
  impact; and explicit conflict decisions.
- Selective new-timeline regeneration that updates only chosen script-owned
  rows, preserves compatible Resolve work, retains deselected rows as out of
  sync, orphans rather than deletes work whose anchor disappeared, and verifies
  the applied plan before creating a new baseline.
- Bounded adoption of a clean Resolve trim or subtitle-copy edit into a new
  reversible script revision; no general inference from arbitrary Resolve edits.
- Batch resolution of placeholders and incremental regeneration.

Gate: changing a paragraph or visual choice produces a new Free import package
and opens a two-sided Studio Regeneration Review whose safe script changes are
preselected but adjustable. Applying a subset produces a new verified timeline,
preserves supported Resolve work, records deliberately out-of-sync rows and
conflicts, and does not regenerate unchanged assets or lose manual work.

## 17. MVP acceptance path

1. Sign in through the shared workspace identity, create an authoring project,
   assign Producer/Editor/Reviewer/Viewer members, and verify that authoring
   membership neither reveals nor bypasses a linked research project's access.
1. Open one script in two Editor sessions. Make overlapping prose edits and a
   simultaneous typed-card reorder; verify both accepted contributions converge,
   presence is ephemeral, and each Editor's undo does not remove the other's
   work.
1. Take one Editor offline, make a nonconflicting Draft edit, reconnect, and
   verify the operation merges with visible sync state. Revoke that Editor while
   another local edit is unsynced and verify the server rejects it while the
   client preserves a private recovery export.
1. Add a range comment with a mentioned Reviewer, reply, resolve, and reopen it.
   Delete the anchor and verify the thread becomes stale instead of jumping to
   neighboring content; confirm comments never enter prompter or build input.
1. Create a new script with no Draft content, add a three-level Ideas outline, reorder and indent items, close/reopen the script, and confirm the hierarchy persists.
1. Promote one idea at a chosen Draft location; confirm the idea remains linked and marked incorporated while only the new Draft block becomes build-eligible.
1. Import a copy of the example two-column Google Doc and review inferred rows.
1. Move one rich-text passage and one structured card/row to Extras; confirm neither affects validation, duration, voice generation, prompter output, or build input, then restore one at a chosen Draft location without losing content or references.
1. Move the imported notes/drafts tail to Extras and confirm it does not affect the build.
1. Create and name a checkpoint, request review, approve it, edit the live head,
   compare both states semantically, and restore the checkpoint as a new head.
   Verify the approved checkpoint, intervening history, comments, and later head
   all remain available.
1. Generate voiceover for a short chosen section, including one pronunciation override and one stage direction that remains unspoken.
1. Confirm that narration is generated as separately cached block assets; edit
   one block, update both delivery targets, and verify only that block and its
   timing dependents regenerate.
1. **Keep one narration paragraph intact while adding at least two visual events that begin/end at different word anchors inside it; verify hover highlighting in both directions.**
1. **Mark successive ranges OC, VO, and OC; verify OC words appear semibold, every VO range has visual coverage, and a deliberate unresolved placeholder is visible as such.**
1. **Export a narration-only prompter text file; verify it begins with (OC) or (VO), emits markers only at transitions, preserves spoken wording/order, and excludes directions and production notes.**
1. Insert one existing research clip by searching its transcript; preserve the clip ID, transcript version, selected bounds, export handles, and source audio choice.
1. Use **Refine clip** to trim that occurrence inward at both ends, preview it,
   verify the readable excerpt and compiled frames follow the refined range,
   reset it, and confirm the research record and a second occurrence remain
   unchanged.
1. Insert one foreign-language research clip. Verify the main script shows its
   English subtitle copy with a source-language/subtitles label; edit that copy,
   confirm the source and baseline translation remain unchanged, and compile the
   approved text with the frozen brand preset and valid timing/layout.
1. Place one production marker on a word and one between blocks. Verify their
   notes become timeline marker names/descriptions, earlier duration changes
   move them with their anchors, regeneration does not duplicate them, and
   deleting an anchor makes the affected marker visibly unplaced.
1. Build with an exact compatible research package already present; verify its
   manifest/hashes, reuse it without rendering, and copy/clone it into the
   authoring project's `Media/Research Clips` area.
1. Move the canonical fixture package outside its recorded locator, run build
   preparation, locate it explicitly, and verify that relink succeeds only after
   the exact manifest/snapshot/hashes pass.
1. Delete another fixture package and verify the build requests exactly one
   durable re-export. Then choose `Re-export all` and verify new immutable
   versions are created without overwriting prior artifact/build history.
1. Add a public webpage URL, preview its capture viewport, and verify the finalized screenshot receives the default top-left drift for exactly the event duration.
1. Enable webpage monitoring, simulate a materially changed page, and verify a
   new immutable capture appears as `Newer capture available` without changing
   the revision selected by an existing build. Verify that no recurring jobs
   are created for image or video sources.
1. Add one direct full-resolution image URL and verify it is acquired once and
   the entire image remains visible with no animation by default, including
   when its aspect ratio differs from the timeline.
1. Import one local image by clone/copy and one local video by move into
   `Media/Local Images` and `Media/Local Clips`; verify hashes/media metadata,
   project-relative locators, and that neither uses a capture provider. Simulate
   unsupported cloning and verify copy fallback. Simulate original deletion
   failure after a move and verify both copies remain, the import records an
   effective copy, and the warning can be retried without reimporting.
1. Set different transitions for presenter→B-roll, B-roll→B-roll, and B-roll→presenter; verify each compiled boundary uses the correct versioned preset and that an event-level override affects only its selected boundary.
1. Add one unresolved visual placeholder.
1. Publish one workspace lower-third standard and one project graphic standard,
   pin project bindings, place a lower third and simple chart, and verify each
   occurrence records separate standard, package, binding, semantic-input, and
   resolved-override identities.
1. Publish one approved music cue with exact audio and rights versions and cue, loop,
   fade, gain/loudness, ducking, attribution, and duration defaults. Place it in
   the script, apply one permitted occurrence override, and verify a locked
   override is rejected without changing the approved cue.
1. Publish newer graphic and music standard revisions. Verify existing project
   bindings, occurrences, checkpoints, and builds remain pinned; compare the
   update and explicitly migrate only one selected occurrence into a new
   document revision.
1. Create an Editor preview build from the fully synchronized live head, then
   have a Producer create a release build from the approved checkpoint. Verify
   each records its exact source and resolved standards, later coauthoring does
   not change either snapshot, and an unapproved/revoked checkpoint cannot start
   a new release.
1. Select Resolve Free and prepare a self-contained import package. Verify its
   manifest, OTIO, FCPXML, media paths/hashes, instructions, and explicit
   fallback/manual-completion list. Confirm no scripting API is called.
1. Manually import the OTIO into Resolve Free and inspect the documented track
   map, timing, media links, supported transitions/graphics, and labeled
   fallbacks. Repeat the compatibility fixture with FCPXML and record any
   representational difference without changing the canonical manifest.
1. Select Resolve Studio for the same frozen revision. Verify the previously
   prepared package is reused, the external API builds a new timeline with the
   documented track map, and automated verification agrees with every
   interchange-representable Free event.
1. Submit two Studio jobs against the same Resolve target and verify target
   application is serialized, claim loss is recoverable, and neither job
   overwrites the sole edited timeline or reports unverified partial work as
   complete.
1. Render a verified review MP4 from the Studio timeline, close/reopen the
   browser while the job is running, and confirm status recovery.
1. Upload the verified MP4 to a selected Drive folder, verify the recorded remote file/link, then simulate an upload failure and confirm retry does not rerender.
1. Change one narration block and rebuild both targets. Verify unchanged
   voice/media artifacts are reused, a new immutable Free import package is
   produced, and the previous Free package and Studio timeline remain available.
1. Manually trim one managed clip in Studio, add protected finishing work, and
   also change two script rows. Open Regeneration Review and verify the script
   highlights changes from both sides, script-changed rows are preselected,
   selection can be adjusted, compatible finishing work is identified for
   preservation, and the overlapping trim conflict requires an explicit
   decision.
1. Apply only one selected row. Verify a new timeline version is created, the
   protected work survives, the unselected row remains explicitly out of sync,
   the prior edited timeline remains available, and the new sync baseline is
   recorded only after plan verification succeeds.
1. Open the build report and trace every timeline item back to its script row and source/version.

## 18. Open questions and current recommendations

| Question                                       | Current recommendation                                                                                                                                                                                                                                     |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Separate repo or current monorepo?             | Treat this as a separate product/repository with a versioned API to the research project. Prototype code can temporarily share contracts, but avoid making either deployment depend on the other’s UI.                                                     |
| Google Docs as canonical editor?               | No. Import legacy docs and export readable snapshots, but make the structured web document canonical. Perfect Docs round-trip would erase semantics or require brittle conventions.                                                                        |
| Ideas versus Extras?                           | Ideas is a nested pre-draft planning/task outline; Extras holds already-authored material removed from the current Draft. Both belong to the same collaborative live head/checkpoint but are excluded from compilation until explicitly promoted/restored. |
| What should deletion do?                       | Keep ordinary delete with undo/revision recovery, and make `Move to Extras` the visible loss-averse action for material the writer may reuse. Do not silently turn every deletion into an Extra.                                                           |
| Timeline interchange or direct API?            | Both. Every build emits a verified OTIO/FCPXML package from one canonical manifest. Resolve Free imports it manually; Resolve Studio then uses supported scripting for automatic placement, Fusion enhancement, and verification.                          |
| Resolve edition support?                       | Support both desktop editions. Free mode is a successful partial workflow ending at a verified import package; Studio adds external automation, live verification, and optional Resolve-side render/delivery.                                              |
| Resolve project target?                        | Create a new project or new generated timeline by default. Never assume permission to overwrite an editor’s active timeline.                                                                                                                               |
| Timing spine?                                  | Narration duration by default, with explicit row policies for clip-led, fixed-duration, overlap, and montage regions.                                                                                                                                      |
| Voice provider?                                | Keep an adapter and compare at least one cloud and one local/offline option on quality, pronunciation, latency, cost, licensing, determinism, and data handling.                                                                                           |
| Speech asset granularity?                      | Narration block/row is the logical cache and replacement unit. Permit internal sentence chunks only as a provider implementation detail.                                                                                                                   |
| What do the delivery actions do?               | Preview freezes the acknowledged collaborative live head; release freezes an approved checkpoint. Both reuse the same preparation. Free prepares an immutable import package; Studio builds in Resolve and may continue to review MP4 and Drive delivery.  |
| Research media reuse policy?                   | Default to reusing exact compatible verified packages and exporting only missing/incompatible requirements. `Re-export all` is explicit and creates new immutable versions.                                                                                |
| Logged clip refinement ownership?              | Keep the research logged range immutable. Store an inward-only use range on each script occurrence, reset reversibly, and require an explicit research update/re-export to access media beyond the log.                                                    |
| Non-English text shown in the script?          | Show editable occurrence-specific English subtitle copy with a clear source-language/subtitles label. Keep source and baseline English evidence in the inspector and never rewrite either when copy changes.                                               |
| Required subtitle rendering?                   | Freeze a project brand-preset version and require visible English subtitles for foreign/mixed/unknown speech in both delivery modes. Use a tested native/title/baked Free path; a manual-only fallback is insufficient.                                    |
| Script production markers?                     | Use point markers with stable semantic anchors and notes. Compile to native timeline markers where tested, update by stable identity, preserve Resolve-created markers, and surface deleted anchors as unplaced.                                           |
| Project media placement?                       | Default to a self-contained project media area populated by copy-on-write clone when safe, otherwise copy. Reference-in-place is advanced; never move canonical research packages.                                                                         |
| Local media import?                            | Local images and clips bypass capture. Default to copy-on-write clone with verified copy fallback; offer explicit move, reference-in-place, or ask-each-time. A move verifies project bytes before attempting original removal.                            |
| Missing previously exported media?             | Verify configured roots or an explicit user-located package, then re-export from the frozen clip snapshot. If reacquisition fails, retain the reference and block or use a labeled placeholder.                                                            |
| Drive upload semantics?                        | Studio automation uploads a new immutable review version by default. Free mode supplies manual render/upload instructions. Keep sharing explicit and retry Studio delivery independently of rendering.                                                     |
| Can a build finish after the browser closes?   | Yes. Free package preparation needs only the local agent; Studio assembly/render also needs a supported running Studio installation. Missing capabilities wait or offer a completed Free package.                                                          |
| Automated B-roll selection?                    | Start with writer-selected assets and explicit placeholders. Add suggestions only after provenance, replacement, and rejection workflows are strong.                                                                                                       |
| Does webpage capture require a browser plugin? | Not for public pages: use a local headless-browser capture adapter. Treat authenticated pages as a later explicit attached-browser/extension capability or accept a user-supplied screenshot.                                                              |
| Webpage capture default?                       | Capture a writer-previewed viewport/region as an immutable still when added and apply a slow top-left-anchored drift across the event duration. Optional daily/weekly monitoring applies only to webpages and never silently retargets a build.            |
| Image fit default?                             | Preserve the full-resolution source and use contain/no-crop with a project background. No animation unless explicitly selected.                                                                                                                            |
| Transition defaults?                           | Store independent presenter→B-roll, B-roll→presenter, and B-roll→B-roll policies. `Apply to everything` is a shortcut, not a fourth semantic category.                                                                                                     |
| Graphic template inputs?                       | Design semantic schemas independent of node/control names. Keep the immutable package, configured standard, project binding, and placed occurrence separate, then map the resolved occurrence to versioned controls.                                       |
| Manual Resolve edits?                          | Begin with new timelines and stable managed IDs. Later Studio updates require three-way Regeneration Review, automatically proposed but adjustable row selection, explicit conflicts, protected Resolve work, and a new timeline version by default.       |
| Collaboration?                                 | Include live multi-editor authoring, presence, anchored comments, per-user undo, offline reconnect, explicit roles, and linear attributed history in MVP. Defer suggestion mode, branches/merges, and mobile authoring.                                    |
| Versioning model?                              | Keep the collaborative live head, immutable checkpoints, dependency revisions, build snapshots, and delivery versions distinct. Restore creates a new head; nothing rewinds or mutates history.                                                            |
| Reusable standard scope?                       | Publish governed workspace and project standards. Projects and occurrences pin exact revisions; updates require comparison and explicit migration.                                                                                                         |
| Standard override policy?                      | Declare each semantic field locked, project-overridable, occurrence-overridable, or both. A lower scope cannot loosen a higher-scope lock.                                                                                                                 |
| Music standard?                                | Pin an exact approved audio asset and rights snapshot plus cue, loop, fade, gain/loudness, ducking, duration, attribution, and allowed overrides; do not use a mutable mood/search recipe as the build identity.                                           |
| Build approval?                                | Editors/Producers may preview a synchronized head. Only a Producer may release a currently approved named checkpoint; continued collaboration never mutates the accepted snapshot.                                                                         |

## 19. Decisions required before implementation

- Minimum supported versions for both Resolve Free import and Resolve Studio
  automation, plus the exact standard-desktop installation and scripting
  preference requirements for Studio mode.
- OTIO/FCPXML feature matrix and required Free fallback for each starter
  transition, marker, transform, audio behavior, and graphic template.
- Primary operating system(s) for the local bridge; macOS can be first if that matches the editing environment.
- Whether presenter/A-roll footage is part of the first rough cut or the initial timing spine is voiceover only.
- Default timeline frame rate, resolution, audio sample rate, and track naming convention.
- Default subtitle brand preset, reading-speed/line-length limits, safe-area
  policy, speaker styling, and tested required-subtitle fallback for each
  supported Resolve Free interchange version.
- Default script-marker color/name convention and whether later marker task
  status should round-trip to Resolve metadata or remain script-only.
- Preferred computer voice characteristics and whether generated voice may leave the local machine.
- Default temporary voice provider/profile, cost ceiling, and whether row-level generation may run automatically on build or requires an explicit cost confirmation.
- Default review-render preset, filename/version convention, and whether a burned-in draft watermark/timecode is desired.
- Default Drive folder, retention/version policy, and who may change link-sharing permissions.
- Completion notification channels and whether the local agent should prevent sleep during an active render/upload.
- Build policy for unresolved assets: block, placeholder, or selectable per project.
- Default webpage viewport, region-selection behavior, page-load settle policy, top-left drift preset, and treatment of consent banners.
- Default contain-background treatment for mismatched image aspect ratios: black, brand color, blurred duplicate, or project template.
- Initial transition library, default duration, and whether any preset may affect audio as well as picture.
- Which five Fusion templates best represent actual repeated needs and who owns their visual approval.
- Exact presence/cursor performance targets and history-retention/compaction
  limits after the collaboration prototype measures representative scripts;
  the product behavior may not discard checkpoint replay or attribution.
- Default music-rights policy for non-release previews and the exact required
  license/territory evidence for release.
- Exact Resolve properties the Studio adapter can observe and preserve reliably,
  the protected-track convention, supported clean changes that may be adopted
  into the script, and the orphaned-work representation used during
  Regeneration Review.

## 20. First implementation slice

Build the smallest collaborative authoring proof before combining every media
and Resolve boundary. Use a deterministic script fixture and four authorized
users: two Editors, one Reviewer, and one Producer.

1. Create one authoring project linked to a separately authorized fake research
   project. Prove that workspace identity and authoring membership do not bypass
   the research permission boundary.
2. Open the same document in two Editor sessions. Concurrently edit one
   narration block with OC → VO → OC spans, reorder a nested Idea, move one typed
   fragment between Draft and Extras, and add one visual anchor. Prove
   convergence, per-user undo, explicit sync state, and no accepted-work loss
   across disconnect/reconnect.
3. Add one anchored comment, mention the Reviewer, reply, resolve/reopen, and
   make the anchor stale through an intentional deletion. Preserve the thread
   and require explicit reattachment; keep all comments out of compilation.
4. Create a named checkpoint, request review, and approve it. Edit the live head
   afterward, compare the two states semantically, then restore the checkpoint
   as a new head without deleting the later revision or review evidence.
5. Define one immutable lower-third implementation package, one approved
   workspace graphic standard, one pinned project binding, and one placed use
   with semantic content plus a permitted occurrence override. Reject a locked
   style override.
6. Define one approved music cue with exact audio and rights fixture versions,
   cue/loop/fade/gain/ducking/duration/attribution defaults, one permitted use
   override, and one locked field. Prove release validation rejects invalid
   rights evidence.
7. Publish new graphic and music standard revisions. Show update comparisons and
   prove that the project binding, placed uses, checkpoint, and prior snapshots
   stay pinned. Explicitly migrate only one occurrence and record the migration
   as a new reversible document revision.
8. Have an Editor create a preview snapshot from the acknowledged live head and
   the Producer create a release snapshot from the approved checkpoint. Each
   snapshot freezes canonical active-Draft content, exact source identity,
   resolved graphic/music uses, rights evidence, and dependency hashes. Continue
   coauthoring and prove neither snapshot changes.
9. Compile both snapshots only as deterministic canonical timeline manifests and
   build reports. Do not yet combine live research media, webpage capture,
   local-file move semantics, Free/Studio delivery, render/upload, or
   Regeneration Review into this slice.

Gate: both Editors' accepted work survives concurrency and restart; the Reviewer
can approve an immutable checkpoint; restore preserves linear history; comments
remain anchored or visibly stale; graphic/music standards enforce override
rules and pinning; standard updates are manual; and preview/release manifests
remain byte-stable after subsequent edits and publications. Run the independent
Resolve capability spike in parallel rather than combining its Free/Studio
boundaries into this proof. Continue to later media/delivery milestones only
after both gates are reliable.

## 21. Technical risks

- External Resolve scripting is Studio-only and may be unavailable in App Store
  or misconfigured installations. Mitigation: make a verified Free-compatible
  import package the common successful base artifact; capability-probe Studio,
  never use UI automation, and stop or downgrade explicitly before any
  Studio-only stage.
- OTIO/FCPXML cannot represent every Resolve/Fusion operation and imports can
  differ by Resolve version. Mitigation: one canonical manifest, parse and
  real-edition fixtures, declared native/baked/placeholder/manual fallbacks,
  immutable reports, and no claim of automated Free timeline verification.
- Fusion templates can expose implementation-specific controls and break when renamed. Mitigation: semantic schema, immutable versions, installer validation, and reference renders.
- Concurrent rich-text edits can converge structurally while violating semantic
  authoring invariants such as complete VO coverage or valid range anchors.
  Mitigation: operation-based convergence, stable semantic IDs/relative
  positions, post-merge typed validation, visible repair states, and no
  conflict policy that deletes accepted prose automatically.
- Presence or optimistic resource versions can be mistaken for durable document
  history. Mitigation: keep presence ephemeral, retain attributed accepted
  operations, materialize immutable checkpoints, and use optimistic versions
  only for comments/reviews/standards/build metadata rather than whole-document
  replacement.
- Offline work may reconnect after membership is revoked. Mitigation: recheck
  project authority on synchronization, reject unauthorized operations, close
  write sessions promptly, and preserve rejected local text only as a private
  recovery export.
- Users may confuse a live revision, approved checkpoint, dependency revision,
  build snapshot, or Resolve timeline version and approve/build the wrong state.
  Mitigation: distinct names/IDs/status language, semantic comparisons, exact
  source labels on every build, and no overloaded generic `version` control.
- Standard inheritance can hide where an effective graphic/music value came
  from or silently retarget many occurrences. Mitigation: fixed project/
  occurrence pins, explicit field-level override rules, provenance in the
  inspector, update comparisons, selected migrations, and fully resolved build
  snapshots.
- Music may become unusable because rights expire, evidence is missing, or the
  audio asset changes. Mitigation: immutable audio and rights revisions, release-time
  verification, prominent policy-controlled preview warnings, attribution in
  the build report, and no automatic replacement with another track.
- Legacy Google Docs contain ambiguous free-form cues. Mitigation: heuristic import with visible confidence and mandatory review; never treat import guesses as production-ready automatically.
- Planning and parked material can leak into production if scope is inferred from document position. Mitigation: persist Ideas, Draft, and Extras as explicit roots and expose only the active Draft to validation, voice, prompter, and build contracts.
- Moving rich fragments out of the Draft can orphan text anchors or media relationships. Mitigation: move whole typed subtrees with stable IDs when possible, preserve source revision/location, mark invalid relationships stale, and require review before restoration or compilation.
- Generated voice changes duration, shifting the entire edit. Mitigation: block-level assets, locked takes, change-impact preview, and immutable build snapshots.
- **Word-level timing may be unavailable or change after voice regeneration. Mitigation: preserve timing precision, align when required, offer a secondary timing mode, and never claim frame accuracy from paragraph position alone.**
- **Text edits can invalidate visual anchors or cause anchor drift. Mitigation: stable token/relative-position anchors, quoted-text checks, visible stale states, repair UI, and immutable build snapshots.**
- Refined media boundaries may imply precision the research transcript does not
  have. Mitigation: preserve word/cue/frame precision, snap honestly, preview
  the actual media, and store the final chosen frames separately from source
  transcript timing.
- Edited English subtitle copy can become unreadable in the source speech time
  or detach semantically from the original. Mitigation: immutable source and
  baseline-English evidence, segment linkage, review state, reading/layout
  validation, and explicit timing overrides rather than invented alignment.
- Marker anchors can drift or disappear as prose changes. Mitigation: stable
  semantic anchors, quoted-text checks, placed/unplaced state, and no silent
  nearest-content rebinding.
- Manual edits and generated rebuilds can diverge. Mitigation: immutable applied
  baseline, stable managed IDs, highlighted three-way Regeneration Review,
  automatically proposed but adjustable row selection, protected work,
  explicit conflicts, new-timeline default, and no silent overwrite.
- Resolve APIs/interchange may not expose enough detail to preserve every grade,
  effect, transition, track operation, or ripple edit. Mitigation: capability-
  tested observation, narrow supported-change classes, protected tracks, honest
  conflicts, prior-timeline retention, and no claim of arbitrary merge.
- Online media may be inaccessible or unauthorized. Mitigation: reuse the research project’s explicit authorization/provider boundaries and keep placeholders useful when export fails.
- A completed research export may have been moved, deleted, or corrupted. Mitigation: separate artifact identity from locators, verify package manifests/hashes at build time, support bounded configured-root lookup and explicit verified relink, then request an immutable re-export when possible.
- Copying all research packages can waste disk, while referencing them in place can make builds fragile. Mitigation: make reuse and materialization independent policies, prefer safe copy-on-write clones with copy fallback for self-contained projects, report estimated storage, and keep reference-in-place advanced.
- Moving a writer-owned local file could lose the only source bytes or leave the
  project half-imported across filesystems. Mitigation: make move explicit,
  stage/copy and media/hash-verify first, atomically promote inside the project,
  remove the original only afterward, and treat removal failure as a completed
  copy plus retryable cleanup warning.
- Provider costs and privacy vary. Mitigation: adapters, per-project policy, previews/estimates, caching, and explicit disclosure of uploaded text/media.
- Background builds depend on workstation availability and Resolve state. Mitigation: persisted waiting states, restart recovery, capability probes, optional sleep prevention, and clear indication of which stages can run unattended.
- Review delivery can accidentally expose unfinished work. Mitigation: private-by-default Drive upload, explicit sharing controls, immutable revision naming, remote verification, and audit records.
- Webpages are mutable and browser capture can be nondeterministic. Mitigation:
  previewed capture profiles, immutable screenshots, final-URL/timestamp/viewport
  provenance, load diagnostics, capture when added, optional webpage-only
  monitoring, and reviewable new revisions rather than silent refresh or build
  retargeting.
- Remote image URLs can change, disappear, or return misleading content types. Mitigation: bounded acquisition, media decoding/metadata verification, hashes, immutable finalized artifacts, and no silent replacement.
- Transitions can consume unavailable handles or obscure editorial timing. Mitigation: frame-based validation, independent boundary policies, explicit audio behavior, and a hard-cut fallback chosen by the writer.

## Appendix A. References

Primary product and implementation sources used to ground Resolve automation, Fusion template design, the example-script analysis, and integration with the existing research clip workflow.

- [Example two-column script: OEV25 Finland](https://docs.google.com/document/d/1-9FhegQDRAqfjRs_UbEIdb3SSDPW-P3qL8nKA1-N24k/edit?tab=t.0)
- [DaVinci Resolve 20 New Features Guide — AI IntelliScript](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_20_New_Features_Guide.pdf)
- [Fusion 20 Reference Manual — macros and Fusion templates](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf)
- [DaVinci Resolve 20 Fusion Visual Effects Guide — creating title templates](https://documents.blackmagicdesign.com/uk/UserManuals/DaVinci-Resolve-20-Fusion-Visual-Effects.pdf)
- [DaVinci Resolve 20 Studio and iPad Features — edition and external-scripting differences](https://documents.blackmagicdesign.com/uk/SupportNotes/DaVinci_Resolve_Studio_20_Features.pdf)
- [DaVinci Resolve OpenTimelineIO import/export guidance](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_18.5_New_Features_Guide.pdf)
- Installed DaVinci Resolve scripting README (local workstation; last updated 28 October 2024).
- Research Video Transcript & Clip Extraction Tool: PROJECT_GUIDE.md.
