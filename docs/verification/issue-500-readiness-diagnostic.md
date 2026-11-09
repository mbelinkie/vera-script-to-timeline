# #500 — independent read-only Resolve readiness diagnostic

**Evidence class:** code inspection + unit-simulated controls in this PR,
**plus an actual-Mac read-only field test on November 9, 2026** using the same
byte-for-byte Python and Swift sources as this branch. **Not** M4 native
acceptance, original #499/PR #474 verification, permission for an edit, or a
claim that the application is ready. No GUI action or Resolve mutation occurred.

## Verified real-Mac field result

At approximately 07:34 Eastern on Nov 9, the Mac bridge invoked the diagnostic
from a separate disposable checkout at
`/private/tmp/vera500-diagnostic-de2b0e5f`. This scratch checkout contains the
phase-2 fixes but has **not** updated the Conductor's worktree or original
#499/#312 branches. SHA-256 of both executable source files was compared
between the Mac checkout and this branch, with **identical bytes**:

| Source file | SHA-256 (Mac and Linux match) |
| --- | --- |
| `scripts/resolve_readiness_probe.swift` | `18a7a6eb27f7866eb6107b6f22493225ca59aacb8e0aa6954b39091fa8689dbd` |
| `scripts/resolve_readiness_diagnostic.py` | `48aa81818bb49b3293ee4c09510fa11a798e4be8426cb63622e60e0d83d8487a` |

Command: `python3 scripts/resolve_readiness_diagnostic.py --timeout 30`
(no target title supplied). **Process exit 0, stderr empty**, JSON report
`evidence="actual-host"`, `hostVerified=true`, `errors=[]`, **`ready=false`**.
The Swift probe compiled and ran through this wrapper on the actual macOS SDK;
Linux's Mac-only `swiftc -typecheck` regression remains skipped there.
Raw stdout is preserved in `.pipeline/500/mac-readiness-actual-host.json`
(ticket evidence, not an automatically committed PR file).

The observed pinned process is PID `30415`, exact Resolve app bundle and
`/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve`,
`CFBundleShortVersionString=21.1.1`, `CFBundleVersion=21.1.10010` (**version
gate now passes**). Exactly one AX window exists, with `AXMain=true`, but
`frontmost=false` and `AXFocused=false`; AX is trusted without a prompt.
System Events no-prompt Automation status is **`-600`** while the Resolve
control query is **`-1744`**. Neither is silently substituted with the earlier
issue-reported `0` from another actor/target context; this actor's automation
readiness **fails**. Edit-page selection, V1-only targeting, actual timeline
focus, key accelerators, modal-free and unlocked-console status remain
**unknown**. The focused role is `AXGroup`/`group`, not evidence of timeline
focus; `AXMenuItemCmdChar` remains missing even for Save Project. Roll/nudge
items exist but are **disabled while Resolve is in the background**. No
separately approved expected window title was provided, so exact-window
identity also remains **unknown**, even though a window title was observed.

This is a **successful probe, failed readiness**. It neither unblocks native
editing on #499 nor counts toward its **0/4** authentic M4 receipts. For #499,
confirm Automation against the actual executing actor/target, explicitly
resolve genuine foreground/focus/project state and replace unreadable AX fields
with trustworthy evidence (or refuse); never infer success from menu defaults.
The next operation still requires its own exact-current source/target and
case-specific approval. No old operation may be replayed.

## Run on the actual target Mac

```sh
python3 scripts/resolve_readiness_diagnostic.py \
  --expected-window 'EXACT CURRENT DISPOSABLE PROJECT WINDOW NAME'
```

This invokes repository-owned `scripts/resolve_readiness_probe.swift` by path
and prints one JSON object. The Python wrapper has no arbitrary-command, custom
script, input-fixture, actuator or `--approve` option. `swift` compilation may
require Command Line Tools. There is no AppleScript/JXA activation, click,
keystroke, page/track switch, project save, receipt write or TCC prompt; only
`NSRunningApplication`/`NSWorkspace`, `AXUIElementCopyAttributeValue`,
`AXIsProcessTrustedWithOptions(prompt=false)`, `CGSessionCopyCurrentDictionary`
and `AEDeterminePermissionToAutomateTarget(..., askUserIfNeeded=false)` are
used. The exact Automation target is **System Events**, not Resolve; the second
Resolve TCC query is a **control**, not a substitute for System Events consent.

`evidence=actual-host` means the *read-only probe ran on macOS with a
well-formed report*. It does **not** mean `ready=true`, editor alignment,
native acceptance or producer approval. `ready` is derived entirely from
explicit checks and deliberately remains false where APIs cannot prove the
required state. `evidence=probe-error`/`not-run` means no valid host observation.
The `raw` object contains exact observed values, including absent (`null`)
AX fields. No data is changed. The analysis is intentionally stricter than a
UI state guess: unknown is not pass, and AXMain is not AXFocused.

