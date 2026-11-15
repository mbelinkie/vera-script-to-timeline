# Changing a row's length in place on Resolve Studio 21.2

Resolve Studio **21.2.0 build 6**, external Local scripting, November 14,
2026, on throwaway projects with the synthetic 24 fps media that #327's
`prepare.py` writes. Three short probes, each saved, closed and reopened
before the final readback. All finishing was set by script, so that the same
script could read it back: a zoom, a clip colour, a clip marker, a
saturation-0 grade (`SetCDL`, read with 21.2's `GetCDL`), one OFX effect
(`AddEffect`), a clip volume, audio fades, and Cross Dissolves
(`AddTransition`).

The question for #104: when a row gets longer or shorter, can the later rows
move, and the changed row be resized, without recreating clips?

| Operation | Call | Result after reopen |
| --- | --- | --- |
| Move a later row (picture, tone, and an extra clip on V2) 48 frames right | `Timeline.MoveItems` | Same clip IDs. Grade, zoom, colour, marker, OFX effect and volume kept. |
| Move two later rows together, with a dissolve on the cut between them | `Timeline.MoveItems` | The dissolve kept its ID and moved with them, right and then left. |
| Extend a picture into the gap, same source | `SetRightOffset(handle − n)` | Same ID, new length, source start unchanged. |
| Shorten it again | `SetRightOffset(handle + n)` | Same ID, original length. |
| Swap a picture, then extend it | `AddTake`, `SelectTakeByIndex`, `FinalizeTake`, then `SetRightOffset` | Same ID. The swapped clip kept its own grade, zoom and marker. |
| Move one clip on its own | `TimelineItem.SetPosition` | Same ID. |
| Dissolve on a cut the change does not touch | none | Kept, same ID and span. |
| Dissolve on the cut that opens when the later row moves away | `Timeline.MoveItems` | **Lost** as soon as the cut opened. Closing the gap did not bring it back. |
| Swap a tone for a different, longer file through the take selector | `AddTake` on an audio clip | **Not possible.** `GetTakesCount` returns nothing and `AddTake` returns false. |
| Replace a tone with a longer file | Place the new file on a spare audio track, `CopyAttributes` (all audio and clip attributes) from the old clip, `SetFades` from the old clip, delete the old clip, `SetPosition` the new one into place, delete the spare track | Works. The new clip has a **new ID**. Volume and fades carried over. The new clip also read back with a Green clip colour the old one did not have. |

## What this means for #104

On 21.2 a row can change length while every later row keeps its clips and
their finishing. The order that worked: to lengthen, move the later clips
right first and then extend into the gap; to shorten, trim first and then move
the later clips left.

Limits to respect:

- A transition on the cut between the changed row and the next row does not
  survive. One that the script wrote can be put back from the script after
  the change; one made or adjusted by hand cannot be reproduced, so that row
  should be refused.
- A narration clip that becomes a different file is a new clip. Its level,
  fades and clip attributes can be carried over; anything `CopyAttributes`
  does not list cannot be shown to survive.
- Finishing was set by script. A grade made by hand on the Color page, a
  Fusion composition and a hand-drawn transition were not part of these
  probes.
- Linked picture-and-sound clips, stills, speed changes and frame rates other
  than 24 were not tested here.

## Reproduce

With Resolve Studio 21.2 running on an empty project:

```sh
cd docs/investigations/issue-104
uv run --frozen python move_probe.py "$media" "$scratch/probe-1.json"
uv run --frozen python move_probe_2.py "$media" "$scratch/probe-2.json"
```

`$media` holds `A.mp4`, `B.mp4`, `C.mp4`, `Spare.mp4`, `A-96.wav`,
`B-96.wav` and `B-144.wav`. Each run creates its own project named
`VERA 104 move probe <id>` and never opens another one.
