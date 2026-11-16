# Issue 61 first review: the YouTube page composite (S16)

This is the first bounded review that #61's Fable handoff asks for. It covers one thing: a Footage clip shown playing inside a frozen picture of its YouTube watch page. The rest of S15 to S18 follows after Matthew decides the points in the [checklist](#producer-checklist).

Nothing here captures a page, downloads a clip, composites a picture or talks to Resolve. Page text, view counts, access results and the zoom are fixtures.

## Open the prototype

The working page is [`r1/S16 YouTube Composite - issue 61 r1.dc.html`](<r1/S16 YouTube Composite - issue 61 r1.dc.html>). It is the accepted #125 source (S03 Integrated Authoring r29, bundle SHA-256 `a210e649…8a2a`) with one added layer. `r1-patch-from-r29.py` is that layer, applied to the untouched r29 `.dc.html`; nothing in the accepted file was rewritten. `support.js` is r29's runtime, unchanged.

Serve the folder and open the page (it loads React from unpkg, so it needs a network connection):

```bash
cd "docs/prototypes/issue-61/r1" && python3 -m http.server 8761 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8761/S16%20YouTube%20Composite%20-%20issue%2061%20r1.dc.html>.

Two ways in:

- The **S16 COMPOSITE** row in the grey harness at the top applies a sample state to the first Footage card and opens the composite.
- On any Footage card, **⋯ › Present on YouTube page**. Clicking a card that is already a composite opens it.

## The proposed default

| Question | Proposed default |
| --- | --- |
| What is frozen | The whole public watch page, captured once, signed out. Title, channel, view count, description and the right-hand column are a still picture. |
| What goes in the player | The Footage card's clip, using the card's existing trim. It is always the whole frame at the shape YouTube shows. It is never cropped or stretched, and the project's "Hide baked-in black bars" setting (#600) does not apply inside a composite. |
| When the shapes differ | The whole clip is fitted inside the player rectangle and the rest of the rectangle is black, as YouTube itself shows a 4:3 video in a 16:9 player. See the **4:3 clip** sample. |
| Motion | The page does not move. The whole composite (page and clip together) gets one slow zoom for the visual's full length, heading toward a focus point. The focus point starts at the centre of the player, which sits toward the upper left, and can be moved. **No motion** is the other choice. |
| Sound | No new rule. A composite follows the accepted Footage rule: silent under narration; the clip's own sound plays when the row has no narration. The page adds no sound. |
| Trim | Unchanged. **Trim…** opens the accepted Clip player. |
| Undo | Creating, refreshing, choosing a revision, moving the rectangle or focus point, changing motion and going back to plain Footage are each one Undo entry. |

### Revision and recovery

| Situation | What the writer sees | What a build does |
| --- | --- | --- |
| Capture in progress | "Capturing the public page…" on the preview; card badge "On YouTube page · capturing…" | Waits for the capture |
| Page refused a capture | Red notice with **Try the capture again** and **Show as plain Footage**; card badge "⚠ … needs attention" | Labelled placeholder (the rule #394 already uses for a failed address) |
| Old capture | Notice giving the capture's age and **Refresh page now**. VERA does not claim to know the live page changed; it only looks when asked. | Uses the selected capture |
| After **Refresh page now** | A new numbered revision is selected for this visual in this draft only. A notice asks the writer to check the rectangle, because VERA does not find the player by itself. Earlier revisions stay selectable. | The **Builds** row shows each earlier build with the revision it used; those never change |
| Rectangle is off | **Adjust rectangle**: drag the rectangle or its corner handle; arrows move, Shift+arrows resize, Enter saves, Escape cancels; **Reset to the template** | Uses the saved rectangle |
| Clip access denied | Red notice; the page capture is kept; **Check access again** | Labelled placeholder |

VERA never silently swaps a broken composite for plain Footage. That switch is always the writer's explicit choice.

## Capability matrix

Checked on 2026-11-16.

| Promised action | Evidence | Supported limits | Gap and owner |
| --- | --- | --- | --- |
| Capture a public page once as an immutable revision; refresh makes a new revision without touching older ones | #39, closed. `packages/public-page-capture` | Public, signed-out pages only. Fixed viewport at scale 2, giving a 3840×2160 PNG. No sign-in, no interaction | None for capture itself |
| Put a page capture on the timeline as a still; a failed address becomes a labelled placeholder | #394, **open** | Still image for the row's length | #394 must land first |
| Use a logged Research clip with its trim | Accepted S03 r29 Footage card; backend entry is #383 | Fixture clips in the prototype; the Research clip payload (#340) is unproved | #383, already a blocker of #165 |
| Place the clip at an exact rectangle over the still | Item transforms (`ZoomX/Y`, `Pan`, `Tilt`) read back in the Resolve guide; compound clips can be made by script (RK-52 and the compound notes) | Proved for single clips and for presenter compounds. **Not proved for a clip scaled into a rectangle over a still**, nor for black fill when shapes differ | Smallest proof below, under #165 |
| Slow zoom on the whole composite toward a focus point | RK-43 and #336: native Dynamic Zoom with a focus on **single still images**, linear only | **Not proved on a composite** (two layers moving as one). Nonlinear easing is unqualified | Smallest proof below, under #165. The prototype says "Not buildable until one Resolve check passes" |
| Find the player rectangle automatically | None | The capture is taken at a fixed viewport, so a template rectangle is a reasonable start; automatic detection is unproved | Design uses a template rectangle plus hand correction. No detection is promised |
| Know that the live page changed | None, and no scheduler (#163 is open) | Only an explicit refresh looks again | Design shows the capture's age, not a change claim |
| Ignore "Hide baked-in black bars" inside a composite | #600 is open; Producer direction 2026-11-16 | Applies to the clip inside the composite | #600 and #165 must both honour it |

Transitions (RK-40, RK-41) do not affect this review. They return in S18.

## Handoff for #165

**Inputs**

1. One Research clip reference with its in and out points.
2. One selected page-capture revision (immutable bytes and its capture time).
3. The composite template name and revision.
4. The player rectangle as four percentages of the capture, and whether it came from the template or was set by hand.
5. Clip fit: always "whole frame inside the rectangle, black fill". Not a per-visual choice.
6. Motion: none, or the slow-zoom preset with a focus point as two percentages of the frame.
7. Sound: decided by the row, exactly as for a Footage card.

**What the frozen output must preserve**

- Each build records the capture revision, clip range, rectangle, template revision and motion it used. A later refresh or rectangle change leaves that record and that build's timeline untouched.
- The clip and the page keep separate identities. Refreshing the page never changes the clip, its trim or its sound.
- A missing capture or a denied clip yields a labelled placeholder that names the cause.

**Representation**

The evidence supports a recommendation only this far: build it natively if the proof below passes, as a still on one video track with the clip on the track above it, the pair wrapped in a compound clip, and the zoom applied to the compound. That keeps both parts editable in Resolve. If the proof fails, fall back to a rendered (derived) composite file. That choice is still open.

**Smallest proof that settles native versus derived**

One throwaway Resolve project, using #520's save, close and reopen check:

1. A 3840×2160 still on V1 and a short clip on V2, the clip scaled and positioned to a known rectangle. Read the transform back.
2. Wrap both in a compound clip. Apply Dynamic Zoom to the compound with an off-centre focus near the upper left.
3. Save, close, reopen. Confirm the rectangle, the zoom and the clip range all read back the same.
4. Repeat step 1 with a 4:3 clip and confirm black fill inside the rectangle.

## Producer checklist

Please reply with a yes or a change for each.

1. **The clip is never cropped.** Whole frame at YouTube's shape, black fill when the shape differs, and "Hide baked-in black bars" ignored inside a composite.
2. **Slow zoom is the default motion**, on the whole composite, heading toward the player, with a movable focus point and a "No motion" choice.
3. **Sound follows the existing Footage rule**, with no separate sound control on the composite.
4. **After a refresh VERA asks you to check the rectangle** instead of trying to find the player itself.
5. **A broken composite builds as a labelled placeholder**, and switching to plain Footage is always your choice.
6. **Capture beyond one screen in the next design pass.** Include the full expanded description and the top comment, with enough room below to zoom toward the description and view count.
7. **Look and wording** of the panel and the card badge.

## Tested

Browser recheck on 2026-11-16. **Run checks** reported 105 passes and the same 26 failures in r1 and in the untouched S03 r29 baseline. The harness covers the 1280×800 and 1024×768 layouts.

At 1024×768, opening **Composite ready** focused **Play**. Activating **Adjust rectangle** focused the player rectangle, and activating **Move focus point** focused the ring. All three focus checks passed.

Fable’s earlier pass ran 32 scripted S16 checks at each layout. Those covered overflow, focus and focus return, zoom playback, pointer and keyboard editing, refresh, revision choice, sample states, 4:3 fit, removal, and Undo. Each state used text or a symbol. After three keyboard-focus fixes, Fable rechecked them at 1280×800.

Not yet done: a self-contained single-file export; the remaining S15, S17 and S18 states and the rest of S16 (Spotlight, motion focus on captures); the full control and state matrix for those.
