# Script-to-Resolve Authoring Platform

Product and implementation specification — **Revision 2**

Working title: Assembly. Status: scoped and sequenced for implementation.
Prepared 13 August 2026; Revision 2 prepared 24 August 2026; Revision 2.1
(same day) integrates Part 3 — recorded performance ingest and conform — as
Phases 6–7 of the ladder, re-scoped to the team's actual shoot practice.
Revision 2.2, prepared 26 August 2026, inserts a bounded Fusion
semantic-input capability spike before production Studio assembly and
renumbers only the Phase 1 slices that had not begun.

Revision 2 supersedes the working draft of 24 August 2026 ("Revision 1"). It
preserves Revision 1's product thinking — which was strong — and changes three
things: **what ships first, in what order, and how the work is packaged for
execution by AI coding agents directed by a producer rather than an engineer.**
Everything Revision 1 specified is still in this document; some of it has moved
from "MVP" to a later phase or to the Deferred Register (section 14), each with
an explicit trigger for bringing it back.

---

## 1. Executive summary

Build a collaborative web-based authoring system that feels as familiar as the
current two-column Google Docs workflow, but stores enough structured
information to compile a written script into a rough-cut DaVinci Resolve
project. Multiple authorized editors work in the same script with presence,
anchored comments, and an attributed linear history. Narration is the primary
surface: the writer marks on-camera (OC) and voiceover (VO) ranges inside
intact paragraphs, anchors visual events to exact word ranges, and the compiler
turns the result into a temp-narrated timeline with research clips, stills,
graphics, and music placed at intentional points. The product is a **compiler,
not a replacement nonlinear editor**: the authoring project is the source of
truth, and a Resolve project or timeline is a generated, inspectable
deliverable that an editor refines.

Two Resolve delivery modes share one canonical timeline manifest: a
Free-compatible verified OTIO import package with one explicit manual import
step, and a Studio automation mode that creates and verifies the timeline
through the supported external scripting API and can continue through an
automated review render and Google Drive upload. Rebuilds are deterministic,
incremental where practical, and never erase manual editorial work without an
explicit reconciliation step.

### 1.1 What changed in Revision 2

Revision 1 was a maximal union: a complete statement of everything the finished
product should honor, labeled almost entirely "MVP." As a reference for product
intent it holds up. As an implementation plan it had three structural problems.

**First, the MVP was eight products stapled together.** Section 5.1 of
Revision 1 bundled live CRDT collaboration, a six-role authorization matrix
with approval workflows, an idea outliner, a loss-averse Extras surface,
word-range visual anchoring, per-occurrence clip refinement, an editable
subtitle-copy system with brand presets, a four-identity standards/governance
system with field-level override rules, music rights evidence, webpage capture
with scheduled monitoring, verified local-file import with move semantics, two
Resolve delivery adapters, durable background jobs, and render-and-deliver
automation — as one release. Every item is defensible. Treating them as one
gate means many months of building before the first video benefits.

**Second, the sequencing optimized for correctness-at-scale before proving the
core loop.** For this team — a producer directing AI coding agents — the
dominant project risk is not data corruption under enterprise load. It is (a)
discovering late that an interaction model is wrong, and (b) the project
stalling because nothing usable emerges for months. The mitigation is a ladder
of short phases, each of which ends with something you actually use on a real
video, with the riskiest external boundary (Resolve interchange and scripting)
proven first and the highest-value magic moment (a written script becomes a
temp-narrated rough cut) delivered before the editor UI even exists.

**Third, the plan was written for a senior engineering team, not for AI-agent
execution.** Agents do excellent work inside narrow, verifiable boundaries and
poor work when a task is open-ended, cross-cutting, or ambiguously done. This
revision repackages the roadmap into numbered slices with explicit scope
boundaries, frozen contracts between slices, and an acceptance script for each
slice that **a producer can run personally, in the product, without reading
code.** The acceptance scripts are the management interface: if the script
passes, the slice is done; if it doesn't, the slice is not done, whatever the
agent reports.

The re-scope follows one rule: **keep everything that is cheap to build in
early and ruinous to retrofit later; defer everything that is governance or
convenience for a larger organization than the one that will use this
product.** Concretely:

- **Kept as architectural DNA from day one** (cheap early, ruinous late):
  stable IDs on every block and card; immutable content-hashed artifacts;
  path-as-locator-never-identity; build snapshots that freeze every dependency;
  the five-layer version model; the canonical manifest shared by both Resolve
  adapters; new-timeline-per-build; narration-first range anchoring.
- **Kept, moved later in the ladder** (real value, separable): research clip
  integration and refinement; subtitle copy for non-English clips; webpage and
  image acquisition; transitions; the graphics/music library; Regeneration
  Review.
- **Simplified** (right-sized for a five-person team): six roles become three;
  checkpoint approval workflow becomes named checkpoints with a Producer
  "approved" label; the four-identity standards system with field-level
  override policy becomes a project template library with pinned versions;
  music rights snapshots become license/attribution fields on the cue.
- **Deferred with revive triggers** (section 14): workspace-level standards
  governance and lifecycle events; field-level override rule enforcement;
  rights-evidence blocking; scheduled webpage monitoring; the heuristic legacy
  Google Docs importer as a product feature (replaced by agent-assisted
  one-time conversion); revoked-editor recovery exports; FCPXML as a
  perpetually-maintained second interchange format (demoted to a spike-time
  contingency decision).

Nothing was cut because it was wrong. Section 14 lists every deferral with the
condition that should bring it back, so the decision is reviewable rather than
silently lost.

**Revision 2.1** folds the Part 3 discovery outline (Recorded Performance
Ingest and Conform, 20 August 2026) into this same ladder as Phases 6 and 7,
applying the same re-scope rule. Three discovery questions are now settled and
recorded as binding: the normal shoot is **one camera with line-by-line
repeats** (dual-system audio and multi-camera are deferred with revive
triggers); the first target is **on-camera presenter footage** (real picture
and production audio become the A-roll spine, so proxy review and a
per-camera color input transform are in scope); and the conform model is **one
active take per performance beat** with recorded alternates (intra-beat
splicing is deferred behind an explicit contract hook). Subtitles, the
graphics/music library, and Regeneration Review move to Phases 8–10 — the
recorded conform is what turns rough cuts into finished-feeling videos, so it
outranks them.

**Revision 2.2** adds Slice 1.5 as an early capability gate for writing typed
semantic values into a hash-pinned Fusion lower-third template, then reading
and verifying them after save/reopen in Resolve Studio. This does not move the
curated graphics product, its shared contracts, or its authoring UI out of
Phase 9/Phase 2 integration; it proves the risky Resolve boundary before the
production Studio adapter is finalized. The former Slices 1.5–1.7 are
renumbered 1.6–1.8.

### 1.2 Suite phases

1. The research tool (existing) logs transcript-backed source clips and
   prepares reusable editing artifacts.
2. This authoring platform compiles a structured script into a temp-narrated
   Resolve rough cut and exports the frozen prompter script used for a shoot.
3. The recorded-performance phase ingests long line-shoot media, aligns
   repeated takes to stable script ranges, records keeper approvals, and
   conforms a new timeline to the real performance — replacing the temporary
   narration spine and reflowing every text-anchored visual to the recorded
   word timings. As of Revision 2.1 this is no longer a separate outline: it
   is Phases 6–7 of this plan, sharing the document, artifact, build, and
   Resolve contracts established by Phases 0–5.

### 1.3 Resolve edition support

Both desktop editions are supported product targets, sharing one compiler,
source resolution, immutable artifacts, narration, timing, and build identity.
Edition mode changes only delivery and post-delivery verification:

- **Resolve Free — Prepare Resolve timeline:** compile the frozen revision,
  materialize verified media, and produce a self-contained import package
  containing the canonical manifest, OTIO (plus FCPXML fallback if the Phase 0
  spike shows it is needed), build report, and clear manual import
  instructions. Free mode never pretends it can use Studio-only external
  scripting; features interchange cannot express become an edition-compatible
  baked asset, a labeled placeholder, or an explicit manual-completion item in
  the report.
- **Resolve Studio — Build in Resolve:** produce the same verified interchange
  package, then use a supported standard desktop Studio installation and the
  external Python API to create projects, bins, and timelines, place media and
  Fusion templates, attach metadata, verify the result against the manifest,
  and optionally render and deliver a review file in the background.

A Free build and a Studio build from the same frozen revision must agree on
every representable event rather than using separate editorial
interpretations.

---

## 2. Product promise

A writer collects and hierarchically organizes research ideas before drafting,
authors a normal-looking two-column script, parks unused passages in Extras
without throwing them away, and assigns or requests media beside each active
passage. Collaborators work concurrently while the Producer controls release
builds. Within the readable script, the writer refines an individual use of a
logged clip, edits the English subtitle copy viewers will see for non-English
speech, and leaves point-anchored Resolve production notes.

A Resolve Free user chooses **Prepare Resolve timeline** and receives a
verified import package plus instructions for one manual timeline import. A
Resolve Studio user chooses **Build in Resolve** to create and verify the
timeline automatically; **Update video** recompiles a later revision through
the same delivery mode, and Studio automation can optionally render and upload
a shareable review MP4 after timeline verification.

The narration remains the writer's primary surface: camera-state and visual
events begin or end inside a paragraph without forcing the writer to split
that paragraph into edit-sized rows. Every off-camera span identifies what the
audience sees. A printed or exported script still makes sense without the
application.

---

## 3. What the example script teaches us

The "OEV25 Finland" document remains the governing real-world specimen. It is
not simply a narration column and a link column: it mixes polished script,
performance directions, section breaks, quoted clips, source URLs, time
ranges, silent footage, still-image requests, named graphics, research
citations, saved assets, alternates, and a long notes/drafts tail. The
interface must support that messiness without forcing the writer to think like
a database administrator.

- The left column usually holds narration, on-camera direction, jokes, pauses,
  pronunciations, and section structure. The right column may hold a clip,
  still, graphic, citation, URL, transcript excerpt, time range, an
  instruction such as "clip with no audio," or merely an unresolved idea.
- Some rows are left-only, right-only, or intentionally blank on one side.
- **One narration paragraph may continue across several picture cuts.
  Paragraph boundaries express writing structure, not edit boundaries.**
- **Host visibility is a continuous state independent of paragraph and row
  boundaries: on camera (OC) or off camera/voiceover (VO). When the host is
  off camera, visual coverage is required — the script must identify the clip,
  still, graphic, screen capture, or explicit unresolved placeholder visible
  for the entire VO span.**
- A clip reference may include a title, YouTube URL, in/out points, translated
  or quoted dialogue, desired audio policy, and commentary about the moment.
- Draft notes and abandoned material coexist with the active script, so build
  eligibility cannot be inferred from document position alone. Early research
  begins as topics, questions, and fragments with parent/child relationships;
  material removed from the current draft is not necessarily rejected.
- The script is optimized for humans collaborating on meaning. Machine
  semantics appear progressively through cards, status, and an inspector — not
  through visible JSON, tags, or syntax.

---

## 4. Product principles

1. **Human-readable first.** A printed or exported script still makes sense
   without the application.
2. **Narration-first authoring.** Paragraphs follow the flow of spoken
   language; camera changes and visual cuts attach to text ranges rather than
   dictating paragraph or row breaks.
3. **Structure beneath the surface.** Every build-relevant row and asset has a
   stable ID and typed data even when it renders as ordinary text.
4. **Collaboration does not trade away provenance.** Concurrent edits converge
   into one attributed live history; comments, restores, and builds keep
   stable actor and revision evidence.
5. **Version terms are not interchangeable.** The live head, named
   checkpoints, dependency revisions, build snapshots, and Resolve timeline or
   package versions have separate identities and lifecycles.
6. **Active scope is explicit.** Ideas and Extras travel with the script but
   never enter narration, validation, prompter exports, duration estimates,
   voice generation, or video builds until explicitly promoted or restored.
7. **The script is canonical; Resolve is compiled output.** Editorial
   refinements can be preserved, but the Resolve timeline is never the only
   copy of authoring intent.
8. **Source evidence and edit usage are separate.** A logged clip, its
   transcript tracks, a script-specific refined range, and editable subtitle
   copy remain independently identifiable and reversible.
9. **References before files.** Reuse clip IDs, transcript versions, and asset
   identities; never duplicate downloads or silently create disconnected
   media.
10. **Immutable builds.** Each build snapshots the frozen revision, media
    versions, voice model, template versions, resolved settings, and tool
    versions. Later edits never rewrite a prior checkpoint, build, or
    generated timeline.
11. **Honest incompleteness.** Missing assets create visible placeholders or
    blocking issues; they never disappear or receive invented substitutions.
12. **Local media authority.** Filesystem access, media acquisition, FFmpeg,
    voice rendering, and Resolve automation run through a trusted local agent.
13. **Edition-aware delivery without split semantics.** Free and Studio builds
    share one canonical manifest and prepared-media graph; capability
    differences are explicit delivery results, not silent omissions.
14. **Replaceable providers.** Voice, image generation, media acquisition, and
    Resolve integration stay behind narrow adapters.
15. **(New in Revision 2) Every phase ends in use.** No phase is complete
    until its output has been exercised on real material by the people who
    will use it. A phase that cannot state what the producer will do with its
    output is misdefined.
16. **(New in Revision 2) Right-size governance to the team.** Enforcement
    machinery (approval gates, override policy, rights blocking) enters the
    product when the team's actual failure modes demand it, not before. Data
    model hooks for that machinery are kept from day one because they are
    cheap; workflows are not.

---

## 5. The phase ladder

Eleven phases, 0 through 10. Each phase ends with a **usable increment** — a
sentence of the form "you can now…" that is demonstrably true on real
material — and a **gate** that must pass before the next phase begins. Phases
are ordered by risk and value, not by architectural layer: the scariest
external boundary (Resolve) is proven first, the biggest payoff (script →
rough cut) lands second, and everything afterward compounds on a loop that
already works.

| Phase | Name | You can now… |
| ----- | ---- | ------------- |
| 0 | Foundations and Resolve capability spike | Trust that OTIO import and Studio scripting actually work on your installations, with a published capability matrix |
| 1 | Walking-skeleton compiler | Turn a structured script file into a temp-narrated Resolve rough cut — before any editor UI exists |
| 2 | Single-writer authoring app | Write a script in the app — OC/VO spans, anchored visuals, coverage validation, prompter export — and build it to Resolve with one button, including a shareable review MP4 |
| 3 | The writing room | Write with your collaborators live: presence, comments, history, named checkpoints, Ideas and Extras |
| 4 | Research clip integration | Search logged clips, drop them into the script as transcript text, refine each use, and build with verified reused media |
| 5 | Visual sources and transitions | Add webpage captures, image URLs, and local files as visuals; control transitions at each boundary type |
| 6 | Shoot ingest and take review | Ingest a line-shoot recording, see matched takes beside the script, and approve a performance for every beat |
| 7 | Recorded performance conform | Build a new timeline where your real on-camera performance replaces the temp voice and every B-roll boundary moves to the spoken words |
| 8 | Subtitles for non-English clips | Edit viewer-facing English subtitle copy per occurrence and compile branded subtitles in both delivery modes |
| 9 | Graphics and music library | Place versioned lower thirds, quotes, charts, and approved music cues from a project library |
| 10 | Regeneration Review and safe rebuild | Update a manually-refined Studio timeline through a highlighted three-way review instead of a full regenerate |

Rationale for the three most consequential ordering decisions:

**The compiler precedes the editor (Phase 1 before Phase 2).** Revision 1 put
the collaborative editor first. But the editor's design — anchoring,
coverage, timing — is only validatable against a compiler that actually
produces timelines, and a producer can evaluate a rough cut far better than an
architecture diagram. Phase 1 needs no UI at all: its input is the canonical
script document in file form, hand-authored or converted from an existing
Google Doc by an agent. This also forces the canonical content model and
manifest contracts to exist and stabilize *before* an editor is built on top
of them, which is the correct dependency direction and dramatically reduces
agent confusion.

**Collaboration follows the single-writer app (Phase 3 after Phase 2).** The
team is real, so live collaboration is in scope and arrives early — but the
document model, anchoring behavior, and build loop should be proven by one
writer first. Retrofitting Yjs under a Tiptap document that was designed for
it from day one (Phase 2 builds on the collaborative-ready document model even
while serving one user) is a planned step, not a rewrite.

**The recorded conform outranks subtitles, graphics, and Regeneration Review
(Phases 6–7 before 8–10).** A temp-narrated rough cut is a planning artifact;
a conform with the real performance is most of a finished video. Once Phases
0–5 can compile a script with real visuals, the biggest remaining gap between
"what the tool makes" and "what gets published" is the performer — so the
shoot pipeline comes next. The dependencies also point this way: the conform
consumes exactly what Phases 1–5 established (text anchors, compiled timing,
the manifest, visual events with handles) and nothing from subtitles or the
template library. Regeneration Review stays last for the same reason as
before — until it ships, every conform and every update is a new timeline,
which is safe — and it applies unchanged to conformed timelines when it
arrives. One risk note: Phase 6's first slice (the alignment corpus and
capability spike) depends only on Phase 1 contracts, so it may be run
opportunistically any time after Phase 1 if a shoot is imminent.

---

## 6. Authoring experience

Each subsection is tagged with the phase where it first ships. Behavior
specified here is contractual for that phase's slices; later phases extend but
do not contradict it.

