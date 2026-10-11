"""European-language check: Parakeet and YouTube auto-captions vs human captions.

For public TEDx talks whose uploaders supplied same-language subtitles, the
human captions are the reference (they may be lightly edited, so absolute WER
is pessimistic; both systems are scored against the same reference). Text is
normalised language-neutrally: lower case, Unicode letters/digits/apostrophes
kept, everything else a separator. Prints aggregates only.

Usage: eu_wer.py DIR [DIR ...]   (each DIR holds manual.<lang>.json3,
       auto.<lang>.vtt and T-C-parakeet.json)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def norm(text: str) -> list[str]:
    return WORD.findall(text.replace("’", "'").casefold())


def json3_text(path: Path) -> str:
    events = json.loads(path.read_text())["events"]
    return " ".join("".join(s.get("utf8", "") for s in e.get("segs", [])) for e in events)


def vtt_text(path: Path) -> str:
    """Auto-caption VTT: keep each cue's new (tagged) line; drop rolling repeats."""
    out, last = [], None
    for line in path.read_text().splitlines():
        if not line.strip() or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean != last and ("<c>" in line or "<" not in line):
            if last is None or not last.endswith(clean):
                out.append(clean)
            last = clean
    return " ".join(out)


def wer(ref: list[str], hyp: list[str]) -> tuple[float, int, int, int]:
    """Word error rate with (substitutions, deletions, insertions)."""
    prev = [(j, 0, 0, j) for j in range(len(hyp) + 1)]  # (cost, sub, del, ins)
    for i in range(1, len(ref) + 1):
        cur = [(i, 0, i, 0)]
        for j in range(1, len(hyp) + 1):
            c, s_, d_, n_ = prev[j - 1]
            miss = ref[i - 1] != hyp[j - 1]
            best = (c + miss, s_ + miss, d_, n_)
            c, s_, d_, n_ = prev[j]
            best = min(best, (c + 1, s_, d_ + 1, n_))
            c, s_, d_, n_ = cur[j - 1]
            best = min(best, (c + 1, s_, d_, n_ + 1))
            cur.append(best)
        prev = cur
    cost, s_, d_, n_ = prev[-1]
    return cost / max(1, len(ref)), s_, d_, n_


def window_report(d: Path, start_s: float = 60.0, end_s: float = 300.0) -> None:
    """Same 4-minute window for every system (whisper ran only on this window)."""
    lang = d.name.split("-")[0]
    events = json.loads(next(d.glob("manual.*.json3")).read_text())["events"]
    ref = norm(" ".join("".join(x.get("utf8", "") for x in e.get("segs", []))
                        for e in events if start_s * 1000 <= e.get("tStartMs", -1) < end_s * 1000))
    tc = json.loads((d / "T-C-parakeet.json").read_text())
    para = norm(" ".join(str(w["text"]) for w in tc["words"] if start_s <= w["start"] < end_s))
    out = [f"{lang} window {start_s:.0f}-{end_s:.0f} s: reference {len(ref)} words"]
    systems = [("Parakeet (auto language)", para)]
    wj = d / "whisper-win.json"
    if wj.exists():
        text = " ".join(seg["text"] for seg in json.loads(wj.read_text())["transcription"])
        systems.append((f"whisper turbo (-l {lang})", norm(text)))
    for name, hyp in systems:
        e, s_, dl, ins = wer(ref, hyp)
        out.append(f"   {name:26s} WER {100 * e:5.1f}%  (sub {s_}, del {dl}, ins {ins})")
    print("\n".join(out))


def main() -> None:
    if sys.argv[1] == "--window":
        for d in map(Path, sys.argv[2:]):
            window_report(d)
        return
    for d in map(Path, sys.argv[1:]):
        lang = d.name.split("-")[0]
        ref = norm(json3_text(next(d.glob("manual.*.json3"))))
        auto = norm(vtt_text(next(d.glob("auto.*.vtt"))))
        tc = json.loads((d / "T-C-parakeet.json").read_text())
        para = norm(" ".join(str(w["text"]) for w in tc["words"]))
        wall = tc.get("provenance", {}).get("wallSeconds")
        print(f"{lang}: reference {len(ref)} words")
        for name, hyp in (("YouTube auto-captions", auto), ("Parakeet (local)", para)):
            e, s, dl, ins = wer(ref, hyp)
            print(f"   {name:22s} WER {100 * e:5.1f}%  (sub {s}, del {dl}, ins {ins}; {len(hyp)} words)")
        if wall:
            print(f"   Parakeet wall time {wall:.0f} s on this Intel Mac")


if __name__ == "__main__":
    main()
