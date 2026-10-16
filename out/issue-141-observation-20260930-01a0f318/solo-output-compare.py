#!/usr/local/bin/python3.14
"""Compare completed A2-Solo PCM with the retained baseline and bounded controls."""

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JOB_ID = "a6ed7f33-9ad4-4d82-bfac-ff72903f4567"
MOV = ROOT / "av-output-20261002T033005.646357Z/render/vera141-av-20261002T033005.646357Z.mov"
PAIR = ROOT / "editorial-context-20261002T031927.605476Z/pair.json"
PAIR_SHA256 = "d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14"
COMPARATOR = ROOT.parent.parent / "docs/investigations/issue-141/program-pcm-check.py"
COMPARATOR_SHA256 = "da049811705d59424f1b4b162c9e1b4867ccfd260ddef4a4edd97a46d1f71f77"
BASELINE = ROOT / "pcm-real-render-20261001T235643.512549Z.wav"
BASELINE_SHA256 = "d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a7"
OUTPUT_WAV = ROOT / "solo-output-20261002T033005.646357Z.wav"
OUTPUT_JSON = ROOT / "solo-output-comparison-result.json"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
A1_UID = "a9175c87-6bc0-4c07-a167-3b7c9de70fba"
A2_UID = "f4e9f649-894a-42f2-9f54-a8321ae7c163"
A3_UID = "050ec572-54d8-4025-a1c7-0e625766245a"
A3_SPEECH_UID = "1dde7d80-6057-4a48-94a4-134a6d79e41f"
RATE = 48_000
SAMPLES_PER_FRAME = 1_920
EXPECTED_FRAMES = 17_664_000
WINDOWS = {
    "A1-only speech control": (4_339_210, 4_356_258),
    "A2 speech support with A3 bed": (8_755_210, 8_772_258),
    "A3-only track control": (7_804_800, 7_814_400),
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def decode_s24le(data):
    value = data[0] | data[1] << 8 | data[2] << 16
    return value - 0x1000000 if value & 0x800000 else value


def _pair_timeline(pair):
    passes = pair.get("timelinePasses")
    if (pair.get("selectedTimelineUid") != MATRIX_UID or not isinstance(passes, list)
            or len(passes) != 2 or passes[0] != passes[1]):
        raise ValueError("fresh pair is not an equal two-pass selected Matrix capture")
    if pair.get("timelineConsistency") != "equal-adjacent-reads":
        raise ValueError("fresh Matrix timeline consistency is missing")
    timelines = passes[0].get("timelines", [])
    found = [t for t in timelines if t.get("GetUniqueId", {}).get("value") == MATRIX_UID]
    if len(found) != 1:
        raise ValueError("pair does not contain exactly one Matrix timeline")
    return found[0]


def _v(item, key):
    entry = item.get(key)
    if not isinstance(entry, dict) or "value" not in entry:
        raise ValueError(f"Matrix item lacks {key}")
    return entry["value"]


def _verify_controls(pair):
    timeline = _pair_timeline(pair)
    tracks = {}
    for track in timeline.get("tracks", []):
        name = _v(track, "GetTrackName")
        if name in {"Audio 1", "Audio 2", "Audio 3"}:
            tracks[name] = track
    if set(tracks) != {"Audio 1", "Audio 2", "Audio 3"}:
        raise ValueError("pair is missing one of the three audio tracks")
    if any(_v(t, "GetIsTrackEnabled") is not True for t in tracks.values()):
        raise ValueError("an audio track is disabled in the pinned control state")

    def rows(track_name):
        result = []
        for item in tracks[track_name].get("items", []):
            media = item.get("GetMediaPoolItem") or {}
            props = _v(media, "GetClipProperty") if media else {}
            result.append({
                "uid": _v(item, "GetUniqueId"),
                "start": int(_v(item, "GetStart")),
                "end": int(_v(item, "GetEnd")),
                "enabled": _v(item, "GetClipEnabled") is True,
                "source": props.get("File Name"),
                "sourceUid": _v(media, "GetUniqueId") if media else None,
            })
        return result

    a1, a2, a3 = rows("Audio 1"), rows("Audio 2"), rows("Audio 3")

    def overlapping(items, lo, hi, *, enabled=None):
        return [x for x in items if x["start"] < hi and x["end"] > lo
                and (enabled is None or x["enabled"] is enabled)]

    a1_control = [x for x in a1 if x["uid"] == A1_UID]
    if (len(a1_control) != 1 or not a1_control[0]["enabled"]
            or (a1_control[0]["start"], a1_control[0]["end"]) != (2250, 2449)
            or a1_control[0]["source"] != "repeated.wav"
            or a1_control[0]["sourceUid"] != "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8"
            or overlapping(a2, 2250, 2449, enabled=True)
            or overlapping(a3, 2250, 2449, enabled=True)):
        raise ValueError("A1-only control interval no longer matches the pinned pair")

    a2_target = [x for x in a2 if x["uid"] == A2_UID]
    a3_gap = [x for x in a3 if x["uid"] == A3_SPEECH_UID]
    if (len(a2_target) != 1 or not a2_target[0]["enabled"]
            or (a2_target[0]["start"], a2_target[0]["end"]) != (4500, 4699)
            or not a3_gap or not any(x["enabled"] and x["start"] <= 4560 and x["end"] >= 4570 for x in a3_gap)
            or overlapping(a1, 4560, 4570, enabled=True)):
        raise ValueError("A2 speech control interval no longer matches the pinned pair")

    a3_only = [x for x in a3 if x["uid"] == A3_UID]
    if (not a3_only or not any(x["enabled"] and x["start"] <= 4065 and x["end"] >= 4070 for x in a3_only)
            or overlapping(a1, 4065, 4070, enabled=True)
            or overlapping(a2, 4065, 4070, enabled=True)):
        raise ValueError("A3-only track control interval no longer matches the pinned pair")


def _load_terminal_handoff(path, expected_sha):
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(ROOT.resolve())):
        raise ValueError("terminal handoff must be a regular file under the Issue 141 output root")
    if sha256(path) != expected_sha.lower():
        raise ValueError("terminal handoff SHA-256 differs from the supplied binding")
    handoff = json.loads(path.read_text(encoding="utf-8"))
    if (handoff.get("kind") != "issue-141-render-terminal-handoff-v1"
            or handoff.get("jobId") != JOB_ID
            or handoff.get("jobStatus") not in {"Complete", "Render Complete"}
            or handoff.get("outputPath") != str(MOV)
            or not isinstance(handoff.get("outputSha256"), str)
            or len(handoff["outputSha256"]) != 64
            or not isinstance(handoff.get("outputBytes"), int)
            or handoff["outputBytes"] <= 0):
        raise ValueError("handoff does not prove successful terminal completion of the exact owned job")
    return handoff