### 6.1 Main document (Phase 2)

The default view is intentionally close to Google Docs: a white page, familiar
typography and text controls, page-like margins, section navigation, undo/redo,
and unobtrusive but explicit save/build status. The central content is a
two-column grid with no spreadsheet chrome. Rows expand naturally and contain
ordinary paragraphs or structured cards. The left column is visually primary.
On-camera text uses a restrained semibold treatment (target CSS font-weight
600), voiceover text stays normal weight, and a small state control, accessible
label, and inspector value accompany the styling so camera state is never
communicated by weight alone.

| Left: spoken / performed | Right: shown / heard / built |
| ------------------------ | ---------------------------- |
| Narration with inline OC/VO spans; OC words semibold | One or more visual cards anchored to exact word ranges |
| Stage direction or performance note | B-roll, still image, screen capture, or source link |
| Section heading or beat | Graphic template plus structured data |
| Blank | Production-only cue, music, transition, or clip |
| Scratch / excluded draft | Optional reference notes and unused alternatives |

### 6.2 Narration-first visual anchoring (Phase 1 model, Phase 2 interface)

**The load-bearing design decision of the whole product.** Each narration
paragraph stays intact; independent, range-anchored event lanes carry the
production semantics. A host-visibility lane records OC/VO spans. A visual
lane records clips, stills, graphics, and placeholders. Both lanes use stable
text anchors — block ID plus start/end token IDs with affinity and quoted-text
repair evidence — rather than new table rows.

A visual card in the right column shows a compact coverage label and aligns
approximately with the relevant text. Hovering the card highlights its covered
words on the left; hovering highlighted words emphasizes the corresponding
card. Multiple cards can cover successive or overlapping ranges inside one
paragraph. Full-frame visuals normally create a VO span over the same range;
overlays can coexist with OC when the host remains visible.

Authoring anchors express meaning before exact audio timing exists. After
generated or recorded narration is available, the compiler resolves text
anchors to milliseconds and frames using provider speech marks or word
alignment. Timing precision is visible and honest — word, sentence, or cue
level — and is never presented as frame-exact until compiled timing is
verified. A secondary timing mode (Phase 5) lets the editor fine-tune frame
boundaries without changing the paragraph or its semantic anchors.

**Coverage rule.** Every spoken token belongs to exactly one host-visibility
state. Every VO interval must be covered by at least one full-frame visual
instruction or an explicit unresolved-visual placeholder. Gaps, contradictory
overlaps, and zero-duration visual events are build validation errors, not
silent defaults.

Rejected interaction alternatives (carried forward from Revision 1, still
binding): inline cut markers between words (optional visibility mode only,
never primary); one row per shot (breaks continuous paragraphs — rejected as
default); a miniature timeline under every paragraph (secondary timing mode
only); sentence-level cards (cannot express mid-sentence cuts — prototype
constraint at most, not the data model).

### 6.3 Row and block types (Phase 1 model; interface arrives with its phase)

| Type | Readable rendering | Build behavior | Phase |
| ---- | ------------------ | -------------- | ----- |
| section | Heading spanning the document | Chapter marker; optional timeline marker | 1 |
| narration | Continuous paragraph; OC ranges semibold | Generates/references narration audio; carries host-visibility spans | 1 |
| direction | Parenthetical or muted text | Non-spoken; may create marker or actor note | 1 |
| visual | Thumbnail, name, or request text | Places still/video or an explicit placeholder | 1 |
| note/draft | Ordinary scratch text | Excluded unless promoted | 1 |
| host-visibility span | OC or VO state over a narration range | Emits prompter markers; validates host visibility | 1 |
| visual event | Right-column card linked to highlighted words | Places a clip/still/graphic over the compiled time range | 1 |
| video marker | Margin marker with expandable production note | Emits a point timeline marker; contributes no duration | 2 |
| citation | Linked source | Preserved in script/build report; no timeline item by default | 2 |
| clip | Title plus transcript excerpt | Resolves a stable clip reference and places chosen source/audio range | 4 |
| subtitle copy | English viewer-facing text plus source-language badge | Compiles reviewed branded captions without changing source evidence | 8 |
| graphic | Template name plus human-readable semantic values | Resolves a pinned template version and inputs | 9 |
| music/sfx | Cue name, license note, and instruction | Resolves pinned audio plus cue and mix-intent settings | 9 |

### 6.4 Progressive controls (Phase 2, extended per phase)

- Typing stays immediate. A blank right cell behaves like text until the
  writer types @, pastes a URL, drags an asset, or chooses Insert.
- Insert opens the choices available in the current phase: placeholder, local
  image/video, video marker, citation (Phase 2); clip search (Phase 4);
  webpage/image capture (Phase 5); graphic template, music cue (Phase 9).
- Selecting a structured card opens a right-hand inspector with timing, audio,
  crop, fit, template inputs, provenance, and build status.
- Every row has an unobtrusive build-state indicator: excluded, ready,
  unresolved, generating, stale, failed, or built.
- Each narration block shows its temporary-audio state — missing, queued,
  generating, ready, stale, locked, failed, or replaced by host recording —
  and can preview or regenerate only that block.
- A Preview timing mode estimates duration from generated narration and
  displays row-level time spans without turning the document into a timeline.
- The primary action distinguishes **Preview** from **Release**, then reflects
  the delivery profile: Free shows **Prepare Resolve timeline** / **Update
  import package**; Studio shows **Build in Resolve** / **Update video**, with
  `Timeline only`, `Timeline + review MP4`, and `Timeline + review MP4 + Drive
  upload` options. Edition, destination, and unsupported-feature fallbacks are
  visible before submission.
- Build preparation summarizes how many media requirements will be reused,
  materialized, exported, relinked, or left unresolved, plus estimated new
  disk usage; it opens a focused remediation view only for blocking items.

### 6.5 Prompter export (Phase 2)

The prompter export contains only spoken host narration, in document order. It
excludes direction blocks, citations, visual notes, asset transcripts,
graphics data, and excluded drafts. It always begins with a state marker and
adds a new marker only when host visibility changes. Default formatting places
(OC) or (VO) on its own line immediately before the first affected word, even
when the transition occurs inside an authoring paragraph; paragraph wording
and order are unchanged. Section headings may be included as non-spoken
navigation labels through an export option.

The export records the source document revision and is deterministic: the same
revision and settings produce the same text file. Validation blocks export if
any spoken range has no camera state.

**Performance-beat sidecar (contract from Phase 2; consumed in Phase 6).**
Every prompter export additionally freezes a machine-readable sidecar: the
ordered performance-beat IDs with their exact expected text, OC/VO state,
non-spoken navigation cues, pronunciation/performance notes included by
policy, and an export hash. The visible prompter text stays natural — beats
never split or pollute the prose — with optional visible beat numbers for
slate/pickup workflows. Beats default to one per sentence within each
narration block and are adjustable (merge/split) before the export freezes.
Because the export records its document revision, the beat map is also
derivable after the fact from that frozen revision, so a shoot made from a
pre-Phase-6 prompter export is not stranded: Phase 6 can reconstruct its beat
map exactly.

### 6.6 Ideas and Extras (Phase 3)

Each script has three explicit content surfaces: **Ideas**, **Draft**, and
**Extras**. The Draft is the primary page and the only build-eligible surface.
Ideas and Extras live in a collapsible side panel or focused full view.

**Ideas is an outliner, not the section-navigation outline.** Every item
contains text and child items, supports add-child/add-sibling, drag/reorder,
indent/outdent, collapse/expand, and open/incorporated state. A script may
exist with only Ideas populated. Promoting an item creates or inserts a chosen
draft block, preserves a backlink, and marks the idea incorporated;
incorporation state is informative and never controls build eligibility by
itself.

**Extras is a loss-averse holding area for authored material not in the
current draft.** `Move to Extras` is a first-class action for selected text,
rows, or structured fragments. It preserves readable content, formatting,
typed cards, citations, media references, provenance, and source
revision/location where practical. Moving a whole block preserves its stable
identity. Restoring inserts the material at a writer-selected Draft location;
duplicating into the Draft creates new identities. References or anchors that
are no longer valid return visibly stale and require review rather than being
silently discarded or rebound.

Ideas and Extras participate atomically in the same collaborative live head
and checkpoint as the Draft. Their counts and unresolved/stale state are
visible, but they never create host-visibility or coverage errors and are
excluded from prompter/print exports by default (explicit appendix option for
human-readable exports only). Ordinary delete still exists with undo and
history recovery; the application does not silently convert every deletion
into an Extra.

### 6.7 Roles and membership (Phase 3)

Revision 2 collapses Revision 1's six roles to three. The suite identity
supplies stable users and a workspace; each authoring project has an explicit
membership list. A linked research project remains a separate authorization
boundary: membership in either project never grants access to the other, and
every clip read or build-time artifact request rechecks the current
research-project permission.

| Role | Authority |
| ---- | --------- |
| Producer | Everything an Editor can do, plus: manage members/settings/links, create release builds, choose release destinations, label a checkpoint approved, apply Regeneration Review plans (Phase 10) |
| Editor | Edit all three surfaces and typed cards, comment, create and name checkpoints, create preview builds |
| Viewer | Read the document, history, comments, and build results |

Deferred from Revision 1 (see section 14): the separate Workspace
Owner/Administrator governance tier (the workspace has an owner; that is
enough for now), the Reviewer role, formal checkpoint review states
(`in_review`, `changes_requested`, `approval_revoked`) and approval evidence
chains, and revoked-editor private recovery exports. What remains contractual
now: every mutation records the stable actor; role removal takes effect on the
next request and terminates write-capable sessions promptly; a release build
requires a Producer and a checkpoint the Producer has labeled approved.

### 6.8 Live collaboration and comments (Phase 3)

Draft, Ideas, Extras, and their typed nodes form one collaborative document
transaction boundary. Multiple Editors change different or overlapping content
concurrently without a whole-document lock. ProseMirror/Tiptap with Yjs is the
recommended implementation (Revision 2 commits to this stack rather than
keeping it open — fewer degrees of freedom for agents; the product contract
remains convergent operation-based editing, so the commitment is revisable at
a contract boundary if the Phase 2 spike fails).

- Presence shows active collaborators, connection state, and cursor or
  selected block/card. Presence is ephemeral and never changes document or
  build identity.
- Autosave distinguishes `local changes`, `syncing`, `synced`, `offline`, and
  `sync failed`. A preview build cannot claim unsynchronized local changes;
  the action waits for acknowledgment or states exactly which synchronized
  revision it will freeze.
- Undo/redo is per user and per editing session.
- Offline Editor operations merge when connectivity returns, at the level Yjs
  provides naturally; semantic build validation may expose a temporarily
  invalid merged state, but the system never resolves it by deleting one
  participant's accepted text. (Engineering beyond Yjs's natural offline
  behavior is deferred.)
- Moving a typed subtree between Draft and Extras or promoting an Idea is one
  atomic collaborative transaction — IDs preserved for moves, new IDs for
  explicit duplicates.

A comment thread anchors to a text range, block/card, Idea, Extra, or point
between blocks. It supports replies, stable-user mentions, resolve/reopen, and
an attributed edit history. Text anchors use collaborative relative positions
plus stable semantic IDs and quoted text as repair evidence. When deletion or
concurrent rewriting makes placement ambiguous, the thread becomes `stale` and
offers explicit reattachment; it never jumps silently. Comments are authoring
discussion and never enter narration, duration, prompter output, or the
compiled timeline.

Suggestion/track-changes mode, document branching, and rich review workflows
remain out of scope and must not be simulated through hidden duplicate
documents or by treating comments as script content.

### 6.9 Document history and checkpoints (Phase 3)

The product uses five separate version layers (unchanged from Revision 1 —
this is architectural DNA):

1. **Collaborative live head:** the current converged document state,
   identified by acknowledged operation/state-vector evidence and a
   materialized content hash.
2. **Document checkpoint:** an immutable named materialization of one live
   state for comparison, restore, or release-build input.
3. **Dependency revision:** an immutable template package, media asset, voice,
   or other external dependency revision.
4. **Build snapshot:** the exact checkpoint or synchronized live revision plus
   every resolved dependency and setting used by one compiler job.
5. **Delivery version:** the generated Resolve import package or Studio
   timeline produced from a build snapshot.

Accepted collaborative operations retain stable actor, client transaction,
server ordering, and timestamp evidence. The history UI groups that evidence
into readable attributed revisions and compares prose, structure, Idea/Extra
movement, typed-card properties, and anchors. Editors and Producers create
named checkpoints; a Producer may label a checkpoint **approved**, which is
the sole gate for release builds. Restore creates a new live-head transaction
whose content comes from the chosen checkpoint — never a destructive rewind or
implicit branch. New edits advance the live head and never rewrite a
checkpoint.

### 6.10 Preview and release builds (Phase 2 single-user; Phase 3 rules)

An Editor or Producer creates a **preview build** from the latest fully
synchronized live revision; the UI labels it non-release, records the exact
revision it froze, and shows when the live head moves ahead. Only a Producer
creates a **release build**, and only from a checkpoint labeled approved. A
release here means an approved rough-cut compiler input, not final legal,
audio, color, or delivery approval.

Both actions produce immutable build snapshots and use the same Free/Studio
delivery adapters. Collaboration continues while a job runs, but later edits
cannot alter its input or retry. Studio application to the same Resolve
project/timeline target is serialized through an expiring target claim.
Simultaneous script authoring never makes a Resolve timeline a
collaboratively edited source document.

### 6.11 Refining a logged clip in the script (Phase 4)

A logged clip keeps the original transcript selection and logged/export bounds
owned by the research project. Each `VisualEvent` that uses it receives an
independent `ClipUsageRange` owned by the script. The writer shortens that
occurrence without changing the logged clip, canonical artifact, or another
occurrence of the same clip.

- A clip card exposes **Refine clip** and summarizes `Using 00:08 of 00:21`.
- Refinement opens a compact player with waveform/transcript context and
  draggable in/out handles. Default interaction snaps to verified word
  boundaries when available, falls back honestly to cue boundaries, and offers
  frame-level adjustment as an explicit precision mode.
- The use range moves inward anywhere inside the logged playable range but
  never extends beyond it. Access to additional source handles is a research
  re-export operation, not a hidden expansion of the log.
- Preview loops only the proposed use range. **Reset to logged range**
  restores the full occurrence reversibly.
- The card and readable script representation immediately show only the
  transcript/subtitle content overlapping the refined range. The build stores
  the exact chosen frames plus timing precision and transcript evidence.
- Refinement changes only the beginning and end initially; removing words from
  the middle (multi-range) is deferred.

### 6.12 Editable English subtitle copy for non-English clips (Phase 8)

For every clip occurrence containing foreign-, mixed-, or unknown-language
speech, the main scripting view shows the English words the audience will
read, labeled unambiguously (`Spanish · English subtitles`), with the source
transcript and baseline translation in the inspector. The first subtitle copy
derives from the immutable English translation supplied by the research clip
snapshot, then becomes a script-owned, occurrence-specific
`SubtitleCopyTrack`:

- Editing subtitle copy changes only the viewer-facing English subtitles for
  this use of the clip in this script — never the media, research record,
  source transcript, baseline translation, or another occurrence.
- Each segment remains time-linked to immutable source evidence. Refining the
  clip removes segments outside the use range and clamps/rebases the rest
  without rewriting source timing.
- After a text edit, the system reflows lines over existing speech-aligned
  timing and warns when reading speed, line length, line count, or safe-area
  constraints are exceeded. Material timing changes require an explicit timing
  edit.
- Machine-generated copy begins in `needs_review`; approval or a human edit
  records the reviewer and revision. Mixed-language clips apply this at the
  timed segment level; unknown language follows the safer subtitle-required
  path.

Every authoring project selects a versioned subtitle brand preset (font,
weight, size, colors, outline/background, position, margins/safe area, max
lines, optional speaker treatment). The compiler emits semantic timed caption
events plus the exact preset version. Studio places and verifies the tested
Resolve representation. Free delivery must use a tested native, title-based,
or baked representation that preserves required visible English subtitles; a
manual-completion item alone is not an acceptable fallback for required
non-English dialogue.

### 6.13 Script video markers (Phase 2)

The writer inserts a point marker anywhere the compiled video has a semantic
position: on a specific word, at the start/end of a clip, or between two
blocks. The marker has a stable ID and an editable production note intended
for work that will be completed in Resolve.

- The script margin shows a marker icon at its anchor; selecting it opens the
  note without adding visible syntax to the narration.
- The first nonempty note line becomes the Resolve marker name; the complete
  note becomes its description. Script-originated markers use a consistent
  project color and identity metadata where the delivery adapter supports it.
- Markers move with their semantic anchor when preceding duration or document
  order changes; they never affect runtime and never appear in rendered video.
- If the anchored content is removed or its mapping becomes ambiguous, the
  marker becomes `unplaced` and requires reattachment or dismissal — never
  silent deletion or reattachment to unrelated content.
- Rebuilds update or remove the matching script-owned timeline marker by
  stable identity instead of duplicating it. Editor-created Resolve markers
  are Resolve-owned and remain protected.

### 6.14 Shoot sessions and take review (Phase 6)

