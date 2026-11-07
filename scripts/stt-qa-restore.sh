#!/usr/bin/env bash
# Never creates, drops or overwrites a database; target must already be empty.
set -euo pipefail
exec node "$(dirname "$0")/stt-qa-ops.mjs" restore "$@"
