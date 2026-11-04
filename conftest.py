"""Split the pytest suite across parallel CI machines.

Set VERA_TEST_SHARD=<index>/<count> (index starts at 1) to run only that share
of the collected tests. Tests are dealt out round-robin in collection order, so
each slow module is spread across all machines. Unset, every test runs.
"""

from __future__ import annotations

import os

import pytest


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
    mine = [position % count == index - 1 for position in range(len(items))]
    drop = [item for item, keep in zip(items, mine, strict=True) if not keep]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = [item for item, keep in zip(items, mine, strict=True) if keep]
