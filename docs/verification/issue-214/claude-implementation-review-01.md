# Retained actual Claude implementation review 01

Candidate `1a768f40bcaa86e25f9148deab8e282f172009a7`, base
`22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`. Actual Claude Opus5.5/high,
CLI2.1.299, tool-free static review of complete new modules/tests/operative
plan plus explicitly bounded accepted seam excerpts. No command/native execution
by reviewer. Exit0, is_error=false; inputs unchanged at finish and owner reinspection.
Result raw SHA256 `10b584ded18b0c9e22eb532736ccd1f94a1f0c63ca424de3b7b1aa88b6dbedc6`. Verdict NO-GO; all findings below
are retained verbatim. This is not acceptance. Required fixes/delta review and
complete final LOCAL evidence remain.

# Verdict: NO-GO for the pure #214 implementation candidate

The package is well structured, and most numeric, hash-domain and closed-shape criteria are met. It does not yet meet the accepted plan on four points:

- lifecycle terminal reachability
- post-render capture evidence
- package-bound narration and preparation provenance
- generic-origin authentication

The repairs below are bounded and stay inside the two production modules, the three owned tests and `INTERFACE.md`.

This is a static review of the supplied bytes only. I ran nothing, and I am relying on the fast evidence exactly as you reported it.

---

## Blocking findings

### B1. Commitment expiry is re-applied at comparison and terminal append, so a terminal state may be unreachable

**Where:**
- `qualification_output_v2.py:943-948` requires `now <= commitment.expiresAt`.
- `_candidate` calls `_validated`, which calls `_geometry`. At `qualification_output_v2.py:250-255` this requires `now <= pre.expiresAt`.
- Both checks run again inside `compare_committed_output` (`:1027`) and again in `_terminal_append` (`:1187`).
- `expiresAt` is copied from the pre-render snapshot (`:896`).

**Mechanism:**
1. The controller reserves before expiry.
2. The MOV render, decode and post-capture (or the sealing step) finish after the pre-snapshot's `expiresAt`.
3. Comparison then raises "commitment chronology/expiry refused", even when the output is bit-exact.
4. `_terminal_append` refuses for the same reason.

The only ledger transition left is `uncertain` (`records:488-498`). That key can then never reach `compared_consistent` or `compared_refused`. The plan's lifecycle is committed → reserved → compared_*.

Expiry should govern the authority to reserve and render. It should not govern the ability to compare an effect that has already happened.

**Repair:**
- Enforce `capturedAt <= createdAt <= reservedAt <= commitment.expiresAt` from the authenticated records.
- At comparison and terminal append, revalidate authenticity and recompute the prediction without a "now ≤ pre/commitment expiry" condition.
- Keep the checked clock for the post snapshot and for monotonic ordering.

**Tests:**
- Compare and terminal-append at `now > expiresAt` with `reservedAt < expiresAt` → result returned and appended.
- `reservedAt > expiresAt` → refuse.

### B2. The post-render snapshot is not distinguishable from, or bound after, the render

**Where:**
- The envelope fields at `qualification_output_v2.py:230-237` contain no capture-phase marker.
- Post geometry is authenticated with exactly the same kind and payload form as pre geometry (`:1070` → `:256`).
- The only ordering check is `reservedAt <= post.capturedAt` (`:1075-1078`).
- Nothing ties the post snapshot to `completionReceiptSha256` or lineage.
- Nothing requires the post raw bytes to differ from the pre raw bytes. The test assertion at `test_issue214_comparison.py:165` is incidental, not enforced.

**Counterexamples:**
- A snapshot captured after reservation but before render start, or during render, is accepted as the "post-render" endpoint.
- If `capturedAt == createdAt == reservedAt` (second-granularity timestamps are allowed by `records:241`), the pre snapshot itself can be replayed as post.

Plan line 32 requires separate pre- and post-render raw snapshots and places "phase-state markers" in the envelope.

**Repair:**
- Add `capturePhase: pre_render|post_render` to the envelope. It stays outside the semantic geometry projection.
- Require `pre_render` for inputs and `post_render` for `post_geometry`.
- Authenticate the post snapshot with `renderLineage=lineage` as an additional bound field, so the adapter can check capture-after-completion.
- Require the post raw hash to differ from the pre raw hash.

