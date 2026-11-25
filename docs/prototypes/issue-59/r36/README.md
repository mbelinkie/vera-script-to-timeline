# Timeline #59 design handoff

[S03 Integrated Authoring r36](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+Integrated+Authoring+r36.dc.html)
is the Claude-owned design reference for [#59](https://github.com/mbelinkie/vera-script-to-timeline/issues/59).
It extends the [accepted S03 r30](../../issue-125/r30/README.md). The separate
[frozen r36 header proposal](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+r36+Header+alignment+proposal.dc.html)
shows the shared shell alongside approved Research r14.

[Download the exact handoff ZIP](issue-59-r36-handoff.zip). Open either
`- export.html` file inside `issue-59-r36-handoff/` in your browser. The
`source/` folder contains both editable Claude files and their local assets.
The `docs/` folder retains the reviewed decision log and spec.
`EVIDENCE.md` records the scripted checks and limitations, and
`MANIFEST.md` identifies every member. The archive SHA-256 is
`ba77cbe66de9e19941164d5105b6c6a292a0eb9eff9bc6e000df0e7528d11127`.

## Decisions to carry into the app

| Area | Behavior |
| --- | --- |
| S07 · Roles | Viewers read and comment. Highlighting words offers only **Add comment**. Editing, placement and Build mutations are absent. A demoted member sees the read-only script after discarding unsaved edits. A removed member sees the access-ended page. Research permission is independently required for Library access. |
| S08 · Collaboration | Keep status and presence distinct from actions. Show syncing, synced, offline and failed states with honest recovery. Attribute collaborator edits and preserve their work through your Undo. Viewer comment creation and replies supersede the earlier read-only comment checklist. Resolve and Reopen are for Editors and Producers. Mentions target project members, with notifications deferred. |
| S09 · History | Keep attributed changes, named checkpoints and a text comparison against the current revision with a checkpoint dropdown. Editors and Producers restore as a new head while retaining later history, comments and build records. #76 owns synchronized Preview and Producer Release from an approved checkpoint. |
| S10 · Stash and Extras | Keep Stash as the UI name and the home for parked material. The separate Ideas and idea-to-stage-direction flows were withdrawn. The global Extras view shows original section and a restore path. The section-linked view is deferred. Existing Stash behavior carries forward from r30. |
| S11 · Build | A verified timeline can complete a Studio build by itself. Render MP4 defaults off and uses a saved Resolve preset when selected. Drive upload is a separate opt-in per rendered build, with the destination visible and a separate sharing decision. The Free route shows the package and manual-import confirmation. Failures state what survived. After a cancelled Studio render, re-verify the target before retry. General render-failure and upload retry remain deferred. |
| Shared header | Use separate app and same-app project menus. **Research** is the destination label. The other app opens in a new tab and checks its own membership per the [suite contract](../../../vera-suite-design-contract-and-claude-brief.md#5-reciprocal-browser-suite-switcher-and-authorization). Keep Research Sources and Library as workspace tabs and its future text-size control under View settings. |
| Authoring and settings | Keep row-end **+ Visual**, selection-based Add visual and right-column range editing. Drop Library footage or a stashed visual onto highlighted words through #691. Keep the picture-change tally, spoken word count and runtime estimate. Estimate from spoken words divided by WPM plus timed visual-only rows. Exclude stage directions from the count and disclose excluded untimed rows. Project settings has Narration pace and Delivery examples, with a provisional list for later settings. |
| Narrow header | Reveal the full truncated title and collaborator status on hover or keyboard focus. The title keeps its project-menu action. The collaborator status stays informational. Escape dismisses the reveal and leaves sync recovery visible. |

## Review evidence

| Viewport | Checks retained |
| --- | --- |
| 1280 × 800 | Claude checked the exact standalone r36 export with the long title, presence and sync failure. Both rows fit and Try again remains visible. The full presence text stays inline. In the live r36 preview, Codex opened the app menu, confirmed **Research** and its new-tab label, then used Escape to return focus to the switcher. The hosted standalone showed the r36 header and runtime readout. |
| 1024 × 768 | Claude checked title and both collaborator tooltip states with sync failure. Full strings wrap below the first row, leave Try again clear and dismiss with Escape. In the live r36 preview, Codex selected 1024, enabled the long title, used Tab to show the full title, and used Escape to dismiss it with focus retained. A Tab from the title to the recent Jonah status revealed the complete status. |

The archive retains Claude's scripted results and the Producer's earlier
prototype review. The independent checks above were real browser key and click
events on the prototype. A full physical-pointer, Tab-order and screen-reader
pass remains part of the running-app review. Preserve the full accessible text,
measure actual overflow on resize and announce changing presence politely.

## Known limits and production ownership

| Area | Remaining work |
| --- | --- |
| Roles, collaboration and comments | #72 and #73 own real permissions, presence and save/Undo behavior. Verify demotion during a pending edit, controls turning off, refused text being discarded and no replay after promotion. #74 owns real anchored comments and eligible thread actions. #356 owns persisted contribution review. |
| Library and switchers | Verify Viewer Library access in #643. The prototype uses fixtures for app switching, same-app project switching, the linked-project chooser and account state. Check new-tab draft preservation, destination authorization and safe fallback in the app. |
| History and Release | #75 and #76 own durable history, restore, Preview and Producer Release authorization. The prototype's Build flow and checkpoint list use fixtures. Apply the approval requirement to Release as scoped in #76. #689 and #690 own the later visual comparison. |
| Stash, Sorting and drop | #78 owns Extras persistence. #616 owns the running Sorting/Stash UI, including a populated pending script in trial order and correctly aligned expanded-row connector lanes. The blank preview and bunched pins are known prototype defects. See the [connector review](https://github.com/mbelinkie/vera-script-to-timeline/issues/59#issuecomment-7081082100). #691 owns drop onto highlighted words. |
| Resolve and Drive | #70 owns the Build and agent flow, #116 the Resolve operator surface, #329 preset and continuous-range proof, and #71 Studio render and consented Drive upload. Prototype outcomes are fixtures. Verify the supported external capabilities before enabling their controls. |
| Settings and timing | Implement role-aware settings storage and use actual timed narrator speech for measured WPM. Keep the manual fallback and surface missing row durations. The remaining settings inventory is provisional. |

The archive preserves historical notes verbatim. The later Viewer comment
decision and the withdrawal of Ideas supersede their earlier checklist entries.
[#693](https://github.com/mbelinkie/vera-script-to-timeline/pull/693) already
resolved the suite contract follow-up listed in the archive. Use the accepted
r30 and its Stash implementation issues for placement semantics.

Use [#692](https://github.com/mbelinkie/vera-script-to-timeline/issues/692) for
acceptance of the running alpha with saved data and authorized users. Paired
review and later integrated conformance remain with #126 and #62.
