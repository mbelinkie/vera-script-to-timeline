"""Pure prediction checks for rounded complete source-audio endpoints."""

from __future__ import annotations

import io
import json
import struct
import wave
from dataclasses import replace
from fractions import Fraction

import pytest
from test_issue214_comparison import rendered
from test_issue214_prediction import (
    Case,
    case,
    committed,
    refresh_package_inputs,
)
from test_issue214_prediction import (
    wav as fixture_wav,
)
from test_issue214_records import canonical, digest
from vera_timeline_agent import qualification_output_v2 as q
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError
from vera_timeline_agent.source_audio_endpoint import endpoint_plan, endpoint_wav


def _endpoint_case(seconds: int, gain: int, *, trailing_samples: int = 0) -> Case:
    frames = seconds * 24
    selected_samples = seconds * 48_000
    c = case(
        kind="source_audio",
        gain=gain,
        frames=frames,
        count=frames * q.FRAME,
    )
    sid = c.binding["sourceEntries"][0]["sourceId"]
    channels = c.binding["sourceEntries"][0]["channels"]
    decoded_samples = selected_samples + trailing_samples
    source_samples = c.samples[: decoded_samples * channels]
    raw = fixture_wav(source_samples, channels=channels)
    c.samples = source_samples
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    event = manifest["events"][0]
    event["audio"]["sampleRange"]["endFrame"] = selected_samples

    proofs = dict(c.inputs.source_proofs)
    proof = proofs[sid]
    record = json.loads(proof.record)
    record["audio"]["contentHash"] = "sha256:" + digest(raw)
    record["audio"]["decodedSamples"] = decoded_samples
    record["audio"]["sourceFirstSample"] = 0
    record["audio"]["sourceExclusiveSample"] = selected_samples
    record_raw = canonical(record)
    proofs[sid] = replace(proof, record=record_raw, receipt=record_raw)

    plan = endpoint_plan(event, record["audio"], Fraction(24_000, 1001))
    assert plan is not None
    derived_native = endpoint_wav(raw, plan, record["audio"])

    entry = c.binding["sourceEntries"][0]
    entry["nativeSourceSha256"] = digest(derived_native)
    entry["pcmFileSha256"] = digest(raw)
    entry["durationSamples"] = decoded_samples
    entry["provenanceReceiptSha256"] = digest(record_raw)
    entry["decodedSamplesSha256"] = digest(
        b"".join(struct.pack("<i", value) for value in source_samples)
    )
    mapping = {
        "sourceId": sid,
        "nativeFrameOrigin": 0,
        "pcmSampleOrigin": 0,
        "sourceSampleRate": 48_000,
        "sampleRate": 48_000,
        "resampledFirstSample": 0,
        "startSample": 0,
        "endSample": selected_samples,
        "provenanceRecordSha256": digest(record_raw),
    }
    entry["pcmMappingSha256"] = digest(canonical(mapping))
    c.binding["nativeSources"][0]["nativeSourceSha256"] = digest(derived_native)

    blobs = dict(c.inputs.blobs)
    blobs["manifestSha256"] = canonical(manifest)
    snapshot = json.loads(c.inputs.geometry)
    snapshot["geometry"]["items"][0]["sourceMappingSha256"] = entry["pcmMappingSha256"]
    source_mapping = snapshot["geometry"]["sourceMappings"][0]
    source_mapping["nativeSourceSha256"] = digest(derived_native)
    source_mapping["sourceEntrySha256"] = digest(canonical(entry))
    c.inputs = replace(
        c.inputs,
        blobs=blobs,
        geometry=canonical(snapshot),
        source_proofs=proofs,
        source_wavs={**c.inputs.source_wavs, sid: raw},
    )
    refresh_package_inputs(c)
    return c


def _expected_pcm(c: Case) -> bytes:
    geometry = json.loads(c.inputs.geometry)["geometry"]
    entry = c.binding["sourceEntries"][0]
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    gain = 10 ** (manifest["events"][0]["audio"]["gainDb"] / 20)
    output = [0.0] * (geometry["extentFrames"] * q.FRAME * 2)
    for item in geometry["items"]:
        if item["kind"] != "audio":
            continue
        start = (item["sourceStart"] - entry["nativeFrameOrigin"]) * q.FRAME + entry[
            "pcmSampleOrigin"
        ]
        for offset in range(item["recordDuration"] * q.FRAME):
            source_index = start + offset
            edge_gain = min(
                1.0, offset / 72, (item["recordDuration"] * q.FRAME - offset) / 72
            )
            value = (
                c.samples[source_index] / 2**23 * gain * edge_gain
                if source_index < len(c.samples)
                else 0.0
            )
            output[(item["recordStart"] * q.FRAME + offset) * 2] += value
            output[(item["recordStart"] * q.FRAME + offset) * 2 + 1] += value
    return b"".join(struct.pack("<d", value) for value in output)


