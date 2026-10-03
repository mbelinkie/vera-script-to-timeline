Completed the LOCAL package in the two assigned OUT files. `--run` now orchestrates R2-offset preparation, exact A1 selection checks, one nudge, strict complete-pair comparison, existing case restoration, and final deselection/playhead checks. **I did not invoke `--run`**, so no native action was dispatched.

The fake-only `--check` passes. It exercises exact-delta success, wrong-target and unrelated-change refusal, and the approved readback/menu protocol labels. It does not verify native behavior, captured Resolve schema completeness, or real restoration.

Driver SHA-256: `87e8887cd4f261b50deb7295ae20e9e8e70096e3ae9b5136bbf376a193f84f1c`

Files: [driver](independent-offset-sequence.py) · [readiness JSON](independent-offset-sequence-readiness.json)