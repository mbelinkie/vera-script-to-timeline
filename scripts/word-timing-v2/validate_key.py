"""Validate and freeze a corrected answer key (plan section 6).

Usage: validate_key.py --prefill rec-a-words.txt --corrected CORRECTED [--freeze]
  CORRECTED is an Audacity label export (.txt) or an Audition marker export (.csv).

Checks: label times in order, no overlaps, positive length, legal tags, and
that the word sequence matches the pre-fill apart from tagged additions and
reported edits. With --freeze it writes the sha256 next to the file and makes
the file read-only.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import stat
import sys
from pathlib import Path

TAGS = {"FRAG", "REP", "FILLER", "STOP"}
LABEL = re.compile(r"^(?:(?P<tag>[A-Z]+) )?(?P<word>[\w'\-]+(?:\[[^\]]+\])?)(?P<unsure>\?)?$")


def read_labels(path: Path) -> list[tuple[float, float, str]]:
    if path.suffix.lower() == ".csv":
        from audition import read_markers

        return [(s, e, name) for s, e, name, _ in read_markers(path)]
    rows = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("\\"):
            continue  # Audacity writes spectral-selection lines starting with a backslash
        parts = line.split("\t")
        if len(parts) != 3:
            sys.exit(f"line {n}: expected start<TAB>end<TAB>label")
        rows.append((float(parts[0]), float(parts[1]), parts[2].strip()))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefill", type=Path, required=True)
    parser.add_argument("--corrected", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()

    corrected = read_labels(args.corrected)
    errors = []
    for n, (s, e, text) in enumerate(corrected):
        if e <= s:
            errors.append(f"row {n + 1} '{text}': end {e:.3f} is not after start {s:.3f}")
        if n and s < corrected[n - 1][1] - 1e-6:
            errors.append(f"row {n + 1} '{text}': starts {s:.3f} before previous ends {corrected[n - 1][1]:.3f}")
        if text == "??":
            errors.append(f"row {n + 1} at {s:.3f}s: unresolved '??' marker (rename it or delete it)")
            continue
        match = LABEL.match(text)
        if not match or (match["tag"] and match["tag"] not in TAGS):
            errors.append(f"row {n + 1}: illegal label '{text}' (tags: {', '.join(sorted(TAGS))})")

    def plain(text: str) -> str:
        match = LABEL.match(text)
        return (match["word"] if match else text).casefold()

    base = [plain(t) for _, _, t in read_labels(args.prefill)]
    def is_addition(text: str) -> bool:
        match = LABEL.match(text)
        return bool(match and match["tag"] and match["tag"] != "STOP")

    words = [plain(t) for _, _, t in corrected if t != "??" and not is_addition(t)]
    edits = [op for op in difflib.SequenceMatcher(a=base, b=words, autojunk=False).get_opcodes() if op[0] != "equal"]
    tagged = sum(1 for _, _, t in corrected if is_addition(t))
    unsure = sum(1 for _, _, t in corrected if t != "??" and t.endswith("?"))

    print(f"{len(corrected)} regions; {tagged} tagged additions; {unsure} marked unsure; {len(edits)} word edits vs pre-fill; "
          f"{sum(1 for _, _, t in corrected if t.startswith('STOP '))} STOP marks")
    for op, a0, a1, b0, b1 in edits:
        print(f"  {op}: pre-fill {base[a0:a1]} -> corrected {words[b0:b1]}")
    if errors:
        print("ERRORS:\n  " + "\n  ".join(errors))
        sys.exit(1)
    if args.freeze:
        digest = hashlib.sha256(args.corrected.read_bytes()).hexdigest()
        Path(f"{args.corrected}.sha256").write_text(f"{digest}  {args.corrected.name}\n")
        os.chmod(args.corrected, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        print(f"frozen sha256 {digest}")


if __name__ == "__main__":
    main()
