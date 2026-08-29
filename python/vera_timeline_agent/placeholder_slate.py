"""Deterministic, dependency-free PNG placeholder slates."""

from __future__ import annotations

import struct
import unicodedata
import zlib
from collections.abc import Iterable

MIN_DIMENSION = 16
MAX_DIMENSION = 16_384
MAX_PIXELS = 67_108_864

_BACKGROUND = (38, 14, 20)
_ACCENT = (178, 45, 65)
_BORDER = (224, 66, 84)
_FOREGROUND = (245, 245, 245)
_SHADOW = (13, 7, 9)

# A fixed 5x7 font keeps slate rendering independent of installed fonts, locale,
# platform drawing APIs, and optional imaging libraries.
_FONT_ROWS = {
    " ": "00000/00000/00000/00000/00000/00000/00000",
    "!": "00100/00100/00100/00100/00100/00000/00100",
    '"': "01010/01010/01010/00000/00000/00000/00000",
    "#": "01010/11111/01010/01010/11111/01010/00000",
    "$": "00100/01111/10100/01110/00101/11110/00100",
    "%": "11001/11010/00100/01000/10110/00110/00000",
    "&": "01100/10010/10100/01000/10101/10010/01101",
    "'": "00100/00100/01000/00000/00000/00000/00000",
    "(": "00010/00100/01000/01000/01000/00100/00010",
    ")": "01000/00100/00010/00010/00010/00100/01000",
    "*": "00000/10101/01110/11111/01110/10101/00000",
    "+": "00000/00100/00100/11111/00100/00100/00000",
    ",": "00000/00000/00000/00000/00110/00100/01000",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    ".": "00000/00000/00000/00000/00000/00110/00110",
    "/": "00001/00010/00100/01000/10000/00000/00000",
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    ":": "00000/00110/00110/00000/00110/00110/00000",
    ";": "00000/00110/00110/00000/00110/00100/01000",
    "<": "00010/00100/01000/10000/01000/00100/00010",
    "=": "00000/00000/11111/00000/11111/00000/00000",
    ">": "01000/00100/00010/00001/00010/00100/01000",
    "?": "01110/10001/00001/00010/00100/00000/00100",
    "@": "01110/10001/10111/10101/10111/10000/01111",
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "01110/00100/00100/00100/00100/00100/01110",
    "J": "00111/00010/00010/00010/00010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001",
    "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010",
    "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "Z": "11111/00001/00010/00100/01000/10000/11111",
    "[": "01110/01000/01000/01000/01000/01000/01110",
    "\\": "10000/01000/00100/00010/00001/00000/00000",
    "]": "01110/00010/00010/00010/00010/00010/01110",
    "^": "00100/01010/10001/00000/00000/00000/00000",
    "_": "00000/00000/00000/00000/00000/00000/11111",
}
_FONT = {character: tuple(rows.split("/")) for character, rows in _FONT_ROWS.items()}


