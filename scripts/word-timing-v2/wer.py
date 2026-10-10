"""Word error rate of T-C transcripts against a reference token list.

Both sides go through textnorm. Sound events (type "event") are dropped. The
script prints substitutions, deletions and insertions so verbatim-heavy and
clean-up-heavy recognisers can be told apart.

Usage: wer.py --reference tokens.json T-C-a.json [T-C-b.json ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textnorm import normalise_token


def edit_ops(ref: list[str], hyp: list[str]) -> tuple[int, int, int]:
    rows, cols = len(ref) + 1, len(hyp) + 1
    cost = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        cost[i][0] = i
    for j in range(cols):
        cost[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost[i][j] = min(cost[i - 1][j] + 1, cost[i][j - 1] + 1,
                             cost[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    subs = dels = ins = 0
    i, j = len(ref), len(hyp)
    while i or j:
        if i and j and cost[i][j] == cost[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            subs += ref[i - 1] != hyp[j - 1]
            i, j = i - 1, j - 1
        elif i and cost[i][j] == cost[i - 1][j] + 1:
            dels, i = dels + 1, i - 1
        else:
            ins, j = ins + 1, j - 1
    return subs, dels, ins


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("candidates", type=Path, nargs="+")
    args = parser.parse_args()
    ref = [t for tok in json.loads(args.reference.read_text()) for t in normalise_token(tok)]
    for path in args.candidates:
        tc = json.loads(path.read_text())
        hyp = [t for w in tc["words"] if w.get("type") != "event" for t in normalise_token(str(w["text"]))]
        s, d, i = edit_ops(ref, hyp)
        print(f'{tc["source"]:18s} WER {(s + d + i) / len(ref):6.1%}  sub {s:3d} del {d:3d} ins {i:3d}  '
              f'(ref {len(ref)}, hyp {len(hyp)})')


if __name__ == "__main__":
    main()
