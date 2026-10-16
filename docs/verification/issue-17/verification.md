# Issue 17 verification and acceptance evidence

## Delivered scope

Task `01a13146-5a49-7421-b5c6-a39f9aa90b64`, branch
`codex/17-external-template-pipeline`, starting commit
`98b9a614bad0539a9df5a29abab63345041c9135`. Documentation and its audit only.
See the [guide](../../external-template-pipeline.md) and
[plan](../../plans/issue-17-external-template-pipeline.md).

## Criterion traceability

| #17 criterion | Guide coverage | Source/evidence |
| --- | --- | --- |
| 1. End-to-end workflow | Receive; register/copy; controls; layered verification | S12 package/profile/approval and S20 domain APIs; `.drfx` extraction/install limitations explicit |
| 2. Layout, rights and pinning | Repository layout/record; intake; copy | S12 exact asset layout and rights; S20 manifest, digest, destination identity and redistribution checks |
| 3. Layered automated/Resolve strategy | Layered verification | S12 12 and S20 15 accepted test inventories; runtime cases are a future plan, not claimed new evidence |
| 4. Troubleshooting/change control | Troubleshooting and change control | Named source failure codes, exact-profile boundary, immutable revision/product-spec rules and repository frozen-change/escalation requirements |
| 5. Reusable producer handoff | Reusable Producer acceptance handoff | Concrete artifacts, seven ordered steps with expectations, visual judgment, exact ACCEPT/FAIL; not repeated approval of #17 |
| 6. Exact accepted evidence and planned limits | Accepted sources; boundary table; semantic controls | Six Git artifacts pinned in source-pins.json; accepted board comments verified; #8/#9 not certified; badge identity syntax does not prove availability |
| 7. Documentation audit and applicable gate | Documentation verification; this record | Audit covers local links, source hashes/anchors, section/boundary presence, scope, negative checks and whitespace; review and final results below |

## Source provenance

[Source pins](source-pins.json) retain SHA-256s for source, tests and acceptance
notes at accepted #12 commit `59838d6a8bf7fa536af3382788a947f5701a7d2c` and
#20 commit `951c658bf06fc9b06caeab88c9d43809c41cef94`.
Their issue comments explicitly name these revisions and record Producer
acceptance. Source was read using `git show`; no source branch was merged,
no package bytes copied or uploaded, and no accepted artifact modified.

The 2026-10-12 workstation preflight is supplementary context only: installed
setting syntax/expression compilation, asset presence and OS font availability
do not prove registration, rights or render acceptance. Current Quote Box source
matched installed bytes and its 51 offline tests passed. Table's 19 source tests
passed but its installed candidate differed from that newer source. These
counts are not S12/S20 tests or issue #17 runtime-acceptance evidence.

## Applicable verification-policy gate

The starting checkout has no `docs/VERIFICATION_POLICY.md`; the canonical
primary copy was read as directed. Its documentation-only provision permits
diff/link/whitespace checks where executable/check inputs do not change.
This is that provision, not reuse of an old full-suite pass or CI substitution.
Canonical policy SHA-256:
`9fd60f330ef33af277d108772412d5e5bd9b907155864656362243b8263f9274`.

Input inspection: root package.json selects generation, JS/TS lint/types/tests,
Python Ruff/mypy/pytest. Generator reads `contracts/` and compares generated
outputs. ESLint selects `scripts/*.mjs` and workspace source/test files; TS
configs select workspace source/tests. Python checks select Python files and
pytest's configured test directory. The new audit is `.mjs` under docs and
explicitly run only by the command below. Existing tests that read docs name
other fixed investigation/verification paths, not issue-17 or this guide.
Roadmap reads `.github/vera-roadmap.json` and explicitly supplied create bodies;
progress reads board inputs, not these documents. No dependency, lockfile,
generated artifact, packaging configuration, source, test or existing consumed
document is changed. The audit enforces the complete changed/untracked path set.

No full or fast suite was started: there is no applicable product-input delta
to justify competing with the shared expensive-test queue. This does not certify
the starting baseline's current full-gate state.

## Review and final checks

Focused criteria/source/confinement review completed against the seven criteria.
No independent/Claude reviewer is explicitly named by #17 or its selected
mechanical-documentation route. Review checked the exact source control map,
year/otis rejection, empty overrides, profile/timing/font pins, manifest/digest
identity, grants, copy rights, idempotency and lifecycle behavior. It also
checked the future Resolve matrix and ordered acceptance handoff against the
issue's requested cases. No remaining blocking finding.

Corrections before final evidence: fixed a transcribed S20 command SHA; removed
an invalid product-spec anchor (the spec uses bold text, not a heading); made
S12 redistribution refusal and badge-ID syntax-only validation explicit; pinned
the installed candidate inventory separately from the newer Table source.
The final audit includes negative checks for broken links/anchors and changed
accepted-artifact hashes. It checks identity/trace anchors, not semantic meaning.

Final commands: `node docs/verification/issue-17/audit.mjs`, `node --check
docs/verification/issue-17/audit.mjs`, and `git diff --check` against the starting
commit and staged candidate. Retained result: [audit-result.json](audit-result.json).
The documentation audit uses only standard Node/Git functionality; observed
Node `v26.5.0` and macOS/Intel are recorded, not misrepresented as a Node 24
locked product gate. No product suite or accepted test was rerun.

## Remaining proposals

Existing Inbox #99 already covers starter package registration/verification and
depends on #12 and unresolved #62. Retain the concrete Quote Box/Table intake
proposal there without status/dependency/routing changes or dispatch. Need their
own semantic profiles, package/rights records and runtime matrices; choose the
installed Table candidate separately from its newer Fit/Shrink source. No new
product decision is embedded in this guide. #8/#9 remain separate integration.
Concrete sanitized proposal: [starter-package-proposal.md](starter-package-proposal.md).
Posted on [existing Inbox #99](https://github.com/mbelinkie/vera-script-to-timeline/issues/99#issuecomment-6134354215)
without changing its status, dependencies, acceptance or routing.
