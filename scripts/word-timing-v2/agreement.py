"""Agreement filter trade-off curve (plan section 7).

A pipeline's MFA boundary is **accepted** when a structurally different neural
aligner (Charsiu or Qwen), run on the same text, puts the same boundary within
tau. Otherwise it is marked **needs review**. A boundary the neural aligner
failed to place also needs review. For tau = 10..100 ms this reports:

- review share: needs-review boundaries over all MFA boundaries (all words the
  pipeline placed, not only reference words);
- accepted-boundary error against the reference: median, p95, and share over
  120 ms, with n.

Usage: agreement.py --mfa R.json::SEG.json --neural N.json --key KEY.csv \
        [--independent ref.json] [--aliases A.json] --out curve.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import score

TAUS = list(range(10, 101, 10))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mfa", required=True)
    parser.add_argument("--neural", type=Path, required=True)
    parser.add_argument(
        "--key", type=Path, help="not needed with a blind-set --independent"
    )
    parser.add_argument("--independent", type=Path)
    parser.add_argument("--aliases", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.aliases:
        score.ALIASES.update(
            {
                k: v
                for k, v in json.loads(args.aliases.read_text()).items()
                if not k.startswith("_")
            }
        )
    mfa_path, seg_path = (Path(p) for p in args.mfa.split("::"))
    mfa = json.loads(mfa_path.read_text())
    neural = {
        (r["i"], r.get("sub", 0)): r
        for r in json.loads(args.neural.read_text())["words"]
    }
    entries = {
        (int(e["i"]), int(e.get("sub", 0))): e["text"]
        for s in json.loads(seg_path.read_text())["segments"]
        for e in s["words"]
    }

    words, gaps = [], []  # gaps[n] = (onset |diff| or None, offset |diff| or None)
    for row in mfa["words"]:
        if row["status"] != "aligned":
            continue
        k = (row["i"], row.get("sub", 0))
        n_row = neural.get(k)
        ok = n_row is not None and n_row.get("status") == "aligned"
        words.append((entries[k], row["start"], row["end"]))
        gaps.append(
            (
                abs(row["start"] - n_row["start"]) * 1000 if ok else None,
                abs(row["end"] - n_row["end"]) * 1000 if ok else None,
            )
        )

    blind = bool(args.independent and args.independent.suffix.lower() == ".csv")
    key = [] if blind else score.load_key(args.key)
    ref = score.load_independent(args.independent, key) if args.independent else key
    pairs = score.match(ref, words)
    curve = []
    for tau in TAUS:
        review = sum((g is None or g > tau) for pair in gaps for g in pair)
        accepted = {"onset": [], "offset": []}
        for n, j in pairs.items():
            for side, idx, err in (
                ("onset", 0, (words[j][1] - ref[n].start) * 1000),
                ("offset", 1, (words[j][2] - ref[n].end) * 1000),
            ):
                g = gaps[j][idx]
                if g is not None and g <= tau:
                    accepted[side].append(err)
        curve.append(
            {
                "tauMs": tau,
                "reviewShare": review / (2 * len(gaps)),
                "accepted": {side: score.stats(v) for side, v in accepted.items()},
            }
        )
    report = {
        "mfa": mfa_path.name,
        "neural": args.neural.name,
        "reference": "independent" if args.independent else "full key",
        "boundaries": 2 * len(gaps),
        "curve": curve,
    }
    args.out.write_text(json.dumps(report, indent=1))
    print(f"{mfa_path.stem} vs {args.neural.stem} ({report['reference']})")
    for c in curve:
        on, off = c["accepted"]["onset"], c["accepted"]["offset"]

        def fmt(s: dict) -> str:
            return (
                f"n {s['n']:3d} med {s['median']:3.0f} p95 {s['p95']:4.0f} >120 {s['over120Share']:4.1%}"
                if s["n"]
                else "n   0"
            )

        print(
            f"  tau {c['tauMs']:3d}  review {c['reviewShare']:5.1%} | onset {fmt(on)} | offset {fmt(off)}"
        )


if __name__ == "__main__":
    main()
