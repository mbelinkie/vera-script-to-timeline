# Actual Claude N1–N4 implementation delta review03

Candidate2ec8e066ce1049e1ca813c1d1d741203728576e9. ActualOpus5.5/high, tools disabled/static supplied-source review. Exit0/drained; session41d7e7f2-f56c-41a4-97b5-b319e70adc71. RawresultSHAc9a813ab7aed601618e2f9afbcda4bb54b8cd3e3ab25a44bba434f4b364605d8. All supplied inputs independently rehashed/current before evidence-wording corrections. Complete finalLOCALvalidation remains required.

# Verdict: GO for the N1–N4 delta (24d0074 → 2ec8e06)

All four follow-ups are resolved in the supplied bytes. The delta introduces no new defect.

- **Production code changes** are limited to:
  - the `OutputTrust` docstring;
  - the two source-proof `_parse(_canonical(...))` wrappers.
- **`_package_view` is unchanged.** The patch has no hunk for it.
- **Review02's GO and all earlier resolutions still stand.** Nothing in this delta reopens them.

I found three non-blocking items, ranked below. Two are about how accurately the evidence is described, and one is an optional strengthening. None requires a production change or blocks the final LOCAL run.

## N1: time-invariant authentication (resolved)

**The contract text is now coherent.**
- `qualification_output_records_v2.py:130-135` and `INTERFACE.md:33-39,75-78` split responsibilities cleanly:
  - authenticity and provenance are checked independently of time;
  - currentness is checked at receipt issuance and by #209 before reservation;
  - expiry is applied only by #214, through `checked_now`.
- The live chain still closes. Create and verify run with `require_live=True`, so pre-geometry `expiresAt` and commitment `expiresAt` both bound staleness after issuance (`v2:274-279`, `v2:1255-1259`). #209 then re-checks before reservation.

**I traced every pair path to confirm none still requires liveness.** The chain is:
- `_terminal_comparison` → `compare_committed_output` → `_verified_commitment(require_live=False)` → `_candidate` → `_validated` → `_geometry(pre, require_live=False)`, plus `_geometry(post, require_live=False)`.
- With liveness off, the only clock checks left are `captured ≤ now`, `createdAt ≤ now` and `reservedAt ≤ now`. All are monotone, so they cannot start failing as time advances.

**The regression test is meaningful.** `comparison:241-243` advances `now` to 2026-10-16:
- That is past every `expiresAt` (02:00 on 10-15, which `rendered()` copies into post as well).
- Both cases share `a.trust` (`comparison:234`), so the clock moves for both.
- The test then requires full `==` equality of the pair result. That covers heads, comparison raw hashes and cross metrics, and none of them contain `now`.

**Scope limit:** the test guards #214's own non-live path. It cannot test an adapter's behaviour, because `SealedTrust` is time-invariant by construction. That is the correct split under the new contract.

## N2: source-proof payload isolation (resolved)

**The copies fully isolate callers.** The port is invoked from exactly three places, and each now receives a fresh copy:
- `_authenticate` (`records:395`), which was already copied;
- the narration authentication (`v2:525-538`);
- the private-preparation authentication (`v2:594-607`).

`checked_now` receives nothing, and receipts are immutable bytes. So no adapter reference can reach `record`, `binding`, `context`, the intent or the payload.

The wrapping changes no semantics:
- The inputs are already `_parse`-validated JSON, so `_canonical` cannot newly refuse them.
- Key order is irrelevant to canonical comparison.

**Item 1 (minor): only the source-audio half of the regression can detect a revert.**
- **Narration** (`prediction:1108-1109`): nothing reads `record` after the authenticate call at `v2:525`. The mapping hashes `proof.record` bytes, and `record` is a fresh local parse that is never embedded in the intent or payload.
  - So reverting the narration copy cannot change any output, and that half of the test cannot fail.
  - This matches your expected-red run exactly: 1 failed (source_audio), 1 passed (narration).
- **Source audio:**
  - The `context` mutation discriminates. Before the fix, `context` was the same object as `binding["context"]`, which goes into the payload at `v2:1177`.
  - The `binding` mutation does not discriminate. `binding` is not read after `v2:594`.
- **Repair:** state in the disposition that the narration copy is defence in depth, with no observable consumer to regress. No code change is needed.

