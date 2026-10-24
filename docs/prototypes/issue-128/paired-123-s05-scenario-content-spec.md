# Paired #123 / S05 scenario content specification

Status: **revised after Claude review for Producer acceptance; no Design
artifact, accepted source, GitHub issue, contract or fixture has been changed**

Companion roadmap:
[`paired-123-s05-scenario-corpus-recommendation.md`](./paired-123-s05-scenario-corpus-recommendation.md)

## Purpose and reading rule

This document fixes the literal content of the proposed 35-scenario corpus
before either successor is built. It defines:

- the exact narration and visual-intent text available to scenarios;
- the exact scenario titles, summaries, annotations and state copy;
- the exact changes applied to those rows; and
- which copy is inherited versus newly drafted.

Text inside quotation marks or code formatting is literal UI/fixture copy.
Unquoted prose is implementation guidance. A scenario may cite a row-bank ID
instead of repeating its narration; the cited row's complete wording is part
of that scenario. No implementer may paraphrase quoted copy silently.

Source tags:

- **S03:** accepted #135 narration or accepted S03 v3 row treatment.
- **#123:** accepted #123 r2 scenario or decision language.
- **#128:** current issue #128 pilot language.
- **S05:** accepted issue #58 behavior or example.
- **NEW:** proposed connective copy requiring Producer acceptance.

## Global literal copy

### Harness

| Purpose | Literal copy |
|---|---|
| Shared ID | `C01 · SHARED` through `C17 · SHARED` |
| #123-only ID | `I01 · #123 ONLY` through `I08 · #123 ONLY` |
| S05-only ID | `O01 · S05 ONLY` through `O10 · S05 ONLY` |
| Viewport choices | `1280 × 800`; `1024 × 768` |
| Normal state | `Default` |
| Missing visual | `Visual offline` |
| Missing audio | `Audio offline` |
| Unverified program audio | `Program audio unverified` |
| Presenter evidence | `Presenter visibility ambiguous` |
| Concurrent script change | `Newer script version` |
| Preserved-media fit | `Fits`; `Ending review`; `Ambiguous`; `Collision` |
| Unbounded conflict | `VERA can't bound the conflict` |
| Partial result | `Partial update failure` |
| Reset | `Reset scenario` |

The ID is plain text in a gap in the neutral-gray harness's top border. It has
no fill, capsule or attached-tab shape and is never repeated inside the
product rail. The gray frame sits outside the measured product shell and is
not its scroll container: the product itself remains exactly `1280 × 800` or
`1024 × 768`, and the host pane must be at least that wide.

### Graphic inspection grammar

| Graphic | At rest | Card/mark hover or keyboard focus |
|---|---|---|
| Transparent | Accepted dashed card outline; no word underline | Dashed underline beneath its words |
| Full-frame | Accepted filled treatment; no word underline | Solid underline beneath its words |

Both use the accepted Graphic shade and straight marks `│N` / `N│`. Dotted
remains reserved for music-bed inspection and boundary editing. A Graphic may
never show dashed and solid word underlines simultaneously.

### Shared surface navigation

| Purpose | Literal copy |
|---|---|
| Script surface | `SCRIPT` |
| Resolve surface | `RESOLVE` |
| Script source | `Current script` |
| Resolve source | `Current Resolve` |
| Reconciled result, only when neither source matches | `Script after reconciling` |
| Resolve version | `Current Resolve · v3` |

Changing the viewed surface never changes a #123 decision or S05 selection.
Both successors expose only `SCRIPT / RESOLVE`; neither adds an `After update`
surface.

The Resolve version token follows the scenario's actual baseline. O02 therefore
uses `Current Resolve · v4`; C17 uses `Current Resolve · edited since v3`.

### Source-state contract

The row bank is immutable source material, not a global before or after state.
Every scenario derives two explicit variants from it:

- #123: `SCRIPT = older`; `RESOLVE = newer`.
- S05: `RESOLVE v3 = older`; `SCRIPT = newer`.

The scenario entry must name the exact older and newer value. For C17, which
tests concurrent edits, it must additionally name the common ancestor, current
script and current Resolve states. Direction-specific consequence copy follows
those states; shared physical geometry does not imply shared action copy.

For S05, an overlapping Resolve edit is judged at the production-fact or timed
range level, not merely because two changes share a row. A bounded edit blocks
only when it changes, anchors, overlaps or invalidates a fact the outbound plan
must execute or verify. C17a deliberately exercises that rule.

### #123 decision copy

| Purpose | Literal copy |
|---|---|
| Resolve outcome | `Accept Resolve` |
| Script outcome | `Keep current script` |
| Compatible combined outcome | `Combine both changes` |
| Postpone | `Defer` |
| Deferred carry-over | `Deferred last review` |
| Primary action | `Reconcile script` |
| Remaining-decision state | `Undecided` |
| Deferred consequence | `No change this review. This difference remains unresolved.` |
| Resolve safety reminder | `Current Resolve is not changed by this review.` |

`Reconcile script` remains disabled while any visible non-deferred, non-Blocked
change is undecided. A Blocked item stays outstanding but does not prevent the
producer from reconciling the independently decidable items.

### S05 selection and action copy

| Purpose | Literal copy |
|---|---|
| Checked state | `Selected` |
| Unchecked state | `Skipped` |
| Unsafe state | `Blocked` |
| Bulk select | `Select all safe` |
| Bulk clear | `Clear all` |
| Primary action | `Update timeline` |
| Action subline | `Creates v4 · v3 is not changed` |
| Selected consequence | `Planned for v4 · verification required.` |
| Skipped consequence | `Resolve keeps current. Difference stays outstanding.` |
| Blocked consequence | `Resolve stays unchanged — blocked. Difference stays outstanding.` |
| Carried skip | `Skipped last update` |
| Retry | `Retry failed update` |
| Verified result | `Verified in v4` |
| Failed result | `Attempted — not verified` |
| Unattempted result | `Not attempted` |
| Skipped result | `Skipped` |
| Blocked result | `Blocked · not submitted` |
| Incomplete heading | `Update incomplete. Timeline v3 remains current. Baseline not updated.` |

At zero selected, `Update timeline` is disabled. Blocked work is unchecked and
cannot be selected by `Select all safe`.

Missing media blocks an item only when VERA must use that media to place or
verify the affected update. Offline media is never deletion evidence. A
bounded conflict blocks only its item; an unbounded conflict uses I07 or O08.

### Structural annotations

| Purpose | Literal copy |
|---|---|
| Shared move relationship | `Same section · three rows apart · one move` |
| Moved from | `Moved from here` |
| Moved to | `Moved here` |
| Atomic three-row deletion | `3 rows removed · one update` |
| Merge older evidence | `2 ROWS` |
| Merge newer result | `MERGED ROW` |
| Merge relationship | `2 rows → 1 · one merge` |
| Return strip | `↩ Footage 1 resumes` |
| #123 no counterpart | `No equivalent row in the current script.` |
| S05 no counterpart | `No equivalent row in current Resolve.` |

Every addition, deletion, merge or move shows the real row immediately before
and after the affected range. Moves show those neighbors at both locations.

## Fixture and combined-review model

