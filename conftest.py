"""Split the pytest suite across parallel CI machines.

Set VERA_TEST_SHARD=<index>/<count> (index starts at 1) to run only that share
of the collected tests. Tests are balanced by the measured durations in
tests/test-durations.json ({node id: seconds}, from CI's --durations output);
unlisted tests count as fast. Stale timings only cost speed, never coverage.
Unset, every test runs.
"""

from __future__ import annotations

import json
import os

import pytest

from ci_shards import DURATIONS, shard_assignment


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    spec = os.environ.get("VERA_TEST_SHARD", "").strip()
    if not spec:
        return
    index_text, _, count_text = spec.partition("/")
    index, count = int(index_text), int(count_text)
    if not 1 <= index <= count:
        raise pytest.UsageError(
            f"VERA_TEST_SHARD must be <index>/<count>, got {spec!r}"
        )
    durations = json.loads(DURATIONS.read_text()) if DURATIONS.exists() else {}
    shard_of = shard_assignment([item.nodeid for item in items], durations, count)
    mine = [shard == index - 1 for shard in shard_of]
    drop = [item for item, keep in zip(items, mine, strict=True) if not keep]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = [item for item, keep in zip(items, mine, strict=True) if keep]
