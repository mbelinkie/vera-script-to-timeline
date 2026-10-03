# Issue 149 discriminator checkpoint

Task ID: native actor NEWresume.

The user stop was honored before any render or file replacement. The retained
project is `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID
`0591bb41-d645-4af7-a2ee-ff75f8f43162`. The final read-only observe and the
single save checkpoint both captured the same full state: current timeline
`D6-kept-r2-20261003` (`70aee9bd-5928-4e3b-9f0e-f45897773337`), six timelines,
24 timeline items, 13 media-pool items, an empty render queue, and
`IsRenderingInProgress == false`. Project settings are 25 fps playback and
timeline rate, 1920x1080, and 48 kHz. The installed action configuration is
atomically disarmed.

The failed original `D6-kept-20261003` timeline remains untouched as retained
partial evidence. The valid r2 W6 bindings are explicit: `D6-kept-r2` uses
`base.mov` as its linked V1/A1 source, so a future kept-time replacement must
guard and atomically replace `media/base.mov`; `D6-changed-r2` uses
`swap.mov`, so its changed-time replacement must guard and replace
`media/swap.mov`. No W6 render, swap, relink, W3 mutation, Console action, or
Fairlight action was performed before this checkpoint.

Evidence: observe result
`vera-issue-149-workflow-discriminators-result-observe-user-stop-checkpoint-20261003-kit-02.json`
and save result
`vera-issue-149-workflow-discriminators-result-save-checkpoint-user-stop-20261003-kit-02.json`.
