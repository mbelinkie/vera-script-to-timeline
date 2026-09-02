# Repository Agent Instructions

These instructions apply to the entire repository. Before working, read the
assigned Ready issue on the GitHub Project configured in
`.github/vera-roadmap.json`, the authoritative slice in
`docs/Script-to-Timeline Product Spec - Fable Rev2.md`, and the relevant plan.
`docs/IMPLEMENTATION_PROGRESS.md` is retained as a historical orchestration and
acceptance record, not a live tracker.

## Slice ritual

- Keep work within one bounded slice and state scope, exclusions, touched
  contracts/fixtures, dependency justifications, automated checks, and the
  producer acceptance steps before implementation.
- Work test-first where practical. Compiler-touching slices require
  byte-identical golden-file tests from frozen fixtures.
- Finish with passing checks, a plain-language walkthrough and judgment calls,
  and the producer acceptance checklist.
- The GitHub Project's `Acceptance` field names the closing authority. For
  `Automated`, retained passing commands/tests are sufficient evidence; for
  `External`, retain evidence from the required real application or service;
  for `Producer`, explicit producer acceptance is required. An agent
  self-report alone never closes any slice.
- Require one Ready issue, one task, and one dedicated branch/worktree. Claim
  only an exact `model:*` and `effort:*` match through `npm run roadmap`.
- Record prerequisites under `## Dependencies` as `- Blocked by #123` or
  `- Blocked by owner/repo#123`, or `None`; hierarchy alone does not imply
  ordering. Promote only with `npm run roadmap -- ready <issue>`. Both Ready
  promotion and claim require every dependency to be closed and `Done`.

## Standing guardrails

- Do not expand a slice's scope; file discovered work as proposed new slices.
- File out-of-scope discoveries as Inbox issues and do not start them. If the
  assigned profile is insufficient, stop, mark the issue Blocked with
  `needs:model-escalation`, retain evidence, release the claim, and wait for
  steward-approved relabeling.
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

## Producer learning channel

- Keep implementation, roadmap, review, and acceptance tasks focused. Do not
  include teaching asides or "engineering lens" notes in their commentary or
  final responses.
- When a completed milestone, important tradeoff, surprising failure, contract
  boundary, or useful test reveals a genuinely helpful big-picture lesson,
  send the lesson context to the dedicated Codex task **VERA Engineering
  Lessons** (`threadId: 01a0627e-a2ea-7ab1-8975-9a85c5e8b4e9`, `hostId: local`)
  with `send_message_to_thread`.
- Ask that task to turn the context into one brief, self-contained lesson in
  simple, non-technical language. Avoid jargon; define any unavoidable term
  plainly. Do not go deeper unless Matthew asks a follow-up there.
- Include the source issue or task title when available so the lesson remains
  connected to the real project. Send at most one lesson per meaningful
  milestone, and skip lessons that would be repetitive or forced.

## Shell commands

Always prefix shell commands with `rtk`, following
`/Users/matthewbelinkie/.codex/RTK.md`:

```sh
rtk git status
rtk npm run validate
rtk uv run pytest
```
