# Claude brief: finish S05 update semantics and move approval behavior

Continue editing the existing **Script to Timeline — Prompter Runtime and Suite Navigation S04–S06** design artifact. Work only on S05. Preserve the current marked-up-script visual design, the approved S04 experience, and the complete deletion of S06.

Use your own product-design and interaction-design judgment within the decisions below. **Before making any edits, stop and ask Matthew focused questions about the design. Wait for his answers before proceeding.** Ask about any decision whose behavior, terminology, count semantics, warning prominence, or presentation could benefit from clarification; include your recommended answer where useful. This consultation is required even if you believe the brief is otherwise clear. Do not start editing in the same response as the questions, and do not guess through a material product decision. After Matthew answers, implement, exercise, and verify the result rather than merely describing it. This remains a design simulation and is not Producer acceptance.

## Keep the current design direction

Preserve the current strengths of S05:

- the page name **Resolve timeline**;
- the comprehensive marked-up-script review;
- recognizable narration and production columns;
- green additions, red removals, inline before/after changes, and explicit non-color **Added / Removed / Changed** labels;
- row-level checkboxes in the dark left gutter;
- unchanged context revealed one row at a time, with Hide and gap-merging behavior;
- skipped rows dim without adding a chip or changing row height;
- the sticky Create/Update/Prepare action;
- the current Resolve closed, connection failure, Resolve Free, unsupported-version, and broken-link recovery concepts;
- the explicit guarantee that an update creates a new timeline version beside the current version and never overwrites it; and
- both 1280 × 800 and 1024 × 768 layouts.

Do not restore any inbound **Changes in Resolve** review. Do not redesign S01–S03 here.

## 1. Advance the comparison baseline after every successful update

The current **Second update after skipping** scenario is logically wrong because it says version 3 was created, but then presents all changes from the version-2 update again.

After VERA successfully creates a new timeline version, that version becomes the outbound comparison baseline for the next update. A later update must show only:

- changes that the user skipped in the previous update and therefore remain unapplied to the timeline; and
- new script changes made after that timeline version was created.

Already applied changes must not reappear. Do not imply that VERA will apply the same additions, removals, rewrites, visual treatments, or move a second time.

Revise the scenario as follows:

- Version 2 was the starting timeline.
- The user created version 3 and applied every original logical row change except the removal of `[VO] This frozen screenshot came from an earlier review.` and its uploaded screenshot.
- After version 3 was created, the user changed `[VO] A final comparison confirms the pattern.` to `[VO] A final comparison confirms the repaired pattern.`; its production content is unchanged.
- The next update review therefore contains exactly two logical row changes, both selected by default:
  1. the previously skipped screenshot-row removal; and
  2. the new partial narration rewrite.
- The page, sticky action, confirmation, and result must all say **2 row changes selected; none skipped** initially.
- Creating the update produces version 4 beside version 3. Version 3 remains untouched.

Make the baseline understandable in ordinary language, for example **Changes since Timeline version 3 was created**. Do not expose implementation bookkeeping.

## 2. Keep approvals at row level; link only pure moves

Row-level approval remains the governing interaction. A user may have a reason to skip either affected row when a move is combined with other edits. Do not universally force all move representations into one atomic checkbox.

Use this conditional rule:

### Pure move

When the only change is that one otherwise-identical row moved from one script position to another:

- show the row in red at its old position and green at its new position;
- keep a checkbox beside both visible representations, preserving the row-level visual pattern;
- link the two checkboxes so they always share one state;
- toggling either checkbox toggles both representations;
- count the move as one logical row change everywhere;
- do not allow a half-move; and
- make the shared relationship clear in the accessible names and, if useful, concise visible text.

The existing chime example is a pure move: the narration and `demo-chime-v1` cue are identical at the old and new positions. Therefore its two checkboxes must be linked in the main **Connected · ready** scenario.

With the section-marker change restored below, the main scenario returns to **8 logical row changes selected; none skipped**, even though nine changed row representations are visible because the pure chime move appears twice.

### Move combined with other row edits

When the moved row also changes narration, media, cue, timing, framing, or other timeline-relevant content, the old-position removal and new-position insertion may be approved independently. Keep the checkboxes unlinked because each visible row-position operation may need a different decision.

Add or retain a dedicated prototype scenario that demonstrates this behavior with a concrete composite example:

