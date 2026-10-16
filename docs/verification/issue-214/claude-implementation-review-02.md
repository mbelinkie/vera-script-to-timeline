# Actual Claude implementation delta review02

Candidate24d0074498a97246b4632a868491e7ecc31117e4; actualOpus5.5/high, static supplied-source review. Exit0, jobs drained; raw resultSHA7379b58deccabb2256ec0a7c418ab1d36dc91e3a51e100fe0029638ed2c05e36; session9938a6ee-0e07-4510-a572-4fbaab5875bf. Supplied inputs equal at start/finish/current before repairs. This GO applies to pure implementation; N1–N4 and finalLOCALfull remain.

# Verdict: GO for the repaired pure #214 implementation

**Scope of this verdict.** Every review01 blocking and major finding is resolved in the supplied candidate bytes (`24d0074`). I traced each one against the current owned files and the unchanged accepted excerpts. I found no introduced bug that breaks a pure responsibility.

The four new findings below are non-blocking. Three of them change production docstrings or code, so fix them before the still-pending final serial LOCAL `validate` run; those changes need that fresh run anyway.

This was a static review only. I executed nothing.

---

## Review01 findings: disposition verified against source

| Finding | Status | Evidence I traced |
|---|---|---|
| **B1** expiry strands terminal | **Resolved** | See B1 below. |
| **B2** ambiguous post capture | **Resolved** | See B2 below. |
| **B3** foreign rows not tied to dependencies | **Resolved** | See B3 below. |
| **B4** origin under geometry kind replaced package derivation | **Resolved** | See B4 below. |
| **M1** identity limits on foreign text | **Resolved** | See M1 below. |
| **M2** caller-copy binding | **Resolved**, minor residual | See M2 below. |
| **M3** late vacuity | **Resolved** | See M3 below. |
| **M4** names fork chain | **Resolved** under the stated plan-owner clarification | See M4 below. |
| **minor1** shared `private_preparation` kind | **Resolved by documentation** | See minor1 below. |
| **minor2** pair needs pre-terminal ledger | **Resolved** | See minor2 below. |
| **minor3** untyped exceptions | **Resolved** | See minor3 below. |
| **minor4** encodings | **Resolved** | See minor4 below. |
| **minor5** test gaps | **Resolved**; oracle strength discussed separately | See minor5 below. |
| **minor6** excluded references | **Resolved** | See minor6 below. |

### B1: expiry stranded the terminal state

**Repair confirmed:**
- `_verified_commitment(require_live=False)` drops the `now ≤ expiresAt` condition (`v2:1247-1251`).
- The pre-geometry check now requires `captured ≤ expiry` only, not liveness (`v2:274-279`).
- Reservation ordering is checked as `createdAt ≤ reservedAt ≤ commitment.expiresAt` and `reservedAt ≤ now` (`v2:1363-1369`).
- `compare_committed_output`, `_terminal_append` and `_terminal_comparison` all reach this non-live path.
- `verify_prediction_commitment` stays live (`v2:1228-1230`).

**Ordering chain:** the commitment payload's `expiresAt` is the pre-snapshot `expiresAt`, enforced by recompute equality (`v2:1184`, `v2:1268-1271`). So the checked chain is pre-capture ≤ creation ≤ reservation ≤ expiry.

**Tests:** `comparison:165-198` covers both the post-expiry positive and the late-reservation refusal.

### B2: post-render capture was ambiguous

**Repair confirmed:**
- `capturePhase` is part of the envelope and must match exactly (`v2:253`, `v2:275`).
- The post snapshot additionally authenticates `renderLineage` (`v2:282-284`).
- Post raw bytes must differ from pre raw bytes (`v2:1410-1413`).
- `reservedAt ≤ post.capturedAt` (`v2:1427-1430`).

**Coverage:**
- A forged `jobId` now refuses at post-geometry authentication (`comparison:380-388`).
- Replay and missing lineage are tested (`comparison:201-221`).
- Capture-after-completion depends on the adapter, because no completion time exists in pure data. This is documented at `INTERFACE:63-64`.

### B3: foreign rows were not tied to the authenticated dependencies

**Narration (`v2:454-467`, `v2:513-516`):**
- Exactly one row with that `blockId` must exist in `narrationTimingMaps ∪ narrationBoundaryEvidence`.
- The supplied record must be structurally equal to that row.
- Boundary status comes from list membership, not from the row's own `schemaVersion`.

