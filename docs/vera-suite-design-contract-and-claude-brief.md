# VERA suite design contract and Claude artifact brief

- Issue: [#13 — Decide VERA suite design-system contract and Claude artifact structure](https://github.com/mbelinkie/vera-script-to-timeline/issues/13)
- Status: proposed for producer acceptance
- Decision authority: Producer
- Prepared: 2026-08-31
- Updated: 2026-09-01 with the Producer-accepted issue #24 bounded handoff
- Scope: Claude Design structure and shared design language only

## Decision in one sentence

Use **one VERA Suite Claude project with separate product artifacts**, keep the
Desktop/Web presentations of a product together inside that product's artifact,
and add one small **contract-only VERA Suite Design Contract artifact** as the
canonical cross-product reference; never put both products' application pages
into one suite artifact.

This is a recommendation until the Producer accepts it. Acceptance of this
document does not authorize a Research redesign, a Script to Timeline
prototype, token wiring, shared production UI code, or any deployment,
permission, data, or runtime change.

## 1. Authority and decision boundaries

The following hierarchy resolves conflicts:

1. Each product's approved product specification or behavior contract governs
   behavior, data meaning, authorization, and runtime capability.
2. The Producer-accepted issue #24 decisions D24-01 through D24-19 govern the
   sample-grounded content-language presentation required of the later Script
   artifact. They do not amend `ScriptDocument v1` or authorize implementation.
3. The accepted VERA Suite Design Contract governs shared visual and
   interaction grammar only.
4. The producer-approved output of issue #21 governs shared token names and
   values. This document does not choose, rename, collapse, or wire tokens.
5. An approved product Claude artifact governs that product's visual
   composition and state presentation only when it agrees with items 1–4.

The Research Video Clips Claude prototype is an input and visual precedent, not
permission to copy Research screens into Script to Timeline. The Script to
Timeline product specification remains authoritative for its purpose-built
authoring surface.

The complete D24-01 through D24-19 record remains authoritative in
`docs/investigations/issue-24-representative-script-coverage.md`. This document
incorporates only its exact §8 handoff. It does not reinterpret, omit, merge, or
silently broaden those decisions, and Claude receives the fictional sanitized
brief rather than the representative production script or URL.

## 2. Investigation of the current Research artifact

### 2.1 Sources inspected

- The live [`VERA Redesign` Claude Design artifact](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=VERA+Redesign.dc.html).
- The approved Research `BEHAVIOR-CONTRACT.md`.
- The approved `WEB-EDITION-DESIGN-BRIEF.md`.
- The live-audit `APPROVAL-CHECKLIST.md` dated 2026-08-31.
- `UI-CONTEXT.md`, the final-audit prompts, and the Research design bundle's
  component and token handoff requirements.
- The Script to Timeline Revision 2 product specification and historical
  implementation record.

### 2.2 Material complexity observed in the live artifact

The current Research artifact is already a design application and regression
harness, not a small set of static mockups.

| Dimension | Current observed breadth |
| --- | --- |
| Primary destinations | Sources, Workspace, Clips |
| Major flows | Application, Installation setup, Owner project setup, Member project entry, Account Settings, Platform Administration |
| Advertised scenarios | 26 interactive scenarios |
| Roles | Owner, Administrator, Researcher |
| Required viewports | `1280 × 800` full and `1024 × 768` compact |
| Service matrices | Online translation and Online transcription, each with Not requested, Pending, Approved, Denied, Revoked, and Withdrawn |
| Handoff surfaces | Component States and Visual Tokens |
| Current Claude pages | Current redesign, pre-wiring baseline, token audit, and prior approval-pass snapshot |
| Approval regression set | 33 corrected `CD-*` items plus 18 `VB-*` baseline items |

The 26 advertised scenarios are:

1. Application
2. Installation setup
3. Owner project setup
4. Member project entry
5. Account Settings
6. Platform Administration
7. Language decision
8. Capability blockers
9. Opening a source that is not ready
10. Duplicate — already in Sources
11. Duplicate — hidden
12. Show hidden
13. Keyword filter active
14. Manual range on a ready source
15. Editing a clip
16. Companion player
17. New activity
18. Clips selected
19. Export dialog
20. Export progress
21. Project switcher
22. Archive confirmation
23. Archived projects
24. Link into an archived project
25. Component States
26. Visual Tokens

The live artifact visibly changes its composition at `1024 × 768`: project
and account labels compact, the keyword strip reduces, Date Added folds into
source metadata, the named compact sort appears, and readiness labels shorten.
This is a real responsive presentation, not a scaled screenshot.

### 2.3 Current approval state and open follow-on work

The Research approval checklist records all `CD-001` through `CD-033`, all
`VB-001` through `VB-018`, and the final visual-model gate as passed on
2026-08-31. No known product-behavior approval blocker remains in that recorded
Desktop visual baseline.

Two later boundaries must remain explicit:

- The approved Research Web brief has not yet been represented as a complete
  Desktop/Web runtime switch and Web scenario set in the observed live
  artifact. It is approved design input, not a finished Web prototype.
- The live Claude project currently contains a token audit and an interrupted
  pixel-preserving token-wiring pass. Issue #21 owns token reconciliation and
  producer decisions. Issue #13 neither waits for nor overrides that work; it
  merely requires its accepted output before later high-fidelity Script to
  Timeline visuals may freeze token values.

### 2.4 Regression risks

| Risk | Why one suite artifact makes it worse | Required control |
| --- | --- | --- |
| Edit reliability | A change to one product shares one large executable artifact with every other screen, scenario, role, and runtime variant. A failed Claude edit or partial rewrite has a larger blast radius. | Separate product artifacts and a contract-only shared artifact. |
| Preview performance | Research already renders dense tables, dialogs, setup flows, state matrices, role variants, and two responsive widths. Adding the Script editor, anchors, build states, and Resolve flows increases parse/render load unrelated to the active review. | Load and present one product artifact at a time. |
| Regression testing | Research currently requires 26 scenarios at two widths, role checks, service matrices, dialogs, and handoff sheets. A combined artifact would multiply this by Script scenarios and cross-product states on every change. | Product-local regression matrices plus a small shared-contract conformance pass. |
| Authority confusion | Similar-looking project switchers or readiness badges could conceal that Research and authoring projects have separate membership and data ownership. | Shared grammar with product-specific labels, capabilities, and authorization tests. |
| False uniformity | A transcript workspace and a narration/visual-anchor editor are both dense work surfaces but have different semantics and failure modes. | Reuse primitives, never page implementations. |
| Token drift | Copying literal values into a second product before issue #21 is accepted would freeze conflicting token sources. | Reference the accepted token ledger by version; do not re-inventory or re-decide tokens here. |
| Baseline pollution | Keeping current, audit, pre-wiring, and prior versions beside both products makes the page menu a historical archive instead of a focused design surface. | Keep baselines as named snapshots/exports or product-local reference pages, not as a suite-wide application artifact. |

## 3. Artifact-structure decision

### 3.1 Options considered

| Option | Editing reliability | Preview performance | Regression testing | Shared-language drift | Decision |
| --- | --- | --- | --- | --- | --- |
| One suite artifact containing both products and all runtime variants | Lowest: broad edit blast radius and large executable file | Lowest as scenarios accumulate | Every product change risks the full suite matrix | Low in theory, but only if the artifact remains operable | Reject |
| Separate Claude projects and separate product artifacts | High product isolation | High | Product-local | Highest risk of duplicated tokens and shell decisions | Reject |
| One Claude project, separate product artifacts, plus one contract-only shared artifact | High product isolation with nearby shared reference | High; only the active product runs | Product-local matrix plus bounded suite-contract checks | Low when primitive ownership and versioning are enforced | **Recommend** |

### 3.2 Canonical Claude project structure

```text
VERA Suite                                  one Claude project
├── VERA Suite Design Contract              contract-only; no product pages
├── Research Video Clips                    Desktop + Web presentations
└── Script to Timeline                      Web + desktop-connected presentations
```

The suite contract artifact contains primitive definitions, behavior notes,
source links, ownership, version history, and conformance examples. It must not
grow into a third application, a component showcase duplicating every product
state, or a hidden store of both products' pages.

Each product artifact may contain its own focused internal surfaces:

- application scenarios;
- runtime/capability variants;
- product component states;
- accessibility and interaction handoff;
- product regression index.

Historical baselines should be retained as immutable named snapshots or
clearly noncanonical product-local references. Claude should not require every
reviewer to choose among several nearly identical live pages before reaching
the current product artifact.

### 3.3 Why Desktop and Web stay together within a product

Desktop and Web are capability presentations of one product, not separate
design languages. Keeping them together makes runtime differences reviewable
against the same component/state definitions, terminology, project data, and
responsive rules. It also makes absence tests possible: a control unavailable
to Web or to a role must be absent from that variant's DOM, not left as a
decorative disabled control copied from Desktop.

This rule does **not** require the two products to have symmetrical runtime
implementations:

| Product | Treatment in its artifact |
| --- | --- |
| Research Video Clips | Keep the installed Electron Desktop edition and limited browser Web edition in the same artifact, controlled by explicit runtime/server capabilities as required by the approved Web brief. |
| Script to Timeline | The current specification defines a hosted Web authoring client plus a trusted local agent on the producer workstation. Model the normal Web presentation and the local-agent/Resolve-connected desktop capability states together. Do not invent a separately packaged Desktop authoring application unless a later product decision authorizes one. |

For Script to Timeline, labels such as **Local agent connected**, **Resolve
Free**, **Resolve Studio**, **Local media unavailable**, or **Build workstation
offline** describe capabilities. They are not evidence that browser identity or
user-agent sniffing grants access.

## 4. Shared design-language contract

### 4.1 Contract rule

Shared means a stable semantic and interaction family with the same user-facing
meaning across products. It does not mean shared data, shared authorization,
identical page layout, or a shared production component package.

Every shared primitive receives:

- a stable primitive ID and human-readable name;
- its semantic purpose and prohibited uses;
- visual/token references;
- required states and interaction behavior;
- keyboard and accessibility behavior;
- responsive behavior at the suite baselines;
- source-of-truth owner and contract version;
- product exceptions, if any, stated explicitly rather than inferred.

### 4.2 Source of truth by primitive family

| Primitive family | Canonical source | Product artifact responsibility |
| --- | --- | --- |
| Color, typography, spacing, radius, shadow, focus, control-size, dialog-width, and responsive token names/values | Producer-approved issue #21 token decision and its accepted wiring handoff | Reference the accepted token version; do not locally rename or consolidate values. |
| VERA identity, product-name lockup, shell spacing, account entry, product switcher, and project-switcher grammar | VERA Suite Design Contract | Apply the grammar while using the product's own destinations and project authority. |
| Product navigation and information architecture | The product's approved behavior contract/specification | Render only that product's destinations; never make shared shell grammar decide IA. |
| Project switching | Shared control behavior in the suite contract; product membership rules in each product authority | Populate only server-authorized product projects and update the entire product context. |
| Comments, mentions, presence, unread/new indicators, and thread controls | Shared interaction/component grammar; product behavior contract for anchors, receipts, and permissions | Research keeps clip-centric flat threads; Script keeps document/block/range anchors with stale reattachment and resolve/reopen. |
| Topics | Shared chip, picker, filter, overflow, and accessible labeling grammar | Research Topics remain canonical clip tags. Script Ideas, Extras, headings, and research-clip Topic filters retain distinct meanings and must not be merged. |
| Search | Shared field, query, clearing, keyboard, result-state, highlight, and empty/error grammar | Each product owns searchable sources, indexes, permissions, result types, and navigation. |
| Readiness and remediation | Shared severity, status-badge, progress, blocking, retry, contextual-action, and disclosure grammar | Research owns transcript/language/export readiness; Script owns sync, narration, media, validation, build, Resolve, and delivery readiness. |
| Dialogs, popovers, menus, toasts, banners, and confirmations | VERA Suite Design Contract | Supply product copy and authorization-valid actions; destructive or durable operations retain their own confirmation rules. |
| Tables, lists, cards, inspectors, tabs, chips, badges, buttons, fields, and empty/loading/error states | VERA Suite Design Contract for primitive anatomy and accessibility | Product artifacts choose composition and density appropriate to their work surface. |
| Accessibility | Suite contract plus each product's behavior requirements | Prove names, roles, focus, keyboard operation, announcements, contrast, non-color cues, and absent unauthorized controls in the live product scenario. |
| Responsive baselines | Suite contract sets `1280 × 800` and `1024 × 768`; each product artifact owns its reflow | Provide real compact composition, not scale-to-fit. Mobile/tablet below approximately 1024 CSS px remains out of scope unless separately approved. |
| Runtime capability disclosure | Product behavior contract, expressed through shared readiness/action grammar | Derive from typed runtime and server-authorized capabilities, never browser identity or renderer-only role inference. |

### 4.3 Required common component and state families

The suite contract must cover at least:

- global identity, product switcher, product name, project switcher, account
  entry, primary navigation, and contextual secondary destinations;
- buttons, icon buttons, links, fields, textareas, selects, comboboxes,
  checkboxes, radio groups, tabs, segmented controls, menus, and tooltips;
- dialogs and confirmations, including accessible name, modal semantics,
  initial focus, forward/reverse focus containment, Escape policy, and focus
  restoration;
- tables, lists, cards, inspectors, metadata rows, pagination/virtualization
  affordances, bulk/contextual actions, and compact-width sort controls;
- status badges, progress, readiness, remediation, retry, empty, loading,
  unavailable, permission denied, stale/conflict, offline/disconnected,
  retryable failure, terminal failure, and success;
- comments, replies, mentions, resolve/reopen, stale anchors, presence, user
  identity, new/unread receipts, and actor attribution;
- Topic chips and pickers, search, filters, result counts, no-results, and
  highlight treatments;
- banners, inline notices, toasts, help disclosures, and contextual setup;
- focus appearance, reduced motion, zoom/reflow, screen-reader names, keyboard
  order, and non-color status cues.

### 4.4 Product-specific patterns that must remain purpose-built

#### Research Video Clips

- Sources, transcript-ready Workspace, and Clips information architecture.
- YouTube player and transcript navigation, word/cue timing, language views,
  logged-range overlap, and source-time evidence.
- Canonical Original and English clip language roles and optional preferred
  viewer context.
- Project keywords versus clip Topics.
- Desktop local transcription/translation/export, companion player, artifact
  recovery, and the limited Web feature boundary.
- Research Owner/Administrator/Researcher roles and project lifecycle.

#### Script to Timeline

- Draft, Ideas, and Extras as one collaborative document transaction boundary.
- The readable two-column narration/visual document without spreadsheet chrome.
- In-paragraph OC/VO spans, exact token-range anchors, visual coverage, cards,
  inspectors, and timing honesty.
- Preview versus Release, synchronized revision and checkpoint identity, build
  snapshots, compiler validation, build reports, Resolve Free packages, Resolve
  Studio automation, and delivery outcomes.
- Producer/Editor/Viewer roles, authoring checkpoints, approved-label release
  gate, and document/range/card comment anchors.
- Script-owned clip usage versus Research-owned clip evidence and artifacts.

Do not create a generic “workspace,” “content row,” “readiness,” or “project”
page implementation and theme it differently. The shared layer supplies
primitives and grammar; each central work surface remains product-designed.

## 5. Reciprocal browser suite switcher and authorization

### 5.1 Interaction

- Both browser products show a VERA product switcher containing **Research
  Video Clips** and **Script to Timeline**.
- Selecting the other product opens it in a **new browser tab**. The source tab
  and its current in-memory session remain intact.
- The control works by pointer and keyboard, exposes its current product and
  destination accessibly, and never looks like the current product's project
  switcher.
- This is browser-suite navigation. It does not merge or cross-launch the
  products' separately installed desktop runtimes.

### 5.2 Safe navigation context

The navigation may carry only the minimum stable context needed to help the
destination choose a safe starting point:

- source product identifier;
- opaque source-project identifier;
- a bounded navigation intent such as `open linked projects`.

The exact production envelope remains a later contract decision. The URL or
handoff must never contain transcript text, script text, comments, clip
content, search terms, credentials, access or refresh tokens, presigned URLs,
object keys, local paths, artifact locators, media package identifiers, or
permission claims.

### 5.3 Destination validation

The destination product must:

1. establish the user's destination-product session through the shared suite
   identity without accepting source-product credentials in the URL;
2. treat the incoming project identifier as an untrusted hint, never a grant;
3. recheck current membership in every destination authoring or research
   project it may show;
4. recheck current authorization to a linked Research project before reading a
   clip, transcript, or artifact descriptor;
5. show a chooser only among projects the current account may know exist;
6. fall back to the normal home or a nonrevealing access explanation when the
   context is stale, archived, removed, unauthorized, or unlinked;
7. never create or link a project automatically.

For Research → Script navigation, one authorized linked authoring project may
be prioritized, several produce an authorized chooser, and none lead to the
normal Script home with the Research context available only for a later
authorized link flow.

For Script → Research navigation, a linked Research project may be prioritized
only after current Research membership is rechecked. Otherwise open the normal
Research home or a safe access state without revealing private project details.

### 5.4 Boundaries that remain separate

| Boundary | Required rule |
| --- | --- |
| Deployment | Each product ships, rolls back, and can be unavailable independently. The suite switcher is a link, not an application merge. |
| Project membership | Research membership and authoring membership are independent. Membership in one never grants the other. |
| Authorization | Every request is checked by the product that owns the resource. Renderer visibility is not authorization. |
| Data ownership | Research owns sources, transcripts, logged clips, provenance, and reusable clip artifacts. Script owns narrative order, usage overrides, narration, graphics intent, builds, and delivery history. |
| APIs | Products integrate through versioned, authorized APIs and verified artifact descriptors, not shared databases or direct UI dependencies. |
| Desktop runtime | Research Desktop and the Script local agent/Resolve workstation remain separately installed and operated. Browser navigation transfers no local work, paths, files, jobs, or unsaved selection. |
| Release lifecycle | Product artifacts and production applications may advance on separate accepted slices. A shared primitive version does not silently rewrite an accepted product release. |

## 6. Shared-change propagation without shared production UI code

### 6.1 Versioned design contract

The contract-only artifact carries a suite contract version and a short change
ledger. Each shared primitive states the earliest contract version containing
it. Each product artifact records the contract version it was reviewed
against.

### 6.2 Change workflow

1. Propose a shared primitive change in a bounded design issue. Name whether it
   is semantic, accessibility, responsive, or visual-token-only.
2. Identify affected products, scenarios, viewports, runtime variants, and
   acceptance evidence before editing either product artifact.
3. If token values or literal consolidation change, route the decision through
   issue #21 or its accepted successor rather than deciding it incidentally.
4. Obtain producer acceptance of the contract change.
5. Update the suite contract artifact and increment its version.
6. Apply the accepted change to each affected product artifact in separate,
   bounded product work. Do not copy product pages into the contract artifact.
7. Run each affected product's own scenario regression at `1280 × 800` and
   `1024 × 768`, plus the small suite conformance checks for shell, switcher,
   accessibility, and token-version references.
8. Record product adoption. A product remains on the prior accepted contract
   version until its own update is reviewed.

This process deliberately allows temporary, explicit version skew. It is safer
than silently mutating every artifact and makes rollback and review evidence
possible.

### 6.3 Production boundary

The design contract does not create a cross-repository UI package. Product
implementations may independently implement the accepted primitive contract in
their own codebases. A future shared production package requires its own
architecture, versioning, accessibility, release, dependency, and rollback
decision; issue #13 does not authorize it.

## 7. Instructions for what Claude should build

These are instructions for a later authorized Claude Design task. They are not
authorization to execute that task now.

### 7.1 Project and artifact setup

1. Use one Claude project named **VERA Suite**.
2. Preserve the current approved Research artifact as the Research product
   artifact. Do not redesign or reorganize its application screens while
   establishing the suite structure.
3. Create **VERA Suite Design Contract** as a compact reference artifact with
   no product application pages.
4. Create **Script to Timeline** as a separate product artifact only after the
   prerequisites in section 8 are accepted.
5. Keep each product's runtime variants in that product artifact. Do not create
   separate Desktop and Web artifacts.
6. Keep historical baselines noncanonical and clearly named. Do not duplicate
   a product's current application implementation merely to preserve history.

### 7.2 VERA Suite Design Contract artifact

Build these sections:

1. **Authority and version** — contract version, accepted token-version
   reference, product authority links, and change ledger.
2. **Suite shell** — identity/product lockup, product switcher, product name,
   project switcher, account entry, primary/secondary navigation grammar, and
   examples showing that product and project switching are different controls.
3. **Primitive families** — the component/state families in section 4.3,
   expressed as semantic specifications and small conformance examples rather
   than copied product pages.
4. **Status and remediation grammar** — available, processing, waiting,
   blocked, setup/access needed, stale/conflict, disconnected, retryable,
   failed, and complete, with action and announcement rules.
5. **Collaboration grammar** — identity, presence, comments, replies, mentions,
   receipts, resolved/reopened/stale states, with explicit product anchor
   differences.
6. **Search and Topics grammar** — shared controls while stating that project
   keywords, Research Topics, Script Ideas/Extras, and document headings are
   not interchangeable taxonomies.
7. **Dialogs and accessibility** — modal and nonmodal rules, labels, focus,
   keyboard, Escape, focus return, announcements, contrast, reduced motion,
   non-color cues, and authorization-valid DOM presence.
8. **Responsive contract** — `1280 × 800` and `1024 × 768`, required reflow
   evidence, compact sorting, overflow, readable measures, and no scale-to-fit.
9. **Suite switching and boundaries** — the complete rules from section 5.
10. **Product adoption table** — accepted contract version and outstanding
    product-local adoption work.

Use symbolic token references until issue #21's producer-approved token set is
available. Never invent numeric values to make the contract artifact look
complete.

### 7.3 Script to Timeline artifact structure

When authorized, structure the product artifact as:

- **Application** — the current approved scenario, not a landing-page collage;
- **Scenarios** — focused state switches for the bounded high-fidelity slice;
- **Runtime capabilities** — Web, local-agent connected/disconnected, Resolve
  Free/Studio capability states without implying a second packaged app;
- **Component states** — product-specific use of the accepted suite primitives;
- **Accessibility and behavior handoff** — product semantics that screenshots
  cannot prove;
- **Regression index** — scenario, role, runtime, viewport, action, expected
  visible state, and expected accessibility/DOM evidence;
- **Content-language coverage** — a focused scenario proving continuous
  narration across multiple visual cuts, left-only/right-only asymmetry,
  hierarchical right-lane roles, exact/unplaced/three-point timing, variants,
  section-linked parked material, Sequences, Option sets, Comparison stacks,
  uploaded/linked images, versioned capture policies and motion presets,
  manual and Spotlight-bound slow-zoom focus with end-frame preview,
  one-action YouTube watch-page composites, capture Spotlights with supervised
  target repair, multi-cue Fusion infographic emphasis,
  typed visible prompter cues, comments/mentions, `Propose cut`, derived-
  graphic provenance, and unresolved local references without treating rows
  as edit boundaries.

Claude must not start with Research pages and replace nouns. The first Script
application surface must derive from the Script specification's readable
two-column document, narration-first anchors, visual cards, validation,
collaboration, and build model.

### 7.4 Required high-fidelity evidence

For every included scenario:

- test `1280 × 800` and `1024 × 768` as real layouts;
- exercise pointer and keyboard activation;
- verify the selected scenario, runtime, role, viewport label, rendered width,
  visible state, and accessibility/DOM state together;
- prove role- or capability-invalid actions are absent, not merely disabled;
- verify dialog focus and naming behavior, status announcements, search and
  Topic labels, and non-color distinctions;
- compare shared primitive use against the exact accepted suite contract and
  token version;
- record every deliberate product-specific exception;
- prove that timed Picture and its `Unresolved visual`, Clip, Image, Capture,
  `YouTube page composite`, and Graphic subtypes remain distinguishable from
  Audio cue, Citation, Editor note/timeline marker, Draft note, Reference, and
  Comment by text/icon and accessible name, not color alone;
- prove hover, focus, and keyboard traversal between exact narration ranges
  and attached cards; prove Unplaced items have no invented interval and the
  two-of-three timing rule exposes incomplete or contradictory timing;
- prove Variants, Sequences, Option sets, and Comparison stacks have visibly
  distinct build behavior; unresolved Option sets block Release unless their
  Producer-set policy is `Choose in Resolve`;
- prove a section-linked parked fragment appears both collapsed under its
  section and in global Extras without duplication or active-build inclusion;
- prove formatting remains nonsemantic and only an attributed `Propose cut`
  action creates strikethrough; accept parks content and reject restores it;
- prove derived graphics show source/version provenance and unresolved local
  references show import/relink/remediation without exposing absolute paths;
- prove upload and linked-image acquisition, Capture `Now`/`On build`/
  `Periodic` policy, immutable revisions/retention state, and versioned motion
  presets without performing real network or media actions;
- prove that `Present on YouTube page` turns a compatible Clip into a nested
  composite in one primary action; description/comments remain visible,
  `Refresh page now` produces a newly selected immutable page revision, slow
  zoom applies to the whole composite, and prior builds remain unchanged;
- prove a Capture Spotlight exposes selectable OCR words/lines over a fictional
  high-resolution capture, turns the confirmed source-pixel boxes into a
  previewed inverse matte, dims everything outside it, and records an exact
  interval. Show the generated matte/nested-sequence handoff, composition
  before whole-picture motion, and a visibly stale target instead of silent
  movement when a recapture changes layout;
- prove `Slow zoom` can focus on center, a manually clicked fictional face,
  or a confirmed Spotlight region. Show `Zoom to spotlight` timing, end-frame
  crop/clamping, ordered focus segments, source-update review, stale/accepted
  Spotlight remapping, resolved transforms, and honest Studio/Free output;
- prove one pinned Fusion infographic exposes semantic targets rather than
  internal node names and previews several narration-anchored highlight cues:
  at minimum one table-row target and two sequential bar targets. Show base,
  active, transition, reset, timing-conflict, template-update-available, Studio
  keyframe, and declared Free-fallback states without selecting issue #21's
  actual colors;
- prove typed pronunciation/performance annotations default to visible non-
  spoken prompter cues, and Comments with optional mentions remain discussion
  only.

## 8. Prerequisites and inputs for a high-fidelity Script prototype

### 8.1 Producer decisions required first

1. Accept this issue #13 artifact structure and shared design-language
   boundary.
2. Accept issue #21's token inventory and every keep/promote/alias/collapse
   decision, then accept the bounded token-wiring handoff. Issue #13 does not
   supply or modify those decisions.
3. Approve a bounded Script to Timeline design slice with its scenario list,
   acceptance matrix, and explicit exclusions.
4. Confirm how the prototype names the Script runtime presentations. The
   current specification supports a hosted Web client plus local desktop agent;
   it does not yet authorize an invented standalone Desktop authoring app.

### 8.2 Required source artifacts

- This accepted VERA suite design contract and its version.
- Issue #21's accepted token set and wiring evidence.
- The approved Research Video Clips Claude artifact and its exact accepted
  revision, used as a visual-language reference only.
- The Research `BEHAVIOR-CONTRACT.md`, `WEB-EDITION-DESIGN-BRIEF.md`,
  `APPROVAL-CHECKLIST.md`, and sanitized fictional fixtures.
- The Producer-accepted issue #24 representative-script coverage audit and
  `docs/prototypes/issue-24-sanitized-prototype-input-brief.md`. Use the
  private source only as retained evidence; Claude receives the sanitized
  brief, never the source document or URL.
- `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, especially sections
  4, 6, 7, 8.1–8.2, 9, and 10.
- Accepted Script contracts and canonical semantic inputs needed to make the
  chosen scenarios honest; the prototype must not contradict frozen behavior
  or invent production wire shapes.

### 8.3 Required bounded brief inputs

- target user and one primary job for the design slice;
- included and excluded product phases;
- exact application scenarios and fixture content;
- Producer/Editor/Viewer variants in scope;
- Web/local-agent/Resolve capability variants in scope;
- comments, mentions, Topics, search, readiness, remediation, and dialog states
  needed by those scenarios;
- reciprocal suite-switcher entry and fallback states;
- `1280 × 800` and `1024 × 768` acceptance at minimum;
- accessibility and keyboard matrix;
- the issue #24 sanitized prototype brief as the required fictional content
  authority; no private source title, URL, document identifier, names,
  quotations, facts, or source-specific links may enter Claude or screenshots;
- explicit statement that Claude edits only design artifacts and never product
  code, deployments, permissions, or data.

## 9. Automated and manual evidence for issue #13

### Automated evidence to retain before review

- repository validation passes;
- Markdown and whitespace checks pass;
- no contracts, fixtures, golden files, generated types, accepted tests,
  dependency manifests, or lockfiles change;
- the issue #24 coverage audit, plan, and sanitized prototype brief remain
  byte-identical to accepted commit `e72aa24`;
- the only new issue #13 edits are the bounded plan and Claude-brief handoff,
  with no private-source content or feature implementation;
- issue #13 remains claimed by the dedicated task and branch and is moved only
  to `In review`.

### Producer acceptance checklist

1. Open `docs/vera-suite-design-contract-and-claude-brief.md`.
2. In section 2, confirm the Research inventory reflects the current artifact:
   26 scenarios, six major flows, three roles, two service matrices, Component
   States, Visual Tokens, and both `1280 × 800` and `1024 × 768`.
   **Expected:** the material regression burden and the independent issue #21
   boundary are explicit.
3. In section 3, compare the three artifact options.
   **Expected:** the recommendation is one Claude project, separate product
   artifacts, and one contract-only suite artifact; it gives explicit editing,
   preview-performance, regression, and drift reasoning.
4. Review the project tree and Desktop/Web table.
   **Expected:** each product keeps runtime variants together, Research retains
   its approved Desktop/Web model, and Script does not invent a packaged
   Desktop app beyond its hosted client plus trusted local agent.
5. Review the source-of-truth table in section 4.2.
   **Expected:** every shared family has one authority, issue #21 owns token
   values, and product IA/semantics remain product-owned.
6. Review sections 4.3 and 4.4.
   **Expected:** common component/state families are comprehensive, while the
   transcript workspace and narration/visual-anchor editor remain purpose-built.
7. Review section 5 from the switch action through destination validation and
   explicit boundaries.
   **Expected:** switching opens a new tab, preserves the source session, passes
   only minimal opaque context, independently reauthorizes destination and
   linked projects, leaks no private content, and merges no deployment,
   membership, data, or desktop runtime.
8. Review section 6.
   **Expected:** shared changes propagate through a versioned design contract
   and bounded per-product adoption with no shared production UI package.
9. Review Claude's build instructions in section 7.
   **Expected:** they are specific enough to create the artifact structure and
   handoff without authorizing or accidentally beginning high-fidelity UI.
10. Review the prerequisites and inputs in section 8.
    **Expected:** later high-fidelity work cannot begin without accepted issue
    #13 structure, issue #21 token decisions, a bounded Script design slice,
    authoritative product inputs, both viewports, and accessibility evidence.
11. Review the issue #24 additions and sanitized prototype brief.
    **Expected:** every accepted sample content family has a visible authoring
    treatment; rows are never edit boundaries; unresolved choices, capture
    freshness, timing, and review states remain explicit; and issue #21 still
    exclusively owns visual-token decisions.
12. Record one precise response on issue #13:
    - acceptance: `Accept issue #13 suite design contract and Claude artifact structure.`
    - failure: `Issue #13 acceptance failed at checklist step <number>: <observed mismatch>.`

Leave issue #13 `In review` until the Producer records the acceptance response.
Never infer acceptance from silence or mark the issue `Done` from an agent
self-report.
