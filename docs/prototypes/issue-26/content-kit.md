# Fictional content-ID kit

Authority: [manifest K24](README.md#1-pinned-authorities-and-precedence),
especially K24 §§2–6. These are documentation aliases for producer review,
not UUIDs, schema examples, application fixtures, asset files, or a claim that
an ID resolves through a service. Do not add them to `/fixtures` or contracts.
Use K24's exact prose when an alias points to it; do not retrieve a URL.

## 1. Story and document aliases

Only K24 story names, prose, numbers and `.invalid` links are permitted.
Operational labels such as “Editor,” “Checkpoint A,” and “Revision A” below
are synthetic scenario metadata, not new story material or real identities.

| ID | Exact K24 source / content | Meaning and relationship |
| --- | --- | --- |
| F01 | §3 Harbor Lights Explainer | Fictional authoring project and its one review script. |
| F02 | §3 Why the Signal Changes | Section containing the content below; every parked fragment refers here. |
| F03 | §4 “A quiet harbor can still hide a moving pattern.” | OC opening narration; `moving pattern` is exact comment range. |
| F04 | §4 “Watch the marker behind me … as the tide turns and the reading begins to drift.” | One intact paragraph. Spoken text excludes the displayed PAUSE cue. Base OC = “Watch the marker behind me”; base VO = “as the tide turns and the reading begins to drift.” |
| F05 | §4 “Keep this calm.” | Ordinary Direction, excluded from prompter by default. |
| F06 | §4 Coastal Sensor Primer; `https://source-a.example.invalid/primer` | Citation on F03; zero picture duration. |
| F07 | §4 wide harbor Clip then sensor close-up Clip | Sequence. Test attachments: first = “as the tide turns”; second = “and the reading begins to drift” in F04. Two exact ranges, one paragraph. |
| F08 | §4 Option A `https://media-a.example.invalid/harbor` 00:12–00:19; Option B `https://media-b.example.invalid/sensor` 01:03–01:10 | One Option set, no selected member on reset. Source in/out is not narration placement time. |
| F09 | §4 three fictional treatments | Comparison stack; all alternates plus Choose in Resolve marker, distinct from F07/F08. Use ordinal candidate labels; no invented imagery. |
| F10 | §4 “The instrument calls this the Lunara effect.” | VO narration; pronunciation target exactly `Lunara`, alias `loo-NAH-rah`. |
| F11 | §4 “The public dashboard shows the same change from another angle.”; `https://page.example.invalid/dashboard` | Capture intent with On build policy, immutable candidate/selected/build revisions distinguished. |
| F12 | §4 “The warning appears directly beneath the second reading.”; “Review required before adjustment” | Capture Spotlight evidence. Narration anchor = that whole sentence; selected captured text = the separate warning. Never confuse OCR words with narration tokens. |
| F13 | §4 “The archive preserves one view each morning.”; `https://page.example.invalid/archive` | Conceptual Periodic example only under R22; history records are synthetic, not scheduled runs. |
| F14 | §4 “Here is the sensor before the trial began.”; `asset-demo-still-01` | Uploaded Image; manual focus `subject face` at source-normalized (0.68, 0.32), as K24 specifies. No actual face image is acquired. |
| F15 | §4 “A second still shows the repaired housing.”; `https://images.example.invalid/housing.png` | Linked Image, automatically acquiring → verifying → ready or failed; Slow zoom with Center focus. |
| F16 | §4 “This frozen screenshot came from an earlier review.”; `asset-demo-screenshot-01` | Uploaded screenshot, Image without live Capture relationship. |
| F17 | §4 “In one trial, the first bar reaches eighteen, then the second reaches twenty-seven.” | Bar Graphic; reading-1 = 18, reading-2 = 27, snapshot `demo-v1`; exact cue ranges `first bar` then `second`. |
| F18 | §4 “In the summary table, the west station needs attention.” | Table Graphic; fictional east/west/north rows; cue range `west station`. |
| F19 | §4 “The operator described the change as ‘slow, then sudden.’”; logged 00:24–00:32 | Logged Clip with readable transcript evidence and source audio on. Copy exact punctuation/prose from K24 for actual mock content. |
| F20 | §4 “Viewers saw the demonstration in its original online context.”; `harbor-demo`, 00:24–00:32 | Compatible YouTube Clip before treatment, then one page composite. Separate page/clip IDs; K24 requires description and two fictional comments. Use neutral description/comment placeholders, not fabricated source text. |
| F21 | §4 “A short chime marks the second reading.”; `demo-chime-v1` | Music/SFX use with fictional license note, pinned identity and phrase anchor. |
| F22 | §4 “That distinction matters because the next step depends on timing.”; `MEASURE FIRST / ADJUST SECOND` | Editable long-text Graphic data; explicit overlay/full-frame intent. |
| F23 | §4 `closing-line` variants A/B/C | A: “We adjust only after the second reading.” B: “The second reading tells us when to adjust.” C: “Timing decides the adjustment.” Exactly A active on reset. |
| F24 | §4 “A final comparison confirms the pattern.” | Narration with pending Propose cut over exact word `final`; actor is synthetic Producer. |
| F25 | §4 “Add a map somewhere near the comparison.” | Graphic intent, duration 4s, end = F24 `pattern`; derived start is compiled evidence, no nearest-row inference. |
| F26 | §4 “Add an establishing still.” | Unplaced Picture, duration 3s only; no start/end. |
| F27 | §4 `[unresolved local reference]` | Local audio Reference; no absolute path, filename, or locator revealed. |
| F28 | §4 “Check the on-screen units in Resolve.” | Zero-duration production marker; test point = F24 `pattern`. |
| F29 | §4 “The result is simple: observe, compare, then act.” | OC-only narration; empty picture lane is valid. |
| F30 | §5 “Explain why the first reading can be misleading.” | Open Idea. Child/sibling/reorder tests reuse this allowed text with distinct synthetic identities. |
| F31 | §5 section-linked unused paragraph with stale visual reference | One parked Extra identity under F02 and in global Extras; use the literal label `Unused paragraph` until Producer supplies more sanitized prose. |
| F32 | §5 “Verify the fictional units before publication.” | Excluded draft note; never active output. |
| F33 | §4 `@Editor Could we simplify “moving pattern”?` | Comment on F03 exact range; optional stable-user mention resolves to synthetic Editor identity. |
| F34 | §§4, 6.7 pause/pronunciation/pacing/emphasis | Pause at OC/VO boundary of F04; pronunciation on F10; optional emphasis on F17 `second`. Include in prompter starts on. |
| F35 | §§4, 6.1 asymmetric presentation | Left-only F29, right-only F26, paired F04/F07, blank separator with no block/event or duration implied. |

The F04 exercise for #14 marks a final OC span on `the reading begins to
drift` while preserving every spoken word and the single paragraph. This is
an explicit author edit after reset, not a rewrite of K24's base OC→VO sample.
Coverage examples use selected ranges/placeholder intent, not invented audio
alignment. F31 and F20 deliberately use neutral placeholders where K24 names
a content slot but supplies no prose. Claude must not import private material
to fill those slots.

## 2. Synthetic state/evidence aliases

These labels make comparisons reproducible. They do not propose production
wire formats. Relationships, rather than invented hashes or executable media,
are the evidence to show.

| ID | Reset / variants | Invariants to inspect |
| --- | --- | --- |
| E01 | Phase 2 single writer; Phase 3 Producer, Editor, Viewer; No membership | Role variants are separate resets; no Owner/Admin/Reviewer roles. |
| E02 | Acknowledged Revision A; local edit Revision B; later acknowledged Revision B | Preview source A until B acknowledged; every accepted operation has a synthetic actor. |
| E03 | Checkpoint A, initially unapproved, materializes Revision A and all three surfaces | Producer approval is a separate label event. Restore creates Revision C; A/B and builds remain. |
| E04 | Preview A from Revision A; Release A from approved Checkpoint A | Snapshot/dependency/delivery identities separate; source never follows live head. |
| E05 | No local agent; agent disconnected; connected + Free; connected + supported Studio; Studio unavailable/mismatch | Role and runtime intersect; runtime never grants Release permission. |
| E06 | Authorized Research link: none / one / several; unauthorized/stale/archived/unlinked destination | Only authorized fictional chooser entries. Denial contains no hidden project title. |
| E07 | Ready Capture revision A selected in Draft; new candidate B; warning-bearing candidate C | Manual recapture B unselected; explicit capture-and-use may select B if expected Draft matches. On build uses build-only B while Draft stays A. |
| E08 | Capture revision A pinned by Checkpoint A/Preview A; optional user pin removed | Automatic references/evidence/holds still protect A. No approved retention policy means all revisions retained. |
| E09 | F12 confirmed Spotlight on A; proposed remap on B; ambiguous match on C | New evidence identity per revision; stale cannot silently update motion. Original A evidence remains valid for A. |
| E10 | F20 Clip revision A + page revision A; page revision B after refresh | Captured count labels `Earlier count` / `Refreshed count` are synthetic placeholders; no fabricated factual counts. Old build pins both A revisions. |
| E11 | Template revision A, update B available; snapshot demo-v1; F17/F18 citation links to F06 and a neutral `Fictional derivation note` placeholder | F17 targets `bar:reading-1`, `bar:reading-2`; F18 `row:west`; human labels, kind, allowed base/emphasis/muted states and template-owned binding evidence. No node names or actual colors. |
| E12 | Timing proof A: start 0s/end 4s; B: start 0s/duration 4s; C: duration 4s/end 4s | All derive [0s,4s] in a clearly simulated timing example. Add duration 3s to A → conflict. These are not asserted speech timings for any paragraph. |
| E13 | Voice state, job stage, render/delivery result | Synthetic enum examples only; no provider calls, builds, media processing, file actions or uploads. |
| E14 | Blank Draft; Ideas-only; populated F01 document | Independent scenario resets, not duplicates masquerading as production branches. |

## 3. Reset protocol

1. Reset to F01/F02, content F03–F35 exactly as sourced, Revision A synced.
   All successful artifact/timing indicators explicitly say simulated.
2. Choose scenario, phase, role and runtime from the spine before each test.
   Tier 1 starts as the Phase 2 single writer with no local agent. Tier 2/3
   state their Phase 3 role. Reset clears prior test edits, not the source kit.
3. Base state: F23 choice A; F08 unresolved; F26 duration-only; F24 pending
   proposal; F31 stored/stale; E03 unapproved; E07 A selected; E11 A pinned.
4. Isolate the current test's blocker. Unrelated incomplete examples remain
   explicitly outside that test's active Draft, while still available in the
   coverage inventory. Never call the entire base kit Release-ready.
5. Only alter named IDs in that test. When testing successful Release, use the
   explicitly resolved test subset and approved checkpoint; when testing a
   blocker, state that blocker and keep the prior snapshot unchanged.
6. Stop on an unexpected default, invented content, hidden policy, or missing
   fixture relationship. Record scenario, content ID, authority ID and result.

A later artifact may implement a scenario reset mechanism. No mechanism or
fixture executable is created here. Determinism means fixed content, fixed
starting states and observable assertions, not a claim of real media or
production-server determinism.