def _wav_info(path):
    with wave.open(str(path), "rb") as w:
        info = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
    if info != (2, 3, RATE, EXPECTED_FRAMES, "NONE"):
        raise ValueError(f"expected stereo PCM24/48 kHz/{EXPECTED_FRAMES} frames, got {info}")
    return {"channels": 2, "sampleWidthBytes": 3, "sampleRateHz": RATE,
            "frames": EXPECTED_FRAMES, "compression": "NONE"}


def _window_stats(path, lo, hi):
    if not (0 <= lo < hi <= EXPECTED_FRAMES):
        raise ValueError("window is empty or outside the full render")
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) != (2, 3, RATE, EXPECTED_FRAMES):
            raise ValueError("PCM window source has the wrong format or frame count")
        w.setpos(lo)
        raw = w.readframes(hi - lo)
    if len(raw) != (hi - lo) * 6:
        raise ValueError("truncated PCM window")
    channels = [array("i"), array("i")]
    for pos in range(0, len(raw), 6):
        channels[0].append(decode_s24le(raw[pos:pos + 3]))
        channels[1].append(decode_s24le(raw[pos + 3:pos + 6]))
    scale = 8_388_608.0
    return [{"channel": c + 1, "frames": hi - lo,
             "rms": math.sqrt(sum(v * v for v in samples) / len(samples)) / scale,
             "peak": max(abs(v) for v in samples) / scale}
            for c, samples in enumerate(channels)]


