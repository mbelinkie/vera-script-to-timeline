# Claude checkpoint 3 — compiler corrections and next bounded seams

Act as the independent reviewer of VERA issue #144. The Producer explicitly
requested both plan and completed-segment reviews and now authenticated the
Claude CLI for direct exchange. Read-only review only: do not edit files, create
claims, run Resolve, import private media, access credentials or publish anything.
Use only repository reads. No additional tools, plugins, connectors or agents.

The local repository is the pinned checkpoint committed immediately before this
request on `codex/issue-144-roundtrip-harness`. Review the current files directly.
Authority: #144 is an Automated bounded file-driven harness; #148 prepares private
real input, #145 owns the later disposable native run. No new native actions,
paid services, acquisition, transcript generation, accepted source edits, frozen
contract/fixture/golden changes, or scope substitutes. Accepted #34 Studio
assembly and #35 jobs remain byte-identical to baseline `9c8973d`. Producer chose
tested linked move/trim with isolated SetClipsLinked setup, using separate source
video/audio. Narration route/wording question is pending; omission rebuild positive
must wait. Do not treat your review as Producer acceptance.

Read:

1. `docs/plans/issue-144-roundtrip-harness.md` (entire corrected plan).
2. `docs/investigations/issue-144/claude-checkpoint-02-verbatim.md` and
   `checkpoint-02-disposition.md`, then earlier reviews if needed.
3. `packages/contracts/src/issue-144-compile-cli.ts` and its issue-owned test.
   Unchanged compiler, validator and canonical serializer as needed.
4. `docs/investigations/issue-144/measure-retained-w1.py` and its report
   `retained-w1-reconstruction-measurements.json`.
5. Relevant accepted build_jobs, Studio assembly and resolve_import_package APIs
   for the planned next host adapter segment. Do not assume injected tests prove
   an actual run.

Completed compiler changes: sourceHashes naming and separate lockfile; output
byte hashes; drift exit75; BOM refusal; 11 subprocess tests (73 including accepted
regressions) green on Node24.19.0, lint/typecheck green. Host strict parser will
reject duplicate keys/non-finite numbers before compiling. Re-read only observes
persistent drift. No claim to fully hash installed dependencies. Evaluate whether
this closes the receipt/failure concerns without an unnecessary custom JS parser.

Next bounded host stage: immutable strict input snapshot, Node-version preflight,
all five #35 core stages using verify-only speech/media adapters, actual compiler
entry, actual package writer and verifier, then accepted Studio boundary injected
in tests. Native side effects require intent before assembly and uncertainty
preservation; no duplicate target creation on lost response. #35 render/delivery
false; program PCM render is a separate later WI seam. Does this map the existing
APIs safely, and are there any plan blockers before that segment?

Audio gate proposal for retained W1 and controlled synthetic tests ONLY:
complete 48k PCM per channel, 20ms sliding residual; route gains fitted once from
unchanged full-program reference, frozen plausible range [0.69,1.01]; edited
mix is reconstructed from hash-bound observed intervals with those same gains.
Proposed max-window RMS 0.006 and whole RMS 0.0004 exceed all retained supported
residuals; both-channel partial-head/tail and opposite-channel tests must fail.
Require exact output extent and bound pre/post snapshot fingerprints, full known
route inventory, fixture-declared target/neighbor supports, full phrase excision,
and neighbor preservation. Unknown routing/effects, gain out of range, source
changes, incomplete output, identity mismatch or whole-route deletion refuse.
Do not generalize the resulting profile to arbitrary speech/private input. Does
the implementation/measurement or proposed frozen profile have a material false
positive gap? Explicitly distinguish calibration limitation from implementation
bugs. A fractional/very short residue may require conservative support checks;
whole-word correlation alone is not used.

Composition qualification: W1 observation has a real one-frame gap; a new narration
asset/event cannot literally equal old split native UIDs or source IDs. Candidate
compile is authority for every retained non-narration occurrence; explicit splice
segment map plus full mix establishes narration equivalence. Is there a safer
minimal comparison seam, or a hidden lower-coverage substitute here?

Future input readiness: no permission to silently accept #148 with missing audio
checks or bypass #145 dependencies. Missing local original narration stays a
named blocker for Producer/steward scope resolution. #144 injected/public tests
are independent of that gate. Confirm this handles the cycle without inventing
authorization.

Return actionable findings with severity, concrete file/plan location, failure
example and smallest bounded correction. State what can proceed now and what
must wait. Do not merely approve the plan. Note anything you could not verify.
