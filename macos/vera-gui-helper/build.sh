#!/bin/sh
# macOS only. Build the direct Aqua-session helper under its OWN stable,
# Apple-team code-signing identity. Never ad-hoc sign, alter TCC, or run Resolve.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: signed VERA GUI helper build requires macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
repo=$(CDPATH='' cd -- "$root/../.." && pwd -P)
python="$repo/.venv/bin/python"
if [ ! -x "$python" ]; then
    echo 'BLOCK: pinned helper build interpreter unavailable' >&2; exit 78
fi
# A signed helper binary must never be swapped while any Conductor native
# campaign owns its long-lived carrier lock, even during CPU-only stages.
# The inherited file descriptor is validated against the real locked inode;
# setting an environment flag cannot bypass this guard.
if [ -z "${VERA_NATIVE_OWNER_FD:-}" ]; then
    export PYTHONPATH="$repo/python"
    exec "$python" -m vera_timeline_agent.resolve_gui_helper_build_guard
fi
PYTHONPATH="$repo/python" "$python" - "$VERA_NATIVE_OWNER_FD" <<'PYGUARD'
import sys
from vera_timeline_agent.resolve_native_owner import _validate_inherited_owner
_validate_inherited_owner(int(sys.argv[1]))
PYGUARD
support="$HOME/Library/Application Support/VERA/GUI Helper"
identity_record="$support/signing-identity.sha1"
mkdir -p "$support"
chmod 700 "$support"
# Install once with VERA_GUI_HELPER_SIGNING_SHA1 set to a valid keychain
# fingerprint. Subsequent builds use the same recorded identity.
identity="$(printenv VERA_GUI_HELPER_SIGNING_SHA1 2>/dev/null || true)"
if [ -f "$identity_record" ]; then
    recorded=$(cat "$identity_record")
    if [ -n "$identity" ] && [ "$identity" != "$recorded" ]; then
        echo 'BLOCK: identity rotation would invalidate helper TCC attribution' >&2
        exit 78
    fi
    identity="$recorded"
fi
if [ -z "$identity" ]; then
    echo 'BLOCK: no stable signing identity selected; available identities:' >&2
    security find-identity -v -p codesigning >&2 || true
    echo 'Complete one-time Apple Development certificate setup, then set VERA_GUI_HELPER_SIGNING_SHA1.' >&2
    exit 78
fi
case "$identity" in
    *[!0-9a-fA-F]*|'')
        echo 'BLOCK: signing identity must be a SHA-1 fingerprint' >&2; exit 78 ;;
esac
if [ "$(printf '%s' "$identity" | wc -c | tr -d ' ')" -ne 40 ]; then
    echo 'BLOCK: signing identity must be a 40-character SHA-1 fingerprint' >&2
    exit 78
fi
if ! security find-identity -v -p codesigning | grep -iFq "$identity"; then
    echo 'BLOCK: the selected signing identity is not valid in the login keychain' >&2
    exit 78
fi
# The installed binary must be demonstrably built from THIS clean, committed
# source graph, not from a dirty intermediate tree later restored to HEAD.
repo=$(CDPATH='' cd -- "$root/../.." && pwd -P)
python="$repo/.venv/bin/python"
if [ ! -x "$python" ]; then
    echo 'BLOCK: pinned source-freeze Python unavailable' >&2; exit 78
fi
freeze_pins() {
    PYTHONPATH="$repo/python" "$python" - <<'PY'
import subprocess
from vera_timeline_agent.resolve_test_bench_full_loop import _frozen_source
from vera_timeline_agent.resolve_gui_helper_protocol import source_manifest_sha256
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
print(head, _frozen_source(head), source_manifest_sha256())
PY
}
frozen=$(CDPATH='' cd -- "$repo" && freeze_pins)
set -- $frozen
if [ "$#" -ne 3 ]; then echo 'BLOCK: source pin record invalid' >&2; exit 78; fi
frozen_commit=$1
frozen_graph=$2
frozen_helper_manifest=$3
stage=$(mktemp -d "$support/.build.XXXXXXXX")
trap 'rm -rf "$stage"' EXIT HUP INT TERM
app="$stage/VERA GUI Helper.app"
mkdir -p "$app/Contents/MacOS"
cp "$root/Info.plist" "$app/Contents/Info.plist"
plutil -lint "$app/Contents/Info.plist" >/dev/null
sdk=$(xcrun --sdk macosx --show-sdk-path)
xcrun clang -isysroot "$sdk" -Werror -Wno-deprecated-declarations \
    -c "$root/Sources/VERAGUIHelper/LegacyForeground.c" \
    -o "$stage/LegacyForeground.o"
xcrun swiftc -O -sdk "$sdk" \
    -import-objc-header "$root/Sources/VERAGUIHelper/LegacyForeground.h" \
    "$root/Sources/VERAGUIHelper/FocusProtocol.swift" \
    "$root/Sources/VERAGUIHelper/TargetInspection.swift" \
    "$root/Sources/VERAGUIHelper/RollActuator.swift" \
    "$root/Sources/VERAGUIHelper/RollSpool.swift" \
    "$root/Sources/VERAGUIHelper/main.swift" \
    "$stage/LegacyForeground.o" \
    -framework AppKit -framework ApplicationServices -framework Carbon -framework Security \
    -o "$app/Contents/MacOS/VERAGUIHelper"