Each `C`, `I` or `O` scenario is an older/newer derivation of the immutable row
bank plus one isolated change geometry. Named cases use suffixes so a
screenshot identifies one exact proof. Harness toggles change evidence or
lifecycle state without making another scenario.

Two combined reviews reuse non-overlapping scenario entries:

### CR-I · #123 COMBINED REVIEW

- C01 — On Camera framing.
- C03a — Footage ends earlier.
- C08 — same-anchor replacement.
- C17a — compatible two-sided change.
- I01 — Blocked cross-heading visual.
- I08 — `Deferred last review` carry-over.
- Purpose: prove aggregate counts, unresolved gating, independent decisions,
  Defer, Blocked exclusion and carry-over. Blocked does not gate the
  `Reconcile script` action. This composition is not a 36th scenario.

### CR-O · S05 COMBINED REVIEW

- C09 — opaque cutaway.
- C05 — three-row deletion.
- C01 — On Camera framing.
- C16 — audio duration, shown in its `Audio offline` Blocked state.
- Purpose: prove selected-by-default safe work, Select all safe, Clear all,
  counts, zero-selected gating, blocked exclusion, frozen submission, partial
  failure and Retry.
  This composition is not a 36th scenario.

## Canonical Harbor Lights row bank

These 22 rows are generated directly from the accepted #135 S03 v3 export;
this prose is a review mirror, not a second fixture authority. Scenario
operations derive explicit older/newer variants and change only the text or
production facts named later.

### Opening the Harbor

#### r1 — visual-only opening

- Narration: none.
- Visual: `Placeholder`.
- Card detail:
  `FUTURE OPENING GRAPHIC — “Why the Signal Changes” over a wide Harbor Lights image, with space for the series mark and episode title. Not designed in S01–S03.`
- Duration: `3.0s needed`.

#### r2 — presenter introduction

Narration:

> Today we're at the mouth of Harbor Lights, where one small sensor has been producing a very strange-looking signal. I'm Wren Alvarez, and over the next few minutes we're going to compare that signal with what the water was actually doing. The surprising part is that the harbor itself was behaving normally. [turns toward the water behind her] The apparent anomaly came from the way the instrument met the changing tide. Once we line up the footage, the keeper's notes, and the readings, the pattern becomes much easier to understand.

Visuals:

- `On Camera · Wide` for the complete row.
- Transparent `Graphic · Wren Alvarez · Harbor Reporter` from
  `I'm Wren Alvarez` through `actually doing.`

### Why the Signal Changes

#### r3 — harbor mouth

Narration:

> The tide has just turned, and the water at the harbor mouth is already running the other way. You can watch it slide past the pilings if you stand at the end of the pier. Nothing about the harbor looks dramatic at this point in the cycle. That is exactly why the change in the sensor reading surprises people. The water is behaving normally, and the instrument is recording that change faithfully.

Visual: `Footage · harbour-mouth-wide_0812.mov · Quiet sound`, complete row.

#### r4 — marker buoy, visual only

- Narration: none.
- Visual: `Footage · horizon-steady_0805.mov · Full sound`.
- Transcript: `…and there is the marker buoy again, dead flat, the way it reads on a settled afternoon. The wake reaches the piling a few seconds later, and then the signal begins to move.`

#### r5 — sensor housing and ferry wake

Narration:

> Down at the piling, the sensor housing sits directly on the waterline. At high tide it disappears beneath the surface, but as the channel drains it is exposed again. Salt and algae build up around the opening, which changes how quickly the probe responds. [more quietly] A ferry wake can push water past the housing for only a few seconds. Once the wake passes, the reading settles back into the pattern we expect.

Visuals:

- `Footage 1 · sensor-housing-cu_0812.mov · Quiet sound`, from `Down` through
  `the probe responds.`
- `Footage 2 · channel-light-dusk_0809.mov · Quiet sound`, from
  `A ferry wake` through its duration-driven endpoint.

#### r6 — sensor cutaway from presenter

Narration:

> From here, you can see how close the housing sits to the normal high-water mark. [gestures toward the piling behind her] Watch the dark band on the post behind me. The band is the line left by repeated tides, and the buildup around the sensor opening sits just below it. When we return to the wider view, compare that position with the keeper's written notes. Together, those details explain why the apparent spike is not a sudden change in the harbor.

Visuals:

- `On Camera · Wide`, then `On Camera resumes · Tight`.
- Cutaway `Footage 1 · sensor-housing-cu_0812.mov · Quiet sound` from
  `The band is` through `just below it.`

#### r7 — second gauge

Narration:

> Across the channel, the keeper checks the same instrument against a second gauge. The comparison matters because a single bad reading can look convincing on its own. A ferry wake reaches the piling before the wider tide changes, and the sensor reacts first. For a moment, the two lines separate. Then the harbor calms, and both readings begin to agree again.

Visuals:

- `On Camera · Tight`, then `On Camera resumes · Tight`.
- Cutaway `Footage 1 · channel-light-dusk_0809.mov · Quiet sound` from
  `A ferry wake reaches` through `two lines separate.`

#### r8 — three camera angles

Narration:

> From the western pier, the first camera watches the marker buoy lean into the current. At the exact moment the wake reaches the piling, a second angle shows water climbing the sensor housing. That view holds until the top of the probe disappears beneath the surface. A third camera then follows the wake toward the channel light. Taken together, the three angles show the same event moving through the harbor.

Visuals:

- `Footage 1 · harbour-mouth-wide_0812.mov · Quiet sound`.
- `Graphic 2 · Wake reaches piling · 0:04`, from `lean into the current.`
  through `climbing the sensor housing.`, spanning the Footage 1-to-Footage 3
  cut.
- `Footage 3 · sensor-housing-cu_0812.mov · Quiet sound` from
  `At the exact moment` through `beneath the surface.`
- `Footage 4 · gull-liftoff_0731.mov · Quiet sound` from `A third camera`
  through `through the harbor.`
- M1 starts on `From the western`.

#### r9 — housing opening

Narration:

> The camera holds on the narrow opening where water enters the sensor housing. At first, the flow looks steady enough to explain the normal readings. Small pieces of algae begin to bend across the opening as the level falls. The shot ends before we can see whether the passage clears completely. That missing moment is exactly what we need to compare with the sudden change in the data.

Visual: `Footage 1 · fogged-lens_0805.mov · Quiet sound`, complete row.
M1 continues.

### Following the Evidence

#### r10 — line chart

Narration:

> The first line shows the water level predicted from the tide table. The second line shows what the sensor reported at the piling. For most of the morning, the two traces rise and fall together. The important moment comes when the sensor produces a sudden spike even though the expected water level continues to change gradually. That difference is the clue that sends us back to the footage.

Visual:
`Placeholder · FUTURE LINE CHART — Title: Expected Tide vs. Sensor Reading. Show both data series. Not designed in S01–S03.`
M1 ends on `back to the footage.`

#### r11 — status page

Narration:

> The harbor authority publishes a public status page for every monitoring station in the channel. On the morning of this reading, that page showed the sensor as active and reported no communications failure. It also listed the most recent maintenance visit and the time of the last successful upload. Those details do not explain the strange value by themselves, but they rule out several simpler failures. The page gives us a timestamped record to compare with the keeper's notes.

Visuals:

- `Web Capture 1 · Harbor authority sensor-status page` through
  `communications failure.`
