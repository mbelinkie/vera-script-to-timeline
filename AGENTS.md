# Repository Agent Instructions

These instructions apply to the entire repository. Before working, read the
authoritative slice in `docs/Script-to-Timeline Product Spec - Fable Rev2.md`,
the relevant plan under `docs/plans/`, and `docs/IMPLEMENTATION_PROGRESS.md`.

## Slice ritual

- Keep work within one bounded slice and state scope, exclusions, touched
  contracts/fixtures, dependency justifications, automated checks, and the
  producer acceptance steps before implementation.
- Work test-first where practical. Compiler-touching slices require
  byte-identical golden-file tests from frozen fixtures.
- Finish with passing checks, a plain-language walkthrough and judgment calls,
  and the producer acceptance checklist.
- Producer acceptance is authoritative. An agent self-report never closes a
  slice.

## Standing guardrails

- Do not expand a slice's scope; file discovered work as proposed new slices.
- Do not modify `/contracts`, `/fixtures`, golden files, or previously accepted
  acceptance tests without an explicit contract-change or fixture-change note
  approved by the producer.
- Do not add dependencies without a one-line justification in the plan.
- Anything irreversible in the real world—deleting files, touching the
  research project's data, uploading, or changing sharing—happens only inside
  the product's own audited flows, never as an agent side effect.
- When blocked or uncertain between two reasonable interpretations of the
  specification, stop and ask; a wrong guess embedded in a contract costs ten
  times the question.

Contracts are frozen between accepted slices. Any proposed contract change
must state what changes, why, what it breaks, which generated types need
regeneration, and how acceptance changes.

## Shell commands

Always prefix shell commands with `rtk`, following
`/Users/matthewbelinkie/.codex/RTK.md`:

```sh
rtk git status
rtk npm run validate
rtk uv run pytest
```
