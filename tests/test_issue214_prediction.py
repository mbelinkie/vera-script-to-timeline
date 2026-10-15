"""Independent synthetic sources, manifest intent and immutable prediction vectors."""

from __future__ import annotations

import io
import json
import struct
import wave
from array import array
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from test_issue214_records import SealedTrust, canonical, context, digest
from vera_timeline_agent import qualification_output_records_v2 as r
from vera_timeline_agent import qualification_output_v2 as q
from vera_timeline_agent.generated.contracts import (
    compiler_dependencies_v2_schema as deps_schema,
)
from vera_timeline_agent.roundtrip_v2_audio import _mix as old_mix
from vera_timeline_agent.v2_package import (
    _compiler_hash,
    _delivery_view,
    _InputArtifact,
    _Preparation,
    _source_audio_range,
)


@dataclass
class Case:
    inputs: q.PredictionInputs
    trust: SealedTrust
    samples: list[int]
    binding: dict[str, Any]

    def capture(self) -> None:
        self.inputs = replace(self.inputs, input_binding=canonical(self.binding))
        snapshot = json.loads(self.inputs.geometry)
        snapshot["inputBindingSha256"] = digest(canonical(self.binding))
        self.inputs = replace(self.inputs, geometry=canonical(snapshot))
        self.reseal_geometry()

    def reseal_geometry(self) -> None:
        snapshot = json.loads(self.inputs.geometry)
        payload = {
            key: value for key, value in snapshot.items() if key != "receiptSha256"
        }
        receipt = self.trust.seal("output_geometry_snapshot", payload)
        snapshot["receiptSha256"] = digest(receipt)
        self.inputs = replace(
            self.inputs, geometry=canonical(snapshot), geometry_receipt=receipt
        )


