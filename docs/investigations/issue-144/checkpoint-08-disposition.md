# Checkpoint 8 disposition: visual file workflow

Claude completed 9 read-only review turns, then 8 correction-review turns,
without permission denials. Full responses and exact prompts are retained.
Static advisory review is not independent tests, native evidence or acceptance.

## Findings and corrections

| Finding | Disposition |
| --- | --- |
| Capture protocol can accept a local package echo | Named #145 readiness gate. Independently review and qualify the real initial inspector/capture adapter; actual native facts must come from live getters. Expected package facts cannot fill missing native results. Nonce/hash binding alone does not authenticate live readback. Current tests are explicitly synthetic injected. |
| Outer CLI conflated process failure with evaluated refusal | Corrected and follow-up confirmed: timeout, abnormal child exit and I/O failure produce `fault`/70; evaluated rejection produces `refused`/2; absent required capture produces `needs_action`/2. Both timeout/exit-70 tests were red before correction. |
| Own first-baseline UID, symlink-parent and status defects | Corrected and statically confirmed. Complete occurrence IDs must equal verified native identity; proof writes guard all symlink components; status returns bound/unbound explicitly. |

Completed-decision replay rederives the actual semantic result from frozen
inputs, archived baseline and verified package/job identity before checking
receipt fields and canonical artifact bytes/hashes. Rebuild obtains a fresh
matching observation before native effects. Interrupted promotion after pointer
publication finishes the same receipt without another baseline advance.

## Validation

Final full `npm run validate` used Node 24.19.0, npm 11.17.0, Python 3.12.14 and
uv 0.12.5, via `npm exec --yes --package=node@24.19.0 -- npm run validate`.
Generated contracts are current; TypeScript lint/typecheck passed with 178
contract tests, tooling 1, progress 6 and roadmap 23. Python Ruff passed for
166 files, strict mypy for 67 source files, and **233 pytest cases passed**
(564.69 seconds). This includes all 14 new workflow cases. A prior full run
passed 231 cases before the final process-fault correction; it is not used as
evidence for that correction.

Focused semantic/CLI checks passed 26 cases. The 64-token timing artifact pins
its own CLI/semantic/compiler/helper source hashes and measures 2,080 candidate
compiles per visual proposal row; this is one controlled machine/profile,
not an arbitrary-document runtime bound. `git diff --check` passed. Protected
contract/fixture/generated/golden/accepted Studio/job/lockfile diff from the
starting baseline remains empty.

## Next bounded work

Reuse actual accepted NarrationService with an injected test
SpeechSynthesisProvider. Generate a whole revised row with fresh timing marks
from its complete text; preserve untouched rows' dependencies and relative cuts.
This separate explicit generation handoff does not turn PreparedBuild's existing
verify-only speech stage into a provider call or authorize paid/cloud use.

Still required for #144: complete audible-omission qualification, explicit
omission decision/canonical revision composition, whole-row generation handoff,
the guarded real WI observer/link/render file boundary, integrated three-case
checks and the operator runbook. Real selected-build/input qualification and
the disposable actual run remain #148/#145 work. No full harness completion,
native round-trip acceptance, music support or untouched human-work preservation
is claimed. #144 remains In progress.
