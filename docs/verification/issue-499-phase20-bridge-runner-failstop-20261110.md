# #499 Phase 20 recovery — Mac Bridge process-lifetime fail-stop

2026-11-10, ~11:45–11:50 UTC. **BLOCKED**, not M4 acceptance.

## Recovered source and previous native state

- Read `.pipeline/499/progress.md` first, then checked the adopted original PR
  #474 worktree status, diff summary and last five commits. The branch was
  clean at `98b4ce00`; the frozen production repair is `0e48fd29`, source
  graph `9b5738df656d8a100ab867b104f0eaef2bb389c51d638b471c8f67d1d3896a4a`,
  and pinned one-command Roll actor
  `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`.
- Previous physical-Mac Phase 20 evidence (in
  `issue-499-phase20-launch-context-blocked-20261110.md`) records **0/4
  authenticated original M4 receipts** and strict #312 **NOT RUN**. The five
  prior sacrificial roots contain blocked/UNKNOWN or unstarted attempts; they
  must not be resumed or replayed. No fresh project, campaign, signed receipt,
  or case-bound authorization was created in this recovery.

## New safe diagnostics

- Mac Bridge `mac_health` returned OK; `mac_trust_status` was inactive. Ordinary
  per-command execution remained available without broad machine-wide trust.
- At `2026-11-10T11:45:55Z`, the physical Mac reported Resolve PID 3376 and
  no matching `vera499` or ResolvePython native worker. A read-only Bridge
  `osascript` query of System Events successfully counted 64 processes, with
  exit status zero. This verifies that the immediate, short-lived Bridge
  ancestry has OS access; it does **not** authorize any other ancestry.
- One new **no-effect background-process probe** was started through the
  bridge. It reported child PID 6591, then exited without writing even the
  initial marker to its private `/private/tmp/vera499-probe-dc54.log`;
  subsequent read-only process inspection confirmed the PID was absent.
  That probe contained no Resolve operation, project selection, Roll, render,
  authority or native M4 call.
- Read the installed bridge's `shell_core.py` directly. Its `execute_bounded`
  uses `subprocess.Popen(..., start_new_session=True)` and calls
  `_kill_group(proc)` **unconditionally after the command returns**, plus on
  timeout/output cap. The public `mac_exec` cap is 35 seconds. Thus `nohup`
  or ordinary shell backgrounding inside that tool cannot provide a durable
  runner; defeating that cleanup is not an acceptable safety workaround.
- Prior physical-Mac evidence independently showed a Terminal-launched
  System Events permission probe returning TCC status `-1744` even while
  Bridge-chain permission passed. A launchctl read-only probe hung before
  reporting permission. These are not substitute trusted launch ancestries.

## Decision and safe continuation

**STOP without native effect.** A one-use four-stage real M4 with the single
327→351 Roll must not start through an unverified or deliberately bounded
launcher. The valid next step is a genuinely persistent, approved Mac execution
ancestry that independently proves no-prompt System Events Automation/TCC,
Accessibility, exact foreground/Edit page/menus and safe one-start lifetime.
This may require the Producer to authorize Terminal Automation in macOS or a
separately reviewed explicit durable-job facility; do not bypass OS or Bridge
authorization boundaries.

Only **after** that facility is proved with a non-effect probe should the
next phase-20 recovery recheck exact frozen source, storage, media provenance,
owner lock and host readiness, create **two new** unique sacrificial SDK
target UIDs under a new root, bind a fresh case-specific short-lived Producer
authority, and start one authentic pristine→edited→revision→distinct rebuild.
On any UNKNOWN/partial effect stop permanently on that case. Four independently
verified signed receipts and strict #312 are still required to admit Phase 21.

No old native root, historical project/UID, signed stage or other agent session
was modified or replayed. No full `validate:fast`, PR push/merge, #473/#312/#313
promotion or Phase 21 advancement occurred. The only new artifacts were the
harmless private probe and this documentation.