def wav(samples: list[int], *, width: int = 3, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setparams((channels, width, 48000, len(samples) // channels, "NONE", ""))
        stream.writeframes(
            b"".join(value.to_bytes(width, "little", signed=True) for value in samples)
        )
    return buffer.getvalue()


def case(
    *,
    phase: str = "pristine",
    kind: str = "narration",
    frames: int = 6,
    count: int | None = None,
    width: int = 3,
    channels: int = 1,
    source_start: int = 0,
    rate: int = 48000,
    q_origin: int = 0,
    gain: int = 0,
    silent: bool = False,
    native_origin: int = 0,
    pcm_origin: int = 0,
    source_id: str = "source-é",
    event_id: str = "event-1",
    trailer: bytes = b"",
    silent_right: bool = False,
) -> Case:
    trust = SealedTrust()
    size = count if count is not None else (source_start + frames) * q.FRAME
    samples = [
        0
        if silent or (silent_right and i % channels == 1)
        else 900000 + ((i * 7919) % 700000)
        for i in range(size * channels)
    ]
    if width == 2:
        samples = [x // 256 for x in samples]
    raw = wav(samples, width=width, channels=channels) + trailer
    integers = [x * (256 if width == 2 else 1) for x in samples]
    eid = event_id
    sid = source_id if kind == "narration" else eid
    native_hash = digest(raw)
    delivered_hash = (
        native_hash if kind == "narration" else digest(b"original AV bytes")
    )
    event: dict[str, Any] = {
        "eventId": eid,
        "kind": kind,
        "trackId": "audio-1",
        "recordRange": {"startFrame": 0, "endFrame": frames},
        "provenance": {
            "sourceId": sid,
            "blockId": "block-1",
            "deliveredSourceHash": "sha256:" + delivered_hash,
        },
    }
    timing, review = b"provider timing", b"human review"
    if kind == "narration":
        audio = {
            "narrationAssetId": sid,
            "audioHash": "sha256:" + digest(raw),
            "durationSamples": size,
            "sampleRate": 48000,
            "channels": channels,
            "cacheAssetId": "cache-asset-1",
            "locator": "media/narration.wav",
            "timingHash": "sha256:" + digest(timing),
        }
        row = {
            "blockId": "block-1",
            "narrationAssetId": sid,
            "timingHash": "sha256:" + digest(timing),
            "audioHash": "sha256:" + digest(raw),
            "audio": audio,
        }
        event["provenance"]["timingMapHash"] = row["timingHash"]
        source = {"id": sid, "narrationAudio": audio}
        proof_receipt = trust.seal(
            "narration_preparation",
            {
                "row": row,
                "timingHash": "sha256:" + digest(timing),
                "reviewHash": "sha256:" + digest(review),
                "audioHash": row["audioHash"],
            },
        )
        proof = q.SourceProof(canonical(row), proof_receipt, timing, review)
        pins: dict[str, Any] = {
            "timing": digest(timing),
            "review": digest(review),
            "receipt": digest(proof_receipt),
        }
        start, end = 0, frames * q.FRAME
    else:
        stream_hash = digest(b"original selected stream packed s24le (NOT sidecar)")
        original_start = Fraction((source_start * q.FRAME + q_origin) * rate, 48000)
        original_end = original_start + Fraction(frames * q.FRAME * rate, 48000)
        assert original_start.denominator == original_end.denominator == 1
        event.update(
            {
                "preparationBindingHash": "sha256:" + digest(b"TS canonical binding"),
                "sourceTimeMapping": {
                    "sourceFrameMap": {
                        "sourceAudioStreamMappings": [
                            {"sampleRate": rate, "streamIndex": 1}
                        ]
                    }
                },
                "audio": {
                    "audioPolicy": "quiet" if gain == -18 else "full",
                    "gainDb": gain,
                    "streamIndex": 1,
                    "audioHash": "sha256:" + stream_hash,
                    "sampleRange": {
                        "startFrame": int(original_start),
                        "endFrame": int(original_end),
                    },
                },
            }
        )
        source = {"id": "logical-AV-source"}
        event["provenance"]["sourceId"] = source["id"]
        preparation_binding = {
            "verification": {"deliveredHash": "sha256:" + delivered_hash}
        }
        row = {
            "recordVersion": "authoring-media-preparation/v1",
            "binding": preparation_binding,
            "audio": {
                "contentHash": "sha256:" + digest(raw),
                "sourceAudioHash": "sha256:" + stream_hash,
                "decodedSamples": size,
                "channels": channels,
                "resampledFirstSample": q_origin,
                "probe": {
                    "streams": [{"codec_name": "pcm_s24le", "sample_rate": "48000"}]
                },
            },
        }
        proof_receipt = canonical(row)
        proof = q.SourceProof(proof_receipt, proof_receipt)
        pins = preparation_binding
        start, end = source_start * q.FRAME, (source_start + frames) * q.FRAME
    manifest = {
        "schemaVersion": "timeline-manifest/v2",
        "sources": [source],
        "events": [event],
    }
    blobs = {key: key.encode() for key in r.CONTEXT_HASH_FIELDS}
    blobs["manifestSha256"] = canonical(manifest)
    ctx = context(phase=phase, **{key: digest(value) for key, value in blobs.items()})
    if phase == "rebuild":
        revised = {
            "kind": "revised",
            "bindingSha256": "0" * 64,
            "acceptedDecisionReceiptSha256": digest(b"decision"),
            "revisionLedgerSha256": digest(b"revision ledger"),
            "proposalEvidenceSha256": digest(b"proposal"),
            "revisedDocumentSha256": ctx["executionDocumentSha256"],
            "revisedDependenciesSha256": ctx["executionDependenciesSha256"],
            "revisedManifestSha256": ctx["manifestSha256"],
        }
        ctx = context(
            phase=phase,
            binding=revised,
            **{key: digest(value) for key, value in blobs.items()},
        )
    if kind == "source_audio":
        trust.seals[proof_receipt] = (
            "private_preparation",
            canonical(
                {
                    "context": ctx,
                    "preparationBindingHash": event["preparationBindingHash"],
                    "recordSha256": digest(proof.record),
                    "binding": row["binding"],
                }
            ),
        )
    if native_origin or pcm_origin:
        origin = {
            "schemaVersion": "qualification-output-origin/v1",
            "lane": r.LANE,
            "context": ctx,
            "sourceId": sid,
            "preparationReceiptSha256": digest(proof_receipt),
            "nativeFrameOrigin": native_origin,
            "pcmSampleOrigin": pcm_origin,
        }
        origin_receipt = trust.seal("output_geometry_snapshot", origin)
        origin["receiptSha256"] = digest(origin_receipt)
        proof = replace(
            proof, origin_record=canonical(origin), origin_receipt=origin_receipt
        )
    native_start = native_origin + (start - pcm_origin) // q.FRAME
    delivery = {
        "eventId": eid,
        "kind": kind,
        "recordRange": {"startFrame": 0, "durationFrames": frames},
        "sourceRange": {"startFrame": native_start, "durationFrames": frames},
    }
    mapping = {
        "sourceId": sid,
        "nativeFrameOrigin": native_origin,
        "pcmSampleOrigin": pcm_origin,
        "sourceSampleRate": rate,
        "sampleRate": 48000,
        "resampledFirstSample": q_origin,
        "startSample": start,
        "endSample": end,
        "provenanceRecordSha256": digest(proof.record),
    }
    entry = {
        "sourceId": sid,
        "nativeSourceSha256": native_hash,
        "pcmMode": "wav-direct" if kind == "narration" else "prepared-audio",
        "provenanceReceiptSha256": digest(proof_receipt),
        "provenancePinsSha256": digest(canonical(pins)),
        "deliveryDerivationSha256": digest(canonical(delivery)),
        "pcmFileSha256": digest(raw),
        "decodedSamplesSha256": digest(
            b"".join(struct.pack("<i", x) for x in integers)
        ),
        "originalBitDepth": width * 8,
        "channels": channels,
        "durationSamples": size,
        "sampleRate": 48000,
        "pcmMappingSha256": digest(canonical(mapping)),
        "nativeFrameOrigin": native_origin,
        "pcmSampleOrigin": pcm_origin,
    }
    track = {
        "trackId": "audio-1",
        "kind": "audio",
        "index": 1,
        "name": "Narration",
        "enabled": True,
        "locked": False,
    }
    item = {
        "itemUid": "item-1",
        "eventId": eid,
        "sourceId": sid,
        "mediaUid": "media-1",
        "kind": "audio",
        "trackId": "audio-1",
        "recordStart": 0,
        "recordDuration": frames,
        "sourceStart": native_start,
        "sourceDuration": frames,
        "linkedItemUids": [],
        "online": True,
        "enabled": True,
        "speed": {"numerator": 1, "denominator": 1},
        "sourceMappingSha256": entry["pcmMappingSha256"],
    }
    binding = {
        "schemaVersion": "qualification-output-inputs/v1",
        "lane": r.LANE,
        "context": ctx,
        "delivery": [delivery],
        "sourceEntries": [entry],
        "tracks": [track],
        "itemMappings": [
            {key: item[key] for key in ("itemUid", "eventId", "sourceId", "mediaUid")}
        ],
        "nativeSources": [{"sourceId": sid, "nativeSourceSha256": native_hash}],
    }
    geometry = {
        "context": ctx,
        "extentFrames": frames,
        "rate": q.RATE,
        "tracks": [track],
        "items": [item],
        "sourceMappings": [
            {
                "sourceId": sid,
                "nativeSourceSha256": native_hash,
                "sourceEntrySha256": digest(canonical(entry)),
            }
        ],
    }
    snapshot = {
        "schemaVersion": "qualification-output-geometry/v1",
        "lane": r.LANE,
        "geometry": geometry,
        "inputBindingSha256": digest(canonical(binding)),
        "capturedAt": "2026-10-15T00:59:59Z",
        "expiresAt": "2026-10-15T02:00:00Z",
    }
    receipt = trust.seal("output_geometry_snapshot", snapshot)
    snapshot["receiptSha256"] = digest(receipt)
    inputs = q.PredictionInputs(
        canonical(binding),
        canonical(snapshot),
        receipt,
        blobs,
        {sid: raw},
        {sid: proof},
    )
    return Case(inputs, trust, integers, binding)


def committed(c: Case) -> tuple[bytes, bytes, bytes]:
    predicted = q.create_prediction(c.inputs, trust=c.trust, ledger=[])
    payload = json.loads(predicted.payload)
    receipt = c.trust.seal("output_prediction_commitment", payload)
    return (
        canonical({**payload, "commitmentReceiptSha256": digest(receipt)}),
        receipt,
        predicted.pcm,
    )


def change_items(c: Case, items: list[dict[str, Any]]) -> None:
    c.binding["itemMappings"] = sorted(
        [
            {key: item[key] for key in ("itemUid", "eventId", "sourceId", "mediaUid")}
            for item in items
        ],
        key=lambda x: x["itemUid"],
    )
    snapshot = json.loads(c.inputs.geometry)
    snapshot["geometry"]["items"] = items
    c.inputs = replace(c.inputs, geometry=canonical(snapshot))
    c.capture()


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize(
    "kind,gain", [("narration", 0), ("source_audio", 0), ("source_audio", -18)]
)
def test_independent_exact_prediction_and_recomputation(
    channels: int, kind: str, gain: int
) -> None:
    c = case(channels=channels, kind=kind, gain=gain)
    raw, receipt, pcm = committed(c)
    expected = b"".join(
        struct.pack(
            "<d",
            c.samples[index * channels + (0 if channels == 1 else ch)]
            / 2**23
            * 10 ** (gain / 20),
        )
        for index in range(6 * q.FRAME)
        for ch in range(2)
    )
    assert pcm == expected
    assert q.verify_prediction_commitment(c.inputs, raw, receipt, pcm, trust=c.trust)[
        "predictionBytesSha256"
    ] == digest(expected)
    with pytest.raises(r.OutputConsistencyError, match="recomputation"):
        q.verify_prediction_commitment(
            c.inputs, raw, receipt, pcm[:-1] + b"\0", trust=c.trust
        )


def test_mixer_matches_old_math_in_same_codepoint_segment_order() -> None:
    extent = 3
    sources = {
        sid: [array("d", [0.005 * (index + 1)]) * (extent * q.FRAME)]
        for index, sid in enumerate(["z", "ä", "\ue000", "😀"])
    }
    intent = [
        {
            "sourceId": sid,
            "gainDb": -18 if i % 2 else 0,
            "segments": [
                {
                    "itemUid": f"i-{i}",
                    "recordStart": 0,
                    "sampleStart": 0,
                    "sampleCount": extent * q.FRAME,
                }
            ],
        }
        for i, sid in enumerate(sorted(sources))
    ]
    routes = [
        {
            "sourceId": row["sourceId"],
            "controls": {"gainDb": row["gainDb"]},
            "segments": [
                {
                    "recordStart": 0,
                    "recordEnd": extent,
                    "sourceStart": 0,
                    "sourceEnd": extent,
                }
            ],
        }
        for row in intent
    ]
    old = old_mix(routes, sources, extent)
    assert q._mix(intent, sources, extent) == b"".join(
        struct.pack("<dd", left, right) for left, right in zip(*old, strict=True)
    )


@pytest.mark.parametrize("phase", ["pristine", "rebuild"])
def test_exact_coverage_and_unaligned_narration_refusal(phase: str) -> None:
    c = case(phase=phase)
    assert (
        q.validate_prediction_intent(c.inputs, trust=c.trust)["sources"][0]["gainDb"]
        == 0
    )
    item = json.loads(c.inputs.geometry)["geometry"]["items"][0]
    item.update(recordDuration=5, sourceDuration=5)
    change_items(c, [item])
    with pytest.raises(r.OutputConsistencyError, match="coverage"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])
    unaligned = case(count=6 * q.FRAME - 1, phase=phase)
    with pytest.raises(r.OutputConsistencyError, match="no padding"):
        q.create_prediction(unaligned.inputs, trust=unaligned.trust, ledger=[])


@pytest.mark.parametrize("kind", ["narration", "source_audio"])
def test_edited_split_and_trim_use_event_containment(kind: str) -> None:
    c = case(phase="edited", kind=kind)
    item = json.loads(c.inputs.geometry)["geometry"]["items"][0]
    left = {**item, "recordDuration": 2, "sourceDuration": 2}
    right = {
        **item,
        "itemUid": "item-2",
        "recordStart": 4,
        "recordDuration": 2,
        "sourceStart": 4,
        "sourceDuration": 2,
    }
    change_items(c, [left, right])
    predicted = q.create_prediction(c.inputs, trust=c.trust, ledger=[])
    assert predicted.pcm[2 * q.FRAME * 16 : 4 * q.FRAME * 16] == b"\0" * (
        2 * q.FRAME * 16
    )
    right["sourceStart"] = 5
    change_items(c, [left, right])
    with pytest.raises(r.OutputConsistencyError, match="outside"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])


@pytest.mark.parametrize(
    "rate,frames,start,q_origin", [(48000, 6, 2, 48000), (44100, 80, 80, 48000)]
)
def test_prepared_mapping_differential_with_accepted_oracle(
    rate: int, frames: int, start: int, q_origin: int
) -> None:
    c = case(
        kind="source_audio",
        frames=frames,
        source_start=start,
        rate=rate,
        q_origin=q_origin,
    )
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    event = manifest["events"][0]
    prep = json.loads(next(iter(c.inputs.source_proofs.values())).record)
    oracle = _source_audio_range(
        event,
        _Preparation(
            "key", prep, canonical(prep), digest(canonical(prep)), "receipt.json"
        ),
        Fraction(24000, 1001),
    )
    assert oracle == c.binding["delivery"][0]["sourceRange"]
    raw, receipt, pcm = committed(c)
    assert struct.unpack_from("<d", pcm)[0] == c.samples[start * q.FRAME] / 2**23
    q.verify_prediction_commitment(c.inputs, raw, receipt, pcm, trust=c.trust)


def test_nonzero_authenticated_native_and_pcm_origin() -> None:
    c = case(
        kind="source_audio", source_start=2, native_origin=100, pcm_origin=2 * q.FRAME
    )
    raw, receipt, pcm = committed(c)
    assert struct.unpack_from("<d", pcm)[0] == c.samples[2 * q.FRAME] / 2**23
    q.verify_prediction_commitment(c.inputs, raw, receipt, pcm, trust=c.trust)
    proofs = dict(c.inputs.source_proofs)
    sid = next(iter(proofs))
    proofs[sid] = replace(proofs[sid], origin_record=None, origin_receipt=None)
    with pytest.raises(r.OutputConsistencyError):
        q.create_prediction(
            replace(c.inputs, source_proofs=proofs), trust=c.trust, ledger=[]
        )


@pytest.mark.parametrize(
    "field",
    ["provenanceReceiptSha256", "provenancePinsSha256", "deliveryDerivationSha256"],
)
def test_null_provenance_refuses(field: str) -> None:
    c = case()
    c.binding["sourceEntries"][0][field] = None
    c.capture()
    with pytest.raises(r.OutputConsistencyError):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])


