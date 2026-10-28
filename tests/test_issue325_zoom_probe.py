"""Probe boundary checks, separate from the retained real Resolve evidence."""

import hashlib
from pathlib import Path

import pytest

from scripts.issue325_zoom_probe import PROFILE, RUNTIME, probe_properties

SOURCE = Path(__file__).resolve().parents[1] / "docs/investigations/issue-325/grid.png"


def request_for(source: Path) -> dict[str, object]:
    return {
        "profile": PROFILE,
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "durationFrames": 48,
        "motion": "native-default",
        "ease": 0,
        "framing": "fit",
        "background": "black",
    }


def test_none_is_explicit_and_source_change_refuses(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.png"
    source.write_bytes(SOURCE.read_bytes())
    request = request_for(source)
    request.update(motion="None", framing="fill")
    assert probe_properties(request, source, RUNTIME, 48) == {
        "DynamicZoomEnabled": False,
        "DynamicZoomEase": 0,
        "Scaling": 3,
    }
    with pytest.raises(ValueError, match="requested duration"):
        probe_properties(request, source, RUNTIME, 120)
    request["durationFrames"] = 144
    with pytest.raises(ValueError, match="rendered matrix"):
        probe_properties(request, source, RUNTIME, 144)
    request["durationFrames"] = 48
    source.write_bytes(b"synthetic source v2")
    with pytest.raises(ValueError, match="stale source"):
        probe_properties(request, source, RUNTIME, 48)
    request["sourceSha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="stale source"):
        probe_properties(request, source, RUNTIME, 48)
    source.unlink()
    with pytest.raises(ValueError, match="stale source"):
        probe_properties(request, source, RUNTIME, 48)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("profile", "older-profile"),
        ("durationFrames", True),
        ("durationFrames", 49),
        ("ease", 99),
        ("ease", 1),
        ("ease", 2),
        ("ease", 3),
        ("ease", True),
        ("motion", "custom"),
        ("framing", "contain-with-no-crop"),
        ("framing", "stretch"),
        ("background", "blue"),
        ("startFocus", [0.75, 0.3]),
        ("endFocus", [0.25, 0.7]),
    ],
)
def test_unsupported_request_refuses_before_application(
    tmp_path: Path, field: str, value: object
) -> None:
    source = tmp_path / "synthetic.png"
    source.write_bytes(SOURCE.read_bytes())
    request = request_for(source)
    request[field] = value
    with pytest.raises(ValueError):
        probe_properties(request, source, RUNTIME, 48)


def test_other_edition_cannot_inherit_studio_qualification(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.png"
    source.write_bytes(SOURCE.read_bytes())
    with pytest.raises(ValueError, match="runtime/profile"):
        probe_properties(
            request_for(source), source, ("DaVinci Resolve", "21.1.1.10"), 48
        )
