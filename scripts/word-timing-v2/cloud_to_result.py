"""Map a cloud transcript (T-C file) onto reference entries as a contract RESULT.

This is for *scoring timing only*. A recognised word lends its times to a
reference entry when the normalised text is identical and its midpoint is
within WINDOW_SEC of that entry's anchor midpoint. The anchors come from the
pre-fill label file (later, the corrected answer key). Text alone cannot tell
apart repeated takes of the same line. Matches are one-to-one and keep order.
Unmatched entries are `failed`, and nothing is interpolated. The recogniser's
text is never changed (plan section 5, no reference leakage).

Usage: cloud_to_result.py --segments SEGMENTS.json --anchor-labels words.txt --tc T-C-x.json --out RESULT.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textnorm import normalise_token

WINDOW_SEC = 0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--segments", "--anchor-labels", "--tc", "--out"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    entries = [
        w for s in json.loads(args.segments.read_text())["segments"] for w in s["words"]
    ]
    labels = [
        line.split("\t")
        for line in args.anchor_labels.read_text().splitlines()
        if line.strip()
    ]
    if len(labels) != len(entries):
        raise SystemExit(f"{len(labels)} anchor labels for {len(entries)} entries")
    anchors = [(float(s) + float(e)) / 2 for s, e, _ in labels]

    tc = json.loads(args.tc.read_text())
    hyp = []
    for w in tc["words"]:
        if w["start"] is None or w["end"] is None:
            continue
        spoken = normalise_token(str(w["text"]))
        if len(spoken) == 1:  # a numeral split into several words has no per-word times
            hyp.append(
                {
                    "text": spoken[0],
                    "start": w["start"],
                    "end": w["end"],
                    "mid": (w["start"] + w["end"]) / 2,
                }
            )

    times: dict[int, dict[str, float]] = {}
    floor = 0  # hypothesis index below which words are used up (keeps order)
    for n, entry in enumerate(entries):
        candidates = [
            k
            for k in range(floor, len(hyp))
            if hyp[k]["text"] == entry["text"]
            and abs(hyp[k]["mid"] - anchors[n]) <= WINDOW_SEC
        ]
        if candidates:
            best = min(candidates, key=lambda k: abs(hyp[k]["mid"] - anchors[n]))
            times[n] = {"start": hyp[best]["start"], "end": hyp[best]["end"]}
            floor = best + 1

    rows = []
    for n, entry in enumerate(entries):
        row: dict[str, object] = {"i": entry["i"]}
        if "sub" in entry:
            row["sub"] = entry["sub"]
        row.update(
            {**times[n], "status": "aligned"}
            if n in times
            else {"start": None, "end": None, "status": "failed"}
        )
        rows.append(row)
    args.out.write_text(
        json.dumps(
            {
                "aligner": "A-CLOUD",
                "variant": tc["source"],
                "words": rows,
                "provenance": {
                    "mappedFrom": args.tc.name,
                    "anchors": args.anchor_labels.name,
                    "windowSec": WINDOW_SEC,
                    "matched": len(times),
                    "entries": len(entries),
                },
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