def _whole_compare(left, right):
    per_channel = [{"channel": ch + 1, "differentSamples": 0, "exactEqualSamples": 0,
                    "baselineEnergy": 0.0, "soloEnergy": 0.0, "residualEnergy": 0.0}
                   for ch in range(2)]
    same = True
    frames_left = EXPECTED_FRAMES
    with wave.open(str(left), "rb") as a, wave.open(str(right), "rb") as b:
        while frames_left:
            count = min(frames_left, 65_536)
            x, y = a.readframes(count), b.readframes(count)
            if len(x) != count * 6 or len(y) != count * 6:
                raise ValueError("truncated PCM during whole-file comparison")
            same &= x == y
            for pos in range(0, len(x), 6):
                for ch, offset in enumerate((0, 3)):
                    u, v = decode_s24le(x[pos + offset:pos + offset + 3]), decode_s24le(y[pos + offset:pos + offset + 3])
                    r = per_channel[ch]
                    r["differentSamples"] += u != v
                    r["exactEqualSamples"] += u == v
                    r["baselineEnergy"] += u * u
                    r["soloEnergy"] += v * v
                    r["residualEnergy"] += (u - v) ** 2
            frames_left -= count
    for row in per_channel:
        row["baselineRms"] = math.sqrt(row.pop("baselineEnergy") / EXPECTED_FRAMES) / 8_388_608.0
        row["soloRms"] = math.sqrt(row.pop("soloEnergy") / EXPECTED_FRAMES) / 8_388_608.0
        row["residualRms"] = math.sqrt(row.pop("residualEnergy") / EXPECTED_FRAMES) / 8_388_608.0
    return {"pcmSampleFramesExactlyEqual": same, "sampleFramesPerChannel": EXPECTED_FRAMES,
            "perChannel": per_channel,
            "meaning": "whole rendered waveform comparison only; no requirement of equality outside a target interval"}


def self_check():
    assert decode_s24le(bytes((0, 0, 0))) == 0
    assert decode_s24le(bytes((255, 255, 127))) == 8_388_607
    assert decode_s24le(bytes((0, 0, 128))) == -8_388_608
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "small.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2); w.setsampwidth(3); w.setframerate(RATE)
            w.writeframes(bytes((0, 0, 0, 0, 0, 0, 255, 255, 127, 0, 0, 128)))
        got = _window_stats_small(path, 0, 2)
        assert got == [(0, 0), (8_388_607, -8_388_608)]
        try:
            _window_stats_small(path, 1, 3)
        except ValueError as error:
            assert "outside" in str(error)
        else:
            raise AssertionError("out-of-bounds interval was accepted")
    return {"status": "passed", "checks": ["PCM24 positive/negative decode", "stereo sample order", "out-of-bounds window refusal"]}


