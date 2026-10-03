#!/usr/local/bin/python3.14
"""Compare the confirmed held-mute program WAV with the retained baseline."""
import argparse
from array import array
import hashlib
import json
import math
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "pcm-real-render-20261001T235643.512549Z.wav"
BASELINE_SHA256 = "d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a7"
BASELINE_ANALYSIS = ROOT / "pcm-real-render-analysis.json"
HELD_RESULT = ROOT / "cli-mute-native-once-result-reviewed.json"
TARGET_UID = "f4e9f649-894a-42f2-9f54-a8321ae7c163"
RATE = 48_000
FRAME_RATE = 25
SAMPLES_PER_FRAME = RATE // FRAME_RATE
TARGET = (4500, 4699)  # exclusive GetEnd; frame 4699 remains outside the edited span
GAP = (4560, 4570)
GAP_END_FRAME_CONTROL = (4570, 4571)
RENDER_MOV = ROOT / "av-output-20261002T020927.190878Z/render/vera141-av-20261002T020927.190878Z.mov"
RENDER_MOV_SHA256 = "7c69f239a3a8e08f5617c4e72f843c345d91bf3baef813f7c43501efccbcbbf4"
RENDER_MOV_BYTES = 131_423_800


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def decode_s24le(b0, b1, b2):
    value = b0 | b1 << 8 | b2 << 16
    return value - 0x1000000 if value & 0x800000 else value


def validate_pcm(path):
    with wave.open(str(path), "rb") as w:
        info = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
    if info != (2, 3, RATE, 17_664_000, "NONE"):
        raise ValueError(f"expected 2-channel PCM24 48kHz 17664000-frame WAV, got {info}")


def read_window(path, lo, hi):
    with wave.open(str(path), "rb") as w:
        w.setpos(lo)
        raw = w.readframes(hi - lo)
    if len(raw) != (hi - lo) * 6:
        raise ValueError("truncated stereo PCM24 window")
    channels = [array("i"), array("i")]
    for i in range(0, len(raw), 6):
        channels[0].append(decode_s24le(raw[i], raw[i + 1], raw[i + 2]))
        channels[1].append(decode_s24le(raw[i + 3], raw[i + 4], raw[i + 5]))
    return channels


def outside_equal(path_a, path_b, lo, hi):
    with wave.open(str(path_a), "rb") as a, wave.open(str(path_b), "rb") as b:
        # PCM24 stereo is six bytes per sample frame; exact byte equality is exact
        # equality in both channels, including every sample before and after span.
        prefix = lo * 6
        suffix_frames = 17_664_000 - hi
        if a.readframes(lo) != b.readframes(lo):
            return False
        a.setpos(hi); b.setpos(hi)
        while suffix_frames:
            count = min(suffix_frames, 65_536)
            if a.readframes(count) != b.readframes(count):
                return False
            suffix_frames -= count
    return True


def stats(a, b, lo, hi):
    result = []
    for ch in range(2):
        x, y = a[ch][lo:hi], b[ch][lo:hi]
        if len(x) != hi - lo or len(y) != hi - lo or not x:
            raise ValueError("window arithmetic produced an empty or truncated region")
        count = len(x)
        sx, sy = sum(x), sum(y)
        mx, my = sx / count, sy / count
        xx = sum((v - mx) ** 2 for v in x)
        yy = sum((v - my) ** 2 for v in y)
        xy = sum((u - mx) * (v - my) for u, v in zip(x, y))
        corr = xy / math.sqrt(xx * yy) if xx and yy else None
        scale = 8388608.0
        residual_rms = math.sqrt(sum((u - v) ** 2 for u, v in zip(x, y)) / count) / scale
        result.append({
            "channel": ch + 1,
            "samples": len(x),
            "exactEqualSamples": sum(u == v for u, v in zip(x, y)),
            "differentSamples": sum(u != v for u, v in zip(x, y)),
            "correlation": corr,
            "residualRms": residual_rms,
            "baselineRms": math.sqrt(sum(v * v for v in x) / count) / scale,
            "heldMuteRms": math.sqrt(sum(v * v for v in y) / count) / scale,
        })
    return result