## Real-Mac truth table (observed facts versus trustworthy checks)

| Production field | Real-Mac observation (issue history where specified) | Read-only OS query / trustworthy interpretation | Refusal when unobservable |
| --- | --- | --- | --- |
| Process + build | PID 30415, version `21.1.1`, build `21.1.10010`, both pass | `NSRunningApplication` exact bundle + PID, executable URL, app bundle version/build | Zero/multiple, stale PID, wrong build, wrong executable → fail |
| Automation | Actual System Events `-600` (fail); Resolve control `-1744`; issue previously reported `0` in a different query | Real `AEDesc*` ABI and `askUserIfNeeded=false`, target `com.apple.systemevents`; independent Resolve control | Error, missing status, mismatch target or prompt flag → fail/unknown |
| Accessibility | AX trusted | `AXIsProcessTrustedWithOptions(prompt=false)` | Never open permissions dialog or promote untrusted AX |
| Foreground | `frontmost=false` (fail) | `NSWorkspace.frontmostApplication` PID, not window existence | App not frontmost → fail; no activation attempted |
| Window | One project window, `AXMain=true`, `AXFocused=false`; exact approved target not supplied | `AXWindows`, exact `AXTitle`, independent `AXMain`, `AXFocused` | Main does not imply focused; unknown/focused=false blocks |
| Session/modal | No positive screen-unlocked proof | `CGSession` hints and read-only direct-child `AXSheet` detection | No direct sheet is **unknown**, not proof no nested modal exists; console/login do not independently prove unlocked |
| Edit page | `editPage=false`; `AXMenuItemMarkChar` absent | Query `Workspace → Switch to Page → Edit` mark; enabled is only available, not selected | Missing mark → unknown; never guess active page |
| Timeline focus | `timelineFocused=false`; AX focused element described `group` | AX focused element role/description/ancestry | Generic group/description is not timeline proof → unknown |
| V1-only targeting | `v1Only=false` | Menu inventory for `Auto Deselect All Tracks` and `Auto Select/Deselect V1` | Enabled menus don't reveal all selected tracks → unknown |
| Roll menu | `trimRollMenu=false` | Read `Trim → Select Nearest Edit To → Roll` presence/enabled | Missing/non-readable path → unknown; enabled is only menu capability |
| Nudge menu | `nudgeMenu=false` | Read `Trim → Nudge → One Frame Right` presence/enabled | Missing/non-readable path → unknown |
| Timeline accelerator | `AXMenuItemCmdChar` absent for timeline focus | Read key **and** modifier bits | Absent key/modifier → unknown; do not assume Cmd+4 |
| Nudge accelerator | `AXMenuItemCmdChar` absent; Save Project control also absent | Read menu key **and** modifier bits | Absent even on control menu means AX exposure may be limited; never fill from defaults |
| `keyboardFocus`, `keyboardNudge` | Both null | Menu attributes are observations, not proof of effective user keymap | No keystroke to validate, no fabricated effective binding |

These observations concern the original #499 actor/source only as **reported in
the issue**; this diagnostic does not read or modify #499's worktree, sealed
hashes, native receipts, case-specific authorization, or original PR.

## Phase 2 verification and #499 handoff

This worker runs in a Linux container, **but performed the Mac test through
the connected Mac bridge**. Source file hashes matched; Mac diagnostic stdout
and return code are preserved above. The live run did **not** supply a separately
approved window identity, and it was run while Resolve was not foreground;
those are real fail/unknown states, not passed acceptance. Additional
context-specific read-only checks must be run by #499's actual native actor
before a physical effect, including the exact current project window and
System Events TCC target; preserve all null and false AX evidence. No probe
invocation authorizes GUI navigation, native edits, source resealing or receipts.

A live TCC status 0 proves only a narrow no-prompt permission query, not
permission to edit. If `AXMenuItemMarkChar`, effective accelerators or
timeline/track identity remain missing, return an explicit `unknown`. #499
must distinguish a verified production-code correction from a UI state that
requires the operator to focus/select Edit and the actual timeline, then
validate an exact-current source/target and obtain genuinely fresh case-specific
authority before any native effect. **Do not turn these absent read-only
observations into a green readiness claim.**

After the small #500 PR merges, #499 owns production-source changes and any
new exact-head source sealing; #499 must acquire genuinely valid fresh
case-specific native authority before effects. Only genuine original M4 4/4,
native save/reopen and independent strict verification may release #473;
then preserved #312 phase 2/5 and #313 follow existing dependencies. No
additional dependency is asserted here.
