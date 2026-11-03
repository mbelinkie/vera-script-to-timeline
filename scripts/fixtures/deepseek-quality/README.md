# DeepSeek quality fixtures

These three small tasks are public, synthetic coding exercises. They do not
call a provider, Resolve, GitHub, or the dispatch controller. Each task is
self-contained. The only authorized candidate edit is its target file.

The Python tasks use:

    python3 scripts/fixtures/deepseek-quality/invoke.py INPUTS.json TARGET.py

The Python tasks pass the candidate target path as the second argument. The TypeScript task uses:

    node scripts/fixtures/deepseek-quality/invoke.mjs INPUTS.json TARGET.ts

Each input file is a JSON array of payload objects. A successful invocation
prints one compact JSON array with one result per input. A wrapper failure
prints one stable JSON error object and exits with status 2. The wrappers
contain no expected answers.

Run the visible checks from the repository root:

    python3 scripts/fixtures/deepseek-quality/prefix/visible_check.py
    python3 scripts/fixtures/deepseek-quality/validator/visible_check.py
    node scripts/fixtures/deepseek-quality/run_policy/visible_check.mjs

The supplied target files are intentionally incomplete baselines. Specs and
visible checks are public task context; hidden grading data is stored outside
this public fixture tree.
