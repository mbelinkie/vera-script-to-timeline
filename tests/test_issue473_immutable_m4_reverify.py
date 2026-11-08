"""Synthetic-only checks for the source-pinned original #473 M4 correction.

No test may access the Producer's actual state directory or Resolve SDK.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts/issue-473-m4-immutable-reverify.py"
)
SPEC = importlib.util.spec_from_file_location("issue473_immutable_m4_reverify", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def qualified() -> dict[str, Any]:
    return {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "items": [{} for _ in range(11)],
        "tracks": [{} for _ in range(6)],
    }


def test_native_rational_rate_is_exact_and_not_string_normalized() -> None:
    MOD.correct_geometry(qualified())


@pytest.mark.parametrize(
    "change",
    [
        lambda g: g.update(rate="24000/1001"),
        lambda g: g.update(rate={"numerator": 24, "denominator": 1}),
        lambda g: g.update(rate={"numerator": 24000, "denominator": 1001, "x": 1}),
        lambda g: g.update(rate={"numerator": True, "denominator": 1001}),
        lambda g: g.update(extentFrames=True),
        lambda g: g.update(extentFrames=1408),
        lambda g: g.update(items=g["items"][:-1]),
        lambda g: g.update(tracks=g["tracks"][:-1]),
        lambda g: g.update(nativeEdited=True, rate={"numerator": 24, "denominator": 1}),
    ],
)
def test_unqualified_native_geometry_is_rejected(change: Any) -> None:
    value = qualified()
    change(value)
    with pytest.raises(ValueError, match="immutable #473 M4 correction refused"):
        MOD.correct_geometry(value)


def test_audit_is_created_once_and_tampering_never_overwritten(
    tmp_path: Path,
) -> None:
    import vera_timeline_agent.resolve_test_queue as queue

    audit = tmp_path / "audit.json"
    expected = {"schema": "read-only", "receipt": "original"}
    MOD._one_time_audit(audit, expected, queue.canonical)
    assert audit.read_bytes() == queue.canonical(expected)
    MOD._one_time_audit(audit, expected, queue.canonical)
    with pytest.raises(ValueError, match="previous audit differs"):
        MOD._one_time_audit(
            audit, {**expected, "receipt": "fabricated"}, queue.canonical
        )
    assert audit.read_bytes() == queue.canonical(expected)