**Prepared audio (`v2:560-571`):**
- `requirementKey` equals the manifest source's key.
- There is exactly one matching `preparedMedia` entry, and `binding` equals it exactly.
- `timeMapping` equals the event's `sourceTimeMapping`.

**Tests:** `prediction:993-1035` and `prediction:1233-1300`.

The TS `boundaryEvidenceHash` is bound only transitively, through the adapter-authenticated manifest and dependencies, as the plan requires. It is never rehashed in Python.

### B4: the origin path bypassed the package derivation

**Repair confirmed:**
- Any supplied origin record or receipt refuses (`v2:427-430`, `v2:908-914`).
- Both origins must equal `(0,0)` (`v2:643-647`).

**Equivalence with the accepted `_source_audio_range`.** Let `r` be the source sample rate, `a` the source start sample, `q` the resampled first sample, and timeline rate = 24000/1001 = 48000/2002.
- The accepted code computes `start_frames = (a/r − q/48000)·48000/2002 = (a·48000/r − q)/2002`.
- #214 requires `a·48000/r − q` to be an integer divisible by 2002, then compares `start/2002` and the duration with the package row (`v2:616-638`).
- An integral frame count implies an integral sample count, and the accepted code's `ceil` is the identity on exact integers. The sidecar bound matches the accepted bound via `durationSamples == decodedSamples`.
- Result: the same events are admitted, with the same ranges.

`_package_view` treats the source-audio range as given (`v2:797`), but `_provenance` re-derives it for every audio event. The bijection check at `v2:1040-1044` guarantees every audio event reaches `_provenance`.

### M1: identity limits were applied to foreign text

**Repair confirmed:**
- `_tree` now enforces only size, surrogates, safe integers, finiteness and depth (`records:185-208`).
- `_identity` remains on the consumed identity fields: ids, `blockId`, `requirementKey`, `trackId`, track `name`, path, `state`, `jobId`, `reservationId`, timestamps and target fields.
- Every string in an owned new record is either constant-checked, an exact enum, or identity-checked. So the owned records still refuse controls, and the removed NUL vector only affects foreign text.

**Test:** `prediction:1046-1066`.

I cannot verify the claimed R16 JSON audit.

### M2: parts of the binding were caller copies

**Repair confirmed:**
- The full `inputBinding` reaches the geometry authenticator (`v2:281`).
- `_package_view` (`v2:666-814`) checks the view's timeline, tracks and composition against the manifest, and checks extent and rate.
- It checks binding tracks against manifest tracks for kind, name and index.
- It checks `nativeSources` against the view's `contentHash`, compares each `v2Event` with its manifest event, and checks gain and picture treatment.
- It derives narration, placeholder and visual ranges, and checks the complete event inventory.
- `_host_identity` (`v2:817-876`) closes the runtime, release and profile domains.
- The package blob in the tests is produced by the accepted `_delivery_view` (`prediction:454`), so the test is a real differential.

**Residual (acceptable):** pure code does not compare placeholder native `contentHash` against the manifest treatment, or manifest `sources[].deliveredHash` directly. Visual is covered through `provenance.deliveredSourceHash`. This is video-only, does not affect audio prediction, and the adapter verifies the full package (`INTERFACE:87-88`).

### M3: vacuity was detected only after the effect

`_candidate` now runs `_nonvacuity` (`v2:1166`), so `create_prediction` refuses before any commitment. Comparison keeps the same gate (`v2:1462`).

### M4: target names forked the ledger chain

**Repair confirmed:**
- The chain key is `(projectUid, timelineUid, caseId, phase)` (`records:427-434`, `records:459-461`).
- Names stay inside the stable binding projection (`records:345-356`).
- A rename produces a new key and appends to the same chain (`records:254-285`).

This matches the plan's "target change is a genuine input change requiring disclosure". I cannot verify where the plan-owner clarification came from.

### minor1: `private_preparation` reused with a new shape

The new-lane payload is explicit (`v2:590-599`, `INTERFACE:215-220`). The kind name is still shared with #190, so the adapter's shape dispatch must be static. The cross-shape refusal test exercises the fake plus production's choice of shape (`prediction:1086-1095`).

### minor2: pair needed a pre-terminal ledger