A user selects the frozen prompter/script revision used at the shoot, creates
a named `ShootSession` with a processing profile, and adds the authorized
camera master files. The MVP shoot shape, per the team's actual practice, is
**one camera (camera or attached mic), reading each beat several times in a
row with natural pauses**; multiple files per session are normal, and the
model never assumes filename order, identical timecode, or one continuous
recording. Dual-system audio and multi-camera sessions are deferred (section
14) but the source model must not preclude them.

Every source is hashed and inspected before acceptance — timecode, duration,
streams, codecs, frame rate, resolution, color metadata, audio layout — with
the filename recorded as provenance, never identity. A moved file is detected
by hash and relinked without creating a new source identity. Local masters
remain the authoritative media; nothing uploads raw shoot media to a hosted
provider without a per-project policy naming the provider, transmitted
content, retention, and cost. Review proxies and waveform derivatives generate
per profile thresholds, with a verified proxy-to-master time mapping; the
browser reviews proxies, but conform in/out values always live in master
source time.

The pipeline transcribes production audio with word timing, aligns the
transcript to the frozen beat map, and segments repeated reads, restarts,
partial takes, ad-libs, pickups, and uncovered spans. The matcher never forces
spoken audio onto a beat, never presents an approximate semantic match as
exact word alignment, never hides an uncovered or ambiguous beat, and never
discards off-script material that may matter in review. Candidate boundaries
prefer natural silence/breath points around a complete read, and handles are
retained for trims and transitions.

**Human approval remains authoritative.** Automated evidence is ranked and
explainable — script coverage with omitted/substituted/added words, alignment
and boundary confidence, complete-versus-partial read, audio warnings
(clipping, noise, interruptions), and duration/pace outliers — stored as
separate components, never one mysterious number. Performance quality (comic
timing, warmth, emphasis, eye line) is not scored. Only explicit approval
creates the active `TakeAssignment`; reprocessing with a new model or profile
may add suggestions but never changes an approved assignment.

In the script editor, each beat shows a compact state badge: no source found,
analyzing, candidates available (with count), approved, approved with
alternates, temporary-voice fallback, needs pickup, ambiguous, stale after a
script or source change, or failed with a reason. Selecting the badge opens a
**takes drawer** — not a full NLE — with proxy playback in master timecode,
rapid sequential playback of all candidates, A/B comparison with keyboard
approve/reject, expected-versus-recognized text with highlighted differences,
waveform and meters, and trim handles that cannot escape the registered
master range. Valid outcomes per beat: one active take plus zero or more
approved alternates, `Use temp voice`, `Needs pickup`, or `No spoken line`.
**One active take per beat is the contract** (Revision 2.1 decision);
`TakeAssignment` reserves a sub-range list field as the hook for deferred
intra-beat splicing. The document also supports **Play approved
performance** — previewing the selected takes in script order from proxies so
gaps and abrupt joins are obvious before any Resolve build. Approval and
trimming never mutate the script text or the source media.

### 6.15 Recorded performance conform (Phase 7)

**Recorded speech becomes the new timing spine.** Temporary narration
established the draft timing; once a take is approved, that performance and
its verified word alignment establish the timing for its beat. Text-anchored
events move with the corresponding recorded words — they are never
proportionally stretched against the old synthetic clip.

For every performance beat the compiler chooses exactly one allowed timing
source: the approved recorded take, explicitly locked temporary narration, an
explicit silence/non-spoken duration, or a blocking `needs pickup`/unresolved
state. Clicking **Build recorded version** freezes a
`RecordedConformSnapshot` — every assignment, trim, and processing choice —
and shows an impact preview first: old duration, new duration, cumulative
shift, changed assignments, events that move, events whose source media
became too short, and protected regions needing reconciliation.

Every visual event declares how it behaves when narration duration changes:

| Policy | Rebuild behavior |
| ------ | ---------------- |
| `follow_text_anchors` | Recompute record in/out from aligned words; use available source handles without changing semantic anchors |
| `stretchable_still_or_graphic` | Recompute duration and stretch only the explicitly stretchable still/template hold |
| `fixed_source_excerpt` | Preserve source in/out; report a coverage gap/overlap if the new narration no longer fits |
| `clip_led` | Keep the clip's duration as the local timing spine per the existing authoring policy |
| `protected_manual_timing` | Do not move automatically; require reconciliation when upstream timing changes |

Ordinary B-roll is trimmed or extended only within verified handles — never
speed-changed, looped, frozen, or generatively extended unless the user picks
a separate explicit policy. Stills and template holds may duration-adjust when
their definition permits.

The first recorded conform and every materially changed conform create a new
generated timeline; the temp-voice build and prior conforms are preserved, and
stable script/beat/assignment/event/build IDs travel in marker custom data or
the nearest supported metadata surface. Part 3 gains no permission to
overwrite an editor's refined timeline; manual Resolve work stays governed by
the Phase 10 reconciliation policy. The result is described as a
**final-candidate conform** — never a delivery master — until picture, audio,
color, graphics, rights, and delivery checks pass outside this product.

**Script changes after a shoot** follow explicit staleness rules: an
unchanged normalized spoken-text hash retains its approved take;
formatting/punctuation-only edits keep assignments; a wording change marks the
match and assignment stale (rematchable, but the old approval is never
silently transferred); a new spoken beat is `needs recording` by default with
explicit temp-voice permission per build; deleting a beat removes it from the
next conform while preserving prior builds and approvals; splitting or
merging beats proposes a mapping requiring confirmation; moving an unchanged
beat changes program order but not source identity, with the move reported
and downstream timing recomputed.

### 6.16 Regeneration Review (Phase 10)

Studio **Update video**, once a generated timeline has been manually refined,
begins with a three-way comparison between the last applied immutable build,
the current script revision, and the current managed Resolve timeline. The
application opens a highlighted script view rather than rewriting the
timeline. Each build-eligible row is one selectable regeneration unit;
expanding it reveals property-level changes and preserved Resolve work.

| Row state | Script display | Default selection |
| --------- | -------------- | ----------------- |
| Script changed only | Green highlight, `Script changed` | Selected |
| Resolve changed only | Purple highlight, `Resolve changed` | Not selected |
| Both changed, compatible | Split highlight, `Both changed` | Selected; compatible Resolve work preserved |
| Both changed, conflicting | Red outline, `Conflict` | Selected proposal, blocked until reviewed |
| Unchanged | No highlight | Hidden by default |

Labels and icons accompany color. Filters include `Changed only`,
`Conflicts`, `Script changes`, and `Resolve changes`, with section-level
selection and **Select all safe updates**. Selecting a row rebuilds its
script-owned contents while carrying forward compatible recognized Resolve
work; deselecting leaves the Resolve row untouched and records it as
explicitly out of sync — it does not silently accept the Resolve
representation back into the script.

A conflict offers only explicit outcomes: **Use script version**; **Keep
Resolve version for now** (out-of-sync row); **Adopt Resolve change into
script** for a deliberately bounded reversible mapping (initially: clean
in/out refinements and subtitle-copy edits); or **Review manually in
Resolve.** Adoption never interprets arbitrary tracks, effects, or ripple
edits as script structure. Finishing work — grades, effects, mix changes,
protected-track additions — appears as a summary (`3 Resolve additions
preserved`) rather than overwhelming the prose diff.

Before application, the review calculates dependency effects: a duration
change states how much later material moves, which anchored Resolve additions
move with it, and which unanchored items require review. The default result is
a new versioned timeline; the sole edited timeline is never overwritten.
Completion reports regenerated rows, preserved Resolve work, deliberately
out-of-sync rows, and deferred conflicts.

---

## 7. Canonical content model

Do not compile directly from HTML, editor markup, or free-form prose. The
editor persists one collaborative document tree whose nodes have stable IDs
and typed properties, plus an append-only attributed operation history and
immutable materialized checkpoints. **The canonical document has a
serialization independent of any editor** — a versioned JSON form
(`ScriptDocument v1`) that is the compiler's sole input. Phase 1 authors this
form directly as fixture files; Phase 2's editor becomes one producer of it;
the compiler never knows the difference. This contract-first split is what
lets phases proceed independently.

Resource metadata, comments, checkpoints, and builds use explicit optimistic
versions and idempotent commands; CRDT operations are not a substitute for
authorization or lifecycle rules.

Core entities (fields marked ⊕ are Revision 2 extension points: present in
the schema, unenforced until their phase or deferral revives):

**Identity and membership (Phase 3; single implicit user until then)**

- `AuthoringWorkspace { id, name, ownerUserId, version }`
- `AuthoringProject { id, workspaceId, title, linkedResearchProjectIds[], settings, version }`
- `ProjectMember { projectId, userId, role: producer | editor | viewer, version }`

**Document (Phase 1 serialized form; Phase 2 editor; Phase 3 collaboration)**

- `ScriptDocument { id, projectId, title, activeDraft, ideaOutline, extras, liveHeadSequence, liveStateVector, liveContentHash }`
- `DocumentOperation { id, documentId, actorUserId, clientTransactionId, serverSequence, operationHash, acceptedAt }`
- `DocumentCheckpoint { id, documentId, name, approvedLabel ⊕review-events, sourceSequence, stateVector, canonicalSnapshotHash, createdBy, createdAt }`
- `CommentThread { id, documentId, anchor, state: open | resolved | stale, createdBy, version }` and `CommentEntry { id, threadId, authorUserId, body, mentionedUserIds[], version, createdAt, editedAt }`
- `IdeaItem { id, parentId, orderKey, text, state: open | incorporated, linkedDraftBlockIds[], collapsed, version }`
- `StoredFragment { id, orderKey, contentTree, sourceBlockIds[], sourceRevision, sourceLocation, state: stored | stale, version }`

**Narration and anchoring (Phase 1)**

- `NarrationBlock { id, orderKey, text, hostVisibilitySpans[], visualEvents[], timingPolicy, state, notes, version }`
- `TextAnchorRange { blockId, startTokenId, endTokenId, startAffinity, endAffinity, quotedText, anchorVersion }`
- `HostVisibilitySpan { id, range, state: on_camera | voiceover, source, version }`
- `VisualEvent { id, range, source, presentationMode, framingPolicy, motionPreset, audioPolicy, layer, transitionIn, transitionOut, timingOverrides, status }`
- `CompiledEventTiming { eventId, startMs, endMs, startFrame, endFrame, timingPrecision, alignmentVersion }`
- `ScriptVideoMarker { id, anchor, note, color, state: placed | unplaced, version }` (Phase 2)

**Clip usage and subtitles (Phases 4 and 8)**

- `ClipUsageRange { id, visualEventId, loggedStartMs, loggedEndMs, useStartMs, useEndMs, startAnchor, endAnchor, timingPrecision, version }`
- `SubtitleCopyTrack { id, visualEventId, sourceLanguage, baselineEnglishTrackId, baselineEnglishTrackVersion, segments[], reviewState, reviewerId, brandPresetId, brandPresetVersion, version }`
- `SubtitleCopySegment { id, sourceSegmentIds[], sourceStartMs, sourceEndMs, englishText, timingOverride, version }`
- `SubtitleBrandPreset { id, version, font, weight, size, fill, outlineOrBackground, position, margins, safeArea, maxLines, speakerTreatment }`

**Media resolution and materialization (Phase 1 minimal; Phase 4 full)**

- `MediaReference { id, kind, sourceSystem, sourceId, sourceUrl, versionSnapshot, transcriptSnapshot, requestedInOut, exportHandles, captureProfile, artifactId, provenance, status }`
- `ArtifactRequirement { id, mediaReferenceId, clipSnapshot, requiredBounds, requiredHandles, conversionRequirements, languageArtifactPolicy, reusePolicy }`
- `ResolvedArtifact { requirementId, artifactId, packageManifestHash, contentHashes, compatibility, availability, verifiedAt, sourceLocatorId }`
- `MaterializedMedia { id, projectId, requirementId, artifactId, mode: clone | copy | move | reference, projectRelativeLocator, contentHashes, verifiedAt }`
- `LocalMediaImport { id, projectId, mediaReferenceId, sourceLocator, sourceFingerprint, requestedMode, completedMode, projectRelativeLocator, contentHashes, originalRemovalStatus, verifiedAt }` (Phase 5)

**Templates and music (Phase 9 — Revision 2 simplified shape)**

- `TemplateItem { id, projectId, kind: graphic | music_cue, name, currentRevisionId, version }`
- `TemplateRevision { id, templateId, revisionNumber, payload, dependencyVersions[], previewArtifactId?, createdBy, createdAt }`
- `GraphicTemplatePackage { id, version, fusionArtifactId, semanticSchema, dependencies, freeFallback, referenceRenderIds[], contentHash }`
- `GraphicUse { id, visualEventId, templateId, templateRevisionId, semanticInputs, occurrenceSettings, resolvedSnapshotHash }`
- `MusicCuePayload { audioAssetId, audioAssetVersion, licenseNote ⊕rights-snapshot, attribution, cueInMs, cueOutMs, loopPolicy, fadeInMs, fadeOutMs, gainOrLoudnessTarget, duckingPolicy, durationPolicy }`
- `MusicCueUse { id, anchor, templateId, templateRevisionId, occurrenceSettings, resolvedSnapshotHash }`

The Revision 1 four-identity standards system (workspace/project scopes,
`OverrideRule` field policies, `ProjectStandardBinding`,
`StandardLifecycleEvent`, `MusicRightsSnapshot`) is deferred (section 14).
What survives now, because it is the expensive-to-retrofit part: templates
have **immutable revisions**, placed uses **pin the exact revision and store a
resolved snapshot hash**, and a newer revision **never changes an existing
use, checkpoint, or build without an explicit migration**. Governance around
who may publish and which fields may be overridden is workflow, and workflow
waits.

**Transitions (Phase 5)**

- `TransitionPolicy { presenterToBroll, brollToPresenter, brollToBroll }`
- `TransitionSpec { kind, durationFrames, easing, templateId, templateVersion, audioBehavior }`

**Builds and delivery (Phase 1)**

- `BuildSnapshot { id, class: preview | release, liveHeadSequence?, checkpointId?, canonicalDocumentHash, activeDraftBlockVersions, assetVersions, voiceSettings, resolvedTemplateUses, timelineSettings, target, createdBy, status, manifestHash }`
- `ResolveDeliveryProfile { mode: free_interchange | studio_automation, resolveVersion, resolveEdition, installationKind, capabilitySnapshot, interchangeFormats, studioApiAvailable }`
- `ResolveImportPackage { id, buildId, manifestHash, otioArtifact, fcpxmlArtifact?, mediaRoot, importInstructionsArtifact, manualCompletionItems[], verifiedAt }`
- `NarrationAudioAsset { id, blockId, blockRevision, kind: temp_synthetic | host_recording, textHash, synthesisProfileHash, provider, model, voiceVersion, audioHash, durationMs, timingPrecision, timingArtifact, normalizationProfile, status }`
- `VideoBuildJob`, `ReviewRenderArtifact`, `DeliveryAttempt` — persisted separately; a successful timeline or MP4 remains successful when a later upload attempt fails.

**Performance and conform (Phases 6–7)**

- `PerformanceBeat { id, documentId, anchorRange, expectedTextHash, normalizedSpokenTextHash, prompterOrder, hostVisibility, version }`
- `ShootSession { id, authoringProjectId, documentRevision, prompterExportId, name, shootDate, processingProfileVersion, status, createdAt }`
- `ShootSource { id, shootSessionId, mediaHash, originalPathLocator, inspectedStreams, sourceTimecode, colorMetadata, authorization, relinkState, status }` (cameraId ⊕multi-camera)
- `ShootProxy { id, shootSourceId, profile, proxyHash, generatorVersion, timeBaseVerification, locator }`
- `ShootTranscript { id, shootSourceIds, provider, model, language, timingPrecision, transcriptHash, wordTimings, version }`
- `TakeCandidate { id, performanceBeatId, sourceId, sourceInMs, sourceOutMs, handleInMs, handleOutMs, alignmentVersion, transcriptDiff, evidenceComponents, warnings, status }`
- `TakeAssignment { id, performanceBeatId, candidateId?, outcome: active_take | temp_voice | needs_pickup | no_spoken_line, approvedAlternates, manualBounds, spliceRanges[] ⊕intra-beat-splicing, actorId, createdAt, version, locked }`
- `ProcessingProfileVersion { id, scope: project | shoot, proxy, transcription, alignment, audio, color, toolVersions, createdAt }` (camera/source scoping ⊕)
- `ProcessedDialogueArtifact { id, shootSourceId, chain, providerVersions, inputHash, outputHash, timingOffset, measuredProperties, status }`
- `ColorInputTransform { id, scope, transform, verificationState, version }`
- `RecordedConformSnapshot { id, buildId, documentRevision, prompterExportId, shootSessionVersions, takeAssignmentVersions, processingProfileVersions, visualEventVersions, timelineSettings, manifestHash, createdAt }`

Two Part 3 foundations are already satisfied by this model and stay binding.
First, **timestamps are audit data, not change identity**: rebuild decisions
compare build snapshots and dependency hashes (expected-text and
normalized-spoken-text hashes on beats), while the append-only operation log
explains how the document got there — wall-clock ordering never selects
rebuild dependencies. Second, **originals and decisions are immutable**:
masters, proxies, transcripts, alignments, processed audio, approvals,
profiles, and conform builds are separately versioned, and derived work never
replaces a master or an artifact an earlier build used.

**Reconciliation (Phase 10)**

