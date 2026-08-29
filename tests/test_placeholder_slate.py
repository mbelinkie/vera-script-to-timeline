from __future__ import annotations

import struct
import zlib

import pytest
from vera_timeline_agent.placeholder_slate import render_placeholder_slate

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _decode_rgb_png(value: bytes) -> tuple[int, int, bytes]:
    assert value.startswith(PNG_SIGNATURE)
    cursor = len(PNG_SIGNATURE)
    width = 0
    height = 0
    compressed = bytearray()
    chunk_names: list[bytes] = []
    while cursor < len(value):
        length = struct.unpack(">I", value[cursor : cursor + 4])[0]
        name = value[cursor + 4 : cursor + 8]
        data = value[cursor + 8 : cursor + 8 + length]
        expected_crc = struct.unpack(
            ">I", value[cursor + 8 + length : cursor + 12 + length]
        )[0]
        assert zlib.crc32(name + data) & 0xFFFFFFFF == expected_crc
        chunk_names.append(name)
        if name == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            assert (depth, color, compression, filtering, interlace) == (
                8,
                2,
                0,
                0,
                0,
            )
        elif name == b"IDAT":
            compressed.extend(data)
        elif name == b"IEND":
            break
        cursor += 12 + length

    assert chunk_names == [b"IHDR", b"IDAT", b"IEND"]
    scanlines = zlib.decompress(compressed)
    row_size = width * 3 + 1
    assert len(scanlines) == height * row_size
    assert all(scanlines[offset] == 0 for offset in range(0, len(scanlines), row_size))
    pixels = b"".join(
        scanlines[offset + 1 : offset + row_size]
        for offset in range(0, len(scanlines), row_size)
    )
    return width, height, pixels


def test_renders_valid_png_at_requested_dimensions() -> None:
    value = render_placeholder_slate("MISSING INTERVIEW CLIP", 320, 180)

    width, height, pixels = _decode_rgb_png(value)

    assert (width, height) == (320, 180)
    assert len(pixels) == width * height * 3


def test_render_is_byte_deterministic_and_label_sensitive() -> None:
    first = render_placeholder_slate("MISSING CLIP A", 192, 108)
    second = render_placeholder_slate("MISSING CLIP A", 192, 108)
    different = render_placeholder_slate("MISSING CLIP B", 192, 108)

    assert first == second
    assert first != different


def test_known_label_draws_foreground_glyph_pixels() -> None:
    _, _, pixels = _decode_rgb_png(render_placeholder_slate("A", 64, 48))

    pixel_colors = {
        tuple(pixels[index : index + 3]) for index in range(0, len(pixels), 3)
    }
    assert (245, 245, 245) in pixel_colors


def test_arbitrary_text_is_normalized_or_uses_fallback_glyphs_safely() -> None:
    unicode_label = render_placeholder_slate(
        "  Caf\N{LATIN SMALL LETTER E WITH ACUTE}\n\N{CAT FACE}  ", 160, 90
    )
    normalized_label = render_placeholder_slate("CAFE ?", 160, 90)

    assert unicode_label == normalized_label


@pytest.mark.parametrize(
    ("width", "height"),
    [(15, 16), (16, 15), (0, 16), (-1, 16), (16_385, 16), (16, 16_385)],
)
def test_rejects_dimensions_outside_supported_bounds(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        render_placeholder_slate("MISSING", width, height)


@pytest.mark.parametrize(("width", "height"), [(True, 16), (16, False), (1.5, 16)])
def test_rejects_non_integer_dimensions(width: object, height: object) -> None:
    with pytest.raises(TypeError, match="integers"):
        render_placeholder_slate("MISSING", width, height)  # type: ignore[arg-type]


def test_rejects_non_string_label() -> None:
    with pytest.raises(TypeError, match="label must be a string"):
        render_placeholder_slate(123, 64, 48)  # type: ignore[arg-type]