def test_forged_mutually_matching_inputs_do_not_authenticate() -> None:
    c = case()
    raw = json.loads(c.inputs.geometry)
    raw["geometry"]["items"][0]["recordDuration"] -= 1
    with pytest.raises(r.OutputConsistencyError, match="authentication"):
        q.create_prediction(
            replace(c.inputs, geometry=canonical(raw)), trust=c.trust, ledger=[]
        )
    blobs = dict(c.inputs.blobs)
    blobs["originalDependenciesSha256"] = b"substitution"
    with pytest.raises(r.OutputConsistencyError, match="current"):
        q.create_prediction(replace(c.inputs, blobs=blobs), trust=c.trust, ledger=[])


def test_wrong_lane_legacy_and_arbitrary_control_keys_refuse() -> None:
    c = case()
    for key, value in [
        ("lane", "strict"),
        ("schemaVersion", "native_observation/v1"),
        ("controls", {}),
    ]:
        row = json.loads(c.inputs.geometry)
        row[key] = value
        with pytest.raises(r.OutputConsistencyError):
            q.create_prediction(
                replace(c.inputs, geometry=canonical(row)), trust=c.trust, ledger=[]
            )


def test_source_stream_hash_is_not_sidecar_or_int32_hash() -> None:
    c = case(kind="source_audio")
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    source = c.binding["sourceEntries"][0]
    stream = manifest["events"][0]["audio"]["audioHash"]
    assert stream not in {
        "sha256:" + source["pcmFileSha256"],
        "sha256:" + source["decodedSamplesSha256"],
    }
    assert q.create_prediction(c.inputs, trust=c.trust, ledger=[]).pcm


