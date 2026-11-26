import io
import subprocess
import sys

import pytest
from PIL import Image
from vera_timeline_agent.direct_image_inspect import inspect


def encoded(format_: str, **options: object) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 7)).save(output, format_, **options)
    return output.getvalue()


@pytest.mark.parametrize("format_", ["PNG", "JPEG"])
def test_decodes_display_dimensions_and_exif_orientation(format_: str) -> None:
    exif = Image.Exif()
    exif[274] = 6
    original = encoded(format_, exif=exif)
    assert inspect(original) == {
        "mimeType": f"image/{format_.lower()}",
        "width": 7,
        "height": 4,
        "orientation": 6,
        "frameCount": 1,
    }


def test_accepts_progressive_jpeg() -> None:
    assert inspect(encoded("JPEG", progressive=True))["width"] == 4


def test_cli_refuses_jpeg_with_truncated_exif() -> None:
    incomplete_exif = Image.Exif().tobytes()[:11]
    result = subprocess.run(
        [sys.executable, "-I", "-m", "vera_timeline_agent.direct_image_inspect"],
        input=encoded("JPEG", dpi=(72, 72), exif=incomplete_exif),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""


@pytest.mark.parametrize("format_", ["PNG", "JPEG"])
def test_refuses_truncated_and_concatenated_images(format_: str) -> None:
    image = encoded(format_)
    for malformed in (image[:-8], image + image):
        with pytest.raises((OSError, ValueError, SyntaxError)):
            inspect(malformed)


def test_refuses_animated_png_and_other_formats() -> None:
    animated = encoded(
        "PNG", save_all=True, append_images=[Image.new("RGB", (4, 7), "red")]
    )
    for unsupported in (animated, encoded("GIF"), b"<html>"):
        with pytest.raises((OSError, ValueError)):
            inspect(unsupported)


def test_refuses_excessive_dimensions() -> None:
    output = io.BytesIO()
    Image.new("RGB", (8193, 1)).save(output, "PNG")
    with pytest.raises(ValueError, match="dimensions"):
        inspect(output.getvalue())
