#!/usr/bin/env python3
"""Small semantic gate for analyze.py output; never calls Resolve."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    raise SystemExit(f"analysis-check.py: {message}")


def assignment(value: str) -> tuple[str, str]:
    label, separator, raw = value.partition("=")
    if not separator or not label or not raw:
        fail(f"expected LABEL=VALUE, got {value!r}")
    return label, raw


def words(value: str) -> list[str]:
    return [word.strip().lower() for word in value.split(",") if word.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--expect-present", action="append", default=[], metavar="LABEL=WORD,...")
    parser.add_argument("--expect-absent", action="append", default=[], metavar="LABEL=WORD,...")
    parser.add_argument("--expect-pilot", action="append", default=[], metavar="LABEL=HZ:MIN")
    parser.add_argument("--expect-pilot-max", action="append", default=[], metavar="LABEL=HZ:MAX")
    parser.add_argument("--expect-agreement", action="append", default=[], metavar="LABEL")
    parser.add_argument("--expect-scalar", action="append", default=[], metavar="LABEL=VALUE")
    parser.add_argument("--expect-src-id", action="append", default=[], metavar="LABEL=ID")
    parser.add_argument("--expect-clicks", action="append", default=[], metavar="LABEL")
    args = parser.parse_args()

    try:
        result: dict[str, Any] = json.loads(args.analysis.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read analysis JSON: {exc}")
    if result.get("schema") != "issue149-workflow-reruns-analysis-v1":
        fail(f"unexpected schema: {result.get('schema')!r}")

    fixture = result.get("fixture", {})
    files = fixture.get("files", {})
    missing = [name for name, row in files.items() if row.get("missing")]
    mismatched = [
        name
        for name, row in files.items()
        if row.get("expected") is not None and not row.get("matches_manifest")
    ]
    if missing:
        fail(f"missing manifest media: {', '.join(missing)}")
    if mismatched:
        fail(f"manifest hash mismatch: {', '.join(mismatched)}")
    layout = fixture.get("stream_layout", {})
    if not layout.get("checked") or not layout.get("matches"):
        fail("base.mov and relink_alt.mov failed the stream-layout gate")

    audio = result.get("audio", {})
    for label, row in audio.items():
        if not isinstance(row.get("present"), list) or not isinstance(row.get("pilots"), dict):
            fail(f"audio record {label!r} lacks present/pilots fields")

    for label, row in result.get("word_agreement", {}).items():
        if not row.get("agrees"):
            fail(f"subtitle/render word disagreement for {label!r}: {row}")

    for label, row in result.get("comparisons", {}).items():
        if not row.get("analysis_equal"):
            fail(f"restore comparison differs for {label!r}: {row}")

    for label, row in result.get("decode", {}).items():
        if row.get("frame_mismatch_count"):
            fail(f"frame-code sequence mismatch for {label!r}: {row}")

    for label, required in (assignment(value) for value in args.expect_present):
        present = set(audio.get(label, {}).get("present", []))
        absent = sorted(set(words(required)) - present)
        if absent:
            fail(f"{label!r} is missing expected words: {', '.join(absent)}")

    for label, required in (assignment(value) for value in args.expect_absent):
        present = set(audio.get(label, {}).get("present", []))
        found = sorted(present & set(words(required)))
        if found:
            fail(f"{label!r} contains forbidden words: {', '.join(found)}")

    for value in args.expect_pilot:
        label, raw = assignment(value)
        hz_text, separator, minimum_text = raw.partition(":")
        if not separator:
            fail(f"--expect-pilot expects LABEL=HZ:MIN, got {value!r}")
        try:
            hz = str(int(float(hz_text)))
            minimum = float(minimum_text)
        except ValueError:
            fail(f"invalid pilot expectation: {value!r}")
        actual = float(audio.get(label, {}).get("pilots", {}).get(hz, -1.0))
        if actual < minimum:
            fail(f"{label!r} pilot {hz} Hz is {actual}, expected >= {minimum}")

    for value in args.expect_pilot_max:
        label, raw = assignment(value)
        hz_text, separator, maximum_text = raw.partition(":")
        if not separator:
            fail(f"--expect-pilot-max expects LABEL=HZ:MAX, got {value!r}")
        try:
            hz = str(int(float(hz_text)))
            maximum = float(maximum_text)
        except ValueError:
            fail(f"invalid pilot maximum expectation: {value!r}")
        actual = audio.get(label, {}).get("pilots", {}).get(hz)
        if actual is None:
            fail(f"{label!r} pilot {hz} Hz is missing")
        if float(actual) > maximum:
            fail(f"{label!r} pilot {hz} Hz is {actual}, expected <= {maximum}")

    for label in args.expect_agreement:
        if not result.get("word_agreement", {}).get(label, {}).get("agrees"):
            fail(f"word agreement not proven for {label!r}")

    for label, expected_text in (assignment(value) for value in args.expect_scalar):
        try:
            expected = float(expected_text)
        except ValueError:
            fail(f"invalid scalar expectation: {value!r}")
        found = [
            scalar
            for row in result.get("otio", {}).get(label, {}).get("tracks", [])
            for clip in row.get("clips", [])
            for scalar in clip.get("time_scalars", [])
        ]
        if not any(abs(float(scalar) - expected) < 1e-9 for scalar in found):
            fail(f"OTIO scalar {expected} not found for {label!r}: {found}")

    for label, expected_text in (assignment(value) for value in args.expect_src_id):
        try:
            expected = int(expected_text)
        except ValueError:
            fail(f"invalid src_id expectation: {value!r}")
        row = result.get("decode", {}).get(label, {})
        if row.get("src_ids") != [expected] or row.get("frame_mismatch_count"):
            fail(f"decoded source mismatch for {label!r}: {row}")

    for label in args.expect_clicks:
        row = result.get("clicks", {}).get(label, {})
        if not row.get("within_1_sample"):
            fail(f"click timing failed for {label!r}: {row}")

    print("analysis checks passed")


if __name__ == "__main__":
    main()
