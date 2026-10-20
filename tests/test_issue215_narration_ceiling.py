from fractions import Fraction

from vera_timeline_agent.v2_package import narration_ceiling_frames

RATE = Fraction(24000, 1001)


def test_ceiling_allows_exactly_ceil_frames() -> None:
    # Campaign Polly row: 262200 samples = 130.97 frames at 48 kHz / 23.976.
    assert narration_ceiling_frames(262200, 48000, RATE) == 131
    assert narration_ceiling_frames(131 * 2002, 48000, RATE) == 131
    assert narration_ceiling_frames(131 * 2002 + 1, 48000, RATE) == 132
    assert narration_ceiling_frames(131 * 2002 - 1, 48000, RATE) == 131
