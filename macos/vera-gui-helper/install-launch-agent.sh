#!/bin/sh
# Source-frozen, signed actor pin installer. NEVER silently migrate to a
# Roll-capable helper with only a focus-only spool path configured.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: Aqua LaunchAgent installation requires macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
repo=$(CDPATH='' cd -- "$root/../.." && pwd -P)
python="$repo/.venv/bin/python"
if [ ! -x "$python" ]; then
    echo 'BLOCK: exact frozen CPython virtualenv not installed' >&2
    exit 78
fi
# The Python installer independently authenticates the exact frozen git HEAD,
# installed Team-ID signed binary, old plist, native owner and live Aqua pins.
# It uses one no-edit Swift actor probe, never any Resolve SDK or menu action.
export PYTHONPATH="$repo/python"
exec "$python" "$root/pin-launch-agent.py"
