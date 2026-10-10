"""Score systems against a frozen answer key, following SCORING-RULES.md.

Usage:
  score.py --key KEY.csv --segments SEGMENTS.json [--result R.json ...] [--tc T-C.json ...] --out metrics.json

`--result` files are contract RESULT files whose rows are tied to SEGMENTS
entries (aligners). `--tc` files are recogniser transcripts with their own
words and times. Prints aggregate tables only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

from audition import read_markers
from textnorm import normalise_token
from validate_key import EVENT, LABEL

WINDOW_SEC = 0.5
PHRASE_EDGE_SEC = 0.700
PAUSE_SEC = 0.150
OVER_MS = 120.0


@dataclass
class KeyWord:
    text: str
    start: float
    end: float
    tag: str | None
    unsure: bool
    onset_class: str = ""
    offset_class: str = ""


def load_key(path: Path) -> list[KeyWord]:
    words = []
    for start, end, name, _ in read_markers(path):
        if EVENT.match(name):
            continue
        match = LABEL.match(name)
        if not match:
            raise SystemExit(f"unreadable key label {name!r}")
        raw = re.sub(r"\[[^\]]*\]$", "", match["word"])
        spoken = normalise_token(raw)
        words.append(KeyWord(spoken[0] if spoken else raw.casefold(), start, end, match["tag"], bool(match["unsure"])))
    for n, w in enumerate(words):
        before = w.start - words[n - 1].end if n else math.inf
        after = words[n + 1].start - w.end if n + 1 < len(words) else math.inf
        w.onset_class, w.offset_class = classify(before), classify(after)
    return words


def classify(gap: float) -> str:
    return "phrase_edge" if gap >= PHRASE_EDGE_SEC else "pause_adjacent" if gap >= PAUSE_SEC else "connected"


def system_words_from_result(result: dict, segments: dict) -> list[tuple[str, float, float]]:
    entries = {(int(e["i"]), int(e.get("sub", 0))): e["text"] for s in segments["segments"] for e in s["words"]}
    out = []
    for row in result["words"]:
        if row.get("status") == "aligned" and row["start"] is not None:
            out.append((entries[(int(row["i"]), int(row.get("sub", 0)))], float(row["start"]), float(row["end"])))
    return out


def system_words_from_tc(tc: dict) -> list[tuple[str, float, float]]:
    out = []
    for w in tc["words"]:
        if w.get("type") == "event" or w["start"] is None or w["end"] is None:
            continue
        spoken = normalise_token(str(w["text"]))
        if len(spoken) == 1:
            out.append((spoken[0], float(w["start"]), float(w["end"])))
        else:  # a split numeral: words share the token span, so only text counts
            out.extend((t, float(w["start"]), float(w["end"])) for t in spoken)
    return out


def match(key: list[KeyWord], words: list[tuple[str, float, float]]) -> dict[int, int]:
    pairs: dict[int, int] = {}
    floor = 0
    for n, k in enumerate(key):
        mid = (k.start + k.end) / 2
        best = None
        for j in range(floor, len(words)):
            text, s, e = words[j]
            if (s + e) / 2 > mid + WINDOW_SEC:
                break
            if text == k.text and abs((s + e) / 2 - mid) <= WINDOW_SEC:
                if best is None or abs((s + e) / 2 - mid) < abs(sum(words[best][1:]) / 2 - mid):
                    best = j
        if best is not None:
            pairs[n] = best
            floor = best + 1
    return pairs


def upper95(k: int, n: int) -> float:
    if n == 0:
        return float("nan")
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        tail = sum(math.comb(n, j) * mid**j * (1 - mid) ** (n - j) for j in range(k + 1))
        lo, hi = (mid, hi) if tail > 0.05 else (lo, mid)
    return hi


def stats(errors: list[float]) -> dict[str, float]:
    if not errors:
        return {"n": 0}
    absolute = sorted(abs(e) for e in errors)

    def pct(q: float) -> float:
        return absolute[min(len(absolute) - 1, math.ceil(q * len(absolute)) - 1)]

    over = sum(a > OVER_MS for a in absolute)
    return {"n": len(errors), "median": statistics.median(absolute), "p90": pct(0.9), "p95": pct(0.95),
            "max": absolute[-1], "bias": statistics.mean(errors), "over120": over,
            "over120Share": over / len(errors), "over120Upper95": upper95(over, len(errors))}


def boundary_errors(key: list[KeyWord], words: list[tuple[str, float, float]], pairs: dict[int, int]) -> dict:
    groups: dict[str, list[float]] = {}
    for n, j in pairs.items():
        k, (_, s, e) = key[n], words[j]
        for side, err, cls in (("onset", (s - k.start) * 1000, k.onset_class), ("offset", (e - k.end) * 1000, k.offset_class)):
            for name in (f"{side}/all", f"{side}/{cls}", *([f"{side}/unsure"] if k.unsure else [])):
                groups.setdefault(name, []).append(err)
    return {name: stats(errs) for name, errs in sorted(groups.items())}


def wer(key: list[KeyWord], words: list[tuple[str, float, float]]) -> dict[str, float]:
    ref, hyp = [k.text for k in key], [w[0] for w in words]
    prev = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        cur = [i] + [0] * len(hyp)
        for j in range(1, len(hyp) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ref[i - 1] != hyp[j - 1]))
        prev = cur
    return {"wer": prev[-1] / len(ref), "refWords": len(ref), "hypWords": len(hyp)}


def stumble_recall(key: list[KeyWord], words: list[tuple[str, float, float]], pairs: dict[int, int]) -> dict:
    used_elsewhere = {j for n, j in pairs.items() if not key[n].tag}
    out: dict[str, list[int]] = {}
    for k in key:
        if not k.tag:
            continue
        span = max(k.end - k.start, 1e-3)
        hit = any(min(e, k.end) - max(s, k.start) >= 0.5 * span
                  for j, (_, s, e) in enumerate(words) if j not in used_elsewhere)
        for name in (k.tag, "all"):
            out.setdefault(name, [0, 0])
            out[name][0] += hit
            out[name][1] += 1
    return {tag: {"recalled": h, "total": t, "recall": h / t} for tag, (h, t) in sorted(out.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--result", type=Path, nargs="*", default=[])
    parser.add_argument("--tc", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = load_key(args.key)
    segments = json.loads(args.segments.read_text())
    report: dict[str, dict] = {"_key": {
        "words": len(key), "stumbles": sum(1 for k in key if k.tag),
        "classes": {side: {c: sum(1 for k in key if getattr(k, f"{side}_class") == c)
                           for c in ("phrase_edge", "pause_adjacent", "connected")} for side in ("onset", "offset")}}}
    systems = [(p, "result") for p in args.result] + [(p, "tc") for p in args.tc]
    for path, kind in systems:
        data = json.loads(path.read_text())
        if kind == "result":
            name = f'{data["aligner"]}{":" + data["variant"] if data.get("variant") else ""} [{path.stem.split("__")[0]}]'
            words = system_words_from_result(data, segments)
        else:
            name = data["source"]
            words = system_words_from_tc(data)
        pairs = match(key, words)
        entry = {"file": path.name, "coverage": len(pairs) / len(key), "boundaries": boundary_errors(key, words, pairs)}
        if kind == "tc":
            entry["wordAccuracy"] = wer(key, words)
            entry["stumbleRecall"] = stumble_recall(key, words, pairs)
        report[name] = entry
    args.out.write_text(json.dumps(report, indent=1))

    print(json.dumps(report["_key"]))
    print(f'{"system":42s} {"cov":>5s} | {"onset med p95 bias >120":>26s} | {"offset med p95 bias >120":>26s}')
    for name, entry in report.items():
        if name == "_key":
            continue
        b = entry["boundaries"]

        def cell(side: str) -> str:
            s = b.get(f"{side}/all", {"n": 0})
            return f'{s["median"]:5.0f} {s["p95"]:5.0f} {s["bias"]:+5.0f} {s["over120Share"]:5.1%}' if s["n"] else "-"

        extra = ""
        if "wordAccuracy" in entry:
            extra = f'  WER {entry["wordAccuracy"]["wer"]:.1%}  stumbles {entry["stumbleRecall"].get("all", {}).get("recall", 0):.0%}'
        print(f'{name:42s} {entry["coverage"]:5.1%} | {cell("onset"):>26s} | {cell("offset"):>26s}{extra}')


if __name__ == "__main__":
    main()