@pytest.mark.parametrize("kind", ["narration", "source_audio"])
def test_native_identity_and_narration_origin_match_actual_package_view(
    kind: str,
) -> None:
    c = case(kind=kind, source_start=2 if kind == "source_audio" else 0)
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    event = manifest["events"][0]
    event["audio"] = event.get("audio")
    manifest.update(
        timeline={"frameRate": q.RATE},
        tracks=[
            {"id": track["trackId"], "kind": track["kind"]}
            for track in c.binding["tracks"]
        ],
        composition={},
    )
    source = c.binding["sourceEntries"][0]
    key = (
        f"event:{event['eventId']}"
        if kind == "source_audio"
        else f"source:{source['sourceId']}"
    )
    artifact = _InputArtifact(
        key,
        Path("audio.wav"),
        "media/audio.wav",
        "sha256:" + source["pcmFileSha256"],
        "audio",
    )
    prepared = {}
    if kind == "source_audio":
        record = json.loads(c.inputs.source_proofs[source["sourceId"]].record)
        event["preparationBindingHash"] = _compiler_hash(record["binding"])
        prepared["key"] = _Preparation(
            "key", record, canonical(record), digest(canonical(record)), "receipt.json"
        )
    view = _delivery_view(manifest, {}, prepared, {key: artifact}, validate=False)
    actual = view["events"][0]
    assert actual["sourceId"] == source["sourceId"]
    assert view["sources"][0]["contentHash"] == "sha256:" + source["nativeSourceSha256"]
    assert {
        "eventId": actual["id"],
        "kind": actual["kind"],
        "recordRange": actual["recordRange"],
        "sourceRange": actual["sourceRange"],
    } == c.binding["delivery"][0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("durationSamples", 959),
        ("durationSamples", 16_000_001),
        ("channels", True),
        ("nativeFrameOrigin", -1),
        ("sampleRate", 44100),
    ],
)
def test_source_scalar_bounds(field: str, value: Any) -> None:
    c = case()
    c.binding["sourceEntries"][0][field] = value
    with pytest.raises(r.OutputConsistencyError):
        r._sources(c.binding["sourceEntries"])


