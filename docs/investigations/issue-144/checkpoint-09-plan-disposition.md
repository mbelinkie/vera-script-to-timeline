## Implementation disposition

No blockers. Retain explicit synthetic lane/provider gates, strict operator parsing, ready/word-timing/new-byte checks, and UTF-16 offsets in the injected provider. Compare row identity/order/text/version while permitting the canonical revision metadata and already-composed visual changes.

One factual correction: an accepted standalone script-validator CLI already exists at `packages/contracts/src/script-validator-cli.ts`. Use that actual validator before generating anything: compiling the revised wording against stale old narration dependencies would intentionally fail. After dependency replacement the actual compiler remains the geometry/validity authority. Neither accepted CLI/compiler source changes. `process_document` can reuse cached rows, but calling `process_block` directly is the smaller seam and ensures untouched rows receive no service calls at all.

Begin new issue-owned tests, then the bounded handoff implementation. Full omission decisions/native integration remain later work.
