"""Repository-local pytest import setup."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


@pytest.fixture(autouse=True)
def isolated_native_ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline tests must never inspect or acquire the Mac's real native owner."""
    from vera_timeline_agent import resolve_native_owner as owner

    root = tmp_path / "native-ownership"
    for name, path in {
        "OWNER_LOCK_PATH": root / "owner.lock",
        "PARENT_ACTIVE_PATH": root / "active.json",
        "ISSUE328_ACTIVE_PATH": root / "issue328.active.json",
        "OUTPUT_ATTEMPTS_ROOT": root / "output-attempts",
        "OUTPUT_TARGETS_ROOT": root / "output-targets",
        "PAUSED_OUTPUT_ROOT": root / "paused-output",
    }.items():
        monkeypatch.setattr(owner, name, path)
    monkeypatch.delenv("VERA_NATIVE_OWNER_FD", raising=False)