def _expected_decoded(c: Case) -> list[int]:
    geometry = json.loads(c.inputs.geometry)["geometry"]
    entry = c.binding["sourceEntries"][0]
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    gain = 10 ** (manifest["events"][0]["audio"]["gainDb"] / 20)
    output = [0] * (geometry["extentFrames"] * q.FRAME * 2)
    for item in geometry["items"]:
        if item["kind"] != "audio":
            continue
        start = (item["sourceStart"] - entry["nativeFrameOrigin"]) * q.FRAME + entry[
            "pcmSampleOrigin"
        ]
        for offset in range(item["recordDuration"] * q.FRAME):
            source_index = start + offset
            edge_gain = min(
                1.0, offset / 72, (item["recordDuration"] * q.FRAME - offset) / 72
            )
            value = (
                round(c.samples[source_index] * gain * edge_gain)
                if source_index < len(c.samples)
                else 0
            )
            record_index = (item["recordStart"] * q.FRAME + offset) * 2
            output[record_index] += value
            output[record_index + 1] += value
    return output


@pytest.mark.parametrize(
    ("seconds", "frames", "remainder"), [(3, 72, 144), (10, 240, 480)]
)
@pytest.mark.parametrize("gain", [0, -18])
def test_source_audio_endpoint_prediction_and_residuals_are_exact(
    seconds: int, frames: int, remainder: int, gain: int
) -> None:
    c = _endpoint_case(seconds, gain)
    _, _, prediction = committed(c)
    expected = _expected_pcm(c)
    assert prediction == expected
    assert prediction[-remainder * 2 * 8 :] == bytes(remainder * 2 * 8)

    entry = c.binding["sourceEntries"][0]
    sid = entry["sourceId"]
    assert entry["durationSamples"] == len(c.samples) == seconds * 48_000
    assert entry["pcmFileSha256"] == digest(c.inputs.source_wavs[sid])
    assert entry["nativeSourceSha256"] != entry["pcmFileSha256"]
    assert remainder == frames * q.FRAME - len(c.samples)
    if (seconds, gain) == (3, 0):
        rendered_output = rendered(c, _expected_decoded(c))
        comparison = q.compare_committed_output(rendered_output, trust=c.trust)
        assert comparison["status"] == "compared_consistent"
        assert all(metric["consistent"] for metric in comparison["metrics"])


def _wav_with_replayed_tail(
    raw: bytes, selected_samples: int, envelope_samples: int
) -> bytes:
    with wave.open(io.BytesIO(raw), "rb") as source:
        params = source.getparams()
        pcm = source.readframes(params.nframes)
    frame_bytes = params.nchannels * params.sampwidth
    tail_start = selected_samples * frame_bytes
    tail_end = tail_start + 2 * frame_bytes
    payload = (
        pcm[:tail_start]
        + pcm[tail_start:tail_end]
        + bytes((envelope_samples - selected_samples - 2) * frame_bytes)
    )
    output = io.BytesIO()
    with wave.open(output, "wb") as destination:
        destination.setparams(
            (params.nchannels, params.sampwidth, params.framerate, 0, "NONE", "")
        )
        destination.writeframes(payload)
    return output.getvalue()


def _replace_endpoint_native_hash(c: Case, replacement: bytes) -> None:
    native_hash = digest(replacement)
    entry = c.binding["sourceEntries"][0]
    entry["nativeSourceSha256"] = native_hash
    c.binding["nativeSources"][0]["nativeSourceSha256"] = native_hash
    snapshot = json.loads(c.inputs.geometry)
    source_mapping = snapshot["geometry"]["sourceMappings"][0]
    source_mapping["nativeSourceSha256"] = native_hash
    source_mapping["sourceEntrySha256"] = digest(canonical(entry))
    c.inputs = replace(c.inputs, geometry=canonical(snapshot))
    refresh_package_inputs(c)


@pytest.mark.parametrize("attack", ["wrong_hash", "replayed_tail"])
def test_prediction_refuses_forged_endpoint_native_wav(attack: str) -> None:
    seconds = 3
    selected_samples = seconds * 48_000
    c = _endpoint_case(seconds, 0, trailing_samples=2)
    event = json.loads(c.inputs.blobs["manifestSha256"])["events"][0]
    record = json.loads(c.inputs.source_proofs[event["eventId"]].record)["audio"]
    plan = endpoint_plan(event, record, Fraction(24_000, 1001))
    assert plan is not None
    raw = c.inputs.source_wavs[event["eventId"]]
    if attack == "wrong_hash":
        forged = b"forged but independently committed native bytes"
    else:
        forged = _wav_with_replayed_tail(raw, selected_samples, plan[2])
        assert forged != endpoint_wav(raw, plan, record)
    _replace_endpoint_native_hash(c, forged)

    with pytest.raises(
        OutputConsistencyError, match="endpoint native WAV derivation differs"
    ):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])