- `On Camera · Wide` for the remainder.

#### r12 — archival photograph

Narration:

> An archival photograph shows the same piling before the current sensor was installed. The dark waterline is already visible on the timber, along with years of salt and algae. Near the center of the frame, the mounting bracket sits just above the ordinary low-tide level. A slow move from the full pier toward that bracket would help the audience understand exactly where the instrument sits. The photograph turns an abstract reading into a physical location.

Visual: `Still Image 1 · Archival photo · piling before installation`.
Motion: `Slow push`.

#### r13 — maintenance-video page

Narration:

> The agency posted a behind-the-scenes video about maintaining the harbor sensor. In its first two months, the video attracted more than 50,000 views. Most viewers encountered the explanation on the original video page rather than through the agency's technical report. Showing the surrounding page lets the audience see both the maintenance footage and the scale of that public response. That context is why the view count belongs in the visual story.

Visuals:

- `Web Capture 1 · Agency maintenance-video page`.
- Transparent `Graphic 2 · 50,000 views`, starting on `the video attracted`
  and ending on `50,000 views.`, with
  `Highlight cue on the word “50,000”`.

#### r14 — three sources

Narration:

> An archival photograph shows the original sensor bracket before the current housing was installed. A supplied screenshot of the maintenance bulletin records the date the replacement was completed. Next, a screen recording of the monitoring dashboard shows the reading arriving in real time. Together, these sources connect the physical repair to the digital record. None of them changes the conclusion, but each explains a different part of the chain.

Visuals:

- `Placeholder 1 · FUTURE STILL IMAGE — archival photo provenance` through
  `was installed.`
- `Placeholder 2 · FUTURE STILL IMAGE — supplied screenshot provenance` from
  `A supplied screenshot` through `was completed.`
- `Placeholder 3 · FUTURE FOOTAGE — screen-recording provenance` from
  `Next, a screen recording` through `of the chain.`

#### r15 — keeper quotation

Narration:

> The keeper described the change in a phrase that is easier to remember than the graph. She called it “slow, then sudden,” because the water moved steadily while the reported value jumped all at once. Her description captures the difference between the physical event and the recorded signal. The signal changed. The tide did not.

Visuals:

- Transparent `Graphic 1 · “slow, then sudden” · Harbor keeper` through
  `the recorded signal.`
- Full-frame `Graphic 2 · THE SIGNAL CHANGED. THE TIDE DID NOT.` from
  `The signal changed.` through `The tide did not.`

#### r16 — station table

Narration:

> Three stations recorded the tide during the same hour. The east station stayed close to its predicted range, and the north station showed only a small delay. The west station is the only one that produced the sharp temporary jump. That comparison makes a harbor-wide event much less likely. It points instead to a condition at one instrument.

Visual: full-frame `Graphic 1 · Station comparison` with
`Highlight cue on the word “west”`.

#### r17 — outstanding visual request

Narration:

> We still need a closer view of the maintenance crew cleaning the sensor housing. That footage would show whether the opening was blocked before the reading changed. For now, the edit can continue with a clearly labeled request in its place. Anyone working in Research can eventually attach candidate clips to the request. When one is selected later, it should replace the stand-in without changing the surrounding narration.

Visual: `Need to Find 1 · Technician cleaning algae from the sensor housing.`
through `reading changed.`; then `On Camera · Wide`.

#### r18 — field notebook

Narration:

> The keeper records every reading by hand before it enters the archive. Those notes tell us when the instrument was cleaned, moved, or exposed by the tide. [holds up the field notebook, page toward camera] This entry was written the morning the signal changed. The number alone looks alarming, but the note beside it explains exactly what happened. Once we compare the two, the pattern becomes ordinary again.

Visual: `On Camera · Wide`, complete row.

### Closing the Loop

#### r19 — conclusion

Narration:

> The strange signal did not come from a sudden change in the harbor. It came from a familiar sensor meeting an ordinary tide in an unusual way. The footage, the public record, and the keeper's notes all point to the same explanation. [future Project Audio theme begins softly under narration] The lesson is simple: before treating a number as a discovery, look closely at how it was measured. That is where this story ends.

Visual: `On Camera · Tight`, complete row.
M2 `Harbor Lights Theme` starts on `The lesson`.

#### r20 — ending Placeholder, visual only

- Narration: none.
- Visual: `Placeholder` with
  `FUTURE ENDING GRAPHIC — Cut here when the future Project Audio theme reaches its named marker “END TITLE HIT”. Hold the Harbor Lights end card through the remaining theme tail.`
- Audio annotation: `Holds through the M2 tail · ~3.9s`.
- M2 ends by duration; there is no out-word.

#### r21 — maintenance report

Narration:

> The final maintenance report arrived two weeks after the sensor was cleaned. It confirmed that debris had collected around the opening during the falling tide. The next inspection found the housing clear and the readings back inside their expected range. That result supports the explanation we have followed through the harbor. One final piece of visual evidence still has to be chosen for this passage.

Visual: `Visual Undefined`.

#### r22 — blank working row

- Narration: none.
- Visual: `Visual Undefined`.

## Allocation and controlled-state matrix

This table is the compact allocation authority. The detailed scenario entry
below supplies the literal words, media and consequence copy.

| ID/case | Affected rows or span | Real context / required shape | Controlled state |
|---|---|---|---|
| C01 | r18 | r17 / r19 | Default |
| C02 | r8 | r7 / r9 | Default; Visual offline; Unverified program audio |
| C03a | r6 | r5 / r7 | Default |
| C03b | r13 | r12 / r14 | Default |
| C04 | r4 | r3 / r5 | Default |
| C05 | r11–r13 | r10 / r14 | Default |
| C06 | r11–r13 moved after r16 | source r10/r14; destination r16/r17; one section has at least eight rows | Default |
| C07 | r5 moved between r7/r8 | source r4/r6; destination r7/r8 | Default |
| C08 | r3 | r2 / r4 | Default |
| C09 | cutaway inside r5 | r4 / r6; base plus return strip | Default |
| C10 | transparent Graphic in r2 | r1 / r3; continuous On Camera base | Default |
| C11 | r7 | r6 / r8; On Camera sibling remains | Default |
| C12 | r8+r9 merge | r7 / r10; maximum connector density and long label | Default; new bridging Graphic offline |
| C13 | clips in adjacent r6/r7 trade rows | r5 / r8 | Default |
| C14 | r21 | r20 / r22; VO with Visual Undefined → OC | Default; presenter visibility ambiguous |
| C15a | M1 added across r8–r10 | r7 / r11; crosses into `Following the Evidence` | Default |
| C15b | M1 removed across r8–r10 | r7 / r11 | Default |
| C15c | M1 moves from r8–r10 to r13–r15 | source r7/r11; destination r12/r16; unique anchors; no M2 overlap | Default |
| C16 | M2 across r19–r20 | r18 / r21; duration-driven end | Default; Audio offline / zero safe |
| C17a | r15 compatible two-sided edit | r14 / r16 | Default |
| C17b | r15 incompatible anchor/geometry edits | r14 / r16 | #123 only; S05 reuses C17a Blocked presentation |
| I01 | r9 → r10 across heading | r8 / r11; both affected rows have visuals | Blocked |
| I02 | covering visual on r8 | r7 / r9; dormant lower alternatives | Default |
| I03 | fulfilled request in r17 | r16 / r18 | Default |
| I04 | unsupported addition after r22 | r21 / document end | Default |
| I05 | r4 timeline-bounds visual | r3 / r5 | Default |
| I06 | preserved clip in r6 | r5 / r7 | Fits; Ending review; Ambiguous; Collision |
| I07 | reconciliation lifecycle | reference r11 | Checking; unavailable; error; current; partial; unbounded; Resolve changed again |
| I08 | C03b carry-over | r12 / r14 | Deferred last review |
| O01a | first creation | complete corpus | No linked timeline |
| O01b | already current | complete corpus | Up to date |
| O02 | C03b carry-over + C01 new | non-overlapping entries | Skipped last update |
| O03 | r15 changes after review opens | r14 / r16 | Newer script version |
| O04a | narration rewrite in r15 | r14 / r16 | Default |
| O04b | rewrite touches r13 Graphic anchor | r12 / r14 | Unique remap; ambiguous remap blocks |
| O05 | narrated r21 inserted after r18 | r18 / r19; before `Closing the Loop` | Blocked · recording needed; placeholder audio → Selected |
| O06 | r14 splits into two | r13 / r15 | Default |
| O07a | marker removed before r3 | r2 / r3 | Default |
| O07b | marker renamed before r19 | r18 / r19 | Default |
| O07c | marker moved from r18 to r19 | r17/r18 and r18/r19; section context | Default |
| O08 | Resolve capability | complete corpus | Ready; closed; unsupported; missing link; Free; unbounded |
| O09 | CR-O frozen run | C09, C05, C01 selected; C16 Blocked | Partial failure; Retry; complete; Resolve-only preservation |
| O10 | render lifecycle | continuous section range | Waiting; resume; render retry; cancel |

