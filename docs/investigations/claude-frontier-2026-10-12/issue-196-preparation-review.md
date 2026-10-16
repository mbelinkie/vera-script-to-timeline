# Issue #196 preparation: bounded Claude review

2026-10-12. Producer requested useful work within the remaining Claude usage
window. Two independent read-only Claude Code reviews used latest `opus`
(`claude-opus-5-5`) at high effort, with all tools disabled. No tests, code
edits, installs, CI, pushes, merges, acceptance or activation occurred.

Candidate: `d2720d9`, preparation baseline `353184b`, branch
`claude/issue-196-cloud-validation-prep`. The candidate and its handoff live
in the dedicated preparation worktree. This review is not qualification.

Reviewed packet: AGENTS/CLAUDE, verification policy, approved cloud plan,
preparation handoff, workflow, four cloud-evidence scripts and root manifest.
It did not include every underlying test, tool configuration or official API
documentation. Platform/library assumptions require verification, not adoption
as proven defects. Parent inspected the validator, collector, library, workflow
and relevant root-manifest references; no exploit/regression execution occurred.

Sessions:

- Spec: `a979e1a4-5312-40f8-8405-67a4efed28c0`, approximately 118 seconds.
- Standards/safety: `5b69a4e8-8132-4685-8419-57d68c2519ff`, approximately 147 seconds.

Raw advisory text is retained in those local Claude session transcripts; this
document is a cleaned report. It does not retain private reasoning.

## Spec

1. **Empty qualification inventories disable required-coverage checks.**
   `scripts/cloud-evidence-lib.mjs:210` creates a draft from manifest inventory;
   `scripts/cloud-evidence-validate.mjs:86` does not first require a successful,
   complete calibration run. Evaluation at library lines 438–447 defaults a
   missing inventory to `[]`. Source-confirmed: an empty approved inventory
   has no required IDs to check. This requires a bad profile to be approved;
   it is not a claim that cloud acceptance is currently active. Refuse empty
   or malformed qualified inventories and incomplete calibration drafts;
   add negative profile/draft tests.

2. **The control-file allowlist omits alternate gate configurations.**
   Library lines 30–46 omit root `ruff.toml`, `.ruff.toml`, `mypy.ini`,
   pytest config variants, `.npmrc`, package ESLint config variants and root
   Vite config. Source-confirmed omission; whether each file changes this
   repository's actual commands depends on tool discovery/precedence and
   must be checked. Include configurations consumed by the real gate and
   assert adding/changing each relevant configuration forces requalification.

3. **Source scans do not prove absence of all skipped tests.**
   Collector lines 107–137 scan only discovered package Vitest test sources.
   Library line 48 does not cover chained modifiers, aliases or runtime skip
   calls. Root `scripts/*.test.mjs` Node tests are not inventoried/scanned,
   although the root manifest runs roadmap/progress tests in validation.
   Source coverage gap confirmed; exact runtime behavior was not exercised.
   Runtime outcome evidence is preferable to claiming a broader regex proves
   all cases. Preserve the unchanged gate or obtain the required reporting
   change approval; do not modify frozen tests to eliminate the symptom.

4. **Failure history is keyed by head commit, not identical tested tree.**
   Library lines 482–484 fetch runs for `head_sha`. The plan asks for failed
   attempts on the same tree. Recommitting identical content can change the
   head SHA without changing the tree. Verify actual PR/merge tree behavior,
   then retain matching-tree failed attempts or a clear reviewer-checked
   limitation. Do not broaden this into repository-wide historical polling.

5. **Approval/disposition records are structurally weak.**
   Library line 260 accepts `approval: {}`; lines 338–347 accept any nonempty
   explanation/evidence for allowed disposition classes and highlight only
   flakes. Local maintainer-provided files are trusted inputs, not a public
   authentication boundary. Require meaningful approval references, retain
   profile identity/hash and expose every accepted prior-failure disposition
   so a reviewer can audit it. This does not require a new auth system.

