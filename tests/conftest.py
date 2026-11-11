"""Repository-local pytest import setup."""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


# A #208 test performs genuine strict wall/monotonic comparisons. Under the
# Linux VM its realtime clock can jump backward while monotonic advances.
# Keep the production rollback guard intact and use one monotonic-derived
# UTC wall clock only inside these synthetic tests (including their isolated
# installed-bootstrap subprocesses).
ISSUE208_BOOTSTRAP_CLOCK = """
import datetime,os,time
_offset=float(os.environ["VERA_ISSUE208_TEST_WALL_OFFSET"])
class _StableDateTime(datetime.datetime):
    @classmethod
    def now(cls,tz=None):
        return cls.fromtimestamp(time.monotonic()+_offset,tz=tz)
datetime.datetime=_StableDateTime
assert datetime.datetime.__name__=="_StableDateTime"
"""


@pytest.fixture(autouse=True)
def stable_issue208_synthetic_clock(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = (
        "test_issue208_target_identity",
        "test_issue208_review_fixes",
        "test_issue208_gate_coverage",
    )
    if request.module.__name__.split(".")[-1] not in names:
        return
    real_monotonic = time.monotonic
    utc_offset = datetime.now(UTC).timestamp() - real_monotonic()

    class StableDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> StableDateTime:
            return cls.fromtimestamp(real_monotonic() + utc_offset, tz=tz)

    monkeypatch.setenv("VERA_ISSUE208_TEST_WALL_OFFSET", repr(utc_offset))
    from vera_timeline_agent import native_qualification_v2 as capability
    from vera_timeline_agent import target_identity_v2 as identity
    from vera_timeline_agent import workflow_v2_cli

    for module in (identity, capability, workflow_v2_cli):
        monkeypatch.setattr(module, "datetime", StableDateTime)
    # Helpers are imported across the three test modules. Their own
    # construction timestamps must use the same origin as the tested runtime.
    for name in names:
        test_module = sys.modules.get(name)
        if test_module is not None and hasattr(test_module, "datetime"):
            monkeypatch.setattr(test_module, "datetime", StableDateTime)


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
