# #499 source-backed recovery plan: phases 12–21 (2026-11-09)

**Producer-directed #499 extension; use Zodex and the EXISTING adopted PR #474 only.** This amendment replaces the unstarted old phases 12–14 and extends the plan to 21 total phases, preserving original phases 1–11 verbatim. Source of truth for the full per-phase **goal** and **done** contracts is [issue-499-conductor-plan-21.json](issue-499-conductor-plan-21.json). Conductor must reconcile its live ticket phase/index and full phase array with the retained plan before any nudge/recovery. The old phase 11 was BLOCKED (not falsely marked as passed), then a separate physically approved single-Roll calibration supplied new evidence; record this as supersession, not as M4 4/4. Do not replay historical tests.

## Evidence anchors and qualified conclusions

- Local adopted HEAD before this planning-only commit: `b613cab5b960ce0d750fd33ef9e598fb4f67ae05` (earlier calibration `b6e083b6`). Those commits and the on-Mac private calibration records are **local**; the external Opus reviewer did not have access to them, and the remote PR474 head may differ. Do not claim Opus independently reviewed the physical result or that the calibration is a production M4 receipt.
- Physical Mac calibration was expressly authorized for **one** disposable `VERA Delivery 75ba39c0-4c56-4d85-ac88-58f0092163a8 c191e694fc19`; a single literal `Trim > Roll > Start to Playhead` at frame 351 yielded a 327→351 boundary, preserved original left/right UIDs, unchanged nine other clips, save/close/reopen geometry readback. It used **synthetic moving H.264** sources, not the production synthetic-312 held-still M4 fixture. Reported raw right `sourceStart` 0→24, *not* permission to change the held-still verifier. One-use intent spent, no second Roll.
- Exact physical calibration private evidence: `~/.local/state/vera/issue-499-one-roll-75ba39c0-v2/{pristine.json,roll-intent.json,post-roll-observation.json,reopened.json}`. Retain originals and hashes; export only redacted/source-digested technical observations. An earlier v1 provisioning guard refused on SDK root folder `""` before CreateProject; it is not an extra Roll/approved target.
- **User has quit Resolve and disconnected the external drive.** Do not auto-launch Resolve in phases 12–18, and do not assume `/Volumes/Family 1A` exists. Last read-only Mac internal free was about **15 GiB** (volatile), so all storage thresholds and input dependencies must be freshly measured. Remaining ResolvePython helper processes do not prove the GUI is open. Do not kill or change them blindly.
- Current #491 product exception approved the old **24-nudge GUI actor**; single-command production integration changes transport and requires independent reviewed fixed script plus **fresh explicit M4 Producer case authorization** after source/target freeze. The prior one-use calibration authorization is spent and does not authorize a new four-stage native campaign.
- Respect the required **original PR474 adoption/lease**; no new PR, push, merge, issue closure or starting/restarting #312 by the phase agent. Conductor alone checkpoints/merges when verified. #473→#312 (continue adopted PR323)→#313 remains gated.

## Execution sequencing: no-drive-first, physical-last

| Phases | Workstream | Can advance now with Resolve quit and drive detached? |
|---|---|---|
| 12–14 | Forensic native evidence, all four source-in gates, fixed read-only SDK observer | **Yes**, code/evidence only; physical SDK call deferred until safe Mac re-entry |
| 15–16 | Single named Roll actor, one-start M4 host and strict source contract | **Yes**, no GUI/native edit; use original adopted branch |
| 17 | Bounded focused fault-injection, independent source review | **Yes**, **not** repository-wide tests |
| 18 | Internal-only media/storage capacity and input provenance | **Yes**, readiness audit; **fail closed** if authentic sources or reserve unavailable |
| 19 | Resume Studio safely, raw clip SDK readback, source freeze and NEW authority | **Only with verified safe app state, no-drive sources, free space and required Producer consent** |
| 20 | ONE newly authorized original M4 4/4 with MOV/PCM and strict #312 verifier | **Only if phase 19 GO**, independent source/one-use/owner/target guards |
| 21 | **After native GO**, full `validate:fast`, original PR exact-head CI/review/Conductor merge | **Only if phase 20 genuine 4/4 and strict #312 pass** |

## Stop/continue rules

1. Phases 12–17 progress unattended with bounded evidence and **focused tests only**. Missing raw source times become a deferred question, **not** permission to alter the verifier. Never ask Producer to reconnect the drive for code-only investigation.
2. Phase 18 must inventory all actual paths and peak disk use. If external-dependent source media is unavailable or internal free/required reserve is insufficient, record exact `BLOCKED: MEDIA_OR_SPACE` with paths/bytes. Do **not** create a fake mount directory, delete existing archives, run unbounded output or consume M4 authority.
3. Phase 19 verifies the vendor SDK on the single previously saved calibration **read-only**, if safe without altering any Producer project; source-match all host code to one frozen graph; then bind a **new** case-specific M4 authorization to unique source/target/actor IDs. If unavailable, stop without native effects.
4. Phase 20 is the **only** production M4 effect phase, with one GUI Roll, no replay. Genuine native full M4 4/4, MOV/PCM and strict #312 independent verifier are non-negotiable.
5. Phase 21 is deliberately the **first broad code validation** phase, as Producer requested. No build/test status is promoted from a previous SHA; exact native evidence and original PR lease must match. Any source graph mutation after native sealing requires re-analysis and fresh authorization, not receipt relabeling.

## Handoff

Per phase: read `.pipeline/499/issue.md`, `adoption.md`, `plan.json`, `progress.md`, exact original PR, then `git status/log`; use existing `.worktrees/pipe-499`. Finish **only** current phase, commit source/doc changes, write `handoff.json` with `status:"phase-done"` and correct 1-based phase. Conductor maintains the original PR and next-phase launch. On any blocked native stage, record `blocked` with evidence instead of writing a false pass, and leave downstream issues gated.
