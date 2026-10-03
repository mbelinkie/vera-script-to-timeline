"""Offline, generated-media-only PCM comparison for Issue 141.

This module accepts the actual retained full Matrix pair from the Issue 141
reader (`timelinePasses`, `poolPasses`, and the selected Matrix timeline).  A
complete Resolve capture can contain protected presenter metadata, which is
allowed as metadata evidence; this comparator never opens, hashes, or infers
anything from that media.  It selects only the Matrix rows whose media-pool
UID is the generated `repeated.wav` UID and binds them to the separately
supplied generated source WAV.

The pair is an evidence binding, not a claim about program audibility.  This
script compares waveform support and reports measured correlation, lag, gain,
and residual only.  It does not classify speech deletion, clip deletion, or
audibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Any


TASK_ID = "pcm-comparator"
SOURCE_SHA256 = "832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e"
SOURCE_NAME = "repeated.wav"
SAMPLE_RATE_HZ = 48_000
FRAME_RATE = 25
SAMPLES_PER_FRAME = SAMPLE_RATE_HZ // FRAME_RATE
SOURCE_SAMPLE_WIDTH = 2
RENDER_SAMPLE_WIDTH = 3
MAX_LAG_SAMPLES = 1_920
COARSE_LAG_STEP = 32
STRONG_CORRELATION = 0.80
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
REPEATED_SOURCE_UID = "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8"
KNOWN_PAIR_PATH = (
    "out/issue-141-observation-20260930-01a0f318/"
    "r2-offset-context-20261001T205629.518751Z/pair.json"
)
KNOWN_PAIR_SHA256 = "7a7d0db1be976dd4e3463e1231a7e00923318742188c0a107c8fc0962085b40d"
SUPPORT_RANGES = (
    (19_210, 36_258),
    (115_210, 132_258),
    (211_210, 228_258),
    (307_210, 324_258),
)


class ComparatorRefusal(RuntimeError):
    """Raised when the evidence binding is incomplete or outside scope."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _absolute_regular(path_value: str | Path, label: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        raise ComparatorRefusal(f"{label} must be an absolute path")
    if path.is_symlink() or not path.is_file():
        raise ComparatorRefusal(f"{label} must be a regular non-symlink file")
    return path.resolve()


def _repo_root() -> Path:
    # program-pcm-check.py is docs/investigations/issue-141/.
    return Path(__file__).resolve().parents[3]


def generated_source_path() -> Path:
    return _repo_root() / "out/issue-141-media-20260930-01a0f318/repeated.wav"


def _require_generated_source(path_value: str | Path) -> Path:
    path = _absolute_regular(path_value, "source WAV")
    expected = generated_source_path().resolve()
    if path != expected:
        raise ComparatorRefusal(
            "source WAV is outside the pinned generated repeated.wav path"
        )
    if path.name != SOURCE_NAME or _sha256(path) != SOURCE_SHA256:
        raise ComparatorRefusal("pinned generated repeated.wav hash does not match")
    return path


