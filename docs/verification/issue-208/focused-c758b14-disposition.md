# Affected focused run: retained failure and scoped correction

`focused-c758b14` completed exit 1: 240 passed, one failed, 48 slow cases
deselected in 136.81 seconds. It is not a combined PASS. Its immutable exit,
full raw output and verified hashes are retained in
`focused-c758b14-failure.json`; the exact full input manifest remains at
`out/issue208/focused-c758b14/manifest.json`.

The only failure was new #208 expiry-test wording after B3: the completed
receipt was correctly rejected at `stale identity result`, whereas the test
expected the old identity-authority `expired` message. The correction matches
the exact anchored completed-result message and retains the no-consumption
assertion, adding no-capability-authority. The focused rerun passed one test
in 1.68 seconds, exit zero (`expiry-focused-green.json`). Raw regex-string
spelling was then made explicit for Ruff; its regex bytes are unchanged.

The 240 unchanged passing cases retain useful affected evidence. Verification
found only this issue-owned test changed among the recorded 6967 tracked
inputs, with the original log/manifest hashes, Python/venv and Node/npm/uv
profile unchanged. No production correction or accepted-test edit was needed.
The next necessary complete fast gate covers this exact candidate, including
the changed test and all ordinary/generated/lint/type/non-slow checks. Final
full/native/External qualification and independent delta review remain pending.