**Tests:**
- Pre snapshot replayed as post → refuse.
- Post-phase snapshot sealed without lineage → refuse.

### B3. Narration rows and #174 receipts are never tied to the authenticated package dependencies, and `boundaryEvidenceHash` is never matched

**Where:**
- At `qualification_output_v2.py:458-470`, `provenance.boundaryEvidenceHash` is only shape-checked (`_legacy_digest`).
- The narration row (`proof.record`) is checked against the manifest and its `narration_preparation` receipt. It is never compared to the execution-dependencies blob, which is supplied and hash-checked at `records:541-550` but never parsed.
- Likewise, the prepared-audio record's `binding` and `requirementKey` are never compared to `dependencies.preparedMedia`. `event.preparationBindingHash` is only forwarded to the adapter (`:528-531`). Compare #190 at `roundtrip_v2_build.py:360-365`, which does check this.

**Example:** a validly authenticated narration row for the same block, WAV and timing hash, but with a different `blockRevision`, token set or boundary `verification`, is accepted. The commitment's `provenanceReceiptSha256` and `provenancePinsSha256` then bind a row that is not in the delivered package.

PCM is unaffected, but plan line 50 ("matched through the authenticated package using the compiler TS hash") is unmet.

**Repair:**
1. Parse the `executionDependenciesSha256` blob.
2. Require exactly one row in `narrationTimingMaps ∪ narrationBoundaryEvidence` with that `blockId`, and require `record == row` by structural equality with no rehash.
3. Derive boundary-ness from list membership.
4. For prepared audio, require `record.requirementKey` to match the manifest source's `preparationRequirementKey`, and `record.binding` to equal that `preparedMedia` entry.

The manifest's TS hash is then bound transitively through the authenticated manifest and dependencies, so no Python recomputation is needed.

**Tests:** a substituted authenticated row and a substituted preparation binding each refuse.

### B4. The generic nonzero origin is authenticated under `output_geometry_snapshot` and silently replaces the package derivation

**Where:**
- `qualification_output_v2.py:584-590` authenticates the `qualification-output-origin/v1` record with kind `output_geometry_snapshot`. A capture-receipt authority is thereby asked to vouch for a PCM mapping. This breaks kind/domain separation, and `INTERFACE.md:98-101` promises an independently authenticated origin record.
- `:595-604` then requires `delivery.sourceRange.startFrame` to equal the origin-shifted value instead of the accepted `_source_audio_range` result.

**Example:** the owned test `test_issue214_prediction.py:530-543` (via `case()` at `:255-261`) accepts `sourceRange.startFrame=100`. For the same event, the accepted package oracle returns `2`. The test never compares against the oracle.

The "authenticated package derivation" bound in `deliveryDerivationSha256` is therefore not the package's derivation.

**Repair (minimal, plan-compatible):** refuse any origin record, so that only the derived `(0,0)` is supported, until a distinct, explicitly approved origin authenticator kind exists.

If origins are kept instead:
- Use a distinct kind.
- Keep the delivery row equal to `_source_audio_range`.
- Apply the origin only to the native-unit → PCM conversion.

**Tests:**
- A geometry-kind seal over an origin payload refuses.
- A delivery row that differs from the accepted oracle refuses.

---

## Major findings

### M1. Identity-string limits are applied to every string in foreign accepted records, so real inputs may refuse

**Where:** `_tree` (`records:173-174`) runs `_identity` on every string and key. That means length 1–512, with no Cc/Cf/Cs characters. This applies to:
- the raw manifest (`v2:670`)
- the #190 narration row (`:395`)
- the #174 preparation receipt, including ffprobe probes and commands (`:395`, `:505`)

Plan line 56 bounds *identity strings*, not every field of accepted external documents.

**Strings that would refuse:**
- an empty string
- a script-marker or slate text longer than 512 characters, or containing `\n` or `\t`
- text containing a soft hyphen or ZWJ (both Cf)
- a control-prefixed ffprobe tag

