# #219 review dispositions

Initial adversarial Claude CLI review of `15e10e2` completed exit 0 and returned
**GO, no blocking findings**. Output SHA-256:
`003639a34993aaa611d0acd1bceb238b22e9727572eff690fde62d691df66c4c`.
The private prompt, exact candidate/source hashes, output, status and stderr are
retained. Read-only tools only; no shell, Resolve or mutating connector access.
The reviewer inspected code, raw synthetic readbacks and selected rendered frames.
It could compare recorded hashes but could not recompute them without shell;
the owner's deterministic analysis and retained digests supply that evidence.

| Finding (all nonblocking) | Disposition |
| --- | --- |
| “Before mutation” overstates live graph/type checking | Clarified before semantic control/state writes. Disposable setup/import/output connection precedes live inspection; a mismatch leaves a refused scratch timeline. Pinned manifest shorthand is interpreted explicitly without changing its tested digest. Unit flag checks are not injected live mismatch coverage. |
| Run A prepared by earlier batch version | Recorded missing pre-refactor code hash and exact distinction from Run B's single-case preparer. Same CASES and write sequence; later current-code verification and decoded render equality cover retained output, not identical preparer binaries. |
| Fast gate started on earlier commit plus working-tree changes | Reported actual `8872434` plus diff digest, not a pass “on candidate.” Final full gate on the reviewed tree remains required and will supersede this limitation. |
| Independence overclaimed | Changed to separate imports in one project/session and one render batch. No independent project or restart qualification. |
| Manifest historical status and private pending list stale | Explained historical pinned status in contract prose; corrected private current checkpoint. No manifest digest change. |
| Reproduction wrappers are workstation-specific | Documented `rtk`/`ctx-wire` as output wrappers around the actual reproducible commands. No new dependency. |
| Source hash/import time gap | Retained as a limitation of this exclusive local read-only-source probe. Post-import exact node/control inspection and source pins reduce the risk; no production concurrency qualification is claimed. |
| Restoration should be explicit in acceptance | Added numbered operator choice: restore the disposable project's initial format during an exclusive window, or explicitly accept the retained difference. The failed attempt and premature completion correction remain visible. |

These fixes change only nonconsumed documentation and private checkpoint metadata.
Executable probe, target-manifest pin and runtime evidence are unchanged.
Delta review of `cb3d6fe` completed exit 0 with **GO, no blocking findings**;
output SHA-256 `92c8ca0cb95b4e5102de6afcfd35d3d242927352b4c99252cf3d00d07216b7b5`.
It recommended replacing the unsupported fast-input-equivalence sentence with
an explicit limitation. That exact correction is applied; no equivalence to
the candidate is claimed for the earlier fast pass. Final full evidence on the
clean committed candidate passed: `5ae5e34`, exit 0, exact receipt in
`final-validation.json`. All tracked inputs remained hash-identical throughout
the run. Post-gate changes only add this evidence and update nonconsumed Markdown
status/checklists; probe, manifest, tests, settings and runtime inputs are unchanged.
These documents/JSON are not generator inputs (contracts schema paths), JS lint
inputs (scripts and workspace src/test), Python lint source, mypy inputs
(`python tests`), pytest inputs (`tests`), or dashboard/roadmap configuration.
Doc link/privacy/whitespace and frozen-boundary checks cover the evidence update;
no new full run is needed under the accepted verification policy. Producer
rights/font, target contract and restoration judgments remain separate gates.
