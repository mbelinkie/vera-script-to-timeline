# Claude checkpoint 2 — finished compiler entry and corrected plan

Review the current pinned branch checkpoint supplied with this prompt. Use the
existing read-only repository/code access; no additional Chrome/Desktop
connection, edits, native calls, GitHub mutations or dispatch. Producer requires
both plan and finished-work reviews through this browser while CLI access waits.

Finished segment:
- `packages/contracts/src/issue-144-compile-cli.ts`
- `packages/contracts/test/issue-144-compile-cli.test.ts`

This entry reads two literal input files, invokes the actual unchanged compiler,
returns exact manifest/report strings in canonical stdout, binds input byte and
code/schema/lock hashes, pins Node24.19.0 and labels the result `compiler_only`.
It writes no files, creates no native target and cannot promote a baseline.
Its one module-resolution hook maps only the compiler's `script-validator.js`
specifier to the accepted `.ts` source and deregisters after import.

Evidence: eight tests failed before the entry existed, then 70 passed with the
62 accepted compiler/validator tests, including byte-identical frozen goldens.
Focused ESLint, contracts typecheck and diff checks pass. Full validation and
integrated harness tests have not run. No accepted source/test/data/lock changed.

Please review correctness, failure output, actual compiler reuse, hash/provenance
binding, runtime/module-hook limits, determinism, input preservation and whether
the tests miss a material boundary failure. Identify misleading receipt claims
or needless complexity. Return ranked actionable findings with file/line and
concrete failure scenario; do not propose a general framework.

Also review the fully rewritten body of
`docs/plans/issue-144-roundtrip-harness.md` against your completed follow-up.
The linked-pair Producer choice is recorded. The concrete local PCM-splice route
and interior-token wording policy are being presented for Producer input; no
omission-rebuild positive is claimed yet. Distinguish #144's injected/public-input
checks from real-input availability and native acceptance in #148/#145; #148 is
blocked by #144, so do not introduce a dependency cycle by requiring its accepted
private inputs for #144 synthetic tests. Check the render/link entry and sidecar
binding, actual compiler anchor mapping, narration dependency provenance,
composition and uncertain recovery before the next implementation segment.

Any offline reconstruction numbers in your prior review remain reviewer evidence
until independently reproduced by retained repository tests. We will not treat
the review itself as a native run, calibration authority or Producer acceptance.
