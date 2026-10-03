The fresh R2-picture run stopped terminally at the `r2-picture-deselected` readback with exit code 1. The probe refused because its `editorial-readback.py` pin is `dba56a71…ce32d22`, while the current module hash is `d9df7622…e93690354`. No retry or cleanup was performed.

Preparation succeeded, then `auto-none`, `auto-v1`, and `deselect` were dispatched. No split or deletion occurred. Because readback failed, final protected-state preservation is unverified; own-context restoration, R2-partial, and output work remain unattempted. Config remains registered with External Scripting `None` and protected-six.

The exact audit and result bindings are in [r2-picture-native-executor-result.json](r2-picture-native-executor-result.json).