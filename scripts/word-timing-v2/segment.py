"""Independent VAD segmentation and word-to-segment assignment (plan section 5).

Usage:
  segment.py vad --audio REC-16k.wav --out vad.json
  segment.py assign --vad vad.json --tokens tokens.json --anchors RESULT.json \
      --audio-name REC-16k.wav --out SEGMENTS.json

`tokens.json` is a list of display tokens. `anchors` is any contract RESULT
file. Its times are used only to decide which segment each word belongs to.
Segment edges sit in silence, so coarse anchor error does not matter there.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PAD_SEC = 0.300
MAX_SEGMENT_SEC = 30.0
SILERO_VERSION = "6.2.1"
SILERO_SETTINGS = {
    "threshold": 0.5,
    "min_speech_duration_ms": 100,
    "min_silence_duration_ms": 150,
    "speech_pad_ms": 0,
}


def run_vad(audio: Path) -> list[tuple[float, float]]:
    from silero_vad import get_speech_timestamps, load_silero_vad, read_audio

    model = load_silero_vad(onnx=True)
    wav = read_audio(str(audio), sampling_rate=16000)
    stamps = get_speech_timestamps(wav, model, sampling_rate=16000, return_seconds=True, **SILERO_SETTINGS)
    return [(float(s["start"]), float(s["end"])) for s in stamps]


def group_regions(regions: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    """Merge speech regions into padded segments of at most MAX_SEGMENT_SEC.

    Any group whose padded span is too long is split at its widest internal
    silence, recursively, so segment edges land in the longest pauses. Padding
    never crosses the midpoint of the gap to a neighbouring group, so segments
    never overlap.
    """
    pending = [regions]
    done: list[list[tuple[float, float]]] = []
    while pending:
        group = pending.pop()
        if len(group) == 1 or (group[-1][1] - group[0][0]) + 2 * PAD_SEC <= MAX_SEGMENT_SEC:
            done.append(group)
            continue
        cut = max(range(1, len(group)), key=lambda k: group[k][0] - group[k - 1][1])
        pending.extend([group[:cut], group[cut:]])
    groups = sorted([[g[0][0], g[-1][1]] for g in done])
    padded = []
    for index, (start, end) in enumerate(groups):
        low = 0.0 if index == 0 else (groups[index - 1][1] + start) / 2
        high = duration if index == len(groups) - 1 else (end + groups[index + 1][0]) / 2
        padded.append((round(max(low, start - PAD_SEC), 3), round(min(high, end + PAD_SEC), 3)))
    return padded


def assign_words(
    entries: list[dict[str, object]],
    anchors: list[dict[str, object]],
    segments: list[tuple[float, float]],
) -> list[dict[str, object]]:
    """Give each entry to the segment holding its anchor midpoint, keeping order."""
    out = [{"id": f"s{n:03d}", "start": s, "end": e, "words": []} for n, (s, e) in enumerate(segments)]
    floor = 0
    for entry, anchor in zip(entries, anchors, strict=True):
        if anchor.get("start") is None:
            target = floor
        else:
            mid = (float(anchor["start"]) + float(anchor["end"])) / 2
            target = min(range(len(segments)), key=lambda n: 0 if segments[n][0] <= mid <= segments[n][1]
                         else min(abs(mid - segments[n][0]), abs(mid - segments[n][1])))
        floor = max(floor, target)
        out[floor]["words"].append(entry)
    return [seg for seg in out if seg["words"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    vad = sub.add_parser("vad")
    vad.add_argument("--audio", type=Path, required=True)
    vad.add_argument("--out", type=Path, required=True)
    assign = sub.add_parser("assign")
    for name in ("--vad", "--tokens", "--anchors", "--out"):
        assign.add_argument(name, type=Path, required=True)
    assign.add_argument("--audio-name", required=True)
    args = parser.parse_args()

    if args.cmd == "vad":
        import soundfile

        duration = soundfile.info(str(args.audio)).duration
        regions = run_vad(args.audio)
        payload = {
            "audio": args.audio.name,
            "durationSec": duration,
            "vad": {"model": "silero-vad", "version": SILERO_VERSION, "onnx": True, **SILERO_SETTINGS},
            "speechRegions": [[round(s, 3), round(e, 3)] for s, e in regions],
            "segments": [list(seg) for seg in group_regions(regions, duration)],
        }
        args.out.write_text(json.dumps(payload, indent=1))
        return

    from textnorm import word_entries

    vad_data = json.loads(args.vad.read_text())
    entries = word_entries(json.loads(args.tokens.read_text()))
    anchors = json.loads(args.anchors.read_text())["words"]
    segments = [tuple(seg) for seg in vad_data["segments"]]
    payload = {"audio": args.audio_name, "offsetSec": 0.0,
               "segments": assign_words(entries, anchors, segments)}
    args.out.write_text(json.dumps(payload, indent=1))


if __name__ == "__main__":
    main()
