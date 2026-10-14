# #192 native mapping identity interoperability fix

Runtime2 completed against cbf5c1daa1d2608b77dd6c24e510c2577b6dbdae:
exit1, no signal, 1 failed in32.02s, stopped before all selected #190 nodes.
The log's SHA256 matches the immutable complete receipt:
1c759cdfed011b9ac9635fe375a078f9552ed2a38440044baa0ce77fe4a7a2ef.
Evidence stays in `out/issue192/runtime-2/`.

The selected-PCM correction passed baseline package validation. The next
failure was own inference's `item mapping hash differs` while consuming
genuine public #190 capture. The retained before_A mapping reconstructs to
Python compact identity hash889a6b7fa7871a917b1c31b83e68fae5b9b1eb1807ca567862d2e2aa9f50495d,
exactly its unchanged native observation receipt. Own TS used the compiler's
indented/newline canonical JSON, which is a different byte identity.

The only production change is the new #192 consumer. It hashes the native
mapping's compact JSON with keys ordered by UTF8 bytes (the Python Unicode
order for valid UTF8); eventId/sourceId are the closed string-valued mapping
fields. Explicit string assembly preserves ordering for numeric-looking UID
keys too. No generic compiler hash change, dual-format acceptance, rewritten
receipt, initial native change or fixture/contract waiver is introduced.

The new fake observation helper now emits compact mapping identity, matching
the existing native producer. The new integration negative supplies the old
compiler-form mapping hash and requires refusal. Actual public-path execution
is still required; fake observations alone cannot establish interoperability.
Focused ESLint and contracts types pass; 25 #192 Vitest cases pass including
the new negative. Exact inputs and immutable logs are retained in
`out/issue192/focused-28-eslint-mapping`, `focused-29-tsc-mapping` and
`focused-30-vitest-mapping`.

Changing the inference source changes the complete consumed proof source graph.
Prior packages, bindings and the10 passing transport tests from runtime1 are
therefore historical rather than equivalent final-source evidence. The next
bounded runtime rerun includes both new #192 Python test files plus only the
four selected #190 regression functions, with fresh packages/bindings. Run the
public path first so a demonstrated failure stops before unrelated repeated
work. Serial `-x --durations=25`, locked tools and retained coordinator scope
remain; no larger gate or actual native/provider/media execution is authorized.

Original #190 guard/effect/receipt bytes, #202 core/test, compiler/shared
contracts, accepted fixtures/goldens/tests and dependency manifests/locks are
unchanged by this fix. No final acceptance, review, Ready claim or closure.
