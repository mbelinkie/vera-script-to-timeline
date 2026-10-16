# #192 simulated render queue lifecycle correction

Runtime3 naturally completed against259d0f48263b63d9748a2b5e16e72b65f081fdb9:
exit1, no signal, 1 failed in47.29s. Log SHA256 matches the immutable receipt:
a7311174871252ccb52076900e4fcceaa98b6769465038b49b68f278be1b2821.
Actual public A/B inference now passes far enough to reach C's two renders.
The pristine public render completed; the edited render correctly refused a
new queue job incorrectly reported as already complete. `-x` stopped before
transport tests and the four selected #190 regression functions.

The new `MixingProject` fake retained unique job IDs but inherited one global
status from the original single-job fixture. After pristine completion, its
second AddRenderJob returned a fresh ID while GetRenderJobStatus returned the
previous job's global Complete state. The public owner guard correctly
requires Ready before recording the start intent and calling StartRendering.

Only new fixture/test siblings change. `MixingProject` now retains status per
actual queued ID. Add creates Ready; Start requires Ready, records Rendering,
writes the independently mixed PCM, then records Complete for that same ID.
Other job statuses remain intact. The public-path test additionally checks
distinct pristine/edited job IDs and the pristine job's retained completion.
No native guard, owner record, adapter sequence, accepted #190 fake, assertion,
timeout, contract or result is weakened or fabricated.

Focused Ruff passes both changed files; strict mypy passes both. The initial
format check required parentheses around the added assertion; the final
affected format check passes. All failed and passing attempts stay in
`out/issue192/focused-31-ruff-job` through `focused-34-format-job`; the initial
format failure remains a failure. Final parentheses preserve the checked AST.

Next: rerun the same serial bounded34-item package, public path first then
both new #192 transport/public test files and only the four already-selected
#190 regression functions. Create fresh temporary packages, bindings, queue
jobs and evidence. No global fast/full/Claude gate or real native/provider/
FFmpeg/original-media operation starts before the actual public-path result.
Actual #202 acceptance remains required before formal Ready/claim/closure.
