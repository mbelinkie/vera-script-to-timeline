# Native image zoom qualification (#325)

Investigation in progress, 2026-10-25. This is capability evidence for #164 and
#319, not production image-motion implementation or design acceptance.

## Experiment

Use only a generated, labeled square grid in the fresh disposable project
`VERA325 Native Zoom 20261025 A`. Installed route: external Resolve scripting,
DaVinci Resolve Studio 21.1.1 build 10. No Free runtime is installed or inferred.

Compare two occurrence durations, Dynamic Zoom enabled/None, all four native
ease values, fit/fill scaling, custom off-center start/end requests, shorter
and longer revisions, and save/reopen readback against rendered frames. Keep
earlier timelines and outputs intact. Refuse unsupported requests rather than
substitute a centered preset. Explicitly distinguish rebuilt durations from a
native trim if the API cannot perform one.

## Status

The live issue was Ready, unclaimed, External acceptance, with #173 Closed/Done.
Claimed by chat `01a174fe-f403-7e23-95ed-91df6f1ce600`, Sol/high, from freshly
fetched main `0d7bb43a59e101c20069b478b76966bd25bf73b7`.
No existing project, installed release, private media or prior proof target is
part of this experiment. Results and limitations will replace this checkpoint.
