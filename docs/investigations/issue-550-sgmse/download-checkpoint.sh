#!/bin/sh
set -eu

MODEL_DIR=${1:-models}
FILE="$MODEL_DIR/ears_reverb.ckpt"
URL='https://huggingface.co/sp-uhh/speech-enhancement-sgmse/resolve/89193ea626c85f3ba36c5ca6d604068ebb2e5e58/pretrained_checkpoints/48_khz_models/ears_reverb.ckpt'
EXPECTED_SHA256='9be62a3df0401398e5626a1c4dc65039220499d506941ecf110b52cccb7309b2'
EXPECTED_BYTES=1295848436

if [ -e "$FILE" ]; then
    echo "Refusing to overwrite existing checkpoint: $FILE" >&2
    exit 1
fi

mkdir -p "$MODEL_DIR"
curl --fail --location --retry 3 --output "$FILE" "$URL"

ACTUAL_BYTES=$(wc -c < "$FILE" | tr -d ' ')
if [ "$ACTUAL_BYTES" -ne "$EXPECTED_BYTES" ]; then
    echo "Unexpected checkpoint size: $ACTUAL_BYTES bytes" >&2
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL_SHA256=$(sha256sum "$FILE" | awk '{print $1}')
else
    ACTUAL_SHA256=$(shasum -a 256 "$FILE" | awk '{print $1}')
fi
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "Unexpected checkpoint SHA-256: $ACTUAL_SHA256" >&2
    exit 1
fi
echo "Verified $FILE ($ACTUAL_BYTES bytes, SHA-256 $EXPECTED_SHA256)"
