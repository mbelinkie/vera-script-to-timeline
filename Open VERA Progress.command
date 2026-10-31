#!/bin/zsh
#
# Double-click in Finder to generate and open the auto-refreshing VERA
# progress dashboard. Keep this file in the root of the VERA repository (next to
# package.json).
#
# Set VERA_PROGRESS_NO_OPEN=1 to generate the dashboard without opening it.

set -u

repository_root="${0:A:h}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pause_and_exit() {
  echo
  read -r "?Press Return to close."
  exit "${1:-1}"
}

fail() {
  echo
  echo "✗ $*"
  pause_and_exit 1
}

append_to_path() {
  local dir
  for dir in "$@"; do
    [[ -d "$dir" && ":$PATH:" != *":$dir:"* ]] && PATH="$PATH:$dir"
  done
  export PATH
}

# Finder-launched scripts don't read ~/.zshrc, so tools installed through
# nvm, fnm, Volta, asdf, mise, etc. are invisible. Borrow the PATH from the
# user's real login shell (with a 10-second limit in case a startup file
# waits for input). +m keeps that shell from taking over the terminal, and
# SIGKILL stops it even though interactive shells ignore SIGTERM.
load_login_shell_path() {
  local user_shell="${SHELL:-/bin/zsh}"
  local tmp captured pid waited=0
  tmp="$(mktemp "${TMPDIR:-/tmp}/vera-path.XXXXXX")" || return

  "$user_shell" +m -ilc 'printf "\n__VERA_PATH__=%s\n" "$PATH"' \
    </dev/null >"$tmp" 2>/dev/null &
  pid=$!
  while kill -0 "$pid" 2>/dev/null && (( waited < 100 )); do
    sleep 0.1
    (( waited++ ))
  done
  kill -KILL "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null

  captured="$(sed -n 's/^__VERA_PATH__=//p' "$tmp" | tail -n 1)"
  rm -f "$tmp"
  [[ -n "$captured" ]] && export PATH="$captured:$PATH"
}

# ---------------------------------------------------------------------------
# Locate Node and npm
# ---------------------------------------------------------------------------

cd "$repository_root" || fail "Could not open the folder: $repository_root"

load_login_shell_path

# Fallback locations, checked only after whatever the login shell provided.
nvm_dir="${NVM_DIR:-$HOME/.nvm}"
newest_nvm_bin=( "$nvm_dir"/versions/node/*/bin(N/nOn[1]) )
append_to_path \
  /opt/homebrew/bin \
  /usr/local/bin \
  "$HOME/.volta/bin" \
  "$HOME/.asdf/shims" \
  "$HOME/.local/share/mise/shims" \
  "$HOME/.nodenv/shims" \
  "$HOME/.local/share/fnm/aliases/default/bin" \
  "$HOME/Library/Application Support/fnm/aliases/default/bin" \
  "$HOME/n/bin" \
  "${newest_nvm_bin[@]}"

# Respect the repository's pinned Node version when nvm is in use.
if [[ -f .nvmrc && -s "$nvm_dir/nvm.sh" ]]; then
  set +u
  source "$nvm_dir/nvm.sh" --no-use
  if ! nvm use --silent >/dev/null 2>&1; then
    echo "⚠ This repo asks for Node $(<.nvmrc), which nvm doesn't have installed."
    echo "  Continuing with the default Node. Run 'nvm install' to match it."
  fi
  set -u
fi

command -v node >/dev/null 2>&1 \
  || fail "Could not find Node.js. Install it from https://nodejs.org (or via Homebrew/nvm), then try again."
command -v npm >/dev/null 2>&1 \
  || fail "Found Node.js but not npm. Reinstall Node.js, then try again."

# ---------------------------------------------------------------------------
# Check the project
# ---------------------------------------------------------------------------

[[ -f package.json ]] \
  || fail "No package.json in $repository_root.
  Move this launcher into the root of the VERA repository and try again."

node -e 'process.exit((require("./package.json").scripts || {}).progress ? 0 : 1)' 2>/dev/null \
  || fail "package.json has no \"progress\" script, so there's nothing to run."

if [[ ! -d node_modules ]]; then
  echo "Installing dependencies (first run)…"
  if [[ -f package-lock.json ]]; then
    npm ci || fail "Installing dependencies failed. See the output above."
  else
    npm install || fail "Installing dependencies failed. See the output above."
  fi
  echo
elif [[ -f package-lock.json && package-lock.json -nt node_modules/.package-lock.json ]]; then
  echo "Dependencies changed since the last install. Updating…"
  npm ci || fail "Updating dependencies failed. See the output above."
  echo
fi

# ---------------------------------------------------------------------------
# Generate (and open) the dashboard
# ---------------------------------------------------------------------------

echo "Using Node $(node -v) and npm $(npm -v)"
echo

if [[ "${VERA_PROGRESS_NO_OPEN:-0}" == "1" ]]; then
  npm run progress \
    || fail "The VERA progress dashboard could not be generated. See the output above."
  echo
  echo "✓ VERA progress snapshot generated."
else
  echo "Starting live dashboard. Keep this Terminal window open for updates."
  echo "Press Ctrl+C when you're finished."
  echo
  # The live server remains in the foreground intentionally. Launch success,
  # refresh status and any errors are reported by the Node process itself.
  npm run progress -- --serve --open
  result=$?
  if (( result != 0 && result != 130 && result != 143 )); then
    fail "The live VERA progress dashboard stopped unexpectedly. See the output above."
  fi
  echo "Dashboard server stopped."
fi