**Repair confirmed:**
- `_terminal_comparison` (`v2:1532-1575`) authenticates the sealed result.
- It requires exactly one matching ledger entry with matching lineage.
- It recomputes over the prefix sliced at that entry's sequence, then pairs the results.
- All four labels are present (`v2:1636-1640`).
- A pre-terminal prefix refuses (`comparison:241-244`).

### minor3: non-refusal exceptions could escape

`_refusal` wraps every public entry point and the ledger/context helpers. I traced the remaining `ValueError` sources: `fromisoformat`, `json`, `decode` and `wave` (`wave.Error`/`EOFError`). Each is caught or pre-guarded. The unwrapped `_terminal_comparison` is reachable only through the wrapped pair operation.

### minor4: raw encodings were accepted

Parsing now calls `raw.decode("utf-8")` (`records:242`). A BOM is rejected by `json`, and UTF-16/UTF-32 fail to decode as UTF-8.

### minor5: weak or missing tests

**Fixed:**
- The B5 legacy test now reaches the old observation-shape gate after a verified positive (`comparison:532-579`).
- Old records are fed into the new consumers.
- There are Full/Quiet end-to-end positives (`comparison:224-228`).
- There is a multi-segment, late-offset `old_mix` differential (`prediction:1303-1353`).

The strength of the real-shape oracle is discussed in its own section below.

### minor6: excluded-reference rationale was inaccurate

The coverage table (`INTERFACE:106-128`) is substantively correct. `q` is determined by `a`, `b`, `r` and the package `sourceRange`, and the sidecar bytes are bound by the view's `contentHash`.

The binding hashes context only; `sourceEntries` and narration receipt bytes are not in the key. That is coarsening only: an identical key with a changed prediction still refuses, unless the state is `expired_unused` with identical bytes. So there is no reopen path.

---

## New findings (ranked, all non-blocking)

### N1. Trust-port contract does not say authentication must be time-invariant

**Where:** `records:127-137` (the "input/currentness … checked chronology as applicable" wording), `INTERFACE:33-36` and `INTERFACE:73-74`.

**Mechanism:** after the B1 and minor2 repairs, historical recomputation sends the identical `(kind, receipt, expected)` to `authenticate`. This happens through `_terminal_append`, `_terminal_comparison`, `_validated` → `_geometry(pre)`, and the source-proof authentications. The port receives no signal distinguishing a live call from a historical one.

**Counterexample:**
1. An adapter follows the INTERFACE text literally and enforces "currentness guards" or receipt expiry inside `authenticate`.
2. Case C pristine reaches its terminal state.
3. The timeline is then edited for the edited phase.
4. `compare_prediction_pair` re-authenticates the pristine pre and post geometry. Those snapshots are no longer native-current, so the pair is refused.
5. The same thing happens to terminal append after expiry, which reintroduces B1 at the adapter.

The accepted #191 pattern verifies receipts long after capture, which supports an authenticity-only reading. The contract is still ambiguous.

**Repair (bounded, docs-only):** state in the `OutputTrust` docstring and in INTERFACE that:
- `authenticate` must be a time-invariant check of seal authenticity and provenance of the exact expected payload;
- live native, input and target currentness is enforced when the receipt is issued, and by #209 before reservation;
- 214 alone applies expiry, using `checked_now`.

**Alternative:** pass an explicit `live: bool` derived from `require_live`.

**Regression:** advance `trust.now` past every `expiresAt` after both terminals, then assert `compare_prediction_pair` still succeeds. The current pair tests never advance the clock.

### N2. Two source-proof authentications pass live references to the port

**Where:** `v2:525-534` and `v2:590-599`.

**Mechanism:** `_authenticate` deliberately hands the port a deep copy (`records:391-393`). These two direct calls pass `record`, `binding` and `context` by reference instead.
- `context` is the same object that is later embedded in the intent and commitment payload.
- `audio` and `binding` are read again after the call (`v2:600-637`).
- A trusted adapter that normalizes its argument in place would silently change committed bytes or the derivation.

**Repair:** wrap both expected payloads in `_parse(_canonical(...))`.

**Regression:** a fake trust that mutates `expected` in place; prediction bytes and commitment payload must be unchanged.

### N3. Real-shape track assumptions in `_package_view` are untested against compiler output

**Where:**
- `v2:688-691` requires `canonical(manifest.tracks) == canonical(dependencies.tracks)`.
- `v2:699-704` requires each manifest track to carry `name` and `index`, with native names equal to manifest names. Review01 asked only for id, kind and index.

