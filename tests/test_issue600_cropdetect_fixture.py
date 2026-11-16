from __future__ import annotations

import shutil

import pytest
from issue600_cropdetect_fixture import (
    OVERRIDE_CONTROL,
    generate_issue600_cropdetect_fixtures,
    observe_issue600_cropdetect,
    sampled_windows,
)
from vera_timeline_agent.cropdetect import (
    CropRect,
    CropWindowSample,
    select_stable_active_rect,
)


@pytest.mark.slow
def test_generated_controls_characterize_cropdetect_and_stable_selection(
    tmp_path,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is required for synthetic cropdetect fixtures")

    paths = generate_issue600_cropdetect_fixtures(tmp_path, ffmpeg)
    observed = {
        name: sampled_windows(observe_issue600_cropdetect(path, ffmpeg))
        for name, path in paths.items()
    }
    expected = {
        "letterbox": CropRect(0, 20, 320, 140),
        "pillarbox": CropRect(24, 0, 272, 180),
        "near_black": CropRect(0, 0, 320, 180),
        "dark_title": CropRect(120, 60, 80, 60),
    }
    assert all(len(windows) == 3 for windows in observed.values())
    for name, rect in expected.items():
        assert [item.rect for item in observed[name]] == [rect, rect, rect]
    assert observed["changing"][0].rect == CropRect(0, 20, 320, 140)
    assert observed["changing"][-1].rect == CropRect(0, 0, 320, 180)

    def select(name: str, mean_luma: float = 120.0) -> CropRect | None:
        samples = [
            CropWindowSample(f"{name}-{index}", item.rect, mean_luma)
            for index, item in enumerate(observed[name])
        ]
        return select_stable_active_rect((320, 180), samples)

    assert select("letterbox") == expected["letterbox"]
    assert select("pillarbox") == expected["pillarbox"]
    assert select("near_black") is None
    assert select("changing") is None
    # The title patch is bright (Y=235) despite its near-black background.
    # Rejecting this stable false crop needs a geometric/edge guard as well as
    # temporal agreement and mean luma; cropdetect cannot infer intent alone.
    assert select("dark_title", mean_luma=235.0) is None

    assert OVERRIDE_CONTROL["source_fixture"] == "letterbox"
    assert OVERRIDE_CONTROL["expected_action"] == "preserve-explicit-framing"
