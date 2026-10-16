# Checkpoint 12d finished-code review — pristine audio preparation and synthetic omission proposal

Read-only review complete, bounded to `roundtrip_omission.py`, the `ProofSession._fresh`→`_capture_files` extraction, the `inspect-script` CLI addition, and the new fixture/preparation test files. I traced the logic directly against each item in the prompt's checklist.

## Old visual UID gate — confirmed genuinely untouched, not just relabeled

I checked the extraction precisely: `_fresh` is now a thin wrapper (`roundtrip_proof.py:260-271`) that calls the new `_capture_files` with `validate=lambda observation: self._occurrence_identity(...)` — the exact same `_occurrence_identity` function, same exactly-one-UID-per-event semantics, unchanged. `OmissionProof.capture()` calls the identical `_capture_files` helper but supplies its own `validate=self.audio` callback and different schema names (`issue-144-omission-capture-request/v1`/`-response/v1`). The shared machinery (reservation, nonce, pending/consumed bookkeeping, `observationA == observationB` freshness check) is reused byte-for-byte; the identity *validation logic* is never shared or weakened — it's two independent validators behind one reservation helper. Confirmed by reading both call sites, not by trusting the docstring.

## Source-based split mapping — traced for soundness, not just plausibility

`audio()`'s association logic (lines 287-304) first tries an exact `itemUid` match against `self.old_items` (unsplit occurrences), and only falls back to `_source_key` matching (mediaUid/sourcePath/sourceHash/trackId/trackKind) restricted to `self.allowed` — the two events explicitly permitted to split. I confirmed `self.old_items`' itemUids are already guaranteed unique by the native-identity layer (`roundtrip_native.py`'s `_inspect`, reviewed earlier), so the exact-match branch can't be ambiguous. An item with a genuinely new UID that doesn't content-match either allowed event correctly yields zero candidates and refuses ("unknown/ambiguous source-based split association") — there's no silent fallback to "pick the closest one." This is the "complete unknown graph refusal" property, confirmed by trace of the empty-candidates path, not asserted from the docstring.

## Reciprocal pair / complete unknown graph refusal — confirmed thorough

I traced the full pair-check block (lines 318-335): group-size equality between primary and companion fragment counts, exactly-one-link-per-fragment, the linked peer must actually be in the other group, and the link must be reciprocal with matching record/source geometry *per fragment pair*, not just in aggregate. "Extra untouched occurrence" (lines 312-317) independently forces every non-allowed event to retain exactly one occurrence and every allowed event to retain at least one — no silent route disappearance is possible.

## Forged/changed pristine inputs — confirmed caught at multiple independent layers

`evidence()` (lines 418-507) doesn't trust the injected supplier's output at all: it re-reads and re-hashes every file (`files.json`/`files.read` with internal hash-consistency checks), requires the supplier's `baseline.json`/`observation-*.json` to equal the already-verified envelopes exactly, cross-checks every profile source's `rowId`/`sha256`/decoded-path-hash against the independently-derived `self.sources`, and only copies files it actually read-and-verified into the immutable destination. `retained_preparation()` re-derives the pristine audio envelope fresh via `self.audio(..., pristine=True)` and requires it to equal a freshly recomputed `expected` dict — the same "never trust a stored claim" discipline already proven in `_retained_decision`. I specifically traced whether a *consistently* forged `inputs.json`+`receipt.json` pair (matching hash, wrong content) could slip through: it can't, because `self.audio()` always validates the observation's content against `self.old_items`/`self.manifest` — independently established from the real baseline at `__init__` time, never from the stored file itself.

## File guards / default waiting — confirmed

`test_default_omission_boundary_waits_without_provider_or_native_effect` and the `NeedsAction` raise in `evidence()` when `self.session.omission_evidence is None` (line 421-425) confirm the same fail-closed default as every other capture seam in this codebase.

## The dynamic exclusion mechanism — confirmed correctly derived, not hardcoded

I worked through why `replaced_files` includes `prior_render["output"]["path"]` specifically from the *render* receipt (not the calibration receipt): the render output is expected to change because it reflects the edited program, while the calibration/reference output must never change. Deriving the excluded filename from the actual prior render receipt rather than a hardcoded string correctly handles a supplier that names its output file differently, while still requiring every other file — profile, calibration, all source WAVs — to remain byte-identical, confirmed via the hash-equality check at lines 601-606.

## One concrete, worthwhile test addition

I did not find a code gap, but I did find a scenario the current tests don't exercise directly: tampering the *stored* `omission-preparations/.../receipt.json` or `inputs.json` between `bind-omission-evidence` and `propose-omission` with an internally-consistent forgery (matching `inputHash`, but claiming different — still plausible-looking — pristine geometry for the allowed pair). I traced that this is already caught by `retained_preparation`'s re-derivation via `self.audio(..., pristine=True)`, but no test exercises that specific path today — the existing tests tamper the *live capture* at proposal time, not the *stored preparation artifact* itself. **Smallest addition:** a test that, after a successful `bind-omission-evidence`, directly edits `omission-preparations/.../inputs.json`'s `observationA` geometry for the allowed pair and recomputes `receipt.json`'s `inputHash` to match, then asserts `propose-omission` still refuses. This would make the re-derivation guarantee explicit rather than only implicit from code reading.

## Verdict

No blockers found. No regression against the existing visual identity gate. The one test I'd add closes a real (if already-covered-by-code) gap in direct evidence rather than a design flaw. Static advisory review only — not live or native acceptance.
