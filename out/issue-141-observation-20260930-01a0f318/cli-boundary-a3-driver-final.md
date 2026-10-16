Created the ignored A3-only driver and local readiness JSON. The driver requires pinned prior-pair and successful base split/restore result paths and hashes. It checks registered source hashes before dispatch, uses the approved A3 labels and menus, records each result reference and the actual final pair, and restores the test’s temporary locks and playhead. `--run` was **not** called.

The fake check passed. It verified supported labels, source pins, and the exact wrong-selection refusal using existing fake editorial helpers; it does **not** exercise driver orchestration or native dispatch.

- Driver SHA-256: `517fbeb4c148fdcee629b9ba866fa8dd6fe289d2d7c852758a71f394bdab99d4`
- Readiness JSON SHA-256: `bf3f0fe5e88a0376d3c6919e4b4ab4b96ea7b63416de08527ee01f9e3b1a3972`

The base-result arguments are enforced for `--run`; there are no successful R3-boundary base result pins available to verify or execute that path in this turn.