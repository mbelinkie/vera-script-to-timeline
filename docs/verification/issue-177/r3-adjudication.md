# R3 GO and retained limits

Actual Claude R3 returned **GO** for the delta from `3021546` to `9d43f61`.
This is a source-reading review: the reviewer did not execute the tests. The
actual result, prompt identity, start/exit and complete report are retained as
`claude-r3-*`. All source fixes required by R1/R2 are covered by that GO.
No further executable or test changes are made for the observations below.

## Evidence gap resolved

Ruff 0.16.4 formats Markdown as well as Python. The precise added format inputs
between FAST-R3 (447 files) and the R4 remainder (449) are the tracked
`claude-r2-review.md` and `r2-adjudication.md`. A verbose formatter inventory and
the retained before snapshots establish this; no extra Python file was added.
`ruff-inventory-disposition.json` records the command and identities. The Python
lint inventory contains 183 files, all tracked, with unchanged membership.
The pinned toolchain block is now in the remainder summary. These documents
are consumed by formatting checks, so final validation includes them.

## Non-blocking coverage and trust limits

The package's geometric layer guard is preserved and reviewed against the
accepted compiler; the role-list permutation has a positive unit test. Swapped
index/role refusals are exercised at the independent runtime/attestation guard.
There is no separate negative unit test of the rewritten package-layer guard;
do not claim that specific isolated coverage. The public attestation boundary
and fake reopened native readback remain the acceptance coverage here.

The accepted compiler checks additional reuse-specific rate, decoded-count,
time-base, probe identity and empty-command invariants. The package validates
receipt/probe/profile/tool/mapping hashes, original/delivered byte identity,
reuse origin, ranges and absence of fictional derivation; it does not duplicate
every compiler predicate. The verified reuse positive fixture satisfies the
compiler predicates, and the reverse report-status negative tests the repaired
D1 seam. R3 classifies additional duplicate checks as optional hardening, not a
D1 blocker. This package verifier is not a replacement compiler or authority to
invent compiler output. Arbitrary hand-authored semantic artifacts are not a
qualified upstream producer; #157/#160 retain the actual compiler handoff.

The synthetic child test now has its own occurrence, preparation binding,
source/event provenance and real public handoff, but its visual sequence
resolution still contains inherited placeholder references. The package retains
that complete metadata without independently recompiling it. This test proves
package topology, ranges and handoff, not complete equivalence to a newly emitted
compiler artifact or payload-to-occurrence compiler diagnostics. Do not describe
the whole child fixture as byte-for-byte compiler output. No accepted golden is
changed, and no unresolved item is relabelled as solved.

These limits remain bounded integration evidence for the existing upstream
compiler/application handoff and later #178 real Studio gate. Final full local
validation must still pass on this reviewed implementation and the retained
evidence documents before Automated acceptance or merge.
