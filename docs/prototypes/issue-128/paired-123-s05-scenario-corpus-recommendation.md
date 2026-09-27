# Paired #123 / S05 successor roadmap

Status: **revised planning recommendation for Producer acceptance; no Design
artifact, GitHub issue, contract, fixture or accepted source has been changed**

## Outcome

Rebuild the complete #123 inbound-reconciliation and S05 outbound-update
successors around:

- one immutable Harbor Lights corpus generated directly from accepted #135;
- one reproducibly derived, read-only S03 review renderer;
- one shared review harness;
- 17 shared scenario geometries; and
- direction-specific scenarios only where product authority, safety or
  lifecycle behavior genuinely differs.

This is not permission to edit the accepted #123, S03, S05 or #128 pilot
artifacts. They remain frozen evidence.

## Authorities and settled product decisions

1. **Accepted #123 r2**, retained at commit `70dfcf2`, including:
   - `docs/prototypes/issue-123/ACCEPTED-HANDOFF.md`;
   - `docs/prototypes/issue-123/reconciliation-annotation-guide.md`; and
   - the accepted 22-change inventory.
2. **Accepted S05 / issue #58**, retained at commit `7eb71ca`, including its
   accepted plan, issue body and evidence.
3. **Accepted S03 v3 / issue #135**, retained as
   `S03 v3 authoring artifact - issue 135 export v2.dc.html`, SHA-256
   `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`.
4. **Current #128 pilot direction:** `SCRIPT / RESOLVE`; no `After update`;
   safe updates selected by default; bounded blocking; a frozen submitted plan;
   all-or-nothing baseline advancement; partial failure and same-attempt Retry.

The following decisions are settled:

- Every scenario names its older and newer state. In #123,
  `SCRIPT = older` and `RESOLVE = newer`; in S05,
  `RESOLVE v3 = older` and `SCRIPT = newer`. C17 also names its common
  ancestor and both current states.
- The row bank is extracted from the accepted #135 export rather than manually
  retyped as another fixture authority.
- A row with several outbound edits is one indivisible S05 update. Individual
  edits within that row cannot be cherry-picked.
- For S05, an overlapping Resolve edit is judged at the production-fact or
  timed-range level, not merely because two changes share a row. A bounded
  edit blocks only the outbound fact it changes, anchors, overlaps or
  invalidates.
- #123 may reconcile VO ↔ OC only when presenter visibility is verified.
  Ambiguous evidence blocks.
- Resolve-driven row splitting remains excluded from #123.
- Resolve-driven section-marker editing remains excluded from #123.
- Render settings and render lifecycle remain part of the complete S05
  successor.
- A deferred #123 item returns as `Deferred last review`.
- M2 changes duration only; its accepted 3.0s fade remains unchanged.
- Missing media blocks only when VERA must use that media to place or verify
  the affected update. A bounded conflict blocks only that item.
- A narrated-row addition is placed after r18, at the end of `Following the
  Evidence`, before `Closing the Loop`. Its fixture starts
  `Blocked · Narration recording needed`; choosing `Use placeholder audio`
  makes it Selected. M2 and the ending Placeholder remain untouched.
- A Blocked #123 item remains outstanding but does not gate `Reconcile script`
  for independently decidable work.
- O07 proves marker removal, rename and move. O01 already proves marker
  addition during first timeline creation.
- Partial execution follows document order and stops at the first failure:
  preceding selected work is `Verified in v4`, the failing item is
  `Attempted — not verified`, and later selected work is `Not attempted`.
  Retry resumes the same frozen plan. O09 also proves Resolve-only material
  survives into v4.
- Display `Footage`, not `Logged Clip`, as the visual type. `Logged` may remain
  source-management metadata.
- A transparent Graphic uses the accepted dashed card outline and a dashed
  underline beneath its words only while its card or boundary mark has
  hover/focus. A full-frame Graphic uses a solid inspection underline. Both
  use the accepted Graphic shade. Dotted remains reserved for music-bed
  inspection and boundary editing. Retain the accepted full-frame Graphic
  fill and straight marks `│N` / `N│`.

## Canonical scenario taxonomy

