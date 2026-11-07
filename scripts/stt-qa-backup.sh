#!/usr/bin/env bash
# Private, local development-QA only. All credentials are passed in environment.
set -euo pipefail
exec node "$(dirname "$0")/stt-qa-ops.mjs" backup "$@"