All current positives use synthetic manifests and receipts. I could not inspect real R16 bytes, so impact on them is unverified.

**Repair:** for foreign records, keep duplicate-key, nonfinite, unsafe-integer, depth and size refusals. Apply `_identity` only to fields 214 consumes as identities.

**Tests:**
- A manifest with a multi-line, 600-character marker note passes.
- A row with an empty `blockId` refuses.
- Re-run the private audit over the frozen R16 manifest, dependencies and receipt bytes.

### M2. The trusted port receives only `inputBindingSha256`, and parts of the binding are mutually matching caller data

**Where:**
- The geometry authentication payload (`v2:256`) carries only the input-binding hash.
- No `OutputTrust` call receives the closed input binding.
- `INTERFACE.md:67` cites a "package binding receipt" that does not exist in the code.

**What 214 re-derives:** audio delivery rows and source entries.

**What 214 does not derive or check:**
- video and placeholder delivery `recordRange`/`sourceRange` against the manifest (`v2:697-705` is shape-only, yet the pristine coverage check at `:733-751` trusts these rows)
- tracks against the manifest (`:264-265` compares two caller copies)
- non-audio `nativeSources` hashes against manifest `deliveredHash`/slate content (`:658-667` checks audio entries only)

An adapter would have to reconstruct 214-private canonical binding bytes from a hash alone.

**Repair:**
- Pass `inputBinding=binding` as an additional authenticated field.
- Derive video and placeholder delivery rows using the `v2_package.py:1760-1802` rules.
- Check track id, kind and index, and non-audio native hashes, against the manifest.
- Correct `INTERFACE.md:67`, and define what bytes the `package`, `runtime`, `installedRelease` and `profile` blobs denote. All are bounded at 8 MiB by `records:546-549`.

**Tests:**
- A resealed geometry with a shifted video delivery row refuses.
- A track index mismatch against the manifest refuses.

### M3. The vacuity refusal happens only after the native effect

**Where:** `v2:1131-1136` raises after the render. `create_prediction` (`:901-926`) never checks vacuity, even though vacuity is a property of the prediction alone.

**Effect:** a silent-channel prediction, or a No-only case, can be committed, reserved and rendered, and then strands the attempt as `uncertain` (plan line 74).

**Repair:** run the zero-vs-prediction gate in `_candidate`/`create_prediction`, and keep the check in compare.

**Test:** a stereo source with a silent right channel refuses in `create_prediction`.

### M4. The ledger chain identity includes target names, so a rename forks the history

**Where:** `_ledger_key` hashes the full target, including names (`records:401`). `_ledger_head` refuses a chain whose `(targetHash, case, phase)` varies (`:428-430`).

**Effect:** renaming the Resolve project or timeline (same UIDs) after a refusal produces a new binding and also a mandatory new, empty chain. The prior attempts are absent from what the new result's `priorLedgerHeadSha256` covers. The pure checker even forbids #209 from keeping one UID-keyed chain that spans the rename.

The implementation matches the literal plan text ("target" = names + UIDs). This needs a plan-owner confirmation.

**Recommended repair:** key the chain by `(projectUid, timelineUid, caseId, phase)` and keep names in the binding. A rename then becomes a disclosed new binding within the same chain.

**Test:** after a refusal, a renamed-target commit appends to the existing chain.

---

## Minor findings

1. **`private_preparation` is reused with a new payload shape** (`v2:524-533`): `{context, preparationBindingHash, recordSha256, binding}` versus accepted #190 `{originalInputs, binding, sourcePins}` (`roundtrip_v2_build.py:438-446`). An adapter must now multiplex two shapes under one old kind, and the INTERFACE describes this as "retained". Document it as a distinct new-lane shape, or use a distinct kind, and test that each shape's seal fails the other.

2. **The pair operation needs pre-terminal ledgers** (`v2:1209-1212`): it calls `compare_committed_output`, which demands that the latest entry be `reserved_by_render_intent` (`:1058-1068`). Pair evidence therefore requires supplying a truncated pre-terminal history, which `INTERFACE.md:132-133` says is never integration. The pair result also omits the `geometryStability` and `controlStability` labels. Accept the sealed terminal results plus the current ledger instead. `_terminal_append` and `_append_ledger` are also private names that #209 must import.

