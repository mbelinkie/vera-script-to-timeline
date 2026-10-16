"""Link accurate transcript words to retained timing, without a new audio alignment."""

from __future__ import annotations

from typing import Any

Record = dict[str, Any]


def link_word_timing(accurate: list[str], retained: list[Record]) -> list[Record]:
    """Transfer only invariant exact matches across ALL optimal edit alignments.

    Coarse Producer clocks and highlight labels are deliberately not inputs.
    This is textual correspondence to existing acoustic estimates, not new
    forced alignment, verification against sound, or missing-time interpolation.
    """
    actual = [w["token"] for w in retained]
    n, m = len(accurate), len(actual)
    forward = [[0] * (m + 1) for _ in range(n + 1)]
    backward = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        forward[i][0], backward[i][m] = i, n - i
    for j in range(m + 1):
        forward[0][j], backward[n][j] = j, m - j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            forward[i][j] = min(
                forward[i - 1][j] + 1,
                forward[i][j - 1] + 1,
                forward[i - 1][j - 1] + (accurate[i - 1] != actual[j - 1]),
            )
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            backward[i][j] = min(
                backward[i + 1][j] + 1,
                backward[i][j + 1] + 1,
                backward[i + 1][j + 1] + (accurate[i] != actual[j]),
            )
    distance = forward[n][m]
    result = []
    for i, token in enumerate(accurate):
        matches = []
        nonexact = False
        for j in range(m + 1):
            if forward[i][j] + 1 + backward[i + 1][j] == distance:
                nonexact = True
            if (
                j < m
                and forward[i][j] + (token != actual[j]) + backward[i + 1][j + 1]
                == distance
            ):
                if token == actual[j]:
                    matches.append(j)
                else:
                    nonexact = True
        unique = len(matches) == 1 and not nonexact
        w = retained[matches[0]] if unique else {}
        result.append(
            {
                "accurate_index": i,
                "retained_index": matches[0] if unique else None,
                "textual_correspondence": "unique_exact"
                if unique
                else "ambiguous_or_changed",
                "start": w.get("start"),
                "end": w.get("end"),
                "precision": w.get("precision", "missing"),
                "acoustically_verified": False,
            }
        )
    return result
