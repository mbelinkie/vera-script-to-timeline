# Task ID #149 — Phase 10 native execution record

Date: 2026-10-02

This record belongs to the native actor for the Phase 10 re-confirmation of
Issue 149 through the injected Workflow Integration path. It covers only the
new disposable project `VERA Issue 149 Workflow Reruns 20261002-kit-01` and
the owned output directory
`out/issue149-workflow-reruns-20261002-kit-01/`.

## Scope and exclusions

The actor owns the execution parameters, immutable dispatch receipts, and
native captures below the named output directory. Each native action is one
hash-bound Workflow Integration dispatch, with a unique `actionId`, a receipt
written before Hammerspoon invocation, and a complete pre/post pair when the
project is available.

The actor does not edit the harness, launcher, analyzer, macros, contracts,
fixtures, accepted evidence, Issue 141 material, roadmap state, or Git state.
It does not use Console, `scriptapp`, an external scripting bridge, or a UI
fallback. Hammerspoon is only the approved exact-menu dispatch mechanism.

## Preconditions

| Gate | Observation/status |
| --- | --- |
| Resolve | Running; currently at Project Manager with no loaded project |
| External Scripting | Must remain `None` |
| Accessibility | Hammerspoon accessibility permission observed true |
| Hammerspoon | `/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs` |
| Workflow Integration files | Not installed or staged at record creation |
| root approval | Required exact harness and launcher source hashes before install, stage, or launch |
| output | `out/issue149-workflow-reruns-20261002-kit-01/` |

Producer-confirmed source hashes for this run:

- `harness.py`: `c17f8a4aa7b04aa8a3a20dcbb0d9c78ca93480ac15082b5cb8f9d9ed31328152`
- `launcher.py`: `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`

The one approved initial menu check ran after installing the unique launcher
entry. Resolve was found, but the exact `Workspace → Workflow Integrations →
VERA Issue 149 Workflow Reruns` item was unavailable (`menuFound: false`,
`menuEnabled: false`). The retained capture is
`out/.../dispatches/context-01-menu-check.json`. Per the dispatch guard, no
context launch was attempted and no retry is allowed without a new root
approval after the menu becomes available.

No installation, staging, project creation, menu dispatch, file swap, relink,
render, or UI action is permitted until root records the approved source and
launcher hashes in this record or an attached dispatch receipt.

## Prepared inputs

The generated media kit is hash-checked and the same-layout audio-preserving
W6 replacement has passed the fixture gate. The canonical media hashes are
retained in `fixture-record.md`. The native prepare action must import only
the hash-pinned entries selected by root under `out/.../media/`.

W4 requires the non-frame-aligned `clicks.wav` to make its impulse timing
criterion observable. Root approved importing it for the native W4 timeline;
its hash is pinned in `params/template.json` and the literal prepare params.

## Planned dispatch order

The IDs below are templates only. Root assigns a fresh safe suffix for every
dispatch and records the exact config and result in `out/.../dispatches/`.

1. `context-01-*`: read only Resolve version and current project name.
2. `prepare-01-*`: with Project Manager still showing no current project,
   create the exact project, apply 25 fps / 1920x1080 / 48 kHz, and import the
   approved media set.
3. `build-01-*`: create the configured W1–W7 timelines and retain their UIDs.
4. W1: one `w1-subtitle-request-*` per source timeline, followed by a bounded
   `w1-subtitle-poll-*` after each request settles.
5. W2: operator sets M/S on the Edit page; one `w2-export-*` per declared
   timeline/state, with no API ownership of those controls.
6. W3: `w3-mapping-mute-*`, render polling, then
   `w3-mapping-restore-*` with an explicit allowed-difference list.
7. W4: `w4-speed-*`, OTIO export and one render; poll only by
   `render-poll-*` after the one StartRendering call.
8. W5: `w5-context-read-*` with current/inactive timeline UIDs and restored
   current selection.
9. W6: `w6-before-swap-*`; root performs the byte-only same-layout swap;
   `w6-after-swap-*`; then `w6-relink-render-*`; root owns restore and relink.
10. W7: `w7-lock-setter-*`; root performs the exact selected-clip Delete
    Selected menu attempt; `w7-unlock-*` runs after the menu result.

Each timeout or unknown native result remains pending and is collected
read-only. No mutation is repeated automatically. Render polling is bounded
per tool call and never calls `StartRendering`.

