**Local package ready for review.** `r1-repeat-six.py` now exposes both dispatcher actions and uses private, hash-bound probe/reader copies for complete seven-timeline captures. Readiness pins and operator context requirements are in [r1-repeat-six-readiness.md](../../docs/investigations/issue-141/r1-repeat-six-readiness.md).

The Python 3.14 `-S` fake checks and compilation passed, including both adapter success paths and pre-mutation refusals. No probe changes, registration, or Resolve calls were made.

Live evidence still requires a fresh checkpoint and operator run; External Scripting `None` remains an operator attestation.