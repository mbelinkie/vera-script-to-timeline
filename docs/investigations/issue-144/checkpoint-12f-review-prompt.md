# Claude finished-code checkpoint 12f: whole-row service/cache and fresh rebuild

Review this bounded implementation before composition/WI. Follow the reviewed
12/12b and12f plan/clarification, producer row-audio policy and original144 scope.
Read-only tools; no edits, test execution or paid/cloud/native side effects. Same
configured model/account/session. On usage exhaustion stop; no workaround.

Prior12e is reviewed and committed/pushed atcdc0a53, focused13 passing in895.88s.
Prior12d full validation passed231 contracts and308 Python (one later forgery
case separate). Current12f Ruff/format, mypy79 and diff checks passed. Current
focus/full validation is pending; do not infer passes from assertions in source.

The test-first whole-row case failed at missing constructor seam. First wired
positive generated a whole revised recording and finalized actual dependencies,
but rebuild waited: intentionally stopping the accepted job after its five core
stages required explicit resume. Corrected by a tiny optional NativeStages
preflight invoked in _manifest before native intent/factory/effect. Original
default behavior remains unchanged. The existing job now runs all stages normally,
with actual durable compiler preview equality checked at native preflight.

The next7-case run had6 passes, including full fresh native round trip/retiming/
historical replay and missing-boundary/pointer-publication recovery. One test
expected ProofBuildError instead of the accepted immutable publisher's
BuildJobError (RuntimeError): the changed voice profile actually refused before
another request, correctly. Its assertion now expects that precise immutable
conflict. No safety gate was relaxed. Full synthesis/normalization/asset metadata
and payload hash snapshots were then added and guarded before replay; their
tampering cases and the interrupted-handoff case are currently rerunning. Full
validation must include the latest source before saving this integrated stage.

Actual code:

- New issue-owned roundtrip_generation.py uses OmissionProof's full actual
  decision/evidence/report/canonical rederivation. generate-omission requires
  current pointer and fresh complete accepted old edited raw facts before any
  service call. Reject refuses; missing actual injected synthetic service waits.
- One immutable generation-inputs.json binds accepted actual service request
  identity/config/adapter, normalizer profile/tool fingerprint/cache root, old
  snapshot/code and exact new canonical row. Existing proof lock/publisher;
  no second reservation/lock/store. Profile drift during crash/resume refuses.
- Guard local independent cache paths. On replay require actual accepted cache
  entries and retained source/timing/asset bytes before service execution. Missing
  synthesis on an input-only interrupted attempt refuses safely instead of an
  uncertain duplicate provider request. Complete9 metadata/payload file hashes
  for the new row's synthesis, normalization and asset are retained and compared;
  do not mistake those consistency hashes for external provider authenticity.
- Actual replace_row_narration/cache verification occurs immediately before every
  pure finalize-omission child call; compare the entire retained handoff. No old
  audio splice or timing subtraction. Retain canonical dependency/manifest/report
  preview and actual compiler-driven source materialization with one new source,
  all unchanged declarations/origins preserved. Actual ready four-input build
  differs from12e prepared_revision. Actual preview/durable output byte equality
  is mandatory before native effects. No canonical script serializer clone.
- Existing _decision dispatches by actual saved operator schema; visual revised
  status/birth UID gate stays strict. Omission old-target pre-rebuild freshness
  uses its separate complete split validator. Existing native job/intent/result/
  verification, fresh target check, baseline/CAS/promotion recovery are reused.
  A waiting durable job still needs its existing explicit audited resume API;
  supplying an adapter never silently retries it. Historical omission replay may
  only verify existing generation/cache/build evidence, never create a missing
  generation/native effect against a stale pointer.

Read full changed files and actual adjacent implementations where needed:
python/vera_timeline_agent/roundtrip_generation.py,
python/vera_timeline_agent/roundtrip_proof.py,
python/vera_timeline_agent/roundtrip_native.py,
python/vera_timeline_agent/roundtrip_build.py,
tests/test_issue144_omission_generation.py,
plus unchanged roundtrip_omission.py, roundtrip_narration.py and actual
NarrationService/cache/normalizer/compiler serializer/finalizer/job APIs.

Find actionable issues with exact file/line and failure scenario: false/stale
acceptance from rehashed generation/dependency/materialization/cache claims;
service drift or cache loss triggering a second provider request; historical
replay allowing new effects; source/clock/row/token/timing mistakes; other rows
modified instead of translated; old audio splice; preview checks after native
effects; failed/interrupted generation/build/promotion harming the original;
symlink/hardlink/parent escapes; original visual regressions or extra machinery.

State whether any blocker remains before combined accepted edits and WI/runbook.
Current positives are honest trusted synthetic closed-source/route/render cases,
not real source-support/native absence qualification (#145). Isolated linked
pair capture facts are explicitly injected; accepted assembly does not link it
implicitly. Original three named positives/composition and executable WI/runbook
still remain required; no narrower gate or issue closure is approved here.