## Evidence locations

- `params/`: offline configuration template and root-approved filled params.
- `dispatches/`: pre-dispatch receipts, Hammerspoon launch records, and
  collected result references.
- `evidence/<actionId>/`: harness journal, `pre.json`, `post.json` (or
  partial post), and action result as written by the injected harness.
- `progress-<actionId>.jsonl` and `vera-issue-149-workflow-reruns-result-*`:
  launcher progress and one result per action.

## Producer acceptance checklist

- [ ] Root confirms exact harness and launcher hashes before staging.
- [ ] New project name and `External Scripting=None` are visible in the
      retained context/prepare evidence.
- [ ] W1–W7 each have a complete result, declared queue deltas, and native
      pre/post evidence; W1 has status completion polls before the next request.
- [ ] W6 has same-layout stream evidence, failed pre-relink render, decoded
      `src_id=2` post-relink render, and root-owned restoration evidence.
- [ ] W7 has proven selected UIDs/all-track locks, a false
      `SetClipEnabled(False)`, unchanged item count, and unlock evidence.
- [ ] Offline analyzer and producer review classify every W row as reproduced,
      adverse, unknown, or harness failure.

## Current status

Offline preparation complete. The template remains non-dispatchable until root
approves the source hashes and action-specific fields. Literal context and
prepare/build params are ready for root review. The build params intentionally
use `videoTracks: 0` per the harness-owner request and remain native-blocked
until that validation change is frozen.

## Restarted initial context dispatch

After the user restart, the installed launcher matched the approved
`e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450` hash. The
exact initial menu check returned `menuFound: true`, `menuEnabled: true`, and
`triggered: false` for `Workspace → Workflow Integrations → VERA Issue 149
Workflow Reruns`.

Root-authorized `context-01-20261002-kit-01` was dispatched once through
`dispatch.py --initial`. Receipt:
`out/issue149-workflow-reruns-20261002-kit-01/dispatches/context-01-20261002-kit-01.json`.
The launcher disarmed the installed config before invoking the probe. Result:
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-context-01-20261002-kit-01.json`
with SHA-256
`1e2774ea02a4373617d3f9fb923ac7ad31679dd8bcc6fe7b4cb6c33a652cf064`.

The probe captured Resolve version `[21, 1, 1, 10, ""]`. The
`GetProjectManager` call was reached, then harness `_json_value` serialization
failed while inspecting the Resolve proxy as a `collections.abc.Mapping`, with
`TypeError: issubclass() arg 1 must be a class`. This is a harness
serialization failure; native Project Manager capability remains unclassified,
and no current project name was captured. The installed config remains
disarmed with `externalScriptingSetting: "None"`. The result status is
`failure`; no retry or prepare action was attempted.

## Serializer-fix context-02 dispatch

With root approval for harness SHA
`b76032dbab910bb985c554b3c3809de80b443e74ff59c3608f21a3c718f81193`, the
unique `context-02-20261002-kit-01` configuration was dispatched once through
`dispatch.py --initial`. Receipt:
`out/issue149-workflow-reruns-20261002-kit-01/dispatches/context-02-20261002-kit-01.json`.
The installed config was disarmed before probe invocation. Result:
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-context-02-20261002-kit-01.json`
with SHA-256
`7de80599e1f2ca272f48f0f1a3480f1cfa0c63e2e6461fe546491e34b25fce33`.

The probe captured Resolve version `[21, 1, 1, 10, ""]`, then failed before a
Project Manager value or current project name was captured with
`AttributeError: 'NoneType' object has no attribute '__name__'`. The result is
terminal `failure`; the config remains disarmed with External Scripting
`None`. No conditional prepare, retry, build, or W1–W7 action was attempted.

## Serializer-fix context-03 dispatch

