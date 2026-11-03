#!/bin/zsh
#
# Double-click in Finder to open the live VERA progress dashboard.
# Reuses the existing server, or starts it in the background if needed. Keep this file in the root of the VERA repository (next to
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

cd "$repository_root" || fail "Could not open the VERA folder."

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

# Prefer the matching runtime installed for VERA without changing the user's
# default Node or relying on Finder to load a version manager.
if [[ -f .nvmrc ]]; then
  pinned_node_version="$(<.nvmrc)"
  node_arch="$(uname -m)"
  [[ "$node_arch" == "x86_64" ]] && node_arch="x64"
  pinned_node_bin="$HOME/.local/share/vera-node/node-v${pinned_node_version}-darwin-${node_arch}/bin"
  [[ -x "$pinned_node_bin/node" ]] && export PATH="$pinned_node_bin:$PATH"
fi

command -v node >/dev/null 2>&1 \
  || fail "Could not find Node.js. Install it from https://nodejs.org (or via Homebrew/nvm), then try again."
command -v npm >/dev/null 2>&1 \
  || fail "Found Node.js but not npm. Reinstall Node.js, then try again."

# ---------------------------------------------------------------------------
# Check the project
# ---------------------------------------------------------------------------

[[ -f package.json ]] \
  || fail "No VERA package.json was found.
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
# Smart VERA Dashboard Launcher
# ---------------------------------------------------------------------------

echo "Using Node $(node -v) and npm $(npm -v)"
echo

# Preserve the optional static-snapshot mode.
if [[ "${VERA_PROGRESS_NO_OPEN:-0}" == "1" ]]; then
  npm run progress || fail "Could not generate the dashboard."
  echo "✓ VERA progress snapshot generated."
  exit 0
fi

state_dir="$repository_root/out/project-progress"
pid_file="$state_dir/dashboard.pid"
url_file="$state_dir/dashboard.url"
log_file="$state_dir/dashboard.log"
lock_dir="$state_dir/launcher.lock"

mkdir -p "$state_dir" || fail "Cannot create local dashboard state."
command -v curl >/dev/null 2>&1 || fail "curl is required to check the dashboard."
[[ -f "$repository_root/scripts/project-progress.mjs" ]] \
  || fail "Dashboard script is missing: scripts/project-progress.mjs"
source_id="$(node "$repository_root/scripts/project-progress.mjs" --identity 2>/dev/null)" \
  || fail "Could not identify this VERA checkout."
[[ "$source_id" =~ ^[a-f0-9]{64}$ ]] || fail "Could not identify this VERA checkout."

lock_held=0
release_lock() {
  if [[ "$lock_held" == "1" ]]; then
    rm -f "$lock_dir/owner.pid"
    rmdir "$lock_dir" 2>/dev/null || true
    lock_held=0
  fi
}
trap release_lock EXIT

# Only one launcher can decide whether to start the server at a time.
# Unlike the previous version, this detects abandoned locks promptly.
echo "Checking VERA dashboard..."
tries=0
while ! mkdir "$lock_dir" 2>/dev/null; do
  (( tries += 1 ))
  holder="$(cat "$lock_dir/owner.pid" 2>/dev/null || true)"

  if [[ "$holder" == <-> ]] && kill -0 "$holder" 2>/dev/null; then
    if (( tries == 1 )); then
      echo "Another launcher is starting. Checking again..."
    fi
    if (( tries >= 10 )); then
      fail "Another VERA launcher is still running. Close it and try again."
    fi
  elif (( tries >= 3 )); then
    echo "Clearing an abandoned startup lock..."
    rm -f "$lock_dir/owner.pid"
    rmdir "$lock_dir" 2>/dev/null \
      || fail "Cannot clear an abandoned local startup lock."
    tries=0
    continue
  fi
  sleep 1
done
lock_held=1
print -r -- "$$" > "$lock_dir/owner.pid"

# Accept the old npm-based launcher PID for backwards compatibility,
# and the direct Node process PID used by this improved launcher.
is_dashboard_process() {
  local candidate_pid="$1" command_line
  [[ "$candidate_pid" == <-> ]] || return 1
  kill -0 "$candidate_pid" 2>/dev/null || return 1
  command_line="$(ps -p "$candidate_pid" -o command= 2>/dev/null)"
  [[ "$command_line" == *"project-progress.mjs"* \
     || "$command_line" == *"npm run progress"* ]]
}

# The server chooses its own available localhost port. Reuse it only when the
# status endpoint identifies this exact checkout and server protocol.
dashboard_url=""
find_live_url() {
  local candidate="" dashboard_status=""
  [[ -f "$url_file" ]] && candidate="$(cat "$url_file")"
  if [[ -z "$candidate" ]]; then
    candidate="$(grep -Eo 'http://127\.0\.0\.1:[0-9]+/' "$log_file" 2>/dev/null | tail -n 1)"
  fi
  print -r -- "$candidate" | grep -Eq '^http://127\.0\.0\.1:[0-9]+/$' \
    || return 1
  dashboard_status="$(curl --noproxy '*' -fsS --max-time 2 -H 'Sec-Fetch-Site: none' "${candidate}status" 2>/dev/null)" \
    || return 1
  print -r -- "$dashboard_status" | grep -Fq "\"sourceId\":\"$source_id\"" || return 1
  print -r -- "$dashboard_status" | grep -Fq '"serverProtocol":"2"' || return 1
  print -r -- "$dashboard_status" | grep -Fq '"refreshIntervalSeconds"' || return 1
  dashboard_url="$candidate"
  return 0
}

server_pid="$(cat "$pid_file" 2>/dev/null || true)"
if is_dashboard_process "$server_pid"; then
  if find_live_url; then
    echo "✓ Found existing VERA server for this checkout."
  else
    release_lock
    fail "An older or mismatched VERA dashboard server is running. Stop it before opening this checkout."
  fi
else
  echo "Starting VERA dashboard in the background..."
  rm -f "$pid_file" "$url_file"
  : > "$log_file"

  # Start Node itself so that the saved PID identifies the actual server.
  # nohup and redirected streams let it survive Terminal closing.
  nohup node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON "$repository_root/scripts/project-progress.mjs" --serve \
    > "$log_file" 2>&1 < /dev/null &
  server_pid=$!
  print -r -- "$server_pid" > "$pid_file"
fi

if [[ -z "$dashboard_url" ]]; then
  # Initial GitHub collection can take time; don't expose raw CLI output.
  for (( attempt=1; attempt<=180; attempt++ )); do
    if find_live_url; then
      break
    fi

    if ! kill -0 "$server_pid" 2>/dev/null; then
      release_lock
      fail "VERA dashboard could not start."
    fi

    if (( attempt % 10 == 0 )); then
      echo "Still loading dashboard data from GitHub... ($attempt seconds)"
    fi
    sleep 1
  done
fi

if [[ -z "$dashboard_url" ]]; then
  release_lock
  fail "VERA dashboard did not become available."
fi

print -r -- "$dashboard_url" > "$url_file"
release_lock

echo
echo "✓ VERA dashboard ready: $dashboard_url"
open "$dashboard_url" || fail "Could not open the dashboard in your browser."
echo "✓ Opened in your browser. You can close this Terminal window."