**Why it matters:** the synthetic oracle makes the two track lists equal by construction (`prediction:397-399`). The real-shape test never exercises them. If the compiler adds or reorders track fields, or if #177 delivery does not apply manifest names, every real case refuses. That is safe, but unusable.

**Repair:** in the slow real-shape test, assert on the freshly compiled `manifest`/`dependencies` that the track lists are equal and that `name`/`index` are present.
- If they are not equal, compare only id, kind and index against dependencies.
- Separately record that native track-name equality is a #209 capture assumption.

### N4. The real-shape #174 oracle is narrower than its description

**Where:** `prediction:1099-1230`.

This is a coverage note, not a defect. Details are in the next section.

**Repair:**
- Add a second selection with a nonzero start: `a=147147`, `b=294294` should map to native `{80, 80}`.
- Build a fully closed source entry, including `sampleRate=48000` and `decodedSamplesSha256` computed from the pinned sidecar bytes in `request["preparations"][k]["audio"]`.
- Run `r._sources([entry])` and `q._pcm(sidecar, entry)` on it.

---

## Does the #174-shaped oracle prove the intended seam?

**It does prove these points, substantively, against freshly compiled #190 output plus the unchanged accepted `_validate_preparations`:**
- The dependency `preparedMedia` binding exactly equals the receipt binding.
- `binding.timeMapping` equals the compiled event's `sourceTimeMapping`.
- `verification.deliveredHash` equals `provenance.deliveredSourceHash`.
- Receipt `sourceAudioHash` equals event `audio.audioHash`; this is the stream-domain check, distinct from the sidecar hash.
- Selected stream index equality.
- `_tree` accepts the real receipt, which is M1-relevant.
- #214's `q/r` derivation at 44.1 kHz agrees with `_source_audio_range`.

The arithmetic holds:
- 80 × 1001/24000 s × 44100 = 147147 samples.
- 147147 × 48000/44100 = 160160 = 80 × 2002.

It also correctly retains the 25 fps refusal as a refusal and does not claim the compiled event changed rate.

**It does not prove the following:**
- **Only `q=0` and `a=0`.** The accepted code forces `start_counter = −q/2002 = 0`, so `q=0`. Nonzero `q` is covered only by the synthetic differential (`prediction:673-699`), which is adequate for the plan's differential requirement.
- **No end-to-end path.** The test calls `_provenance` directly. Its entry is not a closed source entry (it lacks `sampleRate` and `decodedSamplesSha256`), so `_sources`, `_pcm`, `_package_view`, geometry and commitment are not exercised on real shape. The risk is low: `_pcm` mirrors #190's own `wave` checks on the same sidecars (`roundtrip_v2_build.py:413-435`).
- **No real authentication.** The private-preparation seal is the `SealedTrust` fake and confers no authority.

**Are the remaining shape restrictions unusable?** No more than the accepted package already is. #214's range acceptance equals the accepted `_delivery_view` gate. However:
- At 24000/1001, a 44.1 kHz source is admitted only when both endpoints sit on 80-frame multiples, because 44100 × 1001/24000 = 147147/80 samples per frame, while the accepted mapping also subtracts the audio offset `q`.
- 48 kHz sources need `q ≡ 0 (mod 2002)`.

This is an inherited downstream positive-case risk, analogous to the narration CEIL issue. Real R16 source-audio events should be audited before #209 is marked Ready. It is not a #214 defect.

---

## Limits

- This is a static review of the supplied bytes. I ran nothing. Pass counts and log hashes are as you reported them; the supplied logs are internally consistent (1 passed; 97 passed with 2 deselected; 748 passed).
- I cannot verify the R16 audit, the plan-owner rename clarification, how the compiler constructs manifest tracks (N3), or how #177 names native tracks.
- My Python 3.12 `wave` handling of FFmpeg `WAVE_FORMAT_EXTENSIBLE` 24-bit files is inferred from #190 reading the same sidecars, not observed.
- All fakes confer no authority. #209 still owns persistence, effect order, decoder qualification, chain completeness and capture-after-completion; #215 owns the TypeScript and consumer side.
- The owned stress test has not been rerun since phase03. This GO does not substitute for the final complete serial LOCAL `PYTEST_ADDOPTS=--durations=25 VITEST_MAX_WORKERS=1 npm run validate` on the exact final reviewed source. Any N1–N4 source edit needs a delta check before that run.
