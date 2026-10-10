"""Preliminary score of contract RESULT files against the frozen 80-word set.

This is an early read on recording A only. The step-4 metrics use the full
corrected answer key. Prints aggregates only.

Usage: score_80.py --truth frozen-reference-v2.json RESULT.json [RESULT.json ...]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def upper95(k: int, n: int) -> float:
    """One-sided 95% Clopper-Pearson upper bound on a proportion."""
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        tail = sum(
            math.comb(n, j) * mid**j * (1 - mid) ** (n - j) for j in range(k + 1)
        )
        lo, hi = (mid, hi) if tail > 0.05 else (lo, mid)
    return hi


def summarise(errors: list[float]) -> str:
    absolute = [abs(e) for e in errors]
    over = sum(a > 120 for a in absolute)
    return (
        f"n={len(errors):3d} med={statistics.median(absolute):5.0f} p90={pct(absolute, 0.9):5.0f} "
        f"p95={pct(absolute, 0.95):5.0f} max={max(absolute):5.0f} bias={statistics.mean(errors):+5.0f} "
        f">120ms={over}/{len(errors)} (ub95 {upper95(over, len(errors)):.0%})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("results", type=Path, nargs="+")
    args = parser.parse_args()
    truth = json.loads(args.truth.read_text())["wordTimings"]
    for path in args.results:
        result = json.loads(path.read_text())
        spans: dict[int, list[float]] = {}
        for row in result["words"]:
            if row["status"] != "aligned":
                continue
            span = spans.setdefault(int(row["i"]), [row["start"], row["end"]])
            span[0], span[1] = min(span[0], row["start"]), max(span[1], row["end"])
        groups: dict[str, tuple[list[float], list[float]]] = {}
        missing = 0
        for t in truth:
            if t["referenceIndex"] not in spans:
                missing += 1
                continue
            s, e = spans[t["referenceIndex"]]
            onset, offset = s * 1000 - t["startMs"], e * 1000 - t["endMs"]
            for name in [
                "all",
                *(["take-edge"] if "take-edge" in t["categories"] else []),
            ]:
                groups.setdefault(name, ([], []))
                groups[name][0].append(onset)
                groups[name][1].append(offset)
        label = f"{result['aligner']} {result.get('variant') or ''}".strip()
        print(f"{label}  (missing {missing}/{len(truth)})  [{path.name}]")
        for name, (on, off) in groups.items():
            print(f"  {name:9s} onset  {summarise(on)}")
            print(f"  {name:9s} offset {summarise(off)}")


if __name__ == "__main__":
    main()
