"""Resolve `needs_review` boundaries automatically from the audio.

The Producer never reviews words. A flagged boundary only matters where VERA
cuts or anchors, and most can be settled by measuring the audio between the
two aligners' candidate times:

- onset: if the gap between the earlier and later candidate is quiet, speech
  cannot start before the later one, so take it (this is the study's main MFA
  failure: a short word moved onto a breath 0.5-2.5 s early); otherwise take
  the earlier (outer) candidate so speech is never clipped;
- offset: mirror image (quiet gap -> earlier end; otherwise the later end);
- a disagreement over LARGE_MS that is not a quiet gap: take whichever
  candidate is closer to the recogniser's own word anchor (the partner when
  there is no anchor);
- no partner time: keep the primary time and leave the edge unresolved.

"Quiet" = at least QUIET_SHARE of the 10 ms windows in the gap at or below
QUIET_DB dBFS RMS (the #53 cut gate). Resolutions never invent times: the
result is always one of the two aligners' candidates. Unresolved edges are
the only ones that may surface to a person, as a listen-check on a cut.
"""

from __future__ import annotations

import array
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Json = dict[str, Any]

QUIET_DB = -40.0
QUIET_SHARE = 0.9
WINDOW_MS = 10
LARGE_MS = 300
Method = Literal[
    "agreed",
    "quiet_gap_inner",
    "anchor_tiebreak",
    "partner_large_gap",
    "outer_edge",
    "unresolved",
]


@dataclass(frozen=True)
class Resolution:
    token_index: int
    sub: int
    side: Literal["onset", "offset"]
    ms: int
    method: Method


class Loudness:
    """10 ms RMS envelope of a 16-bit mono WAV, in dBFS."""

    def __init__(self, wav: Path) -> None:
        with wave.open(str(wav)) as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError("expected 16-bit mono WAV")
            rate, frames = w.getframerate(), w.readframes(w.getnframes())
        samples = array.array("h", frames)
        step = rate * WINDOW_MS // 1000
        self.db: list[float] = []
        for i in range(0, len(samples), step):
            chunk = samples[i : i + step]
            power = sum(x * x for x in chunk) / max(1, len(chunk))
            self.db.append(10 * math.log10(power / 32768**2) if power > 0 else -120.0)

    def quiet(self, start_ms: int, end_ms: int) -> bool:
        a, b = (
            start_ms // WINDOW_MS,
            max(start_ms // WINDOW_MS + 1, end_ms // WINDOW_MS),
        )
        span = self.db[a:b]
        return (
            bool(span) and sum(v <= QUIET_DB for v in span) / len(span) >= QUIET_SHARE
        )


def resolve(
    alignment: Json, loudness: Loudness, recognition: Json | None = None
) -> list[Resolution]:
    """One resolution per boundary in the alignment's agreement block.

    `recognition` supplies the recogniser's own (coarse) word anchors, used as
    a tie-breaker for large disagreements.
    """
    anchors: dict[int, tuple[int | None, int | None]] = {}
    if recognition is not None:
        anchors = {
            t["index"]: (t["anchorStartMs"], t["anchorEndMs"])
            for t in recognition["tokens"]
        }
    if "agreement" not in alignment:
        raise ValueError("alignment has no agreement block")
    words = {(w["tokenIndex"], w["sub"]): w for w in alignment["words"]}
    out = []
    for b in alignment["agreement"]["boundaries"]:
        w = words[(b["tokenIndex"], b["sub"])]
        side = b["side"]
        mine = w["startMs"] if side == "onset" else w["endMs"]
        if b["verdict"] == "accepted":
            out.append(Resolution(b["tokenIndex"], b["sub"], side, mine, "agreed"))
            continue
        if b["deltaMs"] is None:
            out.append(Resolution(b["tokenIndex"], b["sub"], side, mine, "unresolved"))
            continue
        partner = mine - b["deltaMs"]
        lo, hi = min(mine, partner), max(mine, partner)
        if loudness.quiet(lo, hi):
            ms, method = (hi if side == "onset" else lo), "quiet_gap_inner"
        elif abs(b["deltaMs"]) > LARGE_MS:
            # A large disagreement means one aligner is grossly wrong. The
            # recogniser's own anchor is coarse but never seconds off, so take
            # whichever candidate is closer to it. Held-out check (5 pipelines x
            # 2 recordings): edges > 300 ms off fell from 14-49 to 0-7 per
            # pipeline, with 1-3 edges made worse. Without an anchor, prefer the
            # partner (closer on 28/33 large gaps on recording A).
            a = anchors.get(b["tokenIndex"], (None, None))[0 if side == "onset" else 1]
            if a is not None:
                ms = mine if abs(mine - a) <= abs(partner - a) else partner
                method = "anchor_tiebreak"
            else:
                ms, method = partner, "partner_large_gap"
        else:
            ms, method = (lo if side == "onset" else hi), "outer_edge"
        out.append(Resolution(b["tokenIndex"], b["sub"], side, ms, method))  # type: ignore[arg-type]
    return _keep_intervals_valid(out, words, alignment["words"])


def _keep_intervals_valid(
    resolutions: list[Resolution], words: dict[tuple[int, int], Json], order: list[Json]
) -> list[Resolution]:
    """Never emit an inverted word or one overlapping its neighbour.

    Edges are chosen independently, so a word can end up with onset >= offset,
    or two neighbours can overlap. Each offending word falls back to the primary
    aligner's own times and is marked unresolved (a listen-check), rather than
    looking resolved. For an overlap both neighbours fall back, since either
    moved edge may be the wrong one; falling back can expose a new overlap, so
    the check repeats until the whole sequence is valid (the primary times
    themselves never overlap, so this terminates).
    """
    by_unit: dict[tuple[int, int], dict[str, Resolution]] = {}
    for r in resolutions:
        by_unit.setdefault((r.token_index, r.sub), {})[r.side] = r
    bad: set[tuple[int, int]] = set()
    while True:
        found: set[tuple[int, int]] = set()
        prev: tuple[tuple[int, int], int] | None = None
        for w in order:
            key = (w["tokenIndex"], w["sub"])
            if w.get("status", "acoustic") != "acoustic" or w["startMs"] is None:
                continue
            sides = {} if key in bad else by_unit.get(key, {})
            onset = sides["onset"].ms if "onset" in sides else w["startMs"]
            offset = sides["offset"].ms if "offset" in sides else w["endMs"]
            if onset >= offset:
                found.add(key)
            if prev is not None and onset < prev[1]:
                found |= {key, prev[0]}
            prev = (key, offset)
        found -= bad
        if not found:
            break
        bad |= found
    if not bad:
        return resolutions
    out = []
    for r in resolutions:
        if (r.token_index, r.sub) in bad and r.method != "agreed":
            w = words[(r.token_index, r.sub)]
            primary = w["startMs"] if r.side == "onset" else w["endMs"]
            out.append(Resolution(r.token_index, r.sub, r.side, primary, "unresolved"))
        else:
            out.append(r)
    return out
