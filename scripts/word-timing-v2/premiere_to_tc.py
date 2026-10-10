"""Convert an Adobe Premiere transcript export into a T-C candidate file.

Premiere's JSON gives each word a start and a duration on the source clip's
clock. This keeps the words that fall inside the recording's window and shifts
them onto the recording's clock. Times are not otherwise changed.

Usage: premiere_to_tc.py --premiere X.json --shift SEC --duration SEC --out T-C-premiere.json
  (recording time = premiere time + shift)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--premiere", type=Path, required=True)
    parser.add_argument("--shift", type=float, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.premiere.read_text())
    words = []
    for w in (w for seg in data["segments"] for w in seg["words"]):
        start = w["start"] + args.shift
        end = start + w["duration"]
        if start < 0 or end > args.duration:
            continue
        tags = w.get("tags") or []
        words.append({"k": len(words), "text": w["text"], "start": round(start, 3), "end": round(end, 3),
                      "type": "filler" if "disfluency" in tags else "word", "confidence": w.get("confidence"),
                      "tags": tags})
    args.out.write_text(json.dumps({
        "source": "T-C-premiere", "provider": "Adobe Premiere Pro (Speech to Text)", "model": "unknown (export)",
        "words": words, "transcript": " ".join(w["text"] for w in words),
        "provenance": {"export": args.premiere.name,
                       "exportSha256": hashlib.sha256(args.premiere.read_bytes()).hexdigest(),
                       "shiftSec": args.shift, "windowSec": [0, args.duration],
                       "notes": "end = start + duration as exported; most ends equal the next start"}}, indent=1))
    print(f"{len(words)} words in window; {sum(w['type'] == 'filler' for w in words)} tagged disfluency")


if __name__ == "__main__":
    main()
