Updated only the assigned source and checker.

- `editorial-cases.py`: `1e1c2685…a93f372` → `474daf2e…67544f8e`
- `editorial-cases-check.py`: `0da0fb62…b9dde2` → `868e706d…b63ced05`

For both R2-residual A2 and R3-Graphic V3, the focused fake check now verifies unlock → enable → relock, preserves the original locked state in `originalLocks`, and refuses enable while still locked. A simulated later enable refusal also retains the existing partial-state evidence bindings.

The existing checker passed: `R1-R3 guarded fake checks passed; no native app launched.` No native action was taken.