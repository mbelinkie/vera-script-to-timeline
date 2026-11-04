#!/bin/zsh
# Double-click in Finder to open the VERA prep board (ChatGPT grooming ->
# DeepSeek -> Codex). Reuses a running board, or starts one in the background.
set -u
repository_root="${0:A:h}"
cd "$repository_root" || { echo "Could not open the VERA folder."; read -r "?Press Return to close."; exit 1; }

# Finder-launched scripts don't read ~/.zshrc; borrow the login shell's PATH.
captured="$("${SHELL:-/bin/zsh}" -ilc 'printf "%s" "$PATH"' </dev/null 2>/dev/null)"
[[ -n "$captured" ]] && export PATH="$captured:$PATH"
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"

command -v node >/dev/null || { echo "Node.js was not found."; read -r "?Press Return to close."; exit 1; }
command -v gh >/dev/null || { echo "GitHub CLI (gh) was not found. Install it with: brew install gh"; read -r "?Press Return to close."; exit 1; }

port="${VERA_PREP_PORT:-51750}"
if curl --noproxy '*' -fsS --max-time 2 "http://127.0.0.1:$port/status" 2>/dev/null | grep -q vera-prep-board; then
  open "http://127.0.0.1:$port/"
else
  mkdir -p out
  nohup node scripts/prep-board.mjs > out/prep-board.log 2>&1 < /dev/null &
  sleep 1
fi
echo "✓ VERA prep board: http://127.0.0.1:$port/  (you can close this window)"
