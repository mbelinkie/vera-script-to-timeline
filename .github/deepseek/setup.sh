#!/usr/bin/env bash
# Dependency setup for DeepSeek attempts in Script-to-Timeline (see AGENTS.md bootstrap).
set -uo pipefail
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
echo "== ffmpeg"; command -v ffmpeg >/dev/null || { sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null; } || echo "ffmpeg install FAILED"; ffmpeg -version 2>/dev/null | head -1
echo "== npm ci"; npm ci --no-audit --no-fund || echo "npm ci FAILED"
echo "== uv"; command -v uv >/dev/null || pipx install uv || python3 -m pip install --user uv
export PATH="$HOME/.local/bin:$PATH"
echo "== uv sync --frozen"; uv sync --frozen || echo "uv sync FAILED"
echo "Setup finished. Focused checks: npx vitest / node --test <file>, uv run --frozen pytest <file>."