codesign --force --sign "$identity" --options runtime --timestamp=none "$app"
codesign --verify --strict --deep --verbose=2 "$app"
info=$(codesign -dv --verbose=4 "$app" 2>&1)
printf '%s\n' "$info" | grep -Fx 'Identifier=org.vera.resolve-test-bench.gui' >/dev/null
team=$(printf '%s\n' "$info" | sed -n 's/^TeamIdentifier=//p')
if ! printf '%s' "$team" | grep -Eq '^[A-Z0-9]{10}$'; then
    echo 'BLOCK: signing identity has no valid 10-character Apple TeamIdentifier' >&2
    exit 78
fi
codesign -dr - "$app" 2>&1 | grep -F 'identifier "org.vera.resolve-test-bench.gui"' >/dev/null
if [ "$(CDPATH='' cd -- "$repo" && freeze_pins)" != "$frozen" ]; then
    echo 'BLOCK: helper source changed during build or signing' >&2
    exit 78
fi
# Refuse even if another Conductor acquired its whole-run carrier during this
# expensive compile. A previously signed installed binary remains untouched.
PYTHONPATH="$repo/python" "$python" - <<'PRESWAP'
from pathlib import Path
from vera_timeline_agent.resolve_gui_helper_build_guard import active_conductor_cases, ActiveNativeCampaign
active = active_conductor_cases(Path.home() / '.local/state/vera')
if active:
    raise ActiveNativeCampaign('native carrier appeared during signed build: '+', '.join(active))
PRESWAP
installed="$support/VERA GUI Helper.app"
previous="$support/.previous-VERA-GUI-Helper.app"
archive="$support/retained-signed-helpers"
mkdir -p "$archive"
chmod 700 "$archive"
if [ -L "$archive" ]; then
    echo 'BLOCK: signed helper archive alias' >&2; exit 78
fi
if [ -e "$previous" ] || [ -L "$previous" ] || [ -L "$installed" ]; then
    echo 'BLOCK: existing helper backup or unsafe installed alias requires inspection' >&2
    exit 78
fi
old_digest=''
if [ -e "$installed" ]; then
    codesign --verify --strict --deep "$installed"
    before_req=$(codesign -dr - "$installed" 2>&1 | sed -n 's/^designated => //p')
    after_req=$(codesign -dr - "$app" 2>&1 | sed -n 's/^designated => //p')
    if [ -z "$before_req" ] || [ "$before_req" != "$after_req" ]; then
        echo 'BLOCK: replacing helper would rotate the Accessibility designated requirement' >&2
        exit 78
    fi
    old_digest=$(shasum -a 256 "$installed/Contents/MacOS/VERAGUIHelper" | awk '{print $1}')
    if [ -e "$archive/$old_digest" ] || [ -L "$archive/$old_digest" ]; then
        echo 'BLOCK: previous signed helper archive identity already exists' >&2
        exit 78
    fi
fi
if [ -e "$installed" ]; then
    mv "$installed" "$previous"
fi
if ! mv "$app" "$installed"; then
    if [ -d "$previous" ]; then mv "$previous" "$installed"; fi
    echo 'BLOCK: helper installation failed; previous bundle restored' >&2
    exit 78
fi
if [ -d "$previous" ]; then
    # Preserve the exact prior signed bundle as immutable local test evidence.
    # The earlier M4 cases are spent and must never be replayed after upgrade.
    mkdir "$archive/$old_digest"
    chmod 700 "$archive/$old_digest"
    mv "$previous" "$archive/$old_digest/VERA GUI Helper.app"
fi
if [ ! -f "$identity_record" ]; then
    printf '%s\n' "$identity" > "$identity_record"
    chmod 600 "$identity_record"
fi
codesign --verify --strict --deep "$installed"
binary_digest=$(shasum -a 256 "$installed/Contents/MacOS/VERAGUIHelper" | awk '{print $1}')
# Immutable installed binary -> exact frozen graph/actor source provenance;
# no wrapper can later claim a clean checkout for a dirty-code signed binary.
PYTHONPATH="$repo/python" "$python" - "$support" "$binary_digest" "$frozen_commit" "$frozen_graph" "$frozen_helper_manifest" <<'PY'
import sys
from pathlib import Path
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_queue as queue
support, binary, commit, graph, manifest = sys.argv[1:]
carrier._once(Path(support) / ('built-source-pins-' + binary + '.json'), queue.canonical({
    'schema': 'vera.gui-helper-signed-build-source/v1',
    'binarySha256': binary,
    'frozenCommit': commit,
    'sourceGraphSha256': graph,
    'sourceManifestSha256': manifest,
}))
PY
printf 'SIGNED_HELPER=%s\nTEAM_IDENTIFIER=%s\n' "$installed" "$team"
codesign -dv --verbose=4 "$installed" 2>&1 | grep -E '^(Identifier|TeamIdentifier|CDHash)='
