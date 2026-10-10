"""Turn a T-C transcript into aligner input tokens plus segment-assignment anchors.

This is used when a recording has no Producer transcript (recording B). The
recogniser's words become the display tokens and its own times become the
coarse anchors for `segment.py assign`. Sound events are dropped. The words
are not corrected in any way.

Usage: tc_tokens.py --tc T-C-x.json --tokens-out tokens.json --anchors-out anchors.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textnorm import normalise_token


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--tc", "--tokens-out", "--anchors-out"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    tc = json.loads(args.tc.read_text())
    words = [w for w in tc["words"] if w.get("type") != "event" and normalise_token(str(w["text"]))]
    tokens = [str(w["text"]) for w in words]
    rows = []
    for index, w in enumerate(words):
        spoken = normalise_token(str(w["text"]))
        for sub in range(len(spoken)):
            row = {"i": index, "start": w["start"], "end": w["end"], "status": "aligned"}
            if len(spoken) > 1:
                row["sub"] = sub
            rows.append(row)
    args.tokens_out.write_text(json.dumps(tokens))
    args.anchors_out.write_text(json.dumps({"aligner": f'anchor-{tc["source"]}', "words": rows}, indent=1))
    print(f"{len(tokens)} tokens, {len(rows)} entries from {tc['source']}")


if __name__ == "__main__":
    main()
