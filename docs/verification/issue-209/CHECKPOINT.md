# #209 implementation status

D-0016 (2026-10-16) supersedes the earlier validation and orchestration process.
The owning branch remains `codex/issue-209-qualification-output`.

Implemented: separate synthetic/R16 qualification admission, installed native
construction/save-reopen/render stages, host prediction/reservation/comparison,
same-MOV decoder, and read-only recovery inspection. Ordinary package refusal
for the R16 Presenter override remains unchanged.

The actual Claude CLI review found host/native integration defects. Corrections
include exact authority timestamps, stage-specific output checks, historical
completion after a valid reservation, retained finalize refusals, installed
runtime re-entry provenance, poll duration, empty-track handling, and a sealed
admission cache with separately retained proof bytes. Follow-up focused checks
pass; the repository fast gate is running after a shared-bootstrap regression
was corrected. The initial review's real findings are addressed; no source
review or test result establishes actual Studio qualification.

Local real-source checks passed R16 admission/reopening/native-input validation,
R12 still proofs, and the 111-frame synthetic package. Private-input tests skip
on CI when those inputs are absent. The actual Studio exercise remains pending,
including genuine operator approval, construction, save/reopen, rendered MOV,
same-file decode and comparison. Native getter/codec assumptions remain untested
in the application. See [operator stages](OPERATOR_STAGES.md).

Validation now uses focused tests and `npm run validate:fast` locally, with the
full regression gate supplied by GitHub Actions on the PR. No full validation
runs on the Mac. The old test monitor is paused; no evidence-equivalence bundle
or recurring validation monitor is required. Existing product safety hashes,
authority checks and immutable operation records remain part of the product.
