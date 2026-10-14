# Secure opened bytes for the reopened audio check

Independent Claude delta review GO on 53cfffd retained in CLAUDE-DELTA-GO.md identified a nonblocking violation of the accepted #190 handoff: WAV parsing must use the securely opened hashed bytes, never reopen a pathname. Only owned roundtrip_v2_proof.py and its new test change. No shared native/record helper, accepted #191/#202 core, frozen contract/fixture/golden/test, dependency or effect changes.

Test-first source-hash negative failed as expected before the fix: DID NOT RAISE ProofNativeError; exit1, one failed in20.31s, log SHA32e7221fd51e734d2b6918b2d82195e44cc009e977a635ecf9d68823abcc7d66. This test-only direct forged raw observation is not a forged capture accepted by B1.

The check now reads through the accepted descriptor-safe _operator_bytes with the same64MiB source limit as capture, binds exact bytes to captured sourceHash, parses BytesIO and verifies current file hash afterward. Bad WAV/EOF/filesystem reads become ProofNativeError. Existing gain/channel/link comparisons remain. A second negative retains exact error handling for malformed WAV bytes. Cases now total41, preserving the prior39 and adding source-hash/invalid-WAV guards.

Ruff format/lint and strict mypy pass on both files; exact receipts pinned in reopen-pcm-fix.json. This production file changes the source graph, so earlier runtime/fast passes and ClaudeGO remain historical for this new candidate. Recreate all temporary public bindings/packages/evidence and run affected41 runtime, completefast, narrowClaude delta review, then finalfulllocal. No real Resolve/audio-save-reopen/provider/acoustic qualification is claimed.
