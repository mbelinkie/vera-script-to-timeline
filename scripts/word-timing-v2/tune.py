"""Step 4 tuning: bias correction and silence snap, leave-one-segment-out.

Tuned parameters (3 of the plan's maximum of 5):
- onset_shift_ms, offset_shift_ms: constant shifts, -40..+40 ms in 5 ms steps;
- snap_db: off, or 6/10/15/20 dB above the clip's noise floor (10th-percentile
  frame level). A boundary that the *system's own output* puts next to a pause
  of 150 ms or more moves to the nearest crossing of that level within
  +/-60 ms: an upward crossing for onsets, a downward one for offsets.

Reference: the unanchored independent timing set (see SCORING-RULES.md). The
objective is the mean |error| with each error clipped at 200 ms, so a few gross
mapping errors cannot drive the shifts. Folds are the recording's VAD
segments: parameters are chosen on all other segments and applied to the
held-out one.

Usage: tune.py --result R.json::SEG.json --independent ref.json --key KEY.csv --vad vad.json \
               --audio REC-16k.wav [--aliases A.json] --out tuned.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
from pathlib import Path

import numpy as np
import soundfile as sf

import score

SHIFTS = list(range(-40, 41, 5))
SNAPS: list[float | None] = [None, 6.0, 10.0, 15.0, 20.0]
SNAP_WINDOW = 0.060
PAUSE = 0.150
FRAME = 0.005
CLIP_MS = 200.0


def envelope(audio: Path) -> tuple[np.ndarray, float]:
    x, sr = sf.read(str(audio), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(sr * FRAME)
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    return db, float(np.percentile(db, 10))


def snap(t: float, rising: bool, level: float, db: np.ndarray) -> float:
    lo, hi = int((t - SNAP_WINDOW) / FRAME), int((t + SNAP_WINDOW) / FRAME)
    best = None
    for f in range(max(1, lo), min(len(db) - 1, hi)):
        crossed = db[f - 1] < level <= db[f] if rising else db[f - 1] >= level > db[f]
        if crossed and (best is None or abs(f * FRAME - t) < abs(best - t)):
            best = f * FRAME
    return t if best is None else best


def apply(words: list[tuple[str, float, float]], onset: int, offset: int, snap_db: float | None,
          db: np.ndarray, floor: float) -> list[tuple[str, float, float]]:
    out = []
    for n, (text, s, e) in enumerate(words):
        before = s - words[n - 1][2] if n else 99.0
        after = words[n + 1][1] - e if n + 1 < len(words) else 99.0
        s2, e2 = s + onset / 1000, e + offset / 1000
        if snap_db is not None:
            if before >= PAUSE:
                s2 = snap(s2, True, floor + snap_db, db)
            if after >= PAUSE:
                e2 = snap(e2, False, floor + snap_db, db)
        out.append((text, s2, max(e2, s2 + 0.01)))
    return out


def errors(ref: list[score.KeyWord], words: list[tuple[str, float, float]]) -> list[tuple[int, str, float]]:
    pairs = score.match(ref, words)
    return [(n, side, err) for n, j in pairs.items()
            for side, err in (("onset", (words[j][1] - ref[n].start) * 1000), ("offset", (words[j][2] - ref[n].end) * 1000))]


def objective(errs: list[float]) -> float:
    return statistics.mean(min(abs(e), CLIP_MS) for e in errs) if errs else float("inf")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    for name in ("--independent", "--key", "--vad", "--audio", "--out"):
        parser.add_argument(name, type=Path, required=True)
    parser.add_argument("--aliases", type=Path)
    args = parser.parse_args()
    if args.aliases:
        score.ALIASES.update({k: v for k, v in json.loads(args.aliases.read_text()).items() if not k.startswith("_")})
    result_path, seg_path = (Path(p) for p in args.result.split("::"))
    words = score.system_words_from_result(json.loads(result_path.read_text()), json.loads(seg_path.read_text()))
    ref = score.load_independent(args.independent, score.load_key(args.key))
    segments = json.loads(args.vad.read_text())["segments"]
    fold_of = [next((k for k, (a, b) in enumerate(segments) if a <= (r.start + r.end) / 2 <= b), -1) for r in ref]
    db, floor = envelope(args.audio)

    configs = list(itertools.product(SHIFTS, SHIFTS, SNAPS))
    cache: dict[tuple, list[tuple[int, str, float]]] = {}
    for snap_db in SNAPS:  # shifts are separable from the snap only through apply(), so evaluate every config
        for onset, offset in itertools.product(SHIFTS, SHIFTS):
            cache[(onset, offset, snap_db)] = errors(ref, apply(words, onset, offset, snap_db, db, floor))

    def fit(exclude: int | None) -> tuple:
        def loss(cfg: tuple) -> float:
            return objective([e for n, _, e in cache[cfg] if fold_of[n] != exclude])
        return min(configs, key=loss)

    held_out: list[tuple[int, str, float]] = []
    chosen_per_fold = {}
    for fold in sorted(set(fold_of)):
        cfg = fit(fold)
        chosen_per_fold[fold] = cfg
        held_out += [x for x in cache[cfg] if fold_of[x[0]] == fold]
    final = fit(None)

    def summary(errs: list[tuple[int, str, float]]) -> dict:
        return {side: score.stats([e for _, s, e in errs if s == side]) for side in ("onset", "offset")}

    report = {"result": result_path.name, "configsTried": len(configs),
              "parameters": ["onset_shift_ms", "offset_shift_ms", "snap_db"],
              "final": {"onset_shift_ms": final[0], "offset_shift_ms": final[1], "snap_db": final[2]},
              "perFold": {str(k): list(v) for k, v in chosen_per_fold.items()},
              "untuned": summary(cache[(0, 0, None)]), "crossValidated": summary(held_out),
              "noiseFloorDb": floor}
    args.out.write_text(json.dumps(report, indent=1))
    print(f"{result_path.stem}: final {report['final']} ({len(configs)} configs)")
    for label in ("untuned", "crossValidated"):
        r = report[label]
        print(f"  {label:15s} onset med {r['onset']['median']:4.0f} p95 {r['onset']['p95']:4.0f} bias {r['onset']['bias']:+4.0f}"
              f" | offset med {r['offset']['median']:4.0f} p95 {r['offset']['p95']:4.0f} bias {r['offset']['bias']:+4.0f}"
              f" >120 {r['offset']['over120Share']:.1%}")


if __name__ == "__main__":
    main()
