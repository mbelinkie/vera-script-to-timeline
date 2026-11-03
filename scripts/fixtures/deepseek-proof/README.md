# No-provider transport fixture

This fixture is intentionally red before the approved mock replacement. It is
not part of the normal test suite. Its only use is the separately authorized
GitHub-to-Mac transport proof for issue #396, after protected delivery.

The approved editable file is `target.py`. The private controller replaces it
with the same function returning `"after"`, then runs the frozen `check.py`.
The controller must retain `live_enabled=false`, use its explicit mock mode,
confine check processes with the native sandbox, and preserve the lifetime
ledger unchanged. No provider request is needed.

Prepare the private manifest against the delivered main revision, with hashes
of the exact editable baseline, frozen check and approved adapter build. The
synthetic issue's final DeepSeek Handoff must describe those bounds before its
independent canonical Chat review. Do not manufacture an approval record from
the implementation task.
