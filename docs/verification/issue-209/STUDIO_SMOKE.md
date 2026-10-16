# #209 Studio smoke

The installed qualification route passed an actual disposable-project exercise
on 2026-10-16 using DaVinci Resolve Studio 21.1.1 build 10, injected Python
3.14.7, and source commit `f5111c1`.

All seven native stages completed: construction, save/reopen, pre-render
capture, queue, start, completion polling and post-render capture. The host
independently decoded that delivered MOV and returned `compared_consistent`.
Pre/post observable geometry matched. Earlier incomplete attempts and their
test projects remain preserved.

The verified test package contains 111 frames at 24000/1001 fps, 1920×1080,
with stereo 48 kHz audio. It uses the existing authored quiet policy (−18 dB):
the first full-level test input contained an exactly full-scale sample and
correctly failed prediction before rendering. The final MOV contains ProRes
422, 24-bit LPCM with 222,222 samples per channel, and Studio's standard `tmcd`
metadata track.

The fixed zero-lag, unity-gain comparison measured:

| Channel | Programme residual RMS | Maximum sliding 960-sample residual RMS |
| --- | ---: | ---: |
| Left | 0.0000318731 | 0.000468697 |
| Right | 0.0000318652 | 0.000468898 |
| Required maximum | 0.0004 | 0.006 |

Real-app fixes cover optional speed getter fields, numeric frame-rate readback,
video-exclusive versus audio-inclusive source endpoints, exact ProRes codec
identifiers, single-clip render mode and the optional timecode metadata stream.
The decoder still rejects extra audio/video and unknown metadata streams.

This proves only `bounded_output_residual_consistency` for the disposable smoke.
Internal controls remain unverified; continuous geometry/control stability and
causal exclusivity remain unclaimed. It does not qualify the #178 physical
matrix or Sweden's creative acceptance.
