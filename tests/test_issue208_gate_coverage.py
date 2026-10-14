"""Additional synthetic gate coverage after GO; no installed qualification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_issue208_review_fixes import bootstrap, capability_inputs
from test_issue208_target_identity import native, rewrite
from vera_timeline_agent import native_qualification_v2 as capability
from vera_timeline_agent import target_identity_v2 as identity


@pytest.mark.parametrize("where", ["repository", "release", "installed"])
def test_unsafe_capability_bootstrap_creates_no_protected_directory(
    tmp_path: Path,
    where: str,
) -> None:
    request, authority, installed = capability_inputs(tmp_path)
    auth = identity.ti_object(identity.ti_read(authority))
    output = {
        "repository": tmp_path / "repository/unsafe-evidence",
        "release": tmp_path / "release/unsafe-evidence",
        "installed": installed / "unsafe-evidence",
    }[where]
    auth["binding"]["evidenceDir"] = str(output)
    rewrite(authority, auth)
    req = identity.ti_object(identity.ti_read(request))
    req.update(
        binding=auth["binding"],
        authoritySha256=identity.ti_digest(identity.ti_read(authority)),
    )
    rewrite(request, req)
    roots = (tmp_path / "repository", tmp_path / "release", installed)
    before = {
        str(p): p.read_bytes() for root in roots for p in root.rglob("*") if p.is_file()
    }
    console, calls = bootstrap(installed)
    after = {
        str(p): p.read_bytes() for root in roots for p in root.rglob("*") if p.is_file()
    }
    assert calls == [] and "unavailable" in console
    assert before == after and not output.exists()


def test_request_bound_to_another_valid_v2_authority_refuses_before_getters(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir(mode=0o700)
    second.mkdir(mode=0o700)
    request, _, _ = capability_inputs(first)
    _, other_authority, _ = capability_inputs(second)
    _, other_digest = identity.ti_cap_authority(other_authority)
    req = identity.ti_object(identity.ti_read(request))
    req.update(authorityPath=str(other_authority), authoritySha256=other_digest)
    rewrite(request, req)
    resolve, _, _, _, calls = native()
    with pytest.raises(ValueError, match=r"^capability authority/request mismatch$"):
        capability.run_capability_preflight(
            resolve,
            request,
            expected_request_sha256=identity.ti_digest(identity.ti_read(request)),
        )
    assert calls == []


def test_mid_preflight_expiry_never_publishes_a_success_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_issue204_native_preflight import native as capability_native

    request, _, _ = capability_inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))
    identity.ti_cap_reserve(request, digest)
    resolve, timeline, _, calls = capability_native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    project.values.update(GetName="Synthetic project", GetUniqueId="opaque-p")
    timeline.values.update(GetName="Synthetic timeline", GetUniqueId="opaque-t")
    state = {"expired": False}
    now = datetime.now

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Clock:
            value = now(UTC) + timedelta(seconds=1801 if state["expired"] else 0)
            return cls.fromtimestamp(value.timestamp(), tz=UTC)

    monkeypatch.setattr(identity, "datetime", Clock)

    def expire() -> dict[str, str]:
        state["expired"] = True
        return {"timelineSampleRate": "48000"}

    project.values["GetSettings"] = expire
    with pytest.raises(ValueError, match=r"^stale identity result$"):
        capability.run_capability_preflight(
            resolve, request, expected_request_sha256=digest
        )
    assert "GetSettings" in calls
    assert "GetTrackCount" not in calls
    assert not list((tmp_path / "cap-evidence").glob("hashes-*"))
    assert not list((tmp_path / "cap-evidence").glob("result-*"))
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
