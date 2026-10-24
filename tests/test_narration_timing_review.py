import csv
import io
from typing import Any

import pytest
from vera_timeline_agent.narration.timing_review import audition_timing_review


def specimen() -> dict[str, Any]:
    return dict(
        audio_bytes=b"public audio identity",
        duration_seconds=2,
        tokens=[
            dict(id="one", value="again", startOffset=0, endOffset=5),
            dict(id="two", value="again", startOffset=6, endOffset=11),
        ],
        candidate=[(0.2, 0.5), (0.8, 1.2)],
        partner=[(0.22, 0.51), (0.81, 1.21)],
        native=[0.2, 0.2],
    )


def test_review_markers_keep_occurrences_and_never_imply_human_verification() -> None:
    markers, points, mapping = audition_timing_review(**specimen())
    assert markers.startswith(b"\xef\xbb\xbf") and b"\r\n" in markers
    rows = list(
        csv.DictReader(io.StringIO(markers.decode("utf-8-sig")), delimiter="\t")
    )
    assert rows[0]["Name"] == "CONTEXT 001 again"
    assert rows[1]["Name"] == "REVIEW 002 again"
    assert all("NOT human verified" in row["Description"] for row in rows)
    assert [t["tokenId"] for t in mapping["tokens"]] == ["one", "two"]
    assert not any(t["reviewed"] for t in mapping["tokens"])
    assert (
        len(
            list(
                csv.DictReader(io.StringIO(points.decode("utf-8-sig")), delimiter="\t")
            )
        )
        == 3
    )


def test_abstention_is_not_replaced_by_a_made_up_interval() -> None:
    data = specimen()
    data["candidate"][0] = None
    markers, _, mapping = audition_timing_review(**data)
    assert b"001 again" not in markers
    assert mapping["tokens"][0]["needsReview"]


def test_out_of_bounds_observations_refuse() -> None:
    data = specimen()
    data["partner"][0] = (0.2, 3)
    with pytest.raises(ValueError, match="outside"):
        audition_timing_review(**data)
