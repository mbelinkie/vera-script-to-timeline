"""Compare only #219's fixed private render set using bundled Pillow."""

import hashlib
import json

import probe
from PIL import Image, ImageChops


def chunks(raw):
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    position = 8
    result = []
    while position < len(raw):
        length = int.from_bytes(raw[position : position + 4], "big")
        kind = raw[position + 4 : position + 8].decode()
        payload = raw[position + 8 : position + 8 + length]
        result.append((kind, payload))
        position += length + 12
    assert position == len(raw)
    return result


def analyze():
    root = probe.OUTPUT
    rows = []
    for name, case in probe.CASES.items():
        for frame, state in case["samples"].items():
            matches = [
                list((root / run / "renders" / name).glob(f"{name}-f{frame:03d}_*.png"))
                for run in ("run-a", "run-b")
            ]
            assert all(len(found) == 1 for found in matches)
            a, b = (found[0] for found in matches)
            raw_a, raw_b = a.read_bytes(), b.read_bytes()
            with Image.open(a) as image_a, Image.open(b) as image_b:
                rgb_a, rgb_b = image_a.convert("RGB"), image_b.convert("RGB")
                assert rgb_a.size == rgb_b.size == (1920, 1080)
                assert ImageChops.difference(rgb_a, rgb_b).getbbox() is None
                chunk_a, chunk_b = chunks(raw_a), chunks(raw_b)
                assert len(chunk_a) == len(chunk_b)
                for (kind_a, payload_a), (kind_b, payload_b) in zip(
                    chunk_a, chunk_b, strict=True
                ):
                    assert kind_a == kind_b
                    if kind_a != "iCCP":
                        assert payload_a == payload_b
                icc_a, icc_b = image_a.info["icc_profile"], image_b.info["icc_profile"]
                assert len(icc_a) == len(icc_b)
                differing = [
                    i
                    for i, (x, y) in enumerate(zip(icc_a, icc_b, strict=True))
                    if x != y
                ]
                assert set(differing) <= set(range(24, 36))
                ratios = []
                # Private geometry readback: BodyTop538, RowPitch54; avoid text/grid.
                for y in (550, 604, 658):
                    crop = rgb_a.crop((280, y, 340, y + 30))
                    pixels = list(crop.get_flattened_data())
                    ratios.append(
                        sum(r > g + 25 and r > blue + 10 for r, g, blue in pixels)
                        / len(pixels)
                    )
                if frame in (0, 239):
                    assert rgb_a.getbbox() is None  # Authored entrance/exit is black.
                else:
                    assert [ratio > 0.95 for ratio in ratios] == [
                        str(i) in state.split(",") for i in (1, 2, 3)
                    ]
                rows.append(
                    {
                        "id": f"{name}-f{frame:03d}",
                        "frame": frame,
                        "state": state,
                        "file_a_sha256": hashlib.sha256(raw_a).hexdigest(),
                        "file_b_sha256": hashlib.sha256(raw_b).hexdigest(),
                        "decoded_rgb_sha256": hashlib.sha256(
                            rgb_a.tobytes()
                        ).hexdigest(),
                        "repeat_pixels_equal": True,
                        "icc_diff_offsets": differing,
                        "row_red_coverage": ratios,
                    }
                )
    assert len(rows) == 36
    for run in ("run-a", "run-b"):
        assert len(list((root / run / "renders").rglob("*.png"))) == 36
    report = {
        "frame_pairs": 36,
        "pixel_identical_pairs": 36,
        "semantic_hold_samples": 28,
        "authored_black_endpoints": 8,
        "rows": rows,
    }
    (root / "render-analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    return {key: value for key, value in report.items() if key != "rows"}


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
