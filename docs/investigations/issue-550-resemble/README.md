# Resemble CPU container (unverified)

The lock resolves for Linux x86_64 and Python 3.10; the image build was
interrupted and has not been verified. See the parent investigation for the
source, model, licensing and current status. Build this directory with
`docker build --platform linux/amd64 -t vera-resemble-enhance:issue550 .`.
Only public dependencies, source and model weights belong in the build
context. For inference, use `--network none`, mount inputs read-only and use
a separate output directory. Confirm the CLI and model load before use.

The lock was generated with `DS_BUILD_OPS=0 uv pip compile requirements.in
--python-version 3.10 --python-platform x86_64-unknown-linux-gnu
--index-strategy unsafe-best-match --generate-hashes --emit-index-url
-o requirements.lock`. Hashes pin the selected artifacts; source builds may
still resolve their own build dependencies. `ptflops` is intentionally absent:
the pinned Resemble source imports it only in profiling methods, not its
inference path. This has not yet been confirmed by an inference run.
