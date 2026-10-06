# Checkpoint 4 review — prepared host build stages and audio boundary findings

Read-only review complete (`roundtrip_build.py`, `test_issue144_prepared_build.py`, `checkpoint-03-disposition.md`, current `measure-retained-w1.py`, `retained-w1-boundary-measurements.json`, current plan, and the accepted `resolve_import_package.package`/`studio_spike.py` APIs). One correction to my own prior checkpoint first, then findings.

## Self-correction

My checkpoint-3 answer called the adversarial overlay "full-word" twice. It is half-word: `measure-retained-w1.py:181,216` compute `half_end = support_start + (support_end-support_start)//2` and inject only `a1[support_start:half_end]`. The disposition is right to flag this. Separately, my claim that `GetSubFolderList`/`GetClipList` support a project-tree recovery walk was a category error — those are **media-pool** (within-project bin) methods. I re-checked `studio_spike.py` directly: the only verified **project-manager** (cross-project) surface is `GetProjectManager`, `GetProjectListInCurrentFolder`, `CreateProject`, `SaveProject`, `CloseProject`, `LoadProject` (lines 478-491, 541, 548, 766-770). There is no verified `GetFolderListInCurrentFolder`, `OpenFolder`, or any other project-manager folder-enumeration call anywhere in the accepted code. **Confirmed: no evidence exists today for a project-tree-wide recovery walk.**

**Finding (Medium, plan text):** `docs/plans/issue-144-roundtrip-harness.md:231-232` still promises recovery "requires one unique read-only match **throughout the project tree** or explicit operator identification." That first branch has no verified API behind it. Smallest fix: narrow that sentence to "within the current folder (via the accepted `GetProjectListInCurrentFolder`) or explicit operator identification," and treat cross-folder automatic search as blocked until someone separately adds and verifies project-manager folder-enumeration calls in `studio_spike.py`'s preflight. Don't let an implementer infer tree-wide search is already safe to build.

## 1. Strict parsing / immutable snapshot / binding / tampering — mostly closed, one narrow gap

`roundtrip_build.py:110-142` (`_object`, `_constant`, `_number`, `_parse`) correctly uses `object_pairs_hook` for duplicate keys, `parse_constant` for literal `NaN`/`Infinity`/`-Infinity`, and `parse_float` + `math.isfinite` for numeral overflow (`1e400`). All seven cases in `test_strict_operator_gate_refuses_ambiguous_bytes_without_changes` are covered and leave no file changes. Good.

