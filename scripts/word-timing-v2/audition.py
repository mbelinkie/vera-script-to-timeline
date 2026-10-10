"""Adobe Audition marker CSV support for the answer-key pass.

Audition's Markers panel reads and writes tab-separated, UTF-8 (BOM) files:
  Name<TAB>Start<TAB>Duration<TAB>Time Format<TAB>Type<TAB>Description
with "decimal" times such as 0:08.965 or 1:02:03.250. This format was
confirmed by a round trip through Audition on 2026-10-09.

Usage:
  audition.py export --words REC-words.txt --check REC-check.txt --out REC-markers.csv

Each word becomes a range marker whose Description carries its check flags.
Check items that are not words ("SPEECH WITH NO WORD", "MISSING") become extra
markers named `??`. The Producer renames those (FRAG/REP/FILLER/word) or
deletes them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

PLACEHOLDER = "??"
HEADER = ["Name", "Start", "Duration", "Time Format", "Type", "Description"]


def fmt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}" if h else f"{m}:{s:02d}.{ms:03d}"


def parse_time(text: str) -> float:
    parts = [float(p) for p in text.strip().split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def read_markers(path: Path) -> list[tuple[float, float, str, str]]:
    """Return (start, end, name, description) rows from an Audition marker CSV."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = lines[0].split("\t")
    if header[:3] != HEADER[:3]:
        raise SystemExit(f"{path.name}: not an Audition marker file (header {header})")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = (line.split("\t") + [""] * 6)[:6]
        if cols[3].strip() and cols[3].strip() != "decimal":
            raise SystemExit(f"{path.name}: time format '{cols[3]}' unsupported; set the Markers panel to Decimal")
        start = parse_time(cols[1])
        rows.append((start, start + parse_time(cols[2]), cols[0].strip(), cols[5].strip()))
    return sorted(rows, key=lambda r: (r[0], r[1]))


def export(words: Path, check: Path, out: Path) -> None:
    flags: dict[tuple[str, str], str] = {}
    extras = []
    for line in check.read_text().splitlines():
        start, end, text = line.split("\t", 2)
        if text.startswith(("SPEECH WITH NO WORD", "MISSING")):
            extras.append((float(start), max(float(end), float(start) + 0.05), PLACEHOLDER, text))
        else:
            flags[(start, end)] = text.split(": ", 1)[1] if ": " in text else text
    rows = []
    for line in words.read_text().splitlines():
        start, end, label = line.split("\t")
        rows.append((float(start), float(end), label, flags.get((start, end), "")))
    rows += extras
    rows.sort(key=lambda r: (r[0], r[1]))
    body = ["\t".join(HEADER)] + [
        "\t".join([name, fmt(s), fmt(e - s), "decimal", "Cue", desc]) for s, e, name, desc in rows]
    out.write_text("\r\n".join(body) + "\r\n", encoding="utf-8-sig")
    print(f"{len(rows)} markers ({len(extras)} '{PLACEHOLDER}' placeholders, "
          f"{sum(1 for r in rows if r[3] and r[2] != PLACEHOLDER)} flagged words) -> {out.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    for name in ("--words", "--check", "--out"):
        ex.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    export(args.words, args.check, args.out)


if __name__ == "__main__":
    main()
