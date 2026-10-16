# Checkpoint 12f resolution — generation-inputs record confirmed, finding resolved

I re-derived the gap from scratch rather than just accepting the framing, and it holds — this resolves my sole plan finding.

## Where my prior analysis was incomplete

My "cache lock + proof lock are sufficient" argument covered concurrency correctly but missed a different failure mode: **sequential resume with a changed configuration.** `fcntl.flock` on the cache's synthesis key only deduplicates two callers computing the *same* key at the *same* time. `proof.lock` only serializes calls that overlap in time. Neither one persists anything across a crash-then-later-resume where the *injected service itself* differs between attempt one and attempt two (different `adapter_version`, voice profile, or normalizer). In that specific sequence — provider succeeds, cache publishes, process dies before the handoff file is written, resume happens later with a different service object — `service.process_block` correctly computes a *different* key for the *different* configuration and correctly treats it as new work, because from the cache's perspective it genuinely is new work. The cache was never wrong; there was simply nothing recording "this decision was already bound to a specific service identity" for anything to check that computation against. I didn't construct this scenario in my original review, and the cache/proof-lock argument genuinely doesn't reach it.

## Why this is the smallest sufficient record, not a new mechanism

I checked whether an even smaller existing record could substitute, and it can't without reopening an already-reviewed file:

- The service identity needed here is exactly what's computable *before* synthesis: the request identity hash (`request.identity(provider_input, provider.adapter_version)`, already covering adapter version, voice profile, settings, pronunciations, controls, and the prepared provider input — no duplicated algorithm, just calling the service's own function), plus the normalizer's static identity (`profile_id`, `tool_fingerprint` — fixed properties of the normalizer object, not derived from audio content), plus the cache root path. The full normalization key can't be precomputed (it depends on the raw synthesis output), but that's fine — this record only needs to catch drift in *inputs*, and the cache's own cross-checks (already proven in checkpoint 9/12c) still catch any drift in the *output* once synthesis has actually happened.
- Extending the checkpoint-12e decision receipt instead would be the larger change: `decide-omission` has no service dependency today and shouldn't need one just to decide accept/reject — reopening that already-reviewed schema to carry generation-time concerns would couple two stages that are currently cleanly separated. A new file, written only at the start of `generate-omission`, keeps that separation intact.
- No comparison logic needs writing: `publish_immutable_output` already refuses if freshly-computed bytes differ from what's on disk at that path. Calling it every time with freshly recomputed generation-input bytes, under the existing `proof.lock`, is sufficient — the existing immutable-publish guard does the drift detection for free. This is genuinely "rename one file, no new primitive," not a disguised state machine.

## Confirmed

This resolves the finding. The gap is real, it's distinct from the concurrency case I'd already ruled out, and the fix as reformulated — one immutable file, existing lock, existing publish primitive, no new reservation/lock/store — is the minimal thing that closes it. I don't have a smaller record to propose in its place.

No other blocker identified in the checkpoint-12f plan. Static advisory review only — not test execution or acceptance.
