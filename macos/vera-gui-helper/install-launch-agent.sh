#!/bin/sh
# Direct per-user Aqua LaunchAgent; never installs the M4 Python worker.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: LaunchAgent install requires macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
support="$HOME/Library/Application Support/VERA/GUI Helper"
exe="$support/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
spool="$support/spool"
plist="$HOME/Library/LaunchAgents/org.vera.resolve-test-bench.gui.plist"
if [ ! -f "$exe" ] || [ -L "$exe" ]; then
    echo 'BLOCK: expected installed signed executable missing or aliased' >&2
    exit 78
fi
codesign --verify --strict --deep "$support/VERA GUI Helper.app"
mkdir -p "$spool" "$HOME/Library/LaunchAgents"
chmod 700 "$spool"
if [ -L "$spool" ] || [ -L "$plist" ]; then
    echo 'BLOCK: unsafe LaunchAgent/spool symlink' >&2
    exit 78
fi
tmp=$(mktemp "$HOME/Library/LaunchAgents/.vera-helper.XXXXXXXX")
trap 'rm -f "$tmp"' EXIT HUP INT TERM
/usr/bin/python3 - "$root/LaunchAgent.plist.in" "$tmp" "$exe" "$spool" <<'PY'
import plistlib
import sys
from pathlib import Path

template, output, executable, spool = map(Path, sys.argv[1:])
value = plistlib.loads(template.read_bytes())
assert value["Label"] == "org.vera.resolve-test-bench.gui"
assert value["ProgramArguments"] == ["@VERA_GUI_HELPER_EXECUTABLE@"]
value["ProgramArguments"] = [str(executable)]
value["EnvironmentVariables"]["VERA_GUI_HELPER_SPOOL"] = str(spool)
output.write_bytes(plistlib.dumps(value, sort_keys=True))
PY
plutil -lint "$tmp" >/dev/null
if [ -e "$plist" ] && ! cmp -s "$tmp" "$plist"; then
    echo 'BLOCK: existing LaunchAgent differs; inspect before overwrite' >&2
    exit 78
fi
if [ ! -e "$plist" ]; then
    mv "$tmp" "$plist"
    chmod 600 "$plist"
fi
domain="gui/$(id -u)"
label="org.vera.resolve-test-bench.gui"
if launchctl print "$domain/$label" >/dev/null 2>&1; then
    launchctl kickstart -k "$domain/$label"
else
    launchctl bootstrap "$domain" "$plist"
fi
launchctl print "$domain/$label" >/dev/null
echo 'VERA GUI helper Aqua LaunchAgent installed; Accessibility grant must be verified separately.'
