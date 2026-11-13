# Resolve finishing preservation

[#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327) stopped
at initial build verification. The Local SDK identified DaVinci Resolve
Studio 21.1.1 build 10. All four synthetic scripts compiled and the original
packaged offline. The two-row original also built, saved and reopened in
Resolve, but the shipped command reported an uncertain write and withheld
the #522 row map. The project was retained for inspection.

Read-only inspection found all four expected stamped clips. Both picture
clips had the expected 96-frame record spans. For each clip Resolve reported
source frames 24 to 120, source times 1.0 to 5.0 seconds and left/right
handles of 24/72 frames. The build verifier expects source end 119 for this
range. The 96-frame audio clips reported source frames 0 to 95. This is the
24 fps interior-cut counterpart to the 25 fps picture mismatch reported in
[#544](https://github.com/mbelinkie/vera-script-to-timeline/issues/544).
The standalone readback passed its structural comparison without a prior UID
map. Further Resolve writes stopped at this point.

Current main now includes #520's qualified 24 fps source-clock correction
(RK-32). All four variants have been regenerated and compiled against that
revision. The fresh native build and preservation trials await the Resolve
slot while #101's manual check is in progress. The remaining 25 fps
correction in #544 is separate from this fixture's 24 fps route.

Claude reviewed the experiment after its usage reset on November 13. Its
three findings were fixed by checking retained timelines before saving and
after reopening, validating variant files before connecting, and allowing
manual-edit corrections to retry before a native write. Offline checks of
those failure paths passed. The fresh package and 92 focused build/map tests
also pass. Native preservation remains pending.

Use the row map delivered by [#522](https://github.com/mbelinkie/vera-script-to-timeline/pull/534)
to identify the original items and the save, close and reopen check from
[#520](https://github.com/mbelinkie/vera-script-to-timeline/issues/520) to
verify persistence. Make the archive from the finished original and start
each variant from a separate duplicate of the same original. RK-17 and #101
show why a copied marker alone cannot identify the original Resolve item.
RK-16–19, RK-40–42, RK-45 and [#328](../issue-328-selective-outbound.md)
provide observation, transition, effect and retry evidence. The open question
is what happens to existing hand finishing when a neighboring row changes.

| Hand finishing | Same length, different clip | Longer second row | Rows swapped |
| --- | --- | --- | --- |
| Row 1 grade | Cannot tell | Cannot tell | Cannot tell |
| Row 1 clip volume | Cannot tell | Cannot tell | Cannot tell |
| Row 1 effect | Cannot tell | Cannot tell | Cannot tell |
| Transition at the row boundary | Cannot tell | Cannot tell | Cannot tell |
| Resolve-only clip on a spare track | Cannot tell | Cannot tell | Cannot tell |
| Archive comparison | Pending | Pending | Pending |

The manual finishing and all three trial updates are pending a verified build
with real picture handles. Before #104 applies any of these changes, it
should keep the finished timeline available, warn about finishing at affected
boundaries and require a proved preservation route for each affected item.
The smallest available fallback is to retain the finished timeline and let
the editor make the affected change manually. This is an interim recommendation
based on the vendor limit and the missing preservation evidence.

## Routes to test on Studio 21.1.1 build 10

- **Same length, different clip.** Use the take selector on row 2's picture
  to select and finalize a different source with the same bounds. Check the
  source ID, geometry and whether the transition stayed attached.
- **Longer final row.** Delete and reappend row 2's picture and tone without
  ripple, extending from four to six seconds. Row 1 starts and ends at the
  same frames. Check whether recreating row 2 removes the shared transition.
- **Rows swapped.** Delete and reappend both picture and tone pairs in the
  opposite order. The spare-track clip stays at its record position. Report
  separately whether it survives and whether it still accompanies row 1.
  Check what deleting and recreating row 1's clips costs.

[Blackmagic Developer Support](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215)
confirmed that Studio 21.1.1 build 10 has no supported in-place scripted move
or trim for the edit they were asked about. The offset and position setters
and `Timeline.MoveItems` first appeared in 21.1.2. Support described a roll
that should retain item IDs but changes the second clip’s source start, and
advised checking handles and persistence. This experiment will establish
which finishing carries through the tested 21.1.1 routes.

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
and the first A1 tone. Make a conspicuous primaries saturation change on the
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
each edit. The grade check samples the clip's LUT export and can miss
controls outside that export. The Fusion check covers the one Blur control.
The transition check covers the readable type, identity and span. Use
“cannot tell” wherever the available evidence cannot establish retention.
The original, archive and completed earlier trials are compared before each
save and after each reopen. A manual-edit preflight failure leaves a
temporary observation folder, so the editor can correct the edit and retry.
If a write returns an uncertain result, inspect the retained trial before
any further Resolve work.