A **scenario** is an explicit older/newer derivation of the immutable base
corpus plus one isolated change geometry.
A scenario may contain several named cases when the cases share that geometry.
Harness states such as missing media do not create duplicate scenarios. Every
multi-case scenario uses suffixes (`C03a`, `C03b`, and so on) so screenshots,
copy review and acceptance can point to one exact case.

Bulk behavior is not inferred from one-item fixtures. Each successor also has
one combined review assembled from non-overlapping accepted scenarios:

- `CR-I · #123 COMBINED REVIEW` proves decision counts, unresolved gating,
  Defer and carry-over across several inbound changes.
- `CR-O · S05 COMBINED REVIEW` proves selected-by-default safe work, Select all
  safe excludes Blocked work, Clear all, counts, zero-selected gating, frozen
  submission, document-order partial failure and same-plan Retry across several
  outbound changes.

Combined reviews reuse scenario registry entries; they are acceptance
compositions, not additional scenarios.

The canonical set contains **35 scenarios**:

- **17 shared:** `C01–C17`;
- **8 #123-only:** `I01–I08`; and
- **10 S05-only:** `O01–O10`.

### Shared scenarios

The same ID in both successors must use the same rows, words, media, real
neighbors, anchors, ordering and change geometry.

| ID | Shared geometry | #123 expression | S05 expression |
|---|---|---|---|
| C01 | Visual property changes, such as On Camera Wide → Tight | Accept, keep or defer the verified property | One selectable row update |
| C02 | Words are cut and an existing Footage endpoint moves with them | Word deletion requires verified program-audio evidence; a picture trim alone never deletes words | One atomic row update |
| C03 | Visual range changes: `C03a` Footage ends earlier; `C03b` Graphic starts later | Mark only the changed endpoint; revealed presenter words stay neutral | One update per case |
| C04 | A visual-only row is added between real neighbors | Adopt or reject | Include or skip |
| C05 | Three consecutive rows are removed | Inert red evidence; one reconciliation change | One atomic deletion |
| C06 | A passage moves within a section; adjacent-row swap is its distance-one case | Both locations, linked identity and real neighbors | One update and one count |
| C07 | One row has several changes, such as a move plus a clip trim | Separate decisions only when each fact is independently safe | `Row updated · N edits`; one indivisible checkbox |
| C08 | Same-anchor media replacement | Card changes; anchors remain neutral | One row update |
| C09 | Opaque cutaway inserted in B-roll | Parent, cutaway and compact `↩ Footage N resumes` strip with mini thumbnail | One row update |
| C10 | Transparent Graphic over On Camera, including a cue | Base stays continuously visible | One row update |
| C11 | One visual is removed while narration and a sibling visual remain | Never infer word deletion | One row update |
| C12 | Two ordinary rows merge beneath a bridging Graphic | Preserve identities and anchors; block at unsafe structural boundaries | One atomic merge |
| C13 | Two clips trade fixed narration rows | Show changed pairing, not row travel | One update for the complete swap plan |
| C14 | Camera state changes VO ↔ OC | Verified presenter visibility only | One row update |
| C15 | Audio structure: `C15a` added, `C15b` removed, `C15c` moved across sections | One document-wide M identity; a move counts once | Each case is independently selectable |
| C16 | Audio duration changes, with a duration-driven end and unchanged 3.0s fade | Bed face and duration box; no invented out-word | A valid audio-only update |
| C17 | The same row changed on both sides: `C17a` compatible and `C17b` incompatible | Combine compatible changes or choose/defer incompatible changes | Both produce the same Blocked state, so S05 shows `C17a` only and routes to Resolve-changes reconciliation |

Acceptance checks, not additional scenarios:

- Each isolated S05 fixture proves its own Selected, Skipped or Blocked state,
  its count as one executable/verifiable update and selection-independent
  surface navigation. `CR-O` proves bulk selection, aggregate counts, frozen
  submission, failure and Retry.
- Each isolated #123 fixture proves its own decisions and consequences. `CR-I`
  proves aggregate decision counts, unresolved gating, Defer, Blocked
  exclusion and carry-over.
- Resolve-only material—dormant alternatives and `Preserved as-is` additions—
  is visible on S05's RESOLVE surface, produces no deletion proposal and is
  confirmed present after an update. I02 and I04 remain #123-only interaction
  scenarios because S05 has no decision to present for them.

