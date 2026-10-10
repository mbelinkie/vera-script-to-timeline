"""Convert a saved Resolve `GetTranscription()` dump into a T-C candidate file.

The dump is written by the Resolve run step (`raw-resolve.json`). Word
timecodes are HH:MM:SS:FF at the clip's frame rate (120 fps in this study, so
FF runs 0-119). The clip starts at 00:00:00:00, so timecode equals recording
time. "(...)" items are silences and are dropped. Parenthesised items such as
"(Footsteps)" are sound events and are kept with type "event".

Usage: resolve_to_tc.py --raw raw-resolve.json --out T-C-resolve.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def tc_seconds(tc: str, fps: float) -> float:
    h, m, s, f = (int(x) for x in tc.split(":"))
    return h * 3600 + m * 60 + s + f / fps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw.read_text())
    fps = float(raw["clipProps"]["FPS"])
    if raw["clipProps"]["Start TC"].strip(":0"):
        raise SystemExit(f"clip does not start at zero: {raw['clipProps']['Start TC']}")
    words = []
    for seg in raw["transcription"]["segments"]:
        for w in seg.get("words", []):
            text = w["text"].strip()
            if text == "(...)" or not text:
                continue
            kind = "event" if text.startswith("(") and text.endswith(")") else "word"
            words.append(
                {
                    "k": len(words),
                    "text": text,
                    "start": round(tc_seconds(w["start"], fps), 3),
                    "end": round(tc_seconds(w["end"], fps), 3),
                    "type": kind,
                    "confidence": None,
                }
            )
    args.out.write_text(
        json.dumps(
            {
                "source": "T-C-resolve",
                "provider": "DaVinci Resolve Studio",
                "model": f"Resolve {raw['resolveVersion']} TranscribeAudio",
                "words": words,
                "transcript": " ".join(w["text"] for w in words if w["type"] == "word"),
                "provenance": {
                    "frameRate": fps,
                    "resolutionMs": round(1000 / fps, 2),
                    "language": raw["transcriptionLanguage"],
                    "speakerDetection": False,
                    "notes": "word start/end are Resolve timecodes at the clip frame rate",
                },
            },
            indent=1,
        )
    )
    print(
        f"{sum(w['type'] == 'word' for w in words)} words, {sum(w['type'] == 'event' for w in words)} events"
    )


if __name__ == "__main__":
    main()