- `ResolveSyncBaseline { id, timelineId, appliedBuildId, managedItemMap, observedTimelineFingerprint, createdAt }`
- `RegenerationReview { id, baselineId, scriptRevision, resolveObservationId, rowChanges[], selectedRowIds[], decisions[], status }`
- `RegenerationRowChange { rowId, scriptDelta, resolveDelta, compatibility, protectedWork[], dependencyImpact, proposedAction }`

Cross-cutting rules, unchanged from Revision 1: the collaborative transaction
and live-head identity cover Draft, Ideas, and Extras together, but the
compiler receives only `activeDraft`. Moving a block between Draft and Extras
is a reversible document operation, not deletion. A checkpoint materializes
all three surfaces; a build snapshot records the exact frozen revision plus
the active block versions it compiled. Absolute Resolve timecode is compiled
output: clip uses and markers retain semantic anchors so they move with script
content. Baseline translation, editable subtitle copy, and compiled subtitle
events are separate versioned records.

---

## 8. Media, voice, and visual subsystems

### 8.1 Integration with the research clip project (Phase 4)

The existing research tool remains authoritative for research clips,
transcripts, source-video identity, transcript provenance, selected bounds,
export bounds, notes/tags, and rendered clip packages. The authoring platform
consumes those records through a versioned API; it never scrapes the
spreadsheet or duplicates YouTube/transcript logic.

The insertion flow: the writer searches project clips by tags, notes, source
title, or transcript text; dropping a result onto selected narration creates a
`VisualEvent` whose reference points to the stable project clip ID,
snapshotting the readable transcript plus selected version/bounds while its
`TextAnchorRange` states exactly which words the clip covers. The occurrence
begins with the complete logged range; later refinement is a script-owned use
range inside that immutable logged range. Script-specific choices — mute
source audio, partial range, crop, layer, speed, placement duration — are
usage overrides and never mutate the research clip. If the research record
changes, the script shows "update available" and offers keep snapshot, update
reference, or compare; it never silently retargets the edit.

**Ownership boundary:** the research project owns source acquisition,
transcripts, clip logging, rights/provenance notes, clip export, and reusable
clip artifacts. The authoring project owns narrative order, usage of a clip in
a particular video, voiceover, graphics, visual requests, timeline placement,
and build history. The Resolve bridge owns deterministic translation from one
build snapshot into a Resolve project/timeline and the reconciliation report.

### 8.2 Build-time media resolution and materialization (Phase 1 minimal; Phase 4 full)

Artifact identity and file placement are separate concerns: the immutable
artifact/package ID, manifest, and content hashes identify reusable media;
paths, object keys, and project-local copies are locators. **The build
verifies actual bytes; it never infers availability from a remembered path or
a completed export record.**

When a delivery action freezes a revision, create an `ArtifactRequirement` for
every media source and produce a media-preparation plan before timeline
compilation:

| Resolution state | Default action |
| ---------------- | -------------- |
| Exact, compatible, reachable, hash-verified | Reuse and materialize into the authoring project |
| Reachable but incompatible or lacking required handles | Request a new immutable export |
| Completed record with a missing locator | Search configured roots, then offer verified `Locate` |
| User-located package | Accept only after manifest/snapshot/hash verification |
| Still missing | Request durable re-export from the frozen clip snapshot |
| Source unavailable or unauthorized | Block or use an explicit labeled placeholder per build policy |

Two independent settings: **Reuse policy** (`Reuse verified; export
missing/incompatible` default; `Re-export all`; `Reuse only`) and **Project
media policy** (`Make project self-contained by copy/clone` default;
`Reference verified media in place`; `Ask for each source`).

The authoring workspace keeps reusable media outside build directories:

```text
Authoring Project/
  Media/
    Research Clips/<clip-id>/<artifact-id>/<verified package files>
    Local Images/<asset-id>/<original-filename>
    Local Clips/<asset-id>/<original-filename>
  Builds/
    <build-id>/
      timeline-manifest.json
      build-report.json
```

Prefer a filesystem-supported copy-on-write clone when it preserves
independent bytes; otherwise copy. Never move a canonical research package.
Never use ordinary hard links where later mutation could alter canonical
bytes. Record the materialized artifact ID, mode, project-relative locator,
hashes, and verification time in the build snapshot. If a project-local copy
is deleted later, the next build attempts verified rematerialization from the
canonical package, then verified relink, then durable re-export; if
reacquisition is impossible, preserve the clip reference and transcript and
expose missing media rather than substituting unrelated footage.

**Local file import (Phase 5).** Writer-owned local files have different move
authority than research packages. The import dialog (or a visible project
default) chooses `Clone/copy into project`, `Move into project`, `Reference in
place`, or `Ask each time`; the recommended default is copy-on-write clone
with verified copy fallback. A move is never implicit: stage and hash-verify
the project copy before removing the original; cross-volume moves use the same
copy-verify-promote-delete protocol rather than trusting a rename; if original
removal fails, retain both verified files, record the effective result as a
copy, and show an actionable cleanup warning. Never report `move` complete
until the project artifact verifies and original removal has an explicit
outcome.

### 8.3 Voiceover subsystem (Phase 1)

- Temporary speech is an editing aid, not the intended final performance; that
  status is obvious in the script, build report, Resolve metadata, and review
  export.
- Audio generates per narration block — the logical cache and replacement
  unit — never as one monolithic file. Long blocks may be internally chunked
  for provider limits but finalize as one logical block asset with continuous
  timing metadata.
- A build creates speech only for missing or stale blocks; a verified block
  asset is reused when its text, voice profile, pronunciation dictionary,
  synthesis settings, provider/model version, and normalization profile hashes
  are unchanged.
- Preserve word/speech-mark timing when the provider supplies it; otherwise
  run alignment or expose honest sentence/cue precision.
- Store plain text separately from provider-specific synthesis input. Support
  pronunciation dictionary entries, phoneme/alias overrides, emphasis, pacing,
  pause, and named voice/profile. Record provider, model, voice version,
  settings, input hash, output hash, duration, sample rate, and generation
  time.
- **Locked audio:** once a human recording or approved synthetic take is
  attached, a normal rebuild must not regenerate it. A recorded host take can
  replace a temporary block asset while preserving the block ID; because the
  real performance may differ in duration, replacement triggers a
  timing-impact preview and a new compiled timeline.
- Synthesis failure creates audible and visible placeholders; the timeline is
  never silently compressed to hide a missing line. Loudness and sample-format
  normalization run through the media worker; final mixing is editorial work
  in Resolve.
- The prompter artifact generates from host-visibility spans independently of
  whether the timeline uses synthetic or recorded narration.

**Provider boundary.** A narrow `SpeechSynthesisProvider` contract accepts
normalized block text, voice/profile settings, pronunciations, and requested
timing output, and returns audio plus timing/provenance metadata. Revision 2
recommendation for Phase 1: start with one cloud provider that returns usable
word/character timing marks, chosen during Slice 1.2 from current options, and
add a local/offline provider behind the same adapter later. The build model
never encodes vendor-specific voices, SSML, identifiers, or billing
assumptions.

### 8.4 Visual sources (Phase 2 placeholders and local files; Phase 5 full)

A visual request begins as intent: description, purpose, desired duration,
aspect/crop policy, source preference, and rights note. It can resolve to a
research clip, uploaded file, generated image (deferred), licensed stock item
(deferred), URL-backed reference, screen capture, or placeholder slate. URLs
are references, not durable media: a build resolves them into authorized,
checksum-tracked artifacts before placement.

| Input | Resolution behavior | Default composition |
| ----- | ------------------- | ------------------- |
| Logged research clip | Resolve the stable clip/version; reuse its verified export or request the durable export pipeline | Full-frame B-roll with chosen source-audio policy; no invented retiming |
| Webpage URL | Capture via a versioned adapter recording viewport, device scale, final URL, capture time, and profile; persist an immutable image artifact | Full-frame capture with a slow top-left-anchored drift over the event duration |
| Direct image URL | Download the original full-resolution asset once when added; verify type/dimensions, hash, preserve provenance; no recurring acquisition | Contain (largest size keeping the whole image visible); preserve aspect; no animation by default |
| Local image file | Import via the selected clone/copy/move/reference policy; decode, hash, verify; no capture provider involved | Contain; preserve aspect; no animation by default |
| Local video file | Import via the selected policy; inspect streams/duration, hash, verify; never transcode merely to complete import | Selected in/out, audio, framing, speed, and placement policy |

"Fill without cutting anything off" means **contain**, not crop: the complete
image is visible, letterbox/pillarbox space filled by a project background
preset. Stretching and silent cropping are prohibited; crop-to-fill and motion
presets are explicit overrides. Stills receive a motion preset only when the
author chooses one.

Webpage capture uses a local headless-browser worker for public pages — no
browser extension. Authenticated, paywalled, or session-dependent pages are
deferred to an explicitly authorized flow or a user-supplied screenshot; the
product never copies browser cookies into a background worker silently.
Capture records requested URL, final URL after redirects, page title,
timestamp, viewport, device scale, adapter version, artifact hash, and load
warnings; dynamic pages, consent overlays, failed assets, and blocked
automation are visible failure or review states. A hosted capture service must
reject private/local-network targets and apply normal SSRF protections.
Scheduled webpage monitoring is deferred (section 14); capture-on-add plus
manual recapture ships in Phase 5.

### 8.5 Transitions (Phase 5)

Transitions are properties of visual boundaries, not narration paragraphs. A
project sets three independent defaults — `presenterToBroll`,
`brollToPresenter`, `brollToBroll` — each `cut` or a versioned transition
specification with type, duration, easing, and optional template identity.
`Apply to everything` copies one selection into all three slots as a
convenience; the slots remain independently editable. A visual event can
override either adjacent boundary without changing project defaults.

The compiler classifies each boundary from the OC/VO state plus neighboring
events, resolves the effective transition in order — boundary override,
event/type preset, project default, hard cut — and freezes the result in the
build snapshot. Transitions affect picture only by default; audio behavior
requires an explicit audio setting. Transition duration must fit available
handles and adjacent event durations; when it does not, validation asks the
writer to shorten the transition, extend the event, or use a cut — the
compiler never silently moves narration anchors or steals time from another
visual.

---

### 8.6 Shoot audio and color preparation (Phase 7)

Synchronized production audio and processed dialogue are always separate
immutable artifacts. A processing profile may select channel choice and
mapping, optional denoise/de-reverb/de-plosive/de-ess/hum-removal/voice
isolation, EQ or dialogue matching, gain staging and leveling, loudness
normalization for the review target, and output format. Every processor
records settings, provider/tool version, input/output hashes, timing offset,
and measured output properties, and processing is verified not to shift
synchronization. `More processed` is not automatically better: bypass and A/B
comparison are first-class, per video.

Provider strategy: Resolve Studio's own tools (Voice Isolation, Dialog
Leveler, Dialogue Matcher, EQ Matcher, AI Audio Assistant) are tested as a
non-destructive finishing adapter — the Phase 6 spike records which steps the
scripting API can actually drive and which remain operator-assisted. External
enhancement (e.g. Adobe Podcast Enhance Speech) is supported only as **manual
import of a processed result as a versioned artifact** — no web automation,
no required dependency — and at least one local/offline processing path is
compared before a default is chosen.

Color preparation is a versioned, non-destructive profile, never an
irreversible proxy bake: camera/profile, color space/gamma, data levels,
input transform or LUT, timeline color management, and output transform, with
one reviewed transform per camera in the first release and shot outliers
flagged. Uncertain color metadata shows a visible unverified-transform state
rather than silently applying a LUT. Final conform uses masters and
reproduces the approved transform in Resolve; the look baked into a review
proxy is never source truth. Automatic shot matching, skin-tone analysis, and
creative grading are deferred assisted capabilities.

## 9. DaVinci Resolve output architecture

### 9.1 Shared compiler with two delivery adapters (Phase 1)

Every build compiles first into one editor-neutral **canonical timeline
manifest** — integer frames at the project rate, every source, placement,
transition, marker, and provenance reference resolved — before any edition
adapter runs. OTIO is the primary interchange artifact. FCPXML is generated as
a verified fallback **only if the Phase 0 spike demonstrates OTIO gaps on the
tested Resolve versions**; otherwise FCPXML support is parked as a contingency
(section 14) rather than a perpetually-maintained second format. The canonical
manifest remains the authoritative expected timeline for both editions.

**Free adapter.** Requires no Resolve scripting API. Writes a versioned,
self-contained Resolve Import Package: canonical manifest, human-readable
build report, `.otio` (plus `.fcpxml` if enabled), verified project-relative
media and narration files, baked graphic/transition assets where a template
supplies a Free-compatible renderer, labeled placeholder events, an exact
manual-completion checklist, and edition/version-specific import instructions
(`File > Import > Timeline`). The application verifies package structure,
paths, hashes, frame rate, duration, and interchange parseability before
declaring it ready. Because Resolve Free cannot be queried externally, final
in-application placement verification is a user-confirmed post-import step —
described honestly, never claimed as automated.

**Studio adapter.** Begins with the exact same verified import package, then
uses Resolve's external Python scripting API for project creation, bins, exact
track setup, media import, timeline item placement, markers, Fusion
title/generator insertion, timeline verification against the manifest, and
optional rendering. It requires a supported standard desktop Studio
installation with external scripting enabled; it never falls back to UI
automation and never assumes the Mac App Store build exposes external control.

Capability matrix (published from Phase 0 testing, not inferred from
marketing):

| Capability | Free mode | Studio mode |
| ---------- | --------- | ----------- |
| Authoring, media prep, voice, timing | Full | Full |
| Canonical manifest and interchange | Full | Full |
| Timeline creation in Resolve | One manual import | Automated through supported API |
| Resolve-specific bins/metadata | Best-effort interchange plus manual checklist | Automated and verified |
| Fusion/template behavior | Native interchange, baked asset, or placeholder | Live versioned Fusion insertion when tested |
| Music cue and mix intent | Native interchange when tested; otherwise baked/manual, reported | Versioned placement with tested gain/fade/ducking, verified |
| Required non-English subtitles | Tested native/title/baked visible representation | Versioned branded representation, verified |
| Script video markers | Native interchange when tested; otherwise report | Native stable-ID marker placement and verification |
| Resolve-side timeline verification | User-confirmed after import | Automated against canonical manifest |
| Review render and Drive handoff | Manual | Optional durable automation |
| Update behavior | New immutable import package / new timeline | Phase 10: three-way review, selective plan, new verified timeline by default |

### 9.2 Predictable track map (Phase 1)

| Track | Default purpose |
| ----- | --------------- |
| V1 | Primary picture or presenter/A-roll placeholder |
| V2 | Research clips and featured source footage |
| V3 | B-roll and still images |
| V4 | Fusion graphics, titles, and overlays |
| V5 | Debug slates or unresolved placeholders; can be disabled for clean review |
| A1–A2 | Generated or recorded narration |
| A3–A4 | Source clip audio |
| A5 | Approved music cues and sound effects |
| S1 | Required English subtitle copy for non-English/mixed/unknown speech |

### 9.3 Build sequence (Phase 1 core; later phases add stages)

1. Authorize the requested build class; freeze an immutable build snapshot
   from the acknowledged live head (`preview`) or an approved checkpoint
   (`release`). Validate row order, timeline rate, asset identities, and voice
   settings.
2. Resolve every template/music use through its pinned revision and settings;
   freeze complete effective values. No stage or retry ever asks for
   `latest`.
3. Build the media-preparation plan: resolve exact artifact candidates, verify
   manifests/hashes and compatibility, classify missing or invalid locators,
   freeze effective reuse/media policies.
4. Resolve or generate changed narration, clip packages, stills, and graphics
   dependencies; copy/clone or reference verified packages into the authoring
   workspace; record hashes, locators, and actionable failures.
5. **Calculate durations.** Narration is the default timing spine. Resolve
   text anchors to verified speech timing, compile OC/VO spans and
   visual-event ranges into integer frames, apply explicit timing overrides
   and transitions, and report anchor/alignment precision honestly.
6. Resolve each clip occurrence's use range against the immutable logged range
   and verified media; compile approved subtitle copy into timed events with
   the frozen brand preset (Phase 8), validating reading speed, layout, safe
   area, and coverage.
7. Resolve every visual source into a verified immutable artifact; classify
   boundaries and compile effective transitions, validating duration and
   handles (Phase 5).
8. Emit the canonical timeline manifest — including every placed/unplaced
   marker — plus a human-readable build report. **Manifest emission is
   deterministic: the same frozen inputs produce a byte-identical manifest.**
9. Generate and parse-verify interchange against the manifest, materialize
   project-relative media, and finalize the immutable Resolve Import Package.
   Classify every non-representable item as baked, placeholder, or manual
   completion — never drop one silently.
10. Free: stop at `ready_to_import`, show exact import instructions, and let
    the user confirm the imported timeline/build ID without implying automated
    inspection.
11. Studio: create or select the target project, import into deterministic
    bins, create a new timeline named from the build ID/revision, place
    items, insert supported Fusion templates, and add row/build IDs as marker
    custom data where supported.
12. Studio: save the project, verify item counts/durations/track names against
    the manifest, and report discrepancies. Optionally export a DRT backup;
    retain the interchange package for recovery and portability.

### 9.4 Rebuild safety (Phase 1; Phase 10 extends)

