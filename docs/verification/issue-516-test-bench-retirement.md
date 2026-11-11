# Issue 516: Test Bench retirement

The stopped Test Bench source is preserved in the annotated
[`archive/test-bench-2026-11` tag](https://github.com/mbelinkie/vera-script-to-timeline/tree/archive/test-bench-2026-11)
and the `zodex/499-adopt-pr474` branch. Both remote refs resolve to commit
`6cd70d90f1a0a2f7aed8470ba5a074a923ecd293`. PR #474 was closed unmerged;
its `chat/473-unattended-test-bench` branch remains available.

The archive contains Git objects, not private evidence, renders, or installed
applications. The previously registered frozen temporary worktrees were absent
when inspected. Other relevant local branch tips have no commits outside the
remote refs. No cleanup or Git pruning was performed.

## Mac inventory, 2026-11-11

Allocated sizes are observations, not guaranteed reclaimable space; files may
be shared or duplicated. A private per-path inventory stays on the Mac.

| Item | Observed size | State and recommendation |
| --- | ---: | --- |
| Test Bench helper app and LaunchAgent | about 284 KiB | Running with KeepAlive; retain until explicitly approved and activity is checked. |
| Helper spool and retained signed copies | about 2.6 MiB | Private operational evidence; retain. |
| Test Bench case and attempt roots | about 11.5 GiB | May contain unique renders and journals; retain pending a backup and a separate decision. |
| Overnight watchdog plist and case directory | about 28 KiB | Watchdog is not loaded; retain until explicitly approved. |
| Shared qualification output roots | about 25.2 GiB | Mixed or uncertain ownership; retain. |
| Older campaign and queue services | small plists | Separate issue #447/#448 roots; loaded, with the campaign monitor running. Preserve. |

The native ownership directory contains an active marker; its meaning was not
resolved, so it and associated data remain untouched. The source archive is
not a backup of those files. No local artifacts have been deleted or services
stopped. The issue remains open while the Producer decides what to remove.
