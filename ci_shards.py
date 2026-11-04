"""Balanced split of the pytest suite for parallel CI machines (see conftest.py)."""

from __future__ import annotations

from pathlib import Path

DURATIONS = Path(__file__).parent / "tests" / "test-durations.json"
UNLISTED_SECONDS = 0.3


def shard_assignment(
    node_ids: list[str], durations: dict[str, float], count: int
) -> list[int]:
    """Longest-first greedy split; deterministic for identical collections."""
    order = sorted(
        range(len(node_ids)),
        key=lambda i: (-durations.get(node_ids[i], UNLISTED_SECONDS), i),
    )
    loads = [0.0] * count
    shard_of = [0] * len(node_ids)
    for i in order:
        target = min(range(count), key=lambda s: (loads[s], s))
        shard_of[i] = target
        loads[target] += durations.get(node_ids[i], UNLISTED_SECONDS)
    return shard_of