6. **HEAD identity does not attest post-gate worktree cleanliness.**
   Workflow lines 72–74 check only lockfiles; collector lines 166–168 record
   HEAD's tree. Source-confirmed limitation. A gate that changes tracked test
   inputs in place can leave evidence naming their pre-change tree. Bound
   the intended tracked-state check and regression case before qualification.

Declared remaining work, not preparation defects: real inventory/JUnit shape
validation, durable qualification archive, wiring helper tests into the full
gate, lint, full checks, actual cloud runs and Producer activation. No
unauthorized implementation scope was found by this reviewer.

## Standards and safety

1. **Untracked alternate gate controls can evade control-drift detection.**
   Independent corroboration of Spec finding 2, with the same unverified tool
   discovery assumptions. Check actual consumed controls before changing code.

2. **Malformed profiles can make coverage requirements vacuous.**
   Independent corroboration of Spec finding 1. Validate command, controls,
   runtime profile and nonempty required inventories before evaluating a run.

3. **A suspended media scope still produces CLI success.**
   Library lines 408–416 suspend `media-sensitive`; validator line 123 exits
   zero whenever report status is `pass`. Source-confirmed. A caller using
   only the exit code could mistakenly accept media-sensitive work. Require
   an explicit requested scope or conservatively return nonzero for suspended
   scope; test the CLI path, not only the pure evaluator.

4. **Conditional Vitest markers are always rejected.**
   Library line 448 rejects every source marker; its allowlist applies only
   to pytest. A `runIf` may run rather than skip on the qualified host. Actual
   accepted use was not established. First inspect real tests/runtime outcomes;
   do not weaken skip policy or add a speculative marker allowlist.

5. **CLI/manifest values reach API paths before format validation.**
   Validator lines 27–46 and library line 480 do not first enforce a positive
   run/attempt, canonical repository identifier or 40-hex commit. Source
   finding; low severity for this authorized-maintainer CLI. Reject malformed
   values before subprocess/API calls and add a no-call negative test. No
   shell command injection was demonstrated.

6. **PR checkout provenance is consistency-checked, not independently bound
   to the executed checkout.** Library lines 355–374 use a manifest-named
   commit and check its second parent; no base-parent comparison exists.
   Source fact; GitHub API semantics remain unverified. Make provenance
   assumptions explicit, check base identity where justified, and distinguish
   authoritative run facts from collector attestations.

7. **Quoted unusual paths can cause false rejection.** Collector line 168
   uses non-NUL `git ls-tree` output. Non-ASCII/quoted nested control paths may
   mismatch GitHub's decoded paths. Use NUL-delimited listing with a focused
   unusual-path test if this supported-path case is confirmed. This is a
   fail-closed usability issue, not a demonstrated false acceptance.

8. **Timeout/cancellation evidence retention is uncertain.**
   Workflow collection/upload use `!cancelled()`. Non-passing cancelled runs
   remain rejected; whether collection survives a job timeout is unverified.
   Document that limitation or verify appropriate reporting behavior. Do not
   adopt `always()` blindly or introduce competing/rerun jobs.

9. **Collector and boundary negative tests are incomplete.** No direct
   `collectEvidence` test appears in the candidate packet. Add focused
   collection/validator-seam and malformed identity tests within #196;
   real-CI output-shape confirmation remains the existing qualification gate.

No private-data leak or unsafe archive extraction was proven. Sanitization
must still be checked on the actual first-run artifacts; the advisory's
positive privacy assessment is not privacy acceptance.

## Handoff, not a new programme

Keep these findings inside existing #196. Confirm source-backed findings,
make minimal fixes/new regression tests during its authorized implementation,
and retain API/tool assumptions as explicit qualification checks. No new
ticket, dependency, routing-policy change or producer acceptance was inferred.
Both preparation and this review leave #196 Blocked pending #193; cloud
substitution stays disabled.
