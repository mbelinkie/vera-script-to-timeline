# Review of #167 at `2e4da71`: NO-GO

**Verdict: NO-GO.** There are three blockers. Two are inconsistencies between the design and CN-167-P1. One is hashed material that has no defined shape, so implementations can't agree on it. Each fix is small and stays inside the documentation. The rest of the design holds up when checked against the accepted sources.

## Blockers

### B1. The outcomes the adapter may report contradict the design's outcomes
- **Where:** CN-167-P1, the "v1 BuildReport" row, says the compiler emits only planned/blocked/unqualified/manual and the adapter owns only verified/failed. The design says otherwise in three places:
  - §6 sends a wrong edition/build, trim, speed or mapping to `unqualified` with `GRAPHIC_CUE_PROFILE_UNQUALIFIED`.
  - §6 sends a live graph/control/type difference to `blocked` with `GRAPHIC_CUE_NATIVE_BINDING_MISMATCH`.
  - §4 step 7 says the comp mapping is checked only "after actual placement".
- **Counterexample:** A v1 Studio build compiles to `planned_supported`. Then the adapter finds build 21.1.2 or a trimmed clip, or a graph mismatch after import with zero writes.
  - The compiler can't know the build number. `graphicDeliveryTarget` is only `studio`/`free`.
  - The design therefore requires the *adapter* to report `unqualified` or `blocked`, which the CN forbids.
  - An implementer must either call it `failed`, which breaks the design and its "zero semantic writes, not failed" distinction, or break the CN.
- **Smallest fix:** In the CN v1 and v2 report rows, let the adapter replace `planned_supported` with `verified | failed | blocked | unqualified`. Bind each to the §6 codes and the receipt. Reserve `manual_required` for the compiler.

### B2. The endpoint evidence that feeds `cueScheduleHash` has no defined shape
- **Where:** CN, "Concrete output shape details", the endpoint field `evidenceHash`.
  - For word endpoints it "identifies the verified frozen timing/boundary evidence, including exact audio and text binding". No existing hash or field is named.
  - Derived endpoints (`duration_derived`, `next_cue_start`, `graphic_end`) point to "an addressed evidence record". That record has no fields, schema version or package inventory entry.
- **Counterexample:** Two conforming implementations resolve the same frozen input. One hashes `{blockId, tokenId, timingMapHash}`. The other hashes `{audioHash, tokenId, text}`. Their schedule bytes and `cueScheduleHash` differ.
  - This breaks the claim that identical input gives identical schedule bytes.
  - It also breaks the requirement that the package verifier "derive … independently and reject discrepancies". The verifier can't recompute the hash.
- **Smallest fix:** Define one closed `GraphicCueEndpointEvidence` record:
  - `schemaVersion`, `basis`, `blockId` and block version, `tokenId|null`.
  - The existing timing-map, audio and text hash fields, named exactly.
  - `durationMs|null`, `nextCueId|null`, `occurrence|null`.
  - Set `evidenceHash = H(record)`, list the record in the package inventory, and require the verifier to recompute it.

### B3. The v1 timing anchor type is not named for the only runtime path
- **Where:** Design §3, the `timing` row, says `start`/`end` "reuse current `PointAnchor` shapes". The CN "v1 ScriptDocument" row adds `graphicCueSets`, but does not name any anchor or `TimedPlacement` definition for v1. The handoff (#220) is v1-only.
- **Counterexample:** The supplied evidence shows `PointAnchor` and `TimedPlacement` only in `script-document-v2.schema.json`. A v1 `GraphicCueSet.timing` can't be written into a closed v1 schema without guessing one of three things:
  - copying the v2 definition,
  - referencing it across schemas, or
  - inventing a subset limited to word onset and audible end.

  The "owning narration block" of a v1 `VisualEvent.range` is also undefined if that range crosses blocks.
- **Smallest fix:** In the CN v1 row, name the exact v1 definition to add or reuse, and its allowed kinds (word onset, evidenced audible end). Add it to the generated-type consequences. State that a v1 graphic whose range spans more than one block refuses cues in this profile. If v1 already has an identical definition, citing it is enough.

## Non-blocking improvements
- **v2 `contentPin`:** "v2 additionally pins `graphicId/revisionId`" has no closed form. State whether these are fields required only on the v2 branch or a separate v2 pin variant.
- **`recordRange`:** "v1 boundary converts to existing start+duration shape when embedded" conflicts with the schedule being addressed rather than embedded. Fix one schedule shape for both versions.
- **v2 ownership:** CN v2 ScriptDocument, dependency and report deltas, including the required unsupported result, have no owner, because #220 is scoped to v1 only. Mark them deferred and unowned in the CN, or name an owner.
- **`ResolvedGraphicTargetBinding`:**
  - State whether `datasetSha256` is a prefixed `Hash`.
  - Say who issues `profileId`, and the format of `profileEvidenceHash`; #99 seems likely.
  - These are trusted inputs, so determinism is not affected.
- **v1 `ev24-table` provenance:** Since the branch is new, make `provenance` *required* on it rather than inheriting the optional lower-third rule. That prevents legacy-unclassified Table content.
- **Diagnostic sort key:** The order is undefined when there is no cue ID. Suggest sorting absent values first.
- **Handoff status:** The handoff says #167 is "In progress" while the plan says "In review". This is probably just a snapshot difference.

## Verified with no finding
- **Hash domains:** These are kept distinct and correct:
  - template, manifest, dataset and declaration byte hashes,
  - `S`, `P`, cue set, schedule, binding and plan hashes,
  - #20's `resolvedSnapshotHash`.

  The semantic hash `S` (#7) and provenance hash `P` (#166) are unchanged. Table enters as a typed branch through CN-167-P1, after #218.
- **Two-of-three timing:** It compares exact rational times and quantizes once with ceil. `999 ms` is refused and the frame-collapse cases are right. The 2.001 s example works out: 48.024 rounds up to 49, which gives one frame, and two endpoints at 49 collapse.
- **"Next" start:** Global strictly-later start grouping is consistent across §1, §4.5 and all §5 rows. One example: the A cue ends at 72 rather than 120. Equal starts share a boundary, and the collapse refusal on the same frame holds.
- **Aggregation:** Atomic sweep, equal-state union, explicit base-versus-emphasis conflict, half-open touches, frame-0 initialization, no write at N, and the `""/"1"/"2"/"1,2"` mapping all match the #219 manifest. Every §5 expected schedule recomputes correctly.
- **Invalidation and recovery:** Whole-manifest invalidation, no relabel/position remap, and explicit rebind on a `P` change all agree with #219 and #166.
- **Profile honesty and runtime gating:** These stay within #219's accepted evidence. #8, #167, #218 and #99 are canonical dependencies of #220, and nothing is dispatched or authorized.