The current 22-row bank supplies every required geometry. Any later mismatch
may be resolved only by adding word-for-word accepted S03 content with stable
new row IDs and explicit Producer acceptance; narration is never invented to
make a scenario fit.

## Shared scenario content

### C01 · SHARED — On Camera framing

- Rows: r17, **r18**, r19.
- Title: `On Camera framing`.
- Older: r18 `On Camera · Wide`.
- Newer: r18 `On Camera · Tight`.
- Summary: `On Camera framing changes from Wide to Tight`.
- #123 consequence: `Script records Tight framing on Reconcile.`
- S05 consequence: `Planned for v4: set this row to On Camera · Tight. Verification is still required.`
- Only `Wide`/`Tight` receives change emphasis; narration stays neutral.

### C02 · SHARED — Words cut + Footage endpoint

- Rows: r7, **r8**, r9.
- Title: `Narration cut + Footage endpoint`.
- Older endpoint: Footage 3 ends on `beneath the surface.`.
- Cut words: `beneath the surface`.
- Changed narration sentence:
  `That view holds until the top of the probe disappears.`
- Newer endpoint: Footage 3 ends on `disappears.`.
- Visual: `Footage 3 · sensor-housing-cu_0812.mov`.
- Summary: `3 narration words cut · affected Footage endpoint moves`.
- #123 evidence note:
  `Verified program audio omits “beneath the surface”. A picture trim alone is not deletion evidence.`
- #123 consequence:
  `Script removes “beneath the surface” and records the verified Footage endpoint on Reconcile.`
- S05 consequence:
  `Planned for v4: cut 3 narration words and move the affected Footage endpoint. Verification is still required.`
- Visual-offline state:
  `Media offline locally — not evidence of removal.`
- #123 Visual-offline effect:
  `This change remains decidable from verified timeline structure. Offline local media is not deletion evidence.`
- Unverified-program-audio effect:
  `Blocked — narration removal is not verified. A picture trim alone is not deletion evidence.`
- S05 Visual-offline reason:
  `Blocked — VERA needs this Footage to place and verify the moved endpoint.`

### C03 · SHARED — Visual range changes

Two cases share one scenario.

**C03a — Footage ends earlier**

- Rows: r5, **r6**, r7.
- Older end: `just below it.`
- Newer end: `the sensor opening`.
- Return point: the `↩ On Camera resumes` strip moves to `sits`.
- Summary: `Footage 1 ends earlier`.
- #123 consequence: `Script records the earlier endpoint; presenter picture resumes on “sits”.`
- S05 consequence: `Planned for v4: end Footage 1 on “the sensor opening” and resume presenter picture on “sits”. Verification is still required.`

**C03b — Graphic starts later**

- Rows: r12, **r13**, r14.
- Older start: `the video attracted`.
- Newer start: `50,000 views.`
- Summary: `Graphic 2 starts later`.
- #123 consequence: `Script records Graphic 2 beginning on “50,000 views.”; its end is unchanged.`
- S05 consequence: `Planned for v4: begin Graphic 2 on “50,000 views.” and keep its end. Verification is still required.`

In both cases only the changed boundary/length is annotated. Existing words
and newly revealed base picture remain neutral.

### C04 · SHARED — Visual-only row added

- Rows: r3, **r4**, r5.
- Title: `Marker buoy · visual-only row`.
- Summary: `Visual-only row added between “The tide has just turned…” and “Down at the piling…”`.
- Older: r3 followed by r5; r4 is absent.
- Newer: r4 is present between r3 and r5.
- Added row: r4 exactly.
- #123 script-side marker: `No equivalent row in the current script.`
- S05 Resolve-side marker: `No equivalent row in current Resolve.`
- #123 consequence: `Script gains the visual-only marker-buoy row on Reconcile.`
- S05 consequence: `Planned for v4: add the marker-buoy Footage row. Verification is still required.`

### C05 · SHARED — Three rows removed

- Rows: r10, **r11–r13**, r14.
- Title: `3 rows removed`.
- Older: r10, r11–r13, r14.
- Newer: r10 followed directly by r14.
- Summary: `Status page, archival photograph and maintenance-video page removed · one atomic change`.
- Header: `REMOVED · 3 ROWS`.
- Relationship: `3 rows removed · one update`.
- #123 consequence: `Script removes these 3 verified rows on Reconcile.`
- S05 consequence: `Planned for v4: remove these 3 rows. Verification is still required.`
- Skipped S05 note: `Kept — skipped.`

### C06 · SHARED — Three-row passage moved

- Moved rows: r11–r13.
- Source neighbors: r10 before; r14 after.
- Destination neighbors: r16 before; r17 after.
- Older: the passage is between r10 and r14.
- Newer: the passage is between r16 and r17.
- Title: `3-row passage moved`.
- Summary: `Status page, archival photograph and maintenance-video page move later in “Following the Evidence”`.
- Relationship: `Same section · three rows apart · one move`.
- Source header: `Moved from here`.
- Destination header: `Moved here`.
- #123 consequence: `Script moves the 3 rows to the Resolve location on Reconcile.`
- S05 consequence: `Planned for v4: move the 3 rows together. Verification is still required.`
- Interiors of moved rows remain neutral.

### C07 · SHARED — One row, several changes