### #123-only scenarios

| ID | Scenario | Why it is unique |
|---|---|---|
| I01 | A visual crosses a section heading and blocks | The script model cannot express the Resolve geometry safely |
| I02 | An opaque top visual hides dormant lower alternatives that remain preserved and restorable | Inbound reconciliation compares effective output without deleting topology |
| I03 | Ranged Need to Find is fulfilled by Footage while the request may remain open | The accepted hybrid is an inbound source-authority choice |
| I04 | Unsupported Resolve addition becomes locked `Preserved as-is`, optionally named | It cannot be represented as ordinary authored script content |
| I05 | Standalone visual has trustworthy timeline bounds but no spoken anchor | Timeline evidence exists without a safe script anchor |
| I06 | A preserved clip re-anchors to a verified word, with fit, ambiguity and collision states | These are post-recording reconciliation consequences |
| I07 | Entry/result lifecycle: checking, unavailable, error, no change, partial reconciliation and `VERA can't bound the conflict` | Inbound observation and reconciliation lifecycle |
| I08 | A deferred item returns as `Deferred last review` | This is the inbound counterpart to S05 skip carry-over |

### S05-only scenarios

| ID | Scenario | Why it is unique |
|---|---|---|
| O01 | Entry states: first timeline creation and timeline already current | Creation has no prior diff; current state has no action |
| O02 | Second update after a skip: `Skipped last update`; applied work does not return | Proves baseline advancement and outstanding work |
| O03 | A reviewed row changes again after review opened | Proves frozen-review freshness behavior |
| O04 | Narration is rewritten while production content stays fixed | Only the script authors new words |
| O05 | Narrated row is added with recording or placeholder-audio needs | Resolve cannot add script narration |
| O06 | One row splits into two | Inbound splitting is not authorized |
| O07 | Section marker is removed, renamed or moved | Marker addition is already proven by O01; markers are zero-duration derived timeline points |
| O08 | Capability states: Resolve closed/unreachable, unsupported, broken link, Free manual package and `VERA can't bound the conflict` | These gate execution rather than reconcile content |
| O09 | Partial timeline failure, same-attempt Retry and all-verified completion | Outbound execution and recovery |
| O10 | Render settings and lifecycle: wait/resume, render-only retry and cancellation | Rendering follows verified timeline work |

### Controlled missing-media states

Controlled state is a harness case, not a new geometry. The allocation table
must include every applicable toggle, including:

- C02: the affected visual is offline;
- C02: unverified program-audio evidence, where picture trim alone cannot
  delete narration;
- C12: the new bridging Graphic is offline; VERA must place and verify it, so
  the entire atomic merge is Blocked while existing v3 Footage remains
  evidence and unrelated updates remain selectable;
- C14: ambiguous presenter visibility, which blocks;
- C16: the affected audio file is offline; in its isolated audio-only review
  this is the explicit zero-safe-updates state and disables `Update timeline`;
- I06: fit, ambiguity and collision;
- I07 and O08: bounded and unbounded capability/conflict states;
- O09: blocked exclusion, document-order partial failure, same-plan Retry and
  Resolve-only preservation; and
- O10: render wait, resume, retry and cancellation.

Offline media is never deletion evidence. When the conflict is bounded, block
only the affected item. When VERA cannot bound it, use I07 or O08.

## Shared harness and scenario identification

Both successors must use one harness implementation rather than separately
eyeballed shells. It owns:

- the scenario registry and navigation;
- viewport sizing;
- controlled-state toggles;
- keyboard behavior; and
- the scenario identity frame.

Each scenario presentation—product rail, document stage and sticky product
footer—sits inside the same neutral-gray rectangular border. Its ID is plain
text in a gap in the top border, with no fill, capsule or attached tab:

- `C06 · SHARED` appears in both artifacts;
- `I03 · #123 ONLY` appears only in #123; and
- `O04 · S05 ONLY` appears only in S05.

The gray frame and ID are harness metadata, not product UI. The measured
`1280×800` or `1024×768` product shell sits inside it; the frame consumes none
of that width or height and is not the scroll container. The host pane must be
at least the target width. Semantic red and green borders remain inside the
frame.

The shared `C` number makes paired screenshots directly comparable. Separate
`I` and `O` sequences make it explicit that unique scenarios have no false
counterpart.

