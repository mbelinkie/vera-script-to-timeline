# #503 A / #499 phase 5 of 9 — read-only Studio UI evidence matrix

**Scope:** original adopted PR #474, branch `zodex/499-adopt-pr474`; code and
injected observations only. This matrix does **not** authorize an SDK page
change, a GUI event, TCC changes, a project selection, or native acceptance.
The original fresh M4 campaign remains **0/4**; the previously signed trial and
Producer consent are not usable for a changed source graph.

## Source and observation boundaries

- **Physical Mac (retained evidence, not re-executed in this phase):**
  `.pipeline/499/phase5-systemevents-focus-evidence.md`,
  `phase5-batched-ax-optimization-evidence-20261109.md`,
  `phase5-serial-baseline-and-mac-20261109.md`, and the #500 diagnostic
  handoff. The actual Studio 21.1.1.10 process was PID 30415, bundle
  `com.blackmagic-design.DaVinciResolve`, path
  `/Applications/DaVinci Resolve/DaVinci Resolve.app`, version `21.1.1`,
  CFBundle build `21.1.10010`. These are *historical* observations, never a
  current-process or fresh disposable-target certificate.
- **Read-only OS:** current
  `python/vera_timeline_agent/resolve_test_bench_ui_readiness.py` uses
  `NSWorkspace` for PID, bundle, path, version, frontmost PID and
  `AXIsProcessTrusted`; a no-prompt Automation query and PID-matched
  `System Events` for the actual window and menu. A System Events read
  occasionally took more than the 12-second timeout. Timeout means refusal.
  The separate existing foreground activator is **not** a read-only action and
  was *not called* here.
- **Read-only SDK:** retained actual Studio `GetVersion()` was
  `[21,1,1,10,""]`; actual `GetCurrentPage()` was `deliver` on the producer's
  *pre-existing* VERA Delivery project. `GetCurrentPage()` establishes the
  SDK page, **not** AX menu selection, timeline keyboard focus or track
  auto-select. `resolve_test_bench_edit_probe.inspect_selected`, the
  `GetCurrentProject`/`GetCurrentTimeline`/`GetUniqueId` calls, the signed
  capture and `prepare_owned_f1_inputs` contain the 11-item/six-track target
  checks. That code exists; **no newly selected authorized disposable SDK
  target has been verified**. `OpenPage('edit')` was not called or validated
  against the active 21.1.1.10 project in this phase. Existing older API
  integration is not a substitute for that version-specific test.
- **Original immutable script:** `resolve_gui_roll.ROLL_APPLESCRIPT` still
  contains `keystroke "4" using {command down}`, resolves process `Resolve`
  by name and performs a menu click on Edit before Roll. Its pinned SHA must
  **not** be silently changed in this phase. It does not observe a selected
  Normal Edit Mode or linked/dynamic trim/ripple state. An enabled menu item
  is not evidence that it is active.

## Actual facts: verified versus unknown

| Fact | Existing real-Mac evidence | Can phase A certify dispatch? |
|---|---|---|
| Exact app PID/bundle/path/build | Verified *at observed time* via NSWorkspace and OS/version; PID 30415 | **No**: must be re-read for fresh signed target immediately before effect |
| Frontmost app and process identity | One observation matched PID; focus transitions sometimes failed | **No**: PID/process must be rechecked after activation and before effect |
| Window count/title, no sheet | One exact named main window; AX sheet observation exists | **No**: name resembles a producer project; SDK UIDs and fresh owner required |
| `AXMain` | Reported `true` on existing window | **No**: does not imply `AXFocused` or timeline focus |
| Window `AXFocused` | Reported `false` even with correct foreground PID | **BLOCKED**; no implicit coercion |
| Process `AXFocusedWindow` | AppleScript returned same window title; JXA AXUIElement conversion `-1700` | **UNKNOWN**: matching name is not proven AX object identity; requires real actor-level type/identity and AXMain proof |
| Accessibility / Automation | `AXIsProcessTrusted` true; no-prompt Automation changed with System Events actor liveness, sometimes `-600` | **No**: each actor and PID must independently recheck at use time; no prompt/grant allowed |
| Edit page | SDK returned **`deliver`**. Qt Edit and *currently active Deliver* menu marks both absent | **BLOCKED**: SDK `GetCurrentPage()=='edit'` would prove only page, once target-bound; AX marks cannot |
| Timeline focus | AX focused element role was a group, not `timeline`; Cmd-4 menu shortcut attrs null | **UNKNOWN**: must prove a safe substitute or refuse |
| V1-only auto-select | Qt V1/A1–A5 checkmark attributes absent | **UNKNOWN**: visible menu/enabled V1 alone never proves selected state |
| Roll/Nudge and Auto Select menus | Current JXA can ask whether item exists/is enabled, but was observed on Deliver/old project and is not evidence of correct mode/target | **UNKNOWN** for a fresh target; must recheck in one fixed script immediately before action |
| Active Normal Edit Mode | Existing actuator checks only `enabled`, not `selected` | **UNKNOWN**, not inferred from enabled |
| Linked selection / dynamic trim / ripple state | No trustworthy live SDK/AX state evidence in retained observations | **UNKNOWN**, cannot claim safe roll geometry pre-effect |
| Effective keyboard mappings | Owned default preset XML verified; Qt `AXMenuItemCmdChar/VirtualKey/Glyph` missing | **UNKNOWN**; preset files do not establish effective Cmd-4 or `.`; remove keyboard path only in reviewed phase C |
| Project/timeline identity and 11 UIDs/6 tracks | Signed source and exact UID checks exist in production; real Mac presently selected an existing producer project | **BLOCKED** until a new signed, approved disposable target is selected; name alone is insufficient |

