"""Build the Audacity pre-fill and check tracks (plan section 6).

Usage:
  prefill.py --segments SEGMENTS.json --vad vad.json --results R1.json R2.json R3.json \
      --name rec-a --out-dir DIR

Writes `<name>-words.txt` (one region per spoken word: median of the aligners
per boundary) and `<name>-check.txt` (only the regions worth attention).
Times are seconds on the recording clock, so they line up on the 48 kHz file.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

DISAGREE_SEC = 0.040
TAKE_EDGE_PAUSE_SEC = 0.700
MIN_MISSED_SPEECH_SEC = 0.150
MIN_REGION_SEC = 0.010


def key(row: dict[str, object]) -> tuple[int, int]:
    return int(row["i"]), int(row.get("sub", 0))  # type: ignore[arg-type]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--vad", type=Path, required=True)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    entries = [
        w for s in json.loads(args.segments.read_text())["segments"] for w in s["words"]
    ]
    results = [json.loads(p.read_text()) for p in args.results]
    by_system = [{key(r): r for r in res["words"]} for res in results]
    names = [f"{r['aligner']}:{r.get('variant') or ''}".rstrip(":") for r in results]

    words = []
    checks: list[tuple[float, float, str]] = []
    for entry in entries:
        k = key(entry)
        rows = [table.get(k) for table in by_system]
        ok = [r for r in rows if r and r.get("status") == "aligned"]
        label = (
            str(entry["text"])
            if "sub" not in entry
            else f"{entry['text']}[{entry['display']}]"
        )
        if not ok:
            words.append({"label": label, "missing": True})
            continue
        start = statistics.median(float(r["start"]) for r in ok)
        end = statistics.median(float(r["end"]) for r in ok)
        reasons = []
        if len(ok) < len(rows):
            reasons.append(f"{len(rows) - len(ok)} aligner(s) failed")
        for edge in ("start", "end"):
            spread = max(float(r[edge]) for r in ok) - min(float(r[edge]) for r in ok)
            if spread > DISAGREE_SEC:
                reasons.append(f"{edge} disagree {spread * 1000:.0f}ms")
        words.append({"label": label, "start": start, "end": end, "reasons": reasons})

    # Repair order: each region ends no later than the next one starts.
    placed = [w for w in words if not w.get("missing")]
    for a, b in zip(placed, placed[1:]):
        if a["end"] > b["start"]:
            mid = (a["end"] + b["start"]) / 2
            a["end"] = b["start"] = mid
    for w in placed:
        w["end"] = max(w["end"], w["start"] + MIN_REGION_SEC)

    # A word no aligner placed is flagged as a point where its predecessor ends.
    last_end = 0.0
    for w in words:
        if w.get("missing"):
            checks.append(
                (
                    last_end,
                    last_end,
                    f"MISSING {w['label']}: no aligner placed it, add a region",
                )
            )
        else:
            last_end = w["end"]

    for n, w in enumerate(placed):
        before = w["start"] - placed[n - 1]["end"] if n else 99.0
        after = placed[n + 1]["start"] - w["end"] if n + 1 < len(placed) else 99.0
        if before >= TAKE_EDGE_PAUSE_SEC or after >= TAKE_EDGE_PAUSE_SEC:
            w["reasons"].append("possible take edge")
        if w["reasons"]:
            checks.append(
                (w["start"], w["end"], f"{w['label']}: {', '.join(w['reasons'])}")
            )

    # Speech the VAD heard that no word covers: a stumble may need adding.
    for s, e in json.loads(args.vad.read_text())["speechRegions"]:
        cursor, holes = s, []
        for w in placed:
            if w["end"] <= cursor or w["start"] >= e:
                continue
            if w["start"] - cursor >= MIN_MISSED_SPEECH_SEC:
                holes.append((cursor, w["start"]))
            cursor = max(cursor, w["end"])
        if e - cursor >= MIN_MISSED_SPEECH_SEC:
            holes.append((cursor, e))
        checks.extend(
            (a, b, "SPEECH WITH NO WORD: add FRAG/REP/FILLER if a stumble")
            for a, b in holes
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"{args.name}-words.txt").write_text(
        "".join(f"{w['start']:.6f}\t{w['end']:.6f}\t{w['label']}\n" for w in placed)
    )
    (args.out_dir / f"{args.name}-check.txt").write_text(
        "".join(f"{a:.6f}\t{b:.6f}\t{t}\n" for a, b, t in sorted(checks))
    )
    summary = {
        "systems": names,
        "words": len(entries),
        "placed": len(placed),
        "checks": len(checks),
        "speechWithNoWord": sum(1 for c in checks if c[2].startswith("SPEECH")),
    }
    (args.out_dir / f"{args.name}-prefill-summary.json").write_text(
        json.dumps(summary, indent=1)
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
