#!/bin/sh
# Compile and run isolated admission/fail-closed Swift tests; zero GUI effects.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'BLOCK: Swift/AppKit contract tests require macOS' >&2
    exit 78
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
case "${1:-all}" in all|focus|roll) ;; *) echo 'choose all, focus or roll' >&2; exit 2 ;; esac
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
sdk=$(xcrun --sdk macosx --show-sdk-path)
xcrun clang -isysroot "$sdk" -Werror -Wno-deprecated-declarations \
    -c "$root/Sources/VERAGUIHelper/LegacyForeground.c" \
    -o "$scratch/LegacyForeground.o"
if [ "${1:-all}" != roll ]; then
xcrun swiftc -Onone -parse-as-library -sdk "$sdk" \
    -import-objc-header "$root/Sources/VERAGUIHelper/LegacyForeground.h" \
    "$root/Sources/VERAGUIHelper/FocusProtocol.swift" \
    "$root/Sources/VERAGUIHelper/TargetInspection.swift" \
    "$root/Sources/VERAGUIHelper/RollActuator.swift" \
    "$root/Sources/VERAGUIHelper/RollSpool.swift" \
    "$root/Sources/VERAGUIHelper/FocusContractSelfTest.swift" \
    "$scratch/LegacyForeground.o" \
    -framework AppKit -framework ApplicationServices -framework Carbon -framework Security \
    -o "$scratch/FocusContractSelfTest"
"$scratch/FocusContractSelfTest"
fi

# The Roll self-test supplies a fake AX implementation. It never performs
# AXPress on a real process or launches Resolve.
if [ "${1:-all}" != focus ]; then
xcrun swiftc -Onone -parse-as-library -sdk "$sdk" \
    -import-objc-header "$root/Sources/VERAGUIHelper/LegacyForeground.h" \
    "$root/Sources/VERAGUIHelper/FocusProtocol.swift" \
    "$root/Sources/VERAGUIHelper/TargetInspection.swift" \
    "$root/Sources/VERAGUIHelper/RollActuator.swift" \
    "$root/Sources/VERAGUIHelper/RollSpool.swift" \
    "$root/Sources/VERAGUIHelper/RollActuatorSelfTest.swift" \
    "$scratch/LegacyForeground.o" \
    -framework AppKit -framework ApplicationServices -framework Carbon -framework Security \
    -o "$scratch/RollActuatorSelfTest"
"$scratch/RollActuatorSelfTest"
fi