## All eight Claude findings and disposition

These are from `.pipeline/499/phase5-claude-preparation-plan-review-result.log`.
Claude did not have access to one local AX evidence file; the observations
above are independently checked against retained OS/SDK logs and current code.

| # / severity | Finding | Verified or refused substitute; next owner/phase |
|---|---|---|
| 1 / HIGH | Qt omits AXFocused, Edit/V1 marks, timeline role and shortcut chars | **Confirmed**. Existing strict gate refuses. SDK page may eventually substitute *only* for Edit page, not focus/V1/mode. Phase B/C. |
| 2 / HIGH | Cmd-4 violates menu-only exception #491 | **Confirmed in fixed script**; cannot claim a live mapping. Phase C must remove/review or block, update #491 doc, re-pin SHA and require fresh source-bound authority. |
| 3 / MED | Actual executor targets process by name, not PID | **Confirmed**. Existing OS observer is PID-bound but GUI actor is not; phase C must check exact PID inside one fixed script before and during effect. |
| 4 / MED | SDK→OS→journal is vulnerable to SDK/target drift | **Confirmed**. Phase C requires SDK→OS→SDK same-UID/page/playhead/inventory bracket before journal and source-bound 5-second attestation. |
| 5 / MED | `prepare_owned_f1_inputs` accepts queued/pending stage | **Confirmed**. Phase B must require `awaiting_operator` + `intent_at` + unspent intent file, owner and signed new target *before* a bounded SDK page change. Do not touch old producer project. |
| 6 / MED | Window-focus alternate unproven | **Confirmed**. `AXFocusedWindow` title observed independently but AX object identity unavailable; `AXMain` alone not sufficient. Phase C may use substitute only after independent real-Mac proof; otherwise block. |
| 7 / LOW | Live keyboard checks irrelevant if script uses menus only | **Conditional, not yet fixed**. Current script still keystrokes Cmd-4, so current strict checks may **not** be removed in A. Phase C may delete them only after revised menu-only actor review. |
| 8 / LOW | Hard-coded foreground name, enabled Normal mode, unproven linked/dynamic/ripple state, weak disposable name | **One source-fidelity repair in A:** `_readiness_from_os` now carries the actually observed `frontmostProcess` instead of synthesizing `Resolve`; the existing validator conservatively rejects unsupported name variants. **Everything else remains unproven**. Exact signed project/timeline UIDs, active mode and unsafe trim/ripple state must be addressed in B/C or block. |

## Injected tests and remaining work

`tests/test_resolve_test_bench_ui_readiness.py` covers actual Qt-negative
examples (AXFocused false or absent; page/track/focus/shortcut null or false),
rejects unexpected AXFocusedWindow, AXMain, fake SDK/Edit/mode/linked/ripple
flags, refuses an alternative observed process name rather than fabricating
one, and rejects matching-name/wrong-UID SDK inventories. These are **mock
tests**, not evidence that the real application published the absent fields.

Executed on this adopted worktree (phase A only):

- `uv run --frozen pytest -q tests/test_resolve_test_bench_ui_readiness.py -k '503_a'`:
  **24 passed, 99 deselected**.
- `uv run --frozen pytest -q tests/test_resolve_test_bench_ui_readiness.py
  tests/test_resolve_test_bench_gui_stage.py tests/test_resolve_gui_roll.py
  tests/test_resolve_test_bench_playhead_stage.py`: **247 passed**.
- `uv run --frozen ruff check` and `ruff format --check` on the two touched
  Python files: **passed**. `uv run --frozen mypy` on those same files:
  **passed** (2 source files). `git diff --check`: **passed**.
- Repository-wide `validate:fast` and independent native acceptance were
  **not run in phase A**. The previous fast gate was RED; environmental versus
  regression attribution is not waived.

**Hard stop:** No fresh authorized target, independent actor-level focus/V1/
mode evidence, final code SHA approval, native 4/4 receipts or strict #312
verification exists. Phase B may implement authenticated page preparation
**code and mocks only**; phase C must solve the single-script actor and
evidence question or deliver BLOCKED. Do not reuse old authority/campaign,
infer Qt marks, relax #208, dispatch F1, or push/merge PR #474 from this agent.

## #499 phase 11 reconciliation (2026-11-09)

The later actual Mac phase-10 read-only census supersedes any earlier
suggestion that an `AXMain=true` Resolve window proves usable focused
timeline state. `AXFocused=false`, focused-role group and missing selection
marks remain actual Qt observations. The owner now checks the SDK Edit
page in both read passes and rejects newly signed linked/ambiguous 327
geometry before one-use journal consumption; it **does not** remove the
timeline-focus, V1 auto-select or Normal-mode requirements or offer an
unreviewed click substitute. See
[phase-11 safety stop](issue-499-phase11-safety-stop.md).
