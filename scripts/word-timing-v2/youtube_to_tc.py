"""Convert YouTube automatic captions (yt-dlp `--sub-format json3`) into a T-C transcript.

Auto-generated English captions carry a start time for every word
(`tStartMs` of the event plus the segment's `tOffsetMs`). They carry no word
end times. End times are derived the same way as for Parakeet: the next word's
start, capped at start + 0.5 s, and capped at the caption event's end for the
last word of an event. Bracketed sound tags such as `[Music]` become events.

These are the "native" word timings a Research source gets for free; the
caption text can also feed MFA like any recogniser's text.

Usage: youtube_to_tc.py --json3 ID.en.json3 --out T-C-youtube.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_WORD_S = 0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json3", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.json3.read_text())

    raw = []  # (start_s, text, event_end_s)
    for event in data.get("events", []):
        if "segs" not in event or event.get("aAppend"):
            continue
        t0 = event["tStartMs"]
        event_end = (t0 + event.get("dDurationMs", 0)) / 1000
        for seg in event["segs"]:
            text = seg.get("utf8", "").strip()
            if text:
                raw.append(((t0 + seg.get("tOffsetMs", 0)) / 1000, text, event_end))

    words = []
    for k, (start, text, event_end) in enumerate(raw):
        is_event = text.startswith("[") and text.endswith("]")
        nxt = raw[k + 1][0] if k + 1 < len(raw) else event_end
        end = min(start + MAX_WORD_S, nxt if nxt > start else event_end)
        end = max(end, start + 0.01)
        words.append(
            {
                "k": k,
                "text": text,
                "start": round(start, 3),
                "end": round(end, 3),
                "type": "event" if is_event else "word",
                "confidence": None,
            }
        )

    args.out.write_text(
        json.dumps(
            {
                "source": "T-C-youtube",
                "provider": "YouTube automatic captions (yt-dlp json3)",
                "model": "youtube-asr (unversioned)",
                "words": words,
                "transcript": " ".join(w["text"] for w in words if w["type"] == "word"),
                "provenance": {
                    "file": args.json3.name,
                    "timestampSemantics": "json3 tStartMs + tOffsetMs, word START only",
                    "endTimeDerivation": "min(next word start, start + 0.5 s), last word of an event capped at event end",
                },
            },
            indent=1,
        )
    )
    print(f"{args.out.name}: {sum(w['type'] == 'word' for w in words)} words")


if __name__ == "__main__":
    main()
