# Issue 149 Workflow discriminator verification

**Task ID:** `/root/discriminator_verify` — bounded independent verification of the five Workflow Integration discriminator cases requested for Issue 149.

## Verification status

The offline verification gate passed. No Resolve launch, Hammerspoon dispatch, Workflow Integration invocation, native mutation, Console action, Fairlight action, render, or file swap was performed by this verifier. The five native cases remain unverified until the native actor produces complete retained evidence.

The frozen source hashes are `harness.py` `5663ec6cd01ae119846281d384b4db02faa82ca508890a80b952324c314fe24a`, `launcher.py` `a605b875e0755151e1fa03e91a61612fecbf5058f3fb12a67ac6216e6536e2e9`, `dispatch.py` `47534d06e5742e0875b63085072ac983d7b27b5d708b1954a2ed6e00c362224b`, `hammerspoon-launch.lua` `31fa92f6ede8a29d82ab4dfa227a8e39ab6be5fb950e022afa0424bc226565fb`, and `console-render.py` `2946c63991c07b16e3c7af68389f1379fe433789cb95043ee9df045f0cfd880f`.

## Acceptance surface checked

The review used `task-brief.md`, `evidence-review.md`, and the Phase 10 procedure in `codex-rerun.md`. The required surface is:

- a new disposable synthetic project with External Scripting set to `None`;
- two W6 cases using same-layout video plus mono audio: atomic replacement with the old modified time retained, and atomic replacement followed by a demonstrably new modified time;
- three W3 cases on separate fresh timelines: Workflow Integration mute then Workflow Integration render without a prior baseline, Workflow Integration mute followed by an operator Console render without remapping, and Workflow Integration mute followed by an operator Fairlight-page/playback action and then Workflow Integration render;
- a complete before/after snapshot pair for every mutating phase, exact mapping getter readback and restoration, attributed render job/output, measured output SHA-256, A2 1500 Hz pilot level, and number-word presence;
- no audio-less replacement, no retained #141 project, no `semi1b.mp4`, no `scriptapp` bridge, and no generic UI automation as the test mechanism.

## Offline checks performed

Commands, run from the discriminator worktree, were:

```text
python3.14 -S docs/investigations/issue-149/workflow-discriminators/harness-check.py
python3.14 -S docs/investigations/issue-149/workflow-discriminators/discriminator-check.py
```

Both completed successfully and reported that no native application was launched.

The checks exercised fake native objects and temporary files only. They verified the following guards:

- configuration is bound to the exact disposable project name, `externalScriptingSetting: "None"`, owned output directory, hash-pinned probe and launcher sources, and unique action/state identifiers;
- the Workflow Integration launcher contains no `scriptapp` fallback and uses the installed DaVinci Resolve Workflow Integration Plugins path;
- the render path uses documented `SetCurrentRenderMode`, fixed MOV/H.264 settings, 25 fps, 48 kHz/16-bit audio, and attributable queue results;
- creation guards reject an unexpected current project, UID mismatch, existing timelines, active rendering, or an unowned project;
- W3 accepts only a target-only mapping mute delta, records getter readback, and restores the exact held original mapping;
- W6 rejects a replacement marked without audio or with non-mono audio and checks the current file hash before and after replacement;
- the fixture builder preserves linked and separate audio geometry and the fixture render/failed-render branches classify terminal native outcomes without retrying a timed-out or failed job;
- snapshot collection captures project, timeline, track, item, media-pool, current-page, current-timeline, selection, settings, and render-queue state, while recording current-timeline-only getter context instead of silently treating unavailable non-current values as facts;
- one dispatch creates an exclusive receipt, disarms the configuration before native mutation, binds result attribution to the action ID, and refuses duplicate or pending dispatches.

The D3-console helper is `console-render.py`. Its documented injected-object command is the single `CONSOLE_CONFIG_PATH=...; exec(open(".../console-render.py").read())` command in `plan.md`. Its source guard requires the exact project, timeline UID, owned project UID, output directory, `externalScriptingSetting: "None"`, and an armed unique action ID. It does not call `SetSourceAudioChannelMapping`, `scriptapp`, or any remapping operation. It creates an exclusive progress/evidence path, atomically disarms the config before native render calls, captures `pre.json`, uses `SetCurrentRenderMode(1)` and the fixed render settings, starts exactly the returned job ID, polls that same job, and captures `post.json`. A prior result/progress file, wrong injected object, or invalid guard refuses the action.

The fixture preflight also passed its static requirements: `base.mov`, `relink_alt.mov`, and all W6 copies have H.264 video plus mono 48 kHz PCM audio, each is 400 frames at 25 fps, and the W3 geometry is documented as V1/A1 linked plus A2 and A3 mono tracks over `[0,400)`.

## Native evidence still required

For each W3 result, the final report must state the classification (`reproduced`, `adverse`, `unknown`, or `harness failure`) and include the mute getter, pilot result against the `<= 0.001` silence gate, number-word analysis, render SHA-256, and complete snapshot pair. The restored mapping must compare semantically equal to the original after the owned restore phase.

For W6, the kept-mtime case must decode source ID 1 after `RelinkClips`; the changed-mtime case must decode source ID 2 after `RelinkClips`. The original replacement bytes and metadata must be restored and retained in evidence. Online status and Date Modified readbacks must be reported without treating them as byte identity.

Any native timeout, operator drift, missing injected object, incomplete pair, unowned project, unattributed render, or missing audio stream is an observation or harness failure until diagnosed; it must not be promoted to a Resolve capability limitation. A completed native result must be independently checked against the fixture manifest and actual render, rather than inferred from setter return values.

## Freshness and limits

This verification was performed before native dispatch and is therefore only a guard/readiness result. It does not confirm the W3 or W6 behavior, the modified-time design rule, or the relationship between Workflow Integration, Console, and Fairlight entry points. It does not replace the required producer review of Issue 149.
