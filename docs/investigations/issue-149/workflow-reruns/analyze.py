#!/usr/bin/env python3
"""Offline analysis for the Issue 149 Phase 10 synthetic rerun.

All input paths must be inside one generated kit.  Resolve is never imported;
the optional OTIO, subtitle, and control JSON files are treated as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn


LEGACY = Path(__file__).resolve().parents[1] / "evidence" / "scripts"
WORDS = (
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
)
WORD_RE = re.compile(r"\b(?:" + "|".join(WORDS) + r")\b", re.IGNORECASE)
STREAM_FIELDS = (
    "index",
    "codec_type",
    "codec_name",
    "pix_fmt",
    "width",
    "height",
    "r_frame_rate",
    "avg_frame_rate",
    "sample_rate",
    "channels",
    "channel_layout",
    "time_base",
    "duration",
    "nb_frames",
)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"analyze.py: {message}")


def command(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def safe_path(value: str | Path, roots: tuple[Path, ...], *, must_exist: bool = True) -> Path:
    path = Path(value).expanduser().resolve()
    if not any(path == root or root in path.parents for root in roots):
        fail(f"refusing path outside generated kit: {path}")
    if must_exist and not path.is_file():
        fail(f"missing input: {path}")
    return path


def relative(path: Path, kit: Path) -> str:
    try:
        return path.relative_to(kit).as_posix()
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assignment(value: str) -> tuple[str, str]:
    label, separator, path = value.partition("=")
    if not separator or not label or not path:
        fail(f"expected LABEL=PATH, got {value!r}")
    return label, path


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON {path}: {exc}")


def ffprobe(path: Path) -> dict[str, Any]:
    payload = json.loads(
        command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=" + ",".join(STREAM_FIELDS),
                "-of",
                "json",
                str(path),
            ]
        ).stdout
    )
    return payload


def stream_layout(path: Path) -> list[dict[str, Any]]:
    return [
        {field: stream.get(field) for field in STREAM_FIELDS}
        for stream in ffprobe(path).get("streams", [])
    ]


def fixture_summary(media: Path, manifest: dict[str, Any], kit: Path) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for name, expected in manifest.get("files", {}).items():
        path = media / name
        if not path.is_file():
            files[name] = {"expected": expected.get("sha256"), "missing": True}
            continue
        actual = sha256(path)
        files[name] = {
            "expected": expected.get("sha256"),
            "actual": actual,
            "matches_manifest": actual == expected.get("sha256"),
            "path": relative(path, kit),
        }

    base = media / "base.mov"
    relink = media / "relink_alt.mov"
    layout: dict[str, Any] = {"checked": False}
    if base.is_file() and relink.is_file():
        base_streams = stream_layout(base)
        relink_streams = stream_layout(relink)
        layout = {
            "checked": True,
            "base": base_streams,
            "relink_alt": relink_streams,
            "matches": base_streams == relink_streams,
        }
    return {
        "manifest": relative(media / "manifest.json", kit),
        "files": files,
        "stream_layout": layout,
    }


def run_audio(media: Path, source: Path) -> dict[str, Any]:
    script = LEGACY / "analyze_audio.py"
    output = command([sys.executable, str(script), str(media), str(source)]).stdout
    parsed = json.loads(output)
    return next(iter(parsed.values()))


def known_words(value: Any) -> list[str]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            found.extend(match.group(0).lower() for match in WORD_RE.finditer(node))
        elif isinstance(node, dict):
            for item in node.values():
                visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    return found


def click_analysis(manifest: Path, source: Path, speed: float) -> dict[str, Any]:
    script = LEGACY / "clicks.py"
    output = command([sys.executable, str(script), str(manifest), str(source), str(speed)]).stdout
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        match = re.search(
            r"pred\s+(-?\d+(?:\.\d+)?)\s+found\s+(\S+)\s+diff\s+(\S+)",
            line,
        )
        if not match:
            continue
        found = None if match.group(2) == "None" else int(match.group(2))
        diff = None if match.group(3) == "None" else float(match.group(3))
        rows.append(
            {
                "predicted_sample": float(match.group(1)),
                "found_sample": found,
                "diff_samples": diff,
            }
        )
    return {
        "speed_percent": speed,
        "rows": rows,
        "predicted": len(rows),
        "matched": sum(row["found_sample"] is not None for row in rows),
        "within_1_sample": bool(rows) and all(
            row["diff_samples"] is not None and abs(row["diff_samples"]) <= 1.0
            for row in rows
        ),
        "raw": output,
    }


def decode_analysis(source: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("issue149_decode_code", LEGACY / "decode_code.py")
    if spec is None or spec.loader is None:
        fail(f"cannot load {LEGACY / 'decode_code.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = [module.decode(frame) for frame in module.frames(str(source))]
    frame_mismatches = [index for index, (_, frame) in enumerate(values) if frame != index]
    return {
        "frame_count": len(values),
        "src_ids": sorted({source_id for source_id, _ in values}),
        "first": list(values[:3]),
        "frame_123": list(values[123]) if len(values) > 123 else None,
        "last": list(values[-1]) if values else None,
        "frame_mismatch_count": len(frame_mismatches),
        "frame_mismatch_examples": frame_mismatches[:10],
    }


def otio_summary(source: Path) -> dict[str, Any]:
    root = load_json(source)
    tracks = root.get("tracks", {}).get("children", [])
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for track in tracks:
        metadata = track.get("metadata", {}).get("Resolve_OTIO", {})
        clips: list[dict[str, Any]] = []
        for child in track.get("children", []):
            clip_metadata = child.get("metadata", {}).get("Resolve_OTIO", {})
            scalars = [
                effect.get("time_scalar")
                for effect in child.get("effects", [])
                if effect.get("OTIO_SCHEMA", "").startswith("LinearTimeWarp")
            ]
            clip = {
                "name": child.get("name"),
                "link_group_id": clip_metadata.get("Link Group ID"),
                "time_scalars": scalars,
            }
            clips.append(clip)
            group = clip["link_group_id"]
            if group is not None:
                groups.setdefault(str(group), []).append(
                    {
                        "track": track.get("name"),
                        "kind": track.get("kind"),
                        "name": clip["name"],
                        "time_scalars": scalars,
                    }
                )
        rows.append(
            {
                "name": track.get("name"),
                "kind": track.get("kind"),
                "metadata": metadata,
                "clips": clips,
            }
        )
    return {"tracks": rows, "linked_groups": groups}


def click_assignment(value: str) -> tuple[str, Path, float]:
    label, raw = assignment(value)
    path_text, separator, speed_text = raw.rpartition("@")
    if not separator:
        return label, Path(raw), 100.0
    try:
        speed = float(speed_text)
    except ValueError:
        return label, Path(raw), 100.0
    return label, Path(path_text), speed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-dir", required=True, help="generated kit media directory")
    parser.add_argument("--output", required=True, help="JSON output inside the generated kit")
    parser.add_argument("--audio", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--subtitle", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--control", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--otio", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--click", action="append", default=[], metavar="LABEL=PATH@SPEED")
    parser.add_argument("--decode", action="append", default=[], metavar="LABEL=PATH[@SRC_ID]")
    parser.add_argument("--same", action="append", default=[], metavar="LABEL=PATH1,PATH2")
    args = parser.parse_args()

    media = Path(args.media_dir).expanduser().resolve()
    if not media.is_dir():
        fail(f"missing media directory: {media}")
    kit = media.parent
    output = safe_path(args.output, (kit,), must_exist=False)
    manifest_path = safe_path(media / "manifest.json", (media,))
    manifest = load_json(manifest_path)
    result: dict[str, Any] = {
        "schema": "issue149-workflow-reruns-analysis-v1",
        "media_dir": relative(media, kit),
        "fixture": fixture_summary(media, manifest, kit),
        "audio": {},
        "subtitles": {},
        "word_agreement": {},
        "controls": {},
        "otio": {},
        "clicks": {},
        "decode": {},
        "comparisons": {},
    }

    for value in args.audio:
        label, raw_path = assignment(value)
        path = safe_path(raw_path, (kit,))
        record = run_audio(media, path)
        record["path"] = relative(path, kit)
        result["audio"][label] = record

    for value in args.subtitle:
        label, raw_path = assignment(value)
        path = safe_path(raw_path, (kit,))
        words = known_words(load_json(path))
        record = {"path": relative(path, kit), "words": words, "unique_words": list(dict.fromkeys(words))}
        result["subtitles"][label] = record
        if label in result["audio"]:
            rendered = set(result["audio"][label].get("present", []))
            subtitle = set(record["unique_words"])
            result["word_agreement"][label] = {
                "render_present": sorted(rendered),
                "subtitle_words": record["unique_words"],
                "missing_from_subtitles": sorted(rendered - subtitle),
                "extra_in_subtitles": sorted(subtitle - rendered),
                "agrees": rendered == subtitle,
            }

    for value in args.control:
        label, raw_path = assignment(value)
        path = safe_path(raw_path, (kit,))
        result["controls"][label] = {"path": relative(path, kit), "value": load_json(path)}

    for value in args.otio:
        label, raw_path = assignment(value)
        path = safe_path(raw_path, (kit,))
        result["otio"][label] = {"path": relative(path, kit), **otio_summary(path)}

    for value in args.click:
        label, raw_path, speed = click_assignment(value)
        path = safe_path(raw_path, (kit,))
        result["clicks"][label] = {
            "path": relative(path, kit),
            **click_analysis(media / "manifest.json", path, speed),
        }

    for value in args.decode:
        label, raw_path = assignment(value)
        expected: int | None = None
        path_text, separator, expected_text = raw_path.rpartition("@")
        if separator and expected_text.isdigit():
            raw_path, expected = path_text, int(expected_text)
        path = safe_path(raw_path, (kit,))
        record = {"path": relative(path, kit), **decode_analysis(path)}
        if expected is not None:
            record["expected_src_id"] = expected
            record["matches_expected_src_id"] = record["src_ids"] == [expected]
        result["decode"][label] = record

    for value in args.same:
        label, raw_paths = assignment(value)
        left_text, separator, right_text = raw_paths.partition(",")
        if not separator:
            fail(f"--same expects LABEL=PATH1,PATH2, got {value!r}")
        left = safe_path(left_text, (kit,))
        right = safe_path(right_text, (kit,))
        left_record = run_audio(media, left)
        right_record = run_audio(media, right)
        comparable = ("samples", "pilots", "present", "words")
        result["comparisons"][label] = {
            "left": relative(left, kit),
            "right": relative(right, kit),
            "sha256_equal": sha256(left) == sha256(right),
            "analysis_equal": all(left_record.get(key) == right_record.get(key) for key in comparable),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"output": relative(output, kit), "schema": result["schema"]}))


if __name__ == "__main__":
    main()
