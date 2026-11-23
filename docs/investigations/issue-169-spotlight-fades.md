# Spotlight fades during continuous zoom

Tested on 2026-11-22 for Timeline #61 and #169. Matthew requires fades and a
choice at each incoming highlight between dimming earlier passages and keeping
them bright. Both behaviors passed this bounded native probe.

## Tested mechanism

DaVinci Resolve Studio 21.2.0 build 6 on the Intel Mac, Local scripting,
1920×1080 at exact 24 fps. One disposable project contained three 96-frame
still timelines with identical centered, linear native Dynamic Zoom. The
synthetic webpage was 3840×2160 with four colored registration markers. Passage
A occupied two separate wrapped-line boxes. Passage B occupied a different box.

The existing `packages/spotlight-matte` core generated the confirmed-box alpha
mattes with dim alpha 191 and zero padding. Their pixels were checked against
the specified rectangles. Precomposed dim, A, B, and A+B pictures shared the
same source page and dimensions. Native Fusion MediaIn nodes read these Media
Pool items. Two native Dissolve nodes animated the treatment within one
full-length still occurrence, with native Dynamic Zoom on that occurrence.

- First highlight entrance used Mix 0→1 over frames 0→8.
- The second cue began at frame 40 and used Mix 0→1 over frames 40→48.
- Replace faded A into B. Accumulate faded A into A+B.

Eight frames is a probe choice, about one-third of a second. Matthew has not
accepted it as the product's fade duration. The cue was the start of the fade.

This extends the [November 16 hard-switch probe](https://github.com/mbelinkie/vera-script-to-timeline/issues/169#issuecomment-6933622488)
and RK-43. The earlier adjacent-still representation remains evidence for its
measured hard switch. This fade probe establishes a different native route.

## Save, close, reopen and picture results

An initial AddFusionComp-only attempt lost both compositions after project
reopen. The successful route saved each composition to a `.comp` file and
explicitly imported it onto its still occurrence. After another save, close
and reopen, both compositions and their exact fade keyframes were present.
Native Dynamic Zoom remained enabled.

Resolve exported PNG stills after reopen at frames 0, 4, 8, 39, 40, 42, 44,
46, 48, 49 and 95 for all three timelines, 33 samples total. A cold Fusion frame
export timed out once. Retrying that missing still succeeded. No Deliver movie
was rendered.

| Measurement | Observed result |
| --- | --- |
| Initial highlight entrance, A background at frames 0/4/8 | RGB intensity 62/155/248 in both treatments |
| Replace A, frames 40/42/44/46/48 | 248/202/155/108/62 |
| Replace B, same frames | 62/108/155/202/248 |
| Accumulate A, same frames | 248/248/248/248/248 |
| Accumulate B, same frames | 62/108/155/202/248 |
| Four marker centroid distances from the continuous-zoom control | 0.0 pixels at all sampled frames |
| Fully bright opening edges against marker-projected source boxes | Worst absolute edge error 0.55449 pixels |
| Gap between A's two wrapped lines | Stayed dim at RGB 62 throughout the samples |
| Largest channel difference from the control outside highlight boxes and a four-source-pixel edge margin | 2 levels on an 8-bit channel |

The measurements show progressive fades, both retention choices, registered
openings, and the same page-motion positions as the control at the sampled
frames. The small outside-region difference is recorded as measured. The
comparison is not byte-identical picture output.

## Design handoff and remaining product work

The next focused Claude pass can demonstrate both choices with a required fade,
using an eight-frame prototype example whose duration remains for Producer
review. The fade starts at the selected narration cue in this example. Keep
selection geometry tied to the frozen source capture throughout viewing-scale
changes and playback.

The product path remains open in #169. This probe used explicit native OTIO
and Fusion imports. It did not run browser selection, saved timed-treatment
storage, narration-word-to-frame compilation, matte picture encoding through
the normal build pipeline, or product qualification admission. Those need
implementation and end-to-end checks. Frozen capture identity, confirmations,
matte provenance, unresolved-remap refusal and earlier-build immutability must
carry through that path.

The observed envelope is centered linear zoom, this 16:9 source raster, one
96-frame occurrence, two highlights, and eight-frame fades at exact 24 fps.
Other rates, fade lengths or overlapping cues, tall-page framing, off-centre
motion, arbitrary pages, in-Resolve manual edits, continuous playback/movie
output, and Resolve Free were not verified. The screenshot samples establish
bounded feasibility for the next design pass. They do not certify the complete
product implementation or close either issue.
