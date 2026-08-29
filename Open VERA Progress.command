#!/bin/zsh

set -u

# Finder launches .command files with a minimal PATH. Include the standard
# Intel and Apple Silicon Homebrew locations before looking for npm.
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

repository_root="${0:A:h}"
cd "$repository_root" || exit 1

if ! command -v npm >/dev/null 2>&1; then
  echo "Could not find npm. Install Node.js, then try again."
  echo
  read -r "?Press Return to close."
  exit 1
fi

arguments=()
if [[ "${VERA_PROGRESS_NO_OPEN:-0}" != "1" ]]; then
  arguments=(-- --open)
fi

if ! npm run progress "${arguments[@]}"; then
  echo
  echo "The VERA progress dashboard could not be generated."
  read -r "?Press Return to close."
  exit 1
fi

echo
if [[ "${VERA_PROGRESS_NO_OPEN:-0}" == "1" ]]; then
  echo "VERA progress generated successfully."
else
  echo "VERA progress opened in your browser."
fi