3. **Non-refusal exceptions can escape:**
   - `_ordered(deliveries)` runs before `_shape` (`v2:696`).
   - Raw subscripts into the manifest and receipts (`:440`, `:467`, `:505`, `:535-540`, `:677-686`) can raise `KeyError`/`TypeError`.
   - An unhashable `state` raises `TypeError` at `records:489`.

   Controllers keyed on `OutputConsistencyError` would see these as crashes. Convert them, or shape-check first.

4. **Raw encodings:** `json.loads(bytes)` (`records:214`) accepts UTF-8-with-BOM, UTF-16 and UTF-32 records. The accepted `_parse` rejected these by decoding UTF-8 explicitly. Require strict UTF-8 without a BOM.

5. **Test assertions are weak or vacuous:**
   - The `verify_selected_omission_v2` check (`test_issue214_comparison.py:442-455`) refuses at "stale document" before reading anything, and `prediction.json` is not a file it reads. Plan B5 is therefore untested.
   - No test passes old observation, `native_render` or audio-observation records into the new consumers.
   - There is no positive end-to-end Quiet or source-audio comparison.
   - No positive runs against a #174 receipt shape that passes `_validate_preparations`.
   - The `old_mix` differential exercises only `recordStart=0`/`sampleStart=0` single segments.
   - The nonzero-origin test has no oracle (see B4).

6. **Preflight/preparation exclusion (your explicit question):** I found no retry hole. Excluding these fields coarsens the key, which can only add refusals. However, the stated rationale (`records:42-43`, `INTERFACE.md:69-77`) is inaccurate.
   - The preflight is a content record (`PREFLIGHT_KEYS`: `requestHash`, `verifiedFiles`, `needs`, `packageVerification`, `unchecked`, `revisionBinding`), not an authority envelope. `requestHash` changes with the authority pin, which is why exclusion is the safe direction.
   - Its content is carried elsewhere only partly: manifest, report, inputs, source graph and revised binding are covered.
   - Sidecar `contentHash` and `q` are covered only if `packageSha256` is an attestation that lists them, and that is undefined.
   - Plan line 28 says the exclusion must never cover content fields, so this is a literal deviation that needs a field-by-field coverage note.
   - The real retry exposure runs the other way: included fields that change without a content change, such as target names (M4).

---

## Criteria verified as met

- Closed shapes, versions and lane; duplicate keys; NaN/Infinity; unsafe and bool-as-int values; lowercase raw64 digests; codepoint ordering; nesting depth.
- Stable binding derived from context with no caller preselection; one reservation per key; uncertain, terminal and refused states blocking restart; `expired_unused` identical-bytes recommit; per-key lineage equality.
- Acyclic receipt projections excluding exactly one field; prior-terminal-head CAS including the interleaved case; no post-terminal hash in the result.
- Full/Quiet `(policy, gain)` pairs from the manifest; No as absence of an event; narration at 0 dB.
- Hash domains kept distinct: WAV-file vs packed-s24 stream vs int32; `sha256:` normalization.
- Exact equivalence of the q/r rational conversion with `_source_audio_range`.
- Narration `(0,0)` with CEIL-overrun refusal; pristine/rebuild exact coverage vs edited containment.
- Ordered `+=` mixing; float64-LE byte recomputation; metrics identical to `_metrics(..., [[1.0]])`; both-channel nonvacuity; 0.18/0.19 FS and 0.0005 offset gates; clipping codes; raw and decoded-channel alias refusals; all bounds.
- Same-MOV decode profile; job/output lineage via decode authentication.
- stdlib-only import closure; all four result labels present.

## Limits of this review

- Static review of the supplied excerpts only. No execution, no access to actual R16 or #174 bytes, and no inspection of the contents of the report, package or release artifacts.
- The impact of M1 on real data and the semantics of `packageSha256` are unverified.
- #209 persistence, effect order and decoder qualification are out of scope by design.
- The final local full gate, including the owned slow stress test, remains required after repairs and delta review.
