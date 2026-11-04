"""The CI shard split runs every test exactly once and balances measured time."""

from __future__ import annotations

from ci_shards import shard_assignment


def test_every_test_lands_in_exactly_one_shard() -> None:
    ids = [f"t{i}" for i in range(50)]
    shards = shard_assignment(ids, {"t3": 100.0, "t7": 90.0}, 6)
    assert len(shards) == len(ids)
    assert set(shards) <= set(range(6))


def test_slow_tests_are_spread_across_shards() -> None:
    ids = ["a", "b", "c", "d", "e", "f"]
    durations = {name: 60.0 for name in ids}
    assert sorted(shard_assignment(ids, durations, 3)) == [0, 0, 1, 1, 2, 2]


def test_assignment_is_deterministic() -> None:
    ids = [f"t{i}" for i in range(30)]
    durations = {"t1": 5.0, "t20": 9.0}
    assert shard_assignment(ids, durations, 4) == shard_assignment(ids, durations, 4)