With root approval for harness SHA
`b6b5ac1d5159cc45b4260ea5a200b3beb4e5df96189c4088e97b472cfe7b97a3`, the
unique `context-03-20261002-kit-01` configuration was dispatched once through
`dispatch.py --initial`. Receipt:
`out/issue149-workflow-reruns-20261002-kit-01/dispatches/context-03-20261002-kit-01.json`.
The installed config was disarmed before probe invocation. Result:
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-context-03-20261002-kit-01.json`
with SHA-256
`388492f04f0a8cdad4aee206ff0ac2e163928b43f14e90e606f2a685b02212a1`.

The probe completed successfully with Resolve version `[21, 1, 1, 10, ""]`
and current project name `"Untitled Project"`. Because the current project is
not `None`, the conditional prepare gate is not satisfied. The config remains
disarmed with External Scripting `None`; no prepare, retry, build, or W1–W7
action was attempted.

## First prepare dispatch

With root approval for harness SHA
`b0ea4ddfa84d7e63e1aff1d909610f703f7934e92164b93075c6596f97bdabd3`,
`allowEmptyUntitled: true`, and the reviewed ten-file media set, the unique
`prepare-01-20261002-kit-01` configuration was dispatched once through
`dispatch.py --initial`. Receipt:
`out/issue149-workflow-reruns-20261002-kit-01/dispatches/prepare-01-20261002-kit-01.json`.
The installed config was disarmed before probe invocation. Result:
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-prepare-01-20261002-kit-01.json`
with SHA-256
`6c6dabd10e190dd11586b10e915dd844a66e20896235e047a9b7ce417de58ed5`.

The strict startup guard passed: `Untitled Project` had zero timelines,
no current timeline, no render jobs, was not rendering, and had empty root
clips/subfolders. `CreateProject` returned the new project UID
`1a05ff3a-8b04-43e3-95ab-c970b93b6415`; `SetSettings` returned true. The
post-partial getter reported frame rate `25.0`, resolution `1920x1080`, sample
rate `48000`, but read-only `timelinePlaybackFrameRate` remained `"24"`, so
the harness stopped before media import. Media UID count and timeline/item
counts are all zero; `pre.json` and `post-partial.json` are complete captures.
The terminal result is `failure`; no retry, build, or W1–W7 action was
attempted.

## Saved producer pause checkpoint

