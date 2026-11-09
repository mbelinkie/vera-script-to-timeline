# #503 C / #499 phase 7 — code-only menu-only F1 actor

Scope: original adopted PR #474, branch `zodex/499-adopt-pr474`. These
are **injected Linux tests and static source review, not native Resolve proof**.
There was no GUI edit, no sacrificial-project creation, no SDK page transition,
no TCC change, no journal consumption, no new M4 receipt and no replay.
The original new sacrificial M4 acceptance remains 0/4.

## Reviewed actor contract

- A single one-use, fsynced #473 journal is consumed before the fixed OS
  command. The fixed script SHA-256 is
  `9469ed9b14a290663381395a5c857330c0ebc85c20e9cfbaa777ca3eba352ed5`;
  no caller script, shell string or arbitrary keyboard event is accepted.
- The authenticated System Events executor takes exact **positive integer PID**
  and original signed disposable window name as *separate argv entries*.
  It discovers exactly one process by that PID and checks the independent
  bundle ID, frontmost state and current window before and during the roll.
  OS foreground activation/observation likewise select the PID, not a
  guessed/hardcoded localized app name.
- Removed unverified Cmd-4, GUI Edit-page switching and GUI V1-selection
  toggles. One script requires real visible Edit/timeline/V1-only/Normal Edit
  Mode marks, actual main/focused window, absence of sheets, and currently
  enabled Roll/Nudge menus **before** the first selection. Each of exactly
  24 menu-only one-frame nudges checks PID, bundle, frontmost/window focus,
  modal and currently enabled nudge. Any missing Qt AX attribute refuses.
- Owner-held read-only signed SDK preparation runs before and after the OS
  observation: same signed original operation, target UIDs, 11 native item
  UIDs, 6 tracks, Playhead=327, Studio version and source graph. The first
  intent expiry cannot be extended by the second read; both must be fresh.
  Capture authentication finishes before consumption of the short-lived OS
  attestation and before the fsynced one-use intent. Any crash/partial/timeout
  remains UNKNOWN, never a success receipt or permission to retry.

## Verification

- `uv run --frozen pytest -q tests/test_resolve_gui_roll.py tests/test_resolve_test_bench_gui_stage.py tests/test_resolve_test_bench_ui_readiness.py tests/test_resolve_test_bench_page_stage.py tests/test_resolve_test_bench_full_loop.py` — **293 passed** (injected, Linux).
- `uv run --frozen ruff check` / `ruff format --check` for the six changed
  source/test files — **passed**.
- `uv run --frozen mypy` for the three changed production modules — **passed**.
- Reversible mutation of `inventory_after == inventory` to `True`: **6 tests
  failed**, including changing UID, playhead, six-track count; test guard kills
  the mutation. Reversible mutation of the positive-PID gate to `True`: **1
  test failed**. Both source files restored byte-identical in `finally`.
- `git diff --check` — passed. Original #491 exception plan updated to make
  the historical #495 script non-admissible under the changed source graph.
- Full local `VITEST_MAX_WORKERS=1 npm run validate:fast`: recorded separately
  at `.pipeline/499/phase7-validate-fast.log`; report its actual terminal result
  before final phase handoff. No independent native code review claimed here;
  #503 D owns final independent review and source freeze.

## Known hard stop on actual Studio 21.1.1.10

Retained **real Mac** #500/#499 read-only evidence has `AXFocused=false`,
`AXFocusedUIElement` identified as a group, and missing Qt `AXMenuItemMarkChar`
for Edit/V1/Normal mode. SDK had previously selected **Deliver**, not the
approved new sacrificial Edit target. Neither a correct foreground PID nor
SDK OpenPage(edit) proves timeline keyboard focus, V1-only auto-select, Normal
Edit mode, or linked/dynamic/ripple safety. These are **unknown**, not defaults.
The revised script must therefore refuse on that evidence; no real
AppleScript compilation or actor-level System Events execution was performed
on this Linux host. Phase 8 must preserve this blocker and source graph,
not synthesize AX checks; phase 9 must not attempt a live one-use edit until
independent actual-Mac target/focus/menu/mode proof and fresh exact-source,
case-specific Producer authorization exist. #473, #312 and #313 remain gated.
