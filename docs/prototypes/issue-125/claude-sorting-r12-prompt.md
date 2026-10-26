# Sorting revision after r11 — Producer notes, 2026-10-26

Revise the current **S03 Outline Sorting Comparison r11** into a versioned
successor. Preserve r11 and the other project surfaces. Matthew is leaning
toward **A · Line**, but has not selected it. Keep both options available with
identical script content and behavior. No export.

Use the supplied 20-row script without rewriting or shortening its underlying
narration. Preserve word-level On Camera bolding, including in expanded rows:
an overlay alone must not make voiceover words bold.

Attachments: `sorting-long-rows.md`, `sorting-thumbnail-atlas.png`, and
`sorting-thumbnail-map.md`. The image is a 4-column × 6-row atlas of 24 actual
sample photos, generated as fictional demonstration imagery. The map gives
every tile and all 20 ordered visual sequences. Render ONLY each mapped photo
in its slot and enlarged preview, never the full contact sheet. CSS atlas
positioning is sufficient; do not regenerate the imagery or substitute tiny
text boxes. Import the attached image into project assets and use its actual
project URL. No local filesystem path will work in the live design.

## 1. Real images and thumbnail placement

Remove all thumbnails from the LEFT of each summary. Put the visual cluster
on the RIGHT:

- One planned foreground visual: one thumbnail.
- Multiple foreground visuals: first and last thumbnails.
- Hidden middle visuals: **+N BETWEEN the endpoints**, without a second
  vertical divider.
- Count planned beats, not distinct images. Identical endpoints can surround
  other visuals; preserve them both. Overlays alone add no foreground beat.
- OC slots count as beats and occupy endpoints: s07 and s11 show neutral
  OC · +1 · OC. Do not promote the hidden photo into an endpoint; report this
  recognition limit and let expansion expose the middle visual.

Keep the intentional unavailable first thumbnail in the slate-sign row.
Make the images useful for recognition while preserving compact rows. Hovering
a footage/still thumbnail shows a substantially larger non-interactive floating
preview. It must not resize rows or shift the outline. Close it when the pointer
leaves the thumbnail or Escape is pressed; suppress previews during dragging.
Clicking a thumbnail acts like clicking the summary. Avoid extra Tab stops per
thumbnail: with a row focused, P toggles an enlarged preview of its displayed
photo endpoint(s). Announce the shortcut; Escape closes that preview before
collapsing the row. OC and unavailable slots never enlarge. If neighboring
atlas-tile slivers show, inset the displayed crop slightly without changing
the mapping or regenerating the image.

On Camera slots are neutral, without orange/gold emphasis or hover enlargement.
Bold narration retains its On Camera meaning.

## 2. Text omission in B

A retains its single-line text arrangement. In B replace the vertical orange
omission marker at the beginning of the ending line with a thin HORIZONTAL
orange marker BETWEEN the two text lines of that same row summary:

- Opening excerpt ends with **…**.
- Horizontal omission marker between the lines.
- Ending excerpt begins with **…**.

Show omission cues only when middle text is hidden. Short text appears once.
Keep text omission distinct from the +N count for hidden visuals.

## 3. Moved indicator

Move **Moved** to the LEFT beside the selection/move controls. Give it a clear,
distinct color so changed rows stand out, with color/shape distinct from the
selection highlight. Preserve its meaning: deliberately moved rows are marked,
returning to the starting position clears the mark, and Undo updates it.
Do not consume narration-excerpt width with a right-side status badge.
Reserve a fixed left slot so showing/clearing Moved never shifts the text.

## 4. Quieter dragging

Remove visible destination sentences such as "placing after…" during dragging.
The insertion line and dragged selection communicate placement. Keep accessible
destination announcements for keyboard/screen-reader use and the single group
handle on the left.

## 5. Plain language and expansion

Remove "trial" from user-facing wording. Name the view **Sorting**; use
**Changes not applied** where needed. Preserve Accept sorting, Return to
sorting and Discard sorting behavior.

Remove the dedicated **Collapse** button. Clicking the summary again collapses
its expanded row; retain keyboard equivalents and only one expanded row at a
time. Clicking inside expanded content must not accidentally collapse it.
Keep the summary visible as the expanded row's header and collapse target;
only that header toggles, while content below it stays independently usable.
Remove product labels such as "full row," "read-only standard S03 rendering"
and other implementation notes. Expanded content simply looks like the
established script. Preserve read-only review behavior without developer copy.

## 6. Independent Stash rows and optional sections

Supersede the earlier mandatory-bundle rule:

- Stashing several rows preserves order but does not link them.
- Each saved row can be inspected, edited or restored independently.
- Explicitly selecting several rows permits restoring them together.
- Users can create sections within Stash to organize saved rows.
- Stashing a selection does not automatically create a section or require
  restoring the selection as a unit.

Preserve Show Stash, the saved-row count, sidebar access, wide inspection and
normal-authoring access. **Capability hold: #337** owns the missing independent-
restore/Stash-section proof. #307/#310 prove the former bundle operations,
not these changed interactions. Retain these requirements, but HOLD depicting
their changed operations as working until Codex supplies that handoff. Keep
supported stashing, count, sidebar, inspection and normal-mode content editing.
Show neither superseded bundle restoration nor independent restore/sections
as working. Report those held cases in harness notes outside the product frame.
Do not run a backend investigation or manufacture a simulation as proof.
Other visual corrections in this prompt can proceed independently.

## 7. Preserve music limits

Retain the right music gutter separately from the thumbnail cluster. The
corrected first-interruption behavior remains held for #326. Do not substitute
the former starting-row-only cutoff or claim playback/trim support.
Keep the proved intact span's existing start/end marks; hold changes to that
span, not its already-supported appearance. Report the hold outside the frame.

## Verification and stopping point

Inspect both options at **1280×800 and 1024×768** with the supplied images.
Check atlas images actually load and show the correct individual tile; hover/
focus enlarges the same photo without shifting rows; On Camera remains neutral;
the unavailable case remains unavailable. Check right-side grouping and +N,
B's omission treatment, left colored Moved marks, expansion, quiet dragging,
and keyboard/focus/non-color behavior. A/B content and semantics stay identical.
Use r11's collapsed heights (A 40px, B 50px) as the starting point. Put B's
horizontal marker in the existing line gap and reserve the left Moved slot;
avoid adding vertical chrome that unnecessarily consumes another row.

Keep the target of at least ten readable collapsed rows. Report actual counts
and any unmet target; do not shrink text or remove context to manufacture a
pass. Keep technical harness notes outside the product frame.

Show the revised comparison and explain the strongest remaining recognition
problem in each option. Report the #326/#337 held cases honestly and stop for
Matthew's choice. Do not propagate a selected layout or redesign other surfaces.
