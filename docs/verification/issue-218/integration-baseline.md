# Integration baseline

Starting main: `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`.
The adjacent `foundation-inputs.json` records exact parent/pin/file inventory
and SHA-256 of the three retained compressed integration patches. Non-generated
imported files equal their accepted source bytes (the #12 module equals #7
after #7's accepted export change). Generated outputs also preserve main's
accepted #168 roots; generator currentness passed. Current v2 exports are
preserved; the two accepted foundation
exports are appended. No branch history is merged. No #8-only source or runtime
file enters; only the enumerated accepted #20/#12/#7 deltas are applied.
#3 is accepted capability evidence, with no required runtime import.

Before feature implementation, under Node 24.19.0/npm 11.17.0 and the frozen
Python 3.12.14 environment, all commands exited zero:

- `npm exec --workspace=@vera/contracts -- vitest run test/fusion-graphics.test.ts test/template-library.test.ts test/ev24-lower-third.test.ts`: 3 files, 36 tests passed. Includes original #7 manifest/report byte goldens and #20 use/copy semantics.
- `uv run --frozen pytest tests/test_fusion_graphic_contract.py -q`: 2 passed.
- `npm run check:contracts-generated`: generated types current.
- `git diff --check`: clean.

`npm ci` and `uv sync --frozen` completed with unchanged locks. A sandbox cache
denial was rerun with normal escalation; it was not a test failure. Integration
is retained as a separate commit before the provenance feature. These checks
prove the bounded baseline; final acceptance still requires the feature checks,
Claude review and applicable full gate. The package export delta makes this
candidate ineligible for qualified cloud substitution under the current policy.