- Changed row: r5.
- Source neighbors: r4 and r6.
- Destination: between r7 and r8.
- Title: `Row moved + Footage cut point moves`.
- Changes:
  1. r5 moves from between r4/r6 to between r7/r8.
  2. The visual cut point moves: `Footage 1 · sensor-housing-cu_0812.mov`
     ends on `around the opening,`, and Footage 2 starts on `which changes`,
     instead of Footage 1 ending on `the probe responds.` and Footage 2
     starting on `A ferry wake`.
- Older: r5 is between r4/r6 and Footage 1 ends on `the probe responds.`.
- Newer: r5 is between r7/r8; Footage 1 ends on `around the opening,`; Footage
  2 starts on `which changes`. The row keeps contiguous picture coverage.
- Relationship: `Same section · two rows apart · one move`.
- Summary: `Row moved · Footage cut point moves`.
- S05 state: `Row updated · 2 edits`.
- S05 consequence: `Planned for v4: move the row and move the Footage cut point as one indivisible update. Verification is still required.`
- #123 axis labels: `Row location`; `Footage cut point`.
- #123 presents two independent decisions because the row move and Footage
  cut-point move are independently executable and verifiable. Either may be accepted,
  kept or deferred without making the other unsafe. This follows accepted
  #123 change 10; it is deliberately different from S05's indivisible
  producer-authored row update.

### C08 · SHARED — Same-anchor replacement

- Rows: r2, **r3**, r4.
- Title: `Footage replaced`.
- Existing card: `Footage · harbour-mouth-wide_0812.mov · Quiet sound`.
- Replacement card: `Footage · gull-liftoff_0731.mov · Quiet sound`.
- Older: `harbour-mouth-wide_0812.mov`.
- Newer: `gull-liftoff_0731.mov`.
- Range: complete r3 in both versions.
- Summary: `Footage replaced over the same narration range`.
- #123 consequence: `Script records the replacement Footage card; narration and anchors stay unchanged.`
- S05 consequence: `Planned for v4: replace the Footage card while keeping narration and anchors. Verification is still required.`

### C09 · SHARED — Opaque cutaway

- Rows: r4, **r5**, r6.
- Title: `Opaque cutaway inserted`.
- Base: `Footage 1 · sensor-housing-cu_0812.mov`.
- Cutaway: `Footage 2 · salt-crystal-cu_0915.mov · No sound` (**NEW**).
- Cutaway range: `Salt and algae build up around the opening,`.
- Older: Footage 1 plays continuously; no cutaway is present.
- Newer: Footage 2 interrupts Footage 1 for the named range, then Footage 1 resumes.
- After insertion, the accepted `channel-light-dusk_0809.mov` item becomes
  Footage 3. Routine ordinal renumbering is never annotated as a change.
- Return strip: `↩ Footage 1 resumes` with the
  `sensor-housing-cu_0812.mov` mini thumbnail.
- Summary: `Opaque Footage cutaway added within existing Footage 1`.
- #123 consequence: `Script records the cutaway and the Footage 1 return.`
- S05 consequence: `Planned for v4: add the cutaway while keeping Footage 1 underneath and resuming it. Verification is still required.`

### C10 · SHARED — Transparent Graphic

- Rows: r1, **r2**, r3.
- Title: `Transparent lower third`.
- Graphic: `Graphic 1 · Wren Alvarez · Harbor Reporter`.
- Range: `I'm Wren Alvarez` through `actually doing.`
- Older: continuous On Camera with no lower third.
- Newer: the transparent Graphic overlays the named range.
- Summary: `Transparent Graphic added over continuous On Camera`.
- #123 consequence: `Script records the lower third over the continuous presenter picture.`
- S05 consequence: `Planned for v4: add the lower third while keeping the presenter visible underneath. Verification is still required.`
- Inspection: dashed card outline at rest; dashed narration underline in the
  accepted Graphic shade only while the card or `│1` / `1│` mark has
  hover/focus.

### C11 · SHARED — One visual removed

- Rows: r6, **r7**, r8.
- Title: `Footage 1 removed`.
- Removed visual: r7 `Footage 1 · channel-light-dusk_0809.mov`.
- Unchanged sibling: `On Camera · Tight`.
- Older: the On Camera base and Footage 1 cutaway are present.
- Newer: On Camera remains continuous and Footage 1 is absent.
- Summary: `One Footage item removed · narration and On Camera remain`.
- #123 consequence: `Script removes Footage 1 only; narration and On Camera · Tight remain.`
- S05 consequence: `Planned for v4: remove Footage 1 only and keep On Camera · Tight continuous. Verification is still required.`

### C12 · SHARED — Two rows merged beneath a Graphic

- Rows: r7, **r8 and r9**, r10.
- Title: `2 rows merged beneath a Graphic`.
- Older header: `2 ROWS`.
- Newer header: `MERGED ROW`.
- Relationship: `2 rows → 1 · one merge`.
- Older: r8 and r9 are separate rows.
- Newer: their narration and visual sequence occupy one row.
- Merged narration is r8 followed by one space followed by r9, with no word
  or punctuation change.
- Retain r8's `Footage 1`, `Graphic 2`, `Footage 3` and `Footage 4` sequence.
  The bridging overlay is `Graphic 5`; the original r9 base becomes
  `Footage 6 · fogged-lens_0805.mov` over the original r9 words.
- Bridging transparent Graphic:
  `Graphic 5 · SENSOR RESPONSE · ONE EVENT`.
- Graphic range: `Taken together` in r8 through `change in the data.` in r9.
- Summary: `Row break removed · bridging Graphic spans both source rows`.
- #123 consequence: `Script records one merged row, preserving both source visual sequences and the bridging Graphic.`
- S05 consequence: `Planned for v4: remove one row boundary, preserve both source visual sequences and add the bridging Graphic. Verification is still required.`
- Offline Graphic state:
  `SENSOR RESPONSE · ONE EVENT is offline locally — this atomic merge is blocked. Existing v3 Footage remains evidence. Other updates remain available.`
- The new bridging Graphic's missing media blocks the complete atomic merge
  because VERA must place and verify it with the row-boundary change. Existing
  v3 Footage stays present and is never treated as deletion evidence. Unrelated
  updates remain selectable.
- This is the density-stress host: use its complete long title and maximum
  connector set at `1024 × 768` for the connector-routing comparison.

### C13 · SHARED — Two clips trade rows

- Rows: r5, **r6 and r7**, r8.
- Row A: r6, with `Footage 1 · sensor-housing-cu_0812.mov`.
- Row B: r7, with `Footage 1 · channel-light-dusk_0809.mov`.
- Older: each clip is paired with its original row.
- Newer: the clips exchange rows while the rows stay fixed.
- Resolve exchanges the two cutaway clips; both narration rows, cutaway ranges,
  presenter bases and row order remain fixed.
- Title: `2 Footage clips trade rows`.
- Summary: `Clip-to-row pairings change · words stay in place`.
- #123 consequence: `Script records the two changed clip-to-row pairings as one reconciliation change.`
- S05 consequence: `Planned for v4: swap both Footage assignments as one update. Verification is still required.`

### C14 · SHARED — Camera state

