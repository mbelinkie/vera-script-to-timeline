"""Make a blind timing set: words to time from scratch, with no pre-fill timing.

Words are drawn from a recogniser transcript, stratified by the recogniser's
own gaps: phrase_edge (700 ms or more of silence on either side),
pause_adjacent (150 ms or more) and connected. Chosen words are at least
MIN_SPACING_SEC apart. Each becomes an Audition range marker covering a
search window of about WINDOW_SEC, centred near the word, with random edges so
the window hints nothing about the word's boundaries. The Producer drags the
window's edges onto the word and keeps the name.

Usage: blind_set.py --tc T-C-x.json --seed N --out blind.csv --manifest blind.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from audition import HEADER, fmt
from textnorm import normalise_token

QUOTAS = {"phrase_edge": 15, "pause_adjacent": 10, "connected": 15}
MIN_SPACING_SEC = 2.5
WINDOW_SEC = 2.4
JITTER_SEC = 0.4
CONTEXT_WORDS = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tc", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    words = [
        w
        for w in json.loads(args.tc.read_text())["words"]
        if w.get("type") != "event" and len(normalise_token(str(w["text"]))) == 1
    ]

    def stratum(n: int) -> str:
        before = words[n]["start"] - words[n - 1]["end"] if n else 99.0
        after = words[n + 1]["start"] - words[n]["end"] if n + 1 < len(words) else 99.0
        gap = max(before, after)
        return (
            "phrase_edge"
            if gap >= 0.7
            else "pause_adjacent"
            if gap >= 0.15
            else "connected"
        )

    pools = {
        name: [n for n in range(len(words)) if stratum(n) == name] for name in QUOTAS
    }
    chosen: list[int] = []
    for name, quota in QUOTAS.items():
        candidates = pools[name][:]
        rng.shuffle(candidates)
        taken = 0
        for n in candidates:
            mid = (words[n]["start"] + words[n]["end"]) / 2
            if all(
                abs(mid - (words[c]["start"] + words[c]["end"]) / 2) >= MIN_SPACING_SEC
                for c in chosen
            ):
                chosen.append(n)
                taken += 1
                if taken == quota:
                    break
        if taken < quota:
            raise SystemExit(
                f"only {taken} of {quota} {name} words could be spaced out"
            )
    chosen.sort(key=lambda n: words[n]["start"])

    rows, manifest = [], []
    for number, n in enumerate(chosen, 1):
        w = words[n]
        mid = (w["start"] + w["end"]) / 2 + rng.uniform(-JITTER_SEC, JITTER_SEC)
        start = max(
            0.0, mid - WINDOW_SEC / 2 + rng.uniform(-JITTER_SEC, JITTER_SEC) / 2
        )
        end = mid + WINDOW_SEC / 2 + rng.uniform(-JITTER_SEC, JITTER_SEC) / 2
        before = " ".join(str(x["text"]) for x in words[max(0, n - CONTEXT_WORDS) : n])
        after = " ".join(str(x["text"]) for x in words[n + 1 : n + 1 + CONTEXT_WORDS])
        name = f"{number:02d} {normalise_token(str(w['text']))[0]}"
        rows.append(
            [
                name,
                fmt(start),
                fmt(end - start),
                "decimal",
                "Cue",
                f"…{before} [[{w['text']}]] {after}…",
            ]
        )
        manifest.append(
            {
                "number": number,
                "text": normalise_token(str(w["text"]))[0],
                "stratum": stratum(n),
                "tcIndex": n,
                "windowStart": round(start, 3),
                "windowEnd": round(end, 3),
            }
        )
    body = ["\t".join(HEADER)] + ["\t".join(r) for r in rows]
    args.out.write_text("\r\n".join(body) + "\r\n", encoding="utf-8-sig")
    args.manifest.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "source": args.tc.name,
                "quotas": QUOTAS,
                "minSpacingSec": MIN_SPACING_SEC,
                "windowSec": WINDOW_SEC,
                "jitterSec": JITTER_SEC,
                "words": manifest,
            },
            indent=1,
        )
    )
    print(
        f"{len(rows)} blind words: "
        + ", ".join(f"{k} {sum(m['stratum'] == k for m in manifest)}" for k in QUOTAS)
    )


if __name__ == "__main__":
    main()
