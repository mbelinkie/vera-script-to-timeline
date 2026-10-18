"""Four complete 25 fps source clips for one bounded native endpoint render."""

from fractions import Fraction
from pathlib import Path
from typing import Literal

from issue178_qualification_fixture import (
    _CASES,
    QualificationCase,
    _ClipSpec,
    prepare_qualification_case,
)


def prepare_endpoint_case(root: Path) -> QualificationCase:
    name = "issue249-complete-source-sound"
    policies: tuple[Literal["full", "quiet"], ...] = ("full", "quiet")
    specs = tuple(
        _ClipSpec(
            f"endpoint-{seconds}s-{policy}",
            Fraction(25),
            seconds * 25,
            audio_policy=policy,
            selected_range=False,
        )
        for seconds in (3, 10)
        for policy in policies
    )
    _CASES[name] = specs
    try:
        return prepare_qualification_case(root, name)
    finally:
        del _CASES[name]
