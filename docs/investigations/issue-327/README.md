# Resolve finishing preservation

Resolve Studio **21.1.1 build 10**, Local scripting, November 13, 2026.
The normal build command created two synthetic 96-frame rows at 24 fps,
then saved, closed, reopened and published the verified #522 row map.
Matthew added the finishing by hand. Each trial and the archive started
from a separate duplicate of the finished original.

| Finishing | Same length, different picture | Longer final row | Rows swapped |
| --- | --- | --- | --- |
| Row 1 black-and-white grade | Kept | Kept | Lost. Recreated picture returned to color. |
| Row 1 clip volume | Kept at −12 dB | Kept at −12 dB | Lost. Recreated tone returned to 0 dB. |
| Row 1 Fusion Blur | Kept at 12 | Kept at 12 | Lost. Recreated picture had no Blur. |
| Cross Dissolve at the boundary | Kept, same item and span | Lost | Lost |
| Resolve-only clip on V2 | Kept at frames 24–48 | Kept at frames 24–48 | Kept at frames 24–48. It now sits over row 2. |
| Archive | Matched before save and after reopen | Matched before save and after reopen | Matched before save and after reopen |

- **Same length.** Adding, selecting and finalizing a take on row 2's picture
  switched the source and retained that picture's item ID and bounds. Row 1
  and the 24-frame dissolve retained their item IDs and spans.
- **Longer final row.** Deleting and reappending only row 2's picture and tone
  without ripple extended it from 96 to 144 frames. Row 1 kept both original
  items on the trial copy. The dissolve disappeared even though the cut
  stayed at frame 96.
- **Swap.** Deleting and reappending both rows without ripple reversed their
  positions. Both finished row 1 items received new IDs. Its picture grade,
  Blur and tone level were lost, along with the boundary dissolve.

After each save, close and reopen, readback matched all four expected clips
against the authored sources and record geometry. The archive matched its
initial snapshot for item IDs, source identity, bounds, markers, volume,
Blur and transition geometry. The original and completed earlier trials
also matched before each save and after reopening.

LUT export produced no readable grade file. The installed SDK's Color-page
thumbnail showed grayscale on row 1 in the original, archive, replacement
and longer trial at frame 72, beyond the spare clip and before the dissolve.
The moved row 1 returned to color at frame 168 in the swap. The mean
per-pixel RGB channel spread was zero for each grayscale sample and about
243 out of 255 for the recreated row 1 picture. Color controls on the other
row stayed visibly colored. This measures one saturation edit.

## Recommendation for #104

On 21.1.1, archive the finished timeline first. Use the tested take-selector
route for a same-length picture replacement when the new source fits the
cut and transition handles and the affected items are understood. Verify the
source, clip bounds and existing boundary after reopening.

Refuse an automatic extension across an existing transition if the update
would drop it. Extending the final row can preserve row 1's own clips,
but the tested route removed their shared dissolve. Refuse an automatic
reorder that would recreate finished clips or guess where to put an
editor-only item. Warn before any write which boundary finishing can
disappear and which editor-only clips overlap an affected span. The smallest
fallback is to keep the finished timeline and let the editor make the
affected change on a copy.

[Blackmagic Developer Support](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215)
confirmed that 21.1.1 has no supported scripted in-place move or trim for
the edit they were asked about. The offset and position setters and
`Timeline.MoveItems` first appeared in 21.1.2. Support described a roll that
should retain both IDs, changes the second clip's source start, and requires
handle and persistence checks. Preservation on that version remains untested.

## Reproduce

From the repository root with the pinned Node and Python versions and the
qualified local FFmpeg, set `scratch` to a new absolute scratch directory.
The preparation command has no Resolve access.

```sh
PYTHONPATH="$PWD" uv run --frozen python docs/investigations/issue-327/prepare.py "$scratch"
```

Once the Resolve slot is clear, hold the shared native owner lock and run the
repository's independent-project idle check around the foreground build.
The build command takes its own build lock. Leave Resolve on the disposable
project the build created.

```sh
PYTHONPATH="docs/investigations/issue-327" uv run --frozen python - "$scratch" <<'PY'
import json
import subprocess
import sys
from pathlib import Path
from check import idle_resolve

root = Path(sys.argv[1])
inputs = root / "original"
manifest = json.loads((inputs / "expected-manifest.json").read_bytes())
with idle_resolve(manifest["buildId"]):
    subprocess.run(
        [sys.executable, "-m", "vera_timeline_agent.build_timeline_cli",
         "--script", str(inputs / "script-document.json"),
         "--inputs", str(inputs), "--output", str(root / "built"),
         "--package-cache", str(root / "package-cache")],
        check=True,
    )
PY
uv run --frozen python docs/investigations/issue-327/check.py setup "$scratch"
```

In the printed disposable project and timeline, work on the first V1 picture
and the first A1 tone. Set primaries Saturation to 0 on the
Color page, set the tone clip's Inspector volume to −12 dB, and insert one
Blur node between MediaIn and MediaOut in Fusion with Blur Size set to 12.
Add a standard Cross Dissolve across the V1 cut at four seconds. Place the
one-second `Spare.mp4` from the Media Pool on any higher video track entirely
inside the first row, starting around one second. Save and leave the project
and original timeline open.

```sh
uv run --frozen python docs/investigations/issue-327/check.py compare "$scratch"
```

Use the saved structural observations and the reopened timelines to score
each edit. Compare the graded clip in the Color page at 3 seconds in the
original, archive and first two trials, and at 7 seconds after swapping. The Fusion check covers the one Blur control.
The transition check covers the readable type, identity and span. Use
“cannot tell” wherever the available evidence cannot establish retention.
The original, archive and completed earlier trials are compared before each
save and after each reopen. A manual-edit preflight failure leaves a
temporary observation folder, so the editor can correct the edit and retry.
If a write returns an uncertain result, inspect the retained trial before
any further Resolve work.
