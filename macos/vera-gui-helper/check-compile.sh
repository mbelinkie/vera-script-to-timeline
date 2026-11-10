#!/bin/sh
# Native compile/link validation only; no signing, installation, focus, or GUI.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: Swift/AppKit compile requires macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
sdk=$(xcrun --sdk macosx --show-sdk-path)
xcrun clang -isysroot "$sdk" -Werror -Wno-deprecated-declarations \
    -c "$root/Sources/VERAGUIHelper/LegacyForeground.c" \
    -o "$scratch/LegacyForeground.o"
xcrun swiftc -Onone -sdk "$sdk" \
    -import-objc-header "$root/Sources/VERAGUIHelper/LegacyForeground.h" \
    "$root/Sources/VERAGUIHelper/FocusProtocol.swift" \
    "$root/Sources/VERAGUIHelper/TargetInspection.swift" \
    "$root/Sources/VERAGUIHelper/main.swift" \
    "$scratch/LegacyForeground.o" \
    -framework AppKit -framework ApplicationServices -framework Carbon \
    -o "$scratch/VERAGUIHelper"
test -x "$scratch/VERAGUIHelper"
echo 'SWIFT_HELPER_COMPILE_LINK_PASS (no signing, app launch, or GUI operation)'