def test_pcm16_promotion_has_separate_raw_and_int32_hashes() -> None:
    c = case(width=2)
    source = c.binding["sourceEntries"][0]
    values, channels = q._pcm(next(iter(c.inputs.source_wavs.values())), source)
    assert list(values) == c.samples
    assert channels[0][0] == c.samples[0] / 2**23
    assert source["decodedSamplesSha256"] != source["pcmFileSha256"]


def test_overlap_speed_order_unknown_items_and_no_policy_refuse() -> None:
    for change in ("overlap", "speed", "order", "unknown", "disabled"):
        c = case(phase="edited")
        item = json.loads(c.inputs.geometry)["geometry"]["items"][0]
        items = [item]
        if change == "overlap":
            item.update(recordDuration=2, sourceDuration=2)
            items.append({**item, "itemUid": "item-2", "recordStart": 3})
        elif change == "speed":
            item["speed"] = {"numerator": True, "denominator": 1}
        elif change == "order":
            item.update(recordDuration=2, sourceDuration=2)
            items = [
                {**item, "itemUid": "item-2", "recordStart": 4, "sourceStart": 4},
                item,
            ]
        elif change == "unknown":
            item["eventId"] = "unknown"
        else:
            item["enabled"] = False
        change_items(c, items)
        with pytest.raises(r.OutputConsistencyError):
            q.create_prediction(c.inputs, trust=c.trust, ledger=[])
    c = case(kind="source_audio", gain=-9)
    with pytest.raises(r.OutputConsistencyError, match="gain"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])


