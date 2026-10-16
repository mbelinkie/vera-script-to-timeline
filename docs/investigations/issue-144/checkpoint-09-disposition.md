# Checkpoint 9 complete: whole-row narration handoff

Claude reviewed the plan (6 turns), completed segment (10 turns) and corrections
(6 turns), all read-only with no permission denials. Full prompts and responses
are retained and posted on #144. Review is advisory, not test/native evidence.

The new handoff uses unchanged NarrationService/cache/normalizer/projection and
the accepted standalone validator. It requests the complete revised row only,
verifies the new bytes, UTF-16 word timing and original synthesis provenance,
then replaces that one dependency. Media delivery locators remain separate from
cache origins. Untouched rows are never sent to the service. Original files are
preserved, identical replay uses cached generation, and another wording edit
generates again. Returned dependencies still need canonical omission integration
and fresh build IDs; this is not an omission decision or native acceptance.

Claude identified real-provider miswiring and missing returned provenance.
Two new refusal cases were red before correction. The handoff rejects the
accepted PollyProvider including subclasses, and checks the original synthesis
record rather than fallback profile labels. This is an explicit trusted test
injection, not a sandbox for arbitrary malicious Python providers. The alleged
cache intermediate-path escape was not reproduced: its new test already passed.
Claude retracted that finding after checking Path.parents. The consolidated
ancestor walk is a clarity improvement. Fresh import loads no cloud SDK.

Final isolated `npm exec --yes --package=node@24.19.0 -- npm run validate`
passed: generated-currentness, TypeScript lint/types, contracts 178, tooling 1,
progress 6, roadmap 23; Ruff/format (178 files), strict mypy (69 source files),
and **248 pytest cases in 781.60s**. This includes 15 new narration tests.
The prior 99-case regression run passed; an intervening validation run hit four
existing 5-second subprocess timeouts during concurrent tests and was not
counted as passing evidence. The successful final run was isolated, with no
timeout/test changes. `git diff --check` and protected boundary diff pass.

The two-row test executes actual compiler/package/jobs with no native adapter.
The first row gets new audio/marks and newly anchored cuts. The second retains
its full narration dependency and event/source geometry relative to row start;
only absolute placement changes. Synthetic tones/marks are explicit test data,
not verified spoken-absence evidence. There were zero native/cloud actions.

Next: reviewed checkpoint10 audio-evidence verifier, then canonical omission /
visual composition, generation wiring, guarded real WI boundary, integrated
three-edit checks and runbook. #144 remains In progress; #145 owns independent
real input/route/support/current-build/observer/renderer qualification and the
actual run. This checkpoint does not authorize that live work.
