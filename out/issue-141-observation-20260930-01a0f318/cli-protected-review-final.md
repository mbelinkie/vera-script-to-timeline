Recorded the review in [cli-protected-review.json](cli-protected-review.json).

Protected-inventory, range-repair, editorial-case, and harness checks passed. The availability check did not finish within 60 seconds; the pinned pre-change probe confirms its two-argument fake hook is incompatible with the existing keyword-only `offline` parameter.

**Native dispatch is not ready:** the installed workflow record pins an older probe hash. The review records the read-only action as safe by source review, with fresh protected-six staging and current helper pins required before dispatch. No native action ran; no media was read or hashed.