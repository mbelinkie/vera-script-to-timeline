"""Prepare small, probe-only #326 compiler/package inputs for native music tests."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import uuid
import wave
from array import array
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import opentimelineio as otio  # type: ignore[import-untyped]
from vera_timeline_agent.narration.models import canonical_json_bytes
from vera_timeline_agent.v2_package import (
    BUILD_DIRECTORY,
    OTIO_FILENAME,
    _compiler_hash,
    _render_slate,
    build_v2_package,
    verify_v2_package,
)

Json = dict[str, Any]
ROOT = Path(__file__).resolve().parents[1]
NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
COMPILER_CLI = ROOT / "packages/contracts/src/issue-190-compile-cli.ts"
ROW_EDIT_MODULE = ROOT / "packages/contracts/src/authoring-v2-rows.ts"
INPUT_TEMPLATE = ROOT / (
    "tests/data/authoring_v2/issue_173/compiler/"
    "narrated-image-still-holds.input.golden.json"
)
FRAME_RATE = 24
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FRAME_RATE
MUSIC_SEGMENT_SAMPLES = SAMPLE_RATE // 2
MUSIC_FREQUENCIES = tuple(620 + 40 * index for index in range(24))
NARRATION_FREQUENCIES = {"A": 220, "B": 277, "C": 330, "D": 392, "E": 440}
LABEL_TEXT = {"A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta", "E": "Echo"}
FADE_FRAMES = 6
MUSIC_SOURCE_TRIM_SAMPLES = SAMPLE_RATE
MAX_ARTIFACT_BYTES = 20 * 1024 * 1024

CASE_IDS = (
    "word-end-b",
    "duration-end-b",
    "neighbor-duration-change",
    "intact-reorder",
    "abc-ed-first-interruption",
    "issue125-ending-row-moved",
)

_ROW_EDIT_RUNNER = r"""
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
const moduleUrl = new URL(__MODULE_URL__);
const directory = new URL("./", moduleUrl).href;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    const mapped = context.parentURL?.startsWith(directory)
      && specifier.startsWith("./")
      && specifier.endsWith(".js")
      ? specifier.slice(0, -3) + ".ts"
      : specifier;
    return nextResolve(mapped, context);
  },
});
const api = await import(moduleUrl.href);
hooks.deregister();
const input = JSON.parse(readFileSync(0, "utf8"));
const result = api.applyRowEditV2(input.document, input.revision, input.command);
process.stdout.write(JSON.stringify(result));
"""


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#326-music-probe:v1:{label}"))


def _write_json(path: Path, value: object) -> bytes:
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(raw)
    return raw


def _write_pcm_wav(path: Path, segments: list[tuple[int, int]], peak: float) -> None:
    samples = array("h")
    for frequency, count in segments:
        samples.extend(
            int(32767 * peak * math.sin(2 * math.pi * frequency * offset / SAMPLE_RATE))
            for offset in range(count)
        )
    if sys.byteorder != "little":
        samples.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())


def _music_pcm(path: Path) -> None:
    _write_pcm_wav(
        path,
        [(frequency, MUSIC_SEGMENT_SAMPLES) for frequency in MUSIC_FREQUENCIES],
        0.4,
    )


def _require_pinned_node() -> None:
    if not NODE.is_file() or NODE.is_symlink() or not COMPILER_CLI.is_file():
        raise ValueError("pinned Node 24.19.0 compiler runtime is unavailable")
    result = subprocess.run(
        [str(NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(NODE.parent)},
    )
    if result.returncode != 0 or result.stdout.strip() != b"v24.19.0" or result.stderr:
        raise ValueError("pinned Node 24.19.0 runtime check failed")


def _refresh_bindings(document: Json, dependencies: Json) -> None:
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    text_hash = _sha256(
        "\n".join(
            block["text"]
            for block in document["activeDraft"]["blocks"]
            if block["type"] == "narration"
        ).encode("utf-8")
    )
    dependencies["document"].update(
        {
            "documentId": document["id"],
            "projectId": document["projectId"],
            "liveHeadSequence": document["liveHeadSequence"],
            "contentHash": document["liveContentHash"],
            "textHash": text_hash,
            "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
        }
    )


def _row_audio(
    case_id: str,
    label: str,
    row_id: str,
    text: str,
    audio_path: Path,
    duration_frames: int,
) -> Json:
    token_id = _id(f"{case_id}:{label}:token")
    sequence_id = _id(f"{case_id}:{label}:sequence")
    slot_id = _id(f"{case_id}:{label}:slot")
    payload_id = _id(f"{case_id}:{label}:placeholder")
    narration_asset_id = _id(f"{case_id}:{label}:narration-asset")
    audible_end = (
        {"numerator": 3, "denominator": 2}
        if label == "B"
        else {
            "numerator": 1,
            "denominator": 2,
        }
    )
    audio_hash = _hash_file(audio_path)
    text_hash = _sha256(text.encode("utf-8"))
    timing_content = {
        "blockId": row_id,
        "blockRevision": 1,
        "textHash": text_hash,
        "tokenId": token_id,
        "audioHash": audio_hash,
        "durationFrames": duration_frames,
    }
    timing_hash = _sha256(canonical_json_bytes(timing_content))
    row = {
        "type": "narration",
        "id": row_id,
        "orderKey": f"{label}-1",
        "text": text,
        "tokens": [
            {
                "id": token_id,
                "value": text,
                "startOffset": 0,
                "endOffset": len(text),
            }
        ],
        "primaryVisualSequence": {
            "id": sequence_id,
            "version": 1,
            "slots": [
                {
                    "id": slot_id,
                    "kind": "content",
                    "relation": {"kind": "base"},
                    "boundaryBefore": {"kind": "row_start"},
                    "payload": {
                        "kind": "visual",
                        "payloadId": payload_id,
                        "pictureKind": "intentional_placeholder",
                        "source": {
                            "kind": "intentional_placeholder",
                            "text": f"{label} picture",
                        },
                        "sourceUsage": None,
                        "audioPolicy": "mute",
                        "framingPolicy": "contain",
                    },
                    "playoutPolicy": "match_structural_interval",
                    "version": 1,
                }
            ],
        },
        "overlayEvents": [],
        "timingPolicy": "narration_spine",
        "state": "active",
        "notes": [],
        "version": 1,
    }
    timing_map = {
        "blockId": row_id,
        "blockRevision": 1,
        "textHash": text_hash,
        "tokenizationVersion": "script-document/v2-frozen-tokens",
        "narrationAssetId": narration_asset_id,
        "audioHash": audio_hash,
        "timingHash": timing_hash,
        "alignmentVersion": "issue326-synthetic-tone/v1",
        "precision": "audible_word_marks",
        "tokens": [
            {
                "tokenId": token_id,
                "startOffset": 0,
                "endOffset": len(text),
                "quotedText": text,
                "startTime": {"numerator": 0, "denominator": 1},
                "audibleEnd": audible_end,
                "endBasis": "evidenced_audible_end",
            }
        ],
        "audio": {
            "narrationAssetId": narration_asset_id,
            "audioHash": audio_hash,
            "timingHash": timing_hash,
            "cacheAssetId": hashlib.sha256(
                f"{case_id}:{label}:cache".encode()
            ).hexdigest(),
            "locator": f"synthetic/{case_id}/narration-{label}.wav",
            "durationSamples": duration_frames * SAMPLES_PER_FRAME,
            "sampleRate": SAMPLE_RATE,
            "channels": 1,
        },
    }
    return {"row": row, "timing": timing_map, "assetId": narration_asset_id}


def _case_spec(
    case_id: str,
) -> tuple[list[str], str, str, str, dict[str, int], Json | None]:
    labels = list("ABCDE")
    durations = {label: 48 for label in labels}
    if case_id == "word-end-b":
        return labels, "A", "B", "word_end", durations, None
    if case_id == "duration-end-b":
        return labels, "A", "B", "row_duration", durations, None
    if case_id == "neighbor-duration-change":
        durations["A"] = 72
        return labels, "A", "B", "row_duration", durations, None
    if case_id == "intact-reorder":
        command = {
            "kind": "move_rows",
            "rowIds": [_id(f"{case_id}:A:row"), _id(f"{case_id}:B:row")],
            "destination": {
                "sectionId": None,
                "afterRowId": _id(f"{case_id}:C:row"),
                "beforeRowId": _id(f"{case_id}:D:row"),
            },
        }
        return labels, "A", "B", "row_duration", durations, command
    if case_id == "abc-ed-first-interruption":
        command = {
            "kind": "move_rows",
            "rowIds": [_id(f"{case_id}:E:row")],
            "destination": {
                "sectionId": None,
                "afterRowId": _id(f"{case_id}:C:row"),
                "beforeRowId": _id(f"{case_id}:D:row"),
            },
        }
        return labels, "A", "E", "first_interruption", durations, command
    if case_id == "issue125-ending-row-moved":
        labels = [
            "starting-row",
            "chalk-crescent",
            "paper-signal-frame",
            "unrelated-one",
            "unrelated-two",
        ]
        durations = {label: 48 for label in labels}
        command = {
            "kind": "move_rows",
            "rowIds": [_id(f"{case_id}:paper-signal-frame:row")],
            "destination": {
                "sectionId": None,
                "afterRowId": _id(f"{case_id}:unrelated-two:row"),
                "beforeRowId": None,
            },
        }
        return labels, labels[0], labels[2], "first_interruption", durations, command
    raise ValueError(f"unsupported issue #326 probe case: {case_id}")


def _make_inputs(
    case_dir: Path,
    case_id: str,
    labels: list[str],
    start_label: str,
    end_label: str,
    endpoint_mode: str,
    durations: dict[str, int],
    music_path: Path,
) -> tuple[Json, Json, dict[str, Json], dict[str, Path]]:
    template = json.loads(INPUT_TEMPLATE.read_bytes())
    document = copy.deepcopy(template["document"])
    dependencies = copy.deepcopy(template["dependencies"])
    document_id = _id(f"{case_id}:document")
    project_id = _id(f"{case_id}:project")
    document.update(
        {
            "id": document_id,
            "projectId": project_id,
            "title": f"Issue #326 synthetic {case_id}",
            "activeDraft": {"blocks": [], "supportingItems": []},
            "ideaOutline": [],
            "extras": [],
            "liveHeadSequence": 0,
            "liveStateVector": "",
        }
    )
    row_ids: dict[str, str] = {}
    rows: list[Json] = []
    timing_maps: list[Json] = []
    narration_audio: dict[str, Json] = {}
    media_paths: dict[str, Path] = {}
    fallback_frequencies = (220, 277, 330, 392, 440)
    for label_index, label in enumerate(labels):
        row_id = _id(f"{case_id}:{label}:row")
        row_ids[label] = row_id
        text = LABEL_TEXT.get(label, label.replace("-", " ").title())
        audio_path = case_dir / "media" / f"narration-{label}.wav"
        _write_pcm_wav(
            audio_path,
            [
                (
                    NARRATION_FREQUENCIES.get(label, fallback_frequencies[label_index]),
                    durations[label] * SAMPLES_PER_FRAME,
                )
            ],
            0.12,
        )
        row_info = _row_audio(
            case_id,
            label,
            row_id,
            text,
            audio_path,
            durations[label],
        )
        rows.append(row_info["row"])
        timing_maps.append(row_info["timing"])
        narration_audio[row_info["assetId"]] = {
            "path": audio_path.resolve(),
            "sha256": _hash_file(audio_path),
            "frequencyHz": NARRATION_FREQUENCIES.get(
                label, fallback_frequencies[label_index]
            ),
            "label": label,
            "rowId": row_id,
        }
        media_paths[f"source:{row_info['assetId']}"] = audio_path.resolve()

    settings = {
        "endpointMode": endpoint_mode,
        "gainDb": -12,
        "sourceTrimStartSamples": MUSIC_SOURCE_TRIM_SAMPLES,
        "fadeCurve": "linear",
        "fadeInFrames": FADE_FRAMES,
        "fadeOutFrames": FADE_FRAMES,
    }
    span = {
        "id": _id(f"{case_id}:span"),
        "startRowId": row_ids[start_label],
        "endRowId": row_ids[end_label],
        "source": {
            "mediaReferenceId": _id("shared:music-media-reference"),
            "artifactId": _id("shared:music-artifact"),
            "artifactVersion": 1,
            "contentHash": _hash_file(music_path),
        },
        "settings": settings,
    }
    document["activeDraft"]["blocks"] = rows
    document["rowAudioSpans"] = [span]
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )

    dependencies["build"].update(
        {
            "buildId": _id(f"{case_id}:build"),
            "manifestId": _id(f"{case_id}:manifest"),
            "reportId": _id(f"{case_id}:report"),
            "buildClass": "preview",
        }
    )
    dependencies["timeline"].update(
        {
            "frameRate": {"numerator": FRAME_RATE, "denominator": 1},
            "audioSampleRate": SAMPLE_RATE,
            "startFrame": 0,
            "durationFrames": sum(durations.values()),
        }
    )
    dependencies["narrationTimingMaps"] = timing_maps
    dependencies.pop("narrationBoundaryEvidence", None)
    dependencies["occurrenceResolutions"] = []
    dependencies["preparedMedia"] = []
    _refresh_bindings(document, dependencies)
    full_document_path = case_dir / "authoring" / "script-document-v2.json"
    full_dependencies_path = case_dir / "authoring" / "compiler-dependencies-v2.json"
    _write_json(full_document_path, document)
    _write_json(full_dependencies_path, dependencies)
    return document, dependencies, narration_audio, media_paths


def _apply_row_edit(document: Json, command: Json) -> Json:
    module_url = ROW_EDIT_MODULE.resolve().as_uri()
    runner = _ROW_EDIT_RUNNER.replace("__MODULE_URL__", json.dumps(module_url))
    result = subprocess.run(
        [str(NODE), "--input-type=module", "-e", runner],
        input=json.dumps(
            {
                "document": document,
                "revision": document.get("rowEditRevision", 0),
                "command": command,
            }
        ).encode("utf-8"),
        capture_output=True,
        timeout=20,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(NODE.parent)},
    )
    if result.returncode != 0 or result.stderr:
        detail = result.stderr.decode("utf-8", errors="replace")
        raise ValueError(f"applyRowEditV2 failed in pinned Node: {detail}")
    outcome = json.loads(result.stdout)
    if outcome.get("ok") is not True:
        raise ValueError(
            f"applyRowEditV2 refused the probe move: {outcome.get('diagnostics')}"
        )
    return outcome["document"]


def _run_compiler(
    document_path: Path, dependencies_path: Path
) -> tuple[Json, Json, bytes, bytes]:
    result = subprocess.run(
        [str(NODE), str(COMPILER_CLI), str(document_path), str(dependencies_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(NODE.parent)},
    )
    if result.returncode != 0 or result.stderr:
        raise ValueError(
            "pinned TypeScript compiler refused the probe copy: "
            + result.stderr.decode("utf-8", errors="replace")
        )
    envelope = json.loads(result.stdout)
    compiled = envelope.get("result")
    if not isinstance(compiled, dict) or compiled.get("ok") is not True:
        raise ValueError("pinned compiler did not return an accepted probe build")
    manifest_raw = compiled["manifestJson"].encode("utf-8")
    report_raw = compiled["reportJson"].encode("utf-8")
    manifest_path = document_path.parent / "timeline-manifest-v2.json"
    report_path = document_path.parent / "build-report-v2.json"
    manifest_path.write_bytes(manifest_raw)
    report_path.write_bytes(report_raw)
    return compiled["manifest"], compiled["report"], manifest_raw, report_raw


def _assert_production_guard(document_path: Path, dependencies_path: Path) -> None:
    result = subprocess.run(
        [str(NODE), str(COMPILER_CLI), str(document_path), str(dependencies_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(NODE.parent)},
    )
    if b"ROW_AUDIO_RUNTIME_UNAVAILABLE" not in result.stdout or result.returncode == 0:
        raise ValueError(
            "production compiler did not retain its active music-span refusal"
        )


def _music_endpoint(
    endpoint_mode: str,
    span: Json,
    row_ranges: dict[str, tuple[int, int]],
    row_id_by_label: dict[str, str],
    dependencies: Json,
    manifest: Json,
) -> tuple[int, int, int, Json]:
    start_frame = row_ranges[span["startRowId"]][0]
    end_row_start, end_frame = row_ranges[span["endRowId"]]
    endpoint: Json = {
        "kind": endpoint_mode,
        "rowId": span["endRowId"],
        "recordFrame": end_frame,
    }
    if endpoint_mode == "word_end":
        row = next(
            block
            for block in manifest["events"]
            if block["kind"] == "narration"
            and block["provenance"]["blockId"] == span["endRowId"]
        )
        if span["endRowId"] != row_id_by_label["B"]:
            raise ValueError("word-end fixture must end on row B")
        timing_map = next(
            item
            for item in dependencies["narrationTimingMaps"]
            if item["blockId"] == span["endRowId"]
        )
        token = timing_map["tokens"][0]
        audible_end = token.get("audibleEnd")
        if token.get("endBasis") != "evidenced_audible_end" or not audible_end:
            raise ValueError("word-end fixture lacks an evidenced audible endpoint")
        duration = row["recordRange"]["endFrame"] - row["recordRange"]["startFrame"]
        word_frames = (
            audible_end["numerator"] * FRAME_RATE // audible_end["denominator"]
        )
        if word_frames >= duration:
            raise ValueError("word-end anchor must be inside its narration row")
        end_frame = row["recordRange"]["startFrame"] + word_frames
        endpoint = {
            "kind": "word_end",
            "rowId": span["endRowId"],
            "tokenId": token["tokenId"],
            "audibleEnd": audible_end,
            "recordFrame": end_frame,
        }
    elif end_row_start >= end_frame:
        raise ValueError("span end row has invalid compiled geometry")
    duration_frames = end_frame - start_frame
    if duration_frames <= 0:
        raise ValueError("music event duration must be positive")
    endpoint["recordFrame"] = end_frame
    return start_frame, end_frame, duration_frames, endpoint


def _absolute_package_references(
    timeline: otio.schema.Timeline, package_otio: Path
) -> None:
    package_root = package_otio.parents[2]
    for clip in timeline.find_children(otio.schema.Clip):
        reference = clip.media_reference
        if not isinstance(reference, otio.schema.ExternalReference):
            continue
        target_url = reference.target_url
        parsed = urlparse(target_url)
        if parsed.scheme == "file":
            local_path = Path(unquote(parsed.path))
        elif parsed.scheme:
            continue
        else:
            local_path = package_root / target_url
        if local_path.exists():
            reference.target_url = local_path.resolve().as_uri()


def _append_music_track(
    base_otio: Path,
    output_path: Path,
    case_id: str,
    span: Json,
    event_id: str,
    music_path: Path,
    music_hash: str,
    record_start: int,
    record_end: int,
    duration_frames: int,
    source_start: int,
    source_end: int,
) -> None:
    timeline = otio.adapters.read_from_file(str(base_otio))
    _absolute_package_references(timeline, base_otio)
    track = otio.schema.Track(name="Music", kind=otio.schema.TrackKind.Audio)
    metadata = {
        "schemaVersion": "issue326-music-probe/v1",
        "caseId": case_id,
        "spanId": span["id"],
        "eventId": event_id,
        "kind": "music",
        "trackIndex": 2,
        "sourcePath": str(music_path.resolve()),
        "sourceInFrame": source_start // SAMPLES_PER_FRAME,
        "recordStartFrame": record_start,
        "recordEndFrame": record_end,
        "durationFrames": duration_frames,
        "gainDb": -12,
        "fadeCurve": "linear",
        "fadeInFrames": FADE_FRAMES,
        "fadeOutFrames": FADE_FRAMES,
        "sourceRangeSamples": {"startSample": source_start, "endSample": source_end},
        "sourceSha256": music_hash,
    }
    track.metadata["vera_issue326"] = copy.deepcopy(metadata)
    if record_start:
        track.append(
            otio.schema.Gap(
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(0, FRAME_RATE),
                    otio.opentime.RationalTime(record_start, FRAME_RATE),
                )
            )
        )
    available = otio.opentime.TimeRange(
        otio.opentime.RationalTime(0, SAMPLE_RATE),
        otio.opentime.RationalTime(SAMPLE_RATE * 12, SAMPLE_RATE),
    )
    reference = otio.schema.ExternalReference(
        target_url=music_path.resolve().as_uri(),
        available_range=available,
    )
    clip = otio.schema.Clip(
        name=f"Issue #326 music {case_id}",
        media_reference=reference,
        source_range=otio.opentime.TimeRange(
            otio.opentime.RationalTime(source_start, SAMPLE_RATE),
            otio.opentime.RationalTime(source_end - source_start, SAMPLE_RATE),
        ),
    )
    clip.metadata["vera_issue326"] = copy.deepcopy(metadata)
    track.append(clip)
    timeline.tracks.append(track)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(output_path))


def _generated_bytes(root: Path) -> int:
    total = sum(
        path.stat().st_size for path in (root / "shared").rglob("*") if path.is_file()
    )
    cases = root / "cases"
    if cases.exists():
        for case_dir in cases.iterdir():
            if case_dir.is_dir() and case_dir.name not in {"native", "renders"}:
                for path in case_dir.rglob("*"):
                    if (
                        path.is_file()
                        and "native" not in path.parts
                        and "renders" not in path.parts
                    ):
                        total += path.stat().st_size
    return total


def prepare_case(root: Path, case_id: str, music_path: Path) -> Path:
    if case_id not in CASE_IDS:
        raise ValueError(f"unsupported issue #326 probe case: {case_id}")
    case_dir = root / "cases" / case_id
    if case_dir.exists() or case_dir.is_symlink():
        raise ValueError(f"probe case output already exists: {case_dir}")
    case_dir.mkdir(parents=True)
    labels, start_label, original_end_label, endpoint_mode, durations, command = (
        _case_spec(case_id)
    )
    document, dependencies, narration_assets, media_paths = _make_inputs(
        case_dir,
        case_id,
        labels,
        start_label,
        original_end_label,
        endpoint_mode,
        durations,
        music_path,
    )
    original_document = copy.deepcopy(document)
    original_raw = (case_dir / "authoring" / "script-document-v2.json").read_bytes()
    original_spans = copy.deepcopy(document["rowAudioSpans"])
    if command:
        document = _apply_row_edit(document, command)
        _refresh_bindings(document, dependencies)
    effective_path = case_dir / "authoring" / "effective-script-document-v2.json"
    effective_raw = _write_json(effective_path, document)
    effective_spans = copy.deepcopy(document["rowAudioSpans"])
    if (
        command
        and case_id == "intact-reorder"
        and (
            effective_spans != original_spans
            or document.get("rowAudioSpans", [{}])[0].get("review")
        )
    ):
        raise ValueError("intact group move changed or reviewed its span intent")
    if case_id in {"abc-ed-first-interruption", "issue125-ending-row-moved"}:
        changed = effective_spans[0]
        if changed.get("review", {}).get("alert") != "Music shortened by this move":
            raise ValueError(
                "first-interruption move did not produce the adopted review alert"
            )
        if (
            changed.get("review", {}).get("previousEndRowId")
            != original_spans[0]["endRowId"]
        ):
            raise ValueError(
                "first-interruption move did not preserve its prior endpoint"
            )
        if (
            changed.get("review", {}).get("previousSettings")
            != original_spans[0]["settings"]
        ):
            raise ValueError(
                "first-interruption move did not preserve prior music settings"
            )

    original_snapshot_path = case_dir / "authoring" / "original-script-document-v2.json"
    if not original_snapshot_path.exists():
        _write_json(original_snapshot_path, original_document)
    full_document_path = case_dir / "authoring" / "effective-script-document-v2.json"
    full_dependencies = copy.deepcopy(dependencies)
    full_dependencies_path = (
        case_dir / "authoring" / "effective-compiler-dependencies-v2.json"
    )
    _write_json(full_dependencies_path, full_dependencies)
    _assert_production_guard(full_document_path, full_dependencies_path)

    probe_document = copy.deepcopy(document)
    probe_document.pop("rowAudioSpans", None)
    _refresh_bindings(probe_document, dependencies)
    compiler_dir = case_dir / "compile-input"
    compiler_document_path = compiler_dir / "script-document-v2.json"
    compiler_dependencies_path = compiler_dir / "compiler-dependencies-v2.json"
    _write_json(compiler_document_path, probe_document)
    _write_json(compiler_dependencies_path, dependencies)
    manifest, report, manifest_raw, _report_raw = _run_compiler(
        compiler_document_path,
        compiler_dependencies_path,
    )
    if report.get("status") != "ready" or report.get("diagnostics") != []:
        raise ValueError("probe-only compiler output is not clean and ready")
    events = manifest["events"]
    narration_events = [event for event in events if event["kind"] == "narration"]
    visual_events = [event for event in events if event["kind"] == "placeholder"]
    if len(narration_events) != 5 or len(visual_events) != 5:
        raise ValueError(
            "compiler did not emit five narration and five PNG placeholder events"
        )
    for event in visual_events:
        text = event["pictureTreatment"]["text"]
        png = _render_slate(
            text, manifest["timeline"]["width"], manifest["timeline"]["height"]
        )
        png_path = case_dir / "media" / f"visual-{event['provenance']['blockId']}.png"
        png_path.write_bytes(png)
        media_paths[f"event:{event['eventId']}"] = png_path.resolve()
    manifest_path = compiler_document_path.parent / "timeline-manifest-v2.json"
    report_path = compiler_document_path.parent / "build-report-v2.json"
    package_root = case_dir / "package"
    build = build_v2_package(
        manifest_path,
        report_path,
        compiler_document_path,
        compiler_dependencies_path,
        package_root,
        media_paths=media_paths,
        preparation_paths={},
    )
    verification = verify_v2_package(package_root)
    if verification.build_id != build.build_id:
        raise ValueError("ordinary package verification returned a different build")
    build_root = package_root / BUILD_DIRECTORY / build.build_id
    base_otio = build_root / OTIO_FILENAME
    package_receipt = json.loads(
        (build_root / "package-verification.json").read_bytes()
    )
    if package_receipt.get("status") != "ready_to_import":
        raise ValueError("ordinary v2 package is not ready to import")

    block_to_ranges = {
        event["provenance"]["blockId"]: (
            event["recordRange"]["startFrame"],
            event["recordRange"]["endFrame"],
        )
        for event in narration_events
    }
    row_id_by_label = {label: _id(f"{case_id}:{label}:row") for label in labels}
    row_ranges = {
        row_id: block_to_ranges[row_id] for row_id in row_id_by_label.values()
    }
    span = effective_spans[0]
    record_start, record_end, duration_frames, endpoint_evidence = _music_endpoint(
        endpoint_mode,
        span,
        row_ranges,
        row_id_by_label,
        dependencies,
        manifest,
    )
    source_start = MUSIC_SOURCE_TRIM_SAMPLES
    source_end = source_start + duration_frames * SAMPLES_PER_FRAME
    source_total_samples = SAMPLE_RATE * 12
    if source_end > source_total_samples:
        raise ValueError("music source trim exceeds generated source bounds")
    music_hash = _hash_file(music_path)
    derived_otio = case_dir / "derived-music.otio"
    music_event_id = _id(f"{case_id}:music-event")
    _append_music_track(
        base_otio,
        derived_otio,
        case_id,
        span,
        music_event_id,
        music_path,
        music_hash,
        record_start,
        record_end,
        duration_frames,
        source_start,
        source_end,
    )

    track_by_id = {track["id"]: track for track in dependencies["tracks"]}
    packaged_events: list[Json] = []
    row_summaries: list[Json] = []
    for event in events:
        provenance = event["provenance"]
        source_id = provenance.get("sourceId")
        if event["kind"] == "narration":
            source_path = package_root / "Media" / "Narration" / f"{source_id}.wav"
            source_hash = _hash_file(source_path)
            source_in_frame = (event.get("sourceRange") or {}).get("startFrame", 0)
        elif event["kind"] == "placeholder":
            source_path = (
                package_root / "Media" / "Resolved" / f"{event['eventId']}.png"
            )
            source_hash = _hash_file(source_path)
            source_in_frame = 0
        else:
            raise ValueError(
                f"unexpected compiler event in music probe: {event['kind']}"
            )
        track = track_by_id[event["trackId"]]
        packaged_events.append(
            {
                "eventId": event["eventId"],
                "kind": event["kind"],
                "trackKind": track["kind"],
                "trackIndex": track["index"],
                "sourcePath": str(source_path.resolve()),
                "sourceSha256": source_hash,
                "sourceInFrame": source_in_frame,
                "recordStartFrame": event["recordRange"]["startFrame"],
                "durationFrames": event["recordRange"]["endFrame"]
                - event["recordRange"]["startFrame"],
            }
        )
    for label in labels:
        row_id = row_id_by_label[label]
        event = next(
            event
            for event in narration_events
            if event["provenance"]["blockId"] == row_id
        )
        asset = narration_assets[event["provenance"]["sourceId"]]
        narration_source = (
            package_root
            / "Media"
            / "Narration"
            / f"{event['provenance']['sourceId']}.wav"
        )
        visual_event = next(
            event for event in visual_events if event["provenance"]["blockId"] == row_id
        )
        visual_source = (
            package_root / "Media" / "Resolved" / f"{visual_event['eventId']}.png"
        ).resolve()
        row_summaries.append(
            {
                "label": label,
                "rowId": row_id,
                "recordStartFrame": event["recordRange"]["startFrame"],
                "durationFrames": event["recordRange"]["endFrame"]
                - event["recordRange"]["startFrame"],
                "narrationEventId": event["eventId"],
                "narrationSourcePath": str(narration_source.resolve()),
                "narrationSourceSha256": _hash_file(narration_source),
                "narrationFrequencyHz": asset["frequencyHz"],
                "visualEventId": visual_event["eventId"],
                "visualSourcePath": str(visual_source),
                "visualSourceSha256": _hash_file(visual_source),
            }
        )
    music_event_id = _id(f"{case_id}:music-event")
    packaged_events.append(
        {
            "eventId": music_event_id,
            "kind": "music",
            "trackKind": "audio",
            "trackIndex": 2,
            "sourcePath": str(music_path.resolve()),
            "sourceSha256": music_hash,
            "sourceInFrame": source_start // SAMPLES_PER_FRAME,
            "recordStartFrame": record_start,
            "durationFrames": duration_frames,
        }
    )

    original_path = original_snapshot_path.resolve()
    sidecar = {
        "schemaVersion": "issue326-music-probe/v1",
        "evidenceLevel": "probe_only",
        "caseId": case_id,
        "sampleRate": SAMPLE_RATE,
        "authoringSnapshot": {
            "path": str(original_path),
            "rawSha256": _sha256(original_raw),
            "liveContentHash": original_document["liveContentHash"],
            "rowAudioSpans": original_spans,
        },
        "effectiveAuthoringSnapshot": {
            "path": str(effective_path.resolve()),
            "rawSha256": _sha256(effective_raw),
            "liveContentHash": document["liveContentHash"],
            "rowAudioSpans": effective_spans,
            "rowOrder": [block["id"] for block in document["activeDraft"]["blocks"]],
        },
        "base": {
            "documentContentHash": probe_document["liveContentHash"],
            "buildId": build.build_id,
            "packageRoot": str(package_root.resolve()),
            "productionCompilerRefusal": {
                "code": "ROW_AUDIO_RUNTIME_UNAVAILABLE",
                "documentSha256": _hash_file(full_document_path),
                "dependenciesSha256": _hash_file(full_dependencies_path),
            },
            "verification": package_receipt,
            "manifest": {
                "path": str(manifest_path.resolve()),
                "sha256": _sha256(manifest_raw),
            },
            "compilerInputSha256": {
                "document": _hash_file(compiler_document_path),
                "dependencies": _hash_file(compiler_dependencies_path),
            },
            "otio": {"path": str(base_otio.resolve()), "sha256": _hash_file(base_otio)},
        },
        "timeline": {
            "frameRate": {"numerator": FRAME_RATE, "denominator": 1},
            "audioSampleRate": SAMPLE_RATE,
            "rows": row_summaries,
        },
        "narration": [
            {
                "rowId": row["rowId"],
                "label": row["label"],
                "recordStartFrame": row["recordStartFrame"],
                "recordEndFrame": row["recordStartFrame"] + row["durationFrames"],
                "frequencyHz": row["narrationFrequencyHz"],
                "peakAmplitude": 0.12,
                "sourcePath": row["narrationSourcePath"],
                "sourceSha256": row["narrationSourceSha256"],
            }
            for row in row_summaries
        ],
        "music": {
            "spanId": span["id"],
            "startRowId": span["startRowId"],
            "endRowId": span["endRowId"],
            "recordStartFrame": record_start,
            "recordEndFrame": record_end,
            "durationFrames": duration_frames,
            "recordRange": {
                "startFrame": record_start,
                "endFrame": record_end,
                "durationFrames": duration_frames,
            },
            "endpointEvidence": endpoint_evidence,
            "sourceTrimSamples": source_start,
            "sourceRangeSamples": {
                "startSample": source_start,
                "endSample": source_end,
            },
            "sourcePath": str(music_path.resolve()),
            "sourceSha256": music_hash,
            "source": {
                **copy.deepcopy(span["source"]),
                "path": str(music_path.resolve()),
                "sha256": music_hash,
            },
            "segmentSamples": MUSIC_SEGMENT_SAMPLES,
            "segmentFrequenciesHz": list(MUSIC_FREQUENCIES),
            "sourcePeak": 0.4,
            "gainDb": -12,
            "fadeFrames": FADE_FRAMES,
            "fade": {
                "curve": "linear",
                "fadeInFrames": FADE_FRAMES,
                "fadeOutFrames": FADE_FRAMES,
            },
            "expectedNative": {"events": packaged_events},
        },
        "derivedOtio": {
            "path": str(derived_otio.resolve()),
            "sha256": _hash_file(derived_otio),
            "trackName": "Music",
            "trackIndex": 2,
        },
    }
    _write_json(case_dir / "music-probe.json", sidecar)
    return case_dir


def prepare_probe(root: Path, case_ids: list[str] | None = None) -> list[Path]:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("absolute probe output path required")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("probe output path must be a real directory")
    root.mkdir(parents=True, exist_ok=True)
    _require_pinned_node()
    selected = CASE_IDS if not case_ids else tuple(case_ids)
    if len(set(selected)) != len(selected) or any(
        case not in CASE_IDS for case in selected
    ):
        raise ValueError("probe case selection is invalid or duplicated")
    music_path = root / "shared" / "music.wav"
    music_path.parent.mkdir(parents=True, exist_ok=True)
    if music_path.exists():
        with wave.open(str(music_path), "rb") as source:
            valid = (
                source.getnchannels() == 1
                and source.getsampwidth() == 2
                and source.getframerate() == SAMPLE_RATE
                and source.getnframes() == SAMPLE_RATE * 12
            )
        if not valid:
            raise ValueError(
                "existing shared music fixture differs from the probe format"
            )
    else:
        _music_pcm(music_path)
    results = [
        prepare_case(root, case_id, music_path.resolve()) for case_id in selected
    ]
    if _generated_bytes(root) > MAX_ARTIFACT_BYTES:
        raise ValueError(
            "issue #326 host preparation exceeds the 20 MiB evidence limit"
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", required=True, type=Path, help="absolute, disposable output directory"
    )
    parser.add_argument(
        "--case",
        choices=CASE_IDS,
        action="append",
        help="limit preparation to selected cases",
    )
    args = parser.parse_args()
    try:
        cases = prepare_probe(args.out, args.case)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"issue #326 probe preparation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schemaVersion": "issue326-music-probe-preparation/v1",
                "evidenceLevel": "probe_only",
                "cases": [str(path / "music-probe.json") for path in cases],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
