# Issue 109 — Injected Workflow Integration delivery

Owner: chat `01a12bd6-e49c-7613-b429-649bf4eaaabd`, gpt-6.1-sol/xhigh,
branch `codex/issue-109-injected-delivery`. Acceptance: Producer.

## Authority and pins

Baseline: `5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`. The first roadmap
mutation successfully claimed #109 on 2026-10-11T16:41:57.696Z; re-inspection
confirmed the exact owner/profile, In progress, and #6/#107/#34 Closed/Done.

- #34 accepted source: `2586dded4d3566e944d7938604b20bded6fc36fb`, recorded
  in issue comment 5973622406. Its assembly/adapter source matches the baseline
  byte-for-byte. Studio 21.1.0 build 14 passed; Free parity was explicitly
  skipped under the Producer exception, never passed.
- #107 accepted source: `c9614eaf7bf7aa88f4cf33e77180ff5a393377e4`, recorded
  in acceptance comment 5608749819. Python 3.14 injected startup, a separately
  verified hash inventory, and save/reopen of an empty configured timeline
  passed. Full media assembly was not accepted. These files are absent from
  main; reuse their standard-library inventory/attestation pattern, not their
  unaccepted full-build staging path.
- #147 accepted refinement: `75029de57baa594d3dfc7f509a09cfc21943e088`.
- Authoritative spec: Slice 1.6 and sections 9.1/9.3/9.4. #109 supplies the
  accepted injected alternative to the original external connection.

## Scope and exclusions

Consume one independently verified ready Authoring Project; bind its complete
inventory, receipt, manifest, verifier identity, and unique build-derived target
in an immutable hash-pinned attestation. The injected runtime rechecks this
input before creation and each subsequent mutating adapter stage. Use the
accepted public adapter for bins/media/events/tracks/markers/save/reopen and
extend readback to unused media, unexpected pool media and unexpected markers.
Pin created project/timeline unique IDs through current-context checks and reopen.
Preserve every partial
target and retain a uniquely named version-stamped report, including refusals.

Deliver a reproducible repository-owned Python script release and an exact
manual installation/update/operator runbook. No external bridge fallback,
browser UI, durable jobs, renderer/upload, production target reuse, Fairlight,
audio reattachment/sidecars, arbitrary Fusion controls, or new graphics event
contract. #108/#116/#157/#158 remain separate owners, not dependencies.

## Reach, contracts, fixtures, dependencies

Reach: the existing Studio spike's verifier import location; new standard-library
handoff/runtime/launcher modules; external preparation/release command; new
slice-owned tests; README, plan, runbook and evidence. Existing callers keep
their verification behavior. Existing accepted tests remain unchanged.
No shared contracts, compiler/package contracts, generated output, frozen
fixtures, goldens, locks or dependencies change. Temporary synthetic packages
reuse the accepted #34 helper and frozen inputs read-only. Package files remain
read-only. No research data, real installation or Resolve mutation by the agent.
Dependency justification: reuse standard library and the installed verifier;
add no dependency. Canonical prerequisites: #6, #107, #34, all Closed/Done.

## Checks

Test-first: independent verification and immutable attestation; missing,
unverified, stale and mismatched input refusal before creation; Python `-S`
startup without OTIO/jsonschema/site packages; unavailable object/unsupported
version; collision; package drift before mutation; exact assembly call order;
save/close/reopen failure; discrepancies; unique retained report and partial
identity; reproducible release and source integrity. Run focused tests,
`npm run validate:fast`, then serialized `VITEST_MAX_WORKERS=1 npm run validate`.
Retain outputs/hashes and audit frozen boundaries against baseline.

## Producer acceptance boundary

Prepare concrete release, request and runbook first. Operator manually installs
the versioned script, confirms External Scripting None and a disposable current
project, then explicitly authorizes one named new nonproduction target through
the preparation command. Launch the named Workflow Integration once; retain
the real version-stamped report and hashes. Inspect saved/reopened timeline,
all manifest media/events/tracks/ranges/markers and unchanged existing targets.
Do not substitute mocks for native evidence or close without explicit Producer
acceptance. 21.1.0/14 is the accepted assembly baseline; installed 21.1.1/10 is
an explicit calibration candidate, not an inherited full-delivery success.

## Forecast

Initial evidence-based estimate after source/claim inspection: 2–4 hours active
implementation/validation, moderate confidence. Primary uncertainty is native
version calibration on 21.1.1/10 and observable media/range readback. Operator
installation/native run/Producer response is additional wait, not active work.
Reassess after focused boundary tests and release packaging.

Checkpoint after 87 passing focused tests and runbook preparation: 20–45 minutes
active work remain, mainly serial full validation and source/hash audit. Native
acceptance remains operator wait. Baseline clean `npm ci` fails on the missing
word-timing workspace lock entry already owned by #193; dependencies were
installed using `npm install --package-lock=false --ignore-scripts` with no lock
change. A shipped ResolvePython 3.14.4 `-S` import passed without verifier/native
bridge modules; this is import evidence, not a native WI launch or acceptance.

Producer steering requires a Claude CLI antagonist review of the exact tested
commit before the native acceptance walkthrough. Retain the full findings and
disposition; fix substantive findings, rerun affected checks and obtain re-review.
Claude complements tests and does not supply native/Producer acceptance.
CLI availability was confirmed; allow an additional 10–30 minutes of active
review/fix work, contingent on findings. No issue chaining or self-acceptance.

Checkpoint after the initial serial full gate: 530 tests passed in 46m59s,
with lint/types/generated/TypeScript checks passing. Claude CLI reviewed tested
commit `8afb26e0af4c22b6fe382b003a847e6abde118b3` and required eight bounded
corrections to target identity, bootstrap integrity, authorization, hash/read
binding, result retention and complete readback. All are handled within the
slice-owned modules/tests; frozen boundaries stay unchanged. Findings and
dispositions are retained under `docs/verification/issue-109/`. Allow 30–60
minutes hands-on for fixes/checks/re-review, plus a separate serial full gate
whose first measured runtime was 47 minutes. Native/Producer wait is additional.