**Finding (Low/Medium, `roundtrip_build.py:123-127,130-142`):** the finite-number guard only intercepts tokens that Python's parser routes through `parse_float` (anything with `.`/`e`/`E`). A bare, very long **all-digit integer** literal (no decimal point or exponent) is handled by Python's default `parse_int`, which has arbitrary precision — it stays "finite" from Python's point of view, so it passes this gate untouched. But the *same raw bytes* are later handed unmodified to the Node compiler (`_compile`, line 312-317), whose plain `JSON.parse` converts an out-of-double-range all-digit integer to `Infinity` silently. That value would eventually trip the compiler's own `Number.isFinite` check inside `canonicalize()` during output serialization — but as an uncaught `TypeError` surfacing as `INTERNAL_ERROR`/exit 70, not as the clean deterministic refusal path the whole strict-gate exists to guarantee. Concrete failure example: an operator file containing `{"...": 1` followed by ~400 digits `}`. Smallest fix: add a `parse_int` hook that performs the same `float(token)`/`math.isfinite` check as `_number`, and catch `OverflowError` alongside `ValueError`/`UnicodeError` in `_parse` (Python's `float()` raises `OverflowError`, not `ValueError`, for some giant-int conversions).

**Tampering/replay/different-package checks are solid, verified by tracing the code (not just trusting tests):**
- `_assert_current()` re-checks live root files, the frozen `run_root/inputs/*` copies, and all source/schema/lockfile hashes — called at the top of `run()`, before/after `execute()` for every stage, and inside `reconcile()`. A change to any of these during a run raises before any stage completes.
- `_compile()` cross-checks the compiler envelope's own declared `inputs` hashes, re-verifies output byte hashes against `outputs.manifestSha256/reportSha256`, and only accepts `ok:true`+matching-hash or a clean `ok:false` refusal (persisted to `compiler-refusal.json`) — any other exit/body combination is rejected as "not a valid deterministic refusal."
- `build_resolve_import_package` (accepted, `resolve_import_package/package.py:1198-1231`) is itself already idempotent against a pre-existing `package_root`: it re-verifies and compares manifest/report/materialization bytes, returning the existing result if consistent or raising if the existing package is for *different* artifacts. `writing_interchange` retries can't silently merge into a mismatched prior package.
- `_verify_compiler_files` re-derives manifest/report hashes from the **live files on disk** every time (not from a cached value), so a stale/tampered intermediate is caught on every `reconcile`/`verified_package` call, confirmed directly by `test_altered_intermediate_cannot_replay_into_native_stage`.

No concrete bypass found beyond the integer-overflow gap above.

## 2. Verify-only speech/media mapping — no provider path found

`_verify_speech` (lines 260-308) checks block existence/no-duplicates, text hash, revision, asset-ID-to-materialization uniqueness, audio byte hash, and actual WAV header (channels/sample width/rate/frame count) against the declared dependency — all from local files, no network or synthesis call anywhere in the module. `test_proof_import_does_not_load_any_synthesis_provider` confirms `boto3`, `narration.polly`, `narration.service` are never imported at module load, and a full read of the file shows no import of them at all, so this isn't just an import-time dodge. Confirmed closed.

One thing I could not verify and am not raising as a bug: whether two different narration blocks are permitted to legitimately resolve to the *same* materialized audio artifact (the uniqueness check only forbids an `assetId` mapping to more than one plan entry, not two dependency records sharing one `assetId`). I don't have enough context on whether shared assets across blocks are an intended case; flagging as unverified rather than asserting a defect.

## 3. Job semantics and receipt honesty — no overclaim, one clarity note

- Every stage receipt hardcodes `"evidenceLevel": "local_prepared"` regardless of the requested `proofLane` (lines 460-472); the operator-supplied `evidenceLevel` in `proof-request.json` never escalates a receipt's own claimed evidence. Confirmed directly in code, matching the disposition's claim.
- `generating_speech`/`resolving_media` results are explicitly labeled `"verify_prepared_only"`/`"verify_local_only"` — no overclaim.
- `rendering_mp4`/`verifying_mp4`/`uploading` are `skipped`; `building_resolve_timeline`/`verifying_timeline` are `requested`/`waiting` with `NeedsAction("... requires the explicit #145 seam")`, surfaced as `#145` in `lastError` — matches test assertions exactly, no silent progression into native territory.

**Finding (Low, clarity only):** the `compiling` stage's receipt embeds the *entire* compiler envelope (including its own nested `evidenceLevel: "compiler_only"`) as `result`, inside an outer receipt whose own `evidenceLevel` is `"local_prepared"`. The same file legitimately contains two differently-scoped `evidenceLevel` keys. Not a bug — the compiler's own output must be preserved verbatim — but worth a one-line comment at `roundtrip_build.py:435-436` noting that `result.evidenceLevel` describes the embedded compiler envelope, not the stage.

## Audio boundary probes — confirms the limitation, and sharpens it

The new `retained-w1-boundary-measurements.json` numbers settle the question raised last checkpoint: **tiny/quiet residue does pass the proposed numeric limits.**
- `tenSamples` (full-amplitude 10-sample opposite-channel burst): `maximumSliding20msResidualRms` is *bit-identical* to the unmodified linked-cut baseline (0.0038155 — the window never reaches the 10-sample burst at its peak position) and `residualRms` ≈ 0.000215–0.000231, both under the proposed limits. **Passes.**
- `halfAtOnePointFivePercent` (half-word residue at 1.5% amplitude): `residualRms` ≈ 0.00036, under 0.0004. **Passes.**
- Everything scaled ≥2% or shaped as a quarter/frame-boundary residue correctly fails.

So: RMS-threshold numeric reconstruction, by itself, **cannot** prove zero residual speech-like content — no finite threshold can, since arbitrarily quiet or arbitrarily short injected energy is undetectable by construction. This is not a bug in `measure.py`'s math (the windowing, fitting, and residual computation are correct); it's an inherent property of any amplitude-tolerance check, and the file already says so (`"qualification"` field, lines 281-285).

**Does the proposed gate leave a material unsupported inference? Only if numeric reconstruction is treated as sufficient on its own.** The prompt's own "Proposed bounded next gate" already downgrades it to a "consistency check, not a general speech classifier" and requires "exact full-target support excision and neighbor preservation" as a separate condition — if that excision/preservation check is implemented as a **discrete structural comparison** (declared retained source/record sample ranges vs. the declared target-support interval, read from the hash-bound manifest/segment map — not from audio energy), then the combination is honest:

- **Primary proof (discrete, no tolerance):** the target support's sample interval does not overlap any retained occurrence's source range, and every declared neighboring support is fully contained in a retained occurrence's source range. This alone correctly rejects picture-only (video-only mute, audio route still carries the full support) and disabled-A1 (whole route absent from the inventory) on structural grounds, with no dependence on any RMS number.
- **Secondary consistency check (bounded tolerance, already measured):** the rendered bytes match "declared routes × reference-fitted gains" within 0.006/0.0004 — catches gross content errors (wrong gain, wrong route, wrong extent) that the structural check can't see, but is explicitly *not* the proof of silence.

**Smallest concrete gate for the retained-positive case:** require both conditions above, scoped only to this pinned hash-bound W1 fixture (sources, renders, and fixture-declared supports all hash-verified at measurement time), explicitly non-generalizing — #145/#148 must independently prove their own support declarations and gains, never inherit W1's. The boundary-probe adversarial cases remain valuable as regression tests confirming the numeric check alone is unsafe, but they should not themselves need to "fail" once the structural check is primary — they test that no code path ever lets the numeric check decide on its own.

**On hash-allowlisting:** `measure-retained-w1.py` is not a replay — it recomputes gains via live least-squares fit (lines 120-129, 202) and recomputes residuals via live windowed computation (lines 132-159) from hash-*verified* (not hash-*allowlisted*) bytes every run. That's a real, if bounded, computation. The risk I'd flag forward: when this becomes part of the actual host gate, it must keep recomputing structural overlap + residual from freshly hash-verified bytes on every invocation — if a future implementation ever short-circuits on "this input's hash matches a known-good W1 fixture hash, so return the frozen verdict," that would be a replay, not a gate, and should be rejected outright. Nothing in the current files does this, but it's worth stating as a hard constraint before this gate is wired into `roundtrip_build.py`.

## Next native segment — design check only (nothing implemented yet to inspect)

- `run_studio_assembly(adapter_factory=..., local_facts=...)` injection is real and already used this way in `tests/test_studio_assembly.py`; it only proceeds past `verify_resolve_import_package` on the real package root (`studio_assembly.py:102`), so wiring tests through it on the actual verified package from this segment is sound.
- `roundtrip_build.py` already reserves `self.intent_path = self.run_root / "native-intent.json"` (line 194) but never writes it in this segment — tests correctly assert it stays absent (`assert not build.intent_path.exists()` in three places). This is the right scaffolding for "persist intent before effects" in the next segment; nothing to fix now.
- The one concrete correction, repeated from above: scope recovery/rehydration to the verified current-folder lookup plus explicit operator identification, not a tree-wide walk, until project-manager folder APIs are separately verified.
- WI capture/link/render isn't in these pinned files; I can't review an implementation that doesn't exist yet. The stated intent (validate target, bounded named actions only, disposable proof) is consistent with everything else in this design, but I have nothing concrete to check.

## What can proceed / what must wait

- **Can proceed:** wiring the next native segment's intent-persistence-before-effect pattern against `run_studio_assembly` with injected `adapter_factory`/`local_facts` in tests, scoped to same-current-folder recovery only.
- **Must wait:** any cross-folder automatic recovery (no verified API); freezing the audio gate as a standalone numeric classifier (must be paired with the discrete structural excision/neighbor check before it's a "gate" rather than a "consistency check"); any omission-rebuild positive (still pending the wording/route decision, unchanged from checkpoint 3).
- **Smallest fix to apply now, independent of the above:** the plan-text correction at `issue-144-roundtrip-harness.md:231-232`, and the `parse_int` finiteness gap in `roundtrip_build.py`.

## Could not verify
- Did not run `pytest`/`ruff`/`mypy`; test-pass counts (18 new, 35/23 regressions) were confirmed by direct enumeration of `test_issue144_prepared_build.py`'s parametrized cases, not by execution.
- Did not confirm whether Python's stdlib `wave` module strictly rejects non-PCM-compressed WAV containers (relevant to `_verify_speech`'s format check) — treated as out of scope given the narrow likelihood.
- Did not resolve whether two narration dependencies may legitimately share one materialized asset — noted as unverified, not asserted as a defect.

This is review only, not acceptance.
