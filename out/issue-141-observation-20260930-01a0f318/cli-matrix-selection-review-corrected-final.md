Updated [matrix-selection-delta-review.json](matrix-selection-delta-review.json) with both pair hashes and the complete per-timeline, track, property, and item UID differences.

The differences are track enabled/locked getter values and presence or absence of eight audio `GetProperties` keys. No other property values changed. Both pairs are stable; all six timeline identities match, and all 13 pool records, protected source metadata, markers, and source evidence are unchanged. No source files were accessed during review.

Decision: the fresh after-pair can serve as the current Matrix observation for existing R2-picture preparation. The all-state equality failure remains recorded; missing audio keys do not establish effect removal, so effect readback remains unknown.