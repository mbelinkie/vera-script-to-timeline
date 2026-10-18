"""Complete 25 fps source clips for bounded native endpoint renders."""

from fractions import Fraction
from pathlib import Path
from typing import Literal

from issue178_qualification_fixture import (
    _CASES,
    QualificationCase,
    _ClipSpec,
    prepare_qualification_case,
)


def prepare_endpoint_case(
    root: Path,
    seconds: int,
    policy: Literal["full", "quiet"],
) -> QualificationCase:
    if seconds not in {3, 10} or policy not in {"full", "quiet"}:
        raise ValueError("unsupported issue249 endpoint case")
    name = f"issue249-{seconds}s-{policy}"
    specs = (
        _ClipSpec(
            f"endpoint-{seconds}s-{policy}",
            Fraction(25),
            seconds * 25,
            audio_policy=policy,
        ),
    )
    _CASES[name] = specs
    try:
        return prepare_qualification_case(root, name)
    finally:
        del _CASES[name]