## N3: compiler track shape (resolved as claimed)

**What the test establishes.**
- The `dependencies` it uses are the exact bytes the compiler consumed (`envelope["inputs"]` hash assertion, `prediction:1161-1164`).
- `manifest.tracks == dependencies.tracks` passes on the fresh output, together with name and index presence (`prediction:1167-1171`).
- `INTERFACE:111-114` correctly scopes native-name equality as a #209 assumption, not #177 evidence.

**Item 3 (informational).**
- The oracle uses Python `==`, which is slightly weaker than production's `_canonical` equality (`v2:696-698`): for example, `True == 1` and `1 == 1.0`.
- `index` type is asserted separately, so the residual gap is negligible for compiler JSON.
- It covers one 25 fps source-audio scenario only.
- **Optional repair:** compare `canonical(...)` bytes instead.

## N4: real-shape range and PCM (resolved; description needs tightening)

**Range arithmetic.**
- 147147 × 48000 / 44100 = 160160 = 80 × 2002.
- With q = 0, the second selection maps to native `{80, 80}`. A passing literal assertion also confirms r = 44100 and q = 0, because any other value would refuse.
- I traced `_provenance` for the 147147 case:
  - start/end = (160160, 320320);
  - `native_start` = 80, which matches the oracle-derived delivery;
  - the mapping-hash fields match what production computes;
  - the end of 320320 stays within the sidecar extent.
- The expected values come from the accepted `_source_audio_range` and independent literals, not from the function under test.
- The 25 fps off-grid refusal is retained.
- The source entry is now closed and passes through `_sources` and `_pcm`.

**Item 2 (minor, accuracy of the description): the pinned sidecar is silence.**
- `issue190_case.py:121-127` writes it with Python `wave` as all zero bytes (`bytes(channels*3*decodedSamples)`).
- The test's decoder (`prediction:1217-1221`) mirrors production's own `wave` plus `int.from_bytes` approach.
- On zeros, this proves:
  - the WAV profile and extent;
  - stripping of the `contentHash` prefix;
  - the separation between the file-hash domain and the int32-hash domain;
  - the encoded length.
- It does **not** prove sign extension, channel interleave or value decoding.
- Separately, every owned synthetic sample is non-negative (`prediction:97`: 900000–1599999). So negative signed24 decoding in `_pcm` is never exercised by a #214 test.
  - The production code is correct by inspection: `int.from_bytes(..., signed=True)`, the ×256 promotion and `_little_endian`.
- The sidecar is also not FFmpeg-written, so real #174 WAVE_FORMAT_EXTENSIBLE handling remains unobserved. That stays an inherited #209 incoming risk, consistent with `INTERFACE:116-123`.
- **Repair:**
  - **Required:** reword the evidence to "all-zero synthetic sidecar; profile/extent/hash-domain only".
  - **Optional:** add an owned in-memory stereo vector with negative codes (e.g. −1, −(2²³−1), and mixed signs) through `_pcm`, hashed independently with `struct.pack("<i")`.

## Evidence consistency (as reported, not verified)

**The counts reconcile with the delta:**
- 99 passed = 97 + 2 MutatingTrust parameters.
- 3 deselected = 2 N4 parameters + 1 full-programme test.
- 2 targeted slow tests passed.
- 750 fast = 748 + 2.

**Other checks:**
- `source.json` head equals the candidate.
- The runtime versions match the locked set.

## Static limits

- I executed nothing.
- I cannot verify:
  - the log hashes or the 7005-entry input equality;
  - the private expected-red run (only its 1-failed/1-passed shape, which matches my trace);
  - fast-log lines 1–186, so the TS/lint/types/generated results are not visible to me.
- Not supplied, so I relied on passing assertions and the review02 trace:
  - the bodies of `_source_audio_range`, `_validate_preparations` and `_delivery_view`;
  - the #177 fixture.
- All fakes confer no authority. The final complete serial LOCAL `PYTEST_ADDOPTS=--durations=25 VITEST_MAX_WORKERS=1 npm run validate` on the exact final state is still required.
- Wording-only fixes to the disposition do not change code. If you add the optional owned test, it is test-only, and your policy decides whether it needs another delta check before that final run.
