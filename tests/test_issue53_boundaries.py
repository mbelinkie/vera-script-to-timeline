"""Fictional waveform/boundary cases for the Producer's clipped-edge feedback."""

from experiments.issue53.boundaries import find_quiet_intervals, propose_quiet_cuts


def test_quiet_detection_requires_both_channels_and_sustained_quiet() -> None:
    samples = [0, 0] * 100 + [0, 20000] * 100 + [0, 0] * 100
    quiet = find_quiet_intervals(samples, 1000, 2, minimum_seconds=0.08)
    assert quiet == [[0, 0.1], [0.2, 0.3]]


def test_short_zero_crossing_is_not_silence() -> None:
    assert find_quiet_intervals([20000] * 100 + [0] * 10 + [20000] * 100, 1000, 1) == []


def test_cut_adds_ten_frames_and_sits_inside_quiet_gap() -> None:
    r = propose_quiet_cuts([2, 4], [24, 1], 8, [[1.3, 1.9], [4.1, 4.7]], [])
    assert r["frame_range"] == [38, 106]
    assert r["added_frames"] == [10, 10]
    assert r["quiet_edges_found"] == [True, True]
    assert not r["safe"]


def test_search_moves_outward_if_target_is_not_quiet() -> None:
    r = propose_quiet_cuts([2, 4], [24, 1], 8, [[1.1, 1.4], [4.6, 4.9]], [])
    a, b = r["frame_range"]
    assert a < 38 and b > 106
    assert all(r["quiet_edges_found"])


def test_adjacent_speech_prevents_crossing_to_a_farther_quiet_gap() -> None:
    r = propose_quiet_cuts([2, 4], [24, 1], 8, [[1.1, 1.4], [4.6, 4.9]], [[1.5, 1.8]])
    assert r["frame_range"] is None
    assert "adjacent_speech_blocks_padding" in r["reasons"]


def test_no_quiet_gap_never_falls_back_to_tight_transcript_edges() -> None:
    r = propose_quiet_cuts([2, 4], [24, 1], 8, [], [])
    assert r["frame_range"] is None
    assert r["preview_frame_range"] == [38, 106]
    assert "quiet_boundary_not_found" in r["reasons"]


def test_source_limit_remains_an_explicit_exception() -> None:
    r = propose_quiet_cuts([0.1, 4], [24, 1], 8, [], [])
    assert r["frame_range"] is None
    assert r["preview_frame_range"] is None
    assert "source_limit" in r["reasons"]


def test_explicit_short_gap_policy_keeps_cut_quiet_and_reports_less_padding() -> None:
    r = propose_quiet_cuts(
        [2, 4],
        [30, 1],
        8,
        [[1.71, 2.01], [4.1, 4.29]],
        [[1.3, 1.66]],
        allow_reduced_padding=True,
    )
    assert r["frame_range"] == [52, 128]
    assert r["added_frames"] == [8, 8]
    assert "reduced_padding_to_fit_quiet_gap" in r["reasons"]
    assert all(r["quiet_edges_found"])


def test_reduced_policy_cannot_cut_on_word_edge_without_quiet() -> None:
    r = propose_quiet_cuts([2, 4], [30, 1], 8, [], [], allow_reduced_padding=True)
    assert r["frame_range"] is None
    assert r["preview_frame_range"] == [50, 130]
