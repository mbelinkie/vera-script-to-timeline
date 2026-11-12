# Issue 520 timeline speed check

One command builds a short sample and a public 30-row sample, saves, closes and
reopens Resolve, and checks their structure. The Producer decision on
2026-11-12 requires separate preparation and build-plus-check times.
Only build plus check is compared with the verified timeline duration.

## Updated 24 fps results, 2026-11-12

Both cases now passed save, close, reopen and structural verification through the shipped command on Studio 21.1.1 build 10, Local scripting, Intel Mac.

| Sample | Timeline duration (s) | Preparation (s) | Build plus check (s) | Structural check | Speed result |
| --- | ---: | ---: | ---: | --- | --- |
| Short retained sample | 47.792 | ~2,588 | 74.82 | PASS, 11 events | **FAIL** |
| Public 30-row fixture | 581.250 | ~866 | 199.55 | PASS, 102 events | **PASS** |

This table covers exact 24 fps and does not cover VERA's default 23.976 fps. The gate compares the reported full command time with the timeline duration. Preparation is excluded.

The short source-clock verifier now admits only the demonstrated alternative 24 fps getter shapes with source hash, mapping, media frame count or narration sample count, speed and exact source-time evidence. The long fixture uses the planned source videos in the two former slate slots while retaining the placement timings. The lifted #312 generators remain unchanged.

Preparation times are approximate active elapsed times reconstructed from file timestamps. The long preparation resumed after a checkpoint, and its estimate excludes the stopped interval. Native command times above were printed by the command itself. CPU speed limits observed were 50% after short, and 37% before / 22% after long. The Producer has identified these as representative practical conditions for this Mac.

The short speed miss is pending Claude's independent assessment after 6:03 pm. Producer watch-and-listen acceptance is also pending. Further timing work after 6:03 pm must wait until the Producer confirms he has quit other work on the Mac.

[Updated result table](https://github.com/mbelinkie/vera-script-to-timeline/issues/520#issuecomment-6835566969)

## Delivery and next steps

The duplicate preparation-report fix is merged in
[PR #532](https://github.com/mbelinkie/vera-script-to-timeline/pull/532), closing
#531. The source-clock correction, fixture adaptation, runner and observations
are on [draft PR #529](https://github.com/mbelinkie/vera-script-to-timeline/pull/529).

Focused checks passed, including 78 workflow tests, 27 command tests, 13 runner
tests and one fixture test. The two pinned-compiler command cases initially
used the wrong Node version and passed after the pinned runtime was selected.
Ruff and targeted mypy passed. The Mac fast gate hit an unrelated backup-test
timeout. Full regression runs in GitHub Actions.

Claude's CLI previously hit its usage limit. At 6:03 pm, review the practical
optimization options and the short speed miss with Claude before requesting
acceptance. The Producer may accept that miss only if both agents agree the
remaining optimization is unjustified on this Mac. The speed gate remains
failed until the Producer accepts a revised criterion. The Producer must also
watch and listen to the verified short result once.

[#533](https://github.com/mbelinkie/vera-script-to-timeline/issues/533) covers
the default 23.976 fps command. Its External acceptance requires Mac Studio.
Start it with a Mac-capable agent after #520 completes. Code preparation may
proceed while waiting for review, as authorized by the Producer.
