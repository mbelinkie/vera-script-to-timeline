#!/bin/sh
set -eu

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 IMAGE CHECKPOINT_DIR INPUT_DIR OUTPUT_DIR" >&2
    exit 2
fi

IMAGE=$1
CHECKPOINT_DIR=$2
INPUT_DIR=$3
OUTPUT_DIR=$4

mkdir -p "$OUTPUT_DIR"
docker run --rm \
    --platform linux/amd64 \
    --network none \
    --cpus 6 \
    --memory 7g \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=1g \
    --mount "type=bind,src=$CHECKPOINT_DIR/ears_reverb.ckpt,dst=/models/ears_reverb.ckpt,readonly" \
    --mount "type=bind,src=$INPUT_DIR,dst=/input,readonly" \
    --mount "type=bind,src=$OUTPUT_DIR,dst=/output" \
    "$IMAGE" \
    --test_dir /input \
    --enhanced_dir /output \
    --ckpt /models/ears_reverb.ckpt \
    --device cpu \
    --N 30