## Renderer grammar comparison experiment

Do not decide connector routing from prose. At the first Issue B checkpoint,
use C12—the maximum connector-density case with its longest label—to render
the exact geometry that crossed cards in #128 at `1280×800` and `1024×768`
with:

1. accepted #135 two-track connector routing; and
2. #128-style nested connector lanes.

Compare:

- intersection with cards, thumbnails, labels or readable text;
- traceability of every relationship;
- document width lost to gutters;
- horizontal overflow; and
- pointer and keyboard focus correspondence.

The Producer selects the winner before Issue B completes. The comparison lives
in the shared foundation harness, not a third Design artifact.

### Settled Graphic inspection grammar

Use one coherent transparency cue:

- transparent Graphic: accepted dashed card outline plus dashed narration
  underline on card/mark hover or keyboard focus;
- full-frame Graphic: accepted filled treatment plus solid narration underline
  on card/mark hover or keyboard focus;
- both: accepted Graphic shade, straight marks `│N` / `N│`, and no underline
  at rest.

Dotted is not a Graphic treatment. It remains reserved for music-bed
inspection and boundary editing. Simultaneous dashed and solid underlines are
an implementation defect.

## Required row-allocation table

Before construction, assign every `C`, `I` and `O` scenario to exact Harbor
Lights rows. The accepted table must name:

- scenario and case ID;
- current and changed row IDs;
- real before/after neighbors;
- section and heading relationships;
- required narration shape and camera state;
- visual/media identities and anchors;
- audio identities and spans; and
- every controlled harness state.

The allocation must demonstrate, on paper, that:

- C14 uses r21's narrated `Visual Undefined` state so a verified VO → OC
  change is visible rather than hidden beneath a full-row Still;
- C13 has adjacent rows with clips that can plausibly trade;
- I01 has a heading between the relevant rows;
- C17 has a row that both sources could plausibly edit;
- C06 uses a section with enough rows for a three-row passage, three-row
  separation and real neighbors at both locations;
- C15 and O07 include two sections where their cross-section cases require it;
- move locations have real neighbors at both ends; and
- no logical identity is duplicated as a DOM identity when evidence repeats.

If the 22 current Harbor Lights rows cannot supply a required shape, Issue A
may extend the immutable corpus only with word-for-word accepted S03 content,
stable new IDs and explicit Producer acceptance. It may not invent narration
to make a geometry fit. Finding a mismatch after that blocks renderer
construction rather than forcing fixture improvisation.

## Reproducible shared review foundation

The shared renderer must be a recorded derivation, not another hand-edited
fork or runtime patch chain.

First confirm the repository source matches the accepted #135 SHA-256. Derive
from that exact export through one deterministic, ordered build-time
string-replacement chain. Run it once when the renderer is built, verify every
expected target count and commit the derived output; do not patch at page
load. Record:

- accepted source filename and SHA-256;
- the ordered transformation list;
- a hash of the transformation source; and
- the derived renderer hash.

Repository tooling computes and records hashes if Claude Design cannot do so
reliably.

Fail clearly when the source hash or expected transformation targets change.
Keep one immutable corpus, one scenario registry and one row-rendering path.
Use stable logical IDs and occurrence-local rendered IDs. Thin inbound and
outbound adapters supply decisions, selection and lifecycle behavior without
forking row grammar.

Foundation smoke coverage must include:

- an unchanged row rendered through both adapters;
- removal and move with repeated logical rows;
- merge, transparent Graphic and opaque cutaway;
- words cut and audio duration;
- one dormant alternative;
- one `Preserved as-is` addition;
- one standalone timeline-bounds visual; and
- one Resolve-evidence return strip with mini thumbnail.

It must also prove that the derived output emits zero editor controls, former
or removed evidence rows cannot receive focus, and occurrence-local rendered
IDs remain unique when a logical row appears twice.

These inbound-only smoke cases prevent an outbound-first foundation from
quietly excluding #123 rendering needs.

## Roadmap decomposition

Create four new bounded Inbox issues. Do not promote or dispatch downstream
work until its dependencies are accepted and Done.

### Issue A — Approve paired corpus and renderer grammar