Initial builds always create a new timeline. Free updates produce a new
immutable import package imported as a new timeline by default. Studio records
a `ResolveSyncBaseline` only after the generated timeline verifies against the
manifest. Every managed clip occurrence, subtitle event, marker, narration
block, and graphic keeps stable identity across builds where its authoring
identity survives. Until Phase 10 ships, **the update path is always a new
timeline** — simple, safe, and honest; in-place selective regeneration through
Regeneration Review is the Phase 10 capability, not an early shortcut.
Arbitrary ripple edits, replacements, and effects whose attachment cannot be
established are conflicts, never guessed merges. Never rebuild over the sole
edited timeline in either edition.

### 9.5 Review render and delivery (Phase 2, Studio only)

After Studio timeline assembly passes manifest verification, the build may
continue through optional stages: render a review preset to a staging path
(normally H.264/AAC MP4 at project resolution/rate); inspect with FFprobe and
validate duration, streams, nonzero size, and expected build/revision
metadata; atomically promote the verified MP4 into the completed-artifact
directory; if requested, upload through a `ReviewDeliveryProvider` (initially
Google Drive, resumable where supported); verify remote identity/size, record
the Drive file ID and URL, and mark delivery complete. Sharing permissions are
an explicit separate choice — upload never silently makes the file public.

The local MP4 remains a successful artifact if upload fails; the upload stage
retries without rebuilding or rerendering. A new revision produces a new
review artifact and never overwrites an earlier shared review unless the user
selects a version-replacement policy. Free users render and upload manually
after import.

### 9.6 Background build experience (Phase 1 job core; Phase 2 UI)

Submitting either delivery action freezes the authorized source and creates a
durable `VideoBuildJob`; the browser may close without canceling it. Both
modes report `queued → generating speech → resolving media → compiling →
writing interchange → verifying import package`; Free then reports
`ready_to_import → import_confirmed`; Studio continues through `building
Resolve timeline → verifying timeline → rendering MP4 → verifying MP4 →
uploading → complete`, with unrequested stages labeled skipped rather than
hidden.

Jobs use idempotency keys, attempts, progress, cancellation boundaries, and
worker leases; retry resumes from the last verified immutable artifact. Free
package preparation requires the local agent but not Resolve. Studio
automation requires a running supported installation; sleep, shutdown, closed
Resolve, disabled scripting, or license mismatch moves the job into a
resumable waiting/needs-action state rather than losing it.

---

### 9.7 Recorded conform compilation (Phase 7)

A recorded conform is the same compiler and delivery pipeline with a different
timing source: for each beat, the approved take's verified word alignment
replaces the synthetic narration timing, and every text-anchored event
recompiles against the recorded words under its declared duration policy
(section 6.15). Approved presenter picture and production/processed audio are
placed on V1/A1–A2 in master source time; the temp-narration assets for those
beats are omitted, while explicitly locked temp-voice beats keep them. The
conform emits the same canonical manifest and build report, flows through the
same Free/Studio adapters, and always produces a new timeline. Before final
render, the bridge verifies that every proxy-reviewed edit relinks to the
expected master hash and time base; a wrong or missing relink blocks the
conform rather than degrading it.

Suggested ingest/analyze job states: `queued → registering → probing →
proxying → transcribing → aligning → analyzing → ready_for_review`, with
`waiting_for_source`, `needs_sync_review`, `failed`, and `canceled` exits.
Conform states: `queued → validating → preparing_audio → compiling →
building_timeline → verifying_timeline → rendering_review → verifying_review
→ complete`, with `needs_take_review`, `needs_media`, `needs_relink`, and
`needs_reconciliation` holds. Verified proxies, transcripts, alignments, and
processed audio are reused whenever their full input/profile hashes match;
job retry creates no duplicate approvals, candidates, timelines, or
artifacts.

## 10. System architecture and stack

Revision 2 commits to a concrete default stack. This is a deliberate change
from Revision 1's neutrality: for AI-agent execution, unresolved technology
choices are ambiguity that compounds across every slice, and each commitment
below sits behind a contract boundary that keeps it revisable.

| Component | Choice | Notes |
| --------- | ------ | ----- |
| Repository | One monorepo | TypeScript workspaces plus a Python package; all contracts in one place |
| Shared contracts | Versioned JSON Schemas in `/contracts` | `ScriptDocument v1`, `TimelineManifest v1`, `BuildReport v1`, agent RPC. Types generated for both TS and Python. **Frozen between slices; changed only by an explicit contract-change slice.** |
| Web client | React + Vite + TypeScript | Tiptap (ProseMirror) editor; Yjs wired from Phase 2 even for single-user |
| API + collaboration service | Node + TypeScript, PostgreSQL | Yjs sync (y-websocket-compatible protocol) with durable, attributed update log; REST/JSON for resources; object storage abstraction (filesystem first, S3-compatible later) |
| Local agent | Python (uv-managed) | FFmpeg/FFprobe, voice provider calls, OpenTimelineIO (mature Python bindings), Resolve external scripting API, headless-browser capture worker, shoot ingest/proxy/transcription/alignment workers (Phase 6), artifact cache. Talks to the API over an authenticated job-lease protocol |
| Compiler | TypeScript library in the API workspace | Pure function: frozen `ScriptDocument` + resolved dependencies → `TimelineManifest` + `BuildReport`. Deterministic; golden-file tested. Manifest → OTIO conversion happens in the Python agent |
| Hosting | Managed Postgres + small Node host (e.g. Fly.io/Railway class) | Writers use the hosted web app; the local agent runs on the producer's workstation, where Resolve and media live |

The deployment shape: collaborators anywhere use the hosted web app; builds
that touch media, voice files, or Resolve execute on the producer's
workstation through the local agent, which polls/leases jobs from the API.
Free package preparation needs only the agent; Studio stages need Resolve
running.

Component responsibilities (carried forward from Revision 1, assigned to the
stack above): web client (structured editor, presence, comments, history,
inspectors, build UI); authoring API (projects/memberships, comments,
checkpoints, media references, template registry, build snapshots, idempotent
commands, permissions); collaboration service (authenticated operation-based
sessions, ephemeral presence, per-user undo origins, durable attributed
updates, reconnect, snapshots, materialization into the canonical typed
tree); local agent (filesystem, verified imports, downloads, configured-root
artifact lookup, manifest/hash verification, media materialization,
OTIO writing/verification, Resolve edition discovery, Studio automation);
research clip adapter (versioned API client to the existing catalog and
export worker); provider adapters (voice, review delivery/Drive,
notifications, webpage capture; image generation and stock search deferred).

### 10.1 Persistence and identity rules

- UUIDs for every entity listed in section 7. Immutable artifact versions and
  content hashes everywhere; **a path is a locator, not identity.**
- Collaborative authoring intent persists as durable attributed operations
  plus materialized typed snapshots; comments, checkpoints, templates, and
  build records persist transactionally; large artifact bytes live in object
  storage or the verified local cache.
- Append-only actor/client-transaction/server-order history for accepted
  document operations. Compaction may optimize reconstruction but never
  destroys checkpoint replay, attribution, or audit evidence.
- Long work is durable, observable, retryable jobs with idempotency keys,
  attempts, progress, cancellation boundaries, and leases.
- Every build snapshots its external dependencies: clip/version, artifact
  hash, voice settings, template revisions, resolved occurrence settings,
  timeline settings, delivery mode, detected edition/version, capability
  matrix, adapter versions, and every fallback/manual-completion decision.
- Logged ranges persist separately from occurrence-specific use ranges;
  baseline transcripts separately from subtitle-copy revisions and compiled
  caption events; marker anchors separately from compiled frames.
- `preview` versus `release`, source identity, submitting actor, and resolved
  dependency hashes persist on every build. A later edit, label change, or
  deprecation is new state, never mutation of an accepted snapshot.
- Expiring Resolve target claims persist separately from build state; claim
  recovery never implies a partially applied timeline passed verification.

---

## 11. Execution plan: slices

This section replaces Revision 1's milestone list with the unit AI agents
actually execute well: a **slice** — one bounded piece of work with explicit
scope edges, the contracts it may touch, and a binary done-condition. Slices
within a phase are ordered; a slice may begin when the ones it builds on are
done. Every slice ends with two things: **automated checks** (tests the agent
writes first and CI runs forever) and an **acceptance script** — a numbered
click-through or command sequence the producer runs personally. The acceptance
script is authoritative: a slice the producer cannot verify is not done.

Sizing intent: one slice ≈ one focused agent working session plus one
producer acceptance pass. If a slice turns out to contain two, split it —
never let a slice's scope grow to fit the work.

### Phase 0 — Foundations and Resolve capability spike

*You can now trust the Resolve boundary. Nothing here is product code except
the contracts and fixtures; the point is to convert the two scariest unknowns
(OTIO import fidelity, Studio scripting reliability) into a published,
version-stamped capability matrix before anything depends on them.*

**Slice 0.1 — Repository, contracts, and fixture scaffold.** Create the
monorepo (TS workspaces + Python package), CI running lint/tests on both
sides, `/contracts` with the first drafts of `ScriptDocument v1`,
`TimelineManifest v1`, and `BuildReport v1` JSON Schemas plus generated types,
and `/fixtures` with a deterministic media kit: three short test clips, two
stills, one audio bed, all with recorded hashes. Also create `DECISIONS.md`
and `CAPABILITIES.md` (empty).
*Done when:* CI is green on a fresh clone; the producer can run one documented
command that validates all fixtures against the schemas.

**Slice 0.2 — Handcrafted manifest → OTIO package.** In the Python agent
package, write a converter from a small handcrafted `TimelineManifest` fixture
(three trimmed clips, one still, one narration audio file, one marker, hard
cuts) to a self-contained folder: `.otio`, media, import instructions, build
report. No compiler, no UI, no jobs.
*Done when:* the producer opens the folder, reads the instructions, and the
report lists every event; automated checks parse the OTIO back and match it
against the manifest event-for-event.

**Slice 0.3 — Resolve Free import trial.** On the actual Resolve Free
installation(s) the team uses, manually import Slice 0.2's package. Record in
`CAPABILITIES.md`: exact Resolve version, item counts, durations, track
names/order, media link status, marker fidelity, transition fidelity, and
every discrepancy. Repeat with an FCPXML export of the same manifest and
record whether FCPXML closes any gap OTIO leaves. **Exit decision, recorded in
`DECISIONS.md`: FCPXML is either enabled as a maintained fallback or parked.**
*Done when:* `CAPABILITIES.md` contains the tested Free matrix and the FCPXML
decision is recorded with its evidence.

**Slice 0.4 — Resolve Studio scripting spike.** Python agent code that
detects Resolve edition/version and external-scripting availability; then,
via the supported API: creates a project and bins, imports Slice 0.2's media,
builds a timeline placing three trimmed clips at exact record frames plus
narration audio, inserts one stock Fusion title, attaches marker custom data,
saves, reopens, and verifies item counts/durations/track names against the
manifest. Prove the safety boundary: with Free selected the scripting API is
never invoked (test-enforced), and Studio mode against a Free, App Store, or
disabled-scripting installation stops cleanly after the import package with an
actionable message.
*Done when:* the producer watches one command produce a correct timeline in
Studio, and `CAPABILITIES.md` records the tested Studio matrix and minimum
supported versions for both editions.

**Phase 0 gate:** one deterministic fixture produces a correct, reopenable
manually imported timeline in Resolve Free and a correct externally automated
timeline in Resolve Studio, both from the same manifest and media, with no UI
automation anywhere and every edition-specific difference recorded.

### Phase 1 — Walking-skeleton compiler

*You can now turn a structured script file into a temp-narrated rough cut.
There is still no editor: the canonical `ScriptDocument` JSON is authored as a
file. This is deliberate — the contracts harden against real material before
the UI exists, and the producer gets the product's core magic while the editor
is still being designed.*

**Slice 1.1 — ScriptDocument v1 and the validator.** Finalize the
`ScriptDocument v1` schema for Phase 1 block types (section, narration,
direction, visual, note/draft, host-visibility spans, visual events with
still/local-video/placeholder sources). Implement the semantic validator as a
pure TS library plus CLI: every spoken token in exactly one visibility state;
every VO interval covered by a full-frame visual or explicit placeholder; no
zero-duration events; anchors resolve to real tokens. Write two fixture
scripts: a minimal one and a torture one (mid-sentence cuts, overlapping
overlay + OC, back-to-back VO visuals).
*Done when:* the CLI prints human-readable pass/fail with row references; the
producer can break a fixture on purpose and see the exact complaint Revision 1
promised (gaps and contradictions are errors, not defaults).

**Slice 1.2 — Voice adapter and block asset cache.** Choose the initial cloud
voice provider (evaluate current options for word/character timing marks,
pronunciation control, and cost; record the choice and rationale in
`DECISIONS.md`). Implement `SpeechSynthesisProvider`, per-block synthesis,
`NarrationAudioAsset` records with all identity hashes, loudness/sample
normalization via FFmpeg, and cache reuse: unchanged text + settings never
re-synthesizes.
*Done when:* the producer runs a command over a fixture script, hears each
block as a separate normalized file, reruns it and sees every block reported
as reused, edits one block's text and sees exactly one regeneration.

**Slice 1.3 — Compiler core: anchors to frames to manifest.** The pure
function from frozen `ScriptDocument` + narration assets + resolved visual
artifacts to `TimelineManifest` + `BuildReport`: narration as timing spine,
text anchors resolved through provider timing marks with honest precision
labels, OC/VO and visual events compiled to integer frames on the section 9.2
track map, hard cuts only, placeholders slated on V5. Golden-file tests: the
torture fixture compiles to a byte-identical manifest on every run and on
every machine.
*Done when:* automated golden tests pass twice consecutively in CI; the
producer reads the build report and can trace one narration sentence to its
frame range.

**Slice 1.4 — Package writer and verification.** Wire the compiler output
through the Slice 0.2 converter into the full verified Resolve Import Package,
with media materialized into the section 8.2 project layout (copy/clone,
hash-verified) and the package-verification pass (structure, paths, hashes,
rate, duration, parseability) gating `ready_to_import`.
*Done when:* the producer imports the package into Resolve Free and the rough
cut plays with temp narration; the report's manual-completion list matches
what they see.

**Slice 1.5 — Fusion semantic-input capability spike.** Before production
Studio assembly, use a producer-authored, hash-pinned lower-third template and
an internal test request to prove the documented Resolve/Fusion APIs can find
the expected composition and controls, set required primary text, optional
secondary text, and accent color, read the exact values back, save/reopen, and
verify them again. Place the template through the accepted pinned-template
path on V4 at two exact durations. Do not change shared contracts, frozen
fixtures, or accepted tests; do not implement the curated graphics product or
its authoring UI. Record version-stamped behavior in `CAPABILITIES.md`. See
the [curated Fusion graphics plan](plans/curated-fusion-graphics.md) for the
bounded spike and later productization sequence.
*Done when:* automated checks prove unexpected graph/control identities fail
closed, and the producer visually accepts correct data, placement, duration,
and animation at both tested durations after save/reopen.

**Slice 1.6 — Studio assembly from the same build.** The agent consumes the
same package via the Studio API path proven in Slice 0.4: new project or
selected project, deterministic bins, new timeline named from build ID,
verification against the manifest, discrepancy report.
*Done when:* the producer runs one command and gets a verified Studio timeline
identical (per verification) to the Free import of the same build.

**Slice 1.7 — Durable build jobs.** `VideoBuildJob` with the section 9.6
stage model, idempotency keys, leases, resume-from-last-verified-artifact, and
a CLI status view. Kill the agent mid-build and restart it.
*Done when:* the producer starts a build, force-quits the agent during speech
generation, restarts it, and the build completes without regenerating finished
blocks.

