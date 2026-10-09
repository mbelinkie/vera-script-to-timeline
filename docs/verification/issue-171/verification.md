# Issue #171 verification

Status: focused checks pass after adding the user-selected minimal typed
`PresenterAlignmentResolution` port. The dependency schema preserves slot/take
and master identity, source start frame, alignment version/precision, and paired
expected/recognized word records. Word matching remains semantic validation.
This record is for Automated acceptance and does not claim independent review,
issue closure, or runtime qualification.

Branch: `codex/issue-171-v2-generated-contracts`  
Baseline: `76c9f9635989415e3c7c2c15b2e6cc1ab9ddc7da`  
Accepted design: `e32727f0c0e65dc5a8561e0f470ed28e59bd1809`  
Routing: `gpt-6-luna / max`; task `01a11eff-470c-79a2-b47d-c399bef022d0`.

## Scope and contract boundary

Implement only P2 of the accepted #156 plan: compiler dependency, timeline
manifest, build report, preparation/timing, compiler result, and migration
diagnostic type shapes; separate v2 TypeScript/Python generated surfaces,
registries, exports, and currentness; and issue-owned synthetic schema tests
and samples. #170's document and project-settings schemas remain inputs to the
v2 generator. The Python root registry gains v2 exports while preserving its
existing v1 exports.

The frozen v1 schemas, generated TypeScript, five v1 Python schema modules,
accepted tests, fixtures, and goldens remain byte-identical to the baseline.
The shared Python `__init__.py` is intentionally extended with additive v2
exports; it is not claimed as byte-identical. New schema samples use only
synthetic identifiers, hashes, and locators.

No compiler behavior, media verification/preparation, migration execution,
service activation, UI, Resolve, external delivery, or production data is in
scope. No dependency or lockfile change was made. Existing Ajv,
json-schema-to-typescript, and datamodel-code-generator tooling is reused.

## Checks

Focused checks completed before the full gate:

- `npm run test --workspace @vera/contracts -- compiler-v2-schema.test.ts` —
  9 tests passed, including presenter-alignment shape, unresolved and
  temporary-still diagnostics, and replacement recovery action.
- `npm run lint --workspace @vera/contracts` — passed.
- `npm run typecheck --workspace @vera/contracts` — passed.
- `uv run --frozen pytest -q tests/test_issue171_generated_contracts.py` —
  2 tests passed.
- `uv run --frozen mypy python tests` — passed, 98 source files.
- `npm run check:contracts-generated` — passed.
- `git diff --check` — passed.
- `ruff check` and `ruff format --check` on the corrected new Python test —
  passed.

The generated-currentness check compares generated output against the schema
inputs. `source-pins.json` records exact source and artifact digests and the
frozen-v1 boundary check; all 19 artifact pins match the current files.

Full-gate attempt 1 started `2026-10-09T05:19:03Z`, exited 1 in the repository
wide Python lint stage. Its exact captured output is retained in
[full-validation-attempt-1.txt](full-validation-attempt-1.txt). It did not
reach mypy or Python tests. The lint issues in the new Python test were
corrected; the focused Ruff check and test pass afterward.

Full-gate attempt 2 started `2026-10-09T05:21:34Z` and was interrupted with
exit 130 after the interface audit found the missing presenter-alignment port.
The captured output file is empty; it is retained as
[full-validation-attempt-2-interrupted.txt](full-validation-attempt-2-interrupted.txt).
No full-gate pass is claimed. The field-shape question is now resolved; rerun
the required gate and retain it as [full-validation.txt](full-validation.txt):

```sh
rtk proxy env PATH="/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ctx-wire run rtk npm run validate > docs/verification/issue-171/full-validation.txt 2>&1
```

The actual passing run's exit status, completion time, tool identities, and
test counts will be recorded in [full-validation.json](full-validation.json)
after the command exits.

## Acceptance handoff

Issue #171 has Automated acceptance. After the full gate passes, retain its
exact status, command, tool versions/hashes, source pins, and byte-identical
v1 evidence, then move #171 to In review for independent review. This package
does not qualify runtime/compiler behavior and does not close #171.
