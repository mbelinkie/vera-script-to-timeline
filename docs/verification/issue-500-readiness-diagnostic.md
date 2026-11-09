# #500 — independent read-only Resolve readiness diagnostic

**Evidence class:** code inspection + **unit-simulated** controls in this PR;
**NOT** a real Mac field test, native M4 acceptance, original #499/PR #474
verification or permission for an edit. The reported Nov 9 Mac observations
below are transcribed from the #500 issue; they were **not reproduced** by this
Linux Zodex worktree. No live Resolve GUI operations were performed here.

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

## Real-Mac truth table to reconcile, not to presume

| Production field | #500 issue's reported Studio 21.1.1.10 fact | Read-only OS query / trustworthy interpretation | Refusal when unobservable |
| --- | --- | --- | --- |
| Process + build | One `Resolve` PID; Studio 21.1.1.10 | `NSRunningApplication` exact bundle + PID, executable URL, app bundle version/build | Zero/multiple, stale PID, wrong build, wrong executable → fail |
| Automation | Original frozen JXA `Ref` → `-2700`; corrected binding and minimal Swift reported `OSStatus=0` | Real `AEDesc*` ABI and `askUserIfNeeded=false`, target `com.apple.systemevents`; independent Resolve control | Error, missing status, mismatch target or prompt flag → fail/unknown |
| Accessibility | AX trusted | `AXIsProcessTrustedWithOptions(prompt=false)` | Never open permissions dialog or promote untrusted AX |
| Foreground | `windowFrontmost=false` reported | `NSWorkspace.frontmostApplication` PID, not window existence | App not frontmost → fail; no activation attempted |
| Window | One correct project window; `AXMain=true`, `AXFocused=false` | `AXWindows`, exact `AXTitle`, independent `AXMain`, `AXFocused` | Main does not imply focused; unknown/focused=false blocks |
| Session/modal | No positive screen-unlocked proof | `CGSession` signals and read-only `AXChildren` sheet inspection | Console/login signals don't independently prove unlocked; unknown blocks |
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

## Real-Mac run and #499 handoff still required

The next phase must execute the exact diagnostic source on the **actual** Mac,
preserve stdout, stderr, exit code, installed app version and process identity,
inspect whether the Swift ABI compiles and really returns OSStatus, compare its
System Events target with the fixed original JXA binding, and repeat safe
positive/negative/control observations without GUI actions. A live status 0
proves only a narrow no-prompt permission query; it does not prove permission
to edit. If `AXMenuItemMarkChar`, accelerators or timeline/track identity remain
missing, return an explicit `unknown` and an actionable production/UI handoff
to #499, **not** a green readiness claim.

After the small #500 PR merges, #499 owns production-source changes and any
new exact-head source sealing; #499 must acquire genuinely valid fresh
case-specific native authority before effects. Only genuine original M4 4/4,
native save/reopen and independent strict verification may release #473;
then preserved #312 phase 2/5 and #313 follow existing dependencies. No
additional dependency is asserted here.