**Slice 1.8 — First real script.** One-time, agent-assisted conversion of the
"OEV25 Finland" document (or the current production's script) into a
`ScriptDocument` fixture, reviewed by the producer for row types and
OC/VO/coverage intent. This replaces Revision 1's heuristic-importer product
feature: the back catalog is finite and the conversion is supervised, so it is
a task, not a subsystem. Build it through both delivery modes.
*Done when:* the producer watches a temp-narrated rough cut of a real script
in Resolve, checks the prompter-relevant OC/VO structure against intent, and
files the discrepancies as issues.

**Phase 1 gate:** a real script compiles deterministically into a
temp-narrated rough cut through both delivery modes; unchanged blocks are
reused across rebuilds; the build survives an agent restart. The producer has
used the output on real material.

### Phase 2 — Single-writer authoring app

*You can now write in the product and build with one button. The document
model underneath is the collaborative one (Yjs-backed) from the start, serving
one user; Phase 3 turns on the crowd.*

**Slice 2.1 — App shell and document persistence.** Web app with sign-in
(single account for now), project creation with timeline settings, and a
Tiptap document whose custom nodes carry the stable IDs and typed attributes
of section 7, persisted through the Yjs update log with materialization into
canonical `ScriptDocument` JSON. Round-trip property test: editor state →
canonical JSON → validator.
*Done when:* the producer creates a project, types narration and section
headings, reloads, and nothing is lost; a hidden dev command exports canonical
JSON that passes the Slice 1.1 validator.

**Slice 2.2 — Two-column editor.** The section 6.1 grid: narration,
direction, section, note/draft, and blank rows; visually primary left column;
typing-first behavior (a blank right cell is text until @, paste, drag, or
Insert); row build-state indicators (excluded/ready/unresolved for now).
*Done when:* the producer recreates one page of the example script's structure
without touching a menu more than necessary, and it prints/readably exports as
a script a human can follow.

**Slice 2.3 — OC/VO spans.** Range marking without paragraph splits; semibold
OC rendering plus the accessible state control and inspector value; live
coverage validation surfaced inline (VO span without coverage shows the
Revision 1 error affordance); span editing (extend, shrink, split state at a
word).
*Done when:* the producer marks OC → VO → OC across one intact paragraph,
sees the weight change and the coverage error until a visual or placeholder
covers the VO span, and confirms weight is never the only state signal.

**Slice 2.4 — Visual events and cards.** Select words → create visual event;
right-column cards (local image, local video, placeholder) with approximate
alignment and compact coverage labels; bidirectional hover highlighting;
overlapping and successive ranges in one paragraph; the inspector with
timing/audio/fit/provenance; full-frame events defaulting a VO span over their
range; overlays coexisting with OC.
*Done when:* the producer attaches two visuals to different word ranges of
one paragraph, hovers each to see its words highlight (and the reverse), and
builds a preview in which the cuts land where the words say.

**Slice 2.5 — Prompter export.** Section 6.5 exactly, deterministic, with
validation blocking export when any spoken range lacks a camera state.
*Done when:* the producer exports the example script's narration and the (OC)/
(VO) markers appear exactly at transitions with wording and order untouched;
exporting twice yields identical files.

**Slice 2.6 — Markers and citations.** Section 6.13 point markers on a word,
clip boundary, or between blocks, with notes, placed/unplaced state, and
compile-through to the manifest; citation rows preserved in script and report.
*Done when:* the producer places two markers, builds, and finds them as named
Resolve markers at semantically correct positions; deleting anchored text
makes the marker visibly unplaced rather than gone.

**Slice 2.7 — Build from the app.** Pair the local agent with the project
(one-time token); the Preview action freezes the current saved revision,
submits a durable job, and streams stage progress in a Resolve view showing
last build, track map, warnings, and changed blocks; per-block audio states
with preview/regenerate-one-block; preview timing mode with row-level spans.
Free shows **Prepare Resolve timeline**; Studio shows **Build in Resolve**.
*Done when:* the producer goes from edited script to verified Studio timeline
(and separately a Free package) without leaving the app, closes the browser
mid-build, reopens, and finds the job completed.

**Slice 2.8 — Review render and Drive delivery.** Section 9.5: `Timeline +
review MP4` and `+ Drive upload` menu options, FFprobe verification, atomic
promotion, resumable upload, explicit sharing policy, retry-without-rerender.
*Done when:* one action yields a playable MP4 link in the chosen Drive folder;
the producer simulates an upload failure (network off) and retries without a
rerender; the file is not publicly shared unless explicitly chosen.

**Phase 2 gate:** the producer authors a short real script in the app —
spans, visuals, markers, prompter — and ships a temp-narrated rough cut plus
review MP4 to collaborators without touching a fixture file. From this point
the product, not Google Docs, is where new scripts start.

### Phase 3 — The writing room

*You can now write with your collaborators: live cursors, comments, history,
checkpoints, Ideas and Extras. Roles are three, not six; approval is a label,
not a workflow.*

**Slice 3.1 — Accounts, membership, roles.** Real multi-user auth against the
suite identity; project membership with producer/editor/viewer; every
mutation attributed; role removal effective on next request and terminating
write sessions promptly. Research-project authorization remains independent
(enforced now, exercised in Phase 4).
*Done when:* the producer invites an editor and a viewer; the viewer can read
everything and change nothing; demoting the editor mid-session revokes their
write access promptly.

**Slice 3.2 — Live collaboration.** Multi-client Yjs sessions with presence
(collaborators, connection state, cursors/selected cards), the five sync
states, per-user undo, and reconnect-with-merge at Yjs's natural level.
Concurrency tests: overlapping prose edits, simultaneous card reorder,
disconnect/reconnect without accepted-work loss.
*Done when:* the producer and a collaborator edit the same paragraph from two
machines, both contributions converge, each person's undo removes only their
own work, and pulling one machine's network cable for a minute costs nothing.

**Slice 3.3 — Comments.** Section 6.8 threads: range/block/point anchors,
replies, mentions with notifications, resolve/reopen, attributed edits, stale
state with explicit reattachment. Proof that comments never enter narration,
duration, prompter, or build input.
*Done when:* a mentioned collaborator gets notified and replies; deleting the
commented text turns the thread visibly stale instead of moving it; a build
and prompter export from a heavily commented script are unchanged.

**Slice 3.4 — History and checkpoints.** Attributed revision history grouped
readably from the operation log; named checkpoints materializing all three
surfaces; semantic compare (prose, structure, card properties, anchors);
Producer **approved** label; restore-as-new-head preserving checkpoint,
intervening history, comments, and builds.
*Done when:* the producer names a checkpoint, keeps editing, compares the two
states, restores the checkpoint, and verifies the later edits still exist in
history; nothing anywhere rewound destructively.

**Slice 3.5 — Preview/release rules.** Editor-or-Producer preview from the
fully synchronized live head (with the section 6.8 sync guarantee); Producer
release only from an approved-labeled checkpoint; both immutable; the build UI
shows the frozen source and whether the live head has advanced.
*Done when:* an editor's preview records its exact revision; the same editor
cannot release; the producer can, only after labeling a checkpoint approved;
continued editing changes neither completed build.

**Slice 3.6 — Ideas.** The section 6.6 outliner: nesting, drag/reorder,
indent/outdent, collapse, open/incorporated; promotion into a chosen draft
location with backlink; a script may exist with only Ideas.
*Done when:* the producer plans a video top-down in Ideas, promotes three
items into the Draft where they belong, and confirms Ideas content never
appears in validation, prompter, timing, or builds.

**Slice 3.7 — Extras.** `Move to Extras` for text, rows, and structured
fragments with full fidelity and provenance; restore at a chosen location;
duplicate-to-Draft with new identities; stale-reference marking; appendix
option on human-readable exports only.
*Done when:* the producer moves a scripted-but-cut passage (cards and all) to
Extras, builds (no effect), restores it two sections later intact, and ordinary
delete still works as delete.

**Phase 3 gate:** the writing team drafts a real script together in the
product — concurrent editing, comments, a checkpoint the producer approves and
releases — and the Revision 1 acceptance behaviors for collaboration
(convergence, stale anchors, no comment leakage, restore-preserves-history)
all pass on that real script, not just fixtures.

### Phase 4 — Research clip integration

*You can now write with the clip library: search logged clips, drop them in
as transcript text, refine each use, and build with verified reused media.*

**Slice 4.1 — Research adapter and clip insertion.** Versioned API client to
the research catalog; clip search by project/tags/note/title/transcript;
drop-onto-narration creating a `VisualEvent` with stable clip ID, snapshotted
transcript/version/bounds, and transcript text as the card's readable
representation. Independent authorization enforced per read.
*Done when:* the producer finds a clip by a remembered phrase, drops it onto
the words it should cover, and sees its transcript in the script; a member
without research access sees an authorization error, not cached data.

**Slice 4.2 — Artifact resolution.** `ArtifactRequirement` per occurrence at
build time; manifest/hash verification of reachable packages (`complete`
catalog status alone is never a cache hit); configured-root search; verified
`Locate` relink; durable idempotent re-export requests through the existing
export boundary; the section 8.2 resolution table implemented, with block or
labeled-placeholder policy for the unreachable.
*Done when:* the producer builds with a package present (reused, no render),
then moves it (relinks after verification), then deletes it (exactly one
re-export requested), and the report tells that whole story truthfully.

**Slice 4.3 — Materialization and policies.** Copy/clone into
`Media/Research Clips/`, independent reuse and project-media policies with
recommended defaults, the pre-build media summary (reused / materialized /
exported / relinked / unresolved counts plus estimated disk), and focused
remediation only for blockers.
*Done when:* the producer sees an accurate preparation summary before a build
proceeds without interruption, and the canonical research packages are
untouched afterward (verified by hash).

**Slice 4.4 — Refine clip.** Section 6.11: the compact player with
waveform/transcript context, honest boundary snapping (word → cue → frame
precision modes), inward-only enforcement, loop-preview of the proposed
range, reversible reset, readable excerpt following the refined range, and
compile-through of exact chosen frames with recorded precision.
*Done when:* the producer trims a quote to its strongest eight seconds, the
script text shows only what survives, both delivery outputs contain exactly
those frames, a second occurrence of the same clip is unaffected, and reset
restores everything.

**Slice 4.5 — Update-available flow.** Detect changed research records;
`update available` on affected cards with keep-snapshot / update-reference /
compare choices; never silent retargeting.
*Done when:* re-logging a clip in the research tool surfaces the notice in
the script and choosing "keep snapshot" provably keeps builds byte-stable.

**Phase 4 gate:** a real script section quoting three research clips —
including one refined use and one repeated clip — builds through both modes
with verified reuse, and the research project's canonical records and packages
are bit-identical before and after.

### Phase 5 — Visual sources and transitions

*You can now source visuals the way the example script actually does —
webpages, images, local files — and control the cut feel at each boundary
type.*

**Slice 5.1 — Local file import.** Section 8.2 local-import protocol:
clone/copy default with verified fallback, explicit move with
copy-verify-promote-delete (cross-volume included), reference-in-place as
advanced, `LocalMediaImport` records with fingerprints and removal outcomes,
failure table rows for undecodable files and failed removals.
*Done when:* the producer imports one image by clone and one video by move,
verifies both play in a build, simulates a removal failure and sees both files
retained with the effective-copy warning and a retryable cleanup.

**Slice 5.2 — Direct image URLs.** One-time full-resolution acquisition,
type/dimension verification, hashing, provenance; contain composition with
project background preset; no animation and no recurring acquisition.
*Done when:* the producer pastes an image URL, and a mismatched-aspect image
appears complete (letterboxed, not cropped or stretched) for exactly its
covered words.

**Slice 5.3 — Webpage capture.** Local headless-browser worker for public
pages: previewed viewport/region, capture-on-add, immutable artifact with full
provenance (final URL, timestamp, viewport, scale, adapter version, warnings),
manual recapture creating a new revision, default top-left drift preset,
SSRF protections, and visible failure states for consent overlays and blocked
automation. No scheduled monitoring (deferred).
*Done when:* the producer captures a previewed region of a public page and the
build shows the still drifting for exactly the event's duration; a recapture
appears as a new selectable revision without changing any existing build.

**Slice 5.4 — Transitions.** Section 8.5: three independent project defaults,
`Apply to everything` shortcut, per-boundary event overrides, ordered
resolution, handle/duration validation with corrective choices, frozen results
in the snapshot.
*Done when:* the producer sets three different defaults, sees each compiled
boundary use the right one in Resolve, overrides one boundary on one event,
and a transition that doesn't fit is blocked with the offered fixes instead of
shifting narration.

**Slice 5.5 — Secondary timing mode.** The refinement surface promised in
section 6.2: per-paragraph timing view for fine-tuning compiled frame
boundaries as explicit `timingOverrides`, without changing the paragraph or
its semantic anchors; visible precision labels.
*Done when:* the producer nudges one cut two frames earlier, rebuilds, and
only that boundary changed; the paragraph text and anchors are untouched.

**Phase 5 gate:** one continuous narration passage resolves a logged clip, a
webpage capture, a direct image URL, a local image, and a local video; keeps
full images visible; applies the drift for exactly its range; and produces the
independently selected transition at each boundary without shifting narration
timing — in both delivery modes.

### Phase 6 — Shoot ingest and take review

*You can now ingest a real line-shoot recording and approve a performance for
every beat without opening Resolve. Slice 6.1 depends only on Phase 1
contracts and may be run early if a shoot is imminent.*

**Slice 6.1 — Alignment corpus and capability spike.** Build a small licensed
fixture shoot against a frozen fixture script: several repeated reads per
beat, one intentional ad-lib, one flub, one partial take, and one omitted
line, recorded in the team's actual style (one camera, line-by-line repeats).
On the actual workstation, evaluate Resolve Studio IntelliScript: output
quality, alternative-take layout, what metadata supported interfaces can
actually read back, and scripting limits. Compare at least one independent
transcription/word-alignment route on the same fixture. Test which Resolve
audio tools (Voice Isolation, Dialog Leveler, Dialogue Matcher) supported
automation can drive, recording operator-assisted steps. Record everything in
`CAPABILITIES.md`.
*Done when:* `DECISIONS.md` records the provider strategy — chosen on
measured alignment quality, inspectability, automation, privacy, speed, and
cost, not feature names — and whether IntelliScript is an optional
operator-assisted path or absent from the plan.

**Slice 6.2 — Performance beats and the prompter sidecar.** Implement
`PerformanceBeat` derivation (default one per sentence, merge/split before
freeze), the machine-readable sidecar added to the Slice 2.5 prompter export
(visible text unchanged; optional beat numbers), expected-text and
normalized-spoken-text hashes, and reconstruction of a beat map from any
older export's recorded document revision.
*Done when:* the producer freezes a prompter export, sees natural prose plus
a sidecar listing every beat in order, and reconstructs an identical beat map
from a pre-sidecar export of the same revision.

**Slice 6.3 — Shoot sessions and source registration.** `ShootSession`
against a frozen prompter revision; add camera master files with hash/probe
registration, full stream/timecode/color-metadata inspection, provenance-only
filenames, hash-based moved-file detection, and verified relink that never
creates a new source identity. Multiple files per session; no ordering or
continuity assumptions.
*Done when:* the producer registers a multi-file shoot, renames and moves one
file on disk, and relink recovers it by hash with its identity and history
intact.

**Slice 6.4 — Review proxies and derivatives.** Profile-driven proxy
generation (never / above-threshold / always; resolution, bitrate,
browser-safe codec), waveform/audio extraction, immutable proxy hashes with
generator versions, verified duration/time-base correspondence to the master,
cache location and space accounting, and resumable ingest jobs using the
Phase 1 job core.
*Done when:* the producer scrubs a long master smoothly in the browser from
its proxy, and an automated check proves proxy time maps to master time
frame-exactly; killing the agent mid-ingest and restarting resumes without
duplicate work.

**Slice 6.5 — Transcription, alignment, and candidate takes.** Word-timed
transcription of production audio; alignment against the frozen beat map with
bounded insertions/deletions/paraphrases; segmentation of repeated reads,
restarts, partials, ad-libs, and uncovered spans; `TakeCandidate` records with
handles, transcript diffs, and separated evidence components (coverage,
confidence, complete-read, audio warnings, pace outliers). The matcher's
prohibitions are test-enforced: no forced matches, no hidden uncovered beats,
no boundary that splits a word, no discarded off-script material.
*Done when:* run against the Slice 6.1 fixture, candidates cover every actual
read; the ad-lib, flub, partial, and omitted line are all exposed honestly;
and no beat shows an invented exact match.

**Slice 6.6 — The takes drawer.** Beat state badges in the script editor; the
drawer with proxy playback in master timecode, rapid sequential candidate
playback, A/B comparison, keyboard approve/reject, expected-versus-recognized
text with highlighted differences, waveform/meters, bounded trim handles;
outcomes (active take, alternates, temp voice, needs pickup, no spoken line);
versioned `TakeAssignment` with locks; reanalysis never unseating an approved
take.
*Done when:* the producer selects the intended take for every fixture beat
without opening Resolve, marks one beat needs-pickup, reloads and reanalyzes,
and every decision survives exactly.

**Slice 6.7 — Play approved performance.** Script-ordered preview of the
approved takes from proxies, making gaps, missing beats, and abrupt joins
audible/visible before any build; a summary of unresolved beats.
*Done when:* the producer plays the whole fixture script as approved takes
end to end and can hear where the needs-pickup hole is.

**Phase 6 gate:** a real (or fixture) line-shoot ingests, aligns, and reviews
entirely in the product: every beat reaches an explicit outcome, decisions
survive reload and reanalysis, and the approved performance plays in script
order — with masters untouched and every reviewed range provably mapped to
master time.

### Phase 7 — Recorded performance conform

*You can now build the video with your real performance: recorded picture and
audio replace the temp voice, and every text-anchored visual moves to the
words you actually spoke.*

**Slice 7.1 — Conform snapshot and impact preview.** Per-beat timing-source
resolution (approved take / locked temp voice / explicit silence / blocking
unresolved), visual-event duration policies compiled per the section 6.15
table with `follow_text_anchors` as default, `RecordedConformSnapshot`
freezing assignments/trims/profiles, and the pre-build impact preview: old
and new durations, cumulative shift, moved events, too-short source media,
and reconciliation items.
*Done when:* the producer sees, before building, exactly how much longer the
recorded version runs and which B-roll boundaries will move; a beat left
unresolved blocks with a useful message instead of compiling silence.

**Slice 7.2 — Recorded timeline build.** The conform build through the
standard pipeline: approved presenter picture and audio placed on V1/A1–A2 in
master source time, temp narration replaced (locked temp beats kept),
text-anchored events recompiled from recorded word timings within verified
handles — never speed-changed, looped, or frozen — insufficient handles
raised as reconciliation issues, a new timeline always, manifest
verification, master relink verification blocking on mismatch, and stable
IDs in marker custom data. Prior temp-voice and conform timelines preserved.
*Done when:* the producer builds the fixture conform and each managed B-roll
boundary lands on the correct spoken word in Resolve; a deliberately
shortened source raises a handle issue instead of a hidden retime; the
temp-voice timeline still exists.

**Slice 7.3 — Audio preparation path.** The section 8.6 chain behind the
processing profile: channel mapping, optional cleanup/leveling, loudness
normalization, `ProcessedDialogueArtifact` provenance with sync verification,
first-class bypass and A/B against clean source audio, and manual import of
an externally processed file as a versioned artifact. Enhancement failure
retains clean synchronized audio and never invalidates take approval.
*Done when:* the producer A/Bs processed against clean dialogue in one
keystroke, imports one externally enhanced file for one beat, and an
automated check proves processing shifted nothing in time.

**Slice 7.4 — Color input transform and review render.** One reviewed color
input transform per camera applied non-destructively at conform (never baked
into proxy identity), visible unverified-transform state for uncertain
metadata, shot-outlier flags, and the Phase 2 review-render/Drive path
running against the conform with the final-candidate label and an audit
report of every reuse, replacement, shift, warning, and unresolved item.
*Done when:* the producer renders a review MP4 of the conform whose picture
uses the approved transform, and the report labels it a final-candidate
conform with the complete audit trail.

**Slice 7.5 — Script changes after the shoot.** The section 6.15 staleness
rules implemented and test-enforced: hash-stable beats retain approvals;
formatting-only edits keep them; wording changes mark stale without silent
transfer; new beats are needs-recording; splits/merges propose confirmable
mappings; moves report and recompute. Incremental conform rebuilds reuse
verified transcripts, alignments, and processed audio by hash.
*Done when:* the producer edits one beat's wording and one beat's punctuation
after approving takes; only the worded beat goes stale; rebuilding regenerates
only that beat's dependents.

**Phase 7 gate:** the vertical proof from the Part 3 outline passes on real
material: a script section with several beats and anchored visuals, one
15–30 minute master with repeated reads, a flub, and an omitted beat —
approve most beats, mark one needs-pickup, preview the impact, build a new
Resolve timeline where approved recorded takes replace temp narration and
every visual event recompiles to real word timings, verify proxy ranges map
to correct master frames, and confirm the temp-voice timeline and prior
snapshots survive, with a review artifact and full audit report at the end.

### Phase 8 — Subtitles for non-English clips

**Slice 8.1 — Subtitle copy derivation and editing.** Section 6.12:
occurrence-specific `SubtitleCopyTrack` derived from the snapshotted baseline
translation; the English copy as the card's primary readable text with the
source-language badge; inspector access to source transcript and baseline;
segment-level source linkage; `needs_review` lifecycle with reviewer
recording; mixed-language handling at segment level.
*Done when:* the producer edits a subtitled quote's wording, and the source
transcript, baseline translation, and a second occurrence are all provably
unchanged; refinement of the clip clamps segments correctly.

**Slice 8.2 — Brand presets and caption compilation.** Versioned
`SubtitleBrandPreset` per project; compiled semantic caption events with the
frozen preset version; reflow over speech-aligned timing after edits; reading
speed, line length/count, and safe-area warnings; explicit timing edits for
material timing changes.
*Done when:* the producer over-stuffs a segment and gets the reading-speed
warning; an approved segment compiles with the exact frozen preset even after
the project preset later changes.

**Slice 8.3 — Subtitle delivery.** Studio: tested branded timeline
representation, placed and verified. Free: the tested native/title/baked
representation chosen from Slice 0.3 evidence; a manual-completion item alone
is rejected for required non-English dialogue.
*Done when:* the same foreign-language occurrence shows correct branded
English subtitles in a Studio-verified timeline and in an imported Free
package, and the report names the representation used.

**Phase 8 gate:** a real multilingual script compiles with reviewed English
subtitle copy in both modes while research-side evidence stays immutable.

### Phase 9 — Graphics and music library

*You can now place versioned graphics and approved music from a project
library. This is Revision 1's standards system minus the governance: immutable
revisions and pinning stay; workspace scoping, override-rule policy, and
rights evidence wait for their triggers.*

**Slice 9.1 — Template registry.** Project-scoped `TemplateItem` /
`TemplateRevision` with immutable revisions, current pointers, pinning of
placed uses to exact revisions with resolved snapshot hashes, `Update
available` comparison, and per-occurrence explicit migration recorded as a
reversible document revision. `Save as project template` creates a new draft
item.
*Done when:* the producer publishes revision 2 of a template and proves every
existing placement, checkpoint, and build still renders revision 1 until a
chosen occurrence is explicitly migrated.

**Slice 9.2 — Graphic packages and the starter set.** `GraphicTemplatePackage`
contract: Fusion artifact, semantic input schema (types, constraints), timing
policy, layout support, declared Free fallback
(`interchange_native | baked_media | manual_placeholder`), reference renders,
and validation fixtures. Implement the installer/validator and the first real
package (lower third); the remaining starter set (quote, full-screen text,
image-with-caption, two-series chart) proceeds as a parallel design
workstream against this contract.
*Done when:* installing a deliberately broken package (missing font, renamed
control) fails validation with a useful message; the lower third renders its
reference fixture correctly in Studio.

**Slice 9.3 — Graphic placement.** Semantic-input forms on cards; readable
in-script prose ("Erika Vikman — Singer") backed by full identities; compile
to live Fusion insertion in Studio and the declared fallback in Free, each
reported honestly; field validation with template-named slates for invalid
data.
*Done when:* the producer places a lower third and a chart from authored
data, sees both correct in Studio, and sees the Free package contain the
declared fallback with the report saying exactly which.

**Slice 9.4 — Music cues.** `MusicCuePayload` with pinned audio
asset/version, license note and attribution fields, cue in/out, loop, fades,
gain/loudness target, ducking intent, duration policy; placement anchored to a
range, block, section, or explicit region; per-occurrence setting changes that
never edit the cue or another occurrence; tested gain/fade/ducking compile in
Studio and honest baked/manual reporting in Free; missing-bytes blocking at
release.
*Done when:* the producer places the channel's standard cue under a section,
hears correct fades and ducking intent in the Studio build, tweaks one
occurrence's gain without touching the library cue, and a release with a
missing audio file is blocked with a useful message.

**Phase 9 gate:** the starter graphics and one approved cue render correctly
from authored data in Studio, import into Free through declared fallbacks or
labeled placeholders, and a new template revision changes nothing that was not
explicitly migrated.

### Phase 10 — Regeneration Review and safe rebuild

*You can now update a manually refined Studio timeline without losing work.
Until this phase, every update was a new timeline — safe and honest. This
phase earns the harder promise.*

**Slice 10.1 — Sync baseline and observation.** `ResolveSyncBaseline` written
only after verified Studio builds; managed-item identity map; Studio-side
observation of the applied timeline via the API; observed fingerprints;
honest capability limits — properties the installed API cannot inspect
reliably are recorded as unobservable, never guessed. Record the observable
property set in `CAPABILITIES.md`.
*Done when:* after a verified build, the agent can list every managed item
with identity and current observed properties, and cleanly reports what it
cannot see.

**Slice 10.2 — Three-way classification.** The diff engine over last applied
build, current script revision, and current observed timeline: row states
(script/Resolve/both-compatible/conflict/unchanged), property-level deltas,
protected-work detection (user-created items Resolve-owned by default;
finishing work attached to managed items preserved where the mapping is
provable), and dependency-impact calculation for duration changes.
*Done when:* fixture scenarios for each row state classify correctly in
automated tests, including the trap cases: a ripple edit is a conflict, not a
merge; an effect with unprovable attachment is protected, not adopted.

**Slice 10.3 — Regeneration Review UI.** Section 6.16 rendered: highlighted
script rows with accessible labels, filters, section selection, **Select all
safe updates**, expandable property comparisons showing prior generated /
current script / current Resolve / proposed result, explicit conflict
decisions, and the dependency-impact statement before apply.
*Done when:* the producer manually trims a managed clip in Resolve, adds a
grade, edits two script rows, opens the review, and can read exactly what will
happen — including `N Resolve additions preserved` — before touching anything.

**Slice 10.4 — Selective apply.** Producer-gated application: new timeline
version by default, per-row regeneration preserving compatible Resolve work,
deselected rows recorded out of sync against the same baseline, orphaned work
preserved (never deleted) when an anchor disappears, verification of every
selected result before the new baseline is written, partial-failure semantics
(prior timeline stays authoritative; review stays retryable). Bounded
adoption: clean in/out refinements and subtitle-copy edits become reversible
script revisions; nothing else is inferred.
*Done when:* the producer applies one of two changed rows; the protected
grade survives, the unselected row shows out of sync, the prior timeline
still exists, and adopting a manual trim back into the script produces an
ordinary revision they can undo.

**Phase 10 gate:** the Revision 1 acceptance scenario passes end-to-end: a
manually refined Studio timeline plus two script changes yields a review with
correct highlighting, adjustable selection, preserved finishing work, an
explicit conflict decision, and a verified new timeline version — with the
sole edited prior timeline intact.

---

## 12. Working method: a producer directing AI agents

This section is part of the spec because the builder is part of the system.
The product's correctness guarantees are only as good as the process that
builds it, and that process must not depend on the producer reading code.

**Contracts are the management surface.** The schemas in `/contracts` are
frozen between slices. An agent that needs a contract change stops and
proposes it as an explicit contract-change note — what changes, why, what it
breaks — and the change happens in its own small slice with regenerated types
on both sides. This single rule prevents most cross-slice drift.

**The slice ritual.** Each slice runs the same way:

1. The agent reads this spec's slice definition and writes a short plan —
   what it will build, what it will not, which contracts and fixtures it
   touches, and the acceptance script restated in its own words. The producer
   reads the plan (five minutes) and corrects misreadings *before* code
   exists. A plan that expands scope is corrected, not accommodated.
2. The agent works test-first: the automated checks for the done-condition
   exist and fail before implementation begins. Compiler-touching slices add
   golden-file tests (byte-identical manifests from frozen fixtures) — the
   cheapest determinism insurance available.
3. The agent finishes by delivering three artifacts: the passing test run,
   a plain-language walkthrough of what changed and any judgment calls
   (appended to `DECISIONS.md` when they matter), and the acceptance script
   as a numbered checklist.
4. The producer runs the acceptance script personally. Pass → the slice is
   done and its behavior joins the regression suite. Fail → the failure notes
   go back verbatim; the slice stays open. **No slice is closed on an agent's
   self-report.**

**Standing guardrails for every agent session** (checked into the repo as
agent instructions so they apply automatically):

- Do not expand a slice's scope; file discovered work as proposed new slices.
- Do not modify `/contracts`, `/fixtures`, golden files, or previously
  accepted acceptance tests without an explicit contract-change or
  fixture-change note approved by the producer.
- Do not add dependencies without a one-line justification in the plan.
- Anything irreversible in the real world — deleting files, touching the
  research project's data, uploading, changing sharing — happens only inside
  the product's own audited flows, never as an agent side effect.
- When blocked or uncertain between two reasonable interpretations of this
  spec, stop and ask; a wrong guess embedded in a contract costs ten times
  the question.

**The regression ratchet.** Every acceptance script that has ever passed is
re-runnable, and the automated portion runs in CI on every change. The
producer's confidence does not come from reviewing code; it comes from the
fact that everything that ever worked is continuously re-proven, and that the
fixtures include the torture cases (mid-sentence cuts, refined repeated
clips, mixed-language segments, the Finland script) rather than only happy
paths.

**Cadence and stall detection.** One slice should feel like days, not weeks.
Two consecutive slices that blow past that are a signal the slicing is wrong —
stop and re-slice rather than pushing through. The phase ladder exists so
that even a long stall strands the project on a rung where the product is
already useful.

---

## 13. Failure and placeholder policy

The governing rule across every subsystem: **failures are visible, blocking
where policy demands, and never resolved by invention, silent substitution,
or silent deletion.** The table binds each condition to its default behavior
and the phase where it becomes enforceable.

| Condition | Default behavior | Phase |
| --------- | ---------------- | ----- |
| Voice generation fails | Duration-preserving tone/slate or block build per policy; retain text and error | 1 |
| Image or visual unresolved | Request text on a slate with stable row ID (V5) | 1 |
| Concurrent or imported state violates coverage/anchor invariants | Preserve accepted content, show the validation conflict, block compilation until repaired | 1 |
| OTIO cannot represent a requested operation | Declared baked/placeholder/manual fallback, listed in the report; never silently omitted | 1 |
| Resolve Free selected | Finalize verified import package, stop at `ready_to_import`; never attempt external scripting | 1 |
| Studio selected but Free/App Store/unsupported install detected | Preserve the import package, block Studio-only stages, offer Free completion or remediation | 1 |
| Studio output differs from manifest | Fail verification; retain manifest and generated timeline for diagnosis | 1 |
| Imported Free timeline differs from package | Preserve package, accept user-reported discrepancy; never claim automated Free verification | 1 |
| Workstation sleeps/restarts, Resolve closed | Persist job state; resume from last verified stage when agent and app return | 1 |
| Preview requested with unacknowledged local changes | Wait for sync or freeze the acknowledged revision and identify exclusions explicitly | 2 |
| Script marker loses its anchor | Mark `unplaced`, omit from compilation with a visible warning, require reattachment or dismissal | 2 |
| Review render fails | Retain verified timeline and earlier artifacts; retry render without regenerating dependencies | 2 |
| Drive upload fails or auth expires | Keep verified local MP4; expose reauth/retry; never rebuild to retry delivery | 2 |
| Comment/typed anchor ambiguous after concurrent deletion | Mark stale, require explicit reattachment; never bind to nearby content silently | 3 |
| Release references an unapproved checkpoint | Reject submission without creating a build; completed builds remain immutable | 3 |
| Completed clip record, missing locator | Search configured roots, offer verified `Locate`, then re-export or explicit placeholder/block | 4 |
| Located package fails manifest/snapshot/hash verification | Reject as invalid; retain the clip reference; offer another location or re-export | 4 |
| Reachable package lacks required handles/compatibility | Request a new immutable export; never stretch, substitute, or mutate the prior package | 4 |
| Project-local media copy deleted | Rematerialize from canonical package, then relink, then re-export | 4 |
| Source acquisition unavailable | Keep clip reference and transcript; show remediation; never substitute unrelated footage | 4 |
| Refined use falls outside logged range | Reject the range, retain prior valid use, offer reset or explicit research update | 4 |
| Local file undecodable | Reject import without modifying the source; retain card, intent, and diagnostics | 5 |
| Local clone unsupported | Verified full copy; record `completedMode = copy` | 5 |
| Local move verifies copy but cannot remove original | Keep both files, complete as verified copy with cleanup warning and retry | 5 |
| Referenced local file moved/changed/deleted | Preserve card and expected hash; offer verified relink, copy-in, replacement, or placeholder | 5 |
| Webpage capture blocked, incomplete, or materially different | Keep URL/card and diagnostics; require review, retry with revised profile, or accept a supplied screenshot | 5 |
| Image aspect mismatch | Contain plus project background; never crop or stretch without explicit override | 5 |
| Transition lacks duration/handles | Block with corrective choices; allow explicit hard cut without moving narration anchors | 5 |
| Subtitle copy missing, unreviewed, or over constraints | Keep source and baseline visible; block or explicitly slate the required event per policy | 8 |
| Template package/dependency missing or invalid | Reject release or use only the declared tested fallback; never substitute latest/unrelated | 9 |
| Music bytes missing or unverifiable | Block release; preview allowed per policy with a prominent warning | 9 |
| Two Studio jobs target the same timeline | Serialize through expiring target claim; never apply concurrently or infer success after claim loss | 2+ |
| Timeline/baseline identity unverifiable | Disable in-place reconciliation; preserve the timeline; offer a fresh generated timeline plus report | 10 |
| Script and Resolve changed the same managed property | Blocking row/property conflict; explicit use-script / keep-for-now / adopt-supported / manual decision | 10 |
| Resolve-owned work loses its anchor during regeneration | Preserve in orphaned/disabled review area or on the prior timeline; never delete silently | 10 |
| Shoot master missing or moved | Block conform/final render; proxy take review continues when a verified proxy exists; offer hash relink | 6 |
| Proxy generation fails | Fall back to master review only when the file is safe and practical to stream locally | 6 |
| Unsupported or variable-frame-rate shoot media | Explicit normalization/transcode decision; timing is never guessed | 6 |
| Script alignment ambiguous | Present all plausible ranges and require review | 6 |
| No matching take for a beat | `Needs pickup` or explicit temp-voice fallback; never an invented match | 6 |
| Audio enhancement fails | Retain clean synchronized source audio; allow bypass/retry; take approval remains valid | 7 |
| Color metadata uncertain | Visible unverified-transform state; never silently apply a camera LUT | 7 |
| Insufficient B-roll handles at conform | Reconciliation issue; never a hidden speed change or repeated frame | 7 |
| Proxy-to-master relink mismatch at conform | Block conform/final render on the wrong or missing master; never degrade silently | 7 |

---

## 14. Deferred Register

Everything below existed in Revision 1's MVP or near-MVP scope. Nothing here
is judged wrong; each entry waits for a named trigger. Reviewing this register
is part of every phase gate.

| Deferred item | What ships instead | Revive when… |
| ------------- | ------------------ | ------------- |
| Workspace Owner/Administrator governance tier and workspace-scoped standards publishing | Project-scoped template library; the workspace has an owner | More than one authoring team shares the workspace, or templates need controlled publication across projects |
| Reviewer role; checkpoint review workflow (`in_review`, `changes_requested`, `revoke_approval`) with approval evidence chains | Named checkpoints plus a Producer-set **approved** label; append-only events kept in the schema | An external stakeholder (client, network, sponsor) must sign off, or an approval is disputed after the fact |
| Field-level override rules (`locked`, `project_overridable`, …) with policy enforcement | Occurrence settings on placed uses; conventions instead of enforcement | A template's fields are being changed in ways that break brand consistency in practice |
| `MusicRightsSnapshot` with license evidence, territories, expiry, and rights-based release blocking | License note and attribution fields on the cue; missing-bytes blocking only | Monetization/clearance review becomes real, a license actually carries an expiry, or a third party requires evidence |
| Scheduled webpage monitoring (daily/weekly, material-change detection) | Capture-on-add plus manual recapture with immutable revisions | A build is actually burned by a stale capture more than once |
| Heuristic legacy Google Docs importer with inference-review queue | Agent-assisted, producer-reviewed one-time conversion per legacy doc (Slice 1.8 pattern) | The back catalog grows beyond supervised conversion, or outside writers must self-import |
| Revoked-editor private recovery export of unsynced local text | Prompt session termination on role removal | The team grows beyond people who can coordinate a role change in chat |
| FCPXML as a perpetually maintained second interchange format | OTIO primary; FCPXML only if Slice 0.3 evidence demands it | Slice 0.3 finds OTIO gaps on tested versions, or a Resolve update breaks OTIO import |
| Generated-image and stock-search adapters with candidate review | Placeholders and writer-supplied assets | The core loop is stable and placeholder resolution is the measured bottleneck (Revision 1's own criterion) |
| Authenticated/paywalled webpage capture | User-supplied screenshots | Recurring real need — and only via an explicitly authorized attached-browser flow |
| Multi-range clip refinement (removing words from the middle) | Inward-only in/out refinement; multiple occurrences for jump cuts | Writers demonstrably fight the single-range constraint |
| Marker duration, assignees, status, task management | Point markers with notes | Resolve-side task handoff becomes a real workflow |
| Per-build delivery-profile override | Project-level delivery profile setting | The team actually alternates editions per build |
| Offline editing beyond Yjs's natural behavior | Yjs reconnect merge | Real usage shows long-offline authoring sessions |
| Suggestion/track-changes, branches/merges, mobile authoring, Docs round-trip parity | — (unchanged from Revision 1: explicitly out of scope) | — |
| Fully autonomous research, fact-checking, rights clearance, editorial judgment | — (unchanged: out of scope) | — |
| UI automation or undocumented project-file editing to extend Resolve Free | — (permanently out of scope) | Never |
| Dual-system audio recording and sync (Part 3) | Single camera with camera/attached mic | A shoot actually uses a separate audio recorder |
| Multi-camera sessions and automatic switching (Part 3) | One camera per session; the source model does not preclude more | A second camera becomes routine on shoots |
| Intra-beat take splicing (Part 3) | One active take per beat plus recorded alternates; `spliceRanges[]` reserved on `TakeAssignment` | The producer regularly needs phrases combined from different reads inside one beat |
| Automated video quality analysis — focus, exposure, eye line (Part 3) | Human judgment in the takes drawer; audio-side warnings only | Reviewing long shoots without them is measured, recurring pain |
| Autonomous keeper selection or performance-direction judgment (Part 3) | Ranked, explainable, component-based suggestions; approval always human | Never fully; an experimental ranking learned from the producer's own approvals may be trialed once enough approval history exists |
| Web automation of Adobe Podcast or any enhancement provider (Part 3) | Manual import of a processed result as a versioned artifact | An official, authorized API integration boundary exists |
| Automated creative grade, beauty work, reframing, or generative repair (Part 3) | One reviewed color input transform per camera; outlier flags | Later assisted capabilities, always with human review |
| Remote upload of master footage by default (Part 3) | Local masters remain authoritative | An explicit per-project policy names provider, content, retention, and cost |
| Delivery-master claim from a conform (Part 3) | The `final-candidate conform` label | Human finishing and QC gates (picture, audio, color, captions, rights) exist around the product |
| Per-camera and per-source processing-profile scoping (Part 3) | Project and per-shoot profile scopes | Heterogeneous sources in one session demand finer overrides |

Also unchanged from Revision 1's Not-MVP list and still binding: no complete
browser NLE, color suite, audio mixer, compositing environment, or final
delivery system; no automatic modification of a manually refined Resolve
timeline without the Phase 10 review; no arbitrary automatic merging of every
possible Resolve edit; automated Resolve-side render/upload remains
Studio-only.

---

## 15. Technical risks

Ordered by expected impact on this plan; each mitigation names the phase or
slice that retires the risk.

1. **Resolve interchange and scripting behave worse than documented.** The
   product bets on two external boundaries. Mitigation: Phase 0 exists solely
   to convert this risk into recorded evidence before anything depends on it;
   one canonical manifest; a tested capability matrix; no UI automation ever;
   Free's verified package as the common success base even when Studio
   automation is unavailable.
2. **The AI-agent development process itself drifts.** Cross-slice
   inconsistency, silent contract changes, and self-reported completion are
   this project's equivalent of a weak engineering culture. Mitigation:
   section 12 in full — frozen contracts, producer-run acceptance scripts,
   the regression ratchet, checked-in guardrails, stall detection.
3. **Concurrent rich-text edits converge structurally while violating
   semantic invariants** (coverage, anchors). Mitigation: operation-based
   convergence with stable IDs and relative positions; post-merge typed
   validation; visible repair states; no conflict policy that deletes
   accepted prose (Slices 1.1, 3.2).
4. **Text edits invalidate visual anchors; word-level timing is unavailable
   or changes after voice regeneration.** Mitigation: stable token/relative
   anchors with quoted-text checks; honest precision labels; the secondary
   timing mode; never claiming frame accuracy from paragraph position
   (Slices 1.3, 2.4, 5.5).
5. **Generated voice duration shifts the whole edit on rebuild.** Mitigation:
   block-level assets, locked takes, timing-impact preview on replacement,
   immutable snapshots (Slices 1.2, 1.3).
6. **Manual edits and generated rebuilds diverge.** Mitigation: until Phase
   8 the update path is always a new timeline — divergence is contained by
   policy, not merged by guesswork; Phase 10 then adds baselines, three-way
   review, protected work, and new-timeline defaults.
7. **A completed research export was moved, deleted, or corrupted; copying
   everything wastes disk while referencing is fragile.** Mitigation:
   identity/locator separation, build-time byte verification, verified
   relink, idempotent re-export, independent reuse/materialization policies
   with storage estimates (Slices 4.2, 4.3).
8. **Users confuse version layers and approve or build the wrong state.**
   Mitigation: distinct names and status language for the five layers, exact
   source labels on every build, no overloaded generic "version" control
   (Slices 3.4, 3.5).
9. **A local-file move loses the only source bytes.** Mitigation: explicit
   move only, copy-verify-promote-delete, removal failure treated as a
   completed copy plus retryable warning (Slice 5.1).
10. **Webpages are mutable and capture is nondeterministic; remote images
    change or misreport content types.** Mitigation: previewed capture
    profiles, immutable provenance-stamped artifacts, verification on
    acquisition, reviewable new revisions rather than silent refresh
    (Slices 5.2, 5.3).
11. **Edited subtitle copy becomes unreadable in the source speech time or
    detaches semantically.** Mitigation: immutable evidence, segment linkage,
    review states, reading/layout validation, explicit timing overrides
    (Phase 8).
12. **Provider cost and privacy surprises.** Mitigation: narrow adapters,
    per-project policy, caching, explicit disclosure of what leaves the
    machine, and worksheet decisions settled before Phase 1 spends money.
13. **Planning and parked material leak into production.** Mitigation:
    explicit Ideas/Draft/Extras roots; only `activeDraft` reaches validation,
    voice, prompter, and build contracts (enforced from Slice 1.1).
14. **Review delivery exposes unfinished work.** Mitigation:
    private-by-default upload, explicit sharing, immutable naming, remote
    verification, audit records (Slice 2.8).
15. **Transcription and alignment underperform on real shoots** — jokes,
    proper nouns, accents, ad-libs, and half-finished reads are exactly what
    this channel records. Mitigation: the Slice 6.1 corpus spike chooses
    providers on measured fixture results; evidence stays component-based and
    honest about gaps; human approval is authoritative; `needs pickup` and
    temp-voice fallback keep a bad alignment from blocking a build
    (Slices 6.1, 6.5).
16. **Proxy time and master time drift apart**, silently corrupting every
    reviewed in/out. Mitigation: verified duration/time-base correspondence at
    proxy creation, frame-exact mapping tests, conform in/out stored only in
    master source time, and relink verification that blocks on the wrong
    master (Slices 6.4, 7.2).
17. **The conform reflow moves the wrong things** when recorded durations
    differ from temp narration. Mitigation: per-event duration policies with
    `follow_text_anchors` as the default, the mandatory impact preview,
    handle-bounded trims with reconciliation issues instead of hidden
    retimes, and golden conform tests on the fixture shoot
    (Slices 7.1, 7.2).

---

## 16. Decisions worksheet

Decisions the producer owns, grouped by when they block. Recommended defaults
are pre-filled; confirming a default is a one-word decision. Every decision
lands in `DECISIONS.md`.

**Before Phase 0**

| Decision | Recommended default |
| -------- | ------------------- |
| Primary OS for the local agent | macOS if that matches the editing workstation; one OS only until Phase 3 |
| Resolve versions to test in the spike | The versions actually installed on the team's machines, recorded exactly |
| Timeline frame rate / resolution / audio sample rate | Match the channel's current delivery spec exactly (record once; applied everywhere) |
| Track naming convention | The section 9.2 map as printed |

**Before Phase 1**

| Decision | Recommended default |
| -------- | ------------------- |
| Voice provider and voice profile | Chosen in Slice 1.2 by comparing current cloud options on timing marks, pronunciation control, cost per rebuilt script, and data handling; local/offline adapter later |
| May script text leave the local machine for synthesis? | Yes for temp narration (the text is destined for publication), recorded as explicit policy |
| Voice cost policy | Per-build cost estimate shown; automatic generation under a per-build ceiling, confirmation above it |
| Presenter/A-roll in the first rough cut, or VO-only spine? | VO-only spine with V1 presenter placeholders; the recorded-performance conform is suite phase 3 |
| Build policy for unresolved assets | Placeholder slates for preview; block for release; per-project selection later |

**Before Phase 2**

| Decision | Recommended default |
| -------- | ------------------- |
| Review-render preset and filename convention | H.264/AAC MP4 at project spec; `{project}-{build-id}-{checkpoint-or-rev}`; burned-in draft watermark and timecode on previews |
| Default Drive folder, retention, sharing authority | Producer-owned folder; keep all versions; sharing changes are Producer-only |
| Completion notification channels | In-app first; email adapter when Phase 3 brings real collaborators |
| Sleep prevention during render/upload | Agent prevents sleep during active Studio stages, with a visible indicator |
| Marker color/name convention | One reserved color for script-owned markers; first note line as name |

**Before Phase 6**

| Decision | Recommended default |
| -------- | ------------------- |
| Beat granularity default | One beat per sentence, merge/split adjustable before the prompter freezes |
| Pre/post-roll handles per take | Start at ~1 second each side; tune on the first real shoot |
| Shoot formats to support first | Exactly what the current camera records — codec, frame rate, resolution, log profile — recorded in `DECISIONS.md` during Slice 6.1 |
| Master media location | Local to the editing workstation; shared storage is a later decision |
| May production audio go to a cloud transcription provider? | Decide per the section 6.14 policy rule; compare at least one local Whisper-class route in Slice 6.1 before defaulting to cloud |
| Is Resolve Studio (current version) on every workstation that will run conform automation? | Verify and record during Slice 6.1 |

**Before Phase 7**

| Decision | Recommended default |
| -------- | ------------------- |
| Duration-policy defaults per visual type | `follow_text_anchors` for clips and captures; `stretchable_still_or_graphic` for stills and template holds; `clip_led` where authoring already says so |
| Audio enhancement reference and acceptable processing level | The team's current manual enhancement result is the A/B reference; less processing wins ties |
| Review-render loudness target for conforms | Match the channel's normal delivery loudness for review; final mix remains editorial work in Resolve |
| Conform review watermark | Keep the draft watermark until the finishing gate exists; label stays `final-candidate conform` |

**Before their phase**

| Decision | Phase | Recommended default |
| -------- | ----- | ------------------- |
| Presence/cursor performance targets and history-retention limits | 3 | Measure on representative scripts during Slice 3.2, then set; retention must preserve checkpoint replay and attribution |
| Webpage capture viewport, settle policy, consent-banner treatment | 5 | 1920×1080 viewport, fixed settle timeout, banners handled by profile where safe, else visible in preview for manual region choice |
| Contain-background treatment for mismatched stills | 5 | Project background preset; start with black, revisit with brand |
| Initial transition library and default duration | 5 | Cut, cross-dissolve, dip-to-color; 12-frame default; picture-only |
| Default subtitle brand preset and reading/layout limits | 8 | Channel's existing subtitle look codified; ~17 CPS warning, 2 lines, ~42 chars/line, broadcast-safe margins — tuned in Slice 8.2 |
| The five starter Fusion templates and their visual approver | 9 | Lower third, quote, full-screen text, image-with-caption, two-series chart; the producer approves reference renders |
| Default music-rights posture for previews | 9 | Preview allowed with prominent warning; release blocked on missing bytes (full rights machinery deferred per section 14) |
| Observable-property set and protected-track convention | 10 | Recorded from Slice 10.1 evidence; protected tracks are all tracks above the managed map |

---

## 17. Traceability to Revision 1

Sections 1–4 here revise Revision 1 sections 1–4. Section 5 replaces the
monolithic MVP list (R1 §5.1) with the phase ladder. Section 6 carries
forward R1 §6, with roles simplified (§6.7 here versus R1 §6.11) and the
approval workflow reduced to the approved label. Section 7 carries R1 §7 with
the standards entities simplified and every simplification marked. Section 8
merges R1 §§8–11. Section 9 carries R1 §12. Section 10 replaces R1 §§13–14
with a committed stack. Section 11 replaces R1 §§16, 17, and 20 (milestones,
MVP acceptance path, first implementation slice): every R1 acceptance
behavior reappears as a slice done-condition or phase gate. Section 13
carries R1 §15. Section 14 absorbs R1 §5.2 plus this revision's deferrals.
Section 15 carries R1 §21, reordered by impact. Section 16 carries R1 §19
with recommended defaults. R1 §18's open-questions table is fully resolved:
each recommendation is now either binding text in this document or a
worksheet row above.

**Part 3 traceability (Revision 2.1).** The Recorded Performance Ingest and
Conform outline (20 August 2026) maps as follows: its §§1–2 (position,
promise) are absorbed into sections 1 and 5 here; §3 (foundational decisions)
into sections 6.14–6.15 and the section 7 model notes; §4 (workflow) across
the Phase 6–7 slices; §§5–7 (ingest/proxy, alignment, take review) into
section 6.14 and Slices 6.2–6.7; §8 (conform rules, duration policies,
output safety) into section 6.15 and 9.7; §§9–10 (audio, color) into section
8.6 and Slices 7.3–7.4; §11 (records) into section 7; §12 (script changes
after a shoot) into section 6.15 and Slice 7.5; §13 (job states, failures)
into section 9.7 and the section 13 table; §14 (MVP/deferred) into the Phase
6–7 scope and section 14; §§15–16 (milestones P3-0…P3-5, vertical proof)
into the Phase 6–7 slices and gates — P3-5's adjustable-profile ambitions
are partially deferred per section 14; §17 (critical tests) into slice
done-conditions and automated checks; §18's discovery questions are settled
in section 1.1 (shoot shape, take granularity, first target) or appear as
Phase 6–7 worksheet rows; §19 (platform notes) into Appendix A.

## Appendix A. References

Primary product and implementation sources grounding Resolve automation,
Fusion template design, the example-script analysis, and integration with the
existing research clip workflow.

- Example two-column script: "OEV25 Finland" (Google Docs)
- DaVinci Resolve 20 New Features Guide — AI IntelliScript (Blackmagic Design)
- Fusion 20 Reference Manual — macros and Fusion templates (Blackmagic Design)
- DaVinci Resolve 20 Fusion Visual Effects Guide — creating title templates
- DaVinci Resolve 20 Studio and iPad Features — edition and external-scripting differences
- DaVinci Resolve OpenTimelineIO import/export guidance (18.5 New Features Guide)
- Installed DaVinci Resolve scripting README (local workstation; last updated 28 October 2024)
- Research Video Transcript & Clip Extraction Tool: PROJECT_GUIDE.md
- Recorded-Performance-Conform Product Spec (20 August 2026 discovery
  outline — absorbed into this plan as Phases 6–7 by Revision 2.1)
- DaVinci Resolve 20 New Features Guide — IntelliScript dialogue/script
  matching, preferred/alternative take tracks, and its dialogue-only
  limitation; Voice Isolation, Dialog Leveler, Dialogue Matcher, EQ Matcher,
  AI Audio Assistant (Blackmagic Design)
- Adobe Podcast Enhance Speech — documented upload/process/download browser
  workflow with plan/file limits; treated as optional and replaceable, never
  architectural infrastructure