- Old position: `[VO] A short chime marks the second reading.` with `Music/SFX cue demo-chime-v1`.
- New position: `[VO] A short bell marks the second reading.` with `Music/SFX cue demo-bell-v2`.
- The row has moved and its narration and cue have changed.

If exactly one side is selected, do not block the update. The user deliberately unchecked a row and may know what they are doing. Instead, show a prominent, non-color-only warning:

- beside the affected rows or immediately above the review;
- in the sticky action area; and
- in the confirmation.

State the actual consequence, not merely “half of the move is selected”:

- old removal skipped + new insertion included: both the old chime and new bell will exist in the new timeline version; or
- old removal included + new insertion skipped: the old chime will be removed and no replacement will be added.

The warning must remain advisory. The user may continue and create the new version.

When the pair is unlinked, count the old-position and new-position operations separately because they are independently approved row-level actions. Keep those counts consistent across the review header, section counts, sticky action, confirmation, and result.

## 3. Restore the section-marker change

Restore the marker row because section markers do affect the Resolve timeline:

- Previous timeline: `Section: Conclusion`.
- Current script: `Section: Closing`.
- Timeline consequence: **Rename the Resolve marker from Conclusion to Closing**.
- Present it as a **Changed** row in script order with inline red/green before-and-after treatment and its own checked-by-default row-level checkbox.

Retain the first-time Create timeline statement that VERA creates a marker for each section. The marker behavior and the restored rename row must now agree.

## 4. Remove hard script-revision language

The script is continuously saved to the cloud. Do not describe **Revision A** as a published, released, or manually saved script boundary.

- In the first-time flow, say VERA creates the timeline **from the current script**.
- In update flows, identify the comparison as the current script versus the last timeline version/baseline, such as **Changes since Timeline version 2 was created**.
- Timeline version numbers and dates are useful provenance and should remain.
- Do not add a “Save script,” “Publish revision,” “Release,” or “Latest saved script” concept.

Update harness metadata and accessible text as needed so visible and hidden labels do not continue asserting Revision A as the operative boundary.

## 5. Remove unexplained numeric deltas

Remove the unexplained right-edge values such as `+1`, `−1`, `−3`, and `+4`. They resemble developer notation and do not tell the user what is changing.

Do not replace them with another compact code. The row markup, media treatment, Added/Removed/Changed labels, and plain-language consequence should carry the meaning. If a quantity is genuinely necessary, spell it out in ordinary language, such as **1 image item removed**, and ensure the meaning is obvious without a legend.

## Main-scenario count after these corrections

The connected version-2 update contains the original eight logical changes:

1. operator narration rewrite;
2. housing-image motion change;
3. screenshot-row removal;
4. pure chime move, displayed twice but counted once and linked;
5. archive-capture row addition;
6. sensor-image row addition;
7. Conclusion → Closing marker rename; and
8. closing narration rewrite.

Initial count: **8 logical row changes selected; none skipped**.

## Verification before replying

Exercise and fix the completed artifact at both 1280 × 800 and 1024 × 768:

1. Confirm first-time Create timeline uses **current script**, contains no update-diff section, and truthfully mentions section markers.
2. Confirm the connected update contains all eight logical changes above, nine visual row representations, and consistent eight-change counts.
3. Toggle either pure-chime checkbox and verify both representations change together and the logical count decreases by one.
4. Exercise the composite move scenario with each half selected independently. Verify the correct prominent warning appears in the review, sticky action area, and confirmation, without blocking creation.
5. Complete the version-3 update with the screenshot removal skipped.
6. Open **Second update after skipping** and confirm that only the skipped screenshot removal and the newly written final-comparison narration appear—no already applied change returns.
7. Complete that update and confirm it creates version 4 beside untouched version 3 with consistent two-change counts.
8. Confirm all unexplained right-edge numeric deltas are gone from visible and accessible content.
9. Recheck Resolve closed, Resolve Free, unsupported-version, and broken-link states without restoring inbound Resolve-change claims.
10. Confirm S04 remains unchanged and no S06 tab, page, scenario, label, script, or dead interaction returns.

In your final response, name the artifact, summarize the baseline fix, describe the pure-versus-composite move behavior, report both viewport checks, and identify any remaining limitation. Do not mark issue #58 complete or imply Producer acceptance.