def test_static_compiler_no_and_narration_semantics_remain_pinned() -> None:
    compiler = Path("packages/contracts/src/compiler-core-v2.ts").read_text()
    assert 'if (payload.audioPolicy !== "mute" && isClip)' in compiler
    assert 'gainDb = policy === "quiet"' in compiler
    assert 'kind: "narration"' in compiler and 'kind: "source_audio"' in compiler
    # Pin the real accepted semantic source, not a fabricated source policy enum.
    assert "audioPolicy" in compiler

    c = case()
    row = json.loads(next(iter(c.inputs.source_proofs.values())).record)
    assert set(row["audio"]) == deps_schema.NarrationAudioBindingV2.__required_keys__


def test_raw_alias_source_and_aggregate_bounds() -> None:
    c = case()
    first = c.binding["sourceEntries"][0]
    duplicate = {**first, "sourceId": "source-😀"}
    with pytest.raises(r.OutputConsistencyError, match="alias"):
        r._sources([first, duplicate])
    extra = {**duplicate, "nativeSourceSha256": "a" * 64}
    huge = [{**first, "channels": 2, "durationSamples": 16_000_000}, extra]
    with pytest.raises(r.OutputConsistencyError, match="aggregate"):
        r._sources(huge)
    with pytest.raises(r.OutputConsistencyError, match="inventory"):
        r._sources([first] * 17)


