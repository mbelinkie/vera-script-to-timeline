# Checkpoint 9 completed-segment review — whole-row narration handoff

Read-only review complete (`roundtrip_narration.py`, `test_issue144_row_narration.py`, updated plan, `roundtrip_build.py` CODE_PATHS diff, and the accepted `narration/polly.py` import chain). This traces the actual code, not just the eleven tests' assertions.

## Precision requirements from the plan review — confirmed correctly incorporated

Every concrete risk I named before code existed was addressed, verified by direct trace:
- **Field-exclusion for the "nothing else changed" check** (`roundtrip_narration.py:78-82`): `ignored = {"activeDraft", "liveHeadSequence", "liveStateVector", "liveContentHash"}` excludes exactly the fields `applyVisualDecisions` mutates — confirmed correct.
- **Evidence-lane gate mirrors `NativeStages.__init__`** (lines 43-47): checked first, before any file read or provider call; `test_generation_refusals_do_not_change_original_inputs[real_lane]` confirms `provider.requests == []`.
- **Refuse identical old audio** (line 133: `asset.normalized_audio_hash == old_dep["audioHash"]`) and **refuse non-word-level timing** (line 134: `asset.timing_precision != "word_start_with_derived_end"`) are both present and tested (`test_canned_old_audio_cannot_be_relabelled_as_a_new_row`).
- **UTF-16 via actual code-unit counting**, not codepoint indexing: the test's `_utf16` helper (line 40-41) encodes to `utf-16-le` and divides by 2, and `test_astral_text_preserves_surviving_token_ids_with_new_utf16_marks` exercises an actual astral character (😀), asserting `endUtf16 - startUtf16 == 2` for it — confirms the surrogate-pair case I flagged is genuinely tested, not just a non-ASCII BMP stand-in.
- **Media/ locator vs. cache origin** (line 144 vs. 162/195): `dependency["audio"]["locator"]` is overwritten to the delivery path while `origin` stays bound to the real cache file — confirmed consistently used for materialization-plan construction in the test.
- **Validator runs before synthesis**: `subprocess.run([... VALIDATOR ...])` (line 70) executes before any `changed`/`process_block` logic.

## New findings from reviewing the actual implementation

**Finding (Medium, `roundtrip_narration.py:43-47`) — the synthetic-lane gate checks labels, not the provider object.** The gate inspects `service.config.profile.provider`/`.region` — string metadata used for cache-keying and asset labeling — but never inspects `service.provider` itself, the object whose `.synthesize()` actually runs. A `NarrationService` constructed with a synthetic-looking profile label but a real provider instance (e.g. from `narration/polly.py`) would pass this check and execute a genuine call under `synthetic_injected` cover. Minimal fix: additionally reject if `type(service.provider).__module__` is the accepted real provider module (`vera_timeline_agent.narration.polly`) — the same module `test_proof_import_does_not_load_any_synthesis_provider` already treats as the thing #144 must never reach.

**Finding (Low/Medium, `roundtrip_narration.py:48-58`) — containment check doesn't walk intermediate path components.** `prior.root.is_relative_to(owner)`/`cache_root.is_relative_to(owner)` are purely lexical, and the symlink check only walks `owner`'s and `cache_root`'s own ancestor chains — it never checks directory components *between* `owner` and `prior.root`/`cache_root` for symlinks. This is weaker than the pattern already proven in this same codebase: `NarrationCache._assert_safe_ancestors` (`narration/cache.py:72-83`) walks the full chain from a target up to its root checking every step. `prior.root` itself is independently protected (`PreparedBuild.__init__` already rejects a symlinked root), but an intermediate symlink planted between `owner` and a deeper `cache_root` wouldn't be caught here. Minimal fix: reuse the same walk-up-and-check pattern rather than relying on `is_relative_to` plus owner-only symlink checks.

**Finding (Low, `roundtrip_narration.py:124-139`) — "missing provenance" isn't independently enforced.** The plan names this as a required refusal, but the code only checks derived `asset.provider`/`asset.region` strings, which fall back to `request.profile.provider`/`.region` when the provider returns empty `provenance` (`service.py:347-348`) — and in this test setup, that fallback happens to equal the required check value, so an empty-provenance provider would still pass. Minimal fix: also require `len(asset.request_ids) > 0`, which can only be populated by a genuine successful `synthesize()` return, not the fallback path.

**Confirmed, no action needed:** `narration/service.py` imports `narration/polly.py` only for a price constant, and `polly.py`'s `import boto3` is local to one function (`polly.py:309`), never module-level — so importing the narration chain through `roundtrip_narration.py` does not load `boto3`. Worth a small parity test (`'boto3' not in sys.modules` after importing `roundtrip_narration` fresh) matching the existing checkpoint-4 pattern, but this is a nice-to-have, not a gap — Low severity.

**Minor observability note (Low):** `validation.returncode` nonzero is treated as one blanket refusal regardless of whether the validator CLI reported a genuine validation failure (exit 1) or a usage/parse/internal fault (64/65/70) — safe either way (fail-closed), but the raised message doesn't include `validation.stderr`, making the two hard to distinguish when debugging.

## Core properties — confirmed by trace, not just the tests

- **Whole-text generation/mark/cache identity and replay:** cache keys are scoped by block_id+revision+text+profile (no cross-row coupling); `process_block`'s own replay path (`service.py:397-402`) pins `generated_at` to the originally-cached value on a repeat call, which is why `replace_row_narration(...) == result` holds byte-for-byte on replay — this is accepted, unchanged service behavior, correctly relied upon rather than reimplemented.
- **Untouched-row preservation:** `deps["narration"][1] == prior.dependencies["narration"][1]` is a direct equality assertion on the untouched row's full dependency object, re-confirmed across a *second* edit cycle on the same document later in the same test — row isolation holds across repeated regenerations, not just once.
- **End-to-end integration stopping before native action:** the rebuilt target (new dependencies → real compile → real `build_resolve_import_package`) runs through `PreparedBuild.run()` with no adapter, confirmed `status == "waiting"` and `verified_package().build_id == new["buildId"]` — the real compiler and package writer/verifier genuinely execute against the new narration dependency, with native stages correctly left waiting.
- **Source binding:** `_assert_current()` runs both before and after generation, and `CODE_PATHS` now includes `roundtrip_narration.py`, `script-validator-cli.ts`, and all seven narration module files — drift in any of them during generation is caught.

## Scope confirmation

No splice route reopened, no blocker found. This segment proves the generation handoff mechanics only — row-isolated regeneration, cache identity/replay, and downstream recompilation — and correctly stops short of omission acceptance, native capture, or canonical-revision integration, exactly as the plan states. The test's revised documents are explicitly input-only fixtures, not accepted omission decisions, and nothing in the code claims otherwise.

This is static, read-only review only — not independent test execution, native evidence, or acceptance.
