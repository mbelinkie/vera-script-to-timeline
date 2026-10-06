# Checkpoint15 adversarial disposition and correction checkpoint

The producer authorized the completed-issue adversarial review and then these
fixes on2026-10-05. Same task/branch/sol-xhigh claim; Automated acceptance.
Original source0390b893 had passed full local validation and two actual CI runs.
It nevertheless had threeP2 closure gaps. No real actions occurred.

## Findings and implemented resolution

- P2-1: local preflight creates no job or boundary effect and explicitly lists
  full positive readiness as unchecked. Explicit locked resume-build/resume-rebuild
  continues the same known-safe job. Completed-stage integrity precedes custom
  callbacks; native classification is read-only. Missing/foreign/unverified/
  stopped/integrity-failed evidence blocks uncertainty. Generation preparation
  is separate from a possibly attempted call: one shared service-request intent
  across decision keys is reserved after validation immediately before processing.
  Missing synthesis after an intent cannot trigger another request. Cached
  synthesis may finish normalization; retained generation binds the intent.
- P2-2: baseline validation inputs are content-addressed and retain failed captures.
  Capture no longer silently links. The actual walkthrough explicitly links both
  targets, refuses premature unlinked rebuilt-target promotion, then links that
  target, captures fresh state and promotes once with stable replay counts.
- P2-3: audio-evidence-contract.md specifies exact files/fields/bounds/bindings.
  Supplier render receipts are not currently WI-job authority and pristine fixture
  calibration bypasses WI. The precise real WI→audio render/control bridge is a
  named #145 qualification blocker, not a current live success. Both pristine
  and edited per-channel residual limits are whole-programme RMS≤.0004 and
  maximum sliding20ms RMS≤.006, not peak sample bounds.

Source corrections187c420 and1b87f05 are reviewed. Claude approved the plan with
required shared-intent/validation-address refinements, then found one old
issue-owned status test and incorrect threshold wording. Parent's actual new
missing-both-native-records test caught a dispatch condition missed by Claude's
helper trace: completed native jobs must dispatch classification even when no
record exists. The caller now classifies whenever an explicit adapter is present;
completed adapter-free local reads retain their prior behavior. Claude explicitly
acknowledged the counterexample and approved the final caller fix. No accepted
job store, Studio assembly, narration service, frozen contract/fixture/golden or
previously accepted test was edited. Existing issue-owned safety assertions are
preserved with the new structured status.

## Actual evidence at this checkpoint

Pinned Node24.19.0/npm11.17.0/Python3.12.14, uv --frozen.
Capture retry2passed/2.82s; native/prepared/driver30passed/83.68s on preceding
correction source. Correction focus2:10passed/2test-harness failures/857.30s;
corrected fault hook and waiting exit expectation. Focus3 on187c420:9passed/
1missing-record-dispatch failure/464.78s. Its complete WI walkthrough passed:
1provider request,2native targets,6explicit links,2queued synthetic render jobs,
picture-only and unlinked-promote refusals, full-row replacement, safe rebuild
resumption and single pointer promotion with replay. Original failed logs and
interpretation are retained locally; none counts as a complete passing result.
CI37344569117/37344562122 on187c420 were deliberately cancelled after that known
failure and are not passing evidence.

Ruff/format/strict mypy92source files and diff check pass on1b87f05. Final native/
recovery/full ProofSession focus on1b87f05 passed30cases in596.51s. Full
npm run validate and actual CI on the final source must still pass; results and
exact commit/log hashes are recorded on #144 before Automated acceptance. This
checkpoint does not close the issue or authorize a real run, merge or successor.

## Retained limits and handoff

Nonblocking review notes remain: narrow inspector fault/status mapping, queued/
running exit semantics, deliberate deletion of immutable evidence, read-only
compare locking, and byte-derived decision identities. Different decision keys
have separate local native roots; actual deterministic-name collision checks
provide target protection and must be qualified by145. Shared request intents
independently protect synthesis. No deletion/whitespace rewrite is an approved
recovery flow. Music100, production finishing104 and post-prompter153 remain separate.
No weaker unlinked/muted substitute or extra positive capability is claimed.

#145 exact readiness handoff:
https://github.com/mbelinkie/vera-script-to-timeline/issues/145#issuecomment-5999341931
All prompts, full responses and dispositions are also posted on144:
5997634106/5997634527/5997927444/5997994564 (whole issue),
5998248035/5998445087 (plan),5999094878/5999242570 (source),
5999267368/5999328522 (final follow-up).