`save-checkpoint-01-20261002-kit-01` called `ProjectManager.SaveProject()` exactly once and returned `True`. Terminal result SHA-256: `d3b6612878ec9cdcbf7a68102dde5a2049029b438745c04e2cfb4490822b531a`. Complete pre/post captures were byte-identical, SHA-256 `ab8cedc21293de77bb12e8835dfd0d420edb6af411393f38e99144e9b46eb0c9`. The verified project UID is `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; both captures contain zero media items, zero timelines and zero occurrences. Configuration is disarmed. Verification is retained at `out/issue149-workflow-reruns-20261002-kit-01/pause-checkpoint-verification.json`. No W test has run; W1–W7 remain pending.

Paused at the producer’s explicit request. No further launches, preparation retries, settings fixes or W development should occur until the producer resumes. On resume, address the retained timeline/playback-rate precondition and finish the outstanding harness corrections before native W tests. The issues remain open and unaccepted.

## Resumed native chain and current status

The preceding pause is historical. Root later approved and completed the
remaining native chain in the same disposable project under the retained
`External Scripting=None` guard. W1 linked-cut, picture-only-cut, and disabled-
A1 subtitle requests each settled with their required item evidence, save
checkpoint, and attributed render. W3 mute/restore and the later Edit-page
repeat completed with exact single-path deltas and restored mapping. W4
embedded speed completed its OTIO/render pair; the separate-source speed
case retained its reciprocal link and intentional retime state. W6 completed
the original guard, ALT byte swap, pre-relink render, relink render, original
byte restoration, restored render, and a final SaveProject checkpoint.

W6 final evidence includes original `swap.mov` SHA-256
`164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036`,
restored render `W6-restored-01.mov` SHA-256
`8e4c2fed0c9afeb9373e2ee8a75d7ddc0a4c9588685b9ec841189dea0afb8d78`,
and `save-checkpoint-w6-restored-01-20261002-kit-01` returning true exactly
once. The installed configuration is disarmed after each action.

The current bounded package is W7 under harness SHA
`a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5`,
launcher SHA `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`,
and exact-menu helper SHA
`6fafe12a946dfad139c0bd469f6d254337ee2bcfa2ddad0a576ff5c7e27ef054`.
The next action is the approved W7 Edit-page timeline/timecode selection,
followed by one each of the named focus, deselect, and nearest-clip menu
receipts. Lock/delete/unlock remain gated on adjacent selected-clip reads,
complete snapshot equality, owned UID proof, and all-track lock readbacks.

## W7 completion

W7 selected timeline `14a27cb4-0ecd-4daa-9e90-38c1ff12bdb5` (`W7-lock`) on
the Edit page at `00:00:02:00`. The named helper calls were issued once each
for Timeline focus, Deselect All, Select Nearest Clip/Gap, and Delete Selected.
The observe pair retained two native `GetSelectedClips()` returns containing
the expected V1/linked UIDs
`df179a83-7455-4184-a909-0bbbac2500bd` and
`abd3e5f5-c209-491d-84b1-d82a87e770a2`; canonical complete snapshots matched
after ignoring only volatile proxy addresses. All four tracks were initially
unlocked, then the lock setter read back all four locked and
`SetClipEnabled(False)` returned false with four item UIDs unchanged.

The single Delete Selected receipt carried locked proof SHA
`4cf171973a89329a32dab2c281709b8af3792fd845e811bd185291b5862a73c0`.
The after-menu observe proof retained four unchanged item UIDs, unchanged
selected UIDs, and unchanged `GetClipEnabled=True` values. The unlock action
restored all four pre-unlocked tracks. `save-checkpoint-w7-01-20261002-kit-01`
called SaveProject exactly once and returned true; the installed configuration
is disarmed. Native W7 work is complete and held pending the operator's manual
W2/W5 setup request.

## Producer-requested stopped checkpoint

The producer replied **both off**, then requested **stop at checkpoint**. The existing neutral-Y render settled Complete at100%; its output SHA-256 is `3284339a0cd2c675af276d34ff1540c36c784bb34311ed3bd792234c938662b1`. Neutral Y OTIO SHA is `0ca7911b5c4b5b8712e212badcdd153a94ac7e8a43510bb73aa65d7570031379`, with Audio1/2/3 enabled and SoloOn false. X mute-off is producer-attested and its owned context was restored; a neutral X export/render was intentionally not started after the stop request.

Final context is W2-Y-solo UID `bec69cf7-c76e-4820-9e1f-9b425449614f`, Edit page, `00:00:15:24`. `save-checkpoint-w2-restoration-stop-01-20261002-kit-01` called SaveProject once, returned True, and has terminal result SHA `c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb`. The native actor confirms all known render jobs terminal, installed configuration `__disarmed__`, and stopped. Inventory remains13timelines/64items/23media. W4 retime state is intentionally retained. No old #141 project or protected producer clip was modified.

Six W rows are independently reviewed; five published. W5 publication and W2 retained neutral-media analysis/final result consolidation remain pending. Neither issue is accepted or closed. The recurring ten-minute follow-up is paused. Resume from retained evidence, without replaying completed actions.

## Final neutral-X resume guard

After the producer resumed with **both off**, the native actor first attempted
the required fresh observe. The first unique config,
`observe-final-both-off-03-20261002-kit-01`, was rejected inside the injected
harness before any Resolve API call because the config accidentally omitted its
required `phase`; the terminal result is
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-observe-final-both-off-03-20261002-kit-01.json`
with SHA-256
`c3db0f50a8f95bc225be5801963addaca87278ffdf9d5ca315ffe55e93af44c4`.
This is retained as a harness/configuration failure, not a Resolve result. No
native mutation occurred and the action was not replayed.

A corrected, unique observe config was validated by the frozen launcher and
dispatched once as `observe-final-both-off-04-20261002-kit-01`. Its terminal
result is
`out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-observe-final-both-off-04-20261002-kit-01.json`
with SHA-256
`83e21501465419330e66e2305b8efb68acb32497ffac341c07f484ee8a00dfb3`.
The complete pre/post pair confirmed the named project UID, 13 timelines, 64
timeline items, 23 media-pool items, Edit page, current timeline
`W2-Y-solo` (`bec69cf7-c76e-4820-9e1f-9b425449614f`), no active render, and
the prior queue as terminal. It also read the current timeline's
`GetCurrentTimecode()` as `00:00:00:00`, while the saved checkpoint and the
bounded final context requirement were `00:00:15:24`.

Because the required current-context/timecode guard did not match, the actor
stopped immediately and did not dispatch the neutral-X export, render, poll, or
final SaveProject. No unrelated drift was corrected and no retry was issued.
The prior verified save checkpoint remains authoritative; the neutral-X row is
still unrun, and the #149 issues remain open pending the producer's decision
about the playhead discrepancy.