- **Outcome:** accept the 35-scenario matrix, named cases, combined-review
  compositions, explicit older/newer states, row-allocation/toggle table,
  shared harness specification and settled Graphic grammar. Define the
  connector comparison and its selection gate; construction occurs in Issue B.
- **Routing:** `model:sol`, `effort:xhigh`.
- **Acceptance:** Producer.
- **Dependencies:** `- Blocked by #135`.
- **Exclusions:** no successor construction and no accepted-source edits.

### Issue B — Derive the shared S03 review foundation

- **Outcome:** produce the reproducible renderer derivation, generate the
  immutable corpus directly from accepted #135, and build the shared harness,
  thin adapters and smoke proof. First render the bounded C12 connector
  comparison and obtain the Producer's routing selection, then complete the
  foundation.
- **Routing:** `model:sol`, `effort:xhigh`.
- **Acceptance:** Producer.
- **Dependencies:** `- Blocked by <Issue A>`.
- **Exclusions:** no complete #123 or S05 successor and no production renderer
  extraction.

### Existing #128 — Complete the S05 successor

Before additional work, retain the pilot checkpoint, pause the current slice,
release its active claim and add dependencies on Issues A and B. Do not close
the five-case pilot as the full successor.

After Issue B is accepted, build `C01–C17`, `O01–O10` and `CR-O` with:

- `SCRIPT / RESOLVE`; no `After update`;
- safe changes selected by default and blocked work excluded;
- Select all safe, Clear all and a disabled zero-selection action;
- `Update timeline` with `Creates v4 · v3 is not changed`;
- indivisible multi-edit row bundles;
- atomic move, deletion, merge and spanning-audio counts;
- frozen submission and same-attempt Retry;
- explicit section-marker remove/rename/move cases, with addition proven by
  first timeline creation; and
- render settings and lifecycle.

The pilot checkpoint must retain these open items:

- connector routing awaits the experiment;
- sticky bars were not measured at true target widths;
- #123's full-frame Graphic patch was not visibly exercised; and
- one Graphic hover showed dashed and solid underlines together, with cause
  untraced.

### Issue C — Build the complete #123 successor

- **Outcome:** build `C01–C17` plus `I01–I08` and `CR-I` through the accepted
  shared foundation.
- **Routing:** `model:sol`, `effort:high`.
- **Acceptance:** Producer.
- **Dependencies:**
  - `- Blocked by <Issue A>`;
  - `- Blocked by <Issue B>`.
- **Exclusions:** no continuation of #123's brittle patched renderer; no
  accepted #123 edits.

### Issue D — Paired successor conformance audit

- **Outcome:** compare every shared case at the same state, scroll position and
  exact viewport; accept only intentional inbound/outbound differences.
- **Routing:** `model:sol`, `effort:high`.
- **Acceptance:** Producer.
- **Dependencies:**
  - `- Blocked by #128`; and
  - `- Blocked by <Issue C>`.
- **Exclusions:** no new scenario design; foundation defects return as bounded
  amendments to Issue B.

### Existing #131 — Production feasibility gate

Keep #131 independent. It is not absorbed into Design work. Production
implementation remains blocked until #131 and both successor designs are
accepted.

## Build and acceptance order

1. Accept Issue A's scenario allocation and visual comparison decisions.
2. Accept Issue B's reproducible foundation and smoke cases.
3. Build and accept the full S05 successor in #128 and the #123 successor in
   parallel after Issue B.
4. Complete Issue D's paired audit, in which selecting any `C` ID in either artifact
   shows the same rows, words, media, neighbors, geometry, gray frame and ID.
   Only direction-specific controls, statuses and consequences may differ.
5. Keep production blocked until #131 and the accepted designs authorize it.

Producer evidence for Issues A–C must include:

- exact `1280×800` and `1024×768` viewport measurements;
- scenario IDs and gray-border placement;
- real neighbors around additions, removals, moves and merges;
- sticky navigation throughout the scroll range;
- connector/card clearance and absence of horizontal overflow;
- pointer and keyboard inspection with visible focus;
- selection persistence, atomic counts and missing-media block scope;
- partial failure, Retry and render recovery; and
- exact export filenames, hashes and embedded assets.

No issue is closed on an agent self-report. Each remains In review until the
Producer accepts the named artifact and checklist.