def main():
    assert decode_s24le(0, 0, 0) == 0
    assert decode_s24le(255, 255, 127) == 8_388_607
    assert decode_s24le(0, 0, 128) == -8_388_608
    p = argparse.ArgumentParser()
    p.add_argument("--render", required=True, help="absolute path to confirmed held-mute WAV")
    p.add_argument("--sha256", required=True, help="confirmed WAV SHA-256")
    p.add_argument("--output", help="result JSON path (defaults alongside this script)")
    args = p.parse_args()
    held = Path(args.render)
    if not held.is_absolute() or held.is_symlink() or not held.is_file() or not held.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("render must be an absolute regular non-symlink file under this observation directory")
    if sha256(BASELINE) != BASELINE_SHA256:
        raise ValueError("retained baseline hash mismatch")
    if sha256(held) != args.sha256.lower():
        raise ValueError("held-mute WAV hash differs from the confirmed argument")
    prior = json.loads(BASELINE_ANALYSIS.read_text())
    held_result = json.loads(HELD_RESULT.read_text())
    if held_result["summary"]["target"]["occurrenceUid"] != TARGET_UID:
        raise ValueError("held-result target UID does not match the pinned comparison target")
    source_support = prior["caseFindings"][0]["gapOrDiagnosticWindow"]["sourceSupportReference"]
    # Small arithmetic guard: frame boundaries map exactly to 1,920 samples.
    assert RATE % FRAME_RATE == 0 and (GAP[0] - TARGET[0]) * SAMPLES_PER_FRAME == 115_200
    assert (GAP[1] - GAP[0]) * SAMPLES_PER_FRAME == 19_200
    validate_pcm(BASELINE)
    validate_pcm(held)
    lo, hi = TARGET[0] * SAMPLES_PER_FRAME, TARGET[1] * SAMPLES_PER_FRAME
    gap_lo, gap_hi = GAP[0] * SAMPLES_PER_FRAME, GAP[1] * SAMPLES_PER_FRAME
    outside_same = outside_equal(BASELINE, held, lo, hi)
    controls = {
        "before": [TARGET[0] - 10, TARGET[0]],
        "after": [TARGET[1], TARGET[1] + 10],
        "gapExclusiveEndFrame4570": list(GAP_END_FRAME_CONTROL),
    }
    result = {
        "kind": "issue-141-held-mute-pcm-comparison-v1",
        "status": "comparison-complete-waveform-only",
        "baseline": {"path": str(BASELINE), "sha256": BASELINE_SHA256},
        "heldMute": {"path": str(held.resolve()), "sha256": args.sha256.lower()},
        "renderBinding": {"movPath": str(RENDER_MOV), "movSha256": RENDER_MOV_SHA256, "movBytes": RENDER_MOV_BYTES, "extraction": "ffmpeg -nostdin -hide_banner -loglevel error -n -i <owned MOV> -map 0:a:0 -vn -c:a pcm_s24le <owned WAV>", "wholeWavSha256EqualsBaseline": args.sha256.lower() == BASELINE_SHA256},
        "format": {"channels": 2, "sampleRateHz": RATE, "sampleWidthBytes": 3, "frames": 17_664_000, "samplesPerFrame": SAMPLES_PER_FRAME},
        "target": {"audioTrackItemUid": TARGET_UID, "heldResultPath": str(HELD_RESULT), "recordFramesExclusive": list(TARGET), "sampleRange": [lo, hi], "mapping": "baseline false; held-mute true"},
        "outsideTarget": {"bothChannelsExactlyEqual": outside_same, "samplesPerChannelCompared": 17_664_000 - (hi - lo)},
        "speechGap": {"recordFramesExclusive": list(GAP), "sampleRange": [gap_lo, gap_hi], "sourceSupportReferenceFromPriorAnalysis": source_support, "perChannel": stats(read_window(BASELINE, gap_lo, gap_hi), read_window(held, gap_lo, gap_hi), 0, gap_hi-gap_lo), "exclusiveEndFrameControl": {"frame": 4570, "sampleRange": [GAP_END_FRAME_CONTROL[0] * SAMPLES_PER_FRAME, GAP_END_FRAME_CONTROL[1] * SAMPLES_PER_FRAME], "perChannel": stats(read_window(BASELINE, GAP_END_FRAME_CONTROL[0] * SAMPLES_PER_FRAME, GAP_END_FRAME_CONTROL[1] * SAMPLES_PER_FRAME), read_window(held, GAP_END_FRAME_CONTROL[0] * SAMPLES_PER_FRAME, GAP_END_FRAME_CONTROL[1] * SAMPLES_PER_FRAME), 0, SAMPLES_PER_FRAME)}},
        "neighborControls": {name: {"recordFrames": frames, "sampleRange": [frames[0] * SAMPLES_PER_FRAME, frames[1] * SAMPLES_PER_FRAME], "perChannel": stats(read_window(BASELINE, frames[0] * SAMPLES_PER_FRAME, frames[1] * SAMPLES_PER_FRAME), read_window(held, frames[0] * SAMPLES_PER_FRAME, frames[1] * SAMPLES_PER_FRAME), 0, (frames[1]-frames[0]) * SAMPLES_PER_FRAME)} for name, frames in controls.items()},
        "limitations": ["PCM sample differences establish output waveform change only; no track or bus origin, universal deletion, routing, or final audibility claim."],
        "interpretation": "The held mapping flag was true, but this build/case did not change the rendered program waveform, so the mapping flag does not establish mute of program speech here. This single result is not evidence of a universal API failure.",
    }
    output = Path(args.output) if args.output else ROOT / "mute-pcm-comparison-result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "output": str(output), "outsideTargetExactlyEqual": outside_same}, indent=2))


if __name__ == "__main__":
    main()
