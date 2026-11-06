"""Static offline matte provenance and geometry checks; not Studio output proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from vera_timeline_agent.native_image_motion import native_projected_point

from scripts.issue336_studio_matte_probe import _source_rgb, create_public_matte
from scripts.issue336_studio_qualify import png

_VERIFICATION = (
    Path(__file__).resolve().parents[1] / "docs" / "verification" / "issue-336"
)


def test_actual_studio_source_matte_motion_raster_and_immutable_reopen() -> None:
    """Stored native run5 evidence, not an invented/mocked Resolve capability."""
    prior = json.loads((_VERIFICATION / "studio-run5-pixels.json").read_text())
    result = json.loads((_VERIFICATION / "studio-run5-matte-pixels.json").read_text())
    lineage = result["source_to_matte"]
    assert result["native_app"] == prior["native_app"] == "21.1.1.10"
    assert lineage["sourceSha256"] == prior["source_sha256"]["square"]
    assert lineage["derivedSha256"] != lineage["sourceSha256"]
    assert lineage["canvas"] == [1600, 900]
    assert lineage["contentRect"] == [575, 225, 450, 450]
    assert lineage["backgroundRgb"] == [0, 0, 0]
    for field in ("native_otio_sha256", "native_movie_sha256"):
        assert len(result[field]) == 64
    decoded = result["decoded"]
    assert decoded["frames"] == 48
    assert decoded["size"] == [1280, 720]
    assert len(decoded["decodedSha256"]) == 64
    assert list(decoded["samples"]) == ["0", "12", "24", "36", "47"]
    assert len(result["prior_11_movies_sha256_unchanged"]) == 11
    assert result["reopened"]["names"] == [
        *prior["reopened"]["names"],
        "square-matte-motion-48",
    ]
    assert result["reopened"]["durations"] == [*prior["reopened"]["durations"], 48]
    magenta = []
    for label, sample in decoded["samples"].items():
        witnesses = sample["witnesses"]
        for color in ("red", "green", "blue", "yellow", "magenta"):
            assert witnesses[color] is not None
            assert all(
                0 <= x <= limit
                for x, limit in zip(witnesses[color], (1279, 719), strict=True)
            )
        frame = int(label)
        frac = frame / 48
        projected = native_projected_point(
            source_size=(1600, 900),
            timeline_size=(1280, 720),
            framing="contain",
            source_point=((575 + 450 * 0.75) / 1600, (225 + 450 * 0.30) / 900),
            center=(0.12 * frac, -0.08 * frac),
            native_scale=0.8 + 0.25 * frac,
        )
        assert projected == pytest.approx(witnesses["magenta"], abs=3)
        magenta.append(tuple(witnesses["magenta"]))
    assert len(set(magenta)) == 5


def _pixel(rgb: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    pos = 3 * (y * width + x)
    return tuple(rgb[pos : pos + 3])  # type: ignore[return-value]


def test_matte_is_deterministic_full_source_contain_with_hashed_lineage(
    tmp_path: Path,
) -> None:
    source = tmp_path / "public.png"
    png(source, 1000, 1000)
    prior_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    first = tmp_path / "derived1.png"
    second = tmp_path / "derived2.png"
    evidence = create_public_matte(source, first)
    repeated = create_public_matte(source, second)
    assert evidence["sourceSha256"] == prior_hash
    assert repeated["derivedSha256"] == evidence["derivedSha256"]
    assert evidence["derivedSha256"] != prior_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest() == prior_hash
    assert evidence["canvas"] == [1600, 900]
    assert evidence["contentRect"] == [575, 225, 450, 450]
    assert evidence["backgroundRgb"] == [0, 0, 0]
    width, height, pixels = _source_rgb(first, expected_size=(1600, 900))
    assert (width, height) == (1600, 900)
    assert _pixel(pixels, width, 0, 0) == (0, 0, 0)
    assert _pixel(pixels, width, 1599, 899) == (0, 0, 0)
    assert _pixel(pixels, width, 585, 235) == (245, 24, 20)
    assert _pixel(pixels, width, 1015, 235) == (20, 240, 25)
    assert _pixel(pixels, width, 585, 665) == (24, 35, 245)
    assert _pixel(pixels, width, 1015, 665) == (245, 240, 15)
    assert _pixel(pixels, width, 912, 360) == (245, 25, 245)


@pytest.mark.parametrize("frame", [0, 12, 24, 36, 47])
def test_composed_source_bounds_remain_inside_output_during_native_motion(
    frame: int,
) -> None:
    t = frame / 48
    center = (0.12 * t, -0.08 * t)
    scale = 0.8 + 0.25 * t
    for point in ((575 / 1600, 225 / 900), (1025 / 1600, 675 / 900)):
        x, y = native_projected_point(
            source_size=(1600, 900),
            timeline_size=(1280, 720),
            framing="contain",
            source_point=point,
            center=center,
            native_scale=scale,
        )
        assert 0 < x < 1280
        assert 0 < y < 720


def test_source_tamper_and_overwrite_refuse(tmp_path: Path) -> None:
    source = tmp_path / "wrong-shape.png"
    png(source, 300, 300)
    with pytest.raises(ValueError, match="source dimensions"):
        create_public_matte(source, tmp_path / "matte.png")
    png(source, 1000, 1000)
    target = tmp_path / "matte.png"
    target.write_bytes(b"existing")
    with pytest.raises(ValueError, match="overwrite"):
        create_public_matte(source, target)