- Rows: r20, **r21**, r22.
- Title: `Voice Over → On Camera`.
- Older: `Voice Over · Visual Undefined`.
- Newer: `On Camera · Wide`.
- Narration: r21, unchanged.
- Summary: `Presenter becomes visible · narration unchanged`.
- #123 evidence note: `Presenter visibility verified in program video.`
- Ambiguous evidence state: `Presenter visibility cannot be verified.`
- Blocked consequence: `No script change until presenter visibility is verified.`
- #123 consequence: `Script records this narration as On Camera · Wide.`
- S05 consequence: `Planned for v4: show the presenter On Camera · Wide for this narration. Verification is still required.`

### C15 · SHARED — Audio structure

- Title: `M1 · Harbor Tide Bed`.
- **C15a · Added:** absent in the older state; the newer span starts on `From the western`
  in r8 and ends on `back to the footage.` in r10.
- **C15b · Removed:** the same r8–r10 span exists in the older state and is
  absent in the newer state.
- **C15c · Moved across sections:** the older span is r8–r10; the newer span
  starts on `The agency posted` in r13 and ends on `The tide did not.` in r15.
  Source neighbors are r7/r11; destination neighbors are r12/r16. Both anchors
  are unique, and the newer span ends before M2 begins.
- Summary: `M1 · Harbor Tide Bed · one document-wide audio item`.
- Move relationship: `One bed · two locations · one move`.
- #123 consequence: `Script records the chosen M1 structure without changing row structure.`
- S05 consequence: `Planned for v4: apply the selected M1 structure without changing row structure. Verification is still required.`

### C16 · SHARED — Audio duration

- Rows: r19–r20.
- Title: `M2 · Harbor Lights Theme`.
- Start: `The lesson` in r19.
- Older source selection: `0:04.0–0:17.0`; play duration `13.0s`.
- Newer source selection: `0:04.0–0:20.0`; play duration `16.0s`.
- Fade: unchanged at the accepted `3.0s`.
- Older end: `Ends by duration · ~3.9s into the ending Placeholder`.
- Newer end: `Ends by duration · ~6.9s into the ending Placeholder`.
- Detail: `No out-word`.
- Summary: `M2 duration changes · audio-only update is valid`.
- S05 action summary: `Audio-only update · no picture changes`.
- #123 consequence: `Script records the 16.0s M2 duration and keeps its start and 3.0s fade.`
- S05 consequence: `Planned for v4: extend M2 to 16.0s while keeping its start and 3.0s fade. Verification is still required.`
- Audio-offline state:
  `Audio offline locally — not evidence of removal. M2's identity, start and settings remain known.`
- #123 Audio-offline effect:
  `This duration change remains decidable from verified timeline settings. Offline local audio is not deletion evidence.`
- S05 Audio-offline reason:
  `Blocked — VERA needs this audio to place and verify the new duration.`
- In the isolated audio-only review, Audio offline makes C16 Blocked, leaves
  zero safe updates and disables `Update timeline`.

### C17 · SHARED — Same row changed on both sides

**C17a — Compatible changes**

- Rows: r14, **r15**, r16.
- Common ancestor: accepted S03 r15 exactly, including `slow, then sudden`,
  transparent Graphic 1 and full-frame Graphic 2.
- Current script phrase:
  `The keeper described the change in words that are easier to remember than the graph.`
- Current script otherwise retains the accepted narration and both Graphics.
- Current Resolve retains the accepted narration and both Graphics, but ends
  Graphic 1 on `all at once.` instead of `the recorded signal.`.
- Resolve surface label: `Current Resolve · edited since v3`.
- Title: `Script and Resolve changed the same row`.
- Summary: `Script rewrote words inside Graphic 1's range · Resolve ends Graphic 1 earlier`.
- #123 compatible choice: `Combine both changes`.
- #123 combined consequence:
  `Script keeps its narration rewrite and records Graphic 1's earlier end on Reconcile.`
- S05 state: `Blocked`.
- S05 reason: `Resolve changed a Graphic range that overlaps this script rewrite.`
- S05 route: `Review Resolve changes`.
- S05 consequence:
  `Resolve stays unchanged — blocked. Reconcile this row before updating the timeline.`

**C17b — Incompatible changes**

- Rows and common baseline: C17a.
- Current script phrase:
  `She called it “gradual, then abrupt,” because the water moved steadily while the reported value jumped all at once.`
- Verified current Resolve program audio retains the accepted narration, while
  Resolve retimes Graphic 1 to begin on the accepted phrase
  `slow, then sudden`.
- Title: `Script rewrite conflicts with Resolve Graphic timing`.
- Summary: `Script replaced Graphic 1's anchor words · Resolve retimed Graphic 1 to the old phrase`.
- #123 choices: `Accept Resolve`; `Keep current script`; `Defer`.
- #123 consequence: `Choose the verified Resolve words and timing or keep the script rewrite; the two states cannot be combined safely.`
- S05 does not repeat this case because it has the same Blocked presentation
  and reconciliation route as C17a.

## #123-only scenario content

### I01 · #123 ONLY — Visual crosses a heading

- Rows: r9, section heading `Following the Evidence`, r10.
- Title: `Visual across heading`.
- Added Resolve visual: `Footage · gauge-screen-flatline_0814.mov · Quiet sound` (**NEW**).
- Older Script: no visual crosses the heading.
- Newer Resolve: the added visual spans the named range across the heading.
- Start: `The shot ends before we can see` in r9.
- End: `what the sensor reported at the piling.` in r10.
- Summary: `1 visual crosses the “Following the Evidence” heading`.
- State: `Blocked`.
- Reason: `One script visual cannot cross a section heading.`
- Consequence:
  `No script change. Resolve keeps the visual until its section boundary is reconciled.`

### I02 · #123 ONLY — Dormant alternatives

- Row: r8.
- Added opaque top visual:
  `Footage · wake-overview_0918.mov · Quiet sound`, complete row (**NEW**).
- Older Script: r8 contains its accepted visual stack without the covering
  Footage.
- Newer Resolve: the opaque Footage covers the row while the lower alternatives
  remain dormant and preserved.
- Hidden alternatives: r8 Footage 1, Footage 3, Footage 4 and Graphic 2.
- Title: `Covering visual + dormant alternatives`.
- Summary: `One opaque visual covers the existing row stack`.
- Dormant label: `Dormant · hidden in Resolve · preserved`.
- Accept consequence:
  `Script shows wake-overview_0918.mov; four hidden alternatives remain preserved for restoration.`
- Keep consequence:
  `Script stays unchanged · queued for Resolve: remove wake-overview_0918.mov.`

### I03 · #123 ONLY — Request fulfilled, request retained

- Rows: r16, **r17**, r18.
- Title: `Need to Find fulfilled?`.
- Request: `Technician cleaning algae from the sensor housing.`
- Older Script: the ranged Need to Find request is open.
- Newer Resolve: the named Footage fills the range; request disposition still
  requires a decision.
- Resolve Footage:
  `Footage · housing-waterline_0911.mov · Quiet sound` (**NEW**).
- Range: row start through `reading changed.`
- Summary: `Resolve Footage fills the Need to Find range · research candidate`.
- Choices: `Accept Resolve`; `Keep current script`;
  `Use clip, keep request open`; `Defer`.
- Hybrid consequence:
  `Script uses housing-waterline_0911.mov; the Need to Find request stays open as a non-rendered follow-up.`

### I04 · #123 ONLY — Preserved as-is addition

