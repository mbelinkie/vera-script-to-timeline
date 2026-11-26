"""Decode a bounded direct-image original in a short-lived local process."""

import io
import json
import re
import struct
import sys

from PIL import Image

MAX_BYTES = 56 * 1024 * 1024
MAX_EDGE = 8192
MAX_PIXELS = 16_777_216
JPEG_SCAN_MARKER = re.compile(rb"\xff[^\xff\x00\xd0-\xd7]")


def _single_jpeg(bytes_: bytes) -> bool:
    """Require the first EOI marker to end the file, including progressive JPEGs."""
    offset = 2  # Pillow has already identified SOI.
    while offset < len(bytes_):
        if bytes_[offset] != 0xFF:
            return False
        while offset < len(bytes_) and bytes_[offset] == 0xFF:
            offset += 1
        if offset == len(bytes_):
            return False
        marker = bytes_[offset]
        offset += 1
        if marker == 0xD9:
            return offset == len(bytes_)
        if marker in {0, 1, 0xD8} or 0xD0 <= marker <= 0xD7:
            return False
        length = int.from_bytes(bytes_[offset : offset + 2], "big")
        if length < 2 or offset + length > len(bytes_):
            return False
        offset += length
        if marker == 0xDA:
            match = JPEG_SCAN_MARKER.search(bytes_, offset)
            if match is None:
                return False
            offset = match.start()
    return False


def _single_png(bytes_: bytes) -> bool:
    offset = 8  # Pillow has already identified the signature.
    while offset + 12 <= len(bytes_):
        length = int.from_bytes(bytes_[offset : offset + 4], "big")
        kind = bytes_[offset + 4 : offset + 8]
        offset += 12 + length
        if kind in {b"acTL", b"fcTL", b"fdAT"}:
            return False
        if kind == b"IEND":
            return length == 0 and offset == len(bytes_)
    return False


def inspect(bytes_: bytes) -> dict[str, int | str]:
    if not 0 < len(bytes_) <= MAX_BYTES:
        raise ValueError("invalid image size")
    with Image.open(io.BytesIO(bytes_), formats=["JPEG", "PNG"]) as image:
        width, height = image.size
        if not (
            0 < width <= MAX_EDGE
            and 0 < height <= MAX_EDGE
            and width * height <= MAX_PIXELS
        ):
            raise ValueError("invalid image dimensions")
        if (
            getattr(image, "n_frames", 1) != 1
            or image.get_format_mimetype() == "image/apng"
        ):
            raise ValueError("animated or multi-image input")
        if image.format == "JPEG" and not _single_jpeg(bytes_):
            raise ValueError("invalid JPEG framing")
        if image.format == "PNG" and not _single_png(bytes_):
            raise ValueError("invalid PNG framing")
        mime = "image/png" if image.format == "PNG" else "image/jpeg"
        image.verify()
    with Image.open(io.BytesIO(bytes_), formats=["JPEG", "PNG"]) as image:
        orientation = image.getexif().get(274, 1)
        if type(orientation) is not int or not 1 <= orientation <= 8:
            raise ValueError("invalid orientation")
        image.load()
    if orientation >= 5:
        width, height = height, width
    return {
        "mimeType": mime,
        "width": width,
        "height": height,
        "orientation": orientation,
        "frameCount": 1,
    }


def main() -> int:
    try:
        result = inspect(sys.stdin.buffer.read(MAX_BYTES + 1))
    except (
        OSError,
        ValueError,
        SyntaxError,
        struct.error,
        Image.DecompressionBombError,
    ):
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
