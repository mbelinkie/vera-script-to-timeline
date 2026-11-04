"""Public speech refusal cases; numerical intervals here are parser tests only."""

import copy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.issue312_speech import checked_alignment, verify_source, words


def parser_specimen() -> dict[str, Any]:
    return {
        "aligner": "A-MFA",
        "variant": "english_us_arpa",
        "provenance": {
            "settings": {"mfaExitCode": 0},
            "models": [{"id": "parser-only"}],
        },
        "words": [
            {
                "i": index,
                "status": "aligned",
                "start": index * 0.1,
                "end": index * 0.1 + 0.05,
            }
            for index in range(len(words()))
        ],
    }


def test_alignment_requires_complete_success_and_exact_order() -> None:
    specimen = parser_specimen()
    assert len(checked_alignment(specimen)) == len(words())
    for invalid in ("failure", "partial", "reordered", "overlap", "nan"):
        value = copy.deepcopy(specimen)
        if invalid == "failure":
            value["provenance"]["settings"]["mfaExitCode"] = 1
        elif invalid == "partial":
            value["words"].pop()
        elif invalid == "reordered":
            value["words"][1]["i"] = 0
        elif invalid == "overlap":
            value["words"][1]["start"] = 0.01
        else:
            value["words"][1]["start"] = float("nan")
        with pytest.raises(ValueError):
            checked_alignment(value)


def test_source_refuses_unpinned_bytes_and_symlink(tmp_path: Path) -> None:
    for name in ("source-long.wav", "transcript.txt", "rights.html"):
        (tmp_path / name).write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="pinned"):
        verify_source(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        verify_source(link)