def _require_rendered(path_value: str | Path, *, self_check: bool = False) -> Path:
    path = _absolute_regular(path_value, "rendered WAV")
    if path.suffix.lower() != ".wav":
        raise ComparatorRefusal("rendered input must be a generated WAV")
    if not self_check:
        root = (_repo_root() / "out/issue-141-observation-20260930-01a0f318").resolve()
        if not path.is_relative_to(root):
            raise ComparatorRefusal("rendered WAV must be under the Issue 141 output root")
    return path


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ComparatorRefusal(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ComparatorRefusal(f"{label} must contain a JSON object")
    return value


def _value(record: dict[str, Any], key: str, label: str) -> Any:
    value = record.get(key)
    if not isinstance(value, dict) or "value" not in value:
        raise ComparatorRefusal(f"{label} has no retained {key} getter value")
    return value["value"]


def _matrix_timeline(state: dict[str, Any]) -> dict[str, Any]:
    timelines = state.get("timelines")
    if not isinstance(timelines, list):
        raise ComparatorRefusal("retained Matrix pair has no timeline list")
    matches = [
        timeline
        for timeline in timelines
        if isinstance(timeline, dict)
        and _value(timeline, "GetUniqueId", "Matrix timeline") == MATRIX_UID
    ]
    if len(matches) != 1:
        raise ComparatorRefusal("retained pair does not contain exactly one Matrix timeline")
    return matches[0]


def _actual_source_items(pair: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    passes = pair["timelinePasses"]
    matrix = _matrix_timeline(passes[0])
    items: list[dict[str, Any]] = []
    for track in matrix.get("tracks", []):
        if not isinstance(track, dict):
            raise ComparatorRefusal("Matrix track record is malformed")
        track_enabled = _value(track, "GetIsTrackEnabled", "Matrix track")
        for item in track.get("items", []):
            if not isinstance(item, dict):
                raise ComparatorRefusal("Matrix item record is malformed")
            media = item.get("GetMediaPoolItem")
            if not isinstance(media, dict):
                continue
            if _value(media, "GetUniqueId", "Matrix media") != REPEATED_SOURCE_UID:
                continue
            properties = _value(media, "GetClipProperty", "repeated.wav media")
            if not isinstance(properties, dict):
                raise ComparatorRefusal("repeated.wav media has no clip-property object")
            filename = properties.get("File Name") or properties.get("Clip Name")
            locator = properties.get("File Path")
            if filename != SOURCE_NAME or not isinstance(locator, str):
                raise ComparatorRefusal("repeated source identity is not pinned by metadata")
            if Path(locator).resolve() != source_path:
                raise ComparatorRefusal("repeated source metadata path differs from pinned WAV")
            source_bytes = media.get("sourceBytes")
            if not isinstance(source_bytes, dict):
                raise ComparatorRefusal("repeated source has no retained source hash metadata")
            if source_bytes.get("sha256") != SOURCE_SHA256 or source_bytes.get("hashMatches") is not True:
                raise ComparatorRefusal("repeated source metadata hash is not the pinned generated hash")
            track_type_and_index = _value(item, "GetTrackTypeAndIndex", "repeated item")
            if (
                not isinstance(track_type_and_index, list)
                or len(track_type_and_index) != 2
                or track_type_and_index[0] != "audio"
            ):
                raise ComparatorRefusal("repeated source item is not an audio track item")
            speed = _value(item, "GetSpeed", "repeated item")
            if not isinstance(speed, dict) or "Percentage" not in speed:
                raise ComparatorRefusal("repeated source item has no speed percentage")
            items.append(
                {
                    "uid": _value(item, "GetUniqueId", "repeated item"),
                    "filename": filename,
                    "trackType": track_type_and_index[0],
                    "trackIndex": track_type_and_index[1],
                    "trackEnabled": track_enabled,
                    "enabled": _value(item, "GetClipEnabled", "repeated item"),
                    "speedPercent": speed["Percentage"],
                    "recordStartFrame": _value(item, "GetStart", "repeated item"),
                    "recordEndFrame": _value(item, "GetEnd", "repeated item"),
                    "sourceStartFrame": _value(item, "GetSourceStartFrame", "repeated item"),
                    "sourceEndFrame": _value(item, "GetSourceEndFrame", "repeated item"),
                }
            )
    if not items:
        raise ComparatorRefusal("retained Matrix pair has no repeated.wav audio items")
    return items


def _load_pair(
    path_value: str | Path,
    source_path: Path,
    expected_sha256: str,
) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    path = _absolute_regular(path_value, "retained pair")
    actual_sha256 = _sha256(path)
    if expected_sha256 != actual_sha256:
        raise ComparatorRefusal("retained pair SHA-256 does not match the supplied proof binding")
    pair = _read_json(path, "retained pair")
    if pair.get("selectedTimelineUid") != MATRIX_UID:
        raise ComparatorRefusal("retained pair does not select the Matrix timeline")
    if pair.get("timelineConsistency") != "equal-adjacent-reads":
        raise ComparatorRefusal("retained timeline pair is not equal adjacent reads")
    if pair.get("poolConsistency") != "equal-adjacent-reads":
        raise ComparatorRefusal("retained pool pair is not equal adjacent reads")
    timeline_passes = pair.get("timelinePasses")
    pool_passes = pair.get("poolPasses")
    if (
        not isinstance(timeline_passes, list)
        or len(timeline_passes) != 2
        or timeline_passes[0] != timeline_passes[1]
        or not isinstance(pool_passes, list)
        or len(pool_passes) != 2
        or pool_passes[0] != pool_passes[1]
    ):
        raise ComparatorRefusal("retained pair adjacent passes are not byte-equal")
    items = _actual_source_items(pair, source_path)
    return path, pair, items


def _decode_pcm(path: Path, *, expected_width: int) -> tuple[int, int, array]:
    try:
        reader = wave.open(str(path), "rb")
    except (OSError, wave.Error) as exc:
        raise ComparatorRefusal(f"cannot open WAV {path}: {exc}") from exc
    with reader:
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        rate = reader.getframerate()
        if width != expected_width:
            raise ComparatorRefusal(
                f"{path.name} must be PCM{expected_width * 8}, got {width * 8}-bit"
            )
        if rate != SAMPLE_RATE_HZ:
            raise ComparatorRefusal(f"{path.name} must be 48 kHz, got {rate}")
        if reader.getcomptype() != "NONE":
            raise ComparatorRefusal(f"{path.name} is compressed, not PCM")
        frames = reader.getnframes()
        raw = reader.readframes(frames)
    if channels < 1:
        raise ComparatorRefusal(f"{path.name} has no channels")
    stride = channels * expected_width
    if len(raw) != frames * stride:
        raise ComparatorRefusal(f"{path.name} has truncated PCM data")
    scale = float(1 << (expected_width * 8 - 1))
    mono = array("f")
    for offset in range(0, len(raw), stride):
        total = 0.0
        for channel in range(channels):
            start = offset + channel * expected_width
            sample = int.from_bytes(raw[start : start + expected_width], "little", signed=True)
            total += sample / scale
        mono.append(total / channels)
    return channels, frames, mono


def _source_segments(source: array, item: dict[str, Any]) -> list[dict[str, int]]:
    speed = item.get("speedPercent")
    if not isinstance(speed, (int, float)) or isinstance(speed, bool):
        raise ComparatorRefusal(f"item {item.get('uid', '<unknown>')} has no numeric speed")
    if abs(float(speed) - 100.0) > 1e-9:
        raise ComparatorRefusal(
            f"item {item.get('uid', '<unknown>')} has non-100% audio speed; mapping unsupported"
        )
    if item.get("trackType") != "audio":
        return []
    if item.get("filename") != SOURCE_NAME:
        raise ComparatorRefusal("generated-only item references a non-repeated.wav source")
    try:
        source_start_frame = int(item["sourceStartFrame"])
        source_end_frame = int(item["sourceEndFrame"])
        record_start_frame = int(item["recordStartFrame"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ComparatorRefusal(f"item {item.get('uid', '<unknown>')} lacks frame bounds") from exc
    if source_start_frame < 0 or source_end_frame <= source_start_frame:
        raise ComparatorRefusal("item has invalid source frame bounds")
    if record_start_frame < 0:
        raise ComparatorRefusal("item has a negative record start")
    source_lo = source_start_frame * SAMPLES_PER_FRAME
    source_hi = source_end_frame * SAMPLES_PER_FRAME
    if source_hi > len(source):
        raise ComparatorRefusal("item source range exceeds the supplied repeated.wav")
    segments: list[dict[str, int]] = []
    for support_lo, support_hi in SUPPORT_RANGES:
        lo = max(support_lo, source_lo)
        hi = min(support_hi, source_hi)
        if hi > lo:
            record_lo = record_start_frame * SAMPLES_PER_FRAME + (lo - source_lo)
            record_hi = record_start_frame * SAMPLES_PER_FRAME + (hi - source_lo)
            segments.append(
                {
                    "sourceStartSample": lo,
                    "sourceEndSample": hi,
                    "recordStartSample": record_lo,
                    "recordEndSample": record_hi,
                }
            )
    return segments


def _correlation(
    source: array,
    rendered: array,
    source_lo: int,
    source_hi: int,
    record_lo: int,
) -> dict[str, Any]:
    length = source_hi - source_lo
    if length <= 0:
        raise ComparatorRefusal("empty support interval")
    if record_lo - MAX_LAG_SAMPLES < 0 or record_lo + length + MAX_LAG_SAMPLES > len(rendered):
        return {
            "status": "insufficient-output-window",
            "limits": {
                "maxLagSamples": MAX_LAG_SAMPLES,
                "requiredStartSample": record_lo - MAX_LAG_SAMPLES,
                "requiredEndSampleExclusive": record_lo + length + MAX_LAG_SAMPLES,
                "renderedFrameCount": len(rendered),
            },
        }

    src = source[source_lo:source_hi]
    src_energy = sum(value * value for value in src)
    if src_energy <= 0.0:
        return {"status": "zero-source-support"}

    def measure(lag: int) -> tuple[float, float, float, float]:
        out = rendered[record_lo + lag : record_lo + lag + length]
        dot = sum(left * right for left, right in zip(src, out))
        out_energy = sum(value * value for value in out)
        gain = dot / src_energy
        residual = sum((right - gain * left) ** 2 for left, right in zip(src, out))
        score = dot / math.sqrt(src_energy * out_energy) if out_energy > 0.0 else 0.0
        return score, gain, residual, out_energy

    coarse = range(-MAX_LAG_SAMPLES, MAX_LAG_SAMPLES + 1, COARSE_LAG_STEP)
    best_lag = max(coarse, key=lambda lag: (measure(lag)[0], -abs(lag)))
    refine_start = max(-MAX_LAG_SAMPLES, best_lag - COARSE_LAG_STEP + 1)
    refine_end = min(MAX_LAG_SAMPLES, best_lag + COARSE_LAG_STEP - 1)
    best_lag = max(range(refine_start, refine_end + 1), key=lambda lag: (measure(lag)[0], -abs(lag)))
    score, gain, residual, out_energy = measure(best_lag)
    return {
        "status": "strong-correlation" if score >= STRONG_CORRELATION else "weak-or-ambiguous-correlation",
        "bestLagSamples": best_lag,
        "score": score,
        "gain": gain,
        "residualEnergy": residual,
        "renderedEnergy": out_energy,
        "sampleCount": length,
        "limits": {
            "maxLagSamples": MAX_LAG_SAMPLES,
            "coarseStepSamples": COARSE_LAG_STEP,
            "strongCorrelationThreshold": STRONG_CORRELATION,
            "comparison": "normalized zero-mean-free waveform correlation; no deletion/audibility inference",
        },
    }


def compare(
    source_value: str | Path,
    rendered_value: str | Path,
    pair_value: str | Path,
    pair_sha256: str,
    *,
    item_uids: set[str] | None = None,
    _self_check: bool = False,
) -> dict[str, Any]:
    """Compare generated source support against one generated rendered WAV."""

    source_path = _require_generated_source(source_value)
    rendered_path = _require_rendered(rendered_value, self_check=_self_check)
    pair_path, pair, items = _load_pair(pair_value, source_path, pair_sha256)
    source_channels, source_frames, source = _decode_pcm(
        source_path, expected_width=SOURCE_SAMPLE_WIDTH
    )
    rendered_channels, rendered_frames, rendered = _decode_pcm(
        rendered_path, expected_width=RENDER_SAMPLE_WIDTH
    )
    if source_channels != 1:
        raise ComparatorRefusal("generated source must be mono PCM16")
    observations: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        uid = str(item.get("uid", f"item-{index}"))
        if item_uids is not None and uid not in item_uids:
            continue
        if item.get("speedPercent") != 100.0:
            observations.append(
                {
                    "uid": uid,
                    "trackIndex": item.get("trackIndex"),
                    "speedPercent": item.get("speedPercent"),
                    "enabled": item.get("enabled"),
                    "trackEnabled": item.get("trackEnabled"),
                    "status": "unsupported",
                    "reason": "non-100% audio speed; source-support mapping was not fabricated",
                }
            )
            continue
        if not item.get("enabled") or not item.get("trackEnabled"):
            observations.append(
                {
                    "uid": uid,
                    "trackIndex": item.get("trackIndex"),
                    "speedPercent": item.get("speedPercent"),
                    "enabled": item.get("enabled"),
                    "trackEnabled": item.get("trackEnabled"),
                    "status": "disabled-no-expected-audibility",
                    "reason": "disabled item/track retained as metadata; no expected waveform claim",
                }
            )
            continue
        try:
            segments = _source_segments(source, item)
        except ComparatorRefusal as exc:
            observations.append({"uid": uid, "status": "unsupported", "reason": str(exc)})
            continue
        segment_results = []
        for segment in segments:
            result = _correlation(
                source,
                rendered,
                segment["sourceStartSample"],
                segment["sourceEndSample"],
                segment["recordStartSample"],
            )
            segment_results.append({**segment, "comparison": result})
        observations.append(
            {
                "uid": uid,
                "filename": item.get("filename"),
                "trackIndex": item.get("trackIndex"),
                "speedPercent": item.get("speedPercent"),
                "enabled": item.get("enabled"),
                "trackEnabled": item.get("trackEnabled"),
                "status": "compared",
                "segments": segment_results,
            }
        )
    return {
        "kind": "issue-141-generated-program-pcm-comparison-v1",
        "status": "comparison-complete-waveform-only",
        "taskId": TASK_ID,
        "inputs": {
            "source": {
                "path": str(source_path),
                "sha256": SOURCE_SHA256,
                "channels": source_channels,
                "frames": source_frames,
                "sampleRateHz": SAMPLE_RATE_HZ,
                "pcm": "PCM16",
            },
            "rendered": {
                "path": str(rendered_path),
                "sha256": _sha256(rendered_path),
                "channels": rendered_channels,
                "frames": rendered_frames,
                "sampleRateHz": SAMPLE_RATE_HZ,
                "pcm": "PCM24; channels averaged for comparison",
            },
            "pair": {"path": str(pair_path), "sha256": _sha256(pair_path)},
            "pairBinding": {
                "sha256Argument": pair_sha256,
                "selectedTimelineUid": MATRIX_UID,
                "sourceUid": REPEATED_SOURCE_UID,
                "timelineConsistency": pair.get("timelineConsistency"),
                "poolConsistency": pair.get("poolConsistency"),
                "repeatedItemCount": len(items),
            },
        },
        "observations": observations,
        "limitations": [
            "Waveform correlation does not establish speech deletion, clip deletion, program visibility, routing, or audibility.",
            "Only generated repeated.wav and a generated rendered WAV are read; protected presenter metadata may remain in the retained pair.",
            "Source-support mapping is emitted only for explicit 100% audio speed records.",
            "A weak/insufficient correlation is unresolved evidence, not a Resolve capability failure.",
        ],
    }


def _write_pcm24(path: Path, samples: array, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(3)
        writer.setframerate(SAMPLE_RATE_HZ)
        chunk_size = 65_536
        for chunk_start in range(0, len(samples), chunk_size):
            chunk = samples[chunk_start : chunk_start + chunk_size]
            raw = bytearray()
            for value in chunk:
                value = max(-0.999999, min(0.999999, float(value)))
                sample = int(round(value * ((1 << 23) - 1)))
                encoded = int(sample).to_bytes(3, "little", signed=True)
                raw.extend(encoded * channels)
            writer.writeframes(bytes(raw))


def _self_check(output_path: Path) -> dict[str, Any]:
    source_path = _require_generated_source(generated_source_path())
    _channels, _frames, source = _decode_pcm(source_path, expected_width=SOURCE_SAMPLE_WIDTH)
    pair_path = _repo_root() / KNOWN_PAIR_PATH
    pair_path, pair, items = _load_pair(pair_path, source_path, KNOWN_PAIR_SHA256)
    enabled_items = [
        item
        for item in items
        if item.get("enabled") and item.get("trackEnabled") and item.get("speedPercent") == 100.0
    ]
    by_start: dict[int, list[dict[str, Any]]] = {}
    for item in enabled_items:
        by_start.setdefault(int(item["recordStartFrame"]), []).append(item)
    overlap_group = next(
        (group for group in by_start.values() if len(group) >= 2),
        None,
    )
    if overlap_group is None:
        raise AssertionError("actual Matrix pair has no enabled repeated.wav overlap group")
    selected_items = overlap_group[:2]
    selected_uids = {str(item["uid"]) for item in selected_items}
    with tempfile.TemporaryDirectory(prefix="vera141-pcm-self-check-") as temp_name:
        temp = Path(temp_name)
        rendered_path = temp / "generated-self-check.wav"
        lag = 240
        record_start = int(selected_items[0]["recordStartFrame"]) * SAMPLES_PER_FRAME
        output_length = record_start + len(source) + lag
        rendered = array("f", [0.0]) * output_length
        for index, value in enumerate(source):
            rendered[record_start + index + lag] += 0.80 * value
            rendered[record_start + index + lag] += 0.40 * value
        _write_pcm24(rendered_path, rendered)
        comparison = compare(
            source_path,
            rendered_path,
            pair_path,
            KNOWN_PAIR_SHA256,
            item_uids=selected_uids,
            _self_check=True,
        )
        segment_results = [
            row["segments"] for row in comparison["observations"] if row.get("segments")
        ]
        measured_lags = {
            segment["comparison"].get("bestLagSamples")
            for segments in segment_results
            for segment in segments
            if segment["comparison"].get("bestLagSamples") is not None
        }
        if measured_lags != {lag}:
            raise AssertionError(f"self-check lag mismatch: {measured_lags}")
        if any(
            segment["comparison"].get("status") != "strong-correlation"
            for segments in segment_results
            for segment in segments
        ):
            raise AssertionError("self-check did not produce strong waveform correlation")
        non100 = dict(selected_items[0], speedPercent=50.0)
        try:
            _source_segments(source, non100)
        except ComparatorRefusal as exc:
            non100_refusal = str(exc)
        else:
            raise AssertionError("self-check remapped a non-100% item")
        waveform_metrics = []
        for row in comparison["observations"]:
            if not row.get("segments"):
                continue
            waveform_metrics.append(
                {
                    "uid": row["uid"],
                    "segments": [
                        {
                            key: segment["comparison"].get(key)
                            for key in (
                                "sourceStartSample",
                                "sourceEndSample",
                                "recordStartSample",
                                "recordEndSample",
                                "bestLagSamples",
                                "score",
                                "gain",
                                "residualEnergy",
                                "renderedEnergy",
                                "sampleCount",
                                "limits",
                            )
                            if key in segment or key in segment["comparison"]
                        }
                        for segment in row["segments"]
                    ],
                }
            )
        wrong_source = temp / SOURCE_NAME
        wrong_source.write_bytes(source_path.read_bytes())
        try:
            compare(
                wrong_source,
                rendered_path,
                pair_path,
                KNOWN_PAIR_SHA256,
                item_uids=selected_uids,
                _self_check=True,
            )
        except ComparatorRefusal as exc:
            refusal = str(exc)
        else:
            raise AssertionError("wrong source path was accepted")
        return {
            "kind": "issue-141-generated-program-pcm-comparator-local-check",
            "taskId": TASK_ID,
            "status": "self-check-passed; no native output analyzed",
            "source": {"path": str(source_path), "sha256": SOURCE_SHA256},
            "pairBinding": {
                "path": str(pair_path),
                "sha256": KNOWN_PAIR_SHA256,
                "selectedTimelineUid": MATRIX_UID,
                "sourceUid": REPEATED_SOURCE_UID,
                "repeatedItemCount": len(items),
                "selfCheckItemUids": sorted(selected_uids),
                "recordStartFrame": selected_items[0]["recordStartFrame"],
            },
            "checks": [
                {
                    "name": "delayed-signal",
                    "status": "passed",
                    "expectedLagSamples": lag,
                    "observedLagSamples": sorted(measured_lags),
                },
                {
                    "name": "overlapping-repeated-source-mixture",
                    "status": "passed",
                    "detail": "Two actual enabled repeated.wav Matrix items share a record start; generated waveform metrics were retained without audibility inference.",
                },
                {
                    "name": "non100-speed-refusal",
                    "status": "passed",
                    "detail": non100_refusal,
                },
                {
                    "name": "wrong-source-path-refusal",
                    "status": "passed",
                    "detail": refusal,
                },
            ],
            "waveformMetrics": waveform_metrics,
            "comparisonLimits": {
                "maxLagSamples": MAX_LAG_SAMPLES,
                "coarseStepSamples": COARSE_LAG_STEP,
                "sourcePcm": "PCM16 mono 48 kHz",
                "renderedPcm": "PCM24 48 kHz; channels averaged",
            },
            "limitations": [
                "No Resolve-rendered WAV existed for this local check, so no native PCM conclusion is recorded.",
                "Waveform correlation cannot prove deletion or final program audibility.",
                "Non-100% audio speed records are reported unsupported and are not remapped.",
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--rendered")
    parser.add_argument("--pair")
    parser.add_argument("--pair-sha256")
    args = parser.parse_args(argv)
    if args.self_check:
        if args.output is None:
            parser.error("--self-check requires --output")
        result = _self_check(args.output)
    else:
        if not all((args.source, args.rendered, args.pair, args.pair_sha256, args.output)):
            parser.error(
                "comparison requires --source, --rendered, --pair, "
                "--pair-sha256, and --output"
            )
        rendered_path = _require_rendered(args.rendered)
        result = compare(args.source, rendered_path, args.pair, args.pair_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
