# Checkpoint 12b plan refinement review — pre-edit audio evidence capture and canonical bridge

Read-only review complete, bounded to the plan and the `ProofSession` methods (`_fresh`, `_publish_baseline`, `_baseline`) already fully reviewed in the checkpoint-12 turn immediately preceding this one.

## Question 1: is `bind-omission-evidence` the smallest sound preparation seam?

Yes, and I can ground why rather than just agree. I checked the existing visual observation schema (`ObservedItem` in `issue-144-semantics.ts`, reviewed in checkpoint 6) directly: its fields are `eventId/itemUid/mediaUid/sourcePath/sourceHash/trackId/trackKind/recordRange/sourceRange/available/enabled/speed/linkedUids` — there is no `mute`/`solo`/`effects`/`sends`/`gainDb`/`pan` anywhere in it. It genuinely cannot express audio-control neutrality; this isn't a gap in an otherwise-adequate schema, it's a schema built for a different purpose (geometry/identity, one entry per timeline event) than what the audio verifier needs (per-route controls, a different grain entirely — `roundtrip_audio.py`'s `routes[]`/`segments[]` shape doesn't map onto "one entry per event" at all). Given that, the plan's explicit rejections are each correct, not just cautious:

- **No neutral-default backfill** — consistent with the #141 precedent I verified earlier in this review series (`final-findings.md:11,24`: WI readback `mute:true` did not actually silence a track; the cause was never resolved). Assuming neutral controls without observing them would repeat exactly that failure mode.
- **No edited-control backfill** — correctly avoids circular reasoning (inferring the pristine state from the post-edit state).
- **No weakened old UID gate; a separate schema instead** — correct, since cramming route-level controls into an event-keyed schema would be a structural mismatch, not a simplification.
- **No invented split ancestry** — consistent with the geometry/content-based unique-decomposition discipline already proven in `roundtrip_native.py` and `roundtrip_audio.py`.

The one property that makes "while pristine" actually enforceable (not just a naming convention) is the plan's own requirement that the new capture's geometry facts get cross-checked against the already-bound baseline's stored facts. I traced why this is sufficient: since `_publish_baseline` already requires the visual baseline to reproduce the compiled manifest with zero pending move/trim proposals (`checked["result"]["rows"]` must be empty, `roundtrip_proof.py:421-425`), any drift between the visual baseline capture and a later `bind-omission-evidence` capture — whether from an intervening edit or an accidental native nudge — would show up as a geometry mismatch against that already-verified baseline, not get silently accepted. No blocker found for Question 1.

## Question 2: canonical bridge trust/recovery boundary — one necessary correction

I want to flag a specific ambiguity in the plan's wording before code exists, because it's exactly the kind of thing that reads two different ways depending on who you think the subject is:

> "Finalization must first rerun the actual guarded whole-row service handoff/cache verification and compare the complete retained receipt, not trust a stored dependencies/asset hash claim."

Read one way, this could be taken to mean the TypeScript `finalize-omission` action itself re-runs the whole-row handoff. That's impossible as stated — `replace_row_narration` and the `NarrationService`/`NarrationCache` it drives are Python-only, unreachable from the Node CLI process without a wholly new cross-language call path, which would itself be exactly the kind of "speculative architecture expansion" this review is asked not to recommend.

**The correct and sound reading is the other one:** the *Python host* (`ProofSession`, not the TS bridge) is responsible for re-invoking `replace_row_narration` fresh — via its own already-cache-safe mechanism, the same one proven in checkpoint 9 — immediately before every call to `finalize-omission`, and passing that just-computed result as the `<verified-handoff>` argument. `finalize-omission` itself never needs to "verify" the handoff against anything Python-side; it just has to never be handed a stale, previously-written handoff file as if it were authoritative. This is consistent with — not an addition to — the existing architecture: `_retained_decision` already re-runs `self._semantic("decide", ...)` fresh on every replay rather than trusting a stored receipt (`roundtrip_proof.py:600`), and `replace_row_narration`'s own cache keying means re-invoking it on every call costs nothing extra on a successful replay (no second provider call), exactly matching the plan's own "same successful request replay uses accepted cache without a second provider call."

**Smallest correction:** reword that sentence in the plan to name the Python host explicitly as the thing that re-runs the handoff, and state plainly that `finalize-omission` only ever receives a just-computed (not previously-stored) handoff result as input. This removes the ambiguity before anyone writes code against the ambiguous version.

Everything else in the bridge section checks out against already-proven patterns: reusing `revisionId` rather than a new UUID scheme (checkpoint 6), sourcing materialization IDs from the compiler's own manifest output rather than a parallel allocator (checkpoint 9's test fixture already does exactly this), and binding the fresh-ID seed to the full verified handoff result (not just script+prior-dependencies) to avoid accidental ID collision across different underlying content — a direct, minimal extension of the existing seed-hashing pattern, not a new mechanism.

## Verdict

No blockers for Question 1. One concrete wording correction for Question 2, needed before implementation to prevent a cross-language misreading of who re-derives what. Nothing else flagged as missing or unsound in either section. Advisory plan review only — not test execution or native acceptance.
