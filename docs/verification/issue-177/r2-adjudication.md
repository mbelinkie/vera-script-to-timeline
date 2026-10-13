# R2 review adjudication

Actual R2 completed successfully as a review process but returned **NO-GO**.
The reviewer confirmed R1 B1–B4, canonicalizer/parser/document closure,
child `primary_visual`, and intentional slate fixes. D1 is a real remaining
compatibility defect: accepted `compiler-core-v2.ts:1324` emits `reused` for
`verified_reuse`, while the package expects `prepared` for every binding.
The fix must distinguish those modes and cover a genuine same-rate reuse
receipt through public build, verification, attestation and preflight. A
derived binding incorrectly labelled `reused` must still refuse. Source fixes
invalidate FAST-R3 for final acceptance; fresh focused/fast/delta review and
the full gate remain required.

## Saved document convention

The strict package input uses the accepted #189/#144 canonical-revision
convention: SHA-256 of compiler canonical JSON with only the root
`liveContentHash` removed. This is a package precondition, not a hash algorithm
specified by the v2 JSON schema for arbitrary producers. Accepted
`issue-189-v2-omission.ts:403–405` implements it after advancing the live head
and clearing the state vector. The new parity test executes the accepted
TypeScript canonicalizer; it does not independently establish writer authority.

A read-only investigator calculated that none of the 33 unchanged #173 input
golden documents matches that formula; those documents all use the synthetic
`sha256:aaaa…` sentinel. They establish compiler behavior, not package-qualified
saved snapshot identity. Accepted #172's plan (`:10–18`) and
`authoring-v2-edits.ts:46–52` say the pure visual edit leaves live collaboration
metadata to a separate application acknowledgement boundary. Its unacknowledged
return is not an eligible saved package snapshot. No actual application snapshot
writer is qualified by #177; #157/#160 must bind their saved writer output to
the retained convention before using this package boundary. Keep this precise
integration risk rather than dropping document content closure.

## Temporary presenter and effective defaults

Accepted #156 (`:232–238`) distinguishes a temporary presenter from an
intentional placed placeholder. The unchanged #173 presenter golden retains
`TEMPORARY_PRESENTER_STILL`, `REPLACE_TEMPORARY_PRESENTER`, a manual completion
item and `manual_completion` event disposition despite a ready status envelope.
The package's fully-ready/placed-only gates correctly refuse that unresolved
state. Still/default/slate coverage does not grant temporary-presenter readiness.

The compiler selects a script override, then project default, then pinned torso
(`compiler-core-v2.ts:992–994`), and substitutes the effective presenter into
manifest defaults only for active narration containing On Camera (`:1409–1411`).
Tests must not overwrite that evidence to pretend an unresolved presenter is
ready. No real presenter/native picture qualification is claimed.

## Slate environment and final evidence

The unchanged #34 renderer uses zlib `Z_FIXED` and no installed fonts or drawing
API. Exact regenerated PNG bytes are compared by the independent verifier;
runtime only rehashes the bound bytes. CPython version alone does not promise
identical PNG compression across all zlib builds. The current local environment
is CPython 3.12.14, zlib compiled/runtime 1.2.12, macOS 15.1, x86_64. A verifier
that regenerates different bytes refuses; cross-platform renderer identity is
not claimed. Repeated rendering cost stays a bounded measurement concern, not
permission to weaken independent byte checking.

Final qualification will use the local full gate after GO. The new package
calls a renderer even though the renderer itself is unchanged, so the narrower
cloud substitution is not used to resolve that eligibility ambiguity. Real
Studio/media qualification remains #178's External gate.

Focused-R3 passed all 94 issue-owned tests on unchanged `84a6612` with no
skips. Actual start/exit receipts and complete scrubbed output are retained
as `focused-r3-*`. Static Ruff/mypy checks also passed. Fresh fast validation,
required delta review, and final full validation remain pending.
