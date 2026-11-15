"""Prepare synthetic scripts where the first row changes length.

Reuses #327's ``prepare.py`` with different variants, so that a later row
has to move: ``original`` is rows B then A at 96 frames each, ``longer``
makes row B 144 frames with a new, longer tone, and ``same`` swaps row B's
picture without changing any length.

Usage, from the repository root, with PYTHONPATH set to that root:
uv run --frozen python docs/investigations/issue-104/prepare_rows.py <new-folder>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "issue-327"))
import prepare

prepare.VARIANTS = {
    "original": (("B", "A"), "B", 96),
    "longer": (("B", "A"), "B", 144),
    "same": (("B", "A"), "C", 96),
}

if __name__ == "__main__":
    prepare.prepare(Path(sys.argv[1]).resolve())
