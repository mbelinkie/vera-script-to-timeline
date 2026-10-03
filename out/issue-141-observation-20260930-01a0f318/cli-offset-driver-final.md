**The requested package is incomplete.** The fake-only check passes, but `--run` is not executable yet: it stops before dispatching any actions or performing restoration. I left it that way rather than present a stub as a working driver.

The check confirms the exact A1 one-frame delta, rejects wrong-target and unrelated changes, and checks that the R2-offset labels exist. It does not test native calls, captured Resolve schema completeness, locking, menus, or restoration.

Driver SHA-256: `7b045ec17a993c717ae994b8e054f353817f5e4ec7020a82db7805939d6538af`

Files: [driver](REPOSITORY/docs/investigations/issue-141/independent-offset-sequence.py) and [readiness JSON](REPOSITORY/docs/investigations/issue-141/independent-offset-sequence-readiness.json). `--run` was not invoked.