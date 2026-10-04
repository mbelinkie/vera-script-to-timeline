# Checkpoint 8 follow-up — corrections confirmed

Read-only review complete (changed `roundtrip_proof.py` exception paths, the new parametrized test, and the plan's new readiness-gate language). Both corrections are sound; no new findings, no reopening of settled scope.

## Process-fault correction — confirmed

Traced the actual exception flow, not just the test's assertions:
- `ProofProcessFault(ProofBuildError)` (`roundtrip_proof.py:57`) is raised only at the one specific point it should be: `_semantic`'s `if process.returncode not in {0, 1}: raise ProofProcessFault(...)` (line 347-350) — an abnormal child exit.
- `subprocess.TimeoutExpired` is never wrapped; it propagates naturally from the `subprocess.run(..., timeout=300)` call straight out of `_semantic` with nothing in between to intercept it.
- `main()`'s `except (ProofProcessFault, OSError, subprocess.TimeoutExpired)` clause (line 760) is checked *before* the generic `except (RuntimeError, ValueError, KeyError, TypeError)` clause. Since `ProofProcessFault` is a `RuntimeError` subclass, ordering matters here and it's correct — Python matches the first applicable clause, so process faults never fall through to "refused." Every other `ProofBuildError` raised elsewhere in the file is the base class, not `ProofProcessFault`, so genuine semantic/binding refusals still correctly land in the "refused" clause. No misclassification possible in either direction.
- The new test (`test_cli_process_fault_cannot_masquerade_as_semantic_refusal`, parametrized `timeout`/`abnormal_exit`) exercises this through the real CLI `main()` entry point with `subprocess.run` patched to simulate each fault at the exact call site used for the semantic child process — not a unit test of the exception class in isolation. Confirmed both parametrizations produce `exit 70`/`status: "fault"`.

One consistency check worth noting, not a new defect: the semantic CLI's own drift detection (`issue-144-proof-cli.ts:49-51`, exit 75, same pattern as the compiler CLI) also falls outside `{0, 1}`, so it's swept into `ProofProcessFault`/"fault" by the same generic check. That's the right call — observed drift during evaluation is itself a process-level anomaly, not a judgment about input validity, so it belongs with the other faults rather than with "refused."

**Confirmed closed.**

## Real-observer readiness gate — confirmed, and it's the right minimal boundary

The plan now states this precisely (`issue-144-roundtrip-harness.md:40-45`): "Nonce/receipt/hash consistency alone cannot distinguish a live capture from a package echo; no cryptographic live-readback provenance is claimed," covering both "the real initial inspector and capture adapter."

I re-checked the current code against this exact claim rather than taking the sentence on faith: nowhere does `_fresh`, `_occurrence_identity`, or `validateObservation` fall back to manifest/package facts when a capture response is *absent* — absence always raises `NeedsAction`, never gets silently filled in. Manifest/package facts are used strictly as the *expected* side of a comparison against whatever the capture claims, never as a substitute source of truth. That matches "local manifest/package facts may serve as expected comparisons, never fill in an unobserved native result" exactly.

I agree this is the correct place to stop. The underlying problem — a file-based nonce/hash protocol cannot cryptographically prove that particular bytes came from a live API call rather than a local read, when the capture implementation has access to both — isn't fixable from the protocol side without something far outside this harness's bounds (e.g., instrumenting or sandboxing the capture process to prove which calls it made). Trying to solve that *inside* #144 would mean building exactly the kind of native-execution machinery this segment is deliberately not building yet. Naming it as an explicit independent-review gate before #145 trusts a real adapter is the honest, minimal, correctly-scoped response — not a gap left to paper over.

**No further action needed on either item.** Ready to move to the audio segment review.
