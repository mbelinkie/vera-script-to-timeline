**Local READY: probe registrations and readback pin updated.** The requested sequence work is blocked: this checkout has no `out/issue-141-observation-20260930-01a0f318/` directory or `cli-r2-resume-ready.json`, and I found no `independent-native-call.py` or `independent-cut-sequence.py`. I did not recreate them or alter the retained Matrix-selection stop evidence.

Updated the editorial readback’s reader pin to `9b697774…1879a4`. Added the two requested AV action aliases to the probe’s validation and dispatch lists, pinned to the inspected `av-output.py` hash `a7d52eb2…c0c4c91a`.

Checks passed:

- `python3.14 -S docs/investigations/issue-141/editorial-readback-check.py`
- `python3.14 -S docs/investigations/issue-141/check.py`
- `git diff --check`

Native-call and cut-sequence checks could not run because their files are absent. The 180-second deadline and protected-six propagation remain unverified; no native calls were made.