def render_placeholder_slate(label: str, width: int, height: int) -> bytes:
    """Render ``label`` as deterministic RGB PNG bytes at exact dimensions."""
    if not isinstance(label, str):
        raise TypeError("label must be a string")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
    ):
        raise TypeError("placeholder dimensions must be integers")
    if (
        width < MIN_DIMENSION
        or height < MIN_DIMENSION
        or width > MAX_DIMENSION
        or height > MAX_DIMENSION
        or width * height > MAX_PIXELS
    ):
        raise ValueError(
            "placeholder dimensions must be between "
            f"{MIN_DIMENSION} and {MAX_DIMENSION} pixels per side and no more "
            f"than {MAX_PIXELS} total pixels"
        )

    normalized_label = _normalize_label(label)
    pixels = bytearray(_BACKGROUND * (width * height))
    border_width = max(1, min(width, height) // 64)
    _draw_border(pixels, width, height, border_width)
    _draw_cross(pixels, width, height, max(1, border_width))
    _draw_centered_label(pixels, width, height, normalized_label)
    return _encode_png(pixels, width, height)


def _normalize_label(label: str) -> str:
    characters: list[str] = []
    for character in unicodedata.normalize("NFKD", label).upper():
        if unicodedata.combining(character):
            continue
        if character.isspace():
            characters.append(" ")
        elif character in _FONT:
            characters.append(character)
        else:
            characters.append("?")
    normalized = " ".join("".join(characters).split())
    return normalized or "PLACEHOLDER"


def _draw_border(pixels: bytearray, width: int, height: int, border_width: int) -> None:
    _fill_rect(pixels, width, 0, 0, width, border_width, _BORDER)
    _fill_rect(pixels, width, 0, height - border_width, width, height, _BORDER)
    _fill_rect(pixels, width, 0, 0, border_width, height, _BORDER)
    _fill_rect(pixels, width, width - border_width, 0, width, height, _BORDER)


def _draw_cross(pixels: bytearray, width: int, height: int, thickness: int) -> None:
    for x in range(width):
        first_y = x * (height - 1) // (width - 1)
        second_y = height - 1 - first_y
        for offset in range(-(thickness // 2), thickness - thickness // 2):
            _set_pixel(pixels, width, height, x, first_y + offset, _ACCENT)
            _set_pixel(pixels, width, height, x, second_y + offset, _ACCENT)


def _draw_centered_label(
    pixels: bytearray, width: int, height: int, label: str
) -> None:
    margin = max(2, min(width, height) // 18)
    scale = max(1, min(16, width // 120, height // 45))
    character_step = 6 * scale
    line_step = 9 * scale
    max_characters = max(1, (width - 2 * margin + scale) // character_step)
    max_lines = max(1, (height - 2 * margin + scale) // line_step)
    lines = _wrap_text(label, max_characters, max_lines)
    block_height = len(lines) * line_step - 2 * scale
    start_y = max(margin, (height - block_height) // 2)
    for line_index, line in enumerate(lines):
        line_width = len(line) * character_step - scale
        start_x = max(margin, (width - line_width) // 2)
        _draw_text(
            pixels,
            width,
            height,
            start_x,
            start_y + line_index * line_step,
            line,
            scale,
        )


def _wrap_text(label: str, max_characters: int, max_lines: int) -> tuple[str, ...]:
    words = label.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = tuple(_chunks(word, max_characters)) or ("",)
        for piece_index, piece in enumerate(pieces):
            separator = " " if current and piece_index == 0 else ""
            if current and len(current) + len(separator) + len(piece) > max_characters:
                lines.append(current)
                current = ""
            if len(lines) == max_lines:
                return _mark_truncated(lines, max_characters)
            current = f"{current}{separator}{piece}"
            if piece_index < len(pieces) - 1:
                lines.append(current)
                current = ""
                if len(lines) == max_lines:
                    return _mark_truncated(lines, max_characters)
    if current:
        lines.append(current)
    return tuple(lines[:max_lines])


def _chunks(value: str, size: int) -> Iterable[str]:
    return (value[index : index + size] for index in range(0, len(value), size))


def _mark_truncated(lines: list[str], max_characters: int) -> tuple[str, ...]:
    last = lines[-1]
    lines[-1] = f"{last[: max(0, max_characters - 1)]}?"
    return tuple(lines)


def _draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    start_x: int,
    start_y: int,
    text: str,
    scale: int,
) -> None:
    for character_index, character in enumerate(text):
        glyph = _FONT.get(character, _FONT["?"])
        glyph_x = start_x + character_index * 6 * scale
        _draw_glyph(
            pixels,
            width,
            height,
            glyph_x + scale,
            start_y + scale,
            glyph,
            scale,
            _SHADOW,
        )
        _draw_glyph(pixels, width, height, glyph_x, start_y, glyph, scale, _FOREGROUND)


def _draw_glyph(
    pixels: bytearray,
    width: int,
    height: int,
    start_x: int,
    start_y: int,
    glyph: tuple[str, ...],
    scale: int,
    color: tuple[int, int, int],
) -> None:
    for row_index, row in enumerate(glyph):
        for column_index, value in enumerate(row):
            if value == "1":
                _fill_rect(
                    pixels,
                    width,
                    start_x + column_index * scale,
                    start_y + row_index * scale,
                    start_x + (column_index + 1) * scale,
                    start_y + (row_index + 1) * scale,
                    color,
                    height=height,
                )


def _fill_rect(
    pixels: bytearray,
    width: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    color: tuple[int, int, int],
    *,
    height: int | None = None,
) -> None:
    image_height = bottom if height is None else height
    clipped_left = max(0, left)
    clipped_top = max(0, top)
    clipped_right = min(width, right)
    clipped_bottom = min(image_height, bottom)
    row = bytes(color) * max(0, clipped_right - clipped_left)
    for y in range(clipped_top, clipped_bottom):
        start = (y * width + clipped_left) * 3
        pixels[start : start + len(row)] = row


def _set_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 3
        pixels[offset : offset + 3] = bytes(color)


def _encode_png(pixels: bytearray, width: int, height: int) -> bytes:
    row_bytes = width * 3
    scanlines = bytearray()
    for row_index in range(height):
        start = row_index * row_bytes
        scanlines.append(0)
        scanlines.extend(pixels[start : start + row_bytes])
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressor = zlib.compressobj(level=9, wbits=15, strategy=zlib.Z_FIXED)
    compressed = compressor.compress(scanlines) + compressor.flush()
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(name: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(name + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)
