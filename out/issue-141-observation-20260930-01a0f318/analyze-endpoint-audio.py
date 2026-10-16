import hashlib
import json
import math
import pathlib
import struct
import wave


ROOT = pathlib.Path(__file__).parent
PAIR = ROOT / "av-output-20261001T232620.358140Z/full-pair-007.json"
WAV = ROOT / "pcm-real-render-20261001T235643.512549Z.wav"
MEDIA = ROOT.parent / "issue-141-media-20260930-01a0f318"
BED_SHA256 = "f6da7ab4ffb4cc549e4b41e19da714097877b035abfb0235ac9bf94ea4860c02"


def pcm24le(data):
    return [int.from_bytes(data[i:i + 3], "little", signed=True) for i in range(0, len(data), 3)]


def corr(left, right):
    lm = sum(left) / len(left)
    rm = sum(right) / len(right)
    a = [x - lm for x in left]
    b = [x - rm for x in right]
    den = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / den if den else 0.0


def best_lag(left, right, radius=64):
    candidates = ((corr(left[max(0, lag):len(left) + min(0, lag)],
                        right[max(0, -lag):len(right) - max(0, lag)]), lag)
                  for lag in range(-radius, radius + 1))
    return max(candidates)


manifest = json.loads(pathlib.Path("docs/investigations/issue-141/inputs/manifest.json").read_text())
bed_entry = next(item for item in manifest["files"] if item["path"] == "bed.wav")
bed_path = MEDIA / "bed.wav"
assert bed_entry["sha256"] == BED_SHA256
assert hashlib.sha256(bed_path.read_bytes()).hexdigest() == BED_SHA256

with wave.open(str(WAV), "rb") as rendered:
    assert rendered.getparams() == (2, 3, 48000, 17664000, "NONE", "not compressed")
    print("render_sha256", hashlib.sha256(WAV.read_bytes()).hexdigest())
    print("render_params", rendered.getparams())
    for frame in (9197, 9198, 9199):
        rendered.setpos(frame * 1920)
        samples = rendered.readframes(1920)
        values = [int.from_bytes(samples[i:i + 3], "little", signed=True) for i in range(0, len(samples), 3)]
        print("render_frame", frame, "nonzero", sum(value != 0 for value in values),
              "minmax", (min(values), max(values)), "head", values[:8])
        if frame in (9197, 9198):
            source_frame = frame - 9100 + 100
            with wave.open(str(bed_path), "rb") as source:
                source.setpos(source_frame * 1920)
                bed = struct.unpack("<" + "h" * 1920, source.readframes(1920))
            left, right = values[::2], values[1::2]
            print("frame_signal", frame, source_frame, "rms", (
                math.sqrt(sum(x * x for x in left) / len(left)),
                math.sqrt(sum(x * x for x in right) / len(right))),
                  "correlations", corr(left, bed), corr(right, bed),
                  "best_lag_corr", best_lag(left, bed), best_lag(right, bed))

with wave.open(str(bed_path), "rb") as source:
    print("bed_sha256", BED_SHA256, "params", source.getparams())
    for frame in (197, 198, 199):
        source.setpos(frame * 1920)
        samples = source.readframes(1920)
        values = struct.unpack("<" + "h" * (len(samples) // 2), samples)
        print("bed_frame", frame, "nonzero", sum(value != 0 for value in values),
              "minmax", (min(values), max(values)), "head", values[:8])

pair = json.loads(PAIR.read_text())
for timeline in pair["timelinePasses"][0]["timelines"]:
    if not any(item.get("GetName", {}).get("value") == "bed.wav"
               and item.get("GetStart", {}).get("value") == 9000
               for track in timeline["tracks"] for item in track["items"]):
        continue
    print("timeline", timeline["GetName"], timeline["GetStartFrame"], timeline["GetEndFrame"])
    for track in timeline["tracks"]:
        print("track", track["GetTrackName"], "enabled", track["GetIsTrackEnabled"])
        for item in track["items"]:
            if item.get("GetStart", {}).get("value", 0) >= 8900:
                print("bed_item", json.dumps({key: item.get(key) for key in (
                    "GetName", "GetStart", "GetEnd", "GetDuration", "GetStart(True)",
                    "GetEnd(True)", "GetDuration(True)", "GetSourceStartFrame",
                    "GetSourceEndFrame", "GetSourceStartTime", "GetSourceEndTime",
                    "GetSpeed", "GetClipEnabled",
                )}, sort_keys=True))