def _window_stats_small(path, lo, hi):
    with wave.open(str(path), "rb") as w:
        count = w.getnframes()
        if not 0 <= lo < hi <= count:
            raise ValueError("window is outside the test WAV")
        w.setpos(lo); raw = w.readframes(hi - lo)
    if len(raw) != (hi - lo) * 6:
        raise ValueError("truncated test window")
    return [(decode_s24le(raw[i:i + 3]), decode_s24le(raw[i + 3:i + 6]))
            for i in range(0, len(raw), 6)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--terminal-handoff", type=Path)
    parser.add_argument("--terminal-handoff-sha256")
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(self_check(), indent=2))
        return
    if args.terminal_handoff is None or not args.terminal_handoff_sha256:
        parser.error("comparison requires a hash-bound --terminal-handoff; no output is read without it")

    handoff = _load_terminal_handoff(args.terminal_handoff, args.terminal_handoff_sha256)
    if COMPARATOR.is_symlink() or sha256(COMPARATOR) != COMPARATOR_SHA256:
        raise ValueError("existing generated-media PCM comparator changed")
    # Only after terminal-success proof: inspect/hash the MOV and extract its PCM.
    if MOV.is_symlink() or not MOV.is_file() or MOV.stat().st_size != handoff["outputBytes"]:
        raise ValueError("owned completed MOV is missing or its byte count differs from the handoff")
    if sha256(MOV) != handoff["outputSha256"].lower():
        raise ValueError("owned completed MOV hash differs from the handoff")
    if OUTPUT_WAV.exists() or OUTPUT_WAV.is_symlink():
        raise ValueError("Solo extraction output already exists; refusing overwrite")
    subprocess.run(["/usr/local/bin/ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-i", str(MOV), "-map", "0:a:0", "-vn", "-c:a", "pcm_s24le", "-ar", str(RATE),
                    str(OUTPUT_WAV)], check=True, timeout=600)

    if sha256(BASELINE) != BASELINE_SHA256:
        raise ValueError("retained baseline WAV hash mismatch")
    pair = json.loads(PAIR.read_text(encoding="utf-8"))
    if sha256(PAIR) != PAIR_SHA256:
        raise ValueError("fresh Matrix pair hash mismatch")
    _verify_controls(pair)
    baseline_format, solo_format = _wav_info(BASELINE), _wav_info(OUTPUT_WAV)
    whole = _whole_compare(BASELINE, OUTPUT_WAV)

    spec = importlib.util.spec_from_file_location("program_pcm_check", COMPARATOR)
    if spec is None or spec.loader is None:
        raise ValueError("existing generated-media PCM comparator could not be loaded")
    comparator = importlib.util.module_from_spec(spec); spec.loader.exec_module(comparator)
    support = comparator.compare(
        comparator.generated_source_path(), OUTPUT_WAV, PAIR, PAIR_SHA256,
        item_uids={A1_UID, A2_UID},
    )
    lo_a3, hi_a3 = WINDOWS["A3-only track control"]
    result = {
        "kind": "issue-141-a2-solo-program-pcm-comparison-v1",
        "status": "comparison-complete-waveform-only",
        "operatorState": "A2 Solo on, operator-reported; no output/bus labels visible",
        "routing": "unknown",
        "job": {"jobId": JOB_ID, "jobStatus": handoff["jobStatus"],
                "terminalHandoffPath": str(args.terminal_handoff.resolve()),
                "terminalHandoffSha256": args.terminal_handoff_sha256.lower(),
                "movPath": str(MOV), "movSha256": handoff["outputSha256"].lower(),
                "movBytes": handoff["outputBytes"]},
        "baseline": {"path": str(BASELINE), "sha256": BASELINE_SHA256, "format": baseline_format},
        "soloOutput": {"path": str(OUTPUT_WAV), "sha256": sha256(OUTPUT_WAV),
                       "bytes": OUTPUT_WAV.stat().st_size, "format": solo_format,
                       "extraction": "ffmpeg stream decode: MOV audio 0:a:0 to PCM24 48 kHz"},
        "fullProgram": whole,
        "controls": {
            name: {"sampleRange": [lo, hi],
                   "recordFrames": [lo // SAMPLES_PER_FRAME, (hi + SAMPLES_PER_FRAME - 1) // SAMPLES_PER_FRAME],
                   "baselinePerChannel": _window_stats(BASELINE, lo, hi),
                   "soloPerChannel": _window_stats(OUTPUT_WAV, lo, hi)}
            for name, (lo, hi) in WINDOWS.items()
        },
        "repeatedSourceSupport": support,
        "limitations": [
            "Solo state is operator-held UI evidence and is absent from the API readback.",
            "Bus origin, routing, and final audibility remain unknown.",
            "Whole-file comparison is descriptive; equality outside any named interval is not required.",
            "The existing repeated.wav comparator measures waveform correlation only, not deletion or audibility.",
            "A3 control reports output energy only; it is not bed.wav correlation.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(OUTPUT_JSON)}, indent=2))


if __name__ == "__main__":
    main()
