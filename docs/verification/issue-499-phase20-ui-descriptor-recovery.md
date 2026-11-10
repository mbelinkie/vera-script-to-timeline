# #499 Phase 20 — bounded macOS UI readiness repair, still NO-GO

2026-11-10 UTC. This is a **Phase 20 BLOCKED** evidence report, not an authentic M4 receipt. All previous native target/project/operation journals are preserved. Original PR #474 adopted branch only; no push, merge, Resolve edit, System Events launch, replay, new M4 target, or revision acceptance.

## Existing immutable cases and ownership

- Third distinct disposable case `issue-499-phase20-recovery-803b807cf8904422`: Terminal one-start log records `Resolve foreground activation unavailable` and `THIRD_M4_EXIT:2`. The previously active PID 84242 is no longer running; do not replay the case or trust the absence of a signed stage as proof of no side effects.
- Fourth distinct case `issue-499-phase20-recovery-8fa64ed3bbfd4157`: log records one-start 03:53:36Z, existing-Resolve activation 03:53:37Z, then `OS UI observation missing or ambiguous: windowCount` and `FOURTH_M4_EXIT:2` at 04:01:59Z. Do not replay.
- Fifth provisional case `issue-499-phase20-recovery-63526aeebf9a413e`: inspection found only `config.json`, `authority.json`, `provision/`, with no M4 intent, operation or native receipts. Authorization was bound to the earlier frozen source and cannot be retargeted to changed code. Do not start from it.
- A separate Zodex command-session record `command-session.json` showed execution `0b83f638-3d86-4824-b56b-0903701490f3`, agent `1n19`, `state=running`, 04:17 UTC. This agent did not terminate or replace its foreign handle.

## Root cause and bounded fix

Claude Opus source review `.pipeline/499/phase20-claude-opus-ui-readiness-review.txt` found both JXA probes use `NSAppleEventDescriptor.descriptorWithBundleIdentifier`, rejected by JXA. Changed only `resolve_test_bench_ui_readiness.py` to construct a retained `typeApplicationBundleID` (`0x62756e64`, `bund`) descriptor through `descriptorWithDescriptorTypeData`, with explicit nil/type checks, in both the OS observer and foreground fallback. Preserved strict numeric OSStatus==0, `askUserIfNeeded=false`, original `void*` Carbon ABI and ordering: no System Events scripting before permission. No Roll actor or held-source verifier changes.

Focused `uv run --frozen pytest tests/test_resolve_test_bench_ui_readiness.py -q`: **124 passed**. Ruff lint/format, targeted mypy and diff check passed. Tests exercise the helper's successful descriptor, nil data, nil descriptor, wrong descriptor type; both scripts share identical helper bytes and no prompt or early System Events actor. No broad `validate:fast` (native preconditions still unfulfilled).

The real physical Mac accepted the new descriptor construction read-only through `osascript`, returning descriptor type `1651863140` (`0x62756e64`). The patched full OS observer yielded a valid JSON snapshot with Resolve Studio 21.1.1.10 PID 33770 and Chrome frontmost, so it **did not run the Automation/AX window collection**; its `automation:false` and `windowCount:null` are not evidence of permission denial. A separate bounded no-prompt bridge-chain JXA check reported `{systemEventsRunning:false,axTrusted:true,permissionStatus:-600,allowed:false}`. This confirms NO-GO from that launch chain; **Terminal-specific TCC permission was not verified**, and it must not be inferred from the bridge. No System Events was started, and no TCC grant/prompt was requested.

## Required before another native case

1. Confirm no competing owner/live operation, and obtain already-running System Events plus verified no-prompt numeric status **0** under the exact campaign Terminal process ancestry; no automatic launch or TCC prompting from this preflight. Recheck actual Resolve foreground, single named standard window, menu paths and duration from the same chain.
2. This targeted source edit changes the previously frozen code graph (`1f8ca62d` / graph `513e1453`): re-freeze and verify **new** exact source graph and commit before any native admission; all older fifth/earlier case authorities are ineligible.
3. Under Producer's documented 100-*distinct*-attempt overnight authority, only after deterministic live GO create two **new** disposable SDK project/timeline UID pairs, private one-use authority with new graph and bounded deadline, one fresh root and one start. On UNKNOWN/partial/failure preserve forever and move to another independently authorized case, never reuse spent Roll. Phase 21 remains prohibited until **four signed native M4 receipts plus independent strict #312 MOV/PCM/UID/rate/source/media readback** actually pass.

**Result: M4 0/4 verified, strict #312 NOT RUN, Phase 20 BLOCKED.**
