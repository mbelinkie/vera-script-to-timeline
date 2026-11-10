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
installed="$support/VERA GUI Helper.app"
previous="$support/.previous-VERA-GUI-Helper.app"
if [ -e "$previous" ] || [ -L "$previous" ] || [ -L "$installed" ]; then
    echo 'BLOCK: existing helper backup or unsafe installed alias requires inspection' >&2
    exit 78
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
    # Remove only the previous helper bundle, never project/media evidence.
    rm -rf "$previous"
fi
if [ ! -f "$identity_record" ]; then
    printf '%s\n' "$identity" > "$identity_record"
    chmod 600 "$identity_record"
fi
codesign --verify --strict --deep "$installed"
printf 'SIGNED_HELPER=%s\nTEAM_IDENTIFIER=%s\n' "$installed" "$team"
codesign -dv --verbose=4 "$installed" 2>&1 | grep -E '^(Identifier|TeamIdentifier|CDHash)='
