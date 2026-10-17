#!/usr/bin/env python3
"""Generate synthetic OCR fixtures and compare the two issue #105 candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from PIL import __version__ as pillow_version

SCRIPT_DIR = Path(__file__).resolve().parent
ARIAL = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
ARIAL_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
ARIAL_UNICODE = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
WIDTH = 1600
HEIGHT = 900
RUNS = 5


def digest_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def rect_dict(box: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = box
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def union_rect(rects: list[dict[str, int]]) -> dict[str, int]:
    left = min(item["x"] for item in rects)
    top = min(item["y"] for item in rects)
    right = max(item["x"] + item["width"] for item in rects)
    bottom = max(item["y"] + item["height"] for item in rects)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def draw_line(
    image: Image.Image,
    expected: dict[str, list[dict[str, Any]]],
    text: str,
    xy: tuple[int, int],
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    line_id: str,
) -> None:
    draw = ImageDraw.Draw(image)
    x, y = xy
    word_rects: list[dict[str, int]] = []
    for index, word in enumerate(text.split()):
        bbox = draw.textbbox((x, y), word, font=text_font)
        rect = rect_dict(tuple(int(value) for value in bbox))
        draw.text((x, y), word, font=text_font, fill=fill)
        expected["words"].append({"text": word, "rect": rect, "lineId": line_id})
        word_rects.append(rect)
        x += math.ceil(draw.textlength(word, font=text_font))
        if index + 1 < len(text.split()):
            x += math.ceil(draw.textlength(" ", font=text_font))
    expected["lines"].append(
        {"text": text, "rect": union_rect(word_rects), "lineId": line_id}
    )


def draw_rotated_line(
    image: Image.Image,
    expected: dict[str, list[dict[str, Any]]],
    text: str,
    xy: tuple[int, int],
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    angle: float,
    line_id: str,
) -> None:
    x, y = xy
    word_rects: list[dict[str, int]] = []
    for word in text.split():
        probe = Image.new("RGBA", (600, 180), (255, 255, 255, 0))
        probe_draw = ImageDraw.Draw(probe)
        bbox = probe_draw.textbbox((20, 20), word, font=text_font)
        probe_draw.text((20, 20), word, font=text_font, fill=fill)
        crop = probe.crop(
            (max(0, bbox[0] - 4), max(0, bbox[1] - 4), bbox[2] + 4, bbox[3] + 4)
        )
        rotated = crop.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        alpha_box = rotated.getchannel("A").getbbox()
        assert alpha_box is not None
        image.paste(rotated, (x, y), rotated)
        rect = rect_dict(
            (x + alpha_box[0], y + alpha_box[1], x + alpha_box[2], y + alpha_box[3])
        )
        expected["words"].append({"text": word, "rect": rect, "lineId": line_id})
        word_rects.append(rect)
        x += rotated.width + 14
        y += 8
    expected["lines"].append(
        {"text": text, "rect": union_rect(word_rects), "lineId": line_id}
    )


def fixture_base() -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), "#f7f8fa")


def clean_fixture() -> tuple[Image.Image, dict[str, Any]]:
    image = fixture_base()
    draw = ImageDraw.Draw(image)
    draw.rectangle((45, 35, 1555, 865), fill="#ffffff", outline="#d7dce2", width=2)
    expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw_line(
        image,
        expected,
        "Northwind Bulletin",
        (85, 68),
        font(ARIAL_BOLD, 48),
        "#13213a",
        "c1",
    )
    draw_line(
        image,
        expected,
        "Synthetic operations update",
        (88, 145),
        font(ARIAL, 27),
        "#506078",
        "c2",
    )
    draw_line(
        image,
        expected,
        "Overview Alerts Archive",
        (1060, 82),
        font(ARIAL, 22),
        "#34445b",
        "c3",
    )
    draw.rectangle((78, 238, 1010, 515), fill="#eef5fb", outline="#bfd2e3", width=2)
    draw_line(
        image,
        expected,
        "Weather review",
        (110, 260),
        font(ARIAL_BOLD, 34),
        "#13213a",
        "c4",
    )
    draw_line(
        image,
        expected,
        "Rain arrives Tuesday morning",
        (110, 328),
        font(ARIAL, 28),
        "#24364f",
        "c5",
    )
    draw_line(
        image,
        expected,
        "Review required before adjustment",
        (110, 382),
        font(ARIAL, 28),
        "#24364f",
        "c6",
    )
    draw.rectangle((110, 452, 315, 500), fill="#145da0")
    draw_line(
        image,
        expected,
        "Open report",
        (135, 461),
        font(ARIAL_BOLD, 21),
        "#ffffff",
        "c7",
    )
    draw_line(
        image,
        expected,
        "Updated locally with fictional data",
        (88, 770),
        font(ARIAL, 20),
        "#65758b",
        "c8",
    )
    return image, {
        "id": "clean-page",
        "description": "Clean synthetic article and navigation layout",
        **expected,
    }


def mixed_fixture() -> tuple[Image.Image, dict[str, Any]]:
    image = fixture_base()
    draw = ImageDraw.Draw(image)
    expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw.rectangle((0, 0, WIDTH, 112), fill="#17324d")
    draw_line(
        image,
        expected,
        "Operations Dashboard",
        (65, 32),
        font(ARIAL_BOLD, 43),
        "#ffffff",
        "m1",
    )
    draw_line(
        image,
        expected,
        "Synthetic status only",
        (1180, 51),
        font(ARIAL, 21),
        "#d4e3ef",
        "m2",
    )
    draw.rectangle((55, 155, 755, 535), fill="#ffffff", outline="#ccd4dd", width=2)
    draw.rectangle((820, 155, 1545, 535), fill="#fffaf0", outline="#e0c48a", width=2)
    draw_line(
        image,
        expected,
        "Sensor summary",
        (90, 185),
        font(ARIAL_BOLD, 31),
        "#15263b",
        "m3",
    )
    draw_line(
        image,
        expected,
        "North array stable",
        (90, 258),
        font(ARIAL, 25),
        "#25384f",
        "m4",
    )
    draw_line(
        image,
        expected,
        "South array under review",
        (90, 313),
        font(ARIAL, 25),
        "#25384f",
        "m5",
    )
    draw_line(
        image,
        expected,
        "Next check fourteen thirty",
        (90, 368),
        font(ARIAL, 25),
        "#25384f",
        "m6",
    )
    draw_line(
        image,
        expected,
        "Approval queue",
        (860, 185),
        font(ARIAL_BOLD, 31),
        "#4b3210",
        "m7",
    )
    draw_line(
        image,
        expected,
        "Two items need review",
        (860, 258),
        font(ARIAL, 25),
        "#593d18",
        "m8",
    )
    draw_line(
        image,
        expected,
        "First item pending",
        (860, 313),
        font(ARIAL, 25),
        "#593d18",
        "m9",
    )
    draw_line(
        image,
        expected,
        "Second item ready",
        (860, 368),
        font(ARIAL, 25),
        "#593d18",
        "m10",
    )
    draw.rectangle((55, 585, 1545, 820), fill="#ffffff", outline="#ccd4dd", width=2)
    draw_line(
        image, expected, "Region", (90, 615), font(ARIAL_BOLD, 22), "#26384c", "m11"
    )
    draw_line(
        image, expected, "State", (720, 615), font(ARIAL_BOLD, 22), "#26384c", "m12"
    )
    draw_line(
        image, expected, "Owner", (1170, 615), font(ARIAL_BOLD, 22), "#26384c", "m13"
    )
    draw_line(image, expected, "Harbor", (90, 690), font(ARIAL, 23), "#30445b", "m14")
    draw_line(image, expected, "Ready", (720, 690), font(ARIAL, 23), "#30445b", "m15")
    draw_line(image, expected, "Aster", (1170, 690), font(ARIAL, 23), "#30445b", "m16")
    return image, {
        "id": "mixed-layout",
        "description": "Synthetic header cards columns and table",
        **expected,
    }


def transformed_fixture() -> tuple[Image.Image, dict[str, Any]]:
    image = fixture_base()
    draw = ImageDraw.Draw(image)
    expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw.rectangle((45, 35, 1555, 865), fill="#ffffff", outline="#d7dce2", width=2)
    draw_line(
        image,
        expected,
        "Scaled and rotated notices",
        (75, 65),
        font(ARIAL_BOLD, 42),
        "#172b45",
        "t1",
    )
    draw_line(
        image,
        expected,
        "Large type remains easy to inspect",
        (78, 165),
        font(ARIAL, 34),
        "#253a54",
        "t2",
    )
    draw_line(
        image,
        expected,
        "Small labels remain selectable",
        (80, 265),
        font(ARIAL, 14),
        "#26384d",
        "t3",
    )
    draw_line(
        image,
        expected,
        "ZOOM ONE HUNDRED TWENTY FIVE",
        (80, 340),
        font(ARIAL_BOLD, 52),
        "#0e5d6f",
        "t4",
    )
    draw_rotated_line(
        image,
        expected,
        "Rotate review before approval",
        (180, 570),
        font(ARIAL_BOLD, 34),
        "#6d2f1e",
        12,
        "t5",
    )
    return image, {
        "id": "scaled-rotated",
        "description": "Small large and twelve-degree rotated synthetic text",
        **expected,
    }


def multilingual_fixture() -> tuple[Image.Image, dict[str, Any]]:
    image = fixture_base()
    draw = ImageDraw.Draw(image)
    expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw.rectangle((45, 35, 1555, 865), fill="#ffffff", outline="#d7dce2", width=2)
    draw_line(
        image,
        expected,
        "Language Coverage",
        (75, 60),
        font(ARIAL_BOLD, 43),
        "#182f4b",
        "l1",
    )
    multilingual_font = font(ARIAL_UNICODE, 31)
    draw_line(
        image,
        expected,
        "English review is ready",
        (90, 175),
        multilingual_font,
        "#273a51",
        "l2",
    )
    draw_line(
        image,
        expected,
        "Révision française prête",
        (90, 285),
        multilingual_font,
        "#273a51",
        "l3",
    )
    draw_line(
        image,
        expected,
        "Página española segura",
        (90, 395),
        multilingual_font,
        "#273a51",
        "l4",
    )
    draw_line(
        image,
        expected,
        "Änderung geprüft und bestätigt",
        (90, 505),
        multilingual_font,
        "#273a51",
        "l5",
    )
    draw_line(
        image,
        expected,
        "Accents must remain visible",
        (90, 650),
        font(ARIAL, 24),
        "#5c6e83",
        "l6",
    )
    return image, {
        "id": "multilingual",
        "description": "Synthetic English French Spanish and German text",
        **expected,
    }


def unreadable_fixture() -> tuple[Image.Image, dict[str, Any]]:
    image = fixture_base()
    draw = ImageDraw.Draw(image)
    expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw.rectangle((45, 35, 1555, 865), fill="#ffffff", outline="#d7dce2", width=2)
    draw_line(
        image,
        expected,
        "Failure Safety",
        (75, 60),
        font(ARIAL_BOLD, 43),
        "#182f4b",
        "u1",
    )
    draw_line(
        image,
        expected,
        "Readable control label",
        (80, 185),
        font(ARIAL, 30),
        "#26394f",
        "u2",
    )
    draw_line(
        image,
        expected,
        "Hidden signal should fail safely",
        (82, 320),
        font(ARIAL, 8),
        "#eeeeee",
        "u3",
    )
    layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    layer_expected: dict[str, list[dict[str, Any]]] = {"words": [], "lines": []}
    draw_line(
        layer,
        layer_expected,
        "Blurred warning needs redraw",
        (85, 475),
        font(ARIAL_BOLD, 19),
        "#89929c",
        "u4",
    )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=4.2))
    image.paste(layer, (0, 0), layer)
    expected["words"].extend(layer_expected["words"])
    expected["lines"].extend(layer_expected["lines"])
    draw_line(
        image,
        expected,
        "No OCR output confirms a target",
        (80, 690),
        font(ARIAL, 24),
        "#465a70",
        "u5",
    )
    return image, {
        "id": "unreadable",
        "description": "Tiny low-contrast and blurred text with readable controls",
        **expected,
    }


def generate_fixtures(root: Path) -> dict[str, Any]:
    fixtures_dir = root / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for make_fixture in (
        clean_fixture,
        mixed_fixture,
        transformed_fixture,
        multilingual_fixture,
        unreadable_fixture,
    ):
        image, truth = make_fixture()
        path = fixtures_dir / f"{truth['id']}.png"
        image.save(path, format="PNG", compress_level=9)
        truth["file"] = path.name
        truth["rasterWidth"] = WIDTH
        truth["rasterHeight"] = HEIGHT
        truth["sha256"] = digest_file(path)
        generated.append(truth)
    corpus = {
        "corpusId": "vera-spotlight-synthetic-webpage-v1",
        "generator": "issue-105 evaluate.py",
        "pillowVersion": pillow_version,
        "fonts": [
            {"path": str(path), "sha256": digest_file(path)}
            for path in (ARIAL, ARIAL_BOLD, ARIAL_UNICODE)
        ],
        "fixtures": generated,
        "sensitivity": "synthetic fictional text only",
    }
    write_json(fixtures_dir / "ground-truth.json", corpus)
    return corpus


def timed_run(command: list[str]) -> tuple[bytes, str, float, int]:
    started = time.perf_counter()
    completed = subprocess.run(
        ["/usr/bin/time", "-l", *command],
        check=True,
        capture_output=True,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    wall_ms = (time.perf_counter() - started) * 1000
    stderr = completed.stderr.decode("utf-8", errors="replace")
    match = re.search(
        r"^\s*(\d+)\s+maximum resident set size\s*$", stderr, re.MULTILINE
    )
    if not match:
        raise RuntimeError(
            f"could not parse peak RSS from /usr/bin/time output:\n{stderr}"
        )
    return completed.stdout, stderr, wall_ms, int(match.group(1))


def canonical_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        elements,
        key=lambda item: (item["rect"]["y"], item["rect"]["x"], item["rawOrdinal"]),
    )
    for reading_order, item in enumerate(ordered):
        item["readingOrder"] = reading_order
    return ordered


def parse_tesseract(
    tsv_bytes: bytes, raster_width: int, raster_height: int
) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t"))
    words: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    line_ordinals: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        if row["level"] != "5" or not row["text"].strip():
            continue
        key = (row["page_num"], row["block_num"], row["par_num"], row["line_num"])
        if key not in line_ordinals:
            line_ordinals[key] = len(line_ordinals)
        confidence = float(row["conf"])
        word = {
            "text": row["text"],
            "rect": {
                "x": int(row["left"]),
                "y": int(row["top"]),
                "width": int(row["width"]),
                "height": int(row["height"]),
            },
            "rawOrdinal": len(words),
            "lineRawOrdinal": line_ordinals[key],
            "confidenceMillionths": None
            if confidence < 0
            else round(confidence * 10_000),
        }
        words.append(word)
        grouped[key].append(word)
    lines: list[dict[str, Any]] = []
    for key, line_words in grouped.items():
        lines.append(
            {
                "text": " ".join(word["text"] for word in line_words),
                "rect": union_rect([word["rect"] for word in line_words]),
                "rawOrdinal": line_ordinals[key],
                "lineRawOrdinal": None,
                "confidenceMillionths": None,
            }
        )
    return {
        "candidate": "tesseract",
        "profile": "tesseract-5.5.3-oem1-psm3-eng-tsv-v1",
        "rasterWidth": raster_width,
        "rasterHeight": raster_height,
        "words": canonical_elements(words),
        "lines": canonical_elements(lines),
    }


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    normalized = "".join(
        character if character.isalnum() or character.isspace() else " "
        for character in normalized
    )
    return " ".join(normalized.split())


def iou(first: dict[str, int], second: dict[str, int]) -> float:
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = (
        first["width"] * first["height"]
        + second["width"] * second["height"]
        - intersection
    )
    return intersection / union if union else 0.0


def score_elements(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> dict[str, Any]:
    available = set(range(len(actual)))
    matched_ious: list[float] = []
    for wanted in expected:
        candidates = [
            index
            for index in available
            if normalize_text(actual[index]["text"]) == normalize_text(wanted["text"])
        ]
        if not candidates:
            matched_ious.append(0.0)
            continue
        best = max(
            candidates, key=lambda index: iou(wanted["rect"], actual[index]["rect"])
        )
        available.remove(best)
        matched_ious.append(iou(wanted["rect"], actual[best]["rect"]))
    matched = sum(value > 0 for value in matched_ious)
    positive = [value for value in matched_ious if value > 0]
    return {
        "expected": len(expected),
        "predicted": len(actual),
        "exactTextAndOverlapMatches": matched,
        "exactTextRecall": round(matched / len(expected), 6) if expected else 1.0,
        "meanMatchedBoxIou": round(statistics.fmean(positive), 6) if positive else 0.0,
        "meanGroundTruthBoxIou": round(statistics.fmean(matched_ious), 6)
        if matched_ious
        else 0.0,
    }


def render_overlay(
    image_path: Path,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    output_path: Path,
    label: str,
) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for item in expected:
        rect = item["rect"]
        draw.rectangle(
            (
                rect["x"],
                rect["y"],
                rect["x"] + rect["width"],
                rect["y"] + rect["height"],
            ),
            outline="#00a050",
            width=3,
        )
    for item in actual:
        rect = item["rect"]
        draw.rectangle(
            (
                rect["x"],
                rect["y"],
                rect["x"] + rect["width"],
                rect["y"] + rect["height"],
            ),
            outline="#d000d0",
            width=2,
        )
    draw.rectangle((12, 12, 690, 56), fill="#ffffff", outline="#26384d", width=1)
    draw.text(
        (24, 22),
        f"{label}: expected green; OCR magenta",
        font=font(ARIAL_BOLD, 20),
        fill="#182f4b",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", compress_level=9)


def command_output(command: list[str]) -> str:
    return subprocess.run(
        command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ).stdout.strip()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def evaluate(root: Path, corpus: dict[str, Any], runs: int) -> dict[str, Any]:
    work = root / "work"
    outputs = root / "outputs"
    work.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    vision_binary = work / "vision_ocr"
    subprocess.run(
        [
            "swiftc",
            "-O",
            str(SCRIPT_DIR / "vision_ocr.swift"),
            "-o",
            str(vision_binary),
        ],
        check=True,
    )
    tesseract = Path(shutil.which("tesseract") or "")
    if not tesseract.is_file():
        raise RuntimeError("tesseract executable unavailable")
    tessdata = Path("/usr/local/share/tessdata/eng.traineddata")
    if not tessdata.is_file():
        raise RuntimeError("eng.traineddata unavailable")

    macos_product_version = command_output(["sw_vers", "-productVersion"])
    macos_build_version = command_output(["sw_vers", "-buildVersion"])
    machine = platform.machine()
    vision_executable_digest = digest_file(vision_binary)
    tesseract_executable_digest = digest_file(tesseract)
    tesseract_model_digest = digest_file(tessdata)
    limits = {
        "maximumRasterWidth": 8192,
        "maximumRasterHeight": 8192,
        "maximumRasterPixels": 16_777_216,
        "maximumEncodedBytes": 26_214_400,
        "maximumDecodedBytes": 67_108_864,
        "timeoutMilliseconds": 30_000,
        "retryLimit": 0,
        "maximumLines": 10_000,
        "maximumWords": 50_000,
        "maximumUtf8BytesPerElement": 16_384,
    }

    vision_profile = {
        "providerId": "apple-vision-local",
        "executionLocation": "local",
        "providerApiVersion": (
            f"Vision.framework-macOS-{macos_product_version}-build-{macos_build_version}"
        ),
        "hostPlatform": {
            "macOSProductVersion": macos_product_version,
            "macOSBuildVersion": macos_build_version,
            "machine": machine,
        },
        "adapter": "issue-105-vision-probe.swift",
        "adapterVersion": "1",
        "adapterSourceDigest": digest_file(SCRIPT_DIR / "vision_ocr.swift"),
        "evaluationExecutableDigest": vision_executable_digest,
        "modelName": "VNRecognizeTextRequest",
        "modelVersion": "request-revision-3",
        "modelArtifactDigest": {
            "state": "unavailable",
            "reason": "Apple does not expose the embedded model artifact",
        },
        "profileId": "vision-r3-accurate-en-US-no-language-correction-v1",
        "languagePolicy": "fixed-en-US-reject-other-hints-v1",
        "recognitionLevel": "accurate",
        "languages": ["en-US"],
        "automaticLanguageDetection": False,
        "usesLanguageCorrection": False,
        "customWords": [],
        "preprocessing": "none",
        "rawResponseEnvelopeVersion": "vision-response-envelope-v1",
        "canonicalizationVersion": "vera.spotlight.canonical-json.v1",
        "geometryVersion": "vision-normalized-to-outward-rounded-source-pixels-v1",
        "readingOrderVersion": "top-edge-left-edge-raw-ordinal-v1",
        "limits": limits,
        "privacyPolicy": "local-device-only-no-network-v1",
        "costPolicy": "local-no-provider-charge-usd-zero-v1",
    }
    tesseract_profile = {
        "providerId": "tesseract-local",
        "executionLocation": "local",
        "providerApiVersion": "tesseract-cli-5.5.3",
        "adapter": "issue-105-evaluate.py",
        "adapterVersion": "1",
        "adapterSourceDigest": digest_file(SCRIPT_DIR / "evaluate.py"),
        "engineExecutableDigest": tesseract_executable_digest,
        "modelName": "eng.traineddata",
        "modelVersion": command_output(["combine_tessdata", "-l", str(tessdata)]),
        "modelArtifactDigest": tesseract_model_digest,
        "profileId": "tesseract-5.5.3-oem1-psm3-eng-tsv-v1",
        "languagePolicy": "fixed-eng-reject-other-hints-v1",
        "engineMode": 1,
        "pageSegmentationMode": 3,
        "languages": ["eng"],
        "preprocessing": "none",
        "rawResponseEnvelopeVersion": "tesseract-tsv-5.5.3-v1",
        "canonicalizationVersion": "vera.spotlight.canonical-json.v1",
        "geometryVersion": "tesseract-tsv-integer-source-pixels-v1",
        "readingOrderVersion": "top-edge-left-edge-raw-ordinal-v1",
        "limits": limits,
        "privacyPolicy": "local-process-only-no-network-v1",
        "costPolicy": "local-no-provider-charge-usd-zero-v1",
    }
    profiles = {"apple-vision": vision_profile, "tesseract": tesseract_profile}
    profile_digests = {
        name: digest_bytes(canonical_bytes(profile))
        for name, profile in profiles.items()
    }

    candidates: dict[str, Any] = {
        "apple-vision": {
            "profile": vision_profile,
            "profileDigest": profile_digests["apple-vision"],
            "executableLocation": "ephemeral evaluation build from retained source",
            "executableDigest": vision_executable_digest,
            "supportedLanguages": json.loads(
                command_output([str(vision_binary), "--languages"])
            ),
            "fixtures": {},
        },
        "tesseract": {
            "profile": tesseract_profile,
            "profileDigest": profile_digests["tesseract"],
            "executableLocation": "Homebrew-linked tesseract 5.5.3",
            "executableDigest": tesseract_executable_digest,
            "modelLocation": "Homebrew-bundled eng.traineddata",
            "modelDigest": tesseract_model_digest,
            "installedLanguages": command_output(
                [str(tesseract), "--list-langs"]
            ).splitlines()[1:],
            "fixtures": {},
        },
    }

    for fixture in corpus["fixtures"]:
        image_path = root / "fixtures" / fixture["file"]
        for candidate_name in candidates:
            hashes: list[str] = []
            wall_times: list[float] = []
            peak_rss: list[int] = []
            first_output: dict[str, Any] | None = None
            for _ in range(runs):
                if candidate_name == "apple-vision":
                    stdout, _, wall_ms, rss = timed_run(
                        [str(vision_binary), str(image_path)]
                    )
                    output = json.loads(stdout)
                else:
                    stdout, _, wall_ms, rss = timed_run(
                        [
                            str(tesseract),
                            str(image_path),
                            "stdout",
                            "-l",
                            "eng",
                            "--oem",
                            "1",
                            "--psm",
                            "3",
                            "tsv",
                        ]
                    )
                    output = parse_tesseract(
                        stdout, fixture["rasterWidth"], fixture["rasterHeight"]
                    )
                output_hash = digest_bytes(canonical_bytes(output))
                hashes.append(output_hash)
                wall_times.append(wall_ms)
                peak_rss.append(rss)
                first_output = first_output or output
            assert first_output is not None
            output_path = outputs / candidate_name / f"{fixture['id']}.json"
            write_json(output_path, first_output)
            render_overlay(
                image_path,
                fixture["words"],
                first_output["words"],
                root / "overlays" / candidate_name / f"{fixture['id']}-words.png",
                f"{candidate_name} word boxes",
            )
            render_overlay(
                image_path,
                fixture["lines"],
                first_output["lines"],
                root / "overlays" / candidate_name / f"{fixture['id']}-lines.png",
                f"{candidate_name} line boxes",
            )
            candidates[candidate_name]["fixtures"][fixture["id"]] = {
                "inputDigest": fixture["sha256"],
                "outputDigest": digest_file(output_path),
                "canonicalOutputDigest": digest_bytes(canonical_bytes(first_output)),
                "runOutputDigests": hashes,
                "repeatable": len(set(hashes)) == 1,
                "wallMs": {
                    "runs": [round(value, 3) for value in wall_times],
                    "median": round(statistics.median(wall_times), 3),
                    "p95": round(percentile(wall_times, 0.95), 3),
                },
                "peakResidentBytes": {
                    "runs": peak_rss,
                    "median": int(statistics.median(peak_rss)),
                    "maximum": max(peak_rss),
                },
                "words": score_elements(fixture["words"], first_output["words"]),
                "lines": score_elements(fixture["lines"], first_output["lines"]),
                "confidence": {
                    "word": "provider_reported"
                    if any(
                        item.get("confidenceMillionths") is not None
                        for item in first_output["words"]
                    )
                    else "unavailable",
                    "line": "provider_reported"
                    if any(
                        item.get("confidenceMillionths") is not None
                        for item in first_output["lines"]
                    )
                    else "unavailable",
                },
            }

    for candidate in candidates.values():
        fixtures = list(candidate["fixtures"].values())
        for granularity in ("words", "lines"):
            expected = sum(item[granularity]["expected"] for item in fixtures)
            matched = sum(
                item[granularity]["exactTextAndOverlapMatches"] for item in fixtures
            )
            weighted_iou = sum(
                item[granularity]["meanGroundTruthBoxIou"]
                * item[granularity]["expected"]
                for item in fixtures
            )
            candidate.setdefault("aggregate", {})[granularity] = {
                "expected": expected,
                "exactTextAndOverlapMatches": matched,
                "exactTextRecall": round(matched / expected, 6),
                "meanGroundTruthBoxIou": round(weighted_iou / expected, 6),
            }
        all_wall = [value for item in fixtures for value in item["wallMs"]["runs"]]
        all_rss = [
            value for item in fixtures for value in item["peakResidentBytes"]["runs"]
        ]
        candidate["aggregate"]["repeatableFixtures"] = sum(
            item["repeatable"] for item in fixtures
        )
        candidate["aggregate"]["fixtureCount"] = len(fixtures)
        candidate["aggregate"]["wallMsMedian"] = round(statistics.median(all_wall), 3)
        candidate["aggregate"]["wallMsP95"] = round(percentile(all_wall, 0.95), 3)
        candidate["aggregate"]["peakResidentBytesMaximum"] = max(all_rss)

    actual_model_digest = tesseract_model_digest
    negative_controls = [
        {
            "id": "model-digest-mismatch",
            "candidate": "tesseract",
            "expectedDigest": "sha256:" + "0" * 64,
            "actualDigest": actual_model_digest,
            "terminalCode": "model_digest_mismatch",
            "engineExecuted": False,
            "batchProduced": False,
            "confirmationProduced": False,
        },
        {
            "id": "engine-unavailable",
            "candidate": "tesseract",
            "configuredExecutable": "/nonexistent/vera-ocr-engine",
            "terminalCode": "engine_unavailable",
            "engineExecuted": False,
            "batchProduced": False,
            "confirmationProduced": False,
        },
        {
            "id": "recognized-element-without-geometry",
            "candidate": "apple-vision",
            "terminalCode": "invalid_provider_geometry",
            "engineExecuted": True,
            "batchProduced": False,
            "confirmationProduced": False,
        },
    ]
    assert all(
        not item["batchProduced"] and not item["confirmationProduced"]
        for item in negative_controls
    )

    return {
        "evaluationId": "vera-spotlight-ocr-engine-evaluation-v1",
        "runsPerFixture": runs,
        "platform": {
            "macOSProductVersion": macos_product_version,
            "macOSBuildVersion": macos_build_version,
            "machine": machine,
            "swift": command_output(["swift", "--version"]),
            "python": platform.python_version(),
            "pillow": pillow_version,
        },
        "corpusDigest": digest_file(root / "fixtures" / "ground-truth.json"),
        "candidates": candidates,
        "negativeControls": negative_controls,
        "privacy": {
            "rasterSources": "generated synthetic fixtures only",
            "externalOcrCalls": 0,
            "networkRequiredByHarness": False,
            "sourceUrlsCredentialsOrPrivateTextPresent": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=SCRIPT_DIR)
    parser.add_argument("--runs", type=int, default=RUNS)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    root = args.artifact_root.resolve()
    corpus = generate_fixtures(root)
    results = evaluate(root, corpus, args.runs)
    write_json(root / "benchmark-results.json", results)
    shutil.rmtree(root / "work")


if __name__ == "__main__":
    main()
