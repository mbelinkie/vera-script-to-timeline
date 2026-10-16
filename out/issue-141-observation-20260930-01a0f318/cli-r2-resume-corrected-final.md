**Local READY** is recorded in [cli-r2-resume-ready.json](cli-r2-resume-ready.json).

Both R2-picture and R2-partial driver checks passed against the pinned fresh pair. The readback checker, native-call `--check`, probe harness, and `git diff --check` passed. Native calls use `protected-six` and a 180-second result deadline with no retry. Both AV aliases route to the existing `av-output` module.

The property-context selection stop remains recorded; no selection success is claimed. No native action was run.