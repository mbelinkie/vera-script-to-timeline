#!/bin/sh
# Compile and run isolated admission/fail-closed Swift tests; zero GUI effects.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: Swift/AppKit contract tests require macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
sdk=$(xcrun --sdk macosx --show-sdk-path)
xcrun clang -isysroot "$sdk" -Werror -Wno-deprecated-declarations \
    -c "$root/Sources/VERAGUIHelper/LegacyForeground.c" \
    -o "$scratch/LegacyForeground.o"
xcrun swiftc -Onone -parse-as-library -sdk "$sdk" \
    -import-objc-header "$root/Sources/VERAGUIHelper/LegacyForeground.h" \
    "$root/Sources/VERAGUIHelper/FocusProtocol.swift" \
    "$root/Sources/VERAGUIHelper/TargetInspection.swift" \
    "$root/Sources/VERAGUIHelper/FocusContractSelfTest.swift" \
    "$scratch/LegacyForeground.o" \
    -framework AppKit -framework ApplicationServices -framework Carbon \
    -o "$scratch/FocusContractSelfTest"
"$scratch/FocusContractSelfTest"