def test_decoded_channel_alias_refuses_even_if_wav_file_hashes_differ() -> None:
    a = case(source_id="source-a", event_id="event-a")
    b = case(source_id="source-b", event_id="event-b", trailer=b"JUNK\0\0\0\0")
    a.trust.seals.update(b.trust.seals)
    manifest = json.loads(a.inputs.blobs["manifestSha256"])
    other = json.loads(b.inputs.blobs["manifestSha256"])
    other["events"][0]["trackId"] = "audio-2"
    manifest["sources"] += other["sources"]
    manifest["events"] += other["events"]
    blobs = dict(a.inputs.blobs)
    blobs["manifestSha256"] = canonical(manifest)
    ctx = context(**{key: digest(raw) for key, raw in blobs.items()})
    for key in ("sourceEntries", "nativeSources", "delivery", "itemMappings"):
        a.binding[key] += b.binding[key]
    a.binding["itemMappings"][1]["itemUid"] = "item-2"
    a.binding["tracks"].append(
        {**a.binding["tracks"][0], "trackId": "audio-2", "index": 2}
    )
    a.binding["context"] = ctx
    snapshot = json.loads(a.inputs.geometry)
    second = json.loads(b.inputs.geometry)["geometry"]["items"][0]
    second.update(itemUid="item-2", trackId="audio-2")
    snapshot["geometry"].update(
        context=ctx,
        items=[snapshot["geometry"]["items"][0], second],
        tracks=a.binding["tracks"],
        sourceMappings=[
            {
                "sourceId": source["sourceId"],
                "nativeSourceSha256": source["nativeSourceSha256"],
                "sourceEntrySha256": digest(canonical(source)),
            }
            for source in a.binding["sourceEntries"]
        ],
    )
    a.inputs = replace(
        a.inputs,
        geometry=canonical(snapshot),
        blobs=blobs,
        source_wavs={**a.inputs.source_wavs, **b.inputs.source_wavs},
        source_proofs={**a.inputs.source_proofs, **b.inputs.source_proofs},
    )
    a.capture()
    with pytest.raises(r.OutputConsistencyError, match="decoded-channel"):
        q.create_prediction(a.inputs, trust=a.trust, ledger=[])


def test_prediction_clipping_and_geometry_extent_bounds() -> None:
    signal = array("d", [0.75]) * q.FRAME
    sources = {"a": [signal], "b": [signal]}
    intent = [
        {
            "sourceId": sid,
            "gainDb": 0,
            "segments": [{"recordStart": 0, "sampleStart": 0, "sampleCount": q.FRAME}],
        }
        for sid in sources
    ]
    with pytest.raises(r.OutputConsistencyError, match="clipping"):
        q._mix(intent, sources, 1)
    c = case()
    snapshot = json.loads(c.inputs.geometry)
    snapshot["geometry"]["extentFrames"] = 1499
    c.inputs = replace(c.inputs, geometry=canonical(snapshot))
    c.reseal_geometry()
    with pytest.raises(r.OutputConsistencyError, match="integer"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])