- Rows: r21, **r22**, document end.
- Title: `Unsupported Resolve addition`.
- Added item: `Fusion title · Harbor Authority Live Readout`.
- Older Script: no representable item exists after the final working row.
- Newer Resolve: the Fusion title exists at the named timeline bounds.
- Timeline bounds: `01:03:14:08–01:03:20:19`.
- Optional name: `Harbor Authority Live Readout`.
- Summary: `Resolve item cannot be represented as an ordinary script visual`.
- Accept label: `Preserve as-is`.
- Accepted badge: `Preserved as-is`.
- Consequence:
  `Script records a locked preserved item with its Resolve identity and timeline bounds.`

### I05 · #123 ONLY — Standalone timeline-bounds visual

- Rows: r3, **r4**, r5.
- Title: `Standalone Footage · timeline bounds only`.
- Visual: r4 `horizon-steady_0805.mov`.
- Older Script: the visual-only intent has no trustworthy spoken anchor.
- Newer Resolve: the Footage placement is evidenced by timeline bounds only.
- Bounds: `01:00:18:12–01:00:27:22`.
- Summary: `No trustworthy spoken anchor · timeline placement is preserved`.
- Consequence:
  `Script records the visual-only row with explicit timeline bounds; no narration anchor is invented.`

### I06 · #123 ONLY — Preserved clip re-anchoring

- Row: r6.
- Title: `Preserved Footage follows a verified word`.
- Visual: `sensor-housing-cu_0812.mov`.
- Older Script: the preserved Footage uses its authored range.
- Newer Resolve: the preserved clip begins on the verified word and may fit,
  require ending review, be ambiguous or collide.
- Verified start: `The band is`.
- Safe-fit state: `Fits before “When we return” · no marker needed`.
- Review state: `Ending fit needs review`.
- Marker: `Preserved media outpoint`.
- Ambiguous-state anchor: `band`, which occurs twice in r6.
- Ambiguous state: `Start word “band” occurs more than once`.
- Collision state: `Preserved outpoint overlaps the next visual`.
- Blocked consequence:
  `No script change until the anchor or resulting outpoint can be verified.`

### I07 · #123 ONLY — Reconciliation lifecycle

- Reference row: r11.
- Title: `Resolve changes`.
- Older: the last trusted Script/Resolve snapshot.
- Newer: the current Resolve observation, or an explicit unavailable,
  unbounded or changed-again state when no trustworthy newer snapshot exists.
- Controlled states and exact copy:
  - `Checking the managed Resolve timeline…`
  - `Resolve is unavailable on this computer.`
  - `VERA couldn't read the managed timeline. Try again.`
  - `The script and managed timeline already match.`
  - `Reconciled 4 changes · 1 deferred · 1 blocked · script still differs from Resolve.`
  - `VERA can't bound the conflict. Review the affected Resolve changes before reconciling the script.`
  - `Resolve changed again while this review was open. Refresh before reconciling.`
- Actions: `Try again`; `Open Resolve`; `Review Resolve changes`.
- Concurrent-change action: `Refresh Resolve changes`.
- A refresh replaces stale evidence; it never silently submits decisions against
  a newer Resolve state.

### I08 · #123 ONLY — Deferred last review

- Geometry: C03b on r13.
- Older Script: Graphic 2 uses the older C03b start.
- Newer Resolve: Graphic 2 starts later; the previous review deferred it.
- Title: `Graphic range deferred last review`.
- Badge: `Deferred last review`.
- Summary: `Graphic 2 still starts later in Resolve`.
- Current decision: `Undecided`.
- Consequence:
  `Choose an outcome now or defer it again. Resolve and the script still differ.`

## S05-only scenario content

### O01 · S05 ONLY — Entry states

**O01a — First creation**

- Title: `Create Resolve timeline`.
- Status: `No linked timeline yet`.
- Older Resolve state: no linked timeline.
- Newer Script state: the complete current corpus to create as v1.
- Body:
  `Create a Resolve timeline from the current Harbor Lights script.`
- Actions: `Create timeline`; `Create and render`.
- Subline: `Creates v1 from the current script.`
- No change rail is shown.

**O01b — Already current**

- Title: `Resolve timeline`.
- Status: `Up to date`.
- Older Resolve v3 and newer Script are identical; this case intentionally has
  no change geometry.
- Body: `Timeline version 3 already matches the current script.`
- No Update action or empty change rail is shown.

### O02 · S05 ONLY — Second update after a skip

- Outstanding item: C03b, badge `Skipped last update`.
- New item: C01.
- Older Resolve v4: retains the pre-C03b range and pre-C01 framing.
- Resolve surface label: `Current Resolve · v4`.
- Newer Script: still contains C03b and now also contains C01.
- Title: `2 updates since timeline v4`.
- Summary: `1 skipped last update · 1 new script change`.
- Applied items from the previous update do not reappear.
- Consequence:
  `If the selected work verifies, creates v5. The skipped Graphic range remains outstanding unless selected.`

### O03 · S05 ONLY — Reviewed row changed again

- Row: r15.
- Older Resolve v3 phrase: `in a phrase`.
- Reviewed script phrase: `in words`.
- Newer synchronized script phrase: `in plain words`.
- Badge: `Newer script version available`.
- Action: `Update row`.
- Warning:
  `This row has a newer script version. Continuing will use the version shown in this review.`
- Timeline-only result:
  `Built from the version you reviewed. 1 newer script change was not included.`
- Timeline-and-render result:
  `Rendered from the version you reviewed. 1 newer script change was not included.`

### O04 · S05 ONLY — Narration rewrite

**O04a — Rewrite does not touch an anchor**

- Rows: r14, **r15**, r16.
- Title: `Narration rewritten`.
- Older Resolve v3 phrase:
  `The keeper described the change in a phrase that is easier to remember than the graph.`
- Newer script phrase:
  `The keeper described the change in words that are easier to remember than the graph.`
- Production content is unchanged.
- Summary: `Quotation updated · production content unchanged`.
- Consequence:
  `Planned for v4: replace the narration phrase and keep the existing visual instructions. Verification is still required.`

**O04b — Rewrite touches a visual anchor**

- Rows: r12, **r13**, r14.
- Older Resolve v3 sentence:
  `In its first two months, the video attracted more than 50,000 views.`
- Newer script sentence:
  `In its first two months, more than 50,000 people watched the video.`
- Graphic 2 older range: `the video attracted` through `50,000 views.`
- Current uniquely mapped range: `more than 50,000 people watched the video.`
- Remap rule: a range remaps only when both ends remain surviving clause
  boundaries and the highlight word `50,000` survives inside them.
- Summary: `Narration rewrite changes Graphic 2's anchor words · range uniquely remapped`.
- Safe consequence:
  `Planned for v4: replace the narration words and keep Graphic 2 on its uniquely matched phrase. Verification is still required.`
- Ambiguous state: `Graphic 2's range cannot be remapped uniquely.`
- Ambiguous reason:
  `Blocked — both range boundaries must map to surviving clause boundaries and retain the “50,000” highlight.`
- Blocked consequence:
  `Resolve stays unchanged — blocked. Choose a unique Graphic 2 anchor before updating the timeline.`

### O05 · S05 ONLY — Narrated row added

