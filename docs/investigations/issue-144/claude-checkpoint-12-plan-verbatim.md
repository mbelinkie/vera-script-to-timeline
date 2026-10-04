# Checkpoint 12 plan review — omission workflow integration

Read-only review complete, bounded to the plan, the current `ProofSession` methods (`roundtrip_proof.py`, re-read in full), and `roundtrip_audio.py`'s row/source selection code. No checkpoint-12 code exists yet.

## The primary audio-profile correction — concrete, necessary code change identified

I re-read `roundtrip_audio.py`'s actual source-inventory loop rather than taking the plan's description at face value:

```python
if row in rows or source["sha256"] in hashes:
    raise ProofBuildError("ambiguous row/source binding or alias")
...
matching = [s for s in sources.values() if s["rowId"] == row_id]
if len(matching) != 1 or len(matching[0]["supports"]) < 3:
    raise ProofBuildError("unique row/source support binding required")
```

This confirms the plan's own diagnosis exactly: `row in rows` unconditionally forbids *any* two sources from sharing a `rowId` at all, and `matching` selects by "the one source with this rowId" rather than by an explicit caller-bound identity. Both of these are the specific lines that must change, and the plan's prose doesn't spell that out explicitly — worth stating for whoever implements this:

1. The `row in rows` check must be relaxed to allow multiple sources per `rowId` — but the `identity in sources` (duplicate ID) and `source["sha256"] in hashes` (duplicate bytes) checks must stay exactly as they are, since those are the checks that actually prevent alias/duplicate-content attacks, independent of row grouping.
2. The `matching = [...rowId == row_id]` + `len(matching) != 1` selection must be replaced with selection **by the caller-supplied `primary_source_id`** (a new required parameter, same trust tier as the existing `row_id`/`baseline_hash`/`target` parameters — i.e., supplied by trusted caller code derived from the compiled manifest, never read out of `profile.json`), followed by an explicit cross-check that the selected source's own `rowId == row_id`. Selecting first by ID and only then verifying the row match (rather than selecting by row and hoping it's unique) is what makes "operator profiles cannot pick a different source to qualify" actually true: nothing in `profile.json` can cause a different source to become primary, because the file never supplies the identity used for selection in the first place.

**Does this preserve unique row/source proof?** Yes, provided both changes are made together — relaxing (1) alone without replacing (2)'s selection logic would reopen the exact ambiguity the plan is trying to avoid (multiple same-row sources, no way to know which one is the omission target). The plan's own stated test category ("wrong-primary/alias negatives") is the right place to prove this: include a case where an auxiliary same-row source also independently satisfies the old "3+ supports" heuristic, and confirm the caller's `primary_source_id` — not any property of the file — is what determines the outcome.

## Occurrence-identity gate — confirmed structurally incompatible with a split, correctly not reused

I traced `_occurrence_identity` directly: it requires `mapped == identity["occurrences"]` where `identity["occurrences"]` is fixed once at build time with one entry per original event. A genuine cut produces new split item UIDs that don't exist in that fixed map by construction — any attempt to feed a cut's capture through this exact function would always fail `mapped != identity["occurrences"]`, confirming the plan's claim isn't speculative. The plan's choice to add a *separate* strict omission capture shape rather than loosen this one is the right call — this gate is already proven correct for the move/trim 1:1 case (reviewed across checkpoints 5-6), and weakening it to accommodate splits would reopen exactly the "fabricated unchanged item" risk the plan explicitly disclaims.

## Recovery/replay discipline — confirmed it can reuse the existing proven pattern exactly

I checked `_retained_decision` in full: on replay, it never trusts the stored receipt — it reloads frozen inputs, re-runs `self._semantic(...)` fresh, and requires the stored receipt to equal a freshly recomputed `expected` dict field-by-field (`roundtrip_proof.py:600-621`). The plan's commitment that "a forged report/status/revision cannot bypass actual source and semantic rederivation" is achievable by literally extending this same method shape to also re-invoke the audio verifier and pure text transformer on the omission path's frozen inputs, rather than inventing new replay logic. Same applies to `_promote`'s crash-recovery pattern (`roundtrip_proof.py:720-725`, verify-already-published-pointer-before-re-advancing) — the plan's "interrupted generation/finalization/build/pointer-publication" test category maps directly onto this already-proven mechanism; nothing new needs to be designed there, just reused.

## Everything else checked against the plan's own language — consistent, no gap found

- "Source-based association, never proof of clip ancestry" — consistent with the established discipline from `roundtrip_native.py`'s unique-geometry-decomposition pattern (checkpoint 6) and `roundtrip_audio.py`'s support decomposition (checkpoint 10); applying the same already-validated technique to the split-pair case is not a new risk class, just a new application of one.
- "Do not silently substitute original geometry for edited audio" — this exact anti-pattern is already named and forbidden in the plan text; nothing to add.
- "Non-narration-row guard stays in this segment" — consistent with the checkpoint-9/11 integration boundary already reviewed and confirmed correct; the plan correctly keeps it rather than loosening it here.
- Fresh build IDs, source IDs from the actual compiler result, unchanged-source origin preservation, five-core-stages-plus-injected-native sequencing — all described in terms of APIs already reviewed and proven (checkpoints 4-6, 9), with no new mechanism invented.

## Verdict

One concrete, actionable design correction identified (the exact two-part code change to `roundtrip_audio.py`'s row/source selection), stated precisely enough to implement directly. No other blockers found. This is not an all-refused substitute — it has a real named positive (Charlie omission with auxiliary source, linked split pair, explicit accept, full build chain) and correctly defers composed visual+omission and the stdlib WI entry rather than overclaiming them now.

Static advisory review only — not test execution or native acceptance.
