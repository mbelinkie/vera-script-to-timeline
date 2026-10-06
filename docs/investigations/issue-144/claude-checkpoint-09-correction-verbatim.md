# Checkpoint 9 corrections review

Read-only review complete (`roundtrip_narration.py`, new/changed tests). Confirming each item against the actual code and pathlib semantics, not just the stated summary.

## 1. PollyProvider isinstance gate — confirmed

Line 47: `isinstance(service.provider, PollyProvider)`, checked first in the function (lines 44-49), before any file read, containment check, or provider call. `test_real_provider_object_refuses_despite_synthetic_profile_labels` constructs `GuardedRealProvider(PollyProvider)` with a spy `synthesize()` that raises if ever reached, leaves the profile labels synthetic, and asserts `calls == []` after the expected `ProofBuildError`. `isinstance` naturally covers subclasses in Python, matching "including subclasses." I agree with the stated scope: this guards against the accepted real provider class (and anything built on it) being wired in despite synthetic-looking labels — it is not and cannot be a sandbox against an arbitrary independent malicious provider class that doesn't subclass `PollyProvider`, since no isinstance check can catch that. That's an honest, correctly-bounded claim, not an overstatement.

## 2. Provenance verified from the synthesis cache record — confirmed, and correctly supersedes my original suggestion

Lines 131-166 now read the raw `"synthesis"` cache entry directly (`service.cache.read("synthesis", asset.request_hash[7:], "synthesis.json")`) and check its stored `provenance` dict — the provider's *verbatim* return value, written at generation time (`service.py`'s `_raw_result`/`cache.publish`) — rather than the asset's derived `provider`/`region` fields, which fall back to the request's profile defaults when provenance is empty. I checked the test fixture: `WholeTextProvider.synthesize` sets `provenance={...} if self.provenance else {}` while `request_ids` stays populated (`f"synthetic-{seed.hex()}",` unconditionally) regardless of `self.provenance`. That confirms, concretely, that my originally suggested fix (require `len(asset.request_ids) > 0`) would not have caught this exact `empty_provenance` case — the new fix (reading the raw cache record's provenance) is the one that actually closes it. I retract my suggested fix as insufficient and confirm the implemented one is correct. The additional cross-checks (`raw_audio_hash`, `provider_input_hash`, and the timing file matching byte-for-byte between the synthesis and asset cache tiers) go further than what I asked for and are a real strengthening, not just a label check.

## 3. Cache containment — I was wrong, correcting the record

I re-derived this rather than just accepting the correction. `Path.parents` returns *every* ancestor from the immediate parent up to the filesystem root — so the old code's `any(path.is_symlink() for path in (cache_root, *cache_root.parents))` already walked every directory between `cache_root` and `owner` (and beyond), since those are necessarily ancestors of `cache_root` once `cache_root.is_relative_to(owner)` holds. My claim that "intermediate components between owner and cache_root" were unchecked was a reasoning error about what `.parents` returns, not a demonstrated gap.

Separately, `prior.root`'s own ancestor chain — not walked as an independent target in the old containment check — was already covered through a different path: `_assert_current()` (called immediately after, line 69) hashes each input file via `_file_hash`, which calls `_regular()`, which walks the full ancestor chain of `self.root / name` for symlinks. So `prior.root`'s symlink safety was already enforced before any synthesis could proceed, just via a different call than the containment check itself.

I confirm the disposition: the consolidated `for target in (owner, prior.root, cache_root) for component in (target, *target.parents)` walk is a clarity/maintainability improvement — it makes the invariant locally visible instead of depending on a reader knowing `_assert_current`'s internals — not a fix for a reproducible escape. The passing `test_cache_ancestor_symlink_refuses_before_provider_call` before this change is consistent with that: there was nothing to break. I did not demonstrate an escape, and I shouldn't have implied one with the confidence I did.

## 4. Validator fault distinction, import hygiene — confirmed

- Lines 81-86 now give exit 1 ("actual script validator refused the revised document") a distinct message from any other nonzero exit ("script validator execution fault (exit N)") — addresses the observability note at the level I actually raised it (message clarity), without over-engineering a new exception type for something I'd flagged as low-severity.
- `test_importing_handoff_loads_no_cloud_sdk` imports `vera_timeline_agent.roundtrip_narration` fresh in a subprocess and asserts `'boto3' not in sys.modules` — exactly the parity test I suggested as a nice-to-have, now present. Confirmed `polly.py`'s `boto3` import stays local to its calling method (unchanged), so directly importing `PollyProvider` for the isinstance check doesn't pull in the SDK.

## Summary

All four corrections are confirmed as described. Item 3 is a correction to my own prior review, not a defect either before or after this change — I want that on the record plainly rather than hedged. No new issues found in this pass. This remains review of the synthetic handoff mechanics only; it does not establish canonical omission acceptance or fresh native integration, and this response is static review, not test execution or native evidence.
