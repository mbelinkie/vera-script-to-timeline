Implemented the bounded outer recovery fixes and focused fake Resolve checker. The readiness result records matching helper/checker hashes and offline outcomes.

Verified with Python 3.14 `-S`: both files compile, the checker passes success and fail-closed cases, and `git diff --check` passes. This is offline verification; native Resolve acceptance remains pending.

Skipped native Resolve/config registration and media-byte access, as scoped.