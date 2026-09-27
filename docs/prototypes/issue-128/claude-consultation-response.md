# Claude consultation response — issue #128

Received 27 September 2026 in a fresh chat in the existing `VERA design
feedback` Claude Design project. Claude was explicitly asked for design
critique only and made no edits.

> I didn't edit anything. The critique below covers mechanics only.
>
> The minimum truthful evidence on every change:
>
> - Checkbox with a text state. It reads "Selected" or "Skipped", so the state
>   never depends on color.
> - The changed entity. For example "Narration words · row 14" or "B-roll out
>   point · row 14". The script view annotates that entity only; unchanged words
>   stay neutral.
> - One consequence line:
>   - Selected: "Changes in new timeline v4."
>   - Skipped: "Resolve keeps current. Difference stays outstanding."
> - The annotation stays visible when skipped. Skipping must not hide the
>   difference.
> - Header counts: "4 selected · 1 skipped".
>
> How Compare should open:
>
> - It opens inline on one change, with two labeled columns: Current Resolve
>   (v3) and After update · new timeline.
> - The After column is built from the current selection, not from the script.
>   A skipped change shows the current content in After, labeled "Unchanged —
>   skipped".
> - The script target for a skipped change must never appear in After. That one
>   rule keeps unchecked work from looking applied.
> - Checking or unchecking the box while Compare is open updates After live.
>
> One group for the three rows. Use one checkbox labeled "3 rows removed", with
> the real rows before and after it shown as neutral neighbors.
>
> - Readable old evidence. Show the removed rows in full at normal reading
>   contrast, inside a labeled container: "In current Resolve · 00:01:12–00:01:40
>   · removed from script". Avoid full-text strikethrough, because it makes the
>   words hard to read.
> - Clearly inert. No active ticks or playhead inside the group, and no place in
>   After's order. Range inspection works only as "current" evidence. Keep the
>   old ordinals as "was 12–14".
> - In Compare, selected After shows a seam between the neighbors reading "3
>   rows removed here · 28s". Skipped After shows the rows in place, labeled
>   "Kept — skipped".
>
> Both move treatments are viable because the move stays within one section.
>
> - A (recommend): one primary passage plus a linked stub. The full passage sits
>   at its script position, between its real neighbors. The origin gets a stub:
>   first line of the passage, its real neighbors, and "Moved ↓ row 22 · same
>   passage · 3 rows", with a jump link. One identity, one checkbox, counted
>   once. Audio moves with it atomically, as in S05. In After, selected puts the
>   passage at the destination with a seam at the origin. Skipped keeps it at
>   the origin, and the destination stub reads "Not moved — skipped".
> - B: both locations shown in full. The origin is shown as inert evidence,
>   styled like a deletion. It's clearer when the two locations fit on one
>   screen. It doubles the reading and can look like a duplicate or a second
>   count.
>
> Row merge (transparent Graphic): annotate the boundary as the changed entity,
> "Row break removed". Don't draw connectors between words in the two rows.
> Current evidence stays as two separate rows with their own ticks. The Graphic
> perimeter spans both, and the base shows through. Selected After shows one
> row with a continuous base; skipped After shows the current rows labeled
> "Kept as 2 rows — skipped".
>
> Cross-row music: M2's rail spans the whole document with its own checkbox.
> Selected After shows its new range; skipped shows the current range labeled
> "M2 unchanged — skipped". An audio-only plan remains valid and says
> "Audio-only update · no picture changes". A duration-driven end never snaps
> to a word; say "Ends by duration" and show its time or offset.
>
> Partial failure stays in the same review. Banner: "Update incomplete. Timeline
> v3 remains current. Baseline not updated." Per-change consequences are
> Verified in v4, Attempted — not verified, Not attempted, or Skipped. Counts
> reconcile to the selected plan. Nothing says applied unless verified. Missing
> local media says "Media offline locally — not evidence of removal" and is an
> unprovable conflict, never deletion evidence.
>
> Recommendation: block only the affected protected-work update, escalating to
> whole-plan blocking when the conflict cannot be scoped. Show the affected
> checkbox disabled as "Blocked — attachment can't be verified", count blocked
> separately from skipped, and group dependent changes with it. This preserves
> #58's granular selection while containing risk in a new timeline.
>
> Recommended pilot: compact script view with the #123 rail turned into
> selected-by-default checkboxes and consequence lines. Compare opens inline per
> change and After is built from current selection. Moves use primary passage
> plus a stub. Protected work uses scoped blocking with escalation.
>
> One alternate for the harness: move treatment B, both locations in full.
>
> Producer choices before full assembly:
>
> 1. Is the baseline after partial failure all-or-nothing?
> 2. Approve scoped protected-work blocking with whole-plan escalation?
> 3. Is Blocked a separate state/count from Skipped?
> 4. Does missing local media block that change or allow warning-only update?
> 5. Compare inline per change only, or also document-wide?
> 6. Move default: primary plus stub, or both locations in full?

## Pilot interpretation

The controlled pilot implements the recommendation and exposes the move
alternate. The six questions remain Producer choices; the pilot does not treat
Claude's recommendation as acceptance.
