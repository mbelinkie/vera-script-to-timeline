# Producer correction 1 — S04 prompter composition and readability

Change only the existing Claude Design artifact:

`Script to Timeline - Prompter Runtime and Suite Navigation S04-S06.dc.html`

This is a bounded Producer correction to S04. Preserve S05 and S06 exactly as
they are. Do not modify the accepted S01–S03 artifact, shared tokens, contracts,
fixtures, or any S07–S19 state.

## S04 composition

1. Remove the entire visible `Input boundary — Revision A` column/panel from
   S04. Do not replace it with another source-data inventory, exclusions panel,
   or developer explanation. The user already came from the authoring surface.
2. Make S04 a simple, compact single-column flow:
   - concise title and one-sentence explanation;
   - all prompter options together at the top;
   - the prompter text immediately below;
   - the simulated creation action/result after the text or in a compact sticky
     action area, whichever reads most naturally at both viewports.
3. Reduce the prompter type and spacing substantially. It should read like an
   ordinary review/export document inside the product, not like a full-screen
   teleprompter playback program. Keep it comfortably readable, but fit the
   complete example into a normal working viewport without theatrical scale.
4. Preserve the existing output exclusions without displaying the excluded
   source material: Direction, Citation, production markers, excluded draft
   notes, source transcript content, and other non-prompter families still must
   not enter the prompter text.

## Non-spoken notation

Anything that is not meant to be spoken must appear in square brackets in the
prompter text. This includes camera-state markers, performance directions,
pronunciation guidance, and optional section labels. For example:

- `[OC]`
- `[VO]`
- `[PAUSE]`
- `[SAY: Lunara = loo-NAH-rah]`
- `[SECTION: Why the Signal Changes]`

Inside the VERA interface, these bracketed items may be displayed as compact
pills to distinguish them from narration. The literal copied/downloaded plain
text must still contain the square brackets. Parentheses such as `(OC)` and
`(VO)` are no longer acceptable in this corrected design.

## New readability option

Add a third independent checkbox at the top:

`Simplify brief mid-sentence camera changes`

Use concise supporting text or an accessible description that makes the
behavior precise:

- It changes only the displayed/exported OC/VO markers. It does not rewrite or
  delete narration and does not change the underlying camera assignments in the
  script.
- A brief change means an OC or VO island of five spoken words or fewer that
  begins and ends inside one sentence and is surrounded by the same camera
  state. When the option is on, omit both markers around that island and display
  the sentence under the surrounding camera state.
- Never simplify a change at a sentence or paragraph boundary, a one-way change
  that does not return, a change longer than five words, or a missing/unassigned
  camera state.
- Apply the example deterministically: F04's five-word VO island `as the tide
  turns and` is surrounded by OC. With the option off, show the current
  `[OC] → [VO] → [OC]` markers. With it on, show the entire F04 sentence
  continuously under OC with no mid-sentence VO/OC interruption.
- The setting participates in deterministic export identity. The same source
  revision and all three option values must reproduce the same text and sidecar
  identities; changing this option must produce a different simulated identity.
- Default the new option on for this prototype, because its purpose is
  prompter readability. Make the checked state visible and accessibly named.

## Action and intended use

Replace `Preview prompter` as the primary end action with
`Create prompter export`. This remains a design simulation: never write or
download a real file and label the result `Simulated — no file written`.

After simulated creation, show a compact result tied to the frozen source
revision with:

- `Download prompter text` as a clearly simulated control;
- `Copy prompter text` as a clearly simulated convenience control; and
- the sidecar identity under a secondary `Technical details` disclosure rather
  than as a primary user-facing action.

Explain in one short sentence: `Use this text in your teleprompter. VERA keeps
the companion data for matching recorded takes later.` Do not make the page a
teleprompter playback mode.

The missing-camera branch must still block creation, name the affected phrase,
and offer a return route without inventing a state. The removed-marker branch
must still retain the zero-duration unplaced marker with Reattach/Dismiss while
keeping it out of prompter text. Because the input-boundary panel is removed,
surface that warning as a compact contextual notice rather than restoring the
source inventory.

## Verification

Test S04 at internal 1280 × 800 and 1024 × 768. Verify:

1. no visible `Input boundary` panel or excluded-source inventory remains;
2. all three checkboxes precede the prompter text;
3. the default simplified output keeps every narration word and displays F04
   continuously under OC;
4. turning simplification off restores the exact mid-sentence `[OC] → [VO] →
   [OC]` transitions;
5. annotation and section-label options still affect only their controlled
   non-spoken content, and every displayed/copied non-spoken item uses square
   brackets even when it is rendered as a pill in the app;
6. the same revision/settings reproduce identities, while changing the new
   option changes identity;
7. missing-camera and unplaced-marker branches retain their prior safety
   behavior;
8. the prompter text is materially smaller and the page has no horizontal
   overflow, clipped focus ring, or independent content-column scrolling;
9. Tab/Shift+Tab order is logical, Space toggles each checkbox, Enter activates
   creation, and Escape closes Technical details and returns focus; and
10. S05 and S06 are byte-for-byte/behaviorally unchanged within the artifact.

In the final report, state exactly what changed, the observed results at both
viewports, the two identity comparisons, and confirmation that S05/S06 and the
accepted S01–S03 artifact were not changed. This correction does not constitute
Producer acceptance and must not mark issue #58 Done.
