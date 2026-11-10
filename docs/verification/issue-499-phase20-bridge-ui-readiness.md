# #499 Phase 20 — real-Mac no-effect UI readiness recovery

November 10, 2026. Original adopted PR #474 branch only. **No M4 effect,
one-use Roll, render or strict #312 acceptance is claimed here.** Earlier
native roots, UIDs and UNKNOWN journals remain unchanged.

## Physical Mac findings

- Studio **21.1.1.10**, PID `33770`, has one normal frontmost main window,
  no modal, `AXIsProcessTrusted=true`. Official read-only SDK independently
  returned page `edit`, project UID `174de7bf-860c-49d1-9f61-dfbab3f1b7cc`,
  timeline UID `355a1971-9260-4781-8ce0-a62103455364`, and no active render.
  These are **existing** targets, not authority for a new run.
- The exact no-prompt System Events TCC probe returned `0` when launched from
  the Mac Bridge chain, including a child shell. The same probe launched in
  Terminal returned **`-1744` (requires consent)**. An allowed Bridge-chain
  result cannot authorize a Terminal-chain campaign; no TCC setting was changed
  and no consent was prompted for or inferred.
- After starting ordinary System Events (it had been absent), the old JXA
  observer reached multi-menu checks but was terminated (`-9`) before finishing.
  The full `Workspace > Switch to Page > Edit` Qt AX selection mark is `null`,
  despite the independent SDK page being `edit`.
- A read-only AppleScript using the **same named menus as the fixed actuator**
  returned six successful presence/enabled checks, with no menu click. The
  revised actual Python `MacReadOnlyObserver().observe()` then executed on the
  physical Mac through the Bridge-chain pinned Python environment, returned
  Accessibility/Automation true, one exact main window, no modal, original
  keyboard preset, and `trimRollMenu=true` in **1.607 seconds**.

## Bounded fix and limits

The production observer retains exact AppKit PID, bundle, installed version,
frontmost process, AX trust, no-prompt numeric TCC `0`, one named `AXMain`
window and no modal. It now delegates only the named setup/Roll menu
availability to a **fixed read-only AppleScript**, bound again to the same
PID, bundle and window. The old Qt-selected-page, focus, track-mark and
accelerator fields remain `false`/`null`, never forged true. The production
M4 SDK stage itself verifies the Edit page and 11 native UIDs before and after
OS preflight; the unchanged hash-pinned actor sets absolute V1-only selection
and Normal Mode before one Roll. Any missing actor menu or consent fails closed.

Targeted unit, refusal and negative tests, Ruff and mypy are required on the
new exact source. **This is not a native M4 success** and must not promote
Phase 21. Before a genuinely new attempt, freeze exact committed source,
prove Mac source matches, recheck live storage/owner/source/media/UIDs and
session-specific Automation consent, create two **different new sacrificial**
SDK project/timeline targets and one bounded source-bound authority from the
Producer's distinct-attempt overnight authorization. Do not start the old
Terminal path with TCC `-1744`, replay a spent or UNKNOWN project, or waive
any native receipt/source/MOV/PCM gate.