- Rows: r18, **r21**, section heading `Closing the Loop`, r19.
- Title: `Narrated row added`.
- Added narration: r21 exactly.
- Older: r18 is followed by `Closing the Loop` and r19.
- Newer: r21 is inserted after r18, at the end of `Following the Evidence`,
  before `Closing the Loop`; its real row neighbors are r18 and r19.
- At r21's canonical row-bank position after r20, both states omit r21: r20
  is followed directly by r22. The fixture must never render r21 twice.
- Visual state: `Visual Undefined`.
- Starting state: `Blocked · Narration recording needed`.
- Fallback action: `Use placeholder audio`.
- State after fallback: `Selected`.
- Summary: `New narrated row · recording or placeholder audio required`.
- Consequence:
  `Planned for v4: add the narrated row at the end of Following the Evidence. Verification is still required.`
- This fixture follows one path only: it starts Blocked, the producer chooses
  `Use placeholder audio`, and the item becomes Selected. M2 and the ending
  Placeholder remain untouched.

### O06 · S05 ONLY — One row split into two

- Source row: r14.
- Older Resolve v3: one r14 row.
- Newer Script: the same words and visual ranges are divided into two rows.
- Title: `1 row split into 2`.
- First result row:
  `An archival photograph shows the original sensor bracket before the current housing was installed. A supplied screenshot of the maintenance bulletin records the date the replacement was completed.`
- Second result row:
  `Next, a screen recording of the monitoring dashboard shows the reading arriving in real time. Together, these sources connect the physical repair to the digital record. None of them changes the conclusion, but each explains a different part of the chain.`
- Preserve all three visual ranges with the corresponding sentences.
- Header: `SPLIT IN SCRIPT · 1 ROW BECOMES 2`.
- Summary: `Row boundary added · words and punctuation unchanged`.
- Consequence: `Planned for v4: replace one timeline row with two rows as one atomic update. Verification is still required.`

### O07 · S05 ONLY — Section markers

Three named cases share one scenario. First-timeline creation in O01 already
proves marker addition.

| Case | Baseline | Current script | Exact consequence |
|---|---|---|---|
| O07a · Removed | `Why the Signal Changes` before `The tide has just turned…` | none | `Planned for v4: remove the Why the Signal Changes marker. Verification is still required.` |
| O07b · Renamed | `Conclusion` before `The strange signal did not come…` | `Closing the Loop` | `Planned for v4: rename the Resolve marker from Conclusion to Closing the Loop. Verification is still required.` |
| O07c · Moved | `Closing the Loop` before `The keeper records every reading…` | `Closing the Loop` before `The strange signal did not come…` | `Planned for v4: move the marker one row later; duration remains zero. Verification is still required.` |

Title: `Section markers`. Marker label: `Zero-duration Resolve marker`.

### O08 · S05 ONLY — Resolve capability

- Title: `Resolve connection`.
- Older: capability has not yet been established for this update attempt.
- Newer: one named observed capability state below; no content state is
  inferred when the observation is unavailable or unbounded.
- States and actions:
  - `Resolve Studio connected · ready` → `Update timeline`.
  - `Resolve is closed or unreachable.` → `Open Resolve`; `Try again`.
  - `This Resolve version isn't supported.` → `View supported versions`.
  - `The linked timeline can't be found.` → `Find existing timeline`;
    `Create a fresh timeline`.
  - `Resolve Free · prepare a timeline package for manual import.` →
    `Prepare timeline package`.
  - `VERA can't bound the conflict. Reconcile Resolve changes before updating the timeline.` →
    `Review Resolve changes`.

### O09 · S05 ONLY — Partial update and Retry

- `CR-O` preflight: C09, C05 and C01 are safe and selected by default. C16 is
  `Blocked` by `Audio offline` and `Select all safe` cannot select it.
- Older: current Resolve timeline v3 plus its Resolve-only I02/I04 material.
  Those items are earlier, non-overlapping Resolve edits; S05 shows no outbound
  update for either one.
- Newer Script: contains C01, C05, C09 and C16. C16 is excluded from the
  submitted plan because its required audio is offline.
- Frozen submitted plan in document order: C09, C05 and C01 only.
- Title: `Update incomplete`.
- Results follow document order and stop at the first failure:
  - C09: `Verified in v4`.
  - C05: `Attempted — not verified`.
  - C01: `Not attempted`.
  - C16: `Blocked · not submitted`.
- Heading:
  `Update incomplete. Timeline v3 remains current. Baseline not updated.`
- Count cells: `1 verified`; `1 attempted — not verified`;
  `1 not attempted`; `1 blocked · not submitted`.
- Retry body:
  `Retry resumes this frozen v4 attempt from its last verified artifact. It does not create another timeline or change the submitted plan.`
- Action: `Retry failed update`.
- Retry plan: the same frozen C09/C05/C01 plan; C09 is not duplicated, C05
  resumes from the last verified artifact and C01 follows only after C05
  verifies.
- Completion:
  `All 3 selected updates verified in v4. Timeline v4 is now current. 1 blocked update remains outstanding.`
- Preservation proof after verification:
  `2 Resolve-only items verified present in v4.`
  This covers I02's dormant alternatives and I04's `Harbor Authority Live
  Readout`, with the same identities and bounds.

### O10 · S05 ONLY — Render settings and lifecycle

- Title: `Render settings`.
- Older: verified timeline state with no completed render for this request.
- Newer: the requested render operation and, only after verification, its
  completed render result.
- Range choices: `Complete timeline`; `Continuous section range`.
- From: `Why the Signal Changes`.
- Through: `Following the Evidence`.
- Preset labels: `Last used`; `Saved preset`.
- Fields: `Format`; `Resolution`; `Quality`; `Destination`; `Filename`.
- Final action: `Update timeline and render`.
- Lifecycle:
  - `Preparing timeline…`
  - `Duplicating timeline v3…`
  - `Applying selected updates…`
  - `Verifying timeline v4…`
  - `Rendering…`
  - `Verifying render…`
  - `Timeline v4 and render complete.`
- Resume copy:
  `Resume the existing operation. Completed timeline work will not run again.`
- Render-only retry:
  `Timeline v4 is verified. Retry the render without rebuilding the timeline.`
- Cancellation:
  `Rendering cancelled. Timeline v4 remains verified.`

## Cross-artifact copy rule

For every `C` scenario, the following must be word-for-word identical in both
successors:

- harness ID and scenario title;
- base narration and direction text;
- visual names, filenames and anchor phrases;
- before/after neighbors;
- structural header and relationship copy; and
- descriptive summary of what physically changed.

Only these may differ:

- #123 decisions and reconciliation consequences;
- S05 selection, execution and verification language; and
- direction words required for literal source truth.

## Review checklist before construction

1. Read every row and scenario aloud for story continuity.
2. Confirm every structural scenario has real before/after neighbors.
3. Confirm each `C` scenario can use the exact same registry entry in both
   artifacts.
4. Confirm every controlled state in the allocation matrix has the named
   scope, and that offline media never becomes deletion evidence.
5. Confirm every accepted #123 and S05 case appears in the roadmap crosswalk.
6. Resolve any provisional media title before it becomes fixture data.
7. Have Claude challenge unnatural row allocations, duplicated mechanics and
   copy that implies more execution certainty than the prototype supports.
8. Obtain Producer acceptance of this literal content specification before
   building the shared foundation.
