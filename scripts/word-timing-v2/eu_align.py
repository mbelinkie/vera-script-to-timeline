"""European-language alignment check: do MFA and Qwen agree on Canary's text?

No per-word answer keys exist for these clips, so this measures agreement
between two structurally different aligners on the same words and segments
(the same signal VERA's `needs_review` flag uses), next to the English
baseline from recordings A and B where agreement is known to track accuracy.

Steps per clip (4-minute window): Canary's per-VAD-segment text -> language-
aware normalisation (lower case, punctuation stripped, hyphens split,
numerals spelled in that language via num2words) -> one SEGMENTS file used by
both aligners -> compare boundaries by (i, sub).

Usage:
  eu_align.py segments --canary canary-win.json --lang de --audio-name win-16k.wav --out seg.json
  eu_align.py compare --segments seg.json --a mfa.json --b qwen.json
  eu_align.py baseline   (English: recordings A and B, ElevenLabs MFA-G vs Qwen)
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from num2words import num2words

WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*|\d+")
NUM2WORDS_LANG = {"de": "de", "fr": "fr", "it": "it", "sv": "sv"}


def normalise(token: str, lang: str) -> list[str]:
    out: list[str] = []
    for part in WORD.findall(token.replace("’", "'").casefold()):
        if part.isdigit():
            spoken = num2words(int(part), lang=NUM2WORDS_LANG.get(lang, "en"))
            out += [w for w in re.split(r"[\s\-,]+", spoken.casefold()) if w]
        else:
            out.append(part)
    return out


def build_segments(canary: dict, lang: str, audio_name: str) -> dict:
    segments, i = [], 0
    for n, seg in enumerate(canary["perSegment"]):
        words = []
        for token in seg["text"].split():
            spoken = normalise(token, lang)
            for sub, text in enumerate(spoken):
                entry = {"i": i, "text": text, "display": token}
                if len(spoken) > 1:
                    entry["sub"] = sub
                words.append(entry)
            if spoken:
                i += 1
        if words:
            segments.append(
                {
                    "id": f"s{n:03d}",
                    "start": seg["start"],
                    "end": seg["end"],
                    "words": words,
                }
            )
    return {"audio": audio_name, "offsetSec": 0.0, "segments": segments}


def compare(a: dict, b: dict, tau_ms: float = 70.0) -> dict:
    ra = {(r["i"], r.get("sub", 0)): r for r in a["words"]}
    rb = {(r["i"], r.get("sub", 0)): r for r in b["words"]}
    keys = sorted(set(ra) | set(rb))
    aligned_a = sum(ra[k]["status"] == "aligned" for k in keys if k in ra)
    aligned_b = sum(rb[k]["status"] == "aligned" for k in keys if k in rb)
    diffs = []
    for k in keys:
        x, y = ra.get(k), rb.get(k)
        if x and y and x["status"] == y["status"] == "aligned":
            diffs += [
                abs(x["start"] - y["start"]) * 1000,
                abs(x["end"] - y["end"]) * 1000,
            ]
    q = sorted(diffs)
    return {
        "units": len(keys),
        "alignedA": aligned_a,
        "alignedB": aligned_b,
        "boundaries": len(q),
        "agreeShare": sum(d <= tau_ms for d in q) / len(q) if q else 0.0,
        "medianMs": statistics.median(q) if q else None,
        "p90Ms": q[int(0.9 * (len(q) - 1))] if q else None,
        "over300Share": sum(d > 300 for d in q) / len(q) if q else 0.0,
    }


def line(label: str, r: dict) -> str:
    return (
        f"{label:34s} units {r['units']:4d}  aligned A {r['alignedA']:4d} B {r['alignedB']:4d} | "
        f"agree within 70 ms {100 * r['agreeShare']:5.1f}%  median {r['medianMs']:5.0f} ms  "
        f"p90 {r['p90Ms']:5.0f} ms  >300 ms {100 * r['over300Share']:4.1f}%"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("segments")
    s.add_argument("--canary", type=Path, required=True)
    s.add_argument("--lang", required=True)
    s.add_argument("--audio-name", required=True)
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--label", required=True)
    c.add_argument("--a", type=Path, required=True)
    c.add_argument("--b", type=Path, required=True)
    sub.add_parser("baseline")
    args = ap.parse_args()
    if args.cmd == "segments":
        seg = build_segments(
            json.loads(args.canary.read_text()), args.lang, args.audio_name
        )
        args.out.write_text(json.dumps(seg, ensure_ascii=False, indent=1))
        print(
            f"{args.out.name}: {len(seg['segments'])} segments, {sum(len(x['words']) for x in seg['segments'])} units"
        )
    elif args.cmd == "compare":
        print(
            line(
                args.label,
                compare(json.loads(args.a.read_text()), json.loads(args.b.read_text())),
            )
        )
    else:
        data = Path.home() / ".local/share/vera/word-timing-v2"
        for rec, mfa in (
            ("a", "T-CR-eleven-or__A-MFA-G-english_us_arpa.json"),
            ("b", "T-CR-eleven-or__A-MFA-english_us_arpa.json"),
        ):
            d = data / f"rec-{rec}/runs"
            r = compare(
                json.loads((d / mfa).read_text()),
                json.loads((d / "T-CR-eleven-or__A-QWEN.json").read_text()),
            )
            print(line(f"English rec-{rec} (MFA vs Qwen)", r))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
