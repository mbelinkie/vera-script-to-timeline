# Issue #119 native Wide/Tight qualification

## Result

On DaVinci Resolve Studio 21.1.1 build 10 with External Scripting set to
Local, the native scripting API saved and read back exact Wide/Tight test
transforms after closing and reopening a synthetic project. The Edit page's
color-selection command selected the intended clip groups independently.

| Group | Resolve clip color | Zoom X/Y | Pan | Tilt |
| --- | --- | ---: | ---: | ---: |
| Wide | Blue | 1.22 | -18 | 6 |
| Tight | Orange | 1.65 | 14 | -7 |

The 1920×1080, 24 fps project used a 240-frame synthetic presenter source. A
new profile-v3 request created separate Master and Generated timelines. The
Generated picture intervals are contiguous: Wide `[0,48)`, Tight `[48,120)`,
Wide `[120,240)`. Dialogue spans 240 frames; B-roll occupies record frames
`[96,120)`. Both Master tracks read back locked after application. The final
picture segment's source end reads frame 239 because its exclusive requested
end reaches the 240-frame source EOF, matching the bounded endpoint rule in
the Resolve Knowledge Guide.

In the Edit page, `Timeline → Select Clips → By Clip Color → Blue` highlighted
both Wide clips, and selecting Orange highlighted the Tight clip. The v3 apply
left presenter placement, dialogue, B-roll and the prior v2 timeline unchanged.
Before/after hashes for the existing v2 profile and request matched exactly.

The earlier v2 render remains the only rendered proof: its 240-frame records
were continuous, expected source-frame samples had MAE 0–0.071 versus 3.27–5.62
for adjacent-frame references, before/after PCM matched exactly, and B-roll
frames `[96,120)` were pixel-identical. Those measurements apply to v2's
parameters only.

## Limits

The transform values are synthetic test tuples. This run verifies native
storage/readback and the color-based group-selection workflow; it did not
render v3 or compare decoded v3 frames/audio. It makes no claim about framing
quality, production footage, motion/focus behavior, Resolve Free, or creative
acceptance. The earlier v2 render/identity evidence remains evidence for v2
only.